"""Checkpoint 6B Part 7: the ST-DBSCAN temporal coordinate.

**Availability time and outbreak-event time are different concepts.**
`source_selector.get_eligible_sources` already answers "may this source
exist at t0?" using `effective_availability_date`
(operational/proxy-availability semantics, Checkpoint 1-3). This module
answers a SEPARATE question — "when did the outbreak this source
describes actually occur?" — reusing `services.historical_event_date.derive_historical_event_date`
UNCHANGED (no new silent date-fallback chain is created here).

`cluster_event_date` must be `<= t0` (an outbreak cannot be positioned,
for clustering purposes, at a date after the very forecast origin that
made it eligible in the first place — Part 7). If no defensible event
date exists, OR the derived date is after `t0`, the source stays in the
eligible active-source set (never removed) but is marked
`ST_TEMPORAL_UNUSABLE` for clustering — never silently substituted with
`report_date`, a final follow-up date, or any other later/undocumented
field.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..dates import parse_flexible_date
from ..historical_event_date import UNKNOWN as EVENT_DATE_QUALITY_UNKNOWN
from ..historical_event_date import derive_historical_event_date
from ...domain.models import HistoricalOutbreakRecord

ST_USABLE = "ST_USABLE"
ST_TEMPORAL_UNUSABLE = "ST_TEMPORAL_UNUSABLE"


@dataclass
class ClusterEventDate:
    source_id: str
    cluster_event_date: str | None
    cluster_event_date_quality: str
    cluster_event_date_source_field: str | None
    usability: str  # ST_USABLE | ST_TEMPORAL_UNUSABLE
    reason: str

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "cluster_event_date": self.cluster_event_date,
            "cluster_event_date_quality": self.cluster_event_date_quality,
            "cluster_event_date_source_field": self.cluster_event_date_source_field,
            "usability": self.usability,
            "reason": self.reason,
        }


def resolve_cluster_event_date(record: HistoricalOutbreakRecord, *, t0: str) -> ClusterEventDate:
    """Pure (given the record and t0): derives the event date via the
    UNCHANGED, already-tested `historical_event_date` service, then
    applies the ST-DBSCAN-specific `<= t0` usability rule (ST-10/ST-11)."""
    derived = derive_historical_event_date(record)

    if derived.historical_event_date is None:
        return ClusterEventDate(
            source_id=record.source_record_id,
            cluster_event_date=None,
            cluster_event_date_quality=EVENT_DATE_QUALITY_UNKNOWN,
            cluster_event_date_source_field=None,
            usability=ST_TEMPORAL_UNUSABLE,
            reason="no defensible historical_event_date exists on this record — never substituted with report_date "
            "or any other field",
        )

    event_date = parse_flexible_date(derived.historical_event_date)
    t0_date = parse_flexible_date(t0)
    if event_date is None:
        return ClusterEventDate(
            source_id=record.source_record_id,
            cluster_event_date=derived.historical_event_date,
            cluster_event_date_quality=derived.historical_event_date_quality,
            cluster_event_date_source_field=derived.historical_event_date_source_field,
            usability=ST_TEMPORAL_UNUSABLE,
            reason=f"historical_event_date {derived.historical_event_date!r} is not a parseable date",
        )
    if t0_date is None:
        raise ValueError(f"t0 is not a parseable date: {t0!r}")

    if event_date > t0_date:
        return ClusterEventDate(
            source_id=record.source_record_id,
            cluster_event_date=derived.historical_event_date,
            cluster_event_date_quality=derived.historical_event_date_quality,
            cluster_event_date_source_field=derived.historical_event_date_source_field,
            usability=ST_TEMPORAL_UNUSABLE,
            reason=f"cluster_event_date {derived.historical_event_date} is AFTER t0 {t0} — rejected, never used "
            "for clustering even though the source itself remains eligible",
        )

    return ClusterEventDate(
        source_id=record.source_record_id,
        cluster_event_date=derived.historical_event_date,
        cluster_event_date_quality=derived.historical_event_date_quality,
        cluster_event_date_source_field=derived.historical_event_date_source_field,
        usability=ST_USABLE,
        reason="cluster_event_date resolved and <= t0",
    )
