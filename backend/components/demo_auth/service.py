"""
Service layer for temporary Disease Forecasting demo user authentication and ViewerContext resolution.

Uses dependency-injected DemoUserRepository and DemoAuthConfig.
Enforces anti-user-enumeration dummy password checks, generic error sanitization,
and fresh database user resolution on every ViewerContext request.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from backend.components.demo_auth.models import (
    DemoUserDocument,
    ViewerContextResponse,
    demo_user_to_viewer_context,
)
from backend.components.demo_auth.repository import (
    DemoUserRepository,
    DemoUserRepositoryError,
)
from backend.core.demo_auth_config import DemoAuthConfig
from backend.core.demo_security import (
    create_access_token,
    decode_access_token,
    verify_password,
    DemoSecurityError,
)


GENERIC_AUTH_ERROR_MESSAGE = "Invalid authentication credentials."
SERVICE_UNAVAILABLE_ERROR_MESSAGE = "Authentication service is currently unavailable."

# Constant non-credential Argon2 hash for timing-safe dummy password verification when user is missing
DUMMY_ARGON2_HASH = "$argon2id$v=19$m=65536,t=3,p=4$ZHVtbXlzYWx0ZHVtbXlzYWx0$dummyhashvaluefortimingprotectiononly"


class DemoAuthError(ValueError):
    """Generic, sanitized authentication error."""
    pass


class DemoAuthUnavailableError(DemoAuthError):
    """Sanitized error raised when repository or infrastructure is unavailable."""
    pass


class DemoLoginResult(BaseModel):
    """
    Immutable login response containing only necessary bearer token metadata.
    Does not leak passwords, hashes, user roles, districts, or permissions.
    """
    model_config = ConfigDict(extra="forbid")

    accessToken: StrictStr
    tokenType: StrictStr = Field(default="bearer")
    expiresIn: StrictInt


class DemoAuthService:
    """
    Service managing demo user login, token issuance, and ViewerContext resolution.
    Receives pre-validated repository and configuration through dependency injection.
    """

    def __init__(self, repository: DemoUserRepository, config: DemoAuthConfig):
        if repository is None or not isinstance(repository, DemoUserRepository):
            raise DemoAuthError("Valid DemoUserRepository instance is required.")
        if config is None or not isinstance(config, DemoAuthConfig):
            raise DemoAuthError("Valid DemoAuthConfig instance is required.")

        self._repository = repository
        self._config = config

    async def authenticate(self, login_name: str, password: str) -> DemoLoginResult:
        """
        Authenticates a demo user by login_name and password.
        Uses anti-user-enumeration dummy password checks for missing users.
        """
        if not self._config.enabled:
            raise DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE)

        if not isinstance(login_name, str) or not login_name.strip():
            raise DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE)

        if not isinstance(password, str) or not password:
            raise DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE)

        clean_login = login_name.strip().lower()

        try:
            user = await self._repository.find_by_login_name(clean_login)
        except DemoUserRepositoryError:
            raise DemoAuthUnavailableError(SERVICE_UNAVAILABLE_ERROR_MESSAGE) from None
        except Exception:
            raise DemoAuthUnavailableError(SERVICE_UNAVAILABLE_ERROR_MESSAGE) from None

        if user is None:
            # Dummy password check to prevent timing-based user enumeration
            verify_password(password, DUMMY_ARGON2_HASH)
            raise DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE)

        if not user.enabled:
            # Execute password check before rejecting disabled user to keep timing consistent
            verify_password(password, user.passwordHash)
            raise DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE)

        valid_pass = verify_password(password, user.passwordHash)
        if not valid_pass:
            raise DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE)

        try:
            token = create_access_token(user.userId, self._config)
            expires_in_seconds = (self._config.expire_minutes or 30) * 60
            return DemoLoginResult(
                accessToken=token,
                tokenType="bearer",
                expiresIn=expires_in_seconds,
            )
        except DemoSecurityError:
            raise DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE) from None

    async def resolve_current_user(self, access_token: str) -> DemoUserDocument:
        """
        Decodes access token and reloads current user document from MongoDB repository.
        Does not trust role or permissions from caller token payload.
        """
        if not self._config.enabled:
            raise DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE)

        if not isinstance(access_token, str) or not access_token.strip():
            raise DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE)

        try:
            decoded = decode_access_token(access_token, self._config)
        except DemoSecurityError:
            raise DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE) from None

        try:
            user = await self._repository.find_by_user_id(decoded.user_id)
        except DemoUserRepositoryError:
            raise DemoAuthUnavailableError(SERVICE_UNAVAILABLE_ERROR_MESSAGE) from None
        except Exception:
            raise DemoAuthUnavailableError(SERVICE_UNAVAILABLE_ERROR_MESSAGE) from None

        if user is None or not user.enabled:
            raise DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE)

        return user

    async def get_viewer_context(self, access_token: str) -> ViewerContextResponse:
        """
        Resolves fresh current database user and returns canonical ViewerContextResponse.
        Reflects database permission or district updates immediately.
        """
        user = await self.resolve_current_user(access_token)
        return demo_user_to_viewer_context(user)

    def __repr__(self) -> str:
        return f"DemoAuthService(repository={self._repository!r})"

    def __str__(self) -> str:
        return self.__repr__()
