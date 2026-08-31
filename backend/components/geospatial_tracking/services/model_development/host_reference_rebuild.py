"""Checkpoint 7A Parts 16-17 / Checkpoint 7A.6 Parts 10, 26-27 /
Checkpoint 7A.6.1 Parts 1-2, 26-28: rebuild the `FIT_DEVELOPMENT` host
reference on the FROZEN scientific-grid protocol (25km primary local
evaluation envelope, 5km engineering cell size) — never `build_smoke_grid`,
never dependent on ST-DBSCAN, and (7A.6.1 correction) never dependent on
a single global analysis CRS per origin either.

**Superseded architecture (7A.6.1 Part 1)**: the 7A.6 version of this
module projected ALL of one origin's eligible sources into ONE AOI-local
UTM CRS before building a single domain/grid — labeled
`SUPERSEDED_SINGLE_ANALYSIS_CRS_ALL_SOURCE_DOMAIN_7A6` now that the real
7A.6 audit found 9 real origins where that single-CRS assumption was
itself `PROJECTION_CONTEXT_UNSAFE`. `build_scientific_grid_host_only_snapshot`
now builds a `services.geospatial.scientific_domain.ScientificEvaluationDomain`
— sources are first grouped into geodesically-connected computational
components (never ST-DBSCAN), each with its OWN local CRS — and pools
raster extraction cells from every SAFE component's own grid via
`evaluation_domain.all_cells()`. An origin with one or more UNSAFE
components is never silently truncated to its safe components alone for
the PRIMARY reference — see Part 27/`build_scientific_grid_host_reference_development_report`
for the completeness gate.

The 6D.6 host reference (built on the smoke grid, ~5km half-extent
fixture) remains valid methodological history and is NOT deleted —
`SUPERSEDED_FOR_MODEL_FITTING_BY_7A_GRID_PROTOCOL` marks it as no
longer the primary reference for model fitting once the scientific grid
protocol differs materially (cell size, domain rule, sampling
geometry). Its ECDF/quantiles are never automatically reused or forced
to resemble the new distribution.
"""

from __future__ import annotations

from ...domain.enums import RecordDomainScope
from ...schemas import ValidationMode
from ..factors.reference_profile import build_factor_reference_profile
from ..factors.transform_config import FactorTransformConfig
from ..geospatial.host_density.fao_glw import extract_grid_cell_density
from ..geospatial.scientific_domain import build_scientific_evaluation_domain
from ..geospatial.scientific_grid import ScientificGridConfig
from ..geospatial.source_geometry import EligibleSourcePoint
from ..model_fitting_exposure import assert_fit_development_only
from ..source_selector import get_eligible_sources
from .baseline_scoring import MODEL_INPUT_INCOMPLETE, SCORED

DEFAULT_SPECIES: tuple = ("cattle", "buffalo")
SUPERSEDED_FOR_MODEL_FITTING_BY_7A_GRID_PROTOCOL = "SUPERSEDED_FOR_MODEL_FITTING_BY_7A_GRID_PROTOCOL"
SUPERSEDED_SINGLE_ANALYSIS_CRS_ALL_SOURCE_DOMAIN_7A6 = "SUPERSEDED_SINGLE_ANALYSIS_CRS_ALL_SOURCE_DOMAIN_7A6"


def build_scientific_grid_host_only_snapshot(
    repo, *, origin, disease: str, active_window_days: int, grid_config: ScientificGridConfig, species: tuple = DEFAULT_SPECIES,
) -> tuple:
    """Returns `(snapshot_or_None, n_unsafe_components)`. `snapshot` is
    `None` (never a fabricated snapshot) if this origin has no eligible
    active sources. Same host-only shape as
    `services.factors.host_reference_gathering.build_host_only_snapshot`
    (Checkpoint 6D.5) so the rest of `services/factors/` needs no
    special-casing — only HOW the grid cells are built changed (real
    per-component metric-safe polygons on the frozen 25km/5km protocol,
    instead of `build_smoke_grid` or a single origin-wide CRS).
    `n_unsafe_components` is always reported, even when a snapshot was
    still built from the origin's remaining safe components — callers
    requiring full completeness (Part 27) must check it, never assume
    a non-`None` snapshot means every component succeeded."""
    result = get_eligible_sources(
        repo, disease=disease, t0=origin.t0, active_window_days=active_window_days,
        temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=origin.country, domain_scope=RecordDomainScope.HISTORICAL_ONLY,
    )
    if not result.sources:
        return None, 0
    source_points = [EligibleSourcePoint(source_id=s.source_id, latitude=s.latitude, longitude=s.longitude) for s in result.sources]

    evaluation_domain = build_scientific_evaluation_domain(
        forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, sources=source_points, grid_config=grid_config,
        primary_local_evaluation_distance_km=grid_config.domain_distance_km,
    )
    n_unsafe = evaluation_domain.n_unsafe_components()
    cells = evaluation_domain.all_cells()

    grid_cells = []
    for cell in cells:
        host_density = {sp: extract_grid_cell_density(grid_cell=cell, species=sp).as_dict() for sp in species}
        grid_cells.append({
            "grid_cell_id": cell.grid_cell_id, "scientific_cell_id": cell.scientific_cell_id,
            "centroid_lat": cell.centroid_lat, "centroid_lon": cell.centroid_lon,
            "area_km2": cell.area_km2, "domain_overlap_area_km2": cell.domain_overlap_area_km2,
            "host_density": host_density, "landcover": {}, "hydrology": None,
        })

    snapshot = {
        "snapshot_id": f"SCIGRID_HOSTONLY:{origin.forecast_origin_id}",
        "forecast_origin_id": origin.forecast_origin_id,
        "unsafe_component_count": n_unsafe,
        "model_input_status": MODEL_INPUT_INCOMPLETE if n_unsafe > 0 else SCORED,
        "active_source_ids": [s.source_id for s in result.sources],
        "grid_cells": grid_cells,
        "weather": {},  # deliberately empty -- this path never fetches weather
        "source_dataset_versions": {},
        "landcover_comparability_group": None,
    }
    return snapshot, n_unsafe


