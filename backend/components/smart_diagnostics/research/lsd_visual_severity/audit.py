"""Image inventory, duplicate grouping and a frozen split for the LSD pilot."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from scipy.fft import dctn
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
LABELS = ("normal", "mild", "severe")
SEED = 20261014


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def label_from_name(name: str) -> str:
    for part in Path(name).parts:
        value = part.lower()
        for label in LABELS:
            if re.match(rf"^{label}(?:[\d_ .-]|$)", value):
                return label
    raise ValueError(f"No documented normal/mild/severe filename prefix: {name}")


def image_hashes(image: Image.Image) -> tuple[list[int], list[int]]:
    """Perceptual hashes for original and mirrored variants; no extra dependency."""
    phashes, dhashes = [], []
    variants = (image, ImageOps.mirror(image), ImageOps.flip(image), ImageOps.flip(ImageOps.mirror(image)))
    for variant in variants:
        small = np.asarray(variant.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float32)
        low = dctn(small, type=2, norm="ortho")[:8, :8]
        pbits = low > np.median(low.flatten()[1:])
        pbits[0, 0] = False
        phashes.append(int.from_bytes(np.packbits(pbits).tobytes(), "big"))
        gray = np.asarray(variant.convert("L").resize((9, 8), Image.Resampling.LANCZOS))
        dhashes.append(int.from_bytes(np.packbits(gray[:, 1:] > gray[:, :-1]).tobytes(), "big"))
    return phashes, dhashes


def duplicate_components(records: list[dict], reviewed_groups: list[list[str]] | None = None) -> tuple[list[str], list[dict]]:
    parent = list(range(len(records)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[max(a, b)] = min(a, b)

    edges = []
    for i, a in enumerate(records):
        for j in range(i):
            b = records[j]
            exact = a["pixel_sha256"] == b["pixel_sha256"]
            distances = [
                ((a["phashes"][k] ^ b["phashes"][0]).bit_count(),
                 (a["dhashes"][k] ^ b["dhashes"][0]).bit_count())
                for k in range(len(a["phashes"]))
            ]
            eligible = [pair for pair in distances if pair[0] <= 6 and pair[1] <= 8]
            best = min(eligible or distances)
            if exact or eligible:
                union(i, j)
                edges.append({"a": a["source_name"], "b": b["source_name"],
                              "phash_distance": best[0], "dhash_distance": best[1],
                              "exact_pixels": exact, "labels": [a["label"], b["label"]]})
    by_name = {Path(row["source_name"]).name: i for i, row in enumerate(records)}
    for names in reviewed_groups or []:
        indices = [by_name[name] for name in names]
        for index in indices[1:]:
            anchor = indices[0]
            union(anchor, index)
            edges.append({"a": records[anchor]["source_name"], "b": records[index]["source_name"],
                          "method": "pretraining_visual_content_audit", "labels": [records[anchor]["label"], records[index]["label"]]})
    members = defaultdict(list)
    for i, row in enumerate(records):
        members[find(i)].append(row["pixel_sha256"])
    ids = {key: hashlib.sha256("|".join(sorted(set(values))).encode()).hexdigest()[:16]
           for key, values in members.items()}
    return [ids[find(i)] for i in range(len(records))], edges


def assign_splits(records: list[dict]) -> dict[str, str]:
    group_labels = {}
    for row in records:
        if row["included"]:
            if row["group_id"] in group_labels and group_labels[row["group_id"]] != row["label"]:
                raise ValueError("Conflicting labels must be excluded before splitting.")
            group_labels[row["group_id"]] = row["label"]
    groups = sorted(group_labels)
    counts = Counter(group_labels.values())
    if set(counts) != set(LABELS) or min(counts.values()) < 5:
        raise ValueError(f"Insufficient independent image groups for a stratified split: {dict(counts)}")
    trainval, test = train_test_split(groups, test_size=0.2, random_state=SEED,
                                    stratify=[group_labels[g] for g in groups])
    train, val = train_test_split(trainval, test_size=0.25, random_state=SEED,
                                 stratify=[group_labels[g] for g in trainval])
    return {group: name for name, subset in (("train", train), ("validation", val), ("test", test))
            for group in subset}


def contact_sheet(rows: list[dict], path: Path, title: str) -> None:
    from PIL import ImageDraw
    cols, tile_w, tile_h = 6, 170, 193
    canvas = Image.new("RGB", (cols * tile_w, 34 + ((len(rows) + cols - 1) // cols) * tile_h), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 8), title, fill="black")
    for i, row in enumerate(rows):
        with Image.open(ROOT / row["image_path"]) as image:
            thumb = ImageOps.contain(image.convert("RGB"), (166, 166))
        x, y = (i % cols) * tile_w, 34 + (i // cols) * tile_h
        canvas.paste(thumb, (x + (tile_w - thumb.width) // 2, y))
        draw.text((x + 3, y + 167), row["label"] + " " + Path(row["source_name"]).name[:20], fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def main() -> None:
    archive = ROOT / "data/raw/lumpy_unbalanced.zip"
    images = ROOT / "data/images"
    images.mkdir(parents=True, exist_ok=True)
    records, rejected, unknown, archive_metadata = [], [], [], []
    with zipfile.ZipFile(archive) as source:
        for info in sorted(source.infolist(), key=lambda item: item.filename):
            name = info.filename
            if info.is_dir() or "__MACOSX" in name or Path(name).name.startswith("."):
                continue
            if Path(name).suffix.lower() not in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
                archive_metadata.append(name)
                continue
            try:
                label = label_from_name(name)
            except ValueError:
                unknown.append(name)
                continue
            try:
                raw = source.read(info)
                with Image.open(io.BytesIO(raw)) as original:
                    original_mode = original.mode
                    original_format = original.format
                    image = ImageOps.exif_transpose(original).convert("RGB")
                    image.load()
                pixels = np.asarray(image)
                pixel_hash = hashlib.sha256(str(image.size).encode() + pixels.tobytes()).hexdigest()
                target = images / f"{pixel_hash}.png"
                if not target.exists():
                    image.save(target)
                phashes, dhashes = image_hashes(image)
                records.append({"source_name": name, "label": label, "label_index": LABELS.index(label),
                                "file_sha256": hashlib.sha256(raw).hexdigest(), "pixel_sha256": pixel_hash,
                                "image_path": target.relative_to(ROOT).as_posix(), "width": image.width,
                                "height": image.height, "original_mode": original_mode,
                                "original_format": original_format, "phashes": phashes, "dhashes": dhashes,
                                "pixel_std": round(float(pixels.std()), 3)})
            except Exception as exc:
                rejected.append({"name": name, "error": str(exc)})
    if unknown:
        save_json(ARTIFACTS / "unknown_label_files.json", unknown)
        raise ValueError(f"Unknown filename labels: {unknown[:10]}; inspect rather than guess a mapping.")
    print("Decoded counts:", dict(Counter(row["label"] for row in records)), flush=True)
    review_path = ROOT / "content_review.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    ids, edges = duplicate_components(records, review["same_source_groups"])
    grouped_labels = defaultdict(set)
    for row, group in zip(records, ids):
        row["group_id"] = group
        grouped_labels[group].add(row["label"])
    conflict_groups = {group for group, labels in grouped_labels.items() if len(labels) > 1}
    seen_pixels = set()
    for row in records:
        reason = review["excluded_files"].get(Path(row["source_name"]).name, "")
        if not reason and row["group_id"] in conflict_groups:
            reason = "conflicting_duplicate_group"
        if not reason and row["pixel_sha256"] in seen_pixels:
            reason = "exact_pixel_duplicate"
        seen_pixels.add(row["pixel_sha256"])
        row["included"] = not bool(reason)
        row["exclusion_reason"] = reason
    splits = assign_splits(records)
    for row in records:
        row["split"] = splits[row["group_id"]] if row["included"] else "excluded"
    fields = [key for key in records[0] if key not in ("phashes", "dhashes")]
    ARTIFACTS.mkdir(exist_ok=True)
    manifest = ARTIFACTS / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row[key] for key in fields} for row in records)
    summary = {
        "dataset": "10.5281/zenodo.11003967", "license": "CC-BY-4.0", "seed": SEED,
        "labels": LABELS, "raw_counts": dict(Counter(row["label"] for row in records)),
        "included_counts": dict(Counter(row["label"] for row in records if row["included"])),
        "excluded_counts": dict(Counter(row["exclusion_reason"] for row in records if not row["included"])),
        "conflicting_group_count": len(conflict_groups), "duplicate_edge_count": len(edges),
        "group_counts": dict(Counter({row["group_id"]: row["label"] for row in records if row["included"]}.values())),
        "split_counts": {split: dict(Counter(row["label"] for row in records if row["split"] == split))
                         for split in ("train", "validation", "test")},
        "dimensions": dict(Counter(f"{row['width']}x{row['height']}" for row in records)),
        "corrupt_images": rejected, "non_image_files": archive_metadata,
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "content_review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "content_review": review["policy"],
        "near_duplicate_rule": "Exact decoded RGB pixels OR pHash<=6 AND dHash<=8, including reflections, plus visually reviewed same-source links; transitive components stay in one split.",
        "split_rule": "Stratified 60/20/20 by image-similarity group. No oversampling or augmentation before splitting.",
        "scope": "LSD visual lesion severity only; clinical severity/stage remain veterinary assessments.",
        "limitations": ["No animal/farm identifiers; image-group separation is not proof of animal independence.",
                        "Filename labels are inherited, not independently regraded by a veterinarian.",
                        "Near-duplicate hashes can miss crops or same-animal photos and can merge similar scenes.",
                        "Normal means this dataset's normal-skin class, not freedom from all diseases.",
                        "No pixel lesion masks, temporal stages, or case-level clinical observations are provided."]
    }
    save_json(ARTIFACTS / "audit_summary.json", summary)
    save_json(ARTIFACTS / "duplicate_edges.json", edges)
    save_json(ARTIFACTS / "conflicting_groups.json", [
        {"group": group, "members": [{"file": r["source_name"], "label": r["label"]} for r in records if r["group_id"] == group]}
        for group in sorted(conflict_groups)])
    rng = np.random.default_rng(SEED)
    for label in LABELS:
        rows = [row for row in records if row["label"] == label]
        subset = [rows[i] for i in rng.choice(len(rows), min(len(rows), 30), replace=False)]
        contact_sheet(subset, ARTIFACTS / f"audit_{label}.jpg", f"DataHub audit sample: {label} (inherited labels)")
    conflicts = [row for row in records if row["group_id"] in conflict_groups]
    if conflicts:
        contact_sheet(conflicts[:60], ARTIFACTS / "audit_conflicts.jpg", "Excluded groups with conflicting inherited labels")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
