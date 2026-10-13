"""Checkpoint 7C Part 14: the 7C evaluation-protocol identity + factor
readiness constants.

Reuses every scoring/ranking/selection semantic from 7B UNCHANGED
(percentile definition, MIDRANK ties, area weighting field, TOP5/TOP10
thresholds, fold aggregation rule, primary selection metric, tie-break
order, coverage-eligibility rule) -- see Checkpoint 7C spec Part 2/15.
This module only ADDS the identity facts specific to 7C (weather
temporal protocol, anisotropy implementation version, source-window
protocol) on top of 7B's own `baseline_evaluation_protocol_hash()`, so a
7C candidate's identity is provably anchored to the frozen 7B evaluation
semantics rather than silently redefining them.
"""

from __future__ import annotations

import hashlib
import json

from ...config import ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT
from ..geospatial.weather.base import T0Precision, WeatherTemporalRole
from ..geospatial.weather.era5 import WEATHER_MODEL
from ..hazard.meteorology import MeteorologySpatialMode
from .evaluation_protocol_7b import baseline_evaluation_protocol_hash

# Checkpoint 7C.1 Part 4: "7C.1" (this module's original version) is kept
# ONLY as `LEGACY_EVALUATION_PROTOCOL_VERSION_7C` for the identity-only
# remap (Part 5) -- `EVALUATION_PROTOCOL_VERSION_7C` below is the current,
# hardened identity.
LEGACY_EVALUATION_PROTOCOL_VERSION_7C = "7C.1"
EVALUATION_PROTOCOL_VERSION_7C = "7C.2"

# Part 7: primary weather role is ALWAYS the pre-t0 retrospective proxy --
# never REALIZED_FUTURE_REANALYSIS, never LIVE_OPERATIONAL, in primary
# candidate development.
PRIMARY_WEATHER_TEMPORAL_ROLE_7C = WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY.value
WEATHER_MODEL_7C = WEATHER_MODEL
STRICT_OPERATIONAL_AVAILABILITY_7C = False  # primary path never uses the ERA5T lag-filter sensitivity mode

# Checkpoint 7C.1 Part 3: 24h was set in code BEFORE the 7C candidate
# registry was ever evaluated against real development targets, and was
# never changed in response to 7C candidate performance -- frozen here,
# never tuned (never 12h/48h/72h). A future change to this value creates
# a NEW scientific protocol/candidate identity (it changes
# `evaluation_protocol_hash_7c()`, hence every candidate_id) and can
# never silently reuse these 7C results.
WEATHER_LOOKBACK_HOURS_7C = 24
WEATHER_LOOKBACK_HOURS_7C_STATUS = "FROZEN_7C_PREDECLARED_WEATHER_LOOKBACK_HOURS"

# Checkpoint 7C.1 Part 6: proven against the real 579-origin FIT_DEVELOPMENT
# universe (t0_precision_audit.json: 579 DATE_ONLY, 0 TIMESTAMP, 0 UNKNOWN)
# -- this corpus's `outbreak_start_date`/`proxy_availability_date` fields
# are calendar dates only, never exact timestamps, so a single fixed
# T0Precision policy is scientifically valid for the whole universe.
T0_PRECISION_POLICY_7C = T0Precision.DATE_ONLY.value

# Checkpoint 7C.1 Part 8: ONE real ERA5 observation per forecast origin,
# sampled at the AOI center and held uniform across that origin's entire
# local evaluation domain -- NEVER `SPATIALLY_RESOLVED_REAL` (no
# independent per-cell sampling exists). Per-source DIRECTIONAL
# modulation still varies within the domain because each source keeps
# its own `t_hat_east`/`t_hat_north` geometry to each cell -- only the
# wind VECTOR itself is spatially uniform, never the anisotropy factor.
METEOROLOGY_SPATIAL_MODE_7C = MeteorologySpatialMode.AOI_CENTER_UNIFORM_REAL_PROXY.value
# Records which existing AOI-center rule is reused (`assembler._aoi_center`,
# Checkpoint 6A Part 10: trigger-source centroid, falling back to
# all-active-source centroid) -- 7C never re-derives this rule.
AOI_CENTER_RULE_VERSION_7C = "6A.ASSEMBLER_AOI_CENTER.1"

