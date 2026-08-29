"""Checkpoint 6D Part 27 / Checkpoint 6D.5 Parts 16, 19-21: development
reference audit reporting, global-readiness labeling, and the
development-universe clipping audit.

Reports distribution/provenance facts ONLY — never target capture,
AUC, accuracy, direction error, speed error, or any held-out
performance metric (this module has no access to any outcome field at
all).

**Honest global-readiness labeling (6D.5 Part 16, 20 / 6D.6 Part 12-13,
21)**: a small real smoke run over a handful of origins proves the
transformation machinery works — it does NOT, by itself, make the
resulting reference profile `GLOBAL_REFERENCE_PROFILE_READY`.
`build_development_reference_audit` only reports that label when:

1. every origin in the caller-supplied `total_fit_development_origin_ids`
   (the real, runtime-derived `FIT_DEVELOPMENT` universe — never a
   hardcoded count) has an ACTUALLY, SUCCESSFULLY constructed usable
   host-only snapshot (never merely "an origin ID appeared in the
   supplied list" — a `None`/blocked snapshot never counts as coverage);
2. no unexpected extra snapshot IDs exist outside that universe;
3. `reference_profile.status == COMPLETE_DIAGNOSTIC`;
4. zero reference-observation value conflicts; and
5. zero incompatible reference strata.

Otherwise it reports `GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY`,
honestly, with the real coverage numbers alongside it. No arbitrary
minimum-sample-size threshold is invented here.

**Readiness terminology (Part 21)**: `GLOBAL_REFERENCE_PROFILE_READY`
means the global `FIT_DEVELOPMENT` HOST REFERENCE DISTRIBUTION was
fully constructed under the frozen data/reference protocol. It does
NOT mean: a final host transform was selected, globally validated
predictive performance, a validated PISTES model, calibrated infection
probability, Sri-Lanka validation, or deployment readiness.
`reference_scope`/`selection_status` are always reported explicitly to
prevent that over-reading.
"""

from __future__ import annotations

from .contracts import GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY, GLOBAL_REFERENCE_PROFILE_READY, RAW_REAL_COMPONENT
from .host_transform import compute_host_density_total, transform_log1p_robust_reference_scale

REFERENCE_SCOPE_GLOBAL_FIT_DEVELOPMENT_HOST_REFERENCE = "GLOBAL_FIT_DEVELOPMENT_HOST_REFERENCE"
SELECTION_STATUS_UNFROZEN_DEVELOPMENT_CANDIDATE = "UNFROZEN_DEVELOPMENT_CANDIDATE"


