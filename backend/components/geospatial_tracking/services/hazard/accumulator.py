"""Checkpoint 6C Parts 5-6, 20-22 / Checkpoint 6C.5 Part 19-21:
all-source accumulation with explicit relative-risk numerical status.

For each cell: `H_i = sum_j H_j_i` over EVERY eligible active source —
CORE/BORDER/NOISE/`ST_TEMPORAL_UNUSABLE` alike, provided each
independently satisfies the normal eligible-source contract and has
valid geometry for this cell. A "nearest source" may be stored for
display only — it never replaces the sum.

**Missing geometry blocks, never silently drops**: this function takes
the FULL `eligible_source_ids` list for the cell as well as the
`contributions` actually computed — any eligible source with no
corresponding contribution makes the whole cell
`CELL_HAZARD_INCOMPLETE`, never a quietly-smaller sum.

**Order invariance**: contributions are always sorted by `source_id`
before summing, and `math.fsum` is used for numerically stable,
order-independent floating-point summation.

**Relative-risk numerical status (6C.5 Part 19)**: `relative_risk_index`
is the numeric `.value` from `relative_risk.compute_relative_risk_index`;
`relative_risk_status` (`FINITE_INTERIOR` /
`NUMERIC_SATURATION_ADJUSTED`) is preserved alongside it — never
silently dropped.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .contracts import CELL_HAZARD_INCOMPLETE, COMPLETE
from .relative_risk import compute_relative_risk_index
from .source_hazard import SourceHazardContribution


@dataclass(frozen=True)
class CellHazardResult:
    grid_cell_id: str
    source_contributions: list  # SourceHazardContribution.as_dict(), sorted by source_id
    total_hazard: float | None
    relative_risk_index: float | None
    relative_risk_status: str | None
    status: str  # COMPLETE | CELL_HAZARD_INCOMPLETE
    missing_requirements: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "grid_cell_id": self.grid_cell_id,
            "source_contributions": self.source_contributions,
            "total_hazard": self.total_hazard,
            "relative_risk_index": self.relative_risk_index,
            "relative_risk_status": self.relative_risk_status,
            "status": self.status,
            "missing_requirements": self.missing_requirements,
        }


def accumulate_cell_hazard(
    *,
    grid_cell_id: str,
    eligible_source_ids: list,
    contributions: dict,  # source_id -> SourceHazardContribution
) -> CellHazardResult:
    """`contributions` need not cover every `eligible_source_id` — any
    gap becomes an explicit `missing_requirements` entry
    (`"geometry missing for source <id>"`), never a silent omission
    from the sum."""
    missing_geometry = sorted(set(eligible_source_ids) - set(contributions.keys()))
    sorted_ids = sorted(contributions.keys())
    sorted_contributions = [contributions[sid] for sid in sorted_ids]

    missing_requirements: list = [f"geometry missing for source {sid}" for sid in missing_geometry]
    incomplete_sources = [c for c in sorted_contributions if c.status != COMPLETE]
    for c in incomplete_sources:
        missing_requirements.extend(f"{c.source_id}: {m}" for m in c.missing_requirements)

    if missing_requirements:
        return CellHazardResult(
            grid_cell_id=grid_cell_id,
            source_contributions=[c.as_dict() for c in sorted_contributions],
            total_hazard=None,
            relative_risk_index=None,
            relative_risk_status=None,
            status=CELL_HAZARD_INCOMPLETE,
            missing_requirements=missing_requirements,
        )

    values = [c.source_hazard for c in sorted_contributions]
    total = math.fsum(values) if values else 0.0
    if total < 0:
        raise ValueError(f"total_hazard evaluated negative ({total!r}) — never silently repaired")

    risk_result = compute_relative_risk_index(total)

    return CellHazardResult(
        grid_cell_id=grid_cell_id,
        source_contributions=[c.as_dict() for c in sorted_contributions],
        total_hazard=total,
        relative_risk_index=risk_result.value,
        relative_risk_status=risk_result.status,
        status=COMPLETE,
        missing_requirements=[],
    )
