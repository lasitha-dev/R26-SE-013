"""Checkpoint 7B Part 43: FOLDREF-01..06 fold-safe host reference tests."""

from __future__ import annotations

from components.geospatial_tracking.services.factors.host_transform import build_host_factor_candidates
from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.geospatial.host_density.fao_glw import DATASET_NAME, REFERENCE_YEAR, UNITS
from components.geospatial_tracking.services.model_development.fold_reference import build_fold_safe_reference

DISEASE = "Lumpy skin disease"


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)
    fields.update(overrides)
    return ForecastOrigin(**fields)


def _species_real(value: float, *, digest: str) -> dict:
    return {"status": "REAL", "value": value, "units": UNITS, "dataset_name": DATASET_NAME, "dataset_version": REFERENCE_YEAR, "sample_support_digest": digest}


def _snapshot(*, origin_id: str, host_value: float, digest: str) -> dict:
    return {
        "snapshot_id": f"SNAP:{origin_id}", "forecast_origin_id": origin_id, "active_source_ids": ["S1"],
        "grid_cells": [{
            "grid_cell_id": f"CELL:{origin_id}:0", "scientific_cell_id": f"SCICELL:{origin_id}",
            "centroid_lat": 15.0, "centroid_lon": 101.0, "area_km2": 25.0, "domain_overlap_area_km2": 25.0,
            "host_density": {"cattle": _species_real(host_value, digest=digest), "buffalo": _species_real(0.0, digest=digest + ":b")},
        }],
        "weather": {}, "source_dataset_versions": {}, "landcover_comparability_group": None,
    }


def test_foldref_01_reference_built_only_from_training_origins():
    train = _origin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", t0="2021-06-01")
    val = _origin(forecast_origin_id="ORIGIN:Thailand:2023-06-01", t0="2023-06-01")
    raw = {
        train.forecast_origin_id: _snapshot(origin_id=train.forecast_origin_id, host_value=5.0, digest="D-TRAIN"),
        val.forecast_origin_id: _snapshot(origin_id=val.forecast_origin_id, host_value=999.0, digest="D-VAL"),
    }
    fold_ref = build_fold_safe_reference(
        fold_id="FOLD:2023", training_origins=[train], validation_origins=[val], raw_snapshots_by_origin_id=raw,
        transform_config=FactorTransformConfig(),
    )
    assert fold_ref.reference_profile.n_included_origins == 1
    assert fold_ref.reference_profile.host_density_total_reference_values == (5.0,)  # never 999.0 (validation's value)


def test_foldref_02_changing_validation_snapshot_never_changes_reference_hash():
    train = _origin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", t0="2021-06-01")
    val = _origin(forecast_origin_id="ORIGIN:Thailand:2023-06-01", t0="2023-06-01")
    raw_a = {
        train.forecast_origin_id: _snapshot(origin_id=train.forecast_origin_id, host_value=5.0, digest="D-TRAIN"),
        val.forecast_origin_id: _snapshot(origin_id=val.forecast_origin_id, host_value=999.0, digest="D-VAL"),
    }
    raw_b = dict(raw_a)
    raw_b[val.forecast_origin_id] = _snapshot(origin_id=val.forecast_origin_id, host_value=12345.0, digest="D-VAL-CHANGED")

    ref_a = build_fold_safe_reference(fold_id="FOLD:2023", training_origins=[train], validation_origins=[val], raw_snapshots_by_origin_id=raw_a, transform_config=FactorTransformConfig())
    ref_b = build_fold_safe_reference(fold_id="FOLD:2023", training_origins=[train], validation_origins=[val], raw_snapshots_by_origin_id=raw_b, transform_config=FactorTransformConfig())
    assert ref_a.fold_reference_identity_hash() == ref_b.fold_reference_identity_hash()
    assert ref_a.reference_profile.reference_profile_hash() == ref_b.reference_profile.reference_profile_hash()


def test_foldref_03_fold_reference_deterministic():
    train = _origin()
    val = _origin(forecast_origin_id="ORIGIN:Thailand:2023-06-01", t0="2023-06-01")
    raw = {
        train.forecast_origin_id: _snapshot(origin_id=train.forecast_origin_id, host_value=5.0, digest="D-TRAIN"),
        val.forecast_origin_id: _snapshot(origin_id=val.forecast_origin_id, host_value=999.0, digest="D-VAL"),
    }
    r1 = build_fold_safe_reference(fold_id="FOLD:2023", training_origins=[train], validation_origins=[val], raw_snapshots_by_origin_id=raw, transform_config=FactorTransformConfig())
    r2 = build_fold_safe_reference(fold_id="FOLD:2023", training_origins=[train], validation_origins=[val], raw_snapshots_by_origin_id=raw, transform_config=FactorTransformConfig())
    assert r1.fold_reference_identity_hash() == r2.fold_reference_identity_hash()


