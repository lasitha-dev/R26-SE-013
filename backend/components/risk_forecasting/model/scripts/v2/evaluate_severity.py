"""Stage 2 (severity) re-evaluation against honest baselines.

Question answered: does any model predict the annual severity class of an outbreak district-year better than
simple baselines that use no weather at all? Labels are ANNUAL district-year aggregates (DAPH), not monthly.

Reads only files under model/data/processed and writes only docs/v2/severity_evaluation.json.
Run from the model directory:  python scripts/v2/evaluate_severity.py
"""
import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
MODEL_DIR = Path(__file__).resolve().parents[2]
PROCESSED = MODEL_DIR / "data" / "processed"
OUT = MODEL_DIR / "docs" / "v2" / "severity_evaluation.json"

ORD = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
STATIC = ["lat", "lon", "buffalo_density", "livestock_density"]
WEATHER = ["rainfall_mm", "rfq", "rain_lag1", "humidity", "wind_speed", "temp_lag1", "humidity_lag1"]
FEATURES = STATIC + WEATHER
BOOTSTRAPS = 2000

DISEASES = {
    "FMD": {"labels": "severity_labels.csv", "features": "FMD_dataset_with_spatial_and_climate_indices.csv",
            "rename": {"District": "district", "Year": "year"}},
    "LSD": {"labels": "LSD_severity_labels.csv", "features": "LSD_dataset_with_spatial_and_climate_indices.csv", "rename": {}},
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_units(disease):
    cfg = DISEASES[disease]
    lab = pd.read_csv(PROCESSED / cfg["labels"]).rename(columns=cfg["rename"])
    feat = pd.read_csv(PROCESSED / cfg["features"])
    lab["y"] = lab["severity_class"].map(ORD)
    lab["logscore"] = np.log1p(lab["severity_score"])
    outbreak_weather = feat[feat["Outbreak status"] == 1].groupby(["district", "year"])[WEATHER].mean().reset_index()
    static = feat.groupby("district")[STATIC].first().reset_index()
    units = lab.merge(static, on="district", how="left").merge(outbreak_weather, on=["district", "year"], how="left")
    units[WEATHER] = units.groupby("district")[WEATHER].transform(lambda s: s.fillna(s.mean()))
    units[FEATURES] = units[FEATURES].fillna(units[FEATURES].mean())
    return units.reset_index(drop=True)


def majority(train, test):
    return np.full(len(test), train.y.mode().iloc[0])


def district_history(train, test):
    modes = train.groupby("district").y.agg(lambda s: s.mode().iloc[0]).to_dict()
    fallback = train.y.mode().iloc[0]
    return np.array([modes.get(d, fallback) for d in test.district])


def district_shrunk(train, test, k=2.0):
    grand = train.logscore.mean()
    stats = train.groupby("district").logscore.agg(["sum", "count"])
    out = []
    for d in test.district:
        mu = (stats.loc[d, "sum"] + k * grand) / (stats.loc[d, "count"] + k) if d in stats.index else grand
        score = np.expm1(mu)
        out.append(0 if score < 50 else (1 if score < 300 else 2))
    return np.array(out)


def logistic(train, test):
    scaler = StandardScaler().fit(train[FEATURES])
    model = LogisticRegression(C=0.1, max_iter=2000).fit(scaler.transform(train[FEATURES]), train.y)
    return model.predict(scaler.transform(test[FEATURES]))


def random_forest(train, test):
    model = RandomForestClassifier(300, min_samples_leaf=3, class_weight="balanced", random_state=0).fit(train[FEATURES], train.y)
    return model.predict(test[FEATURES])


MODELS = {"always_majority_class": majority, "district_history_mode": district_history,
          "district_shrunk_score": district_shrunk, "logistic_C0.1": logistic, "random_forest": random_forest}


def metrics(y, p):
    y, p = np.asarray(y, int), np.asarray(p, int)
    return {"accuracy": round(float((p == y).mean()), 4),
            "macro_f1": round(float(f1_score(y, p, average="macro", labels=[0, 1, 2], zero_division=0)), 4),
            "balanced_accuracy": round(float(balanced_accuracy_score(y, p)), 4),
            "mean_abs_class_error": round(float(np.abs(p - y).mean()), 4)}


def run(units, protocol):
    preds = {name: pd.Series(index=units.index, dtype=float) for name in MODELS}
    tested = []
    for year in sorted(units.year.unique()):
        test = units[units.year == year]
        train = units[units.year != year] if protocol == "leave_one_year_out" else units[units.year < year]
        if len(train) < 15 or train.y.nunique() < 2:
            continue
        tested += list(test.index)
        for name, fn in MODELS.items():
            preds[name].loc[test.index] = fn(train, test)
    return preds, tested


def paired_ci(units, tested, pa, pb, rng):
    """95% CI of the macro-F1 difference (a - b), resampling whole years (labels within a year are correlated)."""
    sub = units.loc[tested]
    years = sorted(sub.year.unique())
    diffs = []
    for _ in range(BOOTSTRAPS):
        rows = pd.concat([sub[sub.year == y] for y in rng.choice(years, len(years), replace=True)])
        diffs.append(metrics(rows.y, pa.loc[rows.index])["macro_f1"] - metrics(rows.y, pb.loc[rows.index])["macro_f1"])
    return [round(float(np.percentile(diffs, 2.5)), 4), round(float(np.percentile(diffs, 97.5)), 4)]


def evaluate(disease):
    units = build_units(disease)
    result = {"labels_file": DISEASES[disease]["labels"], "label_unit": "annual district-year", "n_units": int(len(units)),
              "years": [int(y) for y in sorted(units.year.unique())],
              "class_counts": units.severity_class.value_counts().to_dict(), "protocols": {}}
    for protocol in ("leave_one_year_out", "forward_chaining"):
        rng = np.random.default_rng(7)
        preds, tested = run(units, protocol)
        if not tested:
            continue
        sub = units.loc[tested]
        block = {"n_test_units": len(tested), "models": {n: metrics(sub.y, preds[n].loc[tested]) for n in MODELS},
                 "macro_f1_diff_vs_majority_95ci": {n: paired_ci(units, tested, preds[n], preds["always_majority_class"], rng)
                                                    for n in MODELS if n != "always_majority_class"},
                 "macro_f1_diff_vs_district_history_95ci": {n: paired_ci(units, tested, preds[n], preds["district_history_mode"], rng)
                                                            for n in ("district_shrunk_score", "logistic_C0.1", "random_forest")}}
        result["protocols"][protocol] = block
    return result


def main():
    files = {n: PROCESSED / n for n in {c["labels"] for c in DISEASES.values()} | {c["features"] for c in DISEASES.values()}}
    out = {"purpose": "Does any model beat label-free baselines on annual severity class? (negative result is a valid outcome)",
           "inputs_sha256": {n: sha256(p) for n, p in sorted(files.items())},
           "diseases": {d: evaluate(d) for d in DISEASES}}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for d, res in out["diseases"].items():
        print(f"== {d}: {res['n_units']} district-years, classes {res['class_counts']}")
        for proto, blk in res["protocols"].items():
            print(f"  {proto} (n={blk['n_test_units']})")
            for n, m in blk["models"].items():
                print(f"    {n:24s} acc={m['accuracy']:.3f} macroF1={m['macro_f1']:.3f} balAcc={m['balanced_accuracy']:.3f}")
    print("written", OUT)


if __name__ == "__main__":
    main()
