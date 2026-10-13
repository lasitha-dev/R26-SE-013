"""Checkpoint 6D Part 32: leakage tests — FACTOR-LEAK-01..05."""

from __future__ import annotations

import inspect

import pytest

from components.geospatial_tracking.services.factors import factor_snapshot, host_transform, reference_profile
from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(
        forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01",
        temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1,
    )
    fields.update(overrides)
    return ForecastOrigin(**fields)


def test_factor_leak_01_held_out_origin_rejected():
    held_out = _origin(forecast_origin_id="ORIGIN:Thailand:2024-06-01", t0="2024-06-01")
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        reference_profile.build_factor_reference_profile(
            fit_development_origins=[held_out], feature_snapshots_by_origin_id={}, transform_config=FactorTransformConfig(),
        )


def test_factor_leak_02_sri_lanka_origin_rejected():
    sri_lanka = _origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-06-01", country="Sri Lanka", t0="2020-06-01")
    with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
        reference_profile.build_factor_reference_profile(
            fit_development_origins=[sri_lanka], feature_snapshots_by_origin_id={}, transform_config=FactorTransformConfig(),
        )


def test_factor_leak_03_mixed_development_and_held_out_rejects_whole_call():
    good = _origin()
    held_out = _origin(forecast_origin_id="ORIGIN:Thailand:2024-06-01", t0="2024-06-01")
    with pytest.raises(ValueError):
        reference_profile.build_factor_reference_profile(
            fit_development_origins=[good, held_out], feature_snapshots_by_origin_id={}, transform_config=FactorTransformConfig(),
        )


def test_factor_leak_04_no_future_target_outcome_parameter_in_factor_apis():
    modules = [factor_snapshot, host_transform, reference_profile]
    forbidden_substrings = ("target", "future", "outcome", "label", "capture", "direction_error", "speed_error", "accuracy")
    for mod in modules:
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            params = set(inspect.signature(fn).parameters)
            for p in params:
                assert not any(f in p.lower() for f in forbidden_substrings), f"{mod.__name__}.{name} has forbidden parameter {p!r}"


def test_factor_leak_05_package_never_inspects_prediction_performance():
    # Structural check (not raw text search -- module docstrings
    # legitimately NAME these forbidden concepts while explaining they
    # are absent, which would false-positive a substring search): no
    # function parameter and no dataclass field anywhere in the package
    # is named after a performance/outcome metric.
    import dataclasses

    import components.geospatial_tracking.services.factors.audit as audit_mod
    import components.geospatial_tracking.services.factors.factor_snapshot as factor_snapshot_mod
    import components.geospatial_tracking.services.factors.reference_profile as reference_profile_mod

    forbidden = {"capture_rate", "direction_error", "speed_error", "auc", "prediction_accuracy", "held_out_performance"}
    for mod in (audit_mod, factor_snapshot_mod, reference_profile_mod):
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            params = {p.lower() for p in inspect.signature(fn).parameters}
            assert not (params & forbidden), f"{mod.__name__}.{name} has forbidden parameter(s) {params & forbidden}"
        for name, cls in inspect.getmembers(mod, inspect.isclass):
            if dataclasses.is_dataclass(cls):
                field_names = {f.lower() for f in cls.__dataclass_fields__}
                assert not (field_names & forbidden), f"{mod.__name__}.{cls.__name__} has forbidden field(s) {field_names & forbidden}"
