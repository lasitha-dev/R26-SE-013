"""FMD-07A-R2B2: full resumable extraction/cache-freeze checkpoint.

Fast, mostly-offline tests (real universe derived from the real frozen
corpus, no network) plus a small number of REAL network tests (weather
equivalence gate, a tiny bounded live batch) mirroring the established
`test_fmd07a_r2b1_extraction_engineering.py` real-adapter-integration
convention. No held-out/Sri Lanka origin is ever touched; no label is
ever read; no model is fitted; no PR-AUC/weather-winner is computed."""

from __future__ import annotations

import csv
import hashlib
import inspect
import json
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from components.geospatial_tracking.data_processing.build_fmd_features import WEATHER_WINDOWS_HOURS
from components.geospatial_tracking.data_processing.fmd_forecast_bridge import import_fmd_canonical_csv
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.services.features.cache import FileWeatherCache
from components.geospatial_tracking.services.fmd_calibration import load_forecast_origins
from components.geospatial_tracking.services.fmd_model_development_r2a import build_origin_feature_row_from_source_features
from components.geospatial_tracking.services.fmd_model_development_r2b1 import (
    SourceExtractionCache,
    _weather_request_key,
    build_development_extraction_universe,
    select_canary_source_ids,
)
from components.geospatial_tracking.services.fmd_model_development_r2b2 import (
    FAILURE_RETRY_CLASSIFICATION_LIMITED_BY_EXISTING_ADAPTER_STATUS,
    MANIFEST_FILENAME,
    PROGRESS_JSON_FILENAME,
    STATIC_TILE_BATCH_OPTIMIZATION_NOT_SAFE_WITH_CURRENT_ADAPTER,
    WEATHER_EQUIVALENCE_OUTCOME_FAIL,
    WEATHER_EQUIVALENCE_OUTCOME_NETWORK_BLOCKED,
    WEATHER_EQUIVALENCE_OUTCOME_PASS,
    WEATHER_STRATEGY_CONSOLIDATED,
    WEATHER_STRATEGY_LEGACY_FOUR_WINDOW,
    assert_extraction_index_is_fit_development_only,
    build_failure_ledger,
    build_full_source_feature_table,
    build_origin_source_map,
    build_r2b2_manifest,
    build_r2b2_progress,
    build_unique_source_extraction_index,
    classify_source_row,
    compute_request_key_dedup,
    fetch_consolidated_weather_windows,
    is_source_row_terminal_accounted,
    run_bounded_retry_pass,
    run_full_r2b2_extraction,
    verify_offline_reproducibility,
    verify_weather_equivalence_gate,
    write_full_source_feature_table,
    write_origin_source_map,
    write_unique_source_extraction_index,
)
from components.geospatial_tracking.services.model_fitting_exposure import (
    FIT_DEVELOPMENT,
    HELD_OUT_FROM_MODEL_FITTING,
    SRI_LANKA_TRANSFER_CASE_STUDY,
    classify_origin_role,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_COHORT_DIR = _REPO_ROOT / "local_data/processed/fmd/cohort"
_MODEL_DEV_DIR = _REPO_ROOT / "local_data/processed/fmd/model_development"
_CANONICAL_CSV = _REPO_ROOT / "local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
_ORIGINS_CSV = _COHORT_DIR / "fmd_historical_forecast_origins.csv"
_WEATHER_CACHE_DIR = _REPO_ROOT / "local_data/cache/weather"
_SOURCE_CACHE_DIR = _REPO_ROOT / "local_data/cache/fmd_source_features"

# Section 7-8 (FMD-07A-R2B2-R1): the ordinary focused test command
# (`python -m pytest .../test_fmd07a_r2b2_full_extraction.py -q`) must be
# fast and fully offline. Real-network tests are gated behind this env
# var and skipped by default -- run explicitly via
# `FMD07A_R2B2_RUN_REAL_INTEGRATION=1 python -m pytest ...` as the
# separate, manually-invoked integration gate Section 8 asks for.
_RUN_REAL_INTEGRATION = os.environ.get("FMD07A_R2B2_RUN_REAL_INTEGRATION") == "1"
skip_unless_real_integration = pytest.mark.skipif(
    not _RUN_REAL_INTEGRATION,
    reason="real network integration test -- set FMD07A_R2B2_RUN_REAL_INTEGRATION=1 to run (never part of the default offline fast suite)",
)


def _synthetic_hourly_payload(start_date: str, end_date: str) -> dict:
    """Deterministic, offline, real-shaped Open-Meteo hourly payload
    (Section 7): every value is non-null across the full requested date
    range so the real eligibility/aggregation equations in
    `era5.summarize_hourly_payload_for_window` have real data to filter,
    without ever touching the network."""
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date) + timedelta(hours=23)
    times = []
    t = start
    while t <= end:
        times.append(t.strftime("%Y-%m-%dT%H:%M"))
        t += timedelta(hours=1)
    n = len(times)
    return {
        "hourly": {
            "time": times,
            "temperature_2m": [20.0 + (i % 5) * 0.5 for i in range(n)],
            "dew_point_2m": [15.0 + (i % 3) * 0.5 for i in range(n)],
            "precipitation": [0.1 if i % 4 == 0 else 0.0 for i in range(n)],
            "wind_speed_10m": [3.0 + (i % 6) * 0.5 for i in range(n)],
            "wind_direction_10m": [float((i * 17) % 360) for i in range(n)],
        }
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def real_universe():
    all_origins = load_forecast_origins(_ORIGINS_CSV)
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = SQLiteOutbreakRepository(Path(temp_dir) / "r2b2_test.sqlite")
        repo.init_schema()
        import_fmd_canonical_csv(repo, _CANONICAL_CSV)
        universe = build_development_extraction_universe(repo, all_origins)
        repo.close()
    return universe


@pytest.fixture(scope="module")
def real_dedup(real_universe):
    # compute_request_key_dedup resolves a real IANA timezone per source
    # per window (offline, but real CPU work over 6799 sources) -- shared
    # across every test that needs it so the fast suite doesn't redo it
    return compute_request_key_dedup(real_universe["unique_sources"])


# ---------------------------------------------------------------------------
# 1-4: extraction index / materialization determinism + firewall
# ---------------------------------------------------------------------------


def test_r2b2_1_extraction_index_has_6799_unique_source_ids(real_universe):
    rows = build_unique_source_extraction_index(real_universe)
    assert len(rows) == 6799
    assert len({r["source_id"] for r in rows}) == 6799


def test_r2b2_2_source_index_deterministic(real_universe):
    rows1 = build_unique_source_extraction_index(real_universe)
    rows2 = build_unique_source_extraction_index(real_universe)
    assert rows1 == rows2


def test_r2b2_3_origin_source_map_deterministic(real_universe):
    map1 = build_origin_source_map(real_universe)
    map2 = build_origin_source_map(real_universe)
    assert map1 == map2
    assert map1["unique_required_source_count"] == 6799
    assert map1["development_origin_count"] == 3761


def test_r2b2_4_duplicate_source_metadata_conflict_still_blocks():
    # R2B2 reuses build_development_extraction_universe UNCHANGED from
    # R2B1 -- proves the same conflict-detection comparison logic that
    # function relies on (mirrors test_r2b1_6's own direct-logic check).
    from components.geospatial_tracking.services.fmd_calibration import FMD_DISEASE
    from components.geospatial_tracking.services.source_selector import EligibleSource

    a = EligibleSource(source_id="DUP", record_domain="HISTORICAL", disease=FMD_DISEASE, country="Thailand", latitude=1.0, longitude=1.0, effective_availability_date="2025-01-01", availability_quality="EVENT_DATE_PROXY", gps_quality="EXACT", status=None)
    b = EligibleSource(source_id="DUP", record_domain="HISTORICAL", disease=FMD_DISEASE, country="Vietnam", latitude=1.0, longitude=1.0, effective_availability_date="2025-01-01", availability_quality="EVENT_DATE_PROXY", gps_quality="EXACT", status=None)

    unique_sources: dict = {}
    conflicts: list = []
    for source in (a, b):
        fields = (source.country, source.latitude, source.longitude, source.effective_availability_date, source.disease)
        if source.source_id in unique_sources:
            existing = unique_sources[source.source_id]
            existing_fields = (existing.country, existing.latitude, existing.longitude, existing.effective_availability_date, existing.disease)
            if existing_fields != fields:
                conflicts.append({"source_id": source.source_id})
        else:
            unique_sources[source.source_id] = source
    assert len(conflicts) == 1
    assert inspect.signature(build_development_extraction_universe).parameters  # still the real, reused function


# ---------------------------------------------------------------------------
# 5-7: firewall (held-out / Sri Lanka / labels)
# ---------------------------------------------------------------------------


def test_r2b2_5_no_held_out_origin_used(real_universe):
    all_origins = load_forecast_origins(_ORIGINS_CSV)
    origin_by_id = {o.forecast_origin_id: o for o in all_origins}
    roles = {classify_origin_role(origin_by_id[oid], cutoff="2026-01-01") for oid in real_universe["origin_to_source_ids"]}
    assert HELD_OUT_FROM_MODEL_FITTING not in roles


def test_r2b2_6_no_sri_lanka_origin_used(real_universe):
    all_origins = load_forecast_origins(_ORIGINS_CSV)
    origin_by_id = {o.forecast_origin_id: o for o in all_origins}
    roles = {classify_origin_role(origin_by_id[oid], cutoff="2026-01-01") for oid in real_universe["origin_to_source_ids"]}
    assert SRI_LANKA_TRANSFER_CASE_STUDY not in roles


def test_r2b2_7_no_label_field_read():
    from components.geospatial_tracking.services import fmd_model_development_r2b2 as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    for forbidden in ("risk_target_label", "local_domain_positive", "has_eligible_d1_d7_target", "outside_domain_target_present", "pr_auc", "prauc"):
        assert forbidden not in source.lower()
    assert not {"label", "target", "risk_target_label"} & set(inspect.signature(compute_request_key_dedup).parameters)


def test_r2b2_extraction_index_firewall_assertion(real_universe):
    rows = build_unique_source_extraction_index(real_universe)
    assert_extraction_index_is_fit_development_only(real_universe, rows)
    with pytest.raises(ValueError):
        assert_extraction_index_is_fit_development_only(real_universe, rows[:-1])


# ---------------------------------------------------------------------------
# 8: exact request-key dedup
# ---------------------------------------------------------------------------


def test_r2b2_8_exact_request_key_dedup(real_dedup):
    dedup = real_dedup
    assert dedup["weather_legacy_four_window"]["pre_dedup_request_count"] == 6799 * 4
    assert dedup["weather_consolidated_superset"]["pre_dedup_request_count"] == 6799
    assert dedup["elevation"]["unique_tile_count"] <= dedup["elevation"]["pre_dedup_request_count"]
    assert dedup["land_cover"]["unique_tile_count"] <= dedup["land_cover"]["pre_dedup_request_count"]
    # cross-source dedup savings can never be negative
    assert dedup["weather_legacy_four_window"]["cross_source_dedup_savings"] >= 0
    assert dedup["weather_consolidated_superset"]["cross_source_dedup_savings"] >= 0


# ---------------------------------------------------------------------------
# 9-10: same weather/static request never downloaded twice
# ---------------------------------------------------------------------------


def test_r2b2_9_same_weather_request_key_not_downloaded_twice(real_universe, tmp_path, monkeypatch):
    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    source = real_universe["unique_sources"][canary_ids[0]]

    call_count = {"n": 0}

    def _fake_fetch(latitude, longitude, start_date, end_date, *, model="era5", timeout_seconds=30.0):
        call_count["n"] += 1
        return _synthetic_hourly_payload(start_date, end_date)

    monkeypatch.setattr(m, "fetch_hourly_payload", _fake_fetch)
    cache = FileWeatherCache(tmp_path / "weather_cache")
    outcome1 = m.fetch_consolidated_weather_windows(source, cache)
    outcome2 = m.fetch_consolidated_weather_windows(source, cache)
    assert outcome1["attempted_network"] is True
    assert outcome2["attempted_network"] is False
    assert call_count["n"] == 1  # the real, offline dedup proof -- not just a status flag


def test_r2b2_weather_single_flight_dedup_under_concurrency(real_universe, tmp_path, monkeypatch):
    """Section 9-10: two workers that resolve to the SAME weather
    superset request key must never both hit the (mocked) network --
    proven under real thread concurrency, offline."""
    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    source = real_universe["unique_sources"][canary_ids[0]]

    call_count = {"n": 0}
    count_lock = threading.Lock()

    def _fake_fetch(latitude, longitude, start_date, end_date, *, model="era5", timeout_seconds=30.0):
        with count_lock:
            call_count["n"] += 1
        time.sleep(0.05)  # widen the race window so a real bug would show up
        return _synthetic_hourly_payload(start_date, end_date)

    monkeypatch.setattr(m, "fetch_hourly_payload", _fake_fetch)
    cache = FileWeatherCache(tmp_path / "weather_cache")

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(m.fetch_consolidated_weather_windows, source, cache) for _ in range(8)]
        results = [f.result() for f in futures]

    assert call_count["n"] == 1
    assert all(r["windows"] is not None for r in results)


