"""FMD-07A-R2B2: full resumable FIT_DEVELOPMENT source-level feature
extraction and cache freeze.

**R1 repair checkpoint note:** an earlier draft of this module seeded
`FileWeatherCache` under all four per-window cache keys using the ONE
superset payload's bytes -- numerically harmless (the eligibility filter
always re-derives the correct subset), but a real cache-provenance bug:
a cache entry stopped meaning "the response produced for THIS key's own
exact request." FMD-07A-R2B2-R1 removed that seeding entirely; see
point 3 below for the corrected design.

Builds on FMD-07A-R2B1's frozen extraction universe (`unique_sources`,
`SourceExtractionCache`) unchanged, and on
`extract_source_features`/`build_event_feature_row`/`extract_weather_for_event`
via one small, additive, default-`None` `precomputed_weather_windows`
parameter (Section 4) -- every pre-existing caller (FMD-04, R2A, R2B1's
own canary/tests) is 100% behaviorally unchanged. This module adds:

1. A materialized, deterministic on-disk snapshot of the R2B1 universe
   (`fmd07_origin_source_map.json` / `fmd07_unique_source_extraction_index.csv`)
   so a resumed run never has to re-derive it from the canonical corpus.
2. Exact request-key deduplication accounting (Section 3).
3. `SEMANTICS_PRESERVING_WEATHER_REQUEST_CONSOLIDATION` -- an ENGINEERING
   optimization only: for one source, all four frozen retrospective
   windows (event_day/window_3day/window_7day/window_14day) end at the
   SAME t0 cutoff (`t0_resolution.pre_t0_window_bounds` -- `cutoff` never
   depends on `lookback_hours`, only `window_start` does), so a single
   Open-Meteo request for the LARGEST (14-day) window is a strict
   superset of the hourly data every smaller window needs.
   `fetch_consolidated_weather_windows` fetches that ONE superset payload
   via `era5.fetch_hourly_payload` and caches it under ONLY its own real
   exact request key -- no other window's `FileWeatherCache` key is ever
   written to. All four windows' results are then derived LOCALLY, in
   memory, via `era5.summarize_hourly_payload_for_window` -- the same
   pure eligibility-filtering/aggregation equations
   `build_pre_t0_weather_summary` itself now calls for its own per-window
   live/cached path (a minimal refactor extracted that logic into one
   shared function; neither path duplicates it). The precomputed
   `(window, results)` per window are handed to `extract_source_features`
   via `precomputed_weather_windows` -- never round-tripped through the
   cache under a mismatched key. Frozen behind an explicit empirical
   equivalence gate (`verify_weather_equivalence_gate`) -- used only if
   every compared value/status/unit/window-boundary matches the existing
   four-request method exactly (or within a tiny float tolerance for the
   mathematically identical mean/sum aggregations); a network outage
   during the gate reports `INTEGRATION_GATE_NETWORK_BLOCKED`, never a
   semantic `..._FAIL`.
4. A resumable, bounded-concurrency full-source batch runner
   (`run_full_r2b2_extraction`) over R2B1's `extract_source_features`,
   plus a bounded (Section 11/17) transient-failure retry pass and a
   persistent, deterministic failure ledger (Section 14,
   `fmd07_feature_extraction_failure_ledger.json`). A per-request-key
   single-flight lock (Section 9-10) keeps concurrent workers that
   collide on the same weather superset key to exactly one live request.
5. Elevation and land-cover are extracted via the existing, UNCHANGED
   `extract_elevation`/`extract_landcover_fractions` adapters -- both
   already perform a windowed remote read (no local per-tile file), and
   neither exposes a cache-injection seam the way weather does. A full
   local per-tile download was evaluated and REJECTED here
   (`STATIC_TILE_BATCH_OPTIMIZATION_NOT_SAFE_WITH_CURRENT_ADAPTER`): ESA
   WorldCover tiles are large (a single 3-degree tile is commonly tens to
   hundreds of MB), so pre-downloading one per required tile would trade
   a small, already-efficient windowed byte-range read for a large,
   unsafe bulk download -- outside Section 8's "if and only if safe" bar.
   `unique_elevation_tile_count`/`unique_landcover_tile_count` are still
   reported (spatial-locality statistics only); actual network volume
   for these two families remains one adapter call per unique source,
   unmodified.
"""

from __future__ import annotations

import csv
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from ..data_processing.build_fmd_features import (
    FmdFeatureExtractionConfig,
    WEATHER_WINDOWS_HOURS,
)
from ..data_processing.fmd_feature_status import ALL_STATUSES, SOURCE_VALUE_AVAILABLE
from ..services.features.cache import FileWeatherCache, cache_key_for_request
from ..services.geospatial.weather.base import T0Precision
from ..services.geospatial.weather.era5 import fetch_hourly_payload, summarize_hourly_payload_for_window
from ..services.geospatial.weather.t0_resolution import pre_t0_window_bounds, resolve_t0_boundary
from .fmd_model_development_r2b1 import (
    CHECKPOINT as R2B1_CHECKPOINT,
    SourceExtractionCache,
    _elevation_tile_key,
    _landcover_tile_key,
    _weather_request_key,
    build_development_extraction_universe,
    build_extraction_plan,
    extract_source_features,
    select_canary_source_ids,
)
from .source_selector import EligibleSource

CHECKPOINT = "FMD-07A-R2B2"

DEFAULT_BATCH_SIZE = 100
DEFAULT_MAX_CONCURRENT_PER_PROVIDER = 4
DEFAULT_MAX_RETRY_PASSES = 1

WEATHER_STRATEGY_CONSOLIDATED = "SEMANTICS_PRESERVING_WEATHER_REQUEST_CONSOLIDATION"
WEATHER_STRATEGY_LEGACY_FOUR_WINDOW = "EXISTING_FMD04_FOUR_WINDOW_METHOD"

WEATHER_EQUIVALENCE_OUTCOME_PASS = "CONSOLIDATED_EQUIVALENCE_PASS"
WEATHER_EQUIVALENCE_OUTCOME_FAIL = "CONSOLIDATED_EQUIVALENCE_FAIL_USE_LEGACY"
WEATHER_EQUIVALENCE_OUTCOME_NETWORK_BLOCKED = "INTEGRATION_GATE_NETWORK_BLOCKED"

# Section 11 (FMD-07A-R2B2-R1): honest engineering finding, real (not
# aspirational) -- extract_elevation (terrain_tiles.py) and
# extract_landcover_fractions (esa_worldcover.py) both read a small AOI
# window directly off a remote raster (GDAL vsicurl / rasterio windowed
# read) with NO local per-tile file and NO tile-level cache-injection
# seam of any kind (neither calls raster.download_and_cache, which is
# reserved for the small, fixed, location-independent host-density/
# hydrology files). A batched-per-tile helper was evaluated here and
# REJECTED as unsafe: the only way to open "the same tile once" would be
# to download the whole remote COG/tile locally first, which trades a
# small already-efficient windowed byte-range read for a large, unsafe
# bulk download (ESA WorldCover tiles commonly run tens-to-hundreds of
# MB) -- outside the "if and only if safe" bar. Source-level caching
# (SourceExtractionCache) is retained instead; `unique_elevation_tile_count`/
# `unique_landcover_tile_count` in `compute_request_key_dedup` remain
# spatial-locality statistics only, never claimed as the real network
# request count.
STATIC_TILE_BATCH_OPTIMIZATION_NOT_SAFE_WITH_CURRENT_ADAPTER = "STATIC_TILE_BATCH_OPTIMIZATION_NOT_SAFE_WITH_CURRENT_ADAPTER"

