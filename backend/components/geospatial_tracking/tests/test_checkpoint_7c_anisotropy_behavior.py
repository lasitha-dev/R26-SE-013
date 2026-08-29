"""Checkpoint 7C Parts 19-20: zero/low-wind neutrality and direction-
convention behavioral tests, at the real 7C scoring integration level
(not just the underlying `hazard.anisotropy` unit level)."""

from __future__ import annotations

import pytest

from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.geospatial.weather.wind import wind_components_from_speed_direction
from components.geospatial_tracking.services.hazard.anisotropy import CALM_NEUTRAL, compute_anisotropy_factor, compute_meteorological_alignment
from components.geospatial_tracking.services.hazard.contracts import WindVector
from components.geospatial_tracking.services.model_development.candidate_registry_7c import C0_FAMILY, CW_FAMILY, build_candidate_registry_7c
from components.geospatial_tracking.services.model_development.wind_scoring_7c import score_origin_candidates_7c

_SOURCE = EligibleSourcePoint(source_id="S1", latitude=13.50, longitude=100.50)
_EAST_CELL = {"grid_cell_id": "CELL:E", "scientific_cell_id": "SCI:E", "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "centroid_lat": 13.50, "centroid_lon": 100.70}
_WEST_CELL = {"grid_cell_id": "CELL:W", "scientific_cell_id": "SCI:W", "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "centroid_lat": 13.50, "centroid_lon": 100.30}
_NORTH_CELL = {"grid_cell_id": "CELL:N", "scientific_cell_id": "SCI:N", "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "centroid_lat": 13.70, "centroid_lon": 100.50}
_SOUTH_CELL = {"grid_cell_id": "CELL:S", "scientific_cell_id": "SCI:S", "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "centroid_lat": 13.30, "centroid_lon": 100.50}


def _cw(mode: str, kappa: float):
    return next(c for c in build_candidate_registry_7c() if c.family == CW_FAMILY and c.anisotropy_mode == mode and c.anisotropy_kappa == kappa)


def test_7cwind_01_eastward_wind_favors_east_cell_over_west_cell():
    wind = WindVector(u10=5.0, v10=0.0)  # blowing toward the east
    cw = _cw("MODULATING", 2.0)
    scores = score_origin_candidates_7c(grid_cells=[_EAST_CELL, _WEST_CELL], sources=[_SOURCE], candidates=(cw,), wind=wind)[cw.candidate_id]
    by_id = {c.grid_cell_id: c.score for c in scores}
    assert by_id["CELL:E"] > by_id["CELL:W"]


def test_7cwind_02_northward_wind_favors_north_cell_over_south_cell():
    wind = WindVector(u10=0.0, v10=5.0)  # blowing toward the north
    cw = _cw("MODULATING", 2.0)
    scores = score_origin_candidates_7c(grid_cells=[_NORTH_CELL, _SOUTH_CELL], sources=[_SOURCE], candidates=(cw,), wind=wind)[cw.candidate_id]
    by_id = {c.grid_cell_id: c.score for c in scores}
    assert by_id["CELL:N"] > by_id["CELL:S"]


@pytest.mark.parametrize("mode", ["MODULATING", "ANGULAR_NORMALIZED"])
@pytest.mark.parametrize("kappa", [0.25, 0.50, 1.00, 2.00])
def test_7cwind_03_zero_wind_gives_neutral_isotropic_anisotropy_and_matches_c0(mode, kappa):
    zero_wind = WindVector(u10=0.0, v10=0.0)
    c0 = next(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)
    cw = _cw(mode, kappa)
    scores = score_origin_candidates_7c(
        grid_cells=[_EAST_CELL, _WEST_CELL, _NORTH_CELL, _SOUTH_CELL], sources=[_SOURCE], candidates=(c0, cw), wind=zero_wind,
    )
    c0_by_id = {c.grid_cell_id: c.score for c in scores[c0.candidate_id]}
    cw_by_id = {c.grid_cell_id: c.score for c in scores[cw.candidate_id]}
    for gcid in c0_by_id:
        assert cw_by_id[gcid] == pytest.approx(c0_by_id[gcid], rel=1e-12), "zero wind must produce an exactly neutral (isotropic) modifier, never an arbitrary directional preference"


def test_7cwind_04_calm_wind_status_is_explicit_calm_neutral_never_a_fabricated_direction():
    zero_wind = WindVector(u10=0.0, v10=0.0)
    alignment = compute_meteorological_alignment(t_hat_east=1.0, t_hat_north=0.0, wind=zero_wind)
    assert alignment.status == CALM_NEUTRAL
    assert alignment.alignment is None
    result = compute_anisotropy_factor(alignment, kappa=2.0, mode="MODULATING")
    assert result.anisotropy_factor == 1.0


def test_7cwind_05_zero_degree_bearing_remains_valid_north():
    # meteorological direction_from_deg=0 means wind blowing FROM the north,
    # i.e. TOWARD the south: v10 (northward component) must be negative.
    u10, v10 = wind_components_from_speed_direction(speed_m_s=5.0, direction_from_deg=0.0)
    assert u10 == pytest.approx(0.0, abs=1e-9)
    assert v10 < 0


def test_7cwind_06_source_specific_geometry_is_used_different_sources_get_different_alignment():
    wind = WindVector(u10=5.0, v10=0.0)
    source_a = EligibleSourcePoint(source_id="A", latitude=13.50, longitude=100.30)  # west of the cell -> pushed east, high alignment
    source_b = EligibleSourcePoint(source_id="B", latitude=13.50, longitude=100.70)  # east of the cell -> pushed west, low/negative alignment
    from components.geospatial_tracking.services.geospatial.distance import source_to_cell_unit_vector

    cell = {"centroid_lat": 13.50, "centroid_lon": 100.50}
    vec_a = source_to_cell_unit_vector(source_a.latitude, source_a.longitude, cell["centroid_lat"], cell["centroid_lon"])
    vec_b = source_to_cell_unit_vector(source_b.latitude, source_b.longitude, cell["centroid_lat"], cell["centroid_lon"])
    align_a = compute_meteorological_alignment(t_hat_east=vec_a.t_hat_east, t_hat_north=vec_a.t_hat_north, wind=wind)
    align_b = compute_meteorological_alignment(t_hat_east=vec_b.t_hat_east, t_hat_north=vec_b.t_hat_north, wind=wind)
    assert align_a.alignment != pytest.approx(align_b.alignment)


def test_7cwind_07_multiple_sources_contribute_independently():
    wind = WindVector(u10=5.0, v10=0.0)
    source_near = EligibleSourcePoint(source_id="NEAR", latitude=13.50, longitude=100.45)
    source_far = EligibleSourcePoint(source_id="FAR", latitude=13.50, longitude=99.90)
    cw = _cw("MODULATING", 1.0)
    solo_near = score_origin_candidates_7c(grid_cells=[_EAST_CELL], sources=[source_near], candidates=(cw,), wind=wind)[cw.candidate_id][0].score
    solo_far = score_origin_candidates_7c(grid_cells=[_EAST_CELL], sources=[source_far], candidates=(cw,), wind=wind)[cw.candidate_id][0].score
    combined = score_origin_candidates_7c(grid_cells=[_EAST_CELL], sources=[source_near, source_far], candidates=(cw,), wind=wind)[cw.candidate_id][0].score
    assert combined == pytest.approx(solo_near + solo_far, rel=1e-9)


def test_7cwind_08_wind_direction_never_exposed_as_final_spread_direction():
    registry_dump = str([c.as_dict() for c in build_candidate_registry_7c()]).lower()
    for forbidden in ("spread_direction", "spread direction", "bearing_confidence", "spread-front rate", "nominal_reach", "spread_speed"):
        assert forbidden not in registry_dump
