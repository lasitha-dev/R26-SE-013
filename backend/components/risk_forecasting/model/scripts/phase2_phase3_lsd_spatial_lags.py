"""
Step 3: Phase 2 & 3 — Spatial Neighbor Lags & Decision Threshold Optimization (LSD)
====================================================================================
Tests Hypothesis: Does adding spatial neighbor contagion lags (neighbor_outbreak_fraction_lag1)
specifically recover predictive power in 2020 and 2023, and improve overall ROC-AUC / PR-AUC?

Evaluates:
  1. Base Climate (23 features) vs Base + Spatial Lags (27 features)
  2. Per-fold breakdown across all 5 LOYO years (2020-2024)
  3. Decision Threshold Optimization (t in [0.15, 0.50])
  4. 1,000-Iteration Paired Bootstrap Significance Audit
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, average_precision_score

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')

df = pd.read_csv(DATA_PATH)
print("=== STEP 3: PHASE 2 & 3 SPATIAL LAGS & THRESHOLD OPTIMIZATION (LSD) ===")
print(f"Loaded dataset: {df.shape[0]} rows x {df.shape[1]} columns")

base_features = [
    'sin_month', 'cos_month',
    'monsoon_phase_First_Inter_Monsoon', 'monsoon_phase_SW_Monsoon',
    'monsoon_phase_Second_Inter_Monsoon', 'monsoon_phase_NE_Monsoon',
    'rainfall_mm', 'r3h', 'rfq', 'rain_lag1', 'rain_lag2', 'rfq_lag1',
    'humidity', 'wind_speed', 'temp_lag1', 'humidity_lag1', 'wind_lag1',
    'buffalo_density', 'livestock_density',
    'nino34', 'nino34_lag3', 'iod_dmi', 'iod_dmi_lag2'
]

spatial_features = base_features + [
    'neighbor_outbreak_lag1', 'neighbor_outbreak_count_lag1',
    'neighbor_outbreak_fraction_lag1', 'neighbor_outbreak_lag2'
]

years = sorted(df['year'].unique())

df['oof_base_proba']    = 0.0
df['oof_spatial_proba'] = 0.0

fold_records = []

for test_year in years:
    train_df = df[df['year'] != test_year]
    test_df  = df[df['year'] == test_year]
    
    y_train = train_df['Outbreak status'].values
    y_test  = test_df['Outbreak status'].values
    test_idx = test_df.index
    
    # 1. Base Climate Model (23 features)
    scaler_base = StandardScaler()
    X_tr_b = scaler_base.fit_transform(train_df[base_features].values)
    X_te_b = scaler_base.transform(test_df[base_features].values)
    
    lr_base = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr_base.fit(X_tr_b, y_train)
    p_base = lr_base.predict_proba(X_te_b)[:, 1]
    df.loc[test_idx, 'oof_base_proba'] = p_base
    
    roc_base = roc_auc_score(y_test, p_base) if len(np.unique(y_test)) > 1 else 0.5
    pr_base  = average_precision_score(y_test, p_base) if len(np.unique(y_test)) > 1 else np.mean(y_test)
    
    # 2. Base + Spatial Lags Model (27 features)
    scaler_sp = StandardScaler()
    X_tr_s = scaler_sp.fit_transform(train_df[spatial_features].values)
    X_te_s = scaler_sp.transform(test_df[spatial_features].values)
    
    lr_sp = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr_sp.fit(X_tr_s, y_train)
    p_sp = lr_sp.predict_proba(X_te_s)[:, 1]
    df.loc[test_idx, 'oof_spatial_proba'] = p_sp
    
    roc_sp = roc_auc_score(y_test, p_sp) if len(np.unique(y_test)) > 1 else 0.5
    pr_sp  = average_precision_score(y_test, p_sp) if len(np.unique(y_test)) > 1 else np.mean(y_test)
    
    fold_records.append({
        'Year': test_year,
        'Positives': np.sum(y_test),
        'Base ROC-AUC': round(roc_base, 4),
        'Spatial ROC-AUC': round(roc_sp, 4),
        'ROC Gain': round(roc_sp - roc_base, 4),
        'Base PR-AUC': round(pr_base, 4),
        'Spatial PR-AUC': round(pr_sp, 4),
        'PR Gain': round(pr_sp - pr_base, 4)
    })

df_folds = pd.DataFrame(fold_records)
print("\n=== PER-FOLD COMPARISON: BASE CLIMATE VS BASE + SPATIAL LAGS ===")
print(df_folds.to_string(index=False))

# 3. Threshold Tuning Grid Search for Spatial Model
thresholds = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
thresh_records = []

y_true_all = df['Outbreak status'].values
p_sp_all   = df['oof_spatial_proba'].values

for t in thresholds:
    y_pred = (p_sp_all >= t).astype(int)
    prec = precision_score(y_true_all, y_pred, zero_division=0)
    rec  = recall_score(y_true_all, y_pred, zero_division=0)
    f1   = f1_score(y_true_all, y_pred, zero_division=0)
    thresh_records.append({'Threshold (t)': t, 'Precision': round(prec, 4), 'Recall': round(rec, 4), 'F1-Score': round(f1, 4)})

df_thresh = pd.DataFrame(thresh_records)
print("\n=== THRESHOLD TUNING GRID SEARCH (SPATIAL MODEL, ALL 1,500 SAMPLES) ===")
print(df_thresh.to_string(index=False))

# 4. 1,000-Iteration Paired Bootstrap Significance Test
np.random.seed(42)
n_samples = len(y_true_all)
boot_diffs_roc = []
boot_diffs_pr  = []

p_base_all = df['oof_base_proba'].values

for i in range(1000):
    idx = np.random.choice(n_samples, size=n_samples, replace=True)
    y_b = y_true_all[idx]
    if len(np.unique(y_b)) > 1:
        auc_b = roc_auc_score(y_b, p_base_all[idx])
        auc_s = roc_auc_score(y_b, p_sp_all[idx])
        boot_diffs_roc.append(auc_s - auc_b)
        
        pr_b = average_precision_score(y_b, p_base_all[idx])
        pr_s = average_precision_score(y_b, p_sp_all[idx])
        boot_diffs_pr.append(pr_s - pr_b)

boot_diffs_roc = np.array(boot_diffs_roc)
boot_diffs_pr  = np.array(boot_diffs_pr)

p_val_roc = np.mean(boot_diffs_roc <= 0.0)
p_val_pr  = np.mean(boot_diffs_pr <= 0.0)

print("\n=== 1,000-ITERATION PAIRED BOOTSTRAP SIGNIFICANCE TEST (SPATIAL VS BASE) ===")
print(f"Mean ROC-AUC Gain: {np.mean(boot_diffs_roc):+.4f} | 95% CI: [{np.percentile(boot_diffs_roc, 2.5):+.4f}, {np.percentile(boot_diffs_roc, 97.5):+.4f}] | p-value: p = {p_val_roc:.4f}")
print(f"Mean PR-AUC Gain:  {np.mean(boot_diffs_pr):+.4f} | 95% CI: [{np.percentile(boot_diffs_pr, 2.5):+.4f}, {np.percentile(boot_diffs_pr, 97.5):+.4f}] | p-value: p = {p_val_pr:.4f}")
print(f"Is Spatial Lag Gain Statistically Significant (p < 0.05)? {p_val_roc < 0.05 or p_val_pr < 0.05}")
