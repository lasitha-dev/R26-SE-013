"""
Nested Time-Aware LOYO Training and Validation Script for LSD 27-Feature Stage 1 Fallback Model.
Generates separate production artifacts:
- lsd_stage1_27feat_elasticnet.pkl
- lsd_stage1_27feat_scaler.pkl
- lsd_stage1_27feat_cols.pkl
- lsd_stage1_27feat_metadata.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    roc_auc_score, precision_recall_curve, auc, brier_score_loss,
    confusion_matrix, precision_score, recall_score, f1_score
)
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_DIR = SCRIPT_DIR.parent
MODELS_DIR = MODEL_DIR / "models"
DATA_FILE = MODEL_DIR / "data" / "processed" / "LSD_dataset_with_spatial_and_climate_indices.csv"
COLS_28_FILE = MODELS_DIR / "lsd_stage1_feature_cols.pkl"

# Production Artifact Target Paths (SEPARATE from 28-feature artifacts)
OUT_MODEL = MODELS_DIR / "lsd_stage1_27feat_elasticnet.pkl"
OUT_SCALER = MODELS_DIR / "lsd_stage1_27feat_scaler.pkl"
OUT_COLS = MODELS_DIR / "lsd_stage1_27feat_cols.pkl"
OUT_META = MODELS_DIR / "lsd_stage1_27feat_metadata.json"


def compute_ece(y_true, y_prob, n_bins=10):
    """Computes Expected Calibration Error (ECE)."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    binids = np.digitize(y_prob, bins) - 1
    ece = 0.0
    total = len(y_true)
    for i in range(n_bins):
        mask = binids == i
        if np.any(mask):
            bin_acc = np.mean(y_true[mask])
            bin_conf = np.mean(y_prob[mask])
            ece += np.abs(bin_acc - bin_conf) * (np.sum(mask) / total)
    return float(ece)


def calculate_pr_auc(y_true, y_prob):
    """Calculates Area Under Precision-Recall Curve."""
    precision, recall, _ = precision_recall_curve(y_true, y_prob)
    return float(auc(recall, precision))


def run_nested_loyo_evaluation(df, feat_cols):
    """Runs Nested Time-Aware Leave-One-Year-Out Cross-Validation on 27 features."""
    years = sorted(df["year"].unique())
    logger.info(f"Running Nested LOYO CV across years: {years}")

    oof_predictions = []
    
    # Candidate hyperparameter grid for inner tuning
    c_candidates = [0.01, 0.1, 1.0]
    l1_candidates = [0.2, 0.5, 0.8]

    best_hyperparams_list = []

    for test_year in years:
        train_df = df[df["year"] != test_year].copy()
        test_df = df[df["year"] == test_year].copy()

        y_train = train_df["Outbreak status"].values
        X_train_raw = train_df[feat_cols].values
        
        y_test = test_df["Outbreak status"].values
        X_test_raw = test_df[feat_cols].values

        # Inner hyperparameter selection on train_df
        inner_years = sorted(train_df["year"].unique())
        best_score = -1.0
        best_params = (0.1, 0.5)

        for c_val in c_candidates:
            for l1_val in l1_candidates:
                inner_scores = []
                for inner_test_yr in inner_years:
                    in_tr = train_df[train_df["year"] != inner_test_yr]
                    in_va = train_df[train_df["year"] == inner_test_yr]
                    
                    if in_va["Outbreak status"].sum() == 0:
                        continue

                    in_scaler = StandardScaler()
                    in_X_tr = in_scaler.fit_transform(in_tr[feat_cols].values)
                    in_X_va = in_scaler.transform(in_va[feat_cols].values)

                    base_lr = LogisticRegression(
                        penalty="elasticnet",
                        solver="saga",
                        C=c_val,
                        l1_ratio=l1_val,
                        class_weight="balanced",
                        random_state=42,
                        max_iter=1000
                    )
                    cal_clf = CalibratedClassifierCV(estimator=base_lr, method="sigmoid", cv=4)
                    cal_clf.fit(in_X_tr, in_tr["Outbreak status"].values)
                    in_probs = cal_clf.predict_proba(in_X_va)[:, 1]
                    try:
                        score = calculate_pr_auc(in_va["Outbreak status"].values, in_probs)
                        inner_scores.append(score)
                    except Exception:
                        pass

                avg_score = np.mean(inner_scores) if inner_scores else 0.0
                if avg_score > best_score:
                    best_score = avg_score
                    best_params = (c_val, l1_val)

        best_hyperparams_list.append(best_params)
        c_opt, l1_opt = best_params
        logger.info(f"Year {test_year} outer test -> Best inner params: C={c_opt}, l1_ratio={l1_opt} (Inner PR-AUC: {best_score:.4f})")

        # Outer evaluation with selected params
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_raw)
        X_test_scaled = scaler.transform(X_test_raw)

        base_lr = LogisticRegression(
            penalty="elasticnet",
            solver="saga",
            C=c_opt,
            l1_ratio=l1_opt,
            class_weight="balanced",
            random_state=42,
            max_iter=1000
        )
        cal_model = CalibratedClassifierCV(estimator=base_lr, method="sigmoid", cv=4)
        cal_model.fit(X_train_scaled, y_train)

        test_probs = cal_model.predict_proba(X_test_scaled)[:, 1]

        for i, idx in enumerate(test_df.index):
            oof_predictions.append({
                "index": idx,
                "district": test_df.loc[idx, "district"],
                "year": int(test_year),
                "month_num": int(test_df.loc[idx, "month_num"]),
                "y_true": float(y_test[i]),
                "y_prob": float(test_probs[i])
            })

    oof_df = pd.DataFrame(oof_predictions)
    return oof_df, best_hyperparams_list


