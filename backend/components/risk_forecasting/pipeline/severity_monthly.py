"""
Monthly severity pipeline (Stage 2, district level) -- table, readiness gate and evaluation.

Pure functions: no database, no network, no writes. Input is what `pipeline.surveillance` already produces
(district x month observations from verified app records); output is a report dictionary.

What it does, month after month as data accumulates:
  1. keeps the district-months where the app can see the district (unknown is never treated as zero);
  2. builds (previous month -> this month) pairs for district-months with an outbreak (>= 1 case or death);
  3. checks the readiness gate (enough outbreak district-months, months and cases of each class);
  4. only when the gate is met: forward-chaining evaluation of a penalised ordinal model against baselines.

Outcomes: INSUFFICIENT_DATA, EVALUATED_NOT_BETTER, EVALUATED_BETTER. Nothing is deployed automatically.

Severity of an observed month is `cases + 10 x deaths` (LOW < 10, MEDIUM < 30, HIGH >= 30). These weights and
cut-offs are design choices, not clinically validated; they are the application's own definition.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from components.risk_forecasting.pipeline.surveillance import observed_severity
from components.risk_forecasting.services.forecast_v2_service import (
    STAGE2_MIN_DISTINCT_MONTHS, STAGE2_MIN_OUTBREAK_MONTHS)

CLASSES = ("LOW", "MEDIUM", "HIGH")
_BAND_TO_CLASS = {"LOW": "LOW", "MODERATE": "MEDIUM", "HIGH": "HIGH"}
MIN_PER_CLASS = 10
MIN_TRAIN_MONTHS = 3
PENALTIES = (0.03, 0.1, 0.3, 1.0)
K_SHRINK = 2.0

INSUFFICIENT = "INSUFFICIENT_DATA"
NOT_BETTER = "EVALUATED_NOT_BETTER"
BETTER = "EVALUATED_BETTER"


def prev_month(year: int, month: int) -> Tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def month_index(year: int, month: int) -> int:
    return year * 12 + month


def build_rows(observations: Dict[Tuple[int, int], dict]) -> Dict[Tuple[str, int, int], dict]:
    """(district, year, month) -> row, for district-months the app can see (cases and deaths known)."""
    rows = {}
    for (year, month), by_district in observations.items():
        for district, obs in by_district.items():
            cases, deaths = getattr(obs, "cases", None), getattr(obs, "deaths", None)
            if cases is None or deaths is None:
                continue                                    # not observed: unknown, never zero
            band = observed_severity(cases, deaths)
            outbreak = (cases + deaths) > 0
            rows[(district, year, month)] = {
                "district": district, "year": year, "month": month, "cases": cases, "deaths": deaths,
                "score": cases + 10 * deaths, "outbreak": outbreak,
                "severity": _BAND_TO_CLASS.get(band) if outbreak else None,
            }
    return rows


def training_pairs(rows: Dict[Tuple[str, int, int], dict]) -> List[dict]:
    """Outbreak district-months whose previous month was also observed: previous-month features -> this month's class."""
    pairs = []
    for (district, year, month), row in rows.items():
        if not row["outbreak"] or row["severity"] is None:
            continue
        previous = rows.get((district, *prev_month(year, month)))
        if previous is None:
            continue
        pairs.append({
            "district": district, "month_index": month_index(year, month), "y": CLASSES.index(row["severity"]),
            "x": [math.log1p(previous["cases"]), math.log1p(previous["deaths"]), 1.0 if previous["outbreak"] else 0.0],
            "prev_class": CLASSES.index(previous["severity"]) if previous["severity"] else None,
        })
    return sorted(pairs, key=lambda p: (p["month_index"], p["district"]))


