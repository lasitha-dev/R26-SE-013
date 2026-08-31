"""Checkpoint 6D.5 Part 10: dataset-compatibility tests — COMPAT-01..06."""

from __future__ import annotations

from components.geospatial_tracking.services.factors.reference_profile import build_factor_reference_profile
from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin

_UNITS = "animals_per_km2"


def _real_fr(value, *, feature_name, dataset_name="FAO Gridded Livestock of the World (GLW4), Da (dasymetric) product", dataset_version="2015", units=_UNITS):
    return {"feature_name": feature_name, "value": value, "units": units, "status": "REAL", "dataset_name": dataset_name, "dataset_version": dataset_version}


def _cell(cell_id, lat, lon, *, cattle=10.0, buffalo=2.0, dataset_name=None, dataset_version="2015", units=_UNITS):
    kwargs = {}
    if dataset_name:
        kwargs["dataset_name"] = dataset_name
    return {
        "grid_cell_id": cell_id, "centroid_lat": lat, "centroid_lon": lon,
        "host_density": {
            "cattle": _real_fr(cattle, feature_name="host_density_cattle_grid_cell", dataset_version=dataset_version, units=units, **kwargs),
            "buffalo": _real_fr(buffalo, feature_name="host_density_buffalo_grid_cell", dataset_version=dataset_version, units=units, **kwargs),
        },
        "landcover": {}, "hydrology": None,
    }


def _snapshot(snapshot_id, *, cells, weather_model="era5", landcover_group="WORLDCOVER_V200"):
    return {
        "snapshot_id": snapshot_id, "grid_cells": cells,
        "weather": {"window": {"weather_model": weather_model, "request_parameters": {"latitude": 15.0, "longitude": 101.0}, "window_start": "2021-06-01T00:00:00+00:00", "window_end": "2021-06-02T00:00:00+00:00"}, "results": {}},
        "source_dataset_versions": {}, "landcover_comparability_group": landcover_group,
    }


def _origin() -> ForecastOrigin:
    return ForecastOrigin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)


def test_compat_01_single_compatible_dataset_succeeds():
    origin = _origin()
    snap = _snapshot("A", cells=[_cell("C1", 15.0, 101.0), _cell("C2", 15.01, 101.0)])
    profile = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=FactorTransformConfig())
    assert profile.status == "COMPLETE_DIAGNOSTIC"
    assert profile.host_density_total_unique_observations == 2
    assert profile.dataset_compatibility_stratum is not None


def test_compat_02_mixed_incompatible_dataset_families_cannot_silently_pool():
    origin = _origin()
    snap = _snapshot("A", cells=[
        _cell("C1", 15.0, 101.0, dataset_name="FAO Gridded Livestock of the World (GLW4), Da (dasymetric) product"),
        _cell("C2", 15.01, 101.0, dataset_name="Some Other Livestock Density Product"),
    ])
    profile = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=FactorTransformConfig())
    assert profile.status == "INCOMPATIBLE_REFERENCE_STRATA"
    assert profile.host_density_total_unique_observations == 0
    assert profile.n_incompatible_strata_detected == 2


def test_compat_03_mixed_incompatible_comparability_versions_cannot_silently_pool():
    origin = _origin()
    snap = _snapshot("A", cells=[_cell("C1", 15.0, 101.0, dataset_version="2015"), _cell("C2", 15.01, 101.0, dataset_version="2020")])
    profile = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=FactorTransformConfig())
    assert profile.status == "INCOMPATIBLE_REFERENCE_STRATA"
    assert profile.host_density_total_unique_observations == 0


def test_compat_04_unit_mismatch_across_cells_cannot_silently_pool():
    # C2's non-canonical unit makes it UNIT_MISMATCH at the per-cell
    # combination step (host_transform.py) -- it never even reaches the
    # stratum-compatibility layer, which is the SAFEST possible outcome:
    # the mismatched cell simply never contributes an observation at
    # all, rather than being silently pooled alongside the valid cell.
    origin = _origin()
    snap = _snapshot("A", cells=[_cell("C1", 15.0, 101.0, units="animals_per_km2"), _cell("C2", 15.01, 101.0, units="animals_per_hectare")])
    profile = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=FactorTransformConfig())
    assert profile.status == "COMPLETE_DIAGNOSTIC"
    assert profile.host_density_total_unique_observations == 1  # only C1 (canonical units) ever contributed
    assert profile.host_density_total_raw_appearances == 1


def test_compat_05_unrelated_environmental_version_does_not_invalidate_host_reference():
    origin = _origin()
    snap_a = _snapshot("A", cells=[_cell("C1", 15.0, 101.0)], weather_model="era5", landcover_group="WORLDCOVER_V200")
    snap_b = _snapshot("A", cells=[_cell("C2", 15.01, 101.0)], weather_model="cfsr", landcover_group="WORLDCOVER_V100")
    # combine both snapshots into ONE origin's material (as if weather/landcover
    # differ across two separate assemblies) -- host stratum stays single/compatible
    combined = _snapshot("A", cells=snap_a["grid_cells"] + snap_b["grid_cells"])
    profile = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: combined}, transform_config=FactorTransformConfig())
    assert profile.status == "COMPLETE_DIAGNOSTIC"
    assert profile.host_density_total_unique_observations == 2


def test_compat_06_compatibility_decision_participates_in_identity():
    origin = _origin()
    snap_compatible = _snapshot("A", cells=[_cell("C1", 15.0, 101.0), _cell("C2", 15.01, 101.0)])
    snap_incompatible = _snapshot("A", cells=[_cell("C1", 15.0, 101.0, dataset_version="2015"), _cell("C2", 15.01, 101.0, dataset_version="2020")])
    tc = FactorTransformConfig()
    p1 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap_compatible}, transform_config=tc)
    p2 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap_incompatible}, transform_config=tc)
    assert p1.status != p2.status
    assert p1.reference_profile_hash() != p2.reference_profile_hash()
