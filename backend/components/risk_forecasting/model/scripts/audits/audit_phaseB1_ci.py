"""
Phase B1 Confidence Interval Audit Script
==========================================
Reruns the 1,000-iteration paired bootstrap test comparing:
  - Baseline (27 Features: Base + Spatial Lags)
  - Phase B1 (28 Features: + own_outbreak_lag1)

Runs on both:
  1. Active Outbreak Years Subset (2020, 2021, 2023 - N=900)
  2. Full 5-Year Dataset (2020-2024 - N=1500)

Prints exact point estimates, 95% CIs (2.5th & 97.5th percentiles), and p-values.
"""

import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, average_precision_score

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')

df = pd.read_csv(DATA_PATH)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values(['district', 'date']).reset_index(drop=True)

if 'own_outbreak_lag1' not in df.columns:
    df['own_outbreak_lag1'] = df.groupby('district')['Outbreak status'].shift(1).fillna(0.0)

f_spatial = [
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

f_28 = f_spatial + ['own_outbreak_lag1']

years = sorted(df['year'].unique())

p_27 = np.zeros(len(df))
p_28 = np.zeros(len(df))

for test_year in years:
    train_df = df[df['year'] != test_year]
    test_df  = df[df['year'] == test_year]
    test_idx = test_df.index
    
    y_train = train_df['Outbreak status'].values
    y_test  = test_df['Outbreak status'].values
    
    # Fit 27 features
    s27 = StandardScaler()
    X_tr27 = s27.fit_transform(train_df[f_spatial].values)
    X_te27 = s27.transform(test_df[f_spatial].values)
    lr27 = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr27.fit(X_tr27, y_train)
    p_27[test_idx] = lr27.predict_proba(X_te27)[:, 1]
    
    # Fit 28 features
    s28 = StandardScaler()
    X_tr28 = s28.fit_transform(train_df[f_28].values)
    X_te28 = s28.transform(test_df[f_28].values)
    lr28 = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr28.fit(X_tr28, y_train)
    p_28[test_idx] = lr28.predict_proba(X_te28)[:, 1]

df['p_27'] = p_27
df['p_28'] = p_28

def run_bootstrap(sub_df, name, n_boot=1000, seed=42):
    np.random.seed(seed)
    y_true = sub_df['Outbreak status'].values
    pred27 = sub_df['p_27'].values
    pred28 = sub_df['p_28'].values
    
    point_roc27 = roc_auc_score(y_true, pred27)
    point_roc28 = roc_auc_score(y_true, pred28)
    point_delta_roc = point_roc28 - point_roc27
    
    point_pr27 = average_precision_score(y_true, pred27)
    point_pr28 = average_precision_score(y_true, pred28)
    point_delta_pr = point_pr28 - point_pr27
    
    delta_rocs = []
    delta_prs = []
    n = len(sub_df)
    
    for _ in range(n_boot):
        idx = np.random.choice(n, size=n, replace=True)
        y_b = y_true[idx]
        if len(np.unique(y_b)) < 2:
            continue
        p27_b = pred27[idx]
        p28_b = pred28[idx]
        
        d_r = roc_auc_score(y_b, p28_b) - roc_auc_score(y_b, p27_b)
        d_p = average_precision_score(y_b, p28_b) - average_precision_score(y_b, p27_b)
        delta_rocs.append(d_r)
        delta_prs.append(d_p)
        
    delta_rocs = np.array(delta_rocs)
    delta_prs = np.array(delta_prs)
    
    ci_roc = np.percentile(delta_rocs, [2.5, 97.5])
    p_val_roc = np.mean(delta_rocs <= 0)
    
    ci_pr = np.percentile(delta_prs, [2.5, 97.5])
    p_val_pr = np.mean(delta_prs <= 0)
    
    print(f"=== {name} (N={len(sub_df)}) ===")
    print(f"ROC 27f: {point_roc27:.4f} | ROC 28f: {point_roc28:.4f} | Delta ROC: {point_delta_roc:+.4f}")
    print(f"ROC Delta 95% CI: [{ci_roc[0]:+.4f}, {ci_roc[1]:+.4f}] | p-value: {p_val_roc:.4f}")
    print(f"PR  27f: {point_pr27:.4f} | PR  28f: {point_pr28:.4f} | Delta PR:  {point_delta_pr:+.4f}")
    print(f"PR  Delta 95% CI: [{ci_pr[0]:+.4f}, {ci_pr[1]:+.4f}] | p-value: {p_val_pr:.4f}\n")

run_bootstrap(df[df['year'].isin([2020, 2021, 2023])], "Active Outbreak Years Subset")
run_bootstrap(df, "Full 5-Year Dataset")
