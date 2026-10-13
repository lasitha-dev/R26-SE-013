"""
Build the v2 training datasets (FMD, LSD) from public sources with the shared feature builder.

Usage (from backend/):  python components/risk_forecasting/model/scripts/v2/build_dataset.py

Downloads are cached in model/data/cache/ (git-ignored). Outputs:
  model/data/cache/v2_FMD_dataset.csv, model/data/cache/v2_LSD_dataset.csv
The script also cross-checks v2 features against the curated v1 datasets, which
were built from the same sources, and fails loudly if they disagree.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(BACKEND_DIR))

from components.risk_forecasting.pipeline import sources as src  # noqa: E402
from components.risk_forecasting.pipeline.features import (  # noqa: E402
    ALL_FEATURES, FeatureSources, build_features, nino_anomalies,
)
from components.risk_forecasting.pipeline.geography import DISTRICTS  # noqa: E402
from components.risk_forecasting.pipeline.labels import LABEL_YEARS, load_labels  # noqa: E402

MODEL_DIR = BACKEND_DIR / "components" / "risk_forecasting" / "model"
PROCESSED = MODEL_DIR / "data" / "processed"
CACHE = MODEL_DIR / "data" / "cache"
V1 = {"FMD": PROCESSED / "FMD_dataset_with_spatial_and_climate_indices.csv",
      "LSD": PROCESSED / "LSD_dataset_with_spatial_and_climate_indices.csv"}


def cached_text(name, fetch):
    path = CACHE / name
    if not path.exists():
        path.write_text(fetch(), encoding="utf-8")
        time.sleep(0.5)
    return path.read_text(encoding="utf-8")


def load_sources(first_year, last_year):
    CACHE.mkdir(parents=True, exist_ok=True)
    chirps = src.chirps_monthly(cached_text("chirps_lka_subnat_full.csv", lambda: src.http_get_text(src.CHIRPS_URL)))
    rain = {(r.pcode, int(r.year), int(r.month)): {"rainfall_mm": r.rainfall_mm, "r3h": r.r3h, "rfq": r.rfq}
            for r in chirps.itertuples(index=False)}

    weather = {}
    for district, info in DISTRICTS.items():
        name = f"nasa_power_monthly_{info['pcode']}_{first_year - 1}_{last_year}.json"
        fetch = lambda i=info: json.dumps(src.fetch_nasa_power(  # noqa: E731
            i["lat"], i["lon"], str(first_year - 1), str(last_year), daily=False))
        payload = json.loads(cached_text(name, fetch))
        for r in src.nasa_power_monthly_from_payload(payload).itertuples(index=False):
            weather[(district, int(r.year), int(r.month))] = {"T2M": r.T2M, "RH2M": r.RH2M, "WS2M": r.WS2M}

    nino = src.parse_psl_series(cached_text("nina34.data", lambda: src.http_get_text(src.NINO34_URL)))

    v1 = pd.read_csv(V1["FMD"])
    density = {}
    for (district, year), g in v1.groupby(["district", "year"]):
        density.setdefault(district, []).append((int(year), float(g.buffalo_density.iloc[0]), float(g.livestock_density.iloc[0])))
    return rain, weather, nino_anomalies(nino), density


def build(disease, rain, weather, nino_anom, density):
    labels = load_labels(disease, V1[disease])
    sources = FeatureSources(rain=rain, weather=weather, nino_anomaly=nino_anom, density=density,
                             surveillance=lambda d, y, m: labels.get((d, y, m)))
    rows = []
    for (district, year, month), status in sorted(labels.items()):
        feats, missing = build_features(district, year, month, sources)
        rows.append({"district": district, "year": year, "month": month, "outbreak": status,
                     "n_missing": len(missing), **feats})
    return pd.DataFrame(rows)


def cross_check(disease, v2):
    """v2 lag features must equal the corresponding v1 columns (same sources, same rules)."""
    v1 = pd.read_csv(V1[disease]).drop(columns=["month"], errors="ignore").rename(columns={"month_num": "month"})
    m = v2.merge(v1, on=["district", "year", "month"], how="inner")
    checks = {
        "rain_t1": "rain_lag1", "rain_t2": "rain_lag2", "rfq_t1": "rfq_lag1",
        "humidity_t1": "humidity_lag1", "wind_t1": "wind_lag1", "temp_t1": "temp_lag1",
        "neighbour_fraction_t1": "neighbor_outbreak_fraction_lag1",
        "neighbour_count_t1": "neighbor_outbreak_count_lag1",
        "neighbour_fraction_t2": "neighbor_outbreak_lag2",
    }
    report = {}
    first_index = m["year"].min() * 12  # January of the first panel year
    for new, old in checks.items():
        lag = 2 if new.endswith("_t2") else 1
        x = m[[new, old]].dropna()
        # Skip months whose lag falls before the v1 panel start: v1 imputed those lags.
        idx = m.loc[x.index, "year"] * 12 + m.loc[x.index, "month"] - 1
        x = x[idx - lag >= first_index]
        pct = float(np.mean(np.isclose(x[new], x[old], atol=1e-3)) * 100) if len(x) else float("nan")
        report[new] = round(pct, 2)
    return report


def main():
    first = min(min(r) for r in LABEL_YEARS.values())
    last = max(max(r) for r in LABEL_YEARS.values())
    rain, weather, nino_anom, density = load_sources(first, last)
    for disease in ("FMD", "LSD"):
        v2 = build(disease, rain, weather, nino_anom, density)
        out = CACHE / f"v2_{disease}_dataset.csv"
        v2.to_csv(out, index=False)
        print(f"{disease}: {len(v2)} rows, {int(v2.outbreak.sum())} outbreaks, "
              f"years {v2.year.min()}-{v2.year.max()} -> {out.name}")
        print("   rows with all features:", int((v2.n_missing == 0).sum()))
        report = cross_check(disease, v2)
        print("   v1 cross-check (% equal):", report)
        bad = {k: v for k, v in report.items() if v < 99.5}
        if bad:
            raise SystemExit(f"Cross-check failed for {disease}: {bad}")
    print("feature columns:", ALL_FEATURES)


if __name__ == "__main__":
    main()
