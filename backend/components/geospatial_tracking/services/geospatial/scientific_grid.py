"""Checkpoint 7A Parts 1-6, 12-15 / Checkpoint 7A.5 Parts 10-18: the
production scientific evaluation grid — metric-safe, AOI-aware, t0-safe
by construction, and (7A.5 correction) masked to the TRUE source-buffer
UNION rather than its rectangular bounding box.

Distinguished from `build_smoke_grid` (Checkpoint 5), which remains a
degree-approximated smoke/test-scale fixture ONLY — never used by the
model-development pipeline (GRID7A-02).

**GRID RESOLUTION != DATA ACCURACY (Part 3)**: a computational grid cell
size never implies GLW4/ERA5/GPS-precision/prediction accuracy at that
resolution. Source-resolution metadata is preserved independently by
each adapter, never overwritten here.

**Checkpoint 7A.5 Part 16 terminology correction**: buffers are built by
projecting each source point into a local UTM (planar-metric) CRS and
buffering there — this is a `PROJECTED_METRIC_BUFFER_UNION`, NEVER a
"geodesic buffer union" (a true geodesic buffer would trace constant
geodesic distance on the ellipsoid itself, which this module does not
do). Every docstring/label in this module uses the correct term.

**Checkpoint 7A.5 Parts 10-15: true-domain grid masking**. Checkpoint
7A's `build_scientific_grid` tiled the COMPLETE rectangular bounding box
of the source-buffer union — including empty space between
geographically disconnected source-buffer components, and the four
"corner" gaps between a circular buffer and its own bounding square.
That rectangular tiling is no longer the scientific evaluation grid.
The TRUE evaluation domain is the buffer UNION itself:

1. The actual projected union geometry is constructed and kept (not
   just its bounds) — `DomainGeometry.union_geometry_digest` plus the
   in-process union geometry object.
2. If the union is a `MultiPolygon` (geographically disconnected source
   groups), its components are preserved individually and tiled
   INDEPENDENTLY, each over its own local bounding box — never one
   rectangle spanning every component (which would silently fill the
   gap between disconnected outbreak situations with grid cells).
3. A cell is only ever returned if it has POSITIVE intersection area
   with the true union (`domain_overlap_area_km2 > 0`) —
   `intersects_true_domain` is always `True` for a returned cell; there
   is no code path that can return a zero-overlap "gap" cell
   (`build_scientific_grid` filters before appending, structurally,
   not via a post-hoc flag a caller could ignore).
4. A cell may still be only PARTIALLY inside the true domain (an edge
   cell) — `area_km2` remains the FULL square-cell area (an engineering
   fact, unchanged meaning from 7A), while `domain_overlap_area_km2`/
   `domain_overlap_fraction` explicitly report how much of that square
   is actually inside the evaluation domain. Nothing here "pretends"
   the whole square is inside (Part 13).

**Checkpoint 7A.5 Parts 17-18: projection-safety hardening**. A single
AOI-local UTM zone (chosen from the mean of the domain's own source
coordinates) is only a safe planar-metric approximation for a
sufficiently LOCAL, compact source group. `assess_projection_safety`
computes real diagnostics (max pairwise geodesic distance, UTM zones
touched, and the actual relative distortion between real geodesic
distance and projected planar distance for the domain's own most
widely separated source pair) and compares the distortion against a
PREDECLARED SOFTWARE geometry tolerance (`PROJECTION_DISTORTION_REL_TOL`,
versioned — never retuned using predictive performance).
`build_scientific_grid` refuses (`ValueError`, never silently
continues) to tile a domain whose `projection_safety.status !=
PROJECTION_CONTEXT_SAFE` — a genuinely unsafe context is blocked, not
quietly given a distorted grid.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from math import ceil

import shapely.geometry
import shapely.ops

from .crs import CrsChoice, analysis_crs_for, build_transformer, utm_zone_for
from .distance import distance_km
from .source_geometry import EligibleSourcePoint

GEOMETRY_VERSION = "7A.6.1"
CRS_STRATEGY_AOI_LOCAL_UTM = "AOI_LOCAL_UTM"
BUFFER_METHOD_PROJECTED_METRIC_UNION = "PROJECTED_METRIC_BUFFER_UNION"  # Part 16 — never "geodesic"

# Checkpoint 7A.6 Parts 7, 24: domain-distance and cell-size status are
# tracked SEPARATELY — a domain distance can be frozen as an OPERATIONAL
# evaluation envelope while a cell size is frozen as an ENGINEERING
# resolution; neither label is ever conflated with the other, and neither
# is a biological/scientific-accuracy claim.
CELL_SIZE_STATUS_UNFROZEN_ENGINEERING_CANDIDATE = "UNFROZEN_ENGINEERING_CANDIDATE"
CELL_SIZE_STATUS_FROZEN_ENGINEERING_RESOLUTION = "FROZEN_ENGINEERING_RESOLUTION"
DOMAIN_DISTANCE_STATUS_CANDIDATE = "UNFROZEN_DOMAIN_CANDIDATE"
DOMAIN_DISTANCE_STATUS_FROZEN = "FROZEN_EVALUATION_DOMAIN_RULE"  # legacy 7A/7A.5 label — superseded by the operational-envelope framing below
DOMAIN_DISTANCE_STATUS_FROZEN_OPERATIONAL_ENVELOPE = "FROZEN_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE"

DOMAIN_MODE_SOURCE_BUFFER_UNION = "SOURCE_BUFFER_UNION_TRUE_DOMAIN"

# Part 18: predeclared SOFTWARE geometry tolerance for projection safety.
# Versioned so a future change is visible in every identity that includes
# it — never retuned using predictive/held-out performance.
PROJECTION_DISTORTION_REL_TOL = 0.01  # 1% relative planar-vs-geodesic distance distortion
PROJECTION_TOLERANCE_VERSION = "7A.5.1"
PROJECTION_CONTEXT_SAFE = "PROJECTION_CONTEXT_SAFE"
PROJECTION_CONTEXT_UNSAFE = "PROJECTION_CONTEXT_UNSAFE"

_GEOM_DIGEST_DECIMALS = 3  # millimeter precision in UTM meters — a software numerical tolerance for the identity digest only


@dataclass(frozen=True)
class ScientificGridConfig:
    """Every field here is feature/model-affecting and participates in
    `scientific_grid_config_hash()` (never `generated_at`)."""

    cell_size_km: float
    domain_mode: str
    domain_distance_km: float
    crs_strategy: str = CRS_STRATEGY_AOI_LOCAL_UTM
    geometry_version: str = GEOMETRY_VERSION
    domain_distance_status: str = DOMAIN_DISTANCE_STATUS_CANDIDATE
    cell_size_status: str = CELL_SIZE_STATUS_UNFROZEN_ENGINEERING_CANDIDATE
    projection_tolerance_version: str = PROJECTION_TOLERANCE_VERSION

    def __post_init__(self) -> None:
        if self.cell_size_km <= 0:
            raise ValueError(f"cell_size_km must be > 0, got {self.cell_size_km!r}")
        if self.domain_distance_km <= 0:
            raise ValueError(f"domain_distance_km must be > 0, got {self.domain_distance_km!r}")
        if self.domain_mode != DOMAIN_MODE_SOURCE_BUFFER_UNION:
            raise ValueError(f"unknown domain_mode {self.domain_mode!r}")

    def config_dict(self) -> dict:
        return {
            "cell_size_km": self.cell_size_km, "domain_mode": self.domain_mode,
            "domain_distance_km": self.domain_distance_km, "crs_strategy": self.crs_strategy,
            "geometry_version": self.geometry_version, "domain_distance_status": self.domain_distance_status,
            "cell_size_status": self.cell_size_status, "projection_tolerance_version": self.projection_tolerance_version,
        }

    def scientific_grid_config_hash(self) -> str:
        canonical = json.dumps(self.config_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ScientificGridCell:
    grid_cell_id: str
    row: int
    col: int
    component_index: int  # which disconnected true-domain component this cell's local tiling belongs to
    centroid_lat: float
    centroid_lon: float
    cell_size_km: float
    area_km2: float  # FULL square-cell area (engineering fact) — never pretends to be the overlap area
    domain_overlap_area_km2: float  # Part 12: actual intersection with the true domain
    domain_overlap_fraction: float  # Part 12-13: explicit, never hidden
    intersects_true_domain: bool  # always True for a returned cell (Part 12)
    source_crs: str
    analysis_crs: str
    bounds_utm: tuple  # (minx, miny, maxx, maxy) meters, in analysis_crs — for geometry verification/reuse
    # Checkpoint 7A.6.2 Part 4: a deterministic, configuration/projection-
    # sensitive identity — `None` for a cell built outside the
    # componentized pipeline (e.g. a bare single-domain `build_scientific_grid`
    # call); populated by `services.geospatial.scientific_domain` for every
    # componentized scientific cell. `grid_cell_id` remains the
    # human-readable identity for compatibility; this field is the
    # STRONG scientific identity — see `scientific_domain.scientific_cell_id`.
    scientific_cell_id: str | None = None

    def as_dict(self) -> dict:
        return {
            "grid_cell_id": self.grid_cell_id, "row": self.row, "col": self.col, "component_index": self.component_index,
            "centroid_lat": self.centroid_lat, "centroid_lon": self.centroid_lon,
            "cell_size_km": self.cell_size_km, "area_km2": self.area_km2,
            "domain_overlap_area_km2": self.domain_overlap_area_km2, "domain_overlap_fraction": self.domain_overlap_fraction,
            "intersects_true_domain": self.intersects_true_domain,
            "source_crs": self.source_crs, "analysis_crs": self.analysis_crs, "bounds_utm": list(self.bounds_utm),
            "scientific_cell_id": self.scientific_cell_id,
        }

    def polygon(self) -> shapely.geometry.base.BaseGeometry:
        return shapely.geometry.box(*self.bounds_utm)


@dataclass(frozen=True)
class ProjectionSafetyAssessment:
    status: str  # PROJECTION_CONTEXT_SAFE | PROJECTION_CONTEXT_UNSAFE
    source_geographic_span_deg: float
    max_pairwise_geodesic_distance_km: float
    utm_zones_touched: tuple
    analysis_crs: str
    buffer_radius_km: float
    max_relative_distance_distortion: float
    distortion_tolerance: float
    tolerance_version: str

    def as_dict(self) -> dict:
        return {
            "status": self.status, "source_geographic_span_deg": self.source_geographic_span_deg,
            "max_pairwise_geodesic_distance_km": self.max_pairwise_geodesic_distance_km,
            "utm_zones_touched": list(self.utm_zones_touched), "analysis_crs": self.analysis_crs,
            "buffer_radius_km": self.buffer_radius_km, "max_relative_distance_distortion": self.max_relative_distance_distortion,
            "distortion_tolerance": self.distortion_tolerance, "tolerance_version": self.tolerance_version,
        }


def assess_projection_safety(
    sources: list[EligibleSourcePoint], *, crs_choice: CrsChoice, domain_distance_km: float,
) -> ProjectionSafetyAssessment:
    """Real diagnostics, not assumed safety (Part 17). A single-source
    (or otherwise trivial) domain is always `PROJECTION_CONTEXT_SAFE`
    (no pairwise distortion possible). For 2+ sources, the actual
    relative distortion between real WGS84 geodesic distance and the
    projected planar distance is measured for every source pair —
    never estimated or assumed from zone count alone (zone count is
    reported as an additional, explicit diagnostic, not the sole gate)."""
    to_utm = build_transformer(crs_choice.source_crs, crs_choice.analysis_crs)
    zones = sorted({utm_zone_for(s.longitude) for s in sources})

    max_geodesic_km = 0.0
    max_rel_distortion = 0.0
    max_span_deg = 0.0
    ordered = sorted(sources, key=lambda s: s.source_id)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            geo_km = distance_km(a.latitude, a.longitude, b.latitude, b.longitude)
            max_geodesic_km = max(max_geodesic_km, geo_km)
            ax, ay = to_utm.transform(a.longitude, a.latitude)
            bx, by = to_utm.transform(b.longitude, b.latitude)
            planar_km = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 / 1000.0
            rel = (abs(planar_km - geo_km) / geo_km) if geo_km > 0 else 0.0
            max_rel_distortion = max(max_rel_distortion, rel)
            max_span_deg = max(max_span_deg, abs(a.latitude - b.latitude), abs(a.longitude - b.longitude))

    status = PROJECTION_CONTEXT_SAFE if max_rel_distortion <= PROJECTION_DISTORTION_REL_TOL else PROJECTION_CONTEXT_UNSAFE
    return ProjectionSafetyAssessment(
        status=status, source_geographic_span_deg=max_span_deg, max_pairwise_geodesic_distance_km=max_geodesic_km,
        utm_zones_touched=tuple(zones), analysis_crs=crs_choice.analysis_crs, buffer_radius_km=domain_distance_km,
        max_relative_distance_distortion=max_rel_distortion, distortion_tolerance=PROJECTION_DISTORTION_REL_TOL,
        tolerance_version=PROJECTION_TOLERANCE_VERSION,
    )


def _sorted_components(union: shapely.geometry.base.BaseGeometry) -> list:
    comps = list(union.geoms) if union.geom_type == "MultiPolygon" else [union]
    # Part TRUEGRID-07: deterministic component ordering regardless of
    # shapely's own internal MultiPolygon iteration order.
    return sorted(comps, key=lambda g: (round(g.bounds[0], _GEOM_DIGEST_DECIMALS), round(g.bounds[1], _GEOM_DIGEST_DECIMALS)))


def union_geometry_digest(union: shapely.geometry.base.BaseGeometry) -> str:
    """Deterministic — order-independent over MultiPolygon components
    (Part 11/TRUEGRID-07/TRUEGRID-06): every component's exterior ring
    is canonicalized (rounded coordinates) and the component list is
    sorted before hashing, so reordering components (or querying the
    same real geometry twice) never changes this digest."""
    payload = []
    for comp in _sorted_components(union):
        coords = [[round(x, _GEOM_DIGEST_DECIMALS), round(y, _GEOM_DIGEST_DECIMALS)] for x, y in comp.exterior.coords]
        payload.append(coords)
    canonical = json.dumps(payload, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DomainGeometry:
    center_lat: float
    center_lon: float
    crs_choice: CrsChoice
    buffer_method: str  # PROJECTED_METRIC_BUFFER_UNION — Part 16
    bounds_utm: tuple  # overall bounding extent of the TRUE union (diagnostic/legacy-comparison only — never used for cell inclusion)
    union_area_km2: float  # the TRUE union area
    union_geometry_digest: str  # Part 11 — deterministic digest of the ACTUAL union geometry
    component_bounds_utm: tuple  # per-component (minx,miny,maxx,maxy), deterministically ordered
    n_components: int
    domain_geometry_digest: str  # identity over source ids/coords/domain_distance_km/domain_mode
    source_ids: tuple
    domain_distance_km: float
    projection_safety: ProjectionSafetyAssessment
    union_geometry: object = field(repr=False, compare=False, default=None)  # in-process shapely geometry — never serialized

    def as_dict(self) -> dict:
        return {
            "center_lat": self.center_lat, "center_lon": self.center_lon, "crs_choice": self.crs_choice.as_dict(),
            "buffer_method": self.buffer_method, "bounds_utm": list(self.bounds_utm), "union_area_km2": self.union_area_km2,
            "union_geometry_digest": self.union_geometry_digest, "component_bounds_utm": [list(b) for b in self.component_bounds_utm],
            "n_components": self.n_components, "domain_geometry_digest": self.domain_geometry_digest,
            "source_ids": list(self.source_ids), "domain_distance_km": self.domain_distance_km,
            "projection_safety": self.projection_safety.as_dict(),
        }

    def bounding_box_area_km2(self) -> float:
        """Legacy comparison figure only (Checkpoint 7A's old
        bounding-box-tiling area) — never used for grid construction."""
        minx, miny, maxx, maxy = self.bounds_utm
        return (maxx - minx) * (maxy - miny) / 1e6


def build_source_buffer_union_domain(
    sources: list[EligibleSourcePoint], *, domain_distance_km: float
) -> DomainGeometry:
    """T0-safe by construction — takes ONLY eligible-source points and a
    predeclared `domain_distance_km`; there is no parameter here that
    could carry a future target coordinate (DOMAIN-01). Buffers each
    source by `domain_distance_km` in a single AOI-wide local UTM
    projection (`PROJECTED_METRIC_BUFFER_UNION`, Part 16 — never called
    geodesic) and unions the buffers (Part 9's preferred domain
    definition — never just the nearest/trigger source). Preserves the
    ACTUAL union geometry (Part 11) — a `MultiPolygon` union's
    components are kept individually, never silently reduced to one
    bounding rectangle. Runs the real projection-safety assessment
    (Part 17) for this domain."""
    if not sources:
        raise ValueError("build_source_buffer_union_domain requires at least one eligible source")
    center_lat = sum(s.latitude for s in sources) / len(sources)
    center_lon = sum(s.longitude for s in sources) / len(sources)
    crs_choice = analysis_crs_for(center_lat, center_lon)
    to_utm = build_transformer(crs_choice.source_crs, crs_choice.analysis_crs)

    ordered_sources = sorted(sources, key=lambda s: s.source_id)
    buffers = []
    for s in ordered_sources:
        x, y = to_utm.transform(s.longitude, s.latitude)
        buffers.append(shapely.geometry.Point(x, y).buffer(domain_distance_km * 1000.0))
    union = shapely.ops.unary_union(buffers)
    minx, miny, maxx, maxy = union.bounds
    union_area_km2 = union.area / 1e6

    components_sorted = _sorted_components(union)
    component_bounds = tuple(
        tuple(round(v, _GEOM_DIGEST_DECIMALS) for v in comp.bounds) for comp in components_sorted
    )
    geom_digest = union_geometry_digest(union)

    payload = {
        "source_ids": [s.source_id for s in ordered_sources],
        "source_coords": [[round(s.latitude, 6), round(s.longitude, 6)] for s in ordered_sources],
        "domain_distance_km": domain_distance_km,
        "domain_mode": DOMAIN_MODE_SOURCE_BUFFER_UNION,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]

    projection_safety = assess_projection_safety(ordered_sources, crs_choice=crs_choice, domain_distance_km=domain_distance_km)

    return DomainGeometry(
        center_lat=center_lat, center_lon=center_lon, crs_choice=crs_choice, buffer_method=BUFFER_METHOD_PROJECTED_METRIC_UNION,
        bounds_utm=(minx, miny, maxx, maxy), union_area_km2=union_area_km2, union_geometry_digest=geom_digest,
        component_bounds_utm=component_bounds, n_components=len(components_sorted), domain_geometry_digest=digest,
        source_ids=tuple(s.source_id for s in ordered_sources), domain_distance_km=domain_distance_km,
        projection_safety=projection_safety, union_geometry=union,
    )


def build_scientific_grid(
    domain: DomainGeometry, *, config: ScientificGridConfig, id_prefix: str = "SCELL"
) -> list[ScientificGridCell]:
    """Tiles EACH true-domain component's own local bounding box with
    real square cells of edge `config.cell_size_km`, then keeps ONLY
    cells with positive intersection area against that component (Parts
    10.3-10.5, 12) — a cell in the empty gap between disconnected
    components, or in a circular buffer's own bounding-square corners,
    is never returned. Refuses (`ValueError`) to tile a domain whose
    `projection_safety.status != PROJECTION_CONTEXT_SAFE` (Part 18 —
    never silently continues with a distorted projection)."""
    if domain.projection_safety.status != PROJECTION_CONTEXT_SAFE:
        raise ValueError(
            f"cannot build a scientific grid for a {domain.projection_safety.status} domain "
            f"(max_relative_distance_distortion={domain.projection_safety.max_relative_distance_distortion:.4f} "
            f"> tolerance={domain.projection_safety.distortion_tolerance}) — Part 18: never silently continue"
        )
    if domain.union_geometry is None:
        raise ValueError("DomainGeometry has no in-process union_geometry to tile — build it via build_source_buffer_union_domain")

    components_sorted = _sorted_components(domain.union_geometry)
    to_wgs84 = build_transformer(domain.crs_choice.analysis_crs, domain.crs_choice.source_crs)
    cell_m = config.cell_size_km * 1000.0

    cells: list[ScientificGridCell] = []
    for comp_idx, comp in enumerate(components_sorted):
        minx, miny, maxx, maxy = comp.bounds
        n_cols = max(1, ceil((maxx - minx) / cell_m))
        n_rows = max(1, ceil((maxy - miny) / cell_m))
        for row in range(n_rows):
            for col in range(n_cols):
                cell_minx = minx + col * cell_m
                cell_miny = miny + row * cell_m
                cell_maxx = cell_minx + cell_m
                cell_maxy = cell_miny + cell_m
                square = shapely.geometry.box(cell_minx, cell_miny, cell_maxx, cell_maxy)
                overlap_area_km2 = square.intersection(comp).area / 1e6
                if overlap_area_km2 <= 0.0:
                    continue  # Part 10.5/12 — never a zero-overlap gap cell
                full_area_km2 = square.area / 1e6
                centroid = square.centroid
                lon, lat = to_wgs84.transform(centroid.x, centroid.y)
                cells.append(ScientificGridCell(
                    grid_cell_id=f"{id_prefix}:{comp_idx:02d}:{row:04d}:{col:04d}", row=row, col=col, component_index=comp_idx,
                    centroid_lat=lat, centroid_lon=lon, cell_size_km=config.cell_size_km, area_km2=full_area_km2,
                    domain_overlap_area_km2=overlap_area_km2, domain_overlap_fraction=overlap_area_km2 / full_area_km2,
                    intersects_true_domain=True, source_crs=domain.crs_choice.source_crs, analysis_crs=domain.crs_choice.analysis_crs,
                    bounds_utm=(cell_minx, cell_miny, cell_maxx, cell_maxy),
                ))
    return cells


@dataclass(frozen=True)
class ScientificGridSnapshot:
    """Checkpoint 7A Part 14 / 7A.5 Part 11: full grid-construction
    identity for one forecast origin (or local context). `generated_at`
    never participates in `grid_snapshot_id`."""

    grid_snapshot_id: str
    forecast_origin_id: str
    t0: str
    active_source_ids: tuple
    domain_geometry_digest: str
    union_geometry_digest: str  # Part TRUEGRID-06 — the ACTUAL true-domain geometry participates in identity
    domain_mode: str
    domain_distance_km: float
    cell_size_km: float
    crs_strategy: str
    cell_ids: tuple  # sorted — GRID7A-10
    cell_count: int
    total_area_km2: float
    total_domain_overlap_area_km2: float
    scientific_grid_config_hash: str
    generated_at: str

    def as_dict(self) -> dict:
        return {
            "grid_snapshot_id": self.grid_snapshot_id, "forecast_origin_id": self.forecast_origin_id, "t0": self.t0,
            "active_source_ids": list(self.active_source_ids), "domain_geometry_digest": self.domain_geometry_digest,
            "union_geometry_digest": self.union_geometry_digest,
            "domain_mode": self.domain_mode, "domain_distance_km": self.domain_distance_km,
            "cell_size_km": self.cell_size_km, "crs_strategy": self.crs_strategy,
            "cell_ids": list(self.cell_ids), "cell_count": self.cell_count, "total_area_km2": self.total_area_km2,
            "total_domain_overlap_area_km2": self.total_domain_overlap_area_km2,
            "scientific_grid_config_hash": self.scientific_grid_config_hash, "generated_at": self.generated_at,
        }


def build_scientific_grid_snapshot(
    *, forecast_origin_id: str, t0: str, active_source_ids: list, domain: DomainGeometry, config: ScientificGridConfig,
    cells: list[ScientificGridCell], generated_at: str = "",
) -> ScientificGridSnapshot:
    cell_ids = tuple(sorted(c.grid_cell_id for c in cells))
    total_area_km2 = round(sum(c.area_km2 for c in cells), 6)
    total_overlap_km2 = round(sum(c.domain_overlap_area_km2 for c in cells), 6)
    payload = {
        "forecast_origin_id": forecast_origin_id, "t0": t0, "active_source_ids": sorted(active_source_ids),
        "domain_geometry_digest": domain.domain_geometry_digest, "union_geometry_digest": domain.union_geometry_digest,
        "domain_mode": config.domain_mode, "domain_distance_km": config.domain_distance_km, "cell_size_km": config.cell_size_km,
        "crs_strategy": config.crs_strategy, "cell_ids": list(cell_ids), "cell_count": len(cell_ids),
        "total_area_km2": total_area_km2, "total_domain_overlap_area_km2": total_overlap_km2,
        "scientific_grid_config_hash": config.scientific_grid_config_hash(),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
    return ScientificGridSnapshot(
        grid_snapshot_id=f"GRIDSNAP:{digest}", forecast_origin_id=forecast_origin_id, t0=t0,
        active_source_ids=tuple(sorted(active_source_ids)), domain_geometry_digest=domain.domain_geometry_digest,
        union_geometry_digest=domain.union_geometry_digest, domain_mode=config.domain_mode, domain_distance_km=config.domain_distance_km,
        cell_size_km=config.cell_size_km, crs_strategy=config.crs_strategy, cell_ids=cell_ids, cell_count=len(cell_ids),
        total_area_km2=total_area_km2, total_domain_overlap_area_km2=total_overlap_km2,
        scientific_grid_config_hash=config.scientific_grid_config_hash(), generated_at=generated_at,
    )
