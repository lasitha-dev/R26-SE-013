"""
Unit tests for FastAPI application lifespan wiring and demo database dependency accessor.
Uses mocks only. Network calls to MongoDB Atlas are strictly prevented.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from backend.main import app, lifespan
from backend.core.demo_database_config import DemoDatabaseConfig, DemoDatabaseConfigError, APPROVED_DEMO_DATABASE_NAME
from backend.core.demo_database_connection import DemoDatabaseConnectionError
from backend.core.demo_database_dependency import get_demo_db


class TestLifespanAndDependency(unittest.IsolatedAsyncioTestCase):
    SECRET_URI = "mongodb+srv://admin_user:SuperSecretPass123@cluster.mongodb.net/test?retryWrites=true"

    def setUp(self):
        self.disabled_config = DemoDatabaseConfig(enabled=False)
        self.enabled_config = DemoDatabaseConfig(
            enabled=True,
            mongodb_uri=self.SECRET_URI,
            database_name=APPROVED_DEMO_DATABASE_NAME,
        )

    @patch("backend.main.load_demo_database_config")
    @patch("backend.main.DemoDatabaseConnectionManager")
    async def test_disabled_lifespan_starts_without_creating_client(self, mock_manager_cls, mock_load_config):
        mock_load_config.return_value = self.disabled_config

        async with lifespan(app):
            self.assertIsNone(app.state.demo_db_manager)
            mock_manager_cls.assert_not_called()

        self.assertIsNone(app.state.demo_db_manager)

    @patch("backend.main.load_demo_database_config")
    @patch("backend.main.DemoDatabaseConnectionManager")
    async def test_enabled_lifespan_calls_connect_and_ping_once(self, mock_manager_cls, mock_load_config):
        mock_load_config.return_value = self.enabled_config
        mock_manager = MagicMock()
        mock_manager.connect = AsyncMock()
        mock_manager.ping = AsyncMock(return_value=True)
        mock_manager.close = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        async with lifespan(app):
            self.assertEqual(app.state.demo_db_manager, mock_manager)
            mock_manager.connect.assert_awaited_once()
            mock_manager.ping.assert_awaited_once()

        mock_manager.close.assert_awaited_once()
        self.assertIsNone(app.state.demo_db_manager)

    @patch("backend.main.load_demo_database_config")
    async def test_config_failure_prevents_startup_with_sanitized_output(self, mock_load_config):
        mock_load_config.side_effect = DemoDatabaseConfigError("Sanitized config error")

        with self.assertRaises(RuntimeError) as ctx:
            async with lifespan(app):
                pass

        err_msg = str(ctx.exception)
        self.assertIn("Application startup aborted", err_msg)
        self.assertNotIn(self.SECRET_URI, err_msg)

    @patch("backend.main.load_demo_database_config")
    @patch("backend.main.DemoDatabaseConnectionManager")
    async def test_connection_failure_prevents_startup_with_sanitized_output(
        self, mock_manager_cls, mock_load_config
    ):
        mock_load_config.return_value = self.enabled_config
        mock_manager = MagicMock()
        mock_manager.connect = AsyncMock(side_effect=DemoDatabaseConnectionError("Connection timeout"))
        mock_manager_cls.return_value = mock_manager

        with self.assertRaises(RuntimeError) as ctx:
            async with lifespan(app):
                pass

        err_msg = str(ctx.exception)
        self.assertIn("Application startup aborted", err_msg)
        self.assertNotIn(self.SECRET_URI, err_msg)

    def test_accessor_returns_database_when_available(self):
        mock_db = MagicMock()
        mock_manager = MagicMock()
        mock_manager.enabled = True
        mock_manager.is_connected = True
        mock_manager.get_database.return_value = mock_db

        mock_request = MagicMock()
        mock_request.app.state.demo_db_manager = mock_manager

        db = get_demo_db(mock_request)
        self.assertEqual(db, mock_db)
        mock_manager.get_database.assert_called_once()

    def test_accessor_fails_safely_when_disabled_or_unavailable(self):
        mock_request = MagicMock()
        mock_request.app.state.demo_db_manager = None

        with self.assertRaises(HTTPException) as ctx:
            get_demo_db(mock_request)

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("unavailable or disabled", ctx.exception.detail)

    def test_existing_forecasting_routes_remain_registered(self):
        registered_paths = {route.path for route in app.routes}

        expected_paths = {
            "/",
            "/api/v1/risk-forecasting/health",
            "/api/v1/risk-forecasting/districts",
            "/api/v1/risk-forecasting/predict/fmd",
            "/api/v1/risk-forecasting/predict/lsd",
            "/api/v1/risk-forecasting/forecast/fmd",
            "/api/v1/risk-forecasting/forecast/lsd",
        }

        for path in expected_paths:
            self.assertIn(path, registered_paths, f"Expected route missing: {path}")


if __name__ == "__main__":
    unittest.main()