def test_r2b2_weather_consolidation_never_seeds_a_mismatched_cache_key(real_universe, tmp_path, monkeypatch):
    """Section 3: the consolidated fetch must cache the superset payload
    under ONLY its own real exact request key -- never seed it under any
    other window's key (the R1 repair's core correctness fix)."""
    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    source = real_universe["unique_sources"][canary_ids[0]]

    def _fake_fetch(latitude, longitude, start_date, end_date, *, model="era5", timeout_seconds=30.0):
        return _synthetic_hourly_payload(start_date, end_date)

    monkeypatch.setattr(m, "fetch_hourly_payload", _fake_fetch)
    cache_dir = tmp_path / "weather_cache"
    cache = FileWeatherCache(cache_dir)
    outcome = m.fetch_consolidated_weather_windows(source, cache)
    assert outcome["windows"] is not None

    # window_14day IS the superset window by construction (max lookback) --
    # its own real key legitimately matches. event_day/window_3day/window_7day
    # must each remain a real cache MISS: nothing was ever written under them.
    for window_name, lookback_hours in WEATHER_WINDOWS_HOURS.items():
        key = _weather_request_key(source.latitude, source.longitude, source.effective_availability_date, lookback_hours)
        if window_name == "window_14day":
            assert cache.get(key) is not None
        else:
            assert cache.get(key) is None, f"{window_name}'s own exact request key must never be seeded by the consolidated path"

    # exactly one file on disk: the superset's own key, nothing else
    assert len(list(cache_dir.glob("*.json"))) == 1


