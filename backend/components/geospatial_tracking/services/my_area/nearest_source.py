"""GEO-AREA-01 Section 13: nearest real historical source to the
authorized area, for one selected origin's already-fetched eligible
sources. Pure -- operates on plain `(source_id, latitude, longitude,
availability_quality, gps_quality)` tuples the caller extracts from the
real snapshot, never fetches anything itself.
"""

from __future__ import annotations

import math

from ...data_processing.geo import haversine_km
from ...domain.my_area_models import NearestHistoricalSource


def find_nearest_historical_source(
    eligible_sources: list[tuple[str, float, float, str | None, str | None]],
    *,
    area_latitude: float,
    area_longitude: float,
) -> NearestHistoricalSource | None:
    """`eligible_sources` items are
    `(source_id, latitude, longitude, availability_quality, gps_quality)`.
    Returns `None` (Section 13: "Return only if real coordinates exist")
    when no source has a finite coordinate pair -- never a guessed
    nearest source.
    """
    valid = [
        s
        for s in eligible_sources
        if isinstance(s[1], (int, float))
        and isinstance(s[2], (int, float))
        and math.isfinite(s[1])
        and math.isfinite(s[2])
    ]
    if not valid:
        return None

    nearest = min(valid, key=lambda s: haversine_km(area_latitude, area_longitude, s[1], s[2]))
    distance_km = haversine_km(area_latitude, area_longitude, nearest[1], nearest[2])
    return NearestHistoricalSource(
        source_id=nearest[0],
        distance_from_area_km=round(distance_km, 3),
        availability_quality=nearest[3],
        gps_quality=nearest[4],
    )
