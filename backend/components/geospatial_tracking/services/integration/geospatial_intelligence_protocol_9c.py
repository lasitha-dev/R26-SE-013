"""Checkpoint 9C Part 16: versioned scientific/integration protocol
identity for the frozen geospatial intelligence contract.

Binds every frozen parent hash (7C risk, 8B.3 direction, historical 9A,
9B rate/bootstrap), the nominal-reach formula and D1-D7 range, the
frozen rate point estimate and CI endpoints, the risk temporal
semantics, the 25km-vs-reach separation rule, direction semantics,
clarity-not-confidence, risk-not-probability, and the nearest-source
geometric-only rule into ONE deterministic hash --
`integration_protocol_hash_9c()`. Deliberately excludes any timestamp,
absolute machine path, UI styling, or HTTP URL (Part 16).

**No re-derivation** (Part 15): `9b_rate_protocol_hash` and the two
rate-dataset SHA256 values below are copied literally from the
already-frozen Checkpoint 9B result
(`RATE_MODEL_PROTOCOL.md` §21 / `CHECKPOINT_9B_EVIDENCE_SUMMARY.json`)
-- never recomputed by reading `local_data` here, so this module stays
importable and its hash stable even when the gitignored `local_data`
tree is absent (e.g. a fresh clone).
"""

from __future__ import annotations

import hashlib
import json

from ..direction.c0_cell_local_tendency_8b3 import (
    DIRECTION_EVALUATION_TRUTH_STATUS_8B3,
    METHOD_ID_8B3,
    METHOD_VERSION_8B3,
)
from ..model_development.direction_protocol_8b import direction_method_protocol_hash_8b3
from ..model_development.heldout_protocol_7d import FROZEN_7C_SPEC_HASH, SELECTED_CANDIDATE_ID
from ..model_development.rate_protocol_9b import (
    HISTORICAL_9A_PROTOCOL_HASH_9B,
    NINE_A1_EXPOSURE_CLASSIFICATION_9B,
    RATE_LABEL_9B,
)
from .geospatial_intelligence_contract_9c import (
    NEAREST_SOURCE_SEMANTICS_9C,
    OPERATIONAL_EVALUATION_ENVELOPE_KM_9C,
    RATE_SCOPE_9C,
    RATE_STATUS_9C,
    RATE_VALIDATION_STATUS_9C,
    RESEARCH_EVIDENCE_STATUS_9C,
    RISK_SCORE_SEMANTICS_9C,
    RISK_SURFACE_TEMPORAL_SEMANTICS_9C,
    SRI_LANKA_RATE_STATUS_9C,
)
from .nominal_reach_9c import (
    DERIVED_INTERVAL_FORMULA_9C,
    DERIVED_INTERVAL_LABEL_9C,
    FROZEN_BOOTSTRAP_LOWER_RATE_KM_DAY_9C,
    FROZEN_BOOTSTRAP_UPPER_RATE_KM_DAY_9C,
    FROZEN_S0_RATE_KM_DAY_9C,
    NOMINAL_REACH_FORMULA_9C,
    NOMINAL_REACH_LABEL_9C,
    NOMINAL_REACH_SEMANTICS_9C,
    PRIMARY_HORIZON_DAYS_9C,
)

CHECKPOINT_VERSION_9C = "9C"

# Part 15/16: copied literally from the already-frozen Checkpoint 9B
# result -- never recomputed here (would require reading the
# gitignored local_data tree).
S0_BOOTSTRAP_PROTOCOL_HASH_9B_9C = "969161e318508edfa2465d2f4598dbca17fcf29ef01bba2df42bec8093835d28"
RATE_INPUT_CSV_SHA256_9C = "71e7d82f974d1dd01911c45fbbfd7121ef07e915212c3f7004fef6120399b183"
RATE_CANONICAL_PAYLOAD_SHA256_9C = "ebbd08e30c14f91e17110dfe42a20b7239812a4f307f3edc2137cde98ca6202f"

NO_C0_MODIFICATION_RULE_9C = "NOMINAL_REACH_NEVER_MODIFIES_C0_CELL_SCORE_OR_EVALUATION_ENVELOPE"
NO_FAKE_DAILY_RISK_RULE_9C = "NO_DAY_VARYING_C0_RISK_SURFACE_IS_FABRICATED_FROM_RATE_OR_REACH"
DIRECTION_RATE_INDEPENDENCE_RULE_9C = "RATE_IS_NOT_DIRECTION_MAGNITUDE_CLARITY_WIND_SPEED_OR_C0_SCORE_AND_DIRECTION_IS_NEVER_SCALED_INTO_KM_DAY"
CLARITY_NOT_CONFIDENCE_RULE_9C = "DIRECTIONAL_CLARITY_IS_NORMALIZED_GEOMETRIC_RESULTANT_COHERENCE_NEVER_CONFIDENCE"
BEARING_ZERO_VALID_NORTH_RULE_9C = "BEARING_0_DEGREES_IS_VALID_NORTH_NEVER_FABRICATED_FOR_UNAVAILABLE_DIRECTION"
RISK_NOT_PROBABILITY_RULE_9C = "NO_FIELD_NAMED_INFECTION_PROBABILITY_TRANSMISSION_PROBABILITY_OR_PROBABILITY_OF_INFECTION"
D8_D14_OUT_OF_SCOPE_RULE_9C = "D8_D14_EXPLORATORY_HORIZON_NOT_GENERATED_BY_THE_PRIMARY_9C_CONTRACT"

