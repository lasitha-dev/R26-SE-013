"""
Train and honestly evaluate the v2 one-month-ahead outbreak models (FMD, LSD).

Usage (from backend/, after build_dataset.py):
    python components/risk_forecasting/model/scripts/v2/train_evaluate.py

Design (sparse-event forecasting practice):
- Monthly rolling-origin backtest with an expanding window: the forecast for
  month T is trained only on labelled months before T.
- Baselines: always-zero, persistence (last month's status) and a smoothed
  district x calendar-month climatology. A model must beat climatology.
- Candidates: L2 logistic regression on standardised features, optionally plus
  the logit of the climatology prior (partial pooling across districts).
    variant A = base + surveillance features + climatology prior
    variant S = surveillance features only (outbreak-history dynamics, no prior)
    variant B = base + climatology prior (used when surveillance status is unknown)
- Prequential selection: the forecast for month T uses the (variant, C) with the
  best PR-AUC on all earlier backtest months only, as a running system would.
  The first backtest year is a warm-up; metrics come from the later years.
- Onset skill is reported separately (months with no outbreak in t-1).
- The climatology prior used as a model input is computed leave-one-year-out on the
  training rows (a row never sees its own year's labels inside its prior); at prediction
  time the prior comes from all earlier data, exactly as in operation.
- Moving-block bootstrap CIs (6 consecutive months) for PR-AUC differences, which respects
  month-to-month dependence; the i.i.d. month bootstrap is reported alongside as a sensitivity.
Artifacts are written as JSON (no pickles): model/models/v2/<disease>_v2.json.
"""

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

BACKEND_DIR = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(BACKEND_DIR))

from components.risk_forecasting.pipeline.features import BASE_FEATURES, SURVEILLANCE_FEATURES  # noqa: E402

MODEL_DIR = BACKEND_DIR / "components" / "risk_forecasting" / "model"
CACHE = MODEL_DIR / "data" / "cache"
ARTIFACTS = MODEL_DIR / "models" / "v2"
REPORTS = MODEL_DIR / "docs" / "v2"

BACKTEST = {"FMD": (2021, 2023), "LSD": (2022, 2024)}  # first year = C selection, rest = evaluation
C_GRID = [0.01, 0.03, 0.1, 0.3, 1.0]
PRIOR_STRENGTH = 3.0          # pseudo-years pulling a district-month rate toward the national rate
RELATIVE_RISK_ALERT = 2.0     # "elevated" when probability >= 2x the climatological baseline
BOOTSTRAP = 2000
BOOTSTRAP_BLOCK_MONTHS = 6    # decision CI uses 6-month moving blocks (outbreaks cluster in time)
BOOTSTRAP_SEED = 42
# name -> (features, use climatology prior)
VARIANTS = {
    "A": (BASE_FEATURES + SURVEILLANCE_FEATURES, True),
    "S": (SURVEILLANCE_FEATURES, False),
    "B": (BASE_FEATURES, True),
}


def logit(p):
    p = np.clip(p, 1e-3, 1 - 1e-3)
    return np.log(p / (1 - p))


def climatology_table(train):
    """Smoothed outbreak rates: district x month shrunk toward national month, toward overall."""
    overall = train.outbreak.mean()
    nat = train.groupby("month").outbreak.agg(["sum", "count"])
    nat_rate = (nat["sum"] + PRIOR_STRENGTH * overall) / (nat["count"] + PRIOR_STRENGTH)
    dm = train.groupby(["district", "month"]).outbreak.agg(["sum", "count"]).reset_index()
    dm["rate"] = (dm["sum"] + PRIOR_STRENGTH * dm.month.map(nat_rate)) / (dm["count"] + PRIOR_STRENGTH)
    return {
        "overall": float(overall),
        "national_month": {int(m): float(r) for m, r in nat_rate.items()},
        "district_month": {f"{r.district}|{int(r.month)}": float(r.rate) for r in dm.itertuples()},
    }


def prior_for(table, district, month):
    return table["district_month"].get(
        f"{district}|{month}", table["national_month"].get(month, table["overall"]))


