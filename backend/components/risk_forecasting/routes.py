"""
FastAPI Router for the Risk Forecasting Component.
Defines endpoints for FMD and LSD outbreak risk prediction, severity classification,
all-district climatological forecasts, district metadata, and health checks.
"""

from typing import Optional, Literal, List
from fastapi import APIRouter, Body, Depends, HTTPException, Header, Query, status
from components.risk_forecasting.config import SRI_LANKA_DISTRICTS, MONTH_NAMES
from components.risk_forecasting.schemas import (
    FMDOutbreakPredictRequest, FMDOutbreakPredictResponse,
    LSDOutbreakPredictRequest, LSDOutbreakPredictResponse,
    FMDForecastRequest, LSDForecastRequest,
    DistrictForecastResponse, FMDDistrictForecastResponse, LSDDistrictForecastResponse,
    HealthCheckResponse, DistrictListResponse,
    GenerateForecastRecordRequest, ForecastDecisionRecord, ForecastRecordListResponse,
    FarmerAdvisoryRecord, CreateAdvisoryDraftRequest, UpdateAdvisoryDraftRequest,
    AdvisoryPreviewResponse, AdvisoryListResponse,
    NotificationBatch, NotificationDelivery, EnqueueNotificationBatchRequest,
    NotificationBatchListResponse, NotificationDeliveryListResponse,
    RecipientSummaryItem, AssignedRecipientListResponse,
    ForecastFollowUpRecord, CreateFollowUpRequest, TransitionFollowUpRequest,
    LinkExternalResourceRequest, FollowUpListResponse, FollowUpActorContext,
    EligibleVetListResponse
)
from components.risk_forecasting.services.fmd_service import fmd_service
from components.risk_forecasting.services.lsd_service import lsd_service
from components.risk_forecasting.services.forecast_record_service import forecast_record_service
import sys

def setup_production_services():
    from components.risk_forecasting.repositories.mongo_forecast_record_repository import MongoForecastRecordRepository
    from components.risk_forecasting.repositories.mongo_advisory_repository import MongoAdvisoryRepository
    from components.risk_forecasting.repositories.mongo_follow_up_repository import MongoFollowUpRepository
    from components.risk_forecasting.integrations.mongo_vet_directory import MongoVeterinaryOfficerDirectory
    from components.risk_forecasting.integrations.mongo_recipient_directory import MongoRecipientDirectory
    from components.risk_forecasting.integrations.mongo_shared_client import MongoSharedForecastClient
    from components.risk_forecasting.integrations.provider_factory import create_forecast_data_provider
    import os
    from components.risk_forecasting.services.advisory_service import advisory_service
    from components.risk_forecasting.services.notification_service import notification_service
    from components.risk_forecasting.services.follow_up_service import forecast_follow_up_service
    
    forecast_record_service.repository = MongoForecastRecordRepository()
    forecast_follow_up_service.vet_dir = MongoVeterinaryOfficerDirectory()
    
    # Inject MongoDB Repositories instead of In-Memory
    advisory_service.advisory_repo = MongoAdvisoryRepository()
    forecast_follow_up_service.follow_up_repo = MongoFollowUpRepository()
    
    # Inject real MongoDB directory into all services that need it
    shared_recipient_dir = MongoRecipientDirectory()
    recipient_query_service.recipient_dir = shared_recipient_dir
    advisory_service.recipient_dir = shared_recipient_dir
    notification_service.recipient_dir = shared_recipient_dir
    
    provider_mode = "shared_api"
    
    if provider_mode == "shared_api":
        shared_client = MongoSharedForecastClient(cache_ttl_seconds=3600)
        provider = create_forecast_data_provider(mode="shared_api", shared_client=shared_client)
        fmd_service.data_provider = provider
        lsd_service.data_provider = provider
    elif provider_mode == "live_weather":
        from components.risk_forecasting.integrations.live_weather_provider import LiveWeatherForecastDataProvider
        from components.risk_forecasting.integrations.forecast_data_provider import CsvForecastDataProvider
        provider = LiveWeatherForecastDataProvider(fallback_provider=CsvForecastDataProvider())
        fmd_service.data_provider = provider
        lsd_service.data_provider = provider

