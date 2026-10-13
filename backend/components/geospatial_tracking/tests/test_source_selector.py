"""SOURCE-01..14, DATE-01..03, DOMAIN-03..06."""

import pytest

from components.geospatial_tracking.domain.enums import RecordDomain, RecordDomainScope, ReportStatus
from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord, OutbreakEpisode
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality, ValidationMode
from components.geospatial_tracking.services.source_selector import get_eligible_sources


@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


def _historical(**overrides):
    fields = dict(
        source_record_id="H1",
        country="Thailand",
        disease="Lumpy skin disease",
        outbreak_start_date="2026/01/05",
        proxy_availability_date="2026/01/05",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        proxy_availability_source_field="outbreak_start_date",
        operational_availability_date=None,
        operational_availability_quality=AvailabilityQuality.UNKNOWN.value,
        latitude=15.0,
        longitude=101.0,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def _episode(**overrides):
    fields = dict(
        outbreak_id="EP1",
        disease="Lumpy skin disease",
        country="Thailand",
        latitude=15.0,
        longitude=101.0,
        status=ReportStatus.CONFIRMED.value,
        operational_availability_date="2026-01-05",
        operational_availability_quality=AvailabilityQuality.ACTUAL.value,
        gps_quality=GpsQuality.EXACT.value,
    )
    fields.update(overrides)
    return OutbreakEpisode(**fields)


# Every test in this file that exercises HISTORICAL data passes this scope
# explicitly (Checkpoint 4.5 Part 8: domain_scope has no default — see
# test_domain_06_domain_scope_has_no_default below).
HIST = RecordDomainScope.HISTORICAL_ONLY
LIVE = RecordDomainScope.LIVE_ONLY
BOTH = RecordDomainScope.BOTH


class TestTemporalMode:
    def test_source_01_strict_operational_excludes_historical_unknown_availability(self, repo):
        repo.add_historical_record(_historical())  # operational=UNKNOWN, only proxy documented
        result = get_eligible_sources(
            repo,
            disease="Lumpy skin disease",
            t0="2026-01-10",
            active_window_days=14,
            temporal_mode=ValidationMode.STRICT_OPERATIONAL,
            domain_scope=HIST,
        )
        assert result.sources == []

    def test_source_02_retrospective_proxy_may_use_valid_documented_proxy(self, repo):
        repo.add_historical_record(_historical())
        result = get_eligible_sources(
            repo,
            disease="Lumpy skin disease",
            t0="2026-01-10",
            active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY,
            domain_scope=HIST,
        )
        assert len(result.sources) == 1
        s = result.sources[0]
        assert s.effective_availability_date == "2026-01-05"
        assert s.availability_quality == AvailabilityQuality.EVENT_DATE_PROXY.value


class TestT0Invariants:
    def test_source_03_future_source_excluded(self, repo):
        repo.add_historical_record(_historical(outbreak_start_date="2026/01/20", proxy_availability_date="2026/01/20"))
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert result.sources == []

    def test_source_04_source_exactly_at_t0_allowed(self, repo):
        repo.add_historical_record(_historical(outbreak_start_date="2026/01/10", proxy_availability_date="2026/01/10"))
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert len(result.sources) == 1

    def test_source_05_source_before_active_window_excluded(self, repo):
        # t0=2026-01-10, window=14 days -> window_start=2025-12-27
        repo.add_historical_record(_historical(outbreak_start_date="2025/12/20", proxy_availability_date="2025/12/20"))
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert result.sources == []

    def test_source_06_source_exactly_on_window_boundary_is_allowed(self, repo):
        # window_start = t0 - active_window_days, inclusive by documented convention
        repo.add_historical_record(_historical(outbreak_start_date="2025/12/27", proxy_availability_date="2025/12/27"))
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert len(result.sources) == 1
        assert result.sources[0].effective_availability_date == "2025-12-27"

    def test_t0_invariant_holds_across_a_batch(self, repo):
        for i, day in enumerate(["2025/12/20", "2025/12/28", "2026/01/05", "2026/01/10", "2026/01/15"]):
            repo.add_historical_record(
                _historical(source_record_id=f"H{i}", outbreak_start_date=day, proxy_availability_date=day)
            )
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        from datetime import date

        t0 = date(2026, 1, 10)
        window_start = date(2025, 12, 27)
        for s in result.sources:
            d = date.fromisoformat(s.effective_availability_date)
            assert window_start <= d <= t0


class TestDiseaseAndCoordinateFilters:
    def test_source_07_wrong_disease_excluded(self, repo):
        repo.add_historical_record(_historical(disease="Foot and mouth disease"))
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert result.sources == []

    def test_source_07_disease_name_variants_still_match(self, repo):
        # WAHIS-style vs CSV-style spelling of the same disease
        repo.add_historical_record(_historical(disease="Lumpy skin disease virus (Inf. with)"))
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert len(result.sources) == 1

    def test_source_08_invalid_gps_excluded(self, repo):
        repo.add_historical_record(_historical(latitude=None, longitude=None))
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert result.sources == []

    def test_source_17_unknown_gps_precision_with_valid_coordinates_is_not_excluded(self, repo):
        # UNKNOWN precision label != invalid coordinates.
        repo.add_historical_record(_historical(gps_quality=GpsQuality.UNKNOWN.value))
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert len(result.sources) == 1
        assert result.sources[0].gps_quality == GpsQuality.UNKNOWN.value


class TestModelCandidateHardGate:
    def test_source_09_unresolved_medium_excluded(self, repo):
        repo.add_historical_record(
            _historical(dedup_status=DedupStatus.REVIEW_MEDIUM.value, model_candidate=False)
        )
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert result.sources == []

    def test_source_10_unresolved_low_excluded(self, repo):
        repo.add_historical_record(
            _historical(dedup_status=DedupStatus.REVIEW_LOW.value, model_candidate=False)
        )
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert result.sources == []

    def test_source_11_model_candidate_false_excluded_regardless_of_dqs(self, repo):
        # A record that LOOKS resolved (dedup_status says AUTO_MERGED_HIGH)
        # but has model_candidate explicitly False must still be excluded —
        # the gate checks model_candidate directly, never a quality proxy.
        repo.add_historical_record(
            _historical(dedup_status=DedupStatus.AUTO_MERGED_HIGH.value, model_candidate=False)
        )
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert result.sources == []

    def test_source_11_high_dqs_never_consulted(self, repo):
        # Structural proof: the selector module never imports quality.py
        # or touches a `.dqs` attribute, and EligibleSource carries no dqs
        # field — there is no code path through which a DQS value could
        # influence eligibility. (Behavioral proof is
        # test_source_11_model_candidate_false_excluded_regardless_of_dqs
        # above: a record that otherwise looks fully resolved is still
        # excluded once model_candidate=False.)
        import dataclasses
        import inspect

        from components.geospatial_tracking.services import source_selector
        from components.geospatial_tracking.services.source_selector import EligibleSource

        src = inspect.getsource(source_selector)
        assert "compute_quality" not in src
        assert "data_processing.quality" not in src
        assert ".dqs" not in src

        field_names = {f.name for f in dataclasses.fields(EligibleSource)}
        assert "dqs" not in field_names


class TestCountryScopeAndMultipleResults:
    def test_source_12_country_filter_works_but_is_not_hardcoded(self, repo):
        repo.add_historical_record(_historical(source_record_id="H_TH", country="Thailand"))
        repo.add_historical_record(_historical(source_record_id="H_SL", country="Sri Lanka"))
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope="Sri Lanka", domain_scope=HIST,
        )
        assert [s.source_id for s in result.sources] == ["H_SL"]
        # the selector code itself never references "Thailand"/"Sri Lanka" literally
        from components.geospatial_tracking.services import source_selector
        import inspect

        src = inspect.getsource(source_selector)
        assert "Thailand" not in src
        assert "Sri Lanka" not in src

    def test_source_13_multiple_eligible_outbreaks_all_returned(self, repo):
        for i in range(5):
            repo.add_historical_record(_historical(source_record_id=f"H{i}"))
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert len(result.sources) == 5

    def test_source_14_no_st_dbscan_or_clustering_dependency(self):
        from components.geospatial_tracking.services import source_selector
        import inspect

        src = inspect.getsource(source_selector)
        for forbidden in ("dbscan", "sklearn", "cluster"):
            assert forbidden not in src.lower()


