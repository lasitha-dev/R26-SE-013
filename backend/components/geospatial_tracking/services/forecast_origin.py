"""Checkpoint 4 Part 6-7: deterministic forecast-origin ledger + per-origin
source snapshot.

PISTES is outbreak-triggered: a forecast origin exists because one or more
NEW eligible historical sources became available on a given day for a
given country, not because of an arbitrary random t0. This module builds
that ledger from `services/historical_trigger.list_historical_trigger_candidates`
(Checkpoint 4.5 Part 7) — a direct, no-synthetic-date enumeration of
eligible historical records with their own real effective availability
dates.

CHECKPOINT 4.5 CORRECTION: Checkpoint 4 originally discovered trigger
candidates by calling `get_eligible_sources` with a deliberately
far-future `t0` and a deliberately enormous `active_window_days`, purely
to defeat its own T0/window check. That trick worked but was unnecessary
indirection, and the "huge window" constant was initially too small
(caught before the Checkpoint 4 real-data run, but a real bug
nonetheless). `list_historical_trigger_candidates` replaces it entirely —
no synthetic future t0, no magic window, anywhere in this module now. The
real per-origin source snapshot (`build_source_snapshot`) still always
uses the real origin `t0` and the real, explicit `active_window_days`
fixture via `get_eligible_sources`, so the T0 invariants remain enforced
by that already-tested code path.

**One origin per unique (country, t0)** by default (master-prompt Part 6):
multiple sources becoming available on the same country-day collapse into
ONE origin with multiple `trigger_source_ids_at_t0` entries, rather than
creating statistically identical duplicate country-level snapshots. A
primary-source-specific origin scheme is NOT implemented here — if ever
needed, it must be a clearly separate, explicitly-labeled construct, never
silently mixed into this ledger (that would pseudo-replicate what is
really one snapshot).

Every call in this module that touches `get_eligible_sources` (or the
trigger-candidate enumeration) passes
`domain_scope=RecordDomainScope.HISTORICAL_ONLY` (or is historical-only by
construction) explicitly — historical forecast-origin construction must
never rely on any implicit domain default (`domain_scope` has no default
at all as of Checkpoint 4.5 Part 8 — see `source_selector.py`).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ..domain.enums import RecordDomainScope
from ..repositories.base import OutbreakRepository
from ..schemas import ValidationMode
from .historical_trigger import list_historical_trigger_candidates
from .source_selector import get_eligible_sources


@dataclass
class ForecastOrigin:
    forecast_origin_id: str
    country: str
    t0: str
    temporal_mode: str
    trigger_source_ids_at_t0: list[str] = field(default_factory=list)
    trigger_source_count: int = 0

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id,
            "country": self.country,
            "t0": self.t0,
            "temporal_mode": self.temporal_mode,
            "trigger_source_ids_at_t0": ";".join(self.trigger_source_ids_at_t0),
            "trigger_source_count": self.trigger_source_count,
        }


@dataclass
class SourceSnapshot:
    forecast_origin_id: str
    country: str
    t0: str
    active_window_days: int
    active_window_days_label: str
    temporal_mode: str
    source_ids: list[str] = field(default_factory=list)
    source_count: int = 0
    source_effective_dates: list[str] = field(default_factory=list)
    source_availability_quality: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id,
            "country": self.country,
            "t0": self.t0,
            "active_window_days": self.active_window_days,
            "active_window_days_label": self.active_window_days_label,
            "temporal_mode": self.temporal_mode,
            "source_ids": ";".join(self.source_ids),
            "source_count": self.source_count,
            "source_effective_dates": ";".join(self.source_effective_dates),
            "source_availability_quality": ";".join(self.source_availability_quality),
        }


def build_forecast_origin_ledger(
    repo: OutbreakRepository, *, disease: str, country_scope: str | None = None
) -> list[ForecastOrigin]:
    """Deterministic: same input data always produces the same origin list
    in the same order (sorted by country, then t0) — see ORIGIN-01,
    DISCOVERY-04."""
    candidates = list_historical_trigger_candidates(repo, disease=disease, country_scope=country_scope)

    buckets: dict[tuple[str, str], list[str]] = defaultdict(list)
    for candidate in candidates:
        country = candidate.country or "UNKNOWN"
        buckets[(country, candidate.effective_availability_date)].append(candidate.source_id)

    origins: list[ForecastOrigin] = []
    for (country, t0), source_ids in sorted(buckets.items()):
        origins.append(
            ForecastOrigin(
                forecast_origin_id=f"ORIGIN:{country}:{t0}",
                country=country,
                t0=t0,
                temporal_mode=ValidationMode.RETROSPECTIVE_PROXY.value,
                trigger_source_ids_at_t0=sorted(source_ids),
                trigger_source_count=len(source_ids),
            )
        )
    return origins


def build_source_snapshot(
    repo: OutbreakRepository,
    origin: ForecastOrigin,
    *,
    disease: str,
    active_window_days: int,
) -> SourceSnapshot:
    """Uses the REAL origin `t0` and the REAL, explicit
    `active_window_days` — every returned source satisfies
    `t0 - active_window_days <= effective_availability_date <= t0`
    (enforced by `get_eligible_sources` itself, not re-implemented here)."""
    result = get_eligible_sources(
        repo,
        disease=disease,
        t0=origin.t0,
        active_window_days=active_window_days,
        temporal_mode=ValidationMode.RETROSPECTIVE_PROXY,
        country_scope=origin.country,
        domain_scope=RecordDomainScope.HISTORICAL_ONLY,
    )
    return SourceSnapshot(
        forecast_origin_id=origin.forecast_origin_id,
        country=origin.country,
        t0=result.t0,
        active_window_days=active_window_days,
        active_window_days_label="UNFROZEN_DEVELOPMENT_PARAMETER",
        temporal_mode=result.temporal_mode,
        source_ids=[s.source_id for s in result.sources],
        source_count=len(result.sources),
        source_effective_dates=[s.effective_availability_date for s in result.sources],
        source_availability_quality=[s.availability_quality for s in result.sources],
    )
