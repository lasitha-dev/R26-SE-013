"""Counterfactual test: does the forecast change when last month's verified cases appear?

Read-only. ForecastV2Service.forecast_period() computes forecasts and persists nothing; the surveillance
provider below is synthetic, so the database is never read or written. Climate inputs come from the
public-data cache (network on first run). The numbers are a what-if on synthetic cases, not a forecast.
Run from the backend directory:  python components/risk_forecasting/model/scripts/v2/counterfactual_cases_test.py
"""
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from components.risk_forecasting.pipeline.geography import ADJACENCY, DISTRICT_NAMES
from components.risk_forecasting.pipeline.surveillance import DistrictObservation, SurveillanceProvider
from components.risk_forecasting.services.forecast_v2_service import ForecastV2Service

TARGET = (2026, 10)          # last month = September 2026, the month before = August 2026
YEAR, MONTH = TARGET


@dataclass
class FakeSurveillance(SurveillanceProvider):
    """Every district in `known` has a recorded status; the rest are unknown (no surveillance coverage)."""
    known: frozenset = frozenset()
    positive: frozenset = frozenset()
    cases: int = 3

    def month(self, year, month):
        out = {}
        for d in DISTRICT_NAMES:
            if d not in self.known:
                out[d] = DistrictObservation("SOURCE_UNAVAILABLE", "SYNTHETIC")
            elif d in self.positive and (year, month) == (2026, 9):
                out[d] = DistrictObservation("CONFIRMED_OUTBREAK", "SYNTHETIC", cases=self.cases, deaths=0)
            else:
                out[d] = DistrictObservation("NO_REPORTED_CASES", "SYNTHETIC", cases=0, deaths=0)
        return out


class Service(ForecastV2Service):
    scenario = None

    def _surveillance(self, disease):
        return FakeSurveillance(disease, {}, None, **self.scenario)


def run(disease, district, known_mode, cases):
    if known_mode == "all known":
        known = frozenset(DISTRICT_NAMES)
    else:                                   # the district itself only; its neighbours unknown
        known = frozenset({district})
    results = {}
    for label, positive in (("no cases", frozenset()), (f"{cases} cases", frozenset({district}))):
        svc = Service(repository_getter=lambda: None)
        svc.scenario = {"known": known, "positive": positive, "cases": cases}
        records = svc.forecast_period(YEAR, MONTH, diseases=(disease,))
        results[label] = {r.district: r for r in records}
    return results


def show(disease, district, known_mode, cases=3):
    res = run(disease, district, known_mode, cases)
    print(f"\n=== {disease} | {district} | surveillance: {known_mode} | target {YEAR}-{MONTH:02d} ===")
    keys = list(res)
    print(f"{'':28}{keys[0]:>14}{keys[1]:>14}")
    a, b = res[keys[0]][district], res[keys[1]][district]
    rows = (
        ("forecaster", a.forecaster, b.forecaster),
        ("probability %", a.probability_pct, b.probability_pct),
        ("usual rate %", round(a.baseline_probability * 100, 1), round(b.baseline_probability * 100, 1)),
        ("times the usual rate", a.relative_risk, b.relative_risk),
        ("risk tier", a.risk_level, b.risk_level),
        ("input quality", a.input_quality, b.input_quality),
    )
    for name, x, y in rows:
        print(f"{name:28}{str(x):>14}{str(y):>14}")
    moved = [(d, res[keys[0]][d].probability_pct, res[keys[1]][d].probability_pct) for d in ADJACENCY[district]
             if res[keys[0]][d].probability_pct != res[keys[1]][d].probability_pct]
    print("neighbours that changed:", moved or "none")
    others = [d for d in DISTRICT_NAMES if d != district and d not in ADJACENCY[district]
              and res[keys[0]][d].probability_pct != res[keys[1]][d].probability_pct]
    print("other districts that changed:", others or "none")
    if a.missing_inputs:
        print("missing inputs:", a.missing_inputs)


if __name__ == "__main__":
    for args in (("LSD", "Gampaha", "all known"), ("LSD", "Gampaha", "district only"),
                 ("FMD", "Colombo", "all known"), ("FMD", "Colombo", "district only")):
        show(*args)
