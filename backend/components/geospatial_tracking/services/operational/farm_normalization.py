"""GEO-INT-01 Section 9: GPS validation for host-supplied farm records.

A farm is spatially usable only when it carries a real, finite,
in-range coordinate pair. This module never invents one — no district ->
centroid guess, no free-text-location -> GPS guess (Section 9 explicit
prohibition). A farm failing the check is still returned (never dropped
silently) with `LocationStatus.LOCATION_REQUIRED`, so a caller can show
"needs geolocation" rather than have the farm vanish.

Deliberately does not reuse `schemas.GpsQuality` (EXACT/APPROXIMATE/
COARSE/UNKNOWN) — that enum grades the *provenance* of a scientific
historical/live-domain coordinate (was it geocoded, is it a country
centroid, etc.), a question this boundary cannot answer for a live farm
record. `LocationStatus` here only asks the narrower operational question
"is this coordinate present and usable at all" (Section 9's exact
checklist), so a new, smaller enum is the right amount of reuse rather
than overloading a scientific-domain enum with a meaning it wasn't
designed for.
"""

from __future__ import annotations

import math

from ...domain.operational_enums import LocationStatus
from ...domain.operational_models import HostFarmRecord, OperationalFarm


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool):  # bool is a numeric subtype in Python; never a coordinate
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _has_valid_coordinates(latitude: object, longitude: object) -> bool:
    if not _is_finite_number(latitude) or not _is_finite_number(longitude):
        return False
    return -90.0 <= float(latitude) <= 90.0 and -180.0 <= float(longitude) <= 180.0


def normalize_assigned_farm(raw: HostFarmRecord) -> OperationalFarm:
    """Section 8/9: builds the minimal `OperationalFarm` DTO from one raw
    host farm record, classifying its GPS usability. Never repairs or
    guesses a coordinate (Section 9/11)."""
    valid = _has_valid_coordinates(raw.latitude, raw.longitude)
    return OperationalFarm(
        farm_id=raw.farm_id,
        latitude=float(raw.latitude) if valid else None,
        longitude=float(raw.longitude) if valid else None,
        location_status=(LocationStatus.VALID if valid else LocationStatus.LOCATION_REQUIRED).value,
        location_district=raw.location_district,
        total_animals=raw.total_animals,
    )
