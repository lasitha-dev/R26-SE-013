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


class ForecastRequest(BaseModel):
    target_month: int = Field(..., example=1, ge=1, le=12, description="Target forecast month (1-12).")
    year: Optional[int] = Field(default=2024, ge=2017, le=2030, description="Reference forecast year (default 2024).")
    model_variant: Optional[Literal["30_feature_baseline", "31_feature_autocorrelation"]] = Field(
        default="30_feature_baseline",
        description="FMD model variant (ignored for LSD)."
    )


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
    method: str = Field(..., example="Mondrian Conformal Prediction (Class-Conditional)", description="Uncertainty quantification technique.")
    status: str = Field(..., example="VALIDATED", description="UQ validation status (VALIDATED vs UNRELIABLE_INSUFFICIENT_DATA).")
    reliability: Literal["HIGH", "MEDIUM", "LOW"] = Field(..., example="HIGH", description="Reliability grade of uncertainty output.")
    prediction_set: Optional[List[str]] = Field(default=None, example=["MEDIUM", "HIGH"], description="Conformal prediction set classes (null if unreliable).")
    empirical_coverage_pct: Optional[float] = Field(default=None, example=94.9, description="Empirical coverage percentage (null if unreliable).")
    notes: str = Field(..., description="Details regarding uncertainty coverage guarantees and sample-size caveats.")


class DataProvenance(BaseModel):
    fallback_applied: bool = Field(..., example=False, description="Whether historical data fallback was applied for input features.")
    fallback_message: str = Field(..., example="Exact match found in surveillance ground truth.", description="Data provenance message.")


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
    provenance: DataProvenance


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
    provenance: DataProvenance


# ─── Forecast Schemas ────────────────────────────────────────────────────────

class DistrictForecastItem(BaseModel):
    district: str
    probability_pct: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    predicted_severity: str


class DistrictForecastResponse(BaseModel):
    disease: str
    target_month: int
    target_month_name: str
    total_districts: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    districts: List[DistrictForecastItem]


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
