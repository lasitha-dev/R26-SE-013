"""
test_vision_engine.py — Vision pipeline unit tests
=====================================================

Tests for ``SquarePad``, the ViT preprocessing transform pipeline,
bounding-box area computation, and crop extraction strategies.

All tests use deterministic PIL images — no YOLO/ViT model weights
or GPU access required.
"""

from __future__ import annotations

import pytest
from PIL import Image

from components.smart_diagnostics.pipeline.vision_engine import (
    SquarePad,
    _vit_transform,
    _bbox_area_fraction,
    _extract_crop,
)
from components.smart_diagnostics.pipeline import config as cfg


# ═══════════════════════════════════════════════════════════════════════════
# SquarePad transform
# ═══════════════════════════════════════════════════════════════════════════

class TestSquarePad:
    """Tests for the aspect-ratio-preserving ``SquarePad`` transform."""

    def test_squarepad_wide_image_padded_to_square(self):
        """A wide 400×150 image is padded to a 400×400 square."""
        img = Image.new("RGB", (400, 150), color=(200, 100, 50))
        pad = SquarePad()
        result = pad(img)
        assert result.size == (400, 400), (
            f"Expected (400, 400), got {result.size}"
        )

    def test_squarepad_tall_image_padded_to_square(self):
        """A tall 120×380 image is padded to a 380×380 square."""
        img = Image.new("RGB", (120, 380), color=(50, 200, 100))
        pad = SquarePad()
        result = pad(img)
        assert result.size == (380, 380), (
            f"Expected (380, 380), got {result.size}"
        )

    def test_squarepad_square_image_unchanged(self):
        """An already-square 300×300 image retains the same dimensions."""
        img = Image.new("RGB", (300, 300), color=(0, 0, 0))
        pad = SquarePad()
        result = pad(img)
        assert result.size == (300, 300)

    def test_squarepad_fill_color_is_114_114_114(self):
        """The padded region uses the Ultralytics letterbox grey (114, 114, 114).

        We test by padding a tall image and sampling a pixel in the
        horizontal padding region (left column, vertically centred).
        """
        img = Image.new("RGB", (100, 300), color=(255, 0, 0))
        pad = SquarePad(fill=(114, 114, 114))
        result = pad(img)

        # The padded canvas is 300×300.  The original 100-wide image is
        # centred, so the left padding starts at x=0 and extends to
        # x = (300 - 100) // 2 - 1 = 99.  Sample (0, 150) — guaranteed pad.
        px = result.getpixel((0, 150))
        assert px == (114, 114, 114), f"Expected (114, 114, 114), got {px}"

    def test_squarepad_original_image_centered(self):
        """The original image content is centred on the padded canvas.

        Create a 100×300 red image, pad to 300×300, then check that
        the centre pixel is red (from the original image).
        """
        original_color = (255, 0, 0)
        img = Image.new("RGB", (100, 300), color=original_color)
        pad = SquarePad()
        result = pad(img)

        # Centre of canvas = (150, 150).  Original is pasted at x=100,
        # so pixel (150, 150) should be within the original image.
        px = result.getpixel((150, 150))
        assert px == original_color, (
            f"Centre pixel should be {original_color}, got {px}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# ViT transform pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestViTTransform:
    """Tests for the composed ViT preprocessing pipeline (``_vit_transform``).

    The pipeline is: SquarePad → Resize(224) → ToTensor → ImageNet Normalize.
    """

    def test_vit_transform_output_shape_3_224_224(self):
        """Output tensor has exact shape (3, 224, 224) regardless of input size."""
        img = Image.new("RGB", (400, 150), color=(128, 128, 128))
        tensor = _vit_transform(img)
        assert tensor.shape == (3, 224, 224), (
            f"Expected (3, 224, 224), got {tensor.shape}"
        )

    def test_vit_transform_output_imagenet_normalized_range(self):
        """Output tensor values fall within the expected ImageNet normalised range.

        After ``Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])``,
        the theoretical min is ``(0 - 0.485) / 0.229 ≈ -2.12`` and
        max is ``(1 - 0.406) / 0.225 ≈ 2.64``.  We allow a small tolerance.
        """
        img = Image.new("RGB", (224, 224), color=(0, 128, 255))
        tensor = _vit_transform(img)

        assert tensor.min().item() >= -2.5, (
            f"Min value {tensor.min().item():.3f} below expected range"
        )
        assert tensor.max().item() <= 3.0, (
            f"Max value {tensor.max().item():.3f} above expected range"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Bounding box area fraction
# ═══════════════════════════════════════════════════════════════════════════

class TestBboxAreaFraction:
    """Tests for ``_bbox_area_fraction`` helper."""

    def test_bbox_area_fraction_normal_case(self):
        """Known bbox area / frame area computes correctly.

        bbox = [0, 0, 100, 100] → area = 10000
        frame = 200×200 → area = 40000
        fraction = 10000 / 40000 = 0.25
        """
        fraction = _bbox_area_fraction([0, 0, 100, 100], 200, 200)
        assert abs(fraction - 0.25) < 1e-6

    def test_bbox_area_fraction_zero_frame_returns_zero(self):
        """A zero-area frame returns 0.0 without divide-by-zero."""
        fraction = _bbox_area_fraction([0, 0, 50, 50], 0, 0)
        assert fraction == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Crop extraction strategy
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractCrop:
    """Tests for ``_extract_crop`` — the per-detection crop strategy."""

    def test_extract_crop_disease_class_uses_tight_crop(self):
        """Disease class names (e.g. 'foot_and_mouth') → tight bbox crop."""
        img = Image.new("RGB", (640, 480), color=(0, 0, 0))
        bbox = [50.0, 50.0, 200.0, 200.0]

        crop = _extract_crop(img, bbox, "foot_and_mouth", 640, 480)

        # Tight crop: 200-50 = 150 px wide and tall
        assert crop.size == (150, 150)

    def test_extract_crop_cattle_large_box_uses_full_frame(self):
        """Generic 'cattle' with bbox covering >80% of frame → full image."""
        img = Image.new("RGB", (640, 480), color=(0, 0, 0))
        # bbox covers ~90% of the frame
        bbox = [10.0, 10.0, 630.0, 470.0]

        crop = _extract_crop(img, bbox, "cattle", 640, 480)

        # Full frame returned → same dimensions as original
        assert crop.size == img.size

    def test_extract_crop_cattle_small_box_uses_tight_crop(self):
        """Generic 'cattle' with bbox covering <80% of frame → tight crop."""
        img = Image.new("RGB", (640, 480), color=(0, 0, 0))
        # bbox covers ~25% of the frame
        bbox = [100.0, 100.0, 300.0, 300.0]

        crop = _extract_crop(img, bbox, "cattle", 640, 480)

        # Tight crop: 200×200
        assert crop.size == (200, 200)
