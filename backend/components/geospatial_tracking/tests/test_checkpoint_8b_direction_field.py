"""Checkpoint 8B: frozen-C0-derived local geometric relative-risk
tendency field, parameter-free directional weight definition,
zero-distance mass-coverage semantics, and FIT_DEVELOPMENT-only
structural readiness audit.

READINESS/STRUCTURAL ONLY. No direction model is fit, no directional
weight is tuned, no direction candidate selection is run, no future-
target angular error is calculated, and no held-out/Sri Lanka
direction performance is scored anywhere in this file."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import math
from pathlib import Path

import pytest

from components.geospatial_tracking.services.direction import c0_geometric_tendency as c0_dir_module
from components.geospatial_tracking.services.direction.c0_geometric_tendency import (
    COMPLETE_DIRECTIONAL_MASS_COVERAGE,
    DIRECTION_SEMANTICS_8B,
    PARTIAL_DIRECTIONAL_MASS_COVERAGE_ZERO_DISTANCE,
    TEMPORAL_SCOPE_8B,
    CellDirectionTendency8B,
    c0_directional_weight,
    compute_cell_direction_tendency,
)
from components.geospatial_tracking.services.geospatial.distance import source_to_cell_unit_vector
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.hazard.kernels import evaluate_kernel
from components.geospatial_tracking.services.model_development.candidate_registry_7c import (
    C0_FAMILY,
    FROZEN_KERNEL_FAMILY,
    FROZEN_KERNEL_SCALE_KM,
    build_candidate_registry_7c,
)
from components.geospatial_tracking.services.model_development.direction_protocol_8b import (
    DIRECTION_EVALUATION_TRUTH_STATUS_8B,
    DIRECTIONAL_WEIGHT_STATUS_8B,
    FROZEN_7C_SPEC_HASH_8B,
    FROZEN_C0_SELECTED_CANDIDATE_ID,
    OVERALL_CLASSIFICATION_8B,
    direction_method_protocol_dict_8b,
    direction_method_protocol_hash_8b,
    parent_direction_readiness_protocol_hash_8a1,
    verify_8a1_preflight,
)
from components.geospatial_tracking.services.model_development.direction_readiness_8a import (
    DIRECTION_AVAILABLE,
    DIRECTIONAL_CONTRIBUTIONS_CANCELLED,
)
from components.geospatial_tracking.services.model_development.wind_scoring_7c import score_origin_candidates_7c

_EXPECTED_8A1_HASH = "8aa69a68f27980134caa3cb1c5c96f5b66ab1e41274bc9def38a9aa5a627869e"


def _cell(lat: float, lon: float, cell_id: str = "TESTCELL") -> dict:
    return {
        "grid_cell_id": cell_id, "scientific_cell_id": cell_id,
        "area_km2": 25.0, "domain_overlap_area_km2": 25.0,
        "centroid_lat": lat, "centroid_lon": lon,
    }


# ---------------------------------------------------------------------------
# Part 0: 8A.1 pre-flight identity check
# ---------------------------------------------------------------------------


def test_8b_freeze_01_8a1_parent_hash_exact():
    assert parent_direction_readiness_protocol_hash_8a1() == _EXPECTED_8A1_HASH
    live_dict = verify_8a1_preflight()
    required_keys = {
        "bearing_convention", "generic_bearing_zero_semantics", "resultant_relative_cancellation_epsilon",
        "unit_vector_norm_tolerance", "clarity_range_clamp_tolerance", "non_finite_rejection_semantics",
        "zero_distance_semantics", "clarity_range_invariant_semantics", "wind_calm_epsilon_m_s",
        "wind_to_from_conversion", "source_to_cell_orientation", "temporal_firewall",
        "direction_method_candidates_8a1", "direction_weight_status", "direction_evaluation_truth_status",
        "overall_readiness_status",
    }
    assert required_keys <= set(live_dict.keys())
    assert "NOT_SPREAD_DIRECTION" in live_dict["overall_readiness_status"]


def test_8b_freeze_02_frozen_c0_candidate_spec_exact():
    assert FROZEN_C0_SELECTED_CANDIDATE_ID == "C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8"
    assert FROZEN_7C_SPEC_HASH_8B == "ef3511d3527da6d85598846c0d828509ed07f134ac8d987c3d5702b507505a6d"


# ---------------------------------------------------------------------------
# Directional weight = exact frozen C0 per-source contribution (Part 2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("d", [0.0, 1.0, 5.0, 25.0, 100.0])
def test_8b_weight_01_weight_equals_exact_frozen_c0_kernel(d):
    expected = evaluate_kernel(d, family=FROZEN_KERNEL_FAMILY, distance_scale_km=FROZEN_KERNEL_SCALE_KM)
    assert c0_directional_weight(d) == expected
    assert c0_directional_weight(d) == pytest.approx(math.exp(-d / 25.0))


def test_8b_weight_02_sum_of_directional_weights_equals_frozen_c0_cell_score():
    cell = _cell(1.0, 1.0)
    sources = [
        EligibleSourcePoint(source_id="S1", latitude=0.5, longitude=0.5),
        EligibleSourcePoint(source_id="S2", latitude=1.5, longitude=0.8),
        EligibleSourcePoint(source_id="S3", latitude=0.9, longitude=1.4),
    ]
    result = compute_cell_direction_tendency(cell, sources)

    c0_registry = build_candidate_registry_7c()
    c0_spec = next(c for c in c0_registry if c.family == C0_FAMILY)
    c0_scores = score_origin_candidates_7c(grid_cells=[cell], sources=sources, candidates=(c0_spec,), wind=None)
    c0_cell_score = c0_scores[c0_spec.candidate_id][0].score

    assert result.total_scalar_c0_mass == c0_cell_score  # exact, same underlying kernel calls


def test_8b_weight_03_no_new_fitted_directional_coefficient():
    src = inspect.getsource(c0_dir_module)
    for forbidden in ("kappa", "anisotropy", "learned", "fitted_coefficient", "tunable", "CANDIDATES ="):
        assert forbidden not in src

    params = list(inspect.signature(c0_directional_weight).parameters)
    assert params == ["distance_km"]  # no tuning/weight/coefficient argument


# ---------------------------------------------------------------------------
# Geometry orientation (Part 4)
# ---------------------------------------------------------------------------


def test_8b_geo_01_source_to_cell_orientation_preserved():
    cell = _cell(1.0, 0.0)
    sources = [EligibleSourcePoint(source_id="S1", latitude=0.0, longitude=0.0)]  # source due south
    result = compute_cell_direction_tendency(cell, sources)
    term = result.source_terms[0]
    assert term.t_hat_north == pytest.approx(1.0, abs=1e-6)
    assert term.t_hat_east == pytest.approx(0.0, abs=1e-6)


def test_8b_geo_02_single_source_bearing_and_full_clarity():
    cell = _cell(1.0, 0.0)
    sources = [EligibleSourcePoint(source_id="S1", latitude=0.0, longitude=0.0)]
    result = compute_cell_direction_tendency(cell, sources)
    raw = source_to_cell_unit_vector(0.0, 0.0, 1.0, 0.0)
    expected_bearing = math.degrees(math.atan2(raw.t_hat_east, raw.t_hat_north)) % 360.0
    assert result.bearing_deg == pytest.approx(expected_bearing, abs=1e-6)
    assert result.directional_clarity == pytest.approx(1.0)
    assert result.direction_status == DIRECTION_AVAILABLE


# ---------------------------------------------------------------------------
# Multi-source aggregation (Part 5, 9)
# ---------------------------------------------------------------------------


def test_8b_multi_01_all_sources_contribute_before_aggregation():
    cell = _cell(0.0, 0.0)
    sources = [
        EligibleSourcePoint(source_id="S1", latitude=0.05, longitude=0.0),
        EligibleSourcePoint(source_id="S2", latitude=0.0, longitude=0.05),
        EligibleSourcePoint(source_id="S3", latitude=-0.03, longitude=-0.02),
    ]
    result = compute_cell_direction_tendency(cell, sources)

    manual_east, manual_north, manual_mass = 0.0, 0.0, 0.0
    for s in sources:
        vec = source_to_cell_unit_vector(s.latitude, s.longitude, 0.0, 0.0)
        w = c0_directional_weight(vec.distance_km)
        manual_mass += w
        manual_east += w * vec.t_hat_east
        manual_north += w * vec.t_hat_north

    assert result.total_scalar_c0_mass == pytest.approx(manual_mass)
    assert result.resultant_east == pytest.approx(manual_east)
    assert result.resultant_north == pytest.approx(manual_north)
    assert len(result.source_terms) == 3


def test_8b_multi_02_nearest_source_replacement_impossible():
    src = inspect.getsource(c0_dir_module)
    assert "nearest_source_id" not in src
    assert "nearest_source(" not in src

    cell = _cell(0.0, 0.0)
    sources = [
        EligibleSourcePoint(source_id="near", latitude=0.01, longitude=0.0),
        EligibleSourcePoint(source_id="far", latitude=0.5, longitude=0.0),
    ]
    result = compute_cell_direction_tendency(cell, sources)
    assert result.n_directionally_defined_sources == 2
    assert len(result.source_terms) == 2


def test_8b_multi_03_opposing_equal_mass_cancels():
    cell = _cell(0.0, 0.0)
    sources = [
        EligibleSourcePoint(source_id="N", latitude=0.05, longitude=0.0),
        EligibleSourcePoint(source_id="S", latitude=-0.05, longitude=0.0),
    ]
    result = compute_cell_direction_tendency(cell, sources)
    assert result.direction_status == DIRECTIONAL_CONTRIBUTIONS_CANCELLED
    assert result.bearing_deg is None
    assert result.directional_clarity == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Zero-distance mass coverage (Part 6)
# ---------------------------------------------------------------------------


def test_8b_zero_01_zero_distance_retains_scalar_mass_no_fabricated_direction():
    cell = _cell(1.0, 1.0, cell_id="C1")
    sources = [
        EligibleSourcePoint(source_id="AT_CELL", latitude=1.0, longitude=1.0),  # distance == 0
        EligibleSourcePoint(source_id="OFFSET", latitude=1.1, longitude=1.0),
    ]
    result = compute_cell_direction_tendency(cell, sources)
    zero_term = next(t for t in result.source_terms if t.source_id == "AT_CELL")
    assert zero_term.distance_km == 0.0
    assert zero_term.c0_directional_weight == pytest.approx(1.0)  # K(0) == 1
    assert zero_term.direction_defined is False
    assert zero_term.t_hat_east is None and zero_term.t_hat_north is None
    assert zero_term.exclusion_reason is not None

    assert result.total_scalar_c0_mass == pytest.approx(1.0 + c0_directional_weight(next(
        t.distance_km for t in result.source_terms if t.source_id == "OFFSET"
    )))
    assert result.directionally_defined_mass < result.total_scalar_c0_mass


def test_8b_zero_02_coverage_reflects_excluded_zero_distance_mass():
    cell = _cell(1.0, 1.0, cell_id="C1")
    sources = [
        EligibleSourcePoint(source_id="AT_CELL", latitude=1.0, longitude=1.0),
        EligibleSourcePoint(source_id="OFFSET", latitude=1.1, longitude=1.0),
    ]
    result = compute_cell_direction_tendency(cell, sources)
    offset_weight = next(t.c0_directional_weight for t in result.source_terms if t.source_id == "OFFSET")
    expected_coverage = offset_weight / (1.0 + offset_weight)
    assert result.directional_input_coverage == pytest.approx(expected_coverage)


# ---------------------------------------------------------------------------
# Mass-coverage status (structural, never a tuned threshold)
# ---------------------------------------------------------------------------


def test_8b_cov_01_complete_coverage_when_no_zero_distance_mass():
    cell = _cell(0.0, 0.0)
    sources = [
        EligibleSourcePoint(source_id="S1", latitude=0.05, longitude=0.0),
        EligibleSourcePoint(source_id="S2", latitude=0.0, longitude=0.05),
    ]
    result = compute_cell_direction_tendency(cell, sources)
    assert result.directional_mass_coverage_status == COMPLETE_DIRECTIONAL_MASS_COVERAGE
    assert result.directional_input_coverage == pytest.approx(1.0)


def test_8b_cov_02_partial_coverage_when_zero_distance_mass_exists():
    cell = _cell(1.0, 1.0, cell_id="C1")
    sources = [
        EligibleSourcePoint(source_id="AT_CELL", latitude=1.0, longitude=1.0),
        EligibleSourcePoint(source_id="OFFSET", latitude=1.1, longitude=1.0),
    ]
    result = compute_cell_direction_tendency(cell, sources)
    assert result.directional_mass_coverage_status == PARTIAL_DIRECTIONAL_MASS_COVERAGE_ZERO_DISTANCE


# ---------------------------------------------------------------------------
# Terminology / semantics (Part 7, 15, 16)
# ---------------------------------------------------------------------------


def test_8b_sem_01_clarity_and_coverage_are_distinct():
    cell = _cell(1.0, 1.0, cell_id="C1")
    sources = [
        EligibleSourcePoint(source_id="AT_CELL", latitude=1.0, longitude=1.0),
        EligibleSourcePoint(source_id="A", latitude=1.05, longitude=1.0),
        EligibleSourcePoint(source_id="B", latitude=1.05, longitude=1.02),
    ]
    result = compute_cell_direction_tendency(cell, sources)
    assert result.directional_clarity is not None
    assert result.directional_input_coverage is not None
    assert result.directional_clarity != result.directional_input_coverage
    field_names = {f.name for f in dataclasses.fields(CellDirectionTendency8B)}
    assert "directional_clarity" in field_names
    assert "directional_input_coverage" in field_names


def test_8b_sem_02_no_field_named_confidence():
    field_names = {f.name for f in dataclasses.fields(CellDirectionTendency8B)}
    assert not any("confidence" in name for name in field_names)


def test_8b_sem_03_output_semantics_is_geometric_relative_risk_tendency():
    assert DIRECTION_SEMANTICS_8B == "C0_DERIVED_LOCAL_GEOMETRIC_RELATIVE_RISK_TENDENCY"
    cell = _cell(0.0, 0.0)
    sources = [EligibleSourcePoint(source_id="S1", latitude=0.05, longitude=0.0)]
    result = compute_cell_direction_tendency(cell, sources)
    assert result.direction_semantics == DIRECTION_SEMANTICS_8B
    assert "GEOMETRIC_RELATIVE_RISK_TENDENCY" in DIRECTION_SEMANTICS_8B


# ---------------------------------------------------------------------------
# Static t0 temporal semantics (Part 10)
# ---------------------------------------------------------------------------


def test_8b_time_01_field_is_t0_static_not_day_specific():
    assert TEMPORAL_SCOPE_8B == "T0_STATIC_NOT_DAY_SPECIFIC"
    cell = _cell(0.0, 0.0)
    sources = [EligibleSourcePoint(source_id="S1", latitude=0.05, longitude=0.0)]
    result = compute_cell_direction_tendency(cell, sources)
    assert result.temporal_scope == TEMPORAL_SCOPE_8B


def test_8b_time_02_no_future_target_argument_exists():
    params = set(inspect.signature(compute_cell_direction_tendency).parameters)
    forbidden = {"target", "future_target", "target_cell", "target_location", "future_outbreak"}
    assert not (params & forbidden)
    # structural check (not a blunt text scan, which would false-positive on
    # this module's own docstring disclaiming exactly this): no function or
    # dataclass field anywhere in the module is target-named.
    tree = ast.parse(inspect.getsource(c0_dir_module))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for arg in node.args.args + node.args.kwonlyargs:
                assert "target" not in arg.arg.lower(), f"{node.name} has a target-like parameter: {arg.arg}"
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assert "target" not in node.target.id.lower()


def test_8b_time_03_no_d1_d7_realized_weather_used():
    tree = ast.parse(inspect.getsource(c0_dir_module))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    for forbidden_substr in ("weather", "era5", "wind"):
        assert not any(forbidden_substr in m.lower() for m in imported_modules), imported_modules


# ---------------------------------------------------------------------------
# Circular-evaluation prohibition (Part 12)
# ---------------------------------------------------------------------------


def test_8b_circular_01_future_target_coordinates_cannot_be_supplied():
    for name, fn in inspect.getmembers(c0_dir_module, inspect.isfunction):
        params = set(inspect.signature(fn).parameters)
        assert not any("target" in p.lower() for p in params), f"{name} exposes a target-like parameter: {params}"


def test_8b_circular_02_no_angular_performance_evaluation_path():
    from components.geospatial_tracking.services.model_development import direction_protocol_8b as protocol_8b_module

    forbidden = ("angular_error", "mean_angular_error", "median_angular_error", "direction_hit_rate", "bearing_accuracy")
    for module in (c0_dir_module, protocol_8b_module):
        src = inspect.getsource(module)
        for term in forbidden:
            assert term not in src


# ---------------------------------------------------------------------------
# C0 unchanged (Part 1)
# ---------------------------------------------------------------------------


def test_8b_c0_01_c0_scorer_candidate_id_spec_unchanged():
    registry = build_candidate_registry_7c()
    c0 = next(c for c in registry if c.family == C0_FAMILY)
    assert c0.candidate_id == "C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8"
    assert c0.anisotropy_mode is None
    assert c0.anisotropy_kappa is None


# ---------------------------------------------------------------------------
# No wind import (Part 13)
# ---------------------------------------------------------------------------


def test_8b_wind_01_method_a_imports_no_weather_wind_input():
    tree = ast.parse(inspect.getsource(c0_dir_module))
    direct_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            direct_imports.append(node.module)
    for forbidden_substr in ("weather", "wind", "era5", "anisotropy"):
        assert not any(forbidden_substr in m.lower() for m in direct_imports), direct_imports


# ---------------------------------------------------------------------------
# Source-count semantics (Part 8)
# ---------------------------------------------------------------------------


def test_8b_sourcecount_01_counts_unambiguous_and_consistent():
    cell = _cell(1.0, 1.0, cell_id="C1")
    sources = [
        EligibleSourcePoint(source_id="AT_CELL", latitude=1.0, longitude=1.0),
        EligibleSourcePoint(source_id="A", latitude=1.05, longitude=1.0),
        EligibleSourcePoint(source_id="B", latitude=1.05, longitude=1.02),
    ]
    result = compute_cell_direction_tendency(cell, sources)
    assert result.n_total_eligible_sources == 3
    assert result.n_positive_c0_weight_sources == 3  # EXPONENTIAL kernel: always == total
    assert result.n_directionally_defined_sources + result.n_zero_distance_undefined_direction_sources == result.n_total_eligible_sources
    assert result.n_positive_weight_directionally_defined_sources == result.n_directionally_defined_sources
    assert result.n_zero_distance_undefined_direction_sources == 1


# ---------------------------------------------------------------------------
# Protocol hash determinism (Part 17)
# ---------------------------------------------------------------------------


def test_8b_evidence_01_tracked_summary_internally_consistent():
    """Never skips (mirrors the 7D/7E TRACKED evidence-summary pattern)."""
    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_8B_EVIDENCE_SUMMARY.json"
    assert path.exists(), "CHECKPOINT_8B_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = json.loads(path.read_text(encoding="utf-8"))

    assert d["direction_method_protocol_hash_8b"] == direction_method_protocol_hash_8b()
    assert d["parent_direction_readiness_protocol_hash_8a1"] == parent_direction_readiness_protocol_hash_8a1()
    assert d["frozen_c0_selected_candidate_id"] == FROZEN_C0_SELECTED_CANDIDATE_ID
    assert d["frozen_7c_spec_hash"] == FROZEN_7C_SPEC_HASH_8B
    assert d["final_classification"] == OVERALL_CLASSIFICATION_8B
    assert d["structural_audit_summary"]["n_invariant_failures"] == 0
    assert d["structural_audit_summary"]["n_origins_processed"] == d["structural_audit_summary"]["n_fit_development_origins_total"]


def test_8b_hash_01_protocol_hash_deterministic_and_timestamp_free():
    d = direction_method_protocol_dict_8b()
    assert "generated_at" not in d
    assert "timestamp" not in d
    assert direction_method_protocol_hash_8b() == direction_method_protocol_hash_8b()
    assert DIRECTION_EVALUATION_TRUTH_STATUS_8B == "DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN"
    assert DIRECTIONAL_WEIGHT_STATUS_8B == "DIRECTIONAL_WEIGHT_DERIVED_FROM_FROZEN_C0_NO_NEW_PARAMETER"
    assert "NOT_PREDICTIVE_SPREAD_DIRECTION" in OVERALL_CLASSIFICATION_8B
