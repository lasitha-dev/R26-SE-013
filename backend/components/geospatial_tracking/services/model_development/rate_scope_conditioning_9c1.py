"""Checkpoint 9C.1: post-freeze rate-scope conditioning diagnostic.

**Purpose** (Part 0): investigates ONE methodological question --- what
conditioning is induced in the apparent-rate dataset by using the same
fixed 25-km operational local evaluation envelope for every D1-D7 lead
when `v_obs = d_min / lead_days`? This is
`POST_FREEZE_RATE_SCOPE_CONDITIONING_DIAGNOSTIC`, never rate retuning,
alternate S0 selection, new model fitting, held-out/Sri Lanka
evaluation, scope optimization, or radius selection. The frozen 9B
rate result is never changed by anything in this module.

**READ-ONLY, dependency-minimal** (Part 3): every function here
operates on rows already parsed from the persisted Checkpoint 9A CSV
(`rate_origin_target_observations_9a.csv`) -- nothing here queries the
outbreak database, recomputes geodesic distance, rebuilds
`d_min`/`v_obs` from source data, or reruns the 9B bootstrap. No import
of `SQLiteOutbreakRepository`, `build_forecast_origin_ledger`,
`build_forecast_targets`, `get_eligible_sources`,
`derive_fit_development_rate_observations`, `distance_km`,
`pyproj.Geod`, `classify_target_primary_scope`, any weather service, or
any direction evaluator anywhere in this module.

**Theoretical ceiling is a mathematical consequence of the frozen
inclusion rule, never derived from observed data** (Part 1):
`theoretical_ceiling_km_day(lead_days) =
PRIMARY_LOCAL_EVALUATION_DISTANCE_KM / lead_days` -- the 25km constant
is imported directly from the frozen `local_evaluation_scope` module,
never a second hardcoded copy.

**No alternate pooled S0 estimator anywhere in this module** (Part
12): no function here computes a competing S0 using all 3947 rows,
OUTSIDE rows, an alternate radius, EXACT-only GPS, zero-excluded rows,
or an individual lead day as a replacement estimator. Lead-day
descriptive distributions (`within_rate_distribution_by_lead`) are
diagnostic only -- they never feed back into a new pooled estimate.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from ..forecast_target import PRIMARY_HORIZON_DAYS
from .local_evaluation_scope import PRIMARY_LOCAL_EVALUATION_DISTANCE_KM

WITHIN_SCOPE_STATUS_9C1 = "WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE"
OUTSIDE_SCOPE_STATUS_9C1 = "OUTSIDE_DECLARED_LOCAL_RATE_SCOPE"

PRIMARY_HORIZON_RANGE_9C1 = tuple(range(1, PRIMARY_HORIZON_DAYS + 1))

CEILING_NUMERICAL_TOLERANCE_9C1 = 1e-6

V_OBS_FORMULA_9C1 = "v_obs = d_min_km / lead_days"
THEORETICAL_CEILING_FORMULA_9C1 = "theoretical_max_included_rate_km_day(lead_days) = 25 / lead_days"

DIAGNOSTIC_PURPOSE_9C1 = "POST_FREEZE_RATE_SCOPE_CONDITIONING_DIAGNOSTIC"
NOT_RATE_RETUNING_9C1 = (
    "NOT_RATE_RETUNING_NOT_ALTERNATE_S0_SELECTION_NOT_NEW_MODEL_FITTING_NOT_HELD_OUT_OR_SRI_LANKA_EVALUATION_"
    "NOT_SCOPE_OPTIMIZATION_NOT_RADIUS_SELECTION"
)
NO_ALTERNATE_S0_STATUS_9C1 = "NO_ALTERNATE_POOLED_S0_CALCULATED_IN_9C1"
HELD_OUT_FIREWALL_9C1 = "HELD_OUT_RATE_NOT_INSPECTED_IN_9C1"
SRI_LANKA_FIREWALL_9C1 = "SRI_LANKA_RATE_NOT_INSPECTED_IN_9C1"
GPS_QUALITY_AUDIT_SEMANTICS_9C1 = "DESCRIPTIVE_ONLY_NO_INCLUSION_CHANGE_NO_RE_ESTIMATION"

RATE_SCOPE_CONDITIONING_LABEL_9C1 = "RATE_SCOPE_CONDITIONING"
LEAD_DEPENDENT_TRUNCATION_MECHANISM_LABEL_9C1 = "LEAD_DEPENDENT_TRUNCATION_MECHANISM"

RATE_ESTIMAND_CONDITIONING_9C1 = (
    "D1_D7_TARGET_EVENT_APPARENT_RATE_CONDITIONAL_ON_AT_LEAST_ONE_VALID_25KM_LOCAL_SCOPE_OBSERVATION_"
    "UNDER_RETROSPECTIVE_PROXY"
)
RATE_ESTIMAND_STATEMENT_9C1 = (
    "The frozen S0 is a development-derived apparent historical local-rate summary conditional on the "
    "predeclared 25-km operational local-scope inclusion mechanism. Because d_min <= 25 km is applied "
    "across D1-D7, the included origin-target apparent rates have lead-dependent upper bounds of 25/h km/day."
)
NOMINAL_REACH_D7_INTERPRETATION_NOTE_9C1 = (
    "D7 nominal reach is a deterministic visualization extrapolation from the pooled frozen S0. It exceeds "
    "the 25-km operational envelope even though the empirical rate dataset was conditioned by that 25-km "
    "inclusion rule. It is therefore not evidence that a D7 epidemic front was empirically validated beyond 25 km."
)
GPS_QUALITY_LIMITATION_9C1 = (
    "The apparent-rate distribution is materially affected by coordinate and reporting quality; "
    "UNKNOWN/APPROXIMATE location quality is retained rather than selectively removed after rate values "
    "were observed."
)


def theoretical_ceiling_km_day(lead_days: int) -> float:
    """Part 1. A mathematical consequence of the frozen `d_min <= 25km`
    inclusion rule, never derived from observed v_obs values."""
    return PRIMARY_LOCAL_EVALUATION_DISTANCE_KM / lead_days


def theoretical_ceiling_table() -> dict:
    return {str(h): theoretical_ceiling_km_day(h) for h in PRIMARY_HORIZON_RANGE_9C1}


def load_csv_rows(csv_path: Path) -> list[dict]:
    """Part 3/4. Plain `csv.DictReader` over an already-persisted file
    -- no DB, no distance recomputation."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_target_level_ids(csv_path: Path) -> set:
    with csv_path.open(newline="", encoding="utf-8") as f:
        return {row["target_event_id"] for row in csv.DictReader(f)}


