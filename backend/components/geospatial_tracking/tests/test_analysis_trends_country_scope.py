"""GEO-ANALYSIS-01H Sections 16-19: Sri Lanka study-scope hardening
tests.

Two layers of proof:

  1. Unit-level (fakes): `AnalysisTrendsService` always passes
     `country=ANALYSIS_TRENDS_COUNTRY` ("Sri Lanka") to both scientific
     reads, and the selected-origin firewall rejects any `origin_id` not
     present in the already-loaded, country-scoped `origins` ledger --
     by real set membership, never a string-prefix parse.
  2. Integration-level (a real, ephemeral, tmp_path-backed
     `SQLiteOutbreakRepository`, mirroring `test_historical_trigger.py`'s
     own `repo` fixture convention): a genuine end-to-end proof that a
     Sri Lanka record is included and Afghanistan/India records are
     excluded from `AnalysisTrendsService`'s own historical summary/trend
     -- exercising the REAL `list_historical_trigger_candidates`/
     `build_forecast_origin_ledger` functions, never mocked out.
"""

from __future__ import annotations

import pytest

from components.geospatial_tracking.domain.analysis_trends_enums import ANALYSIS_TRENDS_COUNTRY
from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.analysis_trends.context_service import AnalysisTrendsService
from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import RuntimeAnalysisError10A
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin, build_forecast_origin_ledger
from components.geospatial_tracking.services.historical_trigger import list_historical_trigger_candidates

from ._my_area_fakes import FakeScientificReadPort, make_historical_trigger_candidate

# ---------------------------------------------------------------------------
# Unit-level: fakes prove the service ALWAYS requests Sri Lanka.
# ---------------------------------------------------------------------------


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(forecast_origin_id="ORIGIN:Sri Lanka:2020-01-05", country="Sri Lanka", t0="2020-01-05", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["A"], trigger_source_count=1)
    fields.update(overrides)
    return ForecastOrigin(**fields)


class TestServiceAlwaysRequestsSriLanka:
    def test_historical_candidates_requested_with_sri_lanka_country(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert port.historical_candidates_calls == [{"disease": "Lumpy skin disease", "country": "Sri Lanka"}]

    def test_origins_requested_with_sri_lanka_country(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert port.list_origins_calls == [{"disease": "Lumpy skin disease", "country": "Sri Lanka"}]

    def test_never_requests_country_none(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert port.historical_candidates_calls[0]["country"] is not None
        assert port.list_origins_calls[0]["country"] is not None

    def test_fmd_also_requested_with_sri_lanka_country(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate(disease="Foot and mouth disease")], origins=[])
        AnalysisTrendsService(port).get_analysis_trends(disease="fmd")
        assert port.historical_candidates_calls == [{"disease": "Foot and mouth disease", "country": "Sri Lanka"}]
        assert port.list_origins_calls == [{"disease": "Foot and mouth disease", "country": "Sri Lanka"}]


class TestSelectedOriginCountryFirewall:
    def test_real_sri_lanka_origin_accepted(self):
        from ._my_area_fakes import make_geospatial_snapshot

        snapshot = make_geospatial_snapshot(forecast_origin_id="ORIGIN:Sri Lanka:2020-01-05", t0="2020-01-05")
        port = FakeScientificReadPort(
            historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()],
            analyses_by_origin_id={"ORIGIN:Sri Lanka:2020-01-05": snapshot},
        )
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="ORIGIN:Sri Lanka:2020-01-05")
        assert ctx.status == "OK"
        assert ctx.selected_origin_analytics.status == "AVAILABLE"

    def test_real_foreign_country_origin_rejected_as_origin_not_found(self):
        # The ledger the service actually loaded is Sri-Lanka-scoped
        # (only `_origin()` is present) -- a real Afghanistan origin id
        # simply never appears in it.
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="ORIGIN:Afghanistan:2022-05-29")
        assert ctx.status == "ORIGIN_NOT_FOUND"

    def test_foreign_country_origin_does_not_call_get_origin_analysis(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="ORIGIN:Afghanistan:2022-05-29")
        assert port.analysis_calls == []

    def test_real_india_origin_also_rejected(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="ORIGIN:India:2021-03-10")
        assert ctx.status == "ORIGIN_NOT_FOUND"

    def test_no_origin_id_performs_no_selected_origin_analysis(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id=None)
        assert ctx.selected_origin_analytics is None
        assert port.analysis_calls == []

    def test_firewall_uses_real_ledger_membership_not_string_prefix_parsing(self):
        # A fake id that LOOKS like a Sri Lanka id by string convention
        # but was never actually returned by list_origins must still be
        # rejected -- proves this is a set-membership check against the
        # real loaded ledger, never `origin_id.startswith("ORIGIN:Sri Lanka:")`.
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="ORIGIN:Sri Lanka:1899-01-01")
        assert ctx.status == "ORIGIN_NOT_FOUND"
        assert port.analysis_calls == []

    def test_ledger_origin_with_unconventional_id_shape_is_still_accepted(self):
        # The inverse proof: an origin id that does NOT follow the
        # "ORIGIN:<country>:<date>" string convention at all is still
        # accepted purely because it's a real member of the loaded
        # ledger -- confirms authorization is ledger membership, not
        # string parsing, in both directions.
        from ._my_area_fakes import make_geospatial_snapshot

        weird_id = "not-a-conventional-origin-id-at-all"
        snapshot = make_geospatial_snapshot(forecast_origin_id=weird_id, t0="2020-01-05")
        port = FakeScientificReadPort(
            historical_candidates=[make_historical_trigger_candidate()],
            origins=[_origin(forecast_origin_id=weird_id)],
            analyses_by_origin_id={weird_id: snapshot},
        )
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id=weird_id)
        assert ctx.status == "OK"
        assert ctx.selected_origin_analytics.status == "AVAILABLE"

    def test_wrong_disease_sri_lanka_origin_rejected(self):
        # An origin real for LSD's Sri-Lanka-scoped ledger is not
        # present in FMD's own (different) Sri-Lanka-scoped ledger.
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate(disease="Foot and mouth disease")], origins=[])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="fmd", origin_id="ORIGIN:Sri Lanka:2020-01-05")
        # FMD model is not ready, so the model-readiness gate answers
        # first (matching the frozen 10A gate ordering) -- still an
        # honest, non-OK outcome, never a silent cross-disease reuse.
        assert ctx.status == "PARTIAL"
        assert ctx.selected_origin_analytics.status == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"

    def test_nonexistent_origin_rejected(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="ORIGIN:GHOST:1999-01-01")
        assert ctx.status == "ORIGIN_NOT_FOUND"


