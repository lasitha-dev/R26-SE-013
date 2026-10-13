"""
Master Metric Reconciliation & Traceability Audit Script
=========================================================
Computes exact per-fold and aggregated metrics across all pipeline phases:
  - Phase 1 (Base 23 Climate)
  - Phase 2 (27 Features: + Spatial Lags)
  - Phase B1 (28 Features: + Target Persistence own_outbreak_lag1)
  - Phase C (28 Features: Elastic Net Regularization)
  - Phase D (28 Features: Elastic Net + Inner-CV Platt Scaling)

Prints full traceability tables for Active-Years Mean (N=900) and 5-Year Full Dataset Mean (N=1500).
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
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')

df = pd.read_csv(DATA_PATH)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values(['district', 'date']).reset_index(drop=True)

if 'own_outbreak_lag1' not in df.columns:
    df['own_outbreak_lag1'] = df.groupby('district')['Outbreak status'].shift(1).fillna(0.0)

# Feature Sets
f_base = [
    'sin_month', 'cos_month',
    'monsoon_phase_First_Inter_Monsoon', 'monsoon_phase_SW_Monsoon',
    'monsoon_phase_Second_Inter_Monsoon', 'monsoon_phase_NE_Monsoon',
    'rainfall_mm', 'r3h', 'rfq', 'rain_lag1', 'rain_lag2', 'rfq_lag1',
    'humidity', 'wind_speed', 'temp_lag1', 'humidity_lag1', 'wind_lag1',
    'buffalo_density', 'livestock_density',
    'nino34', 'nino34_lag3', 'iod_dmi', 'iod_dmi_lag2'
]

f_spatial = f_base + [
    'neighbor_outbreak_lag1', 'neighbor_outbreak_count_lag1',
    'neighbor_outbreak_fraction_lag1', 'neighbor_outbreak_lag2'
]

f_28 = f_spatial + ['own_outbreak_lag1']

years = sorted(df['year'].unique())

df['p_phase1']  = 0.0
df['p_phase2']  = 0.0
df['p_phaseB1'] = 0.0
df['p_phaseC']  = 0.0
df['p_phaseD']  = 0.0

for test_year in years:
    train_df = df[df['year'] != test_year]
    test_df  = df[df['year'] == test_year]
    test_idx = test_df.index
    
    y_train = train_df['Outbreak status'].values
    y_test  = test_df['Outbreak status'].values
    
    # 1. Phase 1 (23 Features, LR Default)
    s1 = StandardScaler()
    X_tr1 = s1.fit_transform(train_df[f_base].values)
    X_te1 = s1.transform(test_df[f_base].values)
    lr1 = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr1.fit(X_tr1, y_train)
    df.loc[test_idx, 'p_phase1'] = lr1.predict_proba(X_te1)[:, 1]
    
    # 2. Phase 2 (27 Features, LR Default)
    s2 = StandardScaler()
    X_tr2 = s2.fit_transform(train_df[f_spatial].values)
    X_te2 = s2.transform(test_df[f_spatial].values)
    lr2 = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr2.fit(X_tr2, y_train)
    df.loc[test_idx, 'p_phase2'] = lr2.predict_proba(X_te2)[:, 1]
    
    # 3. Phase B1 (28 Features, LR Default)
    s3 = StandardScaler()
    X_tr3 = s3.fit_transform(train_df[f_28].values)
    X_te3 = s3.transform(test_df[f_28].values)
    lr3 = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr3.fit(X_tr3, y_train)
    df.loc[test_idx, 'p_phaseB1'] = lr3.predict_proba(X_te3)[:, 1]
    
    # 4. Phase C (28 Features, Elastic Net Grid Search)
    param_grid_en = {'C': [1e-3, 1e-1, 1.0], 'l1_ratio': [0.2, 0.5, 0.8]}
    grid_en = GridSearchCV(LogisticRegression(penalty='elasticnet', solver='saga', class_weight='balanced', max_iter=1000, random_state=42),
                           param_grid_en, cv=4, scoring='roc_auc', n_jobs=1)
    grid_en.fit(X_tr3, y_train)
    best_en = grid_en.best_estimator_
    df.loc[test_idx, 'p_phaseC'] = best_en.predict_proba(X_te3)[:, 1]
    
    # 5. Phase D (28 Features, Elastic Net + Inner-CV Platt Scaling)
    calib = CalibratedClassifierCV(estimator=best_en, method='sigmoid', cv=4)
    calib.fit(X_tr3, y_train)
    df.loc[test_idx, 'p_phaseD'] = calib.predict_proba(X_te3)[:, 1]

print("=== PER-FOLD ROC-AUC BREAKDOWN ACROSS PHASES ===")
per_fold = []
for yr in years:
    sub = df[df['year'] == yr]
    y_t = sub['Outbreak status'].values
    r1 = roc_auc_score(y_t, sub['p_phase1']) if len(np.unique(y_t)) > 1 else 0.5
    r2 = roc_auc_score(y_t, sub['p_phase2']) if len(np.unique(y_t)) > 1 else 0.5
    rB = roc_auc_score(y_t, sub['p_phaseB1']) if len(np.unique(y_t)) > 1 else 0.5
    rC = roc_auc_score(y_t, sub['p_phaseC']) if len(np.unique(y_t)) > 1 else 0.5
    rD = roc_auc_score(y_t, sub['p_phaseD']) if len(np.unique(y_t)) > 1 else 0.5
    
    per_fold.append({
        'Test Year': yr,
        'N_pos': np.sum(y_t),
        'Phase 1 (23f)': f"{r1:.4f}",
        'Phase 2 (27f)': f"{r2:.4f}",
        'Phase B1 (28f)': f"{rB:.4f}",
        'Phase C (EN 28f)': f"{rC:.4f}",
        'Phase D (Calib EN)': f"{rD:.4f}"
    })

print(pd.DataFrame(per_fold).to_string(index=False))

print("\n=== AGGREGATED METRICS SUMMARY ===")
sub_act = df[df['year'].isin([2020, 2021, 2023])]

print("1. Active Outbreak Years Only (2020, 2021, 2023, N=900):")
print(f"  Phase 1 (23f Base):    ROC = {roc_auc_score(sub_act['Outbreak status'], sub_act['p_phase1']):.4f} | PR = {average_precision_score(sub_act['Outbreak status'], sub_act['p_phase1']):.4f}")
print(f"  Phase 2 (27f Spatial): ROC = {roc_auc_score(sub_act['Outbreak status'], sub_act['p_phase2']):.4f} | PR = {average_precision_score(sub_act['Outbreak status'], sub_act['p_phase2']):.4f}")
print(f"  Phase B1 (28f Target): ROC = {roc_auc_score(sub_act['Outbreak status'], sub_act['p_phaseB1']):.4f} | PR = {average_precision_score(sub_act['Outbreak status'], sub_act['p_phaseB1']):.4f}")
print(f"  Phase C (28f Elastic): ROC = {roc_auc_score(sub_act['Outbreak status'], sub_act['p_phaseC']):.4f} | PR = {average_precision_score(sub_act['Outbreak status'], sub_act['p_phaseC']):.4f}")
print(f"  Phase D (28f Calib):   ROC = {roc_auc_score(sub_act['Outbreak status'], sub_act['p_phaseD']):.4f} | PR = {average_precision_score(sub_act['Outbreak status'], sub_act['p_phaseD']):.4f}")

print("\n2. Full 5-Year Dataset (2020-2024, N=1500):")
print(f"  Phase 1 (23f Base):    ROC = {roc_auc_score(df['Outbreak status'], df['p_phase1']):.4f} | PR = {average_precision_score(df['Outbreak status'], df['p_phase1']):.4f}")
print(f"  Phase 2 (27f Spatial): ROC = {roc_auc_score(df['Outbreak status'], df['p_phase2']):.4f} | PR = {average_precision_score(df['Outbreak status'], df['p_phase2']):.4f}")
print(f"  Phase B1 (28f Target): ROC = {roc_auc_score(df['Outbreak status'], df['p_phaseB1']):.4f} | PR = {average_precision_score(df['Outbreak status'], df['p_phaseB1']):.4f}")
print(f"  Phase C (28f Elastic): ROC = {roc_auc_score(df['Outbreak status'], df['p_phaseC']):.4f} | PR = {average_precision_score(df['Outbreak status'], df['p_phaseC']):.4f}")
print(f"  Phase D (28f Calib):   ROC = {roc_auc_score(df['Outbreak status'], df['p_phaseD']):.4f} | PR = {average_precision_score(df['Outbreak status'], df['p_phaseD']):.4f}")
