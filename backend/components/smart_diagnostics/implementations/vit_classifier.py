import time
import logging
from typing import Dict, List
from PIL.Image import Image

from ..interfaces.classifier import ClassifierInterface

logger = logging.getLogger("smart_diagnostics.vit")


class ViTClassifier(ClassifierInterface):
    """Wrapper around a torchvision ViT model. Lazy-loads torch and weights.

    Returns probabilities in percentage and uses provided class/display names.
    """

    def __init__(self, model_path: str, image_size: int = 224, class_names: List[str] = None, display_names: Dict[str, str] = None):
        self.model_path = model_path
        self.image_size = image_size
        self.class_names = class_names or []
        self.display_names = display_names or {}
        self._model = None
        self._transform = None
        self._device = None

    @property
    def is_loaded(self) -> bool:
        """Return True if the underlying ViT model has been loaded into memory."""
        return self._model is not None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        logger.info("Loading ViT classifier from '%s' ...", self.model_path)
        t0 = time.perf_counter()
        try:
            import torch
            from torchvision import models, transforms
        except Exception as e:
            logger.error("Failed to import torch/torchvision: %s", e)
            raise RuntimeError("torch and torchvision are required for ViTClassifier") from e

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._device = device
        logger.info("ViT device: %s", device)

        vit = models.vit_b_16(weights=None)
        # Adapt classifier head
        if hasattr(vit, "heads") and hasattr(vit.heads, "head"):
            in_features = vit.heads.head.in_features
            vit.heads.head = torch.nn.Linear(in_features, max(1, len(self.class_names)))
        else:
            # fallback
            try:
                in_features = vit.classifier.in_features
                vit.classifier = torch.nn.Linear(in_features, max(1, len(self.class_names)))
            except Exception:
                pass

        # Load weights if possible
        try:
            checkpoint = torch.load(self.model_path, map_location=device)
            state_dict = checkpoint
            if isinstance(checkpoint, dict):
                for key in ("model_state_dict", "state_dict", "model"):
                    if key in checkpoint:
                        state_dict = checkpoint[key]
                        break
            vit.load_state_dict(state_dict)
            logger.info("ViT weights loaded successfully from checkpoint.")
        except Exception as e:
            # Log a warning instead of silently ignoring — the model will run with random weights!
            logger.warning(
                "Failed to load ViT weights from '%s': %s  — model will use RANDOM weights!",
                self.model_path,
                e,
            )

        vit.to(device)
        vit.eval()
        self._model = vit
        self._transform = transforms.Compose([
            transforms.Resize((self.image_size, self.image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        elapsed = time.perf_counter() - t0
        logger.info(
            "ViT classifier loaded successfully in %.2fs  (classes: %s, device: %s)",
            elapsed,
            self.class_names,
            device,
        )

    def predict(self, image: Image) -> Dict:
        self._ensure_loaded()
        import torch

        tensor = self._transform(image).unsqueeze(0).to(self._device)
        with torch.no_grad():
            outputs = self._model(tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)[0]
            top_conf, top_idx = torch.max(probabilities, dim=0)

        top_idx = int(top_idx.item())
        top_conf = float(top_conf.item())

        # Build probabilities mapping (display names)
        all_probs = {}
        for i in range(len(self.class_names)):
            key = self.class_names[i]
            display = self.display_names.get(key, key) if hasattr(self, 'display_names') else key
            all_probs[display] = round(float(probabilities[i].item()) * 100, 2)

        top_key = self.class_names[top_idx] if top_idx < len(self.class_names) else f"Class_{top_idx}"
        top_display = self.display_names.get(top_key, top_key) if hasattr(self, 'display_names') else top_key

        return {
            "name": top_display,
            "confidence": round(top_conf * 100, 2),
            "all_probabilities": all_probs,
        }
