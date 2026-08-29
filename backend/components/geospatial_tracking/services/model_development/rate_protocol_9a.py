"""Checkpoint 9A: frozen protocol identity for the APPARENT LOCAL
SPREAD-FRONT RATE development-data readiness dataset.

Scientific purpose: can a leakage-safe, deduplicated, interpretable
historical dataset be defined for estimating an apparent local
spread-front rate from FIT_DEVELOPMENT data? This module freezes the
observation formula, role/temporal/scope firewalls, de-pseudo-
replication rule, and the future S0/bootstrap plan -- BEFORE any real
rate value is derived or summarized. It computes NO rate value itself.

**"Apparent" is scientifically load-bearing** (Part 1): the output
label is "Estimated apparent local spread-front rate (km/day)" --
never true disease transmission speed, viral velocity, wind speed,
direction-vector magnitude, exact epidemic front velocity, or causal
farm-to-farm transmission speed.

**Independent of the direction field** (Part 2): there is no formula
anywhere in this checkpoint connecting 8B.3's `resultant_magnitude`,
`directional_clarity`, or `directional_input_coverage` to
`apparent_local_spread_front_rate_km_day`. Rate is derived
independently from historical outbreak geometry and elapsed time.

Every identity below REUSES an already-frozen project primitive rather
than re-declaring a new one -- see the imports.
"""

from __future__ import annotations

import hashlib
import json

from .candidate_registry_7c import C0_FAMILY, build_candidate_registry_7c
from .evaluation_protocol_7c import ACTIVE_SOURCE_WINDOW_DAYS_7C
from .local_evaluation_scope import (
    PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
    PRIMARY_LOCAL_EVALUATION_DISTANCE_STATUS,
    PRIMARY_SCOPE_TRUTH_METHOD,
)
from ..forecast_target import PRIMARY_HORIZON_DAYS

CHECKPOINT_VERSION_9A = "9A"
ROLE_9A = "FIT_DEVELOPMENT"
DISEASE_9A = "Lumpy skin disease"

_registry_9a = build_candidate_registry_7c()
_c0_spec_9a = next(c for c in _registry_9a if c.family == C0_FAMILY)
FROZEN_C0_SELECTED_CANDIDATE_ID_9A = _c0_spec_9a.candidate_id
FROZEN_7C_SPEC_HASH_9A = "ef3511d3527da6d85598846c0d828509ed07f134ac8d987c3d5702b507505a6d"

PRIMARY_HORIZON_9A = f"D1_D{PRIMARY_HORIZON_DAYS}"  # D1_D7 -- reuses forecast_target.PRIMARY_HORIZON_DAYS, never re-declared
D8_D14_RESCUE_PROHIBITED_9A = "D8_D14_NEVER_INTRODUCED_TO_RESCUE_PRIMARY_RATE_DATASET_AFTER_OBSERVING_ITS_RESULT"

LOCAL_SCOPE_IDENTITY_9A = {
    "distance_km": PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
    "status": PRIMARY_LOCAL_EVALUATION_DISTANCE_STATUS,
    "truth_method": PRIMARY_SCOPE_TRUTH_METHOD,
    "reused_from": "services.model_development.local_evaluation_scope (7A.6/7A.6.1, unchanged)",
    "semantics": "OPERATIONAL_LOCAL_EVALUATION_ENVELOPE_NEVER_BIOLOGICAL_LSD_SPREAD_RADIUS_OR_MAX_TRANSMISSION_DISTANCE",
}
OUTSIDE_LOCAL_RATE_SCOPE_LABEL_9A = "OUTSIDE_DECLARED_LOCAL_RATE_SCOPE"

ACTIVE_SOURCE_WINDOW_IDENTITY_9A = {
    "active_window_days": ACTIVE_SOURCE_WINDOW_DAYS_7C,
    "reused_from": "services.model_development.evaluation_protocol_7c.ACTIVE_SOURCE_WINDOW_DAYS_7C",
}

ELIGIBLE_SOURCE_PROTOCOL_IDENTITY_9A = (
    "services.source_selector.get_eligible_sources, temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, "
    "domain_scope=RecordDomainScope.HISTORICAL_ONLY -- the EXACT existing eligible-active-source selector "
    "every prior checkpoint (7B-8B.3) already uses; ST-DBSCAN never gates source inclusion"
)

