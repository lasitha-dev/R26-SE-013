from pydantic import BaseModel
from typing import List, Dict, Optional


class Detection(BaseModel):
    bbox: List[float]
    confidence: float
    class_name: str


class BoundingBoxNormalized(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class BestDetection(BaseModel):
    bbox: List[float]
    confidence: float
    bbox_normalized: BoundingBoxNormalized


class Disease(BaseModel):
    name: str
    confidence: float
    all_probabilities: Dict[str, float]


class SeverityMetrics(BaseModel):
    score: float
    grade: str  # "High" | "Moderate" | "Low" | "None"
    lesion_coverage_pct: float
    cluster_count: int
    mean_intensity: float = 0.0
    formatted: str  # e.g. "8.2 / High"


class DetectResponse(BaseModel):
    cattle_detected: bool
    detections: List[Detection]
    best_detection: Optional[BestDetection]
    disease: Optional[Disease]
    severity: Optional[SeverityMetrics] = None
    stage: Optional[str] = None
    spatial_correlation: Optional[str] = None
    cropped_image: Optional[str]
    symptoms_image: Optional[str] = None
    image_size: Optional[Dict[str, int]]
    device: Optional[str]


# ---------------------------------------------------------------------------
# Tier 3 — LLM Clinical Reasoning
# ---------------------------------------------------------------------------

class ReasoningRequest(BaseModel):
    """Request body for POST /api/reason.

    Accepts the full detection result from /api/detect plus optional
    farm metadata for richer LLM context.
    """
    cattle_detected: bool
    detections: List[Detection]
    best_detection: Optional[BestDetection] = None
    disease: Optional[Disease] = None
    severity: Optional[SeverityMetrics] = None
    stage: Optional[str] = None
    spatial_correlation: Optional[str] = None
    image_size: Optional[Dict[str, int]] = None
    farm_metadata: Optional[Dict[str, str]] = None


class ReasoningResponse(BaseModel):
    """Response body for POST /api/reason."""
    status: str                  # "ok" | "error"
    reasoning_report: str        # Markdown clinical briefing (or error message)
    model_name: Optional[str] = None  # LLM model that produced the report

