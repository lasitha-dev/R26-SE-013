"""Checkpoint 8A / 8A.1: frozen direction-readiness protocol identity.

This module defines and hashes the SEMANTIC agreements Checkpoint 8A
freezes -- bearing convention, source->cell orientation, wind FROM/TO
semantics, zero-resultant/zero-distance handling, directional-clarity
semantics, the temporal firewall, the (audited-only, not-selected)
candidate direction-method definitions, and the evaluation-truth
readiness status. It freezes NO predictive parameter, NO direction
model, and NO score. `direction_readiness_protocol_hash_8a()` never
binds a generation timestamp -- only genuinely frozen semantic content.

**Checkpoint 8A.1**: Parts 2-9 changed genuinely load-bearing readiness
semantics (scale-invariant resultant math, non-finite rejection,
unit-vector validation, calm-wind threshold consistency, and a
corrected Method-A readiness classification). The ORIGINAL Checkpoint
8A symbols (`direction_readiness_protocol_dict_8a`,
`direction_readiness_protocol_hash_8a`, `DIRECTION_METHOD_CANDIDATES`)
are left completely UNTOUCHED below, so
`direction_readiness_protocol_hash_8a()` continues to return the exact
same historical value it always did
(`HISTORICAL_CHECKPOINT_8A_INITIAL_READINESS_HASH`) -- never silently
reused to mean something new. The hardened semantics live in NEW,
separately named `..._8a1` symbols instead.
"""

from __future__ import annotations

import hashlib
import json

BEARING_CONVENTION = "CLOCKWISE_FROM_NORTH_DEGREES_0_TO_360_EXCLUSIVE"
SOURCE_TO_CELL_ORIENTATION = "SOURCE_TO_CELL_NEVER_CELL_TO_SOURCE"
WIND_COMPONENT_CONVENTION = "U10_EASTWARD_V10_NORTHWARD_METEOROLOGICAL"
WIND_NAMED_DIRECTION_SENSE = "FROM_DIRECTION_COMPASS_BEARING_WIND_BLOWS_FROM"
WIND_TO_FROM_CONVERSION = "FROM_BEARING_EQUALS_TO_BEARING_PLUS_180_MOD_360_APPLIED_EXACTLY_ONCE"

ZERO_DISTANCE_SEMANTICS = "UNDEFINED_DIRECTION_EXCLUDED_FROM_RESULTANT_AND_CLARITY_DENOMINATOR_NEVER_FABRICATED"
ZERO_RESULTANT_SEMANTICS = "BEARING_NONE_WHEN_MAGNITUDE_AT_OR_BELOW_EPSILON_NEVER_ZERO_DEGREES_AS_FALLBACK"
BEARING_ZERO_IS_VALID_NORTH = True

DIRECTIONAL_CLARITY_SEMANTICS = (
    "RESULTANT_MAGNITUDE_OVER_SUM_OF_USABLE_DIRECTIONAL_WEIGHTS_RANGE_0_TO_1_"
    "AGREEMENT_MEASURE_NEVER_CONFIDENCE_PROBABILITY_OR_ACCURACY"
)

TEMPORAL_FIREWALL = (
    "PRIMARY_DIRECTION_INPUT_MAY_USE_ONLY_PRE_T0_WEATHER_STATE_HISTORY;"
    "FUTURE_TARGET_POSITION_FORBIDDEN_AS_INPUT;"
    "REALIZED_D1_D7_WEATHER_FORBIDDEN_AS_PRIMARY_INPUT_ORACLE_SENSITIVITY_ONLY;"
    "FUTURE_OUTBREAKS_MAY_ONLY_BE_EVALUATION_TRUTH_IN_A_LATER_CHECKPOINT"
)

FROZEN_C0_DIRECTIONAL_STATUS = "FROZEN_C0_HAS_NO_INTRINSIC_DIRECTIONAL_TRANSMISSION_PARAMETER"

