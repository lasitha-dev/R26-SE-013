"""
Pipeline Configuration & Constants
====================================
Centralised constants for the 3-tier Veterinary AI Diagnostic Pipeline.

* Tier 1 — YOLOv8s  (Input Gate & Localizer)
* Tier 2 — ViT-B/16 (Fine-Grained Disease Classifier)
* Tier 3 — Qwen 2.5 via LM Studio (Clinical Reasoning Engine)
"""

from typing import Dict, List

# ---------------------------------------------------------------------------
# Tier 1 – YOLO Detector
# ---------------------------------------------------------------------------
YOLO_MODEL_PATH: str = r"C:\Users\lasit\runs\detect\yolo_smart_diag\cattle_gate_v1\weights\best.pt"
YOLO_CONF_THRESHOLD: float = 0.25

# ---------------------------------------------------------------------------
# Tier 2 – ViT Classifier
# ---------------------------------------------------------------------------
VIT_MODEL_PATH: str = r"C:\Users\lasit\best_vit_model.pth"
VIT_IMAGE_SIZE: int = 224
VIT_CLASSES: List[str] = ["cattle", "foot_and_mouth", "lumpy_skin", "mastitis"]
VIT_DISPLAY_NAMES: Dict[str, str] = {
    "cattle": "Cattle (Healthy)",
    "foot_and_mouth": "Foot and Mouth Disease",
    "lumpy_skin": "Lumpy Skin Disease",
    "mastitis": "Mastitis",
}

# Neutral grey fill for aspect-ratio-preserving SquarePad transform.
# Matches the Ultralytics letterbox default so crops look consistent.
SQUARE_PAD_FILL: tuple = (114, 114, 114)

# Disease class names that YOLO may emit directly (i.e. not generic "cattle").
YOLO_DISEASE_CLASSES: List[str] = ["foot_and_mouth", "lumpy_skin", "mastitis"]

# If a generic "cattle" box covers more than this fraction of the frame,
# use the full original image instead of a tight crop.
CATTLE_FULL_FRAME_THRESHOLD: float = 0.80

# ---------------------------------------------------------------------------
# Tier 3 – LLM (Qwen 2.5 via LM Studio)
# ---------------------------------------------------------------------------
LM_STUDIO_BASE_URL: str = "http://127.0.0.1:1234/v1"
LM_STUDIO_API_KEY: str = "lm-studio"
LLM_MODEL_NAME: str = "qwen2.5-vl-3b-instruct"
