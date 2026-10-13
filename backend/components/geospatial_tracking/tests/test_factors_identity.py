"""Checkpoint 6D Part 38: FactorSnapshot identity tests — FACTOR-ID-01..07."""

from __future__ import annotations

import copy
import time

from components.geospatial_tracking.services.factors.factor_snapshot import build_factor_snapshot
from components.geospatial_tracking.services.factors.reference_profile import build_factor_reference_profile
from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin


def _real_fr(value, *, feature_name, dataset_name="GLW4", dataset_version="2015", units="animals_per_km2"):
    return {"feature_name": feature_name, "value": value, "units": units, "status": "REAL", "dataset_name": dataset_name, "dataset_version": dataset_version}


def _cell(cell_id, lat, lon, *, cattle=10.0, buffalo=2.0):
    return {
        "grid_cell_id": cell_id, "centroid_lat": lat, "centroid_lon": lon,
        "host_density": {"cattle": _real_fr(cattle, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(buffalo, feature_name="host_density_buffalo_grid_cell")},
        "landcover": {}, "hydrology": None,
    }


def _snapshot(snapshot_id="SNAPSHOT:A", *, cattle=10.0, lat=15.0, lon=101.0):
    return {
        "snapshot_id": snapshot_id,
        "active_source_ids": ["SRC1"],
        "grid_cells": [_cell("C1", lat, lon, cattle=cattle)],
        "weather": {
            "window": {"weather_model": "era5", "request_parameters": {"latitude": lat, "longitude": lon}, "window_start": "2021-06-01T00:00:00+00:00", "window_end": "2021-06-02T00:00:00+00:00"},
            "results": {
                "mean_u10": _real_fr(2.0, feature_name="mean_u10", dataset_name="ERA5", units="m/s"),
                "mean_v10": _real_fr(1.0, feature_name="mean_v10", dataset_name="ERA5", units="m/s"),
                "mean_temperature_2m": _real_fr(28.0, feature_name="mean_temperature_2m", dataset_name="ERA5", units="degC"),
                "mean_relative_humidity_2m": _real_fr(80.0, feature_name="mean_relative_humidity_2m", dataset_name="ERA5", units="%"),
                "precipitation_accumulation": _real_fr(1.0, feature_name="precipitation_accumulation", dataset_name="ERA5", units="mm"),
            },
        },
        "source_dataset_versions": {}, "landcover_comparability_group": "WORLDCOVER_V200",
    }


def _origin() -> ForecastOrigin:
    return ForecastOrigin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["SRC1"], trigger_source_count=1)


def _build(snapshot, *, transform_config=None):
    origin = _origin()
    tc = transform_config or FactorTransformConfig()
    profile = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snapshot}, transform_config=tc)
    return build_factor_snapshot(
        feature_snapshot=snapshot, forecast_origin_id=origin.forecast_origin_id, t0=origin.t0,
        expected_grid_cell_ids=["C1"], active_source_ids=["SRC1"], reference_profile=profile, transform_config=tc,
    )


def test_factor_id_01_same_inputs_same_id():
    snap = _snapshot()
    fs1 = _build(copy.deepcopy(snap))
    fs2 = _build(copy.deepcopy(snap))
    assert fs1.factor_snapshot_id == fs2.factor_snapshot_id


def test_factor_id_02_raw_host_value_change_different_id():
    fs1 = _build(_snapshot(cattle=10.0))
    fs2 = _build(_snapshot(cattle=99.0))
    assert fs1.factor_snapshot_id != fs2.factor_snapshot_id


def test_factor_id_03_reference_profile_change_different_id():
    origin = _origin()
    snap = _snapshot()
    tc = FactorTransformConfig()
    profile_a = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc)
    other_snap = _snapshot(cattle=500.0)
    profile_b = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: other_snap}, transform_config=tc)
    fs_a = build_factor_snapshot(feature_snapshot=snap, forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, expected_grid_cell_ids=["C1"], active_source_ids=["SRC1"], reference_profile=profile_a, transform_config=tc)
    fs_b = build_factor_snapshot(feature_snapshot=snap, forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, expected_grid_cell_ids=["C1"], active_source_ids=["SRC1"], reference_profile=profile_b, transform_config=tc)
    assert fs_a.reference_profile_hash != fs_b.reference_profile_hash
    assert fs_a.factor_snapshot_id != fs_b.factor_snapshot_id


def test_factor_id_04_transform_config_change_different_id():
    snap = _snapshot()
    fs1 = _build(copy.deepcopy(snap), transform_config=FactorTransformConfig(log1p_reference_lower_quantile=0.05, log1p_reference_upper_quantile=0.95))
    fs2 = _build(copy.deepcopy(snap), transform_config=FactorTransformConfig(log1p_reference_lower_quantile=0.10, log1p_reference_upper_quantile=0.90))
    assert fs1.factor_transform_config_hash != fs2.factor_transform_config_hash
    assert fs1.factor_snapshot_id != fs2.factor_snapshot_id


