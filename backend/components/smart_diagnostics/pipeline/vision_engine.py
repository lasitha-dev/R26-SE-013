"""
Vision Engine — Tier 1 (YOLO) + Tier 2 (ViT)
================================================
Runs the two-stage computer-vision pipeline:

1. **YOLOv8s** validates cattle image integrity and produces bounding boxes
   with class labels (``cattle``, ``foot_and_mouth``, ``lumpy_skin``, ``mastitis``).
2. **ViT-B/16** classifies each ROI crop (after aspect-ratio-preserving
   ``SquarePad``) into the same 4 classes with softmax confidence scores.

The function :func:`run_vision_pipeline` is the single public entry point.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torchvision import models, transforms

from . import config as cfg

logger = logging.getLogger("smart_diagnostics.pipeline.vision")

# ---------------------------------------------------------------------------
# Prevent OpenCV multithreading conflicts on Windows.
# Some Ultralytics internals import cv2, so we set this early.
# ---------------------------------------------------------------------------
try:
    import cv2
    cv2.setNumThreads(0)
except ImportError:
    pass  # cv2 not installed — fine, YOLO can work without it in some setups


# ═══════════════════════════════════════════════════════════════════════════
# SquarePad — Aspect-ratio preserving transform
# ═══════════════════════════════════════════════════════════════════════════

class SquarePad:
    """Pad a PIL Image to a square canvas with a neutral fill colour.

    The original image is centred on a ``(max_dim × max_dim)`` canvas so that
    no geometric distortion occurs — this is critical for preserving lesion
    morphology in disease classification.

    Parameters
    ----------
    fill : tuple[int, int, int]
        RGB fill colour for the padding region.  Default matches the
        Ultralytics letterbox grey ``(114, 114, 114)``.
    """

    def __init__(self, fill: Tuple[int, int, int] = cfg.SQUARE_PAD_FILL) -> None:
        self.fill = fill

    def __call__(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        max_dim = max(w, h)

        # Create the padded canvas.
        padded = Image.new("RGB", (max_dim, max_dim), self.fill)

        # Centre-paste the original image.
        paste_x = (max_dim - w) // 2
        paste_y = (max_dim - h) // 2
        padded.paste(img, (paste_x, paste_y))

        return padded

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(fill={self.fill})"


# ═══════════════════════════════════════════════════════════════════════════
# ViT model loading (cached singleton)
# ═══════════════════════════════════════════════════════════════════════════

_vit_model: Optional[nn.Module] = None
_vit_device: Optional[torch.device] = None


def _get_vit_model() -> Tuple[nn.Module, torch.device]:
    """Lazily load the fine-tuned ViT-B/16 model.

    The model head is adapted from ImageNet-1k (1 000 classes) to
    ``len(cfg.VIT_CLASSES)`` classes.  Weights are loaded from the
    checkpoint at ``cfg.VIT_MODEL_PATH``.

    Returns
    -------
    model : nn.Module
        The ViT model in eval mode.
    device : torch.device
        The device the model was placed on (CUDA if available).
    """
    global _vit_model, _vit_device

    if _vit_model is not None:
        return _vit_model, _vit_device  # type: ignore[return-value]

    logger.info("Loading ViT-B/16 classifier from '%s' ...", cfg.VIT_MODEL_PATH)
    t0 = time.perf_counter()

    if not os.path.isfile(cfg.VIT_MODEL_PATH):
        raise FileNotFoundError(
            f"ViT checkpoint not found at: {cfg.VIT_MODEL_PATH}"
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Build architecture with correct head size.
    num_classes = len(cfg.VIT_CLASSES)
    vit = models.vit_b_16(weights=None)

    # Adapt the classifier head.
    if hasattr(vit, "heads") and hasattr(vit.heads, "head"):
        in_features = vit.heads.head.in_features
        vit.heads.head = nn.Linear(in_features, num_classes)
    else:
        # Fallback for different torchvision versions.
        in_features = vit.classifier.in_features  # type: ignore[attr-defined]
        vit.classifier = nn.Linear(in_features, num_classes)  # type: ignore[attr-defined]

    # Load trained weights from checkpoint.
    checkpoint = torch.load(cfg.VIT_MODEL_PATH, map_location=device, weights_only=False)
    state_dict = checkpoint
    if isinstance(checkpoint, dict):
        for key in ("model_state_dict", "state_dict", "model"):
            if key in checkpoint:
                state_dict = checkpoint[key]
                break
    vit.load_state_dict(state_dict)

    vit.to(device).eval()
    _vit_model = vit
    _vit_device = device

    elapsed = time.perf_counter() - t0
    logger.info(
        "ViT-B/16 loaded in %.2fs  (classes=%s, device=%s)",
        elapsed, cfg.VIT_CLASSES, device,
    )
    return vit, device


# ═══════════════════════════════════════════════════════════════════════════
# ViT transform pipeline
# ═══════════════════════════════════════════════════════════════════════════

_vit_transform = transforms.Compose([
    SquarePad(fill=cfg.SQUARE_PAD_FILL),
    transforms.Resize((cfg.VIT_IMAGE_SIZE, cfg.VIT_IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],   # ImageNet channel means
        std=[0.229, 0.224, 0.225],     # ImageNet channel stds
    ),
])


# ═══════════════════════════════════════════════════════════════════════════
# YOLO model loading (cached singleton)
# ═══════════════════════════════════════════════════════════════════════════

_yolo_model = None


def _get_yolo_model():
    """Lazily load the YOLOv8s model from ``cfg.YOLO_MODEL_PATH``."""
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model

    logger.info("Loading YOLOv8s model from '%s' ...", cfg.YOLO_MODEL_PATH)
    t0 = time.perf_counter()

    if not os.path.isfile(cfg.YOLO_MODEL_PATH):
        raise FileNotFoundError(
            f"YOLO checkpoint not found at: {cfg.YOLO_MODEL_PATH}"
        )

    from ultralytics import YOLO
    _yolo_model = YOLO(cfg.YOLO_MODEL_PATH)

    elapsed = time.perf_counter() - t0
    names = getattr(_yolo_model, "names", {})
    logger.info(
        "YOLOv8s loaded in %.2fs  (classes=%s)",
        elapsed, list(names.values()) if names else "unknown",
    )
    return _yolo_model


# ═══════════════════════════════════════════════════════════════════════════
# Crop strategy helpers
# ═══════════════════════════════════════════════════════════════════════════

def _bbox_area_fraction(bbox: List[float], img_w: int, img_h: int) -> float:
    """Compute what fraction of the frame area is covered by a bounding box."""
    x1, y1, x2, y2 = bbox
    box_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    frame_area = img_w * img_h
    return box_area / frame_area if frame_area > 0 else 0.0


def _extract_crop(
    img: Image.Image,
    bbox: List[float],
    cls_name: str,
    img_w: int,
    img_h: int,
) -> Image.Image:
    """Decide whether to use a tight crop or the full frame.

    Rules
    -----
    * If YOLO detected a specific disease class, always use a tight crop of
      the bounding box — the lesion region is the focus.
    * If the class is generic ``cattle`` and the bbox covers >80 % of the
      frame, return the full original image to preserve surrounding context.
    * Otherwise, use a tight crop.
    """
    if cls_name in cfg.YOLO_DISEASE_CLASSES:
        # Disease detection → tight crop.
        x1, y1, x2, y2 = [int(c) for c in bbox]
        return img.crop((x1, y1, x2, y2))

    # Generic "cattle" detection.
    area_frac = _bbox_area_fraction(bbox, img_w, img_h)
    if area_frac > cfg.CATTLE_FULL_FRAME_THRESHOLD:
        # Box covers >80 % of frame — use full image for context.
        return img.copy()

    x1, y1, x2, y2 = [int(c) for c in bbox]
    return img.crop((x1, y1, x2, y2))


# ═══════════════════════════════════════════════════════════════════════════
# Tier 2 — ViT classification of a single crop
# ═══════════════════════════════════════════════════════════════════════════

def _classify_crop(crop: Image.Image, extract_attention: bool = True) -> Dict[str, Any]:
    """Run ViT-B/16 inference on a single ROI crop, with attention rollout metrics.

    Returns
    -------
    dict
        ``predicted_class``        — the argmax class name (internal key).
        ``predicted_display``      — human-readable display name.
        ``confidence_pct``          — top-class softmax probability in [0, 100].
        ``probabilities``           — dict mapping each display name → probability %.
        ``top2_margin``             — difference between top-1 and top-2 probabilities (%).
        ``attention_coverage_pct``  — ViT attention rollout coverage %.
        ``attention_cluster_count`` — ViT attention focal clusters count.
    """
    model, device = _get_vit_model()

    tensor = _vit_transform(crop).unsqueeze(0).to(device)  # (1, 3, 224, 224)

    with torch.no_grad():
        logits = model(tensor)                              # (1, num_classes)
        probs = F.softmax(logits, dim=1)[0]                 # (num_classes,)
        top_conf, top_idx = torch.max(probs, dim=0)

        # Top-2 margin
        sorted_probs, _ = torch.sort(probs, descending=True)
        top1_val = float(sorted_probs[0].item())
        top2_val = float(sorted_probs[1].item()) if sorted_probs.size(0) > 1 else 0.0
        top2_margin = round((top1_val - top2_val) * 100.0, 2)

    top_idx_int = int(top_idx.item())
    top_conf_pct = round(float(top_conf.item()) * 100, 2)

    predicted_class = (
        cfg.VIT_CLASSES[top_idx_int]
        if top_idx_int < len(cfg.VIT_CLASSES)
        else f"class_{top_idx_int}"
    )
    predicted_display = cfg.VIT_DISPLAY_NAMES.get(predicted_class, predicted_class)

    probabilities: Dict[str, float] = {}
    for i, cls_key in enumerate(cfg.VIT_CLASSES):
        display = cfg.VIT_DISPLAY_NAMES.get(cls_key, cls_key)
        probabilities[display] = round(float(probs[i].item()) * 100, 2)

    # Attention rollout extraction
    coverage_pct = 0.0
    cluster_count = 0
    if extract_attention:
        try:
            from components.smart_diagnostics.implementations.vit_attention import extract_attention_rollout
            attn_data = extract_attention_rollout(
                model,
                tensor,
                image_size=crop.size,
                percentile_threshold=75.0,
                original_image=crop,
            )
            coverage_pct = attn_data["attention_coverage_pct"]
            cluster_count = attn_data["attention_cluster_count"]
        except Exception as exc:
            logger.warning("Could not extract attention rollout in vision engine: %s", exc)

    return {
        "predicted_class": predicted_class,
        "predicted_display": predicted_display,
        "confidence_pct": top_conf_pct,
        "probabilities": probabilities,
        "top2_margin": top2_margin,
        "attention_coverage_pct": coverage_pct,
        "attention_cluster_count": cluster_count,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Public API — run_vision_pipeline
# ═══════════════════════════════════════════════════════════════════════════

def run_vision_pipeline(image_path: str) -> Dict[str, Any]:
    """Execute the full Tier 1 + Tier 2 vision pipeline.

    Parameters
    ----------
    image_path : str
        Absolute or relative path to a cattle image file.

    Returns
    -------
    dict
        On rejection (no detections):
            ``{"status": "REJECTED", "reason": "..."}``

        On success:
            ``{"status": "PROCESSED", "image_path": ..., "image_size": {...},
               "detections": [...]}``
        Each detection dict contains bounding box coords, YOLO class info,
        ViT classification results, attention rollout metrics, and probability distribution.
    """
    # ------------------------------------------------------------------
    # Validate input image
    # ------------------------------------------------------------------
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    img = Image.open(image_path).convert("RGB")
    img_w, img_h = img.size
    logger.info("Opened image: %s  (%d × %d)", image_path, img_w, img_h)

    # ------------------------------------------------------------------
    # Tier 1 — YOLO inference
    # ------------------------------------------------------------------
    logger.info("═══ Tier 1: YOLOv8s — Input Gate & Localizer ═══")
    yolo = _get_yolo_model()
    results = yolo.predict(source=img, conf=cfg.YOLO_CONF_THRESHOLD, verbose=False)

    # Collect raw boxes.
    raw_detections: List[Dict[str, Any]] = []
    for result in results:
        boxes = getattr(result, "boxes", [])
        names = getattr(yolo, "names", {})
        for box in boxes:
            xyxy = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            cls_name = names.get(cls_id, f"class_{cls_id}")
            raw_detections.append({
                "bbox": xyxy,
                "yolo_confidence": round(conf, 4),
                "yolo_class": cls_name,
            })

    if not raw_detections:
        logger.warning("YOLO detected no valid objects — image rejected.")
        return {
            "status": "REJECTED",
            "reason": "No valid cattle or lesions detected.",
            "image_path": image_path,
            "image_size": {"width": img_w, "height": img_h},
        }

    logger.info("YOLO detected %d object(s).", len(raw_detections))

    # ------------------------------------------------------------------
    # Tier 2 — ViT classification per crop
    # ------------------------------------------------------------------
    logger.info("═══ Tier 2: ViT-B/16 — Fine-Grained Disease Classifier ═══")
    detections: List[Dict[str, Any]] = []

    for det in raw_detections:
        bbox = det["bbox"]
        cls_name = det["yolo_class"]

        # Decide crop strategy.
        crop = _extract_crop(img, bbox, cls_name, img_w, img_h)
        area_pct = round(_bbox_area_fraction(bbox, img_w, img_h) * 100, 2)

        # ViT classification with attention rollout.
        vit_result = _classify_crop(crop)

        # Compute bbox dimensions (pixels).
        x1, y1, x2, y2 = bbox
        bbox_w = round(x2 - x1, 1)
        bbox_h = round(y2 - y1, 1)

        detections.append({
            "bbox": [round(c, 1) for c in bbox],
            "bbox_width_px": bbox_w,
            "bbox_height_px": bbox_h,
            "bbox_area_pct": area_pct,
            "yolo_class": cls_name,
            "yolo_confidence": det["yolo_confidence"],
            "vit_predicted_class": vit_result["predicted_class"],
            "vit_predicted_display": vit_result["predicted_display"],
            "vit_confidence_pct": vit_result["confidence_pct"],
            "vit_probabilities": vit_result["probabilities"],
            "top2_margin": vit_result["top2_margin"],
            "attention_coverage_pct": vit_result["attention_coverage_pct"],
            "attention_cluster_count": vit_result["attention_cluster_count"],
        })

    # ------------------------------------------------------------------
    # Free VRAM so the local LLM in Tier 3 has headroom
    # ------------------------------------------------------------------
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.info("torch.cuda.empty_cache() — freed VRAM for LLM.")

    logger.info("Vision pipeline complete: %d detection(s) classified.", len(detections))

    return {
        "status": "PROCESSED",
        "image_path": image_path,
        "image_size": {"width": img_w, "height": img_h},
        "detections": detections,
    }