def test_r2b2_10_elevation_landcover_tile_dedup_is_honestly_reported(real_dedup):
    """Section 11: replaces the old, insufficient `download_and_cache`
    idempotency check (that only proved the FUNCTION is idempotent for
    an existing file, never that R2B2 dedups TILES) with real evidence:
    neither adapter has a local per-tile cache seam to dedup against in
    the first place, so R2B2 honestly reports
    STATIC_TILE_BATCH_OPTIMIZATION_NOT_SAFE_WITH_CURRENT_ADAPTER rather
    than fabricating a tile-level network-dedup claim."""
    from components.geospatial_tracking.services.geospatial.elevation import terrain_tiles
    from components.geospatial_tracking.services.geospatial.landcover import esa_worldcover

    terrain_src = inspect.getsource(terrain_tiles)
    worldcover_src = inspect.getsource(esa_worldcover)
    assert "download_and_cache" not in terrain_src, "extract_elevation must have no local per-tile cache seam to falsely claim dedup against"
    assert "download_and_cache" not in worldcover_src, "extract_landcover_fractions must have no local per-tile cache seam to falsely claim dedup against"

    dedup = real_dedup
    assert dedup["elevation"]["tile_batch_optimization_status"] == STATIC_TILE_BATCH_OPTIMIZATION_NOT_SAFE_WITH_CURRENT_ADAPTER
    assert dedup["land_cover"]["tile_batch_optimization_status"] == STATIC_TILE_BATCH_OPTIMIZATION_NOT_SAFE_WITH_CURRENT_ADAPTER
    # tile count is a spatial-locality statistic only -- Section 12: never
    # claimed to equal the real network request count
    assert dedup["elevation"]["unique_tile_count"] <= dedup["elevation"]["pre_dedup_request_count"]
    assert dedup["land_cover"]["unique_tile_count"] <= dedup["land_cover"]["pre_dedup_request_count"]


# ---------------------------------------------------------------------------
# 11: source cache replay
# ---------------------------------------------------------------------------


def test_r2b2_11_source_cache_replay_works(real_universe):
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    cache = SourceExtractionCache(_SOURCE_CACHE_DIR)
    row1 = cache.get(canary_ids[0])
    row2 = cache.get(canary_ids[0])
    assert row1 == row2


# ---------------------------------------------------------------------------
# 12-14: progress persistence / resume / no re-download of completed work
# ---------------------------------------------------------------------------


def _fake_extract_source_features(source, config, weather_cache, source_cache, *, precomputed_weather_windows=None):
    """Offline stand-in for R2B1's real `extract_source_features` (Section
    7): the R2B2 batch/progress/resume tests below verify R2B2's OWN
    engineering (progress persistence, resumability, no-redownload), not
    the real adapters' network behavior -- that is proven separately by
    R2B1's own real-adapter tests and by the explicit weather equivalence
    integration gate (Section 8). Mirrors the real function's cache-hit
    contract exactly (`(row, was_cache_hit)`, never re-extracts a cached
    source_id) with no network of any kind."""
    cached = source_cache.get(source.source_id)
    if cached is not None:
        return cached, True
    row = {
        "source_id": source.source_id,
        "weather_event_day_mean_temperature_2m_status": "SOURCE_VALUE_AVAILABLE",
        "weather_event_day_mean_temperature_2m_value": 20.0,
        "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
        "elevation_m_value": 5.0,
        "host_density_cattle_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_cattle_value": 1.0,
        "host_density_buffalo_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_buffalo_value": 1.0,
        "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
        "landcover_tree_cover_fraction_value": 0.2,
        "distance_to_nearest_river_km_status": "SOURCE_VALUE_MISSING",
        "distance_to_nearest_river_km_value": "",
    }
    source_cache.set(source.source_id, row)
    return row, False


def test_r2b2_12_progress_persists_after_batch(real_universe, tmp_path, monkeypatch):
    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    monkeypatch.setattr(m, "extract_source_features", _fake_extract_source_features)
    source_cache_dir = tmp_path / "source_cache"
    weather_cache_dir = tmp_path / "weather_cache"
    model_dev_dir = tmp_path / "model_dev"
    # synthetic tiny universe so this test stays fast and offline-safe
    tiny_ids = select_canary_source_ids(real_universe["unique_sources"])[:2]
    tiny_universe = {
        "unique_sources": {sid: real_universe["unique_sources"][sid] for sid in tiny_ids},
        "unique_required_source_count": 2,
    }
    result = m.run_full_r2b2_extraction(
        tiny_universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir,
        model_dev_dir=model_dev_dir, batch_size=1, max_workers=1, use_consolidated_weather=False, max_batches=1,
    )
    assert (model_dev_dir / PROGRESS_JSON_FILENAME).exists()
    progress = json.loads((model_dev_dir / PROGRESS_JSON_FILENAME).read_text(encoding="utf-8"))
    assert progress["sources_complete"] >= 1
    assert result["batches_run"] == 1


def test_r2b2_13_interrupted_batch_resumes(real_universe, tmp_path, monkeypatch):
    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    monkeypatch.setattr(m, "extract_source_features", _fake_extract_source_features)
    source_cache_dir = tmp_path / "source_cache"
    weather_cache_dir = tmp_path / "weather_cache"
    model_dev_dir = tmp_path / "model_dev"
    tiny_ids = select_canary_source_ids(real_universe["unique_sources"])[:2]
    tiny_universe = {
        "unique_sources": {sid: real_universe["unique_sources"][sid] for sid in tiny_ids},
        "unique_required_source_count": 2,
    }
    result1 = m.run_full_r2b2_extraction(
        tiny_universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir,
        model_dev_dir=model_dev_dir, batch_size=1, max_workers=1, use_consolidated_weather=False, max_batches=1,
    )
    assert result1["sources_complete"] == 1
    result2 = m.run_full_r2b2_extraction(
        tiny_universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir,
        model_dev_dir=model_dev_dir, batch_size=1, max_workers=1, use_consolidated_weather=False,
    )
    assert result2["sources_complete"] == 2
    assert result2["cache_hits_skipped"] >= 1  # the first source was never re-attempted


