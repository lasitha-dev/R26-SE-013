"""Checkpoint 7C Part 21: 7C-LEAK-01..07 leakage-safety tests."""

from __future__ import annotations

import inspect
from datetime import timedelta

import pytest

from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
from components.geospatial_tracking.services.geospatial.weather.base import T0Precision
from components.geospatial_tracking.services.geospatial.weather.era5 import build_pre_t0_weather_summary
from components.geospatial_tracking.services.geospatial.weather.t0_resolution import pre_t0_window_bounds, resolve_t0_boundary
from components.geospatial_tracking.services.model_development import development_run_7b, development_run_7c
from components.geospatial_tracking.services.model_development.candidate_registry_7c import (
    ANISOTROPY_MODE_CANDIDATES,
    ANISOTROPY_STRENGTH_CANDIDATES,
    build_candidate_registry_7c,
    candidate_registry_hash_7c,
)
from components.geospatial_tracking.services.model_development.development_run_7c import run_checkpoint_7c_development
from components.geospatial_tracking.services.model_development import wind_readiness_7c
from components.geospatial_tracking.services.model_development.wind_readiness_7c import resolve_origin_wind
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


def test_7cleak_01_held_out_origin_hard_rejects_before_any_repository_access():
    good = _origin()
    held_out = _origin(forecast_origin_id="ORIGIN:Thailand:2024-06-01", t0="2024-06-01")
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        run_checkpoint_7c_development(_TouchRepo(), fit_development_origins=[good, held_out], disease=DISEASE, active_window_days=14, grid_config=_grid_config())


def test_7cleak_02_sri_lanka_origin_hard_rejects_before_any_repository_access():
    good = _origin()
    sri_lanka = _origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-06-01", country="Sri Lanka", t0="2020-06-01")
    with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
        run_checkpoint_7c_development(_TouchRepo(), fit_development_origins=[good, sri_lanka], disease=DISEASE, active_window_days=14, grid_config=_grid_config())


def test_7cleak_03_wind_acquisition_signature_has_no_future_horizon_or_override_parameter():
    params = set(inspect.signature(resolve_origin_wind).parameters)
    forbidden = {"allow_future_reanalysis", "lead_days", "horizon_days", "future_reanalysis", "d1_d7_weather"}
    assert not (params & forbidden)
    # resolve_origin_wind always requests T0Precision.DATE_ONLY -- never lets
    # a caller widen the window past t0 via a different precision.
    src = inspect.getsource(wind_readiness_7c)
    assert "T0Precision.DATE_ONLY.value" in src


class _FixedPayloadCache:
    """Duck-typed weather cache stub (`.get`/`.set`) that always returns
    the SAME pre-built payload, regardless of the request key -- isolates
    `build_pre_t0_weather_summary`'s own eligible-hour filtering from real
    cache-key computation (LEAK-04/05)."""

    def __init__(self, payload: dict):
        self._payload = payload

    def get(self, key):
        return self._payload

    def set(self, key, payload):
        pass


def _payload_with_hours(*, in_window_wind: tuple[float, float], out_of_window_wind: tuple[float, float], window_start, cutoff):
    in_ts = (window_start + (cutoff - window_start) / 2).replace(minute=0, second=0, microsecond=0)
    out_ts = (cutoff + timedelta(hours=6)).replace(minute=0, second=0, microsecond=0)
    return {
        "hourly": {
            "time": [in_ts.isoformat(), out_ts.isoformat()],
            "temperature_2m": [20.0, 999.0],
            "dew_point_2m": [10.0, 999.0],
            "precipitation": [0.0, 999.0],
            "wind_speed_10m": [in_window_wind[0], out_of_window_wind[0]],
            "wind_direction_10m": [in_window_wind[1], out_of_window_wind[1]],
        }
    }


