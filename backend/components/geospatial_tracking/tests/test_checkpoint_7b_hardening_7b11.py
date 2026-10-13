"""Checkpoint 7B.1.1: VALCOMP7B-01..04 (blocked-origin hard-stop),
CACHE7B-ROOT-01..03 (cache root path), CACHE7B-01..10 (cache scientific
identity, behavioral), and Part 7 (precise selection-note wording)
tests."""

from __future__ import annotations

import importlib
import inspect
import os

import pytest

import components.geospatial_tracking.services.model_development.development_run_7b as dev_run_mod
import components.geospatial_tracking.services.model_development.fold_reference as fold_ref_mod
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.geospatial.raster import LOCAL_GIS_CACHE_DIR
from components.geospatial_tracking.services.geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
from components.geospatial_tracking.services.model_development.development_run_7b import (
    ValidationOriginCompletenessGateError,
    assert_validation_origin_completeness,
)
from components.geospatial_tracking.services.model_development.evaluation_protocol_7b import (
    HOST_DEPENDENT_BASELINES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_DOMAIN_SUPPORT,
    PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE,
    PRIMARY_SELECTION_PARTIAL_COVERAGE_OTHER_CAUSE,
    classify_selection_note,
)

DISEASE = "Lumpy skin disease"


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)
    fields.update(overrides)
    return ForecastOrigin(**fields)


def _grid_config(cell_km=5.0, domain_km=25.0) -> ScientificGridConfig:
    return ScientificGridConfig(cell_size_km=cell_km, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=domain_km)


# ===================== VALCOMP7B: Part 2 =====================================

def test_valcomp7b_01_one_blocked_validation_origin_stops_selection():
    completeness = {
        "FOLD:2020": {"intended_validation_origin_count": 2, "ready_origin_count": 1, "blocked_origin_count": 1,
                       "blocked_origins": {"ORIGIN:Thailand:2020-01-01": "VALIDATION_ORIGIN_NO_ELIGIBLE_SOURCE"}},
    }
    with pytest.raises(ValidationOriginCompletenessGateError) as exc_info:
        assert_validation_origin_completeness(completeness)
    assert exc_info.value.blocked_details == [
        {"fold_id": "FOLD:2020", "forecast_origin_id": "ORIGIN:Thailand:2020-01-01", "status": "VALIDATION_ORIGIN_NO_ELIGIBLE_SOURCE"}
    ]


def test_valcomp7b_02_all_ready_allows_proceeding():
    completeness = {"FOLD:2020": {"intended_validation_origin_count": 2, "ready_origin_count": 2, "blocked_origin_count": 0, "blocked_origins": {}}}
    assert_validation_origin_completeness(completeness) is None


def test_valcomp7b_03_blocked_ids_and_reasons_preserved_across_folds():
    completeness = {
        "FOLD:2019": {"blocked_origins": {"ORIGIN:A": "VALIDATION_ORIGIN_RAW_SNAPSHOT_MISSING"}},
        "FOLD:2020": {"blocked_origins": {"ORIGIN:B": "VALIDATION_ORIGIN_GRID_UNAVAILABLE"}},
    }
    with pytest.raises(ValidationOriginCompletenessGateError) as exc_info:
        assert_validation_origin_completeness(completeness)
    details = exc_info.value.blocked_details
    assert {"fold_id": "FOLD:2019", "forecast_origin_id": "ORIGIN:A", "status": "VALIDATION_ORIGIN_RAW_SNAPSHOT_MISSING"} in details
    assert {"fold_id": "FOLD:2020", "forecast_origin_id": "ORIGIN:B", "status": "VALIDATION_ORIGIN_GRID_UNAVAILABLE"} in details
    assert "VALIDATION_ORIGIN_COMPLETENESS_GATE_FAILED" in str(exc_info.value)


