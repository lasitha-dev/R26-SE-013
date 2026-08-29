"""ST-01..20."""

from __future__ import annotations

import inspect
import random

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.geospatial.distance import distance_km
from components.geospatial_tracking.services.source_selector import EligibleSource
from components.geospatial_tracking.services.stdbscan import cluster as cluster_module
from components.geospatial_tracking.services.stdbscan import snapshot as snapshot_module
from components.geospatial_tracking.services.stdbscan.cluster import (
    BORDER,
    CORE,
    NOISE,
    run_st_clustering,
)
from components.geospatial_tracking.services.stdbscan.config import GpsCorePolicy, STDBSCANConfig, SOFTWARE_FIXTURE_ONLY
from components.geospatial_tracking.services.stdbscan.core_support import compute_core_support_assignments
from components.geospatial_tracking.services.stdbscan.event_date import ST_TEMPORAL_UNUSABLE, ST_USABLE, resolve_cluster_event_date
from components.geospatial_tracking.services.stdbscan.neighborhood import build_neighbor_graph, joint_neighbors
from components.geospatial_tracking.services.stdbscan.snapshot import build_st_cluster_snapshot

# real Sri Lanka Chavakachcheri-area coordinate, reused as an anchor
BASE_LAT, BASE_LON = 9.6579014, 80.1643076


@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


