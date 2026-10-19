import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from .audit import assign_groups, digest, lineage_name, save_json
from .metrics import binary_metrics, classification, detection, group_bootstrap, selective_curve
from . import report
from ..implementations.lesion_segmenter import threshold_mask


def test_classifier_counts_detector_misses_and_absent_classes():
    result = classification(["mastitis", "mastitis", "cattle"], ["mastitis", None, "mastitis"])
    assert result["accuracy"] == pytest.approx(1/3)
    assert result["per_class"]["mastitis"]["recall"] == .5
    assert result["per_class"]["foot_and_mouth"]["recall"] is None
    assert result["confusion_matrix"][3][4] == 1
    assert not result["all_classes_supported"]


def test_calibration_penalizes_confident_wrong_prediction():
    result = classification(["mastitis"], ["cattle"], [[.99, 0, 0, .01]])
    assert result["ece_10_equal_width_bins"] == .99
    assert result["negative_log_likelihood"] > 4
    assert result["brier"] > 1.9
    with pytest.raises(ValueError):
        classification(["cattle"], ["cattle"], [[2, -1, 0, 0]])


def test_abstention_reports_coverage_and_class_support():
    curve = selective_curve(["cattle", "mastitis"], [[.99, 0, 0, .01], [.35, .25, .2, .2]], [.6], [0])
    assert curve[0]["coverage"] == .5
    assert curve[0]["metrics"]["accuracy"] == 1
    assert curve[0]["metrics"]["per_class"]["mastitis"]["support"] == 0


def test_detector_selected_roi_miss_is_not_rescued_by_lower_confidence_box():
    rows = [dict(boxes=[dict(disease="mastitis", bbox=[0, 0, 10, 10])])]
    predictions = [dict(detections=[dict(bbox=[30, 30, 50, 50], confidence=.9, class_name="mastitis"),
                                    dict(bbox=[0, 0, 10, 10], confidence=.8, class_name="mastitis"),
                                    dict(bbox=[0, 0, 10, 10], confidence=.7, class_name="mastitis")])]
    result = detection(rows, predictions)
    assert result["selected_roi_recall"] == 0
    assert result["recall"] == 1 and result["true_positive"] == 1
    assert result["false_positive"] == 2


def test_empty_masks_never_inflate_positive_dice():
    result = binary_metrics(np.zeros((2, 2)), np.array([[1, 0], [0, 0]]))
    assert result["dice"] is None and result["iou"] is None
    assert result["negative_false_positive_fraction"] == .25
    with pytest.raises(ValueError):
        binary_metrics(np.zeros((2, 2)), np.zeros((4, 4)))


def test_postprocessing_matches_connectivity_area_and_float_contract():
    probabilities = np.zeros((8, 8), dtype=np.float32)
    probabilities[1:4, 1:4] = .5001
    probabilities[4, 4] = .5001
    probabilities[7, 7] = .5001
    binary, count = threshold_mask(probabilities, .5, .1)
    assert binary.sum() == 10 and count == 1
    assert threshold_mask(probabilities, .5002, .1)[0].sum() == 0


def test_lineage_links_crops_and_augmented_siblings_without_claiming_identity():
    assert lineage_name("cow_jpg.rf.abc_crop7.jpg") == "cow_jpg"
    rows = [dict(id="a", split="train", sha256="a", pixel_sha256="a", lineage="cow", dhash="a"),
            dict(id="b", split="test", sha256="b", pixel_sha256="b", lineage="cow", dhash="b")]
    links, _ = assign_groups(rows)
    assert links["lineage"] == 1
    assert rows[0]["group_id"] == rows[1]["group_id"]
    assert not rows[1]["split_clean"]


def test_uncertainty_resamples_bundles_rather_than_individual_records():
    rows = [dict(group_id="one", value=0)]*20 + [dict(group_id="two", value=1)]*20
    result = group_bootstrap(rows, lambda r: np.mean([x["value"] for x in r]), repetitions=100)
    assert result["groups"] == 2 and result["lower"] == 0 and result["upper"] == 1


@pytest.fixture
def experiment(tmp_path):
    manifest = tmp_path/"manifest.jsonl"
    rows = [dict(id=split, split=split, kind="roi", disease="cattle", mask=None,
                 split_clean=True, perceptual_cross_split_candidate=False, group_id=split)
            for split in ["val", "test"]]
    manifest.write_text("".join(json.dumps(r)+"\n" for r in rows), encoding="utf8")
    predictions = tmp_path/"cache"; predictions.mkdir()
    path = predictions/"predictions.jsonl"
    path.write_text("".join(json.dumps(dict(id=r["id"], probabilities=[.97, .01, .01, .01]))+"\n" for r in rows), encoding="utf8")
    save_json(predictions/"run.json", dict(complete=True, manifest_sha256=digest(manifest),
              predictions_sha256=digest(path), checkpoint_sha256={"vit": "fixed"}))
    return manifest, predictions, tmp_path/"reports"


def test_validation_only_sees_validation_records_and_does_not_claim_threshold_validation(experiment, monkeypatch):
    manifest, predictions, output = experiment
    real = report.summarize
    def checked(rows, *args, **kwargs):
        assert {r["split"] for r in rows} == {"val"}
        return real(rows, *args, **kwargs)
    monkeypatch.setattr(report, "summarize", checked)
    report.validate(manifest, predictions, output)
    policy = json.loads((output/"frozen_policy.json").read_text())
    assert policy["mask_threshold"] == .5
    assert policy["mask_selection"].startswith("not validated")
    with pytest.raises(ValueError, match="already frozen"):
        report.validate(manifest, predictions, output)


