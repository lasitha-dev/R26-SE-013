"""Stage 2 pre-registered experiment (docs/v2/STAGE2_EXPERIMENT_PLAN.md). Offline: reads data/processed and writes
only docs/v2/stage2_experiment_results.json. Run from the model directory: python scripts/v2/stage2_experiment.py. Candidates: B (district history), N (national
frequency, reference), M1 (penalised cumulative-logit), M2 (empirical-Bayes hierarchical on log1p score)."""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import norm, spearmanr

warnings.filterwarnings("ignore")
sys.dont_write_bytecode = True
MODEL_DIR = Path(__file__).resolve().parents[2]
PROC = MODEL_DIR / "data" / "processed"
OUT = MODEL_DIR / "docs" / "v2" / "stage2_experiment_results.json"
ORD = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
STATIC = ["livestock_density", "buffalo_density"]
ENV = ["rainfall_mm", "humidity", "temp_lag1"]
CFG = {
    "FMD": dict(labels="severity_labels.csv", feat="FMD_dataset_with_spatial_and_climate_indices.csv", ren={"District": "district", "Year": "year"},
                thr=(50.0, 300.0), test_years=[2019, 2020, 2021, 2022, 2023, 2024], use_history=True, drop_year=2024),
    "LSD": dict(labels="LSD_severity_labels.csv", feat="LSD_dataset_with_spatial_and_climate_indices.csv", ren={},
                thr=(63.0, 460.0), test_years=[2021, 2022, 2023, 2024], use_history=False, drop_year=2023),
}
PENALTIES = [0.03, 0.1, 0.3, 1.0]
RIDGE = [1.0, 3.0, 10.0, 30.0]
K_SHRINK = 2.0


def classes(score, thr):
    return np.where(score < thr[0], 0, np.where(score < thr[1], 1, 2))


def load(disease):
    c = CFG[disease]
    lab = pd.read_csv(PROC / c["labels"]).rename(columns=c["ren"])
    feat = pd.read_csv(PROC / c["feat"])
    static = feat.groupby("district")[STATIC].first().reset_index()
    prior = feat.groupby(["district", "year"])[ENV].mean().reset_index()
    prior["year"] = prior["year"] + 1                     # previous calendar year's summary, attached to the target year
    prior = prior.rename(columns={e: "prev_" + e for e in ENV})
    d = lab.merge(static, on="district", how="left").merge(prior, on=["district", "year"], how="left")
    d["logscore"] = np.log1p(d["severity_score"])
    return d.sort_values(["year", "district"]).reset_index(drop=True)


def history_features(d):
    """Earlier labelled years of the same district only (strictly before this row's year)."""
    n, m = [], []
    for r in d.itertuples():
        e = d[(d.district == r.district) & (d.year < r.year)]
        n.append(len(e)); m.append(e.logscore.mean() if len(e) else np.nan)
    d = d.copy(); d["n_earlier"] = n; d["mean_prior"] = m
    d["no_history"] = (d.n_earlier == 0).astype(float)
    return d


def design(train, test, cols):
    mu = train[cols].mean(); sd = train[cols].std().replace(0, 1).fillna(1)
    f = lambda x: ((x[cols].fillna(mu) - mu) / sd).fillna(0).values
    return f(train), f(test)


def class_freq(y, k=3):
    return np.array([(y == c).sum() for c in range(k)], float)


def prob_national(train):
    p = (class_freq(train.y.values) + 1) / (len(train) + 3)
    return p


def prob_history(train, test):
    nat = prob_national(train)
    out = []
    for dist in test.district:
        cnt = class_freq(train[train.district == dist].y.values)
        out.append((cnt + K_SHRINK * nat) / (cnt.sum() + K_SHRINK))
    return np.array(out)


def fit_ordinal(X, y, lam):
    k = X.shape[1]
    def unpack(w):
        b = w[:k]; t1 = w[k]; t2 = t1 + np.exp(w[k + 1]); return b, t1, t2
    def nll(w):
        b, t1, t2 = unpack(w); eta = X @ b
        c1 = expit(t1 - eta); c2 = expit(t2 - eta)
        p = np.where(y == 0, c1, np.where(y == 1, c2 - c1, 1 - c2))
        return -np.log(np.clip(p, 1e-9, None)).sum() + lam * (b @ b)
    w0 = np.zeros(k + 2); w0[k] = -0.5; w0[k + 1] = 0.0
    r = minimize(nll, w0, method="L-BFGS-B")
    return unpack(r.x)


def pred_ordinal(model, X):
    b, t1, t2 = model; eta = X @ b
    c1 = expit(t1 - eta); c2 = expit(t2 - eta)
    return np.column_stack([c1, c2 - c1, 1 - c2])


def prob_m1(train, test, cols, lam=None):
    Xtr, Xte = design(train, test, cols); ytr = train.y.values
    if lam is None:
        lam = tune(lambda tr, te, l: prob_m1_fixed(tr, te, cols, l), train, PENALTIES)
    return prob_m1_fixed(train, test, cols, lam), lam


def prob_m1_fixed(train, test, cols, lam):
    Xtr, Xte = design(train, test, cols)
    return pred_ordinal(fit_ordinal(Xtr, train.y.values, lam), Xte)