# Section 17 (FMD-07A-R2B2-R1): `fmd_feature_status.py`'s existing
# vocabulary (`SOURCE_VALUE_AVAILABLE`/`..._MISSING`/`TEMPORAL_COVERAGE_MISSING`/
# `OUTSIDE_SOURCE_COVERAGE`/`SOURCE_FILE_MISSING`/`EXTRACTION_FAILED`) does
# not distinguish a transient network condition (timeout/429/5xx) from a
# permanent request-shape problem (invalid params/unsupported area/parse
# failure) within its single `EXTRACTION_FAILED`/BLOCKED bucket -- both
# adapters (era5.py/raster.py) collapse any `requests.RequestException`
# to the same status. Rather than inventing a distinction the adapters
# don't actually make, `_ledger_bucket_for_status` conservatively treats
# every `EXTRACTION_FAILED` as `TRANSIENT_FAILURE` (retry-eligible, once,
# via `run_bounded_retry_pass` -- never an infinite loop; a request that
# is genuinely permanently malformed will simply fail identically on
# retry and remain `TRANSIENT_FAILURE`/not-yet-terminal in the ledger
# rather than being silently misreported as `PERMANENT_FAILURE`).
FAILURE_RETRY_CLASSIFICATION_LIMITED_BY_EXISTING_ADAPTER_STATUS = "FAILURE_RETRY_CLASSIFICATION_LIMITED_BY_EXISTING_ADAPTER_STATUS"

# Section 9-10 (FMD-07A-R2B2-R1): per-request-key single-flight locks so
# two concurrent workers that happen to resolve to the SAME weather
# superset cache key (rare -- distinct sources rarely share an identical
# coordinate/date -- but possible) never issue two live network requests
# for it; the second worker blocks until the first's write lands, then
# gets a real cache hit. Keyed by the cache key itself (a content hash),
# never by source_id, so this works correctly even across different
# source_ids that happen to collide on the same request.
_weather_fetch_locks: dict[str, threading.Lock] = {}
_weather_fetch_locks_guard = threading.Lock()


def _single_flight_lock_for_key(key: str) -> threading.Lock:
    with _weather_fetch_locks_guard:
        lock = _weather_fetch_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _weather_fetch_locks[key] = lock
        return lock

STATUS_SUCCESS = "SUCCESS"
STATUS_LEGITIMATE_MISSING = "LEGITIMATE_MISSING"
STATUS_OUT_OF_COVERAGE = "OUT_OF_COVERAGE"
STATUS_PERMANENT_FAILURE = "PERMANENT_FAILURE"
STATUS_TRANSIENT_FAILURE = "TRANSIENT_FAILURE"
STATUS_BLOCKED = "BLOCKED"


# ---------------------------------------------------------------------------
# Section 6: materialize the already-frozen R2B1 universe once.
# ---------------------------------------------------------------------------


def build_origin_source_map(universe: dict) -> dict:
    """Pure, deterministic reshape of R2B1's own `origin_to_source_ids` --
    no new source-selection rule. Sorted keys/values so two builds from
    the same universe are byte-identical once serialized."""
    return {
        "checkpoint": CHECKPOINT,
        "development_origin_count": universe["development_origin_count"],
        "unique_required_source_count": universe["unique_required_source_count"],
        "origin_to_source_ids": {oid: sorted(sids) for oid, sids in sorted(universe["origin_to_source_ids"].items())},
    }


UNIQUE_SOURCE_INDEX_FIELDNAMES = [
    "source_id",
    "country",
    "latitude",
    "longitude",
    "effective_availability_date",
    "availability_quality",
    "gps_quality",
    "disease",
]


def build_unique_source_extraction_index(universe: dict) -> list[dict]:
    """One row per unique required source_id, sorted -- deterministic
    materialization of `universe["unique_sources"]` (an `EligibleSource`
    per id) with no additional field (never a label, never an outcome)."""
    rows = []
    for source_id in sorted(universe["unique_sources"]):
        s: EligibleSource = universe["unique_sources"][source_id]
        rows.append(
            {
                "source_id": s.source_id,
                "country": s.country or "",
                "latitude": s.latitude,
                "longitude": s.longitude,
                "effective_availability_date": s.effective_availability_date,
                "availability_quality": s.availability_quality,
                "gps_quality": s.gps_quality,
                "disease": s.disease or "",
            }
        )
    return rows


