from abc import ABC, abstractmethod
from typing import List, Dict
from PIL.Image import Image


class DetectorInterface(ABC):
    @abstractmethod
    def predict(self, image: Image) -> List[Dict]:
        """Return a list of detections, where each detection is a dict with keys: bbox, confidence, class_name."""

