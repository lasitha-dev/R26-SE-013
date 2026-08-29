"""Checkpoint 6A Part 22: real-data feature-assembly smoke — two real
snapshots only (Sri Lanka Event_3473 case-study origin, one Thailand
development origin), never the full 813-origin corpus.

Not a pytest suite (real network calls). Run directly:

    python -m components.geospatial_tracking.smoke_tests.run_feature_assembly_smoke

Uses the real historical source selector (HISTORICAL_ONLY,
RETROSPECTIVE_PROXY), the real grid/geometry/environmental adapters, and
the `weather_lookback_hours=24` DEVELOPMENT_FIXTURE (Part 9 — never
claimed epidemiologically optimal). No risk prediction of any kind.

Sri Lanka remains a GEOGRAPHIC_TRANSFER_CASE_STUDY (Part 23) — this
script does not read, use, or reference any outcome/validation data to
select the policy below; the identical `FeaturePolicy` (same land-cover
mode resolution rule, same species list, same lookback, same grid
resolution) is applied to both countries.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT, DEFAULT_SQLITE_DB_PATH, WEATHER_LOOKBACK_HOURS_DEV_DEFAULT
from ..repositories.sqlite_repository import SQLiteOutbreakRepository
from ..services.forecast_origin import ForecastOrigin
from ..services.features.assembler import assemble_feature_snapshot
from ..services.features.cache import FileWeatherCache
from ..services.features.feature_policy import DEFAULT_HYDRORIVERS_SEARCH_RADIUS_KM, LandCoverFeaturePolicy, FeaturePolicy
from ..services.features.resolved_data_signature import compare_feature_compatibility
from ..services.geospatial.raster import LOCAL_GIS_CACHE_DIR

REPORT_DIR = LOCAL_GIS_CACHE_DIR.parent / "feature_snapshots"
WEATHER_CACHE_DIR = LOCAL_GIS_CACHE_DIR.parent / "cache" / "weather"

# Identical policy shape for both countries -- Sri Lanka's case-study
# status (Part 23) plays no role in choosing this configuration; it is
# the same DEVELOPMENT_FIXTURE grid/lookback used throughout Checkpoint
# 5.x's real smoke tests.
_GRID_HALF_EXTENT_KM = 5.0
_GRID_CELL_SIZE_KM = 2.5


def _build_policy(*, landcover_mode: str) -> FeaturePolicy:
    return FeaturePolicy(
        disease="Lumpy skin disease",
        active_window_days=ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT,
        grid_half_extent_km=_GRID_HALF_EXTENT_KM,
        grid_cell_size_km=_GRID_CELL_SIZE_KM,
        weather_model="era5",
        weather_lookback_hours=WEATHER_LOOKBACK_HOURS_DEV_DEFAULT,
        landcover_policy=LandCoverFeaturePolicy(mode=landcover_mode),
        host_density_species=("cattle", "buffalo"),
        hydrology_include=True,
        hydrorivers_search_radius_km=DEFAULT_HYDRORIVERS_SEARCH_RADIUS_KM,  # GEOSPATIAL_QUERY_LIMIT, not a biological claim
        elevation_include=False,  # Part 14: never auto-included just because an adapter exists
    )


def _summarize(snapshot) -> dict:
    return {
        "snapshot_id": snapshot.snapshot_id,
        "forecast_origin_id": snapshot.forecast_origin_id,
        "t0": snapshot.t0,
        "t0_precision": snapshot.t0_precision,
        "temporal_mode": snapshot.temporal_mode,
        "country_scope": snapshot.country_scope,
        "disease": snapshot.disease,
        "active_source_count": snapshot.active_source_count,
        "active_source_ids": snapshot.active_source_ids,
        "grid_cell_count": snapshot.grid_meta.get("n_cells"),
        "geometry_count": sum(len(c.geometry_by_source) for c in snapshot.grid_cells),
        "feature_status_summary": snapshot.feature_status_summary,
        "source_dataset_versions": snapshot.source_dataset_versions,
        "landcover_comparability_group": snapshot.landcover_comparability_group,
        "source_timezone": snapshot.source_timezone,
        "t0_timezone_quality": snapshot.t0_timezone_quality,
        "resolved_t0_cutoff_utc": snapshot.resolved_t0_cutoff_utc,
        "feature_policy_hash": snapshot.feature_policy_hash,
        "resolved_data_signature_hash": snapshot.resolved_data_signature_hash,
        "readiness": snapshot.readiness,
        "readiness_notes": snapshot.readiness_notes,
        "weather_window": snapshot.weather["window"],
    }


def _save(snapshot, filename: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot.as_dict(), f, indent=2, ensure_ascii=False, default=str)
    return path


def run_sri_lanka_case_study(repo, weather_cache) -> dict:
    # Real forecast origin from local_data/manifests/historical_forecast_origins.csv
    # (ORIGIN:Sri Lanka:2020-09-09) -- Chavakachcheri's real trigger date
    # within Event_3473, GEOGRAPHIC_TRANSFER_CASE_STUDY (Part 23): its
    # outcome data plays no role in this checkpoint's feature-assembly
    # decisions (land-cover mode, lookback, grid resolution are all fixed
    # identically for both countries below).
    origin = ForecastOrigin(
        forecast_origin_id="ORIGIN:Sri Lanka:2020-09-09",
        country="Sri Lanka",
        t0="2020-09-09",
        temporal_mode="RETROSPECTIVE_PROXY",
        trigger_source_ids_at_t0=["WAHIS_PDF:Event_3473.pdf:002408"],
        trigger_source_count=1,
    )
    policy = _build_policy(landcover_mode="YEAR_MATCHED_REFERENCE")  # 2020 event -> WorldCover 2020 v100
    snapshot = assemble_feature_snapshot(repo, forecast_origin=origin, policy=policy, weather_cache=weather_cache)
    path = _save(snapshot, "sri_lanka_event_3473_snapshot.json")
    print(f"Sri Lanka Event_3473 (case study) snapshot -> {path}")
    return snapshot


def run_thailand_development_origin(repo, weather_cache) -> dict:
    # Real forecast origin (ORIGIN:Thailand:2021-03-10) -- Muang Suang's
    # real trigger date within Event_3644.
    origin = ForecastOrigin(
        forecast_origin_id="ORIGIN:Thailand:2021-03-10",
        country="Thailand",
        t0="2021-03-10",
        temporal_mode="RETROSPECTIVE_PROXY",
        trigger_source_ids_at_t0=["WAHIS_PDF:Event_3644.pdf:002414"],
        trigger_source_count=1,
    )
    policy = _build_policy(landcover_mode="YEAR_MATCHED_REFERENCE")  # 2021 event -> WorldCover 2021 v200
    snapshot = assemble_feature_snapshot(repo, forecast_origin=origin, policy=policy, weather_cache=weather_cache)
    path = _save(snapshot, "thailand_development_origin_snapshot.json")
    print(f"Thailand development-origin snapshot -> {path}")
    return snapshot


if __name__ == "__main__":
    db_path = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
    repo = SQLiteOutbreakRepository(db_path)
    weather_cache = FileWeatherCache(WEATHER_CACHE_DIR)
    try:
        sl_snapshot = run_sri_lanka_case_study(repo, weather_cache)
        print(json.dumps(_summarize(sl_snapshot), indent=2, default=str))
        print()
        th_snapshot = run_thailand_development_origin(repo, weather_cache)
        print(json.dumps(_summarize(th_snapshot), indent=2, default=str))
        print()
        print("=== compatibility comparison (Sri Lanka vs Thailand) ===")
        print(
            "same feature_policy_hash:",
            sl_snapshot.feature_policy_hash == th_snapshot.feature_policy_hash,
        )
        print(
            "same resolved_data_signature_hash:",
            sl_snapshot.resolved_data_signature_hash == th_snapshot.resolved_data_signature_hash,
        )
        print("mismatches:", compare_feature_compatibility(sl_snapshot, th_snapshot))
    finally:
        repo.close()
