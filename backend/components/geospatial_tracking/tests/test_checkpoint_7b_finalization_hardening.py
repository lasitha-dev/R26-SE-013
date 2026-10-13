"""Checkpoint 7B finalization-hardening tests: HOSTFINAL7B-01..03, coverage
persistence, incomplete-domain eligibility, unique-target vs candidate-row
counts (COUNT7B-01), no-silent-validation-origin-disappearance, candidate
evaluation-protocol identity, identity-only remap bijectivity, and frozen
spec naming."""

from __future__ import annotations

import inspect

import pytest

from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
from components.geospatial_tracking.services.model_development import development_run_7b as dev_run_mod
from components.geospatial_tracking.services.model_development.baseline_scoring import SCORED, CellScore, compute_coverage_record
from components.geospatial_tracking.services.model_development.candidate_registry_7b import (
    build_candidate_registry,
    build_identity_only_result_remap,
)
from components.geospatial_tracking.services.model_development.development_run_7b import (
    TargetEvaluationRecord,
    dedupe_targets_by_origin_and_event,
)
from components.geospatial_tracking.services.model_development.evaluation_protocol_7b import (
    PRIMARY_SELECTION_ELIGIBLE,
    PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE,
    SOFTWARE_ZERO_AREA_TOLERANCE_KM2,
    assess_candidate_coverage_eligibility,
)
from components.geospatial_tracking.services.model_development.protocol_7b import (
    REUSED_AS_FINAL_DEVELOPMENT_REFERENCE,
    TRANSFORM_CONFIG_MISMATCH_REBUILD_REQUIRED,
    FrozenBaselineModelSpecification,
    build_final_host_reference_decision,
    existing_reference_metadata_from_persisted_files,
)


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)
    fields.update(overrides)
    return ForecastOrigin(**fields)


def _grid_config() -> ScientificGridConfig:
    return ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)


# -- HOSTFINAL7B: Part 2 -----------------------------------------------

def test_hostfinal7b_01_different_existing_and_selected_hashes_reject_reuse():
    decision = build_final_host_reference_decision(
        selected_baseline_family="B1_HOST_DISTANCE_LOG1P", existing_579_origin_reference_hash="HASH_A",
        existing_579_origin_reference_status="COMPLETE_DIAGNOSTIC", existing_579_origin_transform_config_hash="CFG_OLD",
        selected_transform_config_hash="CFG_NEW",
    )
    assert decision["decision"] == TRANSFORM_CONFIG_MISMATCH_REBUILD_REQUIRED
    assert decision["transform_config_matches_selected_host_transform"] is False


def test_hostfinal7b_02_same_existing_and_selected_hashes_permit_reuse():
    decision = build_final_host_reference_decision(
        selected_baseline_family="B2_HOST_DISTANCE_ECDF", existing_579_origin_reference_hash="HASH_A",
        existing_579_origin_reference_status="COMPLETE_DIAGNOSTIC", existing_579_origin_transform_config_hash="CFG_X",
        selected_transform_config_hash="CFG_X",
    )
    assert decision["decision"] == REUSED_AS_FINAL_DEVELOPMENT_REFERENCE
    assert decision["transform_config_matches_selected_host_transform"] is True


def test_hostfinal7b_03_existing_hash_sourced_from_persisted_metadata_not_selected_value():
    params = list(inspect.signature(existing_reference_metadata_from_persisted_files).parameters)
    assert not any("selected" in p.lower() for p in params)  # structurally cannot alias to the selected run's hash

    profile_dict = {"transform_config_hash": "REAL_PERSISTED_TRANSFORM_CONFIG_HASH"}
    audit_dict = {"reference_profile_hash": "REAL_PERSISTED_REFERENCE_HASH", "status": "COMPLETE_DIAGNOSTIC"}
    meta = existing_reference_metadata_from_persisted_files(profile_dict=profile_dict, audit_dict=audit_dict)
    assert meta["transform_config_hash"] == "REAL_PERSISTED_TRANSFORM_CONFIG_HASH"
    assert meta["reference_profile_hash"] == "REAL_PERSISTED_REFERENCE_HASH"
    assert meta["status"] == "COMPLETE_DIAGNOSTIC"


# -- Part 3: coverage persistence ---------------------------------------

