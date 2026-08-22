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
    AdvisoryPreviewResponse, AdvisoryListResponse,
    NotificationBatch, NotificationDelivery, EnqueueNotificationBatchRequest,
    NotificationBatchListResponse, NotificationDeliveryListResponse,
    RecipientSummaryItem, AssignedRecipientListResponse
)
from backend.components.risk_forecasting.services.fmd_service import fmd_service
from backend.components.risk_forecasting.services.lsd_service import lsd_service
from backend.components.risk_forecasting.services.forecast_record_service import forecast_record_service
from backend.components.risk_forecasting.services.advisory_service import advisory_service
from backend.components.risk_forecasting.services.notification_service import notification_service
from backend.components.risk_forecasting.services.recipient_query_service import recipient_query_service

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
