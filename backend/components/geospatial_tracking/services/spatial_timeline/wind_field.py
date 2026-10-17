"""Daily wind for the Trajectory direction (display extension, read-only).

For each Asia/Colombo calendar day the hourly 10 m wind at a case's ERA5
grid cell is reduced to one vector, and also to eight 3-hour vectors
(`blocks`, 00-03 h ... 21-24 h local) -- on the coast the daytime sea breeze
and night land breeze turn the wind within a day, and the spread path follows
those turns:

  mean (u, v)            vector mean of the hourly winds
  toward_deg             bearing the air moves TOWARD (downwind)
  steadiness = |mean (u, v)| / mean hourly speed   (0 = variable, 1 = steady)

Past dates (older than ARCHIVE_LAG_DAYS) come from the existing ERA5 archive
client (`era5.fetch_hourly_payload`); recent and future dates from the
Open-Meteo forecast API. Each day records which one it is (REANALYSIS vs
FORECAST). A failed request returns no day -- never a substituted value.

Not part of the C0 score. The 7C wind-anisotropic candidates were not
selected because 30.7 % of origins lacked ERA5 wind input, so a wind-informed
direction is an explicitly labelled extension, not the evaluated model.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from ..geospatial.weather.era5 import fetch_hourly_payload
from ..geospatial.weather.wind import wind_components_from_speed_direction
from .environment import snap_to_era5_grid

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_LAG_DAYS = 6
KIND_REANALYSIS = "ERA5_REANALYSIS"
KIND_FORECAST = "OPEN_METEO_FORECAST"
_COLOMBO = ZoneInfo("Asia/Colombo")


BLOCK_HOURS = 3
BLOCKS_PER_DAY = 24 // BLOCK_HOURS


def daily_vectors(hours: list[tuple[str, float, float]]) -> dict[str, dict]:
    """`hours`: (key, speed m/s, direction-FROM deg) samples, grouped by key
    (an Asia/Colombo date ISO, or a (date, block) pair)."""
    by_day: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    for day, speed, direction in hours:
        if speed is None or direction is None or not math.isfinite(speed) or not math.isfinite(direction):
            continue
        u, v = wind_components_from_speed_direction(speed, direction)
        by_day[day].append((u, v, speed))
    out = {}
    for day, samples in by_day.items():
        mean_u = sum(s[0] for s in samples) / len(samples)
        mean_v = sum(s[1] for s in samples) / len(samples)
        mean_speed = sum(s[2] for s in samples) / len(samples)
        resultant = math.hypot(mean_u, mean_v)
        toward = (math.degrees(math.atan2(mean_u, mean_v)) + 360.0) % 360.0 if resultant > 1e-9 else None
        out[day] = {
            "toward_deg": toward,
            "from_deg": (toward + 180.0) % 360.0 if toward is not None else None,
            "mean_speed_ms": round(mean_speed, 3),
            "steadiness": round(resultant / mean_speed, 4) if mean_speed > 1e-9 else 0.0,
            "hours": len(samples),
        }
    return out


def _with_blocks(hours: list[tuple[str, int, float, float]]) -> dict[str, dict]:
    """Daily vectors plus each day's eight 3-hour vectors (None where no hours)."""
    days = daily_vectors([(day, speed, direction) for day, _hour, speed, direction in hours])
    blocks = daily_vectors([((day, hour // BLOCK_HOURS), speed, direction) for day, hour, speed, direction in hours])
    for day, vec in days.items():
        vec["blocks"] = [blocks.get((day, b)) for b in range(BLOCKS_PER_DAY)]
    return days


def _archive_hours(lat: float, lon: float, start: date, end: date) -> list[tuple[str, int, float, float]]:
    # One extra UTC day so the local (UTC+5:30) evening of `end` is included.
    payload = fetch_hourly_payload(lat, lon, start.isoformat(), (end + timedelta(days=1)).isoformat())
    hourly = payload.get("hourly") or {}
    out = []
    for stamp, speed, direction in zip(hourly.get("time", []), hourly.get("wind_speed_10m", []), hourly.get("wind_direction_10m", [])):
        # Archive timestamps are UTC (era5.py); group them by Asia/Colombo day.
        local = datetime.fromisoformat(stamp).replace(tzinfo=ZoneInfo("UTC")).astimezone(_COLOMBO)
        out.append((local.date().isoformat(), local.hour, speed, direction))
    return out


def _forecast_hours(lat: float, lon: float, start: date, end: date) -> list[tuple[str, int, float, float]]:
    params = {"latitude": lat, "longitude": lon, "start_date": start.isoformat(), "end_date": end.isoformat(),
              "hourly": "wind_speed_10m,wind_direction_10m", "wind_speed_unit": "ms", "timezone": "Asia/Colombo"}
    response = requests.get(FORECAST_URL, params=params, timeout=20)
    response.raise_for_status()
    hourly = response.json().get("hourly") or {}
    return [(stamp[:10], int(stamp[11:13]), speed, direction) for stamp, speed, direction
            in zip(hourly.get("time", []), hourly.get("wind_speed_10m", []), hourly.get("wind_direction_10m", []))]


# Only complete fetches are kept: a failed or partial request is retried on the
# next call instead of leaving a case without wind until the server restarts.
_WIND_CACHE: dict[tuple, tuple] = {}
_WIND_CACHE_MAX = 256


def _cached_daily_wind(lat: float, lon: float, start_iso: str, days: int, today_iso: str) -> tuple:
    key = (lat, lon, start_iso, days, today_iso)
    if key in _WIND_CACHE:
        return _WIND_CACHE[key]
    result = _fetch_daily_wind(lat, lon, start_iso, days, today_iso)
    if len(result) >= min(days, 16):  # every requested day that can exist (forecast reaches ~16 days)
        if len(_WIND_CACHE) >= _WIND_CACHE_MAX:
            _WIND_CACHE.pop(next(iter(_WIND_CACHE)))
        _WIND_CACHE[key] = result
    return result


def _fetch_daily_wind(lat: float, lon: float, start_iso: str, days: int, today_iso: str) -> tuple:
    start, today = date.fromisoformat(start_iso), date.fromisoformat(today_iso)
    end = start + timedelta(days=max(0, days - 1))
    archive_end = min(end, today - timedelta(days=ARCHIVE_LAG_DAYS))
    result: dict[str, dict] = {}
    if start <= archive_end:
        try:
            for day, vec in _with_blocks(_archive_hours(lat, lon, start, archive_end)).items():
                if start.isoformat() <= day <= archive_end.isoformat():
                    result[day] = {**vec, "kind": KIND_REANALYSIS}
        except (requests.RequestException, ValueError):
            pass
    forecast_start = max(start, archive_end + timedelta(days=1))
    forecast_end = min(end, today + timedelta(days=15))
    if forecast_start <= forecast_end:
        try:
            for day, vec in _with_blocks(_forecast_hours(lat, lon, forecast_start, forecast_end)).items():
                result.setdefault(day, {**vec, "kind": KIND_FORECAST})
        except (requests.RequestException, ValueError):
            pass
    return tuple(sorted(result.items()))


def daily_wind(lat: float, lon: float, start: date, days: int, *, today: date) -> dict[str, dict]:
    """{Asia/Colombo date ISO: wind vector} at the ERA5 cell of (lat, lon)."""
    glat, glon = snap_to_era5_grid(lat, lon)
    return dict(_cached_daily_wind(glat, glon, start.isoformat(), days, today.isoformat()))
