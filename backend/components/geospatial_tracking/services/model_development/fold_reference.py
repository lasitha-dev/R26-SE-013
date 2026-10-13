"""Checkpoint 7B Parts 4-6, 29: fold-safe host reference construction.

The complete 579-origin 7A.6.2 host reference (Checkpoint 7A.6.2) is the
correct FINAL development reference (Part 31) but must NEVER be used
INSIDE a chronological validation fold — that would let future validation
covariate distributions (quantiles, ECDF support, clipping thresholds,
reference hash) leak backward into training-fold transform statistics
(transductive/temporal leakage, Part 4).

Architecture (Part 5):

    RAW SCIENTIFIC-GRID HOST OBSERVATIONS   (build_raw_host_snapshots,
                     |                       the ONE expensive GLW pass --
                     v                       never repeated per fold)
    TRAIN-FOLD SUBSET
                     |
                     v
    FactorReferenceProfile(training only)   (build_fold_safe_reference)
                     |
                     v
    transform TRAIN + VALIDATION raw host values

`build_raw_host_snapshots` is called exactly ONCE for the whole
`FIT_DEVELOPMENT` universe; every fold then only SUBSETS that already-
built dict by training-origin id -- raw GLW pixel values themselves are
never changed, never recomputed, never faked (Part 5).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...domain.enums import RecordDomainScope
from ...schemas import ValidationMode
from ..factors.reference_profile import FactorReferenceProfile, build_factor_reference_profile
from ..factors.transform_config import FactorTransformConfig
from ..geospatial.host_density.fao_glw import DATASET_NAME as HOST_DATASET_NAME
from ..geospatial.host_density.fao_glw import REFERENCE_YEAR as HOST_DATASET_VERSION
from ..geospatial.host_density.fao_glw import SAMPLING_PROTOCOL_VERSION as HOST_SAMPLING_PROTOCOL_VERSION
from ..geospatial.host_density.fao_glw import UNITS as CANONICAL_HOST_DENSITY_UNITS
from ..geospatial.scientific_domain import build_scientific_evaluation_domain
from ..geospatial.scientific_grid import ScientificGridConfig
from ..geospatial.source_geometry import EligibleSourcePoint
from ..model_fitting_exposure import MODEL_FITTING_CUTOFF, assert_fit_development_only
from ..source_selector import get_eligible_sources
from .baseline_scoring import MODEL_INPUT_INCOMPLETE, SCORED
from .host_reference_rebuild import DEFAULT_SPECIES, build_scientific_grid_host_only_snapshot

FOLD_REFERENCE_IDENTITY_VERSION = "7B.1"
RAW_HOST_SNAPSHOT_CACHE_VERSION = "7B.4"
CACHE_IDENTITY_MISMATCH = "CACHE_IDENTITY_MISMATCH"


def _snapshot_with_unsafe_component_count(snapshot: dict, unsafe_component_count: int) -> dict:
    """Preserve the builder's separately returned completeness count on the
    snapshot itself so in-memory and cached representations cannot discard it."""
    if isinstance(unsafe_component_count, bool) or not isinstance(unsafe_component_count, int) or unsafe_component_count < 0:
        raise ValueError("unsafe_component_count must be a non-negative integer")
    preserved = dict(snapshot)
    preserved["unsafe_component_count"] = unsafe_component_count
    preserved["model_input_status"] = MODEL_INPUT_INCOMPLETE if unsafe_component_count > 0 else SCORED
    return preserved


def snapshot_unsafe_component_count(snapshot: dict) -> int:
    count = snapshot.get("unsafe_component_count", 0)
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("snapshot unsafe_component_count must be a non-negative integer")
    return count


def build_raw_host_snapshots(
    repo, *, fit_development_origins: list, disease: str, active_window_days: int,
    grid_config: ScientificGridConfig, species: tuple = DEFAULT_SPECIES,
    cutoff: str = MODEL_FITTING_CUTOFF,
) -> dict:
    """`{forecast_origin_id: snapshot_dict}` -- the ONE real, expensive raw
    GLW extraction pass over the whole `FIT_DEVELOPMENT` universe (Part 5).
    Firewalled at its OWN entry point (never trusts a pre-filtered caller).
    An origin with no eligible sources contributes no entry (never a
    fabricated empty snapshot). No disk cache -- see
    `build_raw_host_snapshots_cached` for the Part 13 disk-persisted
    variant used by the real development run."""
    assert_fit_development_only(fit_development_origins, cutoff=cutoff, caller="build_raw_host_snapshots")
    snapshots: dict = {}
    for origin in sorted(fit_development_origins, key=lambda o: o.forecast_origin_id):
        snap, n_unsafe = build_scientific_grid_host_only_snapshot(
            repo, origin=origin, disease=disease, active_window_days=active_window_days,
            grid_config=grid_config, species=species,
        )
        if snap is not None:
            snapshots[origin.forecast_origin_id] = _snapshot_with_unsafe_component_count(snap, n_unsafe)
    return snapshots


def raw_snapshot_cache_identity_payload(
    *, forecast_origin_id: str, t0: str, country: str, disease: str, active_window_days: int, species: tuple,
    scientific_evaluation_domain_id: str,
) -> dict:
    """Part 5 (finalization hardening): binds every input that can change
    a raw host-only snapshot's actual scientific numerical content --
    NEVER `generated_at`/runtime/current clock.
    `scientific_evaluation_domain_id` (Checkpoint 7A.6.2) already encodes
    the scientific-domain protocol hash/version, grid config hash,
    origin/t0, and every eligible source id + coordinate (source
    coordinates feed directly into each component's geometry digest) --
    reused here rather than duplicating that geometry logic; this
    payload ADDS the facts that identity does NOT know about: species,
    disease, the active source window, and the host raster dataset/
    sampling-protocol identity (so a future GLW dataset upgrade, or a
    species-tuple change, can never silently reuse a stale cache entry
    that happens to share the same geometry)."""
    return {
        "raw_host_snapshot_cache_version": RAW_HOST_SNAPSHOT_CACHE_VERSION,
        "forecast_origin_id": forecast_origin_id,
        "t0": t0,
        "country": country,
        "disease": disease,
        "active_window_days": active_window_days,
        "species": sorted(species),
        "scientific_evaluation_domain_id": scientific_evaluation_domain_id,
        "host_dataset_name": HOST_DATASET_NAME,
        "host_dataset_version": HOST_DATASET_VERSION,
        "host_sampling_protocol_version": HOST_SAMPLING_PROTOCOL_VERSION,
    }


def raw_snapshot_cache_identity_hash(identity: dict) -> str:
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cache_path(cache_dir: Path, cache_identity_hash: str) -> Path:
    return cache_dir / f"{cache_identity_hash}.json"


def _load_cache_entry(path: Path, *, expected_identity: dict) -> tuple[dict | None, str]:
    """Returns `(snapshot_or_None, outcome)`; outcome is one of
    `"HIT"` / `"MISS_NO_FILE"` / `"MISS_CORRUPT"` / `CACHE_IDENTITY_MISMATCH`.
    Compares the FULL stored identity dict against `expected_identity`
    (dict equality -- key insertion order never matters, CACHE7B-10) --
    never trusts the filename alone. A stored `forecast_origin_id` (or
    any other identity field) that no longer matches is rejected exactly
    like any other mismatch (CACHE7B-09), never silently reused."""
    if not path.exists():
        return None, "MISS_NO_FILE"
    try:
        with path.open("r", encoding="utf-8") as f:
            entry = json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        return None, "MISS_CORRUPT"
    if not isinstance(entry, dict) or entry.get("cache_identity") != expected_identity:
        return None, CACHE_IDENTITY_MISMATCH
    snapshot = entry.get("snapshot")
    if not isinstance(snapshot, dict):
        return None, "MISS_CORRUPT"
    try:
        unsafe_component_count = snapshot_unsafe_component_count(snapshot)
    except ValueError:
        return None, "MISS_CORRUPT"
    expected_status = MODEL_INPUT_INCOMPLETE if unsafe_component_count > 0 else SCORED
    if snapshot.get("model_input_status") != expected_status:
        return None, "MISS_CORRUPT"
    return snapshot, "HIT"


def _write_cache_entry(path: Path, *, snapshot: dict, identity: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"cache_identity": identity, "snapshot": snapshot}
    tmp_path = path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(entry, f)
    tmp_path.replace(path)


def build_raw_host_snapshots_cached(
    repo, *, fit_development_origins: list, disease: str, active_window_days: int,
    grid_config: ScientificGridConfig, species: tuple = DEFAULT_SPECIES, cache_dir: Path,
    cutoff: str = MODEL_FITTING_CUTOFF,
) -> tuple[dict, dict]:
    """Part 13/5: disk-persisted variant of `build_raw_host_snapshots`,
    keyed by the full `raw_snapshot_cache_identity_payload` hash (never
    the bare `scientific_evaluation_domain_id` alone -- that identity
    knows nothing about species/disease/active-window/raster-dataset
    version). Any change to grid/domain/source protocol, OR to any of
    those additional facts, changes the cache key automatically -- a
    stale cache entry can never be silently reused after such a change;
    a cache HIT additionally re-validates the full stored identity
    against the current expected identity before returning any data
    (`CACHE_IDENTITY_MISMATCH` -- never trusted on a mismatch, always
    recomputed).

    Building the `ScientificEvaluationDomain` (cheap: no raster I/O) is
    duplicated here and in `build_scientific_grid_host_only_snapshot`
    on a cache MISS -- an intentional, cheap redundancy so this function
    never needs to touch that frozen 7A.6.2 function's internals.

    Returns `(snapshots_by_origin_id, cache_stats)`."""
    assert_fit_development_only(fit_development_origins, cutoff=cutoff, caller="build_raw_host_snapshots_cached")
    cache_dir.mkdir(parents=True, exist_ok=True)

    snapshots: dict = {}
    n_hits = 0
    n_misses = 0
    n_no_sources = 0
    n_identity_mismatches = 0
    n_with_unsafe_components = 0
    unsafe_component_count = 0
    for origin in sorted(fit_development_origins, key=lambda o: o.forecast_origin_id):
        result = get_eligible_sources(
            repo, disease=disease, t0=origin.t0, active_window_days=active_window_days,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=origin.country, domain_scope=RecordDomainScope.HISTORICAL_ONLY,
        )
        if not result.sources:
            n_no_sources += 1
            continue
        source_points = [EligibleSourcePoint(source_id=s.source_id, latitude=s.latitude, longitude=s.longitude) for s in result.sources]
        evaluation_domain = build_scientific_evaluation_domain(
            forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, sources=source_points, grid_config=grid_config,
            primary_local_evaluation_distance_km=grid_config.domain_distance_km,
        )
        identity = raw_snapshot_cache_identity_payload(
            forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, country=origin.country, disease=disease,
            active_window_days=active_window_days, species=species,
            scientific_evaluation_domain_id=evaluation_domain.scientific_evaluation_domain_id,
        )
        path = _cache_path(cache_dir, raw_snapshot_cache_identity_hash(identity))
        cached_snapshot, outcome = _load_cache_entry(path, expected_identity=identity)
        if outcome == "HIT":
            snapshots[origin.forecast_origin_id] = cached_snapshot
            cached_unsafe_count = snapshot_unsafe_component_count(cached_snapshot)
            unsafe_component_count += cached_unsafe_count
            n_with_unsafe_components += int(cached_unsafe_count > 0)
            n_hits += 1
            continue
        if outcome == CACHE_IDENTITY_MISMATCH:
            n_identity_mismatches += 1

        snap, n_unsafe = build_scientific_grid_host_only_snapshot(
            repo, origin=origin, disease=disease, active_window_days=active_window_days, grid_config=grid_config, species=species,
        )
        if snap is not None:
            snap = _snapshot_with_unsafe_component_count(snap, n_unsafe)
            snapshots[origin.forecast_origin_id] = snap
            _write_cache_entry(path, snapshot=snap, identity=identity)
            unsafe_component_count += n_unsafe
            n_with_unsafe_components += int(n_unsafe > 0)
        n_misses += 1

    return snapshots, {
        "n_cache_hits": n_hits, "n_cache_misses": n_misses, "n_origins_no_eligible_source": n_no_sources,
        "n_cache_identity_mismatches": n_identity_mismatches,
        "n_origins_with_unsafe_components": n_with_unsafe_components,
        "unsafe_component_count": unsafe_component_count,
    }


class FoldSafeHostReference:
    """One fold's training-only `FactorReferenceProfile` plus its own
    deterministic `fold_reference_identity_hash` (Part 6) -- computed from
    training-side facts ONLY. A validation origin's id, coordinates, host
    value, or existence can never appear in this hash (FOLDREF-01/02)."""

    def __init__(
        self, *, fold_id: str, training_origin_ids: tuple, training_t0_min: str | None, training_t0_max: str | None,
        transform_config: FactorTransformConfig, reference_profile: FactorReferenceProfile, unsafe_component_count: int = 0,
    ) -> None:
        if isinstance(unsafe_component_count, bool) or not isinstance(unsafe_component_count, int) or unsafe_component_count < 0:
            raise ValueError("unsafe_component_count must be a non-negative integer")
        self.fold_id = fold_id
        self.training_origin_ids = training_origin_ids
        self.training_t0_min = training_t0_min
        self.training_t0_max = training_t0_max
        self.transform_config = transform_config
        self.reference_profile = reference_profile
        self.unsafe_component_count = unsafe_component_count
        self.model_input_status = MODEL_INPUT_INCOMPLETE if unsafe_component_count > 0 else SCORED

    def _identity_payload(self) -> dict:
        stratum = self.reference_profile.dataset_compatibility_stratum
        return {
            "fold_reference_identity_version": FOLD_REFERENCE_IDENTITY_VERSION,
            "fold_id": self.fold_id,
            "training_origin_ids": sorted(self.training_origin_ids),
            "training_t0_min": self.training_t0_min,
            "training_t0_max": self.training_t0_max,
            "transform_config_hash": self.transform_config.config_hash(),
            "host_density_total_observation_ids": sorted(self.reference_profile.host_density_total_observation_ids),
            "reference_observation_digest": self.reference_profile.reference_observation_digest,
            "dataset_compatibility_stratum": stratum,
            "canonical_units": (stratum or {}).get("canonical_units", CANONICAL_HOST_DENSITY_UNITS),
            "reference_profile_version": self.reference_profile.reference_profile_version,
            "reference_profile_status": self.reference_profile.status,
            "unsafe_component_count": self.unsafe_component_count,
            "model_input_status": self.model_input_status,
        }

    def fold_reference_identity_hash(self) -> str:
        canonical = json.dumps(self._identity_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict:
        d = self._identity_payload()
        d["fold_reference_identity_hash"] = self.fold_reference_identity_hash()
        d["reference_profile"] = self.reference_profile.as_dict()
        d["reference_profile_hash"] = self.reference_profile.reference_profile_hash()
        return d


def build_fold_safe_reference(
    *, fold_id: str, training_origins: list, validation_origins: list, raw_snapshots_by_origin_id: dict,
    transform_config: FactorTransformConfig, generated_at: str = "", cutoff: str = MODEL_FITTING_CUTOFF,
) -> FoldSafeHostReference:
    """Part 3-4/29: `training_origins` and `validation_origins` are BOTH
    hard-firewalled to `FIT_DEVELOPMENT` here (7B-LEAK-01/02) -- rejecting
    the whole call the instant a HELD_OUT/Sri-Lanka origin appears in
    EITHER list, never only the training list. The reference profile
    itself is built from `training_origins`/their raw snapshots ONLY --
    `validation_origins` is accepted purely so the firewall covers both
    roles at once; it never contributes a single observation
    (FOLDREF-01/02)."""
    assert_fit_development_only(
        list(training_origins) + list(validation_origins), cutoff=cutoff, caller="build_fold_safe_reference"
    )

    training_ids = tuple(o.forecast_origin_id for o in training_origins)
    training_snapshots = {oid: raw_snapshots_by_origin_id[oid] for oid in training_ids if oid in raw_snapshots_by_origin_id}
    unsafe_component_count = sum(snapshot_unsafe_component_count(snapshot) for snapshot in training_snapshots.values())

    t0_values = sorted(o.t0 for o in training_origins)
    t0_min = t0_values[0] if t0_values else None
    t0_max = t0_values[-1] if t0_values else None

    profile = build_factor_reference_profile(
        fit_development_origins=list(training_origins), feature_snapshots_by_origin_id=training_snapshots,
        transform_config=transform_config, generated_at=generated_at, require_effective_sample_identity=True,
        cutoff=cutoff,
    )

    return FoldSafeHostReference(
        fold_id=fold_id, training_origin_ids=training_ids, training_t0_min=t0_min, training_t0_max=t0_max,
        transform_config=transform_config, reference_profile=profile, unsafe_component_count=unsafe_component_count,
    )
