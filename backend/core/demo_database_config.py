"""
Safe configuration layer for optional Disease Forecasting demo database.

Enforces strict environment validation, secret redaction, and safe fail-closed defaults.
MongoDB is used ONLY for demo authentication and synthetic surveillance logs.
It MUST NEVER be connected to ML training, calibration, or model prediction logic.
"""

import os
from typing import Optional, Dict


APPROVED_DEMO_DATABASE_NAME = "r26_disease_forecasting_demo"

TRUE_VALUES = frozenset(["true", "1", "yes", "on"])
FALSE_VALUES = frozenset(["false", "0", "no", "off"])
ALLOWED_ENVS = frozenset(["development", "demo", "test"])
DISALLOWED_ENVS = frozenset(["production", "prod"])


class DemoDatabaseConfigError(ValueError):
    """Configuration error for demo database setting failures with sanitized messages."""
    pass


class DemoDatabaseConfig:
    """
    Immutable representation of demo database configuration settings.
    Ensures connection string secrets are never exposed in string representations or exceptions.
    """

    def __init__(self, enabled: bool, mongodb_uri: Optional[str] = None, database_name: Optional[str] = None):
        self._enabled = enabled
        self._mongodb_uri = mongodb_uri
        self._database_name = database_name

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def mongodb_uri(self) -> Optional[str]:
        return self._mongodb_uri

    @property
    def database_name(self) -> Optional[str]:
        return self._database_name

    def __repr__(self) -> str:
        uri_status = "[REDACTED]" if self._mongodb_uri else "None"
        return (
            f"DemoDatabaseConfig(enabled={self._enabled}, "
            f"database_name={self._database_name!r}, "
            f"mongodb_uri={uri_status})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def parse_boolean_env(val: Optional[str], default: bool = False) -> bool:
    """Parses environment variable string to boolean. Fails safely on invalid inputs."""
    if val is None or val.strip() == "":
        return default
    clean_val = val.strip().lower()
    if clean_val in TRUE_VALUES:
        return True
    if clean_val in FALSE_VALUES:
        return False
    raise DemoDatabaseConfigError(
        "Invalid boolean value for FORECASTING_DEMO_ENABLED. Must be one of: true, 1, yes, on, false, 0, no, off."
    )


def load_demo_database_config(env_dict: Optional[Dict[str, str]] = None) -> DemoDatabaseConfig:
    """
    Reads environment variables dynamically without mutating os.environ.

    Environment variables:
    - APP_ENV: 'development', 'demo', or 'test' when demo mode is enabled.
    - FORECASTING_DEMO_ENABLED: 'true'/'1'/'yes'/'on' or 'false'/'0'/'no'/'off'.
    - FORECASTING_DEMO_MONGODB_URI: MongoDB connection string.
    - FORECASTING_DEMO_DATABASE: Must equal 'r26_disease_forecasting_demo'.
    """
    source = env_dict if env_dict is not None else os.environ

    raw_enabled = source.get("FORECASTING_DEMO_ENABLED")
    enabled = parse_boolean_env(raw_enabled, default=False)

    if not enabled:
        return DemoDatabaseConfig(enabled=False, mongodb_uri=None, database_name=None)

    # Demo mode is enabled: validate environment and parameters strictly
    raw_app_env = source.get("APP_ENV", "development")
    app_env = raw_app_env.strip().lower() if raw_app_env else ""

    if app_env in DISALLOWED_ENVS:
        raise DemoDatabaseConfigError(
            "Demo database mode cannot be enabled in production environments (APP_ENV='production' or 'prod')."
        )

    if app_env not in ALLOWED_ENVS:
        raise DemoDatabaseConfigError(
            f"Invalid APP_ENV for demo database mode: '{raw_app_env}'. Allowed environments: development, demo, test."
        )

    raw_uri = source.get("FORECASTING_DEMO_MONGODB_URI")
    if not raw_uri or raw_uri.strip() == "":
        raise DemoDatabaseConfigError(
            "FORECASTING_DEMO_MONGODB_URI is required when FORECASTING_DEMO_ENABLED is true."
        )

    raw_db_name = source.get("FORECASTING_DEMO_DATABASE")
    if not raw_db_name or raw_db_name.strip() != APPROVED_DEMO_DATABASE_NAME:
        raise DemoDatabaseConfigError(
            f"FORECASTING_DEMO_DATABASE must be exactly '{APPROVED_DEMO_DATABASE_NAME}' when demo mode is enabled."
        )

    return DemoDatabaseConfig(
        enabled=True,
        mongodb_uri=raw_uri.strip(),
        database_name=APPROVED_DEMO_DATABASE_NAME,
    )
