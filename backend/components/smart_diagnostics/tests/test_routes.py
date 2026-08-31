"""
test_routes.py — FastAPI endpoint integration tests
======================================================

Tests for ``POST /api/detect``, ``POST /api/reason``, and ``GET /api/health``
using configurable fake model stubs injected via ``conftest.py`` fixtures.

No real model weights, GPU, or network access required.
"""

from __future__ import annotations

import io
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from .conftest import FakeDetector, FakeClassifier, FakeSegmenter


# ═══════════════════════════════════════════════════════════════════════════
# Helper — create a JPEG UploadFile payload from conftest fixtures
# ═══════════════════════════════════════════════════════════════════════════

def _upload_jpeg(client: TestClient, image_bytes: bytes, filename: str = "test.jpg"):
    """POST an image to ``/api/detect`` and return the response."""
    return client.post(
        "/api/detect",
        files={"image": (filename, io.BytesIO(image_bytes), "image/jpeg")},
    )


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/detect
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectEndpoint:
    """Integration tests for the ``/api/detect`` endpoint."""

    def test_detect_endpoint_full_pipeline_success_returns_200_with_detection(
        self, client, dummy_rgb_image_bytes
    ):
        """Full pipeline: YOLO detects cattle → ViT classifies → 200 with result.

        Uses the default ``client`` fixture which wires FakeDetector (single
        cattle detection) and FakeClassifier (healthy prediction).
        """
        resp = _upload_jpeg(client, dummy_rgb_image_bytes)

        assert resp.status_code == 200
        data = resp.json()
        assert data["cattle_detected"] is True
        assert len(data["detections"]) == 1
        assert data["best_detection"] is not None
        assert data["best_detection"]["confidence"] == 0.95
        assert data["disease"]["name"] == "Cattle (Healthy)"
        assert data["disease"]["confidence"] == 95.0
        assert data["image_size"]["width"] == 640
        assert data["image_size"]["height"] == 640

    def test_detect_endpoint_yolo_gate_rejection_returns_200_no_detection(
        self, create_app, dummy_rgb_image_bytes
    ):
        """YOLO returns zero detections → 200 with ``cattle_detected=False``."""
        app = create_app(
            detector=FakeDetector(detections=[]),  # Gate rejection
            classifier=FakeClassifier(),
        )
        client = TestClient(app)

        resp = _upload_jpeg(client, dummy_rgb_image_bytes)

        assert resp.status_code == 200
        data = resp.json()
        assert data["cattle_detected"] is False
        assert data["detections"] == []
        assert data["best_detection"] is None
        assert data["disease"] is None

    def test_detect_endpoint_diseased_prediction_runs_segmenter(
        self, create_app, dummy_rgb_image_bytes, mock_yolo_single_detection
    ):
        """When ViT predicts a disease, the segmenter runs and symptoms_image is populated."""
        disease_result = {
            "name": "Lumpy Skin Disease",
            "confidence": 91.5,
            "all_probabilities": {
                "Cattle (Healthy)": 3.0,
                "Lumpy Skin Disease": 91.5,
                "Mastitis": 3.0,
                "Foot and Mouth Disease": 2.5,
            },
        }
        app = create_app(
            detector=FakeDetector(mock_yolo_single_detection),
            classifier=FakeClassifier(disease_result),
            segmenter=FakeSegmenter(),
        )
        client = TestClient(app)

        resp = _upload_jpeg(client, dummy_rgb_image_bytes)

        assert resp.status_code == 200
        data = resp.json()
        assert data["cattle_detected"] is True
        assert data["disease"]["name"] == "Lumpy Skin Disease"
        # Segmenter should have run → symptoms_image populated
        assert data["symptoms_image"] is not None
        assert data["symptoms_image"].startswith("data:image/jpeg;base64,")

    def test_detect_endpoint_healthy_prediction_skips_segmenter(
        self, create_app, dummy_rgb_image_bytes, mock_yolo_single_detection,
        mock_vit_prediction_healthy
    ):
        """When ViT predicts healthy, the segmenter is skipped → symptoms_image is None."""
        app = create_app(
            detector=FakeDetector(mock_yolo_single_detection),
            classifier=FakeClassifier(mock_vit_prediction_healthy),
            segmenter=FakeSegmenter(),
        )
        client = TestClient(app)

        resp = _upload_jpeg(client, dummy_rgb_image_bytes)

        assert resp.status_code == 200
        data = resp.json()
        assert data["disease"]["name"] == "Cattle (Healthy)"
        assert data["symptoms_image"] is None

    def test_detect_endpoint_no_models_loaded_returns_200_degraded(
        self, create_app, dummy_rgb_image_bytes
    ):
        """When detector=None (models not loaded), returns 200 with cattle_detected=False."""
        app = create_app(detector=None, classifier=None)
        client = TestClient(app)

        resp = _upload_jpeg(client, dummy_rgb_image_bytes)

        assert resp.status_code == 200
        data = resp.json()
        assert data["cattle_detected"] is False

    def test_detect_endpoint_corrupt_image_raises_error(
        self, test_app, dummy_corrupt_image_bytes
    ):
        """Corrupt image bytes cause a server-side error (PIL fails to open)."""
        client = TestClient(test_app, raise_server_exceptions=False)
        resp = _upload_jpeg(client, dummy_corrupt_image_bytes)

        # PIL.UnidentifiedImageError is not caught by routes.py, so we expect 500
        assert resp.status_code == 500

    def test_detect_endpoint_empty_file_raises_error(
        self, test_app, dummy_empty_bytes
    ):
        """Zero-byte upload causes a server-side error."""
        client = TestClient(test_app, raise_server_exceptions=False)
        resp = _upload_jpeg(client, dummy_empty_bytes)

        assert resp.status_code == 500

    def test_detect_endpoint_bounding_box_normalized_correct(
        self, create_app, dummy_rgb_image_bytes
    ):
        """Normalised bounding box values equal raw bbox / image dimensions.

        With a 640×640 image and bbox [10, 10, 300, 300]:
        x1_norm = 10/640, y1_norm = 10/640, x2_norm = 300/640, y2_norm = 300/640
        """
        detections = [{"bbox": [10.0, 10.0, 300.0, 300.0], "confidence": 0.95, "class_name": "cattle"}]
        app = create_app(
            detector=FakeDetector(detections),
            classifier=FakeClassifier(),
        )
        client = TestClient(app)

        resp = _upload_jpeg(client, dummy_rgb_image_bytes)

        data = resp.json()
        bbox_norm = data["best_detection"]["bbox_normalized"]
        assert abs(bbox_norm["x1"] - 10.0 / 640) < 1e-4
        assert abs(bbox_norm["y1"] - 10.0 / 640) < 1e-4
        assert abs(bbox_norm["x2"] - 300.0 / 640) < 1e-4
        assert abs(bbox_norm["y2"] - 300.0 / 640) < 1e-4

    def test_detect_endpoint_secondary_risk_probabilities_surfaced(
        self, create_app, dummy_rgb_image_bytes, mock_yolo_single_detection,
        mock_vit_prediction_cattle_with_secondary_risk
    ):
        """The full probability breakdown (including secondary risks) appears in the response."""
        app = create_app(
            detector=FakeDetector(mock_yolo_single_detection),
            classifier=FakeClassifier(mock_vit_prediction_cattle_with_secondary_risk),
        )
        client = TestClient(app)

        resp = _upload_jpeg(client, dummy_rgb_image_bytes)

        data = resp.json()
        probs = data["disease"]["all_probabilities"]
        assert probs["Cattle (Healthy)"] == 85.0
        assert probs["Mastitis"] == 10.0


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/reason
# ═══════════════════════════════════════════════════════════════════════════