# Checkpoint 7C.1 Part 4: the real, `active_window_days`-based
# eligible-source window -- confirmed NOT already bound anywhere inside
# `model_development_protocol_hash_7a62` (Checkpoint 7A/7B's own protocol
# hash never included it), so it must be bound explicitly here rather
# than assumed transitively covered by the 7B parent hash.
ACTIVE_SOURCE_WINDOW_DAYS_7C = ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT

# Part 8-9: anisotropy is computed from the EXISTING
# `services.hazard.anisotropy` primitive -- this constant records ITS
# version/identity for candidate-id binding, never a re-implementation.
ANISOTROPY_IMPLEMENTATION_VERSION_7C = "6C.HAZARD_ANISOTROPY.1"

# Checkpoint 7C.1 Part 9: `ANGULAR_NORMALIZED(k) = MODULATING(k) / I0(k)`
# -- a single positive per-candidate constant rescaling every cell in an
# origin's domain identically. `AREA_WEIGHTED_TARGET_PERCENTILE` (and
# therefore TOP5/TOP10/rank) is invariant to any such rescaling, so the
# two modes are PROVABLY rank-equivalent at every shared kappa under this
# metric -- confirmed both mathematically and empirically (byte-identical
# metrics, small sanity subset AND the full real 579-origin run). This is
# never resolved by picking a "preferred" mode from the data.
ANISOTROPY_MODE_NOT_IDENTIFIABLE_UNDER_RANK_METRIC = "ANISOTROPY_MODE_NOT_IDENTIFIABLE_UNDER_RANK_METRIC"

WEATHER_INPUT_UNAVAILABLE = "WEATHER_INPUT_UNAVAILABLE"

# Checkpoint 7C.1 Part 4: moved here (canonical, acyclic home) from
# `candidate_registry_7c.py` so this module's identity payload can bind
# it directly -- the real, persisted Checkpoint 7B frozen_spec_hash
# (`local_data/model_development/7b/final_frozen_baseline_model_spec.json`),
# never manufactured. `candidate_registry_7c.py` re-imports it from here.
PARENT_7B_FROZEN_SPEC_HASH = "6bb8f67a7bc1188be324bf0a58e2399ed87df619b96c5a0db0ba5a3191794950"

# Part 5/6/11/12: factors structurally excluded from every 7C primary
# candidate -- see FACTOR_READINESS_AUDIT for the underlying evidence.
HOST_FACTOR_STATUS_7C = "NOT_PRIMARY_ELIGIBLE_FROM_7B_COVERAGE_AUDIT"
SOURCE_STRENGTH_STATUS_7C = "NOT_SELECTED"
ENVIRONMENTAL_SUITABILITY_STATUS_7C = "NOT_YET_SCIENTIFICALLY_DEFINED"
WATER_CONTEXT_STATUS_7C = "NOT_YET_SCIENTIFICALLY_DEFINED"


PRIMARY_SELECTION_ELIGIBLE = "PRIMARY_SELECTION_ELIGIBLE"
PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE = "PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE"
PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE = "PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE"
PRIMARY_SELECTION_PARTIAL_COVERAGE_OTHER_CAUSE = "PRIMARY_SELECTION_PARTIAL_COVERAGE_OTHER_CAUSE"
WIND_CANDIDATES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_WEATHER_SUPPORT = (
    "WIND_CANDIDATES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_WEATHER_SUPPORT"
)


