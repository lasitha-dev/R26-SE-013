"""Configurable visual thresholds and model/LLM severity estimates.

YOLO selects the ROI, ViT supplies disease context, and segmentation measures
predicted foreground. Certainty gates interpretation; it never increases burden.
Grounded LLM recommendations contribute through a configurable ordinal policy.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
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


class ReasoningSeverityPolicy(BaseModel):
    """Combine ordinal visual/LLM grades; weights never use model confidence."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    llm_weight: float = Field(default=0.3, ge=0, le=1)
    moderate_min_score: float = Field(default=1.5, gt=1, lt=3)
    severe_min_score: float = Field(default=2.5, gt=1, le=3)

    @model_validator(mode="after")
    def ordered(self):
        if self.moderate_min_score >= self.severe_min_score:
            raise ValueError("Moderate score must be below severe score.")
        return self


class ReviewPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    require_unvalidated_policy_review: bool = False
    require_unverified_segmentation_review: bool = False
    minimum_crop_side_px: int = Field(default=128, ge=0)
    minimum_image_stddev: float = Field(default=5, ge=0)
    minimum_image_brightness: float = Field(default=20, ge=0, le=255)
    maximum_image_brightness: float = Field(default=235, ge=0, le=255)

    @model_validator(mode="after")
    def ordered(self):
        if self.minimum_image_brightness >= self.maximum_image_brightness:
            raise ValueError("Minimum brightness must be below maximum brightness.")
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
    reasoning: ReasoningSeverityPolicy = Field(default_factory=ReasoningSeverityPolicy)
    review: ReviewPolicy = Field(default_factory=ReviewPolicy)


def load_severity_policy(path: str) -> SeverityPolicy:
    """Read for each assessment so config edits apply without restarting."""
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
    # First check whether the mask and prediction meet the evidence gates.
    # Confidence decides whether grading is possible; coverage determines the grade.
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
    # A grade is assigned only after the required evidence checks have passed.
    if not reasons and coverage is not None and profile is not None:
        grade = ("No visible regions" if coverage == 0 else "Severe" if coverage >= profile.severe_min_pct
                 else "Moderate" if coverage >= profile.moderate_min_pct else "Mild")
        if any(abs(coverage - boundary) <= policy.boundary_margin_pct for boundary in thresholds.values()):
            reasons.append("near_visual_grade_boundary")
    if policy.review.require_unverified_segmentation_review and signals.get("segmentation_contract_status") != "verified":
        reasons.append("segmentation_training_contract_unverified")
    if policy.review.require_unvalidated_policy_review:
        reasons.append("visual_thresholds_unvalidated")
    return VisualSeverityAssessment(grade=grade, coverage_pct=coverage, disease_key=key,
        policy_version=policy.version, policy_sha256=digest, thresholds_pct=thresholds,
        evidence={"yolo_confidence": detector, "vit_confidence_pct": classifier, "top2_margin_pct": margin,
                  "lesion_coverage_pct": coverage}, review_reasons=reasons, rationale=policy.rationale,
        references=profile.references if profile else [])


def compute_composite_severity(signals: dict[str, Any], policy: SeverityPolicy | None = None) -> SeverityMetrics:
    """Return automatic visual grades, or an explicitly requested clinical checklist.

    The old confidence-weighted composite is retired. Score is crop-mask
    coverage / 100 for every disease, not a clinical probability. Missing masks
    never mean healthy. Clinical findings are optional and never inferred.
    """
    from .clinical_severity import assess_clinical_severity, clinical_disease_key

    visual = assess_visual_severity(signals, policy)
    predicted = (signals.get("predicted_class") if clinical_disease_key(signals.get("predicted_class"))
                 else signals.get("predicted_display"))
    if clinical_disease_key(predicted) and signals.get("clinical_observations") is not None:
        assessment = assess_clinical_severity(predicted, signals.get("clinical_observations"), signals)
        assessment.visual_assessment = visual
        return assessment

    score = visual.coverage_pct / 100 if visual.grade != "Unassessable" else None
    formatted = (f"{visual.grade} severity estimate" if visual.grade in ("Mild", "Moderate", "Severe")
                 else "No visible regions" if visual.grade == "No visible regions"
                 else "Severity unavailable - insufficient model evidence")
    return SeverityMetrics(score=score, composite_score=None, grade=visual.grade, formatted=formatted,
        source="visual_thresholds", confidence_level="Model estimate", needs_review=bool(visual.review_reasons),
        assessment_status="provisional" if score is not None else "unassessable",
        assessment_target=visual.assessment_target, rubric_id=visual.policy_version,
        description=f"{formatted}. Predicted mask coverage is limited to the analyzed crop. Clinical severity, stage and prognosis are not established.",
        diagnostic_rationale="YOLO selects the crop; ViT supplies disease context and confidence gates; segmentation supplies predicted lesion coverage. Classifier confidence, cattle count, bounding-box size and attention do not increase severity.",
        spatial_correlation=signals.get("spatial_correlation"), lesion_coverage_pct=visual.coverage_pct,
        cluster_count=signals.get("cluster_count"), mean_intensity=signals.get("mean_intensity"),
        top2_margin=_number(signals.get("top2_margin"), 100), visual_assessment=visual)