def readiness(rows: Dict[Tuple[str, int, int], dict]) -> dict:
    outbreak_rows = [r for r in rows.values() if r["outbreak"] and r["severity"]]
    counts = {c: sum(1 for r in outbreak_rows if r["severity"] == c) for c in CLASSES}
    months = {month_index(r["year"], r["month"]) for r in outbreak_rows}
    checks = {
        "outbreak_district_months": (len(outbreak_rows), STAGE2_MIN_OUTBREAK_MONTHS),
        "distinct_months": (len(months), STAGE2_MIN_DISTINCT_MONTHS),
        **{f"{c.lower()}_district_months": (counts[c], MIN_PER_CLASS) for c in CLASSES},
    }
    return {"ready": all(have >= need for have, need in checks.values()), "class_counts": counts,
            "checks": {k: {"have": have, "need": need} for k, (have, need) in checks.items()}}


# ─── models ────────────────────────────────────────────────────────────────

def _national(train: List[dict]) -> np.ndarray:
    counts = np.array([sum(1 for p in train if p["y"] == c) for c in range(3)], float)
    return (counts + 1) / (counts.sum() + 3)


def _p_national(train, test):
    return np.tile(_national(train), (len(test), 1))


def _p_persistence(train, test):
    nat = _national(train)
    out = []
    for p in test:
        onehot = np.zeros(3)
        if p["prev_class"] is not None:
            onehot[p["prev_class"]] = 1.0
            out.append((onehot + K_SHRINK * nat) / (1 + K_SHRINK))
        else:
            out.append(nat)
    return np.array(out)


def _p_district_history(train, test):
    nat = _national(train)
    out = []
    for p in test:
        counts = np.array([sum(1 for t in train if t["district"] == p["district"] and t["y"] == c) for c in range(3)], float)
        out.append((counts + K_SHRINK * nat) / (counts.sum() + K_SHRINK))
    return np.array(out)


def _design(train, test):
    xtr, xte = np.array([p["x"] for p in train]), np.array([p["x"] for p in test])
    mu, sd = xtr.mean(axis=0), xtr.std(axis=0)
    sd[sd == 0] = 1.0
    return (xtr - mu) / sd, (xte - mu) / sd


def _fit_ordinal(x, y, lam):
    k = x.shape[1]

    def nll(w):
        b, t1, t2 = w[:k], w[k], w[k] + math.exp(w[k + 1])
        eta = x @ b
        c1, c2 = expit(t1 - eta), expit(t2 - eta)
        p = np.where(y == 0, c1, np.where(y == 1, c2 - c1, 1 - c2))
        return -np.log(np.clip(p, 1e-9, None)).sum() + lam * (b @ b)

    w0 = np.zeros(k + 2)
    w0[k] = -0.5
    w = minimize(nll, w0, method="L-BFGS-B").x
    return w[:k], w[k], w[k] + math.exp(w[k + 1])


def _p_ordinal_fixed(train, test, lam):
    xtr, xte = _design(train, test)
    b, t1, t2 = _fit_ordinal(xtr, np.array([p["y"] for p in train]), lam)
    eta = xte @ b
    c1, c2 = expit(t1 - eta), expit(t2 - eta)
    return np.column_stack([c1, c2 - c1, 1 - c2])


