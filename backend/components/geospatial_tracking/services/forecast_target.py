"""Checkpoint 4 Part 8-9: future target construction + pseudo-replication
safety.

For each forecast origin t0 (`services/forecast_origin.py`), a target is a
distinct historical record whose `historical_event_date`
(`services/historical_event_date.py` — biological/target-occurrence time,
never source availability) falls STRICTLY after t0 and within the D1-D7
primary forecast horizon:

    1 <= lead_days <= 7,  lead_days = historical_event_date - t0

A record exactly AT t0 (lead_days = 0) is a possible SOURCE, never a
target (TARGET-01). A record more than 7 days out is excluded from this
primary target set (TARGET-04) — a longer-horizon set is not built here.

Every target passes the SAME model-candidate/dedup-resolved gate as a
source (TARGET-08/09) — `REVIEW_MEDIUM`/`REVIEW_LOW`/`model_candidate =
False` records can never become scientific targets, any more than they
can become sources.

A record already present in the origin's own source snapshot is
explicitly excluded from being a target at that SAME origin (TARGET-05) —
defensive, even though in the current corpus a record's
`proxy_availability_date` and `historical_event_date` are typically the
same underlying field, so a source (date <= t0) structurally can't also
satisfy target eligibility (date > t0) against the SAME t0 today. This
guard stays in case that structural coincidence ever stops holding.

PSEUDO-REPLICATION SAFETY (Part 9): the same real future outbreak can
legitimately appear as a target from several earlier forecast origins
(that is repeated forecasting of one biological event, not several
independent events). `target_event_id` is always the record's own
canonical `source_record_id` — stable across every origin that includes
it — so later statistics can aggregate at the unique target-event level
rather than silently over-counting. `target_id` (unique per
origin+target_event_id pair) is what actually varies across origins.
Within a single origin, `target_event_id` values are unique by
construction (one row per canonical historical record).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.enums import CoordinateCollisionStatus
from ..repositories.base import OutbreakRepository
from ..schemas import DEDUP_RESOLVED_STATUSES
from .dates import parse_flexible_date
from .disease import normalize_disease
from .forecast_origin import ForecastOrigin
from .historical_event_date import derive_historical_event_date
from .target_quality import compute_target_quality_tiers

PRIMARY_HORIZON_DAYS = 7


@dataclass
class ForecastTarget:
    forecast_origin_id: str
    target_id: str
    target_event_id: str  # stable across origins — see module docstring
    historical_event_date: str
    lead_days: int
    latitude: float
    longitude: float
    gps_quality: str
    coordinate_collision_status: str
    risk_target_eligible: bool
    direction_target_tier_a_strict: bool
    direction_target_tier_a_resolved_only: bool
    direction_target_tier_b: bool
    speed_target_tier_a_strict: bool
    speed_target_tier_a_resolved_only: bool
    speed_target_tier_b: bool
    speed_eligibility_status: str
    country: str | None
    disease: str | None
    dedup_status: str
    model_candidate: bool

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id,
            "target_id": self.target_id,
            "target_event_id": self.target_event_id,
            "historical_event_date": self.historical_event_date,
            "lead_days": self.lead_days,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "gps_quality": self.gps_quality,
            "coordinate_collision_status": self.coordinate_collision_status,
            "risk_target_eligible": self.risk_target_eligible,
            "direction_target_tier_a_strict": self.direction_target_tier_a_strict,
            "direction_target_tier_a_resolved_only": self.direction_target_tier_a_resolved_only,
            "direction_target_tier_b": self.direction_target_tier_b,
            "speed_target_tier_a_strict": self.speed_target_tier_a_strict,
            "speed_target_tier_a_resolved_only": self.speed_target_tier_a_resolved_only,
            "speed_target_tier_b": self.speed_target_tier_b,
            "speed_eligibility_status": self.speed_eligibility_status,
            "country": self.country,
            "disease": self.disease,
            "dedup_status": self.dedup_status,
            "model_candidate": self.model_candidate,
        }


def build_forecast_targets(
    repo: OutbreakRepository,
    origin: ForecastOrigin,
    *,
    disease: str,
    source_ids_at_origin: set[str] | None = None,
    coordinate_collision_status_by_id: dict[str, str] | None = None,
    horizon_days: int = PRIMARY_HORIZON_DAYS,
) -> list[ForecastTarget]:
    """One row per distinct historical record with `1 <= lead_days <=
    horizon_days` relative to `origin.t0`, restricted to `origin.country`
    and the requested disease. Never includes a record already in
    `source_ids_at_origin` (see module docstring)."""
    target_disease = normalize_disease(disease)
    t0_date = parse_flexible_date(origin.t0)
    if t0_date is None:
        raise ValueError(f"forecast origin t0 is not a parseable date: {origin.t0!r}")

    source_ids_at_origin = source_ids_at_origin or set()
    collision_by_id = coordinate_collision_status_by_id or {}

    targets: list[ForecastTarget] = []
    for record in repo.list_historical_records(country=origin.country):
        if record.source_record_id in source_ids_at_origin:
            continue
        if not record.model_candidate:
            continue
        if record.dedup_status not in DEDUP_RESOLVED_STATUSES:
            continue
        if normalize_disease(record.disease) != target_disease:
            continue
        if record.latitude is None or record.longitude is None:
            continue

        event = derive_historical_event_date(record)
        if event.historical_event_date is None:
            continue
        event_date = parse_flexible_date(event.historical_event_date)
        if event_date is None:
            continue

        lead_days = (event_date - t0_date).days
        if not (1 <= lead_days <= horizon_days):
            continue

        collision_status = collision_by_id.get(record.source_record_id, CoordinateCollisionStatus.UNKNOWN.value)
        tiers = compute_target_quality_tiers(record, coordinate_collision_status=collision_status)

        targets.append(
            ForecastTarget(
                forecast_origin_id=origin.forecast_origin_id,
                target_id=f"{origin.forecast_origin_id}::{record.source_record_id}",
                target_event_id=record.source_record_id,
                historical_event_date=event.historical_event_date,
                lead_days=lead_days,
                latitude=record.latitude,
                longitude=record.longitude,
                gps_quality=record.gps_quality,
                coordinate_collision_status=collision_status,
                risk_target_eligible=tiers.risk_target_eligible,
                direction_target_tier_a_strict=tiers.direction_target_tier_a_strict,
                direction_target_tier_a_resolved_only=tiers.direction_target_tier_a_resolved_only,
                direction_target_tier_b=tiers.direction_target_tier_b,
                speed_target_tier_a_strict=tiers.speed_target_tier_a_strict,
                speed_target_tier_a_resolved_only=tiers.speed_target_tier_a_resolved_only,
                speed_target_tier_b=tiers.speed_target_tier_b,
                speed_eligibility_status=tiers.speed_eligibility_status,
                country=record.country,
                disease=record.disease,
                dedup_status=record.dedup_status,
                model_candidate=record.model_candidate,
            )
        )

    return targets
