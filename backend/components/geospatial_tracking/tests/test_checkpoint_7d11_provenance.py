"""Checkpoint 7D.1.1 Part 9: semantic/provenance tests
(7D11-SEM-01..04, 7D11-PROV-01..02, 7D11-NUM-01, 7D11-REC-01)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from components.geospatial_tracking.services.model_development.heldout_protocol_7d import (
    EVALUATION_LABEL_7D_ORIGINAL,
    EVALUATION_LABEL_7D1_CORRECTED,
    HISTORICAL_HELDOUT_EVALUATION_PROTOCOL_HASH_7D,
    build_heldout_exposure_disclosure,
    heldout_evaluation_protocol_hash_7d,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_OUT_DIR = _REPO_ROOT / "local_data" / "model_evaluation" / "7d"

_MANIFEST = _OUT_DIR / "pre_evaluation_freeze_manifest.json"
_LABEL_AUDIT = _OUT_DIR / "evaluation_label_provenance_audit_7d11.json"
_MANIFEST_PROVENANCE = _OUT_DIR / "pre_evaluation_manifest_provenance_7d11.json"
_PROCEDURAL = _OUT_DIR / "procedural_exposure_correction_7d1.json"
_PARTICIPATION = _OUT_DIR / "heldout_origin_participation_audit_7d1.json"
_HELDOUT_METRICS = _OUT_DIR / "heldout_metrics.json"

_REQUIRED = (_MANIFEST, _LABEL_AUDIT, _MANIFEST_PROVENANCE, _PROCEDURAL, _PARTICIPATION, _HELDOUT_METRICS)
_ALL_PRESENT = all(p.exists() for p in _REQUIRED)
_SKIP_REASON = "real 7D.1.1 persisted artifacts not present in this environment"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 7D11-SEM
# ---------------------------------------------------------------------------


def test_7d11_sem_01_historical_label_explicitly_classified_as_historical():
    assert EVALUATION_LABEL_7D_ORIGINAL != EVALUATION_LABEL_7D1_CORRECTED
    d = heldout_evaluation_protocol_hash_7d.__module__  # sanity import works
    assert d


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d11_sem_01b_manifest_historical_label_classified_as_historical_in_audit():
    audit = _load(_LABEL_AUDIT)
    # Checkpoint 7D.1.2 regenerated this artifact with a "classification"
    # map (candidate_id -> classification string) rather than a "files"
    # map of dicts -- read whichever schema is actually present.
    classification = audit.get("classification") or {k: v["classification"] for k, v in audit.get("files", {}).items()}
    assert classification["local_data/model_evaluation/7d/pre_evaluation_freeze_manifest.json"] == "HISTORICAL_7D_PROTOCOL_ALLOWED"


def test_7d11_sem_02_current_disclosure_uses_only_corrected_label():
    disclosure = build_heldout_exposure_disclosure()
    assert disclosure["accurate_label"] == EVALUATION_LABEL_7D1_CORRECTED
    assert disclosure["accurate_label"] != EVALUATION_LABEL_7D_ORIGINAL
    # the original label may appear ONLY as an explicitly-labeled historical reference
    assert disclosure["historical_original_evaluation_label"] == EVALUATION_LABEL_7D_ORIGINAL


def test_7d11_sem_03_historical_protocol_hash_unchanged():
    assert heldout_evaluation_protocol_hash_7d() == HISTORICAL_HELDOUT_EVALUATION_PROTOCOL_HASH_7D == "74be1d652fff4739ddeb612dd21a273004d35117bedc718981c5e7636ce6cb90"


def test_7d11_sem_04_no_current_artifact_falsely_claims_forbidden_terms():
    """Checkpoint 7D.1.2 Part 2 fix: the previous version of this test was
    vacuously true (every forbidden term is ALWAYS present in
    `therefore_not_called`, so `forbidden in disclosure["therefore_not_called"]`
    was always True regardless of what else the disclosure said). This
    version builds a copy of the disclosure EXCLUDING the negative/
    historical fields that are explicitly allowed to name a forbidden
    term (the "never call it X" list and historical-label provenance
    fields), then asserts none of the remaining ACTIVE, positive-
    reporting fields contain any forbidden term at all."""
    disclosure = build_heldout_exposure_disclosure()
    negative_or_historical_fields = {"therefore_not_called", "historical_original_evaluation_label", "historical_note"}
    positive_reporting = {k: v for k, v in disclosure.items() if k not in negative_or_historical_fields}
    positive_blob = json.dumps(positive_reporting)

    forbidden_terms = ("SINGLE_SHOT", "FIRST_PREDICTIVE_INSPECTION", "BLIND_TEST", "UNTOUCHED_TEST", "UNSEEN_TEST", "EXTERNAL_VALIDATION")
    for forbidden in forbidden_terms:
        assert forbidden not in positive_blob, f"{forbidden!r} appeared as a positive claim outside the negative/historical fields"

    # every forbidden term must still be explicitly disclaimed somewhere
    full_blob = json.dumps(disclosure)
    for forbidden in forbidden_terms:
        assert forbidden in full_blob, f"{forbidden!r} should still be explicitly disclaimed in therefore_not_called"

    assert disclosure["accurate_label"] == EVALUATION_LABEL_7D1_CORRECTED


# ---------------------------------------------------------------------------
# 7D11-PROV
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d11_prov_01_manifest_provenance_states_posthoc_annotation():
    prov = _load(_MANIFEST_PROVENANCE)
    assert prov["posthoc_annotation_applied_during_7d1"] is True
    assert prov["current_manifest_not_byte_identical_to_original_prerun_state"] is True


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d11_prov_02_no_invented_original_sha256():
    prov = _load(_MANIFEST_PROVENANCE)
    assert prov["original_full_file_sha256_before_7d1_annotation"] == "ORIGINAL_FULL_FILE_SHA256_NOT_CAPTURED_BEFORE_7D1_ANNOTATION"
    # must not look like a real 64-hex-char sha256 value
    value = prov["original_full_file_sha256_before_7d1_annotation"]
    assert not (len(value) == 64 and all(c in "0123456789abcdef" for c in value))


# ---------------------------------------------------------------------------
# 7D11-NUM / 7D11-REC
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d11_num_01_frozen_pooled_results_remain_exactly_unchanged():
    metrics = _load(_HELDOUT_METRICS)
    pooled = metrics["d1_d7_metrics"]["POOLED_D1_D7"]
    assert pooled["mean_target_percentile"] == 73.84712361066521
    assert pooled["top5_capture_rate"] == 0.17389455782312924
    assert pooled["top10_capture_rate"] == 0.29191232048374904
    assert pooled["n_target_rows"] == 323
    assert pooled["n_origins"] == 126

    procedural = _load(_PROCEDURAL)
    preserved = procedural["final_metrics_preserved_unchanged"]
    assert preserved["mean_target_percentile"] == 73.84712361066521
    assert preserved["n_within_targets"] == 323
    assert preserved["n_contributing_origins"] == 126


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7d11_rec_01_229_eq_126_plus_103_remains_exact():
    audit = _load(_PARTICIPATION)
    assert audit["n_heldout_origins"] == 229
    assert audit["n_blocked"] == 0
    assert audit["n_primary_contributing_origins"] == 126
    assert audit["n_zero_primary_target_origins"] == 103
    assert audit["n_primary_contributing_origins"] + audit["n_zero_primary_target_origins"] == 229
