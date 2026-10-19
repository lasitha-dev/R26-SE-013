"""Local, static annotation-review material; exports no approved clinical labels."""
import argparse
import base64
from collections import Counter, defaultdict
import html
import json
import mimetypes
from pathlib import Path
import math

from .audit import digest, read_rows, save_json


def embedded_image(path):
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def mask_svg(image_path, image, annotations):
    width, height = int(image["width"]), int(image["height"])
    if min(width, height) <= 0:
        raise ValueError("Invalid reference image dimensions")
    pieces = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Original source polygons over image"><image width="{width}" height="{height}" href="{embedded_image(image_path)}"/>']
    for annotation in annotations:
        segments = annotation.get("segmentation")
        if not isinstance(segments, list):
            continue
        for polygon in segments:
            if not isinstance(polygon, list) or len(polygon) < 6 or len(polygon) % 2:
                continue
            numbers = [float(value) for value in polygon]
            if not all(math.isfinite(value) for value in numbers):
                raise ValueError("Nonfinite reference polygon")
            points = " ".join(f"{x},{y}" for x,y in zip(numbers[::2], numbers[1::2]))
            pieces.append(f'<polygon points="{points}" fill="rgba(255,210,0,.18)" stroke="#ffd000" stroke-width="{max(width,height)/250}"/>')
    return "".join(pieces)+"</svg>"


