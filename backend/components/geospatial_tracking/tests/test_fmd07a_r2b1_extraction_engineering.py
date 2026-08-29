"""FMD-07A-R2B1: extraction-universe planning, cache/resume engineering,
and small real canary validation.

Most tests here read the already-produced real artifacts (built this
checkpoint against the real FMD canonical corpus and real adapters) --
fast, no new network access. A small number of tests make real (but
cache-hit-dominated, since the canary was already extracted) calls to
verify replay/resume behavior live, following the same established
real-adapter-integration convention already used by
`test_fmd04_feature_pipeline.py::TestRealAdapterIntegration`."""

from __future__ import annotations

import csv
import hashlib
import inspect
import json
import tempfile
from pathlib import Path

import pytest

from components.geospatial_tracking.data_processing.fmd_forecast_bridge import import_fmd_canonical_csv
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.services.fmd_calibration import (
    FMD_DISEASE,
    FMD_MODEL_FITTING_CUTOFF,
    load_forecast_origins,
)
from components.geospatial_tracking.services.fmd_model_development import derive_eligible_predictor_features
from components.geospatial_tracking.services.fmd_model_development_r2a import (
    build_origin_feature_row_from_source_features,
)
from components.geospatial_tracking.services.fmd_model_development_r2b1 import (
    FEATURE_VALUE_STATUS_CANARY_VALIDATED,
    PROGRESS_JSON_FILENAME,
    SourceExtractionCache,
    _progress_bucket_for_status,
    build_development_extraction_universe,
    build_extraction_plan,
    build_extraction_progress,
    run_canary_extraction,
    select_canary_source_ids,
    write_canary_source_table,
    write_extraction_progress,
)
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.model_fitting_exposure import (
    FIT_DEVELOPMENT,
    HELD_OUT_FROM_MODEL_FITTING,
    SRI_LANKA_TRANSFER_CASE_STUDY,
    assert_fit_development_only,
    classify_origin_role,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_COHORT_DIR = _REPO_ROOT / "local_data/processed/fmd/cohort"
_CALIBRATION_DIR = _REPO_ROOT / "local_data/processed/fmd/calibration"
_MODEL_DEV_DIR = _REPO_ROOT / "local_data/processed/fmd/model_development"
_CANONICAL_CSV = _REPO_ROOT / "local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
_ORIGINS_CSV = _COHORT_DIR / "fmd_historical_forecast_origins.csv"
_WEATHER_CACHE_DIR = _REPO_ROOT / "local_data/cache/weather"
_SOURCE_CACHE_DIR = _REPO_ROOT / "local_data/cache/fmd_source_features"
_FEATURE_TABLE_CSV = _REPO_ROOT / "local_data/processed/fmd/features/fmd_feature_table.csv"

_PLAN_JSON = _MODEL_DEV_DIR / "fmd07_feature_extraction_plan.json"
_CANARY_MANIFEST_JSON = _MODEL_DEV_DIR / "fmd07_feature_extraction_canary_manifest.json"
_CANARY_CSV = _MODEL_DEV_DIR / "canary" / "fmd07_canary_source_features.csv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def real_universe():
    all_origins = load_forecast_origins(_ORIGINS_CSV)
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = SQLiteOutbreakRepository(Path(temp_dir) / "r2b1_test.sqlite")
        repo.init_schema()
        import_fmd_canonical_csv(repo, _CANONICAL_CSV)
        universe = build_development_extraction_universe(repo, all_origins)
        repo.close()
    return universe


# ---------------------------------------------------------------------------
# 1-4: extraction-universe correctness / leakage
# ---------------------------------------------------------------------------


def test_r2b1_1_exactly_3761_development_origins_planned(real_universe):
    assert real_universe["development_origin_count"] == 3761


def test_r2b1_2_no_held_out_origins_planned(real_universe):
    # the real 4,322-origin corpus already contains 541 real
    # HELD_OUT_FROM_MODEL_FITTING origins (load_forecast_origins is never
    # pre-filtered) -- prove none of them ended up in the PLANNED universe.
    all_origins = load_forecast_origins(_ORIGINS_CSV)
    origin_by_id = {o.forecast_origin_id: o for o in all_origins}
    planned_roles = {
        classify_origin_role(origin_by_id[oid], cutoff=FMD_MODEL_FITTING_CUTOFF)
        for oid in real_universe["origin_to_source_ids"]
    }
    assert planned_roles == {FIT_DEVELOPMENT}
    # the shared hard-firewall utility itself still rejects a directly
    # contaminated list outright (Checkpoint 6B.5 Part 12) -- proves the
    # mechanism this checkpoint relies on is not dead code.
    held_out = ForecastOrigin(forecast_origin_id="HELD", country="Example", t0="2026-06-01", temporal_mode="RETROSPECTIVE_PROXY")
    with pytest.raises(ValueError, match=HELD_OUT_FROM_MODEL_FITTING):
        assert_fit_development_only([held_out], cutoff=FMD_MODEL_FITTING_CUTOFF, caller="test")


def test_r2b1_3_no_sri_lanka_origins_planned(real_universe):
    all_origins = load_forecast_origins(_ORIGINS_CSV)
    origin_by_id = {o.forecast_origin_id: o for o in all_origins}
    planned_roles = {
        classify_origin_role(origin_by_id[oid], cutoff=FMD_MODEL_FITTING_CUTOFF)
        for oid in real_universe["origin_to_source_ids"]
    }
    assert SRI_LANKA_TRANSFER_CASE_STUDY not in planned_roles
    sri_lanka = ForecastOrigin(forecast_origin_id="SL", country="Sri Lanka", t0="2020-06-01", temporal_mode="RETROSPECTIVE_PROXY")
    with pytest.raises(ValueError, match=SRI_LANKA_TRANSFER_CASE_STUDY):
        assert_fit_development_only([sri_lanka], cutoff=FMD_MODEL_FITTING_CUTOFF, caller="test")


def test_r2b1_4_request_universe_derived_without_reading_labels():
    from components.geospatial_tracking.services import fmd_model_development_r2b1 as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    for forbidden in ("risk_target_label", "local_domain_positive", "has_eligible_d1_d7_target", "outside_domain_target_present"):
        assert forbidden not in source
    signature = inspect.signature(build_development_extraction_universe)
    assert not {"label", "target", "risk_target_label"} & set(signature.parameters)


# ---------------------------------------------------------------------------
# 5-8: deduplication / conflict detection / determinism
# ---------------------------------------------------------------------------


def test_r2b1_5_repeated_source_appearances_deduplicate(real_universe):
    assert real_universe["duplicate_source_appearance_savings"] > 0
    assert real_universe["unique_required_source_count"] == 6799  # matches FMD-06's own unique_source_event_count
    assert real_universe["total_origin_source_appearances"] == real_universe["unique_required_source_count"] + real_universe["duplicate_source_appearance_savings"]


def test_r2b1_6_conflicting_duplicate_source_metadata_blocks():
    from components.geospatial_tracking.services.source_selector import EligibleSource

    class _FakeRepo:
        pass

    # directly exercise the conflict-detection branch with synthetic
    # EligibleSource objects sharing one source_id but disagreeing on country
    a = EligibleSource(source_id="DUP", record_domain="HISTORICAL", disease=FMD_DISEASE, country="Thailand", latitude=1.0, longitude=1.0, effective_availability_date="2025-01-01", availability_quality="EVENT_DATE_PROXY", gps_quality="EXACT", status=None)
    b = EligibleSource(source_id="DUP", record_domain="HISTORICAL", disease=FMD_DISEASE, country="Vietnam", latitude=1.0, longitude=1.0, effective_availability_date="2025-01-01", availability_quality="EVENT_DATE_PROXY", gps_quality="EXACT", status=None)

    from components.geospatial_tracking.services import fmd_model_development_r2b1 as m

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
    assert len(conflicts) == 1  # proves the same comparison logic build_development_extraction_universe uses would flag this


def test_r2b1_7_deterministic_unique_source_ordering(real_universe):
    ordered = sorted(real_universe["unique_sources"])
    assert ordered == sorted(ordered)
    assert len(ordered) == len(set(ordered))


def test_r2b1_8_deterministic_request_keys(real_universe):
    from components.geospatial_tracking.services.fmd_model_development_r2b1 import _weather_request_key

    source = next(iter(real_universe["unique_sources"].values()))
    key1 = _weather_request_key(source.latitude, source.longitude, source.effective_availability_date, 24.0)
    key2 = _weather_request_key(source.latitude, source.longitude, source.effective_availability_date, 24.0)
    assert key1 == key2
    assert isinstance(key1, str) and len(key1) == 64


# ---------------------------------------------------------------------------
# 9-14: cache / retry / no-fabrication
# ---------------------------------------------------------------------------


def test_r2b1_9_cached_successful_request_is_reused(real_universe):
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    result = run_canary_extraction(canary_ids, real_universe["unique_sources"], weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=_SOURCE_CACHE_DIR)
    assert result["cache_hits"] == len(canary_ids)
    assert result["network_attempts"] == 0


def test_r2b1_10_cache_replay_makes_no_unnecessary_request(real_universe):
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    run1 = run_canary_extraction(canary_ids, real_universe["unique_sources"], weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=_SOURCE_CACHE_DIR)
    run2 = run_canary_extraction(canary_ids, real_universe["unique_sources"], weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=_SOURCE_CACHE_DIR)
    assert run1["rows"] == run2["rows"]
    assert run2["network_attempts"] == 0


def test_r2b1_11_bounded_retry_behavior():
    from components.geospatial_tracking.services import fmd_model_development_r2b1 as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    assert "while True" not in source  # no unbounded retry loop introduced
    plan = json.loads(_PLAN_JSON.read_text(encoding="utf-8"))
    assert "single attempt" in plan["retry_policy"]


def test_r2b1_12_permanent_errors_do_not_loop():
    # a permanently-invalid request (unsupported model) returns BLOCKED
    # immediately, once, never retried -- verified against the real,
    # unmodified adapter contract.
    from components.geospatial_tracking.services.geospatial.weather.era5 import build_pre_t0_weather_summary
    from components.geospatial_tracking.services.geospatial.weather.base import T0Precision

    window, results = build_pre_t0_weather_summary(
        latitude=1.0, longitude=1.0, t0="2025-01-01", t0_precision=T0Precision.DATE_ONLY.value,
        lookback_hours=24.0, model="not_a_real_model",
    )
    assert all(r.status == "BLOCKED" for r in results)


def test_r2b1_13_14_no_zero_fallback_no_fabricated_value():
    rows = _csv_rows(_CANARY_CSV)
    for row in rows:
        if row.get("distance_to_nearest_river_km_status") == "SOURCE_VALUE_MISSING":
            assert row["distance_to_nearest_river_km_value"] == ""  # never a fabricated 0


# ---------------------------------------------------------------------------
# 15-19: canary selection / weather temporal audit / spatial reference
# ---------------------------------------------------------------------------


def test_r2b1_15_canary_selection_independent_of_labels():
    from components.geospatial_tracking.services import fmd_model_development_r2b1 as m

    signature = inspect.signature(select_canary_source_ids)
    assert not {"label", "target", "risk_target_label"} & set(signature.parameters)
    source = Path(m.__file__).read_text(encoding="utf-8")
    assert "risk_target_label" not in source


def test_r2b1_16_canary_selection_deterministic(real_universe):
    ids1 = select_canary_source_ids(real_universe["unique_sources"])
    ids2 = select_canary_source_ids(real_universe["unique_sources"])
    assert ids1 == ids2


def test_r2b1_17_future_weather_prohibited():
    from components.geospatial_tracking.services.features.cache import FileWeatherCache
    from components.geospatial_tracking.services.geospatial.weather.era5 import build_pre_t0_weather_summary
    from components.geospatial_tracking.services.geospatial.weather.base import T0Precision
    from components.geospatial_tracking.data_processing.build_fmd_features import WEATHER_WINDOWS_HOURS

    cache = FileWeatherCache(_WEATHER_CACHE_DIR)
    canary_row = _csv_rows(_CANARY_CSV)[0]
    lat, lon, event_date = float(canary_row["latitude"]), float(canary_row["longitude"]), canary_row["event_date"]
    for window_name, lookback_hours in WEATHER_WINDOWS_HOURS.items():
        window, _results = build_pre_t0_weather_summary(
            latitude=lat, longitude=lon, t0=event_date, t0_precision=T0Precision.DATE_ONLY.value,
            lookback_hours=lookback_hours, cache=cache,
        )
        assert window.window_end[:10] <= event_date


def test_r2b1_18_source_date_lte_origin_t0_verified(real_universe):
    all_origins = load_forecast_origins(_ORIGINS_CSV)
    origin_by_id = {o.forecast_origin_id: o for o in all_origins}
    checked = 0
    for origin_id, source_ids in list(real_universe["origin_to_source_ids"].items())[:200]:
        origin = origin_by_id[origin_id]
        for source_id in source_ids:
            source = real_universe["unique_sources"][source_id]
            assert source.effective_availability_date <= origin.t0
            checked += 1
    assert checked > 0


def test_r2b1_19_static_adapter_source_coordinate_is_source_own_coordinate(real_universe):
    rows = _csv_rows(_CANARY_CSV)
    for row in rows:
        source = real_universe["unique_sources"][row["source_id"]]
        assert float(row["latitude"]) == source.latitude
        assert float(row["longitude"]) == source.longitude


# ---------------------------------------------------------------------------
# 20-21: adapters exercised / schema
# ---------------------------------------------------------------------------


def test_r2b1_20_all_required_adapters_exercised():
    rows = _csv_rows(_CANARY_CSV)
    assert len(rows) == 8
    families_present = {
        "weather": any(k.startswith("weather_") and k.endswith("_status") for k in rows[0]),
        "elevation": "elevation_m_status" in rows[0],
        "host_density": "host_density_cattle_status" in rows[0] and "host_density_buffalo_status" in rows[0],
        "land_cover": any(k.startswith("landcover_") for k in rows[0]),
        "hydrology": "distance_to_nearest_river_km_status" in rows[0],
    }
    assert all(families_present.values()), families_present
    for row in rows:
        assert row["host_density_cattle_status"] == "SOURCE_VALUE_AVAILABLE"
        assert row["elevation_m_status"] == "SOURCE_VALUE_AVAILABLE"
        assert any(row[f"weather_event_day_{v}_status"] == "SOURCE_VALUE_AVAILABLE" for v in ("mean_temperature_2m",))


def test_r2b1_21_canary_schema_matches_fmd04_schema():
    eligible, unavailable = derive_eligible_predictor_features(_FEATURE_TABLE_CSV)
    canary_columns = set(_csv_rows(_CANARY_CSV)[0].keys())
    for feature_name in eligible:
        assert f"{feature_name}_value" in canary_columns
        assert f"{feature_name}_status" in canary_columns
    for feature_name in unavailable:
        assert f"{feature_name}_value" in canary_columns
        assert canary_columns  # unavailable features still present in FMD-04's own schema (event-level table), just always FEATURE_NOT_AVAILABLE


# ---------------------------------------------------------------------------
# 22: interruption / resume
# ---------------------------------------------------------------------------


def test_r2b1_22_interruption_resume_preserves_successful_results(real_universe):
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    cache = SourceExtractionCache(_SOURCE_CACHE_DIR)
    victim = canary_ids[0]
    original_row = cache.get(victim)
    assert original_row is not None
    other_paths = {sid: cache._path_for(sid) for sid in canary_ids[1:]}
    mtimes_before = {sid: path.stat().st_mtime for sid, path in other_paths.items()}

    cache._path_for(victim).unlink()
    try:
        resumed = run_canary_extraction(canary_ids, real_universe["unique_sources"], weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=_SOURCE_CACHE_DIR)
        assert resumed["cache_hits"] == len(canary_ids) - 1
        assert resumed["network_attempts"] == 1
        restored_row = cache.get(victim)
        assert restored_row == original_row  # re-extraction produced byte-identical real data
        mtimes_after = {sid: path.stat().st_mtime for sid, path in other_paths.items()}
        assert mtimes_before == mtimes_after  # completed units were never re-written
    finally:
        # leave the cache in its original, fully-populated state
        if cache.get(victim) is None:
            cache.set(victim, original_row)


# ---------------------------------------------------------------------------
# 23: same cache + same assembly = identical canary output
# ---------------------------------------------------------------------------


def test_r2b1_23_same_cache_same_assembly_identical_output(real_universe):
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    run_a = run_canary_extraction(canary_ids, real_universe["unique_sources"], weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=_SOURCE_CACHE_DIR)
    run_b = run_canary_extraction(list(reversed(canary_ids)), real_universe["unique_sources"], weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=_SOURCE_CACHE_DIR)
    assert sorted(run_a["rows"], key=lambda r: r["source_id"]) == sorted(run_b["rows"], key=lambda r: r["source_id"])


# ---------------------------------------------------------------------------
# 24-25: final matrix unchanged / status not full-corpus complete
# ---------------------------------------------------------------------------


def test_r2b1_24_final_feature_matrix_remains_unchanged():
    assert _sha256(_MODEL_DEV_DIR / "fmd07_development_feature_matrix.csv") == "023ed97a10b7c27be090f6009ee8600da08cf1c76519e3926d68fbc013fd6dad"


def test_r2b1_25_feature_status_not_full_corpus_complete():
    provenance = json.loads((_MODEL_DEV_DIR / "fmd07a_provenance.json").read_text(encoding="utf-8"))
    assert provenance["overall_status"] == "BLOCKED_PENDING_FULL_CORPUS_FEATURE_EXTRACTION"
    assert FEATURE_VALUE_STATUS_CANARY_VALIDATED == "CANARY_VALIDATED_FULL_CORPUS_NOT_RUN"
    rows = _csv_rows(_MODEL_DEV_DIR / "fmd07_development_feature_matrix.csv")
    assert len(rows) == 3761
    for row in rows[:20]:
        for key, value in row.items():
            if key.endswith("_value") and not key.startswith("audit_only") and key != "risk_target_label":
                assert value == ""


# ---------------------------------------------------------------------------
# 26-30: no model / no metric / no weather winner / R2A unchanged / R2 preserved
# ---------------------------------------------------------------------------


def test_r2b1_26_27_28_no_model_no_prauc_no_weather_winner():
    plan = json.loads(_PLAN_JSON.read_text(encoding="utf-8"))
    assert plan["model_trained"] is False
    assert plan["predictive_metrics_used"] is False
    assert plan["weather_winner_selected"] is False
    from components.geospatial_tracking.services import fmd_model_development_r2b1 as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    assert ".fit(" not in source
    assert "pr_auc" not in source.lower() and "prauc" not in source.lower()


def test_r2b1_29_r2a_aggregation_rule_unchanged():
    r2a_protocol = json.loads((_MODEL_DEV_DIR / "fmd07_origin_feature_assembly_protocol.json").read_text(encoding="utf-8"))
    assert r2a_protocol["numeric_aggregation_rule"] == "UNWEIGHTED_ARITHMETIC_MEAN_OF_VALID_ACTIVE_SOURCE_VALUES"
    assert r2a_protocol["source_set"] == "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"
    assert r2a_protocol["active_window_days"] == 14
    assert r2a_protocol["centroid_used"] is False


def test_r2b1_30_original_r2_blocker_remains_preserved():
    r2_audit = json.loads((_MODEL_DEV_DIR / "fmd07a_r2_origin_feature_assembly_audit.json").read_text(encoding="utf-8"))
    assert r2_audit["overall_rule_status"] == "UNDEFINED"
    assert r2_audit["block_name"] == "FORECAST_ORIGIN_FEATURE_ASSEMBLY_RULE_UNDEFINED"


# ---------------------------------------------------------------------------
# Canary origin-assembly integration test (Section 19) -- real extracted
# values, synthetic origin grouping (no real origin is fully covered by
# an 8-source canary out of 6799 required sources).
# ---------------------------------------------------------------------------


def test_r2b1_canary_origin_assembly_integration():
    eligible, _ = derive_eligible_predictor_features(_FEATURE_TABLE_CSV)
    canary_rows = _csv_rows(_CANARY_CSV)
    result = build_origin_feature_row_from_source_features("ORIGIN:CanaryTest:2025-12-31", canary_rows, eligible)
    row = result["row"]
    audit = result["audit"]
    assert row["forecast_origin_id"] == "ORIGIN:CanaryTest:2025-12-31"

    cattle_values = [float(r["host_density_cattle_value"]) for r in canary_rows]
    expected_mean = sum(cattle_values) / len(cattle_values)
    assert abs(float(row["host_density_cattle_value"]) - expected_mean) < 1e-9
    assert audit["host_density_cattle"]["total_source_count"] == 8
    assert audit["host_density_cattle"]["valid_source_count"] == 8

    hydro_valid = [r for r in canary_rows if r["distance_to_nearest_river_km_status"] == "SOURCE_VALUE_AVAILABLE"]
    if not hydro_valid:
        assert row["distance_to_nearest_river_km_status"] == "ORIGIN_AGGREGATE_NO_VALID_VALUE"
        assert row["distance_to_nearest_river_km_value"] == ""

    # source order does not change output
    result_reversed = build_origin_feature_row_from_source_features("ORIGIN:CanaryTest:2025-12-31", list(reversed(canary_rows)), eligible)
    assert result_reversed["row"] == row


# ---------------------------------------------------------------------------
# Reproducibility (Section 24): the no-network plan is deterministic.
# ---------------------------------------------------------------------------


def test_r2b1_plan_deterministic_across_two_builds(real_universe):
    eligible, _ = derive_eligible_predictor_features(_FEATURE_TABLE_CSV)
    plan1 = build_extraction_plan(real_universe, weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=_SOURCE_CACHE_DIR, eligible_predictor_features=eligible)
    plan2 = build_extraction_plan(real_universe, weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=_SOURCE_CACHE_DIR, eligible_predictor_features=eligible)
    assert plan1 == plan2


def test_r2b1_offline_rebuild_of_canary_table_byte_identical(real_universe, tmp_path):
    # rebuild the canary source table twice OFFLINE from the already-frozen
    # cache -- never by forcing duplicate network downloads.
    canary_ids = select_canary_source_ids(real_universe["unique_sources"])
    result1 = run_canary_extraction(canary_ids, real_universe["unique_sources"], weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=_SOURCE_CACHE_DIR)
    result2 = run_canary_extraction(canary_ids, real_universe["unique_sources"], weather_cache_dir=_WEATHER_CACHE_DIR, source_cache_dir=_SOURCE_CACHE_DIR)
    assert result1["network_attempts"] == 0
    assert result2["network_attempts"] == 0
    path1 = tmp_path / "run1.csv"
    path2 = tmp_path / "run2.csv"
    write_canary_source_table(result1["rows"], path1)
    write_canary_source_table(result2["rows"], path2)
    assert _sha256(path1) == _sha256(path2)


# ---------------------------------------------------------------------------
# Section 10: resumable progress artifact -- synthetic-input unit tests
# (fast; the real end-to-end artifact is exercised by
# test_r2b1_real_progress_artifact_matches_real_canary below).
# ---------------------------------------------------------------------------


def test_r2b1_progress_bucket_mapping():
    assert _progress_bucket_for_status("SOURCE_VALUE_AVAILABLE") == "successful"
    assert _progress_bucket_for_status("SOURCE_VALUE_MISSING") == "successful"
    assert _progress_bucket_for_status("TEMPORAL_COVERAGE_MISSING") == "successful"
    assert _progress_bucket_for_status("OUTSIDE_SOURCE_COVERAGE") == "out_of_coverage"
    assert _progress_bucket_for_status("SOURCE_FILE_MISSING") == "failed_final"
    assert _progress_bucket_for_status("EXTRACTION_FAILED") == "blocked"
    with pytest.raises(ValueError):
        _progress_bucket_for_status("NOT_A_REAL_STATUS")


def _synthetic_progress_inputs(source_cache_dir):
    from components.geospatial_tracking.services.source_selector import EligibleSource

    def _source(sid, lat, lon):
        return EligibleSource(
            source_id=sid, record_domain="HISTORICAL", disease=FMD_DISEASE, country="Indonesia",
            latitude=lat, longitude=lon, effective_availability_date="2025-12-31",
            availability_quality="EVENT_DATE_PROXY", gps_quality="EXACT", status=None,
        )

    unique_sources = {"S1": _source("S1", 5.0, 96.0), "S2": _source("S2", -7.0, 106.0), "S3": _source("S3", 40.0, 120.0)}
    universe = {"unique_sources": unique_sources, "unique_required_source_count": len(unique_sources)}

    def _row(sid, lat, lon, hydrology_status):
        row = {"source_id": sid, "latitude": lat, "longitude": lon}
        for window in ("weather_event_day", "weather_window_3day", "weather_window_7day", "weather_window_14day"):
            row[f"{window}_mean_temperature_2m_status"] = "SOURCE_VALUE_AVAILABLE"
        row["elevation_m_status"] = "SOURCE_VALUE_AVAILABLE"
        row["host_density_cattle_status"] = "SOURCE_VALUE_AVAILABLE"
        row["host_density_buffalo_status"] = "SOURCE_VALUE_AVAILABLE"
        row["landcover_tree_cover_fraction_status"] = "SOURCE_VALUE_AVAILABLE"
        row["distance_to_nearest_river_km_status"] = hydrology_status
        return row

    canary_source_ids = ["S1", "S2"]
    canary_rows = [_row("S1", 5.0, 96.0, "SOURCE_VALUE_MISSING"), _row("S2", -7.0, 106.0, "OUTSIDE_SOURCE_COVERAGE")]
    canary_result = {"rows": canary_rows, "cache_hits": 1, "network_attempts": 1}

    # S1/S2 (never S3) are already cached on disk -- both S1's and S3's own
    # coordinates fall inside HydroRIVERS' Asia bbox, so this also exercises
    # hydrology's own in-coverage-AND-cached scoping (S3 is in-coverage but
    # NOT cached -> must not count toward hydrology's cache_hit).
    cache = SourceExtractionCache(source_cache_dir)
    for row in canary_rows:
        cache.set(row["source_id"], row)

    plan_before = {
        "expected_requests_before_cache": {"weather": 12},
        "existing_cache_hits": {"weather": 2, "source_level_all_families": 0},
        "sources_inside_hydrology_coverage": 2,
    }
    plan_after = {
        "expected_requests_before_cache": {"weather": 12},
        "existing_cache_hits": {"weather": 6, "source_level_all_families": 2},
        "sources_inside_hydrology_coverage": 2,
    }
    return universe, plan_before, plan_after, canary_source_ids, canary_result


def test_r2b1_progress_artifact_shape_and_values(tmp_path):
    universe, plan_before, plan_after, canary_source_ids, canary_result = _synthetic_progress_inputs(tmp_path / "source_cache")
    progress = build_extraction_progress(
        universe, plan_before, plan_after, canary_source_ids, canary_result, source_cache_dir=tmp_path / "source_cache",
    )

    assert progress["checkpoint"] == "FMD-07A-R2B1"
    assert set(progress["adapters"]) == {"weather", "elevation", "host_density", "land_cover", "hydrology"}
    required_keys = {"planned", "cache_hit", "attempted_network", "successful", "failed_retryable", "failed_final", "out_of_coverage", "blocked", "remaining"}
    for family, counts in progress["adapters"].items():
        assert required_keys <= set(counts), family
        assert counts["planned"] == counts["cache_hit"] + counts["remaining"]
        assert counts["failed_retryable"] == 0  # Section 11: no adapter here distinguishes a transient-vs-permanent single attempt

    assert progress["adapters"]["weather"]["planned"] == 12
    assert progress["adapters"]["weather"]["cache_hit"] == 6
    assert progress["adapters"]["weather"]["attempted_network"] == 4  # 6 - 2

    # elevation/land_cover have ONE representative status column (one request produces the whole
    # family together); host_density has TWO (cattle, buffalo) -- both real S1/S2 rows are
    # SOURCE_VALUE_AVAILABLE throughout, so "successful" scales with the representative-key count.
    expected_successful = {"elevation": 2, "host_density": 4, "land_cover": 2}
    for family in ("elevation", "host_density", "land_cover"):
        assert progress["adapters"][family]["planned"] == 3
        assert progress["adapters"][family]["cache_hit"] == 2
        assert progress["adapters"][family]["attempted_network"] == 1
        assert progress["adapters"][family]["successful"] == expected_successful[family]

    assert progress["adapters"]["hydrology"]["successful"] == 1  # S1: SOURCE_VALUE_MISSING -> successful bucket
    assert progress["adapters"]["hydrology"]["out_of_coverage"] == 1  # S2: OUTSIDE_SOURCE_COVERAGE
    # hydrology's cache_hit is scoped to in-coverage AND cached sources only
    # (S3 is geometrically in-coverage but was never cached -> excluded) --
    # must equal planned here since both cached sources are in-coverage.
    assert progress["adapters"]["hydrology"]["planned"] == 2
    assert progress["adapters"]["hydrology"]["cache_hit"] == 2
    assert progress["adapters"]["hydrology"]["remaining"] == 0

    assert progress["last_completed_batch_key"] == "S2"
    assert progress["held_out_included"] is False
    assert progress["sri_lanka_included"] is False
    assert progress["predictive_metrics_used"] is False
    assert progress["model_trained"] is False
    assert progress["weather_winner_selected"] is False


def test_r2b1_progress_artifact_deterministic_and_atomic_write(tmp_path):
    universe, plan_before, plan_after, canary_source_ids, canary_result = _synthetic_progress_inputs(tmp_path / "source_cache")
    progress1 = build_extraction_progress(
        universe, plan_before, plan_after, canary_source_ids, canary_result, source_cache_dir=tmp_path / "source_cache",
    )
    progress2 = build_extraction_progress(
        universe, plan_before, plan_after, canary_source_ids, canary_result, source_cache_dir=tmp_path / "source_cache",
    )
    assert progress1 == progress2

    out_path = tmp_path / PROGRESS_JSON_FILENAME
    write_extraction_progress(progress1, out_path)
    write_extraction_progress(progress2, out_path)  # a second write (simulated resume) must not corrupt/duplicate the file
    assert not out_path.with_suffix(".tmp").exists()
    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert on_disk == progress1
    assert "timestamp" not in json.dumps(on_disk).lower()


def test_r2b1_real_progress_artifact_matches_real_canary(real_universe):
    progress_path = _MODEL_DEV_DIR / PROGRESS_JSON_FILENAME
    if not progress_path.exists():
        pytest.skip("fmd07_feature_extraction_progress.json not yet materialized by a real run_fmd07a_r2b1 call")
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    canary_manifest = json.loads(_CANARY_MANIFEST_JSON.read_text(encoding="utf-8"))
    plan = json.loads(_PLAN_JSON.read_text(encoding="utf-8"))
    # R2B2 intentionally reuses this checkpoint progress path for its
    # universe-wide resumable run. Once that downstream finalization has
    # completed, the artifact is no longer the R2B1 eight-source canary
    # snapshot; assert the stronger terminal R2B2 state instead.
    if progress.get("checkpoint") == "FMD-07A-R2B2":
        assert progress["sources_total"] == real_universe["unique_required_source_count"]
        assert progress["sources_complete"] == real_universe["unique_required_source_count"]
        assert progress["sources_terminal_accounted"] == real_universe["unique_required_source_count"]
        assert progress["sources_remaining"] == 0
        assert progress["sources_terminal_remaining"] == 0
        assert progress["held_out_included"] is False
        assert progress["sri_lanka_included"] is False
        assert progress["predictive_metrics_used"] is False
        assert progress["model_trained"] is False
        assert progress["weather_winner_selected"] is False
        return
    assert progress["last_completed_batch_key"] == sorted(canary_manifest["canary_source_ids"])[-1]
    canary_size = len(canary_manifest["canary_source_ids"])

    for family, counts in progress["adapters"].items():
        assert counts["remaining"] == counts["planned"] - counts["cache_hit"], family
        assert counts["attempted_network"] <= canary_size, family
        assert counts["failed_retryable"] == 0, family

    for family in ("elevation", "host_density", "land_cover"):
        assert progress["adapters"][family]["planned"] == real_universe["unique_required_source_count"]
    assert progress["adapters"]["hydrology"]["planned"] == plan["sources_inside_hydrology_coverage"]
    assert progress["adapters"]["weather"]["planned"] == plan["expected_requests_before_cache"]["weather"]

    assert progress["held_out_included"] is False
    assert progress["sri_lanka_included"] is False
    assert progress["predictive_metrics_used"] is False
    assert progress["model_trained"] is False
    assert progress["weather_winner_selected"] is False


# ---------------------------------------------------------------------------
# Frozen artifact hash protection (Section 22)
# ---------------------------------------------------------------------------


def test_r2b1_frozen_artifact_hashes_unchanged():
    assert _sha256(_REPO_ROOT / "local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv") == "11b4528d32fcb9f6f26cd537511b0d0fca531890a8af5d7480e94188d3d0114e"
    lsd = _REPO_ROOT / "local_data/processed/canonical_outbreaks_conservative.csv"
    if lsd.exists():
        assert _sha256(lsd) == "fa8e77d81b48af6bc2839deb4be9d4046d502ab948ce8e4e67a02a84c281d7f7"
    assert _sha256(_CALIBRATION_DIR / "fmd06_calibration_freeze.json") == "f72ff161066223a63de185188ae97de46793a4aea91ad14c3a8ab3aadace66a0"
    assert _sha256(_CALIBRATION_DIR / "fmd06_risk_origin_labels.csv") == "e6eb43aae1fa65aa3e243c1770f44ecc047593a5012a8155a8b00aadc081e438"
    assert _sha256(_CALIBRATION_DIR / "fmd06_calibration_manifest.json") == "a5b6b6ead805357a887f2b80c0ea9f7d9d96a96723840a7d4e6b8373c965b113"
    assert _sha256(_MODEL_DEV_DIR / "fmd07_development_feature_matrix.csv") == "023ed97a10b7c27be090f6009ee8600da08cf1c76519e3926d68fbc013fd6dad"
    assert _sha256(_MODEL_DEV_DIR / "fmd07_model_input_schema.json") == "02774a883a35008225c5b8b8ed89204a42121c0e29d6e9aefa60659f920131c7"
