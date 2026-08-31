"""
Unit tests for Composite Severity Scorer (severity_scorer.py).
==============================================================
Tests composite scoring formulas, boundary edge cases, confidence gating,
and veterinarian review triggers.
"""

import pytest
from components.smart_diagnostics.implementations.severity_scorer import (
    compute_composite_severity,
    GRADE_BOUNDARIES,
    BOUNDARY_MARGIN,
)
from components.smart_diagnostics.schemas import SeverityMetrics


class TestCompositeSeverityScorer:
    """Test suite for compute_composite_severity function."""

    def test_healthy_animal_fast_track(self):
        """Healthy cattle with >=80% ViT confidence gets Healthy Baseline directly."""
        signals = {
            "attention_coverage_pct": 5.0,
            "attention_cluster_count": 0,
            "vit_confidence_pct": 95.0,
            "top2_margin": 90.0,
            "yolo_detection_count": 1,
            "yolo_max_bbox_area_pct": 30.0,
            "predicted_class": "cattle",
            "predicted_display": "Cattle (Healthy)",
        }
        sev = compute_composite_severity(signals)

        assert sev.grade == "Healthy Baseline"
        assert sev.stage == "Healthy Baseline"
        assert sev.prognosis == "Excellent"
        assert sev.confidence_level == "High"
        assert sev.needs_review is False
        assert sev.source == "composite_scoring"
        assert sev.composite_score == 0.0

    def test_severe_case_high_signals(self):
        """High attention coverage + high confidence + large area yields Severe grade."""
        signals = {
            "attention_coverage_pct": 80.0,  # 0.8 * 0.30 = 0.24
            "attention_cluster_count": 9,    # 0.9 * 0.20 = 0.18
            "vit_confidence_pct": 92.0,      # 0.92 * 0.20 = 0.184
            "top2_margin": 85.0,             # 0.85 * 0.10 = 0.085
            "yolo_detection_count": 4,       # 0.8 * 0.10 = 0.08
            "yolo_max_bbox_area_pct": 70.0,  # 0.7 * 0.10 = 0.07 -> total = 0.839
            "predicted_class": "lumpy_skin",
            "predicted_display": "Lumpy Skin Disease",
        }
        sev = compute_composite_severity(signals)

        assert sev.grade == "Severe"
        assert sev.stage == "Acute Eruptive / Advanced"
        assert sev.prognosis == "Guarded"
        assert sev.composite_score >= GRADE_BOUNDARIES["SEVERE"]
        assert sev.confidence_level == "High"
        assert sev.needs_review is False

    def test_moderate_case(self):
        """Intermediate signals yield Moderate grade."""
        signals = {
            "attention_coverage_pct": 40.0,  # 0.4 * 0.30 = 0.12
            "attention_cluster_count": 4,    # 0.4 * 0.20 = 0.08
            "vit_confidence_pct": 85.0,      # 0.85 * 0.20 = 0.17
            "top2_margin": 60.0,             # 0.6 * 0.10 = 0.06
            "yolo_detection_count": 2,       # 0.4 * 0.10 = 0.04
            "yolo_max_bbox_area_pct": 40.0,  # 0.4 * 0.10 = 0.04 -> total = 0.51
            "predicted_class": "foot_and_mouth",
            "predicted_display": "Foot and Mouth Disease",
        }
        sev = compute_composite_severity(signals)

        assert sev.grade == "Moderate"
        assert sev.stage == "Active Progression / Multifocal"
        assert sev.prognosis == "Recoverable with Intervention"
        assert 0.35 <= sev.composite_score < 0.65
        assert sev.confidence_level == "High"
        assert sev.needs_review is False

    def test_mild_case(self):
        """Low coverage and localized presentation yield Mild grade."""
        signals = {
            "attention_coverage_pct": 10.0,  # 0.1 * 0.30 = 0.03
            "attention_cluster_count": 1,    # 0.1 * 0.20 = 0.02
            "vit_confidence_pct": 82.0,      # 0.82 * 0.20 = 0.164
            "top2_margin": 40.0,             # 0.4 * 0.10 = 0.04
            "yolo_detection_count": 1,       # 0.2 * 0.10 = 0.02
            "yolo_max_bbox_area_pct": 10.0,  # 0.1 * 0.10 = 0.01 -> total = 0.284
            "predicted_class": "mastitis",
            "predicted_display": "Mastitis",
        }
        sev = compute_composite_severity(signals)

        assert sev.grade == "Mild"
        assert sev.stage == "Early Focal / Prodromal"
        assert sev.prognosis == "Favorable"
        assert 0.10 <= sev.composite_score < 0.35
        # 0.284 is within ±0.05 of 0.30? 0.35 - 0.284 = 0.066 (> 0.05)
        # Check boundary proximity rule
        if abs(sev.composite_score - 0.35) <= BOUNDARY_MARGIN:
            assert sev.needs_review is True
        else:
            assert sev.confidence_level == "High"

    def test_low_vit_confidence_triggers_review(self):
        """ViT confidence < 60% flags needs_review=True and confidence_level=Low."""
        signals = {
            "attention_coverage_pct": 50.0,
            "attention_cluster_count": 5,
            "vit_confidence_pct": 52.0,  # < 60%
            "top2_margin": 10.0,
            "yolo_detection_count": 1,
            "yolo_max_bbox_area_pct": 20.0,
            "predicted_class": "lumpy_skin",
            "predicted_display": "Lumpy Skin Disease",
        }
        sev = compute_composite_severity(signals)

        assert sev.confidence_level == "Low"
        assert sev.needs_review is True

    def test_boundary_proximity_triggers_review(self):
        """Score within ±0.05 of boundary (e.g. 0.35) flags needs_review=True."""
        # Design signals to hit score near 0.36
        signals = {
            "attention_coverage_pct": 20.0,  # 0.2 * 0.30 = 0.06
            "attention_cluster_count": 2,    # 0.2 * 0.20 = 0.04
            "vit_confidence_pct": 80.0,      # 0.8 * 0.20 = 0.16
            "top2_margin": 50.0,             # 0.5 * 0.10 = 0.05
            "yolo_detection_count": 1,       # 0.2 * 0.10 = 0.02
            "yolo_max_bbox_area_pct": 30.0,  # 0.3 * 0.10 = 0.03 -> total = 0.36
            "predicted_class": "foot_and_mouth",
            "predicted_display": "Foot and Mouth Disease",
        }
        sev = compute_composite_severity(signals)

        # 0.36 is within ±0.05 of 0.35 boundary
        assert abs(sev.composite_score - 0.35) <= 0.05
        assert sev.confidence_level == "Low"
        assert sev.needs_review is True

    def test_zero_signals_fallback(self):
        """Zeroed signals produce Healthy Baseline."""
        signals = {
            "attention_coverage_pct": 0.0,
            "attention_cluster_count": 0,
            "vit_confidence_pct": 0.0,
            "top2_margin": 0.0,
            "yolo_detection_count": 0,
            "yolo_max_bbox_area_pct": 0.0,
            "predicted_class": "cattle",
            "predicted_display": "Cattle (Healthy)",
        }
        sev = compute_composite_severity(signals)

        assert sev.grade == "Healthy Baseline"
        assert sev.composite_score == 0.0