class TestLiveDomain:
    def test_live_episode_can_be_eligible_source(self, repo):
        repo.add_outbreak_episode(_episode())
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.STRICT_OPERATIONAL, domain_scope=LIVE,
        )
        assert len(result.sources) == 1
        assert result.sources[0].record_domain == RecordDomain.LIVE_OPERATIONAL_RECORD.value

    def test_live_episode_without_accepted_confirmed_status_excluded(self, repo):
        repo.add_outbreak_episode(_episode(status=ReportStatus.SUBMITTED.value))
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.STRICT_OPERATIONAL, domain_scope=LIVE,
        )
        assert result.sources == []


class TestDateSemantics:
    def test_date_01_biological_date_never_replaces_operational_date(self, repo):
        # A record with a biological date INSIDE the window but no real
        # operational evidence must not sneak in under STRICT_OPERATIONAL
        # via its outbreak_start_date.
        repo.add_historical_record(
            _historical(
                outbreak_start_date="2026/01/08",  # biological — well within window
                operational_availability_date=None,
                operational_availability_quality=AvailabilityQuality.UNKNOWN.value,
            )
        )
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.STRICT_OPERATIONAL, domain_scope=HIST,
        )
        assert result.sources == []

    def test_date_02_proxy_never_becomes_actual(self, repo):
        repo.add_historical_record(_historical())  # proxy_availability_quality=EVENT_DATE_PROXY
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert len(result.sources) == 1
        assert result.sources[0].availability_quality != AvailabilityQuality.ACTUAL.value
        assert result.sources[0].availability_quality == AvailabilityQuality.EVENT_DATE_PROXY.value

    def test_date_03_temporal_mode_propagates_to_result_metadata(self, repo):
        repo.add_historical_record(_historical())
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert result.temporal_mode == ValidationMode.RETROSPECTIVE_PROXY.value
        result2 = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.STRICT_OPERATIONAL, domain_scope=HIST,
        )
        assert result2.temporal_mode == ValidationMode.STRICT_OPERATIONAL.value


