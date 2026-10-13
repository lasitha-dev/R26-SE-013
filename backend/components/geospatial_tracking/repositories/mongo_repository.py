"""GEO-MONGODB-NATIVE-INTEGRATION-24B: Mongo-backed implementation of
`OutbreakRepository` (`repositories/base.py`) — the SAME Protocol
`SQLiteOutbreakRepository` already satisfies structurally. This is the
`MongoOutbreakRepository` anticipated (but explicitly not built) by
`base.py`'s own docstring:

    OutbreakRepository (Protocol)
            |
            +-- SQLiteOutbreakRepository      development/standalone research
            |
            +-- MongoOutbreakRepository       THIS FILE -- host adrs_core

Storage-only — no eligibility/temporal/dedup/scientific business logic
belongs here, exactly as `base.py` documents. `services/source_selector.py`,
`services/forecast_origin.py`, `services/historical_trigger.py`, and the
snapshot/analysis machinery under `services/transport/` and
`services/application/` depend on the `OutbreakRepository` Protocol, never
on this concrete class — this module changes no repository query semantics
and adds no new caller.

Connection discipline (mirrors `host_operational_adapter.py`'s and
`mongo_case_event_source.py`'s discipline exactly): constructor-injected,
generic collection objects only — no `MongoClient`, no connection string,
no `core.database`/`core.security` import anywhere in this module. The
running application (`backend/main.py`'s Geospatial composition block)
supplies four *synchronous* pymongo collections obtained from the host's
single already-existing `core.database.db` Motor client via that client's
own `.delegate` (Motor's documented escape hatch to the underlying
synchronous `pymongo.MongoClient`/`Database`/`Collection` it wraps) —
never a second `MongoClient` instantiated, never a second connection pool.
A synchronous collection is required because `OutbreakRepository` is a
fully synchronous Protocol (mirrors `SQLiteOutbreakRepository` — every
HTTP route that opens one via `api/router.py::get_repository` /
`services/transport/geospatial_snapshot_10b.py::managed_repository_10b`
is a plain `def`, run by FastAPI in its threadpool, never `await`ed).

Collections (four, one per domain entity in `domain/models.py` — no
collection invented beyond what the real repository interface needs):

  - `geospatial_animal_reports`           <- AnimalReport
  - `geospatial_outbreak_episodes`        <- OutbreakEpisode
  - `geospatial_historical_outbreak_records` <- HistoricalOutbreakRecord
  - `geospatial_prediction_runs`          <- PredictionRun

Every collection's Mongo `_id` IS the domain entity's own natural,
scientifically-meaningful id (`report_id` / `outbreak_id` /
`source_record_id` / `prediction_id`) — never a generated `ObjectId`. This
is deliberate, not incidental: it (a) makes every write a natural upsert
keyed on the same id SQLite uses as its `PRIMARY KEY`, so re-running an
import is idempotent for free, and (b) means no `ObjectId` can ever leak
into a `list_*`/`get_*` return value, because none is ever created here in
the first place — every `_row_to_*`-equivalent function below only ever
sees fields the dataclass itself declares.

READ methods never write (Section-mirroring `MongoOperationalDataPort`'s
own read-only discipline for its two methods) — only `add_*` methods call
`replace_one(..., upsert=True)`; `list_*`/`get_*` call `find`/`find_one`
exclusively.
"""

from __future__ import annotations

from typing import Any, Iterator, Protocol

from ..domain.models import AnimalReport, HistoricalOutbreakRecord, OutbreakEpisode, PredictionRun


class SyncCollection(Protocol):
    """The minimal synchronous pymongo-collection surface this repository
    needs -- deliberately not the full `pymongo.collection.Collection`
    API, so a lightweight in-memory fake can implement it for tests
    without a real Mongo driver (mirrors `ReadOnlyCollection`'s /
    `WatchableCollection`'s same minimalism in
    `host_operational_adapter.py` / `mongo_case_event_source.py`)."""

    def find_one(self, filter: dict[str, Any]) -> dict[str, Any] | None: ...

    def find(self, filter: dict[str, Any]) -> Iterator[dict[str, Any]]: ...

    def replace_one(self, filter: dict[str, Any], replacement: dict[str, Any], upsert: bool = False) -> Any: ...

    def create_index(self, keys: Any, **kwargs: Any) -> Any: ...


def _query(**fields: Any) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _doc_to_animal_report(doc: dict[str, Any]) -> AnimalReport:
    d = {k: v for k, v in doc.items() if k != "_id"}
    return AnimalReport(**d)


def _doc_to_outbreak_episode(doc: dict[str, Any]) -> OutbreakEpisode:
    d = {k: v for k, v in doc.items() if k != "_id"}
    d["source_report_ids"] = list(d.get("source_report_ids") or [])
    return OutbreakEpisode(**d)


def _doc_to_historical_record(doc: dict[str, Any]) -> HistoricalOutbreakRecord:
    d = {k: v for k, v in doc.items() if k != "_id"}
    return HistoricalOutbreakRecord(**d)


