"""Validation-only threshold exploration, followed by a frozen-policy test report."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from PIL import Image
from .audit import CLASSES, digest, read_rows, save_json
from .metrics import classification, detection, iou, selective_curve, binary_metrics, group_bootstrap
from ..implementations.lesion_segmenter import threshold_mask

MASK_THRESHOLDS = [.3, .4, .5, .6, .7]
MASK_FILTERS = [0, 15/(224*224), 50/(224*224)]


def load_inputs(manifest, predictions):
    rows = read_rows(manifest)
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate manifest IDs")
    group_splits = {}
    hash_splits = {}
    for row in rows:
        group_splits.setdefault(row["group_id"], set()).add(row["split"])
        if row.get("sha256"):
            hash_splits.setdefault(row["sha256"], set()).add(row["split"])
    for row in rows:
        crossing = len(group_splits[row["group_id"]]) > 1 or len(hash_splits.get(row.get("sha256"), set())) > 1
        if crossing and (row.get("split_clean") or row.get("independent")):
            raise ValueError("A claimed clean/independent record shares an image hash or group across partitions")
    run = json.loads((Path(predictions)/"run.json").read_text(encoding="utf8"))
    if not run["complete"] or run["manifest_sha256"] != digest(manifest):
        raise ValueError("Incomplete predictions or manifest mismatch")
    path = Path(predictions)/"predictions.jsonl"
    if digest(path) != run["predictions_sha256"]:
        raise ValueError("Prediction cache changed")
    cached_rows = read_rows(path)
    if len({r["id"] for r in cached_rows}) != len(cached_rows):
        raise ValueError("Duplicate cached predictions")
    cached = {r["id"]: r for r in cached_rows}
    # Missing predictions never disappear from the denominator.
    for r in rows:
        if r["split"] in ["val", "test"] and r["kind"] in run.get("kinds", ["roi", "frame"]) and r["id"] not in cached:
            raise ValueError("Missing predictions; do not score a partial run as the complete cohort")
    return [r for r in rows if r["kind"] in run.get("kinds", ["roi", "frame"])], cached, run


def mask_results(rows, cached, directory, threshold, fraction):
    from collections import defaultdict
    by_class = defaultdict(list)
    negatives = []
    individual = []
    for row in rows:
        if not row.get("mask"):
            continue
        if not row.get("mask_reviewed") or row.get("mask_semantics") != "visible_lesion_foreground":
            raise ValueError("Mask annotation meaning/review must be explicit; boxes or animal polygons are not lesion ground truth")
        prediction = cached[row["id"]]
        if prediction.get("mask_sha256") != digest(row["mask"]):
            raise ValueError("Reference mask changed after inference")
        with Image.open(row["mask"]) as source:
            target = np.asarray(source)
        if target.ndim != 2 or not set(np.unique(target)).issubset({0, 1, 255}):
            raise ValueError("Reference masks must be single-channel binary images")
        probability = np.load(Path(directory)/prediction["mask_probabilities"], allow_pickle=False)
        predicted, _ = threshold_mask(probability, threshold, fraction)
        metrics = binary_metrics(target, predicted)
        if metrics["target_pixels"]:
            if row["disease"] not in CLASSES[1:]:
                raise ValueError("Positive lesion masks need an in-scope disease label")
            by_class[row["disease"]].append(metrics)
        else:
            if not row.get("negative_reviewed"):
                raise ValueError("An empty mask is not a reviewed negative without explicit attestation")
            negatives.append(metrics["negative_false_positive_fraction"])
        individual.append(dict(id=row["id"], group_id=row["group_id"], **metrics))
    per_class = {c: dict(n=len(v), **{key: float(np.mean([r[key] or 0 for r in v])) for key in ["dice", "iou", "recall"]}) for c, v in by_class.items()}
    all_metrics = [m for v in by_class.values() for m in v]
    tp = sum(m["tp"] for m in all_metrics); fp = sum(m["fp"] for m in all_metrics); fn = sum(m["fn"] for m in all_metrics)
    return dict(threshold=threshold, min_region_fraction=fraction, positive_images=len(all_metrics),
        per_class=per_class, disease_macro_dice=float(np.mean([m["dice"] for m in per_class.values()])) if per_class else None,
        positive_pixel_precision=tp/(tp+fp) if tp+fp else None, positive_pixel_recall=tp/(tp+fn) if tp+fn else None,
        reviewed_negative_images=len(negatives), negative_mean_false_positive_fraction=float(np.mean(negatives)) if negatives else None,
        positive_dice_group_bootstrap=group_bootstrap([m for m in individual if m["target_pixels"]], lambda sample: float(np.mean([m["dice"] for m in sample]))))


def summarize(rows, cached, directory, split, threshold=.5, fraction=15/(224*224)):
    partitions = {}
    for scope in ["all_legacy", "conservative_clean"]:
        subset = [r for r in rows if r["split"] == split and
                  (scope == "all_legacy" or (r.get("split_clean") and not r.get("perceptual_cross_split_candidate")))]
        roi = [r for r in subset if r["kind"] == "roi" and r.get("disease") in CLASSES]
        frames = [r for r in subset if r["kind"] == "frame"]
        scope_report = dict(records=len(subset), excluded=len([r for r in rows if r["split"] == split])-len(subset))
        for mode, cohort, key in [("vit_original_crops", roi, "probabilities"),
                                  ("vit_whole_frame", [r for r in frames if r.get("disease")], "probabilities"),
                                  ("yolo_vit_cascade", [r for r in frames if r.get("disease")], "cascade_probabilities")]:
            targets, predicted, probabilities, individuals = [], [], [], []
            for row in cohort:
                result = cached[row["id"]]
                probability = result.get(key)
                valid = probability is not None
                if mode == "yolo_vit_cascade":
                    box = result.get("selected_box")
                    valid = valid and bool(box) and any(iou(box, b["bbox"]) >= .5 for b in row["boxes"])
                pred = CLASSES[int(np.argmax(probability))] if valid else None
                targets.append(row["disease"]); predicted.append(pred)
                individuals.append(dict(group_id=row["group_id"], target=row["disease"], prediction=pred))
                if valid:
                    probabilities.append(probability)
            metric = classification(targets, predicted, probabilities if len(probabilities) == len(targets) and targets else None)
            metric["accuracy_group_bootstrap"] = group_bootstrap(individuals,
                lambda sample: sum(r["target"] == r["prediction"] for r in sample)/len(sample))
            if split == "val" and mode != "yolo_vit_cascade" and targets and len(probabilities) == len(targets):
                metric["review_threshold_curve"] = selective_curve(targets, probabilities)
            scope_report[mode] = metric
        scope_report["ambiguous_or_unlabelled_frames"] = sum(not r.get("disease") for r in frames)
        scope_report["detector"] = [detection(frames, [cached[r["id"]] for r in frames], c) for c in ([.25, .4, .6] if split == "val" else [.25])]
        scope_report["mask"] = mask_results(subset, cached, directory, threshold, fraction)
        partitions[scope] = scope_report
    return dict(split=split, interpretation="Legacy supplied labels; conservative exclusions do not establish independent clinical validation.", scopes=partitions)


def validate(manifest, predictions, output):
    rows, cached, run = load_inputs(manifest, predictions)
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    if (output/"frozen_policy.json").exists() or (output/"validation_report.json").exists():
        raise ValueError("Validation policy already frozen; preserve it and use a new experiment for changes")
    # No test targets or predictions are passed to selection/summarization.
    validation = [r for r in rows if r["split"] == "val"]
    threshold, fraction = .5, 15/(224*224)
    candidates = []
    mask_rows = [r for r in validation if r.get("mask") and r.get("split_clean") and not r.get("perceptual_cross_split_candidate")]
    eligible = bool(mask_rows) and all(r.get("independent") is True and r.get("training_exclusion_evidence") for r in mask_rows)
    if eligible:
        # Require all intended diseases plus explicit reviewed negatives.
        for t in MASK_THRESHOLDS:
            for f in MASK_FILTERS:
                candidates.append(mask_results(mask_rows, cached, predictions, t, f))
        if set(candidates[0]["per_class"]) == set(CLASSES[1:]) and candidates[0]["reviewed_negative_images"]:
            winner = max(candidates, key=lambda c: (c["disease_macro_dice"], -c["negative_mean_false_positive_fraction"], -abs(c["threshold"]-.5), -c["min_region_fraction"]))
            threshold, fraction = winner["threshold"], winner["min_region_fraction"]
        else:
            eligible = False
    policy = dict(manifest_sha256=digest(manifest), predictions_sha256=run["predictions_sha256"],
                  checkpoint_sha256=run["checkpoint_sha256"], selection_partition="val",
                  detector_threshold=.25, classifier_review_confidence=.6, classifier_review_margin=.15,
                  classifier_selection="unchanged defaults; candidate risk/coverage reported, acceptable risk not specified",
                  mask_threshold=threshold, mask_min_region_fraction=fraction,
                  mask_selection="validation macro disease Dice, negative false-positive area tie-break" if eligible else "not validated: reference masks/independence/class coverage incomplete",
                  deployment="offline candidate only; runtime configuration unchanged",
                  clinical_thresholds="not evaluated; require independently veterinary-graded observations",
                  selection_code_sha256=digest(Path(__file__)))
    report = summarize(validation, cached, predictions, "val", threshold, fraction)
    report.update(mask_threshold_candidates=candidates, frozen_policy=policy)
    save_json(output/"validation_report.json", report)
    save_json(output/"frozen_policy.json", policy)
    print(json.dumps(policy, indent=2))


def test(manifest, predictions, policy_path, output):
    output = Path(output)
    if output.exists():
        raise ValueError("Test report exists; do not overwrite an already inspected holdout")
    rows, cached, run = load_inputs(manifest, predictions)
    policy = json.loads(Path(policy_path).read_text(encoding="utf8"))
    for key, expected in [("manifest_sha256", digest(manifest)), ("predictions_sha256", run["predictions_sha256"]), ("checkpoint_sha256", run["checkpoint_sha256"]), ("selection_partition", "val"), ("selection_code_sha256", digest(Path(__file__)))]:
        if policy[key] != expected:
            raise ValueError(f"Frozen policy mismatch: {key}")
    report = summarize([r for r in rows if r["split"] == "test"], cached, predictions, "test", policy["mask_threshold"], policy["mask_min_region_fraction"])
    # No threshold sweeps on test. Defaults/frozen policy only.
    for scope in report["scopes"].values():
        scope["detector"] = [m for m in scope["detector"] if m["confidence_threshold"] == policy["detector_threshold"]]
        for key in ["vit_original_crops", "vit_whole_frame", "yolo_vit_cascade"]:
            scope[key].pop("review_threshold_curve", None)
    report.update(policy_sha256=digest(policy_path), frozen_policy=policy)
    save_json(output, report)
    print(f"Wrote fixed-policy test report: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["validate", "test"])
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--policy")
    args = parser.parse_args()
    if args.action == "validate":
        validate(args.manifest, args.predictions, args.output)
    else:
        if not args.policy:
            parser.error("Test scoring requires a previously frozen validation policy")
        test(args.manifest, args.predictions, args.policy, args.output)
