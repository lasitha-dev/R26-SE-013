"""
Pydantic Request and Response Schemas for the Risk Forecasting Component API.
Provides validation and documentation for FMD and LSD prediction and forecast endpoints.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from backend.components.risk_forecasting.config import SRI_LANKA_DISTRICTS, MONTH_NAMES


# ─── Shared Base Request Models ──────────────────────────────────────────────

class BasePredictRequest(BaseModel):
    district: str = Field(..., example="Anuradhapura", description="Name of the Sri Lankan district.")
    year: int = Field(..., example=2024, ge=2017, le=2030, description="Target prediction year (2017-2030).")
    month: int = Field(..., example=1, ge=1, le=12, description="Target prediction month (1-12).")

    @field_validator("district")
    @classmethod
    def validate_district(cls, v: str) -> str:
        formatted = v.strip().title()
        # Handle special casing for Sri Lanka district names
        if formatted in ["Moneragala", "Monaragala"]:
            formatted = "Monaragala"
        elif formatted in ["Nuwaraeliya", "Nuwara Eliya"]:
            formatted = "Nuwara Eliya"

        if formatted not in SRI_LANKA_DISTRICTS:
            raise ValueError(f"Invalid district '{v}'. Must be one of {SRI_LANKA_DISTRICTS}")
        return formatted


class FMDOutbreakPredictRequest(BasePredictRequest):
    model_variant: Literal["30_feature_baseline", "31_feature_autocorrelation"] = Field(
        default="30_feature_baseline",
        description="FMD Stage 1 model variant: 30-feature parsimonious baseline (default) or 31-feature target autocorrelation variant."
    )


class LSDOutbreakPredictRequest(BasePredictRequest):
    """LSD Outbreak Predict Request - Single 28-feature Elastic Net production model."""
    pass


class FMDForecastRequest(BaseModel):
    target_month: int = Field(..., example=1, ge=1, le=12, description="Target forecast month (1-12).")
    year: Optional[int] = Field(default=2024, ge=2017, le=2030, description="Reference forecast year (default 2024).")
    model_variant: Literal["30_feature_baseline"] = Field(
        default="30_feature_baseline",
        description="National FMD forecast model variant (standalone mode supports 30_feature_baseline only)."
    )


class LSDForecastRequest(BaseModel):
    target_month: int = Field(..., example=1, ge=1, le=12, description="Target forecast month (1-12).")
    year: Optional[int] = Field(default=2024, ge=2017, le=2030, description="Reference forecast year (default 2024).")


# ─── Response Components ─────────────────────────────────────────────────────

class Stage1Prediction(BaseModel):
    probability: float = Field(..., example=0.684, description="Predicted outbreak probability (0.0 to 1.0).")
    probability_pct: float = Field(..., example=68.4, description="Outbreak probability percentage.")
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(..., example="HIGH", description="Categorical risk tier based on t=0.40 decision boundary.")
    decision_threshold: float = Field(default=0.40, example=0.40, description="Audited operational decision threshold.")
    model_variant: str = Field(..., example="30_feature_baseline", description="Model architecture variant used for inference.")


class Stage2Prediction(BaseModel):
    severity_predicted: str = Field(..., example="HIGH", description="Predicted severity category.")
    severity_code: int = Field(..., example=2, description="Numerical severity code.")
    model_name: str = Field(..., example="RandomForestClassifier", description="Trained Stage 2 classifier name.")
    evaluated: bool = Field(..., example=True, description="Whether Stage 2 model was explicitly evaluated (True when Stage 1 prob >= 0.40; False when bypassed).")
    discriminator_validated: bool = Field(..., example=True, description="Whether Stage 2 is statistically validated for active outbreak discrimination.")
    action_required: bool = Field(..., example=True, description="Whether Stage 2 severity triggers emergency escalation. Note: Stage 1 risk_level assesses outbreak occurrence likelihood, whereas Stage 2 assesses severity. A HIGH outbreak likelihood with LOW predicted severity means an outbreak is likely but mild, so action_required is False.")

    notes: Optional[str] = Field(default=None, example="Stage 2 model evaluated.", description="Explanatory notes on Stage 2 evaluation status.")



class CalibrationInfo(BaseModel):
    is_calibrated: bool = Field(..., example=False, description="Whether probability calibration was applied.")
    calibration_method: str = Field(..., example="Uncalibrated Raw Logistic Regression", description="Calibration algorithm name.")
    ece_score: Optional[float] = Field(default=None, example=0.0212, description="Expected Calibration Error (ECE) if calibrated.")
    notes: str = Field(..., description="Methodological notes regarding probability calibration.")



class UncertaintyInfo(BaseModel):
    method: str = Field(..., example="Rule-Based Risk Tier Uncertainty", description="Uncertainty quantification technique.")
    status: str = Field(..., example="HEURISTIC", description="UQ status (HEURISTIC, VALIDATED, or UNRELIABLE_INSUFFICIENT_DATA).")
    reliability: Literal["HIGH", "MEDIUM", "LOW"] = Field(..., example="MEDIUM", description="Reliability grade of uncertainty output.")
    prediction_set: Optional[List[str]] = Field(default=None, example=["MEDIUM", "HIGH"], description="Prediction/uncertainty set returned by active uncertainty method; null when unavailable or unreliable.")
    empirical_coverage_pct: Optional[float] = Field(default=None, example=None, description="Empirical coverage percentage on test data (null for heuristic or unreliable outputs).")
    notes: str = Field(..., description="Details regarding uncertainty coverage guarantees, heuristic mappings, or sample-size caveats.")


class DataProvenance(BaseModel):
    fallback_applied: bool = Field(..., example=False, description="Whether historical data fallback was applied for input features.")
    fallback_message: str = Field(..., example="Exact feature row found for requested district and period.", description="Data provenance message.")
    requested_year: int = Field(..., example=2024, description="Target prediction requested year.")
    requested_month: int = Field(..., example=1, description="Target prediction requested month.")
    source_year: Optional[int] = Field(default=None, example=2024, description="Actual historical year source of feature row (null for medians).")
    source_month: Optional[int] = Field(default=None, example=1, description="Actual historical month source of feature row (null for medians).")
    data_age_months: Optional[int] = Field(default=0, example=0, description="Age of feature row relative to requested period in months (0 for exact, null for medians).")
    data_quality: Literal[
        "EXACT_REQUESTED_PERIOD",
        "HISTORICAL_SAME_MONTH_PROXY",
        "DISTRICT_HISTORICAL_MEDIAN",
        "NATIONAL_HISTORICAL_MEDIAN"
    ] = Field(..., example="EXACT_REQUESTED_PERIOD", description="Classification of feature input data quality.")


class FMDDataProvenance(DataProvenance):
    model_fallback_applied: bool = Field(default=False, example=False, description="Whether 31-to-30 feature model variant fallback was applied.")
    model_fallback_reason: Optional[str] = Field(default=None, example=None, description="Detailed rationale if model variant fallback occurred.")


class LSDDataProvenance(DataProvenance):
    lag1_status: Literal["VERIFIED_OBSERVATION", "UNAVAILABLE"] = Field(
        ...,
        example="VERIFIED_OBSERVATION",
        description="Target autocorrelation lag-1 observation status for own_outbreak_lag1."
    )
    lag1_value: Optional[float] = Field(
        default=None,
        example=1.0,
        description="Actual ground-truth Outbreak status value (0.0 or 1.0) if verified observation was available."
    )
    lag1_message: Optional[str] = Field(
        default=None,
        example=None,
        description="Detailed rationale regarding target autocorrelation lag-1 observation status."
    )
    model_fallback_applied: bool = Field(
        default=False,
        example=False,
        description="Whether 28-to-27 feature model variant fallback was applied due to missing 28-feature artifacts."
    )
    model_fallback_reason: Optional[str] = Field(
        default=None,
        example=None,
        description="Detailed rationale if model variant fallback occurred."
    )


class FeatureContribution(BaseModel):
    feature: str = Field(..., example="r3h", description="Technical feature name.")
    display_label: str = Field(..., example="3-Hour Relative Humidity (%)", description="Human-readable feature label for UI display.")
    raw_value: float = Field(..., example=88.4, description="Unscaled raw feature input value.")
    contribution_log_odds: float = Field(..., example=-1.12, description="Additive contribution of feature to Logistic Regression log-odds decision score.")
    direction: Literal["RISK_INCREASING", "RISK_DECREASING", "NEUTRAL"] = Field(..., example="RISK_DECREASING", description="Direction of feature influence on outbreak risk.")


class ExplanationInfo(BaseModel):
    method: str = Field(default="Linear Log-Odds Decomposition", example="Linear Log-Odds Decomposition", description="Explainability decomposition technique name.")
    model_variant: str = Field(..., example="30_feature_baseline", description="Exact model variant artifact explained.")
    explanation_scope: str = Field(default="LOCAL_PREDICTION", example="LOCAL_PREDICTION", description="Scope of explanation (e.g. LOCAL_PREDICTION).")
    contribution_unit: str = Field(default="LOG_ODDS", example="LOG_ODDS", description="Unit of feature contributions (LOG_ODDS).")
    baseline_description: str = Field(default="Model decision score relative to training-mean standardized baseline.", description="Description of reference baseline for contributions.")
    top_risk_increasing: List[FeatureContribution] = Field(default_factory=list, description="Top positive feature contributions pushing risk higher.")
    top_risk_decreasing: List[FeatureContribution] = Field(default_factory=list, description="Top negative feature contributions pushing risk lower.")
    decision_score: float = Field(..., example=0.6253, description="Exact Logistic Regression log-odds decision score.")
    reconstructed_probability: float = Field(..., example=0.6514, description="Reconstructed Stage 1 outbreak probability [1 / (1 + exp(-z))].")
    provenance_warning: Optional[str] = Field(default=None, example="Some explanatory feature values were obtained from historical fallback data rather than exact target-period observations.", description="Warning if fallback data was used for explanation inputs.")
    notes: str = Field(..., description="Methodological notes explaining local feature contributions and causality disclaimers.")


# ─── Full Disease Outbreak Prediction Responses ──────────────────────────────

class FMDOutbreakPredictResponse(BaseModel):
    disease: Literal["FMD"] = Field(default="FMD")
    district: str
    year: int
    month: int
    month_name: str
    stage1: Stage1Prediction
    stage2: Stage2Prediction
    calibration_info: CalibrationInfo
    uncertainty: UncertaintyInfo
    recommendations: List[str]
    provenance: FMDDataProvenance
    explanation_info: Optional[ExplanationInfo] = Field(default=None, description="Local explainability breakdown of Stage 1 prediction factors.")


class LSDOutbreakPredictResponse(BaseModel):
    disease: Literal["LSD"] = Field(default="LSD")
    district: str
    year: int
    month: int
    month_name: str
    stage1: Stage1Prediction
    stage2: Stage2Prediction
    calibration_info: CalibrationInfo
    uncertainty: UncertaintyInfo
    recommendations: List[str]
    disclaimer: str = Field(
        ...,
        example="LSD Stage 2 binary severity predictions serve strictly as a quiet-period false-alarm suppressor (LOW vs MOD/HIGH) and are NOT statistically validated to discriminate severity during active outbreak waves.",
        description="Mandatory scientific disclaimer regarding LSD Stage 2 limitations."
    )
    provenance: LSDDataProvenance


# ─── Forecast Schemas ────────────────────────────────────────────────────────

class DistrictForecastItem(BaseModel):
    district: str
    probability_pct: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    predicted_severity: str


class DistrictForecastResponse(BaseModel):
    disease: str
    target_year: int = Field(..., example=2024, description="Target forecast reference year (2017-2030).")
    target_month: int = Field(..., example=1, ge=1, le=12, description="Target forecast month (1-12).")
    target_month_name: str = Field(..., example="January", description="Target forecast month name.")
    total_districts: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    districts: List[DistrictForecastItem]
    exact_data_district_count: int = Field(default=0, example=25, description="Number of districts using exact requested period data.")
    historical_proxy_district_count: int = Field(default=0, example=0, description="Number of districts using historical same-month proxy rows.")
    historical_median_district_count: int = Field(default=0, example=0, description="Number of districts using historical medians.")
    data_quality_status: Literal["EXACT", "MIXED", "HISTORICAL_PROXY"] = Field(default="EXACT", example="EXACT", description="Overall input data quality status across forecasted districts.")
    data_quality_message: str = Field(default="", example="All districts evaluated using exact requested period data.", description="Data quality rationale for forecast.")


class FMDDistrictForecastResponse(DistrictForecastResponse):
    model_variant: Literal["30_feature_baseline", "31_feature_autocorrelation"] = Field(
        ...,
        example="30_feature_baseline",
        description="Model architecture variant executed for all-district FMD forecast."
    )


class LSDDistrictForecastResponse(DistrictForecastResponse):
    lag1_data_status: Literal["VERIFIED_OBSERVATION", "UNAVAILABLE", "MIXED"] = Field(
        ...,
        example="UNAVAILABLE",
        description="Target autocorrelation lag-1 data status across forecasted districts."
    )
    lag1_verified_district_count: int = Field(
        ...,
        example=0,
        description="Number of districts with verified t-1 surveillance data."
    )
    lag1_unavailable_district_count: int = Field(
        ...,
        example=25,
        description="Number of districts where t-1 surveillance data was unavailable."
    )
    lag1_message: Optional[str] = Field(
        default=None,
        example=None,
        description="Top-level rationale explaining target autocorrelation lag-1 data status across districts."
    )


# ─── Metadata Schemas ────────────────────────────────────────────────────────

class HealthCheckResponse(BaseModel):
    status: str = Field(default="ok")
    component: str = Field(default="risk_forecasting")
    version: str = Field(default="1.0.0")
    models_loaded: bool
    loaded_artifacts: List[str]


class DistrictListResponse(BaseModel):
    total_districts: int
    districts: List[str]
    month_names: List[str]


# ─── Forecast Decision Record Schemas ────────────────────────────────────────

class GenerateForecastRecordRequest(BaseModel):
    disease: Literal["FMD", "LSD"] = Field(..., description="Disease type ('FMD' or 'LSD').")
    district: str = Field(..., example="Anuradhapura", description="Sri Lankan district name.")
    year: int = Field(..., example=2024, ge=2017, le=2030, description="Target forecast year (2017-2030).")
    month: int = Field(..., example=1, ge=1, le=12, description="Target forecast month (1-12).")
    model_variant: Optional[str] = Field(
        default=None,
        description="Optional model variant ('30_feature_baseline', '31_feature_autocorrelation', etc.)."
    )
    trigger_type: Literal["MANUAL", "SCHEDULED"] = Field(
        default="MANUAL",
        description="Trigger type for record generation ('MANUAL' or 'SCHEDULED')."
    )
    generated_by: Optional[str] = Field(
        default=None,
        example="user_123",
        description="Optional actor or user reference ID triggering record generation."
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        example="idemp_fmd_colombo_2024_01",
        description="Optional client-provided idempotency key for retry safeguarding."
    )

    @field_validator("district")
    @classmethod
    def validate_district(cls, v: str) -> str:
        formatted = v.strip().title()
        if formatted in ["Moneragala", "Monaragala"]:
            formatted = "Monaragala"
        elif formatted in ["Nuwaraeliya", "Nuwara Eliya"]:
            formatted = "Nuwara Eliya"

        if formatted not in SRI_LANKA_DISTRICTS:
            raise ValueError(f"Invalid district '{v}'. Must be one of {SRI_LANKA_DISTRICTS}")
        return formatted


class ForecastDecisionRecord(BaseModel):
    forecast_id: str = Field(..., example="fdr_a1b2c3d4e5", description="Unique forecast decision record identifier.")
    disease: Literal["FMD", "LSD"] = Field(..., description="Disease type ('FMD' or 'LSD').")
    district: str = Field(..., description="Target Sri Lankan district name.")
    target_year: int = Field(..., description="Target forecast year.")
    target_month: int = Field(..., description="Target forecast month (1-12).")
    generated_at: str = Field(..., description="Timezone-aware ISO 8601 UTC timestamp when record was generated.")
    probability: float = Field(..., ge=0.0, le=1.0, description="Authoritative predicted outbreak probability (0.0 to 1.0).")
    probability_pct: float = Field(..., ge=0.0, le=100.0, description="Authoritative outbreak probability percentage.")
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(..., description="Authoritative categorical outbreak risk tier.")
    predicted_severity: Optional[str] = Field(default=None, description="Stage 2 predicted severity category (null if un-evaluated).")
    model_variant: str = Field(..., description="Exact model architecture variant executed.")
    fallback_applied: bool = Field(..., description="Whether historical data fallback was applied for input features.")
    source_year: Optional[int] = Field(default=None, description="Actual historical year source of feature row (null for medians).")
    source_month: Optional[int] = Field(default=None, description="Actual historical month source of feature row (null for medians).")
    data_age_months: Optional[int] = Field(default=None, description="Age of feature row relative to requested period in months.")
    data_quality: str = Field(..., description="Input feature data quality classification.")
    fallback_message: Optional[str] = Field(default=None, description="Data provenance rationale message.")
    status: Literal["GENERATED", "AVAILABLE", "REFERENCED", "SUPERSEDED"] = Field(
        default="GENERATED",
        description="Forecast decision record lifecycle status."
    )
    trigger_type: Literal["MANUAL", "SCHEDULED"] = Field(
        default="MANUAL",
        description="Trigger type for record generation."
    )
    generated_by: Optional[str] = Field(default=None, description="Optional actor/user reference ID.")
    disclaimer: str = Field(..., description="Mandatory scientific disclaimer for model prediction.")
    idempotency_key: Optional[str] = Field(default=None, description="Idempotency key associated with this record.")
    created_at: str = Field(..., description="Timezone-aware ISO 8601 UTC creation timestamp.")
    updated_at: str = Field(..., description="Timezone-aware ISO 8601 UTC last update timestamp.")


class ForecastRecordListResponse(BaseModel):
    total_count: int = Field(..., description="Total matching record count.")
    limit: int = Field(..., description="Query limit applied.")
    offset: int = Field(..., description="Query offset applied.")
    records: List[ForecastDecisionRecord] = Field(..., description="List of forecast decision records.")


# ─── Farmer Advisory Schemas (Phase 3) ──────────────────────────────────────

class PersonalizedOverride(BaseModel):
    recipient_id: str = Field(..., description="Target recipient or farm ID.")
    custom_note: str = Field(..., description="Personalized note or special advice for this specific recipient.")

    @field_validator("recipient_id", "custom_note")
    @classmethod
    def validate_non_empty_str(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field cannot be empty or whitespace-only")
        return trimmed


class RecipientSummary(BaseModel):
    total_assigned: int = Field(..., ge=0, description="Total farms/recipients assigned to the Vet across all districts.")
    eligible_count: int = Field(..., ge=0, description="Farms assigned to the Vet located within the forecast district.")
    selected_count: int = Field(..., ge=0, description="Number of recipients targeted by this advisory.")
    standard_message_count: int = Field(..., ge=0, description="Number of recipients receiving the standard advisory message.")
    personalized_count: int = Field(..., ge=0, description="Number of recipients receiving personalized override advice.")
    excluded_count: int = Field(..., ge=0, description="Number of assigned recipients excluded from this advisory.")


class RecipientResolvedPreview(BaseModel):
    recipient_id: str = Field(..., description="Recipient or farm identifier.")
    recipient_name: str = Field(..., description="Human-readable farm/recipient name or label.")
    district: str = Field(..., description="Recipient district.")
    is_personalized: bool = Field(..., description="True if recipient has a personalized override applied.")
    final_message: str = Field(..., description="Final fully resolved message text for this recipient.")


class FarmerAdvisoryRecord(BaseModel):
    advisory_id: str = Field(..., example="adv_f1e2d3c4b5", description="Unique advisory record identifier.")
    forecast_id: str = Field(..., example="fdr_a1b2c3d4e5", description="Referenced immutable forecast decision record ID.")
    advisory_type: Literal[
        "SYSTEM_FORECAST_ADVISORY", "VETERINARY_CUSTOM_ADVICE", "OFFICIAL_DAPH_NOTICE"
    ] = Field(default="VETERINARY_CUSTOM_ADVICE", description="Type classification of advisory.")
    disease: Literal["FMD", "LSD"] = Field(..., description="Disease type derived from authoritative forecast.")
    district: str = Field(..., description="District name derived from authoritative forecast.")
    target_year: int = Field(..., description="Target forecast year.")
    target_month: int = Field(..., description="Target forecast month.")
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(..., description="Risk level derived from authoritative forecast.")
    priority: Literal["ROUTINE", "IMPORTANT", "URGENT"] = Field(..., description="Advisory priority level.")
    title: str = Field(..., description="Advisory title line.")
    standard_message: str = Field(..., description="Core standard advisory body text.")
    preventive_actions: List[str] = Field(default_factory=list, description="Recommended preventive biosecurity actions.")
    symptoms_to_watch: List[str] = Field(default_factory=list, description="Clinical symptoms for farmers to observe.")
    contact_instruction: str = Field(..., description="Instructions for contacting local Veterinary Officer.")
    vet_custom_note: Optional[str] = Field(default=None, description="Optional Vet general custom note added to standard message.")
    disclaimer: str = Field(..., description="Scientific decision-support disclaimer.")
    recipient_scope: Literal["ALL_ASSIGNED", "SELECTED"] = Field(..., description="Recipient targeting scope.")
    selected_recipient_ids: List[str] = Field(default_factory=list, description="Selected recipient IDs when scope is SELECTED.")
    personalized_overrides: List[PersonalizedOverride] = Field(default_factory=list, description="Per-recipient personalized advice overrides.")
    recipient_summary: RecipientSummary = Field(..., description="Recipient resolution metrics summary.")
    status: Literal["DRAFT", "REVIEW_READY", "APPROVED", "CANCELLED"] = Field(
        default="DRAFT", description="Advisory lifecycle status."
    )
    created_by: str = Field(..., description="Actor ID of the creator (e.g., vet_officer_01).")
    approved_by: Optional[str] = Field(default=None, description="Actor ID of the approver (populated upon approval).")
    created_at: str = Field(..., description="Timezone-aware ISO 8601 UTC creation timestamp.")
    updated_at: str = Field(..., description="Timezone-aware ISO 8601 UTC update timestamp.")
    approved_at: Optional[str] = Field(default=None, description="Timezone-aware ISO 8601 UTC approval timestamp.")
    idempotency_key: Optional[str] = Field(default=None, description="Optional client idempotency key.")
    version: int = Field(default=1, ge=1, description="Optimistic concurrency control version integer.")


class CreateAdvisoryDraftRequest(BaseModel):
    forecast_id: str = Field(..., description="Referenced forecast decision record ID.")
    advisory_type: Literal[
        "SYSTEM_FORECAST_ADVISORY", "VETERINARY_CUSTOM_ADVICE", "OFFICIAL_DAPH_NOTICE"
    ] = Field(
        default="VETERINARY_CUSTOM_ADVICE",
        description="Type classification of advisory ('SYSTEM_FORECAST_ADVISORY' or 'VETERINARY_CUSTOM_ADVICE')."
    )
    recipient_scope: Literal["ALL_ASSIGNED", "SELECTED"] = Field(
        default="ALL_ASSIGNED", description="Scope of recipient selection ('ALL_ASSIGNED' or 'SELECTED')."
    )
    selected_recipient_ids: Optional[List[str]] = Field(
        default=None, description="List of recipient/farm IDs when recipient_scope is 'SELECTED'."
    )
    vet_custom_note: Optional[str] = Field(
        default=None, description="Optional custom advice note to supplement standard message."
    )
    personalized_overrides: Optional[List[PersonalizedOverride]] = Field(
        default=None, description="Optional list of per-recipient personalized notes."
    )
    created_by: Optional[str] = Field(
        default="vet_officer_01", description="Actor or Vet user ID creating the draft."
    )
    idempotency_key: Optional[str] = Field(
        default=None, description="Optional client idempotency key."
    )

    @field_validator("vet_custom_note")
    @classmethod
    def validate_optional_note(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        return trimmed if trimmed else None


class UpdateAdvisoryDraftRequest(BaseModel):
    version: int = Field(..., ge=1, description="Expected current record version for optimistic locking.")
    recipient_scope: Optional[Literal["ALL_ASSIGNED", "SELECTED"]] = Field(
        default=None, description="Updated recipient targeting scope."
    )
    selected_recipient_ids: Optional[List[str]] = Field(
        default=None, description="Updated selected recipient/farm IDs."
    )
    vet_custom_note: Optional[str] = Field(
        default=None, description="Updated optional Vet custom note."
    )
    personalized_overrides: Optional[List[PersonalizedOverride]] = Field(
        default=None, description="Updated per-recipient personalized overrides."
    )

    @field_validator("vet_custom_note")
    @classmethod
    def validate_optional_note(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        return trimmed if trimmed else None


class AdvisoryPreviewResponse(BaseModel):
    advisory_id: Optional[str] = Field(default=None, description="Advisory ID if previewing an existing draft.")
    forecast_id: str = Field(..., description="Referenced forecast decision record ID.")
    disease: str = Field(..., description="Forecast disease type.")
    district: str = Field(..., description="Forecast district.")
    target_year: int = Field(..., description="Target forecast year.")
    target_month: int = Field(..., description="Target forecast month.")
    risk_level: str = Field(..., description="Forecast risk level.")
    recommended_priority: str = Field(..., description="System recommended advisory priority.")
    status: str = Field(..., description="Current or draft advisory status.")
    recipient_summary: RecipientSummary = Field(..., description="Recipient metrics summary.")
    previews: List[RecipientResolvedPreview] = Field(..., description="List of per-recipient resolved previews.")
    forecast_summary: str = Field(..., description="Standard forecast summary text.")
    disclaimer: str = Field(..., description="Scientific decision-support disclaimer.")


class AdvisoryListResponse(BaseModel):
    total_count: int = Field(..., ge=0, description="Total matching advisory records.")
    limit: int = Field(..., ge=1, description="Pagination limit.")
    offset: int = Field(..., ge=0, description="Pagination offset.")
    advisories: List[FarmerAdvisoryRecord] = Field(..., description="Paginated list of advisory records.")


# =====================================================================
# Phase 4 Notification Outbox & Delivery Schemas
# =====================================================================

class NotificationBatch(BaseModel):
    batch_id: str = Field(..., example="batch_a1b2c3d4e5", description="Unique notification batch identifier.")
    advisory_id: str = Field(..., example="adv_f1e2d3c4b5", description="Referenced approved advisory ID.")
    forecast_id: str = Field(..., example="fdr_a1b2c3d4e5", description="Referenced immutable forecast decision record ID.")
    provider_name: str = Field(
        default="MockNotificationProvider",
        description="Name of notification provider implementation (e.g. MockNotificationProvider identifies standalone mock execution)."
    )
    status: Literal["QUEUED", "PROCESSING", "COMPLETED", "PARTIALLY_FAILED", "FAILED", "CANCELLED"] = Field(
        default="QUEUED", description="Overall batch delivery status."
    )
    recipient_count: int = Field(..., ge=0, description="Total recipients targeted in this batch.")
    pending_count: int = Field(..., ge=0, description="Count of deliveries pending dispatch.")
    processing_count: int = Field(..., ge=0, description="Count of deliveries currently in-flight.")
    succeeded_count: int = Field(..., ge=0, description="Count of successfully delivered items (simulated success in mock mode).")
    failed_count: int = Field(..., ge=0, description="Count of failed delivery attempts.")
    cancelled_count: int = Field(default=0, ge=0, description="Count of cancelled delivery items.")
    created_by: str = Field(..., description="Actor ID who enqueued the batch (e.g. vet_officer_01).")
    idempotency_key: Optional[str] = Field(default=None, description="Optional client idempotency key.")
    created_at: str = Field(..., description="Timezone-aware ISO 8601 UTC creation timestamp.")
    updated_at: str = Field(..., description="Timezone-aware ISO 8601 UTC update timestamp.")
    completed_at: Optional[str] = Field(default=None, description="Timezone-aware ISO 8601 UTC completion timestamp.")
    version: int = Field(default=1, ge=1, description="Optimistic concurrency control version integer.")


class NotificationDelivery(BaseModel):
    delivery_id: str = Field(..., example="del_f1e2d3c4b5", description="Unique delivery item identifier.")
    batch_id: str = Field(..., example="batch_a1b2c3d4e5", description="Parent notification batch ID.")
    advisory_id: str = Field(..., example="adv_f1e2d3c4b5", description="Referenced approved advisory ID.")
    forecast_id: str = Field(..., example="fdr_a1b2c3d4e5", description="Referenced immutable forecast decision record ID.")
    recipient_id: str = Field(..., description="Target recipient or farm ID.")
    resolved_message: str = Field(..., description="Frozen final resolved advisory message for this recipient.")
    status: Literal["PENDING", "PROCESSING", "SUCCEEDED", "FAILED", "CANCELLED"] = Field(
        default="PENDING", description="Per-recipient delivery status. SUCCEEDED means mock provider simulation completed successfully; it does NOT mean the farmer received, opened, read or acknowledged a message."
    )
    attempt_count: int = Field(default=0, ge=0, description="Number of provider delivery attempts made.")
    provider_reference: Optional[str] = Field(default=None, description="External provider transaction reference.")
    last_error: Optional[str] = Field(default=None, description="Error message from most recent failed attempt.")
    created_at: str = Field(..., description="Timezone-aware ISO 8601 UTC creation timestamp.")
    updated_at: str = Field(..., description="Timezone-aware ISO 8601 UTC update timestamp.")
    first_attempted_at: Optional[str] = Field(default=None, description="Timezone-aware ISO 8601 UTC first attempt timestamp.")
    last_attempted_at: Optional[str] = Field(default=None, description="Timezone-aware ISO 8601 UTC last attempt timestamp.")
    succeeded_at: Optional[str] = Field(default=None, description="Timezone-aware ISO 8601 UTC success timestamp.")
    next_retry_at: Optional[str] = Field(default=None, description="Timezone-aware ISO 8601 UTC retry timestamp.")
    version: int = Field(default=1, ge=1, description="Optimistic concurrency control version integer.")


class EnqueueNotificationBatchRequest(BaseModel):
    created_by: Optional[str] = Field(default="vet_officer_01", description="Actor ID requesting enqueue.")
    idempotency_key: Optional[str] = Field(default=None, description="Optional client idempotency key.")


class NotificationBatchListResponse(BaseModel):
    total_count: int = Field(..., ge=0, description="Total matching notification batch records.")
    limit: int = Field(..., ge=1, description="Pagination limit.")
    offset: int = Field(..., ge=0, description="Pagination offset.")
    batches: List[NotificationBatch] = Field(..., description="Paginated list of notification batches.")


class NotificationDeliveryListResponse(BaseModel):
    total_count: int = Field(..., ge=0, description="Total matching notification delivery records.")
    limit: int = Field(..., ge=1, description="Pagination limit.")
    offset: int = Field(..., ge=0, description="Pagination offset.")
    deliveries: List[NotificationDelivery] = Field(..., description="Paginated list of per-recipient delivery records.")
