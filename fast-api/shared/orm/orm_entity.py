import json
import os
import re
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from surrealdb import RecordID
import uuid
import logging
import datetime

from shared.database.database_connection import DatabaseConnection
from unidecode import unidecode

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


def _serialize_for_db(obj):
    pattern = r"^[a-zA-Z0-9]+:[a-zA-Z0-9]+$"
    if isinstance(obj, OrmEntity):
        # Si c'est une instance OrmEntity, retourne son ID string.
        id = obj.id
        if isinstance(id, RecordID):
            return str(id)
        else:
            return RecordID(id.split(":")[0], id.split(":")[1])
    elif isinstance(obj, BaseModel):
        return obj.model_dump()
    elif isinstance(obj, str) and bool(re.match(pattern, obj)):
        # Si c'est une chaîne qui ressemble à un RecordID, la convertir.
        try:
            return RecordID(obj.split(":")[0], obj.split(":")[1])
        except Exception:
            return obj  # Conserve la chaîne originale si le format est invalide
    elif isinstance(obj, dict):
        # Traite récursivement les valeurs du dictionnaire.
        return {k: _serialize_for_db(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        # Traite récursivement les éléments de la liste.
        return [_serialize_for_db(item) for item in obj]
    # Conserve les autres types (int, float, bool, None, datetime) pour l'instant.
    return obj


class OrmEntity(BaseModel):
    id: Optional[str] = None
    db_namespace: Optional[str] = Field(default=None)
    db_database: Optional[str] = Field(default=None)

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self, db_database: str | None = None, db_namespace: str | None = None, **data
    ):
        super().__init__(**data)
        self.db_namespace = db_namespace
        self.db_database = db_database

    async def get_db(self):
        try:
            db = await DatabaseConnection.get_instance(
                self.db_namespace, self.db_database
            )
        except Exception as e:
            print(f"[ERROR] Database connection failed: {str(e)}")
        return db

    @staticmethod
    async def close_db(db):
        try:
            await DatabaseConnection.close_instance(db)
        except Exception as e:
            print(f"[ERROR] Database connection failed: {str(e)}")
        return db

    async def save(self, chosen_id: Optional[str] = None):
        db = await self.get_db()

        try:
            if self.id is not None:
                await self._update_existing(db)
            else:
                await self._create_new(db, chosen_id)

            return self
        except Exception as e:
            logger.error(f"Save operation failed: {str(e)}", e)
        finally:
            await DatabaseConnection.close_instance(db)

    async def update(self, new_values: dict):
        db = await self.get_db()

        try:
            new_values = convert_datetime(new_values)
            await self.update_record(db, self.id, new_values)
        except Exception as e:
            print(f"Failed to update record: {str(e)}")
        finally:
            await DatabaseConnection.close_instance(db)

    async def _update_existing(self, db):
        try:
            result = await db.update(self.id, self.to_json())
            if not result:
                raise Exception(f"No document found matching record: {self.id}")
            return result
        except Exception as e:
            print(f"Failed to update document: {str(e)}")

    async def _create_new(self, db, id: Optional[str] = None):
        try:
            table_name = f"{self.__class__.__name__.lower()}s"
            model_dumped = self.to_json()
            if id:
                model_dumped["id"] = unidecode(id)
            else:
                if "id" in model_dumped:
                    del model_dumped["id"]
            result = await OrmEntity.insert_record(db, table_name, model_dumped)
            self.id = f"{self.__class__.__name__.lower()}s:{result['id'].id}"
        except Exception as e:
            print(f"Failed to create new document: {str(e)}")

    @staticmethod
    async def update_record(db, record: str, new_values: dict):
        try:
            sql_query = f"UPSERT {record} MERGE {new_values}"
            # Execute query with parameters
            result = await db.query(sql_query)

            if not result:
                raise Exception(f"No document found matching record: {record}")
            return result
        except Exception as e:
            print(f"Document update failed: {str(e)}")

    @staticmethod
    async def insert_record(db, table_name: str, record: dict):
        try:
            result = await db.create(table_name, record)
            if not result:
                raise Exception("Document creation failed")
            return result
        except Exception as e:
            print(f"Document insertion failed: {str(e)}")

    def to_dict(self):
        data = self.model_dump()
        return json.loads(json.dumps(data, cls=UUIDEncoder))

    def to_json(self) -> dict:
        """Convertit l'objet en dictionnaire prêt pour SurrealDB.

        1. On construit un dict *sans* passer par ``model_dump`` afin de
            conserver
            `les sous-instances `OrmEntity` (pydantic convertirait en
            dict et on perdrait l'info de type).
        2. On délègue à ``_serialize_for_db`` la conversion vers les `id`.
        3. On retire les champs internes (db_*) et les valeurs nulles.
        """

        # Étape 1 – copie brute des champs définis dans le modèle
        raw_data = {field: getattr(self, field) for field in self.model_fields}

        # Étape 2 – serialisation récursive
        data = _serialize_for_db(raw_data)

        # Étape 3 – nettoyage
        data = remove_db_fields(data)
        data = remove_none_fields(data)

        return data

    def get_feature_folder_name(self) -> str:
        """
        Get the folder name two steps up from the repository of the table.
        """
        current_file_path = os.path.abspath(
            self.__class__.__module__.replace(".", "/") + ".py"
        )
        two_steps_up = os.path.dirname(
            os.path.dirname(os.path.dirname(current_file_path))
        )
        folder_name = os.path.basename(two_steps_up)
        return folder_name

    def get_namespace_folder_name(self) -> str:
        """
        Get the folder name two steps up from the repository of the table.
        """
        return self.get_feature_folder_name()


def remove_db_fields(data):
    return {k: v for k, v in data.items() if not k.startswith("db_")}


def remove_none_fields(obj):
    if isinstance(obj, dict):
        return {k: remove_none_fields(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [remove_none_fields(item) for item in obj if item is not None]
    return obj


def convert_datetime(obj):
    if isinstance(obj, datetime.datetime):
        return f"d\"{obj.strftime('%Y-%m-%dT%H:%M:%SZ')}\""
    elif isinstance(obj, dict):
        return {k: convert_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime(item) for item in obj]
    return obj
