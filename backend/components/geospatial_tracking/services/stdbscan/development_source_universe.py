"""Checkpoint 6B.5 Parts 1-6: the validated FIT_DEVELOPMENT source
universe — the ONLY safe input to ST-DBSCAN parameter-candidate
statistics.

**The bug this module fixes**: Checkpoint 6B's `parameter_candidates.py`
computed real geometric/temporal candidate evidence directly from
`repo.list_historical_records(...)`, documenting that "model_candidate /
dedup filtering is the caller's responsibility." That is unsafe — a
scientific parameter-development function must never permit an
unresolved-dedup, non-model-candidate, or (via a raw event-date-only
role rule) improperly-admitted record to shape `eps_space`/`eps_time`/
`MinPts`/active-window candidates, even by caller accident.

**The fix**: this module reuses `source_selector.get_eligible_sources`
— the ALREADY hard-gated selector (model_candidate=True, dedup
resolved, valid coordinates, t0-window bounded) — across every real
`FIT_DEVELOPMENT` forecast origin's superset window
(`candidate_constants.MAX_ACTIVE_WINDOW_DAYS`, currently 28 days, the
largest `ACTIVE_WINDOW_DAY_CANDIDATES` value). A record never enters
the validated universe by having its own `historical_event_date`
compared to the cutoff (Checkpoint 6B's insufficient rule) — it enters
only because information-availability rules (via `get_eligible_sources`)
put it inside at least one real `FIT_DEVELOPMENT` origin's eligible
window. `cluster_event_date` is derived AFTER that admission decision,
purely to say WHERE the source lies on the ST temporal axis — never to
decide WHETHER it may be used (Part 4's permanent distinction).

Every real historical record for the disease is classified into exactly
one outcome: included in the validated universe, or excluded with one
specific, reported reason (`SourceExclusion`) — `model_candidate=false`,
`unresolved dedup`, `Sri Lanka`, `invalid coordinate`,
`held-out-only availability` (never available inside any
`FIT_DEVELOPMENT` origin's window — covers both a post-cutoff proxy
date and a source seen only in `HELD_OUT_FROM_MODEL_FITTING`/
`SRI_LANKA_TRANSFER_CASE_STUDY` origins), or `missing event date`
(coordinates and availability are fine, but no defensible
`cluster_event_date` could be derived, so the source could never be
`ST_USABLE` for real clustering regardless of which parameter candidate
is chosen). Nothing is ever silently dropped — every exclusion is
reported (Part 5/21: "never hide exclusions").

The same real source frequently appears in many `FIT_DEVELOPMENT`
origins' snapshots (Part 3) — this module represents it exactly ONCE in
the validated universe (keyed by `source_id`), tracking
`first_fit_origin_t0_seen`/`last_fit_origin_t0_seen`, so later parameter
statistics are never pseudo-replicated by repeated origin appearances.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.enums import RecordDomainScope
from ...schemas import DEDUP_RESOLVED_STATUSES, ValidationMode
from ..dates import parse_flexible_date
from ..historical_event_date import derive_historical_event_date
from ..model_fitting_exposure import MODEL_FITTING_CUTOFF, FIT_DEVELOPMENT, classify_origin_role
from ..source_selector import get_eligible_sources
from ..forecast_origin import ForecastOrigin
from .candidate_constants import MAX_ACTIVE_WINDOW_DAYS

_SRI_LANKA_COUNTRY_NAME = "Sri Lanka"

REASON_MODEL_CANDIDATE_FALSE = "MODEL_CANDIDATE_FALSE"
REASON_UNRESOLVED_DEDUP = "UNRESOLVED_DEDUP"
REASON_SRI_LANKA = "SRI_LANKA"
REASON_INVALID_COORDINATE = "INVALID_COORDINATE"
REASON_HELD_OUT_ONLY_AVAILABILITY = "HELD_OUT_ONLY_AVAILABILITY"
REASON_MISSING_EVENT_DATE = "MISSING_EVENT_DATE"


@dataclass
class DevelopmentSource:
    """One validated, unique, FIT_DEVELOPMENT-admissible source — the
    unit of evidence for country-scoped parameter-candidate statistics
    (Part 7-9). Never one row per origin appearance (Part 3/DEV-SOURCE-08)."""

    source_id: str
    country: str
    first_fit_origin_t0_seen: str
    last_fit_origin_t0_seen: str
    effective_availability_date: str
    availability_quality: str
    cluster_event_date: str | None
    cluster_event_date_quality: str
    cluster_event_date_source_field: str | None
    latitude: float
    longitude: float
    gps_quality: str
    dedup_status: str
    model_candidate: bool

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "country": self.country,
            "first_fit_origin_t0_seen": self.first_fit_origin_t0_seen,
            "last_fit_origin_t0_seen": self.last_fit_origin_t0_seen,
            "effective_availability_date": self.effective_availability_date,
            "availability_quality": self.availability_quality,
            "cluster_event_date": self.cluster_event_date,
            "cluster_event_date_quality": self.cluster_event_date_quality,
            "cluster_event_date_source_field": self.cluster_event_date_source_field,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "gps_quality": self.gps_quality,
            "dedup_status": self.dedup_status,
            "model_candidate": self.model_candidate,
        }


@dataclass
class SourceExclusion:
    source_id: str
    country: str | None
    reason_code: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "country": self.country,
            "reason_code": self.reason_code,
            "reason": self.reason,
        }


@dataclass
class DevelopmentSourceUniverseResult:
    n_records_considered: int
    sources: list[DevelopmentSource]
    exclusions: list[SourceExclusion]
    max_active_window_days: int

    @property
    def n_validated_sources(self) -> int:
        return len(self.sources)

    def exclusion_counts_by_reason(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.exclusions:
            counts[e.reason_code] = counts.get(e.reason_code, 0) + 1
        return counts


def build_fit_development_source_universe(
    repo,
    forecast_origins: list[ForecastOrigin],
    *,
    disease: str,
    max_active_window_days: int = MAX_ACTIVE_WINDOW_DAYS,
    cutoff: str = MODEL_FITTING_CUTOFF,
) -> DevelopmentSourceUniverseResult:
    """Part 2: hard-filters `forecast_origins` to `FIT_DEVELOPMENT` role
    itself (never trusts the caller to have done so already — Part 1's
    "do not rely on caller discipline" applies here too). For every such
    origin, calls the existing eligible-source selector with
    `model_candidate=true`/dedup-resolved/valid-coordinate/
    availability-window rules already enforced
    (`domain_scope=HISTORICAL_ONLY`, `temporal_mode=RETROSPECTIVE_PROXY`),
    using `max_active_window_days` (default: the largest
    `ACTIVE_WINDOW_DAY_CANDIDATES` value) purely to build the SUPERSET of
    sources that could participate in ANY development candidate window —
    this is a source-universe construction rule, not an epidemiological
    claim that this window length is correct (Part 2).

    Returns the validated, de-duplicated `DevelopmentSource` universe
    (Part 3) plus a full `SourceExclusion` report (Part 5) covering EVERY
    real historical record for `disease`, so nothing is hidden.
    """
    dev_origins = [o for o in forecast_origins if classify_origin_role(o, cutoff=cutoff) == FIT_DEVELOPMENT]

    # -- Part 2: union of eligible source_ids across every FIT_DEVELOPMENT
    # origin's 28-day superset window, keeping first/last t0 seen. Reuses
    # get_eligible_sources per country-scoped origin exactly as the real
    # ST-DBSCAN pipeline does (never a raw global record scan).
    first_t0_seen: dict[str, str] = {}
    last_t0_seen: dict[str, str] = {}
    availability_by_id: dict[str, tuple[str, str]] = {}
    country_by_id: dict[str, str] = {}

    for origin in dev_origins:
        result = get_eligible_sources(
            repo,
            disease=disease,
            t0=origin.t0,
            active_window_days=max_active_window_days,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY,
            country_scope=origin.country,
            domain_scope=RecordDomainScope.HISTORICAL_ONLY,
        )
        for s in result.sources:
            if s.source_id not in first_t0_seen or origin.t0 < first_t0_seen[s.source_id]:
                first_t0_seen[s.source_id] = origin.t0
            if s.source_id not in last_t0_seen or origin.t0 > last_t0_seen[s.source_id]:
                last_t0_seen[s.source_id] = origin.t0
            availability_by_id[s.source_id] = (s.effective_availability_date, s.availability_quality)
            country_by_id[s.source_id] = s.country or origin.country

    fit_dev_source_ids = set(first_t0_seen.keys())

    # -- Part 5/6/21: classify EVERY real historical record for `disease`
    # into included-or-excluded-with-reason, checking hard invariants
    # directly on the record (never relying on `fit_dev_source_ids`
    # membership alone to explain WHY something is excluded).
    all_records = repo.list_historical_records(disease=disease)

    sources: list[DevelopmentSource] = []
    exclusions: list[SourceExclusion] = []

    for record in all_records:
        sid = record.source_record_id
        if not record.model_candidate:
            exclusions.append(
                SourceExclusion(
                    source_id=sid, country=record.country, reason_code=REASON_MODEL_CANDIDATE_FALSE,
                    reason="model_candidate=False — never permitted to influence ST parameter evidence",
                )
            )
            continue
        if record.dedup_status not in DEDUP_RESOLVED_STATUSES:
            exclusions.append(
                SourceExclusion(
                    source_id=sid, country=record.country, reason_code=REASON_UNRESOLVED_DEDUP,
                    reason=f"dedup_status={record.dedup_status!r} is not a resolved status ({sorted(DEDUP_RESOLVED_STATUSES)})",
                )
            )
            continue
        if record.country == _SRI_LANKA_COUNTRY_NAME:
            exclusions.append(
                SourceExclusion(
                    source_id=sid, country=record.country, reason_code=REASON_SRI_LANKA,
                    reason="Sri Lanka is SRI_LANKA_TRANSFER_CASE_STUDY unconditionally — never used for parameter development",
                )
            )
            continue
        if record.latitude is None or record.longitude is None:
            exclusions.append(
                SourceExclusion(
                    source_id=sid, country=record.country, reason_code=REASON_INVALID_COORDINATE,
                    reason="missing/invalid latitude or longitude",
                )
            )
            continue
        if sid not in fit_dev_source_ids:
            exclusions.append(
                SourceExclusion(
                    source_id=sid, country=record.country, reason_code=REASON_HELD_OUT_ONLY_AVAILABILITY,
                    reason="never fell inside any real FIT_DEVELOPMENT origin's eligible-source window under "
                    f"the {max_active_window_days}-day superset (e.g. only available at/after the cutoff, or "
                    "only observed via a HELD_OUT_FROM_MODEL_FITTING/SRI_LANKA_TRANSFER_CASE_STUDY origin)",
                )
            )
            continue

        derived = derive_historical_event_date(record)
        event_date_str = derived.historical_event_date
        if event_date_str is None or parse_flexible_date(event_date_str) is None:
            exclusions.append(
                SourceExclusion(
                    source_id=sid, country=record.country, reason_code=REASON_MISSING_EVENT_DATE,
                    reason="no defensible historical_event_date could be derived — this source could never be "
                    "ST_USABLE for real clustering regardless of parameter choice",
                )
            )
            continue

        avail_date, avail_quality = availability_by_id[sid]
        sources.append(
            DevelopmentSource(
                source_id=sid,
                country=record.country,
                first_fit_origin_t0_seen=first_t0_seen[sid],
                last_fit_origin_t0_seen=last_t0_seen[sid],
                effective_availability_date=avail_date,
                availability_quality=avail_quality,
                cluster_event_date=event_date_str,
                cluster_event_date_quality=derived.historical_event_date_quality,
                cluster_event_date_source_field=derived.historical_event_date_source_field,
                latitude=record.latitude,
                longitude=record.longitude,
                gps_quality=record.gps_quality,
                dedup_status=record.dedup_status,
                model_candidate=record.model_candidate,
            )
        )

    sources.sort(key=lambda s: s.source_id)
    exclusions.sort(key=lambda e: e.source_id)

    return DevelopmentSourceUniverseResult(
        n_records_considered=len(all_records),
        sources=sources,
        exclusions=exclusions,
        max_active_window_days=max_active_window_days,
    )
