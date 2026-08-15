"""
Phase B2 Re-run: Policy-Constrained vs Unconstrained Nested Threshold Selection
================================================================================
Compares two nested threshold selection rules on historical training folds:
  1. Unconstrained F1-Maximization (freely picks t in [0.05, 0.95])
  2. Policy-Constrained Recall Floor (highest t in [0.05, 0.95] that satisfies Recall >= 50%)

Evaluates both blindly on held-out test years against fixed baselines (t=0.50, t=0.40).
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')

df = pd.read_csv(DATA_PATH)
print("=== PHASE B2 AUDIT: POLICY-CONSTRAINED VS UNCONSTRAINED THRESHOLD TUNING ===")
print(f"Loaded master LSD dataset: {df.shape[0]} rows x {df.shape[1]} columns")

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

years = sorted(df['year'].unique())
oof_preds = np.zeros(len(df))
oof_y     = df['Outbreak status'].values

for test_year in years:
    train_df = df[df['year'] != test_year]
    test_df  = df[df['year'] == test_year]
    test_idx = test_df.index
    
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(train_df[features].values)
    X_te_s = scaler.transform(test_df[features].values)
    
    lr = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr.fit(X_tr_s, train_df['Outbreak status'].values)
    
    oof_preds[test_idx] = lr.predict_proba(X_te_s)[:, 1]

df['oof_proba'] = oof_preds
candidate_thresholds = np.arange(0.05, 0.95, 0.05)

y_pred_unconstrained = np.zeros(len(df))
y_pred_constrained   = np.zeros(len(df))
y_pred_t50           = (oof_preds >= 0.50).astype(int)
y_pred_t40           = (oof_preds >= 0.40).astype(int)

fold_records = []

for test_year in years:
    test_mask = (df['year'] == test_year)
    train_hist_mask = (df['year'] < test_year)
    
    if train_hist_mask.sum() == 0:
        t_unconstrained = 0.50
        t_constrained   = 0.40
    else:
        hist_y = oof_y[train_hist_mask]
        hist_p = oof_preds[train_hist_mask]
        
        # Rule 1: Unconstrained F1-Max
        best_f1 = -1.0
        t_unconstrained = 0.50
        for t in candidate_thresholds:
            p_t = (hist_p >= t).astype(int)
            s = f1_score(hist_y, p_t, zero_division=0)
            if s > best_f1:
                best_f1 = s
                t_unconstrained = t
                
        # Rule 2: Policy-Constrained (Highest t meeting Recall >= 50%)
        t_constrained = 0.20 # Fallback high-sensitivity
        for t in reversed(candidate_thresholds):
            p_t = (hist_p >= t).astype(int)
            rec = recall_score(hist_y, p_t, zero_division=0)
            if rec >= 0.50:
                t_constrained = t
                break
                
    test_y = oof_y[test_mask]
    test_p = oof_preds[test_mask]
    
    p_unc = (test_p >= t_unconstrained).astype(int)
    p_con = (test_p >= t_constrained).astype(int)
    
    y_pred_unconstrained[test_mask] = p_unc
    y_pred_constrained[test_mask]   = p_con
    
    f1_unc = f1_score(test_y, p_unc, zero_division=0)
    rec_unc = recall_score(test_y, p_unc, zero_division=0)
    
    f1_con = f1_score(test_y, p_con, zero_division=0)
    rec_con = recall_score(test_y, p_con, zero_division=0)
    
    fold_records.append({
        'Test Year': test_year,
        'N_pos': np.sum(test_y),
        'Unc t*': f"{t_unconstrained:.2f}",
        'Unc Recall': f"{rec_unc*100:.1f}%",
        'Unc F1': f"{f1_unc:.4f}",
        'Con t*': f"{t_constrained:.2f}",
        'Con Recall': f"{rec_con*100:.1f}%",
        'Con F1': f"{f1_con:.4f}"
    })

df_folds = pd.DataFrame(fold_records)
print("\n=== PER-FOLD BREAKDOWN: UNCONSTRAINED VS POLICY-CONSTRAINED (RECALL >= 50%) ===")
print(df_folds.to_string(index=False))

print("\n=== OVERALL OUT-OF-FOLD PERFORMANCE COMPARISON (N=1500) ===")
summary_rows = []
for name, y_p in [('Default Fixed (t = 0.50)', y_pred_t50),
                  ('Global Fixed (t = 0.40)', y_pred_t40),
                  ('Unconstrained Nested F1-Max', y_pred_unconstrained),
                  ('Policy-Constrained (Recall >= 50%)', y_pred_constrained)]:
    p = precision_score(oof_y, y_p, zero_division=0)
    r = recall_score(oof_y, y_p, zero_division=0)
    f = f1_score(oof_y, y_p, zero_division=0)
    summary_rows.append({
        'Threshold Strategy': name,
        'Overall Precision': f"{p:.4f}",
        'Overall Recall': f"{r*100:.2f}%",
        'Overall F1-Score': f"{f:.4f}",
        'Positives Detected': f"{np.sum((oof_y == 1) & (y_p == 1))} / {np.sum(oof_y)}"
    })

print(pd.DataFrame(summary_rows).to_string(index=False))