class TestReasonEndpoint:
    """Integration tests for the ``/api/reason`` endpoint (Tier 3 LLM)."""

    @patch("components.smart_diagnostics.pipeline.llm_reasoner.generate_veterinary_report")
    def test_reason_endpoint_success_returns_ok_report(
        self, mock_generate, client
    ):
        """Successful LLM report generation returns status=ok with Markdown content and severity assessment."""
        from components.smart_diagnostics.schemas import SeverityMetrics
        mock_sev = SeverityMetrics(grade="Mild", prognosis="Favorable", confidence_level="High")
        mock_generate.return_value = ("## 1. Primary Diagnostic Assessment\nAll clear.", mock_sev)

        resp = client.post("/api/reason", json={
            "cattle_detected": True,
            "detections": [{"bbox": [10, 20, 100, 200], "confidence": 0.95, "class_name": "cattle"}],
            "best_detection": {
                "bbox": [10, 20, 100, 200],
                "confidence": 0.95,
                "bbox_normalized": {"x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5},
            },
            "disease": {"name": "Cattle (Healthy)", "confidence": 95.0, "all_probabilities": {}},
            "image_size": {"width": 640, "height": 480},
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "Primary Diagnostic Assessment" in data["reasoning_report"]
        assert data["severity_assessment"]["grade"] == "Mild"

    @patch("components.smart_diagnostics.pipeline.llm_reasoner.generate_veterinary_report")
    def test_reason_endpoint_llm_error_returns_error_status(
        self, mock_generate, client
    ):
        """An LLM error report (starting with ⚠) returns status=error."""
        from components.smart_diagnostics.schemas import SeverityMetrics
        mock_sev = SeverityMetrics(grade="Moderate", prognosis="Guarded", confidence_level="Low", needs_review=True)
        mock_generate.return_value = ("⚠️  **Tier 3 Error — LLM Unreachable**", mock_sev)

        resp = client.post("/api/reason", json={
            "cattle_detected": True,
            "detections": [],
            "image_size": {"width": 640, "height": 480},
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "Unreachable" in data["reasoning_report"]
        assert data["severity_assessment"]["needs_review"] is True

    @patch("components.smart_diagnostics.pipeline.llm_reasoner.generate_veterinary_report")
    def test_reason_endpoint_exception_returns_error_gracefully(
        self, mock_generate, client
    ):
        """An unhandled exception in the reasoner returns status=error."""
        mock_generate.side_effect = RuntimeError("Unexpected LLM failure")

        resp = client.post("/api/reason", json={
            "cattle_detected": True,
            "detections": [],
            "image_size": {"width": 640, "height": 480},
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "Unexpected LLM failure" in data["reasoning_report"]


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/health
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    """Tests for the ``/api/health`` model status endpoint."""

    def test_health_endpoint_all_loaded_returns_ok(self, create_app):
        """When all 3 models are loaded, health status is 'ok'."""
        app = create_app(
            detector=FakeDetector(),
            classifier=FakeClassifier(),
            segmenter=FakeSegmenter(),
        )
        client = TestClient(app)

        resp = client.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["models"]["yolo_detector"]["loaded"] is True
        assert data["models"]["vit_classifier"]["loaded"] is True
        assert data["models"]["mask_rcnn_segmenter"]["loaded"] is True

    def test_health_endpoint_partial_load_returns_degraded(self, create_app):
        """When one model is missing (None), health status is 'degraded'."""
        app = create_app(
            detector=FakeDetector(),
            classifier=FakeClassifier(),
            segmenter=None,  # Not loaded
        )
        client = TestClient(app)

        resp = client.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["models"]["mask_rcnn_segmenter"]["registered"] is False
