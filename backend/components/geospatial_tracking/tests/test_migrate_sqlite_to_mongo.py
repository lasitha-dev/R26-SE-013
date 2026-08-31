"""GEO-MONGODB-NATIVE-INTEGRATION-24B: `scripts/migrate_sqlite_to_mongo.py`
tests. Builds a real temporary SQLite file (via `SQLiteOutbreakRepository`,
the same schema the standalone research pipeline already uses) as test
FIXTURE data, then exercises the migration module's own functions against
it through a strictly read-only connection -- exactly the discipline the
real migration performs against the OTHER worktree's real
`pistes_dev.db`. The destination is `FakeDestinationDb`
(`_migration_fakes.py`) -- no real Mongo driver, no network, never the
real `adrs_core` database.

Covers: dry-run behavior (no writes), idempotency (rerun -> 0 new
inserts), invalid-row rejection, and the firewall that the migration must
never write to `diagnostic_cases`/`farms`/`vets`."""

from __future__ import annotations

import sqlite3

import pytest

from components.geospatial_tracking.domain.enums import RecordDomain
from components.geospatial_tracking.repositories.sqlite_repository import _SCHEMA
from components.geospatial_tracking.schemas import AvailabilityQuality
from components.geospatial_tracking.scripts.migrate_sqlite_to_mongo import (
    _FORBIDDEN_DESTINATIONS,
    _TABLES,
    apply_plan,
    build_migration_plan,
    open_source_readonly,
)

from ._migration_fakes import FakeDestinationDb


