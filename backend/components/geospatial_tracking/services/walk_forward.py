"""Checkpoint 4.5 Part 13: candidate walk-forward folds.

Built from CHRONOLOGY ONLY — never from any model accuracy/performance
metric (no model exists yet, and none is ever read here; see FOLD-02).
Boundaries are proposed at even QUANTILES of the sorted, unique forecast-
origin `t0` dates, so each fold's validation window contains a roughly
equal number of origins — a standard, principled, chronology-only method,
never cherry-picked to favor a particular outcome.

Each candidate fold applies the frozen `PURGED_7_DAY_HORIZON_POLICY`
(`services/split_embargo.py`) to its training/validation split: training
origins are `t0 < boundary` MINUS purged origins (whose target window
reaches or crosses the boundary); validation origins are `t0` in
`[boundary_k, boundary_{k+1})`, restricted to those whose own D1-D7 window
stays inside that block (the last fold's block is open-ended — no upper
completeness bound).

`unique_validation_target_events`, `risk_eligible_validation_targets`, and
`strict_tier_a_direction_validation_targets` are all deduplicated by
`target_event_id` (FOLD-03) — a real future outbreak appearing as a
target from several validation origins in the same fold is counted once,
never once per appearance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from .dates import parse_flexible_date
from .forecast_origin import ForecastOrigin
from .forecast_target import PRIMARY_HORIZON_DAYS, ForecastTarget
from .split_embargo import assess_validation_block


@dataclass
class FoldCandidate:
    fold_id: str
    training_date_range_end: str  # boundary B_k — training covers t0 < B_k, purge-filtered
    validation_date_range_start: str
    validation_date_range_end: str | None  # None = open-ended (final fold)
    purged_origin_count: int
    training_origin_count: int
    validation_origin_count: int
    unique_validation_target_events: int
    risk_eligible_validation_targets: int
    strict_tier_a_direction_validation_targets: int
    countries_represented: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "fold_id": self.fold_id,
            "training_date_range_end": self.training_date_range_end,
            "validation_date_range_start": self.validation_date_range_start,
            "validation_date_range_end": self.validation_date_range_end,
            "purged_origin_count": self.purged_origin_count,
            "training_origin_count": self.training_origin_count,
            "validation_origin_count": self.validation_origin_count,
            "unique_validation_target_events": self.unique_validation_target_events,
            "risk_eligible_validation_targets": self.risk_eligible_validation_targets,
            "strict_tier_a_direction_validation_targets": self.strict_tier_a_direction_validation_targets,
            "countries_represented": ";".join(self.countries_represented),
        }


def propose_chronological_boundaries(origins: list[ForecastOrigin], *, num_folds: int) -> list[str]:
    """Chronology-only, quantile-based boundary proposal. `num_folds` must
    be >= 2. Returns `num_folds - 1` boundary date strings (ISO), the
    edges splitting the origins' distinct t0 values into `num_folds`
    roughly-equal-by-ORIGIN-COUNT chronological chunks. Never reads any
    target/model metric (FOLD-02)."""
    if num_folds < 2:
        raise ValueError(f"num_folds must be >= 2, got {num_folds}")
    unique_dates = sorted({parse_flexible_date(o.t0) for o in origins if parse_flexible_date(o.t0)})
    if len(unique_dates) < num_folds:
        raise ValueError(
            f"only {len(unique_dates)} unique t0 dates available, need at least {num_folds} for {num_folds} folds"
        )
    n = len(unique_dates)
    boundaries = []
    for k in range(1, num_folds):
        idx = (n * k) // num_folds
        boundaries.append(unique_dates[idx].isoformat())
    return boundaries


def build_candidate_folds(
    origins: list[ForecastOrigin],
    targets_by_origin_id: dict[str, list[ForecastTarget]],
    *,
    boundaries: list[str],
    horizon_days: int = PRIMARY_HORIZON_DAYS,
    fold_id_prefix: str = "FOLD",
) -> list[FoldCandidate]:
    """`boundaries` must be a chronologically sorted list of candidate
    split-boundary dates (e.g. from `propose_chronological_boundaries`),
    defining `len(boundaries)` folds: fold k's validation block is
    `[boundaries[k], boundaries[k+1])`, with the last fold's block
    open-ended. FOLD-01: deterministic — same origins/targets/boundaries
    always produce the same output, no randomness anywhere in this
    function."""
    boundary_dates = sorted(parse_flexible_date(b) for b in boundaries)
    if any(d is None for d in boundary_dates):
        raise ValueError("all boundaries must be parseable dates")

    folds: list[FoldCandidate] = []
    for k, boundary in enumerate(boundary_dates):
        val_start = boundary
        val_end = boundary_dates[k + 1] if k + 1 < len(boundary_dates) else None

        purged_count = 0
        training_count = 0
        for origin in origins:
            t0 = parse_flexible_date(origin.t0)
            if t0 is None or t0 >= boundary:
                continue
            window_end = t0 + timedelta(days=horizon_days)
            if window_end >= boundary:
                purged_count += 1
            else:
                training_count += 1

        val_end_str = val_end.isoformat() if val_end is not None else None
        val_block_origins = origins  # assess_validation_block filters by t0 >= val_start internally
        block_assessments = assess_validation_block(
            val_block_origins, block_start=val_start.isoformat(), block_end=val_end_str, horizon_days=horizon_days
        )
        # restrict to this fold's window (>= val_start, < val_end if finite) and complete only
        validation_origin_ids = set()
        for a in block_assessments:
            if not a.complete:
                continue
            t0 = parse_flexible_date(a.t0)
            if val_end is not None and t0 >= val_end:
                continue
            validation_origin_ids.add(a.forecast_origin_id)

        validation_origins = [o for o in origins if o.forecast_origin_id in validation_origin_ids]

        val_targets: list[ForecastTarget] = []
        for o in validation_origins:
            val_targets.extend(targets_by_origin_id.get(o.forecast_origin_id, []))

        unique_events = {t.target_event_id for t in val_targets}
        risk_eligible_events = {t.target_event_id for t in val_targets if t.risk_target_eligible}
        tier_a_strict_events = {t.target_event_id for t in val_targets if t.direction_target_tier_a_strict}
        countries = sorted({o.country for o in validation_origins})

        folds.append(
            FoldCandidate(
                fold_id=f"{fold_id_prefix}:{k + 1:02d}",
                training_date_range_end=boundary.isoformat(),
                validation_date_range_start=val_start.isoformat(),
                validation_date_range_end=val_end_str,
                purged_origin_count=purged_count,
                training_origin_count=training_count,
                validation_origin_count=len(validation_origins),
                unique_validation_target_events=len(unique_events),
                risk_eligible_validation_targets=len(risk_eligible_events),
                strict_tier_a_direction_validation_targets=len(tier_a_strict_events),
                countries_represented=countries,
            )
        )

    return folds
