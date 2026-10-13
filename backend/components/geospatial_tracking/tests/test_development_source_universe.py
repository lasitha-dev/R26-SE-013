"""Checkpoint 6B.5 Parts 1-6: validated FIT_DEVELOPMENT source universe —
DEV-SOURCE-01..09."""

from __future__ import annotations

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.stdbscan.development_source_universe import (
    REASON_HELD_OUT_ONLY_AVAILABILITY,
    REASON_MISSING_EVENT_DATE,
    REASON_MODEL_CANDIDATE_FALSE,
    REASON_SRI_LANKA,
    REASON_UNRESOLVED_DEDUP,
    build_fit_development_source_universe,
)

DISEASE = "Lumpy skin disease"


@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


def _historical(**overrides) -> HistoricalOutbreakRecord:
    fields = dict(
        source_record_id="H1",
        country="Thailand",
        disease=DISEASE,
        outbreak_start_date="2021/06/01",
        proxy_availability_date="2021/06/01",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        proxy_availability_source_field="outbreak_start_date",
        latitude=15.0,
        longitude=101.0,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def _dev_origin(**overrides) -> ForecastOrigin:
    fields = dict(
        forecast_origin_id="ORIGIN:Thailand:2021-06-01",
        country="Thailand",
        t0="2021-06-01",
        temporal_mode="RETROSPECTIVE_PROXY",
        trigger_source_ids_at_t0=["H1"],
        trigger_source_count=1,
    )
    fields.update(overrides)
    return ForecastOrigin(**fields)


def test_dev_source_01_model_candidate_false_cannot_enter(repo):
    repo.add_historical_record(_historical(model_candidate=False))
    result = build_fit_development_source_universe(repo, [_dev_origin()], disease=DISEASE)
    assert result.n_validated_sources == 0
    assert any(e.source_id == "H1" and e.reason_code == REASON_MODEL_CANDIDATE_FALSE for e in result.exclusions)


def test_dev_source_02_review_medium_cannot_enter(repo):
    repo.add_historical_record(_historical(dedup_status=DedupStatus.REVIEW_MEDIUM.value))
    result = build_fit_development_source_universe(repo, [_dev_origin()], disease=DISEASE)
    assert result.n_validated_sources == 0
    assert any(e.source_id == "H1" and e.reason_code == REASON_UNRESOLVED_DEDUP for e in result.exclusions)


def test_dev_source_03_review_low_cannot_enter(repo):
    repo.add_historical_record(_historical(dedup_status=DedupStatus.REVIEW_LOW.value))
    result = build_fit_development_source_universe(repo, [_dev_origin()], disease=DISEASE)
    assert result.n_validated_sources == 0
    assert any(e.source_id == "H1" and e.reason_code == REASON_UNRESOLVED_DEDUP for e in result.exclusions)


def test_dev_source_04_resolved_candidate_source_can_enter(repo):
    repo.add_historical_record(_historical())
    result = build_fit_development_source_universe(repo, [_dev_origin()], disease=DISEASE)
    assert result.n_validated_sources == 1
    assert result.sources[0].source_id == "H1"
    assert result.exclusions == []


def test_dev_source_05_sri_lanka_cannot_enter(repo):
    repo.add_historical_record(_historical(country="Sri Lanka"))
    origin = _dev_origin(forecast_origin_id="ORIGIN:Sri Lanka:2021-06-01", country="Sri Lanka")
    # even if somehow passed in, classify_origin_role marks this
    # SRI_LANKA_TRANSFER_CASE_STUDY, so it is not a FIT_DEVELOPMENT origin
    # at all -- the record can never be observed under any dev origin.
    result = build_fit_development_source_universe(repo, [origin], disease=DISEASE)
    assert result.n_validated_sources == 0
    assert any(e.source_id == "H1" and e.reason_code == REASON_SRI_LANKA for e in result.exclusions)


def test_dev_source_06_source_seen_only_in_held_out_origins_cannot_enter(repo):
    repo.add_historical_record(_historical(proxy_availability_date="2021/06/01"))
    held_out_origin = ForecastOrigin(
        forecast_origin_id="ORIGIN:Thailand:2024-06-01",
        country="Thailand",
        t0="2024-06-01",
        temporal_mode="RETROSPECTIVE_PROXY",
        trigger_source_ids_at_t0=["H1"],
        trigger_source_count=1,
    )
    # no FIT_DEVELOPMENT origin supplied at all -- only a held-out one
    result = build_fit_development_source_universe(repo, [held_out_origin], disease=DISEASE)
    assert result.n_validated_sources == 0
    assert any(e.source_id == "H1" and e.reason_code == REASON_HELD_OUT_ONLY_AVAILABILITY for e in result.exclusions)


def test_dev_source_07_pre_2024_biological_event_with_post_cutoff_availability_cannot_enter(repo):
    # biological event is 2021 (pre-cutoff), but the only availability
    # evidence is dated 2024+ (post-cutoff) -- must be excluded, unlike
    # Checkpoint 6B's insufficient event-date-only rule which would have
    # wrongly admitted it.
    repo.add_historical_record(
        _historical(outbreak_start_date="2021/06/01", proxy_availability_date="2024/06/01")
    )
    result = build_fit_development_source_universe(repo, [_dev_origin(t0="2021-06-01")], disease=DISEASE)
    assert result.n_validated_sources == 0
    assert any(e.source_id == "H1" and e.reason_code == REASON_HELD_OUT_ONLY_AVAILABILITY for e in result.exclusions)


def test_dev_source_08_same_source_across_many_origins_represented_once(repo):
    repo.add_historical_record(_historical(proxy_availability_date="2021/06/01"))
    origin_a = _dev_origin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", t0="2021-06-01")
    origin_b = _dev_origin(forecast_origin_id="ORIGIN:Thailand:2021-06-10", t0="2021-06-10")
    result = build_fit_development_source_universe(repo, [origin_a, origin_b], disease=DISEASE)
    assert result.n_validated_sources == 1
    src = result.sources[0]
    assert src.first_fit_origin_t0_seen == "2021-06-01"
    assert src.last_fit_origin_t0_seen == "2021-06-10"


def test_dev_source_09_availability_and_event_date_remain_separate_fields(repo):
    repo.add_historical_record(
        _historical(outbreak_start_date="2021/06/01", proxy_availability_date="2021/06/05")
    )
    result = build_fit_development_source_universe(repo, [_dev_origin(t0="2021-06-05")], disease=DISEASE)
    assert result.n_validated_sources == 1
    src = result.sources[0]
    assert src.effective_availability_date != src.cluster_event_date
    assert src.effective_availability_date == "2021-06-05"
    assert src.cluster_event_date == "2021/06/01"


def test_missing_event_date_excluded(repo):
    # valid coordinates/availability, but no derivable biological event
    # date at all (no outbreak_start_date/onset_date/event_start_date/etc.)
    repo.add_historical_record(
        _historical(outbreak_start_date=None, onset_date=None, event_start_date=None, confirmation_date=None)
    )
    result = build_fit_development_source_universe(repo, [_dev_origin()], disease=DISEASE)
    assert result.n_validated_sources == 0
    assert any(e.source_id == "H1" and e.reason_code == REASON_MISSING_EVENT_DATE for e in result.exclusions)


def test_invalid_coordinate_excluded(repo):
    repo.add_historical_record(_historical(latitude=None, longitude=None))
    result = build_fit_development_source_universe(repo, [_dev_origin()], disease=DISEASE)
    assert result.n_validated_sources == 0
    from components.geospatial_tracking.services.stdbscan.development_source_universe import REASON_INVALID_COORDINATE

    assert any(e.source_id == "H1" and e.reason_code == REASON_INVALID_COORDINATE for e in result.exclusions)


def test_exclusions_never_hidden_every_record_accounted_for(repo):
    repo.add_historical_record(_historical(source_record_id="OK1"))
    repo.add_historical_record(_historical(source_record_id="BAD1", model_candidate=False))
    result = build_fit_development_source_universe(repo, [_dev_origin(trigger_source_ids_at_t0=["OK1", "BAD1"])], disease=DISEASE)
    assert result.n_records_considered == 2
    assert result.n_validated_sources + len(result.exclusions) == 2
