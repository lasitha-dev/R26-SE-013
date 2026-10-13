"""Checkpoint 8B: frozen protocol identity for the C0-derived local
geometric relative-risk tendency field.

Binds the 8A.1 parent hash, the frozen C0 identity, the directional-
weight identity, and every 8B-specific semantic (cell-local scope,
zero-distance mass-coverage rule, source-count definitions, static t0
temporal scope, the future-target firewall, the circular-evaluation
prohibition, and the wind/environment exclusion) into one deterministic
hash that never binds a generation timestamp.
"""

from __future__ import annotations

import hashlib
import json

from .candidate_registry_7c import C0_FAMILY, build_candidate_registry_7c
from .direction_protocol_8a import (
    DIRECTION_EVALUATION_TRUTH_STATUS,
    HISTORICAL_CHECKPOINT_8A_INITIAL_READINESS_HASH,
    OVERALL_READINESS_STATUS_8A1,
)
from .direction_protocol_8a import direction_readiness_protocol_hash_8a1 as _parent_hash_fn
from .heldout_protocol_7d import assert_frozen_c0_model  # the same hard freeze gate 7D/7E already reuse

_registry = build_candidate_registry_7c()
_c0_spec = next(c for c in _registry if c.family == C0_FAMILY)

FROZEN_C0_SELECTED_CANDIDATE_ID = _c0_spec.candidate_id
FROZEN_7C_SPEC_HASH_8B = "ef3511d3527da6d85598846c0d828509ed07f134ac8d987c3d5702b507505a6d"

DIRECTIONAL_WEIGHT_IDENTITY_8B = "FROZEN_C0_PER_SOURCE_SCALAR_CONTRIBUTION"
DIRECTIONAL_WEIGHT_STATUS_8B = "DIRECTIONAL_WEIGHT_DERIVED_FROM_FROZEN_C0_NO_NEW_PARAMETER"
KERNEL_FAMILY_8B = _c0_spec.kernel_family  # EXPONENTIAL
KERNEL_SCALE_KM_8B = _c0_spec.kernel_scale_km  # 25.0

SOURCE_TO_CELL_ORIENTATION_8B = "SOURCE_TO_CELL_NEVER_CELL_TO_SOURCE"
FIELD_SCOPE_8B = "CELL_LOCAL_NO_GLOBAL_OR_ORIGIN_LEVEL_AGGREGATION"

ZERO_DISTANCE_MASS_COVERAGE_SEMANTICS_8B = (
    "ZERO_DISTANCE_SOURCE_SCALAR_C0_MASS_RETAINED_IN_TOTAL_SCALAR_C0_MASS_"
    "NEVER_DELETED_EXCLUDED_FROM_DIRECTIONAL_SUM_AND_CLARITY_NEVER_FABRICATED_DIRECTION_"
    "COVERAGE_STATUS_DETERMINED_STRUCTURALLY_NEVER_A_TUNED_THRESHOLD"
)

RESULTANT_CLARITY_SEMANTICS_8B = "INHERITED_UNCHANGED_FROM_DIRECTION_READINESS_PROTOCOL_HASH_8A1"

SOURCE_COUNT_DEFINITIONS_8B = (
    "n_total_eligible_sources=ALL_SOURCES_PASSED_IN;"
    "n_positive_c0_weight_sources=SOURCES_WITH_K_C0_D_GT_0_STRUCTURALLY_ALWAYS_EQUAL_TO_TOTAL_FOR_EXPONENTIAL_KERNEL;"
    "n_directionally_defined_sources=SOURCES_WITH_DISTANCE_KM_GT_0_SAME_MEANING_AS_8A1_N_TERMS_USABLE;"
    "n_zero_distance_undefined_direction_sources=COMPLEMENT_OF_DIRECTIONALLY_DEFINED;"
    "n_positive_weight_directionally_defined_sources=INTERSECTION"
)

STATIC_T0_TEMPORAL_SCOPE_8B = "T0_STATIC_NOT_DAY_SPECIFIC"

FUTURE_TARGET_FIREWALL_8B = (
    "COMPUTE_CELL_DIRECTION_TENDENCY_TAKES_ONLY_CELL_AND_ELIGIBLE_SOURCES;"
    "NO_TARGET_OR_FUTURE_OUTBREAK_PARAMETER_EXISTS_IN_ANY_PUBLIC_SIGNATURE"
)