def test_coverage_record_uses_domain_overlap_area_and_is_fully_populated():
    cells = [
        CellScore(grid_cell_id="A", scientific_cell_id="SCICELL:A", area_km2=25.0, domain_overlap_area_km2=25.0, score=1.0, status=SCORED),
        CellScore(grid_cell_id="B", scientific_cell_id="SCICELL:B", area_km2=25.0, domain_overlap_area_km2=10.0, score=None, status="MODEL_INPUT_INCOMPLETE"),
    ]
    rec = compute_coverage_record(cells, forecast_origin_id="O1", fold_id="F1", candidate_id="C1")
    assert rec.declared_domain_area_km2 == 35.0  # sums domain_overlap_area_km2, never full area_km2 (would be 50.0)
    assert rec.scored_domain_area_km2 == 25.0
    assert rec.missing_domain_area_km2 == 10.0
    assert abs(rec.missing_domain_area_fraction - (10.0 / 35.0)) < 1e-12
    assert rec.n_scientific_cells == 2
    assert rec.n_scored_cells == 1
    assert rec.n_incomplete_cells == 1
    d = rec.as_dict()
    for key in ("declared_domain_area_km2", "scored_domain_area_km2", "missing_domain_area_km2", "missing_domain_area_fraction", "n_scientific_cells", "n_scored_cells", "n_incomplete_cells"):
        assert key in d


# -- Part 4: coverage eligibility ----------------------------------------

def test_eligibility_complete_coverage_is_eligible():
    status = assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=0, max_missing_domain_area_km2=0.0)
    assert status == PRIMARY_SELECTION_ELIGIBLE


def test_eligibility_any_target_score_unavailable_row_makes_ineligible():
    status = assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=1, max_missing_domain_area_km2=0.0)
    assert status == PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE


def test_eligibility_material_missing_area_makes_ineligible():
    status = assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=0, max_missing_domain_area_km2=1.0)
    assert status == PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE


def test_eligibility_uses_only_a_tiny_software_zero_tolerance_never_a_percentage():
    # the tolerance itself must be tiny (floating-point-zero scale), never
    # a biological/statistical percentage such as 0.05 (5%) or 0.1 (10%)
    assert SOFTWARE_ZERO_AREA_TOLERANCE_KM2 <= 1e-3
    src = inspect.getsource(assess_candidate_coverage_eligibility)
    for forbidden in ("0.05", "0.1", "5%", "10%", "five percent", "ten percent"):
        assert forbidden not in src
    # a missing area WITHIN the tiny tolerance still counts as eligible
    status = assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=0, max_missing_domain_area_km2=SOFTWARE_ZERO_AREA_TOLERANCE_KM2 / 10)
    assert status == PRIMARY_SELECTION_ELIGIBLE


# -- Part 6: COUNT7B-01 ---------------------------------------------------

def test_count7b_01_one_unique_target_times_24_candidates():
    candidates = build_candidate_registry()
    assert len(candidates) == 24
    records = [
        TargetEvaluationRecord(
            forecast_origin_id="O1", fold_id="F1", candidate_id=c.candidate_id, target_event_id="E1", target_id="O1::E1",
            lead_days=3, target_grid_cell_id="CELL:1", target_score=1.0, area_weighted_target_percentile=50.0,
            top5_capture=False, top10_capture=False, target_cell_rank=1, valid_domain_area_km2=10.0, scored_domain_area_km2=10.0,
            model_input_status=SCORED,
        )
        for c in candidates
    ]
    n_candidate_target_rows = len(records)
    n_unique_targets = len({(r.forecast_origin_id, r.target_event_id) for r in records})
    assert n_candidate_target_rows == 24
    assert n_unique_targets == 1


def test_dedup_does_not_rely_on_target_id_string_encoding():
    src = inspect.getsource(dedupe_targets_by_origin_and_event)
    assert "t.target_id" not in src
    assert "forecast_origin_id" in src and "target_event_id" in src


# -- Part 7: no silent validation-origin disappearance ---------------------

def test_no_silent_drop_raw_snapshot_missing():
    outcome = dev_run_mod._evaluate_validation_origin(
        None, _origin(), fold_id="F", disease="Lumpy skin disease", active_window_days=14, grid_config=_grid_config(),
        raw_snapshot=None, candidates=(), reference_profile=None, transform_config=FactorTransformConfig(),
    )
    assert outcome.status == dev_run_mod.VALIDATION_ORIGIN_RAW_SNAPSHOT_MISSING
    assert outcome.target_records == ()
    assert outcome.coverage_records == ()


