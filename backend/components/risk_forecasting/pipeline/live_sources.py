"""
Assemble FeatureSources for operational forecasts from the public sources.

Weather for a month is aggregated from NASA POWER *daily* values (identical to the
monthly product, published ~4 days after the month ends). Downloads are cached on disk
in model/data/cache/live/ so repeated forecasts do not re-query the APIs.
"""

from __future__ import annotations

import calendar
import json
import logging
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple

import pandas as pd

from components.risk_forecasting.pipeline import sources as src
from components.risk_forecasting.pipeline.features import FeatureSources, nino_anomalies, shift
from components.risk_forecasting.pipeline.geography import DISTRICTS

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parents[1] / "model"
LIVE_CACHE = MODEL_DIR / "data" / "cache" / "live"
DENSITY_SOURCE = MODEL_DIR / "data" / "processed" / "FMD_dataset_with_spatial_and_climate_indices.csv"
INDEX_TTL_SECONDS = 12 * 3600


class PublicDataCache:
    def __init__(self, directory: Path = LIVE_CACHE, fetch_text: Callable = src.http_get_text,
                 fetch_power: Callable = src.fetch_nasa_power, now: Callable[[], float] = time.time):
        self.directory = directory
        self.fetch_text = fetch_text
        self.fetch_power = fetch_power
        self.now = now

    def _read(self, name: str, ttl: Optional[float]):
        path = self.directory / name
        if path.exists() and (ttl is None or self.now() - path.stat().st_mtime < ttl):
            return path.read_text(encoding="utf-8")
        return None

    def _write(self, name: str, text: str) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / name).write_text(text, encoding="utf-8")
        return text

    def text(self, name: str, url: str, ttl: Optional[float] = INDEX_TTL_SECONDS) -> str:
        cached = self._read(name, ttl)
        return cached if cached is not None else self._write(name, self.fetch_text(url))

    def weather_month(self, district: str, year: int, month: int) -> Optional[dict]:
        info = DISTRICTS[district]
        name = f"power_daily_{info['pcode']}_{year}{month:02d}.json"
        cached = self._read(name, ttl=None)
        if cached is None:
            last = calendar.monthrange(year, month)[1]
            payload = self.fetch_power(info["lat"], info["lon"], f"{year}{month:02d}01",
                                       f"{year}{month:02d}{last:02d}", daily=True)
            monthly = src.nasa_power_monthly_from_daily_payload(payload)
            if monthly.empty:
                return None  # month not complete yet: do not cache
            cached = self._write(name, json.dumps(payload))
        monthly = src.nasa_power_monthly_from_daily_payload(json.loads(cached))
        row = monthly[(monthly.year == year) & (monthly.month == month)]
        if row.empty:
            return None
        r = row.iloc[0]
        return {"T2M": float(r.T2M), "RH2M": float(r.RH2M), "WS2M": float(r.WS2M)}


def load_density(path: Path = DENSITY_SOURCE) -> Dict[str, list]:
    frame = pd.read_csv(path, usecols=["district", "year", "buffalo_density", "livestock_density"])
    density: Dict[str, list] = {}
    for (district, year), g in frame.groupby(["district", "year"]):
        density.setdefault(district, []).append(
            (int(year), float(g.buffalo_density.iloc[0]), float(g.livestock_density.iloc[0])))
    return density


def build_live_sources(targets: Iterable[Tuple[int, int]], surveillance, cache: Optional[PublicDataCache] = None,
                       density: Optional[Dict[str, list]] = None) -> Tuple[FeatureSources, Dict[str, str]]:
    """Gather inputs needed for the given target months. Returns (sources, source_notes).
    Any source that cannot be fetched is reported in source_notes and left empty, so the
    affected features become missing (never zero)."""
    cache = cache or PublicDataCache()
    notes: Dict[str, str] = {}

    rain: Dict[tuple, dict] = {}
    try:
        monthly = src.chirps_monthly(cache.text("chirps_lka_subnat_full.csv", src.CHIRPS_URL))
        rain = {(r.pcode, int(r.year), int(r.month)): {"rainfall_mm": r.rainfall_mm, "r3h": r.r3h, "rfq": r.rfq,
                                                       "preliminary": bool(r.preliminary)}
                for r in monthly.itertuples(index=False)}
        notes["rainfall"] = "CHIRPS (WFP/HDX)"
    except Exception as exc:
        logger.error("CHIRPS unavailable: %s", exc)
        notes["rainfall"] = "UNAVAILABLE"

    nino_anomaly: Dict[tuple, float] = {}
    try:
        nino_anomaly = nino_anomalies(src.parse_psl_series(cache.text("nina34.data", src.NINO34_URL)))
        notes["enso"] = "NOAA PSL Nino 3.4"
    except Exception as exc:
        logger.error("Nino 3.4 unavailable: %s", exc)
        notes["enso"] = "UNAVAILABLE"

    weather: Dict[tuple, dict] = {}
    weather_failures = 0
    for target in set(targets):
        y, m = shift(target, -1)
        for district in DISTRICTS:
            try:
                value = cache.weather_month(district, y, m)
            except Exception as exc:
                logger.error("NASA POWER unavailable for %s %d-%02d: %s", district, y, m, exc)
                value = None
            if value is None:
                weather_failures += 1
            else:
                weather[(district, y, m)] = value
    notes["weather"] = "NASA POWER daily" + (f" ({weather_failures} district-months unavailable)" if weather_failures else "")

    sources = FeatureSources(
        rain=rain,
        weather=weather,
        nino_anomaly=nino_anomaly,
        density=density if density is not None else load_density(),
        surveillance=surveillance.status,
        notes=notes,
    )
    return sources, notes
