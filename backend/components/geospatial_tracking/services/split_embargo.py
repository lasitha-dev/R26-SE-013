"""Checkpoint 4 Part 14 / Checkpoint 4.5 Part 12: PURGED_7_DAY_HORIZON_POLICY
— the frozen horizon-safe split-boundary purge rule.

**Frozen as of Checkpoint 4.5** (no longer just a draft): given a split
boundary date B and the primary forecast horizon H
(`forecast_target.PRIMARY_HORIZON_DAYS` = 7):

    A development/training origin is eligible for the earlier partition
    ONLY when      t0 + H < B
    If             t0 < B   AND   t0 + H >= B
    the origin is PURGED from the earlier partition — its future targets
    are never clipped-and-pretended-normal; the whole origin is excluded
    from that partition.

    For a FINITE validation block [B, E] (E may be None for an
    intentionally open-ended/final block): a validation origin supports a
    COMPLETE D1-D7 evaluation only when
                   t0 >= B   AND   t0 + H <= E
    An origin failing this within a finite block is not silently included
    with a truncated horizon — it is excluded from that block's complete-
    evaluation set (see `validation_block_targets_are_complete`).

RULE for partition assignment: an origin's t0 determines its partition —
`t0 < B` is "BEFORE_BOUNDARY", `t0 >= B` is "AT_OR_AFTER_BOUNDARY" (B
itself belongs to the "after" side — a documented, consistent,
arbitrary-but-fixed convention, matching the T0-invariant inclusive-bounds
convention already used in `source_selector.py`).

This module identifies which origins the purge policy applies to. It does
NOT choose an exclusion mechanism beyond "purge the whole origin from the
earlier partition" (frozen — no clip-and-pretend, no partial-horizon
substitution) and does not itself build any train/test file (master-prompt
Part 11: "Do NOT create final train/test files yet unless the split is
genuinely frozen" — the split BOUNDARY placement itself is not frozen by
this module, only the purge RULE once a boundary is chosen elsewhere).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from .dates import parse_flexible_date
from .forecast_origin import ForecastOrigin
from .forecast_target import PRIMARY_HORIZON_DAYS

PURGED_7_DAY_HORIZON_POLICY = "PURGED_7_DAY_HORIZON_POLICY"

BEFORE_BOUNDARY = "BEFORE_BOUNDARY"
AT_OR_AFTER_BOUNDARY = "AT_OR_AFTER_BOUNDARY"


@dataclass
class EmbargoAssessment:
    forecast_origin_id: str
    t0: str
    partition: str
    target_window_end: str
    embargoed: bool
    reason: str

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id,
            "t0": self.t0,
            "partition": self.partition,
            "target_window_end": self.target_window_end,
            "embargoed": self.embargoed,
            "reason": self.reason,
        }


def assess_embargo(
    origins: list[ForecastOrigin], *, boundary: str, horizon_days: int = PRIMARY_HORIZON_DAYS
) -> list[EmbargoAssessment]:
    boundary_date = parse_flexible_date(boundary)
    if boundary_date is None:
        raise ValueError(f"boundary is not a parseable date: {boundary!r}")

    results: list[EmbargoAssessment] = []
    for origin in origins:
        t0_date = parse_flexible_date(origin.t0)
        if t0_date is None:
            continue
        window_end = t0_date + timedelta(days=horizon_days)

        if t0_date < boundary_date:
            partition = BEFORE_BOUNDARY
            embargoed = window_end >= boundary_date
            reason = (
                f"target window [t0+1, t0+{horizon_days}] reaches or crosses the split "
                "boundary — target labels would leak across it"
                if embargoed
                else "target window stays entirely before the boundary"
            )
        else:
            partition = AT_OR_AFTER_BOUNDARY
            embargoed = False
            reason = "origin itself is at/after the boundary — not a BEFORE_BOUNDARY leak candidate"

        results.append(
            EmbargoAssessment(
                forecast_origin_id=origin.forecast_origin_id,
                t0=origin.t0,
                partition=partition,
                target_window_end=window_end.isoformat(),
                embargoed=embargoed,
                reason=reason,
            )
        )
    return results


def embargoed_before_origins(
    origins: list[ForecastOrigin], *, boundary: str, horizon_days: int = PRIMARY_HORIZON_DAYS
) -> list[EmbargoAssessment]:
    return [a for a in assess_embargo(origins, boundary=boundary, horizon_days=horizon_days) if a.embargoed]


@dataclass
class ValidationBlockAssessment:
    forecast_origin_id: str
    t0: str
    target_window_end: str
    complete: bool
    reason: str

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id,
            "t0": self.t0,
            "target_window_end": self.target_window_end,
            "complete": self.complete,
            "reason": self.reason,
        }


def assess_validation_block(
    origins: list[ForecastOrigin],
    *,
    block_start: str,
    block_end: str | None,
    horizon_days: int = PRIMARY_HORIZON_DAYS,
) -> list[ValidationBlockAssessment]:
    """PURGE-04: a validation origin supports a COMPLETE D1-D7 evaluation
    only when `t0 >= block_start` and (`block_end is None` — an
    intentionally open-ended/final block — or `t0 + horizon_days <=
    block_end`). Origins with `t0 < block_start` are not part of this
    block at all (not returned). An origin whose window would cross a
    FINITE `block_end` is returned with `complete = False`, never silently
    included as if its D1-D7 coverage were whole."""
    start_date = parse_flexible_date(block_start)
    if start_date is None:
        raise ValueError(f"block_start is not a parseable date: {block_start!r}")
    end_date = parse_flexible_date(block_end) if block_end is not None else None
    if block_end is not None and end_date is None:
        raise ValueError(f"block_end is not a parseable date: {block_end!r}")

    results: list[ValidationBlockAssessment] = []
    for origin in origins:
        t0_date = parse_flexible_date(origin.t0)
        if t0_date is None or t0_date < start_date:
            continue
        window_end = t0_date + timedelta(days=horizon_days)

        if end_date is None:
            complete = True
            reason = "open-ended/final validation block — no upper completeness bound applied"
        elif window_end <= end_date:
            complete = True
            reason = "full D1-D7 target window fits inside the finite validation block"
        else:
            complete = False
            reason = (
                f"target window [t0+1, t0+{horizon_days}] extends past the finite "
                "validation block's end — excluded from this block's complete-evaluation set"
            )

        results.append(
            ValidationBlockAssessment(
                forecast_origin_id=origin.forecast_origin_id,
                t0=origin.t0,
                target_window_end=window_end.isoformat(),
                complete=complete,
                reason=reason,
            )
        )
    return results
