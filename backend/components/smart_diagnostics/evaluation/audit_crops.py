"""Check saved ViT crop dimensions against the notebook's polygon parsing error."""
import argparse
from collections import Counter
from pathlib import Path
from .audit import read_rows, save_json


def audit_crops(manifest, output):
    if Path(output).exists():
        raise ValueError("Crop audit output exists; preserve the previous evidence")
    rows = read_rows(manifest)
    frames = {(r["split"], Path(r["image"]).stem): r for r in rows if r["kind"] == "frame"}
    labels, counts, examples = {}, Counter(), []
    for row in rows:
        if row["kind"] != "roi":
            continue
        stem, index = Path(row["image"]).stem.rsplit("_crop", 1)
        index = int(index)
        parent = frames.get((row["split"], stem))
        if not parent or index >= len(parent["boxes"]):
            counts["missing_parent_annotation"] += 1
            continue
        annotation = parent["boxes"][index]
        if annotation["annotation_type"] != "polygon_envelope":
            continue
        counts["polygon_parent_saved_crops"] += 1
        counts["class_"+row["disease"]] += 1
        counts["split_"+row["split"]] += 1
        if parent["id"] not in labels:
            path = Path(parent["image"])
            labels[parent["id"]] = (path.parent.parent/"labels"/(path.stem+".txt")).read_text().splitlines()
        parts = labels[parent["id"]][index].split()
        x, y, w, h = map(float, parts[1:5])
        iw, ih = parent["size"]
        incorrect = [int(min(iw, (x+w/2)*iw))-int(max(0, (x-w/2)*iw)),
                     int(min(ih, (y+h/2)*ih))-int(max(0, (y-h/2)*ih))]
        box = annotation["bbox"]
        correct = [int(box[2])-int(box[0]), int(box[3])-int(box[1])]
        counts["saved_size_matches_notebook_polygon_misparse"] += row["size"] == incorrect
        counts["saved_size_matches_polygon_envelope"] += row["size"] == correct
        if row["split"] == "test" and len(examples) < 3:
            examples.append(dict(filename=Path(row["image"]).name, actual_size=row["size"],
                                 notebook_misparsed_size=incorrect, polygon_envelope_size=correct))
    save_json(output, dict(counts=dict(counts), examples=examples,
        interpretation="Dimension agreement confirms the notebook parsing issue for these crops; no labels/images were modified."))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    audit_crops(args.manifest, args.output)