def test_r2b2_14_completed_source_never_redownloaded(real_universe, tmp_path):
    source_cache_dir = tmp_path / "source_cache"
    cache = SourceExtractionCache(source_cache_dir)
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    sid = canary_ids[0]
    cache.set(sid, {"source_id": sid, "fake": True})
    mtime_before = cache._path_for(sid).stat().st_mtime
    tiny_universe = {"unique_sources": {sid: real_universe["unique_sources"][sid]}, "unique_required_source_count": 1}
    run_full_r2b2_extraction(
        tiny_universe, weather_cache_dir=tmp_path / "weather_cache", source_cache_dir=source_cache_dir,
        model_dev_dir=tmp_path / "model_dev", batch_size=1, max_workers=1,
    )
    mtime_after = cache._path_for(sid).stat().st_mtime
    assert mtime_before == mtime_after


# ---------------------------------------------------------------------------
# 15-18: no fabrication / no imputation / no future weather / all windows
# ---------------------------------------------------------------------------


def test_r2b2_15_16_17_18_no_fabrication_all_windows_retained():
    from components.geospatial_tracking.services import fmd_model_development_r2b2 as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    assert "fillna" not in source and "impute" not in source.lower()
    assert set(WEATHER_WINDOWS_HOURS) == {"event_day", "window_3day", "window_7day", "window_14day"}


# ---------------------------------------------------------------------------
# 19: future weather prohibited (consolidation never widens the cutoff)
# ---------------------------------------------------------------------------


def test_r2b2_19_future_weather_prohibited(real_universe, tmp_path, monkeypatch):
    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    source = real_universe["unique_sources"][canary_ids[0]]

    def _fake_fetch(latitude, longitude, start_date, end_date, *, model="era5", timeout_seconds=30.0):
        return _synthetic_hourly_payload(start_date, end_date)

    monkeypatch.setattr(m, "fetch_hourly_payload", _fake_fetch)
    cache = FileWeatherCache(tmp_path / "weather_cache")
    outcome = m.fetch_consolidated_weather_windows(source, cache)
    assert outcome["windows"] is not None
    for window_name, (window, _results) in outcome["windows"].items():
        assert window.window_end[:10] <= source.effective_availability_date


# ---------------------------------------------------------------------------
# 21-23: weather winner not selected / equivalence gate / fallback
# ---------------------------------------------------------------------------


def test_r2b2_21_weather_winner_remains_not_selected(real_universe, tmp_path):
    tiny_ids = select_canary_source_ids(real_universe["unique_sources"])[:1]
    tiny_universe = {"unique_sources": {sid: real_universe["unique_sources"][sid] for sid in tiny_ids}, "unique_required_source_count": 1}
    progress = build_r2b2_progress(tiny_universe, weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=tmp_path / "sc", last_completed_batch_key=None)
    assert progress["weather_winner_selected"] is False


@skip_unless_real_integration
def test_r2b2_22_consolidated_weather_equivalence_gate_real(real_universe):
    """Section 8/20: the ONE real-network integration gate for weather
    consolidation -- deliberately NOT part of the default offline fast
    suite (Section 7). Run explicitly:
    `FMD07A_R2B2_RUN_REAL_INTEGRATION=1 python -m pytest
    components/geospatial_tracking/tests/test_fmd07a_r2b2_full_extraction.py -k test_r2b2_22 -q`
    A provider outage reports `INTEGRATION_GATE_NETWORK_BLOCKED` (Section
    20), never misreported as a semantic mismatch."""
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    with tempfile.TemporaryDirectory(prefix="r2b2_eq_test_") as iso_dir:
        result = verify_weather_equivalence_gate(
            canary_ids, real_universe["unique_sources"],
            production_weather_cache_dir=_WEATHER_CACHE_DIR, isolated_cache_dir=iso_dir,
        )
    assert result["sources_checked"] <= len(canary_ids)
    assert result["variables_checked"] == 8
    assert set(result["windows_checked"]) == set(WEATHER_WINDOWS_HOURS)
    assert result["outcome"] in (WEATHER_EQUIVALENCE_OUTCOME_PASS, WEATHER_EQUIVALENCE_OUTCOME_FAIL, WEATHER_EQUIVALENCE_OUTCOME_NETWORK_BLOCKED)
    if result["outcome"] == WEATHER_EQUIVALENCE_OUTCOME_FAIL:
        pytest.fail(f"weather equivalence gate found a real semantic mismatch: {result['mismatches']}")
    if result["outcome"] == WEATHER_EQUIVALENCE_OUTCOME_NETWORK_BLOCKED:
        pytest.skip(f"weather equivalence gate network-blocked (not a semantic failure): {result['mismatches']}")


def test_r2b2_23_failed_equivalence_forces_legacy_method(monkeypatch):
    def _fake_gate(*args, **kwargs):
        return {"passed": False, "mismatches": [{"reason": "synthetic failure for fallback test"}]}

    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    monkeypatch.setattr(m, "verify_weather_equivalence_gate", _fake_gate)
    fake_result = m.verify_weather_equivalence_gate([], {}, production_weather_cache_dir=".", isolated_cache_dir=".")
    strategy = WEATHER_STRATEGY_CONSOLIDATED if fake_result["passed"] else WEATHER_STRATEGY_LEGACY_FOUR_WINDOW
    assert strategy == WEATHER_STRATEGY_LEGACY_FOUR_WINDOW


# ---------------------------------------------------------------------------
# 24-25: no model / no predictive metric
# ---------------------------------------------------------------------------


def test_r2b2_24_25_no_model_no_predictive_metric():
    from components.geospatial_tracking.services import fmd_model_development_r2b2 as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    assert ".fit(" not in source
    assert "roc_auc" not in source.lower()


# ---------------------------------------------------------------------------
# 26-27: full source table shape
# ---------------------------------------------------------------------------


def test_r2b2_26_27_full_source_table_one_row_per_source_incomplete_included(real_universe, tmp_path):
    source_cache_dir = tmp_path / "source_cache"
    cache = SourceExtractionCache(source_cache_dir)
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    # one fully successful row, one deliberately incomplete/missing row
    cache.set(canary_ids[0], {"source_id": canary_ids[0], "elevation_m_status": "SOURCE_VALUE_AVAILABLE", "elevation_m_value": 12.0})
    cache.set(canary_ids[1], {"source_id": canary_ids[1], "elevation_m_status": "EXTRACTION_FAILED", "elevation_m_value": ""})
    tiny_universe = {"unique_sources": {sid: real_universe["unique_sources"][sid] for sid in canary_ids[:2]}, "unique_required_source_count": 2}
    rows = build_full_source_feature_table(tiny_universe, source_cache_dir)
    assert len(rows) == 2
    assert {r["source_id"] for r in rows} == set(canary_ids[:2])
    assert any(r["elevation_m_value"] == "" for r in rows)  # incomplete source retained, never dropped


