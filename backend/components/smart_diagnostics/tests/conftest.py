"""
Shared pytest fixtures for the smart_diagnostics test suite.
=============================================================

Provides reusable image byte streams, mock model outputs, and a
pre-configured FastAPI ``TestClient`` so that individual test
modules stay focused on assertions rather than setup boilerplate.

No real model weights, GPU, or network access is required.
"""

from __future__ import annotations

import io
from typing import Dict, List
from unittest.mock import MagicMock

import pytest
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.smart_diagnostics.routes import router


# ═══════════════════════════════════════════════════════════════════════════
# Image byte-stream fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def dummy_rgb_image_bytes() -> bytes:
    """A valid 640×640 JPEG byte stream generated in-memory via PIL.

    Useful for any test that needs to POST a legitimate image file to
    the ``/api/detect`` endpoint without touching the filesystem.
    """
    img = Image.new("RGB", (640, 640), color=(120, 80, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def dummy_small_image_bytes() -> bytes:
    """A valid but small 100×100 JPEG for lightweight tests."""
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def dummy_corrupt_image_bytes() -> bytes:
    """Truncated garbage bytes that will cause ``PIL.Image.open()`` to fail.

    Simulates a partially uploaded or corrupted image file.
    """
    return b"\x89PNG\r\n\x1a\n\x00\x00"  # 10 bytes — incomplete PNG header


@pytest.fixture
def dummy_non_image_bytes() -> bytes:
    """Plain text bytes to test MIME-type/content rejection."""
    return b"Hello, this is definitely not an image file."


@pytest.fixture
def dummy_empty_bytes() -> bytes:
    """Zero-byte payload for empty file upload tests."""
    return b""


# ═══════════════════════════════════════════════════════════════════════════
# Mock model output fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_yolo_detections() -> List[Dict]:
    """Synthetic YOLO bounding box results matching the detector output format.

    Two detections: one high-confidence cattle, one lower-confidence
    foot_and_mouth, to support tests that need ``max()`` selection.
    """
    return [
        {
            "bbox": [50.0, 30.0, 400.0, 350.0],
            "confidence": 0.92,
            "class_name": "cattle",
        },
        {
            "bbox": [120.0, 100.0, 250.0, 220.0],
            "confidence": 0.78,
            "class_name": "foot_and_mouth",
        },
    ]


@pytest.fixture
def mock_yolo_single_detection() -> List[Dict]:
    """Single high-confidence cattle detection."""
    return [
        {
            "bbox": [10.0, 10.0, 300.0, 300.0],
            "confidence": 0.95,
            "class_name": "cattle",
        },
    ]


@pytest.fixture
def mock_vit_prediction_healthy() -> Dict:
    """Deterministic ViT output for a healthy cattle classification."""
    return {
        "name": "Cattle (Healthy)",
        "confidence": 95.0,
        "all_probabilities": {
            "Cattle (Healthy)": 95.0,
            "Foot and Mouth Disease": 2.0,
            "Lumpy Skin Disease": 1.5,
            "Mastitis": 1.5,
        },
        "top2_margin": 93.0,
        "attention_coverage_pct": 0.0,
        "attention_cluster_count": 0,
    }


@pytest.fixture
def mock_vit_prediction_diseased() -> Dict:
    """Deterministic ViT output for a Lumpy Skin Disease classification."""
    return {
        "name": "Lumpy Skin Disease",
        "confidence": 91.5,
        "all_probabilities": {
            "Cattle (Healthy)": 3.0,
            "Foot and Mouth Disease": 2.5,
            "Lumpy Skin Disease": 91.5,
            "Mastitis": 3.0,
        },
        "top2_margin": 88.5,
        "attention_coverage_pct": 45.0,
        "attention_cluster_count": 5,
    }


@pytest.fixture
def mock_vit_prediction_with_attention_diseased() -> Dict:
    """Deterministic ViT output with detailed attention rollout telemetry."""
    return {
        "name": "Lumpy Skin Disease",
        "confidence": 91.5,
        "all_probabilities": {
            "Cattle (Healthy)": 3.0,
            "Foot and Mouth Disease": 2.5,
            "Lumpy Skin Disease": 91.5,
            "Mastitis": 3.0,
        },
        "top2_margin": 88.5,
        "attention_coverage_pct": 65.0,
        "attention_cluster_count": 8,
    }


@pytest.fixture
def mock_vit_prediction_cattle_with_secondary_risk() -> Dict:
    """ViT output where primary is healthy (85%) but mastitis is 10%.

    Useful for asserting that secondary risk probabilities are surfaced.
    """
    return {
        "name": "Cattle (Healthy)",
        "confidence": 85.0,
        "all_probabilities": {
            "Cattle (Healthy)": 85.0,
            "Foot and Mouth Disease": 3.0,
            "Lumpy Skin Disease": 2.0,
            "Mastitis": 10.0,
        },
        "top2_margin": 75.0,
        "attention_coverage_pct": 0.0,
        "attention_cluster_count": 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Fake model stubs for route-level integration tests
# ═══════════════════════════════════════════════════════════════════════════

class FakeDetector:
    """Configurable fake detector for route integration tests.

    Parameters
    ----------
    detections : list[dict] | None
        The detections to return.  Pass ``[]`` for gate rejection
        or ``None`` to simulate no model loaded.
    """

    def __init__(self, detections: List[Dict] | None = None):
        self._detections = detections if detections is not None else []
        self.is_loaded = True

    def predict(self, image) -> List[Dict]:
        return self._detections


class FakeClassifier:
    """Configurable fake classifier for route integration tests."""

    def __init__(self, result: Dict | None = None):
        self._result = result or {
            "name": "Cattle (Healthy)",
            "confidence": 95.0,
            "all_probabilities": {"Cattle (Healthy)": 95.0},
            "top2_margin": 95.0,
            "attention_coverage_pct": 0.0,
            "attention_cluster_count": 0,
        }
        self.is_loaded = True

    def predict(self, image) -> Dict:
        return self._result

    def predict_with_attention(self, image) -> Dict:
        res = dict(self._result)
        res.setdefault("attention_coverage_pct", 0.0)
        res.setdefault("attention_cluster_count", 0)
        res.setdefault("top2_margin", 0.0)
        return res


class FakeSegmenter:
    """Fake segmenter that returns a test image and metrics."""

    def __init__(self):
        self.is_loaded = True

    def predict(self, image):
        # Return a small RGB image as the "symptoms overlay"
        return Image.new("RGB", (100, 100), color=(255, 0, 0))

    def predict_with_metrics(self, image):
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        metrics = {
            "lesion_coverage_pct": 5.0,
            "cluster_count": 2,
            "lesion_pixels": 500,
            "mean_intensity": 0.75,
        }
        return img, metrics


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI TestClient fixtures
# ═══════════════════════════════════════════════════════════════════════════

def _create_test_app(
    detector=None,
    classifier=None,
    segmenter=None,
    device: str = "cpu",
) -> FastAPI:
    """Build a minimal FastAPI app wired with injectable model stubs."""
    app = FastAPI()
    app.state.detector = detector
    app.state.classifier = classifier
    app.state.segmenter = segmenter
    app.state.device = device
    app.include_router(router)
    return app


@pytest.fixture
def test_app(mock_yolo_single_detection, mock_vit_prediction_healthy):
    """A fully-wired test app with fake detector + classifier + segmenter.

    Default behaviour: single cattle detection → healthy classification.
    """
    return _create_test_app(
        detector=FakeDetector(mock_yolo_single_detection),
        classifier=FakeClassifier(mock_vit_prediction_healthy),
        segmenter=FakeSegmenter(),
    )


@pytest.fixture
def client(test_app) -> TestClient:
    """FastAPI ``TestClient`` initialised with the default test app."""
    return TestClient(test_app)


@pytest.fixture
def create_app():
    """Factory fixture — returns ``_create_test_app`` so tests can
    customise the detector/classifier/segmenter per-scenario.
    """
    return _create_test_app