class TestResponseScopeProvenance:
    def test_response_explicitly_states_sri_lanka_scope(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.scope_country == "Sri Lanka"
        assert ctx.scope_country == ANALYSIS_TRENDS_COUNTRY

    def test_scope_present_even_on_no_historical_data_response(self):
        port = FakeScientificReadPort(historical_candidates=[], origins=[])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.scope_country == "Sri Lanka"

    def test_scope_present_on_origin_not_found_response(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="ORIGIN:Afghanistan:2022-05-29")
        assert ctx.scope_country == "Sri Lanka"

    def test_scope_absent_only_for_unsupported_disease_where_no_scoped_read_was_attempted(self):
        port = FakeScientificReadPort()
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="rabies")
        assert ctx.status == "UNSUPPORTED_DISEASE"
        assert ctx.scope_country is None


# ---------------------------------------------------------------------------
# Integration-level: a REAL, ephemeral SQLite repository -- proves actual
# country filtering, not merely that the right kwarg was passed.
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


def _historical(**overrides) -> HistoricalOutbreakRecord:
    fields = dict(
        source_record_id="H1", country="Sri Lanka", disease="Lumpy skin disease",
        outbreak_start_date="2020-09-07", proxy_availability_date="2020-09-07",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        latitude=7.0, longitude=80.0, gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value, model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


class _RealPortOverRepo:
    """A minimal `ScientificReadPort`-shaped adapter over a real,
    ephemeral repository -- exercises the REAL frozen
    `list_historical_trigger_candidates`/`build_forecast_origin_ledger`
    functions directly, never a fake/mock of them."""

    def __init__(self, repo):
        self._repo = repo

    def list_origins(self, *, disease, country=None):
        return build_forecast_origin_ledger(self._repo, disease=disease, country_scope=country)

    def get_origin_trigger_locations(self, origin):
        return []

    def get_origin_analysis(self, forecast_origin_id, *, disease):
        raise RuntimeAnalysisError10A("ORIGIN_NOT_FOUND", "not exercised by this integration test")

    def list_historical_trigger_candidates(self, *, disease, country=None):
        return list_historical_trigger_candidates(self._repo, disease=disease, country_scope=country)


class TestRealRepositoryCountryFiltering:
    def test_sri_lanka_record_included_foreign_records_excluded(self, repo):
        repo.add_historical_record(_historical(source_record_id="LK1", country="Sri Lanka", outbreak_start_date="2020-09-07", proxy_availability_date="2020-09-07"))
        repo.add_historical_record(_historical(source_record_id="AF1", country="Afghanistan", outbreak_start_date="2022-05-29", proxy_availability_date="2022-05-29"))
        repo.add_historical_record(_historical(source_record_id="IN1", country="India", outbreak_start_date="2021-03-10", proxy_availability_date="2021-03-10"))

        ctx = AnalysisTrendsService(_RealPortOverRepo(repo)).get_analysis_trends(disease="lsd")

        assert ctx.historical_summary.historical_source_count == 1
        assert ctx.historical_summary.first_observed_date == "2020-09-07"
        assert ctx.historical_summary.last_observed_date == "2020-09-07"

    def test_mixed_country_input_does_not_affect_sri_lanka_count(self, repo):
        repo.add_historical_record(_historical(source_record_id="LK1", country="Sri Lanka", outbreak_start_date="2020-09-07", proxy_availability_date="2020-09-07"))
        repo.add_historical_record(_historical(source_record_id="LK2", country="Sri Lanka", outbreak_start_date="2020-09-09", proxy_availability_date="2020-09-09"))
        repo.add_historical_record(_historical(source_record_id="AF1", country="Afghanistan", outbreak_start_date="2022-05-29", proxy_availability_date="2022-05-29"))

        ctx = AnalysisTrendsService(_RealPortOverRepo(repo)).get_analysis_trends(disease="lsd")

        assert ctx.historical_summary.historical_source_count == 2

    def test_forecast_origin_count_is_sri_lanka_only(self, repo):
        repo.add_historical_record(_historical(source_record_id="LK1", country="Sri Lanka", outbreak_start_date="2020-09-07", proxy_availability_date="2020-09-07"))
        repo.add_historical_record(_historical(source_record_id="AF1", country="Afghanistan", outbreak_start_date="2022-05-29", proxy_availability_date="2022-05-29"))

        ctx = AnalysisTrendsService(_RealPortOverRepo(repo)).get_analysis_trends(disease="lsd")

        assert ctx.historical_summary.forecast_origin_count == 1

    def test_foreign_dates_never_extend_the_trend_bounds(self, repo):
        # A foreign record's date is OUTSIDE the Sri Lanka date range --
        # if country filtering leaked, it would incorrectly widen the
        # bounded trend interval.
        repo.add_historical_record(_historical(source_record_id="LK1", country="Sri Lanka", outbreak_start_date="2020-09-07", proxy_availability_date="2020-09-07"))
        repo.add_historical_record(_historical(source_record_id="LK2", country="Sri Lanka", outbreak_start_date="2020-09-09", proxy_availability_date="2020-09-09"))
        repo.add_historical_record(_historical(source_record_id="AF1", country="Afghanistan", outbreak_start_date="2010-01-01", proxy_availability_date="2010-01-01"))
        repo.add_historical_record(_historical(source_record_id="IN1", country="India", outbreak_start_date="2030-01-01", proxy_availability_date="2030-01-01"))

        ctx = AnalysisTrendsService(_RealPortOverRepo(repo)).get_analysis_trends(disease="lsd")

        assert ctx.historical_summary.first_observed_date == "2020-09-07"
        assert ctx.historical_summary.last_observed_date == "2020-09-09"
        periods = [p.period for p in ctx.historical_trend.points]
        assert all("2010" not in p and "2030" not in p for p in periods)

    def test_trend_contains_only_sri_lanka_derived_periods(self, repo):
        repo.add_historical_record(_historical(source_record_id="LK1", country="Sri Lanka", outbreak_start_date="2020-09-07", proxy_availability_date="2020-09-07"))
        repo.add_historical_record(_historical(source_record_id="AF1", country="Afghanistan", outbreak_start_date="2022-05-29", proxy_availability_date="2022-05-29"))

        ctx = AnalysisTrendsService(_RealPortOverRepo(repo)).get_analysis_trends(disease="lsd")

        # Only 1 real Sri Lanka record -> a single-period trend, never
        # stretching out to cover the excluded Afghanistan date.
        assert ctx.historical_trend.status == "AVAILABLE"
        assert len(ctx.historical_trend.points) == 1

    def test_no_sri_lanka_records_but_foreign_records_exist_is_honestly_no_historical_data(self, repo):
        repo.add_historical_record(_historical(source_record_id="AF1", country="Afghanistan", outbreak_start_date="2022-05-29", proxy_availability_date="2022-05-29"))
        repo.add_historical_record(_historical(source_record_id="IN1", country="India", outbreak_start_date="2021-03-10", proxy_availability_date="2021-03-10"))

        ctx = AnalysisTrendsService(_RealPortOverRepo(repo)).get_analysis_trends(disease="lsd")

        # A populated GLOBAL corpus must never be reported as "available"
        # Sri Lanka evidence -- this is the exact original defect.
        assert ctx.status == "NO_HISTORICAL_DATA"
        assert ctx.historical_summary.historical_source_count == 0
