"""SQLite implementation of `OutbreakRepository` — development persistence
only (master-prompt §6). Never imported by anything claiming to be the
"scientific" layer directly; services depend on the `OutbreakRepository`
Protocol, and this class happens to satisfy it structurally (no explicit
inheritance needed — see `repositories/base.py`).

Schema/migration is a single idempotent `CREATE TABLE IF NOT EXISTS` pass
(`init_schema`), deterministic and safe to call on every process start.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..domain.models import AnimalReport, HistoricalOutbreakRecord, OutbreakEpisode, PredictionRun

_SCHEMA = """
CREATE TABLE IF NOT EXISTS animal_reports (
    report_id           TEXT PRIMARY KEY,
    disease             TEXT NOT NULL,
    farm_id             TEXT,
    animal_id           TEXT,
    country             TEXT,
    latitude            REAL,
    longitude           REAL,
    onset_date          TEXT,
    submitted_at        TEXT,
    notification_date   TEXT,
    confirmation_date   TEXT,
    accepted_at         TEXT,
    status              TEXT NOT NULL,
    source              TEXT,
    created_at          TEXT
);

CREATE TABLE IF NOT EXISTS outbreak_episodes (
    outbreak_id                        TEXT PRIMARY KEY,
    disease                            TEXT NOT NULL,
    farm_id                            TEXT,
    country                            TEXT,
    latitude                           REAL,
    longitude                          REAL,
    affected_animals                   INTEGER,
    affected_animals_quality           TEXT NOT NULL,
    unidentified_report_count          INTEGER NOT NULL DEFAULT 0,
    onset_date                         TEXT,
    episode_grouping_date              TEXT,
    episode_grouping_date_quality      TEXT NOT NULL,
    aggregation_review_required        INTEGER NOT NULL DEFAULT 0,
    operational_availability_date      TEXT,
    operational_availability_quality   TEXT NOT NULL,
    status                             TEXT NOT NULL,
    gps_quality                        TEXT NOT NULL,
    date_quality                       TEXT NOT NULL,
    source_report_ids                  TEXT NOT NULL,
    record_domain                      TEXT NOT NULL,
    created_at                         TEXT
);

CREATE TABLE IF NOT EXISTS historical_outbreak_records (
    source_record_id                   TEXT PRIMARY KEY,
    country                            TEXT,
    disease                            TEXT,
    event_id                           TEXT,
    outbreak_id                        TEXT,
    event_start_date                   TEXT,
    outbreak_start_date                TEXT,
    onset_date                         TEXT,
    confirmation_date                  TEXT,
    report_date                        TEXT,
    operational_availability_date      TEXT,
    operational_availability_quality   TEXT NOT NULL,
    proxy_availability_date            TEXT,
    proxy_availability_quality         TEXT NOT NULL,
    proxy_availability_source_field    TEXT,
    latitude                           REAL,
    longitude                          REAL,
    gps_quality                        TEXT NOT NULL,
    species                            TEXT,
    dedup_status                       TEXT NOT NULL,
    dedup_confidence                   TEXT,
    model_candidate                    INTEGER NOT NULL,
    duplicate_group_id                 TEXT,
    member_record_ids                  TEXT,
    record_domain                      TEXT NOT NULL,
    imported_at                        TEXT
);

