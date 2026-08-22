"""
FastAPI Router for the Risk Forecasting Component.
Defines endpoints for FMD and LSD outbreak risk prediction, severity classification,
all-district climatological forecasts, district metadata, and health checks.
"""

from typing import Optional, Literal
from fastapi import APIRouter, Body, HTTPException, Header, Query, status
from backend.components.risk_forecasting.config import SRI_LANKA_DISTRICTS, MONTH_NAMES
from backend.components.risk_forecasting.schemas import (
    FMDOutbreakPredictRequest, FMDOutbreakPredictResponse,
    LSDOutbreakPredictRequest, LSDOutbreakPredictResponse,
    FMDForecastRequest, LSDForecastRequest,
    DistrictForecastResponse, FMDDistrictForecastResponse, LSDDistrictForecastResponse,
    HealthCheckResponse, DistrictListResponse,
    GenerateForecastRecordRequest, ForecastDecisionRecord, ForecastRecordListResponse,
    FarmerAdvisoryRecord, CreateAdvisoryDraftRequest, UpdateAdvisoryDraftRequest,
    AdvisoryPreviewResponse, AdvisoryListResponse
)
from backend.components.risk_forecasting.services.fmd_service import fmd_service
from backend.components.risk_forecasting.services.lsd_service import lsd_service
from backend.components.risk_forecasting.services.forecast_record_service import forecast_record_service
from backend.components.risk_forecasting.services.advisory_service import advisory_service

router = APIRouter()



@router.get("/health", response_model=HealthCheckResponse, summary="Component Health Check")
def health_check():
    """Returns component operational health status and loaded model artifacts."""
    loaded_artifacts = fmd_service.loaded_artifacts + lsd_service.loaded_artifacts
    models_ready = fmd_service.models_loaded and lsd_service.models_loaded
    return HealthCheckResponse(
        status="ok" if models_ready else "degraded",
        component="risk_forecasting",
        version="1.0.0",
        models_loaded=models_ready,
        loaded_artifacts=loaded_artifacts
    )


@router.get("/districts", response_model=DistrictListResponse, summary="List Supported Sri Lankan Districts")
def list_districts():
    """Returns the list of 25 supported Sri Lankan administrative districts and 12 month names."""
    return DistrictListResponse(
        total_districts=len(SRI_LANKA_DISTRICTS),
        districts=list(SRI_LANKA_DISTRICTS),
        month_names=list(MONTH_NAMES)
    )


@router.post("/predict/fmd", response_model=FMDOutbreakPredictResponse, summary="Predict FMD Outbreak Risk & Severity")
def predict_fmd(request: FMDOutbreakPredictRequest):
    """
    Predicts Foot-and-Mouth Disease (FMD) outbreak probability (Stage 1) and severity classification (Stage 2)
    with operational decision thresholding (t=0.40), Mondrian conformal uncertainty coverage, and actionable recommendations.
    """
    try:
        return fmd_service.predict(request)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"FMD service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FMD prediction failed: {str(e)}"
        )


@router.post("/predict/lsd", response_model=LSDOutbreakPredictResponse, summary="Predict LSD Outbreak Risk & Severity")
def predict_lsd(request: LSDOutbreakPredictRequest):
    """
    Predicts Lumpy Skin Disease (LSD) Platt-calibrated outbreak probability, risk tier (t=0.40),
    Stage 2 quiet-period suppressor severity, honest non-numeric conformal UQ, and scientific disclaimers.
    """
    try:
        return lsd_service.predict(request)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LSD service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LSD prediction failed: {str(e)}"
        )


@router.post("/forecast/fmd", response_model=FMDDistrictForecastResponse, summary="FMD All-District Forecast")
def forecast_fmd(request: FMDForecastRequest):
    """Generates an all-district climatological FMD risk forecast for the specified month."""
    try:
        year = request.year or 2024
        return fmd_service.compute_forecast(
            target_month=request.target_month,
            year=year,
            model_variant="30_feature_baseline"
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"FMD forecast service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FMD forecast failed: {str(e)}"
        )


@router.post("/forecast/lsd", response_model=LSDDistrictForecastResponse, summary="LSD All-District Forecast")
def forecast_lsd(request: LSDForecastRequest):
    """Generates an all-district climatological LSD risk forecast for the specified month."""
    try:
        year = request.year or 2024
        return lsd_service.compute_forecast(
            target_month=request.target_month,
            year=year
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LSD forecast service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LSD forecast failed: {str(e)}"
        )


# ─── Forecast Decision Record Endpoints ─────────────────────────────────────

