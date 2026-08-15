"""
Phase B3 Diagnostic Audit: Stage 2 Severity Model Audit
========================================================
Comprehensive diagnostic audit addressing all 5 review points:
  1. 1,000-Iteration Bootstrap Significance Test (SMOTE vs No-SMOTE vs Always-MOD/HIGH)
  2. 2023 Fold Confusion Matrix & Specificity Analysis
  3. 2022 and 2024 Dormancy Fold Raw Predictions & Confusion Breakdown
  4. LightGBM Diagnostic Breakdown (47.78% Accuracy Analysis)
  5. Code Verification & SMOTE Synthetic Sample Count Audit
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
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from imblearn.over_sampling import SMOTE

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')
SEV_PATH  = os.path.join(BASE_DIR, 'data', 'raw', 'daph', 'LSD_District_Year_Cases_Deaths.csv')

df_grid = pd.read_csv(DATA_PATH)
df_sev  = pd.read_csv(SEV_PATH)

df_grid['district'] = df_grid['district'].replace({'Moneragala': 'Monaragala', 'NuwaraEliya': 'Nuwara Eliya'})
df_sev['District']  = df_sev['District'].replace({'Moneragala': 'Monaragala', 'NuwaraEliya': 'Nuwara Eliya'})

df_grid['date'] = pd.to_datetime(df_grid['date'])
df_grid = df_grid.sort_values(['district', 'date']).reset_index(drop=True)
if 'own_outbreak_lag1' not in df_grid.columns:
    df_grid['own_outbreak_lag1'] = df_grid.groupby('district')['Outbreak status'].shift(1).fillna(0.0)

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
df_merged = pd.merge(df_sev, df_annual_feats, left_on=['District', 'Year'], right_on=['district', 'year'], how='inner')

df_merged['severity_class'] = (df_merged['Cases'] > 57.0).astype(int)

test_years = [2022, 2023, 2024]

# Track predictions out-of-fold across all test events (N=31 total evaluation events)
eval_indices = df_merged[df_merged['Year'].isin(test_years)].index
df_eval = df_merged.loc[eval_indices].copy()

df_eval['pred_always_high'] = 1
df_eval['pred_lr_no_smote'] = 0
df_eval['pred_lr_smote']    = 0
df_eval['pred_rf_smote']    = 0
df_eval['pred_lgbm_smote']  = 0

print("=== POINT 5: SMOTE-INSIDE-FOLDS SAMPLE COUNT AUDIT ===")

for test_year in test_years:
    train_df = df_merged[df_merged['Year'] < test_year]
    test_df  = df_merged[df_merged['Year'] == test_year]
    test_idx = test_df.index
    
    X_train = train_df[features].values
    y_train = train_df['severity_class'].values
    X_test  = test_df[features].values
    y_test  = test_df['severity_class'].values
    
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_train)
    X_te_s = scaler.transform(X_test)
    
    n_neg_tr = np.sum(y_train == 0)
    n_pos_tr = np.sum(y_train == 1)
    
    if len(np.unique(y_train)) > 1 and np.min(np.bincount(y_train)) >= 2:
        k_neigh = min(2, np.min(np.bincount(y_train)) - 1)
        smote = SMOTE(random_state=42, k_neighbors=k_neigh)
        X_tr_res, y_tr_res = smote.fit_resample(X_tr_s, y_train)
        n_res = len(X_tr_res)
        n_syn = n_res - len(X_train)
    else:
        X_tr_res, y_tr_res = X_tr_s, y_train
        n_res = len(X_train)
        n_syn = 0
        
    print(f"Year {test_year} Train Set: Real N={len(train_df)} (LOW={n_neg_tr}, MOD/HIGH={n_pos_tr}) | Synthetic Generated N={n_syn} | Total SMOTE Training N={n_res}")
    
    # 1. LR No SMOTE
    lr_no_smote = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr_no_smote.fit(X_tr_s, y_train)
    df_eval.loc[test_idx, 'pred_lr_no_smote'] = (lr_no_smote.predict_proba(X_te_s)[:, 1] >= 0.50).astype(int)
    
    # 2. LR SMOTE
    lr_smote = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
    lr_smote.fit(X_tr_res, y_tr_res)
    df_eval.loc[test_idx, 'pred_lr_smote'] = (lr_smote.predict_proba(X_te_s)[:, 1] >= 0.50).astype(int)
    
    # 3. RF SMOTE
    rf_smote = RandomForestClassifier(n_estimators=50, max_depth=3, class_weight='balanced', random_state=42)
    rf_smote.fit(X_tr_res, y_tr_res)
    df_eval.loc[test_idx, 'pred_rf_smote'] = (rf_smote.predict_proba(X_te_s)[:, 1] >= 0.50).astype(int)
    
    # 4. LGBM SMOTE
    lgbm_smote = LGBMClassifier(n_estimators=50, max_depth=3, is_unbalance=True, random_state=42, verbose=-1)
    lgbm_smote.fit(X_tr_res, y_tr_res)
    df_eval.loc[test_idx, 'pred_lgbm_smote'] = (lgbm_smote.predict_proba(X_te_s)[:, 1] >= 0.50).astype(int)

print("\n" + "="*70)
print("=== POINT 2 & POINT 3: PER-FOLD CONFUSION MATRICES & RAW PREDICTIONS ===")

for test_year in test_years:
    sub = df_eval[df_eval['Year'] == test_year]
    print(f"\n--- FOLD YEAR {test_year} (Total Events N={len(sub)}) ---")
    y_true = sub['severity_class'].values
    print(f"Ground Truth Distribution: LOW (0) = {np.sum(y_true==0)}, MOD/HIGH (1) = {np.sum(y_true==1)}")
    
    for model_col in ['pred_always_high', 'pred_lr_no_smote', 'pred_lr_smote', 'pred_rf_smote', 'pred_lgbm_smote']:
        preds = sub[model_col].values
        tn, fp, fn, tp = confusion_matrix(y_true, preds, labels=[0, 1]).ravel()
        spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        acc  = accuracy_score(y_true, preds)
        
        print(f"  {model_col:20s} | TN={tn}, FP={fp}, FN={fn}, TP={tp} | Acc={acc*100:5.1f}% | Specificity(LOW)={spec*100:5.1f}% | Recall(HIGH)={rec*100:5.1f}%")

print("\n" + "="*70)
print("=== POINT 4: LIGHTGBM DIAGNOSTIC BREAKDOWN ===")
for test_year in test_years:
    sub = df_eval[df_eval['Year'] == test_year]
    print(f"Year {test_year} Raw LGBM Predictions: {sub['pred_lgbm_smote'].tolist()} vs True: {sub['severity_class'].tolist()}")

print("\n" + "="*70)
print("=== POINT 1: 1,000-ITERATION BOOTSTRAP SIGNIFICANCE TEST (N=31 EVALUATION EVENTS) ===")

np.random.seed(42)
y_true_all = df_eval['severity_class'].values
p_always   = df_eval['pred_always_high'].values
p_no_smote = df_eval['pred_lr_no_smote'].values
p_smote    = df_eval['pred_lr_smote'].values

def run_bootstrap_comp(p_candidate, p_baseline, name_candidate, name_baseline):
    n = len(y_true_all)
    diffs_acc = []
    diffs_f1  = []
    
    for _ in range(1000):
        idx = np.random.choice(n, size=n, replace=True)
        y_s = y_true_all[idx]
        pc_s = p_candidate[idx]
        pb_s = p_baseline[idx]
        
        acc_c = accuracy_score(y_s, pc_s)
        acc_b = accuracy_score(y_s, pb_s)
        diffs_acc.append(acc_c - acc_b)
        
        f1_c  = f1_score(y_s, pc_s, zero_division=0)
        f1_b  = f1_score(y_s, pb_s, zero_division=0)
        diffs_f1.append(f1_c - f1_b)
        
    diffs_acc = np.array(diffs_acc)
    diffs_f1  = np.array(diffs_f1)
    
    p_val_acc = np.mean(diffs_acc <= 0.0)
    p_val_f1  = np.mean(diffs_f1 <= 0.0)
    
    print(f"\n--- Significance Test: {name_candidate} vs. {name_baseline} ---")
    print(f"Mean Accuracy Gain: {np.mean(diffs_acc):+.4f} | 95% CI: [{np.percentile(diffs_acc, 2.5):+.4f}, {np.percentile(diffs_acc, 97.5):+.4f}] | p-value: {p_val_acc:.4f} ({np.sum(diffs_acc <= 0)} / 1000 <= 0)")
    print(f"Mean F1-Score Gain: {np.mean(diffs_f1):+.4f} | 95% CI: [{np.percentile(diffs_f1, 2.5):+.4f}, {np.percentile(diffs_f1, 97.5):+.4f}] | p-value: {p_val_f1:.4f} ({np.sum(diffs_f1 <= 0)} / 1000 <= 0)")

run_bootstrap_comp(p_smote, p_always, "Logistic Regression + SMOTE", "Always-MOD/HIGH Baseline")
run_bootstrap_comp(p_smote, p_no_smote, "Logistic Regression + SMOTE", "Logistic Regression WITHOUT SMOTE")
