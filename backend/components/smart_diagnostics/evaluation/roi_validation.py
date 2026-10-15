"""Separate validation-only annotation-envelope correction and paired evaluation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .audit import CLASSES, digest, inspect_image, read_rows, save_json
from .infer import crop_box, open_rgb
from .metrics import classification, group_bootstrap
from .report import load_inputs


def annotation_box(parts, size):
    """YOLO xywh boxes or polygon vertex pairs -> clipped float envelope."""
    values = np.asarray([float(v) for v in parts[1:]], dtype=float)
    if not np.isfinite(values).all() or np.any(values < -1e-6) or np.any(values > 1+1e-6):
        raise ValueError("Invalid normalized annotation coordinates")
    if len(values) == 4:
        x, y, w, h = values
        result = np.array([x-w/2, y-h/2, x+w/2, y+h/2])
    elif len(values) >= 6 and len(values) % 2 == 0:
        points = values.reshape(-1, 2)
        result = np.r_[points.min(axis=0), points.max(axis=0)]
    else:
        raise ValueError("Expected a YOLO box or polygon")
    w, h = size
    result = np.clip(result, 0, 1) * [w, h, w, h]
    if result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError("Degenerate annotation envelope")
    return result.tolist()


def prepare(manifest, baseline_predictions, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output/"protocol.json").exists() or (output/"manifest.jsonl").exists():
        raise ValueError("ROI experiment exists; preserve it and choose a new directory")
    rows = read_rows(manifest)
    parents = {(r["split"], Path(r["image"]).stem): r for r in rows if r["kind"] == "frame"}
    validation = [r for r in rows if r["kind"] == "roi" and r["split"] == "val"]
    if not validation:
        raise ValueError("No validation crops")
    baseline_run = json.loads((Path(baseline_predictions)/"run.json").read_text(encoding="utf8"))
    if baseline_run["manifest_sha256"] != digest(manifest) or not baseline_run["complete"]:
        raise ValueError("Baseline cache does not match the audited manifest")
    if baseline_run["predictions_sha256"] != digest(Path(baseline_predictions)/"predictions.jsonl"):
        raise ValueError("Baseline predictions changed")
    # Fixed before any new predictions; no test examples are selected or regenerated.
    protocol = dict(version="validation_roi_envelopes_v1", partition="val",
        baseline_manifest_sha256=digest(manifest), baseline_predictions_sha256=baseline_run["predictions_sha256"],
        baseline_checkpoint_sha256=baseline_run["checkpoint_sha256"],
        intervention="polygon-derived validation crops use the full annotation envelope; box-derived crops retain original bytes",
        encoding="Pillow JPEG quality=95 subsampling=2 for regenerated crops; decoder/encoder differences may contribute",
        labels="inherited, unchanged, not veterinarian-reviewed", independent=False,
        thresholds="unchanged; no threshold selection in this experiment", test_partition="not regenerated or rescored",
        code_sha256=digest(Path(__file__)))
    save_json(output/"protocol.json", protocol)
    images = output/"images"; images.mkdir(exist_ok=True)
    prepared, changes = [], []
    for i, old in enumerate(validation, 1):
        stem, index = Path(old["image"]).stem.rsplit("_crop", 1)
        index = int(index)
        parent = parents.get(("val", stem))
        if not parent or index >= len(parent["boxes"]):
            raise ValueError(f"Missing parent for {old['id']}")
        if digest(old["image"]) != old["sha256"]:
            raise ValueError("Original validation crop changed")
        annotation = parent["boxes"][index]
        if old["disease"] != annotation["disease"]:
            raise ValueError("Crop and parent class disagree")
        row = dict(old, parent_frame_id=parent["id"], annotation_index=index,
                   baseline_crop_sha256=old["sha256"], geometry_version="validation_roi_envelopes_v1",
                   geometry_changed=annotation["annotation_type"] == "polygon_envelope",
                   label_reviewed=False, independent=False)
        if row["geometry_changed"]:
            if digest(parent["image"]) != parent["sha256"]:
                raise ValueError("Parent image changed")
            with Image.open(parent["image"]) as raw:
                if raw.getexif().get(274, 1) != 1:
                    raise ValueError("Noncanonical image orientation requires reference-coordinate review")
            source = open_rgb(parent["image"])
            p = Path(parent["image"])
            parts = (p.parent.parent/"labels"/(p.stem+".txt")).read_text().splitlines()[index].split()
            current = annotation_box(parts, source.size)
            if not np.allclose(current, annotation["bbox"], atol=1e-6, rtol=0):
                raise ValueError("Annotation envelope changed since audit")
            box = crop_box(source, current)
            corrected = source.crop(box)
            path = images/(old["id"]+".jpg")
            corrected.save(path, quality=95, subsampling=2)
            row.update(image=str(path.resolve()))
            inspect_image(row)
            changes.append(dict(id=old["id"], parent_frame_id=parent["id"], disease=old["disease"],
                                previous_size=old["size"], new_size=row["size"], crop_box=box))
        prepared.append(row)
        if i % 300 == 0:
            print(f"Prepared {i}/{len(validation)} validation records", flush=True)
    manifest_path = output/"manifest.jsonl"
    manifest_path.write_text("".join(json.dumps(r)+"\n" for r in prepared), encoding="utf8")
    (output/"geometry_changes.jsonl").write_text("".join(json.dumps(r)+"\n" for r in changes), encoding="utf8")
    save_json(output/"preparation_summary.json", dict(validation_records=len(prepared), changed_geometry=len(changes),
        unchanged_original_crops=len(prepared)-len(changes), classes_changed=dict(Counter(c["disease"] for c in changes)),
        manifest_sha256=digest(manifest_path), protocol_sha256=digest(output/"protocol.json"),
        independent=False, reviewed_lesion_masks=0))


def paired(manifest, predictions, baseline_predictions, protocol_path, output):
    if Path(output).exists():
        raise ValueError("Paired report exists; preserve it")
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf8"))
    if protocol["code_sha256"] != digest(Path(__file__)):
        raise ValueError("Experiment code differs from prepared protocol")
    rows, cache, run = load_inputs(manifest, predictions)
    preparation = json.loads(Path(manifest).with_name("preparation_summary.json").read_text(encoding="utf8"))
    if preparation["manifest_sha256"] != digest(manifest) or preparation["protocol_sha256"] != digest(protocol_path):
        raise ValueError("Prepared experiment changed")
    if any(r["split"] != "val" for r in rows):
        raise ValueError("Paired study is validation only")
    baseline_path = Path(baseline_predictions)/"predictions.jsonl"
    baseline_run = json.loads((Path(baseline_predictions)/"run.json").read_text(encoding="utf8"))
    if digest(baseline_path) != protocol["baseline_predictions_sha256"] or baseline_run["checkpoint_sha256"] != protocol["baseline_checkpoint_sha256"]:
        raise ValueError("Baseline predictions or weights changed")
    if run["checkpoint_sha256"]["vit"] != protocol["baseline_checkpoint_sha256"]["vit"]:
        raise ValueError("Paired comparison must use the same classifier weights")
    baseline = {r["id"]: r for r in read_rows(baseline_path) if r.get("split") == "val"}
    result = dict(partition="val", independent=False, labels="inherited, pending review", thresholds_changed=False,
                  test_partition_evaluated=False, protocol_sha256=digest(protocol_path), cohorts={})
    for name, cohort in [("all_validation", rows), ("polygon_geometry_changed", [r for r in rows if r["geometry_changed"]]),
                         ("original_box_crops_unchanged", [r for r in rows if not r["geometry_changed"]]),
                         ("conservative_clean", [r for r in rows if r["split_clean"] and not r["perceptual_cross_split_candidate"]])]:
        targets, old_preds, new_preds, pairs = [], [], [], []
        for row in cohort:
            a = CLASSES[int(np.argmax(baseline[row["id"]]["probabilities"]))]
            b = CLASSES[int(np.argmax(cache[row["id"]]["probabilities"]))]
            target = row["disease"]
            targets.append(target); old_preds.append(a); new_preds.append(b)
            pairs.append(dict(group_id=row["group_id"], old_correct=a==target, new_correct=b==target))
        before, after = classification(targets, old_preds), classification(targets, new_preds)
        result["cohorts"][name] = dict(n=len(cohort), original=before, corrected_envelope=after,
            accuracy_delta=after["accuracy"]-before["accuracy"] if cohort else None,
            wrong_to_correct=sum(not p["old_correct"] and p["new_correct"] for p in pairs),
            correct_to_wrong=sum(p["old_correct"] and not p["new_correct"] for p in pairs),
            accuracy_delta_bootstrap=group_bootstrap(pairs, lambda sample: sum(int(p["new_correct"])-int(p["old_correct"]) for p in sample)/len(sample)))
    save_json(output, result)
    print(json.dumps({k: dict(n=v["n"], original=v["original"]["accuracy"], corrected=v["corrected_envelope"]["accuracy"], delta=v["accuracy_delta"]) for k,v in result["cohorts"].items()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "compare"])
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--baseline-predictions", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--predictions")
    parser.add_argument("--protocol")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.manifest, args.baseline_predictions, args.output)
    else:
        if not args.predictions or not args.protocol:
            parser.error("Comparison requires predictions and a prepared protocol")
        paired(args.manifest, args.predictions, args.baseline_predictions, args.protocol, args.output)
