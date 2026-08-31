"""Checkpoint 5 Part 7: reusable computational grid generator.

**Grid resolution is a COMPUTATIONAL resolution, not model accuracy.** A
500m grid cell size means feature extraction is computed at 500m
granularity — it is never a claim that any resulting prediction is
accurate to 500m. Every `GridCell.as_dict()` / manifest row this module
produces should be read alongside that caveat; nothing in this module or
its callers labels grid resolution as prediction accuracy (GRID-03).

For Checkpoint 5, grids are SMOKE-TEST scale only (a handful to a few
hundred cells around one real historical source's coordinates) — never a
national 10m grid. `id_prefix` + deterministic row/col enumeration keeps
`grid_cell_id` values stable and reproducible across runs (GRID-01).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from .crs import CrsChoice, analysis_crs_for
from .distance import distance_km


@dataclass(frozen=True)
class GridCell:
    grid_cell_id: str
    row: int
    col: int
    centroid_lat: float
    centroid_lon: float
    cell_size_km: float
    area_km2: float
    source_crs: str
    analysis_crs: str

    def as_dict(self) -> dict:
        return {
            "grid_cell_id": self.grid_cell_id,
            "row": self.row,
            "col": self.col,
            "centroid_lat": self.centroid_lat,
            "centroid_lon": self.centroid_lon,
            "cell_size_km": self.cell_size_km,
            "area_km2": self.area_km2,
            "source_crs": self.source_crs,
            "analysis_crs": self.analysis_crs,
        }


def build_smoke_grid(
    *,
    center_lat: float,
    center_lon: float,
    half_extent_km: float,
    cell_size_km: float,
    id_prefix: str = "CELL",
) -> tuple[list[GridCell], CrsChoice]:
    """A small square grid of cells centered on `(center_lat, center_lon)`,
    spanning `+/- half_extent_km` in each direction, cell edge length
    `cell_size_km`. Deliberately simple (degree-per-km approximated
    locally from the AOI centroid's own latitude, then refined by
    geodesic distance for the reported `cell_size_km`/`area_km2`) — this
    is smoke-test-scale grid construction, not a production-grade equal-
    area grid.

    `half_extent_km` and `cell_size_km` are NOT derived from the resulting
    AOI itself (no normalization by AOI bounds) — they are caller-supplied
    parameters, matching master-prompt Part 3 "Do not use AOI bounds as a
    source of normalization."
    """
    if half_extent_km <= 0 or cell_size_km <= 0:
        raise ValueError("half_extent_km and cell_size_km must both be > 0")

    crs_choice = analysis_crs_for(center_lat, center_lon)

    # local degrees-per-km at this AOI's own latitude — used ONLY to lay
    # out grid cell centers roughly evenly; every reported distance/area
    # figure is separately computed via the real geodesic functions above,
    # never taken from this local approximation.
    km_per_deg_lat = distance_km(center_lat, center_lon, center_lat + 0.01, center_lon) / 0.01
    km_per_deg_lon = distance_km(center_lat, center_lon, center_lat, center_lon + 0.01) / 0.01
    deg_per_km_lat = 1.0 / km_per_deg_lat
    deg_per_km_lon = 1.0 / km_per_deg_lon

    n_cells_per_side = max(1, ceil((2 * half_extent_km) / cell_size_km))
    if n_cells_per_side % 2 == 0:
        n_cells_per_side += 1  # keep the center cell centered on (center_lat, center_lon)
    half_n = n_cells_per_side // 2

    cells: list[GridCell] = []
    for row in range(-half_n, half_n + 1):
        for col in range(-half_n, half_n + 1):
            cell_lat = center_lat + row * cell_size_km * deg_per_km_lat
            cell_lon = center_lon + col * cell_size_km * deg_per_km_lon

            # real geodesic edge lengths for THIS cell's own centroid latitude
            edge_km_lat = distance_km(cell_lat, cell_lon, cell_lat + cell_size_km * deg_per_km_lat, cell_lon)
            edge_km_lon = distance_km(cell_lat, cell_lon, cell_lat, cell_lon + cell_size_km * deg_per_km_lon)

            cells.append(
                GridCell(
                    grid_cell_id=f"{id_prefix}:{row + half_n:04d}:{col + half_n:04d}",
                    row=row + half_n,
                    col=col + half_n,
                    centroid_lat=cell_lat,
                    centroid_lon=cell_lon,
                    cell_size_km=cell_size_km,
                    area_km2=edge_km_lat * edge_km_lon,
                    source_crs=crs_choice.source_crs,
                    analysis_crs=crs_choice.analysis_crs,
                )
            )

    return cells, crs_choice
