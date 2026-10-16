"""
Public data sources for the v2 forecasting pipeline.

Every aggregation rule below was verified on 2026-10-13 by reproducing the
curated training datasets exactly:
- CHIRPS (WFP/HDX "Sri Lanka: Rainfall Indicators at Subnational Level", adm2):
    rainfall_mm = sum of the month's dekadal `rfh`   (100% of 2,400 rows)
    r3h         = mean of the month's dekadal `r3h`  (3-month rolling rainfall, mm)
    rfq         = mean of the month's dekadal `rfq`  (rainfall anomaly, % of normal)
- NASA POWER (community=AG, district points from geography.DISTRICTS):
    temperature = T2M, humidity = RH2M, wind_speed = WS2M (m/s)   (100% of rows).
    The monthly value equals the mean of the daily values, so recent months can be
    built from the daily endpoint (~4 day latency) before the monthly one is published.
- NOAA PSL indices: DMI (HadISST) matches the training data exactly. Nino 3.4
  (nina34.data) is now served from ERSST v6, so values differ slightly from the
  training extract; v2 rebuilds every year from the current file for consistency.
"""

from __future__ import annotations

import calendar
import io
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd

CHIRPS_URL = (
    "https://data.humdata.org/dataset/4302257e-5fa6-4c88-b8f7-f78730d8c48b/resource/"
    "afc6a8ca-dc55-4eb4-baf0-4afaa2c6673e/download/lka-rainfall-subnat-full.csv"
)
NASA_POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_POWER_MONTHLY_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
NINO34_URL = "https://psl.noaa.gov/data/correlation/nina34.data"
DMI_URL = "https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data"

NASA_PARAMETERS = ("T2M", "RH2M", "WS2M")
# Surface soil wetness (0 = dry, 1 = saturated) from NASA POWER, community AG. It stands in for the
# proposal's SMAP surface soil moisture, which needs an Earthdata login and has a different latency.
NASA_SOIL_PARAMETERS = ("GWETTOP",)
NASA_FILL_VALUE = -999.0


def http_get_text(url: str, params: Optional[dict] = None, timeout: float = 120.0) -> str:
    import httpx

    response = httpx.get(url, params=params, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.text


# ─── CHIRPS ────────────────────────────────────────────────────────────────

def chirps_monthly(chirps_csv_text: str) -> pd.DataFrame:
    """Aggregate HDX dekadal CHIRPS indicators to district-month features.

    Returns columns: pcode, year, month, rainfall_mm, r3h, rfq, dekads, preliminary.
    `preliminary` is True when any dekad of the month is still a preliminary estimate.
    """
    raw = pd.read_csv(io.StringIO(chirps_csv_text))
    raw = raw[raw["adm_level"] == 2].copy()
    raw["date"] = pd.to_datetime(raw["date"])
    raw["year"] = raw["date"].dt.year
    raw["month"] = raw["date"].dt.month
    raw["is_prelim"] = raw["version"].astype(str).str.lower().ne("final")
    grouped = raw.groupby(["PCODE", "year", "month"])
    monthly = pd.DataFrame({
        "rainfall_mm": grouped["rfh"].sum(min_count=1),
        "r3h": grouped["r3h"].mean(),
        "rfq": grouped["rfq"].mean(),
        "dekads": grouped["rfh"].count(),
        "preliminary": grouped["is_prelim"].any(),
    }).reset_index().rename(columns={"PCODE": "pcode"})
    # A month is only usable once all three dekads are published.
    return monthly[monthly["dekads"] == 3].reset_index(drop=True)


# ─── NASA POWER ────────────────────────────────────────────────────────────

def nasa_power_monthly_from_payload(payload: dict, parameters=NASA_PARAMETERS) -> pd.DataFrame:
    """Parse a NASA POWER *monthly* point payload into year, month and one column per parameter."""
    params = payload["properties"]["parameter"]
    rows = []
    for key, value in params[parameters[0]].items():
        month = int(key[4:])
        if month == 13:  # annual mean row
            continue
        row = {"year": int(key[:4]), "month": month}
        for p in parameters:
            v = params[p][key]
            row[p] = None if v == NASA_FILL_VALUE else v
        rows.append(row)
    return pd.DataFrame(rows).dropna()


def nasa_power_monthly_from_daily_payload(payload: dict, parameters=NASA_PARAMETERS) -> pd.DataFrame:
    """Aggregate a NASA POWER *daily* payload to monthly means, keeping complete months only."""
    params = payload["properties"]["parameter"]
    records = []
    for key in params[parameters[0]]:
        values = {p: params[p][key] for p in parameters}
        if any(v == NASA_FILL_VALUE for v in values.values()):
            continue
        records.append({"year": int(key[:4]), "month": int(key[4:6]), **values})
    if not records:
        return pd.DataFrame(columns=["year", "month", *parameters])
    daily = pd.DataFrame(records)
    grouped = daily.groupby(["year", "month"])
    monthly = grouped[list(parameters)].mean().round(2)
    monthly["days"] = grouped.size()
    monthly = monthly.reset_index()
    complete = monthly.apply(lambda r: r["days"] == calendar.monthrange(int(r.year), int(r.month))[1], axis=1)
    return monthly[complete].drop(columns="days").reset_index(drop=True)


def fetch_nasa_power(lat: float, lon: float, start: str, end: str, daily: bool, parameters=NASA_PARAMETERS) -> dict:
    import json

    url = NASA_POWER_DAILY_URL if daily else NASA_POWER_MONTHLY_URL
    params = {
        "parameters": ",".join(parameters),
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    return json.loads(http_get_text(url, params=params))


# ─── NOAA PSL indices ──────────────────────────────────────────────────────

def parse_psl_series(text: str) -> Dict[Tuple[int, int], float]:
    """Parse the NOAA PSL fixed-width monthly format into {(year, month): value}."""
    lines = text.splitlines()
    start, end = (int(x) for x in lines[0].split()[:2])
    series: Dict[Tuple[int, int], float] = {}
    for line in lines[1:]:
        parts = line.split()
        if len(parts) != 13 or not parts[0].isdigit():
            continue
        year = int(parts[0])
        if not start <= year <= end:
            continue
        for month, raw in enumerate(parts[1:], start=1):
            value = float(raw)
            if value > -99:  # -99.99 / -9999 are missing markers
                series[(year, month)] = value
    return series


def series_frame(series: Dict[Tuple[int, int], float], name: str, years: Iterable[int] = ()) -> pd.DataFrame:
    frame = pd.DataFrame(
        [{"year": y, "month": m, name: v} for (y, m), v in sorted(series.items())]
    )
    if years:
        frame = frame[frame["year"].isin(list(years))]
    return frame.reset_index(drop=True)
