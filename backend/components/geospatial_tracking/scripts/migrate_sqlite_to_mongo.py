"""GEO-MONGODB-NATIVE-INTEGRATION-24B: one-time, idempotent, rerunnable
migration of the standalone SQLite scientific research database into the
host `adrs_core` Mongo database's `geospatial_*` collections.

SOURCE (SQLite): opened strictly READ-ONLY via `file:...?mode=ro` URI mode
-- no `INSERT`/`UPDATE`/`DELETE`/schema statement is ever executed against
it, from this script or any function it calls. Never reads the host's
Mongo `diagnostic_cases` collection as an input (Section 14: clinical and
scientific data provenance stay completely separate) -- this script's only
input is the SQLite file named by `--source`.

DESTINATION (Mongo): only the four `geospatial_*`-prefixed collections
(`geospatial_animal_reports`, `geospatial_outbreak_episodes`,
`geospatial_historical_outbreak_records`, `geospatial_prediction_runs`) --
asserted by name prefix before any write, and NEVER `diagnostic_cases`/
`farms`/`vets`/any other pre-existing collection. Every write is a
`ReplaceOne(..., upsert=True)` keyed on the entity's own natural
scientific id (`source_record_id`/`report_id`/`outbreak_id`/
`prediction_id`) -- rerunning this script against unchanged source data is
a no-op (0 new inserts, N matched), never a duplicate.

VALIDATION: every source row is parsed into its real domain dataclass
(`domain.models.HistoricalOutbreakRecord` etc.) exactly as
`SQLiteOutbreakRepository`'s own `_row_to_*` helpers do -- no coordinate,
disease, or date is invented; a row that fails the dataclass's own
`__post_init__` invariants (e.g. `HistoricalOutbreakRecord`'s
ACTUAL-requires-evidence / proxy-never-ACTUAL checks) is counted as
INVALID and never written.

Default behavior is DRY RUN -- prints planned insert/matched/invalid
counts per table and writes nothing. Pass `--apply` to actually write.
`--apply` always prints the same pre-write summary first, and refuses to
run if any destination collection name fails the `geospatial_` prefix
check or if the source cannot be opened read-only.

Usage:
    python -m components.geospatial_tracking.scripts.migrate_sqlite_to_mongo \\
        --source "C:/path/to/pistes_dev.db"                 # dry run
    python -m components.geospatial_tracking.scripts.migrate_sqlite_to_mongo \\
        --source "C:/path/to/pistes_dev.db" --apply          # writes
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..domain.models import AnimalReport, HistoricalOutbreakRecord, OutbreakEpisode, PredictionRun
from ..repositories.sqlite_repository import (
    _row_to_animal_report,
    _row_to_historical_record,
    _row_to_outbreak_episode,
    _row_to_prediction_run,
)

GEOSPATIAL_COLLECTION_PREFIX = "geospatial_"

# (sqlite table, mongo collection, natural-id field, row->domain parser)
_TABLES: list[tuple[str, str, str, Callable[[sqlite3.Row], Any]]] = [
    ("animal_reports", "geospatial_animal_reports", "report_id", _row_to_animal_report),
    ("outbreak_episodes", "geospatial_outbreak_episodes", "outbreak_id", _row_to_outbreak_episode),
    ("historical_outbreak_records", "geospatial_historical_outbreak_records", "source_record_id", _row_to_historical_record),
    ("prediction_runs", "geospatial_prediction_runs", "prediction_id", _row_to_prediction_run),
]

_FORBIDDEN_DESTINATIONS = frozenset({"diagnostic_cases", "farms", "vets", "cattle", "daily_logs", "bcs_logs", "forecast_records"})


@dataclass
class TableMigrationPlan:
    sqlite_table: str
    mongo_collection: str
    total_source_rows: int = 0
    valid_ids: list[str] = field(default_factory=list)
    valid_docs: dict[str, dict[str, Any]] = field(default_factory=dict)
    invalid_rows: list[tuple[Any, str]] = field(default_factory=list)  # (row_identifier, reason)
    existing_destination_ids: set[str] = field(default_factory=set)

    @property
    def n_invalid(self) -> int:
        return len(self.invalid_rows)

    @property
    def planned_inserts(self) -> int:
        return len([i for i in self.valid_ids if i not in self.existing_destination_ids])

    @property
    def planned_updates(self) -> int:
        return len([i for i in self.valid_ids if i in self.existing_destination_ids])


def open_source_readonly(source_path: Path) -> sqlite3.Connection:
    """STRICTLY read-only -- `mode=ro` refuses to open a database that
    does not already exist and refuses any write statement at the SQLite
    engine level (not merely "we chose not to call write methods")."""
    if not source_path.exists():
        raise FileNotFoundError(f"source SQLite database does not exist: {source_path}")
    uri = f"file:{source_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _to_doc(domain_obj: Any, id_field: str) -> dict[str, Any]:
    d = domain_obj.as_dict()
    d["_id"] = d[id_field]
    return d


def build_migration_plan(
    source_conn: sqlite3.Connection,
    destination_db: Any,
) -> list[TableMigrationPlan]:
    """Read-only against BOTH sides: reads every source row, validates
    it, and reads (never writes) each destination collection's existing
    ids to classify insert-vs-update. No write happens in this
    function."""
    plans: list[TableMigrationPlan] = []
    for sqlite_table, mongo_collection, id_field, row_parser in _TABLES:
        assert mongo_collection.startswith(GEOSPATIAL_COLLECTION_PREFIX), (
            f"refusing to plan a migration destination that is not geospatial_*-prefixed: {mongo_collection!r}"
        )
        assert mongo_collection not in _FORBIDDEN_DESTINATIONS

        plan = TableMigrationPlan(sqlite_table=sqlite_table, mongo_collection=mongo_collection)
        rows = source_conn.execute(f"SELECT * FROM {sqlite_table}").fetchall()
        plan.total_source_rows = len(rows)

        for row in rows:
            row_dict = dict(row)
            row_id = row_dict.get(id_field, "<missing id>")
            try:
                domain_obj = row_parser(row)
            except (ValueError, TypeError) as exc:
                plan.invalid_rows.append((row_id, str(exc)))
                continue
            doc = _to_doc(domain_obj, id_field)
            plan.valid_ids.append(doc["_id"])
            plan.valid_docs[doc["_id"]] = doc

        if plan.valid_ids:
            existing_cursor = destination_db[mongo_collection].find(
                {"_id": {"$in": plan.valid_ids}}, {"_id": 1}
            )
            plan.existing_destination_ids = {doc["_id"] for doc in existing_cursor}

        plans.append(plan)
    return plans


def print_plan_summary(plans: list[TableMigrationPlan], *, source_path: Path, destination_db_name: str) -> None:
    print(f"SOURCE_SQLITE = {source_path}")
    print(f"SOURCE_TABLE_COUNTS = {{{', '.join(f'{p.sqlite_table}: {p.total_source_rows}' for p in plans)}}}")
    print(f"DESTINATION_DB = {destination_db_name}")
    print(f"DESTINATION_COLLECTIONS = {[p.mongo_collection for p in plans]}")
    print(f"EXISTING_DESTINATION_COUNTS = {{{', '.join(f'{p.mongo_collection}: {len(p.existing_destination_ids)}' for p in plans)}}}")
    print(
        "PLANNED_INSERTS = "
        f"{{{', '.join(f'{p.mongo_collection}: {p.planned_inserts}' for p in plans)}}}"
    )
    print(
        "PLANNED_MATCHES = "
        f"{{{', '.join(f'{p.mongo_collection}: {p.planned_updates}' for p in plans)}}}"
    )
    print(f"PLANNED_SKIPS = 0")
    print(
        "PLANNED_INVALID = "
        f"{{{', '.join(f'{p.mongo_collection}: {p.n_invalid}' for p in plans)}}}"
    )
    print("PLANNED_DELETES = 0")
    print("NON_GEOSPATIAL_DESTINATIONS = NONE")
    print()
    header = f"{'table':32}{'source_rows':>12}{'valid':>8}{'invalid':>9}{'insert':>9}{'update':>9}{'delete':>8}"
    print(header)
    print("-" * len(header))
    for plan in plans:
        print(
            f"{plan.mongo_collection:32}{plan.total_source_rows:>12}{len(plan.valid_ids):>8}"
            f"{plan.n_invalid:>9}{plan.planned_inserts:>9}{plan.planned_updates:>9}{0:>8}"
        )
    print()
    for plan in plans:
        for row_id, reason in plan.invalid_rows[:10]:
            print(f"  INVALID [{plan.sqlite_table}] id={row_id!r}: {reason}")
        if plan.n_invalid > 10:
            print(f"  ... and {plan.n_invalid - 10} more invalid rows in {plan.sqlite_table}")


def apply_plan(plans: list[TableMigrationPlan], destination_db: Any) -> dict[str, dict[str, int]]:
    """Executes the upserts. Only ever calls `bulk_write` with
    `ReplaceOne(..., upsert=True)` against a `geospatial_*` collection
    already asserted safe in `build_migration_plan`. Returns per-table
    {inserted, matched, invalid} result counts."""
    from pymongo import ReplaceOne

    results: dict[str, dict[str, int]] = {}
    for plan in plans:
        if not plan.valid_ids:
            results[plan.mongo_collection] = {"inserted": 0, "matched": 0, "invalid": plan.n_invalid}
            continue
        assert plan.mongo_collection.startswith(GEOSPATIAL_COLLECTION_PREFIX)
        assert plan.mongo_collection not in _FORBIDDEN_DESTINATIONS

        operations = [
            ReplaceOne({"_id": doc_id}, doc, upsert=True)
            for doc_id, doc in plan.valid_docs.items()
        ]
        result = destination_db[plan.mongo_collection].bulk_write(operations, ordered=False)
        results[plan.mongo_collection] = {
            "inserted": result.upserted_count,
            "matched": result.matched_count,
            "invalid": plan.n_invalid,
        }
    return results


def _connect_destination(mongodb_url: str):
    import pymongo

    client = pymongo.MongoClient(mongodb_url, serverSelectionTimeoutMS=15000)
    return client, client.adrs_core


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="Absolute path to the source pistes_dev.db (read-only)")
    parser.add_argument("--apply", action="store_true", help="Actually write. Omit for a dry run (default).")
    parser.add_argument(
        "--mongodb-url", default=None,
        help="Override the destination Mongo connection string. Defaults to the SAME "
             "core.database.MONGODB_URL the running application already uses.",
    )
    args = parser.parse_args(argv)

    source_path = Path(args.source).resolve()
    try:
        source_conn = open_source_readonly(source_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    mongodb_url = args.mongodb_url
    if mongodb_url is None:
        # Reuse the exact same connection string the running application
        # uses (never a different/second credential) -- read-only import,
        # never mutates core.database.
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # backend/ on sys.path
        from core.database import MONGODB_URL as mongodb_url  # type: ignore[assignment]

    client, destination_db = _connect_destination(mongodb_url)
    try:
        existing_collections = set(destination_db.list_collection_names())
        for _, mongo_collection, _, _ in _TABLES:
            if mongo_collection in _FORBIDDEN_DESTINATIONS:
                print(f"ERROR: refusing to migrate into forbidden collection {mongo_collection!r}")
                return 3

        plans = build_migration_plan(source_conn, destination_db)
        print_plan_summary(plans, source_path=source_path, destination_db_name=destination_db.name)

        total_invalid = sum(p.n_invalid for p in plans)
        if not args.apply:
            print()
            print("DRY RUN complete -- no writes performed. Re-run with --apply to write.")
            return 0 if total_invalid == 0 else 1

        print()
        print("--apply given: writing now...")
        results = apply_plan(plans, destination_db)
        print()
        print(f"{'table':32}{'inserted':>10}{'matched':>10}{'invalid':>10}")
        for mongo_collection, counts in results.items():
            print(f"{mongo_collection:32}{counts['inserted']:>10}{counts['matched']:>10}{counts['invalid']:>10}")
        return 0
    finally:
        source_conn.close()
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