def test_factor_id_05_meteorology_spatial_provenance_change_different_id():
    from components.geospatial_tracking.services.factors import factor_snapshot as fsmod

    origin = _origin()
    snap = _snapshot()
    tc = FactorTransformConfig()
    profile = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc)
    fs1 = build_factor_snapshot(feature_snapshot=snap, forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, expected_grid_cell_ids=["C1"], active_source_ids=["SRC1"], reference_profile=profile, transform_config=tc)

    # directly recompute the ID with a mutated meteorology_by_cell spatial_mode
    import components.geospatial_tracking.services.factors.meteorology_adapter as met_mod

    real_meteorology = met_mod.build_meteorology_by_cell(snap, expected_grid_cell_ids=["C1"])
    mutated = {cid: met_mod.RealMeteorologyObservation(**{**obs.__dict__, "spatial_mode": "SPATIALLY_RESOLVED_REAL"}) for cid, obs in real_meteorology.items()}

    from components.geospatial_tracking.services.factors.environmental_components import build_environmental_component_vector
    from components.geospatial_tracking.services.factors.host_transform import build_host_factor_candidates
    from components.geospatial_tracking.services.factors.source_strength import build_source_strength_status
    from components.geospatial_tracking.services.factors.water_context import build_water_context_status

    cell = snap["grid_cells"][0]
    cell_factor_candidates = {"C1": build_host_factor_candidates(cell=cell, feature_snapshot_id=snap["snapshot_id"], reference_profile=profile, transform_config=tc)}
    env_vectors = {"C1": build_environmental_component_vector(cell=cell, snapshot=snap, feature_snapshot_id=snap["snapshot_id"])}
    water_status = {"C1": build_water_context_status(cell=cell, feature_snapshot_id=snap["snapshot_id"])}
    source_status = {"SRC1": build_source_strength_status(source_id="SRC1")}

    id_original = fsmod.compute_factor_snapshot_id(
        feature_snapshot_id=snap["snapshot_id"], transform_config_hash=tc.config_hash(), reference_profile_hash=profile.reference_profile_hash(),
        cell_factor_candidates=cell_factor_candidates, environmental_component_vectors=env_vectors, source_factor_status=source_status,
        meteorology_by_cell=real_meteorology, water_context_status=water_status, expected_grid_cell_ids=["C1"], active_source_ids=["SRC1"],
    )
    id_mutated = fsmod.compute_factor_snapshot_id(
        feature_snapshot_id=snap["snapshot_id"], transform_config_hash=tc.config_hash(), reference_profile_hash=profile.reference_profile_hash(),
        cell_factor_candidates=cell_factor_candidates, environmental_component_vectors=env_vectors, source_factor_status=source_status,
        meteorology_by_cell=mutated, water_context_status=water_status, expected_grid_cell_ids=["C1"], active_source_ids=["SRC1"],
    )
    assert id_original != id_mutated


def test_factor_id_06_generated_at_does_not_change_id():
    snap = _snapshot()
    fs1 = _build(copy.deepcopy(snap))
    time.sleep(0.01)
    fs2 = _build(copy.deepcopy(snap))
    assert fs1.generated_at != fs2.generated_at
    assert fs1.factor_snapshot_id == fs2.factor_snapshot_id


def test_factor_id_07_dictionary_ordering_does_not_change_id():
    from components.geospatial_tracking.services.factors import factor_snapshot as fsmod

    origin = _origin()
    snap = _snapshot()
    tc = FactorTransformConfig()
    profile = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc)
    cell = snap["grid_cells"][0]

    from components.geospatial_tracking.services.factors.environmental_components import build_environmental_component_vector
    from components.geospatial_tracking.services.factors.host_transform import build_host_factor_candidates
    from components.geospatial_tracking.services.factors.meteorology_adapter import build_meteorology_by_cell
    from components.geospatial_tracking.services.factors.source_strength import build_source_strength_status
    from components.geospatial_tracking.services.factors.water_context import build_water_context_status

    cell_factor_candidates = {"C1": build_host_factor_candidates(cell=cell, feature_snapshot_id=snap["snapshot_id"], reference_profile=profile, transform_config=tc)}
    env_vectors = {"C1": build_environmental_component_vector(cell=cell, snapshot=snap, feature_snapshot_id=snap["snapshot_id"])}
    water_status = {"C1": build_water_context_status(cell=cell, feature_snapshot_id=snap["snapshot_id"])}
    source_status_forward = {"SRC1": build_source_strength_status(source_id="SRC1"), "SRC2": build_source_strength_status(source_id="SRC2")}
    source_status_reversed = dict(reversed(list(source_status_forward.items())))
    meteorology_by_cell = build_meteorology_by_cell(snap, expected_grid_cell_ids=["C1"])

    id_forward = fsmod.compute_factor_snapshot_id(
        feature_snapshot_id=snap["snapshot_id"], transform_config_hash=tc.config_hash(), reference_profile_hash=profile.reference_profile_hash(),
        cell_factor_candidates=cell_factor_candidates, environmental_component_vectors=env_vectors, source_factor_status=source_status_forward,
        meteorology_by_cell=meteorology_by_cell, water_context_status=water_status, expected_grid_cell_ids=["C1"], active_source_ids=["SRC1", "SRC2"],
    )
    id_reversed = fsmod.compute_factor_snapshot_id(
        feature_snapshot_id=snap["snapshot_id"], transform_config_hash=tc.config_hash(), reference_profile_hash=profile.reference_profile_hash(),
        cell_factor_candidates=cell_factor_candidates, environmental_component_vectors=env_vectors, source_factor_status=source_status_reversed,
        meteorology_by_cell=meteorology_by_cell, water_context_status=water_status, expected_grid_cell_ids=["C1"], active_source_ids=["SRC2", "SRC1"],
    )
    assert id_forward == id_reversed
