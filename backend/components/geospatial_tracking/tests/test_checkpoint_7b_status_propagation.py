"""Focused synthetic tests for unsafe-component status propagation."""

from __future__ import annotations

from types import SimpleNamespace

import components.geospatial_tracking.services.model_development.development_run_7b as dev_run_mod
import components.geospatial_tracking.services.model_development.fold_reference as fold_ref_mod
from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.geospatial.host_density.fao_glw import DATASET_NAME, REFERENCE_YEAR, UNITS
from components.geospatial_tracking.services.geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.model_development.baseline_scoring import (
    MODEL_INPUT_INCOMPLETE,
    SCORED,
    TARGET_SCORE_UNAVAILABLE,
    compute_area_weighted_percentiles,
    compute_coverage_record,
    score_origin_all_candidates,
)
from components.geospatial_tracking.services.model_development.candidate_registry_7b import BaselineCandidateSpec
from components.geospatial_tracking.services.model_development.local_evaluation_scope import WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE

DISEASE = "Lumpy skin disease"


def _origin(*, origin_id: str = "ORIGIN:Thailand:2021-06-01", t0: str = "2021-06-01") -> ForecastOrigin:
    return ForecastOrigin(
        forecast_origin_id=origin_id,
        country="Thailand",
        t0=t0,
        temporal_mode="RETROSPECTIVE_PROXY",
        trigger_source_ids_at_t0=["S1"],
        trigger_source_count=1,
    )


def _grid_config() -> ScientificGridConfig:
    return ScientificGridConfig(
        cell_size_km=5.0,
        domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION,
        domain_distance_km=25.0,
    )


def _species_real(value: float, digest: str) -> dict:
    return {
        "status": "REAL",
        "value": value,
        "units": UNITS,
        "dataset_name": DATASET_NAME,
        "dataset_version": REFERENCE_YEAR,
        "sample_support_digest": digest,
    }


def _cell(*, origin_id: str = "O1") -> dict:
    return {
        "grid_cell_id": "CELL:1",
        "scientific_cell_id": f"SCICELL:{origin_id}",
        "centroid_lat": 15.0,
        "centroid_lon": 101.0,
        "area_km2": 25.0,
        "domain_overlap_area_km2": 25.0,
        "host_density": {
            "cattle": _species_real(5.0, f"{origin_id}:cattle"),
            "buffalo": _species_real(1.0, f"{origin_id}:buffalo"),
        },
    }


def _snapshot(*, origin_id: str, unsafe_component_count: int) -> dict:
    return {
        "snapshot_id": f"SNAP:{origin_id}",
        "forecast_origin_id": origin_id,
        "unsafe_component_count": unsafe_component_count,
        "model_input_status": MODEL_INPUT_INCOMPLETE if unsafe_component_count > 0 else SCORED,
        "active_source_ids": ["S1"],
        "grid_cells": [_cell(origin_id=origin_id)],
        "weather": {},
        "source_dataset_versions": {},
        "landcover_comparability_group": None,
    }


def _candidate() -> BaselineCandidateSpec:
    return BaselineCandidateSpec(
        candidate_id="TEST:B0:EXPONENTIAL:10",
        baseline_family="B0_DISTANCE_ONLY",
        host_factor_candidate=None,
        kernel_family="EXPONENTIAL",
        kernel_scale_km=10.0,
        source_weighting="EQUAL_SOURCE_BASELINE",
        output_label="RELATIVE_SPATIAL_SCORE",
    )


def _sources() -> list[EligibleSourcePoint]:
    return [EligibleSourcePoint(source_id="S1", latitude=15.1, longitude=101.0)]


def test_zero_count_preserves_complete_numeric_scoring_and_is_deterministic():
    candidate = _candidate()
    kwargs = {"grid_cells": [_cell()], "sources": _sources(), "candidates": (candidate,)}

    existing_behavior = score_origin_all_candidates(**kwargs)
    explicit_zero = score_origin_all_candidates(**kwargs, unsafe_component_count=0)
    repeated_zero = score_origin_all_candidates(**kwargs, unsafe_component_count=0)

    assert explicit_zero == existing_behavior == repeated_zero
    cell_score = explicit_zero[candidate.candidate_id][0]
    assert cell_score.status == SCORED
    assert isinstance(cell_score.score, float)

    existing_coverage = compute_coverage_record(
        existing_behavior[candidate.candidate_id], forecast_origin_id="O1", fold_id="F1", candidate_id=candidate.candidate_id,
    )
    explicit_coverage = compute_coverage_record(
        explicit_zero[candidate.candidate_id], forecast_origin_id="O1", fold_id="F1", candidate_id=candidate.candidate_id,
        unsafe_component_count=0,
    )
    assert explicit_coverage == existing_coverage
    assert explicit_coverage.model_input_status == SCORED


