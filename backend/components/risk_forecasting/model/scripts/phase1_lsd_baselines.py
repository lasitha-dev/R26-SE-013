"""
Step 2: Phase 1 — Trivial Baseline Benchmarking vs Stage 1 Logistic Regression (LSD)
=====================================================================================
Evaluates:
  1. Always-Zero Baseline
  2. Lag-1 Persistence Baseline
  3. Stage 1 Logistic Regression (Baseline 30-feature set)

Using Leave-One-Year-Out (LOYO) Cross-Validation across 5 folds (2020-2024).
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, average_precision_score

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH   = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')

print("=== STEP 2: PHASE 1 TRIVIAL BASELINE BENCHMARKING (LSD) ===")
df = pd.read_csv(DATA_PATH)
print(f"Loaded LSD dataset: {df.shape[0]} rows x {df.shape[1]} columns")

# Base 30 features
base_features = [
    'sin_month', 'cos_month',
    'monsoon_phase_First_Inter_Monsoon', 'monsoon_phase_SW_Monsoon',
    'monsoon_phase_Second_Inter_Monsoon', 'monsoon_phase_NE_Monsoon',
    'rainfall_mm', 'r3h', 'rfq', 'rain_lag1', 'rain_lag2', 'rfq_lag1',
    'humidity', 'wind_speed', 'temp_lag1', 'humidity_lag1', 'wind_lag1',
    'buffalo_density', 'livestock_density',
    'nino34', 'nino34_lag3', 'iod_dmi', 'iod_dmi_lag2'
]

# Calculate own_outbreak_lag1 for Lag-1 Persistence baseline evaluation
df.sort_values(by=['district', 'year', 'month_num'], inplace=True)
df['own_outbreak_lag1'] = df.groupby('district')['Outbreak status'].shift(1).fillna(0.0)
df.sort_values(by=['year', 'month_num', 'district'], inplace=True)
df.reset_index(drop=True, inplace=True)

years = sorted(df['year'].unique())
print(f"LOYO Fold Years: {years}")

results = {
    'Always-Zero': {'precision': [], 'recall': [], 'f1': [], 'roc_auc': [], 'pr_auc': []},
    'Lag-1 Persistence': {'precision': [], 'recall': [], 'f1': [], 'roc_auc': [], 'pr_auc': []},
    'Logistic Regression': {'precision': [], 'recall': [], 'f1': [], 'roc_auc': [], 'pr_auc': []}
}

for test_year in years:
    train_df = df[df['year'] != test_year]
    test_df  = df[df['year'] == test_year]
    
    y_test = test_df['Outbreak status'].values
    
    # 1. Always-Zero
    y_pred_zero = np.zeros_like(y_test)
    results['Always-Zero']['precision'].append(precision_score(y_test, y_pred_zero, zero_division=0))
    results['Always-Zero']['recall'].append(recall_score(y_test, y_pred_zero, zero_division=0))
    results['Always-Zero']['f1'].append(f1_score(y_test, y_pred_zero, zero_division=0))
    results['Always-Zero']['roc_auc'].append(0.5000)
    results['Always-Zero']['pr_auc'].append(np.mean(y_test))
    
    # 2. Lag-1 Persistence
    y_pred_pers = test_df['own_outbreak_lag1'].values
    results['Lag-1 Persistence']['precision'].append(precision_score(y_test, y_pred_pers, zero_division=0))
    results['Lag-1 Persistence']['recall'].append(recall_score(y_test, y_pred_pers, zero_division=0))
    results['Lag-1 Persistence']['f1'].append(f1_score(y_test, y_pred_pers, zero_division=0))
    results['Lag-1 Persistence']['roc_auc'].append(roc_auc_score(y_test, y_pred_pers) if len(np.unique(y_test)) > 1 else 0.5)
    results['Lag-1 Persistence']['pr_auc'].append(average_precision_score(y_test, y_pred_pers) if len(np.unique(y_test)) > 1 else np.mean(y_test))
    
    # 3. Logistic Regression
    X_train = train_df[base_features].values
    y_train = train_df['Outbreak status'].values
    X_test  = test_df[base_features].values
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)
    
    lr = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr.fit(X_train_scaled, y_train)
    
    y_proba = lr.predict_proba(X_test_scaled)[:, 1]
    y_pred_lr = (y_proba >= 0.50).astype(int)
    
    results['Logistic Regression']['precision'].append(precision_score(y_test, y_pred_lr, zero_division=0))
    results['Logistic Regression']['recall'].append(recall_score(y_test, y_pred_lr, zero_division=0))
    results['Logistic Regression']['f1'].append(f1_score(y_test, y_pred_lr, zero_division=0))
    results['Logistic Regression']['roc_auc'].append(roc_auc_score(y_test, y_proba) if len(np.unique(y_test)) > 1 else 0.5)
    results['Logistic Regression']['pr_auc'].append(average_precision_score(y_test, y_proba) if len(np.unique(y_test)) > 1 else np.mean(y_test))

summary_rows = []
for model_name, metrics in results.items():
    summary_rows.append({
        'Model': model_name,
        'Precision': f"{np.mean(metrics['precision']):.4f} +/- {np.std(metrics['precision']):.4f}",
        'Recall': f"{np.mean(metrics['recall']):.4f} +/- {np.std(metrics['recall']):.4f}",
        'F1-Score': f"{np.mean(metrics['f1']):.4f} +/- {np.std(metrics['f1']):.4f}",
        'ROC-AUC': f"{np.mean(metrics['roc_auc']):.4f} +/- {np.std(metrics['roc_auc']):.4f}",
        'PR-AUC': f"{np.mean(metrics['pr_auc']):.4f} +/- {np.std(metrics['pr_auc']):.4f}"
    })

df_summary = pd.DataFrame(summary_rows)
print("\n=== PHASE 1 LOYO BENCHMARK SUMMARY (5 FOLDS: 2020-2024) ===")
print(df_summary.to_string(index=False))
