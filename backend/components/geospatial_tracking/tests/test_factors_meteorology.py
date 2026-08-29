"""Checkpoint 6D Part 37: meteorology tests — MET-01..06."""

from __future__ import annotations

from components.geospatial_tracking.services.factors.meteorology_adapter import (
    WIND_SPEED_EFFECT_NOT_YET_SELECTED,
    RealMeteorologyObservation,
    build_meteorology_by_cell,
)
from components.geospatial_tracking.services.hazard.meteorology import MeteorologySpatialMode


def _real_fr(value, *, feature_name, dataset_name="ERA5"):
    return {"feature_name": feature_name, "value": value, "units": "m/s", "status": "REAL", "dataset_name": dataset_name, "dataset_version": "v1"}


def _snapshot(*, u10=2.0, v10=1.0, u10_status="REAL", v10_status="REAL"):
    u_fr = _real_fr(u10, feature_name="mean_u10") if u10_status == "REAL" else {"feature_name": "mean_u10", "value": None, "status": u10_status, "dataset_name": "ERA5"}
    v_fr = _real_fr(v10, feature_name="mean_v10") if v10_status == "REAL" else {"feature_name": "mean_v10", "value": None, "status": v10_status, "dataset_name": "ERA5"}
    return {"weather": {"window": {"weather_model": "era5"}, "results": {"mean_u10": u_fr, "mean_v10": v_fr}}}


def test_met_01_u10_v10_pairing_preserved():
    snap = _snapshot(u10=3.0, v10=4.0)
    result = build_meteorology_by_cell(snap, expected_grid_cell_ids=["C1"])
    assert result["C1"].u10 == 3.0
    assert result["C1"].v10 == 4.0


def test_met_02_aoi_center_real_weather_labeled_proxy():
    snap = _snapshot()
    result = build_meteorology_by_cell(snap, expected_grid_cell_ids=["C1", "C2", "C3"])
    for cid, obs in result.items():
        assert obs.spatial_mode == MeteorologySpatialMode.AOI_CENTER_UNIFORM_REAL_PROXY.value


def test_met_03_mode_never_spatially_resolved_real():
    snap = _snapshot()
    result = build_meteorology_by_cell(snap, expected_grid_cell_ids=["C1"])
    assert result["C1"].spatial_mode != MeteorologySpatialMode.SPATIALLY_RESOLVED_REAL.value


def test_met_04_missing_real_weather_remains_missing():
    snap = _snapshot(u10_status="MISSING", v10_status="MISSING")
    result = build_meteorology_by_cell(snap, expected_grid_cell_ids=["C1"])
    assert result["C1"].u10 is None
    assert result["C1"].u10_status == "MISSING"
    assert result["C1"].v10 is None


def test_met_05_wind_speed_not_converted_to_hazard_multiplier():
    snap = _snapshot()
    result = build_meteorology_by_cell(snap, expected_grid_cell_ids=["C1"])
    assert result["C1"].wind_speed_effect_status == WIND_SPEED_EFFECT_NOT_YET_SELECTED


def test_met_06_wind_vector_never_called_disease_direction():
    forbidden = {"disease_direction", "transmission_bearing", "spread_direction"}
    field_names = {n.lower() for n in RealMeteorologyObservation.__dataclass_fields__}
    assert not (field_names & forbidden)