TARGET_ELIGIBILITY_IDENTITY_9A = "services.forecast_target.build_forecast_targets + ForecastTarget.risk_target_eligible (Checkpoint 4/4.5, unchanged)"
TARGET_UNIQUENESS_RULE_9A = "(forecast_origin_id, target_event_id) unique per origin -- target identity is outbreak-episode based, never a raw animal report"
TARGET_EVENT_DEDUP_RULE_9A = "services.model_development.development_run_7b.dedupe_targets_by_origin_and_event -- first occurrence of (origin, target_event_id) kept"

LEAD_DAYS_RULE_9A = "lead_days > 0, structurally guaranteed by build_forecast_targets (1 <= lead_days <= 7); re-verified defensively, never assumed"

GEODESIC_DISTANCE_IMPLEMENTATION_IDENTITY_9A = "services.geospatial.distance.distance_km (WGS84 geodesic, pyproj.Geod) -- never degrees-as-km, never grid-cell-center approximation"
D_MIN_DEFINITION_9A = "MIN over ALL eligible t0 sources, via services.model_development.local_evaluation_scope.classify_target_primary_scope.min_distance_to_eligible_source_km"
NEAREST_SOURCE_STATUS_9A = "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE -- never causal parent, confirmed transmission source, or infection origin"

V_OBS_EQUATION_9A = "v_obs(o,k) = d_min(o,k) / lead_days(o,k), units km/day"
V_OBS_OUTPUT_LABEL_9A = "Estimated apparent local spread-front rate (km/day)"

TARGET_LEVEL_MEDIAN_RULE_9A = "target_level_v(target_event_id) = MEDIAN of all valid FIT_DEVELOPMENT v_obs rows for that unique target_event_id"
FUTURE_S0_FORMULA_9A = "S0 = MEDIAN of target_level_v across UNIQUE target_event_id values -- never the median of raw origin-target rows"
FUTURE_S0_STATUS_9A = "FORMULA_FROZEN_VALUE_NOT_YET_COMPUTED"

ZERO_DISTANCE_SEMANTICS_9A = (
    "A legitimate distinct deduplicated outbreak episode with d_min=0 and lead_days>0 retains v_obs=0 km/day "
    "as a genuine geometric apparent-rate observation, with coordinate-quality/collision warning attached -- "
    "never converted to missing, never asserted as 'no spread', never epsilon-substituted. If coordinate "
    "identity is unresolved under an existing dedup/collision rule, that frozen rule is applied and the "
    "exclusion reason is reported, not silently dropped."
)

GPS_QUALITY_SEMANTICS_9A = (
    "Reuses the existing GpsQuality enum (EXACT/APPROXIMATE/COARSE/UNKNOWN) verbatim -- EXACT is never read "
    "as implying meter-level or survey-grade precision. Approximate/coarse coordinates are never silently "
    "excluded merely because they produce inconvenient rate values; their counts are reported."
)

TEMPORAL_DATE_LIMITATION_9A = "APPARENT_RATE_FROM_RECORDED_EVENT_CHRONOLOGY_NOT_TRUE_INFECTION_TIME"

NO_CLIPPING_STATUS_9A = "NO_WINSORIZATION_NO_CLIPPING_NO_POST_HOC_TRANSFORMATION_NO_SCOPE_CHANGE_AFTER_VIEWING_VALUES"

NO_DIRECTION_OR_WIND_INPUT_9A = (
    "NO_FORMULA_CONNECTS_8B3_RESULTANT_MAGNITUDE_DIRECTIONAL_CLARITY_OR_DIRECTIONAL_INPUT_COVERAGE_"
    "TO_APPARENT_LOCAL_SPREAD_FRONT_RATE_KM_DAY; NO_WIND_SPEED_INPUT; NO_FUTURE_WEATHER_INPUT"
)

HELD_OUT_FIREWALL_9A = "services.model_fitting_exposure.assert_fit_development_only -- HELD_OUT_FROM_MODEL_FITTING hard-rejected before any repository access"
SRI_LANKA_FIREWALL_9A = "services.model_fitting_exposure.assert_fit_development_only -- SRI_LANKA_TRANSFER_CASE_STUDY hard-rejected before any repository access"

