"""Run the prespecified, validation-selected experiment on a frozen manifest."""
from __future__ import annotations

import csv
import hashlib
import json
import random
import time
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from PIL import Image
from scipy.optimize import minimize_scalar
from scipy.special import softmax
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, classification_report,
                             cohen_kappa_score, confusion_matrix, f1_score, log_loss)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, Dataset

from audit import ARTIFACTS, LABELS, ROOT, SEED, save_json
from model import build_model, image_transform, load_checkpoint


class ImageRows(Dataset):
    def __init__(self, rows: list[dict], training: bool = False):
        self.rows, self.transform = rows, image_transform(training)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(ROOT / row["image_path"]) as image:
            tensor = self.transform(image)
        return tensor, int(row["label_index"])


def metrics(y: np.ndarray, probabilities: np.ndarray) -> dict:
    pred = probabilities.argmax(axis=1)
    return {"n": len(y), "accuracy": float(accuracy_score(y, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
            "macro_f1": float(f1_score(y, pred, labels=[0, 1, 2], average="macro", zero_division=0)),
            "weighted_kappa": float(cohen_kappa_score(y, pred, labels=[0, 1, 2], weights="quadratic")),
            "ordinal_mae": float(np.abs(y - pred).mean()),
            "nll": float(log_loss(y, probabilities, labels=[0, 1, 2])),
            "multiclass_brier": float(((probabilities - np.eye(3)[y]) ** 2).sum(axis=1).mean()),
            "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1, 2]).tolist(),
            "classification_report": classification_report(y, pred, labels=[0, 1, 2],
                target_names=list(LABELS), output_dict=True, zero_division=0)}


def evaluate(model, loader, device, features: bool = False):
    model.eval()
    output, targets = [], []
    with torch.inference_mode():
        for x, y in loader:
            x = x.to(device)
            if features:
                values = model.avgpool(model.features(x)).flatten(1)
            else:
                values = model(x)
            output.append(values.float().cpu().numpy())
            targets.extend(y.tolist())
    return np.concatenate(output), np.asarray(targets, dtype=int)


def checkpoint(model, architecture, audit, extra=None):
    return {"model_state_dict": {key: value.detach().cpu().clone() for key, value in model.state_dict().items()},
            "architecture": architecture, "labels": list(LABELS), "target": "visual_lsd_lesion_grade",
            "clinical_severity_supported": False, "clinical_stage_supported": False,
            "manifest_sha256": audit["manifest_sha256"], "seed": SEED, "image_size": 224,
            "temperature": 1.0, "normalization_mean": [0.485, 0.456, 0.406],
            "normalization_std": [0.229, 0.224, 0.225], **(extra or {})}


def bootstrap_groups(rows, y, probs, repetitions=1000):
    rng = np.random.default_rng(SEED)
    group_indices = {}
    for i, row in enumerate(rows):
        group_indices.setdefault(row["group_id"], []).append(i)
    class_groups = {c: [g for g, idx in group_indices.items() if y[idx[0]] == c] for c in range(3)}
    values = {"accuracy": [], "macro_f1": [], "ordinal_mae": [], "severe_recall": []}
    for _ in range(repetitions):
        sampled = [g for groups in class_groups.values() for g in rng.choice(groups, len(groups), replace=True)]
        idx = np.asarray([i for g in sampled for i in group_indices[g]])
        truth, pred = y[idx], probs[idx].argmax(axis=1)
        values["accuracy"].append(float((truth == pred).mean()))
        values["macro_f1"].append(float(f1_score(truth, pred, labels=[0, 1, 2], average="macro", zero_division=0)))
        values["ordinal_mae"].append(float(np.abs(truth - pred).mean()))
        values["severe_recall"].append(float((pred[truth == 2] == 2).mean()))
    return {name: {"low_95": float(np.quantile(v, 0.025)), "high_95": float(np.quantile(v, 0.975))}
            for name, v in values.items()}


def main():
    start = time.perf_counter()
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(4)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    protocol_path = ROOT / "protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    audit = json.loads((ARTIFACTS / "audit_summary.json").read_text(encoding="utf-8"))
    manifest = ARTIFACTS / "manifest.csv"
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != audit["manifest_sha256"]:
        raise RuntimeError("Manifest changed since the audit; refusing to train.")
    with manifest.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["included"] == "True"]
    subsets = {name: [row for row in rows if row["split"] == name] for name in ("train", "validation", "test")}
    groups = {name: {row["group_id"] for row in subset} for name, subset in subsets.items()}
    if groups["train"] & groups["validation"] or groups["train"] & groups["test"] or groups["validation"] & groups["test"]:
        raise RuntimeError("Duplicate group leakage detected.")
    weights_dir = ARTIFACTS / "weights"
    weights_dir.mkdir(exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    save_json(ARTIFACTS / "run_protocol.json", {**protocol, "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
              "manifest_sha256": audit["manifest_sha256"], "device": str(device),
              "device_name": torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU",
              "torch_version": str(torch.__version__)})
    batch_size = protocol["batch_size"]
    loaders = {name: DataLoader(ImageRows(subset), batch_size=batch_size, shuffle=False, num_workers=0)
               for name, subset in subsets.items()}
    training = DataLoader(ImageRows(subsets["train"], True), batch_size=batch_size, shuffle=True,
                          num_workers=0, generator=torch.Generator().manual_seed(SEED))
    model = build_model(pretrained=True).to(device)
    print("Device:", device, "partitions:", {k: len(v) for k, v in subsets.items()}, flush=True)

    # Test images are not inspected by either candidate until selection is complete.
    train_features, y_train = evaluate(model, loaders["train"], device, features=True)
    val_features, y_val = evaluate(model, loaders["validation"], device, features=True)
    probe = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=SEED))
    probe.fit(train_features, y_train)
    probe_logits = probe.decision_function(val_features)
    probe_val = metrics(y_val, softmax(probe_logits, axis=1))
    scale, lr = probe[0], probe[1]
    probe_model = build_model("mobilenet_v3_small_linear")
    probe_model.features.load_state_dict(model.features.state_dict())
    folded_w = lr.coef_ / scale.scale_
    folded_b = lr.intercept_ - folded_w @ scale.mean_
    with torch.no_grad():
        probe_model.classifier.weight.copy_(torch.tensor(folded_w, dtype=torch.float32))
        probe_model.classifier.bias.copy_(torch.tensor(folded_b, dtype=torch.float32))
        exported_logits = probe_model.classifier(torch.tensor(val_features)).numpy()
    if not np.allclose(exported_logits, probe_logits, atol=2e-4, rtol=2e-4):
        raise RuntimeError("Exported linear probe does not match the fitted validation logits.")
    torch.save(checkpoint(probe_model, "mobilenet_v3_small_linear", audit), weights_dir / "linear_probe.pt")
    print(f"Frozen linear probe validation macro F1: {probe_val['macro_f1']:.4f}", flush=True)
    del probe_model, train_features, val_features

    counts = np.bincount(y_train, minlength=3)
    class_weights = torch.tensor(len(y_train) / (3 * counts), dtype=torch.float32, device=device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    history, best_key, stale = [], (-1.0, float("-inf")), 0
    best_neural_val, best_neural_logits = None, None
    total_epochs = protocol["head_epochs"] + protocol["finetune_epochs"]
    optimizer = None
    for epoch in range(total_epochs):
        phase = "head" if epoch < protocol["head_epochs"] else "finetune"
        if epoch in (0, protocol["head_epochs"]):
            for p in model.features.parameters():
                p.requires_grad_(False)
            if phase == "finetune":
                best_bundle = torch.load(weights_dir / "neural_best.pt", map_location=device, weights_only=True)
                model.load_state_dict(best_bundle["model_state_dict"])
                for block in list(model.features.children())[-4:]:
                    for p in block.parameters():
                        p.requires_grad_(True)
                stale = 0
            optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                lr=protocol["head_lr"] if phase == "head" else protocol["finetune_lr"],
                weight_decay=protocol["weight_decay"])
        model.train()
        for block in model.features.children():
            if not any(p.requires_grad for p in block.parameters()):
                block.eval()
        epoch_start, total_loss = time.perf_counter(), 0.0
        for x, y in training:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                loss = criterion(model(x), y)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            total_loss += float(loss.detach()) * len(y)
        logits, target = evaluate(model, loaders["validation"], device)
        score = metrics(target, softmax(logits, axis=1))
        key = (score["macro_f1"], -score["nll"])
        if key > best_key:
            best_key, stale = key, 0
            best_neural_val, best_neural_logits = score, logits
            torch.save(checkpoint(model, "mobilenet_v3_small_mlp", audit, {"best_epoch": epoch + 1}), weights_dir / "neural_best.pt")
        else:
            stale += 1
        record = {"epoch": epoch + 1, "phase": phase, "training_loss": total_loss / len(y_train),
                  "validation_macro_f1": score["macro_f1"], "validation_accuracy": score["accuracy"],
                  "validation_nll": score["nll"], "seconds": time.perf_counter() - epoch_start}
        history.append(record)
        save_json(ARTIFACTS / "training_history.json", history)
        print(json.dumps(record), flush=True)
        if phase == "finetune" and stale >= 5:
            break
    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    selected_name = "linear_probe" if (probe_val["macro_f1"], -probe_val["nll"]) >= best_key else "neural_best"
    chosen_logits = probe_logits if selected_name == "linear_probe" else best_neural_logits
    chosen_val = probe_val if selected_name == "linear_probe" else best_neural_val
    fit = minimize_scalar(lambda t: log_loss(y_val, softmax(chosen_logits / t, axis=1), labels=[0, 1, 2]),
                          bounds=(0.25, 10.0), method="bounded")
    temperature = float(fit.x) if fit.success else 1.0
    if log_loss(y_val, softmax(chosen_logits / temperature, axis=1), labels=[0, 1, 2]) > chosen_val["nll"]:
        temperature = 1.0
    selected_model, bundle = load_checkpoint(weights_dir / f"{selected_name}.pt", device)
    bundle.update({"temperature": temperature, "selected_by": "validation_macro_f1_then_nll",
                   "selected_candidate": selected_name, "validation_macro_f1": chosen_val["macro_f1"],
                   "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest()})
    torch.save(bundle, weights_dir / "best_model.pt")
    print("Model/temperature frozen; now evaluating the held-out test partition.", flush=True)
    test_logits, y_test = evaluate(selected_model, loaders["test"], device)
    test_probs = softmax(test_logits / temperature, axis=1)
    test_metrics = metrics(y_test, test_probs)
    validation_metrics = metrics(y_val, softmax(chosen_logits / temperature, axis=1))
    majority_probs = np.tile(np.array([1.0, 0.0, 0.0]), (len(y_test), 1))
    summary = {"target": "visual_lsd_lesion_grade", "clinical_severity_supported": False,
               "selected_candidate": selected_name, "temperature": temperature,
               "validation_linear_probe_uncalibrated": probe_val,
               "validation_neural_uncalibrated": best_neural_val,
               "validation_selected_calibrated": validation_metrics,
               "test_selected_calibrated": test_metrics,
               "test_always_normal_baseline": metrics(y_test, majority_probs),
               "test_95pct_group_bootstrap": bootstrap_groups(subsets["test"], y_test, test_probs),
               "test_groups": len(groups["test"]), "training_counts": dict(Counter(row["label"] for row in subsets["train"])),
               "manifest_sha256": audit["manifest_sha256"], "total_seconds": time.perf_counter() - start,
               "model_sha256": hashlib.sha256((weights_dir / "best_model.pt").read_bytes()).hexdigest(),
               "limitations": audit["limitations"], "runtime": {"torch": str(torch.__version__), "device": str(device)}}
    save_json(ARTIFACTS / "metrics.json", summary)
    with (ARTIFACTS / "test_predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_name", "group_id", "label", "predicted", "p_normal", "p_mild", "p_severe"])
        writer.writeheader()
        for row, probs in zip(subsets["test"], test_probs):
            writer.writerow({"source_name": row["source_name"], "group_id": row["group_id"], "label": row["label"],
                             "predicted": LABELS[int(probs.argmax())], **{f"p_{label}": float(probs[i]) for i, label in enumerate(LABELS)}})
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    cm = np.asarray(test_metrics["confusion_matrix"])
    axes[0].imshow(cm, cmap="Blues")
    for i in range(3):
        for j in range(3):
            axes[0].text(j, i, str(cm[i, j]), ha="center", va="center", color="white" if cm[i, j] > cm.max()/2 else "black")
    axes[0].set(xticks=range(3), yticks=range(3), xticklabels=LABELS, yticklabels=LABELS,
                xlabel="Predicted visual grade", ylabel="Inherited label", title="Held-out image-group test")
    axes[1].plot([r["epoch"] for r in history], [r["validation_macro_f1"] for r in history], marker=".")
    axes[1].axhline(probe_val["macro_f1"], color="gray", linestyle="--", label="Frozen linear probe")
    axes[1].set(xlabel="Epoch", ylabel="Validation macro F1", ylim=(0, 1), title="Model selection uses validation only")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(ARTIFACTS / "evaluation.png", dpi=160)
    plt.close(fig)
    print(json.dumps({"selected": selected_name, "test": test_metrics, "time_seconds": summary["total_seconds"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
