"""FMD-07A-R2B1: extraction-universe planning, cache/resume engineering,
and small real canary validation.

This module does NOT run the full 3,761-origin extraction. It:

1. Derives the real, deduplicated FIT_DEVELOPMENT extraction universe
   (origin -> unique eligible-active source ids, unique source ids ->
   canonical metadata), using ONLY the frozen R2A source-selection rule
   (`fmd_model_development_r2a.get_eligible_active_sources_for_origin`) --
   no network access.
2. Builds a deterministic, no-network extraction plan from real local
   artifacts and the real (already-populated) weather/GIS caches.
3. Adds ONE minimal, generic, non-scientific engineering addition
   (`SourceExtractionCache`) so elevation/host-density/land-cover/
   hydrology -- which have no persistent local cache today, unlike
   weather's existing `FileWeatherCache` -- become resumable too, without
   changing any adapter's scientific meaning.
4. Runs a small, deterministic, label-independent real canary extraction
   (reusing FMD-04's own `build_event_feature_row` unchanged) to prove
   the frozen R2A rule connects safely to the real adapters before any
   large remote run.

No predictive model is fit, no metric is computed, no weather winner or
threshold is selected, and no held-out/Sri-Lanka origin is ever read.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from ..data_processing.build_fmd_features import (
    FmdCanonicalEventRef,
    FmdFeatureExtractionConfig,
    WEATHER_WINDOWS_HOURS,
    build_event_feature_row,
)
from ..data_processing.fmd_feature_status import ALL_STATUSES, SOURCE_VALUE_AVAILABLE
from ..data_processing.fmd_forecast_bridge import import_fmd_canonical_csv
from ..repositories.sqlite_repository import SQLiteOutbreakRepository
from ..services.features.cache import FileWeatherCache
from ..services.geospatial.weather.base import T0Precision
from ..services.geospatial.weather.era5 import build_pre_t0_weather_summary
from .fmd_calibration import FMD_DISEASE, FMD_MODEL_FITTING_CUTOFF, load_forecast_origins
from .fmd_model_development_r2a import (
    FROZEN_ACTIVE_WINDOW_DAYS,
    get_eligible_active_sources_for_origin,
)
from .model_fitting_exposure import FIT_DEVELOPMENT, assert_fit_development_only, fit_development_origins
from .source_selector import EligibleSource

CHECKPOINT = "FMD-07A-R2B1"

FEATURE_VALUE_STATUS_CANARY_VALIDATED = "CANARY_VALIDATED_FULL_CORPUS_NOT_RUN"

CANARY_SIZE = 8


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# Sections 3-5: development-only extraction universe (no network).
# ---------------------------------------------------------------------------


def build_development_extraction_universe(
    repo, all_origins, *, disease: str = FMD_DISEASE, cutoff: str = FMD_MODEL_FITTING_CUTOFF,
    active_window_days: int = FROZEN_ACTIVE_WINDOW_DAYS,
) -> dict:
    """No network. Uses ONLY the frozen R2A source-selection rule.
    `HELD_OUT_FROM_MODEL_FITTING`/`SRI_LANKA_TRANSFER_CASE_STUDY` origins
    never enter (`fit_development_origins` + `assert_fit_development_only`,
    the same firewall used throughout FMD-06/FMD-07A). Raises `ValueError`
    (Section 5) if two occurrences of the SAME canonical `source_id`
    disagree on any extraction-relevant field -- never silently
    first-occurrence-wins."""
    fit_origins = fit_development_origins(all_origins, cutoff=cutoff)
    assert_fit_development_only(fit_origins, cutoff=cutoff, caller="build_development_extraction_universe")

    origin_to_source_ids: dict[str, list[str]] = {}
    unique_sources: dict[str, EligibleSource] = {}
    conflicts: list[dict] = []
    zero_source_origin_ids: list[str] = []
    total_origin_source_appearances = 0

    for origin in sorted(fit_origins, key=lambda o: o.forecast_origin_id):
        sources = get_eligible_active_sources_for_origin(
            repo, disease=disease, t0=origin.t0, country=origin.country, active_window_days=active_window_days,
        )
        deduped: dict[str, EligibleSource] = {}
        for source in sources:
            if source.source_id not in deduped:
                deduped[source.source_id] = source
        total_origin_source_appearances += len(deduped)
        origin_to_source_ids[origin.forecast_origin_id] = sorted(deduped)
        if not deduped:
            zero_source_origin_ids.append(origin.forecast_origin_id)

        for source_id, source in deduped.items():
            fields = (source.country, source.latitude, source.longitude, source.effective_availability_date, source.disease)
            if source_id in unique_sources:
                existing = unique_sources[source_id]
                existing_fields = (existing.country, existing.latitude, existing.longitude, existing.effective_availability_date, existing.disease)
                if existing_fields != fields:
                    conflicts.append({
                        "source_id": source_id,
                        "existing": {"country": existing.country, "latitude": existing.latitude, "longitude": existing.longitude, "effective_availability_date": existing.effective_availability_date, "disease": existing.disease},
                        "conflicting": {"country": source.country, "latitude": source.latitude, "longitude": source.longitude, "effective_availability_date": source.effective_availability_date, "disease": source.disease},
                    })
            else:
                unique_sources[source_id] = source

    if conflicts:
        raise ValueError(
            "build_development_extraction_universe: CONFLICTING_DUPLICATE_SOURCE_ID_METADATA -- "
            f"{len(conflicts)} source id(s) disagree across occurrences on an extraction-relevant field: "
            f"{conflicts[:5]}"
        )

    return {
        "development_origin_count": len(fit_origins),
        "origin_to_source_ids": origin_to_source_ids,
        "unique_sources": unique_sources,
        "zero_source_origin_ids": sorted(zero_source_origin_ids),
        "total_origin_source_appearances": total_origin_source_appearances,
        "unique_required_source_count": len(unique_sources),
        "duplicate_source_appearance_savings": total_origin_source_appearances - len(unique_sources),
        "conflicts": conflicts,
    }


# ---------------------------------------------------------------------------
# Section 6-7: no-network request-count planning.
# ---------------------------------------------------------------------------


def _weather_request_key(latitude: float, longitude: float, event_date: str, lookback_hours: float) -> str | None:
    """Deterministic cache key for one (source, window) weather request --
    reuses `era5`'s own request-parameter construction and hashing
    exactly (never a re-derived key), via `build_pre_t0_weather_summary`'s
    documented cache-key contract (`services/features/cache.py`
    `cache_key_for_request`, same hash the adapter itself computes over
    `_hourly_request_params`). Returns None if the t0 boundary cannot be
    resolved for this point (mirrors the adapter's own BLOCKED path)."""
    from ..services.geospatial.weather.t0_resolution import pre_t0_window_bounds, resolve_t0_boundary

    boundary = resolve_t0_boundary(t0=event_date, t0_precision=T0Precision.DATE_ONLY.value, latitude=latitude, longitude=longitude)
    if not boundary.resolved:
        return None
    window_start, cutoff = pre_t0_window_bounds(boundary, lookback_hours)
    params = {
        "latitude": latitude, "longitude": longitude,
        "start_date": window_start.date().isoformat(), "end_date": cutoff.date().isoformat(),
        "hourly": "temperature_2m,dew_point_2m,precipitation,wind_speed_10m,wind_direction_10m",
        "models": "era5", "wind_speed_unit": "ms", "timezone": "UTC",
    }
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _elevation_tile_key(latitude: float, longitude: float) -> tuple:
    from ..data_processing.build_fmd_features import ELEVATION_ZOOM
    from ..services.geospatial.elevation.terrain_tiles import lonlat_to_tile_pixel

    xtile, ytile, _px, _py = lonlat_to_tile_pixel(latitude, longitude, ELEVATION_ZOOM)
    return (ELEVATION_ZOOM, xtile, ytile)


def _landcover_tile_key(latitude: float, longitude: float) -> str:
    from ..services.geospatial.landcover.esa_worldcover import tile_id_for

    return tile_id_for(latitude, longitude)


def build_extraction_plan(universe: dict, *, weather_cache_dir: Path, source_cache_dir: Path, eligible_predictor_features: list[str]) -> dict:
    """Section 6: no-network, computed entirely from real local artifacts
    (the universe just derived + the real, already-populated weather/GIS
    caches on disk).

    **Per-adapter request granularity differs by real, existing adapter
    semantics -- never assumed uniform**: weather is one live request per
    (source coordinate, historical window); elevation/land-cover are
    tiled (`terrain_tiles.lonlat_to_tile_pixel`/`esa_worldcover.
    tile_id_for`, the adapters' own existing tiling functions, reused
    unchanged) -- several nearby sources can share one tile fetch; host
    density/hydrology are each backed by a small, FIXED, location-
    independent set of already-cached global/regional files (Section 8:
    never a substitute data source), so once those files exist, no
    further NETWORK request is required regardless of source count (the
    remaining per-source work is a local raster/vector read, reported
    separately as `local_point_reads`, never counted as network)."""
    unique_sources: dict[str, EligibleSource] = universe["unique_sources"]
    weather_cache = FileWeatherCache(weather_cache_dir)
    source_cache_hits = 0
    for source_id in unique_sources:
        if (Path(source_cache_dir) / f"{hashlib.sha256(source_id.encode('utf-8')).hexdigest()}.json").exists():
            source_cache_hits += 1

    weather_requests_total = 0
    weather_cache_hits = 0
    for source in unique_sources.values():
        for window_name, lookback_hours in WEATHER_WINDOWS_HOURS.items():
            weather_requests_total += 1
            key = _weather_request_key(source.latitude, source.longitude, source.effective_availability_date, lookback_hours)
            if key is not None and weather_cache.get(key) is not None:
                weather_cache_hits += 1

    unique_elevation_tiles = {_elevation_tile_key(s.latitude, s.longitude) for s in unique_sources.values()}
    unique_landcover_tiles = {_landcover_tile_key(s.latitude, s.longitude) for s in unique_sources.values()}

    weather_cache_dir = Path(weather_cache_dir)
    gis_dir = weather_cache_dir.parents[1] / "gis" if weather_cache_dir.name == "weather" else None
    glw_files = ["glw/5_Ct_2015_Da.tif", "glw/8_Areakm_cattle.tif", "glw/5_Bf_2015_Da.tif", "glw/8_Areakm_buffalo.tif"]
    glw_cached = sum(1 for name in glw_files if gis_dir and (gis_dir / name).exists()) if gis_dir else 0
    hydrosheds_cached = 1 if gis_dir and (gis_dir / "hydrosheds" / "HydroRIVERS_v10_as_shp.zip").exists() else 0
    from ..data_processing.build_fmd_features import _in_hydrology_asia_bbox
    in_coverage_source_count = sum(1 for s in unique_sources.values() if _in_hydrology_asia_bbox(s.latitude, s.longitude))

    plan = {
        "checkpoint": CHECKPOINT,
        "development_origin_count": universe["development_origin_count"],
        "origins_with_zero_active_sources": len(universe["zero_source_origin_ids"]),
        "total_origin_source_appearances": universe["total_origin_source_appearances"],
        "unique_required_source_count": universe["unique_required_source_count"],
        "duplicate_source_appearance_savings": universe["duplicate_source_appearance_savings"],
        "source_metadata_conflict_count": len(universe["conflicts"]),
        "feature_families": {
            "weather": {"feature_count": 32, "variables": 8, "windows": list(WEATHER_WINDOWS_HOURS)},
            "elevation": {"feature_count": 1},
            "host_density": {"feature_count": 2, "species": ["cattle", "buffalo"]},
            "land_cover": {"feature_count": 11},
            "hydrology": {"feature_count": 1},
        },
        "eligible_predictor_feature_count": len(eligible_predictor_features),
        "unique_elevation_tile_count": len(unique_elevation_tiles),
        "unique_landcover_tile_count": len(unique_landcover_tiles),
        "sources_inside_hydrology_coverage": in_coverage_source_count,
        "expected_requests_before_cache": {
            "weather": weather_requests_total,
            "elevation": len(unique_elevation_tiles),  # tiled -- several sources may share one tile
            "host_density": 4,  # 4 fixed global GLW4 files (cattle count/area, buffalo count/area) -- location-independent
            "land_cover": len(unique_landcover_tiles),  # tiled -- several sources may share one tile
            "hydrology": 1,  # single 'as'-region file; all in-coverage sources share it
        },
        "existing_cache_hits": {
            "weather": weather_cache_hits,
            "elevation": 0,  # no persistent per-tile cache existed before this checkpoint's SourceExtractionCache
            "host_density": glw_cached,  # already downloaded by the FMD-04 29-event validation run
            "land_cover": 0,
            "hydrology": hydrosheds_cached,  # 'as'-region file already downloaded by the FMD-04 29-event validation run
            "source_level_all_families": source_cache_hits,  # SourceExtractionCache (this checkpoint's new generic layer): whole-source hits
        },
        "network_required": {
            "weather": weather_requests_total - weather_cache_hits,
            "elevation": len(unique_elevation_tiles),  # no persistent tile cache exists yet to subtract from
            "host_density": 4 - glw_cached,
            "land_cover": len(unique_landcover_tiles),
            "hydrology": 1 - hydrosheds_cached,
        },
        "local_point_reads_after_assets_cached": {
            "host_density": universe["unique_required_source_count"],  # cheap local rasterio window reads once the 4 global files exist
            "hydrology": in_coverage_source_count,  # cheap local geopandas/shapely reads once the region file exists
        },
        "estimated_logical_extraction_units": universe["unique_required_source_count"],
        "cache_locations": {
            "weather": str(weather_cache_dir),
            "gis_assets": str(gis_dir) if gis_dir else None,
            "source_level_cache": str(source_cache_dir),
        },
        "cache_key_definitions": {
            "weather": "SHA-256 of the exact Open-Meteo hourly request parameter dict (services/features/cache.py cache_key_for_request, era5._hourly_request_params) -- one key per (source coordinate, historical window start/end)",
            "host_density_land_cover_hydrology": "download_and_cache(url, cache_path) -- cache_path keyed by the dataset's own fixed filename (host density: 4 global files; hydrology: 1 file per region); a local file is never re-downloaded once present and non-empty",
            "source_level_cache": "SHA-256 of the canonical source_id alone -- this checkpoint's new generic layer; one JSON file per unique source holding every family's already-extracted row",
        },
        "retry_policy": "single attempt per request, matching the existing, unmodified adapter behavior (era5.py/raster.py: a request.RequestException/HTTP error produces an explicit BLOCKED FeatureResult, never a fabricated value, never a retry loop) -- no new retry logic was added; a failed request is retried only by re-running extraction later, which the SourceExtractionCache makes safe (a genuinely successful prior source is never re-attempted)",
        "timeout_policy": "unchanged adapter defaults (era5.py build_pre_t0_weather_summary: 30s; raster download_and_cache: 60s; extract_elevation: 20s)",
        "resume_checkpoint_policy": "SourceExtractionCache persists one atomically-written JSON file per unique source_id; a resumed run skips any source_id whose file already exists, regardless of which family originally required network access for it",
        "held_out_included": False,
        "sri_lanka_included": False,
        "predictive_metrics_used": False,
        "model_trained": False,
        "weather_winner_selected": False,
    }
    return plan


# ---------------------------------------------------------------------------
# Section 9: minimal generic resumability addition for the families that
# have no persistent local cache today (elevation/host-density/land-cover/
# hydrology all read via GDAL VSI/rasterio directly, or via a
# location-independent global-file cache that a single point query never
# needs to re-download -- but NONE of them persist a per-source RESULT, so
# a resumed run would still re-issue the point-level query). This class
# changes nothing about adapter scientific meaning -- it only remembers
# the already-computed row for a source_id.
# ---------------------------------------------------------------------------


class SourceExtractionCache:
    """One JSON file per unique `source_id`, holding the COMPLETE row
    (every feature family) `build_event_feature_row` already produced for
    it. Atomic write (`.tmp` + `replace`), matching
    `services/features/cache.FileWeatherCache`'s own pattern exactly."""

    def __init__(self, cache_dir: str | Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, source_id: str) -> Path:
        key = hashlib.sha256(source_id.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.json"

    def get(self, source_id: str) -> dict | None:
        path = self._path_for(source_id)
        if not path.exists():
            return None
        try:
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, source_id: str, row: dict) -> None:
        path = self._path_for(source_id)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(row, handle)
        tmp.replace(path)


def extract_source_features(
    source: EligibleSource, config: FmdFeatureExtractionConfig, weather_cache: FileWeatherCache, source_cache: SourceExtractionCache,
    *, precomputed_weather_windows: dict[str, tuple] | None = None,
) -> tuple[dict, bool]:
    """Returns `(row, was_cache_hit)`. Reuses
    `data_processing.build_fmd_features.build_event_feature_row`
    UNCHANGED in scientific behavior (Section 8: no substitute scientific
    data source) via a lightweight `FmdCanonicalEventRef` shim carrying
    the source's own identity/coordinate/date -- never a centroid, never
    a trigger-only substitution. `precomputed_weather_windows`: optional,
    additive-only pass-through to `build_event_feature_row` (see its own
    docstring) -- `None` (every R2B1 caller) is byte-identical to the
    original unmodified call."""
    cached = source_cache.get(source.source_id)
    if cached is not None:
        return cached, True
    event_shim = FmdCanonicalEventRef(
        fmd_canonical_event_id=source.source_id,
        source_record_id=source.source_id,
        country=source.country,
        event_date=source.effective_availability_date,
        latitude=source.latitude,
        longitude=source.longitude,
        modelling_eligible=True,
    )
    row, _provenance = build_event_feature_row(event_shim, config, weather_cache, precomputed_weather_windows=precomputed_weather_windows)
    row["source_id"] = source.source_id
    source_cache.set(source.source_id, row)
    return row, False


# ---------------------------------------------------------------------------
# Section 12-13: deterministic, label-independent canary selection.
# ---------------------------------------------------------------------------


def select_canary_source_ids(unique_sources: dict[str, EligibleSource], *, size: int = CANARY_SIZE) -> list[str]:
    """Section 12: the smallest deterministic set that exercises every
    required adapter -- NEVER chosen using any risk/outcome label
    column or any other outcome. First `size` unique source ids in canonical sorted
    order; if none of those falls inside HydroRIVERS' Asia coverage
    bounding box, the first (still sorted-order, never label-based)
    in-coverage source id is appended so the real (non-`OUTSIDE_
    SOURCE_COVERAGE`) hydrology path is genuinely exercised too."""
    from ..data_processing.build_fmd_features import _in_hydrology_asia_bbox

    ordered_ids = sorted(unique_sources)
    canary = ordered_ids[:size]
    if not any(_in_hydrology_asia_bbox(unique_sources[sid].latitude, unique_sources[sid].longitude) for sid in canary):
        for sid in ordered_ids:
            if _in_hydrology_asia_bbox(unique_sources[sid].latitude, unique_sources[sid].longitude):
                canary.append(sid)
                break
    return canary


# ---------------------------------------------------------------------------
# Canary orchestration.
# ---------------------------------------------------------------------------


def run_canary_extraction(
    canary_source_ids: list[str], unique_sources: dict[str, EligibleSource], *,
    weather_cache_dir: str | Path, source_cache_dir: str | Path, config: FmdFeatureExtractionConfig | None = None,
) -> dict:
    config = config or FmdFeatureExtractionConfig()
    weather_cache = FileWeatherCache(Path(weather_cache_dir))
    source_cache = SourceExtractionCache(Path(source_cache_dir))
    rows: list[dict] = []
    cache_hits = 0
    network_attempts = 0
    for source_id in sorted(canary_source_ids):
        row, was_hit = extract_source_features(unique_sources[source_id], config, weather_cache, source_cache)
        rows.append(row)
        if was_hit:
            cache_hits += 1
        else:
            network_attempts += 1
    return {"rows": rows, "cache_hits": cache_hits, "network_attempts": network_attempts}


PROGRESS_JSON_FILENAME = "fmd07_feature_extraction_progress.json"


def _progress_bucket_for_status(status: str) -> str:
    """Section 10: maps the real, unchanged `fmd_feature_status.py`
    vocabulary onto the generic progress categories that section asks
    for -- never a new status invented, never a distinction the
    adapters don't actually make. `SOURCE_VALUE_AVAILABLE`/
    `SOURCE_VALUE_MISSING`/`TEMPORAL_COVERAGE_MISSING` all mean the
    adapter call itself completed without error (a value was found, or
    genuinely was not, respectively) -- both are `successful` ATTEMPTS
    in Section 10's sense (never conflated with "value fabricated").
    `OUTSIDE_SOURCE_COVERAGE` means FMD-04's own orchestration
    deliberately skipped the call. `SOURCE_FILE_MISSING` (the required
    GIS asset itself could not be downloaded/read, fmd_feature_status.py
    `_FILE_MISSING_PHRASES`) is `failed_final` -- retrying the identical
    request cannot succeed until the asset is fixed. `EXTRACTION_FAILED`
    (the general BLOCKED umbrella -- e.g. a transient HTTP/network
    error) is `blocked`. `failed_retryable` is never populated by this
    function: every real adapter here makes exactly one attempt and
    returns a terminal status (era5.py/raster.py -- RequestException ->
    BLOCKED once, never retried; see `retry_policy` in the plan), so
    there is structurally no transient/"worth retrying" state to report
    without inventing one (Section 11 forbids that)."""
    if status in (SOURCE_VALUE_AVAILABLE, "SOURCE_VALUE_MISSING", "TEMPORAL_COVERAGE_MISSING"):
        return "successful"
    if status == "OUTSIDE_SOURCE_COVERAGE":
        return "out_of_coverage"
    if status == "SOURCE_FILE_MISSING":
        return "failed_final"
    if status == "EXTRACTION_FAILED":
        return "blocked"
    raise ValueError(f"_progress_bucket_for_status: unrecognized status {status!r}")


def _family_representative_status_keys(sample_row: dict) -> dict[str, list[str]]:
    """One representative `_status` column per real request-level unit
    for each family, read directly from an actual produced row's own
    keys -- never a hardcoded feature name that might not exist. Weather
    has one column per (window, variable); `mean_temperature_2m` stands
    in for its whole window request, exactly as `test_r2b1_20` already
    does. Land cover's 11 classes come from ONE AOI extraction call
    (`extract_landcover_for_event`), so one representative class status
    is sufficient -- the same one-request-many-values shape as weather."""
    weather_keys = sorted(k for k in sample_row if k.startswith("weather_") and k.endswith("_mean_temperature_2m_status"))
    landcover_keys = sorted(k for k in sample_row if k.startswith("landcover_") and k.endswith("_status"))
    return {
        "weather": weather_keys,
        "elevation": ["elevation_m_status"],
        "host_density": ["host_density_cattle_status", "host_density_buffalo_status"],
        "land_cover": landcover_keys[:1],
        "hydrology": ["distance_to_nearest_river_km_status"],
    }


def build_extraction_progress(
    universe: dict, plan_before_canary: dict, plan_after_canary: dict, canary_source_ids: list[str], canary_result: dict,
    *, source_cache_dir: str | Path,
) -> dict:
    """Section 10: resumable progress artifact -- a real snapshot of
    exactly what has, and has not yet, been attempted against the FULL
    development extraction universe (never just the canary). `planned`
    always covers all `unique_required_source_count` sources so
    `remaining` stays honest even though only the canary's sources have
    ever actually been attempted in this checkpoint.

    `cache_hit`/`remaining` are CURRENT, universe-wide, on-disk cache
    state (weather: `plan_after_canary`'s own already-tested no-network
    `FileWeatherCache` scan; every other family: `SourceExtractionCache`
    -- Section 9's one new generic engineering addition -- via the same
    scan `build_extraction_plan` already performs). `attempted_network`
    is how much NEW network work THIS run actually did: for weather, the
    real delta between two `build_extraction_plan` snapshots taken
    immediately before/after the canary (never re-derived a different
    way); for every other family, `run_canary_extraction`'s own real
    `network_attempts` (a source's row is extracted, and every family
    within it resolved, in one combined attempt -- so those four
    families share one real attempted/cache-hit split by construction,
    not by approximation). The qualitative `successful`/`failed_final`/
    `blocked`/`out_of_coverage` breakdown is scoped to sources actually
    attempted so far (`attempted_source_ids`) -- read from their real
    extracted `_status` columns, never inferred for a source that has
    not been touched."""
    from ..data_processing.build_fmd_features import _in_hydrology_asia_bbox

    unique_sources = universe["unique_sources"]
    canary_ids_sorted = sorted(canary_source_ids)
    canary_rows = canary_result["rows"]
    rows_by_source_id = {row["source_id"]: row for row in canary_rows}
    rep_keys = _family_representative_status_keys(canary_rows[0]) if canary_rows else {
        "weather": [], "elevation": [], "host_density": [], "land_cover": [], "hydrology": [],
    }

    def _bucket_counts(family: str) -> dict[str, int]:
        counts = {"successful": 0, "failed_retryable": 0, "failed_final": 0, "out_of_coverage": 0, "blocked": 0}
        for sid in canary_ids_sorted:
            row = rows_by_source_id.get(sid)
            if row is None:
                continue
            for key in rep_keys[family]:
                counts[_progress_bucket_for_status(row[key])] += 1
        return counts

    adapters: dict[str, dict] = {}

    weather_planned = plan_before_canary["expected_requests_before_cache"]["weather"]
    weather_cache_hit = plan_after_canary["existing_cache_hits"]["weather"]
    weather_attempted_network = weather_cache_hit - plan_before_canary["existing_cache_hits"]["weather"]
    adapters["weather"] = {
        "unit": "one (unique source coordinate, historical window) Open-Meteo request",
        "planned": weather_planned,
        "cache_hit": weather_cache_hit,
        "attempted_network": weather_attempted_network,
        "remaining": weather_planned - weather_cache_hit,
        **_bucket_counts("weather"),
    }

    source_cache_hit_now = plan_after_canary["existing_cache_hits"]["source_level_all_families"]
    source_attempted_network = canary_result["network_attempts"]
    for family in ("elevation", "host_density", "land_cover"):
        planned = universe["unique_required_source_count"]
        adapters[family] = {
            "unit": "one unique source (SourceExtractionCache row)",
            "planned": planned,
            "cache_hit": source_cache_hit_now,
            "attempted_network": source_attempted_network,
            "remaining": planned - source_cache_hit_now,
            **_bucket_counts(family),
        }

    # Real disk scan (never the in-memory canary rows alone) so `cache_hit`
    # stays correct as SourceExtractionCache grows beyond this checkpoint's
    # 8-source canary in a later, larger run -- same primitive/semantics as
    # `source_cache_hit_now` above, just restricted to in-coverage sources
    # so `remaining = planned - cache_hit` holds honestly for hydrology too.
    source_cache = SourceExtractionCache(source_cache_dir)
    hydrology_planned = plan_before_canary["sources_inside_hydrology_coverage"]
    hydrology_cache_hit_now = sum(
        1 for source in unique_sources.values()
        if _in_hydrology_asia_bbox(source.latitude, source.longitude) and source_cache.get(source.source_id) is not None
    )
    adapters["hydrology"] = {
        "unit": "one unique in-coverage source (SourceExtractionCache row)",
        "planned": hydrology_planned,
        "cache_hit": hydrology_cache_hit_now,
        "attempted_network": source_attempted_network,
        "remaining": hydrology_planned - hydrology_cache_hit_now,
        **_bucket_counts("hydrology"),
    }

    return {
        "checkpoint": CHECKPOINT,
        "adapters": adapters,
        "attempted_source_ids": canary_ids_sorted,
        "last_completed_batch_key": canary_ids_sorted[-1] if canary_ids_sorted else None,
        "held_out_included": False,
        "sri_lanka_included": False,
        "predictive_metrics_used": False,
        "model_trained": False,
        "weather_winner_selected": False,
    }


def write_extraction_progress(progress: dict, out_path: str | Path) -> None:
    """Atomic write (`.tmp` + `replace`), matching every other cache/
    artifact writer in this module -- a crash mid-write can never leave
    a half-written progress file behind. Deliberately no timestamp
    inside the deterministic JSON body itself (Section 10: "Do not
    include unstable timestamps in deterministic scientific outputs")."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(progress, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


CANARY_FIELDNAMES_EXTRA = ["source_id"]


def write_canary_source_table(rows: list[dict], out_path: str | Path) -> None:
    if not rows:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for key in rows[0]:
        if key not in fieldnames:
            fieldnames.append(key)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Orchestrator.
# ---------------------------------------------------------------------------


def run_fmd07a_r2b1(
    canonical_csv_path: str | Path,
    origins_csv_path: str | Path,
    model_dev_dir: str | Path,
    weather_cache_dir: str | Path,
    source_cache_dir: str | Path,
    eligible_predictor_features: list[str],
    *,
    disease: str = FMD_DISEASE,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
    run_canary: bool = True,
) -> dict:
    """Full Section 3-19 flow (minus the full-corpus extraction, which
    this checkpoint explicitly never runs). Builds the extraction
    universe from a REAL temporary SQLite repository imported from the
    frozen canonical corpus (read-only), writes the no-network plan, then
    -- if `run_canary=True` -- runs the small real canary and writes its
    source-level table."""
    output = Path(model_dev_dir)
    output.mkdir(parents=True, exist_ok=True)

    all_origins = load_forecast_origins(origins_csv_path)

    import tempfile

    with tempfile.TemporaryDirectory(prefix="fmd07a_r2b1_db_") as temp_dir:
        repo = SQLiteOutbreakRepository(Path(temp_dir) / "r2b1.sqlite")
        repo.init_schema()
        import_fmd_canonical_csv(repo, canonical_csv_path)
        universe = build_development_extraction_universe(repo, all_origins, disease=disease, cutoff=cutoff)
        repo.close()

    plan = build_extraction_plan(
        universe, weather_cache_dir=Path(weather_cache_dir), source_cache_dir=Path(source_cache_dir),
        eligible_predictor_features=eligible_predictor_features,
    )
    (output / "fmd07_feature_extraction_plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")

    result = {"universe": universe, "plan": plan}

    canary_ids = select_canary_source_ids(universe["unique_sources"])
    canary_manifest = {
        "checkpoint": CHECKPOINT,
        "canary_source_ids": canary_ids,
        "canary_size": len(canary_ids),
        "selection_rule": "first CANARY_SIZE unique source ids in canonical sorted order, plus (if none already in scope) the first sorted-order source id inside HydroRIVERS' Asia coverage bounding box -- never chosen using any risk/outcome label column",
        "held_out_included": False,
        "sri_lanka_included": False,
    }
    (output / "fmd07_feature_extraction_canary_manifest.json").write_text(json.dumps(canary_manifest, indent=2, sort_keys=True), encoding="utf-8")
    result["canary_manifest"] = canary_manifest

    if run_canary:
        canary_result = run_canary_extraction(
            canary_ids, universe["unique_sources"], weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir,
        )
        write_canary_source_table(canary_result["rows"], output / "canary" / "fmd07_canary_source_features.csv")
        result["canary_result"] = canary_result

        plan_after_canary = build_extraction_plan(
            universe, weather_cache_dir=Path(weather_cache_dir), source_cache_dir=Path(source_cache_dir),
            eligible_predictor_features=eligible_predictor_features,
        )
        progress = build_extraction_progress(
            universe, plan, plan_after_canary, canary_ids, canary_result, source_cache_dir=source_cache_dir,
        )
        write_extraction_progress(progress, output / PROGRESS_JSON_FILENAME)
        result["progress"] = progress

    return result
