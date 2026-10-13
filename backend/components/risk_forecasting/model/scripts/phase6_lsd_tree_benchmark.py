"""
Step 4: Phase 6 — Empirical Tree Model Benchmark for LSD
=========================================================
Trains and benchmarks 5 classifiers under class weighting on LSD dataset:
  1. Logistic Regression (class_weight='balanced')
  2. Random Forest (class_weight='balanced')
  3. XGBoost (scale_pos_weight=12.0)
  4. LightGBM (is_unbalance=True)
  5. CatBoost (auto_class_weights='Balanced')

Evaluates out-of-fold metrics across 5 LOYO folds (2020-2024) using 27 features (Base + Spatial).
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, average_precision_score

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')

df = pd.read_csv(DATA_PATH)
print("=== STEP 4: PHASE 6 EMPIRICAL TREE MODEL BENCHMARK (LSD) ===")
print(f"Loaded LSD dataset: {df.shape[0]} rows x {df.shape[1]} columns")

features = [
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

years = sorted(df['year'].unique())

models = {
    'Logistic Regression': LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42),
    'Random Forest': RandomForestClassifier(n_estimators=100, class_weight='balanced', max_depth=5, random_state=42),
    'XGBoost': XGBClassifier(n_estimators=100, scale_pos_weight=12.0, max_depth=3, learning_rate=0.05, random_state=42, eval_metric='logloss'),
    'LightGBM': LGBMClassifier(n_estimators=100, is_unbalance=True, max_depth=3, learning_rate=0.05, random_state=42, verbose=-1),
    'CatBoost': CatBoostClassifier(iterations=100, auto_class_weights='Balanced', depth=4, learning_rate=0.05, random_state=42, verbose=0)
}

results = {m_name: {'precision': [], 'recall': [], 'f1': [], 'roc_auc': [], 'pr_auc': []} for m_name in models}

for test_year in years:
    train_df = df[df['year'] != test_year]
    test_df  = df[df['year'] == test_year]
    
    X_train = train_df[features].values
    y_train = train_df['Outbreak status'].values
    X_test  = test_df[features].values
    y_test  = test_df['Outbreak status'].values
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)
    
    for name, model in models.items():
        # Fit model
        if name in ['Logistic Regression']:
            model.fit(X_train_scaled, y_train)
            p_test = model.predict_proba(X_test_scaled)[:, 1]
        else:
            model.fit(X_train, y_train)
            p_test = model.predict_proba(X_test)[:, 1]
            
        y_pred = (p_test >= 0.50).astype(int)
        
        results[name]['precision'].append(precision_score(y_test, y_pred, zero_division=0))
        results[name]['recall'].append(recall_score(y_test, y_pred, zero_division=0))
        results[name]['f1'].append(f1_score(y_test, y_pred, zero_division=0))
        results[name]['roc_auc'].append(roc_auc_score(y_test, p_test) if len(np.unique(y_test)) > 1 else 0.5)
        results[name]['pr_auc'].append(average_precision_score(y_test, p_test) if len(np.unique(y_test)) > 1 else np.mean(y_test))

summary_rows = []
for name, metrics in results.items():
    summary_rows.append({
        'Model': name,
        'Precision': f"{np.mean(metrics['precision']):.4f} +/- {np.std(metrics['precision']):.4f}",
        'Recall': f"{np.mean(metrics['recall']):.4f} +/- {np.std(metrics['recall']):.4f}",
        'F1-Score': f"{np.mean(metrics['f1']):.4f} +/- {np.std(metrics['f1']):.4f}",
        'ROC-AUC': f"{np.mean(metrics['roc_auc']):.4f} +/- {np.std(metrics['roc_auc']):.4f}",
        'PR-AUC': f"{np.mean(metrics['pr_auc']):.4f} +/- {np.std(metrics['pr_auc']):.4f}"
    })

df_summary = pd.DataFrame(summary_rows)
print("\n=== PHASE 6 TREE ENSEMBLE BENCHMARK SUMMARY (5 LOYO FOLDS: 2020-2024) ===")
print(df_summary.to_string(index=False))
