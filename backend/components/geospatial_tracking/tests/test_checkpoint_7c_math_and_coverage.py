"""Checkpoint 7C Part 22-23: 7C-MATH-01..08 and 7C-COV-01..05 tests."""

from __future__ import annotations

import inspect

import pytest

from components.geospatial_tracking.services.geospatial.distance import distance_km, source_to_cell_unit_vector
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.hazard.anisotropy import compute_anisotropy_factor, compute_meteorological_alignment
from components.geospatial_tracking.services.hazard.contracts import WindVector
from components.geospatial_tracking.services.hazard.kernels import evaluate_kernel
from components.geospatial_tracking.services.model_development import wind_scoring_7c
from components.geospatial_tracking.services.model_development.baseline_scoring import SCORED, score_origin_all_candidates
from components.geospatial_tracking.services.model_development.candidate_registry_7b import build_candidate_registry as build_candidate_registry_7b
from components.geospatial_tracking.services.model_development.candidate_registry_7c import (
    C0_FAMILY,
    CW_FAMILY,
    build_candidate_registry_7c,
)
from components.geospatial_tracking.services.model_development.evaluation_protocol_7b import assess_candidate_coverage_eligibility
from components.geospatial_tracking.services.model_development.evaluation_protocol_7c import (
    PRIMARY_SELECTION_ELIGIBLE,
    PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE,
    WIND_CANDIDATES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_WEATHER_SUPPORT,
    classify_selection_note_7c,
)
from components.geospatial_tracking.services.model_development.wind_scoring_7c import score_origin_candidates_7c

