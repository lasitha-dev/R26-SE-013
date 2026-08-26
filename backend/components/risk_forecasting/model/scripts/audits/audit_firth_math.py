"""
Firth's Penalized Logistic Regression Audit Script
===================================================
Audits Firth's implementation under:
  1. Unweighted Firth (Original)
  2. Class-Weighted Firth (Firth + Balanced Class Weights)
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')

df = pd.read_csv(DATA_PATH)
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

class WeightedFirthLogisticRegression:
    def __init__(self, max_iter=100, tol=1e-5):
        self.max_iter = max_iter
        self.tol = tol
        self.coef_ = None
        self.intercept_ = None

    def _sigmoid(self, z):
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

    def fit(self, X, y, sample_weight=None):
        n_samples, n_features = X.shape
        X_design = np.column_stack([np.ones(n_samples), X])
        n_params = n_features + 1
        
        if sample_weight is None:
            sw = np.ones(n_samples)
        else:
            sw = sample_weight
            
        beta = np.zeros(n_params)
        
        for iteration in range(self.max_iter):
            p = self._sigmoid(X_design @ beta)
            w = p * (1.0 - p) * sw
            w = np.maximum(w, 1e-5)
            
            # Fisher Information Matrix I = X^T W X
            I = X_design.T @ (w[:, np.newaxis] * X_design)
            
            try:
                I_inv = np.linalg.pinv(I)
            except np.linalg.LinAlgError:
                break
                
            # Hat matrix diagonals h_i
            H_mat = (X_design @ I_inv) * (X_design * w[:, np.newaxis])
            h = np.sum(H_mat, axis=1)
            
            # Firth modified score vector with sample weights: g* = X^T (sw * (y - p) + h * (0.5 - p))
            modified_y = sw * (y - p) + h * (0.5 - p)
            g_star = X_design.T @ modified_y
            
            delta = I_inv @ g_star
            beta += delta
            
            if np.max(np.abs(delta)) < self.tol:
                break
                
        self.intercept_ = beta[0]
        self.coef_      = beta[1:]
        return self

    def predict_proba(self, X):
        z = X @ self.coef_ + self.intercept_
        p = self._sigmoid(z)
        return np.column_stack([1.0 - p, p])

years = sorted(df['year'].unique())

df['oof_p_def']   = 0.0
df['oof_p_firth_unw'] = 0.0
df['oof_p_firth_w']   = 0.0

for test_year in years:
    train_df = df[df['year'] != test_year]
    test_df  = df[df['year'] == test_year]
    test_idx = test_df.index
    
    y_train = train_df['Outbreak status'].values
    y_test  = test_df['Outbreak status'].values
    
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(train_df[features].values)
    X_te_s = scaler.transform(test_df[features].values)
    
    # 1. Default L2 Baseline
    lr_def = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr_def.fit(X_tr_s, y_train)
    df.loc[test_idx, 'oof_p_def'] = lr_def.predict_proba(X_te_s)[:, 1]
    
    # 2. Unweighted Firth
    firth_unw = WeightedFirthLogisticRegression()
    firth_unw.fit(X_tr_s, y_train)
    df.loc[test_idx, 'oof_p_firth_unw'] = firth_unw.predict_proba(X_te_s)[:, 1]
    
    # 3. Balanced Class-Weighted Firth
    n_neg = np.sum(y_train == 0)
    n_pos = np.sum(y_train == 1)
    sw = np.where(y_train == 1, len(y_train) / (2.0 * n_pos), len(y_train) / (2.0 * n_neg))
    
    firth_w = WeightedFirthLogisticRegression()
    firth_w.fit(X_tr_s, y_train, sample_weight=sw)
    df.loc[test_idx, 'oof_p_firth_w'] = firth_w.predict_proba(X_te_s)[:, 1]

print("=== BASELINE INTEGRITY CHECK ACROSS 5 FOLDS ===")
for yr in years:
    sub_y = df[df['year'] == yr]['Outbreak status'].values
    p_def = df[df['year'] == yr]['oof_p_def'].values
    p_fun = df[df['year'] == yr]['oof_p_firth_unw'].values
    p_fw  = df[df['year'] == yr]['oof_p_firth_w'].values
    
    auc_def = roc_auc_score(sub_y, p_def) if len(np.unique(sub_y)) > 1 else 0.5
    auc_fun = roc_auc_score(sub_y, p_fun) if len(np.unique(sub_y)) > 1 else 0.5
    auc_fw  = roc_auc_score(sub_y, p_fw) if len(np.unique(sub_y)) > 1 else 0.5
    
    print(f"Year {yr}: Default L2 ROC = {auc_def:.4f} | Unweighted Firth ROC = {auc_fun:.4f} | Weighted Firth ROC = {auc_fw:.4f}")

# Bootstrap Significance Test on Active Years (2020, 2021, 2023)
sub_active = df[df['year'].isin([2020, 2021, 2023])]
y_act = sub_active['Outbreak status'].values
p_def_act = sub_active['oof_p_def'].values
p_fw_act  = sub_active['oof_p_firth_w'].values

np.random.seed(42)
diffs_w = []
for _ in range(1000):
    idx = np.random.choice(len(y_act), size=len(y_act), replace=True)
    if len(np.unique(y_act[idx])) > 1:
        diffs_w.append(roc_auc_score(y_act[idx], p_fw_act[idx]) - roc_auc_score(y_act[idx], p_def_act[idx]))

diffs_w = np.array(diffs_w)
print("\n=== CLASS-WEIGHTED FIRTH VS DEFAULT BASELINE (ACTIVE YEARS N=900) ===")
print(f"Mean ROC Gain: {np.mean(diffs_w):+.4f} | 95% CI: [{np.percentile(diffs_w, 2.5):+.4f}, {np.percentile(diffs_w, 97.5):+.4f}] | p-val: {np.mean(diffs_w <= 0):.4f}")
