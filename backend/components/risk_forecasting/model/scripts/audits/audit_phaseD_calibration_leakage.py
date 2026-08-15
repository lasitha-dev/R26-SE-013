"""
Phase D Audit: Calibration Leakage & Discrimination Rank Preservation
======================================================================
Addressing review points:
  1. Side-by-side ROC-AUC and PR-AUC before and after Platt scaling fold by fold.
  2. Temporal Calibration Split vs. Stratified K-Fold Calibration comparison.
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score, average_precision_score

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')

df = pd.read_csv(DATA_PATH)
print("=== PHASE D AUDIT: LEAKAGE & DISCRIMINATION RANK PRESERVATION ===")

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

df['oof_p_raw']      = 0.0
df['oof_p_cal_kfold'] = 0.0

rank_comparison = []

for test_year in years:
    train_df = df[df['year'] != test_year]
    test_df  = df[df['year'] == test_year]
    test_idx = test_df.index
    
    y_train = train_df['Outbreak status'].values
    y_test  = test_df['Outbreak status'].values
    
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(train_df[features].values)
    X_te_s = scaler.transform(test_df[features].values)
    
    param_grid_en = {'C': [1e-3, 1e-1, 1.0], 'l1_ratio': [0.2, 0.5, 0.8]}
    grid_en = GridSearchCV(LogisticRegression(penalty='elasticnet', solver='saga', class_weight='balanced', max_iter=1000, random_state=42),
                           param_grid_en, cv=4, scoring='roc_auc', n_jobs=1)
    grid_en.fit(X_tr_s, y_train)
    best_en = grid_en.best_estimator_
    
    p_raw = best_en.predict_proba(X_te_s)[:, 1]
    df.loc[test_idx, 'oof_p_raw'] = p_raw
    
    # Stratified K-Fold Calibrated Model
    calib_kfold = CalibratedClassifierCV(estimator=best_en, method='sigmoid', cv=4)
    calib_kfold.fit(X_tr_s, y_train)
    p_cal_kfold = calib_kfold.predict_proba(X_te_s)[:, 1]
    df.loc[test_idx, 'oof_p_cal_kfold'] = p_cal_kfold
    
    roc_raw = roc_auc_score(y_test, p_raw) if len(np.unique(y_test)) > 1 else 0.5
    roc_cal = roc_auc_score(y_test, p_cal_kfold) if len(np.unique(y_test)) > 1 else 0.5
    
    pr_raw = average_precision_score(y_test, p_raw) if len(np.unique(y_test)) > 1 else 0.0
    pr_cal = average_precision_score(y_test, p_cal_kfold) if len(np.unique(y_test)) > 1 else 0.0
    
    rank_comparison.append({
        'Test Year': test_year,
        'N_pos': np.sum(y_test),
        'Raw ROC-AUC': f"{roc_raw:.4f}",
        'Calib ROC-AUC': f"{roc_cal:.4f}",
        'ROC Delta': f"{roc_cal - roc_raw:+.4f}",
        'Raw PR-AUC': f"{pr_raw:.4f}",
        'Calib PR-AUC': f"{pr_cal:.4f}",
        'PR Delta': f"{pr_cal - pr_raw:+.4f}"
    })

print("\n=== POINT 2: SIDE-BY-SIDE DISCRIMINATION RANK PRESERVATION (ROC-AUC & PR-AUC) ===")
print(pd.DataFrame(rank_comparison).to_string(index=False))

# Temporal Calibration Audit
print("\n" + "="*70)
print("=== POINT 1: TEMPORAL CALIBRATION VS STRATIFIED K-FOLD CALIBRATION ===")

df_temp_cal = df.copy()
df_temp_cal['oof_p_cal_temp'] = 0.0

for i, test_year in enumerate(years):
    if test_year in [2020, 2021]:
        # Fallback to K-Fold for early years where training slice has only 1 year
        df_temp_cal.loc[df_temp_cal['year'] == test_year, 'oof_p_cal_temp'] = df_temp_cal.loc[df_temp_cal['year'] == test_year, 'oof_p_cal_kfold']
        continue
        
    # Temporal Split inside training data:
    # Model Fit: Training years prior to (test_year - 1)
    # Calibrator Fit: Training year (test_year - 1)
    # Test Evaluation: test_year
    
    fit_years   = [y for y in years if y < test_year - 1]
    cal_year    = test_year - 1
    
    fit_df = df[df['year'].isin(fit_years)]
    cal_df = df[df['year'] == cal_year]
    test_df = df[df['year'] == test_year]
    test_idx = test_df.index
    
    y_fit = fit_df['Outbreak status'].values
    y_cal = cal_df['Outbreak status'].values
    y_test = test_df['Outbreak status'].values
    
    scaler = StandardScaler()
    X_fit_s  = scaler.fit_transform(fit_df[features].values)
    X_cal_s  = scaler.transform(cal_df[features].values)
    X_test_s = scaler.transform(test_df[features].values)
    
    grid_en = GridSearchCV(LogisticRegression(penalty='elasticnet', solver='saga', class_weight='balanced', max_iter=1000, random_state=42),
                           param_grid_en, cv=3, scoring='roc_auc', n_jobs=1)
    grid_en.fit(X_fit_s, y_fit)
    best_en = grid_en.best_estimator_
    
    # Fit Platt Scaler on strictly distinct, temporally-later calibration fold
    p_cal_logits = best_en.predict_proba(X_cal_s)[:, 1]
    p_test_logits = best_en.predict_proba(X_test_s)[:, 1]
    
    platt_lr = LogisticRegression(penalty=None, solver='lbfgs', max_iter=1000)
    platt_lr.fit(p_cal_logits.reshape(-1, 1), y_cal)
    
    p_temp_cal = platt_lr.predict_proba(p_test_logits.reshape(-1, 1))[:, 1]
    df_temp_cal.loc[test_idx, 'oof_p_cal_temp'] = p_temp_cal

for yr in [2022, 2023, 2024]:
    sub = df_temp_cal[df_temp_cal['year'] == yr]
    y_t  = sub['Outbreak status'].values
    p_k  = sub['oof_p_cal_kfold'].values
    p_tm = sub['oof_p_cal_temp'].values
    
    b_k  = brier_score_loss(y_t, p_k)
    b_tm = brier_score_loss(y_t, p_tm)
    
    print(f"Year {yr}: Stratified K-Fold Calib Brier = {b_k:.4f} | Strict Temporal Calib Brier = {b_tm:.4f} | Delta = {b_tm - b_k:+.4f}")
