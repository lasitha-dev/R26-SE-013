"""
Unit tests for safe demo database configuration layer.
Tests environment parsing, secret redaction, production rejection, and fail-closed defaults.
"""

import os
import unittest
from backend.core.demo_database_config import (
    load_demo_database_config,
    parse_boolean_env,
    DemoDatabaseConfig,
    DemoDatabaseConfigError,
    APPROVED_DEMO_DATABASE_NAME,
)


class TestDemoDatabaseConfig(unittest.TestCase):
    SECRET_URI = "mongodb+srv://admin_user:SuperSecretPass123@cluster.mongodb.net/test?retryWrites=true"

    def test_disabled_by_default(self):
        config = load_demo_database_config({})
        self.assertFalse(config.enabled)
        self.assertIsNone(config.mongodb_uri)
        self.assertIsNone(config.database_name)

    def test_disabled_mode_with_missing_uri_is_valid(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "false",
            # FORECASTING_DEMO_MONGODB_URI omitted intentionally
        }
        config = load_demo_database_config(env)
        self.assertFalse(config.enabled)
        self.assertIsNone(config.mongodb_uri)

    def test_every_accepted_true_value(self):
        for true_val in ["true", "1", "yes", "on", "TRUE", "Yes", "ON"]:
            env = {
                "APP_ENV": "development",
                "FORECASTING_DEMO_ENABLED": true_val,
                "FORECASTING_DEMO_MONGODB_URI": self.SECRET_URI,
                "FORECASTING_DEMO_DATABASE": APPROVED_DEMO_DATABASE_NAME,
            }
            config = load_demo_database_config(env)
            self.assertTrue(config.enabled, f"Failed for true_val: {true_val}")

    def test_every_accepted_false_value(self):
        for false_val in ["false", "0", "no", "off", "FALSE", "No", "OFF"]:
            env = {
                "FORECASTING_DEMO_ENABLED": false_val,
            }
            config = load_demo_database_config(env)
            self.assertFalse(config.enabled, f"Failed for false_val: {false_val}")

    def test_unknown_boolean_value_fails_safely(self):
        for invalid_val in ["maybe", "enabled", "2", "invalid_bool"]:
            env = {"FORECASTING_DEMO_ENABLED": invalid_val}
            with self.assertRaises(DemoDatabaseConfigError):
                load_demo_database_config(env)

    def test_enabled_development_mode_succeeds(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_MONGODB_URI": self.SECRET_URI,
            "FORECASTING_DEMO_DATABASE": APPROVED_DEMO_DATABASE_NAME,
        }
        config = load_demo_database_config(env)
        self.assertTrue(config.enabled)
        self.assertEqual(config.mongodb_uri, self.SECRET_URI)
        self.assertEqual(config.database_name, APPROVED_DEMO_DATABASE_NAME)

    def test_enabled_demo_mode_succeeds(self):
        env = {
            "APP_ENV": "demo",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_MONGODB_URI": self.SECRET_URI,
            "FORECASTING_DEMO_DATABASE": APPROVED_DEMO_DATABASE_NAME,
        }
        config = load_demo_database_config(env)
        self.assertTrue(config.enabled)

    def test_enabled_test_mode_succeeds(self):
        env = {
            "APP_ENV": "test",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_MONGODB_URI": self.SECRET_URI,
            "FORECASTING_DEMO_DATABASE": APPROVED_DEMO_DATABASE_NAME,
        }
        config = load_demo_database_config(env)
        self.assertTrue(config.enabled)

    def test_enabled_production_mode_is_rejected(self):
        for prod_env in ["production", "prod", "PRODUCTION", "PROD"]:
            env = {
                "APP_ENV": prod_env,
                "FORECASTING_DEMO_ENABLED": "true",
                "FORECASTING_DEMO_MONGODB_URI": self.SECRET_URI,
                "FORECASTING_DEMO_DATABASE": APPROVED_DEMO_DATABASE_NAME,
            }
            with self.assertRaises(DemoDatabaseConfigError) as ctx:
                load_demo_database_config(env)
            self.assertIn("production", str(ctx.exception).lower())

    def test_enabled_mode_with_missing_uri_is_rejected(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_DATABASE": APPROVED_DEMO_DATABASE_NAME,
        }
        with self.assertRaises(DemoDatabaseConfigError):
            load_demo_database_config(env)

    def test_enabled_mode_with_empty_uri_is_rejected(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_MONGODB_URI": "   ",
            "FORECASTING_DEMO_DATABASE": APPROVED_DEMO_DATABASE_NAME,
        }
        with self.assertRaises(DemoDatabaseConfigError):
            load_demo_database_config(env)

    def test_enabled_mode_with_wrong_database_name_is_rejected(self):
        for wrong_db in ["wrong_db", "production_db", "r26_prod_db"]:
            env = {
                "APP_ENV": "development",
                "FORECASTING_DEMO_ENABLED": "true",
                "FORECASTING_DEMO_MONGODB_URI": self.SECRET_URI,
                "FORECASTING_DEMO_DATABASE": wrong_db,
            }
            with self.assertRaises(DemoDatabaseConfigError) as ctx:
                load_demo_database_config(env)
            self.assertIn(APPROVED_DEMO_DATABASE_NAME, str(ctx.exception))

    def test_errors_and_repr_never_expose_secret_uri(self):
        config = DemoDatabaseConfig(enabled=True, mongodb_uri=self.SECRET_URI, database_name=APPROVED_DEMO_DATABASE_NAME)
        repr_str = repr(config)
        str_str = str(config)

        self.assertNotIn(self.SECRET_URI, repr_str)
        self.assertNotIn("SuperSecretPass123", repr_str)
        self.assertNotIn(self.SECRET_URI, str_str)

        # Test Exception message redaction
        env = {
            "APP_ENV": "production",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_MONGODB_URI": self.SECRET_URI,
            "FORECASTING_DEMO_DATABASE": APPROVED_DEMO_DATABASE_NAME,
        }
        try:
            load_demo_database_config(env)
        except DemoDatabaseConfigError as e:
            err_msg = str(e)
            self.assertNotIn(self.SECRET_URI, err_msg)
            self.assertNotIn("SuperSecretPass123", err_msg)

    def test_reading_config_does_not_mutate_environ(self):
        original_env = dict(os.environ)
        test_env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_MONGODB_URI": self.SECRET_URI,
            "FORECASTING_DEMO_DATABASE": APPROVED_DEMO_DATABASE_NAME,
        }
        load_demo_database_config(test_env)
        self.assertEqual(os.environ, original_env)


if __name__ == "__main__":
    unittest.main()