def test_active_window_days_must_be_passed_explicitly():
    import inspect

    sig = inspect.signature(get_eligible_sources)
    assert sig.parameters["active_window_days"].default is inspect.Parameter.empty


class TestParameterValidation:
    def test_time_01_negative_active_window_days_rejected(self, repo):
        with pytest.raises(ValueError, match="active_window_days must be >= 0"):
            get_eligible_sources(
                repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=-1,
                temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
            )

    def test_active_window_days_zero_means_same_day_only(self, repo):
        repo.add_historical_record(_historical(outbreak_start_date="2026/01/10", proxy_availability_date="2026/01/10"))
        repo.add_historical_record(
            _historical(source_record_id="H_off_by_one", outbreak_start_date="2026/01/09", proxy_availability_date="2026/01/09")
        )
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=0,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert [s.source_id for s in result.sources] == ["H1"]


class TestAvailRegressionLabels:
    """AVAIL-05/06 — explicit-labeled regression coverage; the underlying
    behavior is also covered by TestTemporalMode above and by the
    Checkpoint 3.5 real-data smoke test (services not exercised here)."""

    def test_avail_05_historical_retrospective_proxy_behavior_unchanged(self, repo):
        repo.add_historical_record(_historical())
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=HIST,
        )
        assert len(result.sources) == 1
        assert result.sources[0].availability_quality == AvailabilityQuality.EVENT_DATE_PROXY.value

    def test_avail_06_strict_operational_historical_smoke_query_still_returns_zero(self, repo):
        repo.add_historical_record(_historical())
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.STRICT_OPERATIONAL, domain_scope=HIST,
        )
        assert result.sources == []