def test_positive_count_stops_numeric_scoring_and_marks_coverage_incomplete():
    candidate = _candidate()
    kwargs = {
        "grid_cells": [_cell()],
        "sources": _sources(),
        "candidates": (candidate,),
        "unsafe_component_count": 2,
    }

    first = score_origin_all_candidates(**kwargs)
    second = score_origin_all_candidates(**kwargs)
    assert first == second

    cell_score = first[candidate.candidate_id][0]
    assert cell_score.status == MODEL_INPUT_INCOMPLETE
    assert cell_score.score is None
    assert compute_area_weighted_percentiles(first[candidate.candidate_id]) == {}

    coverage = compute_coverage_record(
        first[candidate.candidate_id], forecast_origin_id="O1", fold_id="F1", candidate_id=candidate.candidate_id,
        unsafe_component_count=2,
    )
    assert coverage.model_input_status == MODEL_INPUT_INCOMPLETE
    assert coverage.unsafe_component_count == 2
    assert coverage.n_scored_cells == 0
    assert coverage.scored_domain_area_km2 == 0.0


def test_separately_returned_count_survives_raw_snapshot_and_cache_hit(tmp_path, monkeypatch):
    origin = _origin()
    calls = {"builder": 0}

    monkeypatch.setattr(
        fold_ref_mod,
        "get_eligible_sources",
        lambda *args, **kwargs: SimpleNamespace(
            sources=[SimpleNamespace(source_id="S1", latitude=15.0, longitude=101.0)]
        ),
    )
    monkeypatch.setattr(
        fold_ref_mod,
        "build_scientific_evaluation_domain",
        lambda **kwargs: SimpleNamespace(scientific_evaluation_domain_id="DOMAIN:TEST"),
    )

    def _builder(*args, **kwargs):
        calls["builder"] += 1
        snapshot = _snapshot(origin_id=origin.forecast_origin_id, unsafe_component_count=0)
        snapshot.pop("unsafe_component_count")
        snapshot.pop("model_input_status")
        return snapshot, 2

    monkeypatch.setattr(fold_ref_mod, "build_scientific_grid_host_only_snapshot", _builder)

    first, first_stats = fold_ref_mod.build_raw_host_snapshots_cached(
        object(),
        fit_development_origins=[origin],
        disease=DISEASE,
        active_window_days=14,
        grid_config=_grid_config(),
        cache_dir=tmp_path,
    )
    second, second_stats = fold_ref_mod.build_raw_host_snapshots_cached(
        object(),
        fit_development_origins=[origin],
        disease=DISEASE,
        active_window_days=14,
        grid_config=_grid_config(),
        cache_dir=tmp_path,
    )

    first_snapshot = first[origin.forecast_origin_id]
    second_snapshot = second[origin.forecast_origin_id]
    assert first_snapshot["unsafe_component_count"] == second_snapshot["unsafe_component_count"] == 2
    assert first_snapshot["model_input_status"] == second_snapshot["model_input_status"] == MODEL_INPUT_INCOMPLETE
    assert first_stats["unsafe_component_count"] == second_stats["unsafe_component_count"] == 2
    assert first_stats["n_origins_with_unsafe_components"] == second_stats["n_origins_with_unsafe_components"] == 1
    assert first_stats["n_cache_misses"] == 1
    assert second_stats["n_cache_hits"] == 1
    assert calls["builder"] == 1


