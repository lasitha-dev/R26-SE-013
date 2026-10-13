"""Checkpoint 5 Part 11: relative humidity, derived — never invented.

Relative humidity is computed from temperature and dew point using the
Magnus-Tetens approximation (a standard, widely-used meteorological
formula — see e.g. Lawrence, M.G. (2005), "The Relationship between
Relative Humidity and the Dewpoint Temperature in Moist Air", BAMS):

    RH = 100 * exp((b*Td)/(c+Td)) / exp((b*T)/(c+T))

with b = 17.625, c = 243.04 (deg C), T = air temperature (deg C), Td = dew
point temperature (deg C). Both inputs must be real, sourced values (ERA5-
Land-derived `temperature_2m`/`dewpoint_2m` from the weather adapter) —
this module never invents T or Td; it only combines two already-real
values with a documented, tested formula.
"""

from __future__ import annotations

import math

MAGNUS_B = 17.625
MAGNUS_C = 243.04


def relative_humidity_percent(temperature_c: float, dewpoint_c: float) -> float:
    """Returns relative humidity in percent (0-100). Clamped to [0, 100]
    to absorb floating-point overshoot at the physical boundary
    (dewpoint == temperature -> RH == 100 exactly)."""
    numerator = math.exp((MAGNUS_B * dewpoint_c) / (MAGNUS_C + dewpoint_c))
    denominator = math.exp((MAGNUS_B * temperature_c) / (MAGNUS_C + temperature_c))
    rh = 100.0 * (numerator / denominator)
    return max(0.0, min(100.0, rh))
