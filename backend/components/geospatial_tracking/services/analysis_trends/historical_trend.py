"""GEO-ANALYSIS-01/01H Section 6/7/11: deterministic historical-trend
aggregation over real, unique, Sri-Lanka-scoped historical source
records.

Pure functions only -- no repository access, no country filtering here
(that happens once, at the `ScientificReadPort.list_historical_trigger_
candidates(disease=..., country=ANALYSIS_TRENDS_COUNTRY)` call site in
`context_service.py`). `build_historical_trend` takes the already-scoped
`HistoricalTriggerCandidate` list and groups it by real
`effective_availability_date`, choosing WEEK/MONTH/YEAR granularity from
the REAL observed date span rather than a fixed choice -- GEO-ANALYSIS-01H
corrected the original MONTH-only decision, which was based on the
pre-hardening GLOBAL corpus density and did not fit either real
Sri-Lanka-scoped disease corpus (LSD: 51-day span; FMD: ~3752-day span).
"""

from __future__ import annotations

from datetime import date, timedelta

from ...domain.analysis_trends_enums import (
    HISTORICAL_COUNT_BASIS,
    HISTORICAL_TREND_MONTH_SPAN_THRESHOLD_DAYS,
    HISTORICAL_TREND_PERIOD_BASIS_MONTH,
    HISTORICAL_TREND_PERIOD_BASIS_WEEK,
    HISTORICAL_TREND_PERIOD_BASIS_YEAR,
    HISTORICAL_TREND_WEEK_SPAN_THRESHOLD_DAYS,
    HistoricalDataStatus,
)
from ...domain.analysis_trends_models import HistoricalTrend, HistoricalTrendPoint
from ...services.historical_trigger import HistoricalTriggerCandidate


def choose_trend_period_basis(span_days: int) -> str:
    """Deterministic, density-driven, never chosen for chart appearance
    -- see `domain/analysis_trends_enums.py`'s threshold constants for
    the real Sri-Lanka-scoped evidence behind the two cutoffs."""
    if span_days < HISTORICAL_TREND_WEEK_SPAN_THRESHOLD_DAYS:
        return HISTORICAL_TREND_PERIOD_BASIS_WEEK
    if span_days < HISTORICAL_TREND_MONTH_SPAN_THRESHOLD_DAYS:
        return HISTORICAL_TREND_PERIOD_BASIS_MONTH
    return HISTORICAL_TREND_PERIOD_BASIS_YEAR


def _parse(date_str: str) -> date:
    return date.fromisoformat(date_str)


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _iter_months(start: date, end: date) -> list[str]:
    months: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def _year_key(d: date) -> str:
    return f"{d.year:04d}"


def _iter_years(start: date, end: date) -> list[str]:
    return [str(y) for y in range(start.year, end.year + 1)]


def _week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday == 0


def _week_key(d: date) -> str:
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def _iter_week_mondays(start: date, end: date) -> list[str]:
    cursor = _week_monday(start)
    last_monday = _week_monday(end)
    keys: list[str] = []
    while cursor <= last_monday:
        keys.append(_week_key(cursor))
        cursor += timedelta(days=7)
    return keys


_PERIOD_KEY_FN = {
    HISTORICAL_TREND_PERIOD_BASIS_WEEK: _week_key,
    HISTORICAL_TREND_PERIOD_BASIS_MONTH: _month_key,
    HISTORICAL_TREND_PERIOD_BASIS_YEAR: _year_key,
}
_PERIOD_ITER_FN = {
    HISTORICAL_TREND_PERIOD_BASIS_WEEK: _iter_week_mondays,
    HISTORICAL_TREND_PERIOD_BASIS_MONTH: _iter_months,
    HISTORICAL_TREND_PERIOD_BASIS_YEAR: _iter_years,
}


def build_historical_trend(candidates: list[HistoricalTriggerCandidate]) -> HistoricalTrend:
    """Deterministic: same input candidates always produce the same
    ordered point list. Returns a `NO_HISTORICAL_DATA` trend with zero
    points when `candidates` is empty -- never a fabricated single
    zero-count point. Zero-count periods are only ever emitted strictly
    between the real first and last observed period -- never outside
    the dataset's own coverage."""
    if not candidates:
        return HistoricalTrend(status=HistoricalDataStatus.NO_HISTORICAL_DATA.value, period_basis=HISTORICAL_TREND_PERIOD_BASIS_MONTH, points=[])

    dates_sorted = sorted(_parse(c.effective_availability_date) for c in candidates)
    first_date, last_date = dates_sorted[0], dates_sorted[-1]
    span_days = (last_date - first_date).days
    period_basis = choose_trend_period_basis(span_days)
    key_fn = _PERIOD_KEY_FN[period_basis]
    iter_fn = _PERIOD_ITER_FN[period_basis]

    counts: dict[str, int] = {}
    for candidate in candidates:
        key = key_fn(_parse(candidate.effective_availability_date))
        counts[key] = counts.get(key, 0) + 1

    points = [
        HistoricalTrendPoint(period=period, count=counts.get(period, 0), count_basis=HISTORICAL_COUNT_BASIS)
        for period in iter_fn(first_date, last_date)
    ]
    return HistoricalTrend(status=HistoricalDataStatus.AVAILABLE.value, period_basis=period_basis, points=points)
