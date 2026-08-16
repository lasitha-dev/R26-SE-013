"""
test_llm_reasoner.py — LLM reasoning & client resilience tests
================================================================

Tests for user prompt construction, model discovery fallback, and
error resilience when LM Studio is unreachable.

All OpenAI/LM Studio network calls are mocked — no local LLM or
network access required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from components.smart_diagnostics.pipeline.llm_reasoner import (
    _build_user_prompt,
    _discover_model_name,
    generate_veterinary_report,
)
from components.smart_diagnostics.pipeline import config as cfg


# ═══════════════════════════════════════════════════════════════════════════
# _build_user_prompt
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildUserPrompt:
    """Tests for the user prompt builder that formats vision telemetry."""

    def test_build_user_prompt_contains_detection_telemetry(self):
        """All key vision fields appear in the generated prompt text."""
        detections = [
            {
                "yolo_class": "cattle",
                "bbox": [50.0, 30.0, 400.0, 350.0],
                "bbox_width_px": 350.0,
                "bbox_height_px": 320.0,
                "bbox_area_pct": 36.46,
                "yolo_confidence": 0.92,
                "vit_predicted_display": "Lumpy Skin Disease",
                "vit_predicted_class": "lumpy_skin",
                "vit_confidence_pct": 91.5,
                "vit_probabilities": {
                    "Cattle (Healthy)": 3.0,
                    "Lumpy Skin Disease": 91.5,
                },
            }
        ]
        image_size = {"width": 640, "height": 480}

        prompt = _build_user_prompt(detections, image_size)

        # Primary diagnosis and confidence
        assert "Lumpy Skin Disease" in prompt
        assert "91.5" in prompt
        # Bounding box coordinates
        assert "50.0" in prompt
        assert "400.0" in prompt
        # Image dimensions
        assert "640" in prompt
        assert "480" in prompt
        # YOLO confidence
        assert "0.92" in prompt
        # Probability distribution
        assert "Cattle (Healthy)" in prompt
        assert "3.0%" in prompt

    def test_build_user_prompt_includes_farm_metadata(self):
        """Farm metadata keys are formatted with title case in the prompt."""
        detections = []
        image_size = {"width": 640, "height": 480}
        farm_metadata = {
            "herd_size": "45",
            "location": "Western Province, Sri Lanka",
        }

        prompt = _build_user_prompt(detections, image_size, farm_metadata)

        assert "Farm Metadata" in prompt
        assert "Herd Size" in prompt
        assert "45" in prompt
        assert "Location" in prompt
        assert "Western Province" in prompt

    def test_build_user_prompt_handles_empty_detections(self):
        """Zero detections produce a valid prompt without errors."""
        prompt = _build_user_prompt([], {"width": 640, "height": 480})

        assert "Total detections" in prompt
        assert "0" in prompt

    def test_build_user_prompt_multiple_detections_numbered(self):
        """Multiple detections are numbered sequentially (Detection 1, 2, 3)."""
        detections = [
            {"yolo_class": "cattle", "bbox": [0, 0, 100, 100],
             "bbox_width_px": 100, "bbox_height_px": 100,
             "bbox_area_pct": 3.0, "yolo_confidence": 0.9,
             "vit_predicted_display": "Healthy", "vit_confidence_pct": 90.0,
             "vit_probabilities": {}},
            {"yolo_class": "foot_and_mouth", "bbox": [200, 200, 300, 300],
             "bbox_width_px": 100, "bbox_height_px": 100,
             "bbox_area_pct": 3.0, "yolo_confidence": 0.8,
             "vit_predicted_display": "Foot and Mouth Disease",
             "vit_confidence_pct": 85.0, "vit_probabilities": {}},
            {"yolo_class": "cattle", "bbox": [400, 400, 500, 500],
             "bbox_width_px": 100, "bbox_height_px": 100,
             "bbox_area_pct": 3.0, "yolo_confidence": 0.7,
             "vit_predicted_display": "Healthy", "vit_confidence_pct": 70.0,
             "vit_probabilities": {}},
        ]

        prompt = _build_user_prompt(detections, {"width": 640, "height": 640})

        assert "Detection 1" in prompt
        assert "Detection 2" in prompt
        assert "Detection 3" in prompt


# ═══════════════════════════════════════════════════════════════════════════
# _discover_model_name
# ═══════════════════════════════════════════════════════════════════════════

class TestDiscoverModelName:
    """Tests for the LM Studio model discovery helper."""

    def test_discover_model_name_fallback_on_failure(self):
        """When the models.list() call fails, falls back to cfg.LLM_MODEL_NAME."""
        mock_client = MagicMock()
        mock_client.models.list.side_effect = Exception("Connection refused")

        result = _discover_model_name(mock_client)

        assert result == cfg.LLM_MODEL_NAME


# ═══════════════════════════════════════════════════════════════════════════
# generate_veterinary_report
# ═══════════════════════════════════════════════════════════════════════════

class TestGenerateVeterinaryReport:
    """Tests for the main report generation function.

    All OpenAI client calls are mocked to avoid network access.
    The ``from openai import OpenAI`` inside ``generate_veterinary_report``
    resolves from the ``openai`` package, so we patch ``openai.OpenAI``.
    """

    @patch("openai.OpenAI")
    def test_generate_report_success_returns_llm_content(self, MockOpenAI):
        """A successful LLM completion returns the response content."""
        # Configure the mock chain: client.chat.completions.create()
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client

        # Mock model discovery
        mock_model_list = MagicMock()
        mock_model_list.data = []
        mock_client.models.list.return_value = mock_model_list

        # Mock chat completion
        mock_choice = MagicMock()
        mock_choice.message.content = "## 1. Primary Diagnostic Assessment\nTest report content."
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        vision_results = {
            "detections": [],
            "image_size": {"width": 640, "height": 480},
        }

        report = generate_veterinary_report(vision_results)

        assert "Primary Diagnostic Assessment" in report
        assert "Test report content" in report

    @patch("openai.OpenAI")
    def test_generate_report_empty_response_returns_warning(self, MockOpenAI):
        """An empty LLM response returns a warning message."""
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.models.list.return_value = MagicMock(data=[])

        mock_choice = MagicMock()
        mock_choice.message.content = ""  # Empty response
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        vision_results = {
            "detections": [],
            "image_size": {"width": 640, "height": 480},
        }

        report = generate_veterinary_report(vision_results)

        assert "⚠" in report
        assert "empty" in report.lower()

    @patch("openai.OpenAI")
    def test_generate_report_api_connection_error_returns_fallback(self, MockOpenAI):
        """An API connection error returns a graceful fallback string.

        The function must NOT crash with an unhandled exception — it should
        return a ``⚠️`` prefixed fallback containing troubleshooting steps.
        """
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.models.list.return_value = MagicMock(data=[])

        # Simulate a connection error during chat completion
        mock_client.chat.completions.create.side_effect = ConnectionError(
            "Connection refused"
        )

        vision_results = {
            "detections": [],
            "image_size": {"width": 640, "height": 480},
        }

        # Should NOT raise — returns fallback string instead
        report = generate_veterinary_report(vision_results)

        assert isinstance(report, str)
        assert "⚠" in report
        assert "LM Studio" in report or "Unreachable" in report or "Error" in report

    @patch("openai.OpenAI")
    def test_generate_report_api_timeout_error_returns_fallback(self, MockOpenAI):
        """A timeout error returns a graceful fallback without crashing."""
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.models.list.return_value = MagicMock(data=[])

        mock_client.chat.completions.create.side_effect = TimeoutError(
            "Request timed out"
        )

        vision_results = {
            "detections": [],
            "image_size": {"width": 640, "height": 480},
        }

        report = generate_veterinary_report(vision_results)

        assert isinstance(report, str)
        assert "⚠" in report