def test_valcomp7b_04_zero_within_target_ready_origin_is_not_blocked(monkeypatch):
    class _S:
        source_id = "S1"
        latitude = 15.0
        longitude = 101.0

    class _Result:
        sources = [_S()]

    monkeypatch.setattr(dev_run_mod, "get_eligible_sources", lambda *a, **k: _Result())
    monkeypatch.setattr(dev_run_mod, "build_forecast_targets", lambda *a, **k: [])
    outcome = dev_run_mod._evaluate_validation_origin(
        object(), _origin(), fold_id="F", disease=DISEASE, active_window_days=14, grid_config=_grid_config(),
        raw_snapshot={"grid_cells": [{"grid_cell_id": "X", "centroid_lat": 15.0, "centroid_lon": 101.0, "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "host_density": {}}]},
        candidates=(), reference_profile=None, transform_config=None,
    )
    assert outcome.status == dev_run_mod.VALIDATION_ORIGIN_READY
    # a READY origin with zero within-scope targets must never appear as blocked
    completeness = {"F": {"blocked_origins": {}}}
    assert_validation_origin_completeness(completeness) is None


# ===================== CACHE7B-ROOT: Part 3 ===================================

def test_cache7b_root_01_cache_path_is_absolute_and_not_cwd_relative():
    assert dev_run_mod.DEFAULT_RAW_HOST_SNAPSHOT_CACHE_DIR.is_absolute()


def test_cache7b_root_02_resolved_path_identical_regardless_of_cwd(tmp_path):
    original_cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        reloaded = importlib.reload(dev_run_mod)
        path_from_tmp_cwd = reloaded.DEFAULT_RAW_HOST_SNAPSHOT_CACHE_DIR
    finally:
        os.chdir(original_cwd)
        importlib.reload(dev_run_mod)  # restore normal module state for subsequent tests
    assert path_from_tmp_cwd == dev_run_mod.DEFAULT_RAW_HOST_SNAPSHOT_CACHE_DIR


def test_cache7b_root_03_resolved_path_under_canonical_repository_local_data_root():
    expected = LOCAL_GIS_CACHE_DIR.parent / "model_development" / "7b" / "raw_host_snapshot_cache"
    assert dev_run_mod.DEFAULT_RAW_HOST_SNAPSHOT_CACHE_DIR == expected
    assert str(dev_run_mod.DEFAULT_RAW_HOST_SNAPSHOT_CACHE_DIR).startswith(str(LOCAL_GIS_CACHE_DIR.parent))
    assert "backend" not in dev_run_mod.DEFAULT_RAW_HOST_SNAPSHOT_CACHE_DIR.parts


# ===================== CACHE7B: Part 5-6 (behavioral) =========================

class _FakeSource:
    def __init__(self, source_id, lat, lon):
        self.source_id = source_id
        self.latitude = lat
        self.longitude = lon


class _FakeResult:
    def __init__(self, sources):
        self.sources = sources


def _patch_sources(monkeypatch, sources):
    monkeypatch.setattr(fold_ref_mod, "get_eligible_sources", lambda *a, **k: _FakeResult(sources))


def _patch_snapshot_builder(monkeypatch):
    counter = {"calls": 0}

    def _fake_builder(repo, *, origin, disease, active_window_days, grid_config, species):
        counter["calls"] += 1
        return {"snapshot_id": f"FAKE:{counter['calls']}", "forecast_origin_id": origin.forecast_origin_id, "grid_cells": []}, 0

    monkeypatch.setattr(fold_ref_mod, "build_scientific_grid_host_only_snapshot", _fake_builder)
    return counter


def test_cache7b_01_identical_request_is_a_cache_hit_and_never_recomputes(tmp_path, monkeypatch):
    _patch_sources(monkeypatch, [_FakeSource("S1", 15.0, 101.0)])
    counter = _patch_snapshot_builder(monkeypatch)
    origin = _origin()
    gc = _grid_config()

    snaps1, stats1 = fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    assert stats1["n_cache_misses"] == 1 and stats1["n_cache_hits"] == 0 and counter["calls"] == 1

    snaps2, stats2 = fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    assert stats2["n_cache_hits"] == 1 and stats2["n_cache_misses"] == 0 and counter["calls"] == 1
    assert snaps1[origin.forecast_origin_id]["snapshot_id"] == snaps2[origin.forecast_origin_id]["snapshot_id"]


def test_cache7b_02_changing_cell_size_is_a_cache_miss(tmp_path, monkeypatch):
    _patch_sources(monkeypatch, [_FakeSource("S1", 15.0, 101.0)])
    counter = _patch_snapshot_builder(monkeypatch)
    origin = _origin()
    fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=_grid_config(cell_km=5.0), cache_dir=tmp_path)
    _, stats = fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=_grid_config(cell_km=2.5), cache_dir=tmp_path)
    assert stats["n_cache_misses"] == 1 and counter["calls"] == 2


def test_cache7b_03_changing_domain_distance_is_a_cache_miss(tmp_path, monkeypatch):
    _patch_sources(monkeypatch, [_FakeSource("S1", 15.0, 101.0)])
    counter = _patch_snapshot_builder(monkeypatch)
    origin = _origin()
    fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=_grid_config(domain_km=25.0), cache_dir=tmp_path)
    _, stats = fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=_grid_config(domain_km=50.0), cache_dir=tmp_path)
    assert stats["n_cache_misses"] == 1 and counter["calls"] == 2


