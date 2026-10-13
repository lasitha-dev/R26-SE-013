"""Checkpoint 4 Part 4 / Checkpoint 4.5 Part 5: target quality tiers.

Separate eligibility concepts for different future scientific tasks — NOT
one blanket "good row" flag, because a record usable for a coarse risk
surface is not automatically trustworthy evidence for direction/speed
accuracy metrics.

    RISK_TARGET_ELIGIBLE:
        model_candidate = True
        AND dedup resolved (SINGLETON / AUTO_MERGED_HIGH / MANUALLY_ACCEPTED)
        AND valid coordinates (latitude and longitude both present)
        AND a usable historical_event_date (see historical_event_date.py)

CHECKPOINT 4.5 CORRECTION: Checkpoint 4's Tier A required a boolean
`canonical_spatial_independence is True`. That was a misleading name for
"coordinate uniqueness" (see `services/coordinate_collision.py`'s module
docstring — coordinate uniqueness is a data-quality/co-location
indicator, not proof of statistical/epidemiological independence) AND it
collapsed two genuinely different situations (a resolved candidate
sharing its coordinate with another RESOLVED outbreak, vs. sharing it
only with an UNRESOLVED REVIEW_LOW/REVIEW_MEDIUM candidate) into one
"non-independent" bucket. Tier A is now reported as TWO explicit
sensitivity variants, both computed and both reported — no choice is made
between them here, and neither is chosen later based on model
performance:

    DIRECTION_TARGET_TIER_A_STRICT:
        all of RISK_TARGET_ELIGIBLE, AND
        gps_quality == EXACT, AND
        historical_event_date_quality == HIGH, AND
        coordinate_collision_status == UNIQUE_AMONG_RESOLVED
        (excludes BOTH resolved AND unresolved coordinate collisions)

    DIRECTION_TARGET_TIER_A_RESOLVED_ONLY:
        all of RISK_TARGET_ELIGIBLE, AND
        gps_quality == EXACT, AND
        historical_event_date_quality == HIGH, AND
        coordinate_collision_status in (UNIQUE_AMONG_RESOLVED, SHARED_WITH_UNRESOLVED)
        (excludes only collisions among RESOLVED candidates — an
        unresolved-only collision does not disqualify, since that
        ambiguity has not been confirmed as a real second outbreak)

    DIRECTION_TARGET_TIER_B:
        RISK_TARGET_ELIGIBLE but not TIER_A_RESOLVED_ONLY (the less
        strict of the two variants) — usable but with weaker location/
        date evidence, retained for sensitivity analysis only.

SPEED tiers (Checkpoint 4.5 Part 10.C): computed identically to the
direction tiers for now (still no distinct evidence to justify a
different rule — see the Checkpoint 4 note this replaces), BUT every row
additionally carries `speed_eligibility_status =
"SPEED_ELIGIBILITY_PENDING_GEOMETRY"` (a constant, always this value
today). **A speed tier count must never be reported as a validated speed
sample count without this status alongside it** — source-to-target
geometry and event-level conditions have not been built yet
(master-prompt Part 10.C).

APPROXIMATE/COARSE coordinates are still excluded from BOTH Tier-A
variants by the `gps_quality == EXACT` requirement (Checkpoint 4.5 Part
4) — they may still be RISK_TARGET_ELIGIBLE and Tier B, never Tier A of
either kind.

Tier definitions here are provisional, not fabricated blindly — see
`HISTORICAL_CHRONOLOGY_AUDIT.md` for the actual counts produced by these
exact rules against the real corpus.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.enums import CoordinateCollisionStatus
from ..domain.models import HistoricalOutbreakRecord
from ..schemas import DEDUP_RESOLVED_STATUSES, GpsQuality
from .historical_event_date import derive_historical_event_date

SPEED_ELIGIBILITY_PENDING_GEOMETRY = "SPEED_ELIGIBILITY_PENDING_GEOMETRY"

_NOT_RESOLVED_COLLISION = (
    CoordinateCollisionStatus.UNIQUE_AMONG_RESOLVED.value,
    CoordinateCollisionStatus.SHARED_WITH_UNRESOLVED.value,
)


@dataclass
class TargetQualityTiers:
    source_record_id: str
    risk_target_eligible: bool
    direction_target_tier_a_strict: bool
    direction_target_tier_a_resolved_only: bool
    direction_target_tier_b: bool
    speed_target_tier_a_strict: bool
    speed_target_tier_a_resolved_only: bool
    speed_target_tier_b: bool
    speed_eligibility_status: str
    historical_event_date: str | None
    historical_event_date_quality: str
    coordinate_collision_status: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "source_record_id": self.source_record_id,
            "risk_target_eligible": self.risk_target_eligible,
            "direction_target_tier_a_strict": self.direction_target_tier_a_strict,
            "direction_target_tier_a_resolved_only": self.direction_target_tier_a_resolved_only,
            "direction_target_tier_b": self.direction_target_tier_b,
            "speed_target_tier_a_strict": self.speed_target_tier_a_strict,
            "speed_target_tier_a_resolved_only": self.speed_target_tier_a_resolved_only,
            "speed_target_tier_b": self.speed_target_tier_b,
            "speed_eligibility_status": self.speed_eligibility_status,
            "historical_event_date": self.historical_event_date,
            "historical_event_date_quality": self.historical_event_date_quality,
            "coordinate_collision_status": self.coordinate_collision_status,
            "reason": self.reason,
        }


def compute_target_quality_tiers(
    record: HistoricalOutbreakRecord,
    *,
    coordinate_collision_status: str,
) -> TargetQualityTiers:
    event = derive_historical_event_date(record)

    dedup_resolved = record.dedup_status in DEDUP_RESOLVED_STATUSES
    valid_coords = record.latitude is not None and record.longitude is not None
    usable_event_date = event.historical_event_date is not None

    risk_eligible = record.model_candidate and dedup_resolved and valid_coords and usable_event_date

    strongest_gps = record.gps_quality == GpsQuality.EXACT.value
    high_date_quality = event.historical_event_date_quality == "HIGH"
    no_collision_at_all = coordinate_collision_status == CoordinateCollisionStatus.UNIQUE_AMONG_RESOLVED.value
    no_resolved_collision = coordinate_collision_status in _NOT_RESOLVED_COLLISION

    tier_a_strict = risk_eligible and strongest_gps and high_date_quality and no_collision_at_all
    tier_a_resolved_only = risk_eligible and strongest_gps and high_date_quality and no_resolved_collision
    tier_b = risk_eligible and not tier_a_resolved_only

    reasons: list[str] = []
    if not risk_eligible:
        if not record.model_candidate:
            reasons.append("model_candidate=False")
        if not dedup_resolved:
            reasons.append(f"dedup_status={record.dedup_status} (not resolved)")
        if not valid_coords:
            reasons.append("missing coordinates")
        if not usable_event_date:
            reasons.append("no usable historical_event_date")
    else:
        if not strongest_gps:
            reasons.append(f"gps_quality={record.gps_quality} (not EXACT)")
        if not high_date_quality:
            reasons.append(f"historical_event_date_quality={event.historical_event_date_quality} (not HIGH)")
        if not no_resolved_collision:
            reasons.append(f"coordinate_collision_status={coordinate_collision_status} (resolved collision)")
        elif not no_collision_at_all:
            reasons.append(
                f"coordinate_collision_status={coordinate_collision_status} "
                "(strict tier excludes unresolved collisions too; resolved-only tier does not)"
            )
        if not reasons:
            reasons.append("meets all Tier A criteria (both strict and resolved-only)")

    return TargetQualityTiers(
        source_record_id=record.source_record_id,
        risk_target_eligible=risk_eligible,
        direction_target_tier_a_strict=tier_a_strict,
        direction_target_tier_a_resolved_only=tier_a_resolved_only,
        direction_target_tier_b=tier_b,
        speed_target_tier_a_strict=tier_a_strict,
        speed_target_tier_a_resolved_only=tier_a_resolved_only,
        speed_target_tier_b=tier_b,
        speed_eligibility_status=SPEED_ELIGIBILITY_PENDING_GEOMETRY,
        historical_event_date=event.historical_event_date,
        historical_event_date_quality=event.historical_event_date_quality,
        coordinate_collision_status=coordinate_collision_status,
        reason="; ".join(reasons),
    )
