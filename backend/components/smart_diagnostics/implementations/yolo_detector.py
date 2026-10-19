import time
import logging
from typing import List, Dict
from PIL.Image import Image

from ..interfaces.detector import DetectorInterface
from ..model_errors import ModelUnavailable

logger = logging.getLogger("smart_diagnostics.yolo")


class YOLODetector(DetectorInterface):
    """Lightweight wrapper around ultralytics.YOLO.

    Model loading is lazy to avoid importing heavy packages at module import time.
    """

    def __init__(self, model_path: str, conf_threshold: float = 0.25):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self._model = None
        self._names = {}

    @property
    def is_loaded(self) -> bool:
        """Return True if the underlying YOLO model has been loaded into memory."""
        return self._model is not None

    def _resolve_model_path(self) -> str:
        from pathlib import Path
        path = Path(self.model_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[3] / path
        if not path.is_file():
            raise ModelUnavailable("The configured cattle detector checkpoint is unavailable.")
        with path.open("rb") as checkpoint:
            if checkpoint.read(100).startswith(b"version https://git-lfs.github.com"):
                raise ModelUnavailable("The cattle detector checkpoint is an unmaterialized LFS pointer.")
        return str(path)

    def _ensure_loaded(self):
        # Load once on first use, then reuse the checkpoint across requests.
        if self._model is None:
            resolved_path = self._resolve_model_path()
            logger.info("Loading YOLO model from '%s' ...", resolved_path)
            t0 = time.perf_counter()
            try:
                from ultralytics import YOLO
            except Exception as e:
                logger.error("Failed to import ultralytics: %s", e)
                raise RuntimeError("ultralytics is required for YOLODetector") from e
            self._model = YOLO(resolved_path)
            try:
                self._names = getattr(self._model, "names", {}) or {}
            except Exception:
                self._names = {}
            elapsed = time.perf_counter() - t0
            logger.info(
                "YOLO model loaded successfully in %.2fs  (classes: %s)",
                elapsed,
                list(self._names.values()) if self._names else "unknown",
            )

    def predict(self, image: Image) -> List[Dict]:
        # YOLO localizes supported regions. Disease classification is handled
        # separately by ViT after the route selects and crops a region.
        self._ensure_loaded()
        results = self._model.predict(source=image, conf=self.conf_threshold, verbose=False)
        detections: List[Dict] = []
        for result in results:
            boxes = getattr(result, "boxes", [])
            for box in boxes:
                # Convert library tensors into plain values for the API contract.
                xyxy = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = self._names.get(cls_id, f"class_{cls_id}")
                detections.append({
                    "bbox": xyxy,
                    "confidence": round(conf, 4),
                    "class_name": cls_name,
                })
        return detections