def test_foldref_04_different_training_history_changes_hash_when_support_changes():
    train_1 = _origin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", t0="2021-06-01")
    train_2 = _origin(forecast_origin_id="ORIGIN:Thailand:2022-06-01", t0="2022-06-01")
    val = _origin(forecast_origin_id="ORIGIN:Thailand:2023-06-01", t0="2023-06-01")
    raw = {
        train_1.forecast_origin_id: _snapshot(origin_id=train_1.forecast_origin_id, host_value=5.0, digest="D1"),
        train_2.forecast_origin_id: _snapshot(origin_id=train_2.forecast_origin_id, host_value=8.0, digest="D2"),
        val.forecast_origin_id: _snapshot(origin_id=val.forecast_origin_id, host_value=999.0, digest="DV"),
    }
    small = build_fold_safe_reference(fold_id="FOLD:A", training_origins=[train_1], validation_origins=[val], raw_snapshots_by_origin_id=raw, transform_config=FactorTransformConfig())
    big = build_fold_safe_reference(fold_id="FOLD:B", training_origins=[train_1, train_2], validation_origins=[val], raw_snapshots_by_origin_id=raw, transform_config=FactorTransformConfig())
    assert small.fold_reference_identity_hash() != big.fold_reference_identity_hash()
    assert small.reference_profile.reference_profile_hash() != big.reference_profile.reference_profile_hash()


def test_foldref_05_same_training_support_reordered_gives_same_hash():
    train_1 = _origin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", t0="2021-06-01")
    train_2 = _origin(forecast_origin_id="ORIGIN:Thailand:2022-06-01", t0="2022-06-01")
    val = _origin(forecast_origin_id="ORIGIN:Thailand:2023-06-01", t0="2023-06-01")
    raw = {
        train_1.forecast_origin_id: _snapshot(origin_id=train_1.forecast_origin_id, host_value=5.0, digest="D1"),
        train_2.forecast_origin_id: _snapshot(origin_id=train_2.forecast_origin_id, host_value=8.0, digest="D2"),
        val.forecast_origin_id: _snapshot(origin_id=val.forecast_origin_id, host_value=999.0, digest="DV"),
    }
    forward = build_fold_safe_reference(fold_id="FOLD:B", training_origins=[train_1, train_2], validation_origins=[val], raw_snapshots_by_origin_id=raw, transform_config=FactorTransformConfig())
    reversed_ = build_fold_safe_reference(fold_id="FOLD:B", training_origins=[train_2, train_1], validation_origins=[val], raw_snapshots_by_origin_id=raw, transform_config=FactorTransformConfig())
    assert forward.fold_reference_identity_hash() == reversed_.fold_reference_identity_hash()


def test_foldref_06_validation_transform_uses_matching_training_fold_reference_hash():
    train = _origin()
    val = _origin(forecast_origin_id="ORIGIN:Thailand:2023-06-01", t0="2023-06-01")
    raw = {
        train.forecast_origin_id: _snapshot(origin_id=train.forecast_origin_id, host_value=5.0, digest="D-TRAIN"),
        val.forecast_origin_id: _snapshot(origin_id=val.forecast_origin_id, host_value=999.0, digest="D-VAL"),
    }
    fold_ref = build_fold_safe_reference(fold_id="FOLD:2023", training_origins=[train], validation_origins=[val], raw_snapshots_by_origin_id=raw, transform_config=FactorTransformConfig())

    val_cell = raw[val.forecast_origin_id]["grid_cells"][0]
    candidates = build_host_factor_candidates(
        cell=val_cell, feature_snapshot_id="SNAP:VAL", reference_profile=fold_ref.reference_profile, transform_config=FactorTransformConfig(),
    )
    assert candidates["LOG1P_ROBUST_REFERENCE_SCALE"].reference_profile_hash == fold_ref.reference_profile.reference_profile_hash()


def test_fold_reference_propagates_nondefault_development_cutoff_to_nested_profile():
    train = _origin(forecast_origin_id="ORIGIN:Thailand:2024-06-01", t0="2024-06-01")
    val = _origin(forecast_origin_id="ORIGIN:Thailand:2025-06-01", t0="2025-06-01")

    fold_ref = build_fold_safe_reference(
        fold_id="FOLD:2025",
        training_origins=[train],
        validation_origins=[val],
        raw_snapshots_by_origin_id={},
        transform_config=FactorTransformConfig(),
        cutoff="2026-01-01",
    )

    assert fold_ref.reference_profile.development_cutoff == "2026-01-01"
    assert fold_ref.reference_profile.n_included_origins == 1
