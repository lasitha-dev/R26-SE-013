"""
Security utility layer for temporary Disease Forecasting demo authentication.

Provides password hashing and verification using pwdlib (Argon2)
and JWT access token creation and decoding using PyJWT.
"""

from datetime import datetime, timezone, timedelta
import uuid
from typing import Optional
import jwt
from pwdlib import PasswordHash

from backend.core.demo_auth_config import DemoAuthConfig


DEMO_JWT_ISSUER = "r26-disease-forecasting-demo"
DEMO_JWT_AUDIENCE = "r26-disease-forecasting-frontend"
DEMO_TOKEN_TYPE = "access"
ALLOWED_ALGORITHM = "HS256"

# Initialize recommended pwdlib PasswordHash (Argon2)
_password_hash = PasswordHash.recommended()


class DemoSecurityError(ValueError):
    """Sanitized security and authentication error."""
    pass


class DecodedDemoToken:
    """
    Immutable representation of a validated decoded demo access token.
    Exposes only safe read-only attributes required by caller.
    """

    def __init__(self, user_id: str, token_id: str, issued_at: datetime, expires_at: datetime):
        self._user_id = user_id
        self._token_id = token_id
        self._issued_at = issued_at
        self._expires_at = expires_at

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def token_id(self) -> str:
        return self._token_id

    @property
    def issued_at(self) -> datetime:
        return self._issued_at

    @property
    def expires_at(self) -> datetime:
        return self._expires_at

    def __repr__(self) -> str:
        return (
            f"DecodedDemoToken(user_id={self._user_id!r}, "
            f"token_id={self._token_id!r}, "
            f"issued_at={self._issued_at.isoformat()!r}, "
            f"expires_at={self._expires_at.isoformat()!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using pwdlib's recommended Argon2 configuration.
    Never exposes or logs the plaintext password.
    """
    if not isinstance(password, str) or not password:
        raise DemoSecurityError("Password must be a non-empty string.")
    try:
        return _password_hash.hash(password)
    except Exception:
        raise DemoSecurityError("Failed to hash password safely.")


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a stored Argon2 hash.
    Fails safely on invalid, malformed, or unsupported hashes without exposing exceptions.
    """
    if not isinstance(password, str) or not password:
        return False
    if not isinstance(hashed_password, str) or not hashed_password:
        return False
    try:
        return _password_hash.verify(password, hashed_password)
    except Exception:
        return False


def create_access_token(
    subject: str,
    config: DemoAuthConfig,
    now: Optional[datetime] = None,
) -> str:
    """
    Creates a signed JWT access token for the given subject using config settings.
    Requires config.enabled == True.
    """
    if not isinstance(config, DemoAuthConfig) or not config.enabled:
        raise DemoSecurityError("Demo authentication configuration is disabled or invalid.")

    if not isinstance(subject, str) or not subject.strip():
        raise DemoSecurityError("Subject (sub) must be a non-empty string.")

    secret = config.jwt_secret
    algorithm = config.jwt_algorithm
    expire_minutes = config.expire_minutes

    if not secret or algorithm != ALLOWED_ALGORITHM or expire_minutes is None:
        raise DemoSecurityError("Demo authentication configuration is incomplete or invalid.")

    current_time = now if now is not None else datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    iat_dt = current_time
    nbf_dt = current_time
    exp_dt = current_time + timedelta(minutes=expire_minutes)

    payload = {
        "sub": subject.strip(),
        "type": DEMO_TOKEN_TYPE,
        "iat": int(iat_dt.timestamp()),
        "nbf": int(nbf_dt.timestamp()),
        "exp": int(exp_dt.timestamp()),
        "jti": str(uuid.uuid4()),
        "iss": DEMO_JWT_ISSUER,
        "aud": DEMO_JWT_AUDIENCE,
    }

    try:
        token = jwt.encode(payload, secret, algorithm=ALLOWED_ALGORITHM)
        return token
    except Exception:
        raise DemoSecurityError("Failed to encode demo access token.")


def decode_access_token(
    token: str,
    config: DemoAuthConfig,
    now: Optional[datetime] = None,
) -> DecodedDemoToken:
    """
    Decodes and validates a JWT access token using config settings.
    Sanitizes all exceptions to DemoSecurityError without exposing secrets or raw tokens.
    """
    if not isinstance(config, DemoAuthConfig) or not config.enabled:
        raise DemoSecurityError("Demo authentication configuration is disabled or invalid.")

    if not isinstance(token, str) or not token.strip():
        raise DemoSecurityError("Token must be a non-empty string.")

    secret = config.jwt_secret
    if not secret:
        raise DemoSecurityError("Demo authentication configuration is incomplete.")

    current_time = now if now is not None else datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    # When custom clock 'now' is supplied, delegate time-boundary checks to explicit evaluation
    verify_time_claims = now is None

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALLOWED_ALGORITHM],
            issuer=DEMO_JWT_ISSUER,
            audience=DEMO_JWT_AUDIENCE,
            options={
                "verify_signature": True,
                "verify_exp": verify_time_claims,
                "verify_nbf": verify_time_claims,
                "verify_iat": verify_time_claims,
                "verify_iss": True,
                "verify_aud": True,
                "require": ["sub", "type", "iat", "nbf", "exp", "jti", "iss", "aud"],
            },
        )
    except Exception:
        raise DemoSecurityError("Invalid, expired, or malformed demo access token.")

    # Validate claim specifics strictly
    token_type = payload.get("type")
    if token_type != DEMO_TOKEN_TYPE:
        raise DemoSecurityError("Invalid token type.")

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise DemoSecurityError("Invalid token subject.")

    jti = payload.get("jti")
    if not isinstance(jti, str) or not jti.strip():
        raise DemoSecurityError("Invalid token ID.")

    exp = payload.get("exp")
    iat = payload.get("iat")
    if not isinstance(exp, (int, float)) or not isinstance(iat, (int, float)):
        raise DemoSecurityError("Invalid timestamp claims.")

    # Additional explicit check for custom 'now' parameter if provided
    if now is not None:
        now_ts = int(current_time.timestamp())
        nbf = payload.get("nbf")
        if isinstance(nbf, (int, float)) and now_ts < nbf:
            raise DemoSecurityError("Invalid, expired, or malformed demo access token.")
        if now_ts >= exp:
            raise DemoSecurityError("Invalid, expired, or malformed demo access token.")

    issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

    return DecodedDemoToken(
        user_id=sub.strip(),
        token_id=jti.strip(),
        issued_at=issued_at,
        expires_at=expires_at,
    )
