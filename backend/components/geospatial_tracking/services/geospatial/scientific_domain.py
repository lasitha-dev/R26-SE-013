"""Checkpoint 7A.6.1: geodesic source componentization + per-component
projection-safe scientific grid geometry.

**Root cause corrected (Parts 1-2)**: 7A.6's `services.model_development.host_reference_rebuild`
projected ALL of one forecast origin's eligible sources into a SINGLE
AOI-local UTM CRS chosen from their combined mean coordinate — safe only
for a sufficiently compact source set. The real 7A.6 audit found 9 real
origins whose eligible sources were dispersed too widely for a single
CRS to be safe. That single-global-CRS, all-source-per-origin domain
construction pattern is now labeled
`SUPERSEDED_SINGLE_ANALYSIS_CRS_ALL_SOURCE_DOMAIN_7A6` — the underlying
`services.geospatial.scientific_grid` primitives (`DomainGeometry`,
`build_source_buffer_union_domain`, `build_scientific_grid`,
`assess_projection_safety`) are NOT deleted or modified; they are reused
here UNCHANGED, but applied to one COMPONENT's own sources at a time,
never to an entire origin's full eligible-source set at once.

**Geodesic componentization, never ST-DBSCAN (Part 7)**: sources are
grouped into `SCIENTIFIC_DOMAIN_COMPONENTS` via a PURELY GEOMETRIC
connectivity graph over real WGS84 geodesic distances — an edge exists
between two sources iff their real geodesic distance is
`<= 2 * PRIMARY_LOCAL_EVALUATION_DISTANCE_KM` (two 25km buffers can only
touch/overlap within that separation). This is NEVER an ST-DBSCAN
cluster, transmission chain, infection chain, or causal outbreak group —
purely computational geometry, with zero `STDBSCANConfig` involvement
anywhere in this module.

**Each component owns its own local CRS (Parts 9-11)**: chosen only from
that component's OWN source coordinates via the existing
`services.geospatial.crs.analysis_crs_for` — never from the mean of an
entire origin's dispersed source set. The parent
`ScientificEvaluationDomain` never claims one global `analysis_crs`/
`bounds_utm`/projected geometry of its own; it only aggregates its
components.

**Buffer-radial distortion audit (Part 12)**: source-source distance
distortion (`scientific_grid.assess_projection_safety`) alone does not
prove a component's own 25km BUFFER is well-represented in its
projection. For every source in a component, 8 real geodesic test points
exactly 25km away (at 0/45/90/135/180/225/270/315 degrees) are compared
against their own projected planar distance from that source; the
largest relative error is checked against the SAME predeclared 1%
software tolerance
(`services.geospatial.scientific_grid.PROJECTION_DISTORTION_REL_TOL`) —
never a separately tuned number.

**If a component is still unsafe, it is never silently skipped or
dropped (Part 13)** — `ScientificDomainComponent.is_safe=False` components
carry no cells at all; callers building a real audit must report
`PROJECTION_COMPONENT_UNSAFE_AFTER_GEODESIC_COMPONENTIZATION` explicitly,
never quietly omit the origin.

**Terminology (Part 14)**: a component's own projected 25km buffer union
is a `PROJECTION_SAFE_PROJECTED_APPROXIMATION_OF_25KM_GEODESIC_ENVELOPE`
— NEVER an "exact geodesic buffer." Primary scientific SCOPE truth
(`services.model_development.local_evaluation_scope.classify_target_primary_scope_geodesic`)
is computed directly from real WGS84 geodesic distance and never depends
on any geometry built here — this module's grid geometry is used ONLY
for factor sampling and target-to-cell assignment (Part 6, 17-18).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import pyproj
import shapely.geometry

import dataclasses

from .crs import CrsChoice, analysis_crs_for, build_transformer
from .distance import distance_km
from .scientific_grid import (
    PROJECTION_CONTEXT_SAFE,
    PROJECTION_DISTORTION_REL_TOL,
    PROJECTION_TOLERANCE_VERSION,
    DomainGeometry,
    ProjectionSafetyAssessment,
    ScientificGridCell,
    ScientificGridConfig,
    assess_projection_safety,
    build_scientific_grid,
    build_source_buffer_union_domain,
)
from .source_geometry import EligibleSourcePoint

SCIENTIFIC_DOMAIN_PROTOCOL_VERSION = "7A.6.2"
SCIENTIFIC_CELL_IDENTITY_VERSION = "7A.6.2"  # scientific_cell_id()'s own payload/version — explicit per Part 13
BUFFER_METHOD_PROJECTED_APPROXIMATION = "PROJECTION_SAFE_PROJECTED_APPROXIMATION_OF_25KM_GEODESIC_ENVELOPE"  # Part 14 — never "exact geodesic"
TRUE_DOMAIN_POSITIVE_OVERLAP_RULE_VERSION = "7A.5.1"  # scientific_grid.build_scientific_grid's own masking rule — reused unchanged, cited here for protocol-hash completeness

# Part 4: a named SOFTWARE numerical boundary tolerance — never biological
# uncertainty, only floating-point equality handling at exactly the
# component-edge/envelope-radius distance.
GEODESIC_BOUNDARY_TOLERANCE_KM = 1e-6
GEODESIC_BOUNDARY_TOLERANCE_VERSION = "7A.6.1"

# Part 7: two 25km buffers can only touch/overlap within 2x the envelope.
COMPONENT_EDGE_DISTANCE_KM_MULTIPLE = 2.0

RADIAL_DISTORTION_BEARINGS_DEG: tuple = (0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0)
_GEOD = pyproj.Geod(ellps="WGS84")

PROJECTION_COMPONENT_UNSAFE_AFTER_GEODESIC_COMPONENTIZATION = "PROJECTION_COMPONENT_UNSAFE_AFTER_GEODESIC_COMPONENTIZATION"

GRID_CELL_ASSIGNED = "GRID_CELL_ASSIGNED"
GRID_REPRESENTATION_BOUNDARY_MISMATCH = "GRID_REPRESENTATION_BOUNDARY_MISMATCH"  # Part 18


def component_edge_distance_km(primary_local_evaluation_distance_km: float) -> float:
    return COMPONENT_EDGE_DISTANCE_KM_MULTIPLE * primary_local_evaluation_distance_km


def build_geodesic_source_components(sources: list[EligibleSourcePoint], *, edge_distance_km: float) -> list[list[str]]:
    """Pure connectivity grouping over real WGS84 geodesic distance —
    deterministic regardless of input order (`COMP-04`): iterates and
    unions over `sorted(source_id)` throughout, mirroring
    `services.stdbscan.cluster`'s own determinism discipline (without
    reusing any of its code or config)."""
    ids = sorted(s.source_id for s in sources)
    by_id = {s.source_id: s for s in sources}
    parent: dict = {sid: sid for sid in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            lo, hi = (ra, rb) if ra < rb else (rb, ra)
            parent[hi] = lo

    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d = distance_km(by_id[a].latitude, by_id[a].longitude, by_id[b].latitude, by_id[b].longitude)
            if d <= edge_distance_km + GEODESIC_BOUNDARY_TOLERANCE_KM:
                union(a, b)

    groups: dict = {}
    for sid in ids:
        groups.setdefault(find(sid), []).append(sid)
    return sorted((sorted(members) for members in groups.values()), key=lambda g: g[0])


def scientific_domain_protocol_hash(grid_config: ScientificGridConfig) -> str:
    """Checkpoint 7A.6.2 Part 3A: the PROTOCOL-level identity — the
    scientific/engineering RULES this module applies, never a concrete
    prediction-time instance. Contains no `forecast_origin_id`, `t0`,
    source ID, or `generated_at` (verified structurally,
    `DOMAINID-01/02`). Two calls with the same `grid_config` (same
    `domain_distance_km`/`cell_size_km`/`crs_strategy`/
    `projection_tolerance_version`/statuses) always produce the same
    hash; changing any of them changes it (`DOMAINID-06/07/08/09`)."""
    payload = {
        "scientific_domain_protocol_version": SCIENTIFIC_DOMAIN_PROTOCOL_VERSION,
        "scientific_grid_config": grid_config.config_dict(),
        "scientific_grid_config_hash": grid_config.scientific_grid_config_hash(),
        "geodesic_boundary_tolerance_km": GEODESIC_BOUNDARY_TOLERANCE_KM,
        "geodesic_boundary_tolerance_version": GEODESIC_BOUNDARY_TOLERANCE_VERSION,
        "component_edge_distance_km_multiple": COMPONENT_EDGE_DISTANCE_KM_MULTIPLE,
        "component_builder_version": SCIENTIFIC_DOMAIN_PROTOCOL_VERSION,
        "component_local_crs_strategy": grid_config.crs_strategy,
        "projection_distortion_tolerance": PROJECTION_DISTORTION_REL_TOL,
        "projection_tolerance_version": PROJECTION_TOLERANCE_VERSION,
        "radial_distortion_bearings_deg": list(RADIAL_DISTORTION_BEARINGS_DEG),
        "radial_distortion_audit_version": SCIENTIFIC_DOMAIN_PROTOCOL_VERSION,
        "buffer_method": BUFFER_METHOD_PROJECTED_APPROXIMATION,
        "true_domain_positive_overlap_rule_version": TRUE_DOMAIN_POSITIVE_OVERLAP_RULE_VERSION,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def scientific_cell_id(
    *, protocol_hash: str, component_id: str, component_crs_choice: CrsChoice, component_geometry_digest: str | None,
    grid_config_hash: str, domain_distance_km: float, cell: ScientificGridCell,
) -> str:
    """Checkpoint 7A.6.2 Part 4: a deterministic, configuration- and
    projection-sensitive identity for one scientific cell — never
    dependent only on the 8-character `component_id` prefix baked into
    `grid_cell_id`. Two numerically identical cells built under
    identical inputs (including source ordering) always share this
    identity; a changed cell size, domain distance, component CRS/
    projection strategy, or component geometry always changes it."""
    payload = {
        "scientific_domain_protocol_hash": protocol_hash,
        "component_id": component_id,
        "component_analysis_crs": component_crs_choice.analysis_crs,
        "component_geometry_digest": component_geometry_digest,
        "scientific_grid_config_hash": grid_config_hash,
        "domain_distance_km": domain_distance_km,
        "cell_size_km": cell.cell_size_km,
        "bounds_utm": [round(v, 3) for v in cell.bounds_utm],  # canonical projected bounds, mm-precision software tolerance
        "domain_overlap_protocol_version": TRUE_DOMAIN_POSITIVE_OVERLAP_RULE_VERSION,
        "scientific_cell_identity_version": SCIENTIFIC_CELL_IDENTITY_VERSION,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"SCICELL:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"


def _component_id(*, source_ids: list, coords_by_id: dict) -> str:
    payload = {
        "source_ids": sorted(source_ids),
        "coords": {sid: [round(coords_by_id[sid][0], 6), round(coords_by_id[sid][1], 6)] for sid in sorted(source_ids)},
        "envelope_protocol_version": SCIENTIFIC_DOMAIN_PROTOCOL_VERSION,
        "component_builder_version": SCIENTIFIC_DOMAIN_PROTOCOL_VERSION,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"SCICOMP:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"


def max_buffer_radial_relative_error(
    sources: list[EligibleSourcePoint], *, crs_choice: CrsChoice, domain_distance_km: float,
) -> float:
    """Part 12: for every source, 8 real geodesic test points exactly
    `domain_distance_km` away are compared against their own projected
    planar distance from that source — the largest relative error across
    every source/bearing pair. Bearings and tolerance are fixed BEFORE
    any real audit runs — never tuned using outcomes."""
    to_utm = build_transformer(crs_choice.source_crs, crs_choice.analysis_crs)
    max_rel = 0.0
    for s in sorted(sources, key=lambda s: s.source_id):
        sx, sy = to_utm.transform(s.longitude, s.latitude)
        for bearing in RADIAL_DISTORTION_BEARINGS_DEG:
            lon2, lat2, _ = _GEOD.fwd(s.longitude, s.latitude, bearing, domain_distance_km * 1000.0)
            tx, ty = to_utm.transform(lon2, lat2)
            planar_km = ((tx - sx) ** 2 + (ty - sy) ** 2) ** 0.5 / 1000.0
            rel = abs(planar_km - domain_distance_km) / domain_distance_km
            max_rel = max(max_rel, rel)
    return max_rel


@dataclass(frozen=True)
class ScientificDomainComponent:
    component_id: str
    source_ids: tuple
    center_lat: float
    center_lon: float
    crs_choice: CrsChoice
    projection_safety: ProjectionSafetyAssessment
    max_buffer_radial_relative_error: float
    radial_distortion_tolerance: float
    is_safe: bool
    buffer_method: str
    domain: DomainGeometry | None
    cells: tuple

    def as_dict(self) -> dict:
        return {
            "component_id": self.component_id, "source_ids": list(self.source_ids),
            "center_lat": self.center_lat, "center_lon": self.center_lon, "crs_choice": self.crs_choice.as_dict(),
            "projection_safety": self.projection_safety.as_dict(),
            "max_buffer_radial_relative_error": self.max_buffer_radial_relative_error,
            "radial_distortion_tolerance": self.radial_distortion_tolerance, "is_safe": self.is_safe,
            "buffer_method": self.buffer_method, "n_cells": len(self.cells),
            "domain_geometry_digest": self.domain.union_geometry_digest if self.domain else None,
        }


@dataclass(frozen=True)
class ScientificEvaluationDomain:
    forecast_origin_id: str
    t0: str
    all_eligible_source_ids: tuple
    components: tuple
    scientific_domain_protocol_hash: str  # Part 3A: the RULES this domain was built under — no origin/t0/source/generated_at
    scientific_evaluation_domain_id: str  # Part 3B: THIS concrete instance's own identity

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id, "t0": self.t0,
            "all_eligible_source_ids": list(self.all_eligible_source_ids),
            "components": [c.as_dict() for c in self.components],
            "scientific_domain_protocol_hash": self.scientific_domain_protocol_hash,
            "scientific_evaluation_domain_id": self.scientific_evaluation_domain_id,
        }

    def all_cells(self) -> list[ScientificGridCell]:
        cells: list[ScientificGridCell] = []
        for c in self.components:
            cells.extend(c.cells)
        return cells

    def n_unsafe_components(self) -> int:
        return sum(1 for c in self.components if not c.is_safe)


def build_scientific_evaluation_domain(
    *, forecast_origin_id: str, t0: str, sources: list[EligibleSourcePoint], grid_config: ScientificGridConfig,
    primary_local_evaluation_distance_km: float,
) -> ScientificEvaluationDomain:
    """T0-safe by construction — no parameter here can carry a future
    target coordinate. Never assumes one parent CRS (Part 9): groups
    `sources` into geodesically-connected components first
    (`build_geodesic_source_components`), then builds EACH component's
    own local domain/grid independently via the UNCHANGED
    `scientific_grid.build_source_buffer_union_domain`/
    `build_scientific_grid`, scoped to that component's own sources
    only.

    Checkpoint 7A.6.2 Part 3: `grid_config.domain_distance_km` and
    `primary_local_evaluation_distance_km` are two parameters that MUST
    describe the same real distance — this is a hard, explicit contract
    invariant, never a silent choice of one over the other. A future
    caller passing mismatched values (e.g. a config built for the 25km
    primary envelope alongside a 50km sensitivity distance) would
    otherwise produce a `scientific_domain_protocol_hash` describing one
    distance while the actual component/grid geometry was built at
    another."""
    if abs(primary_local_evaluation_distance_km - grid_config.domain_distance_km) > GEODESIC_BOUNDARY_TOLERANCE_KM:
        raise ValueError(
            f"primary_local_evaluation_distance_km ({primary_local_evaluation_distance_km!r}) and "
            f"grid_config.domain_distance_km ({grid_config.domain_distance_km!r}) must describe the SAME distance "
            f"(within {GEODESIC_BOUNDARY_TOLERANCE_KM}km software tolerance) — they disagree, which would let "
            f"scientific_domain_protocol_hash describe a different distance than the actual component/grid geometry"
        )

    protocol_hash = scientific_domain_protocol_hash(grid_config)
    grid_config_hash = grid_config.scientific_grid_config_hash()

    edge_km = component_edge_distance_km(primary_local_evaluation_distance_km)
    by_id = {s.source_id: s for s in sources}
    groups = build_geodesic_source_components(sources, edge_distance_km=edge_km) if sources else []

    components: list[ScientificDomainComponent] = []
    for group_ids in groups:
        group_sources = [by_id[sid] for sid in group_ids]
        coords_by_id = {sid: (by_id[sid].latitude, by_id[sid].longitude) for sid in group_ids}
        component_id = _component_id(source_ids=group_ids, coords_by_id=coords_by_id)
        center_lat = sum(s.latitude for s in group_sources) / len(group_sources)
        center_lon = sum(s.longitude for s in group_sources) / len(group_sources)

        domain = build_source_buffer_union_domain(group_sources, domain_distance_km=primary_local_evaluation_distance_km)
        radial_error = max_buffer_radial_relative_error(
            group_sources, crs_choice=domain.crs_choice, domain_distance_km=primary_local_evaluation_distance_km,
        )
        is_safe = (domain.projection_safety.status == PROJECTION_CONTEXT_SAFE) and (radial_error <= PROJECTION_DISTORTION_REL_TOL)

        cells: tuple = ()
        if is_safe:
            id_prefix = f"{forecast_origin_id.replace(':', '_').replace(' ', '_')}_C{component_id[8:16]}"
            raw_cells = build_scientific_grid(domain, config=grid_config, id_prefix=id_prefix)
            cells = tuple(
                dataclasses.replace(cell, scientific_cell_id=scientific_cell_id(
                    protocol_hash=protocol_hash, component_id=component_id, component_crs_choice=domain.crs_choice,
                    component_geometry_digest=domain.union_geometry_digest, grid_config_hash=grid_config_hash,
                    domain_distance_km=primary_local_evaluation_distance_km, cell=cell,
                ))
                for cell in raw_cells
            )

        components.append(ScientificDomainComponent(
            component_id=component_id, source_ids=tuple(group_ids), center_lat=center_lat, center_lon=center_lon,
            crs_choice=domain.crs_choice, projection_safety=domain.projection_safety,
            max_buffer_radial_relative_error=radial_error, radial_distortion_tolerance=PROJECTION_DISTORTION_REL_TOL,
            is_safe=is_safe, buffer_method=BUFFER_METHOD_PROJECTED_APPROXIMATION, domain=domain, cells=cells,
        ))

    instance_payload = {
        "scientific_domain_protocol_hash": protocol_hash, "forecast_origin_id": forecast_origin_id, "t0": t0,
        "all_eligible_source_ids": sorted(by_id.keys()),
        "components": sorted(
            (
                {
                    "component_id": c.component_id, "analysis_crs": c.crs_choice.analysis_crs,
                    "geometry_digest": c.domain.union_geometry_digest if c.domain else None,
                    "cell_ids": sorted(cell.scientific_cell_id for cell in c.cells),
                }
                for c in components
            ),
            key=lambda d: d["component_id"],
        ),
        "scientific_grid_config_hash": grid_config_hash,
    }
    scientific_evaluation_domain_id = hashlib.sha256(
        json.dumps(instance_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return ScientificEvaluationDomain(
        forecast_origin_id=forecast_origin_id, t0=t0, all_eligible_source_ids=tuple(sorted(by_id.keys())),
        components=tuple(components), scientific_domain_protocol_hash=protocol_hash,
        scientific_evaluation_domain_id=scientific_evaluation_domain_id,
    )


def assign_target_to_scientific_evaluation_domain(*, target, evaluation_domain: ScientificEvaluationDomain) -> tuple:
    """Part 17-18: assignment is a SEPARATE step from scope truth
    (`local_evaluation_scope.classify_target_primary_scope_geodesic`) —
    never used to override it. Checks every SAFE component's real cells
    via deterministic polygon containment (lexicographically-smallest
    `grid_cell_id` tie-break, matching `target_assignment.py`'s existing
    rule) — an unsafe/uncelled component simply contributes no matches,
    never raises. Returns `(target_grid_cell_id_or_None, grid_representation_status)`."""
    matches: list[str] = []
    for component in evaluation_domain.components:
        if not component.is_safe or not component.cells:
            continue
        to_utm = build_transformer(component.crs_choice.source_crs, component.crs_choice.analysis_crs)
        x, y = to_utm.transform(target.longitude, target.latitude)
        point = shapely.geometry.Point(x, y)
        matches.extend(cell.grid_cell_id for cell in component.cells if cell.polygon().intersects(point))
    if matches:
        return sorted(matches)[0], GRID_CELL_ASSIGNED
    return None, GRID_REPRESENTATION_BOUNDARY_MISMATCH
