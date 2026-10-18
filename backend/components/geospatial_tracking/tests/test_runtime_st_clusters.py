"""Runtime ST-DBSCAN (EXPLORATORY) over FICTIONAL in-memory points only."""

from __future__ import annotations

from datetime import date

from components.geospatial_tracking.services.spatial_timeline.clusters import (
    EXPLORATORY_CONFIG,
    operational_case_points,
    run_runtime_st_clustering,
)
from components.geospatial_tracking.services.stdbscan.config import UNFROZEN_DEVELOPMENT_CANDIDATE

AS_OF = date(2026, 8, 31)


def _run(points):
    return run_runtime_st_clustering(operational_points=points, historical_sources=[], as_of=AS_OF, disease_display="Lumpy skin disease")


def test_parameters_are_the_documented_unfrozen_development_candidate():
    cfg = EXPLORATORY_CONFIG
    assert (cfg.eps_space_km, cfg.eps_time_days, cfg.min_core_supports, cfg.active_window_days) == (12.37, 3, 2, 14)
    assert cfg.parameter_status == UNFROZEN_DEVELOPMENT_CANDIDATE


def test_two_nearby_farms_within_three_days_form_one_exploratory_cluster():
    # Fictional farms ~1.6 km apart, reports 1 day apart -> joint space-time neighbours.
    points = [("A1", 5.948, 80.548, "2026-08-30", "FA"), ("A2", 5.948, 80.548, "2026-08-30", "FA"),
              ("B1", 5.950, 80.562, "2026-08-31", "FB")]
    result = _run(points)
    assert result["cluster_count"] == 1 and result["noise_count"] == 0
    cluster = result["clusters"][0]
    assert cluster["member_count"] == 3 and cluster["distinct_farm_or_support_count"] == 2
    assert (cluster["start_date"], cluster["end_date"]) == ("2026-08-30", "2026-08-31")
    assert result["evidence_status"] == "EXPLORATORY"


def test_repeat_reports_from_one_farm_never_cluster_alone():
    points = [(f"C{i}", 6.915, 79.967, "2026-08-31", "FC") for i in range(7)]
    result = _run(points)
    assert result["cluster_count"] == 0 and result["noise_count"] == 7


def test_far_apart_or_too_late_reports_are_noise_never_manufactured_clusters():
    far = [("M1", 5.948, 80.548, "2026-08-30", "FM"), ("K1", 6.915, 79.967, "2026-08-30", "FK")]  # > 100 km
    late = [("A1", 5.948, 80.548, "2026-08-20", "FA"), ("B1", 5.950, 80.562, "2026-08-31", "FB")]  # 11 days apart
    for points in (far, late):
        result = _run(points)
        assert result["cluster_count"] == 0 and result["noise_count"] == 2
    assert _run([])["status"] == "NO_ELIGIBLE_POINTS"


def test_case_point_eligibility_uses_sri_lanka_dates_disease_and_farm_gps():
    farms = {"f1": {"latitude": 5.948, "longitude": 80.548}, "f2": {"latitude": None, "longitude": None}}
    docs = [
        {"_id": "c1", "farm_id": "f1", "disease_name": "Lumpy Skin Disease", "verified": True, "verified_at": "2026-08-30 20:05:00"},  # 31 Aug SL
        {"_id": "c2", "farm_id": "f1", "disease_name": "Foot and Mouth Disease", "verified": True, "verified_at": "2026-08-30 08:00:00"},
        {"_id": "c3", "farm_id": "f1", "disease_name": "Lumpy Skin Disease", "verified": False, "verified_at": None},
        {"_id": "c4", "farm_id": "f2", "disease_name": "Lumpy Skin Disease", "verified": True, "verified_at": "2026-08-30 08:00:00"},
    ]
    points, excluded = operational_case_points(docs, farms, disease_code="LSD", as_of=AS_OF, window_days=14)
    assert [(p[3]) for p in points] == ["2026-08-31"]
    assert points[0][0].startswith("CASE:")  # privacy-reduced identity
    assert dict(excluded) == {"WRONG_DISEASE": 1, "NOT_VET_VERIFIED": 1, "NO_USABLE_FARM_GPS": 1}


# ---- environment (pure parts; no network) ----
from components.geospatial_tracking.services.geospatial.weather.wind import wind_components_from_speed_direction
from components.geospatial_tracking.services.spatial_timeline.environment import snap_to_era5_grid, wind_direction_from_components


def test_wind_direction_is_the_exact_inverse_of_the_research_component_convention():
    for direction in (0.0, 45.0, 90.0, 180.0, 270.0, 315.0):
        u, v = wind_components_from_speed_direction(5.0, direction)
        assert abs(((wind_direction_from_components(u, v) - direction) + 180) % 360 - 180) < 1e-9
    assert wind_direction_from_components(0.0, 0.0) is None


def test_sources_are_snapped_to_the_era5_quarter_degree_grid():
    assert snap_to_era5_grid(5.9478, 80.5483) == (6.0, 80.5)
    assert snap_to_era5_grid(6.9148, 79.9670) == (7.0, 80.0)


def test_cluster_radius_and_drift_are_descriptive_geometry():
    """Radius = farthest member from the centroid; drift = early-half to
    late-half member centroid (FICTIONAL points ~11 km apart, east of each other)."""
    from components.geospatial_tracking.services.spatial_timeline.clusters import cluster_geometry

    early = [(6.00, 80.50, "2026-10-01"), (6.00, 80.52, "2026-10-02")]
    late = [(6.00, 80.60, "2026-10-04"), (6.00, 80.62, "2026-10-05")]
    result = cluster_geometry(early + late, 6.00, 80.56)
    assert 6.5 < result["radius_km"] < 7.0  # 0.06 deg of longitude at 6 N
    drift = result["drift"]
    assert drift["supported"] is True and drift["early_member_count"] == 2 and drift["late_member_count"] == 2
    assert 10.5 < drift["km"] < 11.5
    assert 89.0 < drift["bearing_deg"] < 91.0  # due east


def test_cluster_drift_unsupported_on_a_single_day():
    from components.geospatial_tracking.services.spatial_timeline.clusters import cluster_geometry

    same_day = [(6.00, 80.50, "2026-10-03"), (6.05, 80.55, "2026-10-03")]
    result = cluster_geometry(same_day, 6.025, 80.525)
    assert result["drift"]["supported"] is False and result["drift"]["km"] is None and result["drift"]["bearing_deg"] is None
    assert result["radius_km"] > 0