def test_training_count_survives_fold_reference_and_changes_only_its_completeness_identity():
    train = _origin()
    validation = _origin(origin_id="ORIGIN:Thailand:2023-06-01", t0="2023-06-01")
    raw_incomplete = {
        train.forecast_origin_id: _snapshot(origin_id=train.forecast_origin_id, unsafe_component_count=3),
        validation.forecast_origin_id: _snapshot(origin_id=validation.forecast_origin_id, unsafe_component_count=8),
    }
    raw_complete = dict(raw_incomplete)
    raw_complete[train.forecast_origin_id] = _snapshot(origin_id=train.forecast_origin_id, unsafe_component_count=0)

    kwargs = {
        "fold_id": "FOLD:2023",
        "training_origins": [train],
        "validation_origins": [validation],
        "transform_config": FactorTransformConfig(),
    }
    incomplete = fold_ref_mod.build_fold_safe_reference(raw_snapshots_by_origin_id=raw_incomplete, **kwargs)
    repeated = fold_ref_mod.build_fold_safe_reference(raw_snapshots_by_origin_id=raw_incomplete, **kwargs)
    complete = fold_ref_mod.build_fold_safe_reference(raw_snapshots_by_origin_id=raw_complete, **kwargs)

    assert incomplete.unsafe_component_count == 3
    assert incomplete.model_input_status == MODEL_INPUT_INCOMPLETE
    assert incomplete.as_dict()["unsafe_component_count"] == 3
    assert incomplete.as_dict()["model_input_status"] == MODEL_INPUT_INCOMPLETE
    assert incomplete.fold_reference_identity_hash() == repeated.fold_reference_identity_hash()
    assert incomplete.reference_profile.reference_profile_hash() == complete.reference_profile.reference_profile_hash()
    assert incomplete.fold_reference_identity_hash() != complete.fold_reference_identity_hash()
    assert complete.unsafe_component_count == 0
    assert complete.model_input_status == SCORED


def test_origin_boundary_reuses_unavailable_statuses_and_never_emits_a_primary_number(monkeypatch):
    origin = _origin()
    candidate = _candidate()
    target = SimpleNamespace(
        forecast_origin_id=origin.forecast_origin_id,
        target_event_id="EVENT:1",
        target_id=f"{origin.forecast_origin_id}::EVENT:1",
        lead_days=3,
        risk_target_eligible=True,
    )

    monkeypatch.setattr(dev_run_mod, "_eligible_source_points", lambda *args, **kwargs: _sources())
    monkeypatch.setattr(dev_run_mod, "build_scientific_evaluation_domain", lambda **kwargs: object())
    monkeypatch.setattr(dev_run_mod, "build_forecast_targets", lambda *args, **kwargs: [target])
    monkeypatch.setattr(
        dev_run_mod,
        "classify_target_primary_scope",
        lambda **kwargs: SimpleNamespace(
            scope_status=WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE,
            target_grid_cell_id="CELL:1",
        ),
    )

    common = {
        "repo": object(),
        "origin": origin,
        "fold_id": "FOLD:2023",
        "disease": DISEASE,
        "active_window_days": 14,
        "grid_config": _grid_config(),
        "candidates": (candidate,),
        "reference_profile": None,
        "transform_config": FactorTransformConfig(),
    }
    complete = dev_run_mod._evaluate_validation_origin(
        raw_snapshot=_snapshot(origin_id=origin.forecast_origin_id, unsafe_component_count=0),
        reference_unsafe_component_count=0,
        **common,
    )
    incomplete = dev_run_mod._evaluate_validation_origin(
        raw_snapshot=_snapshot(origin_id=origin.forecast_origin_id, unsafe_component_count=1),
        reference_unsafe_component_count=2,
        **common,
    )
    repeated = dev_run_mod._evaluate_validation_origin(
        raw_snapshot=_snapshot(origin_id=origin.forecast_origin_id, unsafe_component_count=1),
        reference_unsafe_component_count=2,
        **common,
    )

    assert complete.status == dev_run_mod.VALIDATION_ORIGIN_READY
    assert complete.target_records[0].model_input_status == SCORED
    assert isinstance(complete.target_records[0].target_score, float)
    assert complete.coverage_records[0].model_input_status == SCORED

    assert incomplete == repeated
    assert incomplete.status == dev_run_mod.VALIDATION_ORIGIN_GRID_UNAVAILABLE
    assert incomplete.status == "VALIDATION_ORIGIN_GRID_UNAVAILABLE"
    assert incomplete.unsafe_component_count == 3
    assert incomplete.target_records[0].model_input_status == TARGET_SCORE_UNAVAILABLE
    assert incomplete.target_records[0].model_input_status == "TARGET_SCORE_UNAVAILABLE"
    assert incomplete.target_records[0].target_score is None
    assert incomplete.target_records[0].area_weighted_target_percentile is None
    assert incomplete.coverage_records[0].model_input_status == MODEL_INPUT_INCOMPLETE
    assert incomplete.coverage_records[0].model_input_status == "MODEL_INPUT_INCOMPLETE"
    assert incomplete.coverage_records[0].unsafe_component_count == 3