def _doc_to_prediction_run(doc: dict[str, Any]) -> PredictionRun:
    d = {k: v for k, v in doc.items() if k != "_id"}
    d["active_source_ids"] = list(d.get("active_source_ids") or [])
    return PredictionRun(**d)


class MongoOutbreakRepository:
    """Implements `OutbreakRepository` (structural typing -- see
    `repositories/base.py`) against four host `adrs_core`
    `geospatial_*`-prefixed collections. Never touches `diagnostic_cases`,
    `farms`, `vets`, or any other pre-existing collection -- those belong
    exclusively to the separate, already-Mongo-backed OPERATIONAL path
    (`host_operational_adapter.py`)."""

    def __init__(
        self,
        animal_reports_collection: SyncCollection,
        outbreak_episodes_collection: SyncCollection,
        historical_outbreak_records_collection: SyncCollection,
        prediction_runs_collection: SyncCollection,
    ) -> None:
        self._animal_reports = animal_reports_collection
        self._outbreak_episodes = outbreak_episodes_collection
        self._historical_outbreak_records = historical_outbreak_records_collection
        self._prediction_runs = prediction_runs_collection

    def close(self) -> None:
        """No-op -- these collections are borrowed from the host's single
        shared Mongo client (`core.database.db`'s own underlying
        `.delegate`), never a connection this repository instance owns.
        Kept only so callers written against `OutbreakRepository` (which
        always call `.close()` in a `finally`, e.g.
        `api/router.py::get_repository`) need no special-casing."""
        return None

    def init_schema(self) -> None:
        """Idempotent -- `create_index` on an already-existing index is a
        no-op in Mongo, mirroring `CREATE TABLE IF NOT EXISTS`'s
        idempotence. Indexes only what the real read paths actually
        filter on (`services/source_selector.py`,
        `services/historical_trigger.py`) -- never a scientific decision,
        purely a query-performance aid."""
        self._historical_outbreak_records.create_index("disease")
        self._historical_outbreak_records.create_index("country")
        self._outbreak_episodes.create_index("disease")
        self._outbreak_episodes.create_index("country")
        self._animal_reports.create_index("farm_id")
        self._animal_reports.create_index("disease")

    # -- animal reports (live domain input) --------------------------------
    def add_animal_report(self, report: AnimalReport) -> None:
        d = report.as_dict()
        d["_id"] = d["report_id"]
        self._animal_reports.replace_one({"_id": d["_id"]}, d, upsert=True)

    def get_animal_report(self, report_id: str) -> AnimalReport | None:
        doc = self._animal_reports.find_one({"_id": report_id})
        return _doc_to_animal_report(doc) if doc else None

    def list_animal_reports(self, *, farm_id: str | None = None, disease: str | None = None) -> list[AnimalReport]:
        return [_doc_to_animal_report(d) for d in self._animal_reports.find(_query(farm_id=farm_id, disease=disease))]

    # -- outbreak episodes (live domain, aggregated) ------------------------
    def add_outbreak_episode(self, episode: OutbreakEpisode) -> None:
        d = episode.as_dict()
        d["_id"] = d["outbreak_id"]
        self._outbreak_episodes.replace_one({"_id": d["_id"]}, d, upsert=True)

    def get_outbreak_episode(self, outbreak_id: str) -> OutbreakEpisode | None:
        doc = self._outbreak_episodes.find_one({"_id": outbreak_id})
        return _doc_to_outbreak_episode(doc) if doc else None

    def list_outbreak_episodes(self, *, disease: str | None = None, country: str | None = None) -> list[OutbreakEpisode]:
        return [_doc_to_outbreak_episode(d) for d in self._outbreak_episodes.find(_query(disease=disease, country=country))]

    # -- historical research records (retrospective domain) ------------------
    def add_historical_record(self, record: HistoricalOutbreakRecord) -> None:
        d = record.as_dict()
        d["_id"] = d["source_record_id"]
        self._historical_outbreak_records.replace_one({"_id": d["_id"]}, d, upsert=True)

    def get_historical_record(self, source_record_id: str) -> HistoricalOutbreakRecord | None:
        doc = self._historical_outbreak_records.find_one({"_id": source_record_id})
        return _doc_to_historical_record(doc) if doc else None

    def list_historical_records(self, *, disease: str | None = None, country: str | None = None) -> list[HistoricalOutbreakRecord]:
        return [
            _doc_to_historical_record(d)
            for d in self._historical_outbreak_records.find(_query(disease=disease, country=country))
        ]

    # -- prediction run audit trail ------------------------------------------
    def add_prediction_run(self, run: PredictionRun) -> None:
        d = run.as_dict()
        d["_id"] = d["prediction_id"]
        self._prediction_runs.replace_one({"_id": d["_id"]}, d, upsert=True)

    def get_prediction_run(self, prediction_id: str) -> PredictionRun | None:
        doc = self._prediction_runs.find_one({"_id": prediction_id})
        return _doc_to_prediction_run(doc) if doc else None