def field_completeness_by_scope(rows: list[dict]) -> dict:
    """Part 4. Reports, separately for WITHIN/OUTSIDE/unresolved, how
    many rows have a non-blank value for each required field. Never
    assumes OUTSIDE rows have a usable v_obs."""
    fields = (
        "lead_days", "d_min_km", "v_obs_km_day", "target_event_id",
        "target_gps_quality", "nearest_source_gps_quality", "scope_status", "observation_status",
    )
    buckets = {
        "WITHIN": [r for r in rows if r["scope_status"] == WITHIN_SCOPE_STATUS_9C1],
        "OUTSIDE": [r for r in rows if r["scope_status"] == OUTSIDE_SCOPE_STATUS_9C1],
        "UNRESOLVED": [r for r in rows if r["scope_status"] not in (WITHIN_SCOPE_STATUS_9C1, OUTSIDE_SCOPE_STATUS_9C1)],
    }
    return {
        bucket: {
            "n_rows": len(bucket_rows),
            "field_present_counts": {field: sum(1 for r in bucket_rows if r.get(field, "") != "") for field in fields},
        }
        for bucket, bucket_rows in buckets.items()
    }


def reconcile_by_lead_day(rows: list[dict]) -> dict:
    """Part 5. Per-lead within/outside/unresolved counts -- always
    counted from the real rows, never hardcoded."""
    result = {}
    for h in PRIMARY_HORIZON_RANGE_9C1:
        lead_rows = [r for r in rows if r["lead_days"] == str(h)]
        n_within = sum(1 for r in lead_rows if r["scope_status"] == WITHIN_SCOPE_STATUS_9C1)
        n_outside = sum(1 for r in lead_rows if r["scope_status"] == OUTSIDE_SCOPE_STATUS_9C1)
        n_total = len(lead_rows)
        n_unresolved = n_total - n_within - n_outside
        result[str(h)] = {
            "n_total_origin_target_rows": n_total,
            "n_within_25km": n_within,
            "n_outside_25km": n_outside,
            "n_unresolved": n_unresolved,
            "within_fraction": (n_within / n_total) if n_total else None,
            "outside_fraction": (n_outside / n_total) if n_total else None,
        }
    return result