CIRCULAR_EVALUATION_PROHIBITION_8B = (
    "NO_FUTURE_TARGET_DIRECTION_PERFORMANCE_METRIC_COMPUTED_IN_8B;"
    "SELECTING_THE_FIELD_AT_A_FUTURE_TARGET_CELL_AND_COMPARING_TO_SOURCE_TO_TARGET_BEARING_IS_TAUTOLOGICAL_"
    "FOR_A_SINGLE_SOURCE_AND_IS_NEVER_PERFORMED;"
    "DIRECTION_EVALUATION_TRUTH_REMAINS_NOT_YET_FROZEN"
)

WIND_ENVIRONMENT_EXCLUSION_8B = (
    "METHOD_A_DERIVED_FROM_FROZEN_C0_GEOMETRY_ONLY;"
    "NO_ERA5_RAINFALL_HUMIDITY_WATER_TERRAIN_HOST_SOURCE_STRENGTH_OR_ST_CLUSTER_INPUT;"
    "METHOD_B_WIND_INFORMED_HAZARD_RESULTANT_REMAINS_SEPARATELY_BLOCKED_BY_INCOMPLETE_7C_WIND_COVERAGE"
)

OUTPUT_TERMINOLOGY_8B = "C0_DERIVED_LOCAL_GEOMETRIC_RELATIVE_RISK_TENDENCY"
DIRECTION_EVALUATION_TRUTH_STATUS_8B = DIRECTION_EVALUATION_TRUTH_STATUS  # unresolved, unchanged from 8A

OVERALL_CLASSIFICATION_8B = "C0_DERIVED_LOCAL_GEOMETRIC_RISK_TENDENCY_FIELD_READY_NOT_PREDICTIVE_SPREAD_DIRECTION"


def parent_direction_readiness_protocol_hash_8a1() -> str:
    return _parent_hash_fn()


def verify_8a1_preflight() -> dict:
    """Part 0: loads the LIVE 8A.1 protocol dict and asserts every
    semantic this checkpoint depends on is actually bound in it -- never
    trusts the hash string alone. Raises `AssertionError` (fail closed)
    if any expected key is missing."""
    from .direction_protocol_8a import direction_readiness_protocol_dict_8a1

    live_hash = _parent_hash_fn()
    if live_hash != "8aa69a68f27980134caa3cb1c5c96f5b66ab1e41274bc9def38a9aa5a627869e":
        raise AssertionError(
            f"direction_readiness_protocol_hash_8a1() = {live_hash!r} does not match the expected hardened "
            "Checkpoint 8A.1 hash -- 8B must not proceed against a drifted parent protocol"
        )

    live_dict = direction_readiness_protocol_dict_8a1()
    required_keys = {
        "bearing_convention", "generic_bearing_zero_semantics", "resultant_relative_cancellation_epsilon",
        "unit_vector_norm_tolerance", "clarity_range_clamp_tolerance", "non_finite_rejection_semantics",
        "zero_distance_semantics", "clarity_range_invariant_semantics", "wind_calm_epsilon_m_s",
        "wind_to_from_conversion", "source_to_cell_orientation", "temporal_firewall",
        "direction_method_candidates_8a1", "direction_weight_status", "direction_evaluation_truth_status",
        "overall_readiness_status",
    }
    missing = required_keys - set(live_dict.keys())
    if missing:
        raise AssertionError(
            f"direction_readiness_protocol_hash_8a1() hash matched, but the live protocol dict is missing "
            f"expected keys {sorted(missing)} -- the hash existing is not proof the semantics are actually "
            "bound; 8B must not silently continue"
        )
    if "NOT_SPREAD_DIRECTION" not in live_dict["overall_readiness_status"]:
        raise AssertionError("8A.1 overall_readiness_status no longer contains NOT_SPREAD_DIRECTION -- 8B must not proceed")
    return live_dict


def assert_frozen_c0_model_8b(loaded_spec: dict) -> None:
    """Reuses the SAME hard freeze gate 7D/7E already call -- no
    reimplementation."""
    assert_frozen_c0_model(loaded_spec)