def classify_selection_note_7c(*, candidate_families_by_id: dict, eligible_candidate_ids, ineligible_candidate_ids) -> str:
    """Part 17: precise wording for why (if at all) some 7C candidates were
    excluded from primary selection -- mirrors 7B's
    `classify_selection_note` exactly, generalized from B0/B1B2 to
    C0/CW. Ineligibility here always traces to real ERA5 weather-fetch
    gaps for specific origins (`WEATHER_INPUT_UNAVAILABLE`), never to a
    predictive-performance judgement."""
    if not eligible_candidate_ids:
        return PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE
    if not ineligible_candidate_ids:
        return ""
    from .candidate_registry_7c import C0_FAMILY, CW_FAMILY

    ineligible_families = {candidate_families_by_id[cid] for cid in ineligible_candidate_ids}
    c0_ids = {cid for cid, fam in candidate_families_by_id.items() if fam == C0_FAMILY}
    all_ineligible_are_wind = ineligible_families <= {CW_FAMILY}
    all_c0_eligible = c0_ids <= set(eligible_candidate_ids)
    if all_ineligible_are_wind and all_c0_eligible:
        return WIND_CANDIDATES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_WEATHER_SUPPORT
    return PRIMARY_SELECTION_PARTIAL_COVERAGE_OTHER_CAUSE


def _evaluation_protocol_dict_7c(*, version: str) -> dict:
    d = {
        "evaluation_protocol_version_7c": version,
        "parent_7b_evaluation_protocol_hash": baseline_evaluation_protocol_hash(),
        "primary_weather_temporal_role": PRIMARY_WEATHER_TEMPORAL_ROLE_7C,
        "weather_model": WEATHER_MODEL_7C,
        "strict_operational_availability": STRICT_OPERATIONAL_AVAILABILITY_7C,
        "anisotropy_implementation_version": ANISOTROPY_IMPLEMENTATION_VERSION_7C,
        "host_factor_status": HOST_FACTOR_STATUS_7C,
        "source_strength_status": SOURCE_STRENGTH_STATUS_7C,
        "environmental_suitability_status": ENVIRONMENTAL_SUITABILITY_STATUS_7C,
        "water_context_status": WATER_CONTEXT_STATUS_7C,
    }
    if version != LEGACY_EVALUATION_PROTOCOL_VERSION_7C:
        # Checkpoint 7C.1 Part 4: identity hardening -- binds every
        # numerical weather/temporal/spatial semantic that could silently
        # change 7C's real scored output without changing candidate_id.
        # None of these change the ACTUAL numerical values 7C computes
        # (lookback was already 24h, t0 precision was already DATE_ONLY,
        # AOI center/anisotropy code is unchanged) -- this is identity
        # hardening only (Part 5: IDENTITY_ONLY_7C_RESULT_REMAP).
        d["parent_7b_frozen_spec_hash"] = PARENT_7B_FROZEN_SPEC_HASH
        d["weather_lookback_hours"] = WEATHER_LOOKBACK_HOURS_7C
        d["weather_lookback_hours_status"] = WEATHER_LOOKBACK_HOURS_7C_STATUS
        d["t0_precision_policy"] = T0_PRECISION_POLICY_7C
        d["meteorology_spatial_mode"] = METEOROLOGY_SPATIAL_MODE_7C
        d["aoi_center_rule_version"] = AOI_CENTER_RULE_VERSION_7C
        d["active_source_window_days"] = ACTIVE_SOURCE_WINDOW_DAYS_7C
    return d


def evaluation_protocol_dict_7c() -> dict:
    return _evaluation_protocol_dict_7c(version=EVALUATION_PROTOCOL_VERSION_7C)


def evaluation_protocol_hash_7c() -> str:
    canonical = json.dumps(evaluation_protocol_dict_7c(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def legacy_evaluation_protocol_hash_7c() -> str:
    """Checkpoint 7C.1 Part 5: the PRE-hardening (7C.1) evaluation
    protocol hash -- preserved ONLY so `candidate_registry_7c`'s
    `build_identity_only_result_remap_7c` can prove a deterministic
    mapping from the already-completed real run's candidate ids to the
    hardened ones. Never used to build the live registry."""
    canonical = json.dumps(_evaluation_protocol_dict_7c(version=LEGACY_EVALUATION_PROTOCOL_VERSION_7C), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
