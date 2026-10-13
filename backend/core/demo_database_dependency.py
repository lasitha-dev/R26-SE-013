"""
Narrow FastAPI dependency accessor for optional Disease Forecasting demo database.

Fails safely with HTTP 503 Service Unavailable when demo database support is disabled or unavailable.
Never exposes connection secrets or credentials.
Unused by risk forecasting prediction routes.
"""

from typing import Any
from fastapi import Request, HTTPException, status
from backend.core.demo_database_connection import DemoDatabaseConnectionManager, DemoDatabaseConnectionError


def get_demo_db(request: Request) -> Any:
    """
    FastAPI dependency accessor returning the active demo database instance.
    Raises HTTP 503 if demo database support is disabled or connection is inactive.
    """
    manager: DemoDatabaseConnectionManager = getattr(request.app.state, "demo_db_manager", None)
    if manager is None or not manager.enabled or not manager.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo database service is currently unavailable or disabled.",
        )
    try:
        return manager.get_database()
    except DemoDatabaseConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo database service is currently unavailable or disabled.",
        )
