from abc import ABC, abstractmethod
from typing import Dict
from PIL.Image import Image


class ClassifierInterface(ABC):
    @abstractmethod
    def predict(self, image: Image) -> Dict:
        """Return a dict with keys: name (display string), confidence (float %), all_probabilities (dict display_name->float %)."""