@pytest.fixture
def fixture_source_db(tmp_path):
    """A real, on-disk SQLite file with the standalone research schema,
    seeded with: two valid historical records (one Sri Lanka LSD, one
    Thailand FMD), and one row whose stored combination violates
    `HistoricalOutbreakRecord.__post_init__` (proxy_availability_quality
    ACTUAL is never legal) -- proving the migration classifies it INVALID
    rather than fabricating around the violation."""
    db_path = tmp_path / "fixture_pistes_dev.db"
    setup_conn = sqlite3.connect(str(db_path))
    setup_conn.executescript(_SCHEMA)
    setup_conn.execute(
        """INSERT INTO historical_outbreak_records
           (source_record_id, country, disease, latitude, longitude, gps_quality,
            operational_availability_quality, proxy_availability_date, proxy_availability_quality,
            dedup_status, model_candidate, record_domain)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "FIXTURE-SRC-1", "Sri Lanka", "Lumpy skin disease virus (Inf. with)", 9.7, 80.0, "EXACT",
            "UNKNOWN", "2026-01-01", "EVENT_DATE_PROXY", "SINGLETON", 1,
            RecordDomain.HISTORICAL_RESEARCH_RECORD.value,
        ),
    )
    setup_conn.execute(
        """INSERT INTO historical_outbreak_records
           (source_record_id, country, disease, latitude, longitude, gps_quality,
            operational_availability_quality, proxy_availability_date, proxy_availability_quality,
            dedup_status, model_candidate, record_domain)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "FIXTURE-SRC-2", "Thailand", "Foot and mouth disease", 15.0, 101.0, "APPROXIMATE",
            "UNKNOWN", "2026-02-01", "REPORT_DATE_PROXY", "SINGLETON", 1,
            RecordDomain.HISTORICAL_RESEARCH_RECORD.value,
        ),
    )
    # INVALID: proxy_availability_quality=ACTUAL is structurally forbidden
    # (proxy fields are RETROSPECTIVE_PROXY-mode substitutes only, never
    # real operational availability) -- see domain/models.py __post_init__.
    setup_conn.execute(
        """INSERT INTO historical_outbreak_records
           (source_record_id, country, disease, latitude, longitude, gps_quality,
            operational_availability_quality, proxy_availability_date, proxy_availability_quality,
            dedup_status, model_candidate, record_domain)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "FIXTURE-SRC-INVALID", "Nowhereland", "Lumpy skin disease", None, None, "UNKNOWN",
            "UNKNOWN", "2026-03-01", AvailabilityQuality.ACTUAL.value, "SINGLETON", 1,
            RecordDomain.HISTORICAL_RESEARCH_RECORD.value,
        ),
    )
    setup_conn.commit()
    setup_conn.close()
    return db_path


def test_source_connection_is_strictly_read_only(fixture_source_db):
    conn = open_source_readonly(fixture_source_db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM historical_outbreak_records")
    finally:
        conn.close()


def test_open_source_readonly_refuses_a_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        open_source_readonly(tmp_path / "does-not-exist.db")


def test_dry_run_plan_classifies_valid_and_invalid_rows(fixture_source_db):
    conn = open_source_readonly(fixture_source_db)
    try:
        destination = FakeDestinationDb()
        plans = build_migration_plan(conn, destination)
    finally:
        conn.close()

    hist_plan = next(p for p in plans if p.sqlite_table == "historical_outbreak_records")
    assert hist_plan.total_source_rows == 3
    assert sorted(hist_plan.valid_ids) == ["FIXTURE-SRC-1", "FIXTURE-SRC-2"]
    assert hist_plan.n_invalid == 1
    assert hist_plan.invalid_rows[0][0] == "FIXTURE-SRC-INVALID"
    # Nothing exists in the destination yet -- both valid rows are planned inserts.
    assert hist_plan.planned_inserts == 2
    assert hist_plan.planned_updates == 0

    # Empty source tables plan cleanly with zero everything.
    for p in plans:
        if p.sqlite_table != "historical_outbreak_records":
            assert p.total_source_rows == 0
            assert p.planned_inserts == 0
            assert p.n_invalid == 0


def test_dry_run_performs_no_writes(fixture_source_db):
    conn = open_source_readonly(fixture_source_db)
    try:
        destination = FakeDestinationDb()
        build_migration_plan(conn, destination)
    finally:
        conn.close()
    assert destination["geospatial_historical_outbreak_records"].find({}) == []


def test_apply_writes_only_valid_rows_and_is_idempotent_on_rerun(fixture_source_db):
    destination = FakeDestinationDb(preexisting_collections=["diagnostic_cases", "farms", "vets"])

    conn = open_source_readonly(fixture_source_db)
    try:
        plans = build_migration_plan(conn, destination)
        first_results = apply_plan(plans, destination)
    finally:
        conn.close()

    hist_results = first_results["geospatial_historical_outbreak_records"]
    assert hist_results["inserted"] == 2
    assert hist_results["matched"] == 0
    assert hist_results["invalid"] == 1

    stored = destination["geospatial_historical_outbreak_records"].find({})
    assert sorted(d["_id"] for d in stored) == ["FIXTURE-SRC-1", "FIXTURE-SRC-2"]
    assert all(not isinstance(d["_id"], bytes) for d in stored)  # natural string ids, never ObjectId

    # Re-run against the SAME unchanged source -- idempotent: 0 new inserts.
    conn2 = open_source_readonly(fixture_source_db)
    try:
        plans2 = build_migration_plan(conn2, destination)
        second_results = apply_plan(plans2, destination)
    finally:
        conn2.close()

    hist_results_2 = second_results["geospatial_historical_outbreak_records"]
    assert hist_results_2["inserted"] == 0
    assert hist_results_2["matched"] == 2
    assert len(destination["geospatial_historical_outbreak_records"].find({})) == 2  # never duplicated


def test_migration_never_touches_diagnostic_cases_farms_or_vets(fixture_source_db):
    destination = FakeDestinationDb(preexisting_collections=["diagnostic_cases", "farms", "vets"])
    destination["diagnostic_cases"].seed({"_id": "case-1", "verified": True})
    destination["farms"].seed({"_id": "farm-1", "latitude": 1.0, "longitude": 2.0})
    destination["vets"].seed({"_id": "vet-1", "email": "vet@example.com"})

    conn = open_source_readonly(fixture_source_db)
    try:
        plans = build_migration_plan(conn, destination)
        apply_plan(plans, destination)
    finally:
        conn.close()

    assert destination["diagnostic_cases"].find({}) == [{"_id": "case-1", "verified": True}]
    assert destination["farms"].find({}) == [{"_id": "farm-1", "latitude": 1.0, "longitude": 2.0}]
    assert destination["vets"].find({}) == [{"_id": "vet-1", "email": "vet@example.com"}]


def test_every_migration_table_targets_a_geospatial_prefixed_collection():
    for _, mongo_collection, _, _ in _TABLES:
        assert mongo_collection.startswith("geospatial_")
        assert mongo_collection not in _FORBIDDEN_DESTINATIONS