# Part 10: audited-only candidate direction-method definitions. None of
# these is selected, fit, tuned, or scored in Checkpoint 8A.
DIRECTION_METHOD_CANDIDATES = {
    "GEOMETRIC_SOURCE_RESULTANT_TENDENCY": {
        "scientifically_defined": True,
        "implemented": False,
        "tested": True,
        "data_ready": True,
        "temporally_safe": True,
        "eligible_for_8b_development": True,
        "reason": (
            "Source->cell unit-vector geometry (t_hat_east/t_hat_north, "
            "services.geospatial.distance.source_to_cell_unit_vector) is real, "
            "tested, and available for every eligible source at every "
            "already-frozen forecast origin with no additional data dependency. "
            "The resultant-vector aggregation (compute_resultant_vector, "
            "direction_readiness_8a.py) is a new 8A readiness primitive, not "
            "previously implemented, and uses NO scientifically selected weight "
            "yet -- w_j_i is undefined (DIRECTION_WEIGHT_NOT_YET_SCIENTIFICALLY_DEFINED). "
            "This must be labelled a geometric/relative-risk tendency, never "
            "disease spread direction, until/unless a weight is scientifically "
            "justified in 8B."
        ),
    },
    "WIND_INFORMED_HAZARD_RESULTANT": {
        "scientifically_defined": True,
        "implemented": False,
        "tested": True,
        "data_ready": False,
        "temporally_safe": True,
        "eligible_for_8b_development": False,
        "reason": (
            "services.hazard.anisotropy.compute_meteorological_alignment already "
            "computes a real, tested, source-specific alignment "
            "(t_hat . wind_unit) fed the SAME per-source geometry, applied BEFORE "
            "summation (services.model_development.wind_scoring_7c.score_origin_candidates_7c). "
            "However wind acquisition (services.model_development.wind_readiness_7c.resolve_origin_wind) "
            "is ORIGIN-level (one AOI-center wind vector shared by all sources at "
            "an origin), not source-specific, and the real Checkpoint 7C.1 "
            "579-origin development run found REAL wind for only 192/277 "
            "(~69.3%) of reachable origins -- 85/277 (~30.7%) "
            "WEATHER_INPUT_UNAVAILABLE (see ENVIRONMENTAL_WIND_MODEL_DEVELOPMENT_PROTOCOL.md "
            "section 11). All 8 CW wind candidates were "
            "PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE in 7C -- this "
            "is a real, unresolved input-coverage gap, not a resolved readiness "
            "state. AUXILIARY_DIRECTION_METHOD_BLOCKED_BY_INPUT_COVERAGE until a "
            "protocol-justified missing-wind handling rule is frozen."
        ),
    },
    "HAZARD_SURFACE_GRADIENT_DIRECTION": {
        "scientifically_defined": False,
        "implemented": False,
        "tested": False,
        "data_ready": False,
        "temporally_safe": False,
        "eligible_for_8b_development": False,
        "reason": (
            "No existing mathematically coherent gradient-direction "
            "implementation or protocol exists anywhere in this codebase "
            "(services/hazard, services/geospatial, or any *.md protocol). "
            "Checkpoint 8A explicitly does not invent a new gradient method. "
            "DIRECTION_METHOD_NOT_YET_SCIENTIFICALLY_IDENTIFIABLE for this option."
        ),
    },
}

DIRECTION_WEIGHT_STATUS = "DIRECTION_WEIGHT_NOT_YET_SCIENTIFICALLY_DEFINED"
DIRECTION_EVALUATION_TRUTH_STATUS = "DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN"

OVERALL_READINESS_STATUS = "GEOMETRIC_DIRECTION_ONLY_READY_NOT_SPREAD_DIRECTION"


def direction_readiness_protocol_dict_8a() -> dict:
    """Every field bound into the frozen protocol hash. Deliberately
    excludes any timestamp."""
    return {
        "bearing_convention": BEARING_CONVENTION,
        "source_to_cell_orientation": SOURCE_TO_CELL_ORIENTATION,
        "wind_component_convention": WIND_COMPONENT_CONVENTION,
        "wind_named_direction_sense": WIND_NAMED_DIRECTION_SENSE,
        "wind_to_from_conversion": WIND_TO_FROM_CONVERSION,
        "zero_distance_semantics": ZERO_DISTANCE_SEMANTICS,
        "zero_resultant_semantics": ZERO_RESULTANT_SEMANTICS,
        "bearing_zero_is_valid_north": BEARING_ZERO_IS_VALID_NORTH,
        "directional_clarity_semantics": DIRECTIONAL_CLARITY_SEMANTICS,
        "temporal_firewall": TEMPORAL_FIREWALL,
        "frozen_c0_directional_status": FROZEN_C0_DIRECTIONAL_STATUS,
        "direction_method_candidates": DIRECTION_METHOD_CANDIDATES,
        "direction_weight_status": DIRECTION_WEIGHT_STATUS,
        "direction_evaluation_truth_status": DIRECTION_EVALUATION_TRUTH_STATUS,
        "overall_readiness_status": OVERALL_READINESS_STATUS,
    }


