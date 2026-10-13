"""Checkpoint 8A.1: resultant scale-invariance, directional-term
validation, calm-wind semantic consistency, method-readiness
classification hardening, and final 8A freeze.

READINESS/SEMANTICS ONLY. No direction model is fit, no directional
weight is selected, and no FIT_DEVELOPMENT/held-out/Sri Lanka direction
performance is scored anywhere in this file."""

from __future__ import annotations

import dataclasses
import math

import pytest

from components.geospatial_tracking.services.hazard.anisotropy import (
    CALM_WIND_EPSILON_M_S,
    compute_meteorological_alignment,
)
from components.geospatial_tracking.services.hazard.contracts import WindVector
from components.geospatial_tracking.services.model_development.candidate_registry_7c import (
    C0_FAMILY,
    build_candidate_registry_7c,
)
from components.geospatial_tracking.services.model_development.direction_protocol_8a import (
    DIRECTION_METHOD_CANDIDATES_8A1,
    HISTORICAL_CHECKPOINT_8A_INITIAL_READINESS_HASH,
    OVERALL_READINESS_STATUS_8A1,
    direction_readiness_protocol_dict_8a,
    direction_readiness_protocol_dict_8a1,
    direction_readiness_protocol_hash_8a,
    direction_readiness_protocol_hash_8a1,
)
from components.geospatial_tracking.services.model_development.direction_readiness_8a import (
    DIRECTION_AVAILABLE,
    DIRECTIONAL_CONTRIBUTIONS_CANCELLED,
    NO_DIRECTIONAL_MASS,
    DirectionalMassTerm,
    ResultantVectorResult,
    bearing_deg_from_components,
    compute_resultant_vector,
    wind_from_bearing_deg,
    wind_to_bearing_from_components,
)

from components.geospatial_tracking.services.geospatial.weather import wind as raw_wind_module


def _asymmetric_terms(scale: float) -> list[DirectionalMassTerm]:
    return [
        DirectionalMassTerm("A", weight=2.0 * scale, t_hat_east=0.6, t_hat_north=0.8, distance_km=5.0),
        DirectionalMassTerm("B", weight=1.0 * scale, t_hat_east=1.0, t_hat_north=0.0, distance_km=5.0),
        DirectionalMassTerm("C", weight=1.0 * scale, t_hat_east=0.0, t_hat_north=-1.0, distance_km=5.0),
    ]


# ---------------------------------------------------------------------------
# Scale invariance (Part 2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scale", [1e-12, 1.0, 1e12])
def test_8a1_scale_01_common_rescaling_preserves_bearing(scale):
    baseline = compute_resultant_vector(_asymmetric_terms(1.0))
    scaled = compute_resultant_vector(_asymmetric_terms(scale))
    assert baseline.bearing_deg is not None
    assert scaled.bearing_deg is not None
    assert scaled.bearing_deg == pytest.approx(baseline.bearing_deg, abs=1e-6)


@pytest.mark.parametrize("scale", [1e-12, 1.0, 1e12])
def test_8a1_scale_02_common_rescaling_preserves_clarity(scale):
    baseline = compute_resultant_vector(_asymmetric_terms(1.0))
    scaled = compute_resultant_vector(_asymmetric_terms(scale))
    assert scaled.directional_clarity == pytest.approx(baseline.directional_clarity, abs=1e-9)


# ---------------------------------------------------------------------------
# No directional mass / cancellation (Part 2)
# ---------------------------------------------------------------------------


def test_8a1_zero_01_no_usable_mass_bearing_and_clarity_none():
    terms = [
        DirectionalMassTerm("A", weight=0.0, t_hat_east=1.0, t_hat_north=0.0, distance_km=5.0),
        DirectionalMassTerm("B", weight=0.0, t_hat_east=0.0, t_hat_north=1.0, distance_km=5.0),
    ]
    result = compute_resultant_vector(terms)
    assert result.bearing_deg is None
    assert result.directional_clarity is None
    assert result.cancellation_status == NO_DIRECTIONAL_MASS


def test_8a1_cancel_01_equal_opposing_positive_mass_cancels():
    terms = [
        DirectionalMassTerm("A", weight=1.0, t_hat_east=1.0, t_hat_north=0.0, distance_km=5.0),
        DirectionalMassTerm("B", weight=1.0, t_hat_east=-1.0, t_hat_north=0.0, distance_km=5.0),
    ]
    result = compute_resultant_vector(terms)
    assert result.bearing_deg is None
    assert result.directional_clarity == pytest.approx(0.0, abs=1e-9)
    assert result.cancellation_status == DIRECTIONAL_CONTRIBUTIONS_CANCELLED