def build_development_reference_audit(
    *,
    fit_development_origins: list,
    feature_snapshots_by_origin_id: dict,
    reference_profile,
    total_fit_development_origin_ids: list | None = None,
) -> dict:
    n_considered = len(fit_development_origins)
    countries = sorted({o.country for o in fit_development_origins})
    considered_ids = {o.forecast_origin_id for o in fit_development_origins}
    # Part 12: "available" means a SUCCESSFULLY constructed, usable
    # snapshot actually exists -- never merely that an origin ID appears
    # somewhere in the supplied list.
    available_ids = {oid for oid, snap in feature_snapshots_by_origin_id.items() if snap is not None}
    n_available = len(available_ids & considered_ids)
    n_blocked = n_considered - n_available

    if total_fit_development_origin_ids is not None:
        intended_ids = set(total_fit_development_origin_ids)
        usable_within_intended = available_ids & intended_ids
        extra_ids = available_ids - intended_ids  # unexpected extra IDs outside the intended universe
        universe_fully_available = (usable_within_intended == intended_ids) and not extra_ids
        reference_ok = (
            reference_profile.status == "COMPLETE_DIAGNOSTIC"
            and getattr(reference_profile, "n_reference_observation_conflicts", 0) == 0
            and getattr(reference_profile, "n_incompatible_strata_detected", 0) == 0
        )
        global_status = GLOBAL_REFERENCE_PROFILE_READY if (universe_fully_available and reference_ok) else GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY
        coverage_fraction = len(usable_within_intended) / len(intended_ids) if intended_ids else None
        n_extra_ids = len(extra_ids)
    else:
        global_status = GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY
        coverage_fraction = None
        n_extra_ids = 0

    return {
        "n_fit_development_origins_considered": n_considered,
        "countries_represented": countries,
        "n_feature_snapshots_available": n_available,
        "n_feature_snapshots_blocked_or_missing": n_blocked,
        "n_unexpected_extra_snapshot_ids": n_extra_ids,
        "unique_host_density_reference_observations": reference_profile.host_density_total_unique_observations,
        "host_density_raw_appearances": reference_profile.host_density_total_raw_appearances,
        "host_density_raw_distribution_quantiles": reference_profile.host_density_total_quantiles,
        "log1p_host_distribution_quantiles": reference_profile.host_density_total_log1p_quantiles,
        "weather_reference_observation_counts": reference_profile.weather_reference_observation_counts,
        "dataset_version_composition": reference_profile.dataset_version_composition,
        "landcover_comparability_composition": reference_profile.landcover_comparability_composition,
        "weather_model_composition": reference_profile.weather_model_composition,
        "dataset_compatibility_stratum": reference_profile.dataset_compatibility_stratum,
        "n_incompatible_strata_detected": reference_profile.n_incompatible_strata_detected,
        "n_reference_observation_conflicts": getattr(reference_profile, "n_reference_observation_conflicts", 0),
        "reference_profile_hash": reference_profile.reference_profile_hash(),
        "reference_profile_status": reference_profile.status,
        "global_reference_universe_coverage_fraction": coverage_fraction,
        "global_reference_profile_status": global_status,
        "reference_scope": REFERENCE_SCOPE_GLOBAL_FIT_DEVELOPMENT_HOST_REFERENCE,
        "selection_status": SELECTION_STATUS_UNFROZEN_DEVELOPMENT_CANDIDATE,
    }


def build_development_clipping_audit(
    *,
    feature_snapshots_by_origin_id: dict,
    reference_profile,
    transform_config,
) -> dict:
    """Checkpoint 6D.5 Part 21: LOG1P_ROBUST_REFERENCE_SCALE clipping
    counts over the REAL development universe actually processed — never
    generalized from one diagnostic cell. Grouped by country (via the
    forecast-origin id prefix `ORIGIN:<country>:...` when present) and
    by host dataset stratum. Never inspects held-out/Sri-Lanka data —
    only ever called with `FIT_DEVELOPMENT`-sourced snapshots."""
    lower = reference_profile.host_density_total_log1p_quantiles.get("lower")
    upper = reference_profile.host_density_total_log1p_quantiles.get("upper")

    total_transformed = 0
    clipped_low = 0
    clipped_high = 0
    by_country: dict[str, dict] = {}
    by_stratum: dict[str, dict] = {}

    for origin_id, snap in feature_snapshots_by_origin_id.items():
        if snap is None:
            continue
        country = origin_id.split(":")[1] if origin_id.count(":") >= 2 else "UNKNOWN"
        for cell in snap.get("grid_cells", []) or []:
            raw = compute_host_density_total(cell)
            if raw.host_density_total_status != RAW_REAL_COMPONENT:
                continue
            if lower is None or upper is None:
                continue
            _z, clip_audit, status = transform_log1p_robust_reference_scale(
                host_density_total=raw.host_density_total, reference_log1p_lower=lower, reference_log1p_upper=upper,
            )
            if status != "REAL_TRANSFORMED_CANDIDATE" or clip_audit is None:
                continue
            total_transformed += 1
            country_bucket = by_country.setdefault(country, {"total": 0, "clipped_low": 0, "clipped_high": 0})
            country_bucket["total"] += 1
            if clip_audit.was_clipped_low:
                clipped_low += 1
                country_bucket["clipped_low"] += 1
            if clip_audit.was_clipped_high:
                clipped_high += 1
                country_bucket["clipped_high"] += 1

    def _pct(n: int) -> float | None:
        return (n / total_transformed) if total_transformed else None

    return {
        "total_transformed": total_transformed,
        "clipped_low_count": clipped_low, "clipped_low_pct": _pct(clipped_low),
        "clipped_high_count": clipped_high, "clipped_high_pct": _pct(clipped_high),
        "by_country": by_country,
    }
