"""Day-by-day spread heading of one case (Trajectory display).

Lumpy skin disease moves mainly with blood-feeding insects (carried by the
wind) and between cattle, over land. So once a day, at the case's current
front, every compass direction theta (SECTORS of 10 deg) is scored by what
lies within the next ~10 km (LOOKAHEAD_KM):

    land     land_k  share of look-ahead points on Sri Lanka land (0 -> the
                     direction is impossible: insects and cattle do not cross
                     open sea, and a path is never deflected along the coast)
    hosts    host_k  mean FAO GLW4 cattle density ahead (2015, ~10 km pixels,
                     animals/km2) + HOST_FLOOR_PER_KM2
    wind     wind_k  exp(WIND_KAPPA * steadiness * cos(theta - downwind)) with the
                     day's NET wind: the vector mean of its hourly winds (ERA5
                     reanalysis / Open-Meteo forecast, wind_field.py). Sea and
                     land breezes cancel inside the day, so only the wind that
                     actually carries insects over 24 h counts -- no 3-hourly
                     zigzag.
    cases    case_k  exp(CASE_KAPPA * share * cos(theta - 8B.3 bearing)): the
                     frozen C0 negative-gradient tendency of the nearby eligible
                     cases (away from where cases are dense, into fresh herds),
                     weighted by its directional share (|resultant| / C0 mass).
    course   keep_k  exp(INERTIA_KAPPA * cos(theta - previous day's heading))

score = land_k * host_k * wind_k * case_k * keep_k. The day's heading is the
score-weighted circular mean of the dominant lobe (sectors within half of the
best score, so two opposite options never average into the sea); `confidence`
is the resultant length of ALL sector scores (0 = every direction equally
likely, 1 = one direction only). Below MIN_CONFIDENCE there is no direction.

Speed and length are NOT set here: the front moves at the evaluated 9C rate S0
and stops at the 25 km local evaluation distance (engine.py). The C0 score is
never changed by any of these factors.

This is an ADRS display heuristic built from real inputs, not a validated
spread model: the 7C wind and 7D host candidates were not selected in the
research, so wind and cattle are labelled environmental/host EXTENSIONS, and
WIND_KAPPA, CASE_KAPPA, INERTIA_KAPPA and MIN_CONFIDENCE are presentation
assumptions. Every factor is returned in the heading basis so the map can
explain each day.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pyproj
from shapely.geometry import Point

from ..geospatial.host_density.fao_glw import GLW_SPECIES, _cache_path_for

SECTORS = 36
LOOKAHEAD_KM = (2.0, 4.0, 6.0, 8.0, 10.0)  # spans one GLW4 pixel (~10 km)
WIND_KAPPA = 1.5      # fully steady net wind: downwind preferred ~20x over upwind (e^3)
CASE_KAPPA = 1.5      # same scale for the 8B.3 push of nearby cases
INERTIA_KAPPA = 1.0   # keeps a smooth course (e^2 ~ 7x ahead vs. turning back)
HOST_FLOOR_PER_KM2 = 1.0  # a direction with no recorded cattle is unlikely, not impossible
MIN_CONFIDENCE = 0.05     # below this the factors give no usable direction
SRI_LANKA_BBOX = (79.5, 5.85, 82.0, 9.9)
HEURISTIC_ID = "ADRS_DAILY_SPREAD_HEADING_2"

_GEOD = pyproj.Geod(ellps="WGS84")


@lru_cache(maxsize=1)
def cattle_density_grid():
    """(density array animals/km2, rasterio transform) over Sri Lanka, or None
    when the local GLW4 rasters are missing (then host_k = 1 and it is reported)."""
    try:
        import rasterio
        from rasterio.windows import from_bounds
        spec = GLW_SPECIES["cattle"]
        with rasterio.open(_cache_path_for(spec.count_filename)) as counts, rasterio.open(_cache_path_for(spec.area_filename)) as areas:
            window = from_bounds(*SRI_LANKA_BBOX, counts.transform)
            count = counts.read(1, window=window).astype("float64")
            area = areas.read(1, window=from_bounds(*SRI_LANKA_BBOX, areas.transform)).astype("float64")
            transform = counts.window_transform(window)
        valid = (count > 0) & (area > 0) & np.isfinite(count) & np.isfinite(area)
        return np.where(valid, count / np.where(valid, area, 1.0), 0.0), transform
    except Exception:
        return None


def cattle_density_at(lon: float, lat: float) -> float | None:
    grid = cattle_density_grid()
    if grid is None:
        return None
    density, transform = grid
    col, row = ~transform * (lon, lat)
    r, c = int(math.floor(row)), int(math.floor(col))
    if 0 <= r < density.shape[0] and 0 <= c < density.shape[1]:
        return float(density[r, c])
    return 0.0


def _angle_diff(a: float, b: float) -> float:
    return math.radians(((a - b) + 180.0) % 360.0 - 180.0)


def daily_heading(lat: float, lon: float, *, land_contains, case_tendency: dict | None = None, wind: dict | None = None,
                  previous_bearing: float | None = None) -> dict:
    """One day's heading at a front (see module docstring). `case_tendency`:
    8B.3 at the front ({bearing_deg, directional_share}); `wind`: the day's net
    wind ({toward_deg, steadiness, mean_speed_ms, kind}) or None."""
    has_hosts = cattle_density_grid() is not None
    downwind = wind.get("toward_deg") if wind else None
    steadiness = float(wind.get("steadiness") or 0.0) if downwind is not None else 0.0
    case_bearing = (case_tendency or {}).get("bearing_deg")
    case_share = float((case_tendency or {}).get("directional_share") or 0.0) if case_bearing is not None else 0.0
    sectors = []
    for k in range(SECTORS):
        theta = 360.0 * k / SECTORS
        on_land, hosts = 0, []
        for distance in LOOKAHEAD_KM:
            plon, plat, _ = _GEOD.fwd(lon, lat, theta, distance * 1000.0)
            if not land_contains(Point(plon, plat)):
                continue
            on_land += 1
            if has_hosts:
                hosts.append(cattle_density_at(plon, plat) or 0.0)
        land_k = on_land / len(LOOKAHEAD_KM)
        host_mean = sum(hosts) / len(hosts) if hosts else 0.0
        host_k = (host_mean + HOST_FLOOR_PER_KM2) if has_hosts else 1.0
        wind_k = math.exp(WIND_KAPPA * steadiness * math.cos(_angle_diff(theta, downwind))) if downwind is not None else 1.0
        case_k = math.exp(CASE_KAPPA * case_share * math.cos(_angle_diff(theta, case_bearing))) if case_bearing is not None else 1.0
        keep_k = math.exp(INERTIA_KAPPA * math.cos(_angle_diff(theta, previous_bearing))) if previous_bearing is not None else 1.0
        sectors.append({"bearing": theta, "score": land_k * host_k * wind_k * case_k * keep_k, "land": land_k,
                        "cattle_per_km2": round(host_mean, 2) if has_hosts else None})
    total = sum(s["score"] for s in sectors)
    basis = {"heuristic": HEURISTIC_ID, "wind_toward_deg": downwind, "wind_weight": round(steadiness, 4),
             "wind_speed_ms": wind.get("mean_speed_ms") if wind else None, "wind_kind": wind.get("kind") if wind else None,
             "case_bearing_deg": case_bearing, "case_share": round(case_share, 4),
             "cattle_here_per_km2": round(cattle_density_at(lon, lat), 2) if has_hosts else None,
             "cattle_source": "FAO GLW4 cattle 2015 (~10 km)" if has_hosts else "UNAVAILABLE"}
    if total <= 0:
        return {**basis, "bearing_deg": None, "confidence": 0.0, "reason": "NO_LAND_AHEAD"}
    east = sum(s["score"] * math.sin(math.radians(s["bearing"])) for s in sectors)
    north = sum(s["score"] * math.cos(math.radians(s["bearing"])) for s in sectors)
    confidence = math.hypot(east, north) / total
    if confidence < MIN_CONFIDENCE:
        return {**basis, "bearing_deg": None, "confidence": round(confidence, 4), "reason": "NO_PREFERRED_DIRECTION"}
    best = max(sectors, key=lambda s: s["score"])
    lobe = [s for s in sectors if s["score"] >= 0.5 * best["score"]]
    le = sum(s["score"] * math.sin(math.radians(s["bearing"])) for s in lobe)
    ln = sum(s["score"] * math.cos(math.radians(s["bearing"])) for s in lobe)
    bearing = (math.degrees(math.atan2(le, ln)) + 360.0) % 360.0 if math.hypot(le, ln) > 1e-12 else best["bearing"]
    ahead = min(sectors, key=lambda s: abs(_angle_diff(s["bearing"], bearing)))
    return {**basis, "bearing_deg": bearing, "confidence": round(confidence, 4),
            "cattle_ahead_per_km2": ahead["cattle_per_km2"], "land_ahead": ahead["land"]}
