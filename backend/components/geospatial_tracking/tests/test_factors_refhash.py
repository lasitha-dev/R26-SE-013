"""Checkpoint 6D.5 Part 22, 25: reference-profile hash content tests —
REFHASH-01..08, and FactorSnapshot ID propagation."""

from __future__ import annotations

import time

from components.geospatial_tracking.services.factors.factor_snapshot import build_factor_snapshot
from components.geospatial_tracking.services.factors.reference_profile import build_factor_reference_profile
from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin

_UNITS = "animals_per_km2"


def _real_fr(value, *, feature_name, sample_identity=None, dataset_version="2015"):
    return {"feature_name": feature_name, "value": value, "units": _UNITS, "status": "REAL", "dataset_name": "GLW4", "dataset_version": dataset_version, "sample_identity": sample_identity}


def _cell(cell_id, lat, lon, *, cattle=10.0, buffalo=2.0, cattle_id=None, buffalo_id=None):
    return {
        "grid_cell_id": cell_id, "centroid_lat": lat, "centroid_lon": lon,
        "host_density": {
            "cattle": _real_fr(cattle, feature_name="host_density_cattle_grid_cell", sample_identity=cattle_id),
            "buffalo": _real_fr(buffalo, feature_name="host_density_buffalo_grid_cell", sample_identity=buffalo_id),
        },
        "landcover": {}, "hydrology": None,
    }


def _snapshot(snapshot_id, *, cells):
    return {
        "snapshot_id": snapshot_id, "active_source_ids": ["SRC1"], "grid_cells": cells,
        "weather": {"window": {"weather_model": "era5", "request_parameters": {"latitude": 15.0, "longitude": 101.0}, "window_start": "2021-06-01T00:00:00+00:00", "window_end": "2021-06-02T00:00:00+00:00"}, "results": {}},
        "source_dataset_versions": {}, "landcover_comparability_group": "WORLDCOVER_V200",
    }


def _origin() -> ForecastOrigin:
    return ForecastOrigin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["SRC1"], trigger_source_count=1)


def test_refhash_01_same_effective_inputs_same_hash():
    origin = _origin()
    snap = _snapshot("A", cells=[_cell("C1", 15.0, 101.0, cattle=10.0, cattle_id="P1", buffalo_id="P2")])
    tc = FactorTransformConfig()
    p1 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc)
    p2 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc)
    assert p1.reference_profile_hash() == p2.reference_profile_hash()


def test_refhash_02_generated_at_change_same_hash():
    origin = _origin()
    snap = _snapshot("A", cells=[_cell("C1", 15.0, 101.0)])
    tc = FactorTransformConfig()
    p1 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc, generated_at="2020-01-01T00:00:00Z")
    time.sleep(0.01)
    p2 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap}, transform_config=tc, generated_at="2030-01-01T00:00:00Z")
    assert p1.reference_profile_hash() == p2.reference_profile_hash()


def test_refhash_03_reference_observation_value_change_different_hash():
    origin = _origin()
    tc = FactorTransformConfig()
    snap1 = _snapshot("A", cells=[_cell("C1", 15.0, 101.0, cattle=10.0)])
    snap2 = _snapshot("A", cells=[_cell("C1", 15.0, 101.0, cattle=99.0)])
    p1 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap1}, transform_config=tc)
    p2 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap2}, transform_config=tc)
    assert p1.reference_profile_hash() != p2.reference_profile_hash()


def test_refhash_04_reference_observation_id_provenance_change_different_hash():
    origin = _origin()
    tc = FactorTransformConfig()
    # same numeric values, different underlying pixel identity
    snap1 = _snapshot("A", cells=[_cell("C1", 15.0, 101.0, cattle_id="PIXEL_A", buffalo_id="PIXEL_B")])
    snap2 = _snapshot("A", cells=[_cell("C1", 15.0, 101.0, cattle_id="PIXEL_X", buffalo_id="PIXEL_Y")])
    p1 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap1}, transform_config=tc)
    p2 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap2}, transform_config=tc)
    assert p1.reference_profile_hash() != p2.reference_profile_hash()


def test_refhash_05_ecdf_interior_support_change_same_summary_quantiles_different_hash():
    # two small distributions engineered so p05/p50/p95 (the summary
    # quantiles) come out identical while the interior differs, proving
    # the fix: reference_profile_hash must NOT alias these.
    origin = _origin()
    tc = FactorTransformConfig()
    snap_a = _snapshot("A", cells=[
        _cell("C1", 15.00, 101.0, cattle=8.0, buffalo=0.0, cattle_id="P1"),
        _cell("C2", 15.01, 101.0, cattle=8.0, buffalo=0.0, cattle_id="P2"),
        _cell("C3", 15.02, 101.0, cattle=8.0, buffalo=0.0, cattle_id="P3"),
    ])
    snap_b = _snapshot("A", cells=[
        _cell("C1", 15.00, 101.0, cattle=8.0, buffalo=0.0, cattle_id="P1"),
        _cell("C2", 15.01, 101.0, cattle=6.0, buffalo=0.0, cattle_id="P2"),  # interior value changed
        _cell("C3", 15.02, 101.0, cattle=10.0, buffalo=0.0, cattle_id="P3"),  # interior value changed (mean preserved-ish)
    ])
    p_a = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap_a}, transform_config=tc)
    p_b = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap_b}, transform_config=tc)
    assert p_a.host_density_total_quantiles["p50"] == p_b.host_density_total_quantiles["p50"] == 8.0
    assert p_a.reference_profile_hash() != p_b.reference_profile_hash()
    assert p_a.reference_observation_digest != p_b.reference_observation_digest


