"""Checkpoint 9C.1 Part 14: non-destructive rate-scope conditioning
protocol identity.

Binds the historical 9A protocol hash, the 9B protocol hash, the 9C
integration protocol hash, the input 9A origin-target observation CSV
SHA256, the frozen S0 exact value, the frozen 9B interval, the D1-D7
horizon, the 25km operational envelope, the v_obs/theoretical-ceiling
formulas, and the audit-only/no-alternate-S0/no-held-out/no-Sri-Lanka/
GPS-quality-audit semantics into one deterministic hash. Deliberately
excludes any timestamp, absolute machine path, or API/UI field.

**Modifies nothing historical** (Part 14): this module never redefines
`HISTORICAL_9A_PROTOCOL_HASH_9B`, the 9B protocol hash, or
`integration_protocol_hash_9c()` -- it only reads/re-states them
(the 9B and 9C hashes as literal copies, matching the established
project convention of not letting a downstream checkpoint's protocol
module take on a disk/import dependency on an upstream one purely to
re-derive an already-frozen scalar)."""

from __future__ import annotations

import hashlib
import json

from ..forecast_target import PRIMARY_HORIZON_DAYS
from .local_evaluation_scope import PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
from .rate_protocol_9b import EXPOSED_ESTIMATOR_VALUE_9B, HISTORICAL_9A_PROTOCOL_HASH_9B
from .rate_scope_conditioning_9c1 import (
    DIAGNOSTIC_PURPOSE_9C1,
    GPS_QUALITY_AUDIT_SEMANTICS_9C1,
    HELD_OUT_FIREWALL_9C1,
    LEAD_DEPENDENT_TRUNCATION_MECHANISM_LABEL_9C1,
    NO_ALTERNATE_S0_STATUS_9C1,
    NOT_RATE_RETUNING_9C1,
    PRIMARY_HORIZON_RANGE_9C1,
    RATE_ESTIMAND_CONDITIONING_9C1,
    RATE_SCOPE_CONDITIONING_LABEL_9C1,
    SRI_LANKA_FIREWALL_9C1,
    THEORETICAL_CEILING_FORMULA_9C1,
    V_OBS_FORMULA_9C1,
)

CHECKPOINT_VERSION_9C1 = "9C.1"

# Part 14: literal copies of already-frozen upstream scalars -- never
# recomputed by reading local_data/calling upstream functions here, so
# this module stays importable and its hash stable on a clean clone.
HISTORICAL_9B_PROTOCOL_HASH_9C1 = "969161e318508edfa2465d2f4598dbca17fcf29ef01bba2df42bec8093835d28"
HISTORICAL_9C_INTEGRATION_PROTOCOL_HASH_9C1 = "cec826a26c860c752d1fa32d94edcdfba2e0186950cdccfc96067fef2ce51a90"
INPUT_OBSERVATION_CSV_SHA256_9C1 = "d67f02709a2ddac8b5f02cb4ebacafe42242229deafea153c600fb2bbd714a2d"
FROZEN_9B_INTERVAL_LOWER_9C1 = 3.5491046170907765
FROZEN_9B_INTERVAL_UPPER_9C1 = 4.343077329563724


def rate_scope_conditioning_protocol_dict_9c1() -> dict:
    return {
        "checkpoint": CHECKPOINT_VERSION_9C1,
        "diagnostic_purpose": DIAGNOSTIC_PURPOSE_9C1,
        "not_rate_retuning": NOT_RATE_RETUNING_9C1,
        "historical_9a_protocol_hash": HISTORICAL_9A_PROTOCOL_HASH_9B,
        "historical_9b_protocol_hash": HISTORICAL_9B_PROTOCOL_HASH_9C1,
        "historical_9c_integration_protocol_hash": HISTORICAL_9C_INTEGRATION_PROTOCOL_HASH_9C1,
        "input_observation_csv_sha256": INPUT_OBSERVATION_CSV_SHA256_9C1,
        "frozen_s0_km_day": EXPOSED_ESTIMATOR_VALUE_9B,
        "frozen_9b_interval_lower_km_day": FROZEN_9B_INTERVAL_LOWER_9C1,
        "frozen_9b_interval_upper_km_day": FROZEN_9B_INTERVAL_UPPER_9C1,
        "primary_horizon_days": list(PRIMARY_HORIZON_RANGE_9C1),
        "operational_evaluation_envelope_km": PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
        "v_obs_formula": V_OBS_FORMULA_9C1,
        "theoretical_ceiling_formula": THEORETICAL_CEILING_FORMULA_9C1,
        "rate_estimand_conditioning": RATE_ESTIMAND_CONDITIONING_9C1,
        "rate_scope_conditioning_label": RATE_SCOPE_CONDITIONING_LABEL_9C1,
        "lead_dependent_truncation_mechanism_label": LEAD_DEPENDENT_TRUNCATION_MECHANISM_LABEL_9C1,
        "no_alternate_s0_status": NO_ALTERNATE_S0_STATUS_9C1,
        "held_out_firewall": HELD_OUT_FIREWALL_9C1,
        "sri_lanka_firewall": SRI_LANKA_FIREWALL_9C1,
        "gps_quality_audit_semantics": GPS_QUALITY_AUDIT_SEMANTICS_9C1,
    }


def rate_scope_conditioning_protocol_hash_9c1() -> str:
    canonical = json.dumps(rate_scope_conditioning_protocol_dict_9c1(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