def direction_method_protocol_dict_8b() -> dict:
    """Every field bound into the frozen 8B protocol hash. Deliberately
    excludes any timestamp."""
    return {
        "parent_direction_readiness_protocol_hash_8a1": parent_direction_readiness_protocol_hash_8a1(),
        "historical_checkpoint_8a_initial_readiness_hash": HISTORICAL_CHECKPOINT_8A_INITIAL_READINESS_HASH,
        "frozen_c0_selected_candidate_id": FROZEN_C0_SELECTED_CANDIDATE_ID,
        "frozen_7c_spec_hash": FROZEN_7C_SPEC_HASH_8B,
        "directional_weight_identity": DIRECTIONAL_WEIGHT_IDENTITY_8B,
        "directional_weight_status": DIRECTIONAL_WEIGHT_STATUS_8B,
        "kernel_family": KERNEL_FAMILY_8B,
        "kernel_scale_km": KERNEL_SCALE_KM_8B,
        "source_to_cell_orientation": SOURCE_TO_CELL_ORIENTATION_8B,
        "field_scope": FIELD_SCOPE_8B,
        "zero_distance_mass_coverage_semantics": ZERO_DISTANCE_MASS_COVERAGE_SEMANTICS_8B,
        "resultant_clarity_semantics": RESULTANT_CLARITY_SEMANTICS_8B,
        "source_count_definitions": SOURCE_COUNT_DEFINITIONS_8B,
        "static_t0_temporal_scope": STATIC_T0_TEMPORAL_SCOPE_8B,
        "future_target_firewall": FUTURE_TARGET_FIREWALL_8B,
        "circular_evaluation_prohibition": CIRCULAR_EVALUATION_PROHIBITION_8B,
        "wind_environment_exclusion": WIND_ENVIRONMENT_EXCLUSION_8B,
        "direction_evaluation_truth_status": DIRECTION_EVALUATION_TRUTH_STATUS_8B,
        "output_terminology": OUTPUT_TERMINOLOGY_8B,
        "overall_classification": OVERALL_CLASSIFICATION_8B,
    }


