"""Real ERA5 environmental observations at the spatial timeline's sources.

Executes the existing research feature builder unchanged:
`services.geospatial.weather.era5.build_pre_t0_weather_summary` (Open-Meteo
archive, ERA5 reanalysis, strictly pre-t0 hourly samples, Asia/Colombo date
boundary, Magnus-Tetens relative humidity, u/v wind components and vector
resultant). Lookback = `config.WEATHER_LOOKBACK_HOURS_DEV_DEFAULT` (24 h, the
research development default).

DISPLAY ONLY. No evaluated environmental influence model exists: the
wind-anisotropic C0 candidates were evaluated in 7C/7D and NOT selected, and
no coefficients exist for temperature, humidity or rainfall. These values are
therefore never used in the frozen C0 score.

Privacy: each source is snapped to its ERA5 0.25-degree grid cell before the
request, so no exact farm coordinate leaves the backend; sources sharing a
grid cell share one request.
"""

from __future__ import annotations

import math
from datetime import date
from functools import lru_cache

from ...config import WEATHER_LOOKBACK_HOURS_DEV_DEFAULT
from ..geospatial.weather.base import T0Precision
from ..geospatial.weather.era5 import WEATHER_MODEL_LABEL, WEATHER_MODEL_RESOLUTION, WEATHER_PROVIDER, build_pre_t0_weather_summary

ERA5_GRID_DEG = 0.25
INFLUENCE_STATUS = "NOT_EXECUTING_NO_SELECTED_ENVIRONMENTAL_MODEL"
INFLUENCE_REASON = ("Wind-anisotropic C0 candidates were evaluated in 7C/7D and not selected; no coefficients exist for "
                    "temperature, humidity or rainfall. Values are descriptive context only and never change the frozen C0 score.")


def snap_to_era5_grid(lat: float, lon: float) -> tuple[float, float]:
    return round(lat / ERA5_GRID_DEG) * ERA5_GRID_DEG, round(lon / ERA5_GRID_DEG) * ERA5_GRID_DEG


def wind_direction_from_components(u10: float, v10: float) -> float | None:
    """Meteorological direction the wind blows FROM (deg, 0 = north), the
    inverse of `wind.wind_components_from_speed_direction` (u = -s sin d, v = -s cos d)."""
    if not (math.isfinite(u10) and math.isfinite(v10)) or (u10 == 0 and v10 == 0):
        return None
    return (math.degrees(math.atan2(-u10, -v10)) + 360.0) % 360.0


@lru_cache(maxsize=256)
def _summary(lat: float, lon: float, t0: str, lookback_hours: float) -> tuple[dict, tuple[dict, ...]]:
    window, features = build_pre_t0_weather_summary(
        latitude=lat, longitude=lon, t0=t0, t0_precision=T0Precision.DATE_ONLY.value, lookback_hours=lookback_hours)
    return window.as_dict(), tuple(f.as_dict() for f in features)


def _observation(lat: float, lon: float, source_ids: list[str], *, as_of: date, lookback_hours: float, role: str) -> dict:
    try:
        window, features = _summary(lat, lon, as_of.isoformat(), float(lookback_hours))
    except Exception as exc:  # network/provider failure -> explicit, never invented
        return {"role": role, "grid_cell": {"latitude": lat, "longitude": lon}, "source_ids": sorted(source_ids),
                "status": "WEATHER_PROVIDER_UNAVAILABLE", "error": type(exc).__name__, "features": []}
    return _build_observation(lat, lon, source_ids, window, features, role)


def environment_at_sources(sources: list[dict], *, as_of: date, lookback_hours: float = WEATHER_LOOKBACK_HOURS_DEV_DEFAULT,
                           district_reference: tuple[str, float, float] | None = None) -> dict:
    """Observations at each eligible source's ERA5 cell, plus (district scope)
    one at a representative point INSIDE the vet's own district polygon, so a
    district never shows only another district's weather."""
    cells: dict[tuple[float, float], list[str]] = {}
    for s in sources:
        cells.setdefault(snap_to_era5_grid(s["latitude"], s["longitude"]), []).append(s["source_id"])
    observations = []
    if district_reference is not None:
        name, ref_lat, ref_lon = district_reference
        lat, lon = snap_to_era5_grid(ref_lat, ref_lon)
        obs = _observation(lat, lon, [], as_of=as_of, lookback_hours=lookback_hours, role="DISTRICT_REFERENCE_POINT")
        obs["district"] = name
        observations.append(obs)
    for (lat, lon), source_ids in sorted(cells.items()):
        observations.append(_observation(lat, lon, source_ids, as_of=as_of, lookback_hours=lookback_hours, role="ELIGIBLE_SOURCE_CELL"))
    return _result(observations, as_of=as_of, lookback_hours=lookback_hours)


def _build_observation(lat, lon, source_ids, window, features, role) -> dict:
    values = {f["feature_name"]: f for f in features}
    u, v = values.get("mean_u10", {}).get("value"), values.get("mean_v10", {}).get("value")
    derived = []
    if isinstance(u, (int, float)) and isinstance(v, (int, float)):
        direction = wind_direction_from_components(u, v)
        if direction is not None:
            derived.append({"feature_name": "vector_mean_wind_direction_from", "value": direction, "units": "deg (from, 0=N)",
                            "status": "REAL", "analysis_method": "atan2(-mean_u10, -mean_v10): inverse of the module's u=-s*sin(d), v=-s*cos(d)"})
    return {
        "role": role, "grid_cell": {"latitude": lat, "longitude": lon}, "source_ids": sorted(source_ids), "status": "OK",
        "window": {k: window[k] for k in ("window_start", "window_end", "number_of_hourly_samples", "source_timezone", "temporal_role", "availability_quality")},
        "features": [{k: f[k] for k in ("feature_name", "value", "units", "status", "analysis_method")} for f in features] + derived,
    }


def _result(observations: list[dict], *, as_of: date, lookback_hours: float) -> dict:
    return {
        "status": "OK" if observations else "NO_SOURCES",
        "evidence_status": "EXECUTING_DISPLAY_ONLY",
        "used_in_score": False,
        "influence_status": INFLUENCE_STATUS,
        "influence_reason": INFLUENCE_REASON,
        "provider": WEATHER_PROVIDER, "model": WEATHER_MODEL_LABEL, "resolution": WEATHER_MODEL_RESOLUTION,
        "kind": "REANALYSIS_HISTORICAL_NOT_LIVE_WEATHER",
        "forecast_context": {"status": "NOT_AVAILABLE",
                             "reason": "No weather forecast source is integrated; ERA5 is historical reanalysis (~5-day lag). Nothing is extrapolated."},
        "as_of": as_of.isoformat(), "lookback_hours": lookback_hours,
        "lookback_provenance": "config.WEATHER_LOOKBACK_HOURS_DEV_DEFAULT (research development default)",
        "privacy": "source coordinates snapped to the 0.25-degree ERA5 grid before any request",
        "observations": observations,
    }
