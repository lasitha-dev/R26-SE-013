"""Checkpoint 7A Part 34: reference-protocol hardening tests —
REF7A-01..05."""

from __future__ import annotations

from components.geospatial_tracking.services.factors.host_transform import compute_host_density_total
from components.geospatial_tracking.services.factors.reference_observations import (
    QUERY_CENTROID_FALLBACK,
    RASTER_EFFECTIVE_SAMPLE_IDENTITY,
    RASTER_LEGACY_PIXEL_SET_IDENTITY,
    REFERENCE_VALUE_CONFLICT_ABS_TOL,
    REFERENCE_VALUE_CONFLICT_REL_TOL,
    resolve_static_observation_identity,
    values_conflict,
)
from components.geospatial_tracking.services.factors.reference_profile import build_factor_reference_profile
from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin

_DATASET = "FAO Gridded Livestock of the World (GLW4), Da (dasymetric) product"


def _origin(suffix="A") -> ForecastOrigin:
    return ForecastOrigin(forecast_origin_id=f"ORIGIN:Thailand:2021-06-0{suffix}", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)


def _real_fr(value, *, feature_name, digest="GLW4SUPPORT:x"):
    return {"feature_name": feature_name, "value": value, "units": "animals_per_km2", "status": "REAL", "dataset_name": _DATASET, "dataset_version": "2015", "sample_support_digest": digest}


def _cell():
    return {
        "centroid_lat": 15.0, "centroid_lon": 101.0,
        "host_density": {"cattle": _real_fr(10.0, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell")},
        "landcover": {}, "hydrology": None,
    }


def _snapshot():
    return {
        "snapshot_id": "A", "grid_cells": [_cell()],
        "weather": {"window": {"weather_model": "era5", "request_parameters": {"latitude": 15.0, "longitude": 101.0}, "window_start": "2021-06-01T00:00:00+00:00", "window_end": "2021-06-02T00:00:00+00:00"}, "results": {}},
        "source_dataset_versions": {}, "landcover_comparability_group": "WORLDCOVER_V200",
    }


def _profile(**kwargs):
    origin = _origin()
    return build_factor_reference_profile(
        fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: _snapshot()},
        transform_config=FactorTransformConfig(), **kwargs,
    )


def test_ref7a_01_tolerance_participates_in_protocol_identity():
    profile = _profile()
    assert profile.reference_value_conflict_tolerance == {"rel_tol": REFERENCE_VALUE_CONFLICT_REL_TOL, "abs_tol": REFERENCE_VALUE_CONFLICT_ABS_TOL}
    assert profile.reference_value_conflict_tolerance in profile.as_dict().values() or "reference_value_conflict_tolerance" in profile.as_dict()


def test_ref7a_02_changing_conflict_tolerance_changes_protocol_identity():
    profile_default = _profile()
    hash_default = profile_default.reference_profile_hash()

    # simulate a different tolerance having been used to build the
    # profile (as a future config change would) -- the hash must move,
    # never silently stay identical merely because THIS corpus happens
    # to pool to the same values under either tolerance.
    from dataclasses import replace
    profile_retuned = replace(profile_default, reference_value_conflict_tolerance={"rel_tol": 1e-6, "abs_tol": 1e-6})
    assert profile_retuned.reference_profile_hash() != hash_default


def test_ref7a_03_legacy_pixel_set_identity_is_distinguishable_from_effective():
    fr_effective = {"feature_name": "host_density_cattle_grid_cell", "value": 24.0, "status": "REAL", "dataset_name": _DATASET, "dataset_version": "2015", "sample_support_digest": "GLW4SUPPORT:x"}
    fr_legacy = {"feature_name": "host_density_cattle_grid_cell", "value": 24.0, "status": "REAL", "dataset_name": _DATASET, "dataset_version": "2015", "sample_identity": "GLW4PIXELS:x"}
    cell = {"centroid_lat": 15.0, "centroid_lon": 101.0}
    _id_eff, source_eff = resolve_static_observation_identity(fr_effective, cell=cell)
    _id_legacy, source_legacy = resolve_static_observation_identity(fr_legacy, cell=cell)
    assert source_eff == RASTER_EFFECTIVE_SAMPLE_IDENTITY
    assert source_legacy == RASTER_LEGACY_PIXEL_SET_IDENTITY
    assert source_eff != source_legacy


def test_ref7a_04_strict_primary_reference_rejects_legacy_and_fallback_identity():
    origin = _origin()
    cell_effective = _cell()
    cell_legacy = {
        "centroid_lat": 16.0, "centroid_lon": 102.0,
        "host_density": {
            "cattle": {"feature_name": "host_density_cattle_grid_cell", "value": 5.0, "units": "animals_per_km2", "status": "REAL", "dataset_name": _DATASET, "dataset_version": "2015", "sample_identity": "GLW4PIXELS:legacy"},
            "buffalo": {"feature_name": "host_density_buffalo_grid_cell", "value": 1.0, "units": "animals_per_km2", "status": "REAL", "dataset_name": _DATASET, "dataset_version": "2015", "sample_identity": "GLW4PIXELS:legacy_b"},
        },
        "landcover": {}, "hydrology": None,
    }
    snap = {
        "snapshot_id": "A", "grid_cells": [cell_effective, cell_legacy],
        "weather": {"window": {}, "results": {}}, "source_dataset_versions": {}, "landcover_comparability_group": "WORLDCOVER_V200",
    }

    lenient = build_factor_reference_profile(
        fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap},
        transform_config=FactorTransformConfig(), require_effective_sample_identity=False,
    )
    strict = build_factor_reference_profile(
        fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap},
        transform_config=FactorTransformConfig(), require_effective_sample_identity=True,
    )
    # lenient pools BOTH cells; strict withholds the legacy-identity cell
    assert lenient.host_density_total_unique_observations == 2
    assert strict.host_density_total_unique_observations == 1
    assert strict.n_excluded_by_strict_identity_requirement >= 1
    assert strict.require_effective_sample_identity is True