def loyo_prior(train):
    """Climatology prior for each training row computed WITHOUT that row's calendar year, so the
    model is fitted on out-of-sample priors like the ones it receives at prediction time.
    (An in-sample prior contains the row's own label and makes the model over-trust it.)"""
    prior = np.empty(len(train))
    for year in train.year.unique():
        mask = (train.year == year).to_numpy()
        rest = train[~mask]
        if rest.empty:
            prior[mask] = train.outbreak.mean()
            continue
        table = climatology_table(rest)
        prior[mask] = [prior_for(table, d, m) for d, m in zip(train.district[mask], train.month[mask])]
    return prior


def design_matrix(rows, features, mean, std, table, use_prior, prior=None):
    x = (rows[features].to_numpy(float) - mean) / std
    if not use_prior:
        return x
    if prior is None:
        prior = np.array([prior_for(table, d, m) for d, m in zip(rows.district, rows.month)])
    return np.column_stack([x, logit(prior)])


def fit_lr(train, features, c, table, use_prior, train_prior=None):
    x = train[features].to_numpy(float)
    mean, std = x.mean(axis=0), x.std(axis=0)
    std[std == 0] = 1.0
    if use_prior and train_prior is None:
        train_prior = loyo_prior(train)
    design = design_matrix(train, features, mean, std, table, use_prior, prior=train_prior)
    model = LogisticRegression(C=c, max_iter=5000)
    model.fit(design, train.outbreak.to_numpy(int))
    return {"mean": mean, "std": std, "coef": model.coef_[0], "intercept": float(model.intercept_[0])}


def predict_lr(params, rows, features, table, use_prior):
    design = design_matrix(rows, features, params["mean"], params["std"], table, use_prior)
    z = design @ params["coef"] + params["intercept"]
    return 1 / (1 + np.exp(-z))


def backtest(data, disease):
    first, last = BACKTEST[disease]
    data = data.assign(t=data.year * 12 + data.month - 1)
    preds = []
    for t in range(first * 12, (last + 1) * 12):
        train, test = data[data.t < t], data[data.t == t]
        table = climatology_table(train)
        out = test[["district", "year", "month", "outbreak", "own_t1"]].copy()
        out["climatology"] = [prior_for(table, d, m) for d, m in zip(test.district, test.month)]
        out["persistence"] = test.own_t1
        for name, (features, use_prior) in VARIANTS.items():
            tr = train.dropna(subset=features)
            ok = test[features].notna().all(axis=1)
            tr_prior = loyo_prior(tr) if use_prior else None
            for c in C_GRID:
                params = fit_lr(tr, features, c, table, use_prior, train_prior=tr_prior)
                col = f"{name}_C{c}"
                out[col] = np.nan
                out.loc[ok, col] = predict_lr(params, test[ok], features, table, use_prior)
        preds.append(out)
    return pd.concat(preds, ignore_index=True)


def metrics(y, p, base):
    y, p, base = np.asarray(y), np.asarray(p, float), np.asarray(base, float)
    res = {"n": int(len(y)), "positives": int(y.sum())}
    if y.sum() == 0 or y.sum() == len(y):
        return res
    res["pr_auc"] = float(average_precision_score(y, p))
    res["roc_auc"] = float(roc_auc_score(y, p))
    res["brier"] = float(brier_score_loss(y, p))
    ref = brier_score_loss(y, base)
    res["brier_skill_vs_climatology"] = float(1 - res["brier"] / ref) if ref > 0 else None
    alert = p >= RELATIVE_RISK_ALERT * base
    tp = int((alert & (y == 1)).sum())
    res["alert_rate"] = float(alert.mean())
    res["recall_at_rr2"] = float(tp / y.sum())
    res["precision_at_rr2"] = float(tp / alert.sum()) if alert.sum() else None
    return res


