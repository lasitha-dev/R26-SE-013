"""Checkpoint 6D Part 33: reference profile tests — REF-01..07."""

from __future__ import annotations

import time

from components.geospatial_tracking.services.factors.reference_profile import build_factor_reference_profile
from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin


def _real_fr(value, *, feature_name, dataset_name="DATASET", dataset_version="v1", units="u", sample_identity=None):
    return {"feature_name": feature_name, "value": value, "units": units, "status": "REAL", "dataset_name": dataset_name, "dataset_version": dataset_version, "sample_identity": sample_identity}


def _cell(cell_id, lat, lon, *, cattle, buffalo, dataset_version="2015", sample_identity=None):
    # host-density units MUST be the real canonical unit (Part 11) --
    # the new unit-safety check rejects anything else.
    return {
        "grid_cell_id": cell_id, "centroid_lat": lat, "centroid_lon": lon,
        "host_density": {
            "cattle": _real_fr(cattle, feature_name="host_density_cattle_grid_cell", dataset_version=dataset_version, units="animals_per_km2", sample_identity=sample_identity),
            "buffalo": _real_fr(buffalo, feature_name="host_density_buffalo_grid_cell", dataset_version=dataset_version, units="animals_per_km2", sample_identity=sample_identity),
        },
        "landcover": {}, "hydrology": None,
    }


def _snapshot(snapshot_id, *, cells, lat=15.0, lon=101.0, window_start="2021-06-01T00:00:00+00:00", window_end="2021-06-02T00:00:00+00:00"):
    return {
        "snapshot_id": snapshot_id,
        "grid_cells": cells,
        "weather": {
            "window": {"weather_model": "era5", "request_parameters": {"latitude": lat, "longitude": lon}, "window_start": window_start, "window_end": window_end},
            "results": {
                "mean_u10": _real_fr(2.0, feature_name="mean_u10", dataset_name="ERA5"),
                "mean_v10": _real_fr(1.0, feature_name="mean_v10", dataset_name="ERA5"),
                "mean_temperature_2m": _real_fr(28.0, feature_name="mean_temperature_2m", dataset_name="ERA5"),
                "mean_relative_humidity_2m": _real_fr(80.0, feature_name="mean_relative_humidity_2m", dataset_name="ERA5"),
                "precipitation_accumulation": _real_fr(1.0, feature_name="precipitation_accumulation", dataset_name="ERA5"),
            },
        },
        "source_dataset_versions": {"host_density": "GLW4 2015", "weather": "ERA5"},
        "landcover_comparability_group": "WORLDCOVER_V200",
    }


def _origin(oid="ORIGIN:Thailand:2021-06-01", t0="2021-06-01", country="Thailand") -> ForecastOrigin:
    return ForecastOrigin(forecast_origin_id=oid, country=country, t0=t0, temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)


def test_ref_01_same_inputs_same_hash():
    origin = _origin()
    snap = _snapshot("SNAPSHOT:A", cells=[_cell("C1", 15.0, 101.0, cattle=10.0, buffalo=2.0)])
    tc = FactorTransformConfig()
    p1 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc)
    p2 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc)
    assert p1.reference_profile_hash() == p2.reference_profile_hash()


def test_ref_02_generated_at_does_not_affect_hash():
    origin = _origin()
    snap = _snapshot("SNAPSHOT:A", cells=[_cell("C1", 15.0, 101.0, cattle=10.0, buffalo=2.0)])
    tc = FactorTransformConfig()
    p1 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc, generated_at="2020-01-01T00:00:00Z")
    time.sleep(0.01)
    p2 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc, generated_at="2030-01-01T00:00:00Z")
    assert p1.reference_profile_hash() == p2.reference_profile_hash()


def test_ref_03_changed_development_observation_changes_hash():
    origin = _origin()
    snap1 = _snapshot("SNAPSHOT:A", cells=[_cell("C1", 15.0, 101.0, cattle=10.0, buffalo=2.0)])
    snap2 = _snapshot("SNAPSHOT:A", cells=[_cell("C1", 15.0, 101.0, cattle=99.0, buffalo=2.0)])
    tc = FactorTransformConfig()
    p1 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap1}, transform_config=tc)
    p2 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap2}, transform_config=tc)
    assert p1.reference_profile_hash() != p2.reference_profile_hash()


def test_ref_04_aoi_min_max_never_used():
    # structural: build_factor_reference_profile has no per-AOI/per-origin
    # min-max parameter at all -- it only accepts the FULL FIT_DEVELOPMENT
    # origin set and their snapshots, computing one pooled profile.
    import inspect

    from components.geospatial_tracking.services.factors.reference_profile import build_factor_reference_profile as fn

    params = set(inspect.signature(fn).parameters)
    assert not any("aoi" in p.lower() or "this_origin" in p.lower() for p in params)


def test_ref_05_duplicate_raw_appearances_do_not_pseudo_replicate():
    origin = _origin()
    # same real-world coordinate + same dataset appearing twice within one
    # snapshot's cells (e.g. a data artifact) must count once.
    snap = _snapshot("SNAPSHOT:A", cells=[
        _cell("C1", 15.0, 101.0, cattle=10.0, buffalo=2.0),
        _cell("C2", 15.0, 101.0, cattle=10.0, buffalo=2.0),  # identical real-world location + dataset
    ])
    tc = FactorTransformConfig()
    profile = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc)
    assert profile.host_density_total_raw_appearances == 2
    assert profile.host_density_total_unique_observations == 1


def test_ref_06_one_aoi_center_weather_observation_across_cells_counts_once():
    origin = _origin()
    snap = _snapshot("SNAPSHOT:A", cells=[_cell(f"C{i}", 15.0, 101.0, cattle=10.0, buffalo=2.0) for i in range(25)])
    tc = FactorTransformConfig()
    profile = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc)
    assert profile.weather_reference_observation_counts["mean_u10"]["raw_appearances"] == 1
    assert profile.weather_reference_observation_counts["mean_u10"]["unique_observations"] == 1


def test_ref_07_dataset_version_included_in_identity():
    # SUPERSEDED_BY_6D5_COMPATIBILITY_FIREWALL: Checkpoint 6D's version
    # of this test expected two different dataset_version observations
    # to simply pool as 2 separate reference values. Checkpoint 6D.5
    # Part 7-8 correctly REFUSES to pool incompatible dataset strata at
    # all (a stronger guarantee) -- so this now asserts the firewall
    # triggers (INCOMPATIBLE_REFERENCE_STRATA, 0 pooled), never a
    # silent 2-value pool. dataset_version still participates in
    # identity, just at the stratum-compatibility layer now, not only
    # observation-identity layer.
    origin = _origin()
    cell_a = _cell("C1", 15.0, 101.0, cattle=10.0, buffalo=2.0, dataset_version="2015")
    cell_b = _cell("C2", 15.0, 101.0, cattle=10.0, buffalo=2.0, dataset_version="2020")
    snap = _snapshot("SNAPSHOT:A", cells=[cell_a, cell_b])
    tc = FactorTransformConfig()
    profile = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc)
    assert profile.status == "INCOMPATIBLE_REFERENCE_STRATA"
    assert profile.host_density_total_unique_observations == 0
    assert profile.n_incompatible_strata_detected == 2
