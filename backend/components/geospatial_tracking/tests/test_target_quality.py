"""TIER-01..04."""

from components.geospatial_tracking.domain.enums import CoordinateCollisionStatus
from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.schemas import DedupStatus, GpsQuality
from components.geospatial_tracking.services.target_quality import (
    SPEED_ELIGIBILITY_PENDING_GEOMETRY,
    compute_target_quality_tiers,
)

UNIQUE = CoordinateCollisionStatus.UNIQUE_AMONG_RESOLVED.value
SHARED_RESOLVED = CoordinateCollisionStatus.SHARED_WITH_RESOLVED.value
SHARED_UNRESOLVED = CoordinateCollisionStatus.SHARED_WITH_UNRESOLVED.value
SHARED_BOTH = CoordinateCollisionStatus.SHARED_WITH_BOTH.value


def _record(**overrides):
    fields = dict(
        source_record_id="WAHIS_PDF:Event_3473.pdf:000002",
        outbreak_start_date="2020/09/07",
        latitude=9.7151701,
        longitude=80.0668497,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def test_both_tier_a_variants_true_when_fully_unique():
    tiers = compute_target_quality_tiers(_record(), coordinate_collision_status=UNIQUE)
    assert tiers.risk_target_eligible is True
    assert tiers.direction_target_tier_a_strict is True
    assert tiers.direction_target_tier_a_resolved_only is True
    assert tiers.direction_target_tier_b is False


def test_tier_01_strict_tier_a_excludes_resolved_coordinate_collision():
    tiers = compute_target_quality_tiers(_record(), coordinate_collision_status=SHARED_RESOLVED)
    assert tiers.direction_target_tier_a_strict is False
    assert tiers.direction_target_tier_a_resolved_only is False  # resolved collision excludes both
    assert tiers.direction_target_tier_b is True


def test_tier_02_strict_tier_a_excludes_unresolved_collision_ambiguity():
    # Documented strict rule: SHARED_WITH_UNRESOLVED is excluded from
    # STRICT (ambiguity is not tolerated there) but NOT from
    # RESOLVED_ONLY (the ambiguity hasn't been confirmed as a real second
    # outbreak, so the resolved-only sensitivity variant tolerates it).
    tiers = compute_target_quality_tiers(_record(), coordinate_collision_status=SHARED_UNRESOLVED)
    assert tiers.direction_target_tier_a_strict is False
    assert tiers.direction_target_tier_a_resolved_only is True
    assert tiers.direction_target_tier_b is False  # meets resolved-only Tier A, so not Tier B


def test_tier_03_resolved_only_sensitivity_tier_behaves_separately_from_strict():
    # SHARED_WITH_BOTH: resolved collision present -> excluded from BOTH variants.
    tiers = compute_target_quality_tiers(_record(), coordinate_collision_status=SHARED_BOTH)
    assert tiers.direction_target_tier_a_strict is False
    assert tiers.direction_target_tier_a_resolved_only is False
    assert tiers.direction_target_tier_b is True

    # Cross-check: strict and resolved-only diverge specifically (and only)
    # on SHARED_WITH_UNRESOLVED — proving they are genuinely separate rules,
    # not the same computation under two names.
    unresolved_tiers = compute_target_quality_tiers(_record(), coordinate_collision_status=SHARED_UNRESOLVED)
    assert unresolved_tiers.direction_target_tier_a_strict != unresolved_tiers.direction_target_tier_a_resolved_only


def test_tier_04_speed_tiers_carry_pending_geometry_status_not_falsely_validated():
    tiers = compute_target_quality_tiers(_record(), coordinate_collision_status=UNIQUE)
    assert tiers.speed_target_tier_a_strict is True  # same candidate criteria as direction, for now
    assert tiers.speed_eligibility_status == SPEED_ELIGIBILITY_PENDING_GEOMETRY
    assert tiers.speed_eligibility_status == "SPEED_ELIGIBILITY_PENDING_GEOMETRY"
    # every record gets this status, regardless of tier outcome — a speed
    # tier count is never presented as validated without it
    unresolved_tiers = compute_target_quality_tiers(_record(), coordinate_collision_status=SHARED_RESOLVED)
    assert unresolved_tiers.speed_eligibility_status == SPEED_ELIGIBILITY_PENDING_GEOMETRY


def test_tier_b_when_gps_approximate():
    record = _record(gps_quality=GpsQuality.APPROXIMATE.value)
    tiers = compute_target_quality_tiers(record, coordinate_collision_status=UNIQUE)
    assert tiers.risk_target_eligible is True
    assert tiers.direction_target_tier_a_strict is False  # APPROXIMATE never enters Tier A
    assert tiers.direction_target_tier_a_resolved_only is False
    assert tiers.direction_target_tier_b is True


def test_tier_b_when_event_date_quality_medium():
    record = _record(outbreak_start_date=None, event_start_date="2020/09/01")
    tiers = compute_target_quality_tiers(record, coordinate_collision_status=UNIQUE)
    assert tiers.historical_event_date_quality == "MEDIUM"
    assert tiers.direction_target_tier_a_strict is False
    assert tiers.direction_target_tier_a_resolved_only is False
    assert tiers.direction_target_tier_b is True


def test_not_risk_eligible_when_model_candidate_false():
    record = _record(model_candidate=False)
    tiers = compute_target_quality_tiers(record, coordinate_collision_status=UNIQUE)
    assert tiers.risk_target_eligible is False
    assert tiers.direction_target_tier_a_strict is False
    assert tiers.direction_target_tier_b is False  # never Tier B either — not eligible at all


def test_not_risk_eligible_when_dedup_unresolved():
    record = _record(dedup_status=DedupStatus.REVIEW_MEDIUM.value)
    tiers = compute_target_quality_tiers(record, coordinate_collision_status=UNIQUE)
    assert tiers.risk_target_eligible is False


def test_not_risk_eligible_when_missing_coordinates():
    record = _record(latitude=None, longitude=None)
    tiers = compute_target_quality_tiers(
        record, coordinate_collision_status=CoordinateCollisionStatus.MISSING_COORDINATE.value
    )
    assert tiers.risk_target_eligible is False


def test_not_risk_eligible_when_no_usable_event_date():
    record = _record(outbreak_start_date=None, event_start_date=None)
    tiers = compute_target_quality_tiers(record, coordinate_collision_status=UNIQUE)
    assert tiers.risk_target_eligible is False
    assert tiers.historical_event_date is None