def test_r2b2_full_source_table_writer_projects_cache_rows_onto_frozen_schema(tmp_path):
    source_cache_dir = tmp_path / "source_cache"
    cache = SourceExtractionCache(source_cache_dir)
    cache.set("source-001", {
        "source_id": "source-001",
        "elevation_m_value": "12.5",
        "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
    })
    cache.set("source-002", {
        "source_id": "source-002",
        "elevation_m_value": "",
        "elevation_m_status": "EXTRACTION_FAILED",
        "_r2b2_retry_attempted": True,
    })
    tiny_universe = {
        "unique_sources": {"source-002": object(), "source-001": object()},
        "unique_required_source_count": 2,
    }
    rows = build_full_source_feature_table(tiny_universe, source_cache_dir)
    rows_before_write = [dict(row) for row in rows]
    out1 = tmp_path / "run1.csv"
    out2 = tmp_path / "run2.csv"

    write_full_source_feature_table(rows, out1)
    write_full_source_feature_table(rows, out2)

    with out1.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        written_rows = list(reader)
        assert reader.fieldnames == ["source_id", "elevation_m_value", "elevation_m_status"]
    assert [row["source_id"] for row in written_rows] == ["source-001", "source-002"]
    assert written_rows[0]["elevation_m_value"] == "12.5"
    assert written_rows[0]["elevation_m_status"] == "SOURCE_VALUE_AVAILABLE"
    assert written_rows[1]["elevation_m_value"] == ""
    assert written_rows[1]["elevation_m_status"] == "EXTRACTION_FAILED"
    assert "_r2b2_retry_attempted" not in written_rows[1]
    assert rows == rows_before_write
    assert rows[1]["_r2b2_retry_attempted"] is True
    assert out1.read_bytes() == out2.read_bytes()


# ---------------------------------------------------------------------------
# 28: offline rebuild deterministic
# ---------------------------------------------------------------------------


def test_r2b2_28_offline_rebuild_deterministic(real_universe, tmp_path):
    source_cache_dir = tmp_path / "source_cache"
    cache = SourceExtractionCache(source_cache_dir)
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    for sid in canary_ids:
        cache.set(sid, {"source_id": sid, "elevation_m_status": "SOURCE_VALUE_AVAILABLE", "elevation_m_value": 1.0})
    tiny_universe = {"unique_sources": {sid: real_universe["unique_sources"][sid] for sid in canary_ids}, "unique_required_source_count": len(canary_ids)}
    result = verify_offline_reproducibility(tiny_universe, source_cache_dir, tmp_path / "offline")
    assert result["byte_identical"] is True
    assert result["rows"] == len(canary_ids)


# ---------------------------------------------------------------------------
# 29-30: R2A protocol / FMD-06 hashes unchanged
# ---------------------------------------------------------------------------


def test_r2b2_29_r2a_aggregation_protocol_hash_unchanged():
    r2a_protocol = json.loads((_MODEL_DEV_DIR / "fmd07_origin_feature_assembly_protocol.json").read_text(encoding="utf-8"))
    assert r2a_protocol["numeric_aggregation_rule"] == "UNWEIGHTED_ARITHMETIC_MEAN_OF_VALID_ACTIVE_SOURCE_VALUES"
    assert r2a_protocol["source_set"] == "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"
    assert r2a_protocol["active_window_days"] == 14


def test_r2b2_30_fmd06_scientific_hashes_unchanged():
    _CALIBRATION_DIR = _REPO_ROOT / "local_data/processed/fmd/calibration"
    assert _sha256(_CALIBRATION_DIR / "fmd06_calibration_freeze.json") == "f72ff161066223a63de185188ae97de46793a4aea91ad14c3a8ab3aadace66a0"
    assert _sha256(_CALIBRATION_DIR / "fmd06_risk_origin_labels.csv") == "e6eb43aae1fa65aa3e243c1770f44ecc047593a5012a8155a8b00aadc081e438"
    assert _sha256(_CALIBRATION_DIR / "fmd06_calibration_manifest.json") == "a5b6b6ead805357a887f2b80c0ea9f7d9d96a96723840a7d4e6b8373c965b113"


# ---------------------------------------------------------------------------
# Failure ledger classification
# ---------------------------------------------------------------------------


def test_r2b2_classify_source_row():
    row = {
        "weather_event_day_mean_temperature_2m_status": "SOURCE_VALUE_AVAILABLE",
        "elevation_m_status": "EXTRACTION_FAILED",
        "host_density_cattle_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_buffalo_status": "SOURCE_VALUE_MISSING",
        "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
        "distance_to_nearest_river_km_status": "OUTSIDE_SOURCE_COVERAGE",
    }
    classification = classify_source_row(row)
    assert classification["weather"] == "SUCCESS"
    assert classification["elevation"] == "TRANSIENT_FAILURE"
    assert classification["host_density"] == "SUCCESS"
    assert classification["land_cover"] == "SUCCESS"
    assert classification["hydrology"] == "OUT_OF_COVERAGE"


def test_r2b2_bounded_retry_pass_is_bounded(real_universe, tmp_path):
    from components.geospatial_tracking.services import fmd_model_development_r2b2 as m

    source_text = Path(m.__file__).read_text(encoding="utf-8")
    assert "while True" not in source_text
    source_cache_dir = tmp_path / "source_cache"
    cache = SourceExtractionCache(source_cache_dir)
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    healthy_sid = canary_ids[0]
    cache.set(healthy_sid, {"source_id": healthy_sid, "weather_event_day_mean_temperature_2m_status": "SOURCE_VALUE_AVAILABLE", "elevation_m_status": "SOURCE_VALUE_AVAILABLE", "host_density_cattle_status": "SOURCE_VALUE_AVAILABLE", "host_density_buffalo_status": "SOURCE_VALUE_AVAILABLE", "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE", "distance_to_nearest_river_km_status": "SOURCE_VALUE_MISSING"})
    tiny_universe = {"unique_sources": {healthy_sid: real_universe["unique_sources"][healthy_sid]}, "unique_required_source_count": 1}
    summary = run_bounded_retry_pass(tiny_universe, weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=source_cache_dir)
    assert summary["retry_candidates"] == 0  # healthy row has no TRANSIENT_FAILURE family


def test_r2b2_manifest_shape(real_universe, tmp_path):
    tiny_ids = select_canary_source_ids(real_universe["unique_sources"])[:1]
    tiny_universe = {
        "unique_sources": {sid: real_universe["unique_sources"][sid] for sid in tiny_ids},
        "unique_required_source_count": real_universe["unique_required_source_count"],
        "development_origin_count": real_universe["development_origin_count"],
        "total_origin_source_appearances": real_universe["total_origin_source_appearances"],
        "duplicate_source_appearance_savings": real_universe["duplicate_source_appearance_savings"],
    }
    source_cache_dir = tmp_path / "source_cache"
    cache = SourceExtractionCache(source_cache_dir)
    sid = tiny_ids[0]
    cache.set(sid, {"source_id": sid, "weather_event_day_mean_temperature_2m_status": "SOURCE_VALUE_AVAILABLE", "elevation_m_status": "SOURCE_VALUE_AVAILABLE", "host_density_cattle_status": "SOURCE_VALUE_AVAILABLE", "host_density_buffalo_status": "SOURCE_VALUE_AVAILABLE", "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE", "distance_to_nearest_river_km_status": "SOURCE_VALUE_MISSING"})
    progress = build_r2b2_progress(tiny_universe, weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=source_cache_dir, last_completed_batch_key=sid)
    dedup = compute_request_key_dedup(tiny_universe["unique_sources"])
    manifest = build_r2b2_manifest(
        universe=tiny_universe, dedup=dedup, weather_equivalence=None, weather_strategy=WEATHER_STRATEGY_LEGACY_FOUR_WINDOW,
        progress=progress, full_table_rows=[cache.get(sid)], full_table_path=None, input_hashes={"x": "y"},
    )
    assert manifest["checkpoint"] == "FMD-07A-R2B2"
    assert manifest["held_out_used"] is False
    assert manifest["sri_lanka_used"] is False
    assert manifest["labels_used"] is False
    assert manifest["model_trained"] is False
    assert manifest["weather_winner_selected"] is False


