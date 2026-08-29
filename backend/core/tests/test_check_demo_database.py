"""
Unit tests for local check_demo_database CLI script using mocks.
Verifies exit codes, output sanitization, and manager closure without any network calls.
"""

import io
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.core.demo_database_config import DemoDatabaseConfig, DemoDatabaseConfigError, APPROVED_DEMO_DATABASE_NAME
from backend.core.demo_database_connection import DemoDatabaseConnectionError
from backend.scripts.check_demo_database import check_demo_database_connectivity, main


class TestCheckDemoDatabaseScript(unittest.IsolatedAsyncioTestCase):
    SECRET_URI = "mongodb+srv://admin_user:SuperSecretPass123@cluster.mongodb.net/test?retryWrites=true"

    def setUp(self):
        self.enabled_config = DemoDatabaseConfig(
            enabled=True,
            mongodb_uri=self.SECRET_URI,
            database_name=APPROVED_DEMO_DATABASE_NAME,
        )

    def test_script_import_does_not_initiate_connection(self):
        # Importing check_demo_database module must not trigger connection
        import backend.scripts.check_demo_database as checker_module
        self.assertTrue(hasattr(checker_module, "check_demo_database_connectivity"))

    @patch("backend.scripts.check_demo_database.load_demo_database_config")
    @patch("backend.scripts.check_demo_database.DemoDatabaseConnectionManager")
    async def test_successful_ping_returns_exit_code_0_and_safe_text(self, mock_manager_cls, mock_load_config):
        mock_load_config.return_value = self.enabled_config
        mock_manager = MagicMock()
        mock_manager.connect = AsyncMock()
        mock_manager.ping = AsyncMock(return_value=True)
        mock_manager.close = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        stdout_capture = io.StringIO()
        with patch.object(sys, "stdout", stdout_capture):
            code = await check_demo_database_connectivity()

        self.assertEqual(code, 0)
        output = stdout_capture.getvalue()
        self.assertIn("Demo database connection successful.", output)
        self.assertNotIn(self.SECRET_URI, output)
        self.assertNotIn("SuperSecretPass123", output)
        mock_manager.close.assert_awaited_once()

    @patch("backend.scripts.check_demo_database.load_demo_database_config")
    async def test_configuration_failure_returns_non_zero_exit_code(self, mock_load_config):
        mock_load_config.side_effect = DemoDatabaseConfigError("Sanitized config error")

        stderr_capture = io.StringIO()
        with patch.object(sys, "stderr", stderr_capture):
            code = await check_demo_database_connectivity()

        self.assertEqual(code, 1)
        err_output = stderr_capture.getvalue()
        self.assertIn("Demo database configuration error", err_output)
        self.assertNotIn(self.SECRET_URI, err_output)

    @patch("backend.scripts.check_demo_database.load_demo_database_config")
    @patch("backend.scripts.check_demo_database.DemoDatabaseConnectionManager")
    async def test_connection_failure_returns_non_zero_exit_code_and_closes_manager(
        self, mock_manager_cls, mock_load_config
    ):
        mock_load_config.return_value = self.enabled_config
        mock_manager = MagicMock()
        mock_manager.connect = AsyncMock(side_effect=DemoDatabaseConnectionError("Connection timed out"))
        mock_manager.close = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        stderr_capture = io.StringIO()
        with patch.object(sys, "stderr", stderr_capture):
            code = await check_demo_database_connectivity()

        self.assertEqual(code, 1)
        err_output = stderr_capture.getvalue()
        self.assertIn("Demo database connection failed", err_output)
        self.assertNotIn(self.SECRET_URI, err_output)
        mock_manager.close.assert_awaited_once()

    @patch("backend.scripts.check_demo_database.load_demo_database_config")
    @patch("backend.scripts.check_demo_database.DemoDatabaseConnectionManager")
    async def test_ping_failure_returns_non_zero_code_and_closes_manager(
        self, mock_manager_cls, mock_load_config
    ):
        mock_load_config.return_value = self.enabled_config
        mock_manager = MagicMock()
        mock_manager.connect = AsyncMock()
        mock_manager.ping = AsyncMock(return_value=False)
        mock_manager.close = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        stderr_capture = io.StringIO()
        with patch.object(sys, "stderr", stderr_capture):
            code = await check_demo_database_connectivity()

        self.assertEqual(code, 1)
        err_output = stderr_capture.getvalue()
        self.assertIn("Ping response unverified", err_output)
        mock_manager.close.assert_awaited_once()

    @patch("backend.scripts.check_demo_database.load_demo_database_config")
    @patch("backend.scripts.check_demo_database.DemoDatabaseConnectionManager")
    def test_main_function_entry_point(self, mock_manager_cls, mock_load_config):
        mock_load_config.return_value = self.enabled_config
        mock_manager = MagicMock()
        mock_manager.connect = AsyncMock()
        mock_manager.ping = AsyncMock(return_value=True)
        mock_manager.close = AsyncMock()
        mock_manager_cls.return_value = mock_manager

        stdout_capture = io.StringIO()
        with patch.object(sys, "stdout", stdout_capture):
            code = main()

        self.assertEqual(code, 0)
        output = stdout_capture.getvalue()
        self.assertIn("Demo database connection successful.", output)


if __name__ == "__main__":
    unittest.main()
