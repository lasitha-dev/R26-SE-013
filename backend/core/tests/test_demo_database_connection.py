"""
Unit tests for isolated asynchronous demo database connection manager.
Uses unittest AsyncTestCase and mocks AsyncMongoClient completely.
No network calls or real MongoDB Atlas connections are made.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock
import bson
from bson.codec_options import CodecOptions
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure, ConnectionFailure

from backend.core.demo_database_config import DemoDatabaseConfig, APPROVED_DEMO_DATABASE_NAME
from backend.core.demo_database_connection import (
    DemoDatabaseConnectionManager,
    DemoDatabaseConnectionError,
)


class TestDemoDatabaseConnectionManager(unittest.IsolatedAsyncioTestCase):
    SECRET_URI = "mongodb+srv://admin_user:SuperSecretPass123@cluster.mongodb.net/test?retryWrites=true"

    def setUp(self):
        self.disabled_config = DemoDatabaseConfig(enabled=False)
        self.enabled_config = DemoDatabaseConfig(
            enabled=True,
            mongodb_uri=self.SECRET_URI,
            database_name=APPROVED_DEMO_DATABASE_NAME,
        )

    def test_no_connection_at_import_time(self):
        # Simply instantiating manager must not connect or read environment
        manager = DemoDatabaseConnectionManager(self.disabled_config)
        self.assertFalse(manager.is_connected)
        self.assertFalse(manager.enabled)

    def test_disabled_mode_creates_no_client(self):
        manager = DemoDatabaseConnectionManager(self.disabled_config)
        self.assertFalse(manager.enabled)
        self.assertFalse(manager.is_connected)
        with self.assertRaises(DemoDatabaseConnectionError):
            manager.get_database()

    @patch("backend.core.demo_database_connection.AsyncMongoClient")
    async def test_disabled_connect_is_safe_and_creates_no_client(self, mock_client_cls):
        manager = DemoDatabaseConnectionManager(self.disabled_config)
        await manager.connect()
        self.assertFalse(manager.is_connected)
        mock_client_cls.assert_not_called()

    @patch("backend.core.demo_database_connection.AsyncMongoClient")
    async def test_enabled_connect_creates_one_client(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        manager = DemoDatabaseConnectionManager(self.enabled_config)
        await manager.connect()

        self.assertTrue(manager.is_connected)
        mock_client_cls.assert_called_once()
        # Verify secret URI passed to client initialization
        args, kwargs = mock_client_cls.call_args
        self.assertEqual(args[0], self.SECRET_URI)
        self.assertEqual(kwargs.get("serverSelectionTimeoutMS"), 5000)
        self.assertTrue(kwargs.get("tz_aware"))
        self.assertEqual(kwargs.get("tzinfo"), timezone.utc)

    def test_bson_codec_decodes_utc_aware_datetime(self):
        now_utc = datetime.now(timezone.utc)
        encoded_bson = bson.BSON.encode({"createdAt": now_utc})
        codec = CodecOptions(tz_aware=True, tzinfo=timezone.utc)
        decoded_doc = bson.BSON.decode(encoded_bson, codec_options=codec)

        decoded_dt = decoded_doc["createdAt"]
        self.assertIsInstance(decoded_dt, datetime)
        self.assertIsNotNone(decoded_dt.tzinfo)
        self.assertEqual(decoded_dt.tzinfo, timezone.utc)

    @patch("backend.core.demo_database_connection.AsyncMongoClient")
    async def test_repeated_connect_does_not_create_duplicate_clients(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        manager = DemoDatabaseConnectionManager(self.enabled_config)
        await manager.connect()
        await manager.connect()
        await manager.connect()

        self.assertEqual(mock_client_cls.call_count, 1)

    @patch("backend.core.demo_database_connection.AsyncMongoClient")
    async def test_correct_validated_database_is_selected(self, mock_client_cls):
        mock_db = MagicMock()
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_client_cls.return_value = mock_client

        manager = DemoDatabaseConnectionManager(self.enabled_config)
        await manager.connect()

        db = manager.get_database()
        self.assertEqual(db, mock_db)
        mock_client.__getitem__.assert_called_once_with(APPROVED_DEMO_DATABASE_NAME)

    @patch("backend.core.demo_database_connection.AsyncMongoClient")
    async def test_ping_uses_admin_ping_command_and_returns_true(self, mock_client_cls):
        mock_client = MagicMock()
        mock_admin = MagicMock()
        mock_admin.command = AsyncMock(return_value={"ok": 1.0})
        mock_client.admin = mock_admin
        mock_client_cls.return_value = mock_client

        manager = DemoDatabaseConnectionManager(self.enabled_config)
        res = await manager.ping()

        self.assertTrue(res)
        mock_admin.command.assert_awaited_once_with("ping")

    @patch("backend.core.demo_database_connection.AsyncMongoClient")
    async def test_driver_connection_failure_becomes_sanitized_custom_error(self, mock_client_cls):
        mock_client_cls.side_effect = ConnectionFailure("Raw driver socket connection error")

        manager = DemoDatabaseConnectionManager(self.enabled_config)
        with self.assertRaises(DemoDatabaseConnectionError) as ctx:
            await manager.connect()

        err_msg = str(ctx.exception)
        self.assertNotIn(self.SECRET_URI, err_msg)
        self.assertNotIn("SuperSecretPass123", err_msg)
        self.assertIn("Demo database connection failed", err_msg)

    @patch("backend.core.demo_database_connection.AsyncMongoClient")
    async def test_authentication_failure_becomes_sanitized_custom_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_admin = MagicMock()
        mock_admin.command = AsyncMock(side_effect=OperationFailure("Authentication failed: invalid password"))
        mock_client.admin = mock_admin
        mock_client_cls.return_value = mock_client

        manager = DemoDatabaseConnectionManager(self.enabled_config)
        with self.assertRaises(DemoDatabaseConnectionError) as ctx:
            await manager.ping()

        err_msg = str(ctx.exception)
        self.assertNotIn(self.SECRET_URI, err_msg)
        self.assertNotIn("SuperSecretPass123", err_msg)
        self.assertIn("ping failed", err_msg)

    @patch("backend.core.demo_database_connection.AsyncMongoClient")
    async def test_timeout_becomes_sanitized_custom_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_admin = MagicMock()
        mock_admin.command = AsyncMock(side_effect=ServerSelectionTimeoutError("No primary available within 5000ms"))
        mock_client.admin = mock_admin
        mock_client_cls.return_value = mock_client

        manager = DemoDatabaseConnectionManager(self.enabled_config)
        with self.assertRaises(DemoDatabaseConnectionError) as ctx:
            await manager.ping()

        err_msg = str(ctx.exception)
        self.assertNotIn(self.SECRET_URI, err_msg)
        self.assertNotIn("SuperSecretPass123", err_msg)
        self.assertIn("unreachable or timed out", err_msg)

    def test_error_text_and_repr_do_not_contain_secret_uri(self):
        manager = DemoDatabaseConnectionManager(self.enabled_config)
        repr_str = repr(manager)
        str_str = str(manager)

        self.assertNotIn(self.SECRET_URI, repr_str)
        self.assertNotIn("SuperSecretPass123", repr_str)
        self.assertNotIn(self.SECRET_URI, str_str)

    @patch("backend.core.demo_database_connection.AsyncMongoClient")
    async def test_close_closes_the_client(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        mock_client_cls.return_value = mock_client

        manager = DemoDatabaseConnectionManager(self.enabled_config)
        await manager.connect()
        self.assertTrue(manager.is_connected)

        await manager.close()
        self.assertFalse(manager.is_connected)
        mock_client.aclose.assert_awaited_once()

    @patch("backend.core.demo_database_connection.AsyncMongoClient")
    async def test_repeated_close_is_safe(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        mock_client_cls.return_value = mock_client

        manager = DemoDatabaseConnectionManager(self.enabled_config)
        await manager.connect()
        await manager.close()
        await manager.close()
        await manager.close()

        self.assertFalse(manager.is_connected)

    async def test_close_before_connect_is_safe(self):
        manager = DemoDatabaseConnectionManager(self.enabled_config)
        await manager.close()
        self.assertFalse(manager.is_connected)


if __name__ == "__main__":
    unittest.main()
