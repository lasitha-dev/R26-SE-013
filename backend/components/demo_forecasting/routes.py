"""
FastAPI protected routes for Disease Forecasting role-scoped demo forecasting.

Endpoints:
- POST /api/v1/demo-forecasting/forecast/fmd
- POST /api/v1/demo-forecasting/forecast/lsd

Requires Bearer authentication and enforces server-side district authorization
derived strictly from the authenticated DemoUserDocument.
"""

from typing import List, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import Field

from backend.components.demo_auth.models import DemoUserDocument
from backend.components.demo_auth.routes import extract_bearer_token, get_demo_auth_service
from backend.components.demo_auth.service import DemoAuthService, DemoAuthError, DemoAuthUnavailableError
from backend.components.risk_forecasting.config import SRI_LANKA_DISTRICTS
from backend.components.risk_forecasting.schemas import (
    FMDForecastRequest,
    LSDForecastRequest,
    FMDDistrictForecastResponse,
    LSDDistrictForecastResponse,
    DistrictForecastItem,
)
from backend.components.risk_forecasting.services.fmd_service import fmd_service
from backend.components.risk_forecasting.services.lsd_service import lsd_service


router = APIRouter(prefix="", tags=["Demo Role-Scoped Forecasting"])


class DemoFMDForecastRequest(FMDForecastRequest):
    district: Optional[str] = Field(
        default=None,
        description="Optional single target district to filter authorized forecast."
    )
    districts: Optional[List[str]] = Field(
        default=None,
        description="Optional list of target districts to filter authorized forecast."
    )


class DemoLSDForecastRequest(LSDForecastRequest):
    district: Optional[str] = Field(
        default=None,
        description="Optional single target district to filter authorized forecast."
    )
    districts: Optional[List[str]] = Field(
        default=None,
        description="Optional list of target districts to filter authorized forecast."
    )


async def get_current_demo_user(
    token: str = Depends(extract_bearer_token),
    auth_service: DemoAuthService = Depends(get_demo_auth_service),
) -> DemoUserDocument:
    """FastAPI dependency resolving fresh DemoUserDocument from Bearer token and MongoDB on every request."""
    try:
        return await auth_service.resolve_current_user(token)
    except DemoAuthUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forecast service is currently unavailable.",
        )
    except (DemoAuthError, Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _normalize_district_name(v: str) -> str:
    """Normalizes district name for matching against SRI_LANKA_DISTRICTS."""
    if not isinstance(v, str):
        return v
    formatted = v.strip().title()
    if formatted in ["Moneragala", "Monaragala"]:
        formatted = "Monaragala"
    elif formatted in ["Nuwaraeliya", "Nuwara Eliya"]:
        formatted = "Nuwara Eliya"
    return formatted


def _derive_authorized_districts(user: DemoUserDocument) -> Set[str]:
    """
    Derives the allowed district set strictly from the freshly loaded DemoUserDocument.
    Fails closed (returns empty set) for invalid role/scope combinations or missing authorization data.
    """
    role = getattr(user, "role", None)
    auth = getattr(user, "authorization", None)

    if not role or not auth:
        return set()

    scope = getattr(auth, "scopeLevel", None)

    if role == "FARMER":
        if scope != "FARM":
            return set()
        reg_district = getattr(auth, "registeredFarmDistrict", None)
        if not reg_district or not isinstance(reg_district, str) or not reg_district.strip():
            return set()
        norm = _normalize_district_name(reg_district)
        return {norm} if norm in SRI_LANKA_DISTRICTS else set()

    elif role == "VETERINARY_OFFICER":
        if scope not in ("DISTRICT", "PROVINCE"):
            return set()
        auth_districts = getattr(auth, "authorizedDistricts", None) or []
        allowed = set()
        for d in auth_districts:
            if isinstance(d, str) and d.strip():
                norm = _normalize_district_name(d)
                if norm in SRI_LANKA_DISTRICTS:
                    allowed.add(norm)
        return allowed

    elif role == "DAPH_OFFICIAL":
        if scope not in ("DISTRICT", "PROVINCE", "NATIONAL"):
            return set()
        # Note: NATIONAL scope must NOT auto-expand to all districts! Only explicitly authorizedDistricts are allowed.
        auth_districts = getattr(auth, "authorizedDistricts", None) or []
        allowed = set()
        for d in auth_districts:
            if isinstance(d, str) and d.strip():
                norm = _normalize_district_name(d)
                if norm in SRI_LANKA_DISTRICTS:
                    allowed.add(norm)
        return allowed

    return set()


def _validate_and_get_requested_districts(
    payload_district: Optional[str],
    payload_districts: Optional[List[str]],
    allowed_districts: Set[str],
) -> Set[str]:
    """
    Validates requested districts against allowed_districts set.
    Raises HTTP 403 if allowed_districts is empty or if any requested district is unauthorized.
    Returns the target set of authorized districts to include in forecast output.
    """
    if not allowed_districts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forecast access to the requested district is forbidden.",
        )

    requested = set()

    if payload_district and isinstance(payload_district, str) and payload_district.strip():
        norm = _normalize_district_name(payload_district)
        if norm not in SRI_LANKA_DISTRICTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid district '{payload_district}'.",
            )
        requested.add(norm)

    if payload_districts and isinstance(payload_districts, list):
        for d in payload_districts:
            if isinstance(d, str) and d.strip():
                norm = _normalize_district_name(d)
                if norm not in SRI_LANKA_DISTRICTS:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Invalid district '{d}'.",
                    )
                requested.add(norm)

    # If no specific district requested in payload, target set is all allowed_districts
    target_set = requested if requested else set(allowed_districts)

    # Verify every requested district is in allowed_districts
    if not target_set.issubset(allowed_districts) or not target_set:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forecast access to the requested district is forbidden.",
        )

    return target_set


