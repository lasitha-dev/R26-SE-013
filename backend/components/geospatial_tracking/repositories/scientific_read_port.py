"""GEO-AREA-01 Section 21: a small, Geospatial-owned READ-ONLY port
around the EXISTING scientific read services -- never a second
historical repository, never a duplicated algorithm.

Every method below calls a real, already-frozen function verbatim:

  - `list_origins` -> `services.forecast_origin.build_forecast_origin_ledger`
    (the exact function backing `GET /origins`).
  - `get_origin_trigger_locations` -> `OutbreakRepository.get_historical_record`
    (a plain Protocol read method, GEO-AREA-01 Section 11's answer to
    "search first for an existing distance helper": `ForecastOrigin`
    itself carries NO coordinate -- verified read-only,
    `services/forecast_origin.py` -- so a real per-origin distance can
    only come from resolving each origin's own real trigger-source
    records, never a fabricated origin centroid).
  - `get_origin_analysis` -> `services.transport.geospatial_snapshot_10b.
    compute_snapshot_with_managed_repository_10b` (the exact function
    backing `GET /analysis/{id}/summary|cells|sources`).
  - `list_historical_trigger_candidates` (GEO-ANALYSIS-01 Section 24: the
    smallest read-only addition needed for Page 3's historical trend) ->
    `services.historical_trigger.list_historical_trigger_candidates` --
    the SAME unique-per-source-record enumeration `build_forecast_origin_
    ledger` itself is built from (Checkpoint 4.5 Part 7). Reused here
    verbatim rather than duplicated so Page 3's historical counts can
    never numerically drift from the forecast-origin ledger they're
    reported alongside.

All four open/close their own repository via `managed_repository_10b`
(the same try/finally idiom `api/router.py::get_repository` and
`geospatial_snapshot_10b.py` itself already use) -- never a second
Mongo/SQLite connection convention.
"""

from __future__ import annotations

from typing import Protocol

from ..services.forecast_origin import ForecastOrigin, build_forecast_origin_ledger
from ..services.historical_trigger import HistoricalTriggerCandidate, list_historical_trigger_candidates
from ..services.transport.geospatial_snapshot_10b import GeospatialSnapshot10B, compute_snapshot_with_managed_repository_10b, managed_repository_10b


class ScientificReadPort(Protocol):
    """Storage-agnostic read boundary over the existing scientific
    services -- no eligibility/distance/relevance decision belongs here;
    that lives entirely in `services/my_area/*`/`services/analysis_trends/*`,
    which depend on this Protocol rather than any concrete backend."""

    def list_origins(self, *, disease: str, country: str | None = None) -> list[ForecastOrigin]: ...

    def get_origin_trigger_locations(self, origin: ForecastOrigin) -> list[tuple[str, float, float]]: ...
    """Returns `(source_id, latitude, longitude)` for every one of
    `origin.trigger_source_ids_at_t0` that resolves to a real
    `HistoricalOutbreakRecord` with a stored coordinate. Never fabricates
    a coordinate for a source that lacks one -- such a source is simply
    absent from the returned list."""

    def get_origin_analysis(self, forecast_origin_id: str, *, disease: str) -> GeospatialSnapshot10B: ...
    """May raise `services.disease.UnsupportedDiseaseError` or
    `services.application.frozen_geospatial_analysis_10a.
    RuntimeAnalysisError10A` -- callers handle these exactly as
    `api/router.py` already does, never suppressing them into a
    fabricated result."""

    def list_historical_trigger_candidates(self, *, disease: str, country: str | None = None) -> list[HistoricalTriggerCandidate]: ...
    """One entry per unique real historical source record eligible to
    trigger a forecast origin for `disease` (the exact enumeration
    `build_forecast_origin_ledger` buckets into origins) -- never a
    per-origin eligible-source window, which can repeat the same source
    across multiple overlapping origins (GEO-ANALYSIS-01 Section 7)."""


class RepositoryScientificReadPort:
    """The only implementation -- wraps the real repository/services,
    never constructs a second data-access layer."""

    def list_origins(self, *, disease: str, country: str | None = None) -> list[ForecastOrigin]:
        with managed_repository_10b() as repo:
            return build_forecast_origin_ledger(repo, disease=disease, country_scope=country)

    def get_origin_trigger_locations(self, origin: ForecastOrigin) -> list[tuple[str, float, float]]:
        locations: list[tuple[str, float, float]] = []
        with managed_repository_10b() as repo:
            for source_id in origin.trigger_source_ids_at_t0:
                record = repo.get_historical_record(source_id)
                if record is not None and isinstance(record.latitude, (int, float)) and isinstance(record.longitude, (int, float)):
                    locations.append((source_id, record.latitude, record.longitude))
        return locations

    def get_origin_analysis(self, forecast_origin_id: str, *, disease: str) -> GeospatialSnapshot10B:
        return compute_snapshot_with_managed_repository_10b(forecast_origin_id, disease=disease)

    def list_historical_trigger_candidates(self, *, disease: str, country: str | None = None) -> list[HistoricalTriggerCandidate]:
        with managed_repository_10b() as repo:
            return list_historical_trigger_candidates(repo, disease=disease, country_scope=country)