def test_7cleak_04_realized_future_weather_value_cannot_change_the_wind_result():
    t0 = "2021-06-10T00:00:00+00:00"
    boundary = resolve_t0_boundary(t0=t0, t0_precision=T0Precision.TIMESTAMP.value, latitude=13.75, longitude=100.5)
    window_start, cutoff = pre_t0_window_bounds(boundary, 24.0)

    payload_a = _payload_with_hours(in_window_wind=(5.0, 90.0), out_of_window_wind=(5.0, 90.0), window_start=window_start, cutoff=cutoff)
    payload_b = _payload_with_hours(in_window_wind=(5.0, 90.0), out_of_window_wind=(500.0, 270.0), window_start=window_start, cutoff=cutoff)

    _win_a, results_a = build_pre_t0_weather_summary(latitude=13.75, longitude=100.5, t0=t0, t0_precision=T0Precision.TIMESTAMP.value, lookback_hours=24.0, cache=_FixedPayloadCache(payload_a))
    _win_b, results_b = build_pre_t0_weather_summary(latitude=13.75, longitude=100.5, t0=t0, t0_precision=T0Precision.TIMESTAMP.value, lookback_hours=24.0, cache=_FixedPayloadCache(payload_b))

    u10_a = next(r for r in results_a if r.feature_name == "mean_u10").value
    u10_b = next(r for r in results_b if r.feature_name == "mean_u10").value
    assert u10_a == u10_b, "a wind value dated strictly after t0 (REALIZED_FUTURE_REANALYSIS) changed the primary pre-t0 wind result"


def test_7cleak_05_pre_t0_weather_change_does_change_the_wind_result():
    t0 = "2021-06-10T00:00:00+00:00"
    boundary = resolve_t0_boundary(t0=t0, t0_precision=T0Precision.TIMESTAMP.value, latitude=13.75, longitude=100.5)
    window_start, cutoff = pre_t0_window_bounds(boundary, 24.0)

    payload_a = _payload_with_hours(in_window_wind=(5.0, 90.0), out_of_window_wind=(5.0, 90.0), window_start=window_start, cutoff=cutoff)
    payload_b = _payload_with_hours(in_window_wind=(20.0, 180.0), out_of_window_wind=(5.0, 90.0), window_start=window_start, cutoff=cutoff)

    _win_a, results_a = build_pre_t0_weather_summary(latitude=13.75, longitude=100.5, t0=t0, t0_precision=T0Precision.TIMESTAMP.value, lookback_hours=24.0, cache=_FixedPayloadCache(payload_a))
    _win_b, results_b = build_pre_t0_weather_summary(latitude=13.75, longitude=100.5, t0=t0, t0_precision=T0Precision.TIMESTAMP.value, lookback_hours=24.0, cache=_FixedPayloadCache(payload_b))

    u10_a = next(r for r in results_a if r.feature_name == "mean_u10").value
    u10_b = next(r for r in results_b if r.feature_name == "mean_u10").value
    assert u10_a != u10_b, "changing a genuinely pre-t0 hourly wind value should change the primary wind result"


def test_7cleak_06_purge_delegates_unmodified_to_the_frozen_calendar_year_fold_builder():
    import components.geospatial_tracking.services.model_fitting_exposure as exposure_mod

    assert development_run_7c.build_calendar_year_folds is exposure_mod.build_calendar_year_folds
    assert development_run_7b.build_calendar_year_folds is exposure_mod.build_calendar_year_folds

    late_2021 = _origin(forecast_origin_id="ORIGIN:Thailand:2021-12-28", t0="2021-12-28")
    early_2022 = _origin(forecast_origin_id="ORIGIN:Thailand:2022-01-15", t0="2022-01-15")
    folds = build_calendar_year_folds([late_2021, early_2022])
    fold_2022 = next(f for f in folds if f.validation_year == 2022)
    assert late_2021.forecast_origin_id in fold_2022.purged_origin_ids
    assert late_2021.forecast_origin_id not in fold_2022.training_origin_ids


def test_7cleak_07_candidate_registry_and_anisotropy_strengths_take_no_target_or_validation_input():
    params = set(inspect.signature(build_candidate_registry_7c).parameters)
    assert params == set()
    assert ANISOTROPY_STRENGTH_CANDIDATES == (0.25, 0.50, 1.00, 2.00)
    assert set(ANISOTROPY_MODE_CANDIDATES) == {"MODULATING", "ANGULAR_NORMALIZED"}
    assert candidate_registry_hash_7c() == candidate_registry_hash_7c()  # pure, no external state