LIMITATIONS_9C = (
    "NOMINAL_REACH_IS_A_DETERMINISTIC_VISUALIZATION_CONTEXT_QUANTITY_NOT_A_HARD_DISEASE_BOUNDARY",
    "NOMINAL_REACH_INHERITS_ALL_CHECKPOINT_9B_RATE_LIMITATIONS_A_THROUGH_I",
    "25KM_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE_IS_A_DIFFERENT_QUANTITY_FROM_NOMINAL_REACH_NEVER_RECONCILED",
    "FROZEN_C0_RISK_SURFACE_IS_STATIC_T0_SPATIAL_RANK_CONTEXT_NOT_A_DAY_VARYING_PREDICTION",
    "DIRECTION_IS_DESCRIPTIVE_GEOMETRIC_TENDENCY_NOT_VALIDATED_PREDICTIVE_SPREAD_DIRECTION_AND_INDEPENDENT_OF_RATE",
)


def integration_protocol_dict_9c() -> dict:
    """Every field bound into the frozen 9C protocol hash. No
    timestamp, absolute machine path, UI styling, or HTTP URL."""
    return {
        "checkpoint": CHECKPOINT_VERSION_9C,
        "frozen_c0_candidate_id": SELECTED_CANDIDATE_ID,
        "frozen_7c_spec_hash": FROZEN_7C_SPEC_HASH,
        "risk_score_semantics": RISK_SCORE_SEMANTICS_9C,
        "risk_surface_temporal_semantics": RISK_SURFACE_TEMPORAL_SEMANTICS_9C,
        "direction_method_id": METHOD_ID_8B3,
        "direction_method_version": METHOD_VERSION_8B3,
        "direction_method_protocol_hash_8b3": direction_method_protocol_hash_8b3(),
        "direction_evaluation_truth_status": DIRECTION_EVALUATION_TRUTH_STATUS_8B3,
        "historical_9a_protocol_hash": HISTORICAL_9A_PROTOCOL_HASH_9B,
        "nine_a1_exposure_classification": NINE_A1_EXPOSURE_CLASSIFICATION_9B,
        "s0_bootstrap_protocol_hash_9b": S0_BOOTSTRAP_PROTOCOL_HASH_9B_9C,
        "rate_input_csv_sha256": RATE_INPUT_CSV_SHA256_9C,
        "rate_canonical_payload_sha256": RATE_CANONICAL_PAYLOAD_SHA256_9C,
        "rate_label": RATE_LABEL_9B,
        "frozen_s0_rate_km_day": FROZEN_S0_RATE_KM_DAY_9C,
        "frozen_bootstrap_lower_rate_km_day": FROZEN_BOOTSTRAP_LOWER_RATE_KM_DAY_9C,
        "frozen_bootstrap_upper_rate_km_day": FROZEN_BOOTSTRAP_UPPER_RATE_KM_DAY_9C,
        "rate_status": RATE_STATUS_9C,
        "rate_scope": RATE_SCOPE_9C,
        "rate_validation_status": RATE_VALIDATION_STATUS_9C,
        "sri_lanka_rate_status": SRI_LANKA_RATE_STATUS_9C,
        "nominal_reach_label": NOMINAL_REACH_LABEL_9C,
        "nominal_reach_formula": NOMINAL_REACH_FORMULA_9C,
        "nominal_reach_semantics": NOMINAL_REACH_SEMANTICS_9C,
        "derived_interval_label": DERIVED_INTERVAL_LABEL_9C,
        "derived_interval_formula": DERIVED_INTERVAL_FORMULA_9C,
        "primary_horizon_days": list(PRIMARY_HORIZON_DAYS_9C),
        "operational_evaluation_envelope_km": OPERATIONAL_EVALUATION_ENVELOPE_KM_9C,
        "no_c0_modification_rule": NO_C0_MODIFICATION_RULE_9C,
        "no_fake_daily_risk_rule": NO_FAKE_DAILY_RISK_RULE_9C,
        "direction_rate_independence_rule": DIRECTION_RATE_INDEPENDENCE_RULE_9C,
        "clarity_not_confidence_rule": CLARITY_NOT_CONFIDENCE_RULE_9C,
        "bearing_zero_valid_north_rule": BEARING_ZERO_VALID_NORTH_RULE_9C,
        "risk_not_probability_rule": RISK_NOT_PROBABILITY_RULE_9C,
        "d8_d14_out_of_scope_rule": D8_D14_OUT_OF_SCOPE_RULE_9C,
        "nearest_source_semantics": NEAREST_SOURCE_SEMANTICS_9C,
        "research_evidence_status": RESEARCH_EVIDENCE_STATUS_9C,
        "limitations": list(LIMITATIONS_9C),
    }


def integration_protocol_hash_9c() -> str:
    canonical = json.dumps(integration_protocol_dict_9c(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
