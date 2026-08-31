"""Checkpoint 6D Parts 3, 6-8, 26 / Checkpoint 6D.5 Parts 1-2, 5-9, 15-16:
`FactorReferenceProfile` — the FIT_DEVELOPMENT-only, leakage-safe,
scientifically-identified reference distribution every real
transformation candidate must scale against.

**Critical hash correction (6D.5 Part 1)**: Checkpoint 6D's
`reference_profile_hash()` covered only summary quantiles, not the full
effective `EMPIRICAL_CDF_REFERENCE` support
(`host_density_total_reference_values`) — two profiles with different
interior reference distributions could alias to the same hash if their
5/25/50/75/95th percentiles happened to match. `reference_profile_hash()`
now includes a `reference_observation_digest` — a SHA256 over every
contributing host-total observation's identity + value — so ANY change
to the effective ECDF support changes the hash, even when summary
quantiles are unchanged.

**Model-fitting exposure firewall (Part 3)**: `assert_factor_development_only`
reuses `model_fitting_exposure.assert_fit_development_only` unchanged.

**No AOI normalization (Part 7)**: nothing here or downstream computes
a per-AOI/per-forecast-origin/per-cell-neighborhood min/max/mean/
quantile — every candidate scaling reads from this ONE precomputed,
FIT_DEVELOPMENT-only profile.

**Dataset-compatibility firewall (6D.5 Parts 7-9)**: host reference
observations are stratified by `ReferenceStratumKey` (dataset family,
comparability group, canonical units, sampling protocol version).
Under `ReferenceCompatibilityMode.STRICT_COMPATIBLE` (the only mode in
6D.5), more than one distinct HOST stratum among the observations that
would otherwise be pooled makes the profile
`status=INCOMPATIBLE_REFERENCE_STRATA` — no pooled quantiles are
computed, never silently pooled with a warning appended after the fact.
Country is NEVER automatically a stratum — only real dataset-lineage
facts are.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass, field

from ..model_fitting_exposure import MODEL_FITTING_CUTOFF, assert_fit_development_only
from .contracts import (
    COMPLETE_DIAGNOSTIC,
    INCOMPATIBLE_REFERENCE_STRATA,
    NO_USABLE_HOST_DENSITY_OBSERVATIONS,
    RAW_REAL_COMPONENT,
    REFERENCE_OBSERVATION_VALUE_CONFLICT,
    ReferenceCompatibilityMode,
    ReferenceStratumKey,
)
from .host_transform import compute_host_density_total
from .reference_observations import (
    QUERY_CENTROID_FALLBACK,
    RASTER_EFFECTIVE_SAMPLE_IDENTITY,
    RASTER_LEGACY_PIXEL_SET_IDENTITY,
    REFERENCE_VALUE_CONFLICT_ABS_TOL,
    REFERENCE_VALUE_CONFLICT_REL_TOL,
    ObservationConflict,
    build_weather_reference_observations,
    values_conflict,
)
from .transform_config import FactorTransformConfig

REFERENCE_PROFILE_VERSION = "7A.1"
HOST_FACTOR_FAMILY = "HOST_DENSITY"
HOST_SAMPLING_PROTOCOL_VERSION = "GLW4_OVERLAP_AREA_WEIGHTED_V1"


def assert_factor_development_only(
    origins, *, caller: str = "reference_profile", cutoff: str = MODEL_FITTING_CUTOFF
) -> None:
    """Checkpoint 6D Part 3: the hard firewall for reference-profile
    estimation and transformation development decisions. Does not
    depend on caller discipline — raises immediately on any
    non-FIT_DEVELOPMENT origin, rejecting the entire call."""
    assert_fit_development_only(origins, cutoff=cutoff, caller=caller)


def _quantile(sorted_values: list, q: float) -> float:
    idx = q * (len(sorted_values) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def _quantile_set(sorted_values: list, *, lower_q: float, upper_q: float) -> dict:
    if not sorted_values:
        return {"p05": None, "p25": None, "p50": None, "p75": None, "p95": None, "lower": None, "upper": None}
    return {
        "p05": _quantile(sorted_values, 0.05), "p25": _quantile(sorted_values, 0.25),
        "p50": _quantile(sorted_values, 0.50), "p75": _quantile(sorted_values, 0.75),
        "p95": _quantile(sorted_values, 0.95),
        "lower": _quantile(sorted_values, lower_q), "upper": _quantile(sorted_values, upper_q),
    }


def _host_stratum_key(*, cell: dict) -> ReferenceStratumKey | None:
    hd = cell.get("host_density") or {}
    cattle = hd.get("cattle") or {}
    buffalo = hd.get("buffalo") or {}
    dataset_family = cattle.get("dataset_name") or buffalo.get("dataset_name")
    version = cattle.get("dataset_version") or buffalo.get("dataset_version")
    units = cattle.get("units") or buffalo.get("units")
    if not dataset_family or not version or not units:
        return None
    return ReferenceStratumKey(
        factor_family=HOST_FACTOR_FAMILY, dataset_family=dataset_family,
        dataset_comparability_group=f"{dataset_family}:{version}", canonical_units=units,
        sampling_protocol_version=HOST_SAMPLING_PROTOCOL_VERSION,
    )


@dataclass(frozen=True)
class FactorReferenceProfile:
    reference_profile_version: str
    development_role: str
    development_cutoff: str
    included_origin_ids_digest: str
    n_included_origins: int
    country_coverage: tuple
    n_feature_snapshots_considered: int

    host_density_total_raw_appearances: int
    host_density_total_unique_observations: int
    host_density_total_reference_values: tuple  # sorted, deduplicated REAL values
    host_density_total_observation_ids: tuple  # aligned with the SORTED reference values
    host_density_total_quantiles: dict
    host_density_total_log1p_quantiles: dict
    reference_observation_digest: str  # covers the FULL effective ECDF support -- Part 1

    dataset_compatibility_stratum: dict | None  # ReferenceStratumKey.as_dict(), or None if incompatible/unavailable
    n_incompatible_strata_detected: int
    reference_compatibility_mode: str

    n_reference_observation_conflicts: int
    reference_observation_conflicts: tuple  # ObservationConflict.as_dict(), capped for diagnostics

    n_host_species_observations_via_raster_identity: int  # 6D.6 Part 15
    n_host_species_observations_via_query_centroid_fallback: int

    weather_reference_observation_counts: dict  # feature_name -> {raw_appearances, unique_observations, dedup_ratio}
    dataset_version_composition: dict  # dataset_name -> {version: count}
    landcover_comparability_composition: dict  # group -> count
    weather_model_composition: dict  # model -> count

    transform_config_hash: str
    status: str
    generated_at: str

    # -- Checkpoint 7A Part 0 -----------------------------------------
    n_host_species_observations_via_legacy_pixel_set_identity: int = 0  # Part 0B: pixel-set-only, NOT weight-aware
    reference_value_conflict_tolerance: dict = field(
        default_factory=lambda: {"rel_tol": REFERENCE_VALUE_CONFLICT_REL_TOL, "abs_tol": REFERENCE_VALUE_CONFLICT_ABS_TOL}
    )  # Part 0A: participates in reference_profile_hash() -- see as_dict()
    require_effective_sample_identity: bool = False  # Part 0B: strict primary-path mode
    n_excluded_by_strict_identity_requirement: int = 0  # observations withheld from pooling by that strict mode

    def as_dict(self) -> dict:
        return {
            "reference_profile_version": self.reference_profile_version,
            "development_role": self.development_role,
            "development_cutoff": self.development_cutoff,
            "included_origin_ids_digest": self.included_origin_ids_digest,
            "n_included_origins": self.n_included_origins,
            "country_coverage": list(self.country_coverage),
            "n_feature_snapshots_considered": self.n_feature_snapshots_considered,
            "host_density_total_raw_appearances": self.host_density_total_raw_appearances,
            "host_density_total_unique_observations": self.host_density_total_unique_observations,
            "host_density_total_quantiles": self.host_density_total_quantiles,
            "host_density_total_log1p_quantiles": self.host_density_total_log1p_quantiles,
            "reference_observation_digest": self.reference_observation_digest,
            "dataset_compatibility_stratum": self.dataset_compatibility_stratum,
            "n_incompatible_strata_detected": self.n_incompatible_strata_detected,
            "reference_compatibility_mode": self.reference_compatibility_mode,
            "n_reference_observation_conflicts": self.n_reference_observation_conflicts,
            "reference_observation_conflicts": list(self.reference_observation_conflicts),
            "n_host_species_observations_via_raster_identity": self.n_host_species_observations_via_raster_identity,
            "n_host_species_observations_via_query_centroid_fallback": self.n_host_species_observations_via_query_centroid_fallback,
            "weather_reference_observation_counts": self.weather_reference_observation_counts,
            "dataset_version_composition": self.dataset_version_composition,
            "landcover_comparability_composition": self.landcover_comparability_composition,
            "weather_model_composition": self.weather_model_composition,
            "transform_config_hash": self.transform_config_hash,
            "status": self.status,
            "generated_at": self.generated_at,
            "n_host_species_observations_via_legacy_pixel_set_identity": self.n_host_species_observations_via_legacy_pixel_set_identity,
            "reference_value_conflict_tolerance": self.reference_value_conflict_tolerance,
            "require_effective_sample_identity": self.require_effective_sample_identity,
            "n_excluded_by_strict_identity_requirement": self.n_excluded_by_strict_identity_requirement,
        }

    def _hash_payload(self) -> dict:
        d = self.as_dict()
        d.pop("generated_at", None)
        # host_density_total_quantiles/log1p_quantiles are summary
        # statistics DERIVED from reference_observation_digest's own
        # inputs -- kept in the hash payload too (harmless, deterministic
        # given the same inputs) so a quantile-computation bug would also
        # be caught, but reference_observation_digest is what actually
        # guarantees full-support coverage (Part 1/22).
        return d

    def reference_profile_hash(self) -> str:
        canonical = json.dumps(self._hash_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_factor_reference_profile(
    *,
    fit_development_origins: list,
    feature_snapshots_by_origin_id: dict,
    transform_config: FactorTransformConfig,
    generated_at: str = "",
    require_effective_sample_identity: bool = False,
    cutoff: str = MODEL_FITTING_CUTOFF,
) -> FactorReferenceProfile:
    """`feature_snapshots_by_origin_id`: `{forecast_origin_id: FeatureSnapshot.as_dict() | None}`
    (may be host-only shaped, e.g. from `host_reference_gathering.py`)
    — `None`/absent means that origin's snapshot could not be assembled
    (MISSING/BLOCKED), never silently substituted.

    `require_effective_sample_identity` (Checkpoint 7A Part 0B): when
    `True`, a cell whose REAL cattle/buffalo identity resolved via
    `RASTER_LEGACY_PIXEL_SET_IDENTITY` or `QUERY_CENTROID_FALLBACK`
    (rather than the weight-aware `RASTER_EFFECTIVE_SAMPLE_IDENTITY`) is
    withheld from pooling entirely — never silently pooled alongside
    strict observations. Withheld cells are still tallied (identity-
    source counters, `n_excluded_by_strict_identity_requirement`) so
    the exclusion is visible, never hidden. Default `False` preserves
    6D.6 behavior for existing callers."""
    assert_factor_development_only(
        fit_development_origins,
        caller="build_factor_reference_profile",
        cutoff=cutoff,
    )

    origin_ids = sorted(o.forecast_origin_id for o in fit_development_origins)
    digest = hashlib.sha256("|".join(origin_ids).encode("utf-8")).hexdigest()[:24]
    countries = tuple(sorted({o.country for o in fit_development_origins}))

    snapshots = [feature_snapshots_by_origin_id[oid] for oid in origin_ids if feature_snapshots_by_origin_id.get(oid) is not None]

    # -- Part 5/9: host_density_total, de-duplicated by the SPECIES
    # observation-derived identity (never independently re-derived from
    # dataset version + rounded coordinates); stratified for the
    # dataset-compatibility firewall (Part 7-8), using the FULL
    # ReferenceStratumKey (6D.6 Part 9) — never only comparability
    # group + units.
    raw_appearances = 0
    seen_by_id: dict[str, float] = {}
    conflicts: list[ObservationConflict] = []
    strata_seen: dict[str, ReferenceStratumKey] = {}
    n_raster_identity = 0
    n_raster_legacy = 0
    n_fallback_identity = 0
    n_excluded_by_strict = 0
    for snap in snapshots:
        for cell in snap.get("grid_cells", []) or []:
            raw = compute_host_density_total(cell)
            real_sources = []
            for source in (raw.cattle_identity_source, raw.buffalo_identity_source):
                if source == RASTER_EFFECTIVE_SAMPLE_IDENTITY:
                    n_raster_identity += 1
                    real_sources.append(source)
                elif source == RASTER_LEGACY_PIXEL_SET_IDENTITY:
                    n_raster_legacy += 1
                    real_sources.append(source)
                elif source == QUERY_CENTROID_FALLBACK:
                    n_fallback_identity += 1
                    real_sources.append(source)
            if raw.host_density_total_status != RAW_REAL_COMPONENT:
                continue
            if require_effective_sample_identity and any(s != RASTER_EFFECTIVE_SAMPLE_IDENTITY for s in real_sources):
                # -- 7A Part 0B: strict primary path -- a legacy/fallback
                # identity never silently enters this pool.
                n_excluded_by_strict += 1
                continue
            raw_appearances += 1
            obs_id = raw.host_density_total_observation_id
            if obs_id in seen_by_id:
                # -- 6D.6 Part 6-8: same identity, different value =>
                # explicit conflict, NEVER first-wins/last-wins/average.
                # `values_conflict` applies a tiny documented SOFTWARE
                # numerical tolerance (Part 7) for float summation-order
                # noise, not a scientific-similarity judgement.
                if values_conflict(seen_by_id[obs_id], raw.host_density_total):
                    conflicts.append(ObservationConflict(
                        observation_id=obs_id, first_value=seen_by_id[obs_id], conflicting_value=raw.host_density_total,
                        identity={"host_density_total_observation_id": obs_id},
                    ))
                continue
            seen_by_id[obs_id] = raw.host_density_total
            stratum = _host_stratum_key(cell=cell)
            if stratum is not None:
                strata_seen[stratum.canonical_key()] = stratum

    n_strata = len(strata_seen)
    compatible = n_strata <= 1
    has_conflicts = len(conflicts) > 0

    if has_conflicts:
        # 6D.6 Part 6/8: a conflict blocks the ENTIRE pool, never a
        # partially-cleaned subset -- READY-05.
        status = REFERENCE_OBSERVATION_VALUE_CONFLICT
        pooled_ids: tuple = ()
        pooled_values: tuple = ()
        quantiles = _quantile_set([], lower_q=transform_config.log1p_reference_lower_quantile, upper_q=transform_config.log1p_reference_upper_quantile)
        log1p_quantiles = quantiles
        obs_digest = hashlib.sha256(b"[]").hexdigest()
        stratum_dict = None
    elif not seen_by_id:
        status = NO_USABLE_HOST_DENSITY_OBSERVATIONS
        pooled_ids = ()
        pooled_values = ()
        quantiles = _quantile_set([], lower_q=transform_config.log1p_reference_lower_quantile, upper_q=transform_config.log1p_reference_upper_quantile)
        log1p_quantiles = quantiles
        obs_digest = hashlib.sha256(b"[]").hexdigest()
        stratum_dict = None
    elif not compatible and transform_config.reference_compatibility_mode == ReferenceCompatibilityMode.STRICT_COMPATIBLE.value:
        status = INCOMPATIBLE_REFERENCE_STRATA
        pooled_ids = ()
        pooled_values = ()
        quantiles = _quantile_set([], lower_q=transform_config.log1p_reference_lower_quantile, upper_q=transform_config.log1p_reference_upper_quantile)
        log1p_quantiles = quantiles
        obs_digest = hashlib.sha256(b"[]").hexdigest()
        stratum_dict = None
    else:
        status = COMPLETE_DIAGNOSTIC
        ordered = sorted(seen_by_id.items(), key=lambda kv: (kv[1], kv[0]))
        pooled_ids = tuple(k for k, _v in ordered)
        pooled_values = tuple(v for _k, v in ordered)
        quantiles = _quantile_set(list(pooled_values), lower_q=transform_config.log1p_reference_lower_quantile, upper_q=transform_config.log1p_reference_upper_quantile)
        log1p_sorted = sorted(math.log1p(v) for v in pooled_values)
        log1p_quantiles = _quantile_set(log1p_sorted, lower_q=transform_config.log1p_reference_lower_quantile, upper_q=transform_config.log1p_reference_upper_quantile)
        obs_payload = [[oid, seen_by_id[oid]] for oid in sorted(seen_by_id.keys())]
        obs_digest = hashlib.sha256(json.dumps(obs_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        stratum_dict = next(iter(strata_seen.values())).as_dict() if strata_seen else None

    weather_counts = {}
    for feature_name in ("mean_u10", "mean_v10", "mean_temperature_2m", "mean_relative_humidity_2m", "precipitation_accumulation"):
        _obs, report = build_weather_reference_observations(snapshots, feature_name=feature_name)
        weather_counts[feature_name] = report

    dataset_version_composition: dict = {}
    landcover_composition: Counter = Counter()
    weather_model_composition: Counter = Counter()
    for snap in snapshots:
        for dataset_name, version in (snap.get("source_dataset_versions") or {}).items():
            dataset_version_composition.setdefault(dataset_name, Counter())[str(version)] += 1
        group = snap.get("landcover_comparability_group")
        if group:
            landcover_composition[group] += 1
        model = ((snap.get("weather") or {}).get("window") or {}).get("weather_model")
        if model:
            weather_model_composition[model] += 1

    dataset_version_composition = {k: dict(v) for k, v in dataset_version_composition.items()}

    return FactorReferenceProfile(
        reference_profile_version=REFERENCE_PROFILE_VERSION,
        development_role="FIT_DEVELOPMENT",
        development_cutoff=cutoff,
        included_origin_ids_digest=digest,
        n_included_origins=len(fit_development_origins),
        country_coverage=countries,
        n_feature_snapshots_considered=len(snapshots),
        host_density_total_raw_appearances=raw_appearances,
        host_density_total_unique_observations=len(pooled_values),
        host_density_total_reference_values=pooled_values,
        host_density_total_observation_ids=pooled_ids,
        host_density_total_quantiles=quantiles,
        host_density_total_log1p_quantiles=log1p_quantiles,
        reference_observation_digest=obs_digest,
        dataset_compatibility_stratum=stratum_dict,
        n_incompatible_strata_detected=n_strata if not compatible else 0,
        reference_compatibility_mode=transform_config.reference_compatibility_mode,
        n_reference_observation_conflicts=len(conflicts),
        reference_observation_conflicts=tuple(c.as_dict() for c in conflicts[:50]),
        n_host_species_observations_via_raster_identity=n_raster_identity,
        n_host_species_observations_via_query_centroid_fallback=n_fallback_identity,
        weather_reference_observation_counts=weather_counts,
        dataset_version_composition=dataset_version_composition,
        landcover_comparability_composition=dict(landcover_composition),
        weather_model_composition=dict(weather_model_composition),
        transform_config_hash=transform_config.config_hash(),
        status=status,
        generated_at=generated_at,
        n_host_species_observations_via_legacy_pixel_set_identity=n_raster_legacy,
        reference_value_conflict_tolerance={"rel_tol": REFERENCE_VALUE_CONFLICT_REL_TOL, "abs_tol": REFERENCE_VALUE_CONFLICT_ABS_TOL},
        require_effective_sample_identity=require_effective_sample_identity,
        n_excluded_by_strict_identity_requirement=n_excluded_by_strict,
    )
