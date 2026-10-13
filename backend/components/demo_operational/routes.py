"""
FastAPI protected routes for synthetic operational demo data.

Endpoints:
- GET /api/v1/demo-operational/farms
- GET /api/v1/demo-operational/surveillance-records
- GET /api/v1/demo-operational/alerts
- GET /api/v1/demo-operational/response-tasks

All endpoints require a valid Bearer token and delegate authorization exclusively
to DemoOperationalAuthorizationService.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from backend.components.demo_auth.models import DemoUserDocument
from backend.components.demo_auth.routes import extract_bearer_token, get_demo_auth_service
from backend.components.demo_auth.service import DemoAuthService, DemoAuthError, DemoAuthUnavailableError
from backend.components.demo_operational.models import (
    DemoFarm,
    DemoSurveillanceRecord,
    DemoAlert,
    DemoResponseTask,
)
from backend.components.demo_operational.repositories import (
    DemoFarmRepository,
    DemoSurveillanceRepository,
    DemoAlertRepository,
    DemoResponseTaskRepository,
)
from backend.components.demo_operational.service import (
    DemoOperationalAuthorizationService,
    DemoOperationalForbiddenError,
    DemoOperationalUnavailableError,
)


router = APIRouter(prefix="", tags=["Demo Operational Data"])


class DemoFarmListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[DemoFarm]
    skip: StrictInt
    limit: StrictInt
    count: StrictInt
    dataOrigin: StrictStr = Field(default="SYNTHETIC_DEMO")
    scientificUseAllowed: StrictBool = Field(default=False)


class DemoSurveillanceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[DemoSurveillanceRecord]
    skip: StrictInt
    limit: StrictInt
    count: StrictInt
    dataOrigin: StrictStr = Field(default="SYNTHETIC_DEMO")
    scientificUseAllowed: StrictBool = Field(default=False)


class DemoAlertListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[DemoAlert]
    skip: StrictInt
    limit: StrictInt
    count: StrictInt
    dataOrigin: StrictStr = Field(default="SYNTHETIC_DEMO")
    scientificUseAllowed: StrictBool = Field(default=False)


class DemoTaskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[DemoResponseTask]
    skip: StrictInt
    limit: StrictInt
    count: StrictInt
    dataOrigin: StrictStr = Field(default="SYNTHETIC_DEMO")
    scientificUseAllowed: StrictBool = Field(default=False)


async def get_current_demo_user(
    token: str = Depends(extract_bearer_token),
    auth_service: DemoAuthService = Depends(get_demo_auth_service),
) -> DemoUserDocument:
    """FastAPI dependency resolving fresh DemoUserDocument from Bearer token and MongoDB."""
    try:
        return await auth_service.resolve_current_user(token)
    except DemoAuthUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operational data service is currently unavailable.",
        )
    except (DemoAuthError, Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_demo_operational_service(
    request: Request,
    current_user: DemoUserDocument = Depends(get_current_demo_user),
) -> DemoOperationalAuthorizationService:
    """FastAPI dependency constructing DemoOperationalAuthorizationService from app.state.demo_db_manager."""
    manager = getattr(request.app.state, "demo_db_manager", None)
    if manager is None or not manager.enabled or not manager.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operational data service is currently unavailable.",
        )

    try:
        db = manager.get_database()
        farm_repo = DemoFarmRepository(db)
        surv_repo = DemoSurveillanceRepository(db)
        alert_repo = DemoAlertRepository(db)
        task_repo = DemoResponseTaskRepository(db)
        return DemoOperationalAuthorizationService(
            farm_repo=farm_repo,
            surv_repo=surv_repo,
            alert_repo=alert_repo,
            task_repo=task_repo,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operational data service is currently unavailable.",
        )


@router.get("/farms", response_model=DemoFarmListResponse)
async def get_farms(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: DemoUserDocument = Depends(get_current_demo_user),
    service: DemoOperationalAuthorizationService = Depends(get_demo_operational_service),
):
    """Retrieves accessible farms for current_user."""
    try:
        items = await service.get_accessible_farms(current_user, skip=skip, limit=limit)
        return DemoFarmListResponse(
            items=items,
            skip=skip,
            limit=limit,
            count=len(items),
            dataOrigin="SYNTHETIC_DEMO",
            scientificUseAllowed=False,
        )
    except DemoOperationalForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to requested operational data is forbidden.",
        )
    except (DemoOperationalUnavailableError, Exception):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operational data service is currently unavailable.",
        )


@router.get("/surveillance-records", response_model=DemoSurveillanceListResponse)
async def get_surveillance_records(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: DemoUserDocument = Depends(get_current_demo_user),
    service: DemoOperationalAuthorizationService = Depends(get_demo_operational_service),
):
    """Retrieves accessible surveillance records for current_user."""
    try:
        items = await service.get_accessible_surveillance_records(current_user, skip=skip, limit=limit)
        return DemoSurveillanceListResponse(
            items=items,
            skip=skip,
            limit=limit,
            count=len(items),
            dataOrigin="SYNTHETIC_DEMO",
            scientificUseAllowed=False,
        )
    except DemoOperationalForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to requested operational data is forbidden.",
        )
    except (DemoOperationalUnavailableError, Exception):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operational data service is currently unavailable.",
        )


@router.get("/alerts", response_model=DemoAlertListResponse)
async def get_alerts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: DemoUserDocument = Depends(get_current_demo_user),
    service: DemoOperationalAuthorizationService = Depends(get_demo_operational_service),
):
    """Retrieves accessible operational alerts for current_user."""
    try:
        items = await service.get_accessible_alerts(current_user, skip=skip, limit=limit)
        return DemoAlertListResponse(
            items=items,
            skip=skip,
            limit=limit,
            count=len(items),
            dataOrigin="SYNTHETIC_DEMO",
            scientificUseAllowed=False,
        )
    except DemoOperationalForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to requested operational data is forbidden.",
        )
    except (DemoOperationalUnavailableError, Exception):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operational data service is currently unavailable.",
        )


@router.get("/response-tasks", response_model=DemoTaskListResponse)
async def get_response_tasks(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: DemoUserDocument = Depends(get_current_demo_user),
    service: DemoOperationalAuthorizationService = Depends(get_demo_operational_service),
):
    """Retrieves accessible response tasks for current_user."""
    try:
        items = await service.get_accessible_response_tasks(current_user, skip=skip, limit=limit)
        return DemoTaskListResponse(
            items=items,
            skip=skip,
            limit=limit,
            count=len(items),
            dataOrigin="SYNTHETIC_DEMO",
            scientificUseAllowed=False,
        )
    except DemoOperationalForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to requested operational data is forbidden.",
        )
    except (DemoOperationalUnavailableError, Exception):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operational data service is currently unavailable.",
        )
