"""DISCOVERY-01/02/03/04."""

import inspect

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services import historical_trigger
from components.geospatial_tracking.services.historical_trigger import list_historical_trigger_candidates


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
        latitude=15.0,
        longitude=101.0,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def test_discovery_01_no_synthetic_future_t0_anywhere(repo):
    src = inspect.getsource(historical_trigger)
    assert "2999" not in src
    assert "far_future" not in src.lower()
    assert "huge_window" not in src.lower()
    assert "1_000_000" not in src
    assert "1000000" not in src


def test_discovery_02_enforces_model_candidate_and_dedup_gate(repo):
    repo.add_historical_record(_historical(source_record_id="H_good"))
    repo.add_historical_record(
        _historical(source_record_id="H_not_candidate", model_candidate=False)
    )
    repo.add_historical_record(
        _historical(
            source_record_id="H_unresolved",
            dedup_status=DedupStatus.REVIEW_MEDIUM.value,
            model_candidate=False,
        )
    )
    candidates = list_historical_trigger_candidates(repo, disease="Lumpy skin disease")
    assert [c.source_id for c in candidates] == ["H_good"]


def test_discovery_03_unresolved_records_cannot_create_trigger_candidates(repo):
    repo.add_historical_record(
        _historical(dedup_status=DedupStatus.REVIEW_LOW.value, model_candidate=False)
    )
    candidates = list_historical_trigger_candidates(repo, disease="Lumpy skin disease")
    assert candidates == []


def test_discovery_04_deterministic_across_repeated_calls(repo):
    repo.add_historical_record(_historical(source_record_id="H2", outbreak_start_date="2026/01/09", proxy_availability_date="2026/01/09"))
    repo.add_historical_record(_historical(source_record_id="H1", outbreak_start_date="2026/01/05", proxy_availability_date="2026/01/05"))
    c1 = list_historical_trigger_candidates(repo, disease="Lumpy skin disease")
    c2 = list_historical_trigger_candidates(repo, disease="Lumpy skin disease")
    assert [c.as_dict() for c in c1] == [c.as_dict() for c in c2]
    assert [c.source_id for c in c1] == ["H1", "H2"]  # sorted


def test_reports_real_effective_availability_date_not_a_placeholder(repo):
    repo.add_historical_record(_historical(outbreak_start_date="2026/01/05", proxy_availability_date="2026/01/05"))
    candidates = list_historical_trigger_candidates(repo, disease="Lumpy skin disease")
    assert candidates[0].effective_availability_date == "2026-01-05"
    assert candidates[0].availability_quality == AvailabilityQuality.EVENT_DATE_PROXY.value


def test_proxy_never_upgraded_to_actual(repo):
    repo.add_historical_record(_historical())
    candidates = list_historical_trigger_candidates(repo, disease="Lumpy skin disease")
    assert candidates[0].availability_quality != AvailabilityQuality.ACTUAL.value


def test_invalid_coordinates_excluded(repo):
    repo.add_historical_record(_historical(latitude=None, longitude=None))
    candidates = list_historical_trigger_candidates(repo, disease="Lumpy skin disease")
    assert candidates == []


def test_disease_mismatch_excluded(repo):
    repo.add_historical_record(_historical(disease="Foot and mouth disease"))
    candidates = list_historical_trigger_candidates(repo, disease="Lumpy skin disease")
    assert candidates == []


def test_country_scope_filters(repo):
    repo.add_historical_record(_historical(source_record_id="H_TH", country="Thailand"))
    repo.add_historical_record(_historical(source_record_id="H_SL", country="Sri Lanka"))
    candidates = list_historical_trigger_candidates(repo, disease="Lumpy skin disease", country_scope="Sri Lanka")
    assert [c.source_id for c in candidates] == ["H_SL"]