def direction_method_protocol_hash_8b() -> str:
    canonical = json.dumps(direction_method_protocol_dict_8b(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Checkpoint 8B.2 -- analytical negative-gradient equivalence, sign/semantic
# hardening, method-identity binding. All symbols below are NEW; nothing
# above this line was modified, and no numerical vector result changes.
# =============================================================================

from ..direction.c0_geometric_tendency import (  # noqa: E402
    DIRECTION_SEMANTICS_8B as HISTORICAL_CHECKPOINT_8B_OUTPUT_TERMINOLOGY,
)
from ..direction.c0_geometric_tendency import (  # noqa: E402
    METHOD_ID_8B,
    METHOD_VERSION_8B as HISTORICAL_METHOD_VERSION_STRING,
)

HISTORICAL_CHECKPOINT_8B_PROTOCOL_HASH = "9d111741d303d1dcf73c2a624b99c3fa7c3aaa2020d52d3254d5d744e963f32d"
CHECKPOINT_8B1_ROLE = "ARTIFACT_PATH_AND_PROVENANCE_REPAIR"  # Checkpoint 8B.1 never redefined the method version string

METHOD_VERSION_8B2 = "8B.2"

# Part 3: the active, sign-explicit terminology. The historical field VALUE
# actually persisted by `c0_geometric_tendency.CellDirectionTendency8B.direction_semantics`
# is UNCHANGED (still `HISTORICAL_CHECKPOINT_8B_OUTPUT_TERMINOLOGY`) -- this
# is documentation/protocol-identity only, describing what the SAME
# unchanged numerical quantity should be CALLED going forward, never a
# retroactive rewrite of already-persisted artifacts.
ACTIVE_OUTPUT_SEMANTICS_8B2 = "C0_DERIVED_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY"

# Part 1: the analytical identity, proven (not merely asserted) in
# `tests/test_checkpoint_8b2_negative_gradient.py` (8B2-GRAD-01..08) against
# the real `source_to_cell_unit_vector` orientation, the real frozen
# EXPONENTIAL kernel derivative, and the real `compute_cell_direction_tendency`
# output, cross-checked by finite-difference on real WGS84 geodesics (never
# reused/rerun over the 579-origin/560,853-cell real corpus).
NEGATIVE_GRADIENT_IDENTITY_8B2 = (
    "FOR_A_SINGLE_SOURCE_J_AND_KERNEL_SCALE_LAMBDA_25KM:"
    "GRAD_X_D_J(X)_EQUALS_T_HAT_J(X)_THE_SOURCE_TO_CELL_UNIT_TANGENT_"
    "(STANDARD_RESULT_FOR_GRAD_OF_A_DISTANCE_FUNCTION_FROM_A_FIXED_POINT_"
    "ALMOST_EVERYWHERE_EXCEPT_AT_D=0_WHERE_D_IS_NOT_DIFFERENTIABLE_AND_"
    "EXCEPT_AT_THE_GEODESIC_CUT_LOCUS_WHICH_IS_NEVER_REACHED_AT_THE_"
    "FROZEN_25KM_KERNEL_SCALE_ON_EARTH_~20000KM_ANTIPODAL_CUT_LOCUS_DISTANCE);"
    "THEREFORE_GRAD_EXP(-D_J/LAMBDA)_EQUALS_(-1/LAMBDA)*EXP(-D_J/LAMBDA)*T_HAT_J_BY_CHAIN_RULE_"
    "MATCHING_THE_FROZEN_EXPONENTIAL_KERNEL_DERIVATIVE_D_K/D_D=-(1/LAMBDA)*K;"
    "SUMMING_OVER_ALL_ELIGIBLE_SOURCES:_GRAD_C0(X)_EQUALS_(-1/LAMBDA)*SUM_J_W_J*T_HAT_J_EQUALS_(-1/LAMBDA)*V(X);"
    "THEREFORE_V(X)_EQUALS_MINUS_LAMBDA_TIMES_GRAD_C0(X);"
    "LOCAL_EAST_NORTH_COMPONENTS_ARE_THE_STANDARD_LOCAL_TANGENT_PLANE_"
    "REPRESENTATION_OF_THE_GEODESIC_GRADIENT_ON_THE_WGS84_ELLIPSOID;"
    "FINITE_FLOATING_POINT_GEODESIC_NUMERICS_MEAN_ANY_FINITE_DIFFERENCE_"
    "CROSS_CHECK_AGREES_ONLY_WITHIN_A_DOCUMENTED_NUMERICAL_TOLERANCE_NEVER_BIT_EXACT;"
    "A_FOURTH_EXCEPTION_(EMPIRICALLY_CONFIRMED_DURING_8B.2_TEST_DEVELOPMENT):_"
    "SOURCE_TO_CELL_UNIT_VECTOR_USES_THE_GEODESIC_DEPARTURE_AZIMUTH_MEASURED_AT_THE_SOURCE_"
    "(THE_CODEBASE'S_EXISTING_FROZEN_CONVENTION_SINCE_CHECKPOINT_5_USED_THROUGHOUT_7B-8B)_"
    "RATHER_THAN_THE_TRUE_LOCAL_GRADIENT_TANGENT_AT_THE_CELL_(THE_ARRIVAL_AZIMUTH);_"
    "ON_THE_WGS84_ELLIPSOID_THESE_DIFFER_BY_THE_GEODESIC'S_MERIDIAN_CONVERGENCE_ANGLE_OVER_"
    "THE_SOURCE_TO_CELL_PATH_(CONFIRMED_EMPIRICALLY_~0.0012_DEGREES_FOR_A_3KM_GEODESIC);_"
    "THIS_MAKES_THE_IDENTITY_APPROXIMATE_RATHER_THAN_EXACT_AT_THE_SUB-PERCENT_LEVEL_FOR_"
    "SOURCE_DISTANCES_UP_TO_TENS_OF_KM_AT_THE_FROZEN_25KM_KERNEL_SCALE_-_SMALL_AND_NEVER_"
    "HIDDEN_NEVER_CLAIMED_AS_EXACT_TO_MACHINE_PRECISION"
)

GRADIENT_SIGN_STATEMENT_8B2 = (
    "V_EQUALS_NEGATIVE_LAMBDA_GRAD_C0_POINTS_DOWN_THE_C0_SCALAR_GRADIENT_"
    "I.E._IN_THE_DIRECTION_OF_DECREASING_C0_AWAY_FROM_SOURCES_FOR_AN_ISOLATED_SOURCE;"
    "POSITIVE_GRAD_C0_POINTS_TOWARD_INCREASING_C0_TOWARD_SOURCES;"
    "THE_TWO_ARE_EXACTLY_180_DEGREES_APART_WHENEVER_THE_GRADIENT_MAGNITUDE_IS_NONZERO;"
    "V_IS_NEVER_DESCRIBED_AS_DIRECTION_OF_INCREASING_RISK_RISK_GRADIENT_DIRECTION_"
    "DIRECTION_TOWARD_HIGHER_RELATIVE_RISK_PREDICTED_DISEASE_SPREAD_DIRECTION_OR_TRANSMISSION_DIRECTION;"
    "FOR_MULTIPLE_SOURCES_V_IS_THE_NEGATIVE_LOCAL_GRADIENT_OF_THE_AGGREGATE_C0_FIELD_NOT_A_"
    "CLAIM_THAT_EVERY_INDIVIDUAL_SOURCE_CONTRIBUTION_POINTS_AWAY_FROM_EVERY_SOURCE_SIMULTANEOUSLY_"
    "AT_EVERY_CELL_ALTHOUGH_FOR_THIS_KERNEL_EACH_PER_SOURCE_TERM_INDIVIDUALLY_DOES"
)

# Part 4: reconciliation of Checkpoint 8A's HAZARD_SURFACE_GRADIENT_DIRECTION
# (Method C, DIRECTION_METHOD_NOT_YET_SCIENTIFICALLY_IDENTIFIABLE) with
# Checkpoint 8B's Method A.
METHOD_C_RECONCILIATION_8B2 = (
    "CHECKPOINT_8A_METHOD_C_(HAZARD_SURFACE_GRADIENT_DIRECTION)_ASSESSED_WHETHER_A_"
    "SEPARATELY_INVENTED_OR_ESTIMATED_GENERIC_GRADIENT_METHOD_ALREADY_EXISTED_IN_THE_"
    "CODEBASE_AT_THAT_TIME_-_IT_DID_NOT_(NOT_SCIENTIFICALLY_DEFINED_NOT_IMPLEMENTED);"
    "CHECKPOINT_8B_DID_NOT_FIT_TUNE_OR_INVENT_A_NEW_GRADIENT_METHOD_TO_CLOSE_THAT_GAP;"
    "CHECKPOINT_8B_INSTEAD_FROZE_METHOD_A'S_DIRECTIONAL_WEIGHT_AS_THE_EXACT_C0_PER_SOURCE_"
    "KERNEL_CONTRIBUTION_FOR_INDEPENDENT_GEOMETRIC_REASONS_(PART_2_OF_THE_8B_CHECKPOINT);"
    "CHECKPOINT_8B.2_DISCOVERED_ANALYTICALLY_(NOT_BY_DESIGN_OR_FITTING)_THAT_THE_RESULTING_"
    "SOURCE_TO_CELL_WEIGHTED_RESULTANT_IS_MATHEMATICALLY_EQUAL_TO_THE_NEGATIVE_GRADIENT_OF_"
    "THAT_SPECIFIC_ALREADY_FROZEN_C0_SCALAR_FIELD_-_A_LATER_ANALYTICAL_CONSEQUENCE_DISCOVERED_"
    "AFTER_THE_FACT_NEVER_A_CLAIM_THAT_8A_WAS_WRONG_OR_THAT_A_HAZARD_SURFACE_GRADIENT_METHOD_"
    "WAS_SECRETLY_ALREADY_IMPLEMENTED_IN_8A;"
    "POSITIVE_GRAD(C0)_AND_THE_CURRENT_8B_VECTOR_V_POINT_IN_OPPOSITE_DIRECTIONS"
)

# Part 6: clarity's analytical relation -- documented as an IDENTITY that
# holds under specific conditions, never as a new score and never silently
# generalized to partial-coverage/zero-distance cells.
CLARITY_ANALYTICAL_RELATION_8B2 = (
    "UNDER_COMPLETE_DIRECTIONAL_MASS_COVERAGE_AND_AWAY_FROM_D=0:_"
    "DIRECTIONAL_CLARITY_EQUALS_NORM(V)/SUM_J_W_J_EQUALS_NORM(V)/C0_"
    "EQUALS_LAMBDA*NORM(GRAD_C0)/C0_EQUALS_LAMBDA*NORM(GRAD_LOG_C0)_WHERE_C0>0;"
    "THIS_IS_A_NORMALIZED_LOCAL_SLOPE_MAGNITUDE_AN_AGREEMENT_QUANTITY_NEVER_"
    "CONFIDENCE_PROBABILITY_ACCURACY_OR_CERTAINTY;"
    "UNDER_PARTIAL_DIRECTIONAL_MASS_COVERAGE_(ZERO_DISTANCE_SOURCES_PRESENT)_"
    "THE_SAME_LOG_GRADIENT_IDENTITY_DOES_NOT_HOLD_WITH_THE_SAME_DENOMINATOR_"
    "BECAUSE_DIRECTIONALLY_DEFINED_MASS_EXCLUDES_THE_ZERO_DISTANCE_TERM_WHILE_"
    "C0_INCLUDES_IT_-_NEVER_CLAIMED_IN_THAT_CASE"
)

DIRECTIONAL_INPUT_COVERAGE_SEMANTICS_8B2 = "INHERITED_UNCHANGED_FROM_ZERO_DISTANCE_MASS_COVERAGE_SEMANTICS_8B"

_registry_8b2 = build_candidate_registry_7c()
_c0_spec_8b2 = next(c for c in _registry_8b2 if c.family == C0_FAMILY)


def direction_method_protocol_dict_8b2() -> dict:
    """Every field bound into the hardened 8B.2 protocol hash. Binds
    `method_id`/`method_version` explicitly -- a reproducibility gap the
    historical `direction_method_protocol_dict_8b()` never closed (and is
    NOT retroactively changed to close). Deliberately excludes any
    timestamp."""
    return {
        "historical_checkpoint_8b_protocol_hash": HISTORICAL_CHECKPOINT_8B_PROTOCOL_HASH,
        "parent_direction_readiness_protocol_hash_8a1": parent_direction_readiness_protocol_hash_8a1(),
        "historical_checkpoint_8a_initial_readiness_hash": HISTORICAL_CHECKPOINT_8A_INITIAL_READINESS_HASH,
        "method_id": METHOD_ID_8B,
        "method_version": METHOD_VERSION_8B2,
        "historical_method_version_string": HISTORICAL_METHOD_VERSION_STRING,
        "frozen_c0_selected_candidate_id": _c0_spec_8b2.candidate_id,
        "frozen_7c_spec_hash": FROZEN_7C_SPEC_HASH_8B,
        "kernel_family": _c0_spec_8b2.kernel_family,
        "kernel_scale_km": _c0_spec_8b2.kernel_scale_km,
        "source_to_cell_orientation": SOURCE_TO_CELL_ORIENTATION_8B,
        "historical_output_semantics": HISTORICAL_CHECKPOINT_8B_OUTPUT_TERMINOLOGY,
        "active_output_semantics": ACTIVE_OUTPUT_SEMANTICS_8B2,
        "negative_gradient_identity": NEGATIVE_GRADIENT_IDENTITY_8B2,
        "gradient_sign_statement": GRADIENT_SIGN_STATEMENT_8B2,
        "method_c_reconciliation": METHOD_C_RECONCILIATION_8B2,
        "zero_distance_mass_coverage_semantics": ZERO_DISTANCE_MASS_COVERAGE_SEMANTICS_8B,
        "clarity_analytical_relation": CLARITY_ANALYTICAL_RELATION_8B2,
        "directional_input_coverage_semantics": DIRECTIONAL_INPUT_COVERAGE_SEMANTICS_8B2,
        "static_t0_temporal_scope": STATIC_T0_TEMPORAL_SCOPE_8B,
        "future_target_firewall": FUTURE_TARGET_FIREWALL_8B,
        "direction_evaluation_truth_status": DIRECTION_EVALUATION_TRUTH_STATUS_8B,
        "overall_classification": OVERALL_CLASSIFICATION_8B,
    }


def direction_method_protocol_hash_8b2() -> str:
    canonical = json.dumps(direction_method_protocol_dict_8b2(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Checkpoint 8B.3 -- cell-local geodesic tangent-frame correction, exact C0
# negative-gradient consistency, active method/version identity. All symbols
# below are NEW; nothing above this line was modified, and no historical 8B/
# 8B.2 numerical artifact changes.
# =============================================================================

from ..geospatial.distance import CELL_LOCAL_EAST_NORTH_TANGENT_FRAME  # noqa: E402
from ..direction.c0_cell_local_tendency_8b3 import (  # noqa: E402
    ACTIVE_COORDINATE_FRAME_8B3,
    ACTIVE_OUTPUT_SEMANTICS_8B3,
    DIRECTION_EVALUATION_TRUTH_STATUS_8B3,
    METHOD_ID_8B3,
    METHOD_VERSION_8B3,
    PREDICTIVE_SPREAD_DIRECTION_STATUS_8B3,
    TEMPORAL_SCOPE_8B3,
)
from .direction_readiness_8a import (  # noqa: E402
    RESULTANT_RELATIVE_CANCELLATION_EPSILON,
    UNIT_VECTOR_NORM_TOLERANCE,
)

HISTORICAL_CHECKPOINT_8B2_PROTOCOL_HASH = "d8dd12da100f3446f29967dcd221d25112669703ab3d201333a17a07ad89f906"

# Part 14: honest reclassification of 8B.2 -- never deleted, never called
# fraudulent. The historical numerical field itself is re-described
# precisely; no historical artifact/hash changes as a result of this
# reclassification.
CHECKPOINT_8B2_STATUS_CORRECTION = "CHECKPOINT_8B2_ANALYTICAL_IDENTITY_OVERSTATED_DUE_TO_SOURCE_FRAME_VS_CELL_FRAME_MISMATCH"
HISTORICAL_8B_FIELD_DESCRIPTION = "SOURCE_DEPARTURE_FRAME_GEOMETRIC_RESULTANT"
CHECKPOINT_8B2_CORRECTION_NOTE = (
    "THE_OBSERVED_MERIDIAN_CONVERGENCE_DISCREPANCY_8B.2_FOUND_EMPIRICALLY_REVEALED_THAT_THE_"
    "SOURCE_DEPARTURE_FRAME_REPRESENTATION_(HISTORICAL_8B/8B.2)_WAS_ONLY_APPROXIMATELY_ALIGNED_"
    "WITH_THE_TRUE_CELL_LOCAL_NEGATIVE_GRADIENT_OF_C0_NOT_EXACTLY_-_8B.2'S_CLAIMED_IDENTITY_"
    "V=-LAMBDA*GRAD(C0)_WAS_THEREFORE_AN_APPROXIMATE_STATEMENT_PRESENTED_WITHOUT_THAT_QUALIFICATION_"
    "MADE_EXPLICIT_ENOUGH;_8B.3_CORRECTS_THE_FRAME_EXPLICITLY_SO_THE_IDENTITY_NOW_HOLDS_TO_"
    "CONVERGENT_NUMERICAL_PRECISION;_THE_HISTORICAL_8B/8B.2_NUMERICAL_FIELD_ITSELF_WAS_NEVER_"
    "WRONG_ON_ITS_OWN_TERMS_(A_REAL_SOURCE_DEPARTURE_FRAME_WEIGHTED_RESULTANT)_AND_WAS_NEVER_"
    "CALLED_A_PREDICTIVE_SPREAD_DIRECTION_IN_EITHER_CHECKPOINT"
)

# Part 3: the CORRECTED analytical identity -- V_CELL(x) = -lambda*grad(C0(x))
# holds to convergent numerical precision (proven in
# tests/test_checkpoint_8b3_cell_local_correction.py, 8B3-GRAD-01..05),
# unlike the historical source-frame field's approximate version.
NEGATIVE_GRADIENT_IDENTITY_8B3 = (
    "FOR_EACH_SOURCE_J_AWAY_FROM_D=0_AND_THE_GEODESIC_CUT_LOCUS:_"
    "GRAD_X_D_J(X)_EQUALS_T_HAT_CELL_J(X)_THE_SOURCE_TO_CELL_GEODESIC_TANGENT_EXPRESSED_"
    "AT_THE_CELL_(THE_ARRIVAL_AZIMUTH_(AZ21+180)_MOD_360_NOT_THE_DEPARTURE_AZIMUTH_AZ12);"
    "THEREFORE_GRAD_C0(X)_EQUALS_(-1/LAMBDA)*SUM_J_W_J*T_HAT_CELL_J(X)_EQUALS_(-1/LAMBDA)*V_CELL(X);"
    "V_CELL(X)_EQUALS_MINUS_LAMBDA_TIMES_GRAD_C0(X)_TO_CONVERGENT_NUMERICAL_GEODESIC_PRECISION_"
    "(NOT_MERELY_APPROXIMATE_LIKE_THE_HISTORICAL_SOURCE_DEPARTURE_FRAME_FIELD)"
)

ARRIVAL_BEARING_FORMULA_8B3 = "CELL_ARRIVAL_FORWARD_AZIMUTH_DEG_EQUALS_(AZ21_PLUS_180)_MOD_360_WHERE_AZ21_IS_PYPROJ_GEOD_INV_BACK_AZIMUTH"
GEODESIC_CONVENTION_IDENTITY_8B3 = "PYPROJ_GEOD_ELLPS_WGS84_INV_AZ12_DEPARTURE_AT_POINT1_AZ21_ARRIVAL_BEARING_BACK_TOWARD_POINT1_AT_POINT2"
CELL_ARRIVAL_TANGENT_DEFINITION_8B3 = "T_CELL_EAST_NORTH_EQUALS_SIN_COS_OF_CELL_ARRIVAL_FORWARD_AZIMUTH_DEG_ZERO_AT_EXACT_ZERO_DISTANCE"
ZERO_DISTANCE_SEMANTICS_8B3 = ZERO_DISTANCE_MASS_COVERAGE_SEMANTICS_8B  # unchanged rule, cell-local frame only affects nonzero-distance terms

CLARITY_ANALYTICAL_RELATION_8B3 = (
    "UNDER_COMPLETE_DIRECTIONAL_MASS_COVERAGE_AND_AWAY_FROM_D=0:_"
    "DIRECTIONAL_CLARITY_EQUALS_NORM(V_CELL)/C0_EQUALS_LAMBDA*NORM(GRAD_C0)/C0_EQUALS_LAMBDA*NORM(GRAD_LOG_C0)_"
    "NOW_A_LEGITIMATE_CELL_LOCAL_ANALYTICAL_IDENTITY_NEVER_CLAIMED_FOR_THE_HISTORICAL_SOURCE_FRAME_FIELD;_"
    "NEVER_CONFIDENCE_PROBABILITY_ACCURACY_OR_CERTAINTY"
)

_registry_8b3 = build_candidate_registry_7c()
_c0_spec_8b3 = next(c for c in _registry_8b3 if c.family == C0_FAMILY)


def direction_method_protocol_dict_8b3() -> dict:
    """Every field bound into the hardened, ACTIVE 8B.3 protocol hash.
    Deliberately excludes any timestamp."""
    return {
        "parent_direction_readiness_protocol_hash_8a1": parent_direction_readiness_protocol_hash_8a1(),
        "historical_checkpoint_8b_protocol_hash": HISTORICAL_CHECKPOINT_8B_PROTOCOL_HASH,
        "historical_checkpoint_8b2_protocol_hash": HISTORICAL_CHECKPOINT_8B2_PROTOCOL_HASH,
        "checkpoint_8b2_status_correction": CHECKPOINT_8B2_STATUS_CORRECTION,
        "historical_8b_field_description": HISTORICAL_8B_FIELD_DESCRIPTION,
        "frozen_c0_selected_candidate_id": _c0_spec_8b3.candidate_id,
        "frozen_7c_spec_hash": FROZEN_7C_SPEC_HASH_8B,
        "kernel_family": _c0_spec_8b3.kernel_family,
        "kernel_scale_km": _c0_spec_8b3.kernel_scale_km,
        "method_id": METHOD_ID_8B3,
        "method_version": METHOD_VERSION_8B3,
        "active_output_semantics": ACTIVE_OUTPUT_SEMANTICS_8B3,
        "active_coordinate_frame": ACTIVE_COORDINATE_FRAME_8B3,
        "geodesic_convention_identity": GEODESIC_CONVENTION_IDENTITY_8B3,
        "cell_arrival_tangent_definition": CELL_ARRIVAL_TANGENT_DEFINITION_8B3,
        "arrival_bearing_formula": ARRIVAL_BEARING_FORMULA_8B3,
        "zero_distance_semantics": ZERO_DISTANCE_SEMANTICS_8B3,
        "unit_vector_norm_tolerance": UNIT_VECTOR_NORM_TOLERANCE,
        "resultant_relative_cancellation_epsilon": RESULTANT_RELATIVE_CANCELLATION_EPSILON,
        "negative_gradient_identity": NEGATIVE_GRADIENT_IDENTITY_8B3,
        "clarity_analytical_relation": CLARITY_ANALYTICAL_RELATION_8B3,
        "directional_input_coverage_semantics": DIRECTIONAL_INPUT_COVERAGE_SEMANTICS_8B2,
        "static_t0_temporal_scope": TEMPORAL_SCOPE_8B3,
        "future_target_firewall": FUTURE_TARGET_FIREWALL_8B,
        "direction_evaluation_truth_status": DIRECTION_EVALUATION_TRUTH_STATUS_8B3,
        "predictive_spread_direction_status": PREDICTIVE_SPREAD_DIRECTION_STATUS_8B3,
    }


def direction_method_protocol_hash_8b3() -> str:
    canonical = json.dumps(direction_method_protocol_dict_8b3(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
