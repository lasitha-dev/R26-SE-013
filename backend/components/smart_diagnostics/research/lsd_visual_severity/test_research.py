"""Checks for split leakage, duplicate handling and the clinical scope boundary."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pytest
import torch
from PIL import Image, ImageOps

from audit import LABELS, assign_splits, duplicate_components, image_hashes, label_from_name
from model import SquarePad, build_model, image_transform, load_checkpoint


def row(name, label, pixel, phashes, dhashes):
    return {"source_name": name, "label": label, "pixel_sha256": pixel,
            "phashes": phashes, "dhashes": dhashes}


def test_mirrored_duplicates_and_reviewed_crop_stay_together():
    rng = np.random.default_rng(19)
    image = Image.fromarray(rng.integers(0, 256, (70, 90, 3), dtype=np.uint8))
    mirrored = ImageOps.mirror(image)
    a, b = image_hashes(image), image_hashes(mirrored)
    rows = [row("Mild_1.png", "mild", "a", *a),
            row("Mild_2.png", "mild", "b", *b),
            row("Mild_3.png", "mild", "c", [2**64-1]*4, [0]*4)]
    ids, edges = duplicate_components(rows, [["Mild_2.png", "Mild_3.png"]])
    assert len(set(ids)) == 1
    assert any(edge.get("method") == "pretraining_visual_content_audit" for edge in edges)


def test_duplicate_rule_accepts_any_orientation_satisfying_both_limits():
    rows = [row("a", "normal", "a", [0], [0]),
            row("b", "normal", "b", [15, 31], [511, 127])]
    ids, _ = duplicate_components(rows)
    assert ids[0] == ids[1]  # (4,9) fails; the other orientation (5,7) passes.


def test_unknown_labels_and_conflicts_are_not_guessed():
    assert label_from_name("lumpy/Normal_Skin_2.png") == "normal"
    with pytest.raises(ValueError):
        label_from_name("lumpy/1.png")
    with pytest.raises(ValueError, match="Conflicting"):
        assign_splits([{"group_id": "same", "label": label, "included": True}
                       for label in ("normal", "severe")])


def test_stratified_split_has_no_group_overlap_and_is_reproducible():
    rows = [{"group_id": f"{label}_{i}", "label": label, "included": True}
            for label in LABELS for i in range(15) for _ in range(2)]
    splits = assign_splits(rows)
    assert splits == assign_splits(list(reversed(rows)))
    for label in LABELS:
        assert {splits[r["group_id"]] for r in rows if r["label"] == label} == {"train", "validation", "test"}
    assert len(splits) == 45


def test_full_image_padding_preserves_borders_and_accepts_grayscale():
    image = Image.new("L", (30, 10), 200)
    padded = SquarePad()(image)
    assert padded.size == (30, 30)
    assert padded.getpixel((0, 10)) == (200, 200, 200)
    assert padded.getpixel((0, 0)) == (114, 114, 114)
    tensor = image_transform()(image)
    assert tensor.shape == (3, 224, 224)
    assert torch.isfinite(tensor).all()


def test_checkpoint_rejects_a_clinical_grading_target(tmp_path):
    path = tmp_path / "wrong.pt"
    torch.save({"labels": list(LABELS), "target": "clinical_severity"}, path)
    with pytest.raises(ValueError, match="compatible"):
        load_checkpoint(path)


@pytest.mark.parametrize("architecture", ["mobilenet_v3_small_linear", "mobilenet_v3_small_mlp"])
def test_checkpoint_roundtrip_preserves_research_logits(tmp_path, architecture):
    torch.set_num_threads(2)
    model = build_model(architecture).eval()
    path = tmp_path / "roundtrip.pt"
    torch.save({"labels": list(LABELS), "target": "visual_lsd_lesion_grade",
                "architecture": architecture, "model_state_dict": model.state_dict()}, path)
    loaded, _ = load_checkpoint(path)
    x = torch.zeros(1, 3, 224, 224)
    with torch.inference_mode():
        assert torch.equal(model(x), loaded(x))
        assert loaded(x).shape == (1, 3)
