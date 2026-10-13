"""
Asynchronous MongoDB Repository for Disease Forecasting demo users.

Provides CRUD operations on the isolated 'demo_users' collection.
Enforces strict synthetic data isolation, string normalization, and error sanitization.
"""

from typing import Optional, Any, Dict
from backend.components.demo_auth.models import DemoUserDocument


class DemoUserRepositoryError(ValueError):
    """Sanitized exception for demo user repository failures."""
    pass


class DemoUserDuplicateError(DemoUserRepositoryError):
    """Sanitized exception when attempting to insert or replace a duplicate user."""
    pass


class DemoUserRepository:
    """
    Asynchronous MongoDB repository for temporary synthetic demo users.
    Operates on the 'demo_users' collection using a supplied database instance.
    """

    COLLECTION_NAME = "demo_users"

    def __init__(self, db: Any):
        if db is None:
            raise DemoUserRepositoryError("Database instance is required.")
        self._db = db
        self._collection = db[self.COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        """
        Creates stable unique indexes for userId and loginName, and an index for enabled status.
        """
        try:
            await self._collection.create_index(
                [("userId", 1)],
                unique=True,
                name="idx_demo_users_user_id_unique",
            )
            await self._collection.create_index(
                [("loginName", 1)],
                unique=True,
                name="idx_demo_users_login_name_unique",
            )
            await self._collection.create_index(
                [("enabled", 1)],
                name="idx_demo_users_enabled",
            )
        except Exception as exc:
            raise DemoUserRepositoryError(f"Failed to ensure indexes: {exc.__class__.__name__}") from None

    async def find_by_login_name(self, login_name: str) -> Optional[DemoUserDocument]:
        """
        Finds a demo user by loginName.
        Normalizes loginName (trim, lowercase) and enforces synthetic markers in the query filter.
        """
        if not isinstance(login_name, str) or not login_name.strip():
            raise DemoUserRepositoryError("Invalid loginName: Must be a non-empty string.")

        clean_login = login_name.strip().lower()

        query_filter = {
            "loginName": clean_login,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }

        try:
            doc = await self._collection.find_one(query_filter)
        except Exception as exc:
            raise DemoUserRepositoryError(f"Database query error ({exc.__class__.__name__})") from None

        if doc is None:
            return None

        return self._to_user_document(doc)

    async def find_by_user_id(self, user_id: str) -> Optional[DemoUserDocument]:
        """
        Finds a demo user by userId.
        Enforces userId prefix 'DEMO_USER_' and synthetic markers in the query filter.
        """
        if not isinstance(user_id, str) or not user_id.startswith("DEMO_USER_") or not user_id.strip():
            raise DemoUserRepositoryError("Invalid userId: Must be a non-empty string starting with 'DEMO_USER_'.")

        clean_user_id = user_id.strip()

        query_filter = {
            "userId": clean_user_id,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }

        try:
            doc = await self._collection.find_one(query_filter)
        except Exception as exc:
            raise DemoUserRepositoryError(f"Database query error ({exc.__class__.__name__})") from None

        if doc is None:
            return None

        return self._to_user_document(doc)

    async def insert_user(self, user: DemoUserDocument) -> DemoUserDocument:
        """
        Inserts a new synthetic demo user document into MongoDB.
        """
        if not isinstance(user, DemoUserDocument):
            raise DemoUserRepositoryError("User must be a valid DemoUserDocument instance.")

        doc = user.model_dump()

        try:
            await self._collection.insert_one(doc)
            return user
        except Exception as exc:
            if "duplicate" in str(exc).lower() or exc.__class__.__name__ == "DuplicateKeyError":
                raise DemoUserDuplicateError("User with this userId or loginName already exists.") from None
            raise DemoUserRepositoryError(f"Failed to insert demo user ({exc.__class__.__name__})") from None

    async def replace_user(self, user: DemoUserDocument, upsert: bool = False) -> DemoUserDocument:
        """
        Replaces or upserts an existing synthetic demo user document targeting exact userId.
        """
        if not isinstance(user, DemoUserDocument):
            raise DemoUserRepositoryError("User must be a valid DemoUserDocument instance.")

        query_filter = {
            "userId": user.userId,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }

        doc = user.model_dump()

        try:
            res = await self._collection.replace_one(query_filter, doc, upsert=upsert)
            if not upsert and hasattr(res, "matched_count") and res.matched_count == 0:
                raise DemoUserRepositoryError("No matching demo user found to replace.")
            return user
        except DemoUserRepositoryError:
            raise
        except Exception as exc:
            if "duplicate" in str(exc).lower() or exc.__class__.__name__ == "DuplicateKeyError":
                raise DemoUserDuplicateError("Duplicate key constraint violated on user replace.") from None
            raise DemoUserRepositoryError(f"Failed to replace demo user ({exc.__class__.__name__})") from None

    def _to_user_document(self, doc: Dict[str, Any]) -> DemoUserDocument:
        """
        Helper to convert a Mongo document to DemoUserDocument, removing '_id' safely
        and raising sanitized DemoUserRepositoryError on corrupt or invalid data.
        """
        clean_doc = dict(doc)
        clean_doc.pop("_id", None)
        try:
            return DemoUserDocument(**clean_doc)
        except Exception:
            raise DemoUserRepositoryError("Database document is corrupt or invalid.") from None

    def __repr__(self) -> str:
        return f"DemoUserRepository(collection={self.COLLECTION_NAME!r})"

    def __str__(self) -> str:
        return self.__repr__()
