"""Checkpoint 9B: frozen protocol identity for the formal S0 apparent
local spread-front rate estimate.

Binds the parent Checkpoint 9A protocol hash, the 9A.1 pre-9B numeric-
exposure classification, the canonical input-dataset identity (read
from the already-persisted Checkpoint 9A target-level CSV -- never
regenerated), the bootstrap implementation/RNG identity, the frozen
quantile-endpoint formula, and every 9B-specific semantic into one
deterministic hash computed BEFORE the real 1000-replicate bootstrap
runs. Never binds a timestamp.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

from . import rate_s0_bootstrap_9b
from .rate_input_identity_9b import compute_dataset_identity
from .rate_s0_bootstrap_9b import (
    BOOTSTRAP_CI_TYPE_9B,
    BOOTSTRAP_INTERVAL_LEVEL_9B,
    BOOTSTRAP_N_RESAMPLES_9B,
    BOOTSTRAP_SAMPLE_SIZE_RULE_9B,
    BOOTSTRAP_SEED_9B,
    BOOTSTRAP_UNIT_9B,
    BOOTSTRAP_WITH_REPLACEMENT_9B,
    QUANTILE_FORMULA_9B,
    QUANTILE_METHOD_9B,
    Q_LOWER_9B,
    Q_UPPER_9B,
    S0_ESTIMATOR_9B,
    bootstrap_implementation_identity,
)
from ..geospatial.raster import LOCAL_GIS_CACHE_DIR

CHECKPOINT_VERSION_9B = "9B"

HISTORICAL_9A_PROTOCOL_HASH_9B = "326427b08f5c43b9708409ae112460e8f0804db0c972a007caaae8ffca3b58ac"
NINE_A1_EXPOSURE_CLASSIFICATION_9B = "PRE_9B_S0_NUMERIC_ESTIMATOR_EXPOSURE_IN_9A_DIAGNOSTIC_DISCLOSED"
EXPOSED_ESTIMATOR_VALUE_9B = 3.946421443154751

RATE_LABEL_9B = "Estimated apparent local spread-front rate (km/day)"
TARGET_LEVEL_ESTIMATOR_FORMULA_9B = "S0 = MEDIAN of target_level_v across UNIQUE target_event_id values -- never the median of raw origin-target rows"

N_ZERO_DISTANCE_ORIGIN_TARGET_9B = 12
N_ZERO_TARGET_LEVEL_MEDIAN_9B = 4

PRIMARY_HORIZON_IDENTITY_9B = "D1_D7"
LOCAL_SCOPE_IDENTITY_9B = "25_KM_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE"
RETROSPECTIVE_EVENT_DATE_LIMITATION_9B = "RECORDED_HISTORICAL_EVENT_DATE_TARGET_OCCURRENCE_PROXY_NOT_TRUE_INFECTION_TIME"

NO_CLIPPING_9B = "NO_WINSORIZATION_NO_CLIPPING_NO_LOG_TRANSFORMATION"
S1_STATUS_9B = "NOT_SELECTED"
NO_DIRECTION_OR_WIND_RATE_9B = "NO_FORMULA_CONNECTS_8B3_DIRECTION_FIELD_OR_WIND_SPEED_TO_S0"
HELD_OUT_FIREWALL_9B = "HELD_OUT_RATE_NOT_EVALUATED_IN_9B"
SRI_LANKA_FIREWALL_9B = "SRI_LANKA_RATE_NOT_EVALUATED_IN_9B"
NOMINAL_REACH_STATUS_9B = "NOT_COMPUTED_IN_9B"

PRE_9B_NUMERIC_EXPOSURE_DISCLOSURE_9B = "PRE_9B_S0_NUMERIC_ESTIMATOR_EXPOSURE_IN_9A_DIAGNOSTIC_DISCLOSED_NEVER_DESCRIBED_AS_FIRST_LOOK_OR_BLIND_ESTIMATION"

RESULT_INTERPRETATION_LIMITATIONS_9B = (
    "A. This is an apparent geometric historical rate, not biological transmission speed. "
    "B. Recorded event dates are occurrence-time proxies, not exact infection or transmission times. "
    "C. The nearest known eligible source is a geometric reference, not a confirmed causal parent. "
    "D. The estimate is conditional on the frozen D1-D7 / 25-km local evaluation protocol. "
    "E. GPS/reporting uncertainty remains. "
    "F. The target-event bootstrap does not model higher-level dependence by country, outbreak episode, "
    "reporting system, spatial cluster, or calendar period -- it treats the 371 target-event summaries as "
    "the empirical resampling units. "
    "G. The bootstrap interval quantifies empirical sampling uncertainty of the target-level median under "
    "the declared target-event resampling assumption; it is not complete epidemiological or measurement "
    "uncertainty. "
    "H. The reported percentile endpoints are based on the preregistered finite set of 1000 bootstrap "
    "replicates; additional Monte-Carlo uncertainty of the bootstrap endpoints is not separately quantified. "
    "I. This is development historical evidence, not a held-out rate-performance result and not a "
    "Sri Lanka-specific rate estimate."
)

DEFAULT_9A_TARGET_LEVEL_CSV_PATH = LOCAL_GIS_CACHE_DIR.parent / "model_development" / "9a_rate" / "rate_target_level_readiness_9a.csv"


def bootstrap_implementation_source_sha256() -> str:
    source_path = Path(inspect.getfile(rate_s0_bootstrap_9b))
    return hashlib.sha256(source_path.read_bytes()).hexdigest()


def s0_bootstrap_protocol_dict_9b(csv_path: Path = DEFAULT_9A_TARGET_LEVEL_CSV_PATH) -> dict:
    """Every field bound into the frozen 9B protocol hash. Reads the
    already-persisted Checkpoint 9A CSV ONLY to compute its identity
    (SHA256 + canonical payload hash) -- never regenerates it, never
    touches the outbreak database. Deliberately excludes any
    timestamp."""
    identity, _rows = compute_dataset_identity(csv_path)
    if identity.n_rows != 371 or identity.n_unique_target_event_id != 371:
        raise AssertionError(
            f"9B protocol freeze: expected 371 rows/371 unique target_event_id, got "
            f"n_rows={identity.n_rows} n_unique={identity.n_unique_target_event_id} -- STOP, do not proceed"
        )

    return {
        "checkpoint": CHECKPOINT_VERSION_9B,
        "parent_historical_9a_protocol_hash": HISTORICAL_9A_PROTOCOL_HASH_9B,
        "nine_a1_exposure_classification": NINE_A1_EXPOSURE_CLASSIFICATION_9B,
        "exposed_estimator_value_km_day": EXPOSED_ESTIMATOR_VALUE_9B,
        "rate_label": RATE_LABEL_9B,
        "target_level_estimator_formula": TARGET_LEVEL_ESTIMATOR_FORMULA_9B,
        "input_csv_sha256": identity.input_csv_sha256,
        "canonical_payload_hash_from_persisted_text": identity.canonical_payload_hash_from_persisted_text,
        "row_count": identity.n_rows,
        "unique_target_count": identity.n_unique_target_event_id,
        "n_zero_distance_origin_target_observations": N_ZERO_DISTANCE_ORIGIN_TARGET_9B,
        "n_zero_target_level_median_rates": N_ZERO_TARGET_LEVEL_MEDIAN_9B,
        "primary_horizon_identity": PRIMARY_HORIZON_IDENTITY_9B,
        "local_scope_identity": LOCAL_SCOPE_IDENTITY_9B,
        "retrospective_event_date_limitation": RETROSPECTIVE_EVENT_DATE_LIMITATION_9B,
        "bootstrap_unit": BOOTSTRAP_UNIT_9B,
        "bootstrap_sample_size_rule": BOOTSTRAP_SAMPLE_SIZE_RULE_9B,
        "bootstrap_with_replacement": BOOTSTRAP_WITH_REPLACEMENT_9B,
        "bootstrap_seed": BOOTSTRAP_SEED_9B,
        "bootstrap_n_resamples": BOOTSTRAP_N_RESAMPLES_9B,
        "bootstrap_interval_level": BOOTSTRAP_INTERVAL_LEVEL_9B,
        "bootstrap_ci_type": BOOTSTRAP_CI_TYPE_9B,
        "quantile_method": QUANTILE_METHOD_9B,
        "quantile_formula": QUANTILE_FORMULA_9B,
        "q_lower": Q_LOWER_9B,
        "q_upper": Q_UPPER_9B,
        "s0_estimator": S0_ESTIMATOR_9B,
        "rng_implementation_identity": bootstrap_implementation_identity(),
        "bootstrap_implementation_source_sha256": bootstrap_implementation_source_sha256(),
        "no_clipping": NO_CLIPPING_9B,
        "s1_status": S1_STATUS_9B,
        "no_direction_or_wind_rate": NO_DIRECTION_OR_WIND_RATE_9B,
        "held_out_firewall": HELD_OUT_FIREWALL_9B,
        "sri_lanka_firewall": SRI_LANKA_FIREWALL_9B,
        "nominal_reach_status": NOMINAL_REACH_STATUS_9B,
        "pre_9b_numeric_exposure_disclosure": PRE_9B_NUMERIC_EXPOSURE_DISCLOSURE_9B,
        "result_interpretation_limitations": RESULT_INTERPRETATION_LIMITATIONS_9B,
    }


def s0_bootstrap_protocol_hash_9b(csv_path: Path = DEFAULT_9A_TARGET_LEVEL_CSV_PATH) -> str:
    canonical = json.dumps(s0_bootstrap_protocol_dict_9b(csv_path), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