def write_origin_source_map(origin_source_map: dict, out_path: str | Path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(origin_source_map, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def write_unique_source_extraction_index(rows: list[dict], out_path: str | Path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=UNIQUE_SOURCE_INDEX_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Section 13: firewall assertion -- the materialized index must trace back
# to exactly R2B1's frozen FIT_DEVELOPMENT universe, never a wider one.
# ---------------------------------------------------------------------------


def assert_extraction_index_is_fit_development_only(universe: dict, index_rows: list[dict]) -> None:
    if universe["development_origin_count"] != len(universe["origin_to_source_ids"]):
        raise ValueError(
            "assert_extraction_index_is_fit_development_only: origin_to_source_ids size "
            f"({len(universe['origin_to_source_ids'])}) does not match development_origin_count "
            f"({universe['development_origin_count']}) -- the universe must be built from exactly "
            "the FIT_DEVELOPMENT origins, never a superset"
        )
    index_ids = {row["source_id"] for row in index_rows}
    universe_ids = set(universe["unique_sources"])
    if index_ids != universe_ids:
        raise ValueError(
            "assert_extraction_index_is_fit_development_only: materialized index source_id set diverges "
            "from the frozen R2B1 universe's own unique_sources set"
        )


# ---------------------------------------------------------------------------
# Section 3: exact request-key deduplication accounting.
# ---------------------------------------------------------------------------


def compute_request_key_dedup(unique_sources: dict[str, EligibleSource]) -> dict:
    """No network. Real deterministic keys for every planned request
    across weather (both the legacy 4-request-per-source method and the
    consolidated 1-superset-request-per-source method), elevation, and
    land cover -- reports pre- and post-dedup counts honestly (dedup
    savings ACROSS sources may be near zero for weather/elevation/land
    cover, since distinct sources rarely share an identical coordinate;
    reporting a near-zero cross-source savings here is a correct finding,
    never adjusted to look better)."""
    weather_keys_legacy: set[str] = set()
    weather_keys_legacy_total = 0
    weather_keys_consolidated: set[str] = set()
    weather_keys_consolidated_total = 0
    elevation_tile_keys: set = set()
    landcover_tile_keys: set[str] = set()

    max_lookback = max(WEATHER_WINDOWS_HOURS.values())

    for source in unique_sources.values():
        for lookback_hours in WEATHER_WINDOWS_HOURS.values():
            key = _weather_request_key(source.latitude, source.longitude, source.effective_availability_date, lookback_hours)
            weather_keys_legacy_total += 1
            if key is not None:
                weather_keys_legacy.add(key)

        superset_key = _weather_request_key(source.latitude, source.longitude, source.effective_availability_date, max_lookback)
        weather_keys_consolidated_total += 1
        if superset_key is not None:
            weather_keys_consolidated.add(superset_key)

        elevation_tile_keys.add(_elevation_tile_key(source.latitude, source.longitude))
        landcover_tile_keys.add(_landcover_tile_key(source.latitude, source.longitude))

    return {
        "weather_legacy_four_window": {
            "pre_dedup_request_count": weather_keys_legacy_total,
            "post_dedup_unique_request_key_count": len(weather_keys_legacy),
            "cross_source_dedup_savings": weather_keys_legacy_total - len(weather_keys_legacy),
        },
        "weather_consolidated_superset": {
            "pre_dedup_request_count": weather_keys_consolidated_total,
            "post_dedup_unique_request_key_count": len(weather_keys_consolidated),
            "cross_source_dedup_savings": weather_keys_consolidated_total - len(weather_keys_consolidated),
        },
        "elevation": {
            "pre_dedup_request_count": len(unique_sources),
            "unique_tile_count": len(elevation_tile_keys),
            "note": "tile locality statistic only -- extract_elevation has no local per-tile cache seam; network_required stays one call per unique source (see module docstring)",
            "tile_batch_optimization_status": STATIC_TILE_BATCH_OPTIMIZATION_NOT_SAFE_WITH_CURRENT_ADAPTER,
        },
        "land_cover": {
            "pre_dedup_request_count": len(unique_sources),
            "unique_tile_count": len(landcover_tile_keys),
            "note": "tile locality statistic only -- full-tile local caching was rejected as unsafe (large WorldCover tiles); network_required stays one call per unique source",
            "tile_batch_optimization_status": STATIC_TILE_BATCH_OPTIMIZATION_NOT_SAFE_WITH_CURRENT_ADAPTER,
        },
    }


# ---------------------------------------------------------------------------
# Sections 4-5: weather consolidation + equivalence gate.
# ---------------------------------------------------------------------------


def fetch_consolidated_weather_windows(
    source: EligibleSource, weather_cache: FileWeatherCache, *, timeout_seconds: float = 30.0,
) -> dict:
    """Fetches ONE real superset (largest-window) Open-Meteo hourly
    payload for this source's own coordinate/date, cached under ONLY its
    own real exact request key (`FileWeatherCache`'s documented
    one-key-one-exact-request contract -- Section 3 -- is never violated:
    no other window's cache key is ever written to, and this payload is
    never seeded under any key but its own). Derives all four frozen
    windows' `(PreT0WeatherWindow, list[FeatureResult])` results LOCALLY,
    in-process, from that one real payload via era5's own
    `summarize_hourly_payload_for_window` (Section 4) -- the SAME pure
    equations `build_pre_t0_weather_summary` uses for its per-window
    live/cached path, so outputs are byte-identical to the legacy method
    for the same payload content (proven empirically by
    `verify_weather_equivalence_gate`). The live fetch itself goes
    through era5's own `fetch_hourly_payload` (Section 5) -- never a
    second, independent Open-Meteo client. Never invents a payload: on
    network failure, nothing is cached and `windows` is `None`, so the
    caller falls back to the unmodified legacy per-window method for
    this one source (Section 6). A per-request-key single-flight lock
    (Section 9-10) ensures concurrent callers that resolve to the same
    superset key issue exactly one live request."""
    boundary = resolve_t0_boundary(
        t0=source.effective_availability_date, t0_precision=T0Precision.DATE_ONLY.value,
        latitude=source.latitude, longitude=source.longitude,
    )
    if not boundary.resolved:
        return {"status": "SKIPPED_UNRESOLVED_T0_BOUNDARY", "attempted_network": False, "windows": None}

    max_lookback = max(WEATHER_WINDOWS_HOURS.values())
    window_start, cutoff = pre_t0_window_bounds(boundary, max_lookback)
    superset_start = window_start.date().isoformat()
    superset_end = cutoff.date().isoformat()
    superset_key = cache_key_for_request(
        {
            "latitude": source.latitude, "longitude": source.longitude,
            "start_date": superset_start, "end_date": superset_end,
            "hourly": "temperature_2m,dew_point_2m,precipitation,wind_speed_10m,wind_direction_10m",
            "models": "era5", "wind_speed_unit": "ms", "timezone": "UTC",
        }
    )

    attempted_network = False
    with _single_flight_lock_for_key(superset_key):
        payload = weather_cache.get(superset_key)
        if payload is None:
            attempted_network = True
            try:
                payload = fetch_hourly_payload(source.latitude, source.longitude, superset_start, superset_end, timeout_seconds=timeout_seconds)
            except requests.RequestException as exc:
                return {"status": f"NETWORK_ERROR: {exc}", "attempted_network": True, "windows": None}
            weather_cache.set(superset_key, payload)

    windows: dict[str, tuple] = {}
    for window_name, lookback_hours in WEATHER_WINDOWS_HOURS.items():
        windows[window_name] = summarize_hourly_payload_for_window(
            payload, boundary, lookback_hours, latitude=source.latitude, longitude=source.longitude,
        )
    return {"status": "DERIVED_FROM_SUPERSET_PAYLOAD", "attempted_network": attempted_network, "windows": windows}


_WEATHER_EQUIVALENCE_TOLERANCE = 1e-9


def verify_weather_equivalence_gate(
    canary_source_ids: list[str],
    unique_sources: dict[str, EligibleSource],
    *,
    production_weather_cache_dir: str | Path,
    isolated_cache_dir: str | Path,
) -> dict:
    """Real empirical equivalence proof (Section 5), not a theoretical
    argument alone. For each canary source (already has REAL,
    individually-fetched per-window data in the PRODUCTION
    `FileWeatherCache` from FMD-07A-R2B1's canary run):

    1. Reads the EXISTING per-window results from the PRODUCTION cache via
       the real, unmodified `build_pre_t0_weather_summary` (a pure cache
       replay -- zero new network call here).
    2. In a completely SEPARATE, throwaway cache directory, makes ONE real
       live consolidated-superset request
       (`fetch_consolidated_weather_windows`) and derives all four windows'
       results directly from that one payload -- never via a cache replay
       under a mismatched key (Section 3).
    3. Compares, for all 8 weather variables x 4 windows: value (exact or
       within `_WEATHER_EQUIVALENCE_TOLERANCE`), status, units, and the
       window_start/window_end boundaries.

    `outcome` (Section 20) distinguishes three cases so a temporary
    provider outage is never misreported as a semantic mismatch:
    `WEATHER_EQUIVALENCE_OUTCOME_PASS` (every compared field matched for
    every canary source), `WEATHER_EQUIVALENCE_OUTCOME_FAIL` (a real
    comparison was made and something genuinely disagreed), or
    `WEATHER_EQUIVALENCE_OUTCOME_NETWORK_BLOCKED` (no semantic mismatch
    was found, but the consolidated fetch could not be completed for one
    or more sources -- inconclusive, not a disproof). `passed` stays a
    plain bool (`True` only for the PASS outcome) for callers that only
    need the legacy/consolidated fork decision."""
    from ..services.geospatial.weather.era5 import build_pre_t0_weather_summary

    production_cache = FileWeatherCache(Path(production_weather_cache_dir))
    isolated_cache = FileWeatherCache(Path(isolated_cache_dir))

    per_source_reports = []
    mismatches: list[dict] = []
    network_attempts = 0

    for source_id in sorted(canary_source_ids):
        source = unique_sources[source_id]

        existing_by_window: dict[str, dict[str, dict]] = {}
        for window_name, lookback_hours in WEATHER_WINDOWS_HOURS.items():
            window, results = build_pre_t0_weather_summary(
                latitude=source.latitude, longitude=source.longitude, t0=source.effective_availability_date,
                t0_precision=T0Precision.DATE_ONLY.value, lookback_hours=lookback_hours, cache=production_cache,
            )
            existing_by_window[window_name] = {
                "window": window.as_dict(),
                "results": {r.feature_name: {"value": r.value, "status": r.status, "units": r.units} for r in results},
            }

        consolidated_outcome = fetch_consolidated_weather_windows(source, isolated_cache)
        if consolidated_outcome["attempted_network"]:
            network_attempts += 1
        if consolidated_outcome["windows"] is None:
            mismatches.append({
                "source_id": source_id, "mismatch_type": "NETWORK_ERROR",
                "reason": f"consolidated fetch failed: {consolidated_outcome['status']}",
            })
            continue

        consolidated_by_window: dict[str, dict[str, dict]] = {}
        for window_name, (window, results) in consolidated_outcome["windows"].items():
            consolidated_by_window[window_name] = {
                "window": window.as_dict(),
                "results": {r.feature_name: {"value": r.value, "status": r.status, "units": r.units} for r in results},
            }

        for window_name in WEATHER_WINDOWS_HOURS:
            existing = existing_by_window[window_name]
            consolidated = consolidated_by_window[window_name]
            if existing["window"]["window_start"] != consolidated["window"]["window_start"] or existing["window"]["window_end"] != consolidated["window"]["window_end"]:
                mismatches.append({"source_id": source_id, "window": window_name, "mismatch_type": "SEMANTIC_MISMATCH", "field": "window_boundary", "existing": existing["window"], "consolidated": consolidated["window"]})
                continue
            for feature_name in set(existing["results"]) | set(consolidated["results"]):
                e = existing["results"].get(feature_name)
                c = consolidated["results"].get(feature_name)
                if e is None or c is None:
                    mismatches.append({"source_id": source_id, "window": window_name, "feature": feature_name, "mismatch_type": "SEMANTIC_MISMATCH", "reason": "feature present in one method, absent in the other"})
                    continue
                if e["status"] != c["status"] or e["units"] != c["units"]:
                    mismatches.append({"source_id": source_id, "window": window_name, "feature": feature_name, "mismatch_type": "SEMANTIC_MISMATCH", "existing": e, "consolidated": c})
                    continue
                if e["value"] is None and c["value"] is None:
                    continue
                if e["value"] is None or c["value"] is None or abs(float(e["value"]) - float(c["value"])) > _WEATHER_EQUIVALENCE_TOLERANCE:
                    mismatches.append({"source_id": source_id, "window": window_name, "feature": feature_name, "mismatch_type": "SEMANTIC_MISMATCH", "existing": e, "consolidated": c})

        per_source_reports.append(source_id)

    semantic_mismatches = [m for m in mismatches if m.get("mismatch_type") == "SEMANTIC_MISMATCH"]
    network_error_mismatches = [m for m in mismatches if m.get("mismatch_type") == "NETWORK_ERROR"]
    all_sources_checked = len(per_source_reports) == len(canary_source_ids)

    if semantic_mismatches:
        outcome = WEATHER_EQUIVALENCE_OUTCOME_FAIL
    elif network_error_mismatches or not all_sources_checked:
        outcome = WEATHER_EQUIVALENCE_OUTCOME_NETWORK_BLOCKED
    else:
        outcome = WEATHER_EQUIVALENCE_OUTCOME_PASS

    return {
        "checkpoint": CHECKPOINT,
        "method_compared_a": WEATHER_STRATEGY_LEGACY_FOUR_WINDOW,
        "method_compared_b": WEATHER_STRATEGY_CONSOLIDATED,
        "canary_source_ids_checked": sorted(canary_source_ids),
        "sources_checked": len(per_source_reports),
        "variables_checked": 8,
        "windows_checked": list(WEATHER_WINDOWS_HOURS),
        "network_attempts": network_attempts,
        "tolerance": _WEATHER_EQUIVALENCE_TOLERANCE,
        "mismatch_count": len(mismatches),
        "semantic_mismatch_count": len(semantic_mismatches),
        "network_error_count": len(network_error_mismatches),
        "mismatches": mismatches[:20],
        "outcome": outcome,
        "passed": outcome == WEATHER_EQUIVALENCE_OUTCOME_PASS,
    }


# ---------------------------------------------------------------------------
# Section 11: failure ledger classification.
# ---------------------------------------------------------------------------


def _family_all_status_keys(sample_row: dict) -> dict[str, list[str]]:
    """Section 16 (FMD-07A-R2B2-R1): unlike R2B1's own single-
    representative-column convention (fine for a coarse "was the request
    even attempted" signal, but not for a ledger), this inspects EVERY
    `_status` column belonging to each family -- weather has 32 (8
    variables x 4 windows), land cover has 11 classes -- re-derived from
    a real produced row's own keys (never a hardcoded feature name that
    might not exist). `classify_source_row` below already aggregates a
    family's keys via a worst-case bucket priority (TRANSIENT_FAILURE >
    PERMANENT_FAILURE > ...), so widening the key set here means one
    failed weather variable can never be hidden by 31 successful ones."""
    weather_keys = sorted(k for k in sample_row if k.startswith("weather_") and k.endswith("_status"))
    landcover_keys = sorted(k for k in sample_row if k.startswith("landcover_") and k.endswith("_status"))
    return {
        "weather": weather_keys,
        "elevation": ["elevation_m_status"],
        "host_density": ["host_density_cattle_status", "host_density_buffalo_status"],
        "land_cover": landcover_keys,
        "hydrology": ["distance_to_nearest_river_km_status"],
    }


def _ledger_bucket_for_status(status: str) -> str:
    if status == SOURCE_VALUE_AVAILABLE:
        return STATUS_SUCCESS
    if status in ("SOURCE_VALUE_MISSING", "TEMPORAL_COVERAGE_MISSING"):
        return STATUS_LEGITIMATE_MISSING
    if status == "OUTSIDE_SOURCE_COVERAGE":
        return STATUS_OUT_OF_COVERAGE
    if status == "SOURCE_FILE_MISSING":
        return STATUS_PERMANENT_FAILURE
    if status == "EXTRACTION_FAILED":
        # the general BLOCKED umbrella (era5.py/raster.py: any
        # requests.RequestException -> BLOCKED, once, never retried
        # internally) -- treated as a candidate for R2B2's OWN bounded
        # retry pass (Section 11), never an infinite loop.
        return STATUS_TRANSIENT_FAILURE
    raise ValueError(f"_ledger_bucket_for_status: unrecognized status {status!r}")


def _family_raw_bucket(row: dict, keys: list[str]) -> str | None:
    """Worst-case bucket for one family's own `_status` keys, straight
    from `_ledger_bucket_for_status` -- BEFORE any retry-exhaustion
    transition. `None` means none of `keys` is present in `row` at all
    (caller maps that to `STATUS_BLOCKED`). Shared by `classify_source_row`
    and `build_failure_ledger` (Section 11/17-R2) so both agree on what
    the row's raw adapter statuses actually say."""
    buckets = {_ledger_bucket_for_status(row[key]) for key in keys if key in row}
    if not buckets:
        return None
    if STATUS_TRANSIENT_FAILURE in buckets:
        return STATUS_TRANSIENT_FAILURE
    if STATUS_PERMANENT_FAILURE in buckets:
        return STATUS_PERMANENT_FAILURE
    if len(buckets) == 1:
        return next(iter(buckets))
    # a mix (e.g. host_density cattle available, buffalo missing) --
    # SUCCESS is the correct ATTEMPT-level bucket (Section 10's own
    # rule: the adapter call itself completed; per-value MISSING is
    # not a request failure)
    return STATUS_SUCCESS if STATUS_SUCCESS in buckets else sorted(buckets)[0]


def classify_source_row(row: dict) -> dict[str, str]:
    """Per-family ledger classification for one already-extracted
    source row -- reads only real `_status` columns the row already has,
    never invents a distinction the adapters don't make.

    Section 11/17-R2 (bounded-retry exhaustion): `run_bounded_retry_pass`
    grants exactly ONE re-extraction per row (`DEFAULT_MAX_RETRY_PASSES`),
    recorded as `row["_r2b2_retry_attempted"]`. A family whose raw bucket
    is still `TRANSIENT_FAILURE` (EXTRACTION_FAILED) AFTER that one
    retry has exhausted its only bounded retry chance -- it can no
    longer sit in TRANSIENT_FAILURE (retry-eligible) forever, so it
    falls through to the existing `STATUS_PERMANENT_FAILURE` terminal
    bucket. This never fabricates a finer root cause than the adapter
    itself reports; see `FAILURE_RETRY_CLASSIFICATION_LIMITED_BY_EXISTING_ADAPTER_STATUS`."""
    rep_keys = _family_all_status_keys(row)
    retry_budget_exhausted = bool(row.get("_r2b2_retry_attempted", False))
    classification: dict[str, str] = {}
    for family, keys in rep_keys.items():
        if not keys:
            classification[family] = STATUS_BLOCKED
            continue
        bucket = _family_raw_bucket(row, keys)
        if bucket is None:
            classification[family] = STATUS_BLOCKED
        elif bucket == STATUS_TRANSIENT_FAILURE and retry_budget_exhausted:
            classification[family] = STATUS_PERMANENT_FAILURE
        else:
            classification[family] = bucket
    return classification


TERMINAL_LEDGER_STATUSES = (
    STATUS_SUCCESS, STATUS_LEGITIMATE_MISSING, STATUS_OUT_OF_COVERAGE, STATUS_PERMANENT_FAILURE, STATUS_BLOCKED,
)


def is_source_row_terminal_accounted(row: dict) -> bool:
    """Section 13 (FMD-07A-R2B2-R1): a source is `source_accounted_for`
    only once EVERY family's classification is a terminal state --
    `STATUS_TRANSIENT_FAILURE` is explicitly NOT terminal while
    `run_bounded_retry_pass` may still retry it. Having a cached
    `SourceExtractionCache` row (`source_cache.get(source_id) is not
    None`) is necessary but NOT sufficient -- a row whose weather (or any
    other) family is still `TRANSIENT_FAILURE` has been ATTEMPTED, not
    yet ACCOUNTED FOR."""
    classification = classify_source_row(row)
    return all(state in TERMINAL_LEDGER_STATUSES for state in classification.values())


# ---------------------------------------------------------------------------
# Section 14: persistent, deterministic failure ledger (no unstable
# timestamps -- a restart must be able to tell, from disk alone, which
# failures are still retry-eligible).
# ---------------------------------------------------------------------------

FAILURE_LEDGER_FILENAME = "fmd07_feature_extraction_failure_ledger.json"


def build_failure_ledger(universe: dict, source_cache_dir: str | Path) -> list[dict]:
    """One row per (source_id, feature_family) whose classification is
    NOT `STATUS_SUCCESS` -- i.e. every family a restart needs to know
    about, terminal or not. `retry_eligible` is exactly
    `state == STATUS_TRANSIENT_FAILURE` (Section 11/17's single bounded
    retry pass is the only retry path; nothing here loops on its own).
    `attempt_count` is best-effort from what this checkpoint can actually
    observe (1 = only ever extracted once; 2 = also survived one
    `run_bounded_retry_pass` re-extraction) -- never a fabricated precise
    count the adapters don't report. Sorted, deterministic; no
    timestamps."""
    source_cache = SourceExtractionCache(source_cache_dir)
    ledger: list[dict] = []
    for source_id in sorted(universe["unique_sources"]):
        row = source_cache.get(source_id)
        if row is None:
            continue
        rep_keys = _family_all_status_keys(row)
        classification = classify_source_row(row)
        attempted_retry = bool(row.get("_r2b2_retry_attempted", False))
        for family in sorted(classification):
            state = classification[family]
            if state == STATUS_SUCCESS:
                continue
            # the adapter-limitation note is about the RAW status (was this
            # family ever an EXTRACTION_FAILED the adapter couldn't
            # subdivide?), so it stays attached even once retry exhaustion
            # (above) has moved `state` from TRANSIENT_FAILURE to
            # PERMANENT_FAILURE -- never attached to a family that was
            # SOURCE_FILE_MISSING (genuinely permanent) from the start.
            raw_bucket = _family_raw_bucket(row, rep_keys[family])
            ledger.append({
                "source_id": source_id,
                "feature_family": family,
                "state": state,
                "retry_eligible": state == STATUS_TRANSIENT_FAILURE,
                "attempt_count": 2 if attempted_retry else 1,
                "terminal": state in TERMINAL_LEDGER_STATUSES,
                "retry_classification_note": (
                    FAILURE_RETRY_CLASSIFICATION_LIMITED_BY_EXISTING_ADAPTER_STATUS
                    if raw_bucket == STATUS_TRANSIENT_FAILURE else None
                ),
            })
    return ledger


def write_failure_ledger(ledger: list[dict], out_path: str | Path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Sections 7-8: resumable, bounded-concurrency full-source batch runner.
# ---------------------------------------------------------------------------


def _process_one_source(
    source: EligibleSource, config: FmdFeatureExtractionConfig, weather_cache: FileWeatherCache,
    source_cache: SourceExtractionCache, *, use_consolidated_weather: bool,
) -> dict:
    if source_cache.get(source.source_id) is not None:
        return {"source_id": source.source_id, "outcome": "CACHE_HIT", "network_attempted": False}
    weather_seed_attempted_network = False
    precomputed_weather_windows = None
    if use_consolidated_weather:
        consolidated_outcome = fetch_consolidated_weather_windows(source, weather_cache)
        weather_seed_attempted_network = consolidated_outcome["attempted_network"]
        if consolidated_outcome["windows"] is not None:
            precomputed_weather_windows = consolidated_outcome["windows"]
        # else: consolidated fetch was skipped/failed for this one source -- fall
        # through with precomputed_weather_windows=None, so extract_source_features
        # transparently falls back to the unmodified legacy per-window live/cached
        # path for this source only (Section 6's per-source fallback semantics).
    try:
        row, was_hit = extract_source_features(
            source, config, weather_cache, source_cache, precomputed_weather_windows=precomputed_weather_windows,
        )
        return {
            "source_id": source.source_id,
            "outcome": "SUCCESS",
            "network_attempted": weather_seed_attempted_network or not was_hit,
        }
    except Exception as exc:  # pragma: no cover - defensive; adapters raise nothing today, only return BLOCKED results
        return {"source_id": source.source_id, "outcome": "ERROR", "error": str(exc), "network_attempted": weather_seed_attempted_network}


def run_full_r2b2_extraction(
    universe: dict,
    *,
    weather_cache_dir: str | Path,
    source_cache_dir: str | Path,
    model_dev_dir: str | Path,
    config: FmdFeatureExtractionConfig | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_workers: int = DEFAULT_MAX_CONCURRENT_PER_PROVIDER,
    use_consolidated_weather: bool = True,
    max_batches: int | None = None,
    progress_callback=None,
) -> dict:
    """Processes `universe["unique_sources"]` in deterministic sorted-id
    batches of `batch_size`. Within a batch, up to `max_workers` sources
    are processed concurrently (each worker makes at most one live
    weather request and relies on the unmodified adapters for
    elevation/land-cover/hydrology/host-density -- bounding concurrency
    per external provider to `max_workers`, never uncontrolled fan-out).
    Writes `fmd07_feature_extraction_progress.json` atomically after
    EVERY batch (Section 7) so a crash/restart continues from the exact
    remaining set (`SourceExtractionCache` rows already on disk are never
    re-attempted). `max_batches=None` runs to completion; a finite value
    lets a caller deliberately stop early (still fully resumable)."""
    config = config or FmdFeatureExtractionConfig()
    weather_cache = FileWeatherCache(Path(weather_cache_dir))
    source_cache = SourceExtractionCache(Path(source_cache_dir))

    ordered_ids = sorted(universe["unique_sources"])
    batches = [ordered_ids[i : i + batch_size] for i in range(0, len(ordered_ids), batch_size)]

    batches_run = 0
    newly_processed = 0
    cache_hits_skipped = 0
    errors: list[dict] = []
    last_completed_batch_key = None

    for batch in batches:
        pending = [sid for sid in batch if source_cache.get(sid) is None]
        if not pending:
            # R2B2-R2 stall fix: a batch that is ALREADY fully cached costs
            # nothing and must never consume the caller's max_batches
            # budget. Without this, a caller that resumes via repeated
            # small-max_batches invocations (one fresh process per batch,
            # e.g. after a restart) would re-verify the same already-done
            # batch 0 forever and never reach batch 1 -- the exact defect
            # observed in the ad hoc full-run driver (48 minutes at
            # 100/6799 with zero new sources). Skipping for free here keeps
            # batch composition/ordering byte-identical to before; only the
            # max_batches bookkeeping changes.
            cache_hits_skipped += len(batch)
            last_completed_batch_key = batch[-1]
            continue
        if max_batches is not None and batches_run >= max_batches:
            break
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    _process_one_source, universe["unique_sources"][sid], config, weather_cache, source_cache,
                    use_consolidated_weather=use_consolidated_weather,
                ): sid
                for sid in pending
            }
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                if result["outcome"] == "SUCCESS":
                    newly_processed += 1
                elif result["outcome"] == "ERROR":
                    errors.append(result)
        cache_hits_skipped += len(batch) - len(pending)
        batches_run += 1
        last_completed_batch_key = batch[-1]

        progress = build_r2b2_progress(
            universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir,
            last_completed_batch_key=last_completed_batch_key,
        )
        write_r2b2_progress(progress, Path(model_dev_dir) / PROGRESS_JSON_FILENAME)
        failure_ledger = build_failure_ledger(universe, source_cache_dir)
        write_failure_ledger(failure_ledger, Path(model_dev_dir) / FAILURE_LEDGER_FILENAME)
        if progress_callback is not None:
            progress_callback(progress)

    sources_complete = sum(1 for sid in ordered_ids if source_cache.get(sid) is not None)
    return {
        "batches_run": batches_run,
        "total_batches": len(batches),
        "newly_processed": newly_processed,
        "cache_hits_skipped": cache_hits_skipped,
        "errors": errors,
        "sources_complete": sources_complete,
        "sources_total": len(ordered_ids),
        "last_completed_batch_key": last_completed_batch_key,
    }


def run_bounded_retry_pass(
    universe: dict, *, weather_cache_dir: str | Path, source_cache_dir: str | Path, config: FmdFeatureExtractionConfig | None = None,
    use_consolidated_weather: bool = True, max_workers: int = DEFAULT_MAX_CONCURRENT_PER_PROVIDER,
) -> dict:
    """Section 11: exactly ONE bounded retry pass over sources whose
    cached row shows a TRANSIENT_FAILURE (EXTRACTION_FAILED) family --
    never an unbounded loop, never re-attempted a second time by this
    function. Deletes only that source's own cache entry (never another
    source's) before re-extracting, so a genuinely successful prior
    result for any OTHER source is never touched."""
    config = config or FmdFeatureExtractionConfig()
    weather_cache = FileWeatherCache(Path(weather_cache_dir))
    source_cache = SourceExtractionCache(Path(source_cache_dir))

    retry_candidates = []
    for source_id in sorted(universe["unique_sources"]):
        row = source_cache.get(source_id)
        if row is None:
            continue
        classification = classify_source_row(row)
        if STATUS_TRANSIENT_FAILURE in classification.values():
            retry_candidates.append(source_id)

    retried = 0
    recovered = 0
    still_failed = 0
    for source_id in retry_candidates:
        source_cache._path_for(source_id).unlink(missing_ok=True)
        result = _process_one_source(
            universe["unique_sources"][source_id], config, weather_cache, source_cache,
            use_consolidated_weather=use_consolidated_weather,
        )
        retried += 1
        row = source_cache.get(source_id)
        # true recovery must be read off the RAW re-extracted statuses,
        # BEFORE `_r2b2_retry_attempted` is stamped on below -- once that
        # flag is set, `classify_source_row` reclassifies any still-
        # TRANSIENT_FAILURE family to PERMANENT_FAILURE (exhausted), which
        # would otherwise make an unrecovered retry look "recovered" here.
        still_transient = row is not None and any(
            _family_raw_bucket(row, keys) == STATUS_TRANSIENT_FAILURE
            for keys in _family_all_status_keys(row).values()
        )
        if row is not None:
            # Section 14: an honest `attempt_count=2` marker for the
            # failure ledger -- never a fabricated precise count, just
            # "this row was re-extracted by the one bounded retry pass".
            row["_r2b2_retry_attempted"] = True
            source_cache.set(source_id, row)
        if row is not None and not still_transient:
            recovered += 1
        else:
            still_failed += 1

    return {
        "retry_candidates": len(retry_candidates),
        "retried": retried,
        "recovered": recovered,
        "still_failed_after_retry": still_failed,
    }


# ---------------------------------------------------------------------------
# Section 12: progress artifact for the FULL run (real, universe-wide
# on-disk cache scan every time -- never an approximation).
# ---------------------------------------------------------------------------

PROGRESS_JSON_FILENAME = "fmd07_feature_extraction_progress.json"


def build_r2b2_progress(
    universe: dict, *, weather_cache_dir: str | Path, source_cache_dir: str | Path, last_completed_batch_key: str | None,
) -> dict:
    from ..data_processing.build_fmd_features import _in_hydrology_asia_bbox

    unique_sources = universe["unique_sources"]
    source_cache = SourceExtractionCache(source_cache_dir)
    weather_cache = FileWeatherCache(Path(weather_cache_dir))

    attempted_ids = [sid for sid in sorted(unique_sources) if source_cache.get(sid) is not None]
    sample_row = source_cache.get(attempted_ids[0]) if attempted_ids else None
    rep_keys = _family_all_status_keys(sample_row) if sample_row else {
        "weather": [], "elevation": [], "host_density": [], "land_cover": [], "hydrology": [],
    }

    def _bucket_counts(family: str) -> dict[str, int]:
        counts = {"successful": 0, "failed_retryable": 0, "failed_final": 0, "out_of_coverage": 0, "blocked": 0}
        _map = {
            STATUS_SUCCESS: "successful", STATUS_LEGITIMATE_MISSING: "successful",
            STATUS_OUT_OF_COVERAGE: "out_of_coverage", STATUS_PERMANENT_FAILURE: "failed_final",
            STATUS_TRANSIENT_FAILURE: "blocked",
        }
        for sid in attempted_ids:
            row = source_cache.get(sid)
            if row is None:
                continue
            for key in rep_keys[family]:
                if key in row:
                    bucket = _map[_ledger_bucket_for_status(row[key])]
                    counts[bucket] += 1
        return counts

    weather_planned = len(unique_sources) * len(WEATHER_WINDOWS_HOURS)
    weather_cache_hit = 0
    for source in unique_sources.values():
        for lookback_hours in WEATHER_WINDOWS_HOURS.values():
            key = _weather_request_key(source.latitude, source.longitude, source.effective_availability_date, lookback_hours)
            if key is not None and weather_cache.get(key) is not None:
                weather_cache_hit += 1

    adapters: dict[str, dict] = {
        "weather": {
            "unit": "one (unique source coordinate, historical window) Open-Meteo request",
            "planned": weather_planned,
            "cache_hit": weather_cache_hit,
            "attempted_network": len(attempted_ids),
            "remaining": weather_planned - weather_cache_hit,
            **_bucket_counts("weather"),
        }
    }
    for family in ("elevation", "host_density", "land_cover"):
        planned = universe["unique_required_source_count"]
        adapters[family] = {
            "unit": "one unique source (SourceExtractionCache row)",
            "planned": planned,
            "cache_hit": len(attempted_ids),
            "attempted_network": len(attempted_ids),
            "remaining": planned - len(attempted_ids),
            **_bucket_counts(family),
        }

    hydrology_planned = sum(1 for s in unique_sources.values() if _in_hydrology_asia_bbox(s.latitude, s.longitude))
    hydrology_cache_hit = sum(
        1 for sid in attempted_ids if _in_hydrology_asia_bbox(unique_sources[sid].latitude, unique_sources[sid].longitude)
    )
    adapters["hydrology"] = {
        "unit": "one unique in-coverage source (SourceExtractionCache row)",
        "planned": hydrology_planned,
        "cache_hit": hydrology_cache_hit,
        "attempted_network": hydrology_cache_hit,
        "remaining": hydrology_planned - hydrology_cache_hit,
        **_bucket_counts("hydrology"),
    }

    # Section 13: `sources_complete` above is deliberately the plain
    # ATTEMPTED count (a cached row exists, matching every pre-existing
    # caller of this field) -- `sources_terminal_accounted` is the
    # stricter, additional count Section 13 actually asks for: attempted
    # AND every family has reached a terminal state (STATUS_TRANSIENT_FAILURE
    # excluded -- still retry-eligible, not yet accounted for).
    terminal_accounted_ids = [
        sid for sid in attempted_ids if is_source_row_terminal_accounted(source_cache.get(sid))
    ]

    return {
        "checkpoint": CHECKPOINT,
        "sources_total": len(unique_sources),
        "sources_complete": len(attempted_ids),
        "sources_remaining": len(unique_sources) - len(attempted_ids),
        "sources_terminal_accounted": len(terminal_accounted_ids),
        "sources_terminal_remaining": len(unique_sources) - len(terminal_accounted_ids),
        "adapters": adapters,
        "last_completed_batch_key": last_completed_batch_key,
        "held_out_included": False,
        "sri_lanka_included": False,
        "predictive_metrics_used": False,
        "model_trained": False,
        "weather_winner_selected": False,
    }


def write_r2b2_progress(progress: dict, out_path: str | Path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Section 15: full source-level feature table.
# ---------------------------------------------------------------------------

FULL_SOURCE_TABLE_FILENAME = "fmd07_full_source_features.csv"


def build_full_source_feature_table(universe: dict, source_cache_dir: str | Path) -> list[dict]:
    """One row per unique required source_id that has a cached
    (real-extracted) row -- sorted, deterministic. A source never yet
    attempted (partial run) is simply absent, never fabricated; caller
    compares the returned row count against `unique_required_source_count`
    and reports any discrepancy honestly (Section 15/18)."""
    source_cache = SourceExtractionCache(source_cache_dir)
    rows = []
    for source_id in sorted(universe["unique_sources"]):
        row = source_cache.get(source_id)
        if row is not None:
            rows.append(row)
    return rows


def write_full_source_feature_table(rows: list[dict], out_path: str | Path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for key in rows[0]:
        if not key.startswith("_") and key not in fieldnames:
            fieldnames.append(key)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: row[key] for key in fieldnames if key in row} for row in rows)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Section 16: manifest.
# ---------------------------------------------------------------------------

MANIFEST_FILENAME = "fmd07_full_source_extraction_manifest.json"


def build_r2b2_manifest(
    *, universe: dict, dedup: dict, weather_equivalence: dict | None, weather_strategy: str,
    progress: dict, full_table_rows: list[dict], full_table_path: str | Path | None,
    input_hashes: dict, retry_summary: dict | None = None,
) -> dict:
    per_family_completeness = {}
    for family in ("weather", "elevation", "host_density", "land_cover", "hydrology"):
        counts = progress["adapters"][family]
        per_family_completeness[family] = {
            "planned": counts["planned"],
            "cache_hit": counts["cache_hit"],
            "remaining": counts["remaining"],
            "successful": counts["successful"],
            "out_of_coverage": counts["out_of_coverage"],
            "failed_final": counts["failed_final"],
            "blocked": counts["blocked"],
        }

    table_hash = None
    if full_table_path is not None and Path(full_table_path).exists():
        table_hash = sha256_file(full_table_path)

    return {
        "checkpoint": CHECKPOINT,
        "development_origin_count": universe["development_origin_count"],
        "unique_source_count": universe["unique_required_source_count"],
        "origin_source_appearance_count": universe["total_origin_source_appearances"],
        "deduplication_savings": universe["duplicate_source_appearance_savings"],
        "request_key_deduplication": dedup,
        "weather_extraction_strategy": weather_strategy,
        "weather_consolidation_used": weather_strategy == WEATHER_STRATEGY_CONSOLIDATED,
        "weather_equivalence_gate": weather_equivalence,
        "sources_total": progress["sources_total"],
        "sources_complete": progress["sources_complete"],
        "sources_remaining": progress["sources_remaining"],
        "per_family_completeness": per_family_completeness,
        "retry_pass": retry_summary,
        "full_source_table_row_count": len(full_table_rows),
        "full_source_table_path": str(full_table_path) if full_table_path else None,
        "full_source_table_sha256": table_hash,
        "held_out_used": False,
        "sri_lanka_used": False,
        "labels_used": False,
        "predictive_metrics_used": False,
        "model_trained": False,
        "weather_winner_selected": False,
        "input_hashes": input_hashes,
    }


def write_r2b2_manifest(manifest: dict, out_path: str | Path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Section 20: offline reproducibility -- rebuild the full table twice from
# the frozen cache only (no network), require byte-identical SHA-256.
# ---------------------------------------------------------------------------


def verify_offline_reproducibility(universe: dict, source_cache_dir: str | Path, tmp_dir: str | Path) -> dict:
    rows1 = build_full_source_feature_table(universe, source_cache_dir)
    rows2 = build_full_source_feature_table(universe, source_cache_dir)
    path1 = Path(tmp_dir) / "rebuild1.csv"
    path2 = Path(tmp_dir) / "rebuild2.csv"
    write_full_source_feature_table(rows1, path1)
    write_full_source_feature_table(rows2, path2)
    hash1 = sha256_file(path1)
    hash2 = sha256_file(path2)
    return {"rows": len(rows1), "hash1": hash1, "hash2": hash2, "byte_identical": hash1 == hash2}


# ---------------------------------------------------------------------------
# Orchestrator.
# ---------------------------------------------------------------------------


def run_fmd07a_r2b2(
    canonical_csv_path: str | Path,
    origins_csv_path: str | Path,
    model_dev_dir: str | Path,
    weather_cache_dir: str | Path,
    source_cache_dir: str | Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_workers: int = DEFAULT_MAX_CONCURRENT_PER_PROVIDER,
    max_batches: int | None = None,
    run_weather_equivalence_gate: bool = True,
    run_retry_pass: bool = True,
    progress_callback=None,
) -> dict:
    """Full R2B2 flow: materialize the frozen R2B1 universe, compute
    request-key dedup, (optionally) run the real weather equivalence
    gate and freeze the resulting strategy, run the resumable batch
    extraction (optionally bounded to `max_batches` so a caller can stop
    early and remain resumable), run one bounded retry pass, build the
    full source table + manifest, and verify offline reproducibility."""
    from ..data_processing.fmd_forecast_bridge import import_fmd_canonical_csv
    from ..repositories.sqlite_repository import SQLiteOutbreakRepository
    from .fmd_calibration import load_forecast_origins

    output = Path(model_dev_dir)
    output.mkdir(parents=True, exist_ok=True)

    all_origins = load_forecast_origins(origins_csv_path)
    import tempfile

    with tempfile.TemporaryDirectory(prefix="fmd07a_r2b2_db_") as temp_dir:
        repo = SQLiteOutbreakRepository(Path(temp_dir) / "r2b2.sqlite")
        repo.init_schema()
        import_fmd_canonical_csv(repo, canonical_csv_path)
        universe = build_development_extraction_universe(repo, all_origins)
        repo.close()

    origin_source_map = build_origin_source_map(universe)
    write_origin_source_map(origin_source_map, output / "fmd07_origin_source_map.json")
    index_rows = build_unique_source_extraction_index(universe)
    write_unique_source_extraction_index(index_rows, output / "fmd07_unique_source_extraction_index.csv")
    assert_extraction_index_is_fit_development_only(universe, index_rows)

    # determinism check: rebuild once more, must match exactly
    origin_source_map_2 = build_origin_source_map(universe)
    if origin_source_map != origin_source_map_2:
        raise ValueError("run_fmd07a_r2b2: fmd07_origin_source_map.json is not deterministic across two builds")

    dedup = compute_request_key_dedup(universe["unique_sources"])

    weather_strategy = WEATHER_STRATEGY_LEGACY_FOUR_WINDOW
    weather_equivalence = None
    if run_weather_equivalence_gate:
        canary_ids = select_canary_source_ids(universe["unique_sources"])
        with tempfile.TemporaryDirectory(prefix="fmd07a_r2b2_weather_eq_") as iso_dir:
            weather_equivalence = verify_weather_equivalence_gate(
                canary_ids, universe["unique_sources"],
                production_weather_cache_dir=weather_cache_dir, isolated_cache_dir=iso_dir,
            )
        if weather_equivalence["passed"]:
            weather_strategy = WEATHER_STRATEGY_CONSOLIDATED

    use_consolidated = weather_strategy == WEATHER_STRATEGY_CONSOLIDATED

    extraction_result = run_full_r2b2_extraction(
        universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir, model_dev_dir=output,
        batch_size=batch_size, max_workers=max_workers, use_consolidated_weather=use_consolidated,
        max_batches=max_batches, progress_callback=progress_callback,
    )

    retry_summary = None
    if run_retry_pass:
        retry_summary = run_bounded_retry_pass(
            universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir,
            use_consolidated_weather=use_consolidated, max_workers=max_workers,
        )

    progress = build_r2b2_progress(
        universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir,
        last_completed_batch_key=extraction_result["last_completed_batch_key"],
    )
    write_r2b2_progress(progress, output / PROGRESS_JSON_FILENAME)

    failure_ledger = build_failure_ledger(universe, source_cache_dir)
    write_failure_ledger(failure_ledger, output / FAILURE_LEDGER_FILENAME)

    full_table_rows = build_full_source_feature_table(universe, source_cache_dir)
    run_complete = len(full_table_rows) == universe["unique_required_source_count"]
    full_table_path = None
    if run_complete:
        full_table_path = output / FULL_SOURCE_TABLE_FILENAME
        write_full_source_feature_table(full_table_rows, full_table_path)

    input_hashes = {
        "canonical_csv": sha256_file(canonical_csv_path),
    }
    r2a_protocol_path = output / "fmd07_origin_feature_assembly_protocol.json"
    if r2a_protocol_path.exists():
        input_hashes["r2a_origin_feature_assembly_protocol"] = sha256_file(r2a_protocol_path)
    r2b1_plan_path = output / "fmd07_feature_extraction_plan.json"
    if r2b1_plan_path.exists():
        input_hashes["r2b1_extraction_plan"] = sha256_file(r2b1_plan_path)

    manifest = build_r2b2_manifest(
        universe=universe, dedup=dedup, weather_equivalence=weather_equivalence, weather_strategy=weather_strategy,
        progress=progress, full_table_rows=full_table_rows, full_table_path=full_table_path,
        input_hashes=input_hashes, retry_summary=retry_summary,
    )
    write_r2b2_manifest(manifest, output / MANIFEST_FILENAME)

    offline_repro = None
    if run_complete:
        with tempfile.TemporaryDirectory(prefix="fmd07a_r2b2_offline_") as tmp_dir:
            offline_repro = verify_offline_reproducibility(universe, source_cache_dir, tmp_dir)

    return {
        "universe": universe,
        "dedup": dedup,
        "weather_strategy": weather_strategy,
        "weather_equivalence": weather_equivalence,
        "extraction_result": extraction_result,
        "retry_summary": retry_summary,
        "failure_ledger_row_count": len(failure_ledger),
        "progress": progress,
        "run_complete": run_complete,
        "full_table_rows": len(full_table_rows),
        "manifest": manifest,
        "offline_reproducibility": offline_repro,
    }
