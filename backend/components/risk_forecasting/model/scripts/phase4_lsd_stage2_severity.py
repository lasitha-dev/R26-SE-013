"""
Phase B3: Stage 2 Severity Modeling (Binary LOW vs MODERATE/HIGH) for LSD
==========================================================================
Builds and evaluates Stage 2 binary outbreak severity classification on N=56 
event records using expanding-window forward temporal cross-validation:
  - Class 0 (LOW Severity): Cases <= 57.0 (N=19)
  - Class 1 (MODERATE/HIGH Severity): Cases > 57.0 (N=37)

Fits SMOTE oversampling strictly inside training folds to prevent temporal leakage.
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from lightgbm import LGBMClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from imblearn.over_sampling import SMOTE

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')
SEV_PATH  = os.path.join(BASE_DIR, 'data', 'raw', 'daph', 'LSD_District_Year_Cases_Deaths.csv')

df_grid = pd.read_csv(DATA_PATH)
df_sev  = pd.read_csv(SEV_PATH)

print("=== PHASE B3: STAGE 2 BINARY SEVERITY MODELING (LOW vs MOD/HIGH) ===")

# Standardise names
df_grid['district'] = df_grid['district'].replace({'Moneragala': 'Monaragala', 'NuwaraEliya': 'Nuwara Eliya'})
df_sev['District']  = df_sev['District'].replace({'Moneragala': 'Monaragala', 'NuwaraEliya': 'Nuwara Eliya'})

# Dynamic own_outbreak_lag1 generation
df_grid['date'] = pd.to_datetime(df_grid['date'])
df_grid = df_grid.sort_values(['district', 'date']).reset_index(drop=True)
if 'own_outbreak_lag1' not in df_grid.columns:
    df_grid['own_outbreak_lag1'] = df_grid.groupby('district')['Outbreak status'].shift(1).fillna(0.0)

# Compute annual aggregated features per district-year
features = [
    'rainfall_mm', 'r3h', 'rfq', 'rain_lag1', 'rain_lag2', 'rfq_lag1',
    'humidity', 'wind_speed', 'temp_lag1', 'humidity_lag1', 'wind_lag1',
    'buffalo_density', 'livestock_density',
    'nino34', 'nino34_lag3', 'iod_dmi', 'iod_dmi_lag2',
    'neighbor_outbreak_lag1', 'neighbor_outbreak_count_lag1',
    'neighbor_outbreak_fraction_lag1', 'neighbor_outbreak_lag2',
    'own_outbreak_lag1'
]

df_annual_feats = df_grid.groupby(['district', 'year'])[features].mean().reset_index()

# Merge with severity dataset
df_merged = pd.merge(df_sev, df_annual_feats, left_on=['District', 'Year'], right_on=['district', 'year'], how='inner')

# Pure case cutoff (33.3rd percentile = 57.0)
df_merged['severity_class'] = (df_merged['Cases'] > 57.0).astype(int)

print(f"Merged Severity Event Dataset: {len(df_merged)} records across 2020-2024")
print("Target Distribution:")
print(f"  Class 0 (LOW Severity):           {np.sum(df_merged['severity_class'] == 0)} records ({np.mean(df_merged['severity_class'] == 0)*100:.1f}%)")
print(f"  Class 1 (MODERATE/HIGH Severity): {np.sum(df_merged['severity_class'] == 1)} records ({np.mean(df_merged['severity_class'] == 1)*100:.1f}%)")

test_years = [2022, 2023, 2024]

models = {
    'Logistic Regression (SMOTE)': LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42),
    'Random Forest (SMOTE)': RandomForestClassifier(n_estimators=50, max_depth=3, class_weight='balanced', random_state=42),
    'LightGBM (SMOTE)': LGBMClassifier(n_estimators=50, max_depth=3, is_unbalance=True, random_state=42, verbose=-1)
}

results = {m: {'acc': [], 'prec': [], 'rec': [], 'f1': [], 'auc': []} for m in models}

print("\n=== EXPANDING-WINDOW FORWARD CV PER-FOLD BREAKDOWN ===")

for test_year in test_years:
    train_df = df_merged[df_merged['Year'] < test_year]
    test_df  = df_merged[df_merged['Year'] == test_year]
    
    if len(test_df) == 0:
        continue
        
    X_train = train_df[features].values
    y_train = train_df['severity_class'].values
    X_test  = test_df[features].values
    y_test  = test_df['severity_class'].values
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)
    
    # Apply SMOTE strictly inside training fold if minority class has >= 2 samples
    if len(np.unique(y_train)) > 1 and np.min(np.bincount(y_train)) >= 2:
        smote = SMOTE(random_state=42, k_neighbors=min(2, np.min(np.bincount(y_train)) - 1))
        X_tr_res, y_tr_res = smote.fit_resample(X_train_scaled, y_train)
    else:
        X_tr_res, y_tr_res = X_train_scaled, y_train
        
    print(f"\nFold Test Year {test_year}: Train N={len(train_df)} (SMOTE Resampled N={len(X_tr_res)}) | Test N={len(test_df)} (Positives N_pos={np.sum(y_test)})")
    
    for m_name, model in models.items():
        model.fit(X_tr_res, y_tr_res)
        p_test = model.predict_proba(X_test_scaled)[:, 1]
        y_pred = (p_test >= 0.50).astype(int)
        
        acc  = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec  = recall_score(y_test, y_pred, zero_division=0)
        f1   = f1_score(y_test, y_pred, zero_division=0)
        auc  = roc_auc_score(y_test, p_test) if len(np.unique(y_test)) > 1 else 0.5
        
        results[m_name]['acc'].append(acc)
        results[m_name]['prec'].append(prec)
        results[m_name]['rec'].append(rec)
        results[m_name]['f1'].append(f1)
        results[m_name]['auc'].append(auc)
        
        print(f"  {m_name:28s} | Acc={acc*100:5.1f}% | Prec={prec:.4f} | Rec={rec*100:5.1f}% | F1={f1:.4f} | ROC={auc:.4f}")

# Summary Table
summary_rows = []
for m_name, metrics in results.items():
    summary_rows.append({
        'Stage 2 Model': m_name,
        'Mean Accuracy': f"{np.mean(metrics['acc'])*100:.2f}%",
        'Mean Precision': f"{np.mean(metrics['prec']):.4f}",
        'Mean Recall': f"{np.mean(metrics['rec'])*100:.2f}%",
        'Mean F1-Score': f"{np.mean(metrics['f1']):.4f}",
        'Mean ROC-AUC': f"{np.mean(metrics['auc']):.4f}"
    })

df_summary = pd.DataFrame(summary_rows)
print("\n=== STAGE 2 BINARY SEVERITY MODEL BENCHMARK SUMMARY (HELD-OUT EVALUATION) ===")
print(df_summary.to_string(index=False))
