from typing import Any, Optional, List
from surrealdb import RecordID
import importlib
import logging
import random
import os
from shared.database.database_connection import DatabaseConnection
from shared.orm.orm_entity import OrmEntity

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OrmRepository:
    """
    OrmRepository Class for SurrealDB

    This class provides a set of methods to interact with a SurrealDB database.
    """

    table_name: str
    entity_name: str
    db_namespace: str
    db_database: str

    def __init__(self, db_namespace: str | None = None, db_database: str | None = None):
        """
        Initialize the OrmRepository instance.
        """
        self.entity_name = self.__class__.__name__.replace("Repository", "")
        self.table_name = self.__class__.__name__.lower().replace("repository", "s")
        self.db_namespace = db_namespace
        self.db_database = db_database

    def get_record_id(self, _id: Any) -> RecordID:
        """
        Get the record id.
        """
        record_id = _id
        if isinstance(_id, OrmEntity) and _id.id:
            record_id = _id.id

        if isinstance(record_id, RecordID):
            return record_id
        elif isinstance(record_id, str):
            if not record_id.__contains__(":"):
                record_id = self.table_name + ":" + record_id
            exploded_id = record_id.split(":")
            return RecordID(exploded_id[0], exploded_id[1])

        return record_id

    async def get_db(self):
        """
        Get the database connection.
        """
        try:
            return await DatabaseConnection.get_instance(
                db_namespace=self.db_namespace, db_database=self.db_database
            )
        except Exception as e:
            print(f"[ERROR] Database connection failed: {str(e)}")

    @staticmethod
    async def close_db(db):
        try:
            await DatabaseConnection.close_instance(db)
        except Exception as e:
            print(f"Database close failed: {str(e)}")
        return db

    async def get_by_id(self, _id: RecordID | str) -> Any:
        """
        Get one record by its unique identifier.

        :param _id: The unique identifier of the record
        :return: The found record as an entity instance or None
        """
        db = await self.get_db()

        def est_entier(chaine):
            try:
                int(chaine)
                return True
            except ValueError:
                return False

        try:
            if isinstance(_id, RecordID):
                record_id = _id
            else:
                if not _id.__contains__(":"):
                    _id = self.table_name + ":" + _id
                exploded_id = _id.split(":")

                if est_entier(exploded_id[1]):
                    record_id = RecordID(exploded_id[0], int(exploded_id[1]))
                else:
                    record_id = RecordID(exploded_id[0], exploded_id[1])

            response = await db.select(record_id)

            if response:
                return self._to_instance(response)

        except Exception as e:
            logger.error(f"Error in get_one_by_id: {str(e)}", e)

        finally:
            await db.close()

    def _to_instance(self, result: dict) -> Any:
        """
        Convert a dictionary result to an entity instance.
        """
        if self.entity_name is None:
            raise AttributeError(
                f"Class {self.__class__.__name__} does not have an entity_name attribute."
            )

        try:
            module = importlib.import_module(
                f"shared.orm.entities.{self.entity_name.lower()}"
            )
            class_ = getattr(module, self.entity_name)

            # Convert any RecordID fields to string format 'table:id'
            processed_result = {}
            # Get the defined fields for the Pydantic model
            model_fields = getattr(
                class_, "model_fields", getattr(class_, "__fields__", None)
            )

            if model_fields is None:
                # Fallback or error handling if fields attribute is not found
                print(
                    f"Warning: Could not determine fields for class {class_.__name__}."
                )  # Or raise an error
                model_fields = (
                    {}
                )  # Assign empty dict to avoid further errors, or handle differently

            for key, value in result.items():
                # Check if the key exists in the defined model fields
                if key in model_fields:
                    if isinstance(value, RecordID):
                        # Assuming RecordID has attributes 'tb' and 'id'
                        # Adjust if the attributes are named differently (e.g., table_name, record_id)
                        processed_result[key] = f"{value.table_name}:{value.id}"
                    else:
                        processed_result[key] = value

            return class_(**processed_result)
        except Exception as e:
            print(f"An error occurred while creating the instance: {e}")

    async def find_one_record(self, query: Optional[dict] = None) -> Optional[Any]:
        """
        Find a single record in the collection.

        :param query: The query to find the record
        :return: The found record as an entity instance or None
        """
        db = await self.get_db()
        try:
            if query is None:
                query = {}

            # Convert query to SurrealQL
            where_clause = " AND ".join([f"{k} = ${k}" for k in query.keys()])
            sql_query = f"SELECT * FROM {self.table_name}"
            if where_clause:
                sql_query += f" WHERE {where_clause}"
            sql_query += " LIMIT 1"

            # Execute query with parameters
            result = await db.query(sql_query, query)

            if (
                result
                and len(result) > 0
                and result[0]
                and len(result[0]["result"]) > 0
            ):
                return self._to_instance(result[0]["result"][0])
            return None

        except Exception as e:
            logger.error(f"Error in find_one_record: {str(e)}", e)
        finally:
            await DatabaseConnection.close_instance(db)
            pass

    async def update_record(self, query: dict, new_values: dict) -> Any:
        """
        Update a record in the collection.

        :param query: The query to find the record to update
        :param new_values: The new values to set
        :return: The updated record
        """
        db = await self.get_db()

        try:
            # Convert query to SurrealQL WHERE clause
            where_clause = " AND ".join([f"{k} = ${k}" for k in query.keys()])

            # Create UPDATE statement
            update_clause = ", ".join([f"{k} = ${k}" for k in new_values.keys()])

            # Combine parameters
            params = {**query, **new_values}

            # Create full query
            sql_query = f"UPDATE {self.table_name} SET {update_clause} WHERE {where_clause} RETURN AFTER"

            result = await db.query(sql_query, params)

            if result and len(result) > 0 and result[0]:
                return self._to_instance(result[0][0])
            return None

        except Exception as e:
            logger.error(f"Error in update_record: {str(e)}", e)
        finally:
            await DatabaseConnection.close_instance(db)
            pass

    async def delete_record(self, query: dict) -> bool:
        """
        Delete a record from the collection.

        :param query: The query to find the record to delete
        :return: True if record was deleted, False otherwise
        """
        db = await self.get_db()

        try:
            # Convert query to SurrealQL WHERE clause
            where_clause = " AND ".join([f"{k} = ${k}" for k in query.keys()])

            # Create DELETE statement
            sql_query = f"DELETE FROM {self.table_name} WHERE {where_clause}"

            result = await db.query(sql_query, query)

            return bool(result and len(result) > 0)

        except Exception as e:
            logger.error(f"Error in delete_record: {str(e)}", e)
        finally:
            await DatabaseConnection.close_instance(db)
            pass

    async def find_records(
        self,
        query: Optional[dict] = None,
        sort: Optional[List[tuple]] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> List[Any]:
        """
        Find records in the collection with MongoDB-style query operators.

        :param query: The query to filter records using MongoDB-style operators
            Supported operators:
            - $eq: Equal to
            - $ne: Not equal to
            - $gt: Greater than
            - $gte: Greater than or equal to
            - $lt: Less than
            - $lte: Less than or equal to
            - $in: In array
            - $nin: Not in array
            - $and: Logical AND
            - $or: Logical OR
            - $like: Pattern matching (SQL LIKE)
            - $regex: Regular expression matching
        :param sort: List of tuples (field, direction) to sort by
        :param limit: Maximum number of records to return
        :param skip: Number of records to skip
        :return: List of entity instances

        Example:
            query = {
                "age": {"$gt": 18, "$lt": 65},
                "status": {"$in": ["active", "pending"]},
                "$or": [
                    {"country": "US"},
                    {"premium": True}
                ]
            }
            sort = [("created_at", -1), ("name", 1)]
            records = await repo.find_records(query, sort, limit=10, skip=0)
        """
        db = await self.get_db()
        try:
            params = {}

            def build_condition(
                field: str, operator: str, value: Any, param_count: int
            ) -> tuple[str, dict]:
                """Build a WHERE condition for a given operator"""
                param_name = f"{field}_{param_count}"
                operator_map = {
                    "$eq": "=",
                    "$ne": "!=",
                    "$gt": ">",
                    "$gte": ">=",
                    "$lt": "<",
                    "$lte": "<=",
                    "$in": "INSIDE",
                    "$nin": "NOT INSIDE",
                    "$like": "LIKE",
                    "$regex": "=~",
                }

                if operator in operator_map:
                    params[param_name] = value
                    return f"{field} {operator_map[operator]} ${param_name}", params
                return "", params

            def process_query(q: dict, param_count: int = 0) -> tuple[str, int]:
                """Recursively process query dictionary to build WHERE clause"""
                conditions = []

                for key, value in q.items():
                    if key == "$or" and isinstance(value, list):
                        or_conditions = []
                        for item in value:
                            condition, param_count = process_query(item, param_count)
                            if condition:
                                or_conditions.append(f"({condition})")
                        if or_conditions:
                            conditions.append(f"({' OR '.join(or_conditions)})")

                    elif key == "$and" and isinstance(value, list):
                        and_conditions = []
                        for item in value:
                            condition, param_count = process_query(item, param_count)
                            if condition:
                                and_conditions.append(f"({condition})")
                        if and_conditions:
                            conditions.append(f"({' AND '.join(and_conditions)})")

                    elif isinstance(value, dict):
                        field_conditions = []
                        for op, val in value.items():
                            condition, _ = build_condition(key, op, val, param_count)
                            if condition:
                                field_conditions.append(condition)
                                param_count += 1
                        if field_conditions:
                            conditions.append(f"({' AND '.join(field_conditions)})")

                    else:
                        # Handle direct equality
                        condition, _ = build_condition(key, "$eq", value, param_count)
                        if condition:
                            conditions.append(condition)
                            param_count += 1

                return " AND ".join(conditions), param_count

            # Start building the query
            sql_query = f"SELECT * FROM {self.table_name}"

            # Add WHERE clause if query provided
            if query:
                where_clause, _ = process_query(query)
                if where_clause:
                    sql_query += f" WHERE {where_clause}"

            # Add ORDER BY clause if sort provided
            if sort:
                order_clause = ", ".join(
                    [
                        f"{field} {('ASC' if direction > 0 else 'DESC')}"
                        for field, direction in sort
                    ]
                )
                sql_query += f" ORDER BY {order_clause}"

            # Add LIMIT and START if provided
            if limit is not None:
                sql_query += f" LIMIT {limit}"
            if skip is not None:
                sql_query += f" START {skip}"

            logger.debug(f"Executing query: {sql_query}")
            logger.debug(f"With parameters: {params}")

            result = await db.query(sql_query, params)

            if result and len(result) > 0:
                return [self._to_instance(doc) for doc in result]
            return []

        except Exception as e:
            logger.error(f"Error in find_records: {str(e)}", e)
        finally:
            await DatabaseConnection.close_instance(db)
            pass

    async def find_all_records(self) -> List[Any]:
        """
        Find all records in the collection.

        :return: List of all records as entity instances
        """
        db = await self.get_db()
        try:
            sql_query = f"SELECT * FROM {self.table_name}"
            result = await db.query(sql_query)

            if result and len(result) > 0:
                return [self._to_instance(doc) for doc in result]
            return []
        except Exception as e:
            logger.error(f"Error in find_all_records: {str(e)}", e)
        finally:
            await DatabaseConnection.close_instance(db)
            pass

    async def count_records(self, query: Optional[dict] = None) -> int:
        """
        Count records in the collection.

        :param query: The query to filter records to count
        :return: Number of matching records
        """
        db = await self.get_db()
        try:
            sql_query = f"SELECT count() FROM {self.table_name}"

            if query:
                where_clause = " AND ".join([f"{k} = ${k}" for k in query.keys()])
                sql_query += f" WHERE {where_clause}"

            result = await db.query(sql_query, query or {})

            if result and len(result) > 0 and result[0]:
                return result[0][0]["count"]
            return 0

        except Exception as e:
            logger.error(f"Error in count_records: {str(e)}", e)
        finally:
            await DatabaseConnection.close_instance(db)
            pass

    async def create_record(self, record: dict) -> Any:
        """
        Create a new record in the collection.

        :param record: The record to create
        :return: The created record as an entity instance
        """
        db = await self.get_db()
        try:
            result = await db.create(self.table_name, record)

            if result and len(result) > 0:
                return self._to_instance(result[0])
            return None

        except Exception as e:
            logger.error(f"Error in create_record: {str(e)}", e)
        finally:
            await DatabaseConnection.close_instance(db)
            pass

    async def find_one_random(self, query: Optional[dict] = None) -> Optional[Any]:
        """
        Find a random record in the collection that matches the optional query.

        :param query: Optional dictionary containing filter conditions
        :type query: Optional[dict]
        :return: A random record as an entity instance that matches the query
        :rtype: Optional[Any]
        """
        db = await self.get_db()
        try:
            params = {}

            def build_where_clause(q: dict) -> str:
                """Build WHERE clause for the query"""
                where_conditions = []
                for key, value in q.items():
                    param_name = f"param_{key}"
                    if isinstance(value, dict):
                        if "$in" in value:
                            # Handle array containment - value INSIDE array_field
                            params[param_name] = key  # The value we're searching for
                            where_conditions.append(
                                f"${param_name} INSIDE {value['$in']}"
                            )
                        elif "$contains" in value:
                            # Handle array contains - value INSIDE array_field
                            params[param_name] = value["$contains"]
                            where_conditions.append(f"${param_name} INSIDE {key}")
                        else:
                            # Handle other operators
                            for op, val in value.items():
                                operator = {
                                    "$eq": "=",
                                    "$ne": "!=",
                                    "$gt": ">",
                                    "$gte": ">=",
                                    "$lt": "<",
                                    "$lte": "<=",
                                }.get(op)
                                if operator:
                                    params[f"{param_name}_{op}"] = val
                                    where_conditions.append(
                                        f"{key} {operator} ${param_name}_{op}"
                                    )
                    else:
                        # Handle direct equality
                        params[param_name] = value
                        where_conditions.append(f"{key} = ${param_name}")

                return " AND ".join(where_conditions) if where_conditions else ""

            # Start building the query
            sql_query = f"SELECT * FROM {self.table_name}"

            # Add WHERE clause if query is provided
            if query:
                where_clause = build_where_clause(
                    dict(query)
                )  # Create a copy of the dictionary
                if where_clause:
                    sql_query += f" WHERE {where_clause}"

            # Add random ordering and limit
            logger.debug(f"Executing query: {sql_query}")
            logger.debug(f"With parameters: {params}")

            result = await db.query(sql_query, params)

            if result and len(result) > 0:
                return self._to_instance(random.choice(result))
            return None

        except Exception as e:
            logger.error(f"Error in find_one_random: {str(e)}", e)
        finally:
            await DatabaseConnection.close_instance(db)
            pass

    async def drop_collection(self) -> None:
        """
        Remove all records from the collection.
        """
        db = await self.get_db()
        try:
            await db.query(f"DELETE FROM {self.table_name}")
        except Exception as e:
            logger.error(f"Error in drop_collection: {str(e)}", e)
        finally:
            await DatabaseConnection.close_instance(db)
            pass

    # keep old methods for backward compatibility
    async def find_one_document(self, query: Optional[dict] = None) -> Optional[Any]:
        return await self.find_one_record(query)

    async def find_documents(self, query: Optional[dict] = None) -> List[Any]:
        return await self.find_records(query)
