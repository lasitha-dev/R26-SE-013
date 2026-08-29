"""Checkpoint 5 Part 8: source-specific geometry for every (grid cell,
eligible source) pair.

Later PISTES needs, for every grid cell `i` and every eligible source `j`
(not just the nearest one — GEO-05, "keep geometry for ALL eligible
sources"):

    geometry_by_source[source_id] = {distance_km, t_hat_east, t_hat_north}

with the unit vector pointing SOURCE -> GRID CELL (never the reverse —
see `services/geospatial/distance.py`'s `source_to_cell_unit_vector`,
which this module is a thin batching layer over; no separate distance/
bearing math is reimplemented here).

"Nearest source" is NOT computed by this module — the docstring
explicitly notes it may later be derived for display/reference only from
this full per-source geometry, not the other way around.
"""

from __future__ import annotations

from dataclasses import dataclass

from .distance import SourceToCellVector, source_to_cell_unit_vector
from .grid import GridCell


@dataclass(frozen=True)
class EligibleSourcePoint:
    source_id: str
    latitude: float
    longitude: float


def build_geometry_by_source(
    cell: GridCell, sources: list[EligibleSourcePoint]
) -> dict[str, SourceToCellVector]:
    """One entry per source in `sources`, keyed by `source_id` — every
    eligible source gets its own geometry against this cell, never just
    the closest one."""
    return {
        source.source_id: source_to_cell_unit_vector(
            source.latitude, source.longitude, cell.centroid_lat, cell.centroid_lon
        )
        for source in sources
    }


def build_geometry_for_grid(
    cells: list[GridCell], sources: list[EligibleSourcePoint]
) -> dict[str, dict[str, SourceToCellVector]]:
    """`{grid_cell_id: {source_id: SourceToCellVector}}` for every cell in
    `cells` against every source in `sources`."""
    return {cell.grid_cell_id: build_geometry_by_source(cell, sources) for cell in cells}


def nearest_source_id(geometry_by_source: dict[str, SourceToCellVector]) -> str | None:
    """Display/reference convenience ONLY (master-prompt Part 8: "Nearest
    source may later be computed for display/reference only") — derived
    from the full per-source geometry this module already keeps, never a
    replacement for it. Returns None for an empty geometry dict."""
    if not geometry_by_source:
        return None
    return min(geometry_by_source.items(), key=lambda kv: kv[1].distance_km)[0]
