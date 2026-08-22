"""
Forecast Decision Record Service.

Provides domain business logic for generating, persisting, and querying immutable
ForecastDecisionRecord instances mapped directly from authoritative FMD and LSD model predictions.

ARCHITECTURAL PRINCIPLES:
1. Scientific Authority: Model predictions are generated strictly by invoking FMDService or LSDService.
   This service does NOT alter, re-estimate, or fabricate model inference outputs.
2. Immutability: Once saved, scientific risk parameters (probability, risk_level, predicted_severity)
   are immutable.
3. Idempotency: Duplicate submissions with identical idempotency keys return the pre-existing record.
   Submissions reusing an idempotency key with conflicting request parameters are explicitly rejected.
4. Dependency Injection: Repository, model services, clock, and ID generation are fully injectable
   for isolation testing and future database adapter integration.
"""

from datetime import datetime, timezone
import uuid
from typing import Callable, Optional, Tuple

from backend.components.risk_forecasting.repositories.forecast_record_repository import (
    ForecastRecordRepository,
    InMemoryForecastRecordRepository,
)
from backend.components.risk_forecasting.schemas import (
    FMDOutbreakPredictRequest,
    FMDOutbreakPredictResponse,
    ForecastDecisionRecord,
    ForecastRecordListResponse,
    GenerateForecastRecordRequest,
    LSDOutbreakPredictRequest,
    LSDOutbreakPredictResponse,
)
from backend.components.risk_forecasting.services.fmd_service import FMDService, fmd_service
from backend.components.risk_forecasting.services.lsd_service import LSDService, lsd_service