def prob_m2_fixed(train, test, cols, lam, thr):
    Xtr, Xte = design(train, test, cols)
    ytr = train.logscore.values
    A = Xtr.T @ Xtr + lam * np.eye(Xtr.shape[1]); beta = np.linalg.solve(A, Xtr.T @ (ytr - ytr.mean()))
    resid = ytr - ytr.mean() - Xtr @ beta
    g = pd.DataFrame({"d": train.district.values, "r": resid})
    stats = g.groupby("d").r.agg(["mean", "count", "var"])
    within = stats["var"].dropna()
    sigma2 = float(np.average(within, weights=(stats.loc[within.index, "count"] - 1))) if len(within) else float(resid.var() + 1e-6)
    sigma2 = max(sigma2, 1e-3)
    n_bar = stats["count"].mean()
    tau2 = max(float(stats["mean"].var() - sigma2 / n_bar), 1e-3) if len(stats) > 2 else 1e-3
    lo, hi = np.log1p(thr[0]), np.log1p(thr[1])
    out = []
    for i, dist in enumerate(test.district):
        if dist in stats.index:
            n = stats.loc[dist, "count"]; w = n * tau2 / (n * tau2 + sigma2)
            u = w * stats.loc[dist, "mean"]; var = sigma2 + tau2 * (1 - w)
        else:
            u, var = 0.0, sigma2 + tau2
        mu = ytr.mean() + Xte[i] @ beta + u
        c1 = norm.cdf((lo - mu) / np.sqrt(var)); c2 = norm.cdf((hi - mu) / np.sqrt(var))
        out.append([c1, c2 - c1, 1 - c2])
    return np.array(out), (ytr.mean() + Xte @ beta + 0)


def prob_m2(train, test, cols, thr, lam=None):
    if lam is None:
        lam = tune(lambda tr, te, l: prob_m2_fixed(tr, te, cols, l, thr)[0], train, RIDGE)
    p, mu = prob_m2_fixed(train, test, cols, lam, thr)
    return p, lam


def rps(P, y):
    cum_p = np.cumsum(P, axis=1)[:, :2]
    cum_o = np.column_stack([(y <= 0).astype(float), (y <= 1).astype(float)])
    return ((cum_p - cum_o) ** 2).sum(axis=1) / 2