def test_cache7b_04_changing_active_window_days_is_a_cache_miss(tmp_path, monkeypatch):
    _patch_sources(monkeypatch, [_FakeSource("S1", 15.0, 101.0)])
    counter = _patch_snapshot_builder(monkeypatch)
    origin = _origin()
    gc = _grid_config()
    fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    _, stats = fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=21, grid_config=gc, cache_dir=tmp_path)
    assert stats["n_cache_misses"] == 1 and counter["calls"] == 2


def test_cache7b_05_changing_disease_is_a_cache_miss(tmp_path, monkeypatch):
    _patch_sources(monkeypatch, [_FakeSource("S1", 15.0, 101.0)])
    counter = _patch_snapshot_builder(monkeypatch)
    origin = _origin()
    gc = _grid_config()
    fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    _, stats = fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease="Foot and mouth disease", active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    assert stats["n_cache_misses"] == 1 and counter["calls"] == 2


def test_cache7b_06_changing_source_coordinates_is_a_cache_miss(tmp_path, monkeypatch):
    counter = _patch_snapshot_builder(monkeypatch)
    origin = _origin()
    gc = _grid_config()
    _patch_sources(monkeypatch, [_FakeSource("S1", 15.0, 101.0)])
    fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    _patch_sources(monkeypatch, [_FakeSource("S1", 15.5, 101.5)])  # moved
    _, stats = fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    assert stats["n_cache_misses"] == 1 and counter["calls"] == 2


def test_cache7b_07_generated_at_or_runtime_only_change_gives_same_identity(tmp_path, monkeypatch):
    _patch_sources(monkeypatch, [_FakeSource("S1", 15.0, 101.0)])
    counter = _patch_snapshot_builder(monkeypatch)
    origin = _origin()
    gc = _grid_config()
    fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    # a second, independent call (different wall-clock time, no generated_at
    # parameter exists on this function at all) must still hit the cache.
    _, stats = fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    assert stats["n_cache_hits"] == 1 and counter["calls"] == 1
    assert "generated_at" not in set(inspect.signature(fold_ref_mod.build_raw_host_snapshots_cached).parameters)


def test_cache7b_08_corrupted_cache_file_is_invalidated_and_recomputed(tmp_path, monkeypatch):
    _patch_sources(monkeypatch, [_FakeSource("S1", 15.0, 101.0)])
    counter = _patch_snapshot_builder(monkeypatch)
    origin = _origin()
    gc = _grid_config()
    fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    cache_files = list(tmp_path.glob("*.json"))
    assert len(cache_files) == 1
    cache_files[0].write_text("{not valid json!!", encoding="utf-8")  # corrupt it

    _, stats = fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    assert stats["n_cache_misses"] == 1 and counter["calls"] == 2  # recomputed, never silently accepted garbage


