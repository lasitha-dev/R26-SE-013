import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from .audit import digest, save_json
from .review import notebook_mapping, semantic_issue, resolve_coco_image, trace_frame
from .review_packet import mask_svg
from .roi_validation import annotation_box, prepare


def test_abnormal_is_flagged_as_the_actual_merge_error_without_inventing_diagnosis():
    assert notebook_mapping("abnormal") == "cattle"
    assert semantic_issue("abnormal") == "abnormal_defaulted_to_cattle"
    assert notebook_mapping("Mastitis_infected_udder") == "mastitis"
    assert semantic_issue("Cow_Feeding") == "behaviour_does_not_establish_clinical_health"


def test_normal_and_anatomical_polygons_are_not_silently_treated_as_lesions():
    assert semantic_issue("Mastitis-No") == "healthy_or_normal_annotation_not_lesion_foreground"
    assert semantic_issue("Udder") == "anatomical_or_object_target_not_verified_lesion"
    assert semantic_issue("fmdblisters") == "disease_or_symptom_label_requires_review"


def test_polygon_coordinates_become_an_envelope_instead_of_xywh():
    assert annotation_box("0 .1 .2 .9 .2 .9 .8 .1 .8".split(), (100, 100)) == pytest.approx([10, 20, 90, 80])
    assert annotation_box("0 .5 .5 .8 .6".split(), (100, 100)) == pytest.approx([10, 20, 90, 80])
    with pytest.raises(ValueError):
        annotation_box("0 nan .5 .4 .4".split(), (100, 100))
    with pytest.raises(ValueError):
        annotation_box("0 .1 .1 .2 .2 .3".split(), (100, 100))


def test_relocated_coco_upload_paths_use_local_basename_not_parent_traversal(tmp_path):
    root = tmp_path/"export"; (root/"images").mkdir(parents=True)
    local = root/"images"/"cow.jpg"; Image.new("RGB", (4, 4)).save(local)
    Image.new("RGB", (8, 8)).save(tmp_path/"cow.jpg")
    assert resolve_coco_image(root, r"..\..\uploads\cow.jpg") == local.resolve()
    (root/"cow.jpg").write_bytes(local.read_bytes())
    with pytest.raises(ValueError, match="Ambiguous"):
        resolve_coco_image(root, "cow.jpg")


def test_exact_source_matching_requires_image_and_annotation_evidence(tmp_path):
    index = {}
    for folder in ["merged", "source"]:
        root = tmp_path/folder/"train"
        (root/"images").mkdir(parents=True); (root/"labels").mkdir()
        Image.new("RGB", (10, 10)).save(root/"images"/"cow.jpg")
        (root/"labels"/"cow.txt").write_text("0 .5 .5 .8 .8\n")
    merged = tmp_path/"merged/train/images/cow.jpg"
    source = tmp_path/"source/train/images/cow.jpg"
    row = dict(id="cow", split="train", image=str(merged), sha256=digest(merged))
    index["cow.jpg"] = [dict(id="source", path=source, split="train", names=["abnormal"])]
    result = trace_frame(row, index)
    assert result["provenance_status"] == "unique_export_match"
    assert result["resolved_original_labels"] == ("abnormal",)
    assert result["independent"] is False and result["clinical_label_reviewed"] is False
    (source.parent.parent/"labels/cow.txt").write_text("0 .5 .5 .2 .2\n")
    result = trace_frame(row, index)
    assert result["provenance_status"] == "unresolved" and result["resolved_original_labels"] is None


def test_source_mask_preview_rejects_nonfinite_polygons(tmp_path):
    path = tmp_path/"cow.jpg"; Image.new("RGB", (10, 10)).save(path)
    with pytest.raises(ValueError, match="Nonfinite"):
        mask_svg(path, dict(width=10, height=10), [dict(segmentation=[[0, 0, 1, 1, float("nan"), 1]])])


def test_validation_geometry_preparation_never_reads_or_regenerates_test_images(tmp_path):
    parent = tmp_path/"merged/val/images"; parent.mkdir(parents=True)
    (parent.parent/"labels").mkdir()
    image = parent/"cow.jpg"; Image.new("RGB", (40, 40)).save(image)
    (parent.parent/"labels/cow.txt").write_text("0 .25 .25 .75 .25 .75 .75 .25 .75\n")
    crop = tmp_path/"cow_crop0.jpg"; Image.new("RGB", (7, 8)).save(crop)
    rows = [dict(id="frame", split="val", kind="frame", image=str(image), sha256=digest(image),
                 boxes=[dict(annotation_type="polygon_envelope", disease="cattle", bbox=[10, 10, 30, 30])]),
            dict(id="roi", split="val", kind="roi", image=str(crop), sha256=digest(crop), size=[7, 8], disease="cattle"),
            dict(id="never-read-test", split="test", kind="roi", image="nonexistent_test_crop0.jpg")]
    manifest = tmp_path/"baseline.jsonl"; manifest.write_text("".join(json.dumps(r)+"\n" for r in rows))
    cache = tmp_path/"cache"; cache.mkdir(); (cache/"predictions.jsonl").write_text("")
    save_json(cache/"run.json", dict(complete=True, manifest_sha256=digest(manifest),
              predictions_sha256=digest(cache/"predictions.jsonl"), checkpoint_sha256={"vit": "fixed"}))
    old_bytes = crop.read_bytes()
    out = tmp_path/"review"
    prepare(manifest, cache, out)
    prepared = [json.loads(line) for line in (out/"manifest.jsonl").read_text().splitlines()]
    assert len(prepared) == 1 and prepared[0]["size"] == [20, 20]
    assert prepared[0]["disease"] == "cattle" and prepared[0]["label_reviewed"] is False
    assert prepared[0]["independent"] is False
    assert crop.read_bytes() == old_bytes
    assert not (tmp_path/"nonexistent_test_crop0.jpg").exists()
    with pytest.raises(ValueError, match="exists"):
        prepare(manifest, cache, out)
