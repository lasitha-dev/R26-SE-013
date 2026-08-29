"""Checkpoint 9A Part 25: real FIT_DEVELOPMENT apparent local
spread-front rate READINESS run.

Not a pytest suite. Real DB access over the REAL, runtime-derived
`FIT_DEVELOPMENT` origin universe -- never hardcoded. Run directly:

    python -m components.geospatial_tracking.smoke_tests.run_rate_readiness_9a

**DATA READINESS ONLY**: derives `d_min`/`lead_days`/`v_obs` for every
valid FIT_DEVELOPMENT (origin, target) observation and reports
diagnostic distributions (labelled `DEVELOPMENT_RATE_DATASET_DIAGNOSTIC`).
Does NOT compute or freeze the final S0 aggregate median as the system
rate -- that is Checkpoint 9B. Does NOT touch held-out or Sri Lanka
origins. Does NOT compute nominal reach.
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import DEFAULT_SQLITE_DB_PATH
from ..repositories.sqlite_repository import SQLiteOutbreakRepository
from ..services.forecast_origin import build_forecast_origin_ledger
from ..services.geospatial.raster import LOCAL_GIS_CACHE_DIR
from ..services.model_development.evaluation_protocol_7c import ACTIVE_SOURCE_WINDOW_DAYS_7C
from ..services.model_development.local_evaluation_scope import (
    LOCAL_SCOPE_UNRESOLVED,
    WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE,
)
from ..services.model_development.rate_protocol_9a import (
    DISEASE_9A,
    OUTSIDE_LOCAL_RATE_SCOPE_LABEL_9A,
    rate_readiness_protocol_dict_9a,
    rate_readiness_protocol_hash_9a,
)
from ..services.model_development.rate_readiness_9a import (
    EXCLUDED_LEAD_DAYS_NOT_POSITIVE,
    ORIGIN_NO_ELIGIBLE_SOURCE,
    ORIGIN_READY,
    VALID,
    derive_fit_development_rate_observations,
    target_level_medians,
    valid_observations,
)
from ..services.model_fitting_exposure import fit_development_origins

LOCAL_DATA_ROOT = LOCAL_GIS_CACHE_DIR.parent
LOCAL_OUT_DIR = LOCAL_DATA_ROOT / "model_development" / "9a_rate"


def _percentiles(values: list[float]) -> dict:
    if not values:
        return {"min": None, "p25": None, "median": None, "p75": None, "p95": None, "max": None, "n": 0}
    s = sorted(values)
    n = len(s)

    def _pct(p: float) -> float:
        if n == 1:
            return s[0]
        idx = p * (n - 1)
        lo, hi = int(idx), min(int(idx) + 1, n - 1)
        frac = idx - lo
        return s[lo] + (s[hi] - s[lo]) * frac

    return {"min": s[0], "p25": _pct(0.25), "median": statistics.median(s), "p75": _pct(0.75), "p95": _pct(0.95), "max": s[-1], "n": n}


def _count(values) -> dict:
    counts: dict = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return counts


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


if __name__ == "__main__":
    protocol_dict = rate_readiness_protocol_dict_9a()
    protocol_hash = rate_readiness_protocol_hash_9a()
    print(f"Checkpoint 9A protocol frozen. rate_readiness_protocol_hash_9a = {protocol_hash}")

    start_time = datetime.now(timezone.utc).isoformat()
    t_start = time.monotonic()
    db_path = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
    repo = SQLiteOutbreakRepository(db_path)

    all_origins = build_forecast_origin_ledger(repo, disease=DISEASE_9A)
    dev_origins = fit_development_origins(all_origins)  # real, runtime-derived -- never hardcoded
    print(f"Real FIT_DEVELOPMENT universe (runtime-derived): {len(dev_origins)} origins")

    outcomes = derive_fit_development_rate_observations(repo, dev_origins, active_window_days=ACTIVE_SOURCE_WINDOW_DAYS_7C)
    exit_status = "COMPLETED_SUCCESSFULLY"
    end_time = datetime.now(timezone.utc).isoformat()
    runtime_seconds = time.monotonic() - t_start

    n_origins_ready = sum(1 for o in outcomes.values() if o.status == ORIGIN_READY)
    n_origins_no_source = sum(1 for o in outcomes.values() if o.status == ORIGIN_NO_ELIGIBLE_SOURCE)
    n_raw_target_rows = sum(o.n_raw_target_rows for o in outcomes.values())
    n_not_risk_eligible = sum(o.n_not_risk_eligible_excluded for o in outcomes.values())
    n_after_dedup = sum(o.n_after_dedup for o in outcomes.values())

    all_obs = [obs for o in outcomes.values() for obs in o.observations]
    n_within = sum(1 for obs in all_obs if obs.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE)
    n_outside = sum(1 for obs in all_obs if obs.scope_status == OUTSIDE_LOCAL_RATE_SCOPE_LABEL_9A)
    n_unresolved_scope = sum(1 for obs in all_obs if obs.scope_status == LOCAL_SCOPE_UNRESOLVED)

    n_valid = sum(1 for obs in all_obs if obs.observation_status == VALID)
    n_excluded_lead_leq_0 = sum(1 for obs in all_obs if obs.observation_status == EXCLUDED_LEAD_DAYS_NOT_POSITIVE)

    target_gps_counts = _count(obs.target_gps_quality for obs in all_obs)
    source_gps_counts_nearest = _count(obs.nearest_source_gps_quality for obs in all_obs if obs.nearest_source_gps_quality is not None)
    source_gps_counts_all = _count(q for o in outcomes.values() for q in o.source_gps_qualities)
    source_availability_counts_all = _count(q for o in outcomes.values() for q in o.source_availability_qualities)

    zero_distance_count = sum(1 for obs in all_obs if obs.is_zero_distance)

    valid = valid_observations(outcomes)
    lead_day_counts = _count(obs.lead_days for obs in valid)

    target_medians = target_level_medians(outcomes)
    n_unique_targets = len(target_medians)

    obs_per_target: dict = {}
    for obs in valid:
        obs_per_target[obs.target_event_id] = obs_per_target.get(obs.target_event_id, 0) + 1
    obs_per_target_dist = _percentiles([float(v) for v in obs_per_target.values()])

    episode_v_obs_values = [obs.v_obs_km_day for obs in valid]
    target_level_values = list(target_medians.values())

    # Checkpoint 9A.1: no arbitrary N-sufficiency cutoff (no predeclared/
    # literature justification exists for any threshold, including the
    # prior N=10). Sample size is reported as-is; Checkpoint 9B's
    # predeclared bootstrap (unique target_event_id, seed 42, 1000
    # resamples, 95% percentile interval) quantifies sampling
    # uncertainty instead of a threshold verdict.
    sample_size_status = "SAMPLE_SIZE_REPORTED_WITHOUT_ARBITRARY_SUFFICIENCY_THRESHOLD"

    readiness_audit = {
        "protocol_hash_9a": protocol_hash,
        "n_fit_development_origins_inspected": len(dev_origins),
        "n_origins_with_eligible_sources": n_origins_ready,
        "n_origins_without_eligible_sources": n_origins_no_source,
        "n_raw_future_d1_d7_target_rows": n_raw_target_rows,
        "n_excluded_not_risk_target_eligible": n_not_risk_eligible,
        "n_deduplicated_origin_target_observations": n_after_dedup,
        "n_within_primary_local_scope": n_within,
        "n_outside_local_scope": n_outside,
        "n_unresolved_scope": n_unresolved_scope,
        "n_valid_v_obs_observations": n_valid,
        "n_excluded_lead_leq_0": n_excluded_lead_leq_0,
        "n_unique_target_event_id": n_unique_targets,
        "observations_per_unique_target_distribution": obs_per_target_dist,
        "lead_day_counts_d1_d7": lead_day_counts,
        "zero_distance_observation_count": zero_distance_count,
        "sample_size_readiness_status": sample_size_status,
        "start_time": start_time, "end_time": end_time, "runtime_seconds": runtime_seconds, "exit_status": exit_status,
        "purpose": "DATA_READINESS_ONLY_NO_S0_COMPUTED_NO_NOMINAL_REACH_COMPUTED",
        "no_held_out_or_sri_lanka_origins_used": True,
    }

    quality_audit = {
        "target_gps_quality_counts": target_gps_counts,
        "nearest_source_gps_quality_counts": source_gps_counts_nearest,
        "all_eligible_source_gps_quality_counts": source_gps_counts_all,
        "all_eligible_source_availability_quality_counts": source_availability_counts_all,
    }

    diagnostic = {
        "label": "DEVELOPMENT_RATE_DATASET_DIAGNOSTIC",
        "episode_target_v_obs_km_day_distribution": _percentiles(episode_v_obs_values),
        "target_level_median_v_km_day_distribution": _percentiles(target_level_values),
        "note": "These are diagnostic distributions of the FIT_DEVELOPMENT-only readiness dataset. Neither distribution's median is the final system rate (S0) -- Checkpoint 9B computes and freezes S0.",
    }

    LOCAL_OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(LOCAL_OUT_DIR / "rate_protocol_9a.json", protocol_dict | {"rate_readiness_protocol_hash_9a": protocol_hash})
    _write_json(LOCAL_OUT_DIR / "rate_readiness_audit_9a.json", readiness_audit)
    _write_json(LOCAL_OUT_DIR / "rate_quality_audit_9a.json", quality_audit)
    _write_json(LOCAL_OUT_DIR / "rate_diagnostic_distributions_9a.json", diagnostic)

    with (LOCAL_OUT_DIR / "rate_origin_target_observations_9a.csv").open("w", newline="", encoding="utf-8") as f:
        import csv
        fieldnames = list(all_obs[0].as_dict().keys()) if all_obs else [
            "forecast_origin_id", "target_event_id", "target_id", "lead_days", "d_min_km", "v_obs_km_day",
            "scope_status", "observation_status", "nearest_source_id", "nearest_source_role",
            "target_gps_quality", "target_coordinate_collision_status", "nearest_source_gps_quality",
            "nearest_source_availability_quality", "is_zero_distance",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for obs in all_obs:
            writer.writerow(obs.as_dict())

    with (LOCAL_OUT_DIR / "rate_target_level_readiness_9a.csv").open("w", newline="", encoding="utf-8") as f:
        import csv
        writer = csv.DictWriter(f, fieldnames=["target_event_id", "target_level_median_v_km_day", "n_episode_observations"])
        writer.writeheader()
        for target_event_id, median_v in target_medians.items():
            writer.writerow({
                "target_event_id": target_event_id, "target_level_median_v_km_day": median_v,
                "n_episode_observations": obs_per_target.get(target_event_id, 0),
            })

    print(f"\nRuntime: {runtime_seconds:.1f}s")
    print(json.dumps(readiness_audit, indent=2, default=str))
    print("\n--- Quality audit ---")
    print(json.dumps(quality_audit, indent=2, default=str))
    print("\n--- Diagnostic distributions (DEVELOPMENT_RATE_DATASET_DIAGNOSTIC) ---")
    print(json.dumps(diagnostic, indent=2, default=str))
    print(f"\nWrote: {LOCAL_OUT_DIR}")
