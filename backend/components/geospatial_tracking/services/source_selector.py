"""Eligible active-source selector (master-prompt §10-13, §16-17).

Business/eligibility logic lives HERE, not in the repository — the
repository (`repositories/base.py`) only ever does plain storage/filter
queries (disease, country). This module is what actually enforces:

- the model-candidate hard gate (§16): a historical record with
  `model_candidate = False` — for any reason, including an unresolved
  REVIEW_MEDIUM/REVIEW_LOW dedup status — is NEVER returned, and this is
  never influenced by DQS (DQS isn't even read here).
- the temporal-mode split (§9): STRICT_OPERATIONAL only accepts a
  defensible ACTUAL operational-availability date; RETROSPECTIVE_PROXY may
  use a documented proxy, and every result explicitly carries
  `temporal_mode` and `availability_quality` so a caller can never mistake
  one for the other.
- the T0 invariants (§13): every returned source satisfies
  `t0 - active_window_days <= effective_availability_date <= t0`
  (both bounds inclusive — a documented, arbitrary-but-consistent
  convention, not a scientific claim). A source whose effective date is
  after t0 can never appear, full stop.
- valid-coordinate requirement (§17): a record with missing/invalid
  latitude or longitude can never be an active spatial source, regardless
  of how "UNKNOWN" GPS *precision* is handled (an UNKNOWN precision label
  does NOT by itself exclude a record that has real coordinates).

Deliberately does NOT call this "currently infectious animals/farms" —
infection duration is not established by this selector (§12); the term
used throughout is "eligible active-source set".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from ..domain.enums import RecordDomainScope, ReportStatus
from ..domain.models import HistoricalOutbreakRecord, OutbreakEpisode
from ..repositories.base import OutbreakRepository
from ..schemas import DEDUP_RESOLVED_STATUSES, AvailabilityQuality, ValidationMode
from .dates import parse_flexible_date
from .disease import normalize_disease

# live-domain workflow statuses that count as "accepted/confirmed" per
# domain semantics (master-prompt §10). SUBMITTED/REJECTED never qualify.
_LIVE_ACCEPTED_STATUSES = {ReportStatus.ACCEPTED.value, ReportStatus.CONFIRMED.value}


@dataclass
class EligibleSource:
    source_id: str
    record_domain: str
    disease: str | None
    country: str | None
    latitude: float
    longitude: float
    effective_availability_date: str
    availability_quality: str
    gps_quality: str
    status: str | None


@dataclass
class EligibleSourceResult:
    t0: str
    disease: str
    temporal_mode: str
    active_window_days: int
    country_scope: str | None
    domain_scope: str = RecordDomainScope.BOTH.value
    sources: list[EligibleSource] = field(default_factory=list)


def _historical_eligible(
    record: HistoricalOutbreakRecord,
    *,
    target_disease: str | None,
    temporal_mode: ValidationMode,
    t0: date,
    window_start: date,
) -> EligibleSource | None:
    # -- model-candidate hard gate (§16) — checked first, unconditionally --
    if not record.model_candidate:
        return None
    if record.dedup_status not in DEDUP_RESOLVED_STATUSES:
        return None

    if normalize_disease(record.disease) != target_disease:
        return None

    # -- valid-coordinate requirement (§17) ---------------------------------
    if record.latitude is None or record.longitude is None:
        return None

    avail_date_str, avail_quality = record.effective_availability(temporal_mode)
    if avail_date_str is None:
        return None
    avail_date = parse_flexible_date(avail_date_str)
    if avail_date is None:
        return None

    # -- T0 invariants (§13), both bounds inclusive -------------------------
    if avail_date > t0 or avail_date < window_start:
        return None

    return EligibleSource(
        source_id=record.source_record_id,
        record_domain=record.record_domain,
        disease=record.disease,
        country=record.country,
        latitude=record.latitude,
        longitude=record.longitude,
        effective_availability_date=avail_date.isoformat(),
        availability_quality=avail_quality,
        gps_quality=record.gps_quality,
        status=record.dedup_status,
    )


def _live_eligible(
    episode: OutbreakEpisode,
    *,
    target_disease: str | None,
    t0: date,
    window_start: date,
) -> EligibleSource | None:
    # Live episodes have no dedup/model-candidate concept (they are not
    # cross-source-deduplicated against ambiguous historical evidence by
    # construction) — the workflow-status gate plays that role instead.
    if episode.status not in _LIVE_ACCEPTED_STATUSES:
        return None
    if normalize_disease(episode.disease) != target_disease:
        return None
    if episode.latitude is None or episode.longitude is None:
        return None

    # Live episodes only ever have real operational evidence — there is no
    # "proxy" concept for a live system. temporal_mode does not change
    # this: RETROSPECTIVE_PROXY doesn't invent evidence a live record
    # doesn't have, and STRICT_OPERATIONAL requires exactly what a live
    # episode is supposed to provide anyway.
    if episode.operational_availability_quality != AvailabilityQuality.ACTUAL.value:
        return None
    if not episode.operational_availability_date:
        return None
    avail_date = parse_flexible_date(episode.operational_availability_date)
    if avail_date is None:
        return None

    if avail_date > t0 or avail_date < window_start:
        return None

    return EligibleSource(
        source_id=episode.outbreak_id,
        record_domain=episode.record_domain,
        disease=episode.disease,
        country=episode.country,
        latitude=episode.latitude,
        longitude=episode.longitude,
        effective_availability_date=avail_date.isoformat(),
        availability_quality=episode.operational_availability_quality,
        gps_quality=episode.gps_quality,
        status=episode.status,
    )


def get_eligible_sources(
    repo: OutbreakRepository,
    *,
    disease: str,
    t0: str,
    active_window_days: int,
    temporal_mode: ValidationMode,
    country_scope: str | None = None,
    domain_scope: RecordDomainScope,
) -> EligibleSourceResult:
    """`active_window_days` has NO default — callers must pass it
    explicitly (see config.py: ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT is a
    development convenience value only, never read implicitly here). Must
    be >= 0; 0 means only a source whose effective availability date is
    exactly t0 is eligible ("same-day-only").

    `domain_scope` controls which domain(s) are queried and has **NO
    default** (Checkpoint 4.5 Part 8 — Checkpoint 4 originally defaulted
    this to `BOTH`, which risked accidentally mixing historical and live
    domains through a simple omission; every caller must now say so
    explicitly). Historical replay
    (`services/forecast_origin.py`/`services/list_historical_trigger_candidates`)
    always passes `RecordDomainScope.HISTORICAL_ONLY`; a future live
    forecasting caller passes `LIVE_ONLY`; a diagnostic caller may
    explicitly request `BOTH`. `HISTORICAL_ONLY` never touches
    `outbreak_episodes`; `LIVE_ONLY` never touches
    `historical_outbreak_records`.

    `country_scope` is a SURVEILLANCE/DATA-REPLAY BOUNDARY, not a
    biological one (Checkpoint 4.5 Part 9): it restricts which stored
    records are queried, because that is how this corpus is organized
    administratively — it does not imply, and must never be read to imply,
    that disease transmission stops at a national border. No cross-border
    epidemiological modeling is implemented here or anywhere in this
    checkpoint; `country_scope` is bookkeeping, not a scientific claim.

    Applies the SAME t0/window/disease/coordinate rules to whichever
    domain(s) are queried — but a live episode is never subject to the
    historical dedup/model_candidate gate (it doesn't apply to it), and a
    historical record's proxy path never applies to a live episode (it
    doesn't have one). Never mixes their date semantics: each branch reads
    only its own domain's fields.
    """
    if active_window_days < 0:
        raise ValueError(f"active_window_days must be >= 0, got {active_window_days}")
    t0_date = parse_flexible_date(t0)
    if t0_date is None:
        raise ValueError(f"t0 is not a parseable date: {t0!r}")
    window_start = t0_date - timedelta(days=active_window_days)
    target_disease = normalize_disease(disease)

    sources: list[EligibleSource] = []

    if domain_scope in (RecordDomainScope.HISTORICAL_ONLY, RecordDomainScope.BOTH):
        for record in repo.list_historical_records(country=country_scope):
            eligible = _historical_eligible(
                record,
                target_disease=target_disease,
                temporal_mode=temporal_mode,
                t0=t0_date,
                window_start=window_start,
            )
            if eligible is not None:
                sources.append(eligible)

    if domain_scope in (RecordDomainScope.LIVE_ONLY, RecordDomainScope.BOTH):
        for episode in repo.list_outbreak_episodes(country=country_scope):
            eligible = _live_eligible(
                episode,
                target_disease=target_disease,
                t0=t0_date,
                window_start=window_start,
            )
            if eligible is not None:
                sources.append(eligible)

    sources.sort(key=lambda s: s.source_id)

    return EligibleSourceResult(
        t0=t0_date.isoformat(),
        disease=disease,
        temporal_mode=temporal_mode.value,
        active_window_days=active_window_days,
        country_scope=country_scope,
        domain_scope=domain_scope.value,
        sources=sources,
    )
