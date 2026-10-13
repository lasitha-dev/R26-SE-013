"""ORIGIN-01/02, SOURCE-SNAPSHOT-01/02/03."""

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.forecast_origin import (
    build_forecast_origin_ledger,
    build_source_snapshot,
)


@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


def _historical(**overrides):
    fields = dict(
        source_record_id="H1",
        country="Thailand",
        disease="Lumpy skin disease",
        outbreak_start_date="2026/01/05",
        proxy_availability_date="2026/01/05",
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


class TestForecastOriginLedger:
    def test_origin_01_deterministic_across_repeated_runs(self, repo):
        repo.add_historical_record(_historical(source_record_id="H1", outbreak_start_date="2026/01/05", proxy_availability_date="2026/01/05"))
        repo.add_historical_record(_historical(source_record_id="H2", outbreak_start_date="2026/01/09", proxy_availability_date="2026/01/09"))
        ledger1 = build_forecast_origin_ledger(repo, disease="Lumpy skin disease")
        ledger2 = build_forecast_origin_ledger(repo, disease="Lumpy skin disease")
        assert [o.as_dict() for o in ledger1] == [o.as_dict() for o in ledger2]

    def test_origin_02_same_country_and_t0_with_multiple_triggers_makes_one_origin(self, repo):
        repo.add_historical_record(_historical(source_record_id="H1", outbreak_start_date="2026/01/05", proxy_availability_date="2026/01/05"))
        repo.add_historical_record(_historical(source_record_id="H2", outbreak_start_date="2026/01/05", proxy_availability_date="2026/01/05"))
        repo.add_historical_record(_historical(source_record_id="H3", outbreak_start_date="2026/01/05", proxy_availability_date="2026/01/05"))
        ledger = build_forecast_origin_ledger(repo, disease="Lumpy skin disease")
        assert len(ledger) == 1
        origin = ledger[0]
        assert origin.country == "Thailand"
        assert origin.t0 == "2026-01-05"
        assert origin.trigger_source_count == 3
        assert set(origin.trigger_source_ids_at_t0) == {"H1", "H2", "H3"}

    def test_distinct_dates_produce_distinct_origins(self, repo):
        repo.add_historical_record(_historical(source_record_id="H1", outbreak_start_date="2026/01/05", proxy_availability_date="2026/01/05"))
        repo.add_historical_record(_historical(source_record_id="H2", outbreak_start_date="2026/01/09", proxy_availability_date="2026/01/09"))
        ledger = build_forecast_origin_ledger(repo, disease="Lumpy skin disease")
        assert len(ledger) == 2
        assert {o.t0 for o in ledger} == {"2026-01-05", "2026-01-09"}

    def test_distinct_countries_on_same_date_produce_distinct_origins(self, repo):
        repo.add_historical_record(_historical(source_record_id="H1", country="Thailand", outbreak_start_date="2026/01/05", proxy_availability_date="2026/01/05"))
        repo.add_historical_record(_historical(source_record_id="H2", country="Sri Lanka", outbreak_start_date="2026/01/05", proxy_availability_date="2026/01/05"))
        ledger = build_forecast_origin_ledger(repo, disease="Lumpy skin disease")
        assert len(ledger) == 2
        assert {o.country for o in ledger} == {"Thailand", "Sri Lanka"}

    def test_unresolved_dedup_status_never_becomes_a_trigger(self, repo):
        repo.add_historical_record(
            _historical(dedup_status=DedupStatus.REVIEW_MEDIUM.value, model_candidate=False)
        )
        ledger = build_forecast_origin_ledger(repo, disease="Lumpy skin disease")
        assert ledger == []


class TestSourceSnapshot:
    def test_source_snapshot_01_no_source_after_t0(self, repo):
        repo.add_historical_record(_historical(source_record_id="H1", outbreak_start_date="2026/01/05", proxy_availability_date="2026/01/05"))
        repo.add_historical_record(_historical(source_record_id="H_future", outbreak_start_date="2026/01/06", proxy_availability_date="2026/01/06"))
        ledger = build_forecast_origin_ledger(repo, disease="Lumpy skin disease")
        origin = next(o for o in ledger if o.t0 == "2026-01-05")
        snapshot = build_source_snapshot(repo, origin, disease="Lumpy skin disease", active_window_days=14)
        assert "H_future" not in snapshot.source_ids
        assert snapshot.source_ids == ["H1"]

    def test_source_snapshot_02_source_exactly_at_t0_allowed(self, repo):
        repo.add_historical_record(_historical(source_record_id="H1", outbreak_start_date="2026/01/05", proxy_availability_date="2026/01/05"))
        ledger = build_forecast_origin_ledger(repo, disease="Lumpy skin disease")
        origin = ledger[0]
        snapshot = build_source_snapshot(repo, origin, disease="Lumpy skin disease", active_window_days=14)
        assert "H1" in snapshot.source_ids

    def test_source_snapshot_03_source_before_active_window_excluded(self, repo):
        repo.add_historical_record(_historical(source_record_id="H_trigger", outbreak_start_date="2026/01/20", proxy_availability_date="2026/01/20"))
        repo.add_historical_record(_historical(source_record_id="H_old", outbreak_start_date="2025/12/01", proxy_availability_date="2025/12/01"))
        ledger = build_forecast_origin_ledger(repo, disease="Lumpy skin disease")
        origin = next(o for o in ledger if o.t0 == "2026-01-20")
        snapshot = build_source_snapshot(repo, origin, disease="Lumpy skin disease", active_window_days=14)
        assert "H_old" not in snapshot.source_ids
        assert snapshot.source_ids == ["H_trigger"]

    def test_source_snapshot_labels_window_as_unfrozen_development_parameter(self, repo):
        repo.add_historical_record(_historical())
        ledger = build_forecast_origin_ledger(repo, disease="Lumpy skin disease")
        snapshot = build_source_snapshot(repo, ledger[0], disease="Lumpy skin disease", active_window_days=14)
        assert snapshot.active_window_days_label == "UNFROZEN_DEVELOPMENT_PARAMETER"

    def test_source_snapshot_uses_historical_only_domain_scope(self, repo):
        import inspect

        from components.geospatial_tracking.services import forecast_origin

        src = inspect.getsource(forecast_origin)
        assert src.count("RecordDomainScope.HISTORICAL_ONLY") >= 2  # both discovery and snapshot