class ForecastRecordService:
    """Service layer for managing immutable Forecast Decision Records."""

    def __init__(
        self,
        repository: Optional[ForecastRecordRepository] = None,
        fmd_svc: Optional[FMDService] = None,
        lsd_svc: Optional[LSDService] = None,
        clock: Optional[Callable[[], datetime]] = None,
        id_generator: Optional[Callable[[], str]] = None,
    ):
        self.repository = repository or InMemoryForecastRecordRepository()
        self.fmd_svc = fmd_svc or fmd_service
        self.lsd_svc = lsd_svc or lsd_service
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_generator = id_generator or (lambda: f"fdr_{uuid.uuid4().hex[:12]}")

    def generate_record(
        self, request: GenerateForecastRecordRequest
    ) -> ForecastDecisionRecord:
        """
        Invokes authoritative model prediction and maps the response to an immutable decision record.
        Enforces idempotency and safe transactional creation.
        """
        disease_upper = request.disease.upper()

        # 1. Idempotency Key Safeguard
        if request.idempotency_key:
            existing = self.repository.find_by_idempotency_key(request.idempotency_key)
            if existing:
                # Determine expected model variant
                expected_variant = request.model_variant
                if not expected_variant:
                    expected_variant = (
                        "30_feature_baseline" if disease_upper == "FMD" else "28_feature_autocorrelation"
                    )

                # Check if request parameters match existing record exactly
                matches = (
                    existing.disease == disease_upper
                    and existing.district == request.district
                    and existing.target_year == request.year
                    and existing.target_month == request.month
                )
                if matches:
                    return existing
                else:
                    raise ValueError(
                        f"Idempotency key collision: Key '{request.idempotency_key}' "
                        f"was previously used with different forecast request parameters."
                    )

        # 2. Invoke Authoritative Prediction Service
        if disease_upper == "FMD":
            variant = request.model_variant or "30_feature_baseline"
            fmd_req = FMDOutbreakPredictRequest(
                district=request.district,
                year=request.year,
                month=request.month,
                model_variant=variant,
            )
            prediction: FMDOutbreakPredictResponse = self.fmd_svc.predict(fmd_req)

            probability = prediction.stage1.probability
            probability_pct = prediction.stage1.probability_pct
            risk_level = prediction.stage1.risk_level
            predicted_severity = (
                prediction.stage2.severity_predicted if prediction.stage2.evaluated else None
            )
            model_variant = prediction.stage1.model_variant
            fallback_applied = prediction.provenance.fallback_applied
            source_year = prediction.provenance.source_year
            source_month = prediction.provenance.source_month
            data_age_months = prediction.provenance.data_age_months
            data_quality = prediction.provenance.data_quality
            fallback_message = prediction.provenance.fallback_message
            raw_disclaimer = getattr(prediction, "disclaimer", None)
            disclaimer = (
                raw_disclaimer.strip() if (raw_disclaimer and raw_disclaimer.strip()) else
                "FMD Stage 1 and Stage 2 model predictions serve as statistical decision support "
                "based on audited climate and spatial surveillance indices."
            )

        elif disease_upper == "LSD":
            lsd_req = LSDOutbreakPredictRequest(
                district=request.district,
                year=request.year,
                month=request.month,
            )
            prediction: LSDOutbreakPredictResponse = self.lsd_svc.predict(lsd_req)

            probability = prediction.stage1.probability
            probability_pct = prediction.stage1.probability_pct
            risk_level = prediction.stage1.risk_level
            predicted_severity = prediction.stage2.severity_predicted
            model_variant = prediction.stage1.model_variant
            fallback_applied = prediction.provenance.fallback_applied
            source_year = prediction.provenance.source_year
            source_month = prediction.provenance.source_month
            data_age_months = prediction.provenance.data_age_months
            data_quality = prediction.provenance.data_quality
            fallback_message = prediction.provenance.fallback_message
            raw_disclaimer = getattr(prediction, "disclaimer", None)
            disclaimer = (
                raw_disclaimer.strip() if (raw_disclaimer and raw_disclaimer.strip()) else
                "LSD Stage 2 binary severity predictions serve strictly as a quiet-period false-alarm suppressor (LOW vs MOD/HIGH) and are NOT statistically validated to discriminate severity during active outbreak waves."
            )


        else:
            raise ValueError(f"Unsupported disease type '{request.disease}'. Allowed: FMD, LSD.")

        # 3. Construct Immutable Record
        now_dt = self.clock()
        now_iso = now_dt.isoformat()
        forecast_id = self.id_generator()

        record = ForecastDecisionRecord(
            forecast_id=forecast_id,
            disease=disease_upper,
            district=request.district,
            target_year=request.year,
            target_month=request.month,
            generated_at=now_iso,
            probability=probability,
            probability_pct=probability_pct,
            risk_level=risk_level,
            predicted_severity=predicted_severity,
            model_variant=model_variant,
            fallback_applied=fallback_applied,
            source_year=source_year,
            source_month=source_month,
            data_age_months=data_age_months,
            data_quality=data_quality,
            fallback_message=fallback_message,
            status="GENERATED",
            trigger_type=request.trigger_type,
            generated_by=request.generated_by,
            disclaimer=disclaimer,
            idempotency_key=request.idempotency_key,
            created_at=now_iso,
            updated_at=now_iso,
        )

        # 4. Save to Repository
        return self.repository.save(record)

    def get_record(self, forecast_id: str) -> ForecastDecisionRecord:
        """Retrieves a forecast decision record by ID."""
        record = self.repository.get_by_id(forecast_id)
        if not record:
            raise KeyError(f"Forecast decision record with ID '{forecast_id}' not found.")
        return record

    def list_records(
        self,
        disease: Optional[str] = None,
        district: Optional[str] = None,
        target_year: Optional[int] = None,
        target_month: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ForecastRecordListResponse:
        """Queries stored forecast decision records with bounded filters."""
        # Limit boundary enforcement (max 200)
        bounded_limit = min(max(1, limit), 200)
        bounded_offset = max(0, offset)

        records, total_count = self.repository.list(
            disease=disease,
            district=district,
            target_year=target_year,
            target_month=target_month,
            status=status,
            limit=bounded_limit,
            offset=bounded_offset,
        )

        return ForecastRecordListResponse(
            total_count=total_count,
            limit=bounded_limit,
            offset=bounded_offset,
            records=records,
        )


# Singleton Instance for Default Route Injection
forecast_record_service = ForecastRecordService()