@router.post(
    "/records",
    response_model=ForecastDecisionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Generate & Store Forecast Decision Record"
)
def create_forecast_record(
    request: GenerateForecastRecordRequest,
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Generates an authoritative model prediction (FMD or LSD) and persists an immutable
    ForecastDecisionRecord. Accepts optional client idempotency key via header or body payload.
    """
    if idempotency_key_header and request.idempotency_key:
        if idempotency_key_header != request.idempotency_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Idempotency key mismatch: Header 'Idempotency-Key' ('{idempotency_key_header}') and request body 'idempotency_key' ('{request.idempotency_key}') must match when both are provided."
            )
    elif idempotency_key_header and not request.idempotency_key:
        request.idempotency_key = idempotency_key_header


    try:
        return forecast_record_service.generate_record(request)
    except ValueError as e:
        err_msg = str(e)
        if "Idempotency key collision" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=err_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Forecast model service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forecast decision record generation failed: {str(e)}"
        )


@router.get(
    "/records/{forecast_id}",
    response_model=ForecastDecisionRecord,
    summary="Retrieve Forecast Decision Record by ID"
)
def get_forecast_record(forecast_id: str):
    """Retrieves an immutable ForecastDecisionRecord by its unique forecast_id."""
    try:
        return forecast_record_service.get_record(forecast_id)
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/records",
    response_model=ForecastRecordListResponse,
    summary="List Forecast Decision Records"
)
def list_forecast_records(
    disease: Optional[Literal["FMD", "LSD"]] = Query(None, description="Filter by disease type"),
    district: Optional[str] = Query(None, description="Filter by district name"),
    target_year: Optional[int] = Query(None, ge=2017, le=2030, description="Filter by target year"),
    target_month: Optional[int] = Query(None, ge=1, le=12, description="Filter by target month"),
    status_filter: Optional[Literal["GENERATED", "AVAILABLE", "REFERENCED", "SUPERSEDED"]] = Query(
        None, alias="status", description="Filter by record status"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum records to return (1-200)"),
    offset: int = Query(0, ge=0, description="Record pagination offset")
):
    """Lists stored ForecastDecisionRecord instances matching specified query filters with pagination."""
    try:
        return forecast_record_service.list_records(
            disease=disease,
            district=district,
            target_year=target_year,
            target_month=target_month,
            status=status_filter,
            limit=limit,
            offset=offset
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ─── Farmer Advisory Endpoints (Phase 3) ───────────────────────────────────

@router.post(
    "/advisories",
    response_model=FarmerAdvisoryRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create Farmer Advisory Draft"
)
def create_advisory_draft(
    request: CreateAdvisoryDraftRequest,
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Creates a new FarmerAdvisoryRecord draft linked to an immutable ForecastDecisionRecord.
    Supports optional header or body idempotency key.
    """
    if idempotency_key_header and request.idempotency_key:
        if idempotency_key_header != request.idempotency_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Idempotency key mismatch: Header 'Idempotency-Key' ('{idempotency_key_header}') and request body 'idempotency_key' ('{request.idempotency_key}') must match when both are provided."
            )
    elif idempotency_key_header and not request.idempotency_key:
        request.idempotency_key = idempotency_key_header

    try:
        return advisory_service.create_draft(request)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Idempotency key collision" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/advisories/preview",
    response_model=AdvisoryPreviewResponse,
    summary="Preview Farmer Advisory Message Resolution"
)
def preview_advisory(
    advisory_id: Optional[str] = Query(None, description="Optional existing advisory ID to preview"),
    draft_request: Optional[CreateAdvisoryDraftRequest] = Body(None, description="Optional draft request payload to preview before saving")
):
    """
    Generates recipient-resolved previews and message breakdowns without persisting or sending any notifications.
    """
    try:
        return advisory_service.preview_advisory(advisory_id=advisory_id, draft_req=draft_request)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/advisories/{advisory_id}",
    response_model=FarmerAdvisoryRecord,
    summary="Retrieve Farmer Advisory Record by ID"
)
def get_advisory(advisory_id: str):
    """Retrieves a FarmerAdvisoryRecord by its unique advisory_id."""
    try:
        return advisory_service.get_advisory(advisory_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/advisories",
    response_model=AdvisoryListResponse,
    summary="List Farmer Advisory Records"
)
def list_advisories(
    forecast_id: Optional[str] = Query(None, description="Filter by referenced forecast record ID"),
    disease: Optional[Literal["FMD", "LSD"]] = Query(None, description="Filter by disease type"),
    district: Optional[str] = Query(None, description="Filter by district name"),
    status_filter: Optional[Literal["DRAFT", "REVIEW_READY", "APPROVED", "CANCELLED"]] = Query(
        None, alias="status", description="Filter by advisory status"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum advisories to return (1-200)"),
    offset: int = Query(0, ge=0, description="Advisory pagination offset")
):
    """Lists stored FarmerAdvisoryRecord instances matching specified query filters with pagination."""
    try:
        return advisory_service.list_advisories(
            forecast_id=forecast_id,
            disease=disease,
            district=district,
            status=status_filter,
            limit=limit,
            offset=offset
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "/advisories/{advisory_id}",
    response_model=FarmerAdvisoryRecord,
    summary="Update Editable Advisory Draft"
)
def update_advisory_draft(
    advisory_id: str,
    request: UpdateAdvisoryDraftRequest
):
    """Updates editable advisory draft content using optimistic version checking."""
    try:
        return advisory_service.update_draft(advisory_id, request)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg or "Approved advisories are immutable" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/advisories/{advisory_id}/ready-for-review",
    response_model=FarmerAdvisoryRecord,
    summary="Mark Advisory Ready for Review"
)
def mark_advisory_ready_for_review(
    advisory_id: str,
    version: int = Query(..., ge=1, description="Expected current record version for optimistic locking")
):
    """Transitions advisory status from DRAFT -> REVIEW_READY."""
    try:
        return advisory_service.mark_ready_for_review(advisory_id, version)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/advisories/{advisory_id}/approve",
    response_model=FarmerAdvisoryRecord,
    summary="Approve Farmer Advisory"
)
def approve_advisory(
    advisory_id: str,
    version: int = Query(..., ge=1, description="Expected current record version for optimistic locking"),
    approved_by: str = Query("vet_officer_01", description="Actor ID of the approver")
):
    """Transitions advisory status to APPROVED. Approved content becomes immutable."""
    try:
        return advisory_service.approve_advisory(advisory_id, version, approved_by)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg or "Approved advisories are immutable" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/advisories/{advisory_id}/cancel",
    response_model=FarmerAdvisoryRecord,
    summary="Cancel Farmer Advisory"
)
def cancel_advisory(
    advisory_id: str,
    version: int = Query(..., ge=1, description="Expected current record version for optimistic locking")
):
    """Transitions advisory status to CANCELLED."""
    try:
        return advisory_service.cancel_advisory(advisory_id, version)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