def _p_ordinal(train, test):
    months = sorted({p["month_index"] for p in train})
    best, best_score = PENALTIES[len(PENALTIES) // 2], math.inf
    if len(months) >= 3:
        for lam in PENALTIES:
            scores = []
            for m in months[1:]:
                tr, te = [p for p in train if p["month_index"] < m], [p for p in train if p["month_index"] == m]
                if len(tr) >= 8 and len({p["y"] for p in tr}) >= 2 and te:
                    scores.append(_rps(_p_ordinal_fixed(tr, te, lam), np.array([p["y"] for p in te])).mean())
            if scores and np.mean(scores) < best_score:
                best, best_score = lam, float(np.mean(scores))
    return _p_ordinal_fixed(train, test, best)


MODELS = {"national": _p_national, "persistence": _p_persistence, "district_history": _p_district_history, "ordinal": _p_ordinal}
BASELINES = ("national", "persistence", "district_history")


def _rps(prob, y):
    cum_p = np.cumsum(prob, axis=1)[:, :2]
    cum_o = np.column_stack([(y <= 0).astype(float), (y <= 1).astype(float)])
    return ((cum_p - cum_o) ** 2).sum(axis=1) / 2


def _balanced_accuracy(y, pred):
    recalls = [float((pred[y == c] == c).mean()) for c in range(3) if (y == c).any()]
    return float(np.mean(recalls)) if recalls else 0.0


def _reliability_ok(prob, y):
    """Predicted probability of >= MEDIUM should not be observed less often in its top half than in its bottom half."""
    p = prob[:, 1:].sum(axis=1)
    observed = (y >= 1).astype(float)
    order = np.argsort(p)
    half = len(order) // 2
    if half == 0:
        return True
    return observed[order[half:]].mean() >= observed[order[:half]].mean()


def evaluate(pairs: List[dict]) -> Optional[dict]:
    """Forward chaining by month: train on earlier months, test on the month."""
    months = sorted({p["month_index"] for p in pairs})
    results = {name: [] for name in MODELS}
    test_y, test_month = [], []
    for i, m in enumerate(months):
        train = [p for p in pairs if p["month_index"] < m]
        test = [p for p in pairs if p["month_index"] == m]
        if i < MIN_TRAIN_MONTHS or len(train) < 15 or len({p["y"] for p in train}) < 2:
            continue
        for name, fn in MODELS.items():
            results[name].append(fn(train, test))
        test_y += [p["y"] for p in test]
        test_month += [m] * len(test)
    if not test_y:
        return None
    y, mon = np.array(test_y), np.array(test_month)
    summary = {}
    for name, blocks in results.items():
        prob = np.vstack(blocks)
        rps = _rps(prob, y)
        pred = prob.argmax(axis=1)
        summary[name] = {"rps": round(float(rps.mean()), 4), "ordinal_mae": round(float(np.abs(pred - y).mean()), 4),
                         "balanced_accuracy": round(_balanced_accuracy(y, pred), 4), "reliability_ok": _reliability_ok(prob, y),
                         "per_month_rps": {int(m): float(rps[mon == m].mean()) for m in sorted(set(mon))}}
    best = min(BASELINES, key=lambda n: summary[n]["rps"])
    model = summary["ordinal"]
    months_better = sum(model["per_month_rps"][m] < summary[best]["per_month_rps"][m] for m in model["per_month_rps"])
    rule = {
        "rps_below_every_baseline": all(model["rps"] < summary[n]["rps"] for n in BASELINES),
        "ordinal_mae_not_above_best_baseline": model["ordinal_mae"] <= summary[best]["ordinal_mae"],
        "better_than_best_baseline_in_most_months": months_better > len(model["per_month_rps"]) / 2,
        "no_calibration_reversal": model["reliability_ok"],
    }
    for s in summary.values():
        s["per_month_rps"] = {k: round(v, 4) for k, v in s["per_month_rps"].items()}
    return {"n_test": int(len(y)), "test_months": len(set(mon)), "best_baseline": best, "models": summary,
            "decision_rule": rule, "all_met": all(rule.values())}


def run(observations: Dict[Tuple[int, int], dict], disease: str, synthetic: bool = False) -> dict:
    rows = build_rows(observations)
    gate = readiness(rows)
    pairs = training_pairs(rows)
    report = {"disease": disease, "synthetic": synthetic, "months_read": len(observations),
              "observed_district_months": len(rows), "training_pairs": len(pairs), "readiness": gate,
              "definition": "severity of an outbreak district-month = cases + 10 x deaths (LOW < 10, MEDIUM < 30, HIGH >= 30); "
                            "design choice, not clinically validated"}
    if not gate["ready"]:
        report.update(state=INSUFFICIENT, evaluation=None,
                      message="Not enough monthly counts yet; the application shows the historical severity pattern.")
        return report
    evaluation = evaluate(pairs)
    report["evaluation"] = evaluation
    if evaluation is None:
        report.update(state=INSUFFICIENT, message="Too few consecutive months to evaluate; the historical pattern is shown.")
    elif evaluation["all_met"]:
        report.update(state=BETTER, message="The model beat every baseline under the decision rule. Issuing it needs a separate approval.")
    else:
        report.update(state=NOT_BETTER, message="The model did not beat the baselines; the historical pattern is shown.")
    return report