def _historical(**overrides) -> HistoricalOutbreakRecord:
    fields = dict(
        source_record_id="H1",
        country="Thailand",
        disease="Lumpy skin disease",
        outbreak_start_date="2021/06/01",
        proxy_availability_date="2021/06/01",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        proxy_availability_source_field="outbreak_start_date",
        latitude=15.0,
        longitude=101.0,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def _eligible(**overrides) -> EligibleSource:
    fields = dict(
        source_id="H1",
        record_domain="HISTORICAL_RESEARCH_RECORD",
        disease="Lumpy skin disease",
        country="Thailand",
        latitude=15.0,
        longitude=101.0,
        effective_availability_date="2021-06-01",
        availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        gps_quality=GpsQuality.EXACT.value,
        status=DedupStatus.AUTO_MERGED_HIGH.value,
    )
    fields.update(overrides)
    return EligibleSource(**fields)


class TestJointNeighborhood:
    def test_st_01_nearby_same_time_records_are_neighbors(self):
        assert joint_neighbors(
            lat_a=BASE_LAT, lon_a=BASE_LON, date_a="2021-06-01",
            lat_b=BASE_LAT + 0.01, lon_b=BASE_LON + 0.01, date_b="2021-06-01",
            eps_space_km=50.0, eps_time_days=7,
        ) is True

    def test_st_02_spatially_too_far_not_neighbors(self):
        assert joint_neighbors(
            lat_a=BASE_LAT, lon_a=BASE_LON, date_a="2021-06-01",
            lat_b=BASE_LAT + 5.0, lon_b=BASE_LON + 5.0, date_b="2021-06-01",
            eps_space_km=10.0, eps_time_days=7,
        ) is False

    def test_st_03_temporally_too_far_not_neighbors(self):
        assert joint_neighbors(
            lat_a=BASE_LAT, lon_a=BASE_LON, date_a="2021-01-01",
            lat_b=BASE_LAT, lon_b=BASE_LON, date_b="2021-06-01",
            eps_space_km=10.0, eps_time_days=7,
        ) is False

    def test_st_04_exact_space_boundary_is_included(self):
        # construct two points at EXACTLY the real geodesic distance apart
        lat_b, lon_b = BASE_LAT + 0.1, BASE_LON
        real_distance = distance_km(BASE_LAT, BASE_LON, lat_b, lon_b)
        assert joint_neighbors(
            lat_a=BASE_LAT, lon_a=BASE_LON, date_a="2021-06-01",
            lat_b=lat_b, lon_b=lon_b, date_b="2021-06-01",
            eps_space_km=real_distance, eps_time_days=0,
        ) is True

    def test_st_04_exact_time_boundary_is_included(self):
        assert joint_neighbors(
            lat_a=BASE_LAT, lon_a=BASE_LON, date_a="2021-06-01",
            lat_b=BASE_LAT, lon_b=BASE_LON, date_b="2021-06-08",  # exactly 7 days
            eps_space_km=1.0, eps_time_days=7,
        ) is True

    def test_st_04_one_more_than_boundary_excluded(self):
        lat_b, lon_b = BASE_LAT + 0.1, BASE_LON
        real_distance = distance_km(BASE_LAT, BASE_LON, lat_b, lon_b)
        assert joint_neighbors(
            lat_a=BASE_LAT, lon_a=BASE_LON, date_a="2021-06-01",
            lat_b=lat_b, lon_b=lon_b, date_b="2021-06-01",
            eps_space_km=real_distance - 0.001, eps_time_days=0,
        ) is False

    def test_st_05_self_support_is_documented_and_present_in_graph(self):
        points = [("A", BASE_LAT, BASE_LON, "2021-06-01")]
        graph = build_neighbor_graph(points, eps_space_km=1.0, eps_time_days=1)
        assert "A" in graph["A"]  # a point is always its own neighbor


class TestDeterminism:
    def test_st_06_input_order_does_not_change_assignments_or_cluster_ids(self):
        points = [
            ("A", BASE_LAT, BASE_LON, "2021-06-01"),
            ("B", BASE_LAT + 0.001, BASE_LON, "2021-06-01"),
            ("C", BASE_LAT + 0.002, BASE_LON, "2021-06-01"),
        ]
        sources = [
            _eligible(source_id=sid, latitude=lat, longitude=lon, gps_quality=GpsQuality.EXACT.value)
            for sid, lat, lon, _ in points
        ]
        core_support = compute_core_support_assignments(sources, gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value)

        shuffled = list(points)
        random.Random(7).shuffle(shuffled)

        a1, s1 = run_st_clustering(
            usable_points=points, core_support_by_id=core_support, eps_space_km=5.0, eps_time_days=1,
            min_core_supports=2, config_hash="HASH1", forecast_origin_id="ORIGIN:X",
        )
        a2, s2 = run_st_clustering(
            usable_points=shuffled, core_support_by_id=core_support, eps_space_km=5.0, eps_time_days=1,
            min_core_supports=2, config_hash="HASH1", forecast_origin_id="ORIGIN:X",
        )
        assert {k: v.as_dict() for k, v in a1.items()} == {k: v.as_dict() for k, v in a2.items()}
        assert sorted(x.cluster_id for x in s1) == sorted(x.cluster_id for x in s2)

    def test_st_16_stable_cluster_ids_independent_of_order(self):
        points = [
            ("A", BASE_LAT, BASE_LON, "2021-06-01"),
            ("B", BASE_LAT + 0.001, BASE_LON, "2021-06-01"),
        ]
        sources = [_eligible(source_id=sid, latitude=lat, longitude=lon) for sid, lat, lon, _ in points]
        core_support = compute_core_support_assignments(sources, gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value)
        _, s1 = run_st_clustering(
            usable_points=points, core_support_by_id=core_support, eps_space_km=5.0, eps_time_days=1,
            min_core_supports=2, config_hash="H", forecast_origin_id="O",
        )
        _, s2 = run_st_clustering(
            usable_points=list(reversed(points)), core_support_by_id=core_support, eps_space_km=5.0, eps_time_days=1,
            min_core_supports=2, config_hash="H", forecast_origin_id="O",
        )
        assert s1[0].cluster_id == s2[0].cluster_id


class TestNoiseRetention:
    def test_st_07_noise_retained_not_deleted(self):
        points = [
            ("A", BASE_LAT, BASE_LON, "2021-06-01"),
            ("FAR", BASE_LAT + 10.0, BASE_LON + 10.0, "2021-06-01"),
        ]
        sources = [_eligible(source_id=sid, latitude=lat, longitude=lon) for sid, lat, lon, _ in points]
        core_support = compute_core_support_assignments(sources, gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value)
        assignments, _ = run_st_clustering(
            usable_points=points, core_support_by_id=core_support, eps_space_km=1.0, eps_time_days=1,
            min_core_supports=2, config_hash="H", forecast_origin_id="O",
        )
        assert len(assignments) == 2
        assert assignments["A"].cluster_role == NOISE
        assert assignments["FAR"].cluster_role == NOISE

    def test_st_08_all_noise_result_is_valid(self):
        points = [
            ("A", 0.0, 0.0, "2021-06-01"),
            ("B", 40.0, 40.0, "2021-06-01"),
            ("C", -40.0, -40.0, "2021-06-01"),
        ]
        sources = [_eligible(source_id=sid, latitude=lat, longitude=lon) for sid, lat, lon, _ in points]
        core_support = compute_core_support_assignments(sources, gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value)
        assignments, summaries = run_st_clustering(
            usable_points=points, core_support_by_id=core_support, eps_space_km=1.0, eps_time_days=1,
            min_core_supports=2, config_hash="H", forecast_origin_id="O",
        )
        assert summaries == []
        assert all(a.is_noise for a in assignments.values())

    def test_st_19_noise_source_remains_in_active_source_set(self, repo):
        repo.add_historical_record(_historical(source_record_id="A", latitude=15.0, longitude=101.0))
        config = STDBSCANConfig(
            eps_space_km=0.5, eps_time_days=1, min_core_supports=2, active_window_days=14,
            gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value, parameter_status=SOFTWARE_FIXTURE_ONLY,
        )
        snap = build_st_cluster_snapshot(
            repo, forecast_origin_id="O", t0="2021-06-01", country_scope="Thailand",
            disease="Lumpy skin disease", config=config,
        )
        assert "A" in snap.active_source_ids
        assert "A" in snap.noise_source_ids  # alone -> no core support -> noise
        assert set(snap.noise_source_ids) <= set(snap.active_source_ids)


class TestFutureAndTemporalSafety:
    def test_st_09_future_source_cannot_enter_clustering(self, repo):
        repo.add_historical_record(_historical(source_record_id="PAST", outbreak_start_date="2021/06/01", proxy_availability_date="2021/06/01"))
        repo.add_historical_record(_historical(source_record_id="FUTURE", outbreak_start_date="2021/12/25", proxy_availability_date="2021/12/25"))
        config = STDBSCANConfig(
            eps_space_km=5.0, eps_time_days=7, min_core_supports=1, active_window_days=14,
            gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value, parameter_status=SOFTWARE_FIXTURE_ONLY,
        )
        snap = build_st_cluster_snapshot(
            repo, forecast_origin_id="O", t0="2021-06-01", country_scope="Thailand",
            disease="Lumpy skin disease", config=config,
        )
        assert "FUTURE" not in snap.active_source_ids
        assert "PAST" in snap.active_source_ids

    def test_st_10_cluster_event_date_after_t0_is_unusable(self):
        record = _historical(outbreak_start_date="2021/06/10")
        ced = resolve_cluster_event_date(record, t0="2021-06-01")
        assert ced.usability == ST_TEMPORAL_UNUSABLE
        assert "AFTER t0" in ced.reason

    def test_st_10_cluster_event_date_before_t0_is_usable(self):
        record = _historical(outbreak_start_date="2021/05/01")
        ced = resolve_cluster_event_date(record, t0="2021-06-01")
        assert ced.usability == ST_USABLE

    def test_st_11_missing_event_date_never_falls_back_to_report_date(self):
        record = _historical(outbreak_start_date=None, event_start_date=None, onset_date=None, report_date="2021/06/15")
        ced = resolve_cluster_event_date(record, t0="2021-06-20")
        assert ced.usability == ST_TEMPORAL_UNUSABLE
        assert ced.cluster_event_date is None
        assert ced.cluster_event_date != "2021/06/15"


class TestApproximateGpsGuard:
    def _three_approx_same_coord(self):
        return [
            _eligible(source_id=f"APPROX{i}", latitude=BASE_LAT, longitude=BASE_LON, gps_quality=GpsQuality.APPROXIMATE.value)
            for i in range(3)
        ]

    def test_st_12_three_approximate_same_coord_cannot_alone_satisfy_min_core_supports_3(self):
        sources = self._three_approx_same_coord()
        core_support = compute_core_support_assignments(sources, gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value)
        # all three collapse to the SAME core_support_id
        ids = {a.core_support_id for a in core_support.values()}
        assert len(ids) == 1

        points = [(s.source_id, s.latitude, s.longitude, "2021-06-01") for s in sources]
        assignments, summaries = run_st_clustering(
            usable_points=points, core_support_by_id=core_support, eps_space_km=1.0, eps_time_days=1,
            min_core_supports=3, config_hash="H", forecast_origin_id="O",
        )
        assert summaries == []
        assert all(a.cluster_role == NOISE for a in assignments.values())

    def test_st_13_three_genuinely_distinct_supported_locations_satisfy_core_support(self):
        sources = [
            _eligible(source_id=f"EXACT{i}", latitude=BASE_LAT + i * 0.001, longitude=BASE_LON, gps_quality=GpsQuality.EXACT.value)
            for i in range(3)
        ]
        core_support = compute_core_support_assignments(sources, gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value)
        ids = {a.core_support_id for a in core_support.values()}
        assert len(ids) == 3  # each EXACT record is its own support

        points = [(s.source_id, s.latitude, s.longitude, "2021-06-01") for s in sources]
        assignments, summaries = run_st_clustering(
            usable_points=points, core_support_by_id=core_support, eps_space_km=1.0, eps_time_days=1,
            min_core_supports=3, config_hash="H", forecast_origin_id="O",
        )
        assert len(summaries) == 1
        assert set(summaries[0].core_source_ids) == {"EXACT0", "EXACT1", "EXACT2"}

    def test_st_14_approximate_records_remain_represented_after_collapse(self):
        sources = self._three_approx_same_coord()
        core_support = compute_core_support_assignments(sources, gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value)
        points = [(s.source_id, s.latitude, s.longitude, "2021-06-01") for s in sources]
        assignments, _ = run_st_clustering(
            usable_points=points, core_support_by_id=core_support, eps_space_km=1.0, eps_time_days=1,
            min_core_supports=3, config_hash="H", forecast_origin_id="O",
        )
        # never deleted -- all three still appear, even though none is core
        assert set(assignments.keys()) == {"APPROX0", "APPROX1", "APPROX2"}
        for csa in core_support.values():
            assert len(csa.support_group_source_ids) == 3  # provenance preserved

    def test_st_15_unknown_gps_quality_never_upgraded_to_exact(self):
        sources = [_eligible(source_id="U1", gps_quality=GpsQuality.UNKNOWN.value)]
        core_support = compute_core_support_assignments(sources, gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value)
        assert core_support["U1"].gps_quality == GpsQuality.UNKNOWN.value
        assert core_support["U1"].gps_quality != GpsQuality.EXACT.value

    def test_st_20_exact_only_core_support_behaves_separately(self):
        sources = self._three_approx_same_coord()
        primary = compute_core_support_assignments(sources, gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value)
        strict = compute_core_support_assignments(sources, gps_core_policy=GpsCorePolicy.EXACT_ONLY_CORE_SUPPORT.value)
        # PRIMARY: they share one collapsed support id
        assert len({a.core_support_id for a in primary.values()}) == 1
        # EXACT_ONLY: none of them can ever be core -- support_id is None for all
        assert all(a.core_support_id is None for a in strict.values())


class TestNoTransmissionChainClaim:
    def test_st_17_no_causal_or_transmission_chain_field(self):
        # check actual FIELD NAMES of the dataclasses that make up the
        # cluster/snapshot output contract -- not a naive full-source
        # grep, which would also match this test/module's own
        # explanatory prose describing the prohibition itself
        forbidden = {"transmission_chain", "causal_parent", "infected_by_cluster"}
        for dataclass_type in (
            cluster_module.ClusterAssignment,
            cluster_module.ClusterSummary,
            snapshot_module.STClusterSnapshot,
        ):
            field_names = set(dataclass_type.__dataclass_fields__.keys())
            assert not (field_names & forbidden), f"{dataclass_type.__name__} has a forbidden field: {field_names & forbidden}"

    def test_st_17_permanent_wording_present(self):
        src = inspect.getsource(cluster_module)
        assert "spatiotemporal density-based outbreak context clustering" in src.lower() or "st-dbscan-style outbreak context clustering" in src.lower()


class TestNoFutureTargetInput:
    def test_st_18_snapshot_builder_accepts_no_outcome_parameter(self):
        sig = inspect.signature(build_st_cluster_snapshot)
        for forbidden in ("target", "lead_days", "outcome", "risk", "label", "probability", "direction", "speed"):
            assert forbidden not in sig.parameters
