"""Checkpoint 6D.5 Part 17-19: real host-density observation gathering
WITHOUT weather I/O.

The host-density reference distribution depends only on real GLW4
host-density observations, not on ERA5 weather. Checkpoint 6D's real
smoke used the full `assemble_feature_snapshot` (which also fetches
weather/land-cover/hydrology), making the real network-call runtime
dominated by weather retrieval (~29s/origin) for no reason relevant to
the host transform. This module reuses the SAME real infrastructure
(`source_selector.get_eligible_sources`, `geospatial.grid.build_smoke_grid`,
`geospatial.host_density.fao_glw.extract_grid_cell_density`) the real
assembler uses, but skips weather/land-cover/hydrology entirely —
duplicating no GIS extraction logic, only the orchestration glue.

Returns a `FeatureSnapshot.as_dict()`-shaped dict containing ONLY
`grid_cells[*].host_density` (every other section empty/`None`) so the
rest of `services/factors/` (which already consumes that shape) needs
no special-casing.
"""

from __future__ import annotations

from ...domain.enums import RecordDomainScope
from ...schemas import ValidationMode
from ..geospatial.grid import build_smoke_grid
from ..geospatial.host_density.fao_glw import extract_grid_cell_density
from ..source_selector import get_eligible_sources

DEFAULT_SPECIES = ("cattle", "buffalo")


def _aoi_center(active_sources: list, trigger_source_ids: list) -> tuple[float, float] | None:
    trigger_set = set(trigger_source_ids)
    anchors = [s for s in active_sources if s.source_id in trigger_set] or list(active_sources)
    if not anchors:
        return None
    lat = sum(s.latitude for s in anchors) / len(anchors)
    lon = sum(s.longitude for s in anchors) / len(anchors)
    return lat, lon


def build_host_only_snapshot(
    repo,
    *,
    origin,
    disease: str,
    active_window_days: int,
    grid_half_extent_km: float,
    grid_cell_size_km: float,
    species: tuple = DEFAULT_SPECIES,
) -> dict | None:
    """Returns `None` (never a fabricated snapshot) if this origin has
    no eligible active sources at all, or no AOI center can be
    determined."""
    result = get_eligible_sources(
        repo, disease=disease, t0=origin.t0, active_window_days=active_window_days,
        temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=origin.country, domain_scope=RecordDomainScope.HISTORICAL_ONLY,
    )
    if not result.sources:
        return None
    center = _aoi_center(result.sources, origin.trigger_source_ids_at_t0)
    if center is None:
        return None
    lat, lon = center

    id_prefix = origin.forecast_origin_id.replace(":", "_").replace(" ", "_")
    cells, _crs = build_smoke_grid(center_lat=lat, center_lon=lon, half_extent_km=grid_half_extent_km, cell_size_km=grid_cell_size_km, id_prefix=id_prefix)

    grid_cells = []
    for cell in cells:
        host_density = {sp: extract_grid_cell_density(grid_cell=cell, species=sp).as_dict() for sp in species}
        grid_cells.append({
            "grid_cell_id": cell.grid_cell_id, "centroid_lat": cell.centroid_lat, "centroid_lon": cell.centroid_lon,
            "host_density": host_density, "landcover": {}, "hydrology": None,
        })

    return {
        "snapshot_id": f"HOSTONLY:{origin.forecast_origin_id}",
        "forecast_origin_id": origin.forecast_origin_id,
        "active_source_ids": [s.source_id for s in result.sources],
        "grid_cells": grid_cells,
        "weather": {},  # deliberately empty -- this path never fetches weather (Part 17)
        "source_dataset_versions": {},
        "landcover_comparability_group": None,
    }
