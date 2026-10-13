"""Checkpoint 7C.1.1 Part 10: persisted-artifact identity consistency
and 532->277->192+85 reconciliation tests (7C11-ID-01..04,
7C11-REC-01..03). These intentionally assert against the REAL persisted
checkpoint artifacts (never hardcoded counts in reusable library logic)
-- skipped gracefully if the real files are not present in this
environment."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_OUT_DIR = _REPO_ROOT / "local_data" / "model_development" / "7c"

_REGISTRY = _OUT_DIR / "candidate_registry.json"
_MAPPING = _OUT_DIR / "candidate_identity_mapping_7c1.json"
_COVERAGE_RECORDS = _OUT_DIR / "candidate_coverage_records.json"
_SELECTED = _OUT_DIR / "selected_candidate.json"
_RECONCILIATION = _OUT_DIR / "validation_origin_reconciliation_532_to_277.json"
_WIND_STATUS = _OUT_DIR / "wind_status_by_origin.json"

_REQUIRED = (_REGISTRY, _MAPPING, _COVERAGE_RECORDS, _SELECTED, _RECONCILIATION, _WIND_STATUS)
_ALL_PRESENT = all(p.exists() for p in _REQUIRED)
_SKIP_REASON = "real 7C.1.1 persisted artifacts not present in this environment"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _find_candidate_ids(obj) -> set:
    found: set = set()

    def _walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "candidate_id" and isinstance(v, str) and v.startswith("C7C:"):
                    found.add(v)
                if isinstance(v, (dict, list)):
                    _walk(v)
                elif k in ("eligible_candidate_ids", "ineligible_candidate_ids") and isinstance(v, list):
                    found.update(x for x in v if isinstance(x, str) and x.startswith("C7C:"))
        elif isinstance(o, list):
            for item in o:
                _walk(item)

    _walk(obj)
    return found


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7c11_id_01_current_result_artifacts_contain_no_legacy_ids_except_mapping_history_file():
    mapping = _load(_MAPPING)["mapping"]
    legacy_ids = set(mapping.keys())

    for path in (_SELECTED, _COVERAGE_RECORDS, _OUT_DIR / "checkpoint_7c_audit.json", _OUT_DIR / "target_count_audit.json", _REGISTRY):
        d = _load(path)
        found = _find_candidate_ids(d)
        leaked = found & legacy_ids
        assert not leaked, f"{path.name} still contains legacy candidate ids: {leaked}"


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7c11_id_02_candidate_coverage_records_ids_are_all_members_of_current_registry():
    registry = _load(_REGISTRY)
    current_ids = {c["candidate_id"] for c in registry["candidates"]}
    records = _load(_COVERAGE_RECORDS)
    record_ids = {r["candidate_id"] for r in records}
    assert record_ids <= current_ids
    assert record_ids == current_ids  # every current candidate has at least one coverage record


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7c11_id_03_candidate_coverage_records_non_id_fields_unchanged_by_identity_remap():
    records = _load(_COVERAGE_RECORDS)
    # row count and per-candidate row count must reflect a pure relabel:
    # 9 candidates x 277 origins each, never altered by an identity-only change.
    assert len(records) == 2493
    from collections import Counter

    counts = Counter(r["candidate_id"] for r in records)
    assert len(counts) == 9
    assert set(counts.values()) == {277}
    for r in records:
        assert r["declared_domain_area_km2"] >= 0
        assert r["n_scientific_cells"] >= r["n_scored_cells"] >= 0


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7c11_id_04_nine_current_candidate_identities_appear_consistently_everywhere_expected():
    registry = _load(_REGISTRY)
    current_ids = {c["candidate_id"] for c in registry["candidates"]}
    assert len(current_ids) == 9

    selected = _load(_SELECTED)
    assert set(selected["candidate_overall_metrics"].keys()) == current_ids
    assert set(selected["candidate_coverage_summary"].keys()) == current_ids

    target_audit = _load(_OUT_DIR / "target_count_audit.json")
    assert set(target_audit["per_candidate_evaluable_target_count"].keys()) == current_ids

    with (_OUT_DIR / "candidate_metrics.csv").open(encoding="utf-8", newline="") as f:
        csv_ids = {row["candidate_id"] for row in csv.DictReader(f)}
    assert csv_ids == current_ids


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7c11_rec_01_532_usable_origins_reconcile_exactly_to_evaluable_plus_zero_primary_target():
    rec = _load(_RECONCILIATION)
    totals = rec["totals"]
    assert totals["intended_validation_origins"] == totals["ready_origins"] + totals["blocked_origins"]
    assert totals["ready_origins"] == totals["origins_with_ge1_primary_evaluable_target"] + totals["origins_with_zero_primary_evaluable_target"]
    for fold in rec["per_fold"]:
        assert fold["intended_validation_origins"] == fold["ready_origins"] + fold["blocked_origins"]
        assert fold["ready_origins"] == fold["origins_with_ge1_primary_evaluable_target"] + fold["origins_with_zero_primary_evaluable_target"]


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7c11_rec_02_evaluated_origins_reconcile_exactly_to_real_plus_unavailable_wind():
    rec = _load(_RECONCILIATION)
    totals = rec["totals"]
    assert totals["origins_with_ge1_primary_evaluable_target"] == totals["real_wind_evaluated_origins"] + totals["weather_unavailable_evaluated_origins"]

    wind_status = _load(_WIND_STATUS)
    from collections import Counter

    counts = Counter(wind_status.values())
    assert counts["REAL"] == totals["real_wind_evaluated_origins"]
    assert counts["WEATHER_INPUT_UNAVAILABLE"] == totals["weather_unavailable_evaluated_origins"]
    assert len(wind_status) == totals["origins_with_ge1_primary_evaluable_target"]


@pytest.mark.skipif(not _ALL_PRESENT, reason=_SKIP_REASON)
def test_7c11_rec_03_blocked_origin_count_remains_zero():
    rec = _load(_RECONCILIATION)
    assert rec["totals"]["blocked_origins"] == 0
    for fold in rec["per_fold"]:
        assert fold["blocked_origins"] == 0

    completeness = _load(_OUT_DIR / "validation_origin_completeness.json")
    for fold_id, comp in completeness.items():
        assert comp["blocked_origin_count"] == 0
