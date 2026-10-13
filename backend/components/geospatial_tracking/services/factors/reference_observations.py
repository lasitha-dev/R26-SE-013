"""Checkpoint 6D Part 5 / Checkpoint 6D.5 Parts 3-6: reference-observation
identity and de-duplication.

**Corrected identity (6D.5)**: a computed grid-cell host-density value
may be an overlap-area-weighted blend of one or more real GLW4 raster
pixels — the QUERY location (grid-cell centroid) that TRIGGERED the
extraction is not necessarily the same thing as the underlying RASTER
OBSERVATION(S) that produced the value. Two different query centroids
can resolve to the very same contributing pixel set (e.g. two nearby
grid cells fully inside one coarse GLW4 pixel), and must therefore
collapse to ONE reference observation, not two.

`host_density/fao_glw.py.extract_grid_cell_density` now returns a real,
deterministic `FeatureResult.sample_support_digest` (Checkpoint 6D.6) —
a hash of the ACTUAL EFFECTIVE weighted contribution support (which
real pixels contributed AND their normalized overlap weights, never
merely which pixels were touched — two cells sharing a pixel SET but
different effective weights get DIFFERENT digests). This module uses
that digest AS THE PRIMARY signal, falling back to the older,
weaker `sample_identity` (pixel-set-only, Checkpoint 6D.5) if the
digest is unavailable, and only then to the rounded query centroid —
labeling which path was used (`identity_source`) so this is never
silently ambiguous.

**STATIC layers**: identity = `(dataset_name, dataset_version,
feature_name, sample_support_digest)` when available, else
`(..., sample_identity)`, else `(..., rounded query centroid)`.

**DYNAMIC layers** (weather): identity = `(weather dataset/model,
sampling location, weather window, feature_name)` — unchanged;
weather has no raster-pixel concept, and `FeatureSnapshot.weather` is
sampled once per snapshot, never once per cell, so this module works
at the snapshot level for weather.

**Value-conflict firewall (Checkpoint 6D.6 Part 6-7)**: the SAME
observation identity appearing with a DIFFERENT effective raw value is
a DATA/IDENTITY CONFLICT, never a duplicate — it is never resolved by
keeping the first value, the last value, or an average. Both
`build_static_reference_observations` and (for the host-total pooling
step) `reference_profile.py` detect this and report it explicitly via
`ObservationConflict` — never silently continuing.

**Comparison tolerance (Part 7), corrected against the real universe**:
an initial EXACT (`==`) comparison was tried first, on the reasoning
that the same deterministic overlap-area-weighted computation over the
same real inputs "should" reproduce the same float bit-for-bit. Running
the corrected pooling logic over the real, full FIT_DEVELOPMENT
universe disproved that assumption empirically: 1,690 same-identity
pairs differed, every one of them by between ~3.5e-18 and ~5.7e-14 in
absolute terms — i.e. last-few-ULP floating-point summation-order
noise (the pixel contribution sum inside `compute_cell_density_from_pixel_overlaps`
is not literally re-executed in the same term order for two different
query cells that happen to share the same effective pixel support), not
a genuine differing scientific observation. `values_conflict` therefore
uses a tiny, explicitly-labeled SOFTWARE numerical tolerance
(`REFERENCE_VALUE_CONFLICT_REL_TOL`/`REFERENCE_VALUE_CONFLICT_ABS_TOL`,
via `math.isclose`) — roughly 5 orders of magnitude looser than the
largest real noise observed, and roughly 5 orders of magnitude tighter
than would be needed to call two truly DIFFERENT raster observations
"the same." This is a numerical-precision allowance for reproducing one
deterministic computation, never a scientific-similarity judgement
about two different observations. Never retuned using held-out or Sri
Lanka data (Checkpoint 7A Part 0A).

**Checkpoint 7A Part 0A — tolerance is versioned and identity-bearing**:
the two tolerance constants are named module-level constants (not
buried magic numbers) and `FactorReferenceProfile.reference_value_conflict_tolerance`
carries their actual values into `reference_profile_hash()` — changing
either constant changes every downstream reference-profile hash, even
if the current corpus happens to still pool to the same values (it must
never silently retain an identical protocol identity merely because of
that coincidence).

**Checkpoint 7A Part 0B — raster identity provenance is three-way, not
two-way**: 6D.6 mislabeled the LEGACY pixel-set-only identity
(`FeatureResult.sample_identity`, no normalized overlap weights) with
the SAME `RASTER_EFFECTIVE_SAMPLE_IDENTITY` source label used for the
real weighted `sample_support_digest` path — implying weight-awareness
that path never had. Three explicit, mutually exclusive labels now
exist: `RASTER_EFFECTIVE_SAMPLE_IDENTITY` (weighted digest available),
`RASTER_LEGACY_PIXEL_SET_IDENTITY` (pixel-set only, no weights —
diagnostic/backward-compatibility use only), `QUERY_CENTROID_FALLBACK`.
The real GLW4 adapter has populated `sample_support_digest` on every
REAL result since 6D.6, so `RASTER_LEGACY_PIXEL_SET_IDENTITY` is not
expected to occur in current real data — it exists for a hypothetical
adapter that can supply a pixel set but not weights, and must never
silently enter a strict primary model reference pool (see
`reference_profile.build_factor_reference_profile`'s
`require_effective_sample_identity` flag).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

_COORD_ROUND_DECIMALS = 4  # fallback-only: ~11m at the equator

RASTER_EFFECTIVE_SAMPLE_IDENTITY = "RASTER_EFFECTIVE_SAMPLE_IDENTITY"
RASTER_SAMPLE = RASTER_EFFECTIVE_SAMPLE_IDENTITY  # backward-compatible alias (6D.5 name)
RASTER_LEGACY_PIXEL_SET_IDENTITY = "RASTER_LEGACY_PIXEL_SET_IDENTITY"  # 7A Part 0B: pixel set only, NOT weight-aware
QUERY_CENTROID_FALLBACK = "QUERY_CENTROID_FALLBACK"

# 7A Part 0A: the strict, weight-aware primary path a future model
# reference pool should require -- legacy/fallback identity may remain
# for backward-compatibility/diagnostics but must not silently enter it.
STRICT_PRIMARY_IDENTITY_SOURCES = (RASTER_EFFECTIVE_SAMPLE_IDENTITY,)


@dataclass(frozen=True)
class ReferenceObservation:
    observation_id: str
    kind: str  # "HOST_DENSITY_STATIC" | "WEATHER_DYNAMIC"
    feature_name: str
    value: float
    identity: dict
    identity_source: str = RASTER_EFFECTIVE_SAMPLE_IDENTITY  # RASTER_EFFECTIVE_SAMPLE_IDENTITY | QUERY_CENTROID_FALLBACK

    def as_dict(self) -> dict:
        return {"observation_id": self.observation_id, "kind": self.kind, "feature_name": self.feature_name, "value": self.value, "identity": self.identity, "identity_source": self.identity_source}


@dataclass(frozen=True)
class ObservationConflict:
    """Checkpoint 6D.6 Part 6: the SAME observation identity produced
    TWO DIFFERENT effective raw values — a data/identity conflict, never
    silently resolved."""

    observation_id: str
    first_value: float
    conflicting_value: float
    identity: dict

    def as_dict(self) -> dict:
        return {"observation_id": self.observation_id, "first_value": self.first_value, "conflicting_value": self.conflicting_value, "identity": self.identity}


def _observation_id(identity: dict) -> str:
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def resolve_static_observation_identity(fr: dict, *, cell: dict) -> tuple[dict, str]:
    """Checkpoint 6D.5 Part 3/6, corrected 6D.6 Part 1: returns
    `(identity_dict, identity_source)`. Dataset NAME (not just version)
    always participates — two datasets sharing a version string are
    never treated as the same identity."""
    if fr.get("sample_support_digest"):
        identity = {
            "dataset_name": fr.get("dataset_name"), "dataset_version": fr.get("dataset_version"),
            "feature_name": fr.get("feature_name"), "sample_support_digest": fr["sample_support_digest"],
        }
        return identity, RASTER_EFFECTIVE_SAMPLE_IDENTITY
    if fr.get("sample_identity"):
        identity = {
            "dataset_name": fr.get("dataset_name"), "dataset_version": fr.get("dataset_version"),
            "feature_name": fr.get("feature_name"), "sample_identity": fr["sample_identity"],
        }
        # 7A Part 0B: pixel-set-only -- never labeled as though
        # normalized overlap weights were included.
        return identity, RASTER_LEGACY_PIXEL_SET_IDENTITY
    identity = {
        "dataset_name": fr.get("dataset_name"), "dataset_version": fr.get("dataset_version"),
        "feature_name": fr.get("feature_name"),
        "lat": round(cell["centroid_lat"], _COORD_ROUND_DECIMALS), "lon": round(cell["centroid_lon"], _COORD_ROUND_DECIMALS),
    }
    return identity, QUERY_CENTROID_FALLBACK


# 7A Part 0A: versioned, named constants (never a buried magic number)
# -- see FactorReferenceProfile.reference_value_conflict_tolerance for
# how these participate in reference_profile_hash().
REFERENCE_VALUE_CONFLICT_REL_TOL = 1e-9
REFERENCE_VALUE_CONFLICT_ABS_TOL = 1e-9


def values_conflict(a: float, b: float, *, rel_tol: float = REFERENCE_VALUE_CONFLICT_REL_TOL, abs_tol: float = REFERENCE_VALUE_CONFLICT_ABS_TOL) -> bool:
    """Checkpoint 6D.6 Part 7, corrected against the real universe: a
    tiny SOFTWARE numerical tolerance for floating-point summation-order
    noise in the deterministic overlap-area-weighted computation — see
    module docstring for the real measurements that justified it. This
    is NOT a scientific-similarity tolerance; two genuinely different
    observations differ by far more than this. Callers normally rely on
    the module-default tolerance constants; the keyword overrides exist
    only so `FactorReferenceProfile` can record whichever tolerance was
    actually used, never so a caller can retune it ad hoc using held-out/
    Sri Lanka evidence."""
    return not math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)


_values_conflict = values_conflict  # backward-compatible private alias


def build_static_reference_observations(snapshots: list, *, species: str) -> tuple[list, dict, list]:
    """`species`: the `GridCellFeatures.host_density` key (`"cattle"`/
    `"buffalo"`). Only `REAL`-status values ever become observations —
    MISSING/BLOCKED cells contribute nothing (never a fabricated 0).
    Returns `(observations, report, conflicts)`."""
    raw_appearances = 0
    unique: dict[str, ReferenceObservation] = {}
    conflicts: list[ObservationConflict] = []
    n_raster_effective = 0
    n_raster_legacy = 0
    n_fallback = 0
    for snap in snapshots:
        for cell in snap.get("grid_cells", []) or []:
            hd = cell.get("host_density") or {}
            fr = hd.get(species)
            if not fr or fr.get("status") != "REAL":
                continue
            raw_appearances += 1
            identity, source = resolve_static_observation_identity(fr, cell=cell)
            if source == RASTER_EFFECTIVE_SAMPLE_IDENTITY:
                n_raster_effective += 1
            elif source == RASTER_LEGACY_PIXEL_SET_IDENTITY:
                n_raster_legacy += 1
            else:
                n_fallback += 1
            obs_id = _observation_id(identity)
            if obs_id in unique:
                if _values_conflict(unique[obs_id].value, fr["value"]):
                    conflicts.append(ObservationConflict(observation_id=obs_id, first_value=unique[obs_id].value, conflicting_value=fr["value"], identity=identity))
                continue
            unique[obs_id] = ReferenceObservation(observation_id=obs_id, kind="HOST_DENSITY_STATIC", feature_name=fr["feature_name"], value=fr["value"], identity=identity, identity_source=source)

    dedup_ratio = (len(unique) / raw_appearances) if raw_appearances else None
    report = {
        "raw_appearances": raw_appearances, "unique_observations": len(unique), "dedup_ratio": dedup_ratio,
        "n_identified_by_raster_sample": n_raster_effective + n_raster_legacy,  # backward-compatible combined count
        "n_identified_by_raster_effective_sample_identity": n_raster_effective,
        "n_identified_by_raster_legacy_pixel_set_identity": n_raster_legacy,
        "n_identified_by_query_centroid_fallback": n_fallback,
        "n_value_conflicts": len(conflicts),
    }
    return list(unique.values()), report, conflicts


def build_weather_reference_observations(snapshots: list, *, feature_name: str) -> tuple[list, dict]:
    """One `ReferenceObservation` per real, distinct
    (model, sampling location, window, feature) tuple — an AOI-center
    weather observation expanded to N hazard grid cells is counted ONCE
    (REF-06), because this loop is over snapshots, not cells."""
    raw_appearances = 0
    unique: dict[str, ReferenceObservation] = {}
    for snap in snapshots:
        weather = snap.get("weather") or {}
        results = weather.get("results") or {}
        fr = results.get(feature_name)
        if not fr or fr.get("status") != "REAL":
            continue
        raw_appearances += 1
        window = weather.get("window") or {}
        req = window.get("request_parameters") or {}
        identity = {
            "weather_model": window.get("weather_model"),
            "dataset_name": fr.get("dataset_name"),
            "feature_name": feature_name,
            "lat": round(req.get("latitude"), _COORD_ROUND_DECIMALS) if req.get("latitude") is not None else None,
            "lon": round(req.get("longitude"), _COORD_ROUND_DECIMALS) if req.get("longitude") is not None else None,
            "window_start": window.get("window_start"),
            "window_end": window.get("window_end"),
        }
        obs_id = _observation_id(identity)
        if obs_id not in unique:
            unique[obs_id] = ReferenceObservation(observation_id=obs_id, kind="WEATHER_DYNAMIC", feature_name=feature_name, value=fr["value"], identity=identity)

    dedup_ratio = (len(unique) / raw_appearances) if raw_appearances else None
    report = {"raw_appearances": raw_appearances, "unique_observations": len(unique), "dedup_ratio": dedup_ratio}
    return list(unique.values()), report
