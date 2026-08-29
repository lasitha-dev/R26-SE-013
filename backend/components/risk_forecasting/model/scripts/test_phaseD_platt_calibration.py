"""
Phase D: Inner-CV Platt Scaling Probability Calibration Audit for LSD
======================================================================
Evaluates Platt Scaling (logistic calibration) fit strictly inside inner CV folds:
  - Base Model: Elastic Net (L1+L2) Logistic Regression (Active 28 Features)
  - Inner Calibration: CalibratedClassifierCV(method='sigmoid', cv=4)
  - Metrics: Brier Score, Expected Calibration Error (ECE), ROC-AUC, PR-AUC

Performs 1,000-iteration paired bootstrap significance testing on calibration quality.
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GridSearchCV
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score, average_precision_score

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')

df = pd.read_csv(DATA_PATH)
print("=== PHASE D: INNER-CV PLATT SCALING PROBABILITY CALIBRATION AUDIT ===")

df['date'] = pd.to_datetime(df['date'])
df = df.sort_values(['district', 'date']).reset_index(drop=True)
if 'own_outbreak_lag1' not in df.columns:
    df['own_outbreak_lag1'] = df.groupby('district')['Outbreak status'].shift(1).fillna(0.0)

features = [
    'sin_month', 'cos_month',
    'monsoon_phase_First_Inter_Monsoon', 'monsoon_phase_SW_Monsoon',
    'monsoon_phase_Second_Inter_Monsoon', 'monsoon_phase_NE_Monsoon',
    'rainfall_mm', 'r3h', 'rfq', 'rain_lag1', 'rain_lag2', 'rfq_lag1',
    'humidity', 'wind_speed', 'temp_lag1', 'humidity_lag1', 'wind_lag1',
    'buffalo_density', 'livestock_density',
    'nino34', 'nino34_lag3', 'iod_dmi', 'iod_dmi_lag2',
    'neighbor_outbreak_lag1', 'neighbor_outbreak_count_lag1',
    'neighbor_outbreak_fraction_lag1', 'neighbor_outbreak_lag2',
    'own_outbreak_lag1'
]

def calculate_ece(y_true, y_prob, n_bins=10):
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i+1]
        
        in_bin = (y_prob >= bin_lower) & (y_prob < bin_upper)
        prop_in_bin = np.mean(in_bin)
        
        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(y_true[in_bin])
            avg_confidence_in_bin = np.mean(y_prob[in_bin])
            ece += np.abs(accuracy_in_bin - avg_confidence_in_bin) * prop_in_bin
            
    return ece

years = sorted(df['year'].unique())

df['oof_p_raw'] = 0.0
df['oof_p_cal'] = 0.0

fold_records = []

for test_year in years:
    train_df = df[df['year'] != test_year]
    test_df  = df[df['year'] == test_year]
    test_idx = test_df.index
    
    y_train = train_df['Outbreak status'].values
    y_test  = test_df['Outbreak status'].values
    
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(train_df[features].values)
    X_te_s = scaler.transform(test_df[features].values)
    
    # 1. Base Elastic Net Model
    param_grid_en = {'C': [1e-3, 1e-1, 1.0], 'l1_ratio': [0.2, 0.5, 0.8]}
    grid_en = GridSearchCV(LogisticRegression(penalty='elasticnet', solver='saga', class_weight='balanced', max_iter=1000, random_state=42),
                           param_grid_en, cv=4, scoring='roc_auc', n_jobs=1)
    grid_en.fit(X_tr_s, y_train)
    best_en = grid_en.best_estimator_
    
    # Raw predicted probabilities
    p_raw = best_en.predict_proba(X_te_s)[:, 1]
    df.loc[test_idx, 'oof_p_raw'] = p_raw
    
    # 2. Inner-CV Platt Calibrated Model
    calib_model = CalibratedClassifierCV(estimator=best_en, method='sigmoid', cv=4)
    calib_model.fit(X_tr_s, y_train)
    
    p_cal = calib_model.predict_proba(X_te_s)[:, 1]
    df.loc[test_idx, 'oof_p_cal'] = p_cal
    
    brier_raw = brier_score_loss(y_test, p_raw)
    brier_cal = brier_score_loss(y_test, p_cal)
    
    ece_raw = calculate_ece(y_test, p_raw)
    ece_cal = calculate_ece(y_test, p_cal)
    
    fold_records.append({
        'Test Year': test_year,
        'N_pos': np.sum(y_test),
        'Raw Brier': f"{brier_raw:.4f}",
        'Calib Brier': f"{brier_cal:.4f}",
        'Brier Delta': f"{brier_cal - brier_raw:+.4f}",
        'Raw ECE': f"{ece_raw:.4f}",
        'Calib ECE': f"{ece_cal:.4f}",
        'ECE Delta': f"{ece_cal - ece_raw:+.4f}"
    })

print("\n=== PER-FOLD PLATT CALIBRATION PERFORMANCE BREAKDOWN ===")
print(pd.DataFrame(fold_records).to_string(index=False))

# 1,000-Iteration Bootstrap Significance Test on Calibration Improvement
np.random.seed(42)

def run_calibration_bootstrap(sub_df, label):
    y_true = sub_df['Outbreak status'].values
    p_raw  = sub_df['oof_p_raw'].values
    p_cal  = sub_df['oof_p_cal'].values
    n = len(y_true)
    
    diffs_brier = []
    diffs_ece   = []
    
    for _ in range(1000):
        idx = np.random.choice(n, size=n, replace=True)
        y_s  = y_true[idx]
        pr_s = p_raw[idx]
        pc_s = p_cal[idx]
        
        b_raw_s = brier_score_loss(y_s, pr_s)
        b_cal_s = brier_score_loss(y_s, pc_s)
        diffs_brier.append(b_cal_s - b_raw_s) # Negative delta is improvement
        
        e_raw_s = calculate_ece(y_s, pr_s)
        e_cal_s = calculate_ece(y_s, pc_s)
        diffs_ece.append(e_cal_s - e_raw_s)   # Negative delta is improvement
        
    diffs_brier = np.array(diffs_brier)
    diffs_ece   = np.array(diffs_ece)
    
    p_val_brier = np.mean(diffs_brier >= 0.0) # testing if brier_cal < brier_raw
    p_val_ece   = np.mean(diffs_ece >= 0.0)
    
    print(f"\n" + "="*70)
    print(f"=== 1,000-ITERATION BOOTSTRAP CALIBRATION SIGNIFICANCE TEST ({label}) ===")
    print(f"Sample Count: N={n} | Positives N_pos={np.sum(y_true)}")
    print(f"Mean Brier Score Reduction: {np.mean(diffs_brier):+.4f} | 95% CI: [{np.percentile(diffs_brier, 2.5):+.4f}, {np.percentile(diffs_brier, 97.5):+.4f}] | p-val: {p_val_brier:.4f}")
    print(f"Mean ECE Reduction:         {np.mean(diffs_ece):+.4f} | 95% CI: [{np.percentile(diffs_ece, 2.5):+.4f}, {np.percentile(diffs_ece, 97.5):+.4f}] | p-val: {p_val_ece:.4f}")
    print(f"Brier Reduction Statistically Significant (p < 0.05)? {p_val_brier < 0.05}")

run_calibration_bootstrap(df[df['year'].isin([2020, 2021, 2023])], "Active Outbreak Years Only (2020, 2021, 2023, N=900)")
run_calibration_bootstrap(df, "Full 5-Year Dataset (2020-2024, N=1500)")