def tune(predict, train, grid):
    """Inner forward-chaining on the training years only; criterion = mean RPS."""
    years = sorted(train.year.unique())
    if len(years) < 3:
        return grid[len(grid) // 2]
    best, best_s = grid[len(grid) // 2], np.inf
    for lam in grid:
        scores = []
        for y in years[1:]:
            tr, te = train[train.year < y], train[train.year == y]
            if len(tr) < 8 or tr.y.nunique() < 2: continue
            try:
                scores.append(rps(predict(tr, te, lam), te.y.values).mean())
            except Exception:
                pass
        if scores and np.mean(scores) < best_s:
            best, best_s = lam, np.mean(scores)
    return best


def point(P):
    return P.argmax(axis=1)


def bal_acc_macro_f1(y, p):
    rec, f1s = [], []
    for c in range(3):
        tp = ((p == c) & (y == c)).sum(); fn = ((p != c) & (y == c)).sum(); fp = ((p == c) & (y != c)).sum()
        if (y == c).sum() > 0: rec.append(tp / (tp + fn))
        f1s.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(rec)), float(np.mean([f for f, c in zip(f1s, range(3)) if (y == c).sum() > 0 or (p == c).sum() > 0]))


def calib(P, y, col):
    """Observed frequency of class >= col in three bins of predicted probability."""
    pr = P[:, col:].sum(axis=1); obs = (y >= col).astype(float)
    bins = [(0, 0.2), (0.2, 0.5), (0.5, 1.01)]
    rows = []
    for lo, hi in bins:
        m = (pr >= lo) & (pr < hi)
        rows.append({"bin": f"{lo}-{min(hi, 1)}", "n": int(m.sum()), "observed": None if m.sum() == 0 else round(float(obs[m].mean()), 3)})
    return rows


def run(disease, protocol, thr_mode="fixed", drop_year=None):
    c = CFG[disease]
    d = load(disease)
    if drop_year: d = d[d.year != drop_year].reset_index(drop=True)
    d = history_features(d) if c["use_history"] else d
    cols = STATIC + ["prev_" + e for e in ENV] + (["n_earlier", "mean_prior", "no_history"] if c["use_history"] else [])
    res = {k: [] for k in ("B", "N", "M1", "M2")}
    rows_y, rows_year, rows_lsc = [], [], []
    years = [y for y in c["test_years"] if y != drop_year]
    for ty in years:
        tr = d[d.year < ty] if protocol == "forward" else d[d.year != ty]
        te = d[d.year == ty]
        if len(tr) < 15 or te.empty: continue
        thr = c["thr"]
        if thr_mode == "tertile":
            q = tr.severity_score.quantile([1 / 3, 2 / 3]).values; thr = (float(q[0]), float(q[1]))
        tr = tr.assign(y=classes(tr.severity_score.values, thr)); te = te.assign(y=classes(te.severity_score.values, thr))
        if tr.y.nunique() < 2: continue
        P = {"N": np.tile(prob_national(tr), (len(te), 1)), "B": prob_history(tr, te)}
        P["M1"], lam1 = prob_m1(tr, te, cols)
        P["M2"], lam2 = prob_m2(tr, te, cols, thr)
        for k in res: res[k].append(P[k])
        rows_y.append(te.y.values); rows_year.append(np.full(len(te), ty)); rows_lsc.append(te.logscore.values)
        # remember tuned values
    if not rows_y: return None
    y = np.concatenate(rows_y); yr = np.concatenate(rows_year)
    out = {"n_test": int(len(y)), "years": [int(v) for v in sorted(set(yr))], "class_share": {k: round(float((y == i).mean()), 3) for i, k in enumerate(["LOW", "MEDIUM", "HIGH"])}, "models": {}, "per_year_rps": {}}
    allP = {k: np.vstack(v) for k, v in res.items()}
    for k, P in allP.items():
        r = rps(P, y); p = point(P)
        ba, mf = bal_acc_macro_f1(y, p)
        out["models"][k] = {"rps": round(float(r.mean()), 4), "ordinal_mae": round(float(np.abs(p - y).mean()), 4), "balanced_accuracy": round(ba, 4),
                            "macro_f1": round(mf, 4), "accuracy": round(float((p == y).mean()), 4),
                            "calib_P(>=MEDIUM)": calib(P, y, 1), "calib_P(HIGH)": calib(P, y, 2)}
        out["per_year_rps"][k] = {int(t): round(float(r[yr == t].mean()), 4) for t in sorted(set(yr))}
    # M2 regression-style metrics on log1p(score): expected value reconstructed from class probabilities is not used;
    # report Spearman of expected ordinal class vs observed log score
    lsc = np.concatenate(rows_lsc)
    for k in ("B", "M1", "M2"):
        exp_class = allP[k] @ np.array([0, 1, 2])
        out["models"][k]["spearman_expected_class_vs_logscore"] = round(float(spearmanr(exp_class, lsc).correlation), 4)
    return out


def decision(disease, fwd, sens_drop, sens_tert):
    rows = {}
    for m in ("M1", "M2"):
        mm, b, n = fwd["models"][m], fwd["models"]["B"], fwd["models"]["N"]
        py = fwd["per_year_rps"]
        wins = sum(py[m][t] < py["B"][t] for t in py[m]); total = len(py[m])
        c1 = mm["rps"] < b["rps"] and mm["rps"] < n["rps"]
        c2 = mm["ordinal_mae"] <= b["ordinal_mae"]
        c3 = wins > total / 2
        c4 = bool(sens_drop) and sens_drop["models"][m]["rps"] < sens_drop["models"]["B"]["rps"]
        def calib_ok(blocks):
            obs = [b_["observed"] for b_ in blocks if b_["observed"] is not None]
            return len(obs) < 2 or obs[-1] >= obs[0]
        c5 = calib_ok(mm["calib_P(HIGH)"]) and calib_ok(mm["calib_P(>=MEDIUM)"])
        rows[m] = {"1_rps_below_B_and_N": c1, "2_ordinal_mae_not_above_B": c2, f"3_better_than_B_in_{wins}_of_{total}_years": c3,
                   "4_still_better_without_extreme_year": c4, "5_no_calibration_reversal": c5, "ALL_MET": bool(c1 and c2 and c3 and c4 and c5)}
    return rows


def main():
    results = {}
    for disease in ("FMD", "LSD"):
        r = {}
        r["forward_fixed"] = run(disease, "forward")
        r["loyo_fixed_descriptive"] = run(disease, "loyo")
        r["forward_tertile_sensitivity"] = run(disease, "forward", thr_mode="tertile")
        r["forward_without_extreme_year"] = run(disease, "forward", drop_year=CFG[disease]["drop_year"])
        r["decision_rule"] = decision(disease, r["forward_fixed"], r["forward_without_extreme_year"], r["forward_tertile_sensitivity"])
        results[disease] = r
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    for disease, r in results.items():
        print(f"\n######## {disease}")
        for name in ("forward_fixed", "loyo_fixed_descriptive", "forward_tertile_sensitivity", "forward_without_extreme_year"):
            blk = r[name]
            if not blk: print(name, "n/a"); continue
            print(f"-- {name} (n={blk['n_test']}, years={blk['years']}, class share={blk['class_share']})")
            for k, m in blk["models"].items():
                print(f"   {k:3s} RPS={m['rps']:.4f} ordMAE={m['ordinal_mae']:.3f} balAcc={m['balanced_accuracy']:.3f} macroF1={m['macro_f1']:.3f} acc={m['accuracy']:.3f}" + (f" spearman={m['spearman_expected_class_vs_logscore']:.3f}" if 'spearman_expected_class_vs_logscore' in m else ""))
            if name == "forward_fixed": print("   per-year RPS:", blk["per_year_rps"])
        print("-- decision rule:", json.dumps(r["decision_rule"]))


if __name__ == "__main__":
    main()
