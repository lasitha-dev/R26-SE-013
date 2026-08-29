"""Checkpoint 7B Part 38: 7B-LEAK-01..06 leakage-safety tests."""

from __future__ import annotations

import inspect

import pytest

from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.geospatial.host_density.fao_glw import DATASET_NAME, REFERENCE_YEAR, UNITS
from components.geospatial_tracking.services.geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
from components.geospatial_tracking.services.model_development import development_run_7b
from components.geospatial_tracking.services.model_development.candidate_registry_7b import KERNEL_SCALE_CANDIDATES_KM, build_candidate_registry, candidate_registry_hash
from components.geospatial_tracking.services.model_development.development_run_7b import run_checkpoint_7b_development
from components.geospatial_tracking.services.model_development.fold_reference import build_fold_safe_reference
from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.model_fitting_exposure import build_calendar_year_folds

DISEASE = "Lumpy skin disease"


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)
    fields.update(overrides)
    return ForecastOrigin(**fields)


def _grid_config() -> ScientificGridConfig:
    return ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)


class _TouchRepo:
    def __getattr__(self, name):
        def _fail(*args, **kwargs):
            raise AssertionError(f"repository method {name!r} was called before the FIT_DEVELOPMENT firewall check")
        return _fail


def test_7bleak_01_held_out_origin_hard_rejects_before_any_repository_access():
    good = _origin()
    held_out = _origin(forecast_origin_id="ORIGIN:Thailand:2024-06-01", t0="2024-06-01")
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        run_checkpoint_7b_development(_TouchRepo(), fit_development_origins=[good, held_out], disease=DISEASE, active_window_days=14, grid_config=_grid_config())


def test_7bleak_02_sri_lanka_origin_hard_rejects_before_any_repository_access():
    good = _origin()
    sri_lanka = _origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-06-01", country="Sri Lanka", t0="2020-06-01")
    with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
        run_checkpoint_7b_development(_TouchRepo(), fit_development_origins=[good, sri_lanka], disease=DISEASE, active_window_days=14, grid_config=_grid_config())


def test_7bleak_03_build_fold_safe_reference_also_rejects_mixed_roles_in_either_list():
    good = _origin()
    held_out = _origin(forecast_origin_id="ORIGIN:Thailand:2024-06-01", t0="2024-06-01")
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        build_fold_safe_reference(
            fold_id="FOLD:X", training_origins=[good], validation_origins=[held_out], raw_snapshots_by_origin_id={},
            transform_config=FactorTransformConfig(),
        )
    sri_lanka = _origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-06-01", country="Sri Lanka", t0="2020-06-01")
    with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
        build_fold_safe_reference(
            fold_id="FOLD:X", training_origins=[good, sri_lanka], validation_origins=[], raw_snapshots_by_origin_id={},
            transform_config=FactorTransformConfig(),
        )


def test_7bleak_04_changing_validation_host_value_cannot_change_training_reference_hash():
    # see test_checkpoint_7b_fold_reference.py::test_foldref_02 for the
    # full behavioral proof; this asserts the SAME invariant holds via a
    # direct call here too, per the checkpoint's own LEAK-04 ticket.
    train = _origin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", t0="2021-06-01")
    val = _origin(forecast_origin_id="ORIGIN:Thailand:2023-06-01", t0="2023-06-01")

    def _snap(origin_id, value, digest):
        return {
            "snapshot_id": f"SNAP:{origin_id}", "forecast_origin_id": origin_id, "active_source_ids": ["S1"],
            "grid_cells": [{
                "grid_cell_id": f"CELL:{origin_id}", "scientific_cell_id": f"SCICELL:{origin_id}",
                "centroid_lat": 15.0, "centroid_lon": 101.0, "area_km2": 25.0, "domain_overlap_area_km2": 25.0,
                "host_density": {
                    "cattle": {"status": "REAL", "value": value, "units": UNITS, "dataset_name": DATASET_NAME, "dataset_version": REFERENCE_YEAR, "sample_support_digest": digest},
                    "buffalo": {"status": "REAL", "value": 0.0, "units": UNITS, "dataset_name": DATASET_NAME, "dataset_version": REFERENCE_YEAR, "sample_support_digest": digest + ":b"},
                },
            }],
            "weather": {}, "source_dataset_versions": {}, "landcover_comparability_group": None,
        }

    raw_a = {train.forecast_origin_id: _snap(train.forecast_origin_id, 5.0, "D-T"), val.forecast_origin_id: _snap(val.forecast_origin_id, 1.0, "D-V-1")}
    raw_b = {train.forecast_origin_id: _snap(train.forecast_origin_id, 5.0, "D-T"), val.forecast_origin_id: _snap(val.forecast_origin_id, 555.0, "D-V-2")}
    ref_a = build_fold_safe_reference(fold_id="F", training_origins=[train], validation_origins=[val], raw_snapshots_by_origin_id=raw_a, transform_config=FactorTransformConfig())
    ref_b = build_fold_safe_reference(fold_id="F", training_origins=[train], validation_origins=[val], raw_snapshots_by_origin_id=raw_b, transform_config=FactorTransformConfig())
    assert ref_a.reference_profile.reference_profile_hash() == ref_b.reference_profile.reference_profile_hash()


def test_7bleak_05_candidate_registry_and_kernel_scales_take_no_target_or_validation_input():
    params = set(inspect.signature(build_candidate_registry).parameters)
    assert params == set()
    assert KERNEL_SCALE_CANDIDATES_KM == (5.0, 10.0, 15.0, 25.0)
    assert candidate_registry_hash() == candidate_registry_hash()  # pure, no external state


def test_7bleak_06_purge_delegates_unmodified_to_the_frozen_calendar_year_fold_builder():
    import components.geospatial_tracking.services.model_fitting_exposure as exposure_mod

    assert development_run_7b.build_calendar_year_folds is exposure_mod.build_calendar_year_folds

    # reproduce the frozen purge scenario directly against the SAME
    # function 7B calls: an origin whose D1-D7 window crosses the
    # 2022-01-01 boundary must be purged out of 2021's training set.
    late_2021 = _origin(forecast_origin_id="ORIGIN:Thailand:2021-12-28", t0="2021-12-28")
    early_2022 = _origin(forecast_origin_id="ORIGIN:Thailand:2022-01-15", t0="2022-01-15")
    folds = build_calendar_year_folds([late_2021, early_2022])
    fold_2022 = next(f for f in folds if f.validation_year == 2022)
    assert late_2021.forecast_origin_id in fold_2022.purged_origin_ids
    assert late_2021.forecast_origin_id not in fold_2022.training_origin_ids