@pytest.mark.parametrize("scale", [1.0, 5.0, 1e6])
def test_8a1_cancel_02_cancellation_classification_stable_under_rescaling(scale):
    terms = [
        DirectionalMassTerm("A", weight=1.0 * scale, t_hat_east=0.0, t_hat_north=1.0, distance_km=5.0),
        DirectionalMassTerm("B", weight=1.0 * scale, t_hat_east=0.0, t_hat_north=-1.0, distance_km=5.0),
    ]
    result = compute_resultant_vector(terms)
    assert result.cancellation_status == DIRECTIONAL_CONTRIBUTIONS_CANCELLED
    assert result.bearing_deg is None


# ---------------------------------------------------------------------------
# Non-finite rejection (Part 4)
# ---------------------------------------------------------------------------


def test_8a1_finite_01_nan_weight_rejected():
    with pytest.raises(ValueError):
        DirectionalMassTerm("A", weight=float("nan"), t_hat_east=1.0, t_hat_north=0.0, distance_km=5.0)


def test_8a1_finite_02_infinite_weight_rejected():
    with pytest.raises(ValueError):
        DirectionalMassTerm("A", weight=float("inf"), t_hat_east=1.0, t_hat_north=0.0, distance_km=5.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_8a1_finite_03_non_finite_t_hat_component_rejected(bad):
    with pytest.raises(ValueError):
        DirectionalMassTerm("A", weight=1.0, t_hat_east=bad, t_hat_north=0.0, distance_km=5.0)
    with pytest.raises(ValueError):
        DirectionalMassTerm("A", weight=1.0, t_hat_east=1.0, t_hat_north=bad, distance_km=5.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_8a1_finite_04_non_finite_distance_rejected(bad):
    with pytest.raises(ValueError):
        DirectionalMassTerm("A", weight=1.0, t_hat_east=1.0, t_hat_north=0.0, distance_km=bad)


# ---------------------------------------------------------------------------
# Unit-vector invariant (Part 5)
# ---------------------------------------------------------------------------


def test_8a1_unit_01_valid_unit_vector_accepted():
    term = DirectionalMassTerm("A", weight=1.0, t_hat_east=0.6, t_hat_north=0.8, distance_km=5.0)
    assert term.t_hat_east == 0.6


def test_8a1_unit_02_non_unit_vector_materially_outside_tolerance_rejected():
    with pytest.raises(ValueError):
        DirectionalMassTerm("A", weight=1.0, t_hat_east=0.5, t_hat_north=0.5, distance_km=5.0)


def test_8a1_unit_03_zero_distance_cannot_carry_fabricated_direction():
    with pytest.raises(ValueError):
        DirectionalMassTerm("A", weight=1.0, t_hat_east=1.0, t_hat_north=0.0, distance_km=0.0)
    # exactly (0, 0) at zero distance is the only accepted structural form
    term = DirectionalMassTerm("A", weight=1.0, t_hat_east=0.0, t_hat_north=0.0, distance_km=0.0)
    assert term.distance_km == 0.0


# ---------------------------------------------------------------------------
# Clarity range guarantee (Part 6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("angle_deg", [0, 30, 45, 90, 135, 179, 200, 270, 315])
def test_8a1_clarity_01_valid_inputs_guarantee_clarity_in_unit_interval(angle_deg):
    rad = math.radians(angle_deg)
    terms = [
        DirectionalMassTerm("A", weight=3.0, t_hat_east=0.0, t_hat_north=1.0, distance_km=5.0),
        DirectionalMassTerm("B", weight=1.7, t_hat_east=math.sin(rad), t_hat_north=math.cos(rad), distance_km=5.0),
    ]
    result = compute_resultant_vector(terms)
    assert result.directional_clarity is not None
    assert 0.0 <= result.directional_clarity <= 1.0


# ---------------------------------------------------------------------------
# Calm-wind threshold consistency (Part 7)
# ---------------------------------------------------------------------------


def test_8a1_wind_01_below_existing_calm_threshold_bearing_none():
    magnitude = CALM_WIND_EPSILON_M_S * 0.9
    assert wind_to_bearing_from_components(u10=magnitude, v10=0.0) is None


def test_8a1_wind_02_above_threshold_correct_bearing():
    magnitude = CALM_WIND_EPSILON_M_S * 10.0
    assert wind_to_bearing_from_components(u10=magnitude, v10=0.0) == pytest.approx(90.0)


def test_8a1_wind_03_boundary_matches_compute_meteorological_alignment():
    u10, v10 = CALM_WIND_EPSILON_M_S, 0.0  # magnitude exactly == threshold
    alignment = compute_meteorological_alignment(t_hat_east=1.0, t_hat_north=0.0, wind=WindVector(u10=u10, v10=v10))
    bearing = wind_to_bearing_from_components(u10, v10)
    # compute_meteorological_alignment uses a strict "<" comparison, so
    # magnitude == threshold is NOT calm -- both functions must agree
    assert alignment.status == "DIRECTIONAL"
    assert bearing is not None
    assert bearing == pytest.approx(90.0)

    # just below the threshold, both must agree it IS calm
    u10_below = CALM_WIND_EPSILON_M_S * 0.999999
    alignment_below = compute_meteorological_alignment(t_hat_east=1.0, t_hat_north=0.0, wind=WindVector(u10=u10_below, v10=0.0))
    bearing_below = wind_to_bearing_from_components(u10_below, 0.0)
    assert alignment_below.status == "CALM_NEUTRAL"
    assert bearing_below is None


# ---------------------------------------------------------------------------
# Generic bearing hardening (Part 3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_8a1_bear_01_non_finite_generic_bearing_components_rejected(bad):
    with pytest.raises(ValueError):
        bearing_deg_from_components(bad, 1.0)
    with pytest.raises(ValueError):
        bearing_deg_from_components(1.0, bad)


def test_8a1_bear_02_tiny_nonzero_vector_not_suppressed_by_resultant_epsilon():
    # 1e-15 is far smaller than the retired absolute RESULTANT_MAGNITUDE_EPSILON
    # (1e-9) -- generic bearing must still resolve it, proving the two
    # concepts (generic zero-vector vs. weighted-resultant cancellation)
    # are genuinely decoupled.
    bearing = bearing_deg_from_components(1e-15, 0.0)
    assert bearing is not None
    assert bearing == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# Method readiness matrix correction (Part 9)
# ---------------------------------------------------------------------------


def test_8a1_matrix_01_method_a_incomplete_pending_weight_definition():
    method_a = DIRECTION_METHOD_CANDIDATES_8A1["GEOMETRIC_SOURCE_RESULTANT_TENDENCY"]
    assert method_a["directional_weight_status"] == "NOT_YET_SCIENTIFICALLY_DEFINED"
    assert method_a["complete_method_specification_status"] == "INCOMPLETE_PENDING_WEIGHT_DEFINITION"
    assert "scientifically_defined" not in method_a  # the old flat/ambiguous boolean is gone


def test_8a1_matrix_02_method_a_eligible_only_for_fit_development_methodology():
    method_a = DIRECTION_METHOD_CANDIDATES_8A1["GEOMETRIC_SOURCE_RESULTANT_TENDENCY"]
    assert method_a["eligible_for_8b_development"] is True
    assert method_a["data_ready"] is True
    assert method_a["temporally_safe"] is True
    assert method_a["geometry_definition_status"] == "SCIENTIFICALLY_DEFINED"
    assert method_a["aggregation_framework_status"] == "MATHEMATICALLY_DEFINED"
    reason = method_a["reason"].lower()
    # the four forbidden labels are required to appear together as ONE
    # negated list ("never X, Y, Z, or W") -- checked as a single
    # contiguous clause rather than via a sliding negation window, which
    # cannot reliably span a multi-item comma-separated list.
    negated_clause = (
        "never disease spread direction, validated spread direction, "
        "predicted transmission direction, or disease movement direction"
    )
    assert negated_clause in reason
    assert "fit_development only" in reason


# ---------------------------------------------------------------------------
# Terminology contract (Part 11) -- direct positive assertions, not text scans
# ---------------------------------------------------------------------------


def test_8a1_sem_01_no_output_field_aliases_wind_to_spread_direction():
    field_names = {f.name for f in dataclasses.fields(ResultantVectorResult)}
    assert not any("spread_direction" in name for name in field_names)

    registry = build_candidate_registry_7c()
    c0 = next(c for c in registry if c.family == C0_FAMILY)
    assert c0.anisotropy_mode is None
    assert c0.anisotropy_kappa is None

    assert "NOT_SPREAD_DIRECTION" in OVERALL_READINESS_STATUS_8A1


def test_8a1_sem_02_directional_clarity_not_exposed_as_confidence():
    field_names = {f.name for f in dataclasses.fields(ResultantVectorResult)}
    assert "directional_clarity" in field_names
    assert not any("confidence" in name for name in field_names)

    public_wind_names = {name for name in dir(raw_wind_module) if not name.startswith("_")}
    assert public_wind_names & {"wind_components_from_speed_direction", "wind_speed_from_components"}
    assert not any("spread_direction" in name.lower() or "confidence" in name.lower() for name in public_wind_names)


# ---------------------------------------------------------------------------
# Protocol hash versioning (Part 13)
# ---------------------------------------------------------------------------


def test_8a1_historical_hash_preserved_unchanged():
    assert direction_readiness_protocol_hash_8a() == HISTORICAL_CHECKPOINT_8A_INITIAL_READINESS_HASH


def test_8a1_hardened_hash_differs_and_excludes_timestamp():
    d1 = direction_readiness_protocol_dict_8a1()
    assert "generated_at" not in d1
    assert "timestamp" not in d1
    assert direction_readiness_protocol_hash_8a1() == direction_readiness_protocol_hash_8a1()
    assert direction_readiness_protocol_hash_8a1() != direction_readiness_protocol_hash_8a()