def test_ref7a_05_new_scientific_grid_reference_gets_new_hash_when_sampling_geometry_changes():
    # a change in effective sampling geometry (here: a different
    # sample_support_digest for the SAME cell/value, standing in for a
    # materially different grid/sampling protocol) must change
    # reference_profile_hash() -- never silently reused.
    origin = _origin()

    def _snap_with_digest(digest):
        cell = _cell()
        cell["host_density"]["cattle"]["sample_support_digest"] = digest
        cell["host_density"]["buffalo"]["sample_support_digest"] = digest
        return {"snapshot_id": "A", "grid_cells": [cell], "weather": {"window": {}, "results": {}}, "source_dataset_versions": {}, "landcover_comparability_group": "WORLDCOVER_V200"}

    profile_old_grid = build_factor_reference_profile(
        fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: _snap_with_digest("GLW4SUPPORT:smoke_grid_v1")},
        transform_config=FactorTransformConfig(),
    )
    profile_new_grid = build_factor_reference_profile(
        fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: _snap_with_digest("GLW4SUPPORT:scientific_grid_v1")},
        transform_config=FactorTransformConfig(),
    )
    assert profile_old_grid.reference_profile_hash() != profile_new_grid.reference_profile_hash()


def test_values_conflict_accepts_explicit_tolerance_override():
    assert values_conflict(1.0, 1.0000001, rel_tol=1e-3, abs_tol=1e-3) is False
    assert values_conflict(1.0, 2.0, rel_tol=1e-9, abs_tol=1e-9) is True


def test_host_total_identity_source_labels_propagate_legacy():
    cell = {
        "centroid_lat": 15.0, "centroid_lon": 101.0,
        "host_density": {
            "cattle": {"feature_name": "host_density_cattle_grid_cell", "value": 5.0, "units": "animals_per_km2", "status": "REAL", "dataset_name": _DATASET, "dataset_version": "2015", "sample_identity": "GLW4PIXELS:legacy"},
            "buffalo": {"status": "MISSING"},
        },
    }
    raw = compute_host_density_total(cell)
    assert raw.cattle_identity_source == RASTER_LEGACY_PIXEL_SET_IDENTITY
