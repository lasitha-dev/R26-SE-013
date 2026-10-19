"""Research-only visual-grade CLI. Does not call or change clinical APIs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from PIL import Image

from model import ROOT, image_transform, load_checkpoint


def predict(image_path: Path, checkpoint_path: Path) -> dict:
    torch.set_num_threads(4)
    model, metadata = load_checkpoint(checkpoint_path)
    with Image.open(image_path) as image:
        tensor = image_transform()(image).unsqueeze(0)
    with torch.inference_mode():
        probs = torch.softmax(model(tensor) / metadata["temperature"], dim=1)[0].tolist()
    labels = metadata["labels"]
    return {"visual_lsd_lesion_grade": labels[max(range(len(probs)), key=lambda i: probs[i])],
            "probabilities": dict(zip(labels, probs)), "target": metadata["target"],
            "clinical_severity": None, "clinical_stage": None, "veterinary_review_required": True,
            "scope": "Research prototype for in-scope DataHub-like images; not validated for arbitrary crops or non-cattle images.",
            "model_candidate": metadata["selected_candidate"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "artifacts/weights/best_model.pt")
    args = parser.parse_args()
    print(json.dumps(predict(args.image, args.checkpoint), indent=2))