def _bootstrap_diff(frame, col_a, col_b, block):
    """Moving-block bootstrap over chronologically ordered months: resample blocks of `block`
    consecutive months (block=1 is the i.i.d. month bootstrap) until the original length is reached."""
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    months = frame.groupby(["year", "month"]).indices   # keys iterate in chronological order
    keys = list(months)
    n = len(keys)
    block = max(1, min(block, n))
    diffs = []
    for _ in range(BOOTSTRAP):
        picked = []
        while len(picked) < n:
            start = int(rng.integers(0, n - block + 1))
            picked.extend(range(start, start + block))
        idx = np.concatenate([months[keys[i]] for i in picked[:n]])
        s = frame.iloc[idx]
        if 0 < s.outbreak.sum() < len(s):
            diffs.append(average_precision_score(s.outbreak, s[col_a]) - average_precision_score(s.outbreak, s[col_b]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"mean": float(np.mean(diffs)), "ci95": [float(lo), float(hi)], "p_le_0": float(np.mean(np.array(diffs) <= 0))}


def block_bootstrap_diff(frame, col_a, col_b):
    """PR-AUC(col_a) - PR-AUC(col_b). `ci95` (used for deployment) is the 6-month moving-block
    interval; `iid_month_ci95` is the narrower i.i.d. month interval, kept as a sensitivity."""
    result = _bootstrap_diff(frame, col_a, col_b, BOOTSTRAP_BLOCK_MONTHS)
    result["block_months"] = BOOTSTRAP_BLOCK_MONTHS
    result["iid_month_ci95"] = _bootstrap_diff(frame, col_a, col_b, 1)["ci95"]
    return result


def candidate_columns(variants):
    return [f"{v}_C{c}" for v in variants for c in C_GRID]


def pr_auc_or_none(frame, col):
    s = frame.dropna(subset=[col])
    if s.empty or s.outbreak.sum() == 0 or s.outbreak.sum() == len(s):
        return None
    return average_precision_score(s.outbreak, s[col])


def best_column(history, columns):
    scores = {c: pr_auc_or_none(history, c) for c in columns}
    scores = {c: v for c, v in scores.items() if v is not None}
    return max(scores, key=scores.get) if scores else columns[0]


def prequential(preds, columns, eval_months):
    """For each evaluation month T, use the candidate with the best PR-AUC on all earlier
    backtest months (information available at T). Returns the forecast series and choices."""
    series = pd.Series(np.nan, index=preds.index)
    choices = {}
    for t in eval_months:
        chosen = best_column(preds[preds.t < t], columns)
        idx = preds.index[preds.t == t]
        series.loc[idx] = preds.loc[idx, chosen]
        choices[f"{t // 12}-{t % 12 + 1:02d}"] = chosen
    return series, choices


def evaluate(preds, disease):
    first, _ = BACKTEST[disease]
    preds = preds.assign(t=preds.year * 12 + preds.month - 1)
    eval_months = sorted(preds.loc[preds.year > first, "t"].unique())

    series, choices = {}, {}
    groups = {"known": ("A", "S"), "unknown": ("B",), "A": ("A",), "S": ("S",), "B": ("B",)}
    for name, variants in groups.items():
        series[name], choices[name] = prequential(preds, candidate_columns(variants), eval_months)

    rows = preds[preds.year > first].assign(**{f"model_{k}": v for k, v in series.items()})
    rows = rows.dropna(subset=[f"model_{k}" for k in series] + ["persistence"])
    candidates = {
        "always_zero": np.zeros(len(rows)),
        "persistence": rows.persistence.to_numpy(float),
        "climatology": rows.climatology.to_numpy(float),
        **{f"model_{k}": rows[f"model_{k}"].to_numpy(float) for k in series},
    }
    overall = {k: metrics(rows.outbreak, v, rows.climatology) for k, v in candidates.items()}
    onset_mask = (rows.own_t1 == 0).to_numpy()
    onset_rows = rows[onset_mask]
    onset = {k: metrics(onset_rows.outbreak, v[onset_mask], onset_rows.climatology)
             for k, v in candidates.items() if k != "persistence"}
    comparisons = {}
    for k in ("known", "unknown", "A", "S", "B"):
        comparisons[f"model_{k}_minus_climatology"] = block_bootstrap_diff(rows, f"model_{k}", "climatology")
        comparisons[f"model_{k}_minus_persistence"] = block_bootstrap_diff(rows, f"model_{k}", "persistence")
    per_year = {int(y): metrics(g.outbreak, g.model_known, g.climatology) for y, g in rows.groupby("year")}

    # Configuration deployed from now on: best on the full backtest history.
    final_known = best_column(preds, candidate_columns(("A", "S")))
    final_unknown = best_column(preds, candidate_columns(("B",)))
    final_primary = best_column(preds, candidate_columns(("A",)))
    return {
        "evaluation_years": sorted(int(y) for y in rows.year.unique()),
        "selection": "prequential: each month uses the best (variant, C) on all earlier backtest months",
        "monthly_choices": choices,
        "final_configuration": {"surveillance_known": final_known, "surveillance_unknown": final_unknown,
                                "primary_A": final_primary},
        "overall": overall,
        "onset": onset,
        "bootstrap_pr_auc": comparisons,
        "known_forecaster_per_year": per_year,
    }


def decide(ev):
    """Final deployment protocol (fixed before export; iterations are listed in the model card).

    A forecaster passes when, in the untouched evaluation years, its PR-AUC gain over
    climatology has a 95% CI above zero, its Brier skill vs climatology is positive, and
    it is not worse than persistence on average.

    Surveillance known:
      1. Pre-specified primary variant A passes  -> deploy A, status "back_tested".
      2. Else the prequential A/S forecaster passes -> deploy its final configuration,
         status "exploratory" (variant S was added after the first evaluation run, so it
         needs prospective confirmation).
      3. Else climatology, status "baseline".
    Surveillance unknown: variant B if it passes ("back_tested"), else climatology.
    """
    def ok(name):
        clim = ev["bootstrap_pr_auc"][f"model_{name}_minus_climatology"]
        pers = ev["bootstrap_pr_auc"][f"model_{name}_minus_persistence"]
        skill = ev["overall"][f"model_{name}"].get("brier_skill_vs_climatology") or 0
        return clim["ci95"][0] > 0 and skill > 0 and pers["mean"] >= 0

    def config(column, status):
        variant, c = column.split("_C")
        return {"forecaster": variant, "C": float(c), "status": status}

    final = ev["final_configuration"]
    baseline = {"forecaster": "climatology", "C": None, "status": "baseline"}
    if ok("A"):
        known = config(final["primary_A"], "back_tested")
    elif ok("known"):
        known = config(final["surveillance_known"], "exploratory")
    else:
        known = baseline
    unknown = config(final["surveillance_unknown"], "back_tested") if ok("unknown") else baseline
    return {"surveillance_known": known, "surveillance_unknown": unknown}


def export(data, disease, ev, decision):
    table = climatology_table(data)
    chosen_c = {d["forecaster"]: d["C"] for d in decision.values() if d["forecaster"] != "climatology"}
    artifact = {
        "disease": disease,
        "model_version": f"{disease.lower()}_v2.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_period": [f"{data.year.min()}-01", f"{data.year.max()}-12"],
        "label_policy": "FMD 2017-2023 (2024 excluded as unverified); LSD 2020-2024",
        "issue_rule": "issued on day 5 of target month t using observations up to t-1 (Nino 3.4 up to t-2)",
        "relative_risk_alert": RELATIVE_RISK_ALERT,
        "climatology": table,
        "deployment": decision,
        "variants": {},
        "evaluation_summary": {
            "evaluation_years": ev["evaluation_years"],
            "pr_auc": {k: v.get("pr_auc") for k, v in ev["overall"].items()},
            "brier_skill_vs_climatology": {k: v.get("brier_skill_vs_climatology") for k, v in ev["overall"].items()},
            "known_minus_climatology_ci95": ev["bootstrap_pr_auc"]["model_known_minus_climatology"]["ci95"],
            "known_minus_persistence_ci95": ev["bootstrap_pr_auc"]["model_known_minus_persistence"]["ci95"],
        },
        "training_procedure": {
            "prior_for_training_rows": "leave-one-year-out climatology",
            "prior_for_prediction": "climatology from all training data",
            "bootstrap": {"block_months": BOOTSTRAP_BLOCK_MONTHS, "resamples": BOOTSTRAP, "seed": BOOTSTRAP_SEED},
            "c_grid": C_GRID, "prior_strength": PRIOR_STRENGTH, "backtest_years": list(BACKTEST[disease]),
            "dataset_file": f"v2_{disease}_dataset.csv",
            "dataset_sha256": sha256_of(CACHE / f"v2_{disease}_dataset.csv"),
            "dataset_rows": int(len(data)),
        },
        "library_versions": {"scikit-learn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__},
        "data_sources": {
            "rainfall": "CHIRPS via WFP/HDX lka-rainfall-subnat-full.csv (adm2)",
            "weather": "NASA POWER T2M/RH2M/WS2M, community AG, district points",
            "enso": "NOAA PSL nina34.data (anomaly vs 1991-2020)",
            "surveillance": "curated DAPH-derived outbreak status (training); verified app cases/deaths (operations)",
        },
    }
    for v, c in chosen_c.items():
        features, use_prior = VARIANTS[v]
        train = data.dropna(subset=features)
        params = fit_lr(train, features, c, table, use_prior)  # leave-one-year-out prior inside fit_lr
        artifact["variants"][v] = {
            "features": features,
            "uses_climatology_prior": use_prior,
            "C": c,
            "scaler_mean": params["mean"].tolist(),
            "scaler_std": params["std"].tolist(),
            "coef": params["coef"].tolist(),
            "intercept": params["intercept"],
            "training_rows": int(len(train)),
        }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / f"{disease.lower()}_v2.json"
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return path


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_data_manifest():
    """Fingerprint of every cached input file (name, size, sha256) so a result can be tied to the
    exact data it was computed from. Run logs, live caches and generated predictions are excluded."""
    skip = {"runs", "live"}
    files = {}
    for path in sorted(CACHE.rglob("*")):
        rel = path.relative_to(CACHE)
        if path.is_file() and not (set(rel.parts[:-1]) & skip) and "backtest_predictions" not in path.name:
            files[rel.as_posix()] = {"bytes": path.stat().st_size, "sha256": sha256_of(path)}
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(), "cache_dir": "model/data/cache", "files": files}
    (REPORTS / "data_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return len(files)


def fmt(value, digits=3):
    return "  n/a" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value:.{digits}f}"


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    full = {}
    for disease in ("FMD", "LSD"):
        data = pd.read_csv(CACHE / f"v2_{disease}_dataset.csv").dropna(subset=BASE_FEATURES)
        preds = backtest(data, disease)
        preds.to_csv(CACHE / f"v2_{disease}_backtest_predictions.csv", index=False)
        ev = evaluate(preds, disease)
        decision = decide(ev)
        path = export(data, disease, ev, decision)
        full[disease] = {**ev, "deployment": decision}
        print(f"\n===== {disease}  evaluation years {ev['evaluation_years']}  final config {ev['final_configuration']}")
        for k, v in ev["overall"].items():
            print(f"  {k:14s} PR-AUC {fmt(v.get('pr_auc'))}  ROC {fmt(v.get('roc_auc'))}  "
                  f"BrierSkill {fmt(v.get('brier_skill_vs_climatology'))}  recall@RR2 {fmt(v.get('recall_at_rr2'), 2)}  "
                  f"prec@RR2 {fmt(v.get('precision_at_rr2'), 2)}  (n={v['n']}, pos={v['positives']})")
        print("  onset PR-AUC:", {k: fmt(v.get("pr_auc")) for k, v in ev["onset"].items()})
        for k, v in ev["bootstrap_pr_auc"].items():
            print(f"  {k:34s} mean {v['mean']:+.3f}  95% CI [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]")
        print("  deployment decision:", decision, "->", path.name)
    (REPORTS / "v2_evaluation.json").write_text(json.dumps(full, indent=2), encoding="utf-8")
    print("\nreport ->", REPORTS / "v2_evaluation.json", "| data manifest files:", write_data_manifest())


if __name__ == "__main__":
    main()
