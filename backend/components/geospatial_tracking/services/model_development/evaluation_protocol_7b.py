"""Checkpoint 7B (finalization hardening) Part 8, Part 4: the canonical
home for EVALUATION-semantics constants (never candidate-parameter
constants -- those stay in `baseline_registry.py`/`candidate_registry_7b.py`)
plus `BASELINE_EVALUATION_PROTOCOL_HASH`, which binds every candidate's
scientific identity to HOW it was scored/ranked/selected, not merely
WHICH baseline/kernel/scale/host-transform it is.

The original candidate-identity design (Checkpoint 7B first pass) hashed
only the candidate's own four parameters plus registry versions --
changing the percentile definition, tie semantics, area weighting field,
TOP5/TOP10 thresholds, aggregation rule, horizon, primary scope distance,
or the coverage-eligibility rule (Part 4, below) would have silently left
every `candidate_id` unchanged. This module's hash now participates in
`candidate_registry_7b._candidate_id` so any of those changes visibly
changes every candidate's scientific identity.

This module intentionally has NO dependency on `baseline_scoring.py` or
`candidate_registry_7b.py` (those modules depend on THIS one, for the
constants below) -- keeps the import graph acyclic.
"""

from __future__ import annotations

import hashlib
import json

from ..forecast_target import PRIMARY_HORIZON_DAYS
from .local_evaluation_scope import (
    PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
    PRIMARY_LOCAL_EVALUATION_DISTANCE_STATUS,
    PRIMARY_SCOPE_TRUTH_METHOD,
)
from .selection_7b import FOLD_AGGREGATION_RULE, PRIMARY_SELECTION_METRIC, SELECTION_PROTOCOL_VERSION, TIE_BREAK_ORDER

BASELINE_EVALUATION_PROTOCOL_VERSION = "7B.2"

# -- score/ranking semantics (canonical home; baseline_scoring.py imports
# these rather than redefining them, to keep the import graph acyclic) --
STATIC_T0_SPATIAL_BASELINE = "STATIC_T0_SPATIAL_BASELINE"
AREA_WEIGHTED_MIDRANK = "AREA_WEIGHTED_MIDRANK"
AREA_WEIGHTED_METRIC_VERSION = "7B.1"
AREA_WEIGHT_FIELD = "domain_overlap_area_km2"
TOP5_THRESHOLD_PERCENTILE = 95.0
TOP10_THRESHOLD_PERCENTILE = 90.0

# -- Part 4: complete-domain primary-selection coverage eligibility --
PRIMARY_SELECTION_ELIGIBLE = "PRIMARY_SELECTION_ELIGIBLE"
PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE = "PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE"
INCOMPLETE_DOMAIN_DIAGNOSTIC = "INCOMPLETE_DOMAIN_DIAGNOSTIC"
HOST_DEPENDENT_BASELINES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_DOMAIN_SUPPORT = (
    "HOST_DEPENDENT_BASELINES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_DOMAIN_SUPPORT"
)
PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE = "PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE"
PRIMARY_SELECTION_PARTIAL_COVERAGE_OTHER_CAUSE = "PRIMARY_SELECTION_PARTIAL_COVERAGE_OTHER_CAUSE"
# a tiny SOFTWARE floating-point-zero tolerance ONLY -- never a biological/
# statistical missingness percentage threshold (Part 4: never 5%/10%/etc).
SOFTWARE_ZERO_AREA_TOLERANCE_KM2 = 1e-6
COVERAGE_ELIGIBILITY_RULE_VERSION = "7B.2"

HOST_DEPENDENT_BASELINE_FAMILIES = ("B1_HOST_DISTANCE_LOG1P", "B2_HOST_DISTANCE_ECDF")
B0_FAMILY = "B0_DISTANCE_ONLY"


