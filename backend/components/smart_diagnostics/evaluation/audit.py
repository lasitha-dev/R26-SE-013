"""Read-only audit of the existing YOLO/ImageFolder datasets, never re-split them."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageOps

CLASSES = ["cattle", "foot_and_mouth", "lumpy_skin", "mastitis"]
YOLO_CLASSES = ["cattle", "lumpy_skin", "foot_and_mouth", "mastitis"]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf8")


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf8").splitlines() if line.strip()]


def inspect_image(row):
    path = Path(row["image"])
    with Image.open(path) as original:
        rgb = ImageOps.exif_transpose(original).convert("RGB")
        pixels = np.asarray(rgb)
        small = np.asarray(rgb.convert("L").resize((9, 8)))
        perceptual = np.packbits(small[:, 1:] > small[:, :-1]).tobytes().hex()
        row.update(size=list(rgb.size), sha256=digest(path),
                   pixel_sha256=hashlib.sha256(str(rgb.size).encode() + pixels.tobytes()).hexdigest(),
                   dhash=perceptual)
    return row


def lineage_name(path):
    """Conservative candidate lineage, not proof of identical animals or sources."""
    return re.sub(r"_crop\d+$", "", Path(path).stem).split(".rf.")[0]


def assign_groups(rows):
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        parent[find(a)] = find(b)

    evidence = Counter()
    for key in ["sha256", "pixel_sha256", "lineage"]:
        seen = {}
        for i, row in enumerate(rows):
            value = row[key]
            if value in seen:
                j = seen[value]
                if rows[j]["split"] != row["split"]:
                    evidence[key] += 1
                union(i, j)
            else:
                seen[value] = i
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[find(i)].append(row)
    for members in groups.values():
        group = min(r["id"] for r in members)
        splits = sorted({r["split"] for r in members})
        for row in members:
            row.update(group_id=group, group_splits=splits, split_clean=len(splits) == 1)
    # Exact dHash matches are only review candidates. Do not silently equate similar
    # textures or different animals, and do not claim exhaustive near-duplicate detection.
    hashes = defaultdict(set)
    for row in rows:
        hashes[row["dhash"]].add(row["split"])
    near = {h for h, splits in hashes.items() if len(splits) > 1}
    for row in rows:
        row["perceptual_cross_split_candidate"] = row["dhash"] in near
    return dict(evidence), len(near)


def audit(yolo_root, vit_root, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.jsonl").exists():
        raise ValueError("Audit output already exists; use a new run directory to preserve evidence.")
    rows = []
    for kind, root in [("frame", Path(yolo_root)), ("roi", Path(vit_root))]:
        for split in ["train", "val", "test"]:
            folder = root / split / "images" if kind == "frame" else root / split
            if not folder.is_dir():
                raise ValueError(f"Missing dataset partition: {folder}")
            for path in sorted(folder.rglob("*.jpg")):
                boxes, disease = None, None
                if kind == "roi":
                    disease = path.parent.name
                    if disease not in CLASSES:
                        raise ValueError(f"Unknown class directory: {path.parent}")
                else:
                    label_path = root / split / "labels" / (path.stem + ".txt")
                    boxes = []
                    for line in label_path.read_text(encoding="utf8").splitlines():
                        parts = line.split()
                        if len(parts) != 5 and (len(parts) < 7 or len(parts) % 2 != 1):
                            raise ValueError(f"Invalid YOLO box: {label_path}")
                        class_id = int(parts[0])
                        values = [float(v) for v in parts[1:]]
                        if class_id not in range(4) or not np.isfinite(values).all() or not all(-1e-6 <= v <= 1+1e-6 for v in values):
                            raise ValueError(f"Invalid YOLO coordinates: {label_path}")
                        if len(parts) == 5:
                            box = dict(disease=YOLO_CLASSES[class_id], xywh_normalized=values, annotation_type="box")
                        else:
                            points = np.asarray(values).reshape(-1, 2)
                            lo, hi = points.min(axis=0), points.max(axis=0)
                            box = dict(disease=YOLO_CLASSES[class_id], xywh_normalized=[*((lo+hi)/2), *(hi-lo)], annotation_type="polygon_envelope")
                        if min(box["xywh_normalized"][2:]) <= 0:
                            raise ValueError(f"Degenerate annotation: {label_path}")
                        boxes.append(box)
                    labels = {b["disease"] for b in boxes}
                    disease = next(iter(labels)) if len(labels) == 1 else None
                identifier = hashlib.sha256((kind + str(path.resolve())).encode()).hexdigest()[:20]
                rows.append(dict(id=identifier, image=str(path.resolve()), kind=kind, split=split,
                                 disease=disease, boxes=boxes, lineage=lineage_name(path),
                                 independent=False, animal_id=None, farm_id=None, mask=None,
                                 label_basis="ImageFolder label" if kind == "roi" else "uniform box labels; ambiguous images have no case label",
                                 source="merged Roboflow sources; per-image source unresolved"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(inspect_image, rows))
    for row in rows:
        if row["boxes"] is not None:
            w, h = row["size"]
            for box in row["boxes"]:
                x, y, bw, bh = box.pop("xywh_normalized")
                box["bbox"] = [max(0, (x-bw/2)*w), max(0, (y-bh/2)*h), min(w, (x+bw/2)*w), min(h, (y+bh/2)*h)]
    evidence, near_count = assign_groups(rows)
    manifest = output / "manifest.jsonl"
    manifest.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf8")
    summary = dict(status="legacy_split_audit_not_independent_validation", manifest_sha256=digest(manifest),
                   records=len(rows), cross_split_links=evidence, cross_split_dhash_candidates=near_count,
                   limitations=["No verified animal/farm IDs or source holdout.",
                                "Filename lineage can overgroup unrelated generic names; exclusions are conservative.",
                                "Exact dHash matches need review; transformed near-duplicates can remain undetected.",
                                "Notebook label remapping defaults unmatched names to cattle; labels need semantic review.",
                                "YOLO polygons exist but their foreground semantics are unreviewed; they are NOT accepted as lesion masks.",
                                "ViT creation notebook treats the first four polygon coordinates as xywh boxes; affected crops require review.",
                                "Audit cannot establish which examples the final checkpoint saw, or whether test results influenced its selection."],
                   partitions={})
    summary["annotation_types"] = dict(Counter(b["annotation_type"] for r in rows for b in (r["boxes"] or [])))
    for kind in ["frame", "roi"]:
        for split in ["train", "val", "test"]:
            subset = [r for r in rows if r["kind"] == kind and r["split"] == split]
            summary["partitions"][f"{kind}_{split}"] = dict(total=len(subset),
                cross_split_group_excluded=sum(not r["split_clean"] for r in subset),
                clean_without_dhash_flag=sum(r["split_clean"] and not r["perceptual_cross_split_candidate"] for r in subset),
                class_counts=dict(Counter(r["disease"] or "ambiguous_or_unlabelled" for r in subset)))
    save_json(output / "audit.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yolo-root", required=True)
    parser.add_argument("--vit-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    audit(args.yolo_root, args.vit_root, args.output)
