from abc import ABC, abstractmethod
from typing import Dict
from PIL.Image import Image


class ClassifierInterface(ABC):
    @abstractmethod
    def predict(self, image: Image) -> Dict:
        """Return a dict with keys: name (display string), confidence (float %), all_probabilities (dict display_name->float %)."""

    def predict_with_attention(self, image: Image) -> Dict:
        """Return classification result along with attention rollout metrics."""
        res = self.predict(image)
        res.setdefault("attention_coverage_pct", 0.0)
        res.setdefault("attention_cluster_count", 0)
        res.setdefault("top2_margin", 0.0)
        res.setdefault("attention_map", None)
        return res

