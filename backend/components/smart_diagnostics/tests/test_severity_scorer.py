"""Behavioral checks for visual thresholds and independent clinical grading."""
import pytest
from pydantic import ValidationError

from components.smart_diagnostics.config import settings
from components.smart_diagnostics.implementations.severity_scorer import (
    SeverityPolicy, compute_composite_severity, load_severity_policy,
)


def signals(**changes):
    return dict(predicted_class="lumpy_skin", vit_confidence_pct=90, top2_margin=70,
                yolo_confidence=.9, segmentation_status="completed_with_regions",
                segmentation_contract_status="verified", lesion_coverage_pct=20,
                cluster_count=3) | changes


@pytest.mark.parametrize("coverage,grade", [(0, "No visible regions"), (.01, "Mild"),
    (9.999, "Mild"), (10, "Moderate"), (29.999, "Moderate"), (30, "Severe"), (100, "Severe")])
def test_threshold_boundaries_use_unrounded_measurements(coverage, grade):
    result = compute_composite_severity(signals(lesion_coverage_pct=coverage,
        segmentation_status="completed_no_regions" if coverage == 0 else "completed_with_regions"))
    assert result.grade == grade
    assert result.score == coverage / 100
    assert result.composite_score is None and result.prognosis is None
    assert result.needs_review and result.confidence_level == "Not validated"
    assert result.visual_assessment.validation_status == "unvalidated"


def test_certainty_attention_geometry_and_region_count_do_not_increase_grade():
    low = compute_composite_severity(signals(vit_confidence_pct=65, top2_margin=16, yolo_confidence=.3,
        attention_coverage_pct=1, attention_cluster_count=1, yolo_max_bbox_area_pct=1, yolo_detection_count=1, cluster_count=1))
    high = compute_composite_severity(signals(vit_confidence_pct=100, top2_margin=99, yolo_confidence=1,
        attention_coverage_pct=100, attention_cluster_count=99, yolo_max_bbox_area_pct=100, yolo_detection_count=99, cluster_count=99))
    assert low.grade == high.grade == "Moderate"
    assert low.score == high.score == .2


@pytest.mark.parametrize("changes", [dict(segmentation_status="failed", lesion_coverage_pct=0),
    dict(segmentation_status="unavailable"), dict(lesion_coverage_pct=None),
    dict(lesion_coverage_pct=float("nan")), dict(lesion_coverage_pct=float("inf")),
    dict(lesion_coverage_pct=-1), dict(lesion_coverage_pct=101), dict(lesion_coverage_pct=True),
    dict(vit_confidence_pct=59), dict(top2_margin=14.9), dict(yolo_confidence=.24),
    dict(yolo_confidence=None), dict(segmentation_status="completed_no_regions", lesion_coverage_pct=20),
    dict(predicted_class="cattle", segmentation_status="skipped")])
def test_incomplete_unreliable_or_inconsistent_outputs_withhold_grade(changes):
    result = compute_composite_severity(signals(**changes))
    assert result.grade == "Unassessable" and result.score is None
    assert result.needs_review
    assert result.visual_assessment.review_reasons


def test_missing_outputs_never_become_healthy():
    result = compute_composite_severity({})
    assert result.grade == "Unassessable" and result.lesion_coverage_pct is None


def test_boundary_review_and_policy_identity():
    boundary = compute_composite_severity(signals(lesion_coverage_pct=10))
    middle = compute_composite_severity(signals())
    assert "near_visual_grade_boundary" in boundary.visual_assessment.review_reasons
    assert "near_visual_grade_boundary" not in middle.visual_assessment.review_reasons
    assert len(boundary.visual_assessment.policy_sha256) == 64


def test_each_disease_profile_is_configurable_and_hash_bound():
    raw = load_severity_policy(settings.SEVERITY_POLICY_PATH).model_dump()
    original = compute_composite_severity(signals())
    raw["diseases"]["lumpy_skin"]["moderate_min_pct"] = 25
    modified = compute_composite_severity(signals(), SeverityPolicy.model_validate(raw))
    mastitis = compute_composite_severity(signals(predicted_class="mastitis"), SeverityPolicy.model_validate(raw))
    assert original.grade == "Moderate" and modified.grade == "Mild"
    assert original.visual_assessment.policy_sha256 != modified.visual_assessment.policy_sha256
    assert mastitis.visual_assessment.grade == "Moderate"
    assert mastitis.grade == "Moderate" and mastitis.source == "visual_thresholds"


@pytest.mark.parametrize("name", ["mastitis", "foot_and_mouth", "lumpy_skin"])
def test_automatic_primary_grade_needs_no_clinical_observations(name):
    result = compute_composite_severity(signals(predicted_class=name))
    assert result.grade == "Moderate" and result.source == "visual_thresholds"
    assert result.clinical_observations is None
    assert result.assessment_target == "predicted_lesion_burden_in_analyzed_crop"


@pytest.mark.parametrize("moderate,severe", [(30, 10), (10, 10), (-1, 30), (10, 101), (float("nan"), 30)])
def test_invalid_policy_is_rejected(moderate, severe):
    raw = load_severity_policy(settings.SEVERITY_POLICY_PATH).model_dump()
    raw["diseases"]["lumpy_skin"].update(moderate_min_pct=moderate, severe_min_pct=severe)
    with pytest.raises(ValidationError):
        SeverityPolicy.model_validate(raw)
