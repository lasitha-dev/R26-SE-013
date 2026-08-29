"""GEO-ANALYSIS-01/01H Section 19/30/32: pure historical-trend
aggregation tests. No repository, no fakes beyond
`make_historical_trigger_candidate` -- `build_historical_trend` takes
plain data in, plain data out.

GEO-ANALYSIS-01H replaced the original fixed MONTH-only decision (based
on pre-hardening GLOBAL corpus density) with a density-driven WEEK /
MONTH / YEAR choice derived from the real observed date span -- these
tests were rewritten accordingly, still proving the same underlying
honesty rules (deterministic, bounded zero-fill, no fabricated dates).
"""

from __future__ import annotations

from components.geospatial_tracking.domain.analysis_trends_enums import (
    HISTORICAL_COUNT_BASIS,
    HISTORICAL_TREND_MONTH_SPAN_THRESHOLD_DAYS,
    HISTORICAL_TREND_PERIOD_BASIS_MONTH,
    HISTORICAL_TREND_PERIOD_BASIS_WEEK,
    HISTORICAL_TREND_PERIOD_BASIS_YEAR,
    HISTORICAL_TREND_WEEK_SPAN_THRESHOLD_DAYS,
)
from components.geospatial_tracking.services.analysis_trends.historical_trend import build_historical_trend, choose_trend_period_basis

from ._my_area_fakes import make_historical_trigger_candidate


class TestEmptyInput:
    def test_no_candidates_returns_no_historical_data_status_and_zero_points(self):
        trend = build_historical_trend([])
        assert trend.status == "NO_HISTORICAL_DATA"
        assert trend.points == []


class TestGranularityChoiceIsSpanDriven:
    def test_short_span_uses_week(self):
        assert choose_trend_period_basis(0) == HISTORICAL_TREND_PERIOD_BASIS_WEEK
        assert choose_trend_period_basis(51) == HISTORICAL_TREND_PERIOD_BASIS_WEEK  # real Sri Lanka LSD span
        assert choose_trend_period_basis(HISTORICAL_TREND_WEEK_SPAN_THRESHOLD_DAYS - 1) == HISTORICAL_TREND_PERIOD_BASIS_WEEK

    def test_medium_span_uses_month(self):
        assert choose_trend_period_basis(HISTORICAL_TREND_WEEK_SPAN_THRESHOLD_DAYS) == HISTORICAL_TREND_PERIOD_BASIS_MONTH
        assert choose_trend_period_basis(400) == HISTORICAL_TREND_PERIOD_BASIS_MONTH
        assert choose_trend_period_basis(HISTORICAL_TREND_MONTH_SPAN_THRESHOLD_DAYS - 1) == HISTORICAL_TREND_PERIOD_BASIS_MONTH

    def test_long_span_uses_year(self):
        assert choose_trend_period_basis(HISTORICAL_TREND_MONTH_SPAN_THRESHOLD_DAYS) == HISTORICAL_TREND_PERIOD_BASIS_YEAR
        assert choose_trend_period_basis(3752) == HISTORICAL_TREND_PERIOD_BASIS_YEAR  # real Sri Lanka FMD span

    def test_deterministic_never_random(self):
        assert choose_trend_period_basis(100) == choose_trend_period_basis(100)


class TestWeekGranularity:
    def test_real_sri_lanka_lsd_shaped_corpus_uses_week_and_bounds_correctly(self):
        # Mirrors the real Sri Lanka LSD corpus shape: 2020-09-07 .. 2020-10-28 (51-day span).
        candidates = [
            make_historical_trigger_candidate(source_id="A", effective_availability_date="2020-09-07"),
            make_historical_trigger_candidate(source_id="B", effective_availability_date="2020-09-09"),
            make_historical_trigger_candidate(source_id="C", effective_availability_date="2020-09-28"),
            make_historical_trigger_candidate(source_id="D", effective_availability_date="2020-09-29"),
            make_historical_trigger_candidate(source_id="E", effective_availability_date="2020-10-28"),
        ]
        trend = build_historical_trend(candidates)
        assert trend.status == "AVAILABLE"
        assert trend.period_basis == "WEEK"
        periods = [p.period for p in trend.points]
        assert periods[0] == "2020-W37"  # ISO week containing 2020-09-07
        assert periods[-1] == "2020-W44"  # ISO week containing 2020-10-28
        assert len(periods) == len(set(periods))  # no duplicate weeks

    def test_week_counts_grouped_by_real_iso_week(self):
        candidates = [
            make_historical_trigger_candidate(source_id="A", effective_availability_date="2021-01-04"),  # Monday, W01
            make_historical_trigger_candidate(source_id="B", effective_availability_date="2021-01-06"),  # same W01
            make_historical_trigger_candidate(source_id="C", effective_availability_date="2021-01-15"),  # W02
        ]
        trend = build_historical_trend(candidates)
        by_period = {p.period: p.count for p in trend.points}
        assert by_period["2021-W01"] == 2
        assert by_period["2021-W02"] == 1


