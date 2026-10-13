"""
FastAPI routes for Disease Forecasting temporary demo authentication.

Endpoints:
- POST /api/v1/demo-auth/login
- GET /api/v1/demo-auth/me

Isolated from production auth and risk-forecasting prediction logic.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, StrictStr, field_validator

from backend.components.demo_auth.models import ViewerContextResponse
from backend.components.demo_auth.repository import DemoUserRepository, DemoUserRepositoryError
from backend.components.demo_auth.service import (
    DemoAuthService,
    DemoAuthError,
    DemoAuthUnavailableError,
    DemoLoginResult,
)
from backend.core.demo_auth_config import load_demo_auth_config, DemoAuthConfigError
from backend.core.demo_database_connection import DemoDatabaseConnectionError


router = APIRouter(prefix="", tags=["Demo Authentication"])


MAX_LOGIN_NAME_LENGTH = 100
MAX_PASSWORD_LENGTH = 128


class LoginRequest(BaseModel):
    """
    Strict JSON request payload for demo login.
    Rejects unknown fields, non-string types, and oversized credentials.
    """
    model_config = ConfigDict(extra="forbid")

    loginName: StrictStr
    password: StrictStr

    @field_validator("loginName")
    @classmethod
    def _validate_login_name(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("loginName must be a string")
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("loginName cannot be empty")
        if len(trimmed) > MAX_LOGIN_NAME_LENGTH:
            raise ValueError(f"loginName exceeds maximum length of {MAX_LOGIN_NAME_LENGTH} characters")
        return trimmed

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("password must be a string")
        if not v or not v.strip():
            raise ValueError("password cannot be empty")
        if len(v) > MAX_PASSWORD_LENGTH:
            raise ValueError(f"password exceeds maximum length of {MAX_PASSWORD_LENGTH} characters")
        return v


def get_demo_auth_service(request: Request) -> DemoAuthService:
    """
    FastAPI dependency resolving DemoAuthService.
    Uses app.state.demo_db_manager database instance and validated DemoAuthConfig.
    Fails safely with HTTP 503 if demo mode or database connection is unavailable.
    """
    manager = getattr(request.app.state, "demo_db_manager", None)
    if manager is None or not manager.enabled or not manager.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo authentication service is currently unavailable or disabled.",
        )

    try:
        db = manager.get_database()
    except DemoDatabaseConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo authentication service is currently unavailable or disabled.",
        )

    try:
        config = load_demo_auth_config()
        if not config.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Demo authentication service is currently unavailable or disabled.",
            )
    except DemoAuthConfigError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo authentication service is currently unavailable or disabled.",
        )

    try:
        repo = DemoUserRepository(db)
        return DemoAuthService(repo, config)
    except (DemoUserRepositoryError, DemoAuthError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo authentication service is currently unavailable or disabled.",
        )


def extract_bearer_token(request: Request) -> str:
    """
    Extracts and validates the Bearer token from the HTTP Authorization header.
    Raises HTTP 401 with WWW-Authenticate header on missing or invalid Bearer format.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return parts[1].strip()


@router.post("/login", response_model=DemoLoginResult)
async def login(
    payload: LoginRequest,
    service: DemoAuthService = Depends(get_demo_auth_service),
):
    """
    Authenticates a demo user with login credentials and returns a bearer access token.
    """
    try:
        return await service.authenticate(payload.loginName, payload.password)
    except DemoAuthUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo authentication service is currently unavailable or disabled.",
        )
    except DemoAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=ViewerContextResponse)
async def get_me(
    request: Request,
    service: DemoAuthService = Depends(get_demo_auth_service),
):
    """
    Resolves the current authenticated demo user and returns the canonical ViewerContext response.
    """
    token = extract_bearer_token(request)
    try:
        return await service.get_viewer_context(token)
    except DemoAuthUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo authentication service is currently unavailable or disabled.",
        )
    except DemoAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