def _linear_quantile_9c1(sorted_values: list[float], q: float) -> float:
    """Mirrors the frozen 9B linear-interpolation empirical quantile
    formula, applied independently here -- this function never imports
    or calls anything from `rate_s0_bootstrap_9b` (9C1-FIREWALL-04)."""
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    position = (n - 1) * q
    lower = int(position)
    upper = min(lower + 1, n - 1)
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def within_rate_distribution_by_lead(rows: list[dict]) -> dict:
    """Part 6. Descriptive only -- no clipping, no winsorization, no
    log transform, and never a new pooled estimator. Raises
    `AssertionError` (STOP) if any observed v_obs exceeds its
    theoretical ceiling beyond numerical tolerance -- that would mean
    the persisted scope classification and rate values are internally
    inconsistent."""
    result = {}
    for h in PRIMARY_HORIZON_RANGE_9C1:
        lead_within = [r for r in rows if r["lead_days"] == str(h) and r["scope_status"] == WITHIN_SCOPE_STATUS_9C1]
        values = sorted(float(r["v_obs_km_day"]) for r in lead_within)
        ceiling = theoretical_ceiling_km_day(h)
        if values and values[-1] > ceiling + CEILING_NUMERICAL_TOLERANCE_9C1:
            raise AssertionError(
                f"9C.1 Part 6 STOP: D{h} observed_max={values[-1]} exceeds theoretical ceiling={ceiling} "
                f"beyond tolerance -- persisted scope classification and rate values are inconsistent"
            )
        result[str(h)] = {
            "n_valid": len(values),
            "theoretical_max_included_rate_km_day": ceiling,
            "observed_min": values[0] if values else None,
            "observed_p25": _linear_quantile_9c1(values, 0.25) if values else None,
            "observed_median": _linear_quantile_9c1(values, 0.5) if values else None,
            "observed_p75": _linear_quantile_9c1(values, 0.75) if values else None,
            "observed_p95": _linear_quantile_9c1(values, 0.95) if values else None,
            "observed_max": values[-1] if values else None,
        }
    return result


def s0_vs_theoretical_ceiling(frozen_s0: float) -> dict:
    """Part 7. Compares the frozen S0 against each lead's theoretical
    ceiling -- never modifies S0."""
    return {
        str(h): {
            "theoretical_ceiling_km_day": theoretical_ceiling_km_day(h),
            "s0_below_or_equal_theoretical_ceiling": frozen_s0 <= theoretical_ceiling_km_day(h),
        }
        for h in PRIMARY_HORIZON_RANGE_9C1
    }


