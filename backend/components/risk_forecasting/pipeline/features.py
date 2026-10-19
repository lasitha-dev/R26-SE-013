"""
Shared, availability-aware feature builder for the v2 forecasting models.

The SAME function (`build_features`) is used to build the training dataset and
to build production inputs, so training/serving definitions cannot drift.

Timing contract (decision D-3): a forecast for target month t is issued on day 5
of month t using only information published by then:
  - CHIRPS preliminary dekads and NASA POWER daily data for t-1 (and earlier);
  - Nino 3.4 for t-2 and t-3 (PSL publishes month t-1 about two weeks into t);
  - outbreak surveillance status for t-1 and t-2.
No same-month (t) observation is used. Unknown values stay unknown (None);
they are never replaced by 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from components.risk_forecasting.pipeline.geography import ADJACENCY, DISTRICTS

Period = Tuple[int, int]

SEASONAL_FEATURES = [
    "sin_month", "cos_month",
    "monsoon_first_inter", "monsoon_sw", "monsoon_second_inter", "monsoon_ne",
]
CLIMATE_FEATURES = [
    "rain_t1", "rain_t2", "r3h_t1", "rfq_t1",
    "temp_t1", "humidity_t1", "wind_t1", "soil_top_t1",
    "nino34_anom_t2", "nino34_anom_t3",
]
HOST_FEATURES = ["buffalo_density", "livestock_density"]
SURVEILLANCE_FEATURES = ["own_t1", "own_t2", "neighbour_fraction_t1", "neighbour_count_t1", "neighbour_fraction_t2"]

BASE_FEATURES = SEASONAL_FEATURES + CLIMATE_FEATURES + HOST_FEATURES
ALL_FEATURES = BASE_FEATURES + SURVEILLANCE_FEATURES


def shift(period: Period, months: int) -> Period:
    # A linear month index handles year boundaries (January - 1 = last December).
    index = period[0] * 12 + (period[1] - 1) + months
    return index // 12, index % 12 + 1


def monsoon_flags(month: int) -> Dict[str, int]:
    return {
        "monsoon_first_inter": int(month in (3, 4)),
        "monsoon_sw": int(month in (5, 6, 7, 8, 9)),
        "monsoon_second_inter": int(month in (10, 11)),
        "monsoon_ne": int(month in (12, 1, 2)),
    }


def nino_anomalies(series: Dict[Period, float], base_years=range(1991, 2021)) -> Dict[Period, float]:
    """Nino 3.4 anomalies against the 1991-2020 monthly climatology (WMO standard normal)."""
    climatology = {}
    for month in range(1, 13):
        values = [v for (y, m), v in series.items() if m == month and y in base_years]
        if values:
            climatology[month] = sum(values) / len(values)
    return {(y, m): round(v - climatology[m], 4) for (y, m), v in series.items() if m in climatology}


@dataclass
class FeatureSources:
    """Inputs for the feature builder. Every lookup returns None when unknown."""
    rain: Dict[Tuple[str, int, int], dict]              # (pcode, year, month) -> {rainfall_mm, r3h, rfq}
    weather: Dict[Tuple[str, int, int], dict]           # (district, year, month) -> {T2M, RH2M, WS2M, GWETTOP}
    nino_anomaly: Dict[Period, float]                   # (year, month) -> anomaly
    density: Dict[str, List[Tuple[int, float, float]]]  # district -> [(year, buffalo, livestock)]
    surveillance: Callable[[str, int, int], Optional[int]]  # (district, year, month) -> 0/1/None
    notes: Dict[str, str] = field(default_factory=dict)


def _density(sources: FeatureSources, district: str, year: int):
    # Use the latest density entry at or before the target year, never a later one.
    rows = [r for r in sources.density.get(district, []) if r[0] <= year]
    if not rows:
        return None, None
    _, buffalo, livestock = max(rows, key=lambda r: r[0])
    return buffalo, livestock


def _neighbour_status(sources: FeatureSources, district: str, period: Period):
    # A missing neighbor observation makes the aggregate unknown; treating it as
    # zero would make incomplete surveillance look like lower outbreak activity.
    statuses = [sources.surveillance(n, *period) for n in ADJACENCY[district]]
    if any(s is None for s in statuses):
        return None, None
    count = sum(statuses)
    return count / len(statuses), count


def build_features(district: str, year: int, month: int, sources: FeatureSources):
    """Build the v2 feature dict for one district and target month.

    Returns (features, missing): `features` maps every name in ALL_FEATURES to a
    float or None; `missing` lists the names whose inputs were unavailable.
    """
    target = (year, month)
    # t1/t2/t3 mean one/two/three months before the target. These lags prevent
    # target-month observations from leaking into their own forecast inputs.
    t1, t2, t3 = shift(target, -1), shift(target, -2), shift(target, -3)
    pcode = DISTRICTS[district]["pcode"]

    # Sine/cosine encode the annual cycle smoothly, keeping December near January.
    f: Dict[str, Optional[float]] = {
        "sin_month": math.sin(2 * math.pi * month / 12),
        "cos_month": math.cos(2 * math.pi * month / 12),
        **monsoon_flags(month),
    }

    rain1 = sources.rain.get((pcode, *t1))
    rain2 = sources.rain.get((pcode, *t2))
    f["rain_t1"] = rain1["rainfall_mm"] if rain1 else None
    f["rain_t2"] = rain2["rainfall_mm"] if rain2 else None
    f["r3h_t1"] = rain1["r3h"] if rain1 else None
    f["rfq_t1"] = rain1["rfq"] if rain1 else None

    w1 = sources.weather.get((district, *t1))
    f["temp_t1"] = w1["T2M"] if w1 else None
    f["humidity_t1"] = w1["RH2M"] if w1 else None
    f["wind_t1"] = w1["WS2M"] if w1 else None
    f["soil_top_t1"] = w1.get("GWETTOP") if w1 else None   # surface soil wetness, 0-1

    f["nino34_anom_t2"] = sources.nino_anomaly.get(t2)
    f["nino34_anom_t3"] = sources.nino_anomaly.get(t3)

    f["buffalo_density"], f["livestock_density"] = _density(sources, district, year)

    own1 = sources.surveillance(district, *t1)
    own2 = sources.surveillance(district, *t2)
    f["own_t1"] = float(own1) if own1 is not None else None
    f["own_t2"] = float(own2) if own2 is not None else None
    f["neighbour_fraction_t1"], f["neighbour_count_t1"] = _neighbour_status(sources, district, t1)
    f["neighbour_fraction_t2"], _ = _neighbour_status(sources, district, t2)

    # Report missingness as well as values so model selection can use a supported
    # fallback and the saved forecast can explain which inputs were unavailable.
    missing = [name for name in ALL_FEATURES if f.get(name) is None]
    return f, missing
