"""Repository abstraction: scientific/service code depends on this
Protocol, never on `sqlite3` directly.

Future architecture (master-prompt §5):

    OutbreakRepository (this Protocol)
            |
            +-- SQLiteOutbreakRepository      NOW  (repositories/sqlite_repository.py)
            |
            +-- MongoOutbreakRepository       LATER (not implemented, not connected)

`motor` (async MongoDB driver) is already listed in backend/requirements.txt
for the eventual Mongo implementation, but nothing in this checkpoint
constructs a Mongo client or connection — that is explicitly out of scope
until a `MongoOutbreakRepository` is actually built against this same
Protocol.
"""

from __future__ import annotations

from typing import Protocol

from ..domain.models import AnimalReport, HistoricalOutbreakRecord, OutbreakEpisode, PredictionRun


class OutbreakRepository(Protocol):
    """Storage-only interface. No eligibility/temporal/dedup business
    logic belongs here — that lives in `services/source_selector.py`,
    which depends on this Protocol rather than any concrete backend.
    Filtering parameters here (disease, country, farm_id) are plain data
    filters; none of them encode a scientific policy (e.g. no repository
    method ever hardcodes a country's role as "training" or "test" — see
    master-prompt §8).
    """

    def init_schema(self) -> None:
        """Idempotent: safe to call on every startup."""
        ...

    # -- animal reports (live domain input) --------------------------------
    def add_animal_report(self, report: AnimalReport) -> None: ...
    def get_animal_report(self, report_id: str) -> AnimalReport | None: ...
    def list_animal_reports(
        self, *, farm_id: str | None = None, disease: str | None = None
    ) -> list[AnimalReport]: ...

    # -- outbreak episodes (live domain, aggregated) ------------------------
    def add_outbreak_episode(self, episode: OutbreakEpisode) -> None: ...
    def get_outbreak_episode(self, outbreak_id: str) -> OutbreakEpisode | None: ...
    def list_outbreak_episodes(
        self, *, disease: str | None = None, country: str | None = None
    ) -> list[OutbreakEpisode]: ...

    # -- historical research records (retrospective domain) ------------------
    def add_historical_record(self, record: HistoricalOutbreakRecord) -> None: ...
    def get_historical_record(self, source_record_id: str) -> HistoricalOutbreakRecord | None: ...
    def list_historical_records(
        self, *, disease: str | None = None, country: str | None = None
    ) -> list[HistoricalOutbreakRecord]: ...

    # -- prediction run audit trail ------------------------------------------
    def add_prediction_run(self, run: PredictionRun) -> None: ...
    def get_prediction_run(self, prediction_id: str) -> PredictionRun | None: ...
