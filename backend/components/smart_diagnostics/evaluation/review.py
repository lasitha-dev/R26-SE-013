"""Trace local source labels; prepare explicit, unapproved annotation review queues."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from .audit import YOLO_CLASSES, digest, read_rows, save_json


def notebook_mapping(name):
    name = name.lower()
    if "lumpy" in name:
        return "lumpy_skin"
    if any(word in name for word in ["foot", "mouth", "fmd"]):
        return "foot_and_mouth"
    if "mastitis" in name:
        return "mastitis"
    return "cattle"


def semantic_issue(name):
    """Flags for review, never corrected diagnoses or clinical mask approvals."""
    name = name.lower().replace("_", " ").replace("-", " ")
    if "abnormal" in name:
        return "abnormal_defaulted_to_cattle"
    if "healthy" in name or name.strip() in ["normal", "mastitis no"]:
        return "healthy_or_normal_annotation_not_lesion_foreground"
    if any(word in name for word in ["feeding", "drinking", "lying", "standing"]):
        return "behaviour_does_not_establish_clinical_health"
    if name.strip() in ["foot", "head", "mouth", "torso", "udder", "cow", "object"]:
        return "anatomical_or_object_target_not_verified_lesion"
    return "disease_or_symptom_label_requires_review"


def source_annotations(path, names):
    labels = []
    for line in path.read_text(encoding="utf8").splitlines():
        parts = line.split()
        if not parts:
            continue
        index = int(parts[0])
        name = names[index] if isinstance(names, list) else names.get(index, names.get(str(index)))
        if name is None:
            raise ValueError(f"Unmapped source category in {path}")
        labels.append(dict(name=name, values=[float(v) for v in parts[1:]], mapped=notebook_mapping(name)))
    return labels


def trace_frame(row, index):
    candidates = []
    merged_path = Path(row["image"])
    merged_labels = merged_path.parent.parent/"labels"/(merged_path.stem+".txt")
    merged = [line.split() for line in merged_labels.read_text(encoding="utf8").splitlines() if line.strip()]
    for candidate in index.get(merged_path.name, []):
        path = candidate["path"]
        if digest(path) != row["sha256"]:
            continue
        labels = source_annotations(path.parent.parent/"labels"/(path.stem+".txt"), candidate["names"])
        matches = len(labels) == len(merged)
        if matches:
            for original, remapped in zip(labels, merged):
                coords = list(map(float, remapped[1:]))
                if len(original["values"]) != len(coords) or not np.allclose(original["values"], coords, rtol=0, atol=1e-7) or original["mapped"] != YOLO_CLASSES[int(remapped[0])]:
                    matches = False
                    break
        candidates.append(dict(source_id=candidate["id"], source_split=candidate["split"],
                               image_sha256_matches=True, annotations_and_mapping_match=bool(matches),
                               original_labels=[a["name"] for a in labels]))
    matched = [c for c in candidates if c["annotations_and_mapping_match"]]
    signatures = {tuple(c["original_labels"]) for c in matched}
    resolved_labels = next(iter(signatures)) if len(signatures) == 1 else None
    return dict(id=row["id"], split=row["split"], candidates=candidates,
                provenance_status="unique_export_match" if len(matched) == 1 else "multiple_export_matches" if matched else "unresolved",
                resolved_original_labels=resolved_labels,
                semantic_flags=sorted({semantic_issue(n) for n in resolved_labels}) if resolved_labels is not None else ["source_labels_unresolved"],
                clinical_label_reviewed=False, independent=False)


def trace(manifest, config_path, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output/"source_summary.json").exists():
        raise ValueError("Source review exists; preserve it and choose a new output directory")
    config = json.loads(Path(config_path).read_text(encoding="utf8"))
    rows = read_rows(manifest)
    frames = [r for r in rows if r["kind"] == "frame"]
    index, exports = defaultdict(list), []
    for source in config["yolo_sources"]:
        root = Path(source["root"])
        if not (root/"data.yaml").is_file():
            exports.append(dict(id=source["id"], status="not_available_at_configured_path"))
            continue
        metadata = yaml.safe_load((root/"data.yaml").read_text(encoding="utf8"))
        names = metadata["names"]
        count = 0
        for split in ["train", "valid", "val", "test"]:
            for path in sorted((root/split/"images").glob("*.jpg")):
                index[path.name].append(dict(id=source["id"], path=path, split=split, names=names))
                count += 1
        exports.append(dict(id=source["id"], status="available", images=count,
                            source_metadata=metadata.get("roboflow", {}), class_names=names,
                            metadata_sha256=digest(root/"data.yaml"),
                            mapping={name: dict(merged_class=notebook_mapping(name), review_flag=semantic_issue(name)) for name in (names.values() if isinstance(names, dict) else names)}))
    with ThreadPoolExecutor(max_workers=8) as pool:
        traced = []
        for i, item in enumerate(pool.map(lambda row: trace_frame(row, index), frames), 1):
            traced.append(item)
            if i % 1000 == 0:
                print(f"Traced {i}/{len(frames)} frames", flush=True)
    (output/"frame_provenance.jsonl").write_text("".join(json.dumps(r)+"\n" for r in traced), encoding="utf8")
    by_id = {r["id"]: r for r in traced}
    queue = []
    for row in frames:
        t = by_id[row["id"]]
        if t["resolved_original_labels"] is None:
            continue
        for position, label in enumerate(t["resolved_original_labels"]):
            queue.append(dict(id=row["id"], split=row["split"], annotation_index=position,
                              source_label=label, merged_label=row["boxes"][position]["disease"],
                              flag=semantic_issue(label), decision="pending", reviewer="", evidence=""))
    with (output/"label_review_queue.csv").open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "split", "annotation_index", "source_label", "merged_label", "flag", "decision", "reviewer", "evidence"])
        writer.writeheader(); writer.writerows(queue)
    summary = dict(version=config["version"], baseline_manifest_sha256=digest(manifest),
                   config_sha256=digest(config_path), frames=len(frames),
                   matching="same basename, exact image SHA256, original annotation coordinates and notebook remapping",
                   provenance_status_counts=dict(Counter(r["provenance_status"] for r in traced)),
                   annotation_review_flags=dict(Counter(r["flag"] for r in queue)),
                   flags_by_split={s: dict(Counter(r["flag"] for r in queue if r["split"] == s)) for s in ["train", "val", "test"]},
                   source_exports=exports,
                   independence="not established; matches identify exported artifacts, not animals/farms or checkpoint training exposure")
    save_json(output/"source_summary.json", summary)
    coco_catalog(config["coco_sources"], output)
    print(json.dumps({k: v for k, v in summary.items() if k != "source_exports"}, indent=2))


def coco_catalog(sources, output):
    catalog, queue = [], []
    for source in sources:
        root = Path(source["root"])
        files = sorted(set(root.rglob("_annotations.coco.json")) | set(root.glob("result.json"))) if root.is_dir() else []
        for path in files:
            data = json.loads(path.read_text(encoding="utf8"))
            names = {c["id"]: c["name"] for c in data["categories"]}
            annotations = data.get("annotations", [])
            catalog.append(dict(source_id=source["id"], partition=path.parent.name, annotations_sha256=digest(path),
                images=len(data["images"]), annotations=len(annotations),
                annotations_with_masks=sum(bool(a.get("segmentation")) for a in annotations),
                categories=[dict(id=i, name=n, annotation_count=sum(a["category_id"] == i for a in annotations),
                                 review_flag=semantic_issue(n)) for i, n in names.items()],
                training_exposure="referenced_by_historical_notebook; exact replacement-checkpoint exposure unknown",
                independent=False, lesion_foreground_approved=False))
            for image in data["images"]:
                image_anns = [a for a in annotations if a["image_id"] == image["id"]]
                filename = image["file_name"]
                candidate = resolve_coco_image(path.parent, filename)
                queue.append(dict(source_id=source["id"], annotation_file=str(path), image_id=image["id"],
                    image=str(candidate), annotation_ids=[a["id"] for a in image_anns],
                    category_names=[names[a["category_id"]] for a in image_anns],
                    has_all_segmentations=bool(image_anns) and all(bool(a.get("segmentation")) for a in image_anns),
                    review_status="pending", mask_semantics=None, negative_reviewed=False, independent=False,
                    reviewer=None, evidence=None))
    (output/"mask_review_queue.jsonl").write_text("".join(json.dumps(r)+"\n" for r in queue), encoding="utf8")
    save_json(output/"mask_source_catalog.json", dict(sources=catalog, images_pending_review=len(queue),
        warning="Category names and polygons do not establish clinical severity or lesion foreground. No masks are approved or exported."))


def resolve_coco_image(directory, filename):
    """Resolve relocated exports locally without following stale ../ upload paths."""
    directory = Path(directory).resolve()
    normalized = filename.replace("\\", "/")
    basename = normalized.rsplit("/", 1)[-1]
    direct = directory/normalized
    options = [direct] if direct.resolve().is_relative_to(directory) else []
    options += [directory/basename, directory/"images"/basename]
    found = list(dict.fromkeys(p.resolve() for p in options if p.is_file()))
    if len(found) > 1:
        raise ValueError(f"Ambiguous COCO image basename: {basename}")
    return found[0] if found else directory/"images"/basename


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--sources", default=str(Path(__file__).with_name("review_sources.json")))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    trace(args.manifest, args.sources, args.output)
