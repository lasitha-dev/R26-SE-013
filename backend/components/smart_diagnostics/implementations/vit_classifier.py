import time
import logging
from typing import Dict, List
from PIL.Image import Image

from ..interfaces.classifier import ClassifierInterface
from ..model_errors import ModelUnavailable, InvalidModelOutput

logger = logging.getLogger("smart_diagnostics.vit")


class ViTClassifier(ClassifierInterface):
    """Wrapper around a torchvision ViT model. Lazy-loads torch and weights.

    Returns probabilities in percentage and uses provided class/display names.
    """

    def __init__(self, model_path: str, image_size: int = 224, class_names: List[str] = None, display_names: Dict[str, str] = None):
        self.model_path = model_path
        self.image_size = image_size
        self.class_names = class_names if class_names is not None else [
            "cattle",
            "foot_and_mouth",
            "lumpy_skin",
            "mastitis",
        ]
        self.display_names = display_names if display_names is not None else {
            "cattle": "Cattle (Healthy)",
            "foot_and_mouth": "Foot and Mouth Disease",
            "lumpy_skin": "Lumpy Skin Disease",
            "mastitis": "Mastitis",
        }
        self._model = None
        self._transform = None
        self._device = None
        self.load_state = "not_loaded"

    @property
    def is_loaded(self) -> bool:
        """Return True if the underlying ViT model has been loaded into memory."""
        return self._model is not None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        from pathlib import Path
        if not Path(self.model_path).is_file():
            self.load_state = "unavailable"
            raise ModelUnavailable("The trained disease classifier checkpoint is unavailable.")
        self.load_state = "loading"
        logger.info("Loading ViT classifier from '%s' ...", self.model_path)
        t0 = time.perf_counter()
        try:
            import torch
            from torchvision import models, transforms
        except Exception as e:
            logger.error("Failed to import torch/torchvision: %s", e)
            self.load_state = "unavailable"
            raise ModelUnavailable("torch and torchvision are required for the trained classifier.") from e

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
            self.load_state = "unavailable"
            logger.error("Trained ViT checkpoint could not be loaded: %s", e)
            raise ModelUnavailable("The trained disease classifier checkpoint is incompatible or unreadable.") from e

        vit.to(device)
        # Evaluation mode disables training behavior such as dropout during inference.
        vit.eval()
        self._model = vit
        self.load_state = "loaded"
        # Resize and normalize crops with the deployed model's preprocessing.
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
        # No gradients are needed for prediction; softmax turns logits into
        # class probabilities before converting them to API percentages.
        with torch.no_grad():
            outputs = self._model(tensor)
            if outputs.shape != (1, len(self.class_names)) or not torch.isfinite(outputs).all():
                raise InvalidModelOutput("The disease classifier returned invalid logits.")
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

    def predict_with_attention(self, image: Image) -> Dict:
        """Run classification and extract attention rollout metrics across ViT layers."""
        self._ensure_loaded()
        import torch
        from .vit_attention import extract_attention_rollout

        tensor = self._transform(image).unsqueeze(0).to(self._device)
        with torch.no_grad():
            outputs = self._model(tensor)
            if outputs.shape != (1, len(self.class_names)) or not torch.isfinite(outputs).all():
                raise InvalidModelOutput("The disease classifier returned invalid logits.")
            probabilities = torch.nn.functional.softmax(outputs, dim=1)[0]
            top_conf, top_idx = torch.max(probabilities, dim=0)

            # The gap between the two leading classes describes ambiguity:
            # a small margin means the classifier has similar competing predictions.
            # Top-2 margin
            sorted_probs, _ = torch.sort(probabilities, descending=True)
            top1_val = float(sorted_probs[0].item())
            top2_val = float(sorted_probs[1].item()) if sorted_probs.size(0) > 1 else 0.0
            top2_margin = round((top1_val - top2_val) * 100.0, 2)

        top_idx = int(top_idx.item())
        top_conf = float(top_conf.item())

        all_probs = {}
        for i in range(len(self.class_names)):
            key = self.class_names[i]
            display = self.display_names.get(key, key) if hasattr(self, 'display_names') else key
            all_probs[display] = round(float(probabilities[i].item()) * 100, 2)

        top_key = self.class_names[top_idx] if top_idx < len(self.class_names) else f"Class_{top_idx}"
        top_display = self.display_names.get(top_key, top_key) if hasattr(self, 'display_names') else top_key

        # Attention shows model focus, not a lesion mask or a clinical severity grade.
        # Extract attention rollout
        try:
            attn_data = extract_attention_rollout(
                self._model,
                tensor,
                image_size=image.size,
                percentile_threshold=75.0,
                original_image=image,
            )
            coverage_pct = attn_data["attention_coverage_pct"]
            cluster_count = attn_data["attention_cluster_count"]
            attn_map = attn_data["attention_map"]
            overlay_img = attn_data.get("attention_overlay_image")
            attention_status = "completed"
        except Exception as e:
            logger.warning("Failed to extract attention rollout: %s", e)
            coverage_pct = 0.0
            cluster_count = 0
            attn_map = None
            overlay_img = None
            attention_status = "failed"

        return {
            "name": top_display,
            "confidence": round(top_conf * 100, 2),
            "all_probabilities": all_probs,
            "top2_margin": top2_margin,
            "attention_coverage_pct": coverage_pct,
            "attention_cluster_count": cluster_count,
            "attention_map": attn_map,
            "attention_overlay_image": overlay_img,
            "attention_status": attention_status,
        }