def packet(manifest, source_review, roi_experiment, output):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    if (output/"index.html").exists():
        raise ValueError("Review packet exists; preserve prior decisions")
    rows = read_rows(manifest)
    source_summary = json.loads((Path(source_review)/"source_summary.json").read_text(encoding="utf8"))
    if source_summary["baseline_manifest_sha256"] != digest(manifest):
        raise ValueError("Source review does not match the baseline manifest")
    provenance = {r["id"]: r for r in read_rows(Path(source_review)/"frame_provenance.jsonl")}
    frames = {(r["split"], Path(r["image"]).stem): r for r in rows if r["kind"] == "frame"}
    corrected = {r["id"]: r for r in read_rows(Path(roi_experiment)/"manifest.jsonl")}
    review_rows = []
    for old in rows:
        row = dict(corrected.get(old["id"], old))
        parent = old
        if old["kind"] == "roi":
            stem, index = Path(old["image"]).stem.rsplit("_crop", 1)
            parent = frames[(old["split"], stem)]
            row["parent_frame_id"] = parent["id"]
            row["annotation_index"] = int(index)
        p = provenance[parent["id"]]
        row.update(source_provenance_status=p["provenance_status"], source_candidates=p["candidates"],
                   source_original_labels=p["resolved_original_labels"], source_semantic_flags=p["semantic_flags"],
                   clinical_label_reviewed=False, independent=False, threshold_selection_eligible=False,
                   review_status="pending", reviewer=None, review_evidence=None)
        review_rows.append(row)
    review_manifest = output/"review_manifest.jsonl"
    review_manifest.write_text("".join(json.dumps(r)+"\n" for r in review_rows), encoding="utf8")
    groups = defaultdict(list)
    for row in rows:
        if row["kind"] == "frame":
            groups[row["lineage"]].append(row)
    lineage_queue = []
    for lineage, members in groups.items():
        splits = sorted({r["split"] for r in members})
        if len(splits) < 2:
            continue
        known_sources = sorted({c["source_id"] for r in members for c in provenance[r["id"]]["candidates"] if c["annotations_and_mapping_match"]})
        lineage_queue.append(dict(lineage=lineage, image_ids=[r["id"] for r in members], splits=splits,
                                  matched_exports=known_sources, review_status="pending", decision=None,
                                  warning="Same source/name is a candidate; distinct sources do not rule out reuse of the same photograph."))
    (output/"lineage_review_queue.jsonl").write_text("".join(json.dumps(r)+"\n" for r in lineage_queue), encoding="utf8")

    # Select fixed category examples, without predictions or clinical grade inference.
    masks = read_rows(Path(source_review)/"mask_review_queue.jsonl")
    selected, seen, documents = [], set(), {}
    for row in masks:
        if not row["has_all_segmentations"] or not Path(row["image"]).is_file():
            continue
        for category in sorted(set(row["category_names"])):
            key = row["source_id"], category
            if key in seen:
                continue
            seen.add(key); selected.append((row, category))
    cards = []
    sample_index = []
    for row, category in selected:
        path = row["annotation_file"]
        if path not in documents:
            documents[path] = json.loads(Path(path).read_text(encoding="utf8"))
        data = documents[path]
        image = next(i for i in data["images"] if i["id"] == row["image_id"])
        annotations = [a for a in data["annotations"] if a["image_id"] == row["image_id"]]
        title = row["source_id"]+" / "+category
        preview_id = str(len(sample_index))
        sample_index.append(dict(id=preview_id, source_id=row["source_id"], category=category,
                                 image_id=row["image_id"], annotation_file_sha256=digest(path)))
        cards.append(f'<article data-review="{preview_id}"><h3>{html.escape(title)}</h3><p>All polygons on this source image are shown. Labels: {html.escape(", ".join(row["category_names"]))}</p>'+mask_svg(row["image"], image, annotations)+
                     '<label>Foreground meaning <select><option value="pending">Pending</option><option value="visible_symptom_candidate">Visible symptom candidate</option><option value="anatomy_or_whole_animal">Anatomy / whole animal</option><option value="normal_region">Normal region</option><option value="uncertain">Uncertain</option></select></label><label>Evidence <input placeholder="Describe what the polygons outline"></label></article>')
    changed = [r for r in corrected.values() if r["geometry_changed"]]
    originals = {r["id"]: r for r in rows}
    examples = []
    for disease in sorted({r["disease"] for r in changed}):
        for row in [r for r in changed if r["disease"] == disease][:3]:
            old = originals[row["id"]]
            examples.append(f'<article><h3>{html.escape(disease)} / {row["id"]}</h3><div class="pair"><figure><img src="{embedded_image(old["image"])}"><figcaption>Original saved crop {old["size"]}</figcaption></figure><figure><img src="{embedded_image(row["image"])}"><figcaption>Annotation envelope {row["size"]}</figcaption></figure></div><p>Geometry correction only; inherited diagnosis and ROI meaning remain unreviewed.</p></article>')
    metadata = json.dumps(sample_index).replace("<", "\\u003c")
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Smart Diagnostics annotation review</title><style>body{font:16px system-ui;max-width:1200px;margin:30px auto;padding:16px;background:#f3f5f8;color:#15202b}article{background:white;padding:18px;margin:18px 0;border:1px solid #ccd4de;break-inside:avoid}svg{display:block;width:100%;max-height:600px;background:#18212b}label{display:block;margin:12px 0}input{width:75%;padding:8px}select,button{padding:9px}.pair{display:flex;gap:20px}.pair figure{flex:1}.pair img{width:100%;max-height:400px;object-fit:contain}button{background:#154a68;color:white;border:0}</style><h1>Annotation meaning and crop review</h1><p>Local research packet. Source labels are inherited. No examples are approved clinical references, and this page does not change application data. Yellow outlines show original annotations, not model predictions. Decisions exported here are review notes, not veterinary sign-off or training-exclusion proof.</p><label>Reviewer name <input id="reviewer"></label><button id="export">Export sample review notes</button><h2>Source-mask examples</h2>'''+"".join(cards)+"<h2>Validation crop examples</h2>"+"".join(examples)+f'''<script>const samples={metadata};document.getElementById('export').onclick=()=>{{const result={{status:'notes_require_verification',reviewer:document.getElementById('reviewer').value,clinical_approval:false,independence_established:false,samples:[...document.querySelectorAll('[data-review]')].map(e=>({{...samples[Number(e.dataset.review)],decision:e.querySelector('select').value,evidence:e.querySelector('input').value}}))}};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{{type:'application/json'}}));a.download='annotation-review-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}};</script></html>'''
    (output/"index.html").write_text(document, encoding="utf8")
    save_json(output/"packet_summary.json", dict(records=len(review_rows), review_manifest_sha256=digest(review_manifest),
        cross_split_lineages_pending=len(lineage_queue), cross_split_lineage_frames=sum(len(g["image_ids"]) for g in lineage_queue),
        source_mask_examples=len(selected), crop_examples=len(examples), mask_images_pending=len(masks),
        clinical_labels_approved=0, lesion_masks_approved=0, independent=False,
        html_sha256=digest(output/"index.html"), baseline_manifest_sha256=digest(manifest)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-review", required=True)
    parser.add_argument("--roi-experiment", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    packet(args.manifest, args.source_review, args.roi_experiment, args.output)