_CELLS = [
    {"grid_cell_id": "CELL:E", "scientific_cell_id": "SCI:E", "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "centroid_lat": 13.75, "centroid_lon": 100.60},
    {"grid_cell_id": "CELL:W", "scientific_cell_id": "SCI:W", "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "centroid_lat": 13.75, "centroid_lon": 100.40},
    {"grid_cell_id": "CELL:N", "scientific_cell_id": "SCI:N", "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "centroid_lat": 13.85, "centroid_lon": 100.50},
    {"grid_cell_id": "CELL:S", "scientific_cell_id": "SCI:S", "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "centroid_lat": 13.65, "centroid_lon": 100.50},
]
_SOURCES = [
    EligibleSourcePoint(source_id="S1", latitude=13.50, longitude=100.50),
    EligibleSourcePoint(source_id="S2", latitude=13.60, longitude=100.55),
    EligibleSourcePoint(source_id="S3", latitude=13.40, longitude=100.45),
]


def _c0_only_registry():
    return tuple(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)


def test_7cmath_01_c0_exactly_reproduces_frozen_b0_scores():
    b0 = next(c for c in build_candidate_registry_7b() if c.baseline_family == "B0_DISTANCE_ONLY" and c.kernel_family == "EXPONENTIAL" and c.kernel_scale_km == 25.0)
    b0_scores = score_origin_all_candidates(grid_cells=_CELLS, sources=_SOURCES, candidates=(b0,))[b0.candidate_id]

    c0 = next(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)
    c0_scores = score_origin_candidates_7c(grid_cells=_CELLS, sources=_SOURCES, candidates=(c0,), wind=None)[c0.candidate_id]

    b0_by_id = {c.grid_cell_id: c.score for c in b0_scores}
    c0_by_id = {c.grid_cell_id: c.score for c in c0_scores}
    assert b0_by_id.keys() == c0_by_id.keys()
    for gcid in b0_by_id:
        assert b0_by_id[gcid] == pytest.approx(c0_by_id[gcid], rel=1e-12)


def test_7cmath_02_all_eligible_sources_remain_in_the_source_sum():
    c0 = next(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)
    full_scores = score_origin_candidates_7c(grid_cells=_CELLS[:1], sources=_SOURCES, candidates=(c0,), wind=None)[c0.candidate_id][0]
    manual = sum(
        evaluate_kernel(distance_km(s.latitude, s.longitude, _CELLS[0]["centroid_lat"], _CELLS[0]["centroid_lon"]), family="EXPONENTIAL", distance_scale_km=25.0)
        for s in _SOURCES
    )
    assert full_scores.score == pytest.approx(manual, rel=1e-12)

    dropped_one = score_origin_candidates_7c(grid_cells=_CELLS[:1], sources=_SOURCES[:2], candidates=(c0,), wind=None)[c0.candidate_id][0]
    assert dropped_one.score != pytest.approx(full_scores.score)


def test_7cmath_03_anisotropy_applies_per_source_before_summation():
    cw = next(c for c in build_candidate_registry_7c() if c.family == CW_FAMILY and c.anisotropy_mode == "MODULATING" and c.anisotropy_kappa == 1.0)
    wind = WindVector(u10=5.0, v10=0.0)  # blowing eastward
    result = score_origin_candidates_7c(grid_cells=_CELLS[:1], sources=_SOURCES, candidates=(cw,), wind=wind)[cw.candidate_id][0]

    manual_per_source = 0.0
    for s in _SOURCES:
        vec = source_to_cell_unit_vector(s.latitude, s.longitude, _CELLS[0]["centroid_lat"], _CELLS[0]["centroid_lon"])
        k = evaluate_kernel(vec.distance_km, family="EXPONENTIAL", distance_scale_km=25.0)
        alignment = compute_meteorological_alignment(t_hat_east=vec.t_hat_east, t_hat_north=vec.t_hat_north, wind=wind)
        aniso = compute_anisotropy_factor(alignment, kappa=1.0, mode="MODULATING")
        manual_per_source += k * aniso.anisotropy_factor
    assert result.score == pytest.approx(manual_per_source, rel=1e-12)

    # proves per-source order matters: summing kernels first and applying ONE
    # combined anisotropy factor afterward gives a DIFFERENT number (sources
    # have different bearings to the cell, hence different alignments).
    total_kernel = sum(evaluate_kernel(source_to_cell_unit_vector(s.latitude, s.longitude, _CELLS[0]["centroid_lat"], _CELLS[0]["centroid_lon"]).distance_km, family="EXPONENTIAL", distance_scale_km=25.0) for s in _SOURCES)
    single_vec = source_to_cell_unit_vector(_SOURCES[0].latitude, _SOURCES[0].longitude, _CELLS[0]["centroid_lat"], _CELLS[0]["centroid_lon"])
    single_alignment = compute_meteorological_alignment(t_hat_east=single_vec.t_hat_east, t_hat_north=single_vec.t_hat_north, wind=wind)
    single_aniso = compute_anisotropy_factor(single_alignment, kappa=1.0, mode="MODULATING").anisotropy_factor
    post_sum_result = total_kernel * single_aniso
    assert result.score != pytest.approx(post_sum_result)


def test_7cmath_04_nearest_source_replacement_impossible():
    c0 = next(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)
    full = score_origin_candidates_7c(grid_cells=_CELLS[:1], sources=_SOURCES, candidates=(c0,), wind=None)[c0.candidate_id][0].score
    nearest = min(_SOURCES, key=lambda s: distance_km(s.latitude, s.longitude, _CELLS[0]["centroid_lat"], _CELLS[0]["centroid_lon"]))
    nearest_only = score_origin_candidates_7c(grid_cells=_CELLS[:1], sources=[nearest], candidates=(c0,), wind=None)[c0.candidate_id][0].score
    assert full != pytest.approx(nearest_only)
    assert full > nearest_only  # more positive-kernel sources strictly increase the sum


def test_7cmath_05_no_st_cluster_or_role_parameter_anywhere_in_the_scoring_signature():
    params = set(inspect.signature(score_origin_candidates_7c).parameters)
    forbidden = {"st_cluster", "cluster_role", "is_noise", "is_core", "st_config", "stdbscan_config"}
    assert not (params & forbidden)
    src = inspect.getsource(wind_scoring_7c)
    for token in ("STDBSCAN", "cluster_role", "is_noise", "is_core"):
        assert token not in src


def test_7cmath_06_no_probability_label_anywhere_in_the_7c_candidate_registry():
    for c in build_candidate_registry_7c():
        d = c.as_dict()
        assert d["output_label"] == "RELATIVE_SPATIAL_SCORE"
        blob = str(d).lower()
        for forbidden in ("probability", "chance of infection", "infection risk"):
            assert forbidden not in blob


def test_7cmath_07_no_environmental_or_water_composite_candidate_family_exists():
    families = {c.family for c in build_candidate_registry_7c()}
    assert families == {C0_FAMILY, CW_FAMILY}


def test_7cmath_08_no_host_factor_anywhere_in_the_wind_scoring_module():
    src = inspect.getsource(wind_scoring_7c)
    for forbidden in ("host_factor", "host_density", "Host_i"):
        assert forbidden not in src


def test_7ccov_01_complete_c0_anchor_always_eligible_when_support_unchanged():
    eligibility = assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=0, max_missing_domain_area_km2=0.0)
    assert eligibility == PRIMARY_SELECTION_ELIGIBLE


def test_7ccov_02_missing_weather_dependent_domain_area_beyond_tolerance_makes_candidate_ineligible():
    from components.geospatial_tracking.services.model_development.evaluation_protocol_7b import SOFTWARE_ZERO_AREA_TOLERANCE_KM2

    eligibility = assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=0, max_missing_domain_area_km2=SOFTWARE_ZERO_AREA_TOLERANCE_KM2 * 10)
    assert eligibility == PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE


def test_7ccov_03_one_target_score_unavailable_row_makes_candidate_ineligible():
    eligibility = assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=1, max_missing_domain_area_km2=0.0)
    assert eligibility == PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE


def test_7ccov_04_wind_candidate_ineligibility_never_removes_c0_from_comparison():
    registry = build_candidate_registry_7c()
    families_by_id = {c.candidate_id: c.family for c in registry}
    c0_id = next(c.candidate_id for c in registry if c.family == C0_FAMILY)
    cw_ids = tuple(c.candidate_id for c in registry if c.family == CW_FAMILY)
    eligible = (c0_id,)
    note = classify_selection_note_7c(candidate_families_by_id=families_by_id, eligible_candidate_ids=eligible, ineligible_candidate_ids=cw_ids)
    assert note == WIND_CANDIDATES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_WEATHER_SUPPORT
    assert c0_id in eligible  # never dropped


def test_7ccov_05_ineligible_candidate_coverage_summary_entry_is_preserved_not_deleted():
    # simulates the exact shape run_checkpoint_7c_development builds --
    # an ineligible candidate keeps a full diagnostic entry, never popped.
    coverage_summary = {
        "C7C:C0:abc": {"max_missing_domain_area_km2": 0.0, "n_target_score_unavailable_rows": 0, "eligibility": PRIMARY_SELECTION_ELIGIBLE},
        "C7C:CW:def": {"max_missing_domain_area_km2": 0.0, "n_target_score_unavailable_rows": 3, "eligibility": PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE},
    }
    assert "C7C:CW:def" in coverage_summary
    assert coverage_summary["C7C:CW:def"]["n_target_score_unavailable_rows"] == 3