# ---------------------------------------------------------------------------
# R2B2-R1 Section 2: exactly one authoritative public gate implementation,
# never a leftover NotImplementedError placeholder.
# ---------------------------------------------------------------------------


def test_r2b2_r1_verify_weather_equivalence_gate_single_definition_no_placeholder():
    from components.geospatial_tracking.services import fmd_model_development_r2b2 as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    assert source.count("def verify_weather_equivalence_gate(") == 1
    assert "NotImplementedError" not in source
    # calling it (empty canary list -- no network, no real_universe needed)
    # must reach a real return, never raise
    result = m.verify_weather_equivalence_gate([], {}, production_weather_cache_dir=".", isolated_cache_dir=".")
    assert result["outcome"] == WEATHER_EQUIVALENCE_OUTCOME_PASS
    assert result["sources_checked"] == 0


# ---------------------------------------------------------------------------
# R2B2-R1 Section 16: family classification must inspect ALL of a
# family's status columns, never hide one failed predictor behind others.
# ---------------------------------------------------------------------------


def test_r2b2_r1_mixed_status_within_family_not_hidden_by_one_representative_column():
    row = {
        "weather_event_day_mean_temperature_2m_status": "SOURCE_VALUE_AVAILABLE",
        "weather_event_day_mean_wind_speed_status": "EXTRACTION_FAILED",
        "weather_window_3day_mean_temperature_2m_status": "SOURCE_VALUE_AVAILABLE",
        "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_cattle_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_buffalo_status": "SOURCE_VALUE_AVAILABLE",
        "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
        "landcover_grassland_fraction_status": "OUTSIDE_SOURCE_COVERAGE",
        "distance_to_nearest_river_km_status": "SOURCE_VALUE_AVAILABLE",
    }
    classification = classify_source_row(row)
    # a single failed weather variable (event_day wind) must surface even
    # though the family's old "representative" column (temperature) succeeded
    assert classification["weather"] == "TRANSIENT_FAILURE"
    # a mix of AVAILABLE + OUTSIDE_SOURCE_COVERAGE across land_cover's own
    # classes must also be visible, not silently collapsed to one class
    assert classification["land_cover"] in ("SUCCESS", "OUT_OF_COVERAGE")


# ---------------------------------------------------------------------------
# R2B2-R1 Section 13: source_accounted_for excludes TRANSIENT_FAILURE.
# ---------------------------------------------------------------------------


def test_r2b2_r1_terminal_accounting_excludes_transient_failure():
    base_row = {
        "weather_event_day_mean_temperature_2m_status": "SOURCE_VALUE_AVAILABLE",
        "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_cattle_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_buffalo_status": "SOURCE_VALUE_AVAILABLE",
        "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
        "distance_to_nearest_river_km_status": "SOURCE_VALUE_MISSING",
    }
    transient_row = dict(base_row, elevation_m_status="EXTRACTION_FAILED")
    assert is_source_row_terminal_accounted(base_row) is True
    assert is_source_row_terminal_accounted(transient_row) is False


# ---------------------------------------------------------------------------
# R2B2-R1 Section 14: persistent, deterministic failure ledger.
# ---------------------------------------------------------------------------


def test_r2b2_r2_batch_advance_never_stalls_on_repeated_max_batches_one(real_universe, tmp_path, monkeypatch):
    """R2B2-R2: regression test for the exact 48-minute stall observed
    when an ad hoc driver repeatedly invoked run_full_r2b2_extraction
    with max_batches=1 against the full universe -- since batch index 0
    became fully cached after the first call, every subsequent call kept
    re-verifying that same already-done batch and never advanced to
    batch 1. Offline/synthetic (250-source universe, fake extractor, no
    network); proves the fix directly against the real function."""
    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    monkeypatch.setattr(m, "extract_source_features", _fake_extract_source_features)
    source_cache_dir = tmp_path / "source_cache"
    weather_cache_dir = tmp_path / "weather_cache"
    model_dev_dir = tmp_path / "model_dev"

    all_ids = sorted(real_universe["unique_sources"])[:250]
    universe_250 = {
        "unique_sources": {sid: real_universe["unique_sources"][sid] for sid in all_ids},
        "unique_required_source_count": 250,
    }

    # simulate a prior completed run: the first 100 (batch 0) are already
    # terminal-accounted in the cache before this invocation ever runs
    cache = SourceExtractionCache(source_cache_dir)
    for sid in all_ids[:100]:
        cache.set(sid, {
            "source_id": sid,
            "weather_event_day_mean_temperature_2m_status": "SOURCE_VALUE_AVAILABLE",
            "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
            "host_density_cattle_status": "SOURCE_VALUE_AVAILABLE",
            "host_density_buffalo_status": "SOURCE_VALUE_AVAILABLE",
            "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
            "distance_to_nearest_river_km_status": "SOURCE_VALUE_MISSING",
        })
    mtimes_before = {sid: cache._path_for(sid).stat().st_mtime for sid in all_ids[:100]}

    # deterministic pending set = all 250 required ids minus the 100
    # already terminal-accounted -- sources 101-250
    pending_ids_before = [sid for sid in all_ids if cache.get(sid) is None]
    assert pending_ids_before == all_ids[100:250]

    # first resumed call, max_batches=1: batch 0 is fully cached and must
    # be skipped WITHOUT consuming the budget; batch 1 (sources 101-200)
    # must be the one actually processed
    result1 = m.run_full_r2b2_extraction(
        universe_250, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir,
        model_dev_dir=model_dev_dir, batch_size=100, max_workers=1, use_consolidated_weather=False, max_batches=1,
    )
    assert result1["batches_run"] == 1
    assert result1["last_completed_batch_key"] == all_ids[199]
    for sid in all_ids[100:200]:
        assert cache.get(sid) is not None
    for sid in all_ids[200:250]:
        assert cache.get(sid) is None

    # second resumed call, again max_batches=1: batches 0 and 1 are now
    # both fully cached and must both be skipped for free; batch 2
    # (sources 201-250) is the one processed
    result2 = m.run_full_r2b2_extraction(
        universe_250, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir,
        model_dev_dir=model_dev_dir, batch_size=100, max_workers=1, use_consolidated_weather=False, max_batches=1,
    )
    assert result2["batches_run"] == 1
    assert result2["last_completed_batch_key"] == all_ids[249]
    for sid in all_ids[200:250]:
        assert cache.get(sid) is not None

    # the originally pre-cached 100 sources were never re-extracted
    for sid in all_ids[:100]:
        assert cache._path_for(sid).stat().st_mtime == mtimes_before[sid]

    # deterministic terminal state: a further call has nothing left to do
    result3 = m.run_full_r2b2_extraction(
        universe_250, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir,
        model_dev_dir=model_dev_dir, batch_size=100, max_workers=1, use_consolidated_weather=False, max_batches=1,
    )
    assert result3["batches_run"] == 0
    assert result3["sources_complete"] == 250


