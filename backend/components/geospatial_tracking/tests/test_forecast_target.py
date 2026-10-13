"""TARGET-01..09."""

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.forecast_target import build_forecast_targets


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
        outbreak_start_date="2026/01/10",
        proxy_availability_date="2026/01/10",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        latitude=15.0,
        longitude=101.0,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def _origin(t0="2026-01-05", country="Thailand"):
    return ForecastOrigin(
        forecast_origin_id=f"ORIGIN:{country}:{t0}",
        country=country,
        t0=t0,
        temporal_mode="RETROSPECTIVE_PROXY",
    )


def test_target_01_target_at_t0_is_not_a_future_target(repo):
    repo.add_historical_record(_historical(source_record_id="H_at_t0", outbreak_start_date="2026/01/05"))
    targets = build_forecast_targets(repo, _origin(t0="2026-01-05"), disease="Lumpy skin disease")
    assert targets == []


def test_target_02_d1_target_has_lead_days_1(repo):
    repo.add_historical_record(_historical(source_record_id="H_d1", outbreak_start_date="2026/01/06"))
    targets = build_forecast_targets(repo, _origin(t0="2026-01-05"), disease="Lumpy skin disease")
    assert len(targets) == 1
    assert targets[0].lead_days == 1


def test_target_03_d7_target_has_lead_days_7(repo):
    repo.add_historical_record(_historical(source_record_id="H_d7", outbreak_start_date="2026/01/12"))
    targets = build_forecast_targets(repo, _origin(t0="2026-01-05"), disease="Lumpy skin disease")
    assert len(targets) == 1
    assert targets[0].lead_days == 7


def test_target_04_d8_excluded_from_primary_target_set(repo):
    repo.add_historical_record(_historical(source_record_id="H_d8", outbreak_start_date="2026/01/13"))
    targets = build_forecast_targets(repo, _origin(t0="2026-01-05"), disease="Lumpy skin disease")
    assert targets == []


def test_target_05_future_target_never_appears_in_same_origins_source_set(repo):
    repo.add_historical_record(_historical(source_record_id="H_d3", outbreak_start_date="2026/01/08"))
    # simulate H_d3 somehow also being in the source snapshot (defensive case)
    targets = build_forecast_targets(
        repo, _origin(t0="2026-01-05"), disease="Lumpy skin disease", source_ids_at_origin={"H_d3"}
    )
    assert targets == []


def test_target_06_same_target_appears_only_once_within_an_origin(repo):
    repo.add_historical_record(_historical(source_record_id="H_d3", outbreak_start_date="2026/01/08"))
    targets = build_forecast_targets(repo, _origin(t0="2026-01-05"), disease="Lumpy skin disease")
    target_event_ids = [t.target_event_id for t in targets]
    assert len(target_event_ids) == len(set(target_event_ids))


def test_target_07_stable_target_event_id_across_multiple_origins(repo):
    repo.add_historical_record(_historical(source_record_id="H_future", outbreak_start_date="2026/01/12"))
    origin_early = _origin(t0="2026-01-05")  # lead_days = 7
    origin_later = _origin(t0="2026-01-08")  # lead_days = 4
    targets_early = build_forecast_targets(repo, origin_early, disease="Lumpy skin disease")
    targets_later = build_forecast_targets(repo, origin_later, disease="Lumpy skin disease")
    assert len(targets_early) == 1
    assert len(targets_later) == 1
    assert targets_early[0].target_event_id == targets_later[0].target_event_id == "H_future"
    # but the target_id (origin-specific) differs
    assert targets_early[0].target_id != targets_later[0].target_id
    # and lead_days correctly differs per origin
    assert targets_early[0].lead_days == 7
    assert targets_later[0].lead_days == 4


def test_target_08_model_candidate_false_never_becomes_target(repo):
    repo.add_historical_record(
        _historical(source_record_id="H_excluded", outbreak_start_date="2026/01/08", model_candidate=False)
    )
    targets = build_forecast_targets(repo, _origin(t0="2026-01-05"), disease="Lumpy skin disease")
    assert targets == []


def test_target_09_review_medium_never_becomes_target(repo):
    repo.add_historical_record(
        _historical(
            source_record_id="H_medium", outbreak_start_date="2026/01/08",
            dedup_status=DedupStatus.REVIEW_MEDIUM.value, model_candidate=False,
        )
    )
    targets = build_forecast_targets(repo, _origin(t0="2026-01-05"), disease="Lumpy skin disease")
    assert targets == []


def test_target_09_review_low_never_becomes_target(repo):
    repo.add_historical_record(
        _historical(
            source_record_id="H_low", outbreak_start_date="2026/01/08",
            dedup_status=DedupStatus.REVIEW_LOW.value, model_candidate=False,
        )
    )
    targets = build_forecast_targets(repo, _origin(t0="2026-01-05"), disease="Lumpy skin disease")
    assert targets == []


def test_target_quality_tiers_propagated_onto_target(repo):
    # properly-prefixed id so historical_event_date derivation resolves
    # outbreak_start_date at HIGH quality (WAHIS_PDF priority) -> Tier A eligible
    from components.geospatial_tracking.domain.enums import CoordinateCollisionStatus
    from components.geospatial_tracking.services.target_quality import SPEED_ELIGIBILITY_PENDING_GEOMETRY

    record_id = "WAHIS_PDF:Event_x.pdf:000001"
    repo.add_historical_record(_historical(source_record_id=record_id, outbreak_start_date="2026/01/08"))
    targets = build_forecast_targets(
        repo, _origin(t0="2026-01-05"), disease="Lumpy skin disease",
        coordinate_collision_status_by_id={record_id: CoordinateCollisionStatus.UNIQUE_AMONG_RESOLVED.value},
    )
    assert targets[0].direction_target_tier_a_strict is True
    assert targets[0].direction_target_tier_a_resolved_only is True
    assert targets[0].coordinate_collision_status == CoordinateCollisionStatus.UNIQUE_AMONG_RESOLVED.value
    assert targets[0].speed_eligibility_status == SPEED_ELIGIBILITY_PENDING_GEOMETRY


def test_missing_collision_status_defaults_to_unknown_not_fabricated(repo):
    from components.geospatial_tracking.domain.enums import CoordinateCollisionStatus

    repo.add_historical_record(_historical(source_record_id="H_d3", outbreak_start_date="2026/01/08"))
    targets = build_forecast_targets(repo, _origin(t0="2026-01-05"), disease="Lumpy skin disease")
    assert targets[0].coordinate_collision_status == CoordinateCollisionStatus.UNKNOWN.value
    # UNKNOWN collision status is conservative — never silently Tier A
    assert targets[0].direction_target_tier_a_strict is False


def test_wrong_country_excluded(repo):
    repo.add_historical_record(_historical(source_record_id="H_sl", country="Sri Lanka", outbreak_start_date="2026/01/08"))
    targets = build_forecast_targets(repo, _origin(t0="2026-01-05", country="Thailand"), disease="Lumpy skin disease")
    assert targets == []
