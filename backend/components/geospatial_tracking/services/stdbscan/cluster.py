"""Checkpoint 6B Parts 5, 12-15: deterministic ST-DBSCAN-style clustering.

**PERMANENT SCIENTIFIC CLAIM (Part 5)**: this module performs
"spatiotemporal density-based outbreak context clustering" /
"ST-DBSCAN-style outbreak context clustering" — this is NEVER evidence
that one outbreak caused another, that cluster members form a
transmission chain, that every member is epidemiologically linked, that
noise is unimportant, or that a cluster's spatial extent is an infection
boundary. No field anywhere in this module (or `snapshot.py`) is named
`transmission_chain`, `causal_parent`, or `infected_by_cluster` — a
grep-level guarantee, not just a docstring promise (ST-17).

**Determinism (Part 12, ST-06/ST-16)**: every step sorts by `source_id`
(never input order) before doing anything order-sensitive. Reordering
the input `usable_points` list never changes any assignment or cluster
ID.

**Noise is retained, never deleted (Part 14, ST-07/ST-08/ST-19)**: a
source that is neither CORE nor BORDER gets `cluster_id=None`,
`is_noise=True`, `cluster_role="NOISE"` — it is still a fully valid
member of the eligible active-source set the caller started with. This
module never removes an item from its input; it only classifies it.

**Deterministic border tie-break (Part 12)**: when a border point
touches core members from more than one cluster, it is assigned to the
cluster containing the core member at the smallest geodesic distance;
ties are broken by the smallest preliminary cluster fingerprint (a
stable hash of that cluster's own sorted core membership) — never
random, never dependent on iteration/input order.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field

from ..geospatial.distance import distance_km
from .core_support import CoreSupportAssignment
from .neighborhood import build_neighbor_graph

CORE = "CORE"
BORDER = "BORDER"
NOISE = "NOISE"
TEMPORAL_UNUSABLE = "TEMPORAL_UNUSABLE"


@dataclass
class ClusterAssignment:
    source_id: str
    cluster_id: str | None
    is_noise: bool
    cluster_role: str  # CORE | BORDER | NOISE | TEMPORAL_UNUSABLE

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "cluster_id": self.cluster_id,
            "is_noise": self.is_noise,
            "cluster_role": self.cluster_role,
        }


@dataclass
class ClusterSummary:
    cluster_id: str
    member_source_ids: list[str]
    core_source_ids: list[str]
    border_source_ids: list[str]
    member_count: int
    core_support_count: int
    cluster_start_date: str
    cluster_end_date: str
    centroid_lat: float
    centroid_lon: float
    gps_quality_counts: dict[str, int] = field(default_factory=dict)
    config_hash: str = ""

    def as_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "member_source_ids": self.member_source_ids,
            "core_source_ids": self.core_source_ids,
            "border_source_ids": self.border_source_ids,
            "member_count": self.member_count,
            "core_support_count": self.core_support_count,
            "cluster_start_date": self.cluster_start_date,
            "cluster_end_date": self.cluster_end_date,
            "centroid_lat": self.centroid_lat,
            "centroid_lon": self.centroid_lon,
            "gps_quality_counts": self.gps_quality_counts,
            "config_hash": self.config_hash,
        }


def _preliminary_fingerprint(core_member_ids: list[str]) -> str:
    payload = ",".join(sorted(core_member_ids))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_cluster_id(*, member_source_ids: list[str], config_hash: str, forecast_origin_id: str) -> str:
    """Part 13: sorted member source IDs + config hash + forecast origin
    ID, hashed together — never `cluster_0`/`cluster_1`. Reordering the
    input never changes this, because `member_source_ids` is always
    sorted before hashing."""
    payload = "|".join(sorted(member_source_ids)) + "||" + config_hash + "||" + forecast_origin_id
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"STCLUSTER:{digest[:24]}"


def run_st_clustering(
    *,
    usable_points: list[tuple[str, float, float, str]],
    core_support_by_id: dict[str, CoreSupportAssignment],
    eps_space_km: float,
    eps_time_days: float,
    min_core_supports: int,
    config_hash: str,
    forecast_origin_id: str,
) -> tuple[dict[str, ClusterAssignment], list[ClusterSummary]]:
    """`usable_points`: `(source_id, lat, lon, cluster_event_date)` for
    `ST_USABLE` sources ONLY (the caller — `snapshot.py` — excludes
    `ST_TEMPORAL_UNUSABLE` sources before calling this). Returns
    `({source_id: ClusterAssignment}, [ClusterSummary, ...])`. An empty
    or all-`NOISE` result is valid (ST-08) — this function never raises
    just because no cluster formed."""
    if not usable_points:
        return {}, []

    point_lookup = {p[0]: (p[1], p[2], p[3]) for p in usable_points}
    graph = build_neighbor_graph(usable_points, eps_space_km=eps_space_km, eps_time_days=eps_time_days)

    # -- Step 1: CORE points — distinct core_support_ids among neighbors
    # (self included) >= min_core_supports. Never a raw neighbor headcount.
    core_ids: set[str] = set()
    for source_id, neighbor_ids in graph.items():
        support_ids = set()
        for nid in neighbor_ids:
            csa = core_support_by_id.get(nid)
            if csa is not None and csa.core_support_id is not None:
                support_ids.add(csa.core_support_id)
        if len(support_ids) >= min_core_supports:
            core_ids.add(source_id)

    # -- Step 2: connected components among CORE points (density-reachable
    # via core-to-core joint-neighborhood edges), sorted-id BFS for
    # determinism regardless of input order.
    sorted_ids = sorted(graph.keys())
    component_of: dict[str, int] = {}
    next_component = 0
    for source_id in sorted_ids:
        if source_id not in core_ids or source_id in component_of:
            continue
        stack = [source_id]
        component_of[source_id] = next_component
        while stack:
            current = stack.pop()
            for neighbor in sorted(graph[current]):
                if neighbor in core_ids and neighbor not in component_of:
                    component_of[neighbor] = next_component
                    stack.append(neighbor)
        next_component += 1

    components: dict[int, list[str]] = {}
    for source_id, comp in component_of.items():
        components.setdefault(comp, []).append(source_id)
    preliminary_fingerprint = {comp: _preliminary_fingerprint(members) for comp, members in components.items()}

    # -- Step 3: BORDER assignment — deterministic tie-break (Part 12).
    border_component: dict[str, int] = {}
    for source_id in sorted_ids:
        if source_id in core_ids:
            continue
        touching_components: dict[int, float] = {}
        lat_b, lon_b, _ = point_lookup[source_id]
        for neighbor in graph[source_id]:
            if neighbor not in core_ids:
                continue
            comp = component_of[neighbor]
            lat_c, lon_c, _ = point_lookup[neighbor]
            d = distance_km(lat_b, lon_b, lat_c, lon_c)
            if comp not in touching_components or d < touching_components[comp]:
                touching_components[comp] = d
        if not touching_components:
            continue
        min_distance = min(touching_components.values())
        tied_components = [c for c, d in touching_components.items() if d == min_distance]
        chosen = min(tied_components, key=lambda c: preliminary_fingerprint[c])
        border_component[source_id] = chosen

    # -- Step 4: assemble final clusters + assignments.
    assignments: dict[str, ClusterAssignment] = {}
    summaries: list[ClusterSummary] = []

    for comp in sorted(components.keys()):
        core_members = sorted(components[comp])
        border_members = sorted(sid for sid, c in border_component.items() if c == comp)
        all_members = sorted(core_members + border_members)
        cluster_id = _stable_cluster_id(
            member_source_ids=all_members, config_hash=config_hash, forecast_origin_id=forecast_origin_id
        )

        for sid in core_members:
            assignments[sid] = ClusterAssignment(source_id=sid, cluster_id=cluster_id, is_noise=False, cluster_role=CORE)
        for sid in border_members:
            assignments[sid] = ClusterAssignment(source_id=sid, cluster_id=cluster_id, is_noise=False, cluster_role=BORDER)

        dates = [point_lookup[sid][2] for sid in all_members]
        support_ids = {
            core_support_by_id[sid].core_support_id
            for sid in core_members
            if core_support_by_id.get(sid) and core_support_by_id[sid].core_support_id is not None
        }
        gps_counts = Counter(core_support_by_id[sid].gps_quality for sid in all_members if core_support_by_id.get(sid))
        lats = [point_lookup[sid][0] for sid in all_members]
        lons = [point_lookup[sid][1] for sid in all_members]

        summaries.append(
            ClusterSummary(
                cluster_id=cluster_id,
                member_source_ids=all_members,
                core_source_ids=core_members,
                border_source_ids=border_members,
                member_count=len(all_members),
                core_support_count=len(support_ids),
                cluster_start_date=min(dates),
                cluster_end_date=max(dates),
                centroid_lat=sum(lats) / len(lats),
                centroid_lon=sum(lons) / len(lons),
                gps_quality_counts=dict(gps_counts),
                config_hash=config_hash,
            )
        )

    # -- Step 5: NOISE — everything else, retained explicitly (Part 14).
    for source_id in sorted_ids:
        if source_id in assignments:
            continue
        assignments[source_id] = ClusterAssignment(source_id=source_id, cluster_id=None, is_noise=True, cluster_role=NOISE)

    return assignments, summaries
