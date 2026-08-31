"""REPO-01/02/03."""

from pathlib import Path

import pytest

from components.geospatial_tracking.domain.enums import RecordDomain, ReportStatus
from components.geospatial_tracking.domain.models import (
    AnimalReport,
    HistoricalOutbreakRecord,
    OutbreakEpisode,
    PredictionRun,
)
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality


@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


def test_repo_01_sqlite_initializes_deterministically(tmp_path):
    db_path = tmp_path / "det.db"
    r1 = SQLiteOutbreakRepository(db_path)
    r1.init_schema()
    r1.close()
    # calling init_schema again (fresh connection) must not fail or duplicate anything
    r2 = SQLiteOutbreakRepository(db_path)
    r2.init_schema()
    r2.init_schema()  # idempotent even called twice in a row
    assert r2.list_historical_records() == []
    assert r2.list_outbreak_episodes() == []
    assert r2.list_animal_reports() == []
    r2.close()


def test_repo_02_outbreak_episode_round_trip(repo):
    episode = OutbreakEpisode(
        outbreak_id="EP-1",
        disease="LSD",
        farm_id="F1",
        country="Thailand",
        latitude=9.0,
        longitude=80.0,
        affected_animals=3,
        onset_date="2026-01-01",
        operational_availability_date="2026-01-02",
        operational_availability_quality=AvailabilityQuality.ACTUAL.value,
        status=ReportStatus.CONFIRMED.value,
        gps_quality=GpsQuality.EXACT.value,
        date_quality="HIGH",
        source_report_ids=["R1", "R2", "R3"],
        record_domain=RecordDomain.LIVE_OPERATIONAL_RECORD.value,
        created_at="2026-01-03T00:00:00",
    )
    repo.add_outbreak_episode(episode)
    fetched = repo.get_outbreak_episode("EP-1")
    assert fetched == episode


def test_repo_02_animal_report_round_trip(repo):
    report = AnimalReport(
        report_id="R1",
        disease="LSD",
        farm_id="F1",
        animal_id="C001",
        country="Thailand",
        latitude=9.0,
        longitude=80.0,
        onset_date="2026-01-01",
        submitted_at="2026-01-01T08:00:00",
        accepted_at="2026-01-02T09:00:00",
        status=ReportStatus.CONFIRMED.value,
        source="farmer_app",
        created_at="2026-01-01T08:00:01",
    )
    repo.add_animal_report(report)
    fetched = repo.get_animal_report("R1")
    assert fetched == report


def test_repo_02_historical_record_round_trip(repo):
    record = HistoricalOutbreakRecord(
        source_record_id="WAHIS_PDF:Event_3473.pdf:000002",
        country="Sri Lanka",
        disease="Lumpy skin disease virus (Inf. with)",
        outbreak_id="OB_80063",
        outbreak_start_date="2020/09/07",
        operational_availability_date=None,
        operational_availability_quality=AvailabilityQuality.UNKNOWN.value,
        proxy_availability_date="2020/09/07",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        proxy_availability_source_field="outbreak_start_date",
        latitude=9.7151701,
        longitude=80.0668497,
        gps_quality=GpsQuality.EXACT.value,
        species="cattle (domestic)",
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        dedup_confidence="HIGH",
        model_candidate=True,
        duplicate_group_id="DUPGRP:00001",
        member_record_ids="a;b;c",
    )
    repo.add_historical_record(record)
    fetched = repo.get_historical_record("WAHIS_PDF:Event_3473.pdf:000002")
    assert fetched == record


def test_repo_02_prediction_run_round_trip(repo):
    run = PredictionRun(
        prediction_id="PR-1",
        forecast_origin_t0="2026-01-10",
        temporal_mode="RETROSPECTIVE_PROXY",
        primary_source_id="WAHIS_PDF:Event_3473.pdf:000002",
        active_source_ids=["WAHIS_PDF:Event_3473.pdf:000002", "FAO_EMPRESI_CSV:x.csv:000001"],
        model_version=None,
        config_hash=None,
        created_at="2026-01-10T12:00:00",
    )
    repo.add_prediction_run(run)
    fetched = repo.get_prediction_run("PR-1")
    assert fetched == run


def test_repo_03_local_db_path_is_gitignored():
    repo_root = Path(__file__).resolve().parents[4]
    gitignore_text = (repo_root / ".gitignore").read_text(encoding="utf-8")
    assert "backend/components/geospatial_tracking/data/local/" in gitignore_text
    assert "*.db" in gitignore_text

    from components.geospatial_tracking.config import DEFAULT_SQLITE_DB_PATH

    assert DEFAULT_SQLITE_DB_PATH.startswith("data/local/")
    assert DEFAULT_SQLITE_DB_PATH.endswith(".db")


def test_list_historical_records_filters_by_country_without_hardcoding_it(repo):
    repo.add_historical_record(HistoricalOutbreakRecord(source_record_id="a", country="Thailand"))
    repo.add_historical_record(HistoricalOutbreakRecord(source_record_id="b", country="Sri Lanka"))
    thailand_only = repo.list_historical_records(country="Thailand")
    assert [r.source_record_id for r in thailand_only] == ["a"]
    # the repository's filter takes whatever string is passed — it doesn't
    # know or care that "Thailand"/"Sri Lanka" mean anything special
    arbitrary = repo.list_historical_records(country="Nowhereland")
    assert arbitrary == []