from components.risk_forecasting.services.advisory_service import advisory_service
from components.risk_forecasting.services.notification_service import notification_service
from components.risk_forecasting.services.recipient_query_service import recipient_query_service
from components.risk_forecasting.services.follow_up_service import forecast_follow_up_service
from components.risk_forecasting.integration.auth_adapter import get_viewer_context, ViewerContextResponse
from components.health_anomaly.schemas import OutbreakStatusResponse

_shared_client_instance = None

def get_shared_client():
    global _shared_client_instance
    if _shared_client_instance is None:
        from components.risk_forecasting.integrations.mongo_shared_client import MongoSharedForecastClient
        _shared_client_instance = MongoSharedForecastClient(cache_ttl_seconds=3600)
    return _shared_client_instance

router = APIRouter()



@router.get("/viewer-context", summary="Get Veterinary Viewer Context", response_model=ViewerContextResponse)
async def get_veterinary_viewer_context(
    viewer_context: ViewerContextResponse = Depends(get_viewer_context)
):
    """
    Returns the isolated ViewerContext for a Veterinary Officer.
    Uses the integration auth adapter to parse the JWT and fetch roles from the main vets collection
    without importing heavy AI model dependencies.
    """
    return viewer_context



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


@router.get(
    "/recipients",
    response_model=AssignedRecipientListResponse,
    summary="List Non-Sensitive Recipients Assigned to Veterinary Officer"
)
def list_assigned_recipients(
    vet_id: str = Query(..., description="Veterinary Officer ID (standalone placeholder, required)"),
    district: Optional[str] = Query(None, description="Optional Sri Lankan district name filter")
):
    """
    Lists non-sensitive farm recipient metadata assigned to the given Vet, optionally filtered by district.
    Exposes read-only directory lookups for frontend recipient selection without misusing advisory previews.
    """
    try:
        return recipient_query_service.list_assigned_recipients(vet_id=vet_id, district=district)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
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
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forecast record service is temporarily unavailable."
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Forecast record service is temporarily unavailable."
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
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forecast record service is temporarily unavailable."
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Forecast record service is temporarily unavailable."
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
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forecast record service is temporarily unavailable."
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Forecast record service is temporarily unavailable."
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


# ─── Notification Outbox Endpoints (Phase 4) ───────────────────────────────

"""
POSTMAN-TESTABLE ADVISORY & NOTIFICATION WORKFLOW SEQUENCE:

1. POST /api/v1/risk-forecasting/records
   Body: {"disease": "FMD", "district": "Anuradhapura", "year": 2024, "month": 1, "trigger_type": "MANUAL"}
   Save response.forecast_id (e.g. fdr_12345)

2. POST /api/v1/risk-forecasting/advisories
   Body: {"forecast_id": "<forecast_id>", "recipient_scope": "ALL_ASSIGNED", "vet_custom_note": "Check vaccination cards"}
   Save response.advisory_id (e.g. adv_67890), status="DRAFT", version=1

3. POST /api/v1/risk-forecasting/advisories/<advisory_id>/ready-for-review?version=1
   Updates status to "REVIEW_READY", version=2

4. POST /api/v1/risk-forecasting/advisories/<advisory_id>/approve?version=2&approved_by=vet_officer_01
   Updates status to "APPROVED", version=3

5. POST /api/v1/risk-forecasting/advisories/<advisory_id>/notification-batches
   Header: Idempotency-Key: idemp_batch_001
   Enqueues notification batch (status="QUEUED"). Save response.batch_id

6. GET /api/v1/risk-forecasting/notification-batches/<batch_id>
   GET /api/v1/risk-forecasting/notification-batches/<batch_id>/deliveries
   Inspect batch status ("QUEUED") and per-recipient delivery payloads ("PENDING") before dispatch.

7. POST /api/v1/risk-forecasting/notification-batches/<batch_id>/dispatch
   Executes mock notification delivery dispatch through MockNotificationProvider.
   Updates batch status to "COMPLETED" (or "PARTIALLY_FAILED" / "FAILED").

8. GET /api/v1/risk-forecasting/notification-batches/<batch_id>/deliveries
   Inspect per-recipient delivery statuses ("SUCCEEDED" or "FAILED") and provider_reference.

9. POST /api/v1/risk-forecasting/notification-batches/<batch_id>/retry-failed
   Retries any FAILED items. Verified that SUCCEEDED items are NOT redelivered.

10. GET /api/v1/risk-forecasting/advisories/<advisory_id>
    GET /api/v1/risk-forecasting/records/<forecast_id>
    Confirm advisory status remains "APPROVED" and forecast record remains unchanged.
"""


