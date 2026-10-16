"""
v2 predictor: applies the JSON model artifacts produced by scripts/v2/train_evaluate.py.

The deployment table in each artifact decides the forecaster:
  surveillance known   -> artifact["deployment"]["surveillance_known"]
  surveillance unknown -> artifact["deployment"]["surveillance_unknown"]
where a forecaster is a logistic-regression variant ("A", "S", "B") or "climatology".
Inference is a dot product, so it does not depend on the scikit-learn version.

Risk tiers are based on relative risk (probability / district-month climatology),
because absolute probabilities are low for rare events:
  HIGH   relative risk >= 4, or probability >= 0.5
  MEDIUM relative risk >= 2  (the model card's "elevated" alert)
  LOW    otherwise
These cut-offs are design choices, not tuned on outcomes.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from components.risk_forecasting.pipeline.features import SURVEILLANCE_FEATURES

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "model" / "models" / "v2"
HIGH_RELATIVE_RISK = 4.0
MEDIUM_RELATIVE_RISK = 2.0
HIGH_PROBABILITY = 0.5


def _logit(p: float) -> float:
    p = min(max(p, 1e-3), 1 - 1e-3)
    return math.log(p / (1 - p))


def risk_tier(probability: float, relative_risk: float) -> str:
    if relative_risk >= HIGH_RELATIVE_RISK or probability >= HIGH_PROBABILITY:
        return "HIGH"
    if relative_risk >= MEDIUM_RELATIVE_RISK:
        return "MEDIUM"
    return "LOW"


@dataclass
class Prediction:
    probability: float
    baseline_probability: float
    relative_risk: float
    risk_level: str
    forecaster: str
    deployment_status: str
    model_version: str
    contributions: List[Dict[str, float]]
    probability_low: Optional[float] = None
    probability_high: Optional[float] = None
    interval_level: Optional[float] = None


class V2Predictor:
    def __init__(self, artifact: dict):
        self.artifact = artifact
        self.disease = artifact["disease"]
        self.model_version = artifact["model_version"]
        self.climatology = artifact["climatology"]

    @classmethod
    def load(cls, disease: str, directory: Path = ARTIFACT_DIR) -> "V2Predictor":
        path = directory / f"{disease.lower()}_v2.json"
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def baseline(self, district: str, month: int) -> float:
        table = self.climatology
        return table["district_month"].get(
            f"{district}|{month}", table["national_month"].get(str(month), table["overall"]))

    def baseline_interval(self, district: str, month: int) -> Optional[List[float]]:
        intervals = self.climatology.get("intervals")
        if not intervals:
            return None
        return (intervals["district_month"].get(f"{district}|{month}")
                or intervals["national_month"].get(str(month)) or intervals["overall"])

    @staticmethod
    def surveillance_known(features: Dict[str, Optional[float]]) -> bool:
        return all(features.get(name) is not None for name in SURVEILLANCE_FEATURES)

    @staticmethod
    def own_known(features: Dict[str, Optional[float]]) -> bool:
        """The district's own last two months are known although a neighbour's may not be."""
        return features.get("own_t1") is not None and features.get("own_t2") is not None

    def choose(self, features: Dict[str, Optional[float]]) -> dict:
        deployment = self.artifact["deployment"]
        if self.surveillance_known(features):
            key = "surveillance_known"
        elif self.own_known(features) and "own_known" in deployment:
            key = "own_known"
        else:
            key = "surveillance_unknown"
        choice = dict(deployment[key])
        if choice["forecaster"] != "climatology":
            variant = self.artifact["variants"][choice["forecaster"]]
            if any(features.get(f) is None for f in variant["features"]):
                # Required inputs (e.g. rainfall not yet published) are missing.
                return {"forecaster": "climatology", "C": None, "status": "baseline"}
        return choice

    def predict(self, district: str, month: int, features: Dict[str, Optional[float]]) -> Prediction:
        base = self.baseline(district, month)
        choice = self.choose(features)
        contributions: List[Dict[str, float]] = []
        low = high = level = None
        if choice["forecaster"] == "climatology":
            probability = base
            interval = self.baseline_interval(district, month)
            if interval:
                low, high, level = interval[0], interval[1], self.climatology["intervals"]["level"]
        else:
            variant = self.artifact["variants"][choice["forecaster"]]
            z = variant["intercept"]
            names = list(variant["features"])
            scaled_values = []
            for i, name in enumerate(names):
                scaled = (features[name] - variant["scaler_mean"][i]) / variant["scaler_std"][i]
                scaled_values.append(scaled)
                term = variant["coef"][i] * scaled
                contributions.append({"feature": name, "value": features[name], "contribution_log_odds": term})
                z += term
            if variant["uses_climatology_prior"]:
                term = variant["coef"][len(names)] * _logit(base)
                contributions.append({"feature": "climatology_logit", "value": base, "contribution_log_odds": term})
                z += term
            probability = 1 / (1 + math.exp(-z))
            replicates = (variant.get("interval") or {}).get("replicates")
            if replicates:
                inputs = scaled_values + ([_logit(base)] if variant["uses_climatology_prior"] else [])
                draws = sorted(1 / (1 + math.exp(-(r[0] + sum(c * v for c, v in zip(r[1:], inputs))))) for r in replicates)
                tail = (1 - variant["interval"]["level"]) / 2
                low = draws[int(math.floor(tail * (len(draws) - 1)))]
                high = draws[int(math.ceil((1 - tail) * (len(draws) - 1)))]
                level = variant["interval"]["level"]
        relative = probability / base if base > 0 else 0.0
        contributions.sort(key=lambda c: abs(c["contribution_log_odds"]), reverse=True)
        return Prediction(
            probability=probability,
            baseline_probability=base,
            relative_risk=relative,
            risk_level=risk_tier(probability, relative),
            forecaster=choice["forecaster"],
            deployment_status=choice["status"],
            model_version=self.model_version,
            contributions=[{**c, "contribution_log_odds": round(c["contribution_log_odds"], 4)} for c in contributions[:6]],
            probability_low=low, probability_high=high, interval_level=level,
        )
