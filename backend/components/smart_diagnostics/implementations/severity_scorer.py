"""Versioned crop-mask thresholds, separate from clinical disease severity.

YOLO selects the ROI, ViT supplies disease context, and segmentation measures
predicted foreground. Certainty gates interpretation; it never increases burden.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..config import settings
from ..schemas import SeverityMetrics, VisualSeverityAssessment


class DiseaseThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    moderate_min_pct: float = Field(gt=0, lt=100)
    severe_min_pct: float = Field(gt=0, le=100)
    references: list[dict[str, str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def ordered(self):
        if self.moderate_min_pct >= self.severe_min_pct:
            raise ValueError("Moderate threshold must be below severe threshold.")
        return self


class SeverityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    version: str = Field(min_length=1)
    validation_status: Literal["unvalidated"] = "unvalidated"
    rationale: str = Field(min_length=1)
    minimum_detector_confidence: float = Field(ge=0, le=1)
    minimum_classifier_confidence_pct: float = Field(ge=0, le=100)
    minimum_top_two_margin_pct: float = Field(ge=0, le=100)
    boundary_margin_pct: float = Field(ge=0, le=100)
    diseases: dict[str, DiseaseThresholds]


@lru_cache(maxsize=4)
def load_severity_policy(path: str) -> SeverityPolicy:
    """Read once per process; reject invalid policies rather than using defaults."""
    return SeverityPolicy.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _number(value: Any, maximum: float) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and 0 <= result <= maximum else None


def disease_key(name: Any) -> str | None:
    key = re.sub(r"[^a-z]", "", str(name or "").lower())
    return {"lumpyskin": "lumpy_skin", "lumpyskindisease": "lumpy_skin",
            "fmd": "foot_and_mouth", "footandmouth": "foot_and_mouth",
            "footandmouthdisease": "foot_and_mouth", "mastitis": "mastitis"}.get(key)


def assess_visual_severity(signals: dict[str, Any], policy: SeverityPolicy | None = None) -> VisualSeverityAssessment:
    policy = policy or load_severity_policy(settings.SEVERITY_POLICY_PATH)
    digest = hashlib.sha256(json.dumps(policy.model_dump(), sort_keys=True).encode()).hexdigest()
    key = disease_key(signals.get("predicted_class")) or disease_key(signals.get("predicted_display"))
    profile = policy.diseases.get(key)
    coverage = _number(signals.get("lesion_coverage_pct"), 100)
    detector = _number(signals.get("yolo_confidence"), 1)
    classifier = _number(signals.get("vit_confidence_pct"), 100)
    margin = _number(signals.get("top2_margin"), 100)
    reasons = []
    completed = signals.get("segmentation_status") in ("completed_with_regions", "completed_no_regions")
    if not completed or coverage is None:
        coverage = None
        reasons.append("segmentation_not_measured")
    elif ((signals.get("segmentation_status") == "completed_no_regions") != (coverage == 0)):
        reasons.append("inconsistent_segmentation_measurements")
    if profile is None:
        reasons.append("no_disease_threshold_profile")
    for value, minimum, reason in (
        (detector, policy.minimum_detector_confidence, "detector_confidence_missing_or_low"),
        (classifier, policy.minimum_classifier_confidence_pct, "classifier_confidence_missing_or_low"),
        (margin, policy.minimum_top_two_margin_pct, "classification_margin_missing_or_low"),
    ):
        if value is None or value < minimum:
            reasons.append(reason)

    grade = "Unassessable"
    thresholds = {}
    if profile is not None:
        thresholds = {"moderate_min_pct": profile.moderate_min_pct, "severe_min_pct": profile.severe_min_pct}
    if not reasons and coverage is not None and profile is not None:
        grade = ("No visible regions" if coverage == 0 else "Severe" if coverage >= profile.severe_min_pct
                 else "Moderate" if coverage >= profile.moderate_min_pct else "Mild")
        if any(abs(coverage - boundary) <= policy.boundary_margin_pct for boundary in thresholds.values()):
            reasons.append("near_visual_grade_boundary")
    if signals.get("segmentation_contract_status") != "verified":
        reasons.append("segmentation_training_contract_unverified")
    reasons.append("visual_thresholds_unvalidated")
    return VisualSeverityAssessment(grade=grade, coverage_pct=coverage, disease_key=key,
        policy_version=policy.version, policy_sha256=digest, thresholds_pct=thresholds,
        evidence={"yolo_confidence": detector, "vit_confidence_pct": classifier, "top2_margin_pct": margin,
                  "lesion_coverage_pct": coverage}, review_reasons=reasons, rationale=policy.rationale,
        references=profile.references if profile else [])


def compute_composite_severity(signals: dict[str, Any], policy: SeverityPolicy | None = None) -> SeverityMetrics:
    """Return observation-based clinical checklists plus separate visual evidence.

    The old confidence-weighted composite is retired. For LSD, score is crop-mask
    coverage / 100, not a clinical probability. Missing masks never mean healthy.
    """
    from .clinical_severity import assess_clinical_severity, clinical_disease_key

    visual = assess_visual_severity(signals, policy)
    predicted = (signals.get("predicted_class") if clinical_disease_key(signals.get("predicted_class"))
                 else signals.get("predicted_display"))
    if clinical_disease_key(predicted):
        assessment = assess_clinical_severity(predicted, signals.get("clinical_observations"), signals)
        assessment.visual_assessment = visual
        return assessment

    score = visual.coverage_pct / 100 if visual.grade != "Unassessable" else None
    formatted = (f"{visual.grade} visual burden (provisional)" if visual.grade in ("Mild", "Moderate", "Severe")
                 else f"{visual.grade} - clinical review needed")
    return SeverityMetrics(score=score, composite_score=None, grade=visual.grade, formatted=formatted,
        source="visual_thresholds", confidence_level="Not validated", needs_review=True,
        assessment_status="provisional" if score is not None else "unassessable",
        assessment_target=visual.assessment_target, rubric_id=visual.policy_version,
        description=f"{formatted}. Predicted mask coverage is limited to the analyzed crop. Clinical severity, stage and prognosis are not established.",
        diagnostic_rationale="YOLO selects the crop; ViT supplies disease context and confidence gates; segmentation supplies predicted lesion coverage. Classifier confidence, cattle count, bounding-box size and attention do not increase severity.",
        spatial_correlation=signals.get("spatial_correlation"), lesion_coverage_pct=visual.coverage_pct,
        cluster_count=signals.get("cluster_count"), mean_intensity=signals.get("mean_intensity"),
        top2_margin=_number(signals.get("top2_margin"), 100), visual_assessment=visual)
