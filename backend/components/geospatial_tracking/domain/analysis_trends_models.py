"""GEO-ANALYSIS-01 domain objects for the Page-3 "Analysis & Trends"
backend contract.

Every optional analytics block carries its OWN `status` (Section 22/23),
so a `PARTIAL` response can represent exactly which evidence is real and
which is honestly unavailable -- never a missing field silently read as
zero/empty (Section 23's explicit rule).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields


def _as_dict(obj) -> dict:
    out = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        if hasattr(value, "as_dict"):
            out[f.name] = value.as_dict()
        elif isinstance(value, (list, tuple)) and value and hasattr(value[0], "as_dict"):
            out[f.name] = [v.as_dict() for v in value]
        else:
            out[f.name] = value
    return out


@dataclass(frozen=True)
class HistoricalTrendPoint:
    """Section 6/7: `period` is a real `YYYY-MM` bucket derived only from
    actual `effective_availability_date` values on real historical source
    records -- `count=0` is only ever emitted for a period strictly
    between the real first and last observed period (never outside the
    dataset's own coverage)."""

    period: str
    count: int
    count_basis: str

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class HistoricalSummary:
    status: str  # HistoricalDataStatus value
    historical_source_count: int
    forecast_origin_count: int
    first_observed_date: str | None
    last_observed_date: str | None
    count_basis: str

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class HistoricalTrend:
    status: str  # HistoricalDataStatus value
    period_basis: str
    points: list[HistoricalTrendPoint] = field(default_factory=list)

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class ApparentRateAnalytics:
    """Section 13: `context` is the real `apparent_rate_context` dict
    already produced by `services.application.frozen_geospatial_
    analysis_10a.apparent_rate_context_10a` -- passed through VERBATIM,
    field names/units unchanged, never relabelled as "speed"."""

    status: str  # ApparentRateStatus value
    apparent_rate_km_day: float | None
    context: dict | None

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class DirectionContext:
    """Section 13/17: always `UNAVAILABLE_RUNTIME_METRIC` this
    checkpoint -- see `domain/analysis_trends_enums.py::
    DirectionContextStatus` for why no single origin-level bearing scalar
    is scientifically defined to expose here."""

    status: str  # DirectionContextStatus value
    reason: str

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class NominalReachDayAnalytics:
    day: int
    nominal_reach_km: float | None
    derived_interval_lower_km: float | None
    derived_interval_upper_km: float | None

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class NominalReachAnalytics:
    status: str  # ApparentRateStatus-shaped (AVAILABLE / UNAVAILABLE_RUNTIME_METRIC)
    disclaimer: str
    days: list[NominalReachDayAnalytics] = field(default_factory=list)

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class RelativeSpatialScoreDistribution:
    """Section 15: order statistics (min/median/max) over real, actual
    `raw_c0_score` values from the selected origin's own snapshot cells
    -- never a fabricated/interpolated value, never presented as a
    probability, and never compared against a different snapshot's
    distribution (`cross_snapshot_comparison_status`)."""

    status: str  # RelativeSpatialScoreDistributionStatus value
    label: str
    temporal_basis: str
    min_score: float | None
    median_score: float | None
    max_score: float | None
    n_cells_scored: int
    cross_snapshot_comparison_status: str

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class SelectedOriginAnalytics:
    """Section 11/12: built only when the caller supplies a real
    `origin_id` -- never auto-selected. `area_score_availability`
    preserves the GEO-AREA farm-point limitation verbatim (Section 16)."""

    status: str  # SelectedOriginAnalyticsStatus value
    origin_id: str
    disease: str
    t0: str | None = None
    scientific_mode: str | None = None
    eligible_source_count: int | None = None
    apparent_rate: ApparentRateAnalytics | None = None
    direction_context: DirectionContext | None = None
    nominal_reach: NominalReachAnalytics | None = None
    relative_spatial_score_distribution: RelativeSpatialScoreDistribution | None = None
    area_score_availability: str | None = None

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class ModelEvaluationAnalytics:
    status: str  # EvaluationStatus value
    metrics: list = field(default_factory=list)
    """Section 17/18: always empty this checkpoint -- no stable,
    schema-defined, runtime-readable evaluation artifact exists (see the
    service module docstring for the evidence trail). Populated only by
    a future checkpoint that builds a genuine read-only adapter over a
    real artifact."""

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class ModelRunComparisonAnalytics:
    status: str  # ModelRunComparisonStatus value

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class ConfidenceAnalytics:
    status: str  # ConfidenceStatus value

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class DriversAnalytics:
    status: str  # DriversStatus value

    def as_dict(self) -> dict:
        return _as_dict(self)


@dataclass(frozen=True)
class AnalysisTrendsContext:
    """Section 22 top-level response DTO.

    `scope_country` (GEO-ANALYSIS-01H Section 9): the application's own
    real study scope this ENTIRE response is limited to -- server/
    application controlled (`domain.analysis_trends_enums.
    ANALYSIS_TRENDS_COUNTRY`), never accepted from a client query/header/
    body. Present on every response where a disease was actually
    resolved (i.e. every branch except `UNSUPPORTED_DISEASE`), so a
    frontend never has to infer what geography a trend covers."""

    status: str  # AnalysisTrendsStatus value
    disease: str | None = None
    scope_country: str | None = None
    historical_summary: HistoricalSummary | None = None
    historical_trend: HistoricalTrend | None = None
    selected_origin_analytics: SelectedOriginAnalytics | None = None
    model_evaluation: ModelEvaluationAnalytics | None = None
    model_run_comparison: ModelRunComparisonAnalytics | None = None
    confidence: ConfidenceAnalytics | None = None
    drivers: DriversAnalytics | None = None
    generated_at: str | None = None

    def as_dict(self) -> dict:
        return _as_dict(self)
