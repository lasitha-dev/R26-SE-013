"""Checkpoint 5 Part 5-6: geodesic distance/bearing on the real WGS84
ellipsoid.

**NEVER treat degrees of latitude/longitude as kilometres.** A degree of
longitude is ~111 km at the equator but shrinks toward the poles
(~cos(latitude) * 111 km); a naive `sqrt(dlat**2 + dlon**2)` "distance" is
not a distance in any real unit and is explicitly forbidden by the
master-prompt permanent rule. This module uses `pyproj.Geod` (the WGS84
ellipsoid, the same standard the rest of geodesy/GPS uses) for every
distance and bearing calculation — trusted, tested, no ad-hoc formula
reimplemented here.

Also provides the SOURCE -> GRID CELL unit vector
(`source_to_cell_unit_vector`) used for `geometry_by_source` (Part 8):
`t_hat_east`/`t_hat_north` are the local East/North components of the
unit vector pointing from the source to the cell, derived from the
geodesic forward azimuth — never confused with compass "bearing FROM"
convention, and never swapped with wind-direction ("wind coming FROM")
convention used in `services/geospatial/weather/`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pyproj

_GEOD = pyproj.Geod(ellps="WGS84")


@dataclass(frozen=True)
class GeodesicResult:
    distance_km: float
    forward_azimuth_deg: float  # degrees clockwise from north, source -> target
    back_azimuth_deg: float


def geodesic(lat1: float, lon1: float, lat2: float, lon2: float) -> GeodesicResult:
    """`pyproj.Geod.inv` takes (lon, lat) order internally — this function's
    own public signature is (lat, lon), matching every other field in this
    codebase (`AnimalReport.latitude`/`longitude`,
    `HistoricalOutbreakRecord.latitude`/`longitude`, etc.) so callers never
    have to remember a different argument order for this one function."""
    forward_az, back_az, distance_m = _GEOD.inv(lon1, lat1, lon2, lat2)
    return GeodesicResult(
        distance_km=distance_m / 1000.0,
        forward_azimuth_deg=forward_az % 360.0,
        back_azimuth_deg=back_az % 360.0,
    )


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return geodesic(lat1, lon1, lat2, lon2).distance_km


@dataclass(frozen=True)
class SourceToCellVector:
    distance_km: float
    t_hat_east: float
    t_hat_north: float


def source_to_cell_unit_vector(
    source_lat: float, source_lon: float, cell_lat: float, cell_lon: float
) -> SourceToCellVector:
    """**HISTORICAL** (Checkpoint 5, unchanged through 7B-8B.2) — unit
    vector pointing SOURCE -> GRID CELL, in local East/North components,
    from the geodesic DEPARTURE azimuth measured AT THE SOURCE (source as
    the origin, cell as the target — never the reverse). `t_hat_east**2 +
    t_hat_north**2 == 1` (up to floating point) for any two distinct
    points; both components are 0 only in the degenerate same-point case
    (`distance_km == 0`), where no direction is defined and callers must
    not divide by it.

    **Checkpoint 8B.3 finding**: this vector is expressed in the
    SOURCE's local tangent frame, not the CELL's. On the WGS84 ellipsoid
    these differ by the geodesic's meridian-convergence angle over the
    source-cell path (nonzero off the equator/meridians) -- small at the
    domain's characteristic scales but NOT identically zero. This
    function's contract, output, and every caller that already depends
    on it (7B-8B.2, all historical artifacts) are preserved COMPLETELY
    UNCHANGED for provenance. For the cell-local tangent (the frame the
    true gradient of a distance function actually lives in), use
    `source_to_cell_tangent_at_cell` below -- a distinct, separately
    named function, never silently substituted for this one."""
    result = geodesic(source_lat, source_lon, cell_lat, cell_lon)
    az_rad = math.radians(result.forward_azimuth_deg)
    # compass azimuth (clockwise from north) -> east/north unit components
    t_hat_east = math.sin(az_rad)
    t_hat_north = math.cos(az_rad)
    return SourceToCellVector(
        distance_km=result.distance_km,
        t_hat_east=t_hat_east if result.distance_km > 0 else 0.0,
        t_hat_north=t_hat_north if result.distance_km > 0 else 0.0,
    )


# =============================================================================
# Checkpoint 8B.3 -- ACTIVE cell-local geodesic tangent. New, additive,
# separately named. `source_to_cell_unit_vector` above is untouched.
# =============================================================================

CELL_LOCAL_EAST_NORTH_TANGENT_FRAME = "CELL_LOCAL_EAST_NORTH_TANGENT_FRAME"


@dataclass(frozen=True)
class SourceToCellTangentAtCell:
    distance_km: float
    source_departure_azimuth_deg: float  # az12 -- historical function's convention, kept only for provenance/comparison
    cell_arrival_forward_azimuth_deg: float  # (az21 + 180) % 360 -- the SOURCE->CELL direction expressed AT THE CELL
    t_cell_east: float
    t_cell_north: float
    coordinate_frame: str

    def as_dict(self) -> dict:
        return {
            "distance_km": self.distance_km,
            "source_departure_azimuth_deg": self.source_departure_azimuth_deg,
            "cell_arrival_forward_azimuth_deg": self.cell_arrival_forward_azimuth_deg,
            "t_cell_east": self.t_cell_east, "t_cell_north": self.t_cell_north,
            "coordinate_frame": self.coordinate_frame,
        }


def source_to_cell_tangent_at_cell(
    source_lat: float, source_lon: float, cell_lat: float, cell_lon: float
) -> SourceToCellTangentAtCell:
    """The SOURCE -> CELL direction expressed in the CELL's OWN local
    East/North tangent frame (`CELL_LOCAL_EAST_NORTH_TANGENT_FRAME`) --
    the frame the gradient of a geodesic distance function actually
    lives in at the evaluation point. `pyproj.Geod.inv(lon1, lat1, lon2,
    lat2)` returns `az21` as the azimuth AT POINT 2 (the cell) pointing
    BACK toward point 1 (the source); the direction of arrival AT THE
    CELL (continuing the same geodesic forward, i.e. source->cell) is
    therefore `(az21 + 180) % 360` -- never `az12` (the DEPARTURE
    azimuth at the source, `source_to_cell_unit_vector`'s convention,
    which differs from this by the geodesic's meridian-convergence
    angle off the equator/meridians). `t_cell_east**2 + t_cell_north**2
    == 1` for any two distinct points; both components are exactly 0
    only at `distance_km == 0`, where direction is genuinely undefined
    and never fabricated."""
    result = geodesic(source_lat, source_lon, cell_lat, cell_lon)
    cell_arrival_forward_bearing = (result.back_azimuth_deg + 180.0) % 360.0
    az_rad = math.radians(cell_arrival_forward_bearing)
    t_cell_east = math.sin(az_rad)
    t_cell_north = math.cos(az_rad)
    return SourceToCellTangentAtCell(
        distance_km=result.distance_km,
        source_departure_azimuth_deg=result.forward_azimuth_deg,
        cell_arrival_forward_azimuth_deg=cell_arrival_forward_bearing,
        t_cell_east=t_cell_east if result.distance_km > 0 else 0.0,
        t_cell_north=t_cell_north if result.distance_km > 0 else 0.0,
        coordinate_frame=CELL_LOCAL_EAST_NORTH_TANGENT_FRAME,
    )
