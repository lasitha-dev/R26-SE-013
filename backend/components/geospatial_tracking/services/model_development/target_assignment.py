"""Checkpoint 7A Parts 11, 18-22: presence-only target semantics,
unique-target-event contract, and deterministic D1-D7 target-to-grid
assignment.

**Presence-only (Part 18)**: historical outbreak data are PRESENCE
events. This module never creates a `TRUE_NEGATIVE` label from a grid
cell without an outbreak — every grid cell not carrying a
`TARGET_EVENT` is `BACKGROUND` ("a sampled spatial comparison
location"), never asserted to be confirmed disease-free.

**Out-of-domain targets are retained, never dropped (Part 11)**: a
target outside the frozen scientific evaluation domain is recorded with
`domain_status=TARGET_OUTSIDE_EVALUATION_DOMAIN` — it still gets a row
here. Removing it would let domain design artificially improve future
coverage metrics; this module structurally cannot drop a target (there
is no filtering step here at all, only labeling).

**Unique target-event unit (Part 20)**: one row per
`(forecast_origin_id, target_event_id)` pair, matching
`ForecastTarget`'s own uniqueness guarantee within an origin. The same
real target event legitimately appearing from several different
forecast origins is repeated forecasting of one biological event, not
pseudo-replication — never deduplicated away here.

**Deterministic cell assignment (Part 22)**: real polygon containment
(`shapely` in the SAME UTM projection the grid itself was built in),
never nearest-centroid. A point on a shared cell boundary is assigned
to the lexicographically SMALLEST `grid_cell_id` among every cell
whose polygon it touches — an explicit, deterministic, documented tie
rule (TARGET-03).
"""

from __future__ import annotations

from dataclasses import dataclass

import shapely.geometry

from ..geospatial.crs import CrsChoice, build_transformer
from ..geospatial.distance import distance_km
from ..geospatial.scientific_grid import DomainGeometry, ScientificGridCell
from ..geospatial.source_geometry import EligibleSourcePoint

TARGET_EVENT = "TARGET_EVENT"
BACKGROUND = "BACKGROUND"

INSIDE_EVALUATION_DOMAIN = "INSIDE_EVALUATION_DOMAIN"
TARGET_OUTSIDE_EVALUATION_DOMAIN = "TARGET_OUTSIDE_EVALUATION_DOMAIN"


@dataclass(frozen=True)
class TargetGridAssignment:
    forecast_origin_id: str
    target_id: str
    target_event_id: str
    lead_days: int
    target_lat: float
    target_lon: float
    target_grid_cell_id: str | None  # None only if the target falls entirely outside the grid's own rectangular extent
    min_distance_to_eligible_source_km: float | None  # None only if the origin had zero eligible sources
    inside_evaluation_domain: bool
    domain_status: str  # INSIDE_EVALUATION_DOMAIN | TARGET_OUTSIDE_EVALUATION_DOMAIN
    label: str = TARGET_EVENT  # presence-only (Part 18) — never TRUE_POSITIVE/TRUE_NEGATIVE

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id, "target_id": self.target_id,
            "target_event_id": self.target_event_id, "lead_days": self.lead_days,
            "target_lat": self.target_lat, "target_lon": self.target_lon,
            "target_grid_cell_id": self.target_grid_cell_id,
            "min_distance_to_eligible_source_km": self.min_distance_to_eligible_source_km,
            "inside_evaluation_domain": self.inside_evaluation_domain, "domain_status": self.domain_status,
            "label": self.label,
        }


def assign_target_to_scientific_grid(
    *, target, cells: list[ScientificGridCell], domain: DomainGeometry, sources: list[EligibleSourcePoint], crs_choice: CrsChoice,
) -> TargetGridAssignment:
    """`target`: a `ForecastTarget`-shaped object (`target_id`,
    `target_event_id`, `forecast_origin_id`, `lead_days`, `latitude`,
    `longitude`). Never filters/drops — always returns exactly one
    assignment row, even for a target outside the frozen domain or
    outside the grid's own rectangular extent entirely."""
    to_utm = build_transformer(crs_choice.source_crs, crs_choice.analysis_crs)
    x, y = to_utm.transform(target.longitude, target.latitude)
    point = shapely.geometry.Point(x, y)

    matches = sorted(c.grid_cell_id for c in cells if c.polygon().intersects(point))
    containing_cell_id = matches[0] if matches else None

    if sources:
        min_d = min(distance_km(s.latitude, s.longitude, target.latitude, target.longitude) for s in sources)
    else:
        min_d = None
    inside = min_d is not None and min_d <= domain.domain_distance_km
    status = INSIDE_EVALUATION_DOMAIN if inside else TARGET_OUTSIDE_EVALUATION_DOMAIN

    return TargetGridAssignment(
        forecast_origin_id=target.forecast_origin_id, target_id=target.target_id, target_event_id=target.target_event_id,
        lead_days=target.lead_days, target_lat=target.latitude, target_lon=target.longitude,
        target_grid_cell_id=containing_cell_id, min_distance_to_eligible_source_km=min_d,
        inside_evaluation_domain=inside, domain_status=status,
    )