@router.post(
    "/advisories/{advisory_id}/notification-batches",
    response_model=NotificationBatch,
    status_code=status.HTTP_201_CREATED,
    summary="Enqueue Approved Advisory for Notification Delivery"
)
def enqueue_notification_batch(
    advisory_id: str,
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    request: Optional[EnqueueNotificationBatchRequest] = Body(None)
):
    """
    Enqueues an APPROVED advisory into the notification outbox for recipient delivery.
    Creates frozen delivery payloads for all resolved recipients without invoking external services.
    """
    body_key = request.idempotency_key if request else None
    actor = request.created_by if request and request.created_by else "vet_officer_01"

    # Enforce idempotency header vs body consistency rule
    if idempotency_key_header and body_key:
        if idempotency_key_header != body_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Idempotency key mismatch: Header 'Idempotency-Key' ({idempotency_key_header}) "
                       f"and request body 'idempotency_key' ({body_key}) must match when both are provided."
            )
        final_key = idempotency_key_header
    else:
        final_key = idempotency_key_header or body_key

    try:
        return notification_service.enqueue_approved_advisory(
            advisory_id=advisory_id,
            created_by=actor,
            idempotency_key=final_key
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Idempotency key collision" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.get(
    "/notification-batches/{batch_id}",
    response_model=NotificationBatch,
    summary="Retrieve Notification Batch Summary"
)
def get_notification_batch(batch_id: str):
    """Retrieves notification batch summary by batch ID."""
    try:
        return notification_service.get_batch(batch_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/notification-batches",
    response_model=NotificationBatchListResponse,
    summary="List Notification Batches"
)
def list_notification_batches(
    advisory_id: Optional[str] = Query(None, description="Filter by referenced advisory ID"),
    forecast_id: Optional[str] = Query(None, description="Filter by referenced forecast ID"),
    status_filter: Optional[Literal["QUEUED", "PROCESSING", "COMPLETED", "PARTIALLY_FAILED", "FAILED", "CANCELLED"]] = Query(
        None, alias="status", description="Filter by batch status"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum batches to return (1-200)"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """Lists stored notification batches matching specified query filters with pagination."""
    return notification_service.list_batches(
        advisory_id=advisory_id,
        forecast_id=forecast_id,
        status=status_filter,
        limit=limit,
        offset=offset
    )


@router.get(
    "/notification-batches/{batch_id}/deliveries",
    response_model=NotificationDeliveryListResponse,
    summary="List Per-Recipient Deliveries for Notification Batch"
)
def list_batch_deliveries(
    batch_id: str,
    status_filter: Optional[Literal["PENDING", "PROCESSING", "SUCCEEDED", "FAILED", "CANCELLED"]] = Query(
        None, alias="status", description="Filter by delivery status"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum items to return (1-200)"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """Lists per-recipient delivery items for a specific notification batch."""
    try:
        return notification_service.list_batch_deliveries(
            batch_id=batch_id,
            status=status_filter,
            limit=limit,
            offset=offset
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/notification-batches/{batch_id}/dispatch",
    response_model=NotificationBatch,
    summary="Dispatch Pending Deliveries for Notification Batch"
)
def dispatch_notification_batch(batch_id: str):
    """
    Explicitly dispatches all PENDING delivery items in a batch through the mock provider.
    Updates delivery items to SUCCEEDED or FAILED and recalculates batch status.
    """
    try:
        return notification_service.dispatch_batch(batch_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except ValueError as e:
        err_msg = str(e)
        if "CANCELLED" in err_msg or "is no longer APPROVED" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/notification-batches/{batch_id}/retry-failed",
    response_model=NotificationBatch,
    summary="Retry Failed Deliveries for Notification Batch"
)
def retry_failed_notification_deliveries(batch_id: str):
    """
    Retries all FAILED delivery items in a batch through the mock provider.
    Leaves SUCCEEDED items untouched.
    """
    try:
        return notification_service.retry_failed_deliveries(batch_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "CANCELLED" in err_msg or "is no longer APPROVED" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/notification-batches/{batch_id}/cancel",
    response_model=NotificationBatch,
    summary="Cancel Safe Queued Notification Batch"
)
def cancel_notification_batch(batch_id: str):
    """
    Cancels a safe QUEUED notification batch prior to any delivery attempts.
    Rejects cancellation with HTTP 409 if any delivery attempt has already commenced.
    """
    try:
        return notification_service.cancel_notification_batch(batch_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Cannot cancel notification batch after delivery attempts" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


# ─── Forecast-Linked DAPH–Vet Follow-Up Endpoints (Phase 6B-1) ─────────────

@router.get(
    "/follow-up-vets",
    response_model=EligibleVetListResponse,
    summary="List Active Eligible Veterinary Officers for a District"
)
def list_eligible_follow_up_vets(
    district: str = Query(..., description="Target Sri Lankan district name"),
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID"),
    x_actor_role: Optional[str] = Header(None, alias="X-Actor-Role"),
):
    """
    Retrieves active Veterinary Officers eligible for follow-up assignment in a specified district.

    AUTHORIZATION BOUNDARY:
    - Standalone route authorizes DAPH_OFFICIAL role via X-Actor-ID and X-Actor-Role headers.
    - X-Actor-Role: SYSTEM is explicitly rejected with HTTP 403 Forbidden to prevent header spoofing.
    - Production integration must derive role and NATIONAL scope from verified JWT / central IAM claims.
    """
    actor = None
    if x_actor_id and x_actor_role:
        try:
            actor = FollowUpActorContext(actor_id=x_actor_id.strip(), role=x_actor_role.strip())
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Actor '{x_actor_id}' with role '{x_actor_role}' is not authorized to query eligible Veterinary Officers for follow-up assignment."
            )

    try:
        return forecast_follow_up_service.list_eligible_vets(district=district, actor=actor)
    except ValueError as e:
        err_msg = str(e)
        if "not authorized" in err_msg or "Actor context" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/follow-ups",

    response_model=List[ForecastFollowUpRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Issue DAPH Operational Follow-Up Instructions"
)
def issue_follow_up(
    request: CreateFollowUpRequest,
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID"),
    x_actor_role: Optional[str] = Header(None, alias="X-Actor-Role"),
):
    """
    Issues new DAPH operational follow-up instructions linked to an official forecast record.
    Copies scientific snapshots directly from stored ForecastDecisionRecord.
    """
    body_key = request.idempotency_key
    if idempotency_key_header and body_key:
        if idempotency_key_header != body_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Idempotency key mismatch: Header 'Idempotency-Key' ({idempotency_key_header}) "
                       f"and request body 'idempotency_key' ({body_key}) must match when both are provided."
            )
        final_key = idempotency_key_header
    else:
        final_key = idempotency_key_header or body_key

    if x_actor_role == "SYSTEM":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Actor '{x_actor_id}' with role 'SYSTEM' is not authorized for public follow-up operations."
        )

    req_with_key = request.model_copy(update={"idempotency_key": final_key})
    actor_id = x_actor_id or "daph_hq_01"
    actor_role = x_actor_role or "DAPH_OFFICIAL"
    actor = FollowUpActorContext(actor_id=actor_id, role=actor_role)

    try:
        return forecast_follow_up_service.issue_follow_up(req_with_key, actor=actor)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Idempotency key collision" in err_msg or "already exists" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        elif "not authorized" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.get(
    "/follow-ups",
    response_model=FollowUpListResponse,
    summary="List Forecast Follow-Up Records"
)
def list_follow_ups(
    forecast_id: Optional[str] = Query(None, description="Filter by referenced forecast ID"),
    district: Optional[str] = Query(None, description="Filter by district name"),
    disease: Optional[Literal["FMD", "LSD"]] = Query(None, description="Filter by disease type"),
    assigned_vet_id: Optional[str] = Query(None, description="Filter by assigned Veterinary Officer ID"),
    issued_by_daph_id: Optional[str] = Query(None, description="Filter by issuing DAPH official ID"),
    status_filter: Optional[Literal["ISSUED", "ACKNOWLEDGED", "ACTION_IN_PROGRESS", "COMPLETED", "CANCELLED", "ESCALATED"]] = Query(
        None, alias="status", description="Filter by follow-up status"
    ),
    target_year: Optional[int] = Query(None, description="Filter by target forecast year"),
    target_month: Optional[int] = Query(None, description="Filter by target forecast month"),
    limit: int = Query(50, ge=1, le=200, description="Maximum items to return (1-200)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID"),
    x_actor_role: Optional[str] = Header(None, alias="X-Actor-Role"),
):
    """Lists stored follow-up records matching specified query filters with pagination."""
    if x_actor_role == "SYSTEM":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Actor '{x_actor_id}' with role 'SYSTEM' is not authorized for public follow-up operations."
        )

    actor = None
    if x_actor_id or x_actor_role:
        actor = FollowUpActorContext(actor_id=x_actor_id or "daph_hq_01", role=x_actor_role or "DAPH_OFFICIAL")

    try:
        return forecast_follow_up_service.list_follow_ups(
            forecast_id=forecast_id,
            district=district,
            disease=disease,
            assigned_vet_id=assigned_vet_id,
            issued_by_daph_id=issued_by_daph_id,
            status=status_filter,
            target_year=target_year,
            target_month=target_month,
            limit=limit,
            offset=offset,
            actor=actor,
        )
    except ValueError as e:
        err_msg = str(e)
        if "not authorized" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.get(
    "/follow-ups/{follow_up_id}",
    response_model=ForecastFollowUpRecord,
    summary="Retrieve Follow-Up Record by ID"
)
def get_follow_up(
    follow_up_id: str,
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID"),
    x_actor_role: Optional[str] = Header(None, alias="X-Actor-Role"),
):
    """Retrieves a single follow-up record by follow_up_id."""
    if x_actor_role == "SYSTEM":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Actor '{x_actor_id}' with role 'SYSTEM' is not authorized for public follow-up operations."
        )
    actor = None
    if x_actor_id or x_actor_role:
        actor = FollowUpActorContext(actor_id=x_actor_id or "daph_hq_01", role=x_actor_role or "DAPH_OFFICIAL")

    try:
        return forecast_follow_up_service.get_follow_up(follow_up_id, actor=actor)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "not authorized" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/follow-ups/{follow_up_id}/acknowledge",
    response_model=ForecastFollowUpRecord,
    summary="Acknowledge Follow-Up Instruction (Assigned Vet Only)"
)
def acknowledge_follow_up(
    follow_up_id: str,
    version: Optional[int] = Query(None, ge=1, description="Expected version for optimistic locking"),
    request: Optional[TransitionFollowUpRequest] = Body(None),
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID"),
    x_actor_role: Optional[str] = Header(None, alias="X-Actor-Role"),
):
    """Transitions status from ISSUED -> ACKNOWLEDGED. Only the assigned Veterinary Officer may acknowledge."""
    expected_ver = request.version if request else version
    if expected_ver is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query parameter or body 'version' is required.")

    actor_id = x_actor_id or "vet_officer_01"
    actor_role = x_actor_role or "VETERINARY_OFFICER"
    actor = FollowUpActorContext(actor_id=actor_id, role=actor_role)

    try:
        return forecast_follow_up_service.acknowledge_follow_up(
            follow_up_id=follow_up_id,
            expected_version=expected_ver,
            actor=actor,
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg or "Cannot acknowledge" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        elif "Only a Veterinary Officer" in err_msg or "not the assigned officer" in err_msg or "not authorized" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/follow-ups/{follow_up_id}/start",
    response_model=ForecastFollowUpRecord,
    summary="Start Follow-Up Action (Assigned Vet Only)"
)
def start_follow_up_action(
    follow_up_id: str,
    version: Optional[int] = Query(None, ge=1, description="Expected version for optimistic locking"),
    request: Optional[TransitionFollowUpRequest] = Body(None),
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID"),
    x_actor_role: Optional[str] = Header(None, alias="X-Actor-Role"),
):
    """Transitions status from ACKNOWLEDGED -> ACTION_IN_PROGRESS."""
    expected_ver = request.version if request else version
    if expected_ver is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query parameter or body 'version' is required.")

    actor_id = x_actor_id or "vet_officer_01"
    actor_role = x_actor_role or "VETERINARY_OFFICER"
    actor = FollowUpActorContext(actor_id=actor_id, role=actor_role)

    try:
        return forecast_follow_up_service.start_follow_up_action(
            follow_up_id=follow_up_id,
            expected_version=expected_ver,
            actor=actor,
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg or "Cannot start" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        elif "Only assigned Veterinary Officer" in err_msg or "not authorized" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/follow-ups/{follow_up_id}/complete",
    response_model=ForecastFollowUpRecord,
    summary="Complete Follow-Up Action (Assigned Vet Only)"
)
def complete_follow_up(
    follow_up_id: str,
    version: Optional[int] = Query(None, ge=1, description="Expected version for optimistic locking"),
    request: Optional[TransitionFollowUpRequest] = Body(None),
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID"),
    x_actor_role: Optional[str] = Header(None, alias="X-Actor-Role"),
):
    """Transitions status from ACTION_IN_PROGRESS -> COMPLETED."""
    expected_ver = request.version if request else version
    if expected_ver is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query parameter or body 'version' is required.")

    actor_id = x_actor_id or "vet_officer_01"
    actor_role = x_actor_role or "VETERINARY_OFFICER"
    actor = FollowUpActorContext(actor_id=actor_id, role=actor_role)

    try:
        return forecast_follow_up_service.complete_follow_up(
            follow_up_id=follow_up_id,
            expected_version=expected_ver,
            actor=actor,
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg or "Cannot complete" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        elif "Only assigned Veterinary Officer" in err_msg or "not authorized" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/follow-ups/{follow_up_id}/cancel",
    response_model=ForecastFollowUpRecord,
    summary="Cancel Follow-Up Instruction (DAPH Official Only)"
)
def cancel_follow_up(
    follow_up_id: str,
    version: Optional[int] = Query(None, ge=1, description="Expected version for optimistic locking"),
    request: Optional[TransitionFollowUpRequest] = Body(None),
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID"),
    x_actor_role: Optional[str] = Header(None, alias="X-Actor-Role"),
):
    """Transitions status to CANCELLED. DAPH Official only from ISSUED, ACKNOWLEDGED, or ACTION_IN_PROGRESS."""
    if x_actor_role == "SYSTEM":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Actor '{x_actor_id}' with role 'SYSTEM' is not authorized to cancel follow-up instructions via public HTTP API."
        )

    expected_ver = request.version if request else version
    if expected_ver is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query parameter or body 'version' is required.")

    reason = request.reason if request else None
    actor_id = x_actor_id or "daph_hq_01"
    actor_role = x_actor_role or "DAPH_OFFICIAL"
    actor = FollowUpActorContext(actor_id=actor_id, role=actor_role)

    try:
        return forecast_follow_up_service.cancel_follow_up(
            follow_up_id=follow_up_id,
            expected_version=expected_ver,
            reason=reason,
            actor=actor,
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg or "Cannot cancel" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        elif "Only DAPH Officials" in err_msg or "not authorized" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/follow-ups/{follow_up_id}/escalate",
    response_model=ForecastFollowUpRecord,
    summary="Escalate Follow-Up Instruction"
)
def escalate_follow_up(
    follow_up_id: str,
    request: TransitionFollowUpRequest,
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID"),
    x_actor_role: Optional[str] = Header(None, alias="X-Actor-Role"),
):
    """Transitions status to ESCALATED. Requires explicit controlled reason."""
    if x_actor_role == "SYSTEM":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Actor '{x_actor_id}' with role 'SYSTEM' is not authorized for public follow-up operations."
        )

    if not request.reason or not request.reason.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reason field is required for escalation.")

    actor_id = x_actor_id or "vet_officer_01"
    actor_role = x_actor_role or "VETERINARY_OFFICER"
    actor = FollowUpActorContext(actor_id=actor_id, role=actor_role)

    try:
        return forecast_follow_up_service.escalate_follow_up(
            follow_up_id=follow_up_id,
            expected_version=request.version,
            reason=request.reason,
            actor=actor,
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg or "Cannot escalate" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        elif "not authorized" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/follow-ups/{follow_up_id}/external-resource-reference",
    response_model=ForecastFollowUpRecord,
    summary="Link External Resource Request Reference ID"
)
def link_external_resource_reference(
    follow_up_id: str,
    request: LinkExternalResourceRequest,
    x_actor_id: Optional[str] = Header(None, alias="X-Actor-ID"),
    x_actor_role: Optional[str] = Header(None, alias="X-Actor-Role"),
):
    """Associates an opaque external supply-chain resource request reference ID."""
    if x_actor_role == "SYSTEM":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Actor '{x_actor_id}' with role 'SYSTEM' is not authorized for public follow-up operations."
        )
    actor_id = x_actor_id or "daph_hq_01"
    actor_role = x_actor_role or "DAPH_OFFICIAL"
    actor = FollowUpActorContext(actor_id=actor_id, role=actor_role)

    try:
        return forecast_follow_up_service.link_external_resource_request(
            follow_up_id=follow_up_id,
            expected_version=request.version,
            external_resource_request_id=request.external_resource_request_id,
            actor=actor,
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg or "Cannot link" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        elif "not authorized" in err_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

@router.get(
    "/notifications",
    summary="List Farmer Forecasting Notifications"
)
async def list_farmer_notifications(
    authorization: Optional[str] = Header(None)
):
    import jwt
    from core.security import JWT_SECRET, JWT_ALGORITHM
    from core.database import farms_collection
    from components.risk_forecasting.repositories.farmer_notification_repository import list_for_farm

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token.")

    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        role = payload.get("role")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    if role == "vet" or role == "daph":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role forbidden.")
    if role and role != "farmer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role forbidden.")

    farm = await farms_collection.find_one({"email": email})
    if not farm:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farm profile not found.")

    farm_id = str(farm["_id"])
    notifications = await list_for_farm(farm_id)
    return notifications

@router.post(
    "/advisories/{advisory_id}/forward-to-assigned-farmers",
    summary="Forward Advisory to Assigned Farmers"
)
async def forward_to_assigned_farmers(
    advisory_id: str,
    authorization: Optional[str] = Header(None)
):
    import jwt
    from core.security import JWT_SECRET, JWT_ALGORITHM
    from core.database import vets_collection, farms_collection
    from components.risk_forecasting.repositories.farmer_notification_repository import forward_to_assigned_farms
    from bson import ObjectId

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token.")

    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        role = payload.get("role")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    if role != "vet":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Veterinary Officers can forward advisories.")

    vet = await vets_collection.find_one({"email": email})
    if not vet:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Veterinary profile not found.")

    try:
        advisory = advisory_service.get_advisory(advisory_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    vet_id_str = str(vet["_id"])
    assigned_farm_ids = [ObjectId(f) for f in vet.get("assigned_farm_ids", []) if ObjectId.is_valid(f)]
    assigned_farm_emails = vet.get("assigned_farms", [])

    query = {
        "$or": [
            {"_id": {"$in": assigned_farm_ids}},
            {"email": {"$in": assigned_farm_emails}},
            {"assigned_vet_ids": vet_id_str},
            {"assigned_vet_emails": vet["email"]}
        ]
    }

    cursor = farms_collection.find(query)
    assigned_farms = []
    seen = set()
    async for farm_doc in cursor:
        f_id = str(farm_doc["_id"])
        if f_id not in seen:
            seen.add(f_id)
            assigned_farms.append(farm_doc)

    if not assigned_farms:
        return {
            "advisory_id": advisory_id,
            "notified_count": 0,
            "already_notified_count": 0,
            "status": "forwarded"
        }

    try:
        result = await forward_to_assigned_farms(advisory, assigned_farms, vet)
        return {
            "advisory_id": advisory_id,
            "notified_count": result["notified_count"],
            "already_notified_count": result["already_notified_count"],
            "status": "forwarded"
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to forward advisory to farmers: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while forwarding notifications.")


@router.get(
    "/outbreak-status/{disease}/{district}/{year}/{month}",
    response_model=OutbreakStatusResponse,
    summary="Get Outbreak Status for a District and Month"
)
async def get_outbreak_status(disease: str, district: str, year: int, month: int):
    disease_upper = disease.strip().upper()
    if disease_upper not in ["FMD", "LSD"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported disease. Allowed: FMD, LSD."
        )
    formatted_district = district.strip().title()
    if formatted_district in ["Moneragala", "Monaragala"]:
        formatted_district = "Monaragala"
    elif formatted_district in ["Nuwaraeliya", "Nuwara Eliya"]:
        formatted_district = "Nuwara Eliya"
    
    if formatted_district not in SRI_LANKA_DISTRICTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported Sri Lankan district: '{district}'"
        )
    
    if not (2017 <= year <= 2030):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Year must be between 2017 and 2030."
        )
    
    if not (1 <= month <= 12):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Month must be between 1 and 12."
        )
    
    client = get_shared_client()
    try:
        outbreak_status, cases_count, deaths_count = await client.get_district_status_async(
            disease_upper, formatted_district, year, month
        )
        return OutbreakStatusResponse(
            district=formatted_district,
            disease=disease_upper,
            year=year,
            month=month,
            outbreak_status=outbreak_status,
            cases_count=cases_count,
            deaths_count=deaths_count
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error computing outbreak status: {str(e)}"
        )

