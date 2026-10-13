"""
Phase B1: Target Autocorrelation Test (own_outbreak_lag1) for LSD
===================================================================
Tests whether adding own_outbreak_lag1 (local target autocorrelation) to the 
27-feature baseline (Base Climate + Spatial Lags) produces a statistically 
significant improvement across 5 LOYO folds (2020-2024).

Performs 1,000-iteration paired bootstrap significance testing on both:
  1. Full 5-year dataset (N=1500)
  2. Active outbreak years only (2020, 2021, 2023, N=900)
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
print("=== PHASE B1: TARGET AUTOCORRELATION TEST (own_outbreak_lag1) ===")
print(f"Loaded master LSD dataset: {df.shape[0]} rows x {df.shape[1]} columns")

# Ensure dataset sorted temporally per district to construct own_outbreak_lag1
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values(['district', 'date']).reset_index(drop=True)

# Engineer own_outbreak_lag1 if not already present
if 'own_outbreak_lag1' not in df.columns:
    df['own_outbreak_lag1'] = df.groupby('district')['Outbreak status'].shift(1).fillna(0.0)

base_27_features = [
    'sin_month', 'cos_month',
    'monsoon_phase_First_Inter_Monsoon', 'monsoon_phase_SW_Monsoon',
    'monsoon_phase_Second_Inter_Monsoon', 'monsoon_phase_NE_Monsoon',
    'rainfall_mm', 'r3h', 'rfq', 'rain_lag1', 'rain_lag2', 'rfq_lag1',
    'humidity', 'wind_speed', 'temp_lag1', 'humidity_lag1', 'wind_lag1',
    'buffalo_density', 'livestock_density',
    'nino34', 'nino34_lag3', 'iod_dmi', 'iod_dmi_lag2',
    'neighbor_outbreak_lag1', 'neighbor_outbreak_count_lag1',
    'neighbor_outbreak_fraction_lag1', 'neighbor_outbreak_lag2'
]

base_28_features = base_27_features + ['own_outbreak_lag1']

years = sorted(df['year'].unique())

df['oof_p_27'] = 0.0
df['oof_p_28'] = 0.0

fold_records = []

for test_year in years:
    train_df = df[df['year'] != test_year]
    test_df  = df[df['year'] == test_year]
    
    y_train  = train_df['Outbreak status'].values
    y_test   = test_df['Outbreak status'].values
    test_idx = test_df.index
    
    # 27 features
    scaler_27 = StandardScaler()
    X_tr_27 = scaler_27.fit_transform(train_df[base_27_features].values)
    X_te_27 = scaler_27.transform(test_df[base_27_features].values)
    lr_27   = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr_27.fit(X_tr_27, y_train)
    p_te_27 = lr_27.predict_proba(X_te_27)[:, 1]
    df.loc[test_idx, 'oof_p_27'] = p_te_27
    
    # 28 features
    scaler_28 = StandardScaler()
    X_tr_28 = scaler_28.fit_transform(train_df[base_28_features].values)
    X_te_28 = scaler_28.transform(test_df[base_28_features].values)
    lr_28   = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr_28.fit(X_tr_28, y_train)
    p_te_28 = lr_28.predict_proba(X_te_28)[:, 1]
    df.loc[test_idx, 'oof_p_28'] = p_te_28
    
    auc_27 = roc_auc_score(y_test, p_te_27) if len(np.unique(y_test)) > 1 else 0.5
    auc_28 = roc_auc_score(y_test, p_te_28) if len(np.unique(y_test)) > 1 else 0.5
    
    pr_27 = average_precision_score(y_test, p_te_27) if len(np.unique(y_test)) > 1 else np.mean(y_test)
    pr_28 = average_precision_score(y_test, p_te_28) if len(np.unique(y_test)) > 1 else np.mean(y_test)
    
    fold_records.append({
        'Year': test_year,
        'N_pos': np.sum(y_test),
        'ROC_27': auc_27,
        'ROC_28': auc_28,
        'ROC_Gain': auc_28 - auc_27,
        'PR_27': pr_27,
        'PR_28': pr_28,
        'PR_Gain': pr_28 - pr_27
    })

df_folds = pd.DataFrame(fold_records)
print("\n=== PER-FOLD BREAKDOWN (BASE 27 vs BASE 28 WITH own_outbreak_lag1) ===")
print(df_folds.to_string(index=False))

# 1,000-Iteration Bootstrap Paired Significance Tests
np.random.seed(42)

def run_bootstrap_test(sub_df, label):
    y_t = sub_df['Outbreak status'].values
    p27 = sub_df['oof_p_27'].values
    p28 = sub_df['oof_p_28'].values
    
    n_samples = len(y_t)
    diffs_roc = []
    diffs_pr  = []
    
    for _ in range(1000):
        idx = np.random.choice(n_samples, size=n_samples, replace=True)
        y_s = y_t[idx]
        if len(np.unique(y_s)) > 1:
            auc_27_s = roc_auc_score(y_s, p27[idx])
            auc_28_s = roc_auc_score(y_s, p28[idx])
            diffs_roc.append(auc_28_s - auc_27_s)
            
            pr_27_s = average_precision_score(y_s, p27[idx])
            pr_28_s = average_precision_score(y_s, p28[idx])
            diffs_pr.append(pr_28_s - pr_27_s)
            
    diffs_roc = np.array(diffs_roc)
    diffs_pr  = np.array(diffs_pr)
    
    p_val_roc = np.mean(diffs_roc <= 0.0)
    p_val_pr  = np.mean(diffs_pr <= 0.0)
    
    print(f"\n=== BOOTSTRAP SIGNIFICANCE TEST: {label} ===")
    print(f"Sample Count: N={n_samples} | Positives: N_pos={np.sum(y_t)}")
    print(f"Mean Out-of-Fold ROC-AUC Gain: {np.mean(diffs_roc):+.4f}")
    print(f"95% Confidence Interval:        [{np.percentile(diffs_roc, 2.5):+.4f}, {np.percentile(diffs_roc, 97.5):+.4f}]")
    print(f"Exact p-value (ROC-AUC):        p = {p_val_roc:.4f}")
    print(f"Mean Out-of-Fold PR-AUC Gain:  {np.mean(diffs_pr):+.4f}")
    print(f"95% Confidence Interval:        [{np.percentile(diffs_pr, 2.5):+.4f}, {np.percentile(diffs_pr, 97.5):+.4f}]")
    print(f"Exact p-value (PR-AUC):         p = {p_val_pr:.4f}")
    print(f"Statistically Significant (p < 0.05)? {p_val_roc < 0.05}")

run_bootstrap_test(df[df['year'].isin([2020, 2021, 2023])], "Active Outbreak Years Only (2020, 2021, 2023, N=900)")
run_bootstrap_test(df, "Full 5-Year Dataset (2020-2024, N=1500)")
