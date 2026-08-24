"""
test_schemas.py — Pydantic schema validation tests
=====================================================

Verifies serialisation/deserialisation round-trips and validation
errors for every schema in ``components.smart_diagnostics.schemas``.

These tests run without any model loading or network access.
"""

import pytest
from pydantic import ValidationError

from components.smart_diagnostics.schemas import (
    Detection,
    BoundingBoxNormalized,
    BestDetection,
    Disease,
    DetectResponse,
    ReasoningRequest,
    ReasoningResponse,
)


# ═══════════════════════════════════════════════════════════════════════════
# Detection
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectionSchema:
    """Tests for the ``Detection`` schema (YOLO per-box output)."""

    def test_detection_schema_valid_data_serializes(self):
        """Valid Detection with all required fields round-trips correctly."""
        det = Detection(
            bbox=[10.0, 20.0, 100.0, 200.0],
            confidence=0.95,
            class_name="cattle",
        )
        data = det.model_dump()
        assert data["bbox"] == [10.0, 20.0, 100.0, 200.0]
        assert data["confidence"] == 0.95
        assert data["class_name"] == "cattle"

    def test_detection_schema_missing_field_raises_error(self):
        """Omitting a required field (class_name) raises ValidationError."""
        with pytest.raises(ValidationError):
            Detection(bbox=[10.0, 20.0, 100.0, 200.0], confidence=0.9)


# ═══════════════════════════════════════════════════════════════════════════
# BoundingBoxNormalized
# ═══════════════════════════════════════════════════════════════════════════

class TestBoundingBoxNormalizedSchema:
    """Tests for the ``BoundingBoxNormalized`` schema."""

    def test_bounding_box_normalized_schema_valid(self):
        """Valid normalised bbox with values in [0, 1] serialises."""
        bbox = BoundingBoxNormalized(x1=0.1, y1=0.2, x2=0.8, y2=0.9)
        data = bbox.model_dump()
        assert data == {"x1": 0.1, "y1": 0.2, "x2": 0.8, "y2": 0.9}


# ═══════════════════════════════════════════════════════════════════════════
# Disease
# ═══════════════════════════════════════════════════════════════════════════

class TestDiseaseSchema:
    """Tests for the ``Disease`` schema (ViT classification output)."""

    def test_disease_schema_valid_data_serializes(self):
        """Full Disease object with probability distribution round-trips."""
        disease = Disease(
            name="Lumpy Skin Disease",
            confidence=91.5,
            all_probabilities={
                "Cattle (Healthy)": 3.0,
                "Foot and Mouth Disease": 2.5,
                "Lumpy Skin Disease": 91.5,
                "Mastitis": 3.0,
            },
        )
        data = disease.model_dump()
        assert data["name"] == "Lumpy Skin Disease"
        assert data["confidence"] == 91.5
        assert len(data["all_probabilities"]) == 4
        assert data["all_probabilities"]["Lumpy Skin Disease"] == 91.5


# ═══════════════════════════════════════════════════════════════════════════
# DetectResponse
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectResponseSchema:
    """Tests for the ``DetectResponse`` schema (POST /api/detect response)."""

    def test_detect_response_schema_full_payload(self):
        """Full DetectResponse with all optional fields populated."""
        resp = DetectResponse(
            cattle_detected=True,
            detections=[
                Detection(bbox=[10, 20, 100, 200], confidence=0.95, class_name="cattle"),
            ],
            best_detection=BestDetection(
                bbox=[10, 20, 100, 200],
                confidence=0.95,
                bbox_normalized=BoundingBoxNormalized(x1=0.1, y1=0.1, x2=0.5, y2=0.5),
            ),
            disease=Disease(
                name="Cattle (Healthy)",
                confidence=95.0,
                all_probabilities={"Cattle (Healthy)": 95.0},
            ),
            cropped_image="data:image/jpeg;base64,/9j/...",
            symptoms_image="data:image/jpeg;base64,/9j/...",
            image_size={"width": 640, "height": 480},
            device="cuda:0",
        )
        data = resp.model_dump()
        assert data["cattle_detected"] is True
        assert len(data["detections"]) == 1
        assert data["best_detection"]["confidence"] == 0.95
        assert data["disease"]["name"] == "Cattle (Healthy)"
        assert data["cropped_image"].startswith("data:image")
        assert data["symptoms_image"].startswith("data:image")
        assert data["image_size"]["width"] == 640
        assert data["device"] == "cuda:0"

    def test_detect_response_schema_minimal_payload(self):
        """Minimal DetectResponse for no-detection (gate rejection) case."""
        resp = DetectResponse(
            cattle_detected=False,
            detections=[],
            best_detection=None,
            disease=None,
            cropped_image=None,
            symptoms_image=None,
            image_size={"width": 640, "height": 640},
            device="cpu",
        )
        data = resp.model_dump()
        assert data["cattle_detected"] is False
        assert data["detections"] == []
        assert data["best_detection"] is None
        assert data["disease"] is None
        assert data["cropped_image"] is None


# ═══════════════════════════════════════════════════════════════════════════
# ReasoningRequest / ReasoningResponse
# ═══════════════════════════════════════════════════════════════════════════

class TestReasoningSchemas:
    """Tests for the Tier 3 LLM reasoning request/response schemas."""

    def test_reasoning_request_schema_valid(self):
        """Valid ReasoningRequest with all fields serialises correctly."""
        req = ReasoningRequest(
            cattle_detected=True,
            detections=[
                Detection(bbox=[10, 20, 100, 200], confidence=0.95, class_name="cattle"),
            ],
            best_detection=BestDetection(
                bbox=[10, 20, 100, 200],
                confidence=0.95,
                bbox_normalized=BoundingBoxNormalized(x1=0.1, y1=0.1, x2=0.5, y2=0.5),
            ),
            disease=Disease(
                name="Mastitis",
                confidence=88.3,
                all_probabilities={"Mastitis": 88.3, "Cattle (Healthy)": 11.7},
            ),
            image_size={"width": 640, "height": 480},
            farm_metadata={"herd_size": "45", "location": "Western Province"},
        )
        data = req.model_dump()
        assert data["cattle_detected"] is True
        assert data["farm_metadata"]["herd_size"] == "45"
        assert data["disease"]["name"] == "Mastitis"

    def test_reasoning_response_schema_valid(self):
        """Valid ReasoningResponse round-trips correctly."""
        resp = ReasoningResponse(
            status="ok",
            reasoning_report="## 1. Primary Diagnostic Assessment\n...",
            model_name="qwen2.5-vl-3b-instruct",
        )
        data = resp.model_dump()
        assert data["status"] == "ok"
        assert "Primary Diagnostic Assessment" in data["reasoning_report"]
        assert data["model_name"] == "qwen2.5-vl-3b-instruct"
