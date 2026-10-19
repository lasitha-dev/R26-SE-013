"""Check the saved CPU export against recorded test predictions, without tuning."""
from __future__ import annotations

import csv
import hashlib
import json
import time

import numpy as np
import torch
from scipy.special import softmax
from torch.utils.data import DataLoader

from audit import ARTIFACTS, LABELS, ROOT, contact_sheet, save_json
from model import load_checkpoint
from predict import predict
from train import ImageRows, evaluate, metrics


def main():
    torch.set_num_threads(4)
    checkpoint_path = ARTIFACTS / "weights/best_model.pt"
    reference = json.loads((ARTIFACTS / "metrics.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(checkpoint_path.read_bytes()).hexdigest() == reference["model_sha256"]
    assert hashlib.sha256((ARTIFACTS / "manifest.csv").read_bytes()).hexdigest() == reference["manifest_sha256"]
    with (ARTIFACTS / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        manifest = list(csv.DictReader(handle))
    with (ARTIFACTS / "test_predictions.csv").open(encoding="utf-8", newline="") as handle:
        stored = list(csv.DictReader(handle))
    lookup = {row["source_name"]: row for row in manifest}
    rows = [lookup[row["source_name"]] for row in stored]
    model, metadata = load_checkpoint(checkpoint_path)
    assert metadata["clinical_severity_supported"] is False
    assert metadata["clinical_stage_supported"] is False
    start = time.perf_counter()
    logits, y = evaluate(model, DataLoader(ImageRows(rows), batch_size=32, num_workers=0), torch.device("cpu"))
    seconds = time.perf_counter() - start
    cpu_probs = softmax(logits / metadata["temperature"], axis=1)
    stored_probs = np.array([[float(row[f"p_{label}"]) for label in LABELS] for row in stored])
    max_difference = float(np.max(np.abs(cpu_probs - stored_probs)))
    disagreements = int(np.sum(cpu_probs.argmax(1) != stored_probs.argmax(1)))
    # CUDA/cuDNN and CPU convolution arithmetic can differ slightly. Require
    # close probabilities and identical decisions across the complete test set.
    assert max_difference < 0.002, max_difference
    assert disagreements == 0, disagreements
    checks = []
    for label in LABELS:
        index = next(i for i, row in enumerate(stored) if row["label"] == label)
        output = predict(ROOT / rows[index]["image_path"], checkpoint_path)
        probs = np.array([output["probabilities"][name] for name in LABELS])
        assert np.allclose(probs, cpu_probs[index], atol=1e-5, rtol=1e-4)
        assert output["clinical_severity"] is None and output["clinical_stage"] is None
        assert output["veterinary_review_required"] is True
        checks.append({"source_name": rows[index]["source_name"], "inherited_label": label, "output": output})
    failures = [rows[i] for i in range(len(rows)) if y[i] != cpu_probs[i].argmax()]
    contact_sheet(failures, ARTIFACTS / "test_examples.jpg", "All held-out mistakes; inherited labels shown (not vet-regraded)")
    result = {"checks_passed": True, "test_images": len(rows), "cpu_test_metrics": metrics(y, cpu_probs),
              "cpu_evaluation_seconds": seconds, "cpu_gpu_prediction_disagreements": disagreements,
              "max_probability_difference_cpu_gpu": max_difference,
              "selection": "First stored test example in each class; no model selection or tuning",
              "cli_checks": checks, "mistakes": len(failures)}
    save_json(ARTIFACTS / "export_verification.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