def _filter_fmd_forecast_response(
    response: FMDDistrictForecastResponse,
    target_set: Set[str],
) -> FMDDistrictForecastResponse:
    """Filters FMD forecast items to target_set and updates total/high/medium/low counts."""
    filtered_items: List[DistrictForecastItem] = [
        item for item in response.districts if item.district in target_set
    ]
    high_cnt = sum(1 for item in filtered_items if item.risk_level == "HIGH")
    med_cnt = sum(1 for item in filtered_items if item.risk_level == "MEDIUM")
    low_cnt = sum(1 for item in filtered_items if item.risk_level == "LOW")

    return FMDDistrictForecastResponse(
        disease=response.disease,
        target_year=response.target_year,
        target_month=response.target_month,
        target_month_name=response.target_month_name,
        model_variant=response.model_variant,
        total_districts=len(filtered_items),
        high_risk_count=high_cnt,
        medium_risk_count=med_cnt,
        low_risk_count=low_cnt,
        districts=filtered_items,
        exact_data_district_count=response.exact_data_district_count,
        historical_proxy_district_count=response.historical_proxy_district_count,
        historical_median_district_count=response.historical_median_district_count,
        data_quality_status=response.data_quality_status,
        data_quality_message=response.data_quality_message,
    )


def _filter_lsd_forecast_response(
    response: LSDDistrictForecastResponse,
    target_set: Set[str],
) -> LSDDistrictForecastResponse:
    """Filters LSD forecast items to target_set and updates total/high/medium/low counts."""
    filtered_items: List[DistrictForecastItem] = [
        item for item in response.districts if item.district in target_set
    ]
    high_cnt = sum(1 for item in filtered_items if item.risk_level == "HIGH")
    med_cnt = sum(1 for item in filtered_items if item.risk_level == "MEDIUM")
    low_cnt = sum(1 for item in filtered_items if item.risk_level == "LOW")

    return LSDDistrictForecastResponse(
        disease=response.disease,
        target_year=response.target_year,
        target_month=response.target_month,
        target_month_name=response.target_month_name,
        total_districts=len(filtered_items),
        high_risk_count=high_cnt,
        medium_risk_count=med_cnt,
        low_risk_count=low_cnt,
        districts=filtered_items,
        lag1_data_status=response.lag1_data_status,
        lag1_verified_district_count=response.lag1_verified_district_count,
        lag1_unavailable_district_count=response.lag1_unavailable_district_count,
        lag1_message=response.lag1_message,
        exact_data_district_count=response.exact_data_district_count,
        historical_proxy_district_count=response.historical_proxy_district_count,
        historical_median_district_count=response.historical_median_district_count,
        data_quality_status=response.data_quality_status,
        data_quality_message=response.data_quality_message,
    )


@router.post("/forecast/fmd", response_model=FMDDistrictForecastResponse, summary="Protected Role-Scoped FMD Forecast")
def forecast_fmd(
    payload: DemoFMDForecastRequest,
    response: Response,
    current_user: DemoUserDocument = Depends(get_current_demo_user),
):
    """
    Generates role-scoped FMD district risk forecast for authenticated demo user.
    Enforces district authorization server-side before calling scientific forecasting service.
    """
    allowed_districts = _derive_authorized_districts(current_user)
    target_set = _validate_and_get_requested_districts(
        payload.district, payload.districts, allowed_districts
    )

    try:
        year = payload.year or 2024
        raw_forecast = fmd_service.compute_forecast(
            target_month=payload.target_month,
            year=year,
            model_variant="30_feature_baseline",
        )
        response.headers["X-Demo-Authorization"] = "role-scoped"
        return _filter_fmd_forecast_response(raw_forecast, target_set)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forecast service is currently unavailable.",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="FMD forecast failed.",
        )


@router.post("/forecast/lsd", response_model=LSDDistrictForecastResponse, summary="Protected Role-Scoped LSD Forecast")
def forecast_lsd(
    payload: DemoLSDForecastRequest,
    response: Response,
    current_user: DemoUserDocument = Depends(get_current_demo_user),
):
    """
    Generates role-scoped LSD district risk forecast for authenticated demo user.
    Enforces district authorization server-side before calling scientific forecasting service.
    """
    allowed_districts = _derive_authorized_districts(current_user)
    target_set = _validate_and_get_requested_districts(
        payload.district, payload.districts, allowed_districts
    )

    try:
        year = payload.year or 2024
        raw_forecast = lsd_service.compute_forecast(
            target_month=payload.target_month,
            year=year,
        )
        response.headers["X-Demo-Authorization"] = "role-scoped"
        return _filter_lsd_forecast_response(raw_forecast, target_set)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forecast service is currently unavailable.",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LSD forecast failed.",
        )
