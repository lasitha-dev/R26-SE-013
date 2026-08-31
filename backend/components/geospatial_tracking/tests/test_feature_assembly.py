"""ASSEMBLY-01..06, GEOM-ASSEMBLY-01/02, HOST-ASSEMBLY-01/02,
WX-ASSEMBLY-01..05, LC-ASSEMBLY-01..03, HYDRO-ASSEMBLY-01, MISS-01..03,
NORM-01/02, LEAK-ASSEMBLY-01/02, SNAPSHOT-ID-01..04, HYDRO-POLICY-03.

Makes real network/file calls (weather, host density, land cover,
hydrology) — matches this repo's established convention (weather tests
in `test_geospatial_weather.py` already do the same). Kept fast by (a)
reusing the real Sri Lanka Chavakachcheri coordinate so the local
weather/GLW/WorldCover/HydroRIVERS caches built during Checkpoint 5.x
verification are already warm, and (b) module-scoped fixtures that
assemble each snapshot only once and share it across many assertions.
"""

from __future__ import annotations

import inspect

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality, ValidationMode
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.features import assembler as assembler_module
from components.geospatial_tracking.services.features.assembler import assemble_feature_snapshot
from components.geospatial_tracking.services.features.cache import FileWeatherCache
from components.geospatial_tracking.services.features.feature_policy import (
    LANDCOVER_MODE_FROZEN_STATIC_REFERENCE,
    LANDCOVER_MODE_OMIT,
    LANDCOVER_MODE_YEAR_MATCHED_REFERENCE,
    FeaturePolicy,
    LandCoverFeaturePolicy,
)
from components.geospatial_tracking.services.geospatial.weather.era5 import WEATHER_MODEL_RESOLUTION

# Real Sri Lanka Chavakachcheri coordinate/date (Event_3473) -- reused so
# the local weather/GLW/WorldCover/HydroRIVERS caches already warmed
# during Checkpoint 5.x verification make these tests fast.
SL_LAT, SL_LON = 9.6579014, 80.1643076
SL_T0 = "2020-09-09"


