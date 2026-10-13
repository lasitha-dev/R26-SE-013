"""
Composite Severity Scorer Module
================================
Computes multi-signal composite severity grading, prognosis, and confidence gating
derived from ViT attention rollout, ViT classification certainty, and YOLO geometry.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from ..schemas import SeverityMetrics


# Grade boundaries and weights
GRADE_BOUNDARIES = {
    "SEVERE": 0.65,
    "MODERATE": 0.35,
    "MILD": 0.10,
}

BOUNDARY_MARGIN = 0.05  # ±0.05 uncertainty band around threshold boundaries


def compute_composite_severity(signals: Dict[str, Any]) -> SeverityMetrics:
    """Compute a multi-signal composite score, severity grade, stage, and review flag.

    Parameters
    ----------
    signals : dict
        - attention_coverage_pct (float): Attention rollout coverage % [0, 100]
        - attention_cluster_count (int): Focal cluster count from attention map
        - vit_confidence_pct (float): Top-class classification confidence % [0, 100]
        - top2_margin (float): Difference between top-1 and top-2 probabilities % [0, 100]
        - yolo_detection_count (int): Number of YOLO detections
        - yolo_max_bbox_area_pct (float): Max bbox area as fraction of frame % [0, 100]
        - predicted_class (str): Internal class name
        - predicted_display (str): Human-readable disease name
        - spatial_correlation (str, optional): Anatomical location string
        - lesion_coverage_pct (float, optional): Overlay lesion coverage for display
        - cluster_count (int, optional): Overlay cluster count for display
        - mean_intensity (float, optional): Overlay intensity for display

    Returns
    -------
    SeverityMetrics
        Structured severity evaluation instance with source="composite_scoring".
    """
    # Extract & normalize signals to [0, 1]
    attn_cov_raw = float(signals.get("attention_coverage_pct", 0.0))
    a_cov = min(max(attn_cov_raw / 100.0, 0.0), 1.0)

    attn_cls_raw = int(signals.get("attention_cluster_count", 0))
    a_cls = min(max(attn_cls_raw, 0), 10) / 10.0

    vit_conf_raw = float(signals.get("vit_confidence_pct", 0.0))
    v_conf = min(max(vit_conf_raw / 100.0, 0.0), 1.0)

    top2_margin_raw = float(signals.get("top2_margin", 0.0))
    v_margin = min(max(top2_margin_raw / 100.0, 0.0), 1.0)

    y_count_raw = int(signals.get("yolo_detection_count", 1))
    y_count = min(max(y_count_raw, 0), 5) / 5.0

    y_area_raw = float(signals.get("yolo_max_bbox_area_pct", 0.0))
    y_area = min(max(y_area_raw / 100.0, 0.0), 1.0)

    disease_name = signals.get("predicted_display", signals.get("predicted_class", "Condition"))
    pred_class = signals.get("predicted_class", "").lower()
    is_healthy = "cattle" in pred_class and "disease" not in pred_class

    # Fast track for healthy predictions (Healthy Baseline)
    if is_healthy and v_conf >= 0.80:
        return SeverityMetrics(
            score=0.0,
            composite_score=0.0,
            grade="Healthy Baseline",
            description="Epidermal surface presents homogeneous texture with zero anomalous lesion density or inflammatory markers.",
            prognosis="Excellent",
            diagnostic_rationale="No pathological tissue disruptions detected. Dermal contour aligns with physiological baseline.",
            spatial_correlation=signals.get("spatial_correlation"),
            lesion_coverage_pct=0.0,
            cluster_count=0,
            mean_intensity=0.0,
            formatted="Healthy Baseline",
            source="composite_scoring",
            confidence_level="High",
            needs_review=False,
            attention_coverage_pct=attn_cov_raw,
            attention_cluster_count=attn_cls_raw,
            top2_margin=top2_margin_raw,
        )

    # 1. Calculate weighted composite score
    s = (
        0.30 * a_cov +
        0.20 * a_cls +
        0.20 * v_conf +
        0.10 * v_margin +
        0.10 * y_count +
        0.10 * y_area
    )
    composite_score = round(s, 4)

    # 2. Determine Grade, Prognosis, and baseline Confidence
    if composite_score >= GRADE_BOUNDARIES["SEVERE"]:
        grade = "Severe"
        prognosis = "Guarded"
        confidence_level = "High" if v_margin > 0.30 else "Moderate"
        description = (
            f"Severe pathological manifestation of {disease_name} (Composite Score: {composite_score:.2f}). "
            f"ViT attention saliency indicates widespread multifocal involvement ({attn_cov_raw:.1f}% coverage, "
            f"{attn_cls_raw} focal clusters) with high clinical transmission risk."
        )
    elif composite_score >= GRADE_BOUNDARIES["MODERATE"]:
        grade = "Moderate"
        prognosis = "Recoverable with Intervention"
        confidence_level = "High" if v_margin > 0.30 else "Moderate"
        description = (
            f"Moderate multifocal progression of {disease_name} (Composite Score: {composite_score:.2f}). "
            f"Attention rollout identified {attn_cls_raw} focal eruption cluster(s) spanning {attn_cov_raw:.1f}% "
            f"saliency coverage, requiring clinical intervention."
        )
    elif composite_score >= GRADE_BOUNDARIES["MILD"]:
        grade = "Mild"
        prognosis = "Favorable"
        confidence_level = "High" if v_conf > 0.80 else "Moderate"
        description = (
            f"Mild localized presentation of {disease_name} (Composite Score: {composite_score:.2f}). "
            f"Early focal saliency detected ({attn_cov_raw:.1f}% coverage, {attn_cls_raw} cluster(s)). "
            "Prompt supportive triage recommended."
        )
    else:
        grade = "Healthy Baseline"
        prognosis = "Excellent"
        confidence_level = "High"
        description = (
            "Physiological epidermal baseline. Multi-signal composite score indicates low anomalous lesion density."
        )

    # 3. Confidence Override Rules
    # Rule A: Low ViT classification confidence (< 60%)
    if v_conf < 0.60:
        confidence_level = "Low"

    # Rule B: Boundary proximity uncertainty (within ±0.05 of any boundary)
    for boundary in GRADE_BOUNDARIES.values():
        if abs(composite_score - boundary) <= BOUNDARY_MARGIN:
            confidence_level = "Low"
            break

    # Flag for veterinarian review if confidence is Low
    needs_review = (confidence_level == "Low")

    # Diagnostic rationale synthesizing telemetry
    diagnostic_rationale = (
        f"Multi-signal composite score ({composite_score:.2f}) synthesizes ViT classification "
        f"({vit_conf_raw:.1f}% confidence, top-2 margin {top2_margin_raw:.1f}%) and self-attention "
        f"rollout telemetry ({attn_cov_raw:.1f}% coverage, {attn_cls_raw} focal cluster(s))."
    )

    return SeverityMetrics(
        score=composite_score,
        composite_score=composite_score,
        grade=grade,
        description=description,
        prognosis=prognosis,
        diagnostic_rationale=diagnostic_rationale,
        spatial_correlation=signals.get("spatial_correlation"),
        lesion_coverage_pct=float(signals.get("lesion_coverage_pct", 0.0)),
        cluster_count=int(signals.get("cluster_count", 0)),
        mean_intensity=float(signals.get("mean_intensity", 0.0)),
        formatted=grade,
        source="composite_scoring",
        confidence_level=confidence_level,
        needs_review=needs_review,
        attention_coverage_pct=attn_cov_raw,
        attention_cluster_count=attn_cls_raw,
        top2_margin=top2_margin_raw,
    )