def test_refhash_06_dataset_compatibility_stratum_change_different_hash():
    origin = _origin()
    tc = FactorTransformConfig()
    snap_2015 = _snapshot("A", cells=[_cell("C1", 15.0, 101.0)])
    cell_2020 = _cell("C1", 15.0, 101.0)
    cell_2020["host_density"]["cattle"]["dataset_version"] = "2020"
    cell_2020["host_density"]["buffalo"]["dataset_version"] = "2020"
    snap_2020 = _snapshot("A", cells=[cell_2020])
    p1 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap_2015}, transform_config=tc)
    p2 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap_2020}, transform_config=tc)
    assert p1.dataset_compatibility_stratum != p2.dataset_compatibility_stratum
    assert p1.reference_profile_hash() != p2.reference_profile_hash()


def test_refhash_07_units_change_different_hash():
    origin = _origin()
    tc = FactorTransformConfig()
    snap_a = _snapshot("A", cells=[_cell("C1", 15.0, 101.0)])
    cell_diff_units = _cell("C1", 15.0, 101.0)
    cell_diff_units["host_density"]["cattle"]["units"] = "animals_per_hectare"
    cell_diff_units["host_density"]["buffalo"]["units"] = "animals_per_hectare"
    snap_b = _snapshot("A", cells=[cell_diff_units])
    p_a = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap_a}, transform_config=tc)
    p_b = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap_b}, transform_config=tc)
    assert p_a.reference_profile_hash() != p_b.reference_profile_hash()


def test_refhash_08_observation_ordering_does_not_change_hash():
    origin = _origin()
    tc = FactorTransformConfig()
    snap_forward = _snapshot("A", cells=[
        _cell("C1", 15.00, 101.0, cattle=8.0, buffalo=0.0, cattle_id="P1"),
        _cell("C2", 15.01, 101.0, cattle=6.0, buffalo=0.0, cattle_id="P2"),
    ])
    snap_reversed = _snapshot("A", cells=[
        _cell("C2", 15.01, 101.0, cattle=6.0, buffalo=0.0, cattle_id="P2"),
        _cell("C1", 15.00, 101.0, cattle=8.0, buffalo=0.0, cattle_id="P1"),
    ])
    p1 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap_forward}, transform_config=tc)
    p2 = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: snap_reversed}, transform_config=tc)
    assert p1.reference_profile_hash() == p2.reference_profile_hash()


def test_factor_snapshot_id_propagates_corrected_reference_identity():
    # Part 25: same FeatureSnapshot + same transform config, different
    # effective reference ECDF distribution -> different FactorSnapshot ID.
    origin = _origin()
    tc = FactorTransformConfig()
    feature_snapshot = _snapshot("A", cells=[_cell("C1", 15.0, 101.0, cattle=10.0, cattle_id="P1", buffalo_id="P2")])

    ref_snap_a = _snapshot("A", cells=[
        _cell("C1", 15.00, 101.0, cattle=8.0, buffalo=0.0, cattle_id="P1"),
        _cell("C2", 15.01, 101.0, cattle=8.0, buffalo=0.0, cattle_id="P2"),
    ])
    ref_snap_b = _snapshot("A", cells=[
        _cell("C1", 15.00, 101.0, cattle=8.0, buffalo=0.0, cattle_id="P1"),
        _cell("C2", 15.01, 101.0, cattle=50.0, buffalo=0.0, cattle_id="P2"),
    ])
    profile_a = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: ref_snap_a}, transform_config=tc)
    profile_b = build_factor_reference_profile(fit_development_origins=[origin], feature_snapshots_by_origin_id={origin.forecast_origin_id: ref_snap_b}, transform_config=tc)
    assert profile_a.reference_profile_hash() != profile_b.reference_profile_hash()

    fs_a = build_factor_snapshot(feature_snapshot=feature_snapshot, forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, expected_grid_cell_ids=["C1"], active_source_ids=["SRC1"], reference_profile=profile_a, transform_config=tc)
    fs_b = build_factor_snapshot(feature_snapshot=feature_snapshot, forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, expected_grid_cell_ids=["C1"], active_source_ids=["SRC1"], reference_profile=profile_b, transform_config=tc)
    assert fs_a.factor_snapshot_id != fs_b.factor_snapshot_id