class TestMonthGranularity:
    def test_counts_grouped_by_real_month(self):
        candidates = [
            make_historical_trigger_candidate(source_id="A", effective_availability_date="2020-01-05"),
            make_historical_trigger_candidate(source_id="B", effective_availability_date="2020-01-20"),
            make_historical_trigger_candidate(source_id="C", effective_availability_date="2020-11-01"),
        ]
        trend = build_historical_trend(candidates)
        assert trend.period_basis == HISTORICAL_TREND_PERIOD_BASIS_MONTH
        by_period = {p.period: p.count for p in trend.points}
        assert by_period["2020-01"] == 2
        assert by_period["2020-11"] == 1

    def test_zero_count_period_only_inside_bounded_first_to_last_interval(self):
        # span = 209 days, safely inside the MONTH band (>= 180, < 1095)
        candidates = [
            make_historical_trigger_candidate(source_id="A", effective_availability_date="2020-01-05"),
            make_historical_trigger_candidate(source_id="B", effective_availability_date="2020-08-01"),
        ]
        trend = build_historical_trend(candidates)
        periods = [p.period for p in trend.points]
        assert periods == ["2020-01", "2020-02", "2020-03", "2020-04", "2020-05", "2020-06", "2020-07", "2020-08"]
        by_period = {p.period: p.count for p in trend.points}
        assert by_period["2020-03"] == 0

    def test_spans_a_year_boundary_correctly(self):
        # span = 231 days, safely inside the MONTH band
        candidates = [
            make_historical_trigger_candidate(source_id="A", effective_availability_date="2020-06-15"),
            make_historical_trigger_candidate(source_id="B", effective_availability_date="2021-02-01"),
        ]
        trend = build_historical_trend(candidates)
        periods = [p.period for p in trend.points]
        assert periods == ["2020-06", "2020-07", "2020-08", "2020-09", "2020-10", "2020-11", "2020-12", "2021-01", "2021-02"]


class TestYearGranularity:
    def test_real_sri_lanka_fmd_shaped_corpus_uses_year(self):
        # Mirrors the real Sri Lanka FMD corpus span: 2009-09-09 .. 2019-12-17 (~3752 days).
        candidates = [
            make_historical_trigger_candidate(source_id="A", effective_availability_date="2009-09-09"),
            make_historical_trigger_candidate(source_id="B", effective_availability_date="2012-06-15"),
            make_historical_trigger_candidate(source_id="C", effective_availability_date="2019-12-17"),
        ]
        trend = build_historical_trend(candidates)
        assert trend.period_basis == "YEAR"
        periods = [p.period for p in trend.points]
        assert periods[0] == "2009"
        assert periods[-1] == "2019"
        assert len(periods) == 11  # 2009..2019 inclusive

    def test_zero_year_only_inside_bounded_interval(self):
        candidates = [
            make_historical_trigger_candidate(source_id="A", effective_availability_date="2010-01-01"),
            make_historical_trigger_candidate(source_id="B", effective_availability_date="2020-01-01"),
        ]
        trend = build_historical_trend(candidates)
        by_period = {p.period: p.count for p in trend.points}
        assert by_period["2015"] == 0
        assert "2009" not in by_period
        assert "2021" not in by_period


class TestGeneralInvariants:
    def test_never_emits_a_period_outside_the_real_first_to_last_span(self):
        candidates = [
            make_historical_trigger_candidate(source_id="A", effective_availability_date="2020-06-01"),
            make_historical_trigger_candidate(source_id="B", effective_availability_date="2020-08-15"),
        ]
        trend = build_historical_trend(candidates)
        periods = [p.period for p in trend.points]
        assert "2020-05" not in periods
        assert "2020-09" not in periods

    def test_deterministic_repeated_call_same_input_same_output(self):
        candidates = [
            make_historical_trigger_candidate(source_id="A", effective_availability_date="2020-01-05"),
            make_historical_trigger_candidate(source_id="B", effective_availability_date="2020-02-01"),
        ]
        first = build_historical_trend(candidates)
        second = build_historical_trend(list(reversed(candidates)))
        assert [p.as_dict() for p in first.points] == [p.as_dict() for p in second.points]

    def test_every_point_carries_the_historical_source_records_count_basis(self):
        candidates = [make_historical_trigger_candidate(source_id="A", effective_availability_date="2020-01-05")]
        trend = build_historical_trend(candidates)
        assert all(p.count_basis == HISTORICAL_COUNT_BASIS for p in trend.points)

    def test_single_candidate_produces_exactly_one_point(self):
        candidates = [make_historical_trigger_candidate(source_id="A", effective_availability_date="2020-05-05")]
        trend = build_historical_trend(candidates)
        assert len(trend.points) == 1
        assert trend.points[0].count == 1

    def test_status_values_never_claim_live_or_active_outbreak(self):
        trend = build_historical_trend([make_historical_trigger_candidate()])
        for text in (trend.status, trend.period_basis, *[p.count_basis for p in trend.points]):
            lowered = str(text).lower()
            assert "live" not in lowered
            assert "active outbreak" not in lowered
            assert "current outbreak" not in lowered