def classify_selection_note(*, candidate_families_by_id: dict, eligible_candidate_ids, ineligible_candidate_ids) -> str:
    """Checkpoint 7B.1.1 Part 7: precise wording for WHY (if at all) some
    candidates were excluded from the primary selection comparison.
    `candidate_families_by_id`: `{candidate_id: baseline_family}` for
    every candidate in the registry.

    - `""` if every candidate is eligible (nothing to explain).
    - `PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE` if NO candidate
      is eligible -- the caller must stop, never call `select_candidate`
      with an empty metrics dict.
    - `HOST_DEPENDENT_BASELINES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_DOMAIN_SUPPORT`
      ONLY when every ineligible candidate is B1/B2 AND every B0
      candidate remains eligible -- the one scenario this specific
      wording is scientifically accurate for.
    - `PRIMARY_SELECTION_PARTIAL_COVERAGE_OTHER_CAUSE` for any other
      partial-ineligibility pattern (e.g. an unexpectedly incomplete B0
      candidate) -- never mislabeled as a host-dependence story."""
    if not eligible_candidate_ids:
        return PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE
    if not ineligible_candidate_ids:
        return ""
    ineligible_families = {candidate_families_by_id[cid] for cid in ineligible_candidate_ids}
    b0_ids = {cid for cid, fam in candidate_families_by_id.items() if fam == B0_FAMILY}
    all_ineligible_are_host_dependent = ineligible_families <= set(HOST_DEPENDENT_BASELINE_FAMILIES)
    all_b0_eligible = b0_ids <= set(eligible_candidate_ids)
    if all_ineligible_are_host_dependent and all_b0_eligible:
        return HOST_DEPENDENT_BASELINES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_DOMAIN_SUPPORT
    return PRIMARY_SELECTION_PARTIAL_COVERAGE_OTHER_CAUSE


def assess_candidate_coverage_eligibility(*, n_target_score_unavailable_rows: int, max_missing_domain_area_km2: float) -> str:
    """Part 4: `PRIMARY_SELECTION_ELIGIBLE` only when a candidate has ZERO
    `TARGET_SCORE_UNAVAILABLE` rows AND no scientifically missing
    evaluation-domain area beyond `SOFTWARE_ZERO_AREA_TOLERANCE_KM2`.
    `max_missing_domain_area_km2`: the largest per-origin
    `missing_domain_area_km2` this candidate produced across every
    validation origin it was scored against. Never an invented
    percentage cutoff -- a single km^2 of real missing coverage is
    enough to make a candidate ineligible, exactly as a single
    `TARGET_SCORE_UNAVAILABLE` row is."""
    if n_target_score_unavailable_rows > 0:
        return PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE
    if max_missing_domain_area_km2 > SOFTWARE_ZERO_AREA_TOLERANCE_KM2:
        return PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE
    return PRIMARY_SELECTION_ELIGIBLE


def baseline_evaluation_protocol_dict() -> dict:
    return {
        "baseline_evaluation_protocol_version": BASELINE_EVALUATION_PROTOCOL_VERSION,
        "score_temporal_semantics": STATIC_T0_SPATIAL_BASELINE,
        "primary_metric_name": "AREA_WEIGHTED_TARGET_PERCENTILE",
        "area_weighted_metric_version": AREA_WEIGHTED_METRIC_VERSION,
        "tie_semantics": AREA_WEIGHTED_MIDRANK,
        "area_weight_field": AREA_WEIGHT_FIELD,
        "top5_threshold_percentile": TOP5_THRESHOLD_PERCENTILE,
        "top10_threshold_percentile": TOP10_THRESHOLD_PERCENTILE,
        "fold_aggregation_rule": FOLD_AGGREGATION_RULE,
        "primary_selection_metric": PRIMARY_SELECTION_METRIC,
        "selection_protocol_version": SELECTION_PROTOCOL_VERSION,
        "tie_break_order": list(TIE_BREAK_ORDER),
        "primary_horizon_days": PRIMARY_HORIZON_DAYS,
        "primary_local_evaluation_distance_km": PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
        "primary_local_evaluation_distance_status": PRIMARY_LOCAL_EVALUATION_DISTANCE_STATUS,
        "primary_scope_truth_method": PRIMARY_SCOPE_TRUTH_METHOD,
        "coverage_eligibility_rule_version": COVERAGE_ELIGIBILITY_RULE_VERSION,
        "software_zero_area_tolerance_km2": SOFTWARE_ZERO_AREA_TOLERANCE_KM2,
    }


def baseline_evaluation_protocol_hash() -> str:
    canonical = json.dumps(baseline_evaluation_protocol_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