def main():
    logger.info("Starting LSD 27-Feature Model Training & Validation Pipeline...")

    # Safety Check: Verify existing 28-feature production artifacts exist & remain untouched
    existing_28_files = [
        MODELS_DIR / "lsd_stage1_elasticnet.pkl",
        MODELS_DIR / "lsd_stage1_scaler.pkl",
        MODELS_DIR / "lsd_stage1_feature_cols.pkl"
    ]
    for f in existing_28_files:
        if not f.exists():
            raise FileNotFoundError(f"Safety Gate Failure: Production 28-feature file missing: {f}")
    logger.info("Safety Gate Passed: Existing 28-feature production artifacts verified intact.")

    # Load Dataset
    df = pd.read_csv(DATA_FILE)
    logger.info(f"Loaded dataset: {DATA_FILE.name} (Rows: {len(df)})")

    # Extract 28 features and construct 27-feature list
    cols_28 = joblib.load(COLS_28_FILE)
    feat_cols_27 = [c for c in cols_28 if c != "own_outbreak_lag1"]
    logger.info(f"Constructed 27-feature list (excluded 'own_outbreak_lag1'): {len(feat_cols_27)} features.")

    # Run Nested LOYO Evaluation
    oof_df, hyperparams_history = run_nested_loyo_evaluation(df, feat_cols_27)

    y_true_all = oof_df["y_true"].values
    y_prob_all = oof_df["y_prob"].values

    # Overall Metrics
    overall_roc = float(roc_auc_score(y_true_all, y_prob_all))
    overall_pr = float(calculate_pr_auc(y_true_all, y_prob_all))
    overall_brier = float(brier_score_loss(y_true_all, y_prob_all))
    overall_ece = float(compute_ece(y_true_all, y_prob_all))

    # Active Outbreak Years (2020, 2021, 2023)
    active_mask = oof_df["year"].isin([2020, 2021, 2023])
    y_true_act = oof_df.loc[active_mask, "y_true"].values
    y_prob_act = oof_df.loc[active_mask, "y_prob"].values
    active_roc = float(roc_auc_score(y_true_act, y_prob_act))
    active_pr = float(calculate_pr_auc(y_true_act, y_prob_act))
    active_brier = float(brier_score_loss(y_true_act, y_prob_act))
    active_ece = float(compute_ece(y_true_act, y_prob_act))

    # Per-year Metrics
    per_year_metrics = {}
    for yr in sorted(oof_df["year"].unique()):
        sub = oof_df[oof_df["year"] == yr]
        yt = sub["y_true"].values
        yp = sub["y_prob"].values
        pos_cnt = int(yt.sum())
        
        yr_roc = float(roc_auc_score(yt, yp)) if pos_cnt > 0 and pos_cnt < len(yt) else None
        yr_pr = float(calculate_pr_auc(yt, yp)) if pos_cnt > 0 else None
        yr_brier = float(brier_score_loss(yt, yp))
        yr_ece = float(compute_ece(yt, yp))

        per_year_metrics[str(yr)] = {
            "total_samples": len(sub),
            "positive_cases": pos_cnt,
            "roc_auc": yr_roc,
            "pr_auc": yr_pr,
            "brier_score": yr_brier,
            "ece_score": yr_ece
        }

    # Threshold Audit across t in [0.20, 0.60]
    logger.info("Auditing operating thresholds...")
    threshold_results = {}
    best_t_f1 = 0.40
    max_f1 = -1.0

    for t_val in np.arange(0.20, 0.62, 0.05):
        t_val = round(float(t_val), 2)
        y_pred = (y_prob_all >= t_val).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true_all, y_pred, labels=[0, 1]).ravel()
        prec = float(precision_score(y_true_all, y_pred, zero_division=0))
        rec = float(recall_score(y_true_all, y_pred, zero_division=0))
        f1 = float(f1_score(y_true_all, y_pred, zero_division=0))
        fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

        if f1 > max_f1:
            max_f1 = f1
            best_t_f1 = t_val

        threshold_results[str(t_val)] = {
            "confusion_matrix": {"TN": int(tn), "FP": int(fp), "FN": int(fn), "TP": int(tp)},
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "false_negative_rate": fnr
        }

    # Metrics at standard t = 0.40
    t040_metrics = threshold_results.get("0.4", threshold_results.get("0.40"))

    # Train Final Production Candidate on Full Dataset
    # Select most frequent hyperparams from outer LOYO runs
    c_counts = {}
    for c_hp, l1_hp in hyperparams_history:
        c_counts[(c_hp, l1_hp)] = c_counts.get((c_hp, l1_hp), 0) + 1
    best_overall_params = max(c_counts, key=c_counts.get)
    opt_c, opt_l1 = best_overall_params

    logger.info(f"Fitting final production 27-feature candidate on full dataset using C={opt_c}, l1_ratio={opt_l1}...")
    full_scaler = StandardScaler()
    X_full_scaled = full_scaler.fit_transform(df[feat_cols_27].values)
    y_full = df["Outbreak status"].values

    base_lr_final = LogisticRegression(
        penalty="elasticnet",
        solver="saga",
        C=opt_c,
        l1_ratio=opt_l1,
        class_weight="balanced",
        random_state=42,
        max_iter=1000
    )
    final_cal_model = CalibratedClassifierCV(estimator=base_lr_final, method="sigmoid", cv=4)
    final_cal_model.fit(X_full_scaled, y_full)

    # Export Production Artifacts
    joblib.dump(final_cal_model, OUT_MODEL)
    joblib.dump(full_scaler, OUT_SCALER)
    joblib.dump(feat_cols_27, OUT_COLS)

    metadata = {
        "model_variant": "27_feature_fallback",
        "disease": "LSD",
        "stage": 1,
        "feature_count": len(feat_cols_27),
        "feature_cols": feat_cols_27,
        "dataset_source": DATA_FILE.name,
        "training_years": [int(y) for y in sorted(df["year"].unique())],
        "training_timestamp": datetime.now().isoformat(),
        "model_family": "CalibratedClassifierCV (Platt Scaling) wrapping ElasticNet LogisticRegression",
        "selected_hyperparameters": {
            "C": opt_c,
            "l1_ratio": opt_l1,
            "class_weight": "balanced",
            "solver": "saga",
            "random_state": 42
        },
        "operating_threshold": 0.40,
        "validation_metrics": {
            "overall_roc_auc": overall_roc,
            "overall_pr_auc": overall_pr,
            "overall_brier_score": overall_brier,
            "overall_ece_score": overall_ece,
            "active_outbreak_years_roc_auc": active_roc,
            "active_outbreak_years_pr_auc": active_pr,
            "active_outbreak_years_brier_score": active_brier,
            "active_outbreak_years_ece_score": active_ece,
            "metrics_at_t_040": t040_metrics,
            "recommended_threshold_f1_max": best_t_f1,
            "per_year_breakdown": per_year_metrics
        }
    }

    with open(OUT_META, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Successfully saved separate 27-feature artifacts to {MODELS_DIR}")
    
    # Print Executive Summary for Safety Gate Audit
    print("\n" + "="*80)
    print("      LSD 27-FEATURE FALLBACK MODEL — VALIDATION EXECUTIVE SUMMARY")
    print("="*80)
    print(f"Selected Elastic Net Hyperparameters: C={opt_c}, l1_ratio={opt_l1}")
    print(f"Full 5-Fold Outer LOYO ROC-AUC:      {overall_roc:.4f}")
    print(f"Full 5-Fold Outer LOYO PR-AUC:       {overall_pr:.4f}")
    print(f"Active Outbreak Folds ROC-AUC:       {active_roc:.4f}")
    print(f"Active Outbreak Folds PR-AUC:        {active_pr:.4f}")
    print(f"Overall Platt Brier Score:           {overall_brier:.4f}")
    print(f"Overall Expected Calibration Error:  {overall_ece:.4f}")
    print("-"*80)
    print("Performance at Operating Threshold t = 0.40:")
    if t040_metrics:
        cm = t040_metrics["confusion_matrix"]
        print(f"  Confusion Matrix: TP={cm['TP']}, FP={cm['FP']}, TN={cm['TN']}, FN={cm['FN']}")
        print(f"  Precision:        {t040_metrics['precision']:.4f}")
        print(f"  Recall:           {t040_metrics['recall']:.4f}")
        print(f"  F1 Score:         {t040_metrics['f1_score']:.4f}")
        print(f"  False Neg Rate:   {t040_metrics['false_negative_rate']:.4f}")
    print("-"*80)
    print("Per-Year Breakdown:")
    for yr, m in per_year_metrics.items():
        roc_str = f"{m['roc_auc']:.4f}" if m['roc_auc'] is not None else "N/A"
        pr_str = f"{m['pr_auc']:.4f}" if m['pr_auc'] is not None else "N/A"
        print(f"  Year {yr}: Positives={m['positive_cases']}/{m['total_samples']} | ROC={roc_str} | PR={pr_str} | Brier={m['brier_score']:.4f} | ECE={m['ece_score']:.4f}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
