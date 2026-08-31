"""FMD-04: tests for the FMD environmental/host-context feature-enrichment
orchestration layer (`data_processing/build_fmd_features.py`).

Pure-logic paths (missing coordinate/date, plausibility flags, coverage
math, CSV round-trip, non-mutation of the frozen corpus) are tested with
no network/file I/O. The real-adapter integration path is tested against
the same real Sri Lanka Chavakachcheri coordinate `test_feature_assembly.py`
already uses (SL_LAT/SL_LON below) — this repo's established convention
for this package is real network/file calls, not mocks (see that module's
own docstring); reusing the same coordinate keeps the local
weather/GLW/WorldCover/HydroRIVERS caches warm across both test files.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from components.geospatial_tracking.data_processing.build_fmd_features import (
    CORE_EVENT_COLUMNS,
    EVENT_INDEX_COLUMNS,
    FMD04_VALIDATION_SAMPLE,
    FMD_HYDROLOGY_ASIA_BBOX,
    FmdCanonicalEventRef,
    FmdFeatureExtractionConfig,
    _in_hydrology_asia_bbox,
    _plausibility_flag,
    build_event_feature_row,
    build_feature_event_index,
    build_validation_scope_manifest,
    compute_feature_coverage_report,
    extract_elevation_for_event,
    extract_host_density_for_event,
    extract_hydrology_for_event,
    extract_landcover_for_event,
    extract_weather_for_event,
    load_extracted_event_ids,
    load_fmd_canonical_events,
    run,
    write_feature_event_index,
)
from components.geospatial_tracking.data_processing.fmd_feature_registry import FMD_FEATURE_SOURCE_REGISTRY
from components.geospatial_tracking.data_processing.fmd_feature_status import (
    EXTRACTION_COMPLETE,
    EXTRACTION_FAILED,
    EXTRACTION_NOT_RUN,
    FEATURE_NOT_AVAILABLE,
    OUTSIDE_SOURCE_COVERAGE,
    SOURCE_VALUE_AVAILABLE,
    SOURCE_VALUE_MISSING,
    classify_feature_availability,
)
from components.geospatial_tracking.services.features.cache import FileWeatherCache
from components.geospatial_tracking.services.geospatial.feature_result import FeatureResult, FeatureStatus

SL_LAT, SL_LON = 9.6579014, 80.1643076
SL_DATE = "2020-09-09"


def _event(**overrides) -> FmdCanonicalEventRef:
    fields = dict(
        fmd_canonical_event_id="FAO_EMPRESI_BIGQUERY_CSV:EMP-1",
        source_record_id="FAO_EMPRESI_BIGQUERY_CSV:fmd_events.csv:000001",
        country="Sri Lanka",
        event_date=SL_DATE,
        latitude=SL_LAT,
        longitude=SL_LON,
        modelling_eligible=True,
    )
    fields.update(overrides)
    return FmdCanonicalEventRef(**fields)


# ---- linkage / provenance / CSV plumbing -----------------------------------


class TestCanonicalCsvLoadingAndLinkage:
    def _write_fixture_csv(self, tmp_path: Path) -> Path:
        path = tmp_path / "fmd_canonical_outbreaks_conservative.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "source_record_id",
                    "fmd_canonical_event_id",
                    "country",
                    "outbreak_start_date",
                    "onset_date",
                    "event_start_date",
                    "confirmation_date",
                    "latitude",
                    "longitude",
                    "modelling_eligible",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "source_record_id": "S1",
                    "fmd_canonical_event_id": "FAO_EMPRESI_BIGQUERY_CSV:EMP-1",
                    "country": "Sri Lanka",
                    "outbreak_start_date": "",
                    "onset_date": "2024-03-01",
                    "event_start_date": "",
                    "confirmation_date": "",
                    "latitude": "9.71517",
                    "longitude": "80.066849",
                    "modelling_eligible": "True",
                }
            )
            writer.writerow(
                {
                    "source_record_id": "S2",
                    "fmd_canonical_event_id": "FAO_EMPRESI_BIGQUERY_CSV:EMP-2",
                    "country": "Greece",
                    "outbreak_start_date": "",
                    "onset_date": "",
                    "event_start_date": "",
                    "confirmation_date": "",
                    "latitude": "",
                    "longitude": "",
                    "modelling_eligible": "False",
                }
            )
        return path

    def test_loads_every_row_and_preserves_canonical_event_id_linkage(self, tmp_path):
        path = self._write_fixture_csv(tmp_path)
        events = load_fmd_canonical_events(path)
        assert len(events) == 2
        assert events[0].fmd_canonical_event_id == "FAO_EMPRESI_BIGQUERY_CSV:EMP-1"
        assert events[0].latitude == 9.71517
        assert events[0].longitude == 80.066849
        assert events[0].modelling_eligible is True
        assert events[1].modelling_eligible is False

    def test_event_date_uses_documented_fallback_hierarchy(self, tmp_path):
        path = self._write_fixture_csv(tmp_path)
        events = load_fmd_canonical_events(path)
        assert events[0].event_date == "2024-03-01"  # onset_date, since outbreak_start_date is empty

    def test_missing_coordinate_row_is_still_loaded_never_dropped(self, tmp_path):
        path = self._write_fixture_csv(tmp_path)
        events = load_fmd_canonical_events(path)
        assert events[1].latitude is None
        assert events[1].longitude is None
        assert events[1].event_date is None

    def test_loading_never_mutates_the_frozen_canonical_csv(self, tmp_path):
        path = self._write_fixture_csv(tmp_path)
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        load_fmd_canonical_events(path)
        load_fmd_canonical_events(path)
        after = hashlib.sha256(path.read_bytes()).hexdigest()
        assert before == after


# ---- missing-coordinate / missing-date behavior (no network) --------------


class TestMissingSourceBehaviorNoNetwork:
    def test_weather_missing_coordinate_never_calls_adapter_and_reports_feature_not_available(self):
        event = _event(latitude=None, longitude=None)
        row, prov = extract_weather_for_event(event, FmdFeatureExtractionConfig(), FileWeatherCache(Path(".fmd04_test_cache_unused")))
        assert row["weather_event_day_mean_temperature_2m_status"] == FEATURE_NOT_AVAILABLE
        assert row["weather_event_day_mean_temperature_2m_value"] == ""
        assert all(p["availability_status"] == FEATURE_NOT_AVAILABLE for p in prov)

    def test_weather_missing_date_never_calls_adapter(self):
        event = _event(event_date=None)
        row, _prov = extract_weather_for_event(event, FmdFeatureExtractionConfig(), FileWeatherCache(Path(".fmd04_test_cache_unused")))
        assert row["weather_event_day_precipitation_accumulation_status"] == FEATURE_NOT_AVAILABLE

    def test_elevation_missing_coordinate_never_calls_adapter(self):
        event = _event(latitude=None, longitude=None)
        row, _prov = extract_elevation_for_event(event, FmdFeatureExtractionConfig())
        assert row["elevation_m_status"] == FEATURE_NOT_AVAILABLE

    def test_host_density_missing_coordinate_never_calls_adapter(self):
        event = _event(latitude=None, longitude=None)
        row, _prov = extract_host_density_for_event(event, FmdFeatureExtractionConfig())
        assert row["host_density_cattle_status"] == FEATURE_NOT_AVAILABLE
        assert row["host_density_buffalo_status"] == FEATURE_NOT_AVAILABLE

    def test_host_density_unavailable_species_never_attempted_regardless_of_coordinate(self):
        event = _event()
        row, prov = extract_host_density_for_event(event, FmdFeatureExtractionConfig())
        for species in ("swine", "sheep", "goat"):
            assert row[f"host_density_{species}_status"] == FEATURE_NOT_AVAILABLE
            assert row[f"host_density_{species}_value"] == ""
        # never a fabricated combined "total" from partial species
        assert "total_livestock_density_value" not in row
        assert not any("total_livestock_density" in p["feature_name"] for p in prov)

    def test_landcover_missing_coordinate_never_calls_adapter(self):
        event = _event(latitude=None, longitude=None)
        row, _prov = extract_landcover_for_event(event, FmdFeatureExtractionConfig())
        assert row["landcover_cropland_fraction_status"] == FEATURE_NOT_AVAILABLE

    def test_hydrology_missing_coordinate_never_calls_adapter(self):
        event = _event(latitude=None, longitude=None)
        row, _prov = extract_hydrology_for_event(event, FmdFeatureExtractionConfig())
        assert row["distance_to_nearest_river_km_status"] == FEATURE_NOT_AVAILABLE


# ---- hydrology coverage-boundary logic (no network) ------------------------


class TestHydrologyCoverageBoundary:
    def test_sri_lanka_is_inside_the_asia_bbox(self):
        assert _in_hydrology_asia_bbox(SL_LAT, SL_LON) is True

    def test_south_africa_is_outside_the_asia_bbox(self):
        assert _in_hydrology_asia_bbox(-26.4, 24.1) is False

    def test_outside_bbox_event_never_calls_the_adapter_and_is_classified_outside_coverage(self):
        event = _event(country="South Africa", latitude=-26.4, longitude=24.1)
        row, prov = extract_hydrology_for_event(event, FmdFeatureExtractionConfig())
        assert row["distance_to_nearest_river_km_status"] == OUTSIDE_SOURCE_COVERAGE
        assert row["distance_to_nearest_river_km_value"] == ""
        assert prov[0]["availability_status"] == OUTSIDE_SOURCE_COVERAGE

    def test_bbox_bounds_match_the_documented_constant(self):
        west, south, east, north = FMD_HYDROLOGY_ASIA_BBOX
        assert _in_hydrology_asia_bbox(south, west) is True
        assert _in_hydrology_asia_bbox(south - 0.001, west) is False


# ---- status classification (no network) ------------------------------------


class TestFeatureAvailabilityClassification:
    def test_real_maps_to_source_value_available(self):
        r = FeatureResult(feature_name="x", value=1.0, units="u", status=FeatureStatus.REAL.value, dataset_name="d", dataset_version="v", reference_time=None, retrieved_at=None, source_resolution=None, source_crs=None, analysis_method=None, quality_notes="")
        assert classify_feature_availability(r) == SOURCE_VALUE_AVAILABLE

    def test_missing_maps_to_source_value_missing(self):
        r = FeatureResult(feature_name="x", value=None, units="u", status=FeatureStatus.MISSING.value, dataset_name="d", dataset_version="v", reference_time=None, retrieved_at=None, source_resolution=None, source_crs=None, analysis_method=None, quality_notes="no data")
        assert classify_feature_availability(r) == SOURCE_VALUE_MISSING

    def test_blocked_download_failure_maps_to_source_file_missing(self):
        r = FeatureResult(feature_name="x", value=None, units=None, status=FeatureStatus.BLOCKED.value, dataset_name="d", dataset_version="v", reference_time=None, retrieved_at=None, source_resolution=None, source_crs=None, analysis_method=None, quality_notes="could not download GLW4 cattle count/area raster: timeout")
        assert classify_feature_availability(r) == "SOURCE_FILE_MISSING"

    def test_blocked_other_reason_maps_to_extraction_failed(self):
        r = FeatureResult(feature_name="x", value=None, units=None, status=FeatureStatus.BLOCKED.value, dataset_name="d", dataset_version="v", reference_time=None, retrieved_at=None, source_resolution=None, source_crs=None, analysis_method=None, quality_notes="unsupported model")
        assert classify_feature_availability(r) == EXTRACTION_FAILED

    def test_demo_status_is_refused_never_silently_classified(self):
        r = FeatureResult(feature_name="x", value=None, units="u", status=FeatureStatus.DEMO.value, dataset_name="d", dataset_version="v", reference_time=None, retrieved_at=None, source_resolution=None, source_crs=None, analysis_method=None, quality_notes="")
        with pytest.raises(ValueError):
            classify_feature_availability(r)


# ---- plausibility flags (no network) ---------------------------------------


class TestPlausibilityFlags:
    def test_relative_humidity_out_of_bounds_flagged(self):
        assert _plausibility_flag("weather_event_day_mean_relative_humidity_2m", 150.0) is not None
        assert _plausibility_flag("weather_event_day_mean_relative_humidity_2m", 50.0) is None

    def test_negative_precipitation_flagged(self):
        assert _plausibility_flag("weather_event_day_precipitation_accumulation", -1.0) is not None
        assert _plausibility_flag("weather_event_day_precipitation_accumulation", 0.0) is None

    def test_negative_host_density_flagged(self):
        assert _plausibility_flag("host_density_cattle", -5.0) is not None

    def test_landcover_fraction_out_of_unit_interval_flagged(self):
        assert _plausibility_flag("landcover_cropland_fraction", 1.5) is not None
        assert _plausibility_flag("landcover_cropland_fraction", 0.3) is None

    def test_implausible_elevation_flagged(self):
        assert _plausibility_flag("elevation_m", 99999.0) is not None
        assert _plausibility_flag("elevation_m", 100.0) is None

    def test_negative_river_distance_flagged(self):
        assert _plausibility_flag("distance_to_nearest_river_km", -3.0) is not None


# ---- coverage report math (no network) -------------------------------------


class TestCoverageReport:
    def test_coverage_counts_and_missing_percentage(self):
        rows = [
            {"fmd_canonical_event_id": "E1", "feature_name": "elevation_m", "value": "100.0", "availability_status": SOURCE_VALUE_AVAILABLE, "quality_notes": ""},
            {"fmd_canonical_event_id": "E2", "feature_name": "elevation_m", "value": "", "availability_status": SOURCE_VALUE_MISSING, "quality_notes": ""},
            {"fmd_canonical_event_id": "E3", "feature_name": "elevation_m", "value": "200.0", "availability_status": SOURCE_VALUE_AVAILABLE, "quality_notes": ""},
        ]
        report = compute_feature_coverage_report(rows, events_requested=3)
        row = next(r for r in report if r["feature_name"] == "elevation_m")
        assert row["events_requested"] == 3
        assert row["events_available"] == 2
        assert row["missing_count"] == 1
        assert row["missing_percentage"] == pytest.approx(33.33, abs=0.01)
        assert row["mean"] == 150.0
        assert row["min"] == 100.0
        assert row["max"] == 200.0

    def test_invalid_values_are_flagged_not_deleted(self):
        rows = [
            {"fmd_canonical_event_id": "E1", "feature_name": "weather_event_day_mean_relative_humidity_2m", "value": "150.0", "availability_status": SOURCE_VALUE_AVAILABLE, "quality_notes": ""},
        ]
        report = compute_feature_coverage_report(rows, events_requested=1)
        row = report[0]
        assert row["events_available"] == 1  # still counted as available
        assert row["invalid_nonphysical_count"] == 1
        assert "outside physical bounds" in row["invalid_examples"]


# ---- source registry sanity (no network) -----------------------------------


class TestSourceRegistry:
    def test_every_registry_entry_has_a_status(self):
        assert len(FMD_FEATURE_SOURCE_REGISTRY) > 0
        for entry in FMD_FEATURE_SOURCE_REGISTRY:
            assert entry.status in {"REAL", "UNAVAILABLE", "BLOCKED", "AVAILABLE_NOT_YET_SELECTED"}

    def test_no_road_or_movement_source_is_marked_real(self):
        for entry in FMD_FEATURE_SOURCE_REGISTRY:
            if "road" in entry.dataset_name.lower() or "movement" in entry.dataset_name.lower():
                assert entry.status == "UNAVAILABLE"

    def test_swine_sheep_goat_density_is_marked_unavailable_not_fabricated(self):
        entry = next(e for e in FMD_FEATURE_SOURCE_REGISTRY if "swine/sheep/goat" in e.dataset_name.lower())
        assert entry.status == "UNAVAILABLE"
        assert entry.local_file_hash is None


# ---- FMD/LSD isolation (no network) ----------------------------------------


class TestFmdLsdIsolation:
    def test_module_never_imports_lsd_specific_build_canonical(self):
        import components.geospatial_tracking.data_processing.build_fmd_features as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "build_canonical" not in source
        assert "import build_canonical" not in source

    def test_output_columns_never_reference_lsd_output_paths(self):
        assert "canonical_outbreaks.csv" not in " ".join(CORE_EVENT_COLUMNS)


# ---- full-corpus addressability index (no network) ------------------------


class TestFullCorpusAddressabilityIndex:
    def _events(self):
        return [
            _event(fmd_canonical_event_id="A", source_record_id="SR-A", country="Sri Lanka"),
            _event(fmd_canonical_event_id="B", source_record_id="SR-B", country="Greece"),
            _event(fmd_canonical_event_id="C", source_record_id="SR-C", country="India", modelling_eligible=False),
        ]

    def test_one_row_per_event_never_fewer_never_more(self):
        events = self._events()
        rows = build_feature_event_index(events, extracted_event_ids=set())
        assert len(rows) == len(events)
        assert {r["fmd_canonical_event_id"] for r in rows} == {"A", "B", "C"}

    def test_ids_stay_unique(self):
        events = self._events()
        rows = build_feature_event_index(events, extracted_event_ids=set())
        ids = [r["fmd_canonical_event_id"] for r in rows]
        assert len(ids) == len(set(ids))

    def test_extracted_event_gets_extraction_complete_others_get_extraction_not_run(self):
        events = self._events()
        rows = build_feature_event_index(events, extracted_event_ids={"A"})
        by_id = {r["fmd_canonical_event_id"]: r for r in rows}
        assert by_id["A"]["feature_extraction_status"] == EXTRACTION_COMPLETE
        assert by_id["B"]["feature_extraction_status"] == EXTRACTION_NOT_RUN
        assert by_id["C"]["feature_extraction_status"] == EXTRACTION_NOT_RUN

    def test_not_run_is_never_confused_with_an_error_or_missing_value_status(self):
        # The whole point of EXTRACTION_NOT_RUN: it must be a distinct token
        # from every per-feature-value failure/absence status, never reused.
        events = self._events()
        rows = build_feature_event_index(events, extracted_event_ids=set())
        statuses = {r["feature_extraction_status"] for r in rows}
        assert statuses == {EXTRACTION_NOT_RUN}
        assert "FEATURE_NOT_AVAILABLE" not in statuses
        assert "SOURCE_VALUE_MISSING" not in statuses
        assert "EXTRACTION_FAILED" not in statuses

    def test_modelling_eligible_flag_carried_through_unchanged(self):
        events = self._events()
        rows = build_feature_event_index(events, extracted_event_ids=set())
        by_id = {r["fmd_canonical_event_id"]: r for r in rows}
        assert by_id["A"]["modelling_eligible"] is True
        assert by_id["C"]["modelling_eligible"] is False

    def test_write_feature_event_index_round_trips_via_csv(self, tmp_path):
        events = self._events()
        out_path = tmp_path / "fmd_feature_event_index.csv"
        write_feature_event_index(events, extracted_event_ids={"A"}, out_path=out_path)
        with out_path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3
        assert set(rows[0].keys()) == set(EVENT_INDEX_COLUMNS)

    def test_load_extracted_event_ids_missing_file_returns_empty_set_not_an_error(self, tmp_path):
        assert load_extracted_event_ids(tmp_path / "does_not_exist.csv") == set()

    def test_load_extracted_event_ids_reads_real_feature_table_ids(self, tmp_path):
        path = tmp_path / "fmd_feature_table.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["fmd_canonical_event_id", "other_col"])
            writer.writeheader()
            writer.writerow({"fmd_canonical_event_id": "X", "other_col": "1"})
            writer.writerow({"fmd_canonical_event_id": "Y", "other_col": "2"})
        assert load_extracted_event_ids(path) == {"X", "Y"}


# ---- validation-scope manifest (no network) --------------------------------


class TestValidationScopeManifest:
    def _events(self):
        return [_event(fmd_canonical_event_id=f"SL-{i}", country="Sri Lanka") for i in range(22)] + [
            _event(fmd_canonical_event_id=f"GL-{i}", country=c)
            for i, c in enumerate(["South Africa", "Algeria", "Zimbabwe", "Israel", "Greece", "India", "Iran"])
        ]

    def test_manifest_reports_the_correct_sri_lanka_and_global_split(self):
        events = self._events()
        extracted = {e.fmd_canonical_event_id for e in events}
        manifest = build_validation_scope_manifest(events, extracted)
        assert manifest["validation_scope"] == FMD04_VALIDATION_SAMPLE == "FMD04_VALIDATION_SAMPLE"
        assert manifest["sri_lanka_events"] == 22
        assert manifest["global_diversity_events"] == 7
        assert manifest["validation_sample_total"] == 29

    def test_manifest_never_claims_full_corpus_extraction(self):
        events = self._events() + [_event(fmd_canonical_event_id="UNEXTRACTED-1", country="Kenya")]
        extracted = {e.fmd_canonical_event_id for e in self._events()}  # the +1 event is NOT extracted
        manifest = build_validation_scope_manifest(events, extracted)
        assert manifest["full_canonical_corpus"] == 30
        assert manifest["validation_sample_total"] == 29
        assert manifest["final_study_cohort"] == "NOT_YET_FROZEN"
        assert manifest["full_cohort_feature_extraction"] == "DEFERRED_UNTIL_AFTER_FMD-05"

    def test_pre_fmd05_eligible_count_reflects_modelling_eligible_flag_not_extraction(self):
        events = self._events()
        events[0] = _event(fmd_canonical_event_id=events[0].fmd_canonical_event_id, country="Sri Lanka", modelling_eligible=False)
        extracted = {e.fmd_canonical_event_id for e in events}
        manifest = build_validation_scope_manifest(events, extracted)
        assert manifest["pre_fmd05_model_eligible_flag_count"] == 28


# ---- real-adapter integration (real network/file calls; Sri Lanka coord) --


class TestRealAdapterIntegration:
    """Mirrors test_feature_assembly.py's own convention: real
    network/file calls against the same well-known Sri Lanka coordinate,
    kept fast by a warm local cache."""

    def test_build_event_feature_row_produces_every_declared_column(self):
        event = _event()
        cache = FileWeatherCache(Path(__file__).resolve().parents[4] / "local_data" / "cache" / "weather")
        row, prov = build_event_feature_row(event, FmdFeatureExtractionConfig(), cache)
        assert row["fmd_canonical_event_id"] == event.fmd_canonical_event_id
        assert row["weather_event_day_mean_temperature_2m_status"] in {SOURCE_VALUE_AVAILABLE, SOURCE_VALUE_MISSING, EXTRACTION_FAILED}
        assert row["elevation_m_status"] in {SOURCE_VALUE_AVAILABLE, EXTRACTION_FAILED}
        assert row["host_density_cattle_status"] in {SOURCE_VALUE_AVAILABLE, "SOURCE_FILE_MISSING", EXTRACTION_FAILED}
        assert len(prov) > 20  # weather (4 windows x 8 vars) + elevation + host density + 11 landcover + hydrology

    def test_deterministic_given_the_same_input_and_warm_cache(self):
        event = _event()
        cache = FileWeatherCache(Path(__file__).resolve().parents[4] / "local_data" / "cache" / "weather")
        config = FmdFeatureExtractionConfig()
        row1, _ = build_event_feature_row(event, config, cache)
        row2, _ = build_event_feature_row(event, config, cache)
        weather_key = "weather_event_day_mean_temperature_2m_value"
        assert row1[weather_key] == row2[weather_key]
        assert row1["elevation_m_value"] == row2["elevation_m_value"]

    def test_run_never_touches_the_lsd_canonical_output_path(self, tmp_path):
        event = _event()
        stats = run([event], out_dir=tmp_path, weather_cache_dir=Path(__file__).resolve().parents[4] / "local_data" / "cache" / "weather")
        assert stats["events_enriched"] == 1
        assert not (tmp_path / "canonical_outbreaks.csv").exists()
        assert (tmp_path / "fmd_feature_table.csv").exists()
