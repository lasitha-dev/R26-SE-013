from typing import List, Dict
from PIL.Image import Image

from ..interfaces.detector import DetectorInterface


class YOLODetector(DetectorInterface):
    """Lightweight wrapper around ultralytics.YOLO.

    Model loading is lazy to avoid importing heavy packages at module import time.
    """

    def __init__(self, model_path: str, conf_threshold: float = 0.25):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self._model = None
        self._names = {}

    def _ensure_loaded(self):
        if self._model is None:
            try:
                from ultralytics import YOLO
            except Exception as e:
                raise RuntimeError("ultralytics is required for YOLODetector") from e
            self._model = YOLO(self.model_path)
            try:
                self._names = getattr(self._model, "names", {}) or {}
            except Exception:
                self._names = {}

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
