"""Cache frozen-checkpoint predictions on existing val/test partitions; no fitting."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageOps
from .audit import CLASSES, digest, read_rows, save_json


def open_rgb(path):
    with Image.open(path) as source:
        return ImageOps.exif_transpose(source).convert("RGB")


def crop_box(image, bbox):
    x1, y1, x2, y2 = bbox
    box = [max(0, int(x1)), max(0, int(y1)), min(image.width, int(x2)), min(image.height, int(y2))]
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError("Empty selected ROI")
    return box


def infer(manifest, output, batch_size=16, kinds=("roi", "frame")):
    from ..implementations.vit_classifier import ViTClassifier
    from ..implementations.yolo_detector import YOLODetector
    from ..implementations.lesion_segmenter import LesionSegmenter
    import torch
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / "predictions.jsonl"
    if target.exists() or (output / "run.json").exists():
        raise ValueError("Prediction output exists; use a new directory.")
    models = Path(__file__).resolve().parents[1] / "models"
    vit_path, yolo_path = models/"best_vit_model.pth", models/"yolo_smart_diag_best.pt"
    classifier = ViTClassifier(str(vit_path))
    classifier._ensure_loaded()
    detector = YOLODetector(str(yolo_path), conf_threshold=.25)
    segmenter = None
    rows = [r for r in read_rows(manifest) if r["split"] in ["val", "test"] and r["kind"] in kinds]
    expected = dict(manifest_sha256=digest(manifest), classes=CLASSES,
        checkpoint_sha256=dict(vit=digest(vit_path), yolo=digest(yolo_path)),
        created_utc=datetime.now(timezone.utc).isoformat(), batch_size=batch_size,
        detector_cache_floor=.25, deployed_detector_threshold=.25,
        preprocessing="production adapters; EXIF transpose; RGB; direct resize; no SquarePad",
        attention="not evaluated; not used for class probabilities", code_sha256={
            str(p.relative_to(models.parent)): digest(p) for p in [Path(__file__), models.parent/"implementations/vit_classifier.py",
                models.parent/"implementations/yolo_detector.py", models.parent/"implementations/lesion_segmenter.py"]},
        device=str(classifier._device), complete=False, selected_records=len(rows), kinds=list(kinds))
    save_json(output/"run.json", expected)

    def classify(images):
        with torch.inference_mode():
            batch = torch.stack([classifier._transform(img) for img in images]).to(classifier._device)
            logits = classifier._model(batch)
            probabilities = logits.softmax(dim=1).cpu().numpy()
        if probabilities.shape != (len(images), 4) or not np.isfinite(probabilities).all():
            raise ValueError("Invalid classifier outputs")
        return probabilities.tolist()

    start = time.perf_counter()
    with target.open("x", encoding="utf8") as stream:
        for offset in range(0, len(rows), batch_size):
            batch_rows = rows[offset:offset+batch_size]
            results = [dict(id=r["id"], split=r["split"], status="ok") for r in batch_rows]
            images = []
            for row in batch_rows:
                if digest(row["image"]) != row["sha256"]:
                    raise ValueError(f"Image changed since audit: {row['id']}")
                images.append(open_rgb(row["image"]))
            probs = classify(images)
            crops, crop_indices = [], []
            for index, (row, image, result, probability) in enumerate(zip(batch_rows, images, results, probs)):
                result["probabilities"] = probability
                if row["kind"] == "frame":
                    detections = detector.predict(image)
                    result["detections"] = detections
                    active = [d for d in detections if d["confidence"] >= .25]
                    if active:
                        selected = max(active, key=lambda d: d["confidence"])
                        box = crop_box(image, selected["bbox"])
                        result["selected_box"] = box
                        crops.append(image.crop(box)); crop_indices.append(index)
                    else:
                        result["selected_box"] = None
                if row.get("mask"):
                    if segmenter is None:
                        segmenter = LesionSegmenter(str(models/"mask_rcnn_cow_symptoms_refined.keras"), manifest_path=str(models/"segmenter_manifest.json"))
                        expected["checkpoint_sha256"]["segmenter"] = digest(models/"mask_rcnn_cow_symptoms_refined.keras")
                    if row["kind"] != "roi":
                        raise ValueError("Standalone mask evaluation requires an explicitly annotated ROI; full-frame cascade masks need a separate protocol.")
                    mask_probs = segmenter.predict_probabilities(image)
                    cache = output / (row["id"] + ".npy")
                    np.save(cache, mask_probs, allow_pickle=False)
                    result["mask_probabilities"] = cache.name
                    result["mask_sha256"] = digest(row["mask"])
            if crops:
                for index, probability in zip(crop_indices, classify(crops)):
                    results[index]["cascade_probabilities"] = probability
            for result in results:
                stream.write(json.dumps(result, allow_nan=False) + "\n")
            stream.flush()
            if offset % (batch_size * 10) == 0:
                print(f"Cached {min(offset+batch_size, len(rows))}/{len(rows)} ({time.perf_counter()-start:.1f}s)", flush=True)
    expected.update(complete=True, predictions_sha256=digest(target), elapsed_seconds=time.perf_counter()-start)
    save_json(output/"run.json", expected)
    print(f"Complete: {len(rows)} predictions; {expected['elapsed_seconds']:.1f}s", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--kind", choices=["all", "roi", "frame"], default="all")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("Batch size must be positive")
    infer(args.manifest, args.output, args.batch_size, ("roi", "frame") if args.kind == "all" else (args.kind,))
