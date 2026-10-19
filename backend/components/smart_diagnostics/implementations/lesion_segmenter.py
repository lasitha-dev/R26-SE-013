"""Single-channel semantic lesion-mask adapter; clinical interpretation is separate."""
from pathlib import Path
import hashlib
import json
import logging
import math
import numpy as np
from PIL import Image
from ..model_errors import ModelUnavailable, InvalidModelOutput

logger = logging.getLogger("smart_diagnostics.segmenter")


def threshold_mask(probabilities, threshold, min_region_fraction):
    """Shared crop_mask_v1 postprocessing for runtime and offline validation."""
    if not 0 < threshold < 1 or not 0 <= min_region_fraction < 1:
        raise ValueError("Invalid mask threshold or region-filter fraction.")
    probabilities = np.asarray(probabilities)
    if probabilities.ndim != 2 or not probabilities.size or not np.isfinite(probabilities).all():
        raise InvalidModelOutput("Expected a finite two-dimensional probability map.")
    if np.any(probabilities < 0) or np.any(probabilities > 1):
        raise InvalidModelOutput("Mask values must be probabilities in [0,1].")
    from scipy.ndimage import label
    # Convert pixel probabilities into a mask, then group touching pixels using
    # eight-neighbor connectivity and remove regions below the size policy.
    binary = probabilities >= threshold
    labels, _ = label(binary, structure=np.ones((3, 3), dtype=np.uint8))
    sizes = np.bincount(labels.ravel())
    keep = sizes >= max(1, math.ceil(binary.size * min_region_fraction))
    # Label zero is background and must never count as a lesion region.
    keep[0] = False
    return keep[labels], int(np.count_nonzero(keep))


class LesionSegmenter:
    def __init__(self, model_path: str, image_size: int = 224, threshold: float = 0.5,
                 min_region_fraction: float = 15 / (224 * 224), manifest_path: str | None = None):
        if not 0 < threshold < 1 or not 0 <= min_region_fraction < 1:
            raise ValueError("Invalid mask threshold or region-filter fraction.")
        self.model_path = model_path
        self.image_size = image_size
        self.threshold = threshold
        self.min_region_fraction = min_region_fraction
        self.manifest_path = manifest_path
        self.model = None
        self.load_state = "not_loaded"
        self._device = None

    @property
    def is_loaded(self):
        return self.model is not None

    def _ensure_loaded(self):
        if self.model is not None:
            return
        if not Path(self.model_path).is_file():
            self.load_state = "unavailable"
            raise ModelUnavailable("The lesion-segmentation checkpoint is unavailable.")
        try:
            if self.manifest_path:
                manifest = json.loads(Path(self.manifest_path).read_text(encoding="utf-8"))
                with open(self.model_path, "rb") as checkpoint:
                    digest = hashlib.file_digest(checkpoint, "sha256").hexdigest()
                if digest != manifest["artifact"]["sha256"]:
                    raise ModelUnavailable("The segmenter checkpoint does not match its model manifest.")
            import tensorflow as tf
            candidate = tf.keras.models.load_model(self.model_path, compile=False)
            if tuple(candidate.input_shape) != (None, self.image_size, self.image_size, 3):
                raise InvalidModelOutput("Unexpected segmenter input shape.")
            self.model = candidate
            if candidate.weights:
                self._device = getattr(getattr(candidate.weights[0], "value", candidate.weights[0]), "device", None)
            self.load_state = "loaded"
        except Exception as exc:
            self.load_state = "unavailable"
            logger.error("Segmenter load failed: %s", exc)
            raise ModelUnavailable("The lesion-segmentation checkpoint or manifest could not be loaded.") from exc

    def _select_mask(self, prediction):
        if isinstance(prediction, dict):
            keys = [name for name in ("sigmoid", "mask_output") if name in prediction]
            if len(keys) != 1:
                raise InvalidModelOutput("A named binary mask output is required.")
            prediction = prediction[keys[0]]
        elif isinstance(prediction, (list, tuple)):
            names = list(getattr(self.model, "output_names", []))
            if len(names) != len(prediction):
                raise InvalidModelOutput("Outputs do not match the model's named output contract.")
            return self._select_mask(dict(zip(names, prediction)))
        mask = np.asarray(prediction)
        if mask.shape != (1, self.image_size, self.image_size, 1):
            raise InvalidModelOutput("Expected a single (1,H,W,1) binary-probability mask.")
        if not np.isfinite(mask).all() or np.any(mask < 0) or np.any(mask > 1):
            raise InvalidModelOutput("Mask values must be finite probabilities in [0,1].")
        return mask[0, :, :, 0].astype(np.float32)

    def predict_probabilities(self, image: Image.Image):
        """Unthresholded float probabilities at crop resolution; raises on failure."""
        self._ensure_loaded()
        rgb = image.convert("RGB")
        tensor = np.asarray(rgb.resize((self.image_size, self.image_size)), dtype=np.float32)[None] / 255.0
        probabilities = self._select_mask(self.model.predict(tensor, verbose=0))
        # Restore crop resolution before measuring coverage and drawing an overlay.
        return np.asarray(Image.fromarray(probabilities).resize(rgb.size, Image.Resampling.BILINEAR))

    def predict_with_metrics(self, image: Image.Image):
        empty = dict(lesion_coverage_pct=None, cluster_count=None, lesion_pixels=None, mean_intensity=None,
                     threshold=self.threshold, min_region_fraction=self.min_region_fraction,
                     connectivity=8, denominator="analyzed_crop_pixels", policy_version="crop_mask_v1",
                     contract_status="training_lineage_unverified", error_code=None)
        try:
            self._ensure_loaded()
        except ModelUnavailable:
            return None, dict(empty, status="unavailable", error_code="segmenter_unavailable")
        try:
            # Preserve deployed RGB /255; training lineage remains unverified.
            rgb = image.convert("RGB")
            resized = self.predict_probabilities(rgb)
            binary, cluster_count = threshold_mask(resized, self.threshold, self.min_region_fraction)
            # Coverage = retained foreground pixels / all analyzed crop pixels.
            # Connected regions are image regions, not a count of clinical nodules.
            pixels = int(binary.sum())
            overlay = np.zeros((rgb.height, rgb.width, 4), dtype=np.uint8)
            overlay[binary] = [255, 0, 0, 128]
            annotated = Image.alpha_composite(rgb.convert("RGBA"), Image.fromarray(overlay)).convert("RGB")
            return annotated, dict(empty, status="completed_with_regions" if pixels else "completed_no_regions",
                lesion_coverage_pct=round(pixels / binary.size * 100, 4), cluster_count=cluster_count,
                lesion_pixels=pixels, mean_intensity=float(resized[binary].mean()) if pixels else 0.0,
                analyzed_pixels=binary.size)
        except Exception as exc:
            logger.error("Segmenter inference failed: %s", exc)
            return None, dict(empty, status="failed", error_code="invalid_mask_or_inference_failed")

    def predict(self, image):
        annotated, _ = self.predict_with_metrics(image)
        return annotated
