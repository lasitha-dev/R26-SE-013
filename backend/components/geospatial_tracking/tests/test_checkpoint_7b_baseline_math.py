"""Checkpoint 7B Part 39: BASE7B-01..09 baseline scoring math tests."""

from __future__ import annotations

import inspect
import math

from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.geospatial.distance import distance_km
from components.geospatial_tracking.services.geospatial.host_density.fao_glw import DATASET_NAME, REFERENCE_YEAR, UNITS
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.hazard.kernels import evaluate_kernel
from components.geospatial_tracking.services.model_development import baseline_scoring
from components.geospatial_tracking.services.model_development.baseline_scoring import (
    CellScore,
    score_origin_all_candidates,
)
from components.geospatial_tracking.services.model_development.candidate_registry_7b import BaselineCandidateSpec
from components.geospatial_tracking.services.model_development.development_run_7b import TargetEvaluationRecord

_CELL_LAT, _CELL_LON = 15.0, 101.0
_SOURCES = [
    EligibleSourcePoint(source_id="S1", latitude=15.1, longitude=101.0),
    EligibleSourcePoint(source_id="S2", latitude=14.8, longitude=101.3),
    EligibleSourcePoint(source_id="S3", latitude=15.3, longitude=100.7),
]


def _species_real(value: float) -> dict:
    return {
        "status": "REAL", "value": value, "units": UNITS, "dataset_name": DATASET_NAME, "dataset_version": REFERENCE_YEAR,
        "sample_support_digest": f"digest:{value}",
    }


def _cell(*, host_value_cattle: float | None = None, host_value_buffalo: float | None = None) -> dict:
    host_density = {}
    if host_value_cattle is not None:
        host_density["cattle"] = _species_real(host_value_cattle)
    if host_value_buffalo is not None:
        host_density["buffalo"] = _species_real(host_value_buffalo)
    return {
        "grid_cell_id": "CELL:0:0", "scientific_cell_id": "SCICELL:aaaa", "centroid_lat": _CELL_LAT, "centroid_lon": _CELL_LON,
        "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "host_density": host_density,
    }


def _b0_candidate(family: str, scale: float) -> BaselineCandidateSpec:
    return BaselineCandidateSpec(
        candidate_id=f"TEST:B0:{family}:{scale}", baseline_family="B0_DISTANCE_ONLY", host_factor_candidate=None,
        kernel_family=family, kernel_scale_km=scale, source_weighting="EQUAL_SOURCE_BASELINE", output_label="RELATIVE_SPATIAL_SCORE",
    )


def _host_candidate(family: str, scale: float, host_factor: str) -> BaselineCandidateSpec:
    return BaselineCandidateSpec(
        candidate_id=f"TEST:{host_factor}:{family}:{scale}", baseline_family="B1_HOST_DISTANCE_LOG1P" if "LOG1P" in host_factor else "B2_HOST_DISTANCE_ECDF",
        host_factor_candidate=host_factor, kernel_family=family, kernel_scale_km=scale,
        source_weighting="EQUAL_SOURCE_BASELINE", output_label="RELATIVE_SPATIAL_SCORE",
    )


class _FakeReferenceProfile:
    status = "COMPLETE_DIAGNOSTIC"
    host_density_total_log1p_quantiles = {"lower": 0.0, "upper": 5.0}
    host_density_total_reference_values = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 100.0)


def test_base7b_01_b0_exponential_score_equals_sum_kernel():
    cell = _cell()
    candidate = _b0_candidate("EXPONENTIAL", 10.0)
    out = score_origin_all_candidates(grid_cells=[cell], sources=_SOURCES, candidates=(candidate,))
    got = out[candidate.candidate_id][0].score

    expected = sum(
        evaluate_kernel(distance_km(s.latitude, s.longitude, _CELL_LAT, _CELL_LON), family="EXPONENTIAL", distance_scale_km=10.0)
        for s in _SOURCES
    )
    assert math.isclose(got, expected, rel_tol=1e-12)


def test_base7b_02_b0_gaussian_score_equals_sum_kernel():
    cell = _cell()
    candidate = _b0_candidate("GAUSSIAN", 15.0)
    out = score_origin_all_candidates(grid_cells=[cell], sources=_SOURCES, candidates=(candidate,))
    got = out[candidate.candidate_id][0].score

    expected = sum(
        evaluate_kernel(distance_km(s.latitude, s.longitude, _CELL_LAT, _CELL_LON), family="GAUSSIAN", distance_scale_km=15.0)
        for s in _SOURCES
    )
    assert math.isclose(got, expected, rel_tol=1e-12)