CREATE TABLE IF NOT EXISTS prediction_runs (
    prediction_id       TEXT PRIMARY KEY,
    forecast_origin_t0  TEXT NOT NULL,
    temporal_mode       TEXT NOT NULL,
    primary_source_id   TEXT,
    active_source_ids   TEXT NOT NULL,
    model_version       TEXT,
    config_hash         TEXT,
    created_at          TEXT
);
"""


class SQLiteOutbreakRepository:
    """Implements `OutbreakRepository` (structural typing — see
    `repositories/base.py`). One connection per instance; `sqlite3`'s
    default thread-check is left enabled (a repository instance is not
    meant to be shared across threads without its own care)."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self._conn.close()

    def init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- animal reports ------------------------------------------------------
    def add_animal_report(self, report: AnimalReport) -> None:
        d = report.as_dict()
        self._conn.execute(
            """INSERT OR REPLACE INTO animal_reports
               (report_id, disease, farm_id, animal_id, country, latitude, longitude,
                onset_date, submitted_at, notification_date, confirmation_date,
                accepted_at, status, source, created_at)
               VALUES (:report_id, :disease, :farm_id, :animal_id, :country, :latitude,
                       :longitude, :onset_date, :submitted_at, :notification_date,
                       :confirmation_date, :accepted_at, :status, :source, :created_at)""",
            d,
        )
        self._conn.commit()

    def get_animal_report(self, report_id: str) -> AnimalReport | None:
        row = self._conn.execute(
            "SELECT * FROM animal_reports WHERE report_id = ?", (report_id,)
        ).fetchone()
        return _row_to_animal_report(row) if row else None

    def list_animal_reports(
        self, *, farm_id: str | None = None, disease: str | None = None
    ) -> list[AnimalReport]:
        clauses, params = [], []
        if farm_id is not None:
            clauses.append("farm_id = ?")
            params.append(farm_id)
        if disease is not None:
            clauses.append("disease = ?")
            params.append(disease)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(f"SELECT * FROM animal_reports {where}", params).fetchall()
        return [_row_to_animal_report(r) for r in rows]

    # -- outbreak episodes -----------------------------------------------------
    def add_outbreak_episode(self, episode: OutbreakEpisode) -> None:
        d = episode.as_dict()
        d["source_report_ids"] = json.dumps(d["source_report_ids"])
        d["aggregation_review_required"] = 1 if d["aggregation_review_required"] else 0
        self._conn.execute(
            """INSERT OR REPLACE INTO outbreak_episodes
               (outbreak_id, disease, farm_id, country, latitude, longitude,
                affected_animals, affected_animals_quality, unidentified_report_count,
                onset_date, episode_grouping_date, episode_grouping_date_quality,
                aggregation_review_required, operational_availability_date,
                operational_availability_quality, status, gps_quality, date_quality,
                source_report_ids, record_domain, created_at)
               VALUES (:outbreak_id, :disease, :farm_id, :country, :latitude, :longitude,
                       :affected_animals, :affected_animals_quality, :unidentified_report_count,
                       :onset_date, :episode_grouping_date, :episode_grouping_date_quality,
                       :aggregation_review_required, :operational_availability_date,
                       :operational_availability_quality, :status, :gps_quality,
                       :date_quality, :source_report_ids, :record_domain, :created_at)""",
            d,
        )
        self._conn.commit()

    def get_outbreak_episode(self, outbreak_id: str) -> OutbreakEpisode | None:
        row = self._conn.execute(
            "SELECT * FROM outbreak_episodes WHERE outbreak_id = ?", (outbreak_id,)
        ).fetchone()
        return _row_to_outbreak_episode(row) if row else None

    def list_outbreak_episodes(
        self, *, disease: str | None = None, country: str | None = None
    ) -> list[OutbreakEpisode]:
        clauses, params = [], []
        if disease is not None:
            clauses.append("disease = ?")
            params.append(disease)
        if country is not None:
            clauses.append("country = ?")
            params.append(country)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(f"SELECT * FROM outbreak_episodes {where}", params).fetchall()
        return [_row_to_outbreak_episode(r) for r in rows]

    # -- historical research records --------------------------------------------
    def add_historical_record(self, record: HistoricalOutbreakRecord) -> None:
        d = record.as_dict()
        d["model_candidate"] = 1 if d["model_candidate"] else 0
        self._conn.execute(
            """INSERT OR REPLACE INTO historical_outbreak_records
               (source_record_id, country, disease, event_id, outbreak_id,
                event_start_date, outbreak_start_date, onset_date, confirmation_date,
                report_date, operational_availability_date, operational_availability_quality,
                proxy_availability_date, proxy_availability_quality,
                proxy_availability_source_field, latitude, longitude, gps_quality,
                species, dedup_status, dedup_confidence, model_candidate,
                duplicate_group_id, member_record_ids, record_domain, imported_at)
               VALUES (:source_record_id, :country, :disease, :event_id, :outbreak_id,
                       :event_start_date, :outbreak_start_date, :onset_date,
                       :confirmation_date, :report_date, :operational_availability_date,
                       :operational_availability_quality, :proxy_availability_date,
                       :proxy_availability_quality, :proxy_availability_source_field,
                       :latitude, :longitude, :gps_quality, :species, :dedup_status,
                       :dedup_confidence, :model_candidate, :duplicate_group_id,
                       :member_record_ids, :record_domain, :imported_at)""",
            d,
        )
        self._conn.commit()

    def get_historical_record(self, source_record_id: str) -> HistoricalOutbreakRecord | None:
        row = self._conn.execute(
            "SELECT * FROM historical_outbreak_records WHERE source_record_id = ?",
            (source_record_id,),
        ).fetchone()
        return _row_to_historical_record(row) if row else None

    def list_historical_records(
        self, *, disease: str | None = None, country: str | None = None
    ) -> list[HistoricalOutbreakRecord]:
        clauses, params = [], []
        if disease is not None:
            clauses.append("disease = ?")
            params.append(disease)
        if country is not None:
            clauses.append("country = ?")
            params.append(country)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM historical_outbreak_records {where}", params
        ).fetchall()
        return [_row_to_historical_record(r) for r in rows]

    # -- prediction runs --------------------------------------------------------
    def add_prediction_run(self, run: PredictionRun) -> None:
        d = run.as_dict()
        d["active_source_ids"] = json.dumps(d["active_source_ids"])
        self._conn.execute(
            """INSERT OR REPLACE INTO prediction_runs
               (prediction_id, forecast_origin_t0, temporal_mode, primary_source_id,
                active_source_ids, model_version, config_hash, created_at)
               VALUES (:prediction_id, :forecast_origin_t0, :temporal_mode,
                       :primary_source_id, :active_source_ids, :model_version,
                       :config_hash, :created_at)""",
            d,
        )
        self._conn.commit()

    def get_prediction_run(self, prediction_id: str) -> PredictionRun | None:
        row = self._conn.execute(
            "SELECT * FROM prediction_runs WHERE prediction_id = ?", (prediction_id,)
        ).fetchone()
        return _row_to_prediction_run(row) if row else None


def _row_to_animal_report(row: sqlite3.Row) -> AnimalReport:
    d = dict(row)
    return AnimalReport(**d)


def _row_to_outbreak_episode(row: sqlite3.Row) -> OutbreakEpisode:
    d = dict(row)
    d["source_report_ids"] = json.loads(d["source_report_ids"]) if d["source_report_ids"] else []
    d["aggregation_review_required"] = bool(d["aggregation_review_required"])
    return OutbreakEpisode(**d)


def _row_to_historical_record(row: sqlite3.Row) -> HistoricalOutbreakRecord:
    d = dict(row)
    d["model_candidate"] = bool(d["model_candidate"])
    return HistoricalOutbreakRecord(**d)


def _row_to_prediction_run(row: sqlite3.Row) -> PredictionRun:
    d = dict(row)
    d["active_source_ids"] = json.loads(d["active_source_ids"]) if d["active_source_ids"] else []
    return PredictionRun(**d)
