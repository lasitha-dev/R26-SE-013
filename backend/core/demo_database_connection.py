"""
Isolated Asynchronous Connection Manager for optional Disease Forecasting demo database.

Uses PyMongo 4.17+ AsyncMongoClient with bounded timeouts and Stable API v1.
Exclusively used for temporary demo authentication and synthetic surveillance records.
MUST NEVER be connected to ML model training, feature engineering, calibration, or uncertainty estimation.
"""

from datetime import timezone
from typing import Optional, Any
from pymongo import AsyncMongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import PyMongoError

from backend.core.demo_database_config import DemoDatabaseConfig


class DemoDatabaseConnectionError(RuntimeError):
    """Sanitized exception for demo database connection failures."""
    pass


class DemoDatabaseConnectionManager:
    """
    Asynchronous connection manager for the demo MongoDB instance.
    Receives an explicit DemoDatabaseConfig instance and manages the AsyncMongoClient lifecycle.
    """

    def __init__(self, config: DemoDatabaseConfig):
        self._config = config
        self._client: Optional[AsyncMongoClient] = None
        self._db: Optional[Any] = None

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    @property
    def database_name(self) -> Optional[str]:
        return self._config.database_name

    async def connect(self) -> None:
        """
        Creates and connects the AsyncMongoClient if demo database is enabled.
        Idempotent: calling connect() when already connected does nothing.
        Configures strict UTC timezone-aware datetime decoding.
        """
        if not self._config.enabled:
            return

        if self._client is not None:
            return

        try:
            self._client = AsyncMongoClient(
                self._config.mongodb_uri,
                server_api=ServerApi("1"),
                serverSelectionTimeoutMS=5000,
                tz_aware=True,
                tzinfo=timezone.utc,
            )
            self._db = self._client[self._config.database_name]
        except Exception as exc:
            self._client = None
            self._db = None
            raise DemoDatabaseConnectionError(
                f"Demo database connection failed ({exc.__class__.__name__}): Unable to initialize MongoDB client."
            ) from None

    async def ping(self) -> bool:
        """
        Pings the admin database to verify active network connectivity and authentication.
        Fails safely with DemoDatabaseConnectionError if disconnected or unreachable.
        """
        if not self._config.enabled:
            return False

        if self._client is None:
            await self.connect()

        try:
            # Execute admin ping command
            reply = await self._client.admin.command("ping")
            return bool(reply and reply.get("ok") == 1.0 or reply.get("ok") == 1)
        except Exception as exc:
            raise DemoDatabaseConnectionError(
                f"Demo database ping failed ({exc.__class__.__name__}): MongoDB server is unreachable or timed out."
            ) from None

    def get_database(self) -> Any:
        """
        Returns the configured database instance if enabled and connected.
        Raises DemoDatabaseConnectionError if disabled or not connected.
        """
        if not self._config.enabled:
            raise DemoDatabaseConnectionError("Cannot access database: Demo database mode is disabled.")
        if self._db is None:
            raise DemoDatabaseConnectionError("Cannot access database: Connection has not been established.")
        return self._db

    async def close(self) -> None:
        """
        Safely closes the AsyncMongoClient instance.
        Idempotent: safe to call when disabled or already closed.
        """
        if self._client is not None:
            try:
                # Prefer aclose() if available in AsyncMongoClient, otherwise fallback to close()
                if hasattr(self._client, "aclose"):
                    await self._client.aclose()
                else:
                    self._client.close()
            except Exception:
                pass
            finally:
                self._client = None
                self._db = None

    def __repr__(self) -> str:
        return (
            f"DemoDatabaseConnectionManager(enabled={self._config.enabled}, "
            f"connected={self.is_connected}, "
            f"database={self._config.database_name!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()