def test_test_requires_unchanged_frozen_evidence_and_never_emits_threshold_sweeps(experiment):
    manifest, predictions, output = experiment
    report.validate(manifest, predictions, output)
    target = output/"test_report.json"
    report.test(manifest, predictions, output/"frozen_policy.json", target)
    result = json.loads(target.read_text())
    for scope in result["scopes"].values():
        assert "review_threshold_curve" not in scope["vit_original_crops"]
        assert len(scope["detector"]) == 1
    with pytest.raises(ValueError, match="exists"):
        report.test(manifest, predictions, output/"frozen_policy.json", target)
    with (predictions/"predictions.jsonl").open("a") as f:
        f.write("\n")
    with pytest.raises(ValueError, match="cache changed"):
        report.test(manifest, predictions, output/"frozen_policy.json", output/"tampered.json")


def test_missing_prediction_is_not_dropped_from_denominator(experiment):
    manifest, predictions, _ = experiment
    path = predictions/"predictions.jsonl"
    path.write_text(json.dumps(dict(id="val", probabilities=[1, 0, 0, 0]))+"\n")
    run = json.loads((predictions/"run.json").read_text())
    run["predictions_sha256"] = digest(path)
    save_json(predictions/"run.json", run)
    with pytest.raises(ValueError, match="Missing predictions"):
        report.load_inputs(manifest, predictions)


def test_independence_flag_cannot_override_group_leakage(experiment):
    manifest, predictions, _ = experiment
    rows = [json.loads(line) for line in manifest.read_text().splitlines()]
    for row in rows:
        row.update(group_id="same-animal", independent=True)
    manifest.write_text("".join(json.dumps(r)+"\n" for r in rows))
    with pytest.raises(ValueError, match="across partitions"):
        report.load_inputs(manifest, predictions)


def test_masks_require_review_and_explicit_reviewed_negatives(tmp_path):
    mask = tmp_path/"mask.png"; Image.new("L", (4, 4)).save(mask)
    cache = tmp_path/"prob.npy"; np.save(cache, np.zeros((4, 4)))
    row = dict(id="case", group_id="case", mask=str(mask), disease="cattle")
    prediction = {"case": dict(mask_probabilities=cache.name, mask_sha256=digest(mask))}
    with pytest.raises(ValueError, match="meaning/review"):
        report.mask_results([row], prediction, tmp_path, .5, 0)
    row.update(mask_reviewed=True, mask_semantics="visible_lesion_foreground")
    with pytest.raises(ValueError, match="reviewed negative"):
        report.mask_results([row], prediction, tmp_path, .5, 0)
    row["negative_reviewed"] = True
    result = report.mask_results([row], prediction, tmp_path, .5, 0)
    assert result["positive_images"] == 0 and result["reviewed_negative_images"] == 1
    assert result["disease_macro_dice"] is None


@pytest.mark.parametrize("diseases, expected", [
    (["foot_and_mouth", "lumpy_skin", "mastitis", "cattle"], .3),
    (["foot_and_mouth", "lumpy_skin", "cattle"], .5),
])
def test_mask_selection_requires_all_diseases_and_uses_validation_probabilities(tmp_path, diseases, expected):
    rows, predictions = [], []
    cache = tmp_path/"cache"; cache.mkdir()
    for index, disease in enumerate(diseases):
        pixels = np.zeros((4, 4), dtype=np.uint8)
        probability = np.full((4, 4), .2, dtype=np.float32)
        if disease != "cattle":
            pixels[1, 1] = 255
            probability[1, 1] = .35
        mask = tmp_path/f"{index}.png"; Image.fromarray(pixels).save(mask)
        np.save(cache/f"{index}.npy", probability)
        row = dict(id=str(index), split="val", kind="roi", group_id=str(index), disease=disease,
                   split_clean=True, independent=True, training_exclusion_evidence="synthetic test fixture",
                   mask=str(mask), mask_reviewed=True, mask_semantics="visible_lesion_foreground", negative_reviewed=disease=="cattle")
        rows.append(row)
        p = [0., 0., 0., 0.]; p[report.CLASSES.index(disease)] = 1.
        predictions.append(dict(id=str(index), probabilities=p, mask_probabilities=f"{index}.npy", mask_sha256=digest(mask)))
    manifest = tmp_path/"manifest.jsonl"
    manifest.write_text("".join(json.dumps(r)+"\n" for r in rows))
    path = cache/"predictions.jsonl"; path.write_text("".join(json.dumps(r)+"\n" for r in predictions))
    save_json(cache/"run.json", dict(complete=True, manifest_sha256=digest(manifest), predictions_sha256=digest(path), checkpoint_sha256={"segmenter": "synthetic"}))
    report.validate(manifest, cache, tmp_path/"reports")
    policy = json.loads((tmp_path/"reports/frozen_policy.json").read_text())
    assert policy["mask_threshold"] == expected
    assert policy["mask_selection"].startswith("validation macro" if expected == .3 else "not validated")
    assert policy["deployment"].startswith("offline candidate only")
