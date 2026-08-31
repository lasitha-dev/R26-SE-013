"""Checkpoint 6D.6 Part 17: reference observation value-conflict
firewall tests — REFCONFLICT-01..05."""

from __future__ import annotations

from components.geospatial_tracking.services.factors.reference_observations import build_static_reference_observations


def _fr(value: float, *, digest: str = "GLW4SUPPORT:same", dataset_name: str = "GLW4", dataset_version: str = "2015", feature_name: str = "cattle_density") -> dict:
    return {"status": "REAL", "feature_name": feature_name, "value": value, "dataset_name": dataset_name, "dataset_version": dataset_version, "sample_support_digest": digest}


def _cell(fr: dict, *, lat: float = 7.0, lon: float = 80.0) -> dict:
    return {"centroid_lat": lat, "centroid_lon": lon, "host_density": {"cattle": fr}}


def _snap(*cells) -> dict:
    return {"grid_cells": list(cells)}


def test_refconflict_01_same_id_same_value_dedups_to_one_observation():
    snapshots = [_snap(_cell(_fr(24.5))), _snap(_cell(_fr(24.5)))]
    observations, report, conflicts = build_static_reference_observations(snapshots, species="cattle")
    assert len(observations) == 1
    assert report["raw_appearances"] == 2
    assert report["unique_observations"] == 1
    assert conflicts == []
    assert report["n_value_conflicts"] == 0


def test_refconflict_02_same_id_different_value_reports_explicit_conflict():
    snapshots = [_snap(_cell(_fr(24.5))), _snap(_cell(_fr(30.0)))]
    observations, report, conflicts = build_static_reference_observations(snapshots, species="cattle")
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.first_value == 24.5
    assert conflict.conflicting_value == 30.0
    assert report["n_value_conflicts"] == 1


def test_refconflict_03_conflict_does_not_silently_keep_first_value():
    snapshots = [_snap(_cell(_fr(24.5))), _snap(_cell(_fr(30.0)))]
    observations, report, conflicts = build_static_reference_observations(snapshots, species="cattle")
    # the conflicting observation must NOT be silently retained under the
    # first value -- exactly one observation object exists (the first
    # one seen), and the discrepancy is reported separately, not hidden
    # inside a "successful" pooled observation set that a caller might
    # treat as trustworthy without checking `conflicts`.
    assert len(observations) == 1
    assert observations[0].value == 24.5  # the *first* value is what's held in the dict, but...
    assert len(conflicts) == 1  # ...the conflict is ALWAYS surfaced alongside it, never dropped.


def test_refconflict_04_conflict_does_not_silently_average():
    snapshots = [_snap(_cell(_fr(20.0))), _snap(_cell(_fr(40.0)))]
    observations, report, conflicts = build_static_reference_observations(snapshots, species="cattle")
    assert len(observations) == 1
    assert observations[0].value != 30.0  # never the midpoint/average of 20 and 40
    assert observations[0].value in (20.0, 40.0)
    assert len(conflicts) == 1


def test_refconflict_05_reference_profile_hash_and_status_reflect_conflict():
    from components.geospatial_tracking.services.factors.reference_profile import build_factor_reference_profile
    from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
    from components.geospatial_tracking.services.factors.contracts import REFERENCE_OBSERVATION_VALUE_CONFLICT
    from components.geospatial_tracking.services.forecast_origin import ForecastOrigin

    _DATASET = "FAO Gridded Livestock of the World (GLW4), Da (dasymetric) product"

    def _real_fr(value, *, feature_name):
        return {"feature_name": feature_name, "value": value, "units": "animals_per_km2", "status": "REAL", "dataset_name": _DATASET, "dataset_version": "2015"}

    def _cell(cattle_value):
        # same centroid -> same QUERY_CENTROID_FALLBACK identity for both
        # cattle and buffalo across the two snapshots below, so the
        # resulting host_density_total identity collides while the raw
        # value legitimately differs.
        return {
            "grid_cell_id": "C1", "centroid_lat": 15.0, "centroid_lon": 101.0,
            "host_density": {"cattle": _real_fr(cattle_value, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell")},
            "landcover": {}, "hydrology": None,
        }

    def _snapshot(snapshot_id, cattle_value):
        return {
            "snapshot_id": snapshot_id, "grid_cells": [_cell(cattle_value)],
            "weather": {"window": {"weather_model": "era5", "request_parameters": {"latitude": 15.0, "longitude": 101.0}, "window_start": "2021-06-01T00:00:00+00:00", "window_end": "2021-06-02T00:00:00+00:00"}, "results": {}},
            "source_dataset_versions": {}, "landcover_comparability_group": "WORLDCOVER_V200",
        }

    origin_a = ForecastOrigin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)
    origin_b = ForecastOrigin(forecast_origin_id="ORIGIN:Thailand:2021-06-02", country="Thailand", t0="2021-06-02", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X2"], trigger_source_count=1)

    profile = build_factor_reference_profile(
        fit_development_origins=[origin_a, origin_b],
        feature_snapshots_by_origin_id={origin_a.forecast_origin_id: _snapshot("A", 10.0), origin_b.forecast_origin_id: _snapshot("B", 99.0)},
        transform_config=FactorTransformConfig(),
    )
    assert profile.status == REFERENCE_OBSERVATION_VALUE_CONFLICT
    assert profile.n_reference_observation_conflicts == 1
    # a conflicted profile must never be usable as a silently "complete"
    # pool -- its hash must still be derivable (for provenance/debugging)
    # but its status must never read COMPLETE_DIAGNOSTIC and its pooled
    # observation set must be empty (never a partially-cleaned subset).
    assert profile.reference_profile_hash() is not None
    assert profile.host_density_total_unique_observations == 0
