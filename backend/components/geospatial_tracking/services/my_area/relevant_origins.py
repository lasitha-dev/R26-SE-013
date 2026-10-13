"""GEO-AREA-01 Section 10/11: ranks real historical/model origins by real
distance from an authorized area. Pure -- takes already-fetched
`(origin, trigger_locations)` pairs (`repositories/scientific_read_port.py`
is the only place that touches a repository), so this is fully
unit-testable with plain tuples.

Section 11: distance is `data_processing.geo.haversine_km` -- the
EXISTING geodesic helper (verified read-only, already used for dedup
coordinate-tolerance checks), never a second distance formula.
"""

from __future__ import annotations

from ...data_processing.geo import haversine_km
from ...domain.my_area_models import RelevantOrigin
from ...services.forecast_origin import ForecastOrigin


def rank_relevant_origins(
    origins_with_trigger_locations: list[tuple[ForecastOrigin, list[tuple[str, float, float]]]],
    *,
    area_latitude: float,
    area_longitude: float,
    disease: str,
    limit: int = 5,
) -> list[RelevantOrigin]:
    """Section 10: an origin with NO real trigger-source coordinate is
    excluded entirely (never assigned a fabricated distance). Sorted by
    `distance_from_area_km`, then `origin_id` as a stable tie-breaker
    (Section 10/18's determinism requirement) -- never insertion order.
    """
    candidates: list[RelevantOrigin] = []
    for origin, locations in origins_with_trigger_locations:
        if not locations:
            continue
        nearest_km = min(haversine_km(area_latitude, area_longitude, lat, lon) for _, lat, lon in locations)
        candidates.append(
            RelevantOrigin(
                origin_id=origin.forecast_origin_id,
                disease=disease,
                t0=origin.t0,
                distance_from_area_km=round(nearest_km, 3),
                # distance_basis defaults to RELEVANT_ORIGIN_DISTANCE_BASIS
                # ("NEAREST_T0_TRIGGER_SOURCE") -- `locations` here always
                # come from `ScientificReadPort.get_origin_trigger_locations`,
                # never `analysis.eligible_sources`.
                scientific_mode=origin.temporal_mode,
            )
        )
    candidates.sort(key=lambda c: (c.distance_from_area_km, c.origin_id))
    return candidates[:limit]
