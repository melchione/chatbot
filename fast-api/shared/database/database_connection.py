from surrealdb import AsyncSurreal
import os
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class DatabaseConnection:
    def __init__(self):
        self._db = None

    @classmethod
    async def get_instance(cls, db_namespace: str = None, db_database: str = None):
        """
        Get a database connection instance.
        """
        instance = cls()
        await instance._initialize(db_namespace, db_database)
        # Return the Surreal DB client directly
        return instance._db

    @classmethod
    async def close_instance(cls, db):
        """Close a specific database connection."""
        if db is not None:
            await db.close()
            logger.debug("SurrealDB connection closed.")

    async def _initialize(self, _db_namespace: str, _db_database: str):
        db_host = os.getenv("DB_HOST", "center-code-surrealdb-1")
        db_port = os.getenv("DB_PORT", "8000")
        # Assuming WSS is correct, adjust if needed (e.g., ws:// for non-TLS)
        db_url = os.getenv("DB_URL", f"ws://{db_host}:{db_port}/rpc")
        db_user = os.getenv("DB_USER", "admin")
        db_pass = os.getenv("DB_PASSWORD", "password")
        db_namespace = _db_namespace or os.getenv("DB_NAMESPACE", "main")
        db_database = _db_database or os.getenv("DB_NAME", "af")

        logger.debug(f"Attempting to connect to SurrealDB at {db_url}")

        try:
            # Explicitly instantiate, connect, and await, despite deprecation warnings
            # This seems necessary to avoid the TypeError on subsequent awaits
            db = AsyncSurreal(db_url)
            # Await signin with credentials only
            await db.signin({"username": db_user, "password": db_pass})
            logger.debug(f"Signin successful for user {db_user}")

            # Await use namespace and database AFTER signin
            await db.use(db_namespace, db_database)
            logger.debug(f"Using namespace '{db_namespace}', database '{db_database}'")

            self._db = db
            logger.debug(f"Connection setup complete.")

        except Exception as e:
            logger.error(f"Connection initialization failed: {str(e)}", exc_info=True)
            self._db = None
            raise
