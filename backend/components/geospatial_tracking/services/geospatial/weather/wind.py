"""Checkpoint 5 Part 11: wind speed/direction -> u10/v10 component
derivation.

Meteorological wind direction is the compass bearing the wind is blowing
FROM (clockwise from north) — the OPPOSITE sense from the geodesic
"source -> cell" bearing used in `services/geospatial/distance.py`. Do
not reuse that module's azimuth-to-vector conversion for wind; the sign
convention differs and mixing them up would silently reverse every wind
vector.

    u10 (eastward wind component)  = -speed * sin(direction)
    v10 (northward wind component) = -speed * cos(direction)

`u` = EASTWARD component, `v` = NORTHWARD component — the standard
meteorological convention (never swapped; WX-01 tests they stay distinct
and correctly assigned).

**Wind DIRECTION is never "disease spread direction."** This module
computes nothing about how LSD spreads — it is a physical description of
air movement only, kept as a raw environmental covariate (WX-03).
"""

from __future__ import annotations

import math


def wind_components_from_speed_direction(speed_m_s: float, direction_from_deg: float) -> tuple[float, float]:
    """`direction_from_deg`: meteorological convention, degrees clockwise
    from north, the direction the wind is blowing FROM. Returns
    `(u10, v10)` in the same units as `speed_m_s`."""
    direction_rad = math.radians(direction_from_deg)
    u10 = -speed_m_s * math.sin(direction_rad)
    v10 = -speed_m_s * math.cos(direction_rad)
    return u10, v10


def wind_speed_from_components(u10: float, v10: float) -> float:
    return math.hypot(u10, v10)