S1_STATUS_9A = "NOT_SELECTED_IN_CHECKPOINT_9A"
NOMINAL_REACH_STATUS_9A = "NOT_YET_COMPUTED"
NOMINAL_REACH_LABEL_9A = "Nominal Day-h local reach -- not a hard disease boundary"
NOMINAL_REACH_FORMULA_9A = "nominal_reach_km(day_h) = frozen_rate_km_day * day_h -- never truncates C0/risk surface, never changes target scope, never creates infection probability, never called a biological radius; unavailable/null if rate unavailable, never a default substitution"

# Part 21: predeclared BEFORE seeing the final S0 value.
BOOTSTRAP_PLAN_9B = {
    "primary_estimator": "median across unique target-level rates",
    "bootstrap_unit": "unique target_event_id (never origin-target row, never grid cell)",
    "seed": 42,
    "n_resamples": 1000,
    "interval": "95% percentile interval",
    "interpretation": "uncertainty around the historical target-level median, not a causal transmission-speed confidence interval",
}


def rate_readiness_protocol_dict_9a() -> dict:
    """Every field bound into the frozen 9A protocol hash. Deliberately
    excludes any timestamp."""
    return {
        "checkpoint_version": CHECKPOINT_VERSION_9A,
        "role": ROLE_9A,
        "disease": DISEASE_9A,
        "frozen_c0_selected_candidate_id": FROZEN_C0_SELECTED_CANDIDATE_ID_9A,
        "frozen_7c_spec_hash": FROZEN_7C_SPEC_HASH_9A,
        "primary_horizon": PRIMARY_HORIZON_9A,
        "d8_d14_rescue_prohibited": D8_D14_RESCUE_PROHIBITED_9A,
        "local_scope_identity": LOCAL_SCOPE_IDENTITY_9A,
        "outside_local_rate_scope_label": OUTSIDE_LOCAL_RATE_SCOPE_LABEL_9A,
        "active_source_window_identity": ACTIVE_SOURCE_WINDOW_IDENTITY_9A,
        "eligible_source_protocol_identity": ELIGIBLE_SOURCE_PROTOCOL_IDENTITY_9A,
        "target_eligibility_identity": TARGET_ELIGIBILITY_IDENTITY_9A,
        "target_uniqueness_rule": TARGET_UNIQUENESS_RULE_9A,
        "target_event_dedup_rule": TARGET_EVENT_DEDUP_RULE_9A,
        "lead_days_rule": LEAD_DAYS_RULE_9A,
        "geodesic_distance_implementation_identity": GEODESIC_DISTANCE_IMPLEMENTATION_IDENTITY_9A,
        "d_min_definition": D_MIN_DEFINITION_9A,
        "nearest_source_status": NEAREST_SOURCE_STATUS_9A,
        "v_obs_equation": V_OBS_EQUATION_9A,
        "v_obs_output_label": V_OBS_OUTPUT_LABEL_9A,
        "target_level_median_rule": TARGET_LEVEL_MEDIAN_RULE_9A,
        "future_s0_formula": FUTURE_S0_FORMULA_9A,
        "future_s0_status": FUTURE_S0_STATUS_9A,
        "zero_distance_semantics": ZERO_DISTANCE_SEMANTICS_9A,
        "gps_quality_semantics": GPS_QUALITY_SEMANTICS_9A,
        "temporal_date_limitation": TEMPORAL_DATE_LIMITATION_9A,
        "no_clipping_status": NO_CLIPPING_STATUS_9A,
        "no_direction_or_wind_input": NO_DIRECTION_OR_WIND_INPUT_9A,
        "held_out_firewall": HELD_OUT_FIREWALL_9A,
        "sri_lanka_firewall": SRI_LANKA_FIREWALL_9A,
        "s1_status": S1_STATUS_9A,
        "nominal_reach_status": NOMINAL_REACH_STATUS_9A,
        "nominal_reach_formula": NOMINAL_REACH_FORMULA_9A,
        "bootstrap_plan_9b": BOOTSTRAP_PLAN_9B,
    }


def rate_readiness_protocol_hash_9a() -> str:
    canonical = json.dumps(rate_readiness_protocol_dict_9a(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