def target_event_inclusion_audit(rows: list[dict], frozen_target_ids: set) -> dict:
    """Part 8. Non-predictive appearance counts only -- never a
    recalculated target-level rate. Raises `AssertionError` (STOP) if
    the set of target_event_id with >=1 WITHIN observation does not
    exactly match the frozen `rate_target_level_readiness_9a.csv`
    target set."""
    all_ids: set = set()
    within_ids: set = set()
    outside_ids: set = set()
    per_target: dict = {}

    for r in rows:
        tid = r["target_event_id"]
        all_ids.add(tid)
        is_within = r["scope_status"] == WITHIN_SCOPE_STATUS_9C1
        is_outside = r["scope_status"] == OUTSIDE_SCOPE_STATUS_9C1
        if is_within:
            within_ids.add(tid)
        if is_outside:
            outside_ids.add(tid)
        entry = per_target.setdefault(tid, {
            "n_origin_appearances_total": 0, "n_within_appearances": 0, "n_outside_appearances": 0,
            "lead_days_total": [], "lead_days_within": [], "lead_days_outside": [],
        })
        lead = int(r["lead_days"])
        entry["n_origin_appearances_total"] += 1
        entry["lead_days_total"].append(lead)
        if is_within:
            entry["n_within_appearances"] += 1
            entry["lead_days_within"].append(lead)
        if is_outside:
            entry["n_outside_appearances"] += 1
            entry["lead_days_outside"].append(lead)

    for tid, entry in per_target.items():
        entry["included_in_frozen_S0_target_dataset"] = tid in frozen_target_ids

    if within_ids != frozen_target_ids:
        raise AssertionError(
            "9C.1 Part 8 STOP: target_event_id set with >=1 WITHIN observation does not exactly match "
            "rate_target_level_readiness_9a.csv"
        )

    only_outside = outside_ids - within_ids
    only_within = within_ids - outside_ids
    mixed = within_ids & outside_ids

    return {
        "n_unique_target_event_id_all_rows": len(all_ids),
        "n_unique_target_event_id_with_at_least_one_WITHIN": len(within_ids),
        "n_unique_target_event_id_only_OUTSIDE": len(only_outside),
        "n_unique_target_event_id_mixed_WITHIN_and_OUTSIDE": len(mixed),
        "n_unique_target_event_id_only_WITHIN": len(only_within),
        "target_event_ids_match_frozen_s0_dataset": True,
        "per_target_event": per_target,
    }


def gps_quality_by_lead_audit(rows: list[dict]) -> dict:
    """Part 11. Descriptive only -- changes no inclusion, excludes
    nothing, re-estimates nothing."""
    within_rows = [r for r in rows if r["scope_status"] == WITHIN_SCOPE_STATUS_9C1]
    by_lead = {}
    for h in PRIMARY_HORIZON_RANGE_9C1:
        lead_within = [r for r in within_rows if r["lead_days"] == str(h)]
        by_lead[str(h)] = {
            "n": len(lead_within),
            "target_gps_quality_counts": dict(Counter(r["target_gps_quality"] for r in lead_within)),
            "nearest_source_gps_quality_counts": dict(Counter(r["nearest_source_gps_quality"] for r in lead_within)),
        }

    zero_rows = [r for r in rows if r["is_zero_distance"] == "True"]
    zero_target_ids = {r["target_event_id"] for r in zero_rows}
    zero_gps = Counter(r["target_gps_quality"] for r in zero_rows)
    zero_collision = Counter(r["target_coordinate_collision_status"] for r in zero_rows)

    return {
        "by_lead_within_primary_valid_rows": by_lead,
        "zero_distance_diagnostic": {
            "n_zero_distance_rows": len(zero_rows),
            "n_unique_target_events": len(zero_target_ids),
            "all_zero_distance_target_gps_quality_unknown": (set(zero_gps.keys()) == {"UNKNOWN"}) if zero_rows else None,
            "all_zero_distance_collision_status_unknown": (set(zero_collision.keys()) == {"UNKNOWN"}) if zero_rows else None,
            "target_gps_quality_counts": dict(zero_gps),
            "collision_status_counts": dict(zero_collision),
        },
    }
