"""
test_image_service.py — Image utility tests
==============================================

Verifies that ``image_service`` correctly opens, crops, and
base64-encodes images, and raises on corrupt or empty inputs.

No model loading or network access required.
"""

import base64
import io

import pytest
from PIL import Image, UnidentifiedImageError

from components.smart_diagnostics import image_service


# ═══════════════════════════════════════════════════════════════════════════
# open_image_from_bytes
# ═══════════════════════════════════════════════════════════════════════════

class TestOpenImageFromBytes:
    """Tests for ``image_service.open_image_from_bytes``."""

    def test_open_image_from_bytes_valid_jpeg_returns_rgb(
        self, dummy_rgb_image_bytes
    ):
        """A valid JPEG byte stream is decoded to an RGB PIL Image."""
        img = image_service.open_image_from_bytes(dummy_rgb_image_bytes)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert img.size == (640, 640)

    def test_open_image_from_bytes_valid_png_returns_rgb(self):
        """A valid PNG byte stream (even with RGBA source) returns RGB."""
        # Create a PNG with alpha channel to verify .convert("RGB") works
        rgba_img = Image.new("RGBA", (200, 200), (0, 255, 0, 128))
        buf = io.BytesIO()
        rgba_img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        img = image_service.open_image_from_bytes(png_bytes)
        assert img.mode == "RGB"
        assert img.size == (200, 200)

    def test_open_image_from_bytes_corrupt_raises_error(
        self, dummy_corrupt_image_bytes
    ):
        """Truncated/corrupt bytes cause PIL to raise an error."""
        with pytest.raises((UnidentifiedImageError, Exception)):
            image_service.open_image_from_bytes(dummy_corrupt_image_bytes)

    def test_open_image_from_bytes_empty_raises_error(
        self, dummy_empty_bytes
    ):
        """Zero-byte input raises an error."""
        with pytest.raises((UnidentifiedImageError, Exception)):
            image_service.open_image_from_bytes(dummy_empty_bytes)


# ═══════════════════════════════════════════════════════════════════════════
# crop_image
# ═══════════════════════════════════════════════════════════════════════════

class TestCropImage:
    """Tests for ``image_service.crop_image``."""

    def test_crop_image_returns_correct_dimensions(self):
        """Cropping with a known bbox returns the expected width × height."""
        img = Image.new("RGB", (500, 500), (0, 0, 0))
        bbox = [50.0, 100.0, 250.0, 400.0]  # w=200, h=300

        cropped = image_service.crop_image(img, bbox)

        assert cropped.size == (200, 300)


# ═══════════════════════════════════════════════════════════════════════════
# encode_image_base64
# ═══════════════════════════════════════════════════════════════════════════

class TestEncodeImageBase64:
    """Tests for ``image_service.encode_image_base64``."""

    def test_encode_image_base64_returns_valid_base64(self):
        """The returned string is valid base64 that decodes to JPEG bytes."""
        img = Image.new("RGB", (64, 64), (128, 128, 128))

        b64_str = image_service.encode_image_base64(img)

        # Should be a non-empty string
        assert isinstance(b64_str, str)
        assert len(b64_str) > 0

        # Should decode without error
        decoded = base64.b64decode(b64_str)
        assert len(decoded) > 0

        # Decoded bytes should be a valid JPEG
        result_img = Image.open(io.BytesIO(decoded))
        assert result_img.format == "JPEG"