class TestRecordDomainScope:
    """DOMAIN-03/04/05/06 (Checkpoint 4 Part 0B, Checkpoint 4.5 Part 8)."""

    def test_domain_03_historical_only_excludes_live_domain(self, repo):
        repo.add_historical_record(_historical())
        repo.add_outbreak_episode(_episode())
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=RecordDomainScope.HISTORICAL_ONLY,
        )
        assert len(result.sources) == 1
        assert result.sources[0].record_domain == RecordDomain.HISTORICAL_RESEARCH_RECORD.value
        assert result.domain_scope == RecordDomainScope.HISTORICAL_ONLY.value

    def test_domain_04_live_only_excludes_historical_domain(self, repo):
        repo.add_historical_record(_historical())
        repo.add_outbreak_episode(_episode())
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            # STRICT_OPERATIONAL so the live episode (which has ACTUAL evidence) is eligible
            temporal_mode=ValidationMode.STRICT_OPERATIONAL, domain_scope=RecordDomainScope.LIVE_ONLY,
        )
        assert len(result.sources) == 1
        assert result.sources[0].record_domain == RecordDomain.LIVE_OPERATIONAL_RECORD.value
        assert result.domain_scope == RecordDomainScope.LIVE_ONLY.value

    def test_domain_05_diagnostic_caller_may_explicitly_request_both(self, repo):
        # BOTH remains available for an explicit diagnostic caller — but
        # only when passed explicitly, never as an implicit default (see
        # test_domain_06 below).
        repo.add_historical_record(_historical())
        repo.add_outbreak_episode(_episode())
        result = get_eligible_sources(
            repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, domain_scope=RecordDomainScope.BOTH,
        )
        assert result.domain_scope == RecordDomainScope.BOTH.value
        # both domains queried, both records eligible on their own terms
        # (the live episode's ACTUAL evidence qualifies it regardless of
        # temporal_mode — see source_selector._live_eligible)
        assert len(result.sources) == 2
        domains = {s.record_domain for s in result.sources}
        assert domains == {RecordDomain.HISTORICAL_RESEARCH_RECORD.value, RecordDomain.LIVE_OPERATIONAL_RECORD.value}

        # historical replay (services/forecast_origin.py / list_historical_trigger_candidates)
        # must pass HISTORICAL_ONLY explicitly — verified structurally.
        from components.geospatial_tracking.services import forecast_origin
        import inspect

        src = inspect.getsource(forecast_origin)
        assert "RecordDomainScope.HISTORICAL_ONLY" in src

    def test_domain_06_domain_scope_has_no_default(self):
        # Checkpoint 4.5 Part 8: accidental omission must not silently mix
        # historical and live domains — domain_scope is now a required
        # keyword argument with no default value at all.
        import inspect

        sig = inspect.signature(get_eligible_sources)
        assert sig.parameters["domain_scope"].default is inspect.Parameter.empty

    def test_domain_06_omitting_domain_scope_raises(self, repo):
        repo.add_historical_record(_historical())
        with pytest.raises(TypeError):
            get_eligible_sources(
                repo, disease="Lumpy skin disease", t0="2026-01-10", active_window_days=14,
                temporal_mode=ValidationMode.RETROSPECTIVE_PROXY,
            )


class TestCountryScopeIsReplayBoundaryNotBiologicalBarrier:
    """COUNTRY-01 (Checkpoint 4.5 Part 9)."""

    def test_country_01_country_scope_documented_as_replay_boundary_not_disease_barrier(self):
        import inspect

        from components.geospatial_tracking.services import source_selector

        src = inspect.getsource(source_selector.get_eligible_sources)
        assert "surveillance" in src.lower() or "replay boundary" in src.lower()
        assert "does not imply" in src.lower() or "not a biological" in src.lower()
        # no cross-border modeling logic exists — the function's country
        # filter is a plain repository pass-through, never a disease-
        # transmission rule (see test_source_12_country_filter_works_but_is_not_hardcoded
        # for the complementary "no hardcoded country names" proof).
        assert "cross-border" not in src.lower() or "not implemented" in src.lower() or "no cross-border" in src.lower()
