"""
Phase C: Small-Sample Model Regularization Benchmarking for LSD
================================================================
Evaluates 3 small-sample regularization techniques against the 28-feature Default Logistic Regression:
  1. L2 C-Tuned Logistic Regression (Grid search C in [1e-4..10] inside training folds)
  2. Elastic Net (L1+L2) Logistic Regression (Grid search C and l1_ratio inside training folds)
  3. Firth's Penalized Likelihood Logistic Regression (Jeffreys prior penalty 1/2 ln|I(theta)|)

Performs 1,000-iteration paired bootstrap significance tests with Bonferroni correction (M=3, alpha=0.0167).
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import roc_auc_score, average_precision_score

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')

df = pd.read_csv(DATA_PATH)
print("=== PHASE C: SMALL-SAMPLE MODEL REGULARIZATION BENCHMARKING ===")

df['date'] = pd.to_datetime(df['date'])
df = df.sort_values(['district', 'date']).reset_index(drop=True)
if 'own_outbreak_lag1' not in df.columns:
    df['own_outbreak_lag1'] = df.groupby('district')['Outbreak status'].shift(1).fillna(0.0)

# Active 28 Features
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

# Exact Firth's Penalized Logistic Regression Implementation
class FirthLogisticRegression:
    def __init__(self, max_iter=100, tol=1e-5):
        self.max_iter = max_iter
        self.tol = tol
        self.coef_ = None
        self.intercept_ = None

    def _sigmoid(self, z):
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

    def fit(self, X, y):
        n_samples, n_features = X.shape
        # Add intercept column
        X_design = np.column_stack([np.ones(n_samples), X])
        n_params = n_features + 1
        
        beta = np.zeros(n_params)
        
        for iteration in range(self.max_iter):
            p = self._sigmoid(X_design @ beta)
            w = p * (1.0 - p)
            w = np.maximum(w, 1e-5) # Numerical stability
            
            W = np.diag(w)
            # Fisher Information Matrix I = X^T W X
            I = X_design.T @ (w[:, np.newaxis] * X_design)
            
            # Inverse of Fisher Information Matrix
            try:
                I_inv = np.linalg.pinv(I)
            except np.linalg.LinAlgError:
                break
                
            # Hat matrix diagonals h_i = diag(X (X^T W X)^-1 X^T W)_i
            # h_i = sum_j (X_design @ I_inv)_ij * (X_design * w[:, None])_ij
            H_mat = (X_design @ I_inv) * (X_design * w[:, np.newaxis])
            h = np.sum(H_mat, axis=1)
            
            # Firth modified score vector: g* = X^T (y - p + h * (0.5 - p))
            modified_y = y - p + h * (0.5 - p)
            g_star = X_design.T @ modified_y
            
            # Newton-Raphson update step: delta = I_inv @ g_star
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

df['oof_p_default']   = 0.0
df['oof_p_c_tuned']   = 0.0
df['oof_p_elastic']   = 0.0
df['oof_p_firth']     = 0.0

fold_logs = []

for test_year in years:
    train_df = df[df['year'] != test_year]
    test_df  = df[df['year'] == test_year]
    test_idx = test_df.index
    
    y_train = train_df['Outbreak status'].values
    y_test  = test_df['Outbreak status'].values
    
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(train_df[features].values)
    X_te_s = scaler.transform(test_df[features].values)
    
    # 0. Default Baseline (L2 C=1.0)
    lr_def = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr_def.fit(X_tr_s, y_train)
    p_def = lr_def.predict_proba(X_te_s)[:, 1]
    df.loc[test_idx, 'oof_p_default'] = p_def
    
    # 1. Candidate 1: L2 C-Tuned (Inner CV)
    param_grid_c = {'C': [1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0]}
    grid_c = GridSearchCV(LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42),
                          param_grid_c, cv=4, scoring='roc_auc', n_jobs=1)
    grid_c.fit(X_tr_s, y_train)
    best_c_lr = grid_c.best_estimator_
    p_c_tuned = best_c_lr.predict_proba(X_te_s)[:, 1]
    df.loc[test_idx, 'oof_p_c_tuned'] = p_c_tuned
    
    # 2. Candidate 2: Elastic Net (Inner CV)
    param_grid_en = {'C': [1e-3, 1e-1, 1.0], 'l1_ratio': [0.2, 0.5, 0.8]}
    grid_en = GridSearchCV(LogisticRegression(penalty='elasticnet', solver='saga', class_weight='balanced', max_iter=1000, random_state=42),
                           param_grid_en, cv=4, scoring='roc_auc', n_jobs=1)
    grid_en.fit(X_tr_s, y_train)
    best_en_lr = grid_en.best_estimator_
    p_elastic = best_en_lr.predict_proba(X_te_s)[:, 1]
    df.loc[test_idx, 'oof_p_elastic'] = p_elastic
    
    # 3. Candidate 3: Firth's Penalized Likelihood
    firth = FirthLogisticRegression(max_iter=100, tol=1e-5)
    firth.fit(X_tr_s, y_train)
    p_firth = firth.predict_proba(X_te_s)[:, 1]
    df.loc[test_idx, 'oof_p_firth'] = p_firth
    
    # Evaluate fold ROC-AUC
    auc_def = roc_auc_score(y_test, p_def) if len(np.unique(y_test)) > 1 else 0.5
    auc_c   = roc_auc_score(y_test, p_c_tuned) if len(np.unique(y_test)) > 1 else 0.5
    auc_en  = roc_auc_score(y_test, p_elastic) if len(np.unique(y_test)) > 1 else 0.5
    auc_fir = roc_auc_score(y_test, p_firth) if len(np.unique(y_test)) > 1 else 0.5
    
    fold_logs.append({
        'Test Year': test_year,
        'N_pos': np.sum(y_test),
        'Default ROC': f"{auc_def:.4f}",
        'C-Tuned ROC': f"{auc_c:.4f}",
        'Best C': grid_c.best_params_['C'],
        'Elastic ROC': f"{auc_en:.4f}",
        'Best EN': f"C={grid_en.best_params_['C']}, l1={grid_en.best_params_['l1_ratio']}",
        'Firth ROC': f"{auc_fir:.4f}"
    })

print("\n=== PER-FOLD REGULARIZATION BENCHMARK BREAKDOWN ===")
print(pd.DataFrame(fold_logs).to_string(index=False))

# 1,000-Iteration Bootstrap Significance Tests against Default Baseline (M=3, alpha=0.0167)
np.random.seed(42)

def run_phaseC_bootstrap(sub_df, dataset_name):
    y_true = sub_df['Outbreak status'].values
    p_def  = sub_df['oof_p_default'].values
    p_c    = sub_df['oof_p_c_tuned'].values
    p_en   = sub_df['oof_p_elastic'].values
    p_fir  = sub_df['oof_p_firth'].values
    
    n = len(y_true)
    candidates = [
        ('L2 C-Tuned Logistic Regression', p_c),
        ('Elastic Net Logistic Regression', p_en),
        ('Firth Penalized Likelihood', p_fir)
    ]
    
    print(f"\n" + "="*70)
    print(f"=== 1,000-ITERATION BOOTSTRAP SIGNIFICANCE TESTS ({dataset_name}) ===")
    print(f"Bonferroni Adjusted Significance Threshold: alpha = 0.05 / 3 = 0.0167")
    
    for cand_name, p_cand in candidates:
        diffs_roc = []
        diffs_pr  = []
        
        for _ in range(1000):
            idx = np.random.choice(n, size=n, replace=True)
            y_s = y_true[idx]
            if len(np.unique(y_s)) > 1:
                auc_c_s = roc_auc_score(y_s, p_cand[idx])
                auc_b_s = roc_auc_score(y_s, p_def[idx])
                diffs_roc.append(auc_c_s - auc_b_s)
                
                pr_c_s = average_precision_score(y_s, p_cand[idx])
                pr_b_s = average_precision_score(y_s, p_def[idx])
                diffs_pr.append(pr_c_s - pr_b_s)
                
        diffs_roc = np.array(diffs_roc)
        diffs_pr  = np.array(diffs_pr)
        
        le0_roc = np.sum(diffs_roc <= 0.0)
        le0_pr  = np.sum(diffs_pr <= 0.0)
        
        p_val_roc = le0_roc / 1000.0
        p_val_pr  = le0_pr / 1000.0
        
        sig_str = "YES (Significant)" if p_val_roc < 0.0167 else "NO (Not Significant)"
        
        print(f"\n--- {cand_name} vs. Default Baseline ---")
        print(f"Mean ROC-AUC Gain:  {np.mean(diffs_roc):+.4f} | 95% CI: [{np.percentile(diffs_roc, 2.5):+.4f}, {np.percentile(diffs_roc, 97.5):+.4f}] | p-val: {p_val_roc:.4f} ({le0_roc}/1000 <= 0)")
        print(f"Mean PR-AUC Gain:   {np.mean(diffs_pr):+.4f} | 95% CI: [{np.percentile(diffs_pr, 2.5):+.4f}, {np.percentile(diffs_pr, 97.5):+.4f}] | p-val: {p_val_pr:.4f} ({le0_pr}/1000 <= 0)")
        print(f"Bonferroni Significant (p < 0.0167)? {sig_str}")

run_phaseC_bootstrap(df[df['year'].isin([2020, 2021, 2023])], "Active Outbreak Years Only (2020, 2021, 2023, N=900)")
run_phaseC_bootstrap(df, "Full 5-Year Dataset (2020-2024, N=1500)")
