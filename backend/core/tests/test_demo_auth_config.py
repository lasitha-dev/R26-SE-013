"""
Unit tests for safe demo authentication configuration layer.
Tests secret strength, algorithm enforcement, token expiry bounds, secret redaction, and fail-closed defaults.
"""

import os
import unittest
from backend.core.demo_auth_config import (
    load_demo_auth_config,
    DemoAuthConfig,
    DemoAuthConfigError,
    ALLOWED_ALGORITHM,
    DEFAULT_EXPIRE_MINUTES,
)


class TestDemoAuthConfig(unittest.TestCase):
    VALID_SECRET_32 = "a_super_secret_key_32_chars_long"  # Exactly 32 chars
    VALID_SECRET_LONG = "a_much_longer_super_secret_jwt_signing_key_for_testing_purposes_1234567890"

    def test_demo_disabled_allows_missing_jwt_settings(self):
        config = load_demo_auth_config({})
        self.assertFalse(config.enabled)
        self.assertIsNone(config.jwt_secret)
        self.assertIsNone(config.jwt_algorithm)
        self.assertIsNone(config.expire_minutes)

    def test_demo_enabled_with_valid_settings_succeeds(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_32,
            "FORECASTING_DEMO_JWT_ALGORITHM": "HS256",
            "FORECASTING_DEMO_ACCESS_TOKEN_EXPIRE_MINUTES": "45",
        }
        config = load_demo_auth_config(env)
        self.assertTrue(config.enabled)
        self.assertEqual(config.jwt_secret, self.VALID_SECRET_32)
        self.assertEqual(config.jwt_algorithm, "HS256")
        self.assertEqual(config.expire_minutes, 45)

    def test_missing_secret_fails_when_enabled(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
        }
        with self.assertRaises(DemoAuthConfigError) as ctx:
            load_demo_auth_config(env)
        self.assertIn("required", str(ctx.exception).lower())

    def test_empty_secret_fails_when_enabled(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": "   ",
        }
        with self.assertRaises(DemoAuthConfigError) as ctx:
            load_demo_auth_config(env)
        self.assertIn("required", str(ctx.exception).lower())

    def test_secret_shorter_than_32_characters_fails(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": "short_secret_20_chars",
        }
        with self.assertRaises(DemoAuthConfigError) as ctx:
            load_demo_auth_config(env)
        self.assertIn("32 characters", str(ctx.exception))

    def test_exactly_32_character_secret_succeeds(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_32,
        }
        config = load_demo_auth_config(env)
        self.assertTrue(config.enabled)
        self.assertEqual(len(config.jwt_secret), 32)

    def test_long_secret_succeeds(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_LONG,
        }
        config = load_demo_auth_config(env)
        self.assertTrue(config.enabled)

    def test_hs256_succeeds(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_32,
            "FORECASTING_DEMO_JWT_ALGORITHM": "HS256",
        }
        config = load_demo_auth_config(env)
        self.assertEqual(config.jwt_algorithm, "HS256")

    def test_algorithm_none_fails(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_32,
            "FORECASTING_DEMO_JWT_ALGORITHM": "none",
        }
        with self.assertRaises(DemoAuthConfigError) as ctx:
            load_demo_auth_config(env)
        self.assertIn("HS256", str(ctx.exception))

    def test_different_algorithms_fail(self):
        for invalid_alg in ["RS256", "HS512", "ES256", "none", "INVALID"]:
            env = {
                "APP_ENV": "development",
                "FORECASTING_DEMO_ENABLED": "true",
                "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_32,
                "FORECASTING_DEMO_JWT_ALGORITHM": invalid_alg,
            }
            with self.assertRaises(DemoAuthConfigError):
                load_demo_auth_config(env)

    def test_missing_expiry_defaults_to_30(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_32,
        }
        config = load_demo_auth_config(env)
        self.assertEqual(config.expire_minutes, 30)

    def test_non_integer_expiry_fails(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_32,
            "FORECASTING_DEMO_ACCESS_TOKEN_EXPIRE_MINUTES": "thirty",
        }
        with self.assertRaises(DemoAuthConfigError) as ctx:
            load_demo_auth_config(env)
        self.assertIn("integer", str(ctx.exception))

    def test_expiry_below_5_fails(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_32,
            "FORECASTING_DEMO_ACCESS_TOKEN_EXPIRE_MINUTES": "4",
        }
        with self.assertRaises(DemoAuthConfigError) as ctx:
            load_demo_auth_config(env)
        self.assertIn("between 5 and 120", str(ctx.exception))

    def test_expiry_above_120_fails(self):
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_32,
            "FORECASTING_DEMO_ACCESS_TOKEN_EXPIRE_MINUTES": "121",
        }
        with self.assertRaises(DemoAuthConfigError) as ctx:
            load_demo_auth_config(env)
        self.assertIn("between 5 and 120", str(ctx.exception))

    def test_expiry_boundaries_5_and_120_succeed(self):
        for bound in [5, 120]:
            env = {
                "APP_ENV": "development",
                "FORECASTING_DEMO_ENABLED": "true",
                "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_32,
                "FORECASTING_DEMO_ACCESS_TOKEN_EXPIRE_MINUTES": str(bound),
            }
            config = load_demo_auth_config(env)
            self.assertEqual(config.expire_minutes, bound)

    def test_repr_and_str_redact_the_secret(self):
        config = DemoAuthConfig(
            enabled=True,
            jwt_secret=self.VALID_SECRET_LONG,
            jwt_algorithm="HS256",
            expire_minutes=30,
        )
        repr_str = repr(config)
        str_str = str(config)

        self.assertNotIn(self.VALID_SECRET_LONG, repr_str)
        self.assertNotIn(self.VALID_SECRET_LONG, str_str)
        self.assertIn("[REDACTED]", repr_str)
        self.assertIn("[REDACTED]", str_str)

    def test_exceptions_never_contain_a_supplied_secret(self):
        short_secret = "my_secret_key_123"
        env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": short_secret,
        }
        try:
            load_demo_auth_config(env)
        except DemoAuthConfigError as e:
            err_msg = str(e)
            self.assertNotIn(short_secret, err_msg)

    def test_loading_config_does_not_mutate_environ(self):
        original_env = dict(os.environ)
        test_env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_JWT_SECRET": self.VALID_SECRET_32,
        }
        load_demo_auth_config(test_env)
        self.assertEqual(os.environ, original_env)


if __name__ == "__main__":
    unittest.main()