def test_base7b_03_b1_equals_log1p_host_times_kernel_sum():
    cell = _cell(host_value_cattle=3.0, host_value_buffalo=1.0)
    candidate = _host_candidate("EXPONENTIAL", 10.0, "LOG1P_ROBUST_REFERENCE_SCALE")
    profile = _FakeReferenceProfile()
    out = score_origin_all_candidates(grid_cells=[cell], sources=_SOURCES, candidates=(candidate,), reference_profile=profile, transform_config=FactorTransformConfig())
    got = out[candidate.candidate_id][0].score

    kernel_sum = sum(evaluate_kernel(distance_km(s.latitude, s.longitude, _CELL_LAT, _CELL_LON), family="EXPONENTIAL", distance_scale_km=10.0) for s in _SOURCES)
    host_total = 4.0
    x = math.log1p(host_total)
    z = min(1.0, max(0.0, (x - 0.0) / (5.0 - 0.0)))
    assert math.isclose(got, z * kernel_sum, rel_tol=1e-12)


def test_base7b_04_b2_equals_ecdf_host_times_kernel_sum():
    cell = _cell(host_value_cattle=3.0, host_value_buffalo=1.0)  # host_total = 4.0
    candidate = _host_candidate("EXPONENTIAL", 10.0, "EMPIRICAL_CDF_REFERENCE")
    profile = _FakeReferenceProfile()
    out = score_origin_all_candidates(grid_cells=[cell], sources=_SOURCES, candidates=(candidate,), reference_profile=profile, transform_config=FactorTransformConfig())
    got = out[candidate.candidate_id][0].score

    kernel_sum = sum(evaluate_kernel(distance_km(s.latitude, s.longitude, _CELL_LAT, _CELL_LON), family="EXPONENTIAL", distance_scale_km=10.0) for s in _SOURCES)
    # sorted_reference_values = (1,2,3,4,5,6,100); LOWER_RANK bisect_left(4.0) = 3
    z = 3 / 7
    assert math.isclose(got, z * kernel_sum, rel_tol=1e-12)


def test_base7b_05_all_eligible_sources_contribute():
    cell = _cell()
    candidate = _b0_candidate("EXPONENTIAL", 10.0)
    out_all = score_origin_all_candidates(grid_cells=[cell], sources=_SOURCES, candidates=(candidate,))[candidate.candidate_id][0].score
    out_two = score_origin_all_candidates(grid_cells=[cell], sources=_SOURCES[:2], candidates=(candidate,))[candidate.candidate_id][0].score
    assert out_all != out_two
    single_terms = [
        evaluate_kernel(distance_km(s.latitude, s.longitude, _CELL_LAT, _CELL_LON), family="EXPONENTIAL", distance_scale_km=10.0)
        for s in _SOURCES
    ]
    assert math.isclose(out_all, sum(single_terms), rel_tol=1e-12)


def test_base7b_06_removing_a_farther_nonnearest_source_changes_the_score():
    """Proves the second (non-nearest) source actually contributed --
    nearest-source-only scoring is structurally impossible here."""
    cell = _cell()
    candidate = _b0_candidate("EXPONENTIAL", 10.0)
    nearest_only = [_SOURCES[0]]
    got_nearest_only = score_origin_all_candidates(grid_cells=[cell], sources=nearest_only, candidates=(candidate,))[candidate.candidate_id][0].score
    got_all = score_origin_all_candidates(grid_cells=[cell], sources=_SOURCES, candidates=(candidate,))[candidate.candidate_id][0].score
    assert got_all > got_nearest_only


def test_base7b_07_no_component_or_cluster_gating_parameter_exists():
    params = set(inspect.signature(score_origin_all_candidates).parameters)
    forbidden = {"component_id", "component", "cluster_id", "cluster", "st_cluster", "domain"}
    assert not (params & forbidden), f"scoring function must never accept a component/cluster gate parameter, found {params & forbidden}"


def test_base7b_08_no_st_cluster_reference_in_scoring_module_source():
    source = inspect.getsource(baseline_scoring)
    for forbidden in ("STDBSCAN", "st_cluster", "MinPts", "eps_time"):
        assert forbidden not in source


def test_base7b_09_score_never_labeled_probability():
    for cls in (CellScore, TargetEvaluationRecord):
        for f in cls.__dataclass_fields__:
            assert "probability" not in f.lower()
    candidate = _b0_candidate("EXPONENTIAL", 10.0)
    assert candidate.output_label == "RELATIVE_SPATIAL_SCORE"
