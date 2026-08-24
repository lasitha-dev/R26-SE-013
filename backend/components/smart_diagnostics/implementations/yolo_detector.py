import time
import logging
from typing import List, Dict
from PIL.Image import Image

from ..interfaces.detector import DetectorInterface

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
        import os
        candidates = [
            self.model_path,
            os.path.join(os.path.dirname(__file__), "..", "models", "yolo_smart_diag_best.pt"),
            os.path.join(os.path.dirname(__file__), "..", "models", "best.pt"),
            r"C:\Users\lasit\runs\detect\yolo_smart_diag\cattle_gate_v1\weights\best.pt",
            os.path.join(os.path.dirname(__file__), "..", "..", "health_anomaly", "best.pt"),
        ]
        for path in candidates:
            if path and os.path.exists(path):
                # Verify not a Git LFS pointer file (< 1000 bytes)
                try:
                    if os.path.getsize(path) > 10000:
                        return path
                except Exception:
                    pass
        return self.model_path

    def _ensure_loaded(self):
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
        self._ensure_loaded()
        results = self._model.predict(source=image, conf=self.conf_threshold, verbose=False)
        detections: List[Dict] = []
        for result in results:
            boxes = getattr(result, "boxes", [])
            for box in boxes:
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