def direction_readiness_protocol_hash_8a() -> str:
    canonical = json.dumps(direction_readiness_protocol_dict_8a(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Checkpoint 8A.1 -- hardened semantics. All symbols below are NEW; nothing
# above this line was modified by 8A.1.
# =============================================================================

HISTORICAL_CHECKPOINT_8A_INITIAL_READINESS_HASH = "c896048f4bc11264d17385240898ba6566b843a3f5a56f7fc8c21ae802187160"

# Part 8: three distinct, separately named numerical tolerances -- never
# conflated. Mirrors the constants actually used in direction_readiness_8a.py
# (imported directly below so this protocol dict can never silently drift
# from the real implementation).
from .direction_readiness_8a import (  # noqa: E402
    CLARITY_RANGE_CLAMP_TOLERANCE,
    GENERIC_BEARING_ZERO_SEMANTICS,
    RESULTANT_RELATIVE_CANCELLATION_EPSILON,
    UNIT_VECTOR_NORM_TOLERANCE,
)
from ..hazard.anisotropy import CALM_WIND_EPSILON_M_S  # noqa: E402

WIND_CALM_THRESHOLD_IDENTITY = (
    "REUSES_HAZARD_ANISOTROPY_CALM_WIND_EPSILON_M_S_STRICT_LESS_THAN_COMPARISON_"
    "NEVER_A_DUPLICATED_LITERAL_NEVER_THE_GENERIC_OR_RELATIVE_CANCELLATION_TOLERANCE"
)

NON_FINITE_REJECTION_SEMANTICS = (
    "EVERY_NUMERICAL_INPUT_MUST_BE_FINITE_REAL_NAN_OR_INF_RAISES_VALUEERROR_"
    "NEVER_REINTERPRETED_AS_ZERO_OR_MISSING_NORTH"
)

UNIT_VECTOR_VALIDATION_SEMANTICS = (
    "USABLE_TERM_DISTANCE_KM_GT_0_MUST_HAVE_T_HAT_NORM_WITHIN_UNIT_VECTOR_NORM_TOLERANCE_OF_1_"
    "NEVER_SILENTLY_RENORMALIZED_FAILS_CLOSED_ON_UPSTREAM_GEOMETRY_DEFECT_"
    "ZERO_DISTANCE_TERM_MUST_CARRY_EXACTLY_0_0_NEVER_A_FABRICATED_DIRECTION"
)

CLARITY_RANGE_INVARIANT_SEMANTICS = (
    "DIRECTIONAL_CLARITY_MUST_LIE_IN_0_1_MICROSCOPIC_FLOAT_OVERSHOOT_WITHIN_"
    "CLARITY_RANGE_CLAMP_TOLERANCE_IS_CLAMPED_MATERIAL_OVERSHOOT_RAISES_VALUEERROR"
)

RESULTANT_SCALE_INVARIANCE_SEMANTICS = (
    "BEARING_AVAILABILITY_AND_DIRECTIONAL_CLARITY_DEPEND_ONLY_ON_MAGNITUDE_OVER_TOTAL_MASS_"
    "A_DIMENSIONLESS_RATIO_INVARIANT_UNDER_MULTIPLYING_EVERY_POSITIVE_WEIGHT_BY_A_COMMON_SCALAR"
)

# Part 9: corrected Method-A readiness classification -- the flat
# "scientifically_defined: True" alongside "DIRECTION_WEIGHT_NOT_YET_
# SCIENTIFICALLY_DEFINED" was a genuine semantic contradiction (a complete
# weighted-resultant METHOD is not fully specified until w_j_i is frozen).
# Methods B and C are carried forward UNCHANGED from Checkpoint 8A -- no new
# evidence exists to justify changing them.
DIRECTION_METHOD_CANDIDATES_8A1 = {
    "GEOMETRIC_SOURCE_RESULTANT_TENDENCY": {
        "geometry_definition_status": "SCIENTIFICALLY_DEFINED",
        "aggregation_framework_status": "MATHEMATICALLY_DEFINED",
        "directional_weight_status": "NOT_YET_SCIENTIFICALLY_DEFINED",
        "complete_method_specification_status": "INCOMPLETE_PENDING_WEIGHT_DEFINITION",
        "data_ready": True,
        "temporally_safe": True,
        "eligible_for_8b_development": True,
        "reason": (
            "Source->cell unit-vector geometry (t_hat_east/t_hat_north, "
            "services.geospatial.distance.source_to_cell_unit_vector) is real, "
            "tested, and available for every eligible source at every "
            "already-frozen forecast origin with no additional data dependency "
            "(GEOMETRY_DEFINITION_STATUS=SCIENTIFICALLY_DEFINED). The "
            "resultant-vector aggregation math (compute_resultant_vector, "
            "hardened scale-invariant in Checkpoint 8A.1) is implemented and "
            "tested (AGGREGATION_FRAMEWORK_STATUS=MATHEMATICALLY_DEFINED). "
            "However NO scientifically selected weight exists -- w_j_i is "
            "undefined (DIRECTIONAL_WEIGHT_STATUS=NOT_YET_SCIENTIFICALLY_DEFINED) "
            "-- so the COMPLETE method is INCOMPLETE_PENDING_WEIGHT_DEFINITION, "
            "never fully scientifically specified. 8B may develop/predeclare a "
            "scientifically defensible weighting rule on FIT_DEVELOPMENT only; "
            "this eligibility is NOT evidence that a spread-direction method "
            "already exists. Until a weight is scientifically justified and an "
            "evaluation protocol supports the claim, any output must be labelled "
            "a geometric/relative-risk tendency, never disease spread direction, "
            "validated spread direction, predicted transmission direction, or "
            "disease movement direction."
        ),
    },
    "WIND_INFORMED_HAZARD_RESULTANT": dict(DIRECTION_METHOD_CANDIDATES["WIND_INFORMED_HAZARD_RESULTANT"]),
    "HAZARD_SURFACE_GRADIENT_DIRECTION": dict(DIRECTION_METHOD_CANDIDATES["HAZARD_SURFACE_GRADIENT_DIRECTION"]),
}

# Unchanged from 8A -- re-exported under the _8A1 name only for symmetry;
# their VALUE is identical to the original 8A constants.
DIRECTION_WEIGHT_STATUS_8A1 = DIRECTION_WEIGHT_STATUS
DIRECTION_EVALUATION_TRUTH_STATUS_8A1 = DIRECTION_EVALUATION_TRUTH_STATUS
OVERALL_READINESS_STATUS_8A1 = OVERALL_READINESS_STATUS  # re-affirmed only if evidence still supports it (Part 17)


def direction_readiness_protocol_dict_8a1() -> dict:
    """Every field bound into the HARDENED 8A.1 protocol hash. Includes
    everything genuinely re-affirmed from 8A plus the Part 2-9 hardening.
    Deliberately excludes any timestamp."""
    return {
        "bearing_convention": BEARING_CONVENTION,
        "generic_bearing_zero_semantics": GENERIC_BEARING_ZERO_SEMANTICS,
        "resultant_relative_cancellation_epsilon": RESULTANT_RELATIVE_CANCELLATION_EPSILON,
        "resultant_scale_invariance_semantics": RESULTANT_SCALE_INVARIANCE_SEMANTICS,
        "unit_vector_norm_tolerance": UNIT_VECTOR_NORM_TOLERANCE,
        "unit_vector_validation_semantics": UNIT_VECTOR_VALIDATION_SEMANTICS,
        "non_finite_rejection_semantics": NON_FINITE_REJECTION_SEMANTICS,
        "clarity_range_clamp_tolerance": CLARITY_RANGE_CLAMP_TOLERANCE,
        "clarity_range_invariant_semantics": CLARITY_RANGE_INVARIANT_SEMANTICS,
        "wind_calm_threshold_identity": WIND_CALM_THRESHOLD_IDENTITY,
        "wind_calm_epsilon_m_s": CALM_WIND_EPSILON_M_S,
        "wind_component_convention": WIND_COMPONENT_CONVENTION,
        "wind_named_direction_sense": WIND_NAMED_DIRECTION_SENSE,
        "wind_to_from_conversion": WIND_TO_FROM_CONVERSION,
        "source_to_cell_orientation": SOURCE_TO_CELL_ORIENTATION,
        "zero_distance_semantics": ZERO_DISTANCE_SEMANTICS,
        "temporal_firewall": TEMPORAL_FIREWALL,
        "frozen_c0_directional_status": FROZEN_C0_DIRECTIONAL_STATUS,
        "direction_method_candidates_8a1": DIRECTION_METHOD_CANDIDATES_8A1,
        "direction_weight_status": DIRECTION_WEIGHT_STATUS_8A1,
        "direction_evaluation_truth_status": DIRECTION_EVALUATION_TRUTH_STATUS_8A1,
        "overall_readiness_status": OVERALL_READINESS_STATUS_8A1,
    }


def direction_readiness_protocol_hash_8a1() -> str:
    canonical = json.dumps(direction_readiness_protocol_dict_8a1(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