def build_scientific_grid_host_reference_development_report(
    repo, *, fit_development_origins: list, disease: str, active_window_days: int, grid_config: ScientificGridConfig,
    species: tuple = DEFAULT_SPECIES, transform_config: FactorTransformConfig | None = None, generated_at: str = "",
):
    """Checkpoint 7A.6 Parts 26-27 / 7A.6.1 Parts 26-28 (HOSTREF7A6-01..05,
    HOSTREF7A61-01..05): the ONLY safe real, multi-origin entry point for
    the scientific-grid host reference rebuild — `assert_fit_development_only`
    is called here, at this function's OWN entry point, before ANY
    repository/raster access happens (`HOSTREF7A61-01/02`), never trusting
    a caller to have pre-filtered. Builds one host-only snapshot per origin
    (`build_scientific_grid_host_only_snapshot`, ST-DBSCAN-independent,
    per-component-projected) and pools them via
    `build_factor_reference_profile(..., require_effective_sample_identity=True)`
    (`HOSTREF7A6-04`) — a legacy pixel-set or query-centroid-fallback
    identity can never silently enter this primary pool.

    Returns `(profile, snapshots_by_origin_id, completeness)`.
    `completeness["is_complete"]` (Part 27) is `True` ONLY when every
    intended origin produced a snapshot AND zero origins had any unsafe
    component — a partially-successful subset (dropped difficult
    projections) is never silently reported as complete
    (`HOSTREF7A61-03/04`)."""
    assert_fit_development_only(fit_development_origins, caller="build_scientific_grid_host_reference_development_report")

    snapshots_by_origin_id: dict = {}
    n_with_unsafe_components = 0
    unsafe_origin_ids: list = []
    for origin in sorted(fit_development_origins, key=lambda o: o.forecast_origin_id):
        snap, n_unsafe = build_scientific_grid_host_only_snapshot(
            repo, origin=origin, disease=disease, active_window_days=active_window_days, grid_config=grid_config, species=species,
        )
        if snap is None:
            continue
        snapshots_by_origin_id[origin.forecast_origin_id] = snap
        if n_unsafe > 0:
            n_with_unsafe_components += 1
            unsafe_origin_ids.append(origin.forecast_origin_id)

    profile = build_factor_reference_profile(
        fit_development_origins=fit_development_origins, feature_snapshots_by_origin_id=snapshots_by_origin_id,
        transform_config=transform_config or FactorTransformConfig(), generated_at=generated_at,
        require_effective_sample_identity=True,
    )

    intended_origin_count = len(fit_development_origins)
    successful_snapshot_origin_count = len(snapshots_by_origin_id)
    blocked_origin_count = intended_origin_count - successful_snapshot_origin_count
    completeness = {
        "intended_origin_count": intended_origin_count,
        "successful_snapshot_origin_count": successful_snapshot_origin_count,
        "blocked_origin_count": blocked_origin_count,
        "unexpected_origin_count": len(set(snapshots_by_origin_id) - {o.forecast_origin_id for o in fit_development_origins}),
        "n_origins_with_unsafe_components": n_with_unsafe_components,
        "unsafe_origin_ids": sorted(unsafe_origin_ids),
        "is_complete": blocked_origin_count == 0 and n_with_unsafe_components == 0,
    }
    return profile, snapshots_by_origin_id, completeness
