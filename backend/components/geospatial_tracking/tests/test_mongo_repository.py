"""GEO-MONGODB-NATIVE-INTEGRATION-24B: `MongoOutbreakRepository` contract
tests -- SAME public semantic contract as `test_sqlite_repository.py`
(REPO-01/02/03), against the new Mongo-backed implementation instead.
Uses `FakeSyncCollection` (`_mongo_repository_fakes.py`) -- no real Mongo
driver, no network, never touches the real `adrs_core` database."""

from __future__ import annotations

import pytest

from components.geospatial_tracking.domain.enums import RecordDomain, ReportStatus
from components.geospatial_tracking.domain.models import (
    AnimalReport,
    HistoricalOutbreakRecord,
    OutbreakEpisode,
    PredictionRun,
)
from components.geospatial_tracking.repositories.mongo_repository import MongoOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality

from ._mongo_repository_fakes import FakeSyncCollection


@pytest.fixture
def collections():
    return {
        "animal_reports": FakeSyncCollection(),
        "outbreak_episodes": FakeSyncCollection(),
        "historical_outbreak_records": FakeSyncCollection(),
        "prediction_runs": FakeSyncCollection(),
    }


@pytest.fixture
def repo(collections):
    r = MongoOutbreakRepository(
        collections["animal_reports"],
        collections["outbreak_episodes"],
        collections["historical_outbreak_records"],
        collections["prediction_runs"],
    )
    r.init_schema()
    yield r
    r.close()


def test_mongo_repo_initializes_deterministically(collections):
    r1 = MongoOutbreakRepository(
        collections["animal_reports"], collections["outbreak_episodes"],
        collections["historical_outbreak_records"], collections["prediction_runs"],
    )
    r1.init_schema()
    r1.init_schema()  # idempotent even called twice in a row
    assert r1.list_historical_records() == []
    assert r1.list_outbreak_episodes() == []
    assert r1.list_animal_reports() == []
    r1.close()


def test_mongo_repo_outbreak_episode_round_trip(repo):
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


def test_mongo_repo_animal_report_round_trip(repo):
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


def test_mongo_repo_historical_record_round_trip(repo):
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


def test_mongo_repo_prediction_run_round_trip(repo):
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


def test_list_historical_records_filters_by_country_without_hardcoding_it(repo):
    repo.add_historical_record(HistoricalOutbreakRecord(source_record_id="a", country="Thailand"))
    repo.add_historical_record(HistoricalOutbreakRecord(source_record_id="b", country="Sri Lanka"))
    thailand_only = repo.list_historical_records(country="Thailand")
    assert [r.source_record_id for r in thailand_only] == ["a"]
    arbitrary = repo.list_historical_records(country="Nowhereland")
    assert arbitrary == []


def test_list_historical_records_filters_by_disease(repo):
    repo.add_historical_record(HistoricalOutbreakRecord(source_record_id="fmd-1", disease="Foot and mouth disease"))
    repo.add_historical_record(HistoricalOutbreakRecord(source_record_id="lsd-1", disease="Lumpy skin disease"))
    fmd_only = repo.list_historical_records(disease="Foot and mouth disease")
    assert [r.source_record_id for r in fmd_only] == ["fmd-1"]
    lsd_only = repo.list_historical_records(disease="Lumpy skin disease")
    assert [r.source_record_id for r in lsd_only] == ["lsd-1"]
    # FMD and LSD stay semantically distinct -- never cross-returned.
    assert "lsd-1" not in [r.source_record_id for r in fmd_only]
    assert "fmd-1" not in [r.source_record_id for r in lsd_only]


def test_empty_collection_behavior_returns_empty_lists_and_none(repo):
    assert repo.list_historical_records() == []
    assert repo.list_outbreak_episodes() == []
    assert repo.list_animal_reports() == []
    assert repo.get_historical_record("does-not-exist") is None
    assert repo.get_outbreak_episode("does-not-exist") is None
    assert repo.get_animal_report("does-not-exist") is None
    assert repo.get_prediction_run("does-not-exist") is None


def test_ids_are_natural_keys_never_a_generated_objectid(repo, collections):
    """Section 5's requirement: no ObjectId ever leaks into a returned
    DTO. This repository never generates one in the first place -- the
    Mongo `_id` IS the domain entity's own natural id."""
    record = HistoricalOutbreakRecord(source_record_id="NATURAL-ID-001", country="Sri Lanka")
    repo.add_historical_record(record)
    stored_ids = collections["historical_outbreak_records"].all_ids()
    assert stored_ids == ["NATURAL-ID-001"]
    fetched = repo.get_historical_record("NATURAL-ID-001")
    assert fetched.source_record_id == "NATURAL-ID-001"
    assert isinstance(fetched.source_record_id, str)


def test_reads_never_write(repo, collections):
    """Storage-only discipline mirrors `MongoOperationalDataPort`'s own
    read-only guarantee for its methods -- every `list_*`/`get_*` call
    below must never touch `replace_one`."""
    repo.add_historical_record(HistoricalOutbreakRecord(source_record_id="x", country="Thailand"))
    coll = collections["historical_outbreak_records"]
    coll.write_calls.clear()

    repo.list_historical_records()
    repo.list_historical_records(disease="anything", country="anything")
    repo.get_historical_record("x")
    repo.get_historical_record("does-not-exist")

    assert coll.write_calls == []


def test_outbreak_episodes_read_by_source_selector_are_never_confused_with_historical_records(repo):
    """`services/source_selector.py` reads BOTH `list_historical_records`
    and `list_outbreak_episodes` -- these must stay two independently
    addressable collections, never merged."""
    repo.add_historical_record(HistoricalOutbreakRecord(source_record_id="hist-1", disease="LSD"))
    repo.add_outbreak_episode(OutbreakEpisode(outbreak_id="hist-1", disease="LSD"))  # same natural id, different collection
    assert repo.get_historical_record("hist-1") is not None
    assert repo.get_outbreak_episode("hist-1") is not None
    assert len(repo.list_historical_records()) == 1
    assert len(repo.list_outbreak_episodes()) == 1