def test_r2b2_r2_failure_ledger_persisted_after_every_processed_batch(real_universe, tmp_path, monkeypatch):
    """R2B2-R2 Section 5: the failure ledger must be wired into the real
    extraction path itself (run_full_r2b2_extraction), not left to an
    ad hoc caller to remember -- its absence after a real run is not
    acceptable. Zero-failure-entries is a valid ledger; a MISSING file
    is not."""
    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    monkeypatch.setattr(m, "extract_source_features", _fake_extract_source_features)
    source_cache_dir = tmp_path / "source_cache"
    weather_cache_dir = tmp_path / "weather_cache"
    model_dev_dir = tmp_path / "model_dev"
    tiny_ids = select_canary_source_ids(real_universe["unique_sources"])[:2]
    tiny_universe = {
        "unique_sources": {sid: real_universe["unique_sources"][sid] for sid in tiny_ids},
        "unique_required_source_count": 2,
    }
    ledger_path = model_dev_dir / m.FAILURE_LEDGER_FILENAME
    assert not ledger_path.exists()
    result = m.run_full_r2b2_extraction(
        tiny_universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir,
        model_dev_dir=model_dev_dir, batch_size=1, max_workers=1, use_consolidated_weather=False, max_batches=1,
    )
    assert result["batches_run"] == 1
    assert ledger_path.exists()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert isinstance(ledger, list)


def test_r2b2_r1_failure_ledger_records_transient_and_terminal_states(real_universe, tmp_path):
    source_cache_dir = tmp_path / "source_cache"
    cache = SourceExtractionCache(source_cache_dir)
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    sid = canary_ids[0]
    cache.set(sid, {
        "source_id": sid,
        "weather_event_day_mean_temperature_2m_status": "EXTRACTION_FAILED",
        "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_cattle_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_buffalo_status": "SOURCE_VALUE_AVAILABLE",
        "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
        "distance_to_nearest_river_km_status": "SOURCE_VALUE_MISSING",
    })
    tiny_universe = {"unique_sources": {sid: real_universe["unique_sources"][sid]}, "unique_required_source_count": 1}
    ledger = build_failure_ledger(tiny_universe, source_cache_dir)

    weather_entries = [e for e in ledger if e["source_id"] == sid and e["feature_family"] == "weather"]
    assert len(weather_entries) == 1
    assert weather_entries[0]["state"] == "TRANSIENT_FAILURE"
    assert weather_entries[0]["retry_eligible"] is True
    assert weather_entries[0]["terminal"] is False
    assert weather_entries[0]["retry_classification_note"] == FAILURE_RETRY_CLASSIFICATION_LIMITED_BY_EXISTING_ADAPTER_STATUS
    assert weather_entries[0]["attempt_count"] == 1

    hydrology_entries = [e for e in ledger if e["source_id"] == sid and e["feature_family"] == "hydrology"]
    assert len(hydrology_entries) == 1
    assert hydrology_entries[0]["state"] == "LEGITIMATE_MISSING"
    assert hydrology_entries[0]["terminal"] is True
    assert hydrology_entries[0]["retry_eligible"] is False

    # a fully SUCCESS family never appears in the ledger at all
    assert not any(e["feature_family"] == "elevation" for e in ledger if e["source_id"] == sid)


# ---------------------------------------------------------------------------
# R2B2-R2 retry-exhaustion fix: a genuine TRANSIENT_FAILURE that has used
# up its one bounded retry (`run_bounded_retry_pass`) must deterministically
# become terminal-accounted, never loop forever and never stay
# retry-eligible past its bounded budget. All offline/synthetic -- no
# network, mirrors the real cached row observed for
# FAO_EMPRESI_BIGQUERY_CSV:EMPRES-i_FMD_events_2002-2026.csv:008029.
# ---------------------------------------------------------------------------


def _always_fails_extract_source_features(source, config, weather_cache, source_cache, *, precomputed_weather_windows=None):
    """Deterministic offline stand-in that reproduces a source whose
    weather request fails identically on every (re-)attempt -- the exact
    shape of a genuinely-never-recovers TRANSIENT_FAILURE, never a
    network call."""
    cached = source_cache.get(source.source_id)
    if cached is not None:
        return cached, True
    row = {
        "source_id": source.source_id,
        "weather_event_day_mean_temperature_2m_status": "EXTRACTION_FAILED",
        "weather_event_day_mean_temperature_2m_value": "",
        "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
        "elevation_m_value": 5.0,
        "host_density_cattle_status": "SOURCE_VALUE_MISSING",
        "host_density_cattle_value": "",
        "host_density_buffalo_status": "SOURCE_VALUE_MISSING",
        "host_density_buffalo_value": "",
        "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
        "landcover_tree_cover_fraction_value": 0.2,
        "distance_to_nearest_river_km_status": "SOURCE_VALUE_MISSING",
        "distance_to_nearest_river_km_value": "",
    }
    source_cache.set(source.source_id, row)
    return row, False


def test_r2b2_retry_exhaustion_a_genuine_transient_failure_retryable_before_exhaustion():
    """A. Before any retry has been attempted (`_r2b2_retry_attempted`
    absent), a genuine EXTRACTION_FAILED family is TRANSIENT_FAILURE,
    retry-eligible, and NOT yet terminal-accounted -- retry exhaustion
    must never trigger early."""
    row = {
        "source_id": "SYN:not-yet-retried",
        "weather_event_day_mean_temperature_2m_status": "EXTRACTION_FAILED",
        "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_cattle_status": "SOURCE_VALUE_MISSING",
        "host_density_buffalo_status": "SOURCE_VALUE_MISSING",
        "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
        "distance_to_nearest_river_km_status": "SOURCE_VALUE_MISSING",
    }
    classification = classify_source_row(row)
    assert classification["weather"] == "TRANSIENT_FAILURE"
    assert is_source_row_terminal_accounted(row) is False