def test_cache7b_09_stored_forecast_origin_id_mismatch_rejects_cache_entry(tmp_path, monkeypatch):
    _patch_sources(monkeypatch, [_FakeSource("S1", 15.0, 101.0)])
    counter = _patch_snapshot_builder(monkeypatch)
    origin = _origin()
    gc = _grid_config()
    fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    cache_files = list(tmp_path.glob("*.json"))
    assert len(cache_files) == 1

    import json as _json
    entry = _json.loads(cache_files[0].read_text(encoding="utf-8"))
    entry["cache_identity"]["forecast_origin_id"] = "ORIGIN:SomeoneElse:1999-01-01"  # tamper
    cache_files[0].write_text(_json.dumps(entry), encoding="utf-8")

    _, stats = fold_ref_mod.build_raw_host_snapshots_cached(object(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=gc, cache_dir=tmp_path)
    assert stats["n_cache_identity_mismatches"] == 1
    assert stats["n_cache_misses"] == 1 and counter["calls"] == 2  # rejected + recomputed, never reused


def test_cache7b_10_identity_payload_key_and_species_ordering_never_changes_the_hash():
    payload_a = fold_ref_mod.raw_snapshot_cache_identity_payload(
        forecast_origin_id="O1", t0="2021-06-01", country="Thailand", disease=DISEASE, active_window_days=14,
        species=("cattle", "buffalo"), scientific_evaluation_domain_id="DOMAIN:X",
    )
    payload_b = fold_ref_mod.raw_snapshot_cache_identity_payload(
        forecast_origin_id="O1", t0="2021-06-01", country="Thailand", disease=DISEASE, active_window_days=14,
        species=("buffalo", "cattle"), scientific_evaluation_domain_id="DOMAIN:X",
    )
    assert fold_ref_mod.raw_snapshot_cache_identity_hash(payload_a) == fold_ref_mod.raw_snapshot_cache_identity_hash(payload_b)

    import json as _json
    reordered = _json.loads(_json.dumps({k: payload_a[k] for k in reversed(list(payload_a.keys()))}))
    assert fold_ref_mod.raw_snapshot_cache_identity_hash(reordered) == fold_ref_mod.raw_snapshot_cache_identity_hash(payload_a)


# ===================== Part 7: precise selection-note wording =================

_B0_IDS = ("CAND:B0:1", "CAND:B0:2")
_B1_IDS = ("CAND:B1:1",)
_B2_IDS = ("CAND:B2:1",)
_FAMILIES = {
    "CAND:B0:1": "B0_DISTANCE_ONLY", "CAND:B0:2": "B0_DISTANCE_ONLY",
    "CAND:B1:1": "B1_HOST_DISTANCE_LOG1P", "CAND:B2:1": "B2_HOST_DISTANCE_ECDF",
}


def test_selection_note_host_dependent_only_when_b0_fully_eligible_and_ineligible_are_only_b1_b2():
    note = classify_selection_note(
        candidate_families_by_id=_FAMILIES, eligible_candidate_ids=_B0_IDS, ineligible_candidate_ids=_B1_IDS + _B2_IDS,
    )
    assert note == HOST_DEPENDENT_BASELINES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_DOMAIN_SUPPORT


def test_selection_note_b0_unexpectedly_incomplete_uses_other_cause():
    # one B0 candidate is ALSO ineligible -- never the host-specific wording
    note = classify_selection_note(
        candidate_families_by_id=_FAMILIES, eligible_candidate_ids=("CAND:B0:2",), ineligible_candidate_ids=("CAND:B0:1",) + _B1_IDS + _B2_IDS,
    )
    assert note == PRIMARY_SELECTION_PARTIAL_COVERAGE_OTHER_CAUSE


def test_selection_note_all_candidates_ineligible_is_blocked_not_host_specific():
    note = classify_selection_note(candidate_families_by_id=_FAMILIES, eligible_candidate_ids=(), ineligible_candidate_ids=_B0_IDS + _B1_IDS + _B2_IDS)
    assert note == PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE


def test_selection_note_all_eligible_is_empty_string():
    note = classify_selection_note(candidate_families_by_id=_FAMILIES, eligible_candidate_ids=_B0_IDS + _B1_IDS + _B2_IDS, ineligible_candidate_ids=())
    assert note == ""


def test_select_candidate_never_called_with_empty_metrics_when_none_eligible():
    src = inspect.getsource(dev_run_mod.run_checkpoint_7b_development)
    idx_note = src.index("PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE")
    idx_select_call = src.index("select_candidate(eligible_metrics)")
    assert idx_note < idx_select_call  # the blocked-check is raised BEFORE select_candidate is ever invoked