GRADE_SCORES = {"Mild": 1.0, "Moderate": 2.0, "Severe": 3.0}


def combine_reasoned_severity(assessment: SeverityMetrics, grade: str, evidence: list[str],
                              policy: SeverityPolicy) -> SeverityMetrics:
    """Apply configurable ordinal cutoffs while retaining measured visual evidence."""
    if assessment.source != "visual_thresholds" or assessment.grade not in GRADE_SCORES:
        raise ValueError("LLM severity requires an assessable automatic visual grade.")
    if grade not in GRADE_SCORES or not evidence:
        raise ValueError("A severity recommendation must cite case evidence.")
    weight = policy.reasoning.llm_weight
    if weight == 0:
        return assessment
    # Map grades to ordinal values 1/2/3, blend using the configured weight,
    # then apply ordinal cutoffs. This score is not a probability or mask area.
    score = round((1 - weight) * GRADE_SCORES[assessment.grade] + weight * GRADE_SCORES[grade], 12)
    final_grade = ("Severe" if score >= policy.reasoning.severe_min_score else
                   "Moderate" if score >= policy.reasoning.moderate_min_score else "Mild")
    rationale = (f"Visual grade {assessment.grade} ({GRADE_SCORES[assessment.grade]:g}); "
        f"LLM recommendation {grade} ({GRADE_SCORES[grade]:g}). "
        f"Weighted score: {score:g} = {1-weight:g} × visual + {weight:g} × LLM. "
        f"Moderate begins at {policy.reasoning.moderate_min_score:g}; severe at {policy.reasoning.severe_min_score:g}. "
        "LLM supporting evidence: " + " ".join(evidence))
    return assessment.model_copy(update=dict(grade=final_grade, formatted=f"{final_grade} severity estimate",
        source="model_llm_reasoning", composite_score=score,
        assessment_target="model_and_reasoning_severity_estimate", assessment_status="estimated",
        description=f"{final_grade} severity estimated from model findings and LLM reasoning. This is an automated estimate, not a confirmed clinical grade.",
        diagnostic_rationale=rationale, evidence=evidence,
        reasoning_assessment=dict(visual_grade=assessment.grade, llm_grade=grade, llm_weight=weight,
            weighted_score=score, moderate_min_score=policy.reasoning.moderate_min_score,
            severe_min_score=policy.reasoning.severe_min_score)))


def visual_severity_report(name: str, assessment: SeverityMetrics) -> str:
    """Deterministic explanation of an automatic estimate, without invented signs."""
    visual = assessment.visual_assessment
    coverage = (f"{visual.coverage_pct:g}% of analyzed crop pixels" if visual and visual.coverage_pct is not None
                else "unavailable / not measured")
    return (f"## 1. Automatic Visual Severity Estimate\n\n"
            f"{assessment.formatted or assessment.grade}. {assessment.description}\n\n"
            f"## 2. Image Evidence\n\nImage-model prediction: {name}. "
            f"Predicted lesion coverage: {coverage}. {assessment.diagnostic_rationale}\n\n"
            "## 3. Clinical Review\n\nThis estimate is generated automatically; no clinical checklist is required. "
            "The thresholds are unvalidated. Images do not establish milk abnormalities, systemic illness, "
            "appetite, mobility, physical lesion measurements or whole-animal clinical severity. "
            "A veterinarian may optionally add observed findings for a separate clinical assessment.")
