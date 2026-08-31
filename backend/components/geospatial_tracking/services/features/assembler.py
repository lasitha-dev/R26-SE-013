"""Checkpoint 6A / 6A.5 Parts 2, 4-11: the feature-assembly orchestrator.

    Prediction context (a ForecastOrigin)
        -> eligible sources (source_selector.get_eligible_sources)
        -> grid (geospatial.grid.build_smoke_grid)
        -> geospatial/environmental adapters (host density, land cover,
           hydrology per policy; weather once at the AOI center)
        -> FeatureSnapshot
        -> LATER PISTES engine (not built here)

`assemble_feature_snapshot` is the ONLY function in this module a caller
needs. It never computes risk, direction, or speed, and it never reads
any field describing a future outcome (Part 19) — its only inputs are
`t0` (via `forecast_origin`), the eligible-source set AT `t0`, the grid,
and the declared environmental adapters/policy (`FeaturePolicy`, which
now validates every field at construction time — see `feature_policy.py`).

**Weather spatial sampling (Part 10): AOI_CENTER, once per snapshot.**
ERA5's real resolution (~25km, `WEATHER_MODEL_RESOLUTION`) is coarser
than this checkpoint's entire smoke grid extent (a 5-10km half-extent,
2.5km cells) — sampling weather separately at every grid-cell centroid
or at every individual source would not add any real spatial
information (most or all cells fall inside the SAME ERA5 grid box), it
would only multiply redundant API calls and imply a false precision the
data doesn't have. Weather is therefore evaluated ONCE, at the AOI
center (the centroid of the forecast origin's own TRIGGER sources — the
real reason this forecast origin exists — falling back to the centroid
of all active sources if no trigger source is present in the active
set), and the same `weather` block is shared by every grid cell in the
snapshot. `weather_source_resolution` is preserved so this is never
mistaken for per-cell-resolved weather.

**Checkpoint 6A.5 — two explicit identities.** `feature_policy_hash`
(what was DECLARED — `FeaturePolicy.protocol_hash()`) and
`resolved_data_signature_hash` (what ACTUALLY resolved — real dataset
versions, real weather-cutoff timezone, etc. — `resolved_data_signature.py`)
are computed and hashed separately; `compute_snapshot_id` combines both
plus `t0_precision`/`temporal_mode`/`country_scope`/`disease` so two
snapshots that differ in any feature-affecting way never share an ID.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime, timezone

from ...domain.enums import RecordDomainScope
from ...schemas import ValidationMode
from ..source_selector import EligibleSource, get_eligible_sources
from ..geospatial.grid import build_smoke_grid
from ..geospatial.host_density.fao_glw import REFERENCE_YEAR as GLW_REFERENCE_YEAR
from ..geospatial.host_density.fao_glw import extract_grid_cell_density
from ..geospatial.hydrology.hydrosheds import DATASET_VERSION as HYDRORIVERS_DATASET_VERSION
from ..geospatial.hydrology.hydrosheds import distance_to_nearest_river_km
from ..geospatial.landcover.esa_worldcover import WORLDCOVER_VERSIONS, extract_landcover_fractions
from ..geospatial.source_geometry import EligibleSourcePoint, build_geometry_for_grid
from ..geospatial.weather.base import T0Precision
from ..geospatial.weather.era5 import DATASET_VERSION as ERA5_DATASET_VERSION
from ..geospatial.weather.era5 import WEATHER_MODEL_RESOLUTION, WEATHER_PROVIDER, build_pre_t0_weather_summary
from .contracts import FeatureSnapshot, GridCellFeatures, SnapshotReadiness, compute_snapshot_id
from .feature_policy import (
    FEATURE_PROTOCOL_VERSION,
    LANDCOVER_MODE_FROZEN_STATIC_REFERENCE,
    LANDCOVER_MODE_OMIT,
    LANDCOVER_MODE_YEAR_MATCHED_REFERENCE,
    PRIMARY_WEATHER_TEMPORAL_ROLE,
    FeaturePolicy,
)
from .resolved_data_signature import compute_resolved_data_signature, landcover_comparability_group

WEATHER_SAMPLING_LOCATION = "AOI_CENTER"


def _is_finite_coord(lat: float, lon: float) -> bool:
    return math.isfinite(lat) and math.isfinite(lon)


def _aoi_center(active_sources: list[EligibleSource], trigger_source_ids: list[str]) -> tuple[float, float, list[str]]:
    """The AOI center is the centroid of the forecast origin's own
    TRIGGER sources (why this origin exists) when at least one trigger
    source is present in the active set; otherwise the centroid of every
    active source. Returns `(lat, lon, anchor_source_ids)` — the anchor
    ids are recorded in `grid_meta` for full traceability."""
    trigger_set = set(trigger_source_ids)
    anchors = [s for s in active_sources if s.source_id in trigger_set]
    if not anchors:
        anchors = list(active_sources)
    if not anchors:
        raise ValueError("cannot determine an AOI center: no active or trigger sources")
    lat = sum(s.latitude for s in anchors) / len(anchors)
    lon = sum(s.longitude for s in anchors) / len(anchors)
    return lat, lon, [s.source_id for s in anchors]


def _landcover_for_cell(*, center_lat: float, center_lon: float, half_extent_km: float, policy: FeaturePolicy, target_year: str) -> dict | None:
    lc = policy.landcover_policy
    if lc.mode == LANDCOVER_MODE_OMIT:
        return None
    if lc.mode == LANDCOVER_MODE_YEAR_MATCHED_REFERENCE:
        if target_year not in WORLDCOVER_VERSIONS:
            # Part 12: never silently guess a year-matched product that
            # doesn't exist -- stays NOT_SELECTED, not a fabricated match.
            return None
        worldcover_year = target_year
    elif lc.mode == LANDCOVER_MODE_FROZEN_STATIC_REFERENCE:
        worldcover_year = lc.frozen_worldcover_year
    else:
        return None
    results = extract_landcover_fractions(
        center_lat=center_lat,
        center_lon=center_lon,
        half_extent_km=half_extent_km,
        worldcover_year=worldcover_year,
        target_year=target_year,
    )
    return {r.feature_name: r.as_dict() for r in results}


def _hydrology_for_cell(*, center_lat: float, center_lon: float, policy: FeaturePolicy) -> dict | None:
    """`policy.hydrorivers_search_radius_km` is a GEOSPATIAL_QUERY_LIMIT
    (Checkpoint 6A.5 Part 5) — how far the HydroRIVERS search window
    looks, never a biological spread-distance claim. If no river falls
    within it, `distance_to_nearest_river_km` itself already returns
    MISSING rather than fabricating a `distance == radius` boundary
    value (verified in `hydrosheds.py`, HYDRO-POLICY-03)."""
    if not policy.hydrology_include:
        return None
    result = distance_to_nearest_river_km(
        center_lat=center_lat, center_lon=center_lon, search_radius_km=policy.hydrorivers_search_radius_km
    )
    return result.as_dict()


def _landcover_dataset_version(*, policy: FeaturePolicy, target_year: str) -> str:
    if policy.landcover_policy.mode == LANDCOVER_MODE_OMIT:
        return "NOT_SELECTED"
    if policy.landcover_policy.mode == LANDCOVER_MODE_FROZEN_STATIC_REFERENCE:
        return WORLDCOVER_VERSIONS[policy.landcover_policy.frozen_worldcover_year].dataset_version_label
    if target_year in WORLDCOVER_VERSIONS:
        return WORLDCOVER_VERSIONS[target_year].dataset_version_label
    return "NOT_SELECTED"


def assemble_feature_snapshot(
    repo,
    *,
    forecast_origin,
    policy: FeaturePolicy,
    t0_precision: str = T0Precision.DATE_ONLY.value,
    weather_cache=None,
) -> FeatureSnapshot:
    """`forecast_origin`: a `services.forecast_origin.ForecastOrigin` (or
    anything with the same `forecast_origin_id`/`country`/`t0`/
    `temporal_mode`/`trigger_source_ids_at_t0` attributes).

    Depends ONLY on `t0` (via `forecast_origin.t0`), the eligible-source
    set AT that `t0` (Part 19 — `get_eligible_sources` already enforces
    the T0 invariant: no source with `effective_availability_date > t0`
    can ever appear), the grid, and the declared environmental
    adapters/policy. Accepts no target/label/lead_days/outcome parameter
    of any kind — there is structurally nothing a caller could pass that
    would leak a future outcome into this function (LEAK-ASSEMBLY-01/02).

    Weather always uses `strict_operational_availability=False` and
    `model=policy.weather_model` (validated `== "era5"` at `FeaturePolicy`
    construction, and `era5.py` itself now refuses to silently request a
    different model than declared — Checkpoint 6A.5 Part 2) — the primary
    historical assembly path never uses the ERA5T_LAG_FILTER_SENSITIVITY
    diagnostic mode, and `temporal_role` is always `PRIMARY_WEATHER_TEMPORAL_ROLE`.
    """
    temporal_mode = ValidationMode(forecast_origin.temporal_mode)
    eligible_result = get_eligible_sources(
        repo,
        disease=policy.disease,
        t0=forecast_origin.t0,
        active_window_days=policy.active_window_days,
        temporal_mode=temporal_mode,
        country_scope=forecast_origin.country,
        domain_scope=RecordDomainScope.HISTORICAL_ONLY,
    )
    active_sources = eligible_result.sources
    active_source_ids = [s.source_id for s in active_sources]

    readiness_notes: list[str] = []

    valid_sources = [s for s in active_sources if _is_finite_coord(s.latitude, s.longitude)]
    _valid_ids_set = {s.source_id for s in valid_sources}
    invalid_source_ids = [s.source_id for s in active_sources if s.source_id not in _valid_ids_set]
    if invalid_source_ids:
        readiness_notes.append(
            f"sources excluded from geometry_by_source due to non-finite coordinates: {invalid_source_ids}"
        )

    policy_hash = policy.protocol_hash()
    grid_config_for_id = {"half_extent_km": policy.grid_half_extent_km, "cell_size_km": policy.grid_cell_size_km}

    if not valid_sources:
        # No usable source at all -- nothing was actually resolved.
        generated_at = datetime.now(timezone.utc).isoformat()
        resolved_signature_hash = compute_resolved_data_signature(
            feature_policy_hash=policy_hash,
            landcover_dataset_version="NOT_RESOLVED",
            host_density_dataset_version="NOT_RESOLVED",
            weather_provider="NOT_RESOLVED",
            weather_model="NOT_RESOLVED",
            weather_model_resolution="NOT_RESOLVED",
            weather_temporal_role="NOT_RESOLVED",
            weather_sampling_strategy=WEATHER_SAMPLING_LOCATION,
            hydrology_dataset_version="NOT_RESOLVED",
            resolved_t0_cutoff_utc=None,
            source_timezone=None,
        )
        snapshot_id = compute_snapshot_id(
            forecast_origin_id=forecast_origin.forecast_origin_id,
            t0=forecast_origin.t0,
            t0_precision=t0_precision,
            temporal_mode=forecast_origin.temporal_mode,
            country_scope=forecast_origin.country,
            disease=policy.disease,
            active_source_ids=active_source_ids,
            grid_config=grid_config_for_id,
            feature_policy_hash=policy_hash,
            resolved_data_signature_hash=resolved_signature_hash,
        )
        return FeatureSnapshot(
            snapshot_id=snapshot_id,
            forecast_origin_id=forecast_origin.forecast_origin_id,
            t0=forecast_origin.t0,
            t0_precision=t0_precision,
            temporal_mode=forecast_origin.temporal_mode,
            country_scope=forecast_origin.country,
            disease=policy.disease,
            active_source_ids=active_source_ids,
            active_source_count=len(active_source_ids),
            feature_protocol_version=FEATURE_PROTOCOL_VERSION,
            feature_protocol_config=policy.config_dict(),
            feature_policy_hash=policy_hash,
            resolved_data_signature_hash=resolved_signature_hash,
            readiness=SnapshotReadiness.INCOMPLETE_REQUIRED_FEATURE.value,
            readiness_notes=readiness_notes + ["no eligible source with valid coordinates at t0"],
            generated_at=generated_at,
        )

    aoi_lat, aoi_lon, anchor_source_ids = _aoi_center(valid_sources, forecast_origin.trigger_source_ids_at_t0)

    cells, crs_choice = build_smoke_grid(
        center_lat=aoi_lat,
        center_lon=aoi_lon,
        half_extent_km=policy.grid_half_extent_km,
        cell_size_km=policy.grid_cell_size_km,
        id_prefix=forecast_origin.forecast_origin_id.replace(" ", "_").replace(":", "_"),
    )

    eligible_points = [EligibleSourcePoint(source_id=s.source_id, latitude=s.latitude, longitude=s.longitude) for s in valid_sources]
    geometry_by_grid = build_geometry_for_grid(cells, eligible_points)

    valid_source_ids = {s.source_id for s in valid_sources}
    for cell in cells:
        cell_geometry_ids = set(geometry_by_grid[cell.grid_cell_id].keys())
        if cell_geometry_ids != valid_source_ids:
            missing = valid_source_ids - cell_geometry_ids
            readiness_notes.append(f"cell {cell.grid_cell_id} missing geometry for sources: {sorted(missing)}")

    target_year = forecast_origin.t0[:4]

    grid_cells: list[GridCellFeatures] = []
    for cell in cells:
        host_density = {}
        for species in policy.host_density_species:
            r = extract_grid_cell_density(grid_cell=cell, species=species)
            host_density[species] = r.as_dict()

        landcover = _landcover_for_cell(
            center_lat=cell.centroid_lat,
            center_lon=cell.centroid_lon,
            half_extent_km=cell.cell_size_km / 2.0,
            policy=policy,
            target_year=target_year,
        )
        hydrology = _hydrology_for_cell(center_lat=cell.centroid_lat, center_lon=cell.centroid_lon, policy=policy)

        grid_cells.append(
            GridCellFeatures(
                grid_cell_id=cell.grid_cell_id,
                row=cell.row,
                col=cell.col,
                centroid_lat=cell.centroid_lat,
                centroid_lon=cell.centroid_lon,
                cell_size_km=cell.cell_size_km,
                area_km2=cell.area_km2,
                geometry_by_source={sid: asdict(vec) for sid, vec in geometry_by_grid[cell.grid_cell_id].items()},
                host_density=host_density,
                landcover=landcover,
                hydrology=hydrology,
            )
        )

    # Part 8: primary assembly is ALWAYS strict_operational_availability=False,
    # and model=policy.weather_model, which __post_init__ already restricted
    # to "era5" -- era5.py itself now refuses to silently substitute a
    # different model than requested (Checkpoint 6A.5 Part 2 fix).
    weather_window, weather_results = build_pre_t0_weather_summary(
        latitude=aoi_lat,
        longitude=aoi_lon,
        t0=forecast_origin.t0,
        t0_precision=t0_precision,
        lookback_hours=policy.weather_lookback_hours,
        model=policy.weather_model,
        strict_operational_availability=False,
        cache=weather_cache,
    )
    assert weather_window.temporal_role == PRIMARY_WEATHER_TEMPORAL_ROLE, (
        f"primary historical assembly must always resolve {PRIMARY_WEATHER_TEMPORAL_ROLE!r}, "
        f"got {weather_window.temporal_role!r} -- this is a code bug, not a valid runtime state"
    )
    weather_block = {
        "window": weather_window.as_dict(),
        "results": {r.feature_name: r.as_dict() for r in weather_results},
        # Part 9: explicit, never silently claimed as scientifically frozen.
        "lookback_hours": policy.weather_lookback_hours,
        "lookback_hours_status": "UNFROZEN_DEVELOPMENT_PARAMETER",
    }

    # -- feature_status_summary (Part 15) -----------------------------------
    status_summary: dict[str, int] = {}

    def _bump(status: str) -> None:
        status_summary[status] = status_summary.get(status, 0) + 1

    for cell in grid_cells:
        for r in cell.host_density.values():
            _bump(r["status"])
        if cell.landcover is None:
            _bump("NOT_SELECTED")
        else:
            for r in cell.landcover.values():
                _bump(r["status"])
        if cell.hydrology is None:
            _bump("NOT_SELECTED")
        else:
            _bump(cell.hydrology["status"])
    for r in weather_results:
        _bump(r.status)

    # -- source_dataset_versions ---------------------------------------------
    landcover_version = _landcover_dataset_version(policy=policy, target_year=target_year)
    source_dataset_versions = {
        "host_density": f"GLW4 reference_year={GLW_REFERENCE_YEAR}",
        "landcover": landcover_version,
        "weather": ERA5_DATASET_VERSION,
        "hydrology": HYDRORIVERS_DATASET_VERSION if policy.hydrology_include else "NOT_SELECTED",
    }
    lc_comparability_group = landcover_comparability_group(landcover_version)

    # -- readiness (Part 15) --------------------------------------------------
    if invalid_source_ids or any("missing geometry" in n for n in readiness_notes) or not grid_cells:
        readiness = SnapshotReadiness.INCOMPLETE_REQUIRED_FEATURE.value
    elif any(status_summary.get(s, 0) > 0 for s in ("MISSING", "BLOCKED", "DEMO")):
        readiness = SnapshotReadiness.CANDIDATE_FEATURE_MISSING.value
    else:
        readiness = SnapshotReadiness.COMPLETE_FOR_ASSEMBLY.value

    grid_meta = {
        "n_cells": len(cells),
        "analysis_crs": crs_choice.as_dict(),
        "half_extent_km": policy.grid_half_extent_km,
        "cell_size_km": policy.grid_cell_size_km,
        "center_lat": aoi_lat,
        "center_lon": aoi_lon,
        "aoi_anchor_source_ids": anchor_source_ids,
        "weather_source_resolution": WEATHER_MODEL_RESOLUTION,
    }

    # -- Checkpoint 6A.5 Parts 7, 10: resolved data signature -----------------
    resolved_signature_hash = compute_resolved_data_signature(
        feature_policy_hash=policy_hash,
        landcover_dataset_version=landcover_version,
        host_density_dataset_version=source_dataset_versions["host_density"],
        weather_provider=WEATHER_PROVIDER,
        weather_model=weather_window.weather_model,
        weather_model_resolution=weather_window.weather_model_resolution,
        weather_temporal_role=weather_window.temporal_role,
        weather_sampling_strategy=WEATHER_SAMPLING_LOCATION,
        hydrology_dataset_version=source_dataset_versions["hydrology"],
        resolved_t0_cutoff_utc=weather_window.window_end,
        source_timezone=weather_window.source_timezone,
    )

    snapshot_id = compute_snapshot_id(
        forecast_origin_id=forecast_origin.forecast_origin_id,
        t0=forecast_origin.t0,
        t0_precision=t0_precision,
        temporal_mode=forecast_origin.temporal_mode,
        country_scope=forecast_origin.country,
        disease=policy.disease,
        active_source_ids=active_source_ids,
        grid_config=grid_config_for_id,
        feature_policy_hash=policy_hash,
        resolved_data_signature_hash=resolved_signature_hash,
    )
    generated_at = datetime.now(timezone.utc).isoformat()

    return FeatureSnapshot(
        snapshot_id=snapshot_id,
        forecast_origin_id=forecast_origin.forecast_origin_id,
        t0=forecast_origin.t0,
        t0_precision=t0_precision,
        temporal_mode=forecast_origin.temporal_mode,
        country_scope=forecast_origin.country,
        disease=policy.disease,
        active_source_ids=active_source_ids,
        active_source_count=len(active_source_ids),
        grid_meta=grid_meta,
        grid_cells=grid_cells,
        weather=weather_block,
        weather_sampling_location=WEATHER_SAMPLING_LOCATION,
        feature_status_summary=status_summary,
        source_dataset_versions=source_dataset_versions,
        landcover_comparability_group=lc_comparability_group,
        source_timezone=weather_window.source_timezone,
        t0_timezone_quality=weather_window.t0_timezone_quality,
        resolved_t0_cutoff_utc=weather_window.window_end,
        feature_protocol_version=FEATURE_PROTOCOL_VERSION,
        feature_protocol_config=policy.config_dict(),
        feature_policy_hash=policy_hash,
        resolved_data_signature_hash=resolved_signature_hash,
        readiness=readiness,
        readiness_notes=readiness_notes,
        generated_at=generated_at,
    )
