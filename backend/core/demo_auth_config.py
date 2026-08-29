"""
Safe configuration layer for optional Disease Forecasting demo authentication.

Enforces strict environment validation, secret redaction, and JWT signing requirements.
Used ONLY for temporary demo authentication tokens.
MUST NEVER be connected to ML training, calibration, or model prediction logic.
"""

import os
from typing import Optional, Dict
from backend.core.demo_database_config import parse_boolean_env, DISALLOWED_ENVS, ALLOWED_ENVS

ALLOWED_ALGORITHM = "HS256"
MIN_SECRET_LENGTH = 32
DEFAULT_EXPIRE_MINUTES = 30
MIN_EXPIRE_MINUTES = 5
MAX_EXPIRE_MINUTES = 120


class DemoAuthConfigError(ValueError):
    """Configuration error for demo authentication setting failures with sanitized messages."""
    pass


class DemoAuthConfig:
    """
    Immutable representation of demo authentication configuration settings.
    Ensures signing secret is never exposed in string representations or exceptions.
    """

    def __init__(
        self,
        enabled: bool,
        jwt_secret: Optional[str] = None,
        jwt_algorithm: Optional[str] = None,
        expire_minutes: Optional[int] = None,
    ):
        self._enabled = enabled
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._expire_minutes = expire_minutes

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def jwt_secret(self) -> Optional[str]:
        return self._jwt_secret

    @property
    def jwt_algorithm(self) -> Optional[str]:
        return self._jwt_algorithm

    @property
    def expire_minutes(self) -> Optional[int]:
        return self._expire_minutes

    def __repr__(self) -> str:
        secret_status = "[REDACTED]" if self._jwt_secret else "None"
        return (
            f"DemoAuthConfig(enabled={self._enabled}, "
            f"jwt_algorithm={self._jwt_algorithm!r}, "
            f"expire_minutes={self._expire_minutes}, "
            f"jwt_secret={secret_status})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def load_demo_auth_config(env_dict: Optional[Dict[str, str]] = None) -> DemoAuthConfig:
    """
    Reads environment variables dynamically without mutating os.environ.

    Environment variables:
    - FORECASTING_DEMO_ENABLED: 'true'/'1'/'yes'/'on' or 'false'/'0'/'no'/'off'.
    - FORECASTING_DEMO_JWT_SECRET: Required string (>= 32 chars).
    - FORECASTING_DEMO_JWT_ALGORITHM: Must equal 'HS256'.
    - FORECASTING_DEMO_ACCESS_TOKEN_EXPIRE_MINUTES: Integer between 5 and 120 (default: 30).
    """
    source = env_dict if env_dict is not None else os.environ

    raw_enabled = source.get("FORECASTING_DEMO_ENABLED")
    enabled = parse_boolean_env(raw_enabled, default=False)

    if not enabled:
        return DemoAuthConfig(enabled=False, jwt_secret=None, jwt_algorithm=None, expire_minutes=None)

    raw_app_env = source.get("APP_ENV", "development")
    app_env = raw_app_env.strip().lower() if raw_app_env else ""

    if app_env in DISALLOWED_ENVS:
        raise DemoAuthConfigError(
            "Demo authentication cannot be enabled in production environments (APP_ENV='production' or 'prod')."
        )

    if app_env not in ALLOWED_ENVS:
        raise DemoAuthConfigError(
            f"Invalid APP_ENV for demo authentication mode: '{raw_app_env}'. Allowed environments: development, demo, test."
        )

    raw_secret = source.get("FORECASTING_DEMO_JWT_SECRET")
    if not raw_secret or raw_secret.strip() == "":
        raise DemoAuthConfigError(
            "FORECASTING_DEMO_JWT_SECRET is required when FORECASTING_DEMO_ENABLED is true."
        )

    secret = raw_secret.strip()
    if len(secret) < MIN_SECRET_LENGTH:
        raise DemoAuthConfigError(
            f"FORECASTING_DEMO_JWT_SECRET must be at least {MIN_SECRET_LENGTH} characters long."
        )

    raw_algorithm = source.get("FORECASTING_DEMO_JWT_ALGORITHM", ALLOWED_ALGORITHM)
    if not raw_algorithm or raw_algorithm.strip() != ALLOWED_ALGORITHM:
        raise DemoAuthConfigError(
            f"FORECASTING_DEMO_JWT_ALGORITHM must be exactly '{ALLOWED_ALGORITHM}'."
        )

    raw_expire = source.get("FORECASTING_DEMO_ACCESS_TOKEN_EXPIRE_MINUTES")
    if raw_expire is None or raw_expire.strip() == "":
        expire_minutes = DEFAULT_EXPIRE_MINUTES
    else:
        try:
            expire_minutes = int(raw_expire.strip())
        except ValueError:
            raise DemoAuthConfigError(
                "FORECASTING_DEMO_ACCESS_TOKEN_EXPIRE_MINUTES must be an integer."
            )

    if expire_minutes < MIN_EXPIRE_MINUTES or expire_minutes > MAX_EXPIRE_MINUTES:
        raise DemoAuthConfigError(
            f"FORECASTING_DEMO_ACCESS_TOKEN_EXPIRE_MINUTES must be between {MIN_EXPIRE_MINUTES} and {MAX_EXPIRE_MINUTES} minutes."
        )

    return DemoAuthConfig(
        enabled=True,
        jwt_secret=secret,
        jwt_algorithm=ALLOWED_ALGORITHM,
        expire_minutes=expire_minutes,
    )
