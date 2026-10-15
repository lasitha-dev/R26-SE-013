"""Clinical rule boundaries and integration guards, without models or network."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from components.smart_diagnostics.implementations.clinical_severity import assess_clinical_severity
from components.smart_diagnostics.implementations.severity_scorer import compute_composite_severity
from components.smart_diagnostics.pipeline.llm_reasoner import generate_veterinary_report, parse_llm_severity_assessment
from components.smart_diagnostics.schemas import ClinicalObservations
from .conftest import FakeDetector, FakeClassifier, FakeSegmenter


def mastitis(**changes):
    return dict(disease="mastitis", vet_confirmed=True, milk_abnormal=True,
                udder_inflammation=False, systemic_illness=False) | changes


def fmd(**changes):
    return dict(disease="foot_and_mouth", vet_confirmed=True, affected_feet=1,
                mouth_lesion_cm=1.9, appetite="normal", mentation="normal",
                heel_and_coronary_involved=False, unable_to_stand=False) | changes


@pytest.mark.parametrize("findings, grade", [
    (mastitis(), "Mild"),
    (mastitis(udder_inflammation=True), "Moderate"),
    (mastitis(udder_inflammation=True, systemic_illness=True), "Severe"),
    (mastitis(systemic_illness=True), "Unassessable"),
    (mastitis(milk_abnormal=False), "Unassessable"),
    (mastitis(systemic_illness=None), "Unassessable"),
    (mastitis(vet_confirmed=False), "Unassessable"),
])
def test_mastitis_hierarchy_and_unknowns(findings, grade):
    result = assess_clinical_severity("Mastitis", findings)
    assert result.grade == grade
    assert result.needs_review and result.confidence_level == "Not validated"
    assert result.composite_score is None and result.prognosis == "Not assessed"


@pytest.mark.parametrize("findings, grade", [
    (fmd(), "Mild"),
    (fmd(mouth_lesion_cm=2.0, affected_feet=2, appetite="reduced", mentation="slightly_dull"), "Moderate"),
    (fmd(mouth_lesion_cm=5.0, affected_feet=3, appetite="reduced", mentation="slightly_dull"), "Moderate"),
    (fmd(mouth_lesion_cm=5.01, affected_feet=4, appetite="none", mentation="depressed", heel_and_coronary_involved=True), "Severe"),
    (fmd(mouth_lesion_cm=2.0), "Unassessable"),
    (fmd(mouth_lesion_cm=5.01, affected_feet=4, appetite="none", mentation="depressed"), "Unassessable"),
    (fmd(unable_to_stand=True), "Unassessable"),
    (fmd(heel_and_coronary_involved=True), "Unassessable"),
    (fmd(mouth_lesion_cm=0.0, affected_feet=0), "Unassessable"),
    (fmd(affected_feet=None), "Unassessable"),
])
def test_fmd_boundaries_and_mixed_profiles(findings, grade):
    result = assess_clinical_severity("Foot and Mouth Disease", findings)
    assert result.grade == grade
    assert result.assessment_target == "fmd_field_triage_profile"
    assert result.rubric_id == "fmd_ausvet_concordant_profile_v1"


@pytest.mark.parametrize("name", ["Mastitis", "Foot and Mouth Disease"])
def test_image_metrics_never_supply_a_clinical_grade(name):
    result = compute_composite_severity(dict(predicted_class=name, vit_confidence_pct=100,
        attention_coverage_pct=100, lesion_coverage_pct=100, yolo_detection_count=5))
    assert result.grade == "Unassessable"
    assert result.source == "visual_thresholds" and result.score is None


def test_identical_clinical_findings_ignore_image_confidence_and_coverage():
    low = assess_clinical_severity("Mastitis", mastitis(), dict(vit_confidence_pct=1, lesion_coverage_pct=0))
    high = assess_clinical_severity("Mastitis", mastitis(), dict(vit_confidence_pct=100, lesion_coverage_pct=100))
    assert low.grade == high.grade == "Mild"
    assert low.score == high.score == 1


def test_welfare_concerns_are_visible_in_incomplete_profiles():
    result = assess_clinical_severity("Mastitis", dict(disease="mastitis", systemic_illness=True))
    assert result.grade == "Unassessable"
    assert "prompt in-person veterinary assessment" in result.evidence[0]


@pytest.mark.parametrize("changes", [dict(affected_feet=5), dict(affected_feet=True),
    dict(mouth_lesion_cm=-1), dict(mouth_lesion_cm=float("nan")), dict(mouth_lesion_cm=float("inf")),
    dict(unable_to_stand="false"), dict(milk_abnormal=True)])
def test_reject_malformed_or_cross_disease_observations(changes):
    with pytest.raises(ValidationError):
        ClinicalObservations.model_validate(fmd(**changes))


def test_llm_cannot_override_checklist_in_direct_pipeline_calls():
    vision = {"detections": [{"vit_predicted_class": "mastitis", "severity_grade": "Severe"}],
              "clinical_observations": mastitis()}
    with patch("components.smart_diagnostics.pipeline.llm_reasoner._discover_model_name", side_effect=AssertionError("LLM must not run")):
        report, result = generate_veterinary_report(vision)
    assert result.grade == "Mild"
    assert "checklist" in report.lower()
    _, parsed = parse_llm_severity_assessment("[SEVERITY_META: Grade=Severe | Prognosis=Poor | Description=Fabricated]", vision)
    assert parsed.grade == "Mild" and "Fabricated" not in parsed.description


def test_reason_endpoint_recomputes_grade_and_rejects_wrong_checklist(create_app):
    client = TestClient(create_app())
    request = dict(cattle_detected=True, detections=[],
        disease=dict(name="Mastitis", confidence=99, all_probabilities={"Mastitis": 99}),
        severity=dict(grade="Severe", score=0.99), clinical_observations=mastitis())
    response = client.post("/api/reason", json=request)
    assert response.status_code == 200
    result = response.json()["severity_assessment"]
    assert result["grade"] == "Mild" and result["clinical_observations"] == ClinicalObservations(**mastitis()).model_dump()
    request["clinical_observations"] = fmd()
    assert client.post("/api/reason", json=request).status_code == 422
    del request["clinical_observations"]
    assert client.post("/api/reason", json=request).json()["severity_assessment"]["grade"] == "Unassessable"


@pytest.mark.parametrize("name", ["Foot and Mouth Disease", "Mastitis"])
def test_detect_automatically_estimates_visual_severity_for_clinical_diseases(name, create_app, dummy_rgb_image_bytes, mock_yolo_single_detection):
    client = TestClient(create_app(detector=FakeDetector(mock_yolo_single_detection),
        classifier=FakeClassifier(dict(name=name, confidence=99.9, all_probabilities={name: 99.9},
                                      attention_coverage_pct=99, attention_cluster_count=10, top2_margin=99)),
        segmenter=FakeSegmenter()))
    response = client.post("/api/detect", files={"image": ("cow.jpg", dummy_rgb_image_bytes, "image/jpeg")})
    assert response.status_code == 200
    assert response.json()["severity"]["grade"] == "Mild"
    assert response.json()["severity"]["source"] == "visual_thresholds"
    assert response.json()["severity"]["clinical_observations"] is None
    assert response.json()["symptoms_image"]  # Existing image-model evidence is still returned.