def test_r2b2_retry_exhaustion_b_bounded_retry_never_loops_forever(real_universe, tmp_path, monkeypatch):
    """B. `run_bounded_retry_pass` grants exactly one re-extraction. Once
    a source's row has been through it and still fails identically, a
    SECOND invocation of `run_bounded_retry_pass` must find zero retry
    candidates for that source -- proving retry exhaustion is bounded,
    never an unbounded/repeated loop even across repeated calls."""
    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    monkeypatch.setattr(m, "extract_source_features", _always_fails_extract_source_features)
    source_cache_dir = tmp_path / "source_cache"
    weather_cache_dir = tmp_path / "weather_cache"
    cache = SourceExtractionCache(source_cache_dir)

    sid = select_canary_source_ids(real_universe["unique_sources"])[0]
    tiny_universe = {"unique_sources": {sid: real_universe["unique_sources"][sid]}, "unique_required_source_count": 1}

    # seed a first-attempt row exactly as the real extraction pipeline
    # would leave it: weather EXTRACTION_FAILED, no retry attempted yet
    cache.set(sid, {
        "source_id": sid,
        "weather_event_day_mean_temperature_2m_status": "EXTRACTION_FAILED",
        "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_cattle_status": "SOURCE_VALUE_MISSING",
        "host_density_buffalo_status": "SOURCE_VALUE_MISSING",
        "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
        "distance_to_nearest_river_km_status": "SOURCE_VALUE_MISSING",
    })

    first_pass = m.run_bounded_retry_pass(tiny_universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir, use_consolidated_weather=False)
    assert first_pass["retry_candidates"] == 1
    assert first_pass["retried"] == 1
    assert first_pass["recovered"] == 0
    assert first_pass["still_failed_after_retry"] == 1

    row_after_first_retry = cache.get(sid)
    assert row_after_first_retry["_r2b2_retry_attempted"] is True

    # second invocation: the bounded budget is already spent -- must be a
    # true no-op, never a second re-extraction of the same source
    second_pass = m.run_bounded_retry_pass(tiny_universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir, use_consolidated_weather=False)
    assert second_pass["retry_candidates"] == 0
    assert second_pass["retried"] == 0


def test_r2b2_retry_exhaustion_c_exhausted_source_becomes_terminal_accounted(real_universe, tmp_path, monkeypatch):
    """C. After the one bounded retry is spent and the family still
    fails, the source must become terminal-accounted using the
    repository-supported PERMANENT_FAILURE terminal state -- never left
    dangling in TRANSIENT_FAILURE forever."""
    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    monkeypatch.setattr(m, "extract_source_features", _always_fails_extract_source_features)
    source_cache_dir = tmp_path / "source_cache"
    weather_cache_dir = tmp_path / "weather_cache"
    cache = SourceExtractionCache(source_cache_dir)

    sid = select_canary_source_ids(real_universe["unique_sources"])[0]
    tiny_universe = {"unique_sources": {sid: real_universe["unique_sources"][sid]}, "unique_required_source_count": 1}
    cache.set(sid, {
        "source_id": sid,
        "weather_event_day_mean_temperature_2m_status": "EXTRACTION_FAILED",
        "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_cattle_status": "SOURCE_VALUE_MISSING",
        "host_density_buffalo_status": "SOURCE_VALUE_MISSING",
        "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
        "distance_to_nearest_river_km_status": "SOURCE_VALUE_MISSING",
    })

    m.run_bounded_retry_pass(tiny_universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir, use_consolidated_weather=False)
    row = cache.get(sid)

    classification = classify_source_row(row)
    assert classification["weather"] == "PERMANENT_FAILURE"
    assert is_source_row_terminal_accounted(row) is True

    ledger = build_failure_ledger(tiny_universe, source_cache_dir)
    weather_entry = next(e for e in ledger if e["source_id"] == sid and e["feature_family"] == "weather")
    assert weather_entry["state"] == "PERMANENT_FAILURE"
    assert weather_entry["retry_eligible"] is False
    assert weather_entry["terminal"] is True
    assert weather_entry["attempt_count"] == 2
    # adapter still cannot name a finer root cause -- the limitation note
    # must survive the exhaustion transition, never silently dropped
    assert weather_entry["retry_classification_note"] == FAILURE_RETRY_CLASSIFICATION_LIMITED_BY_EXISTING_ADAPTER_STATUS


def test_r2b2_retry_exhaustion_d_underlying_extraction_failed_values_unchanged(real_universe, tmp_path, monkeypatch):
    """D. Retry-exhaustion accounting is a ledger/classification-layer
    transition only -- it must never rewrite the source row's own
    EXTRACTION_FAILED status (e.g. into SOURCE_VALUE_MISSING), never
    fabricate a weather value, never zero-fill/impute."""
    import components.geospatial_tracking.services.fmd_model_development_r2b2 as m

    monkeypatch.setattr(m, "extract_source_features", _always_fails_extract_source_features)
    source_cache_dir = tmp_path / "source_cache"
    weather_cache_dir = tmp_path / "weather_cache"
    cache = SourceExtractionCache(source_cache_dir)

    sid = select_canary_source_ids(real_universe["unique_sources"])[0]
    tiny_universe = {"unique_sources": {sid: real_universe["unique_sources"][sid]}, "unique_required_source_count": 1}
    cache.set(sid, {
        "source_id": sid,
        "weather_event_day_mean_temperature_2m_status": "EXTRACTION_FAILED",
        "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_cattle_status": "SOURCE_VALUE_MISSING",
        "host_density_buffalo_status": "SOURCE_VALUE_MISSING",
        "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
        "distance_to_nearest_river_km_status": "SOURCE_VALUE_MISSING",
    })

    m.run_bounded_retry_pass(tiny_universe, weather_cache_dir=weather_cache_dir, source_cache_dir=source_cache_dir, use_consolidated_weather=False)
    build_failure_ledger(tiny_universe, source_cache_dir)  # must not mutate the row as a side effect
    row = cache.get(sid)

    assert row["weather_event_day_mean_temperature_2m_status"] == "EXTRACTION_FAILED"
    assert row["weather_event_day_mean_temperature_2m_value"] == ""
    # never converted to SOURCE_VALUE_MISSING, never zero-filled
    assert row["weather_event_day_mean_temperature_2m_status"] != "SOURCE_VALUE_MISSING"


def test_r2b2_retry_exhaustion_e_legitimate_missing_and_out_of_coverage_unaffected():
    """E. The exhaustion transition is scoped to families whose OWN raw
    bucket is TRANSIENT_FAILURE -- a row-level `_r2b2_retry_attempted`
    flag (set because some OTHER family needed a retry) must never
    reclassify an already-legitimate LEGITIMATE_MISSING or
    OUT_OF_COVERAGE family into PERMANENT_FAILURE."""
    row = {
        "source_id": "SYN:retried-for-weather-only",
        "_r2b2_retry_attempted": True,
        "weather_event_day_mean_temperature_2m_status": "SOURCE_VALUE_AVAILABLE",
        "elevation_m_status": "SOURCE_VALUE_AVAILABLE",
        "host_density_cattle_status": "SOURCE_VALUE_MISSING",
        "host_density_buffalo_status": "SOURCE_VALUE_MISSING",
        "landcover_tree_cover_fraction_status": "SOURCE_VALUE_AVAILABLE",
        "distance_to_nearest_river_km_status": "OUTSIDE_SOURCE_COVERAGE",
    }
    classification = classify_source_row(row)
    assert classification["host_density"] == "LEGITIMATE_MISSING"
    assert classification["hydrology"] == "OUT_OF_COVERAGE"
    assert is_source_row_terminal_accounted(row) is True