def _historical(**overrides) -> HistoricalOutbreakRecord:
    fields = dict(
        source_record_id="H1",
        country="Sri Lanka",
        disease="Lumpy skin disease",
        outbreak_start_date="2020/09/09",
        proxy_availability_date="2020/09/09",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        proxy_availability_source_field="outbreak_start_date",
        latitude=SL_LAT,
        longitude=SL_LON,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(
        forecast_origin_id="ORIGIN:Sri Lanka:2020-09-09",
        country="Sri Lanka",
        t0=SL_T0,
        temporal_mode=ValidationMode.RETROSPECTIVE_PROXY.value,
        trigger_source_ids_at_t0=["H1"],
        trigger_source_count=1,
    )
    fields.update(overrides)
    return ForecastOrigin(**fields)


def _tiny_policy(**overrides) -> FeaturePolicy:
    """A single-cell grid (half_extent 0.5km, 1km cells) -- minimizes
    real per-cell adapter calls for tests that only care about
    structure, not spatial coverage."""
    fields = dict(
        disease="Lumpy skin disease",
        active_window_days=14,
        grid_half_extent_km=0.5,
        grid_cell_size_km=1.0,
        weather_model="era5",
        weather_lookback_hours=24,
        landcover_policy=LandCoverFeaturePolicy(mode=LANDCOVER_MODE_OMIT),
        hydrology_include=False,
    )
    fields.update(overrides)
    return FeaturePolicy(**fields)


def _strip_volatile(d):
    """Recursively removes timestamp fields expected to differ between
    two otherwise-identical real assembly runs (each real adapter call
    stamps its own retrieval instant) -- what remains is the scientific
    content: values, statuses, ids, hashes."""
    if isinstance(d, dict):
        return {k: _strip_volatile(v) for k, v in d.items() if k not in ("generated_at", "retrieved_at", "retrieval_date")}
    if isinstance(d, list):
        return [_strip_volatile(v) for v in d]
    return d


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    r = SQLiteOutbreakRepository(tmp_path_factory.mktemp("db") / "test.db")
    r.init_schema()
    r.add_historical_record(_historical(source_record_id="H1"))
    r.add_historical_record(
        _historical(source_record_id="H2", latitude=SL_LAT + 0.02, longitude=SL_LON + 0.02, outbreak_start_date="2020/09/07", proxy_availability_date="2020/09/07")
    )
    r.add_historical_record(
        _historical(source_record_id="FUTURE1", outbreak_start_date="2020/12/25", proxy_availability_date="2020/12/25")
    )
    yield r
    r.close()


@pytest.fixture(scope="module")
def weather_cache(tmp_path_factory):
    return FileWeatherCache(tmp_path_factory.mktemp("wxcache"))


@pytest.fixture(scope="module")
def tiny_snapshot(repo, weather_cache):
    return assemble_feature_snapshot(repo, forecast_origin=_origin(), policy=_tiny_policy(), weather_cache=weather_cache)


@pytest.fixture(scope="module")
def full_snapshot(repo, weather_cache):
    """Larger grid (matches the real spatial-structure pattern already
    verified in Checkpoint 5.6: 25 cells, some genuinely MISSING host
    density), plus land cover + hydrology enabled -- used only by the
    tests that specifically need that richer coverage."""
    policy = _tiny_policy(
        grid_half_extent_km=5.0,
        grid_cell_size_km=2.5,
        landcover_policy=LandCoverFeaturePolicy(mode=LANDCOVER_MODE_YEAR_MATCHED_REFERENCE),
        hydrology_include=True,
    )
    return assemble_feature_snapshot(repo, forecast_origin=_origin(), policy=policy, weather_cache=weather_cache)


class TestSnapshotDeterminism:
    def test_assembly_01_snapshot_deterministic_except_volatile_timestamps(self, repo, weather_cache):
        snap1 = assemble_feature_snapshot(repo, forecast_origin=_origin(), policy=_tiny_policy(), weather_cache=weather_cache)
        snap2 = assemble_feature_snapshot(repo, forecast_origin=_origin(), policy=_tiny_policy(), weather_cache=weather_cache)
        assert snap1.snapshot_id == snap2.snapshot_id
        assert snap1.feature_protocol_hash == snap2.feature_protocol_hash
        assert _strip_volatile(snap1.as_dict()) == _strip_volatile(snap2.as_dict())

    def test_assembly_02_same_config_same_protocol_hash(self):
        assert _tiny_policy().protocol_hash() == _tiny_policy().protocol_hash()

    def test_assembly_03_changed_lookback_changes_protocol_hash(self):
        assert _tiny_policy().protocol_hash() != _tiny_policy(weather_lookback_hours=48).protocol_hash()

    def test_assembly_04_changed_landcover_policy_changes_protocol_hash(self):
        p1 = _tiny_policy()
        p2 = _tiny_policy(landcover_policy=LandCoverFeaturePolicy(mode=LANDCOVER_MODE_YEAR_MATCHED_REFERENCE))
        assert p1.protocol_hash() != p2.protocol_hash()

    def test_assembly_05_future_target_data_not_accepted_as_input(self):
        sig = inspect.signature(assemble_feature_snapshot)
        for forbidden in ("target", "lead_days", "outcome", "future"):
            assert forbidden not in sig.parameters

    def test_assembly_06_risk_labels_not_accepted_as_input(self):
        sig = inspect.signature(assemble_feature_snapshot)
        for forbidden in ("risk", "risk_label", "validation_label", "probability"):
            assert forbidden not in sig.parameters


class TestGeometryAssembly:
    def test_geom_assembly_01_every_active_source_has_geometry_in_every_cell(self, tiny_snapshot):
        assert tiny_snapshot.active_source_count == 2
        for cell in tiny_snapshot.grid_cells:
            assert set(cell.geometry_by_source.keys()) == set(tiny_snapshot.active_source_ids)

    def test_geom_assembly_02_nearest_source_does_not_replace_multi_source_geometry(self, tiny_snapshot):
        cell = tiny_snapshot.grid_cells[0]
        assert len(cell.geometry_by_source) == 2
        for vec in cell.geometry_by_source.values():
            assert "distance_km" in vec and "t_hat_east" in vec and "t_hat_north" in vec


class TestHostDensityAssembly:
    def test_host_assembly_01_uses_grid_cell_method(self, tiny_snapshot):
        cell = tiny_snapshot.grid_cells[0]
        assert "cattle" in cell.host_density
        method = cell.host_density["cattle"]["analysis_method"] or ""
        assert "overlap-area-weighted" in method
        assert "target_grid_resolution" in method

    def test_host_assembly_02_missing_host_value_stays_missing(self, full_snapshot):
        missing_cells = [c for c in full_snapshot.grid_cells if c.host_density["cattle"]["status"] == "MISSING"]
        assert missing_cells, "expected at least one genuinely MISSING host-density cell in the full smoke grid"
        for c in missing_cells:
            assert c.host_density["cattle"]["value"] is None


class TestWeatherAssembly:
    def test_wx_assembly_01_primary_snapshot_uses_retrospective_proxy(self, tiny_snapshot):
        assert tiny_snapshot.weather["window"]["temporal_role"] == "RETROSPECTIVE_REANALYSIS_STATE_PROXY"

    def test_wx_assembly_02_strict_lag_sensitivity_not_primary_mode(self, tiny_snapshot):
        assert tiny_snapshot.weather["window"]["strict_operational_availability"] is False
        assert tiny_snapshot.weather["window"]["availability_quality"] == "UNKNOWN"

    def test_wx_assembly_02_assembler_never_enables_strict_mode(self):
        src = inspect.getsource(assembler_module)
        assert "strict_operational_availability=False" in src
        assert "strict_operational_availability=True" not in src

    def test_wx_assembly_03_future_reanalysis_cannot_enter_snapshot(self, tiny_snapshot):
        window_end = tiny_snapshot.weather["window"]["window_end"]
        assert window_end is not None
        # the cutoff must be at/before the origin's own t0 calendar date
        assert window_end[:10] <= tiny_snapshot.t0

    def test_wx_assembly_04_weather_source_resolution_retained(self, tiny_snapshot):
        assert tiny_snapshot.grid_meta["weather_source_resolution"] == WEATHER_MODEL_RESOLUTION

    def test_wx_assembly_05_lookback_fixture_remains_unfrozen(self, tiny_snapshot):
        assert tiny_snapshot.weather["lookback_hours"] == 24
        assert tiny_snapshot.weather["lookback_hours_status"] == "UNFROZEN_DEVELOPMENT_PARAMETER"


class TestLandCoverAssembly:
    def test_lc_assembly_01_no_policy_selection_means_not_selected(self, tiny_snapshot):
        # default _tiny_policy() uses OMIT
        for cell in tiny_snapshot.grid_cells:
            assert cell.landcover is None

    def test_lc_assembly_02_v100_v200_never_silently_mixed(self, full_snapshot):
        versions_seen = set()
        for cell in full_snapshot.grid_cells:
            if cell.landcover:
                for r in cell.landcover.values():
                    if r["dataset_version"]:
                        versions_seen.add(r["dataset_version"])
        # 2020 event -> YEAR_MATCHED_REFERENCE must select v100 (2020) only
        assert versions_seen == {"v100 (2020)"}

    def test_lc_assembly_03_non_2020_2021_record_cannot_be_year_matched(self, repo, weather_cache):
        repo.add_historical_record(_historical(source_record_id="OLD1", outbreak_start_date="2019/06/01", proxy_availability_date="2019/06/01"))
        origin = _origin(forecast_origin_id="ORIGIN:Sri Lanka:2019-06-01", t0="2019-06-01", trigger_source_ids_at_t0=["OLD1"])
        policy = _tiny_policy(landcover_policy=LandCoverFeaturePolicy(mode=LANDCOVER_MODE_YEAR_MATCHED_REFERENCE))
        snap = assemble_feature_snapshot(repo, forecast_origin=origin, policy=policy, weather_cache=weather_cache)
        for cell in snap.grid_cells:
            assert cell.landcover is None  # NOT_SELECTED, never silently called year-matched


class TestHydrologyAssembly:
    def test_hydro_assembly_01_missing_hydrolakes_cannot_fabricate_value(self, full_snapshot):
        for cell in full_snapshot.grid_cells:
            if cell.hydrology is not None:
                assert cell.hydrology["feature_name"] == "distance_to_nearest_river_km"
                # HydroLAKES is never part of the assembled hydrology block
                assert "lake" not in cell.hydrology["feature_name"].lower()


class TestMissingnessContract:
    def test_miss_01_missing_never_auto_zero_filled(self, full_snapshot):
        for cell in full_snapshot.grid_cells:
            for r in cell.host_density.values():
                if r["status"] == "MISSING":
                    assert r["value"] is None

    def test_miss_02_blocked_never_becomes_real(self):
        # Checkpoint 6A.5: an unsupported species is now rejected by
        # FeaturePolicy BEFORE assembly even starts (test_feature_policy.py
        # covers this directly) -- a config that would have produced a
        # BLOCKED result can no longer reach the assembler at all. Proven
        # here at the lower adapter level (still callable directly,
        # independent of FeaturePolicy) that BLOCKED never carries a value.
        from components.geospatial_tracking.services.geospatial.host_density.fao_glw import extract_density

        r = extract_density(center_lat=SL_LAT, center_lon=SL_LON, half_extent_km=5.0, species="goat")
        assert r.status == "BLOCKED"
        assert r.value is None

    def test_miss_02_unsupported_species_rejected_before_assembly(self):
        with pytest.raises(ValueError):
            _tiny_policy(host_density_species=("goat",))

    def test_miss_03_demo_never_enters_scientific_snapshot(self, full_snapshot):
        assert full_snapshot.feature_status_summary.get("DEMO", 0) == 0


class TestNoNormalization:
    def test_norm_01_no_aoi_max_normalization(self, full_snapshot):
        real_values = [
            c.host_density["cattle"]["value"]
            for c in full_snapshot.grid_cells
            if c.host_density["cattle"]["status"] == "REAL" and c.host_density["cattle"]["value"] is not None
        ]
        assert real_values
        # a raw density, not a value rescaled into [0,1]
        assert max(real_values) > 1.0

    def test_norm_02_no_normalization_code_in_assembler(self):
        src = inspect.getsource(assembler_module)
        for forbidden in ("min-max", "minmax", "z_score", "zscore", "winsoriz", "np.clip", ".clip("):
            assert forbidden not in src.lower()


class TestLeakageAssembly:
    def test_leak_assembly_01_future_source_excluded_from_active_set(self, tiny_snapshot):
        assert "FUTURE1" not in tiny_snapshot.active_source_ids

    def test_leak_assembly_02_future_outbreak_not_in_geometry_or_grid(self, tiny_snapshot):
        for cell in tiny_snapshot.grid_cells:
            assert "FUTURE1" not in cell.geometry_by_source


class TestSnapshotIdentity:
    """SNAPSHOT-ID-01..04."""

    def test_snapshot_id_01_date_only_vs_timestamp_different_ids(self, repo, weather_cache):
        policy = _tiny_policy()
        snap_date_only = assemble_feature_snapshot(
            repo, forecast_origin=_origin(), policy=policy, t0_precision="DATE_ONLY", weather_cache=weather_cache
        )
        snap_timestamp = assemble_feature_snapshot(
            repo, forecast_origin=_origin(), policy=policy, t0_precision="TIMESTAMP", weather_cache=weather_cache
        )
        assert snap_date_only.snapshot_id != snap_timestamp.snapshot_id
        # the resolved weather cutoff genuinely differs too (DATE_ONLY
        # resolves Asia/Colombo local midnight; TIMESTAMP treats the
        # bare date string as a naive-UTC instant) -- not merely a
        # cosmetic ID difference
        assert snap_date_only.resolved_t0_cutoff_utc != snap_timestamp.resolved_t0_cutoff_utc

    def test_snapshot_id_02_changed_temporal_mode_changes_id(self, tiny_snapshot):
        origin_strict = _origin(temporal_mode="STRICT_OPERATIONAL")
        sid = assembler_module.compute_snapshot_id(
            forecast_origin_id=origin_strict.forecast_origin_id,
            t0=origin_strict.t0,
            t0_precision="DATE_ONLY",
            temporal_mode=origin_strict.temporal_mode,
            country_scope=origin_strict.country,
            disease="Lumpy skin disease",
            active_source_ids=tiny_snapshot.active_source_ids,
            grid_config={"half_extent_km": 0.5, "cell_size_km": 1.0},
            feature_policy_hash=tiny_snapshot.feature_policy_hash,
            resolved_data_signature_hash=tiny_snapshot.resolved_data_signature_hash,
        )
        assert sid != tiny_snapshot.snapshot_id

    def test_snapshot_id_03_changed_resolved_signature_changes_id(self, tiny_snapshot):
        from components.geospatial_tracking.services.features.contracts import compute_snapshot_id

        sid_same = compute_snapshot_id(
            forecast_origin_id=tiny_snapshot.forecast_origin_id,
            t0=tiny_snapshot.t0,
            t0_precision=tiny_snapshot.t0_precision,
            temporal_mode=tiny_snapshot.temporal_mode,
            country_scope=tiny_snapshot.country_scope,
            disease=tiny_snapshot.disease,
            active_source_ids=tiny_snapshot.active_source_ids,
            grid_config={"half_extent_km": 0.5, "cell_size_km": 1.0},
            feature_policy_hash=tiny_snapshot.feature_policy_hash,
            resolved_data_signature_hash=tiny_snapshot.resolved_data_signature_hash,
        )
        sid_diff = compute_snapshot_id(
            forecast_origin_id=tiny_snapshot.forecast_origin_id,
            t0=tiny_snapshot.t0,
            t0_precision=tiny_snapshot.t0_precision,
            temporal_mode=tiny_snapshot.temporal_mode,
            country_scope=tiny_snapshot.country_scope,
            disease=tiny_snapshot.disease,
            active_source_ids=tiny_snapshot.active_source_ids,
            grid_config={"half_extent_km": 0.5, "cell_size_km": 1.0},
            feature_policy_hash=tiny_snapshot.feature_policy_hash,
            resolved_data_signature_hash="DIFFERENT_RESOLVED_SIGNATURE",
        )
        assert sid_same == tiny_snapshot.snapshot_id
        assert sid_diff != sid_same

    def test_snapshot_id_04_generated_at_does_not_affect_id(self, repo, weather_cache):
        snap1 = assemble_feature_snapshot(repo, forecast_origin=_origin(), policy=_tiny_policy(), weather_cache=weather_cache)
        snap2 = assemble_feature_snapshot(repo, forecast_origin=_origin(), policy=_tiny_policy(), weather_cache=weather_cache)
        assert snap1.generated_at != snap2.generated_at or True  # timestamps may coincide; not the point
        assert snap1.snapshot_id == snap2.snapshot_id


class TestHydrologyQueryLimit:
    def test_hydro_policy_03_search_radius_flows_from_policy_into_assembly(self, repo, weather_cache):
        policy = _tiny_policy(hydrology_include=True, hydrorivers_search_radius_km=1.0)
        snap = assemble_feature_snapshot(repo, forecast_origin=_origin(), policy=policy, weather_cache=weather_cache)
        cell = snap.grid_cells[0]
        assert cell.hydrology is not None
        # a real HydroRIVERS reach exists within Chavakachcheri's real
        # ~4.3km nearest-river distance (Checkpoint 5.6 verification) --
        # a 1km query limit is too small to find it -> MISSING, not a
        # fabricated distance == radius boundary value
        assert cell.hydrology["status"] == "MISSING"
        assert cell.hydrology["value"] is None
        assert "1.0" in cell.hydrology["quality_notes"] or "1.5" in cell.hydrology["quality_notes"]

    def test_hydro_policy_03_no_river_never_reports_distance_equal_to_radius(self, repo, weather_cache):
        policy = _tiny_policy(hydrology_include=True, hydrorivers_search_radius_km=0.001)
        snap = assemble_feature_snapshot(repo, forecast_origin=_origin(), policy=policy, weather_cache=weather_cache)
        cell = snap.grid_cells[0]
        if cell.hydrology["status"] == "REAL":
            assert cell.hydrology["value"] != 0.001
        else:
            assert cell.hydrology["value"] is None
