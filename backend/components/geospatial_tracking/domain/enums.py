"""Checkpoint 3 domain enums.

`ValidationMode` (STRICT_OPERATIONAL / RETROSPECTIVE_PROXY) and the date-
quality/GPS-quality/dedup enums already live in `schemas.py` — reused here
rather than duplicated, since they mean exactly the same thing for the
domain layer as they did for the raw/canonical pipeline.
"""

from __future__ import annotations

from enum import Enum


class ReportStatus(str, Enum):
    """Workflow status of a single live `AnimalReport` or an aggregated
    `OutbreakEpisode`. Deliberately small and generic — the actual future
    live system's workflow may have more states; this is the minimum set
    Checkpoint 3's domain/aggregation/source-selection logic needs."""

    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class RecordDomain(str, Enum):
    """Which of the two data domains (master-prompt Checkpoint 3 §2) a
    record belongs to. Never inferred implicitly — always set explicitly
    at construction, so a retrospective WAHIS/EMPRES-derived record can
    never be silently treated as a live operational report."""

    LIVE_OPERATIONAL_RECORD = "LIVE_OPERATIONAL_RECORD"
    HISTORICAL_RESEARCH_RECORD = "HISTORICAL_RESEARCH_RECORD"


class GroupingDateQuality(str, Enum):
    """Checkpoint 3.5: what kind of date `OutbreakEpisode.
    episode_grouping_date` actually is — deliberately a SEPARATE concept
    from `onset_date` (real biological onset only). See
    `services/aggregation.py` module docstring for the full fallback
    hierarchy this labels.

    BIOLOGICAL_DATE: the grouping date IS a real reported onset date.
    OPERATIONAL_PROXY: no biological onset was available; an operational
        workflow timestamp was used ONLY to decide clustering, and must
        never be described or read as biological event time.
    UNKNOWN: no defensible date of either kind was available at all.
    """

    BIOLOGICAL_DATE = "BIOLOGICAL_DATE"
    OPERATIONAL_PROXY = "OPERATIONAL_PROXY"
    UNKNOWN = "UNKNOWN"


class RecordDomainScope(str, Enum):
    """Checkpoint 4 Part 0B / Checkpoint 4.5 Part 8: explicit, REQUIRED
    query scope for `services.source_selector.get_eligible_sources`
    (`domain_scope` has no default — every caller must state one).

    HISTORICAL_ONLY: only `historical_outbreak_records` are queried.
        Scientific historical replay/forecast-origin construction always
        passes this.
    LIVE_ONLY: only `outbreak_episodes` (the live domain) are queried. A
        future live-forecasting caller passes this.
    BOTH: both domains are queried and merged — available for an explicit
        diagnostic caller that genuinely wants both, but never silently
        defaulted into: accidental omission must raise, not mix domains.
    """

    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    LIVE_ONLY = "LIVE_ONLY"
    BOTH = "BOTH"


class CoordinateCollisionStatus(str, Enum):
    """Checkpoint 4.5 Parts 1-3: replaces Checkpoint 4's misleadingly-named
    boolean `canonical_spatial_independence`. Coordinate uniqueness is a
    DATA-QUALITY / CO-LOCATION indicator — it is NOT proof that outbreak
    events are epidemiologically or statistically independent. See
    `services/coordinate_collision.py`.

    Computed by comparing one canonical (dedup-resolved-or-not) outbreak
    identity's stored coordinate against every OTHER conservative row's
    coordinate, split by whether those other rows are themselves
    dedup-RESOLVED (`schemas.DEDUP_RESOLVED_STATUSES`) or UNRESOLVED
    (`REVIEW_MEDIUM`/`REVIEW_LOW`) — an unresolved record sharing a
    coordinate is different, weaker evidence than a resolved one sharing
    it, and must never be treated as equivalent.

    UNIQUE_AMONG_RESOLVED: no other RESOLVED row, and no UNRESOLVED row
        either, shares this coordinate.
    SHARED_WITH_RESOLVED: at least one other RESOLVED row shares this
        coordinate (no unresolved sharing).
    SHARED_WITH_UNRESOLVED: only UNRESOLVED row(s) share this coordinate —
        ambiguous, preserved for sensitivity/manual review, never treated
        as definitive non-independence of the resolved candidate.
    SHARED_WITH_BOTH: both a resolved and an unresolved row share it.
    MISSING_COORDINATE: this row itself has no latitude/longitude.
    UNKNOWN: collision status could not be assessed for another reason.
    """

    UNIQUE_AMONG_RESOLVED = "UNIQUE_AMONG_RESOLVED"
    SHARED_WITH_RESOLVED = "SHARED_WITH_RESOLVED"
    SHARED_WITH_UNRESOLVED = "SHARED_WITH_UNRESOLVED"
    SHARED_WITH_BOTH = "SHARED_WITH_BOTH"
    MISSING_COORDINATE = "MISSING_COORDINATE"
    UNKNOWN = "UNKNOWN"


class AnimalCountQuality(str, Enum):
    """Checkpoint 3.5: honesty label for `OutbreakEpisode.affected_animals`
    — see `services/aggregation.py` CASE A/B/C. Never treat a
    LOWER_BOUND/UNKNOWN count as if it were EXACT — in particular, never
    as an exact source-pressure/case-count value for later modeling
    without an explicitly developed rule for doing so (master-prompt §7)."""

    EXACT = "EXACT"
    LOWER_BOUND = "LOWER_BOUND"
    UNKNOWN = "UNKNOWN"
