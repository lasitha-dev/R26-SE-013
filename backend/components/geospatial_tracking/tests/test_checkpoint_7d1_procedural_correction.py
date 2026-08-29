"""Checkpoint 7D.1 Part 12: procedural-exposure-correction tests
(7D1-EXP-01..04, 7D1-REC-01..02, 7D1-COV-01, 7D1-BOOT-01). Asserts
against the REAL persisted checkpoint artifacts (never hardcoded counts
in reusable library logic) -- skipped gracefully if not present."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_OUT_DIR = _REPO_ROOT / "local_data" / "model_evaluation" / "7d"

_DISCLOSURE = _OUT_DIR / "heldout_exposure_disclosure.json"
_SANITY = _OUT_DIR / "pre_final_40_origin_sanity_exposure.json"
_PROCEDURAL = _OUT_DIR / "procedural_exposure_correction_7d1.json"
_MANIFEST = _OUT_DIR / "pre_evaluation_freeze_manifest.json"
_PARTICIPATION = _OUT_DIR / "heldout_origin_participation_audit_7d1.json"
_TARGET_RECORDS = _OUT_DIR / "target_evaluation_records.json"
_HELDOUT_METRICS = _OUT_DIR / "heldout_metrics.json"

_REQUIRED = (_DISCLOSURE, _SANITY, _PROCEDURAL, _MANIFEST, _PARTICIPATION, _TARGET_RECORDS, _HELDOUT_METRICS)
_ALL_PRESENT = all(p.exists() for p in _REQUIRED)
_SKIP_REASON = "real 7D.1 persisted artifacts not present in this environment"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d1_exp_01_disclosure_explicitly_records_the_40_origin_sanity_run():
    disclosure = _load(_DISCLOSURE)
    blob = json.dumps(disclosure)
    assert "40" in blob
    assert "pre_final_predictive_subset_exposure_disclosed" in disclosure
    assert "heldout[:40]" in disclosure["pre_final_predictive_subset_exposure_disclosed"]


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d1_exp_02_evaluation_label_excludes_forbidden_terms():
    disclosure = _load(_DISCLOSURE)
    label = disclosure["accurate_label"]
    for forbidden in ("SINGLE_SHOT", "BLIND", "UNTOUCHED", "UNSEEN", "EXTERNAL_VALIDATION"):
        assert forbidden not in label
    assert "PRE_FINAL_PREDICTIVE_SUBSET_EXPOSURE_DISCLOSED" in label


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d1_exp_03_final_manifest_not_claimed_to_predate_sanity_exposure():
    manifest = _load(_MANIFEST)
    assert manifest.get("manifest_scope_classification") == "FINAL_FULL_RUN_FREEZE_MANIFEST"
    note = manifest.get("manifest_scope_note", "").lower()
    assert "not before all" in note


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d1_exp_04_sanity_exposure_metrics_preserved_exactly():
    sanity = _load(_SANITY)
    pooled = sanity["pooled"]
    assert pooled["n_origins"] == 10
    assert pooled["mean_target_percentile"] == 84.76312352114739
    assert pooled["top5_capture_rate"] == 0.25
    assert pooled["top10_capture_rate"] == 0.38333333333333336
    assert sanity["ready"] == 40 and sanity["blocked"] == 0
    assert sanity["target_scope"] == {"n_all_d1d7_target_rows": 43, "n_within": 14, "n_outside": 29, "n_unresolved": 0}


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d1_rec_01_229_ready_origins_reconcile_exactly():
    audit = _load(_PARTICIPATION)
    assert audit["arithmetic_check_229_eq_ready_plus_blocked"] is True
    assert audit["arithmetic_check_ready_eq_contributing_plus_zero_target"] is True
    assert audit["n_heldout_origins"] == 229
    assert audit["n_blocked"] == 0
    assert audit["n_primary_contributing_origins"] + audit["n_zero_primary_target_origins"] == audit["n_ready"]


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d1_rec_02_contributing_origin_ids_equal_target_evaluation_records_origins():
    audit = _load(_PARTICIPATION)
    assert audit["contributing_set_matches_persisted_target_evaluation_records"] is True

    records = _load(_TARGET_RECORDS)
    record_origin_ids = {r["forecast_origin_id"] for r in records}
    participation_contributing_ids = {r["forecast_origin_id"] for r in audit["rows"] if r["participates_in_primary_metric"]}
    assert participation_contributing_ids == record_origin_ids


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d1_cov_01_zero_target_ready_origins_not_falsely_claimed_covered():
    audit = _load(_PARTICIPATION)
    zero_target_rows = [r for r in audit["rows"] if r["status"] == "READY" and not r["participates_in_primary_metric"]]
    assert len(zero_target_rows) == audit["n_zero_primary_target_origins"]
    for r in zero_target_rows:
        assert r["n_within"] == 0  # no primary target -> no C0 coverage record was ever produced for it


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d1_boot_01_target_event_sensitivity_reports_mean_top5_and_top10_cis():
    metrics = _load(_HELDOUT_METRICS)
    boot = metrics["bootstrap_by_target_event"]
    for key in ("mean_target_percentile_ci", "top5_capture_rate_ci", "top10_capture_rate_ci"):
        ci = boot[key]
        assert ci is not None
        assert ci["lower"] < ci["upper"]
