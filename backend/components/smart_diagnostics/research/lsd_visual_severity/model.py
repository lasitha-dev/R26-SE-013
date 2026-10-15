"""Small isolated vision model and shared preprocessing, without API integration."""
from __future__ import annotations

from pathlib import Path

import torch
from PIL import Image, ImageOps
from torch import nn
from torchvision import transforms
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

ROOT = Path(__file__).resolve().parent
LABELS = ["normal", "mild", "severe"]
MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]


class SquarePad:
    def __call__(self, image: Image.Image) -> Image.Image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        side = max(image.size)
        canvas = Image.new("RGB", (side, side), (114, 114, 114))
        canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
        return canvas


def image_transform(training: bool = False):
    steps = [SquarePad(), transforms.Resize((224, 224), antialias=True)]
    if training:
        steps += [transforms.RandomHorizontalFlip(), transforms.ColorJitter(brightness=0.1, contrast=0.1)]
    return transforms.Compose(steps + [transforms.ToTensor(), transforms.Normalize(MEAN, STD)])


def build_model(architecture: str = "mobilenet_v3_small_mlp", pretrained: bool = False):
    torch.hub.set_dir(str(ROOT / "data/torch_cache"))
    weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
    model = mobilenet_v3_small(weights=weights)
    if architecture == "mobilenet_v3_small_linear":
        model.classifier = nn.Linear(model.classifier[0].in_features, len(LABELS))
    elif architecture == "mobilenet_v3_small_mlp":
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(LABELS))
    else:
        raise ValueError(f"Unsupported prototype architecture: {architecture}")
    return model


def load_checkpoint(path: Path, device: torch.device | str = "cpu"):
    checkpoint = torch.load(path, map_location=device, weights_only=True)
    if checkpoint.get("labels") != LABELS or checkpoint.get("target") != "visual_lsd_lesion_grade":
        raise ValueError("This is not a compatible visual LSD severity checkpoint.")
    model = build_model(checkpoint["architecture"])
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    return model.to(device).eval(), checkpoint
