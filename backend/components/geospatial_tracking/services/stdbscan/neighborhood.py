"""Checkpoint 6B Part 9: the joint spatiotemporal neighborhood definition.

Two source records `a`, `b` are neighbors ONLY when BOTH:

    geodesic_distance_km(a, b) <= eps_space_km   (WGS84 geodesic — pyproj.Geod,
                                                    never raw lat/lon degrees
                                                    treated as kilometres)
    AND
    abs(event_date_a - event_date_b) <= eps_time_days

Both threshold boundaries are INCLUSIVE (ST-04) — `<=`, never `<`.

**Self-support semantics (Part 9 / ST-05)**: a point is always counted as
its own neighbor here (distance 0km, time-diff 0 days, trivially within
any `eps_space_km >= 0`/`eps_time_days >= 0`) — matching standard DBSCAN
semantics, where a point counts toward its own `MinPts`. Because of the
approximate-GPS core-density guard (`core_support.py`), what actually
gets compared against `min_core_supports` downstream is the number of
DISTINCT `core_support_id`s among a point's neighbors (itself included),
never a raw neighbor headcount — see `cluster.py`.
"""

from __future__ import annotations

from ..dates import parse_flexible_date
from ..geospatial.distance import distance_km


def joint_neighbors(
    *,
    lat_a: float,
    lon_a: float,
    date_a: str,
    lat_b: float,
    lon_b: float,
    date_b: str,
    eps_space_km: float,
    eps_time_days: float,
) -> bool:
    """Pure: the exact joint-neighborhood test (ST-01..04)."""
    spatial_km = distance_km(lat_a, lon_a, lat_b, lon_b)
    if spatial_km > eps_space_km:
        return False
    parsed_a = parse_flexible_date(date_a)
    parsed_b = parse_flexible_date(date_b)
    if parsed_a is None or parsed_b is None:
        raise ValueError(f"unparseable cluster_event_date: {date_a!r} / {date_b!r}")
    temporal_days = abs((parsed_a - parsed_b).days)
    return temporal_days <= eps_time_days


def build_neighbor_graph(
    points: list[tuple[str, float, float, str]], *, eps_space_km: float, eps_time_days: float
) -> dict[str, list[str]]:
    """`points`: `(source_id, lat, lon, cluster_event_date)` tuples —
    already restricted to `ST_USABLE` sources only by the caller. Returns
    `{source_id: sorted_list_of_neighbor_source_ids}` — a source is
    always included in its OWN neighbor list (self-support, see module
    docstring). Deterministic regardless of input order (ST-06): the
    graph is built by sorted source_id, and every adjacency list is
    itself sorted."""
    sorted_points = sorted(points, key=lambda p: p[0])
    graph: dict[str, list[str]] = {p[0]: [] for p in sorted_points}

    for i, (id_a, lat_a, lon_a, date_a) in enumerate(sorted_points):
        for id_b, lat_b, lon_b, date_b in sorted_points[i:]:
            if id_a == id_b:
                graph[id_a].append(id_b)  # self-support
                continue
            if joint_neighbors(
                lat_a=lat_a, lon_a=lon_a, date_a=date_a,
                lat_b=lat_b, lon_b=lon_b, date_b=date_b,
                eps_space_km=eps_space_km, eps_time_days=eps_time_days,
            ):
                graph[id_a].append(id_b)
                graph[id_b].append(id_a)

    return {source_id: sorted(set(neighbors)) for source_id, neighbors in graph.items()}
