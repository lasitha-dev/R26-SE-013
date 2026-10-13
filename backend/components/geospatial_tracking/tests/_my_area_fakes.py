"""In-memory `ScientificReadPort` fake for GEO-AREA-01/GEO-ANALYSIS-01
tests (mirrors `_operational_fakes.py`'s convention). Not a `test_*`
module -- pytest will not collect it directly. No real SQLite/repository
is touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import (
    FrozenGeospatialRuntimeAnalysis10A,
    RuntimeAnalysisError10A,
    RuntimeAnalysisMetadata10A,
    RuntimeCell10A,
    RuntimeCellDirection10A,
    RuntimeCellRisk10A,
)
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.historical_trigger import HistoricalTriggerCandidate
from components.geospatial_tracking.services.transport.geospatial_snapshot_10b import GeospatialSnapshot10B


def make_forecast_origin(**overrides) -> ForecastOrigin:
    fields = dict(
        forecast_origin_id="ORIGIN:Sri Lanka:2026-01-01",
        country="Sri Lanka",
        t0="2026-01-01",
        temporal_mode="RETROSPECTIVE_PROXY",
        trigger_source_ids_at_t0=["SRC-1"],
        trigger_source_count=1,
    )
    fields.update(overrides)
    return ForecastOrigin(**fields)


@dataclass(frozen=True)
class _FakeNominalReachDay:
    day: int
    nominal_reach_km: float
    derived_interval_lower_km: float | None = None
    derived_interval_upper_km: float | None = None

    def as_dict(self) -> dict:
        return {
            "day": self.day, "nominal_reach_km": self.nominal_reach_km,
            "derived_interval_lower_km": self.derived_interval_lower_km,
            "derived_interval_upper_km": self.derived_interval_upper_km,
        }


@dataclass(frozen=True)
class _FakeSourcePoint:
    source_id: str
    longitude: float | None
    latitude: float | None
    availability_quality: str | None = "ACTUAL"
    gps_quality: str | None = "EXACT"


def make_nominal_reach_days(days: list[int] | None = None, *, km_per_day: float = 10.0) -> tuple:
    days = days if days is not None else [1, 2, 3, 4, 5, 6, 7]
    return tuple(_FakeNominalReachDay(day=d, nominal_reach_km=km_per_day * d) for d in days)


def make_source_point(**overrides) -> _FakeSourcePoint:
    fields = dict(source_id="SRC-1", longitude=79.8612, latitude=6.9271)
    fields.update(overrides)
    return _FakeSourcePoint(**fields)


def make_historical_trigger_candidate(**overrides) -> HistoricalTriggerCandidate:
    fields = dict(
        source_id="SRC-1", country="Sri Lanka", disease="Lumpy skin disease",
        effective_availability_date="2026-01-01", availability_quality="ACTUAL",
    )
    fields.update(overrides)
    return HistoricalTriggerCandidate(**fields)


def make_runtime_cell(**overrides) -> RuntimeCell10A:
    fields = dict(
        scientific_cell_id="CELL-1", centroid_longitude=79.86, centroid_latitude=6.93, scientific_crs="EPSG:32644",
        risk=RuntimeCellRisk10A(raw_c0_score=0.5, score_status="SCORED", semantics="RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY", risk_surface_temporal_semantics="STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT"),
        direction=RuntimeCellDirection10A(method_id="8B3", method_version="1", bearing_deg=45.0, directional_clarity=0.6, directional_input_coverage=1.0, direction_status="OK", direction_semantics="GEOMETRIC_TENDENCY"),
    )
    fields.update(overrides)
    return RuntimeCell10A(**fields)


def make_geospatial_snapshot(
    *,
    forecast_origin_id: str = "ORIGIN:Sri Lanka:2026-01-01",
    t0: str = "2026-01-01",
    eligible_sources: tuple = (),
    nominal_reach_by_day: tuple = (),
    cells: tuple = (),
    apparent_rate_context: dict | None = None,
) -> GeospatialSnapshot10B:
    metadata = RuntimeAnalysisMetadata10A(
        forecast_origin_id=forecast_origin_id, country="Sri Lanka", t0=t0, temporal_mode="RETROSPECTIVE_PROXY",
        disease="Lumpy skin disease", active_source_window_days=14, active_source_window_days_label="14_DAYS",
        status="OK", runtime_data_mode="HISTORICAL_RETROSPECTIVE_REPLAY", availability_mode="RETROSPECTIVE_PROXY",
        record_domain_scope="HISTORICAL_ONLY", active_source_window_original_provenance="UNFROZEN_DEVELOPMENT_PARAMETER",
        active_source_window_runtime_status="FIXED_HISTORICAL_DEVELOPMENT_PROTOCOL_VALUE_NOT_SCIENTIFICALLY_VALIDATED",
        live_operational_analysis_status="NOT_IMPLEMENTED_NO_ACTUAL_OPERATIONAL_AVAILABILITY_PIPELINE",
    )
    analysis = FrozenGeospatialRuntimeAnalysis10A(
        analysis_metadata=metadata, eligible_sources=eligible_sources, cells=cells,
        apparent_rate_context=apparent_rate_context if apparent_rate_context is not None else {},
        nominal_reach_by_day=nominal_reach_by_day, provenance={}, limitations=(),
    )
    return GeospatialSnapshot10B(
        snapshot_id="SNAPSHOT-TEST", forecast_origin_id=forecast_origin_id, analysis=analysis,
        transport_metadata=metadata.as_dict(), generated_at_utc="2026-01-02T00:00:00Z",
    )


class FakeScientificReadPort:
    def __init__(
        self,
        origins: list[ForecastOrigin] | None = None,
        trigger_locations_by_origin_id: dict[str, list[tuple[str, float, float]]] | None = None,
        analyses_by_origin_id: dict[str, GeospatialSnapshot10B] | None = None,
        raise_on_list_origins: Exception | None = None,
        origin_errors: dict[str, RuntimeAnalysisError10A] | None = None,
        historical_candidates: list[HistoricalTriggerCandidate] | None = None,
        raise_on_historical_candidates: Exception | None = None,
    ) -> None:
        self._origins = origins or []
        self._trigger_locations = trigger_locations_by_origin_id or {}
        self._analyses = analyses_by_origin_id or {}
        self._raise_on_list_origins = raise_on_list_origins
        self._origin_errors = origin_errors or {}
        self._historical_candidates = historical_candidates or []
        self._raise_on_historical_candidates = raise_on_historical_candidates
        self.list_origins_calls: list[dict] = []
        self.analysis_calls: list[str] = []
        self.historical_candidates_calls: list[dict] = []

    def list_origins(self, *, disease: str, country: str | None = None) -> list[ForecastOrigin]:
        self.list_origins_calls.append({"disease": disease, "country": country})
        if self._raise_on_list_origins:
            raise self._raise_on_list_origins
        return list(self._origins)

    def get_origin_trigger_locations(self, origin: ForecastOrigin) -> list[tuple[str, float, float]]:
        return list(self._trigger_locations.get(origin.forecast_origin_id, []))

    def get_origin_analysis(self, forecast_origin_id: str, *, disease: str) -> GeospatialSnapshot10B:
        self.analysis_calls.append(forecast_origin_id)
        if forecast_origin_id in self._origin_errors:
            raise self._origin_errors[forecast_origin_id]
        snapshot = self._analyses.get(forecast_origin_id)
        if snapshot is None:
            raise RuntimeAnalysisError10A("ORIGIN_NOT_FOUND", f"no fake analysis registered for {forecast_origin_id!r}")
        return snapshot

    def list_historical_trigger_candidates(self, *, disease: str, country: str | None = None) -> list[HistoricalTriggerCandidate]:
        self.historical_candidates_calls.append({"disease": disease, "country": country})
        if self._raise_on_historical_candidates:
            raise self._raise_on_historical_candidates
        return list(self._historical_candidates)