def test_no_silent_drop_no_eligible_source(monkeypatch):
    class _EmptyResult:
        sources: list = []

    monkeypatch.setattr(dev_run_mod, "get_eligible_sources", lambda *a, **k: _EmptyResult())
    outcome = dev_run_mod._evaluate_validation_origin(
        object(), _origin(), fold_id="F", disease="Lumpy skin disease", active_window_days=14, grid_config=_grid_config(),
        raw_snapshot={"grid_cells": [{"grid_cell_id": "X"}]}, candidates=(), reference_profile=None, transform_config=FactorTransformConfig(),
    )
    assert outcome.status == dev_run_mod.VALIDATION_ORIGIN_NO_ELIGIBLE_SOURCE


def test_no_silent_drop_grid_unavailable(monkeypatch):
    class _S:
        source_id = "S1"
        latitude = 15.0
        longitude = 101.0

    class _Result:
        sources = [_S()]

    monkeypatch.setattr(dev_run_mod, "get_eligible_sources", lambda *a, **k: _Result())
    outcome = dev_run_mod._evaluate_validation_origin(
        object(), _origin(), fold_id="F", disease="Lumpy skin disease", active_window_days=14, grid_config=_grid_config(),
        raw_snapshot={"grid_cells": []}, candidates=(), reference_profile=None, transform_config=FactorTransformConfig(),
    )
    assert outcome.status == dev_run_mod.VALIDATION_ORIGIN_GRID_UNAVAILABLE


def test_ready_status_reported_even_with_zero_within_targets(monkeypatch):
    class _S:
        source_id = "S1"
        latitude = 15.0
        longitude = 101.0

    class _Result:
        sources = [_S()]

    monkeypatch.setattr(dev_run_mod, "get_eligible_sources", lambda *a, **k: _Result())
    monkeypatch.setattr(dev_run_mod, "build_forecast_targets", lambda *a, **k: [])
    outcome = dev_run_mod._evaluate_validation_origin(
        object(), _origin(), fold_id="F", disease="Lumpy skin disease", active_window_days=14, grid_config=_grid_config(),
        raw_snapshot={"grid_cells": [{"grid_cell_id": "X", "centroid_lat": 15.0, "centroid_lon": 101.0, "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "host_density": {}}]},
        candidates=(), reference_profile=None, transform_config=FactorTransformConfig(),
    )
    assert outcome.status == dev_run_mod.VALIDATION_ORIGIN_READY  # zero targets is READY, never a blocked/dropped status


# -- Part 8: candidate evaluation-protocol identity ------------------------

def test_evaluation_protocol_change_changes_every_candidate_id(monkeypatch):
    import components.geospatial_tracking.services.model_development.evaluation_protocol_7b as eval_mod

    baseline_ids = {c.candidate_id for c in build_candidate_registry()}
    monkeypatch.setattr(eval_mod, "BASELINE_EVALUATION_PROTOCOL_VERSION", "7B.TEST-CHANGED")
    changed_ids = {c.candidate_id for c in build_candidate_registry()}
    assert baseline_ids.isdisjoint(changed_ids)


# -- Part 9: identity-only remap is a bijection -----------------------------

def test_identity_only_remap_is_bijective_over_the_same_24_candidates():
    mapping = build_identity_only_result_remap()
    assert len(mapping) == 24
    assert len(set(mapping.values())) == 24
    current_ids = {c.candidate_id for c in build_candidate_registry()}
    assert set(mapping.values()) == current_ids


# -- Part 10: frozen spec identity naming -----------------------------------

def test_frozen_spec_distinguishes_grid_config_hash_from_domain_and_evaluation_protocol_hashes():
    fields = set(FrozenBaselineModelSpecification.__dataclass_fields__)
    required = {
        "scientific_grid_config_hash", "scientific_domain_protocol_hash", "scientific_domain_protocol_version",
        "model_development_protocol_hash_7a62", "evaluation_protocol_hash", "evaluation_protocol_version",
    }
    assert required <= fields
    assert "scientific_grid_protocol_hash" not in fields  # old, misleadingly-named field removed
    assert "model_development_protocol_hash" not in fields  # renamed to the explicit _7a62 form
