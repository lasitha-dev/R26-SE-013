"""
Phase 6: Advanced Model Benchmarking (5 Models: LR, RF, XGBoost, LightGBM, CatBoost)
===================================================================================
Comprehensive benchmark of modern gradient boosting algorithms against baselines:
  - Stage 1 Outbreak Early-Warning: Independent Per-Model Nested Threshold Optimization (tuned on 2022-2023, tested on 2024)
  - Explicit Fallback Handling: Documents models failing the >= 75% validation recall policy target at any threshold.
  - Stage 2 Severity Classifier: Random Forest, XGBoost, LightGBM, CatBoost (with SMOTE)
  - 1,000-Iteration Fold-Stratified Bootstrap Significance Tests with Bonferroni Correction (M=7 tests, alpha_adj=0.00714)
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, average_precision_score, roc_auc_score, accuracy_score
from imblearn.over_sampling import SMOTE

from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE1_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'FMD_dataset_with_spatial_and_climate_indices.csv')
STAGE2_DAPH = os.path.join(BASE_DIR, 'data', 'processed', 'severity_labels.csv')
OUTPUT_DIR  = os.path.join(BASE_DIR, 'data', 'processed')
PLOT_DIR    = os.path.join(BASE_DIR, 'plots', 'verification_comparison')
DOCS_DIR    = os.path.join(BASE_DIR, 'docs')

os.makedirs(PLOT_DIR, exist_ok=True)

# ─── 1. STAGE 1 BENCHMARK WITH PER-MODEL NESTED THRESHOLD OPTIMIZATION ───────
print("=" * 95)
print("  STAGE 1 BENCHMARK: PER-MODEL INDEPENDENT NESTED THRESHOLD OPTIMIZATION (2022-2024)")
print("=" * 95)

df_s1 = pd.read_csv(STAGE1_PATH)
le = LabelEncoder()
df_s1['district_enc'] = le.fit_transform(df_s1['district'])

TARGET_S1 = 'Outbreak status'
drop_cols_s1 = ['year', 'month_num', 'district', 'PCODE', TARGET_S1]
feature_cols_s1 = [c for c in df_s1.columns if c not in drop_cols_s1]

test_years_s1 = [2022, 2023, 2024]

# All models configured with explicit class-imbalance weighting
models_s1 = {
    'Logistic Regression': LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42),
    'Random Forest':       RandomForestClassifier(n_estimators=200, max_depth=10, class_weight='balanced', random_state=42),
    'XGBoost':             XGBClassifier(n_estimators=200, max_depth=5, scale_pos_weight=9.5, eval_metric='logloss', random_state=42),
    'LightGBM':            LGBMClassifier(n_estimators=200, max_depth=5, class_weight='balanced', min_child_samples=5, verbose=-1, random_state=42),
    'CatBoost':            CatBoostClassifier(iterations=200, depth=5, auto_class_weights='Balanced', verbose=0, random_seed=42)
}

s1_fold_preds = {name: {} for name in models_s1}

for yr in test_years_s1:
    tr = df_s1[df_s1['year'] < yr]
    te = df_s1[df_s1['year'] == yr]
    
    scaler = StandardScaler()
    X_tr = scaler.fit_transform(tr[feature_cols_s1])
    y_tr = tr[TARGET_S1].values
    X_te = scaler.transform(te[feature_cols_s1])
    y_te = te[TARGET_S1].values
    
    for name, m in models_s1.items():
        m_fit = m.fit(X_tr, y_tr)
        p_prob = m_fit.predict_proba(X_te)[:, 1]
        s1_fold_preds[name][yr] = {'y_true': y_te, 'y_prob': p_prob}

s1_summary_rows = []
for name in models_s1:
    val_y_true = np.concatenate([s1_fold_preds[name][2022]['y_true'], s1_fold_preds[name][2023]['y_true']])
    val_y_prob = np.concatenate([s1_fold_preds[name][2022]['y_prob'], s1_fold_preds[name][2023]['y_prob']])
    
    best_t = None
    best_f1 = -1.0
    max_val_rec = 0.0
    
    for t_cand in np.arange(0.05, 0.51, 0.01):
        cand_pred = (val_y_prob >= t_cand).astype(int)
        cand_rec  = recall_score(val_y_true, cand_pred, zero_division=0)
        cand_f1   = f1_score(val_y_true, cand_pred, zero_division=0)
        if cand_rec > max_val_rec:
            max_val_rec = cand_rec
        if cand_rec >= 0.75 and cand_f1 > best_f1:
            best_f1 = cand_f1
            best_t = t_cand
            
    # Check if target >= 75% validation recall was met
    target_met = (best_t is not None)
    eval_t = best_t if target_met else 0.50
    t_status = f"t={eval_t:.2f}" if target_met else f"FAILED (Max Val Rec {max_val_rec*100:.1f}%)"
    
    yt24 = s1_fold_preds[name][2024]['y_true']
    yp24 = s1_fold_preds[name][2024]['y_prob']
    
    pred24 = (yp24 >= eval_t).astype(int)
    rec24  = recall_score(yt24, pred24, zero_division=0)
    prec24 = precision_score(yt24, pred24, zero_division=0)
    f124   = f1_score(yt24, pred24, zero_division=0)
    
    mean_auc   = np.mean([roc_auc_score(s1_fold_preds[name][yr]['y_true'], s1_fold_preds[name][yr]['y_prob']) for yr in test_years_s1])
    mean_prauc = np.mean([average_precision_score(s1_fold_preds[name][yr]['y_true'], s1_fold_preds[name][yr]['y_prob']) for yr in test_years_s1])
    
    s1_summary_rows.append({
        'Model': name,
        'Mean ROC-AUC': round(mean_auc, 4),
        'Mean PR-AUC': round(mean_prauc, 4),
        'Validation Recall Target (>=75%)': t_status,
        'Held-out 2024 Recall': round(rec24, 4),
        'Held-out 2024 Precision': round(prec24, 4),
        'Held-out 2024 F1': round(f124, 4)
    })

df_s1_res = pd.DataFrame(s1_summary_rows)
print(df_s1_res.to_string(index=False))

# ─── 2. STAGE 2 BENCHMARK: OUTBREAK SEVERITY MODEL (LOYO CV with SMOTE) ─────
print("\n" + "=" * 95)
print("  STAGE 2 BENCHMARK: ALL 4 SEVERITY MODELS (LOYO CV with SMOTE)")
print("=" * 95)

daph_df = pd.read_csv(STAGE2_DAPH)
df_s1['district'] = df_s1['district'].astype(str).str.strip().str.title()
df_s1['year']     = pd.to_numeric(df_s1['year'], errors='coerce')
daph_df['District'] = daph_df['District'].astype(str).str.strip().str.title()
daph_df['Year']     = pd.to_numeric(daph_df['Year'], errors='coerce')

merged = df_s1.merge(daph_df[['District', 'Year', 'severity_class']], left_on=['district', 'year'], right_on=['District', 'Year'], how='left')
outbreak_df = merged[merged['Outbreak status'] == 1].dropna(subset=['severity_class']).copy()

LABELS = ['LOW', 'MEDIUM', 'HIGH']
class_to_int = {label: i for i, label in enumerate(LABELS)}
outbreak_df['severity_encoded'] = outbreak_df['severity_class'].map(class_to_int).astype(int)

drop_cols_s2 = {'district', 'year', 'month_num', 'Outbreak status', 'PCODE', 'District', 'Year', 'severity_score', 'severity_class', 'severity_encoded'}
candidate_cols_s2 = [c for c in outbreak_df.columns if c not in drop_cols_s2]
feature_cols_s2   = outbreak_df[candidate_cols_s2].select_dtypes(include=[np.number, 'bool']).columns.tolist()
feature_cols_s2   = [c for c in feature_cols_s2 if c not in ['Cases', 'Deaths', 'Outbreak_Months']]

valid_test_years_s2 = [2018, 2019, 2021, 2022]

models_s2 = {
    'Random Forest': RandomForestClassifier(n_estimators=200, max_depth=10, min_samples_leaf=2, random_state=42),
    'XGBoost':       XGBClassifier(n_estimators=200, max_depth=5, eval_metric='mlogloss', random_state=42),
    'LightGBM':      LGBMClassifier(n_estimators=200, max_depth=5, min_child_samples=2, verbose=-1, random_state=42),
    'CatBoost':      CatBoostClassifier(iterations=200, depth=5, verbose=0, random_seed=42)
}

s2_fold_preds = {name: {} for name in models_s2}

for yr in valid_test_years_s2:
    tr = outbreak_df[outbreak_df['year'] != yr]
    te = outbreak_df[outbreak_df['year'] == yr]
    
    Xtr = tr[feature_cols_s2].fillna(0); ytr = tr['severity_encoded'].values
    Xte = te[feature_cols_s2].fillna(0); yte = te['severity_encoded'].values
    
    smote = SMOTE(random_state=42, k_neighbors=2)
    Xtr_sm, ytr_sm = smote.fit_resample(Xtr, ytr)
    
    for name, m in models_s2.items():
        m_fit = m.fit(Xtr_sm, ytr_sm)
        p_pred = m_fit.predict(Xte)
        s2_fold_preds[name][yr] = {'y_true': yte, 'y_pred': p_pred}

s2_summary_rows = []
for name in models_s2:
    accs, f1s = [], []
    for yr in valid_test_years_s2:
        yt = s2_fold_preds[name][yr]['y_true']
        yp = s2_fold_preds[name][yr]['y_pred']
        
        accs.append(accuracy_score(yt, yp))
        f1s.append(f1_score(yt, yp, average='macro', zero_division=0))
        
    yt22 = s2_fold_preds[name][2022]['y_true']
    yp22 = s2_fold_preds[name][2022]['y_pred']
    
    s2_summary_rows.append({
        'Model': name,
        'LOYO Mean Macro F1': round(np.mean(f1s), 4),
        'LOYO Mean Accuracy': round(np.mean(accs), 4),
        'Held-out 2022 Macro F1': round(f1_score(yt22, yp22, average='macro', zero_division=0), 4),
        'Held-out 2022 Accuracy': round(accuracy_score(yt22, yp22), 4)
    })

df_s2_res = pd.DataFrame(s2_summary_rows)
print(df_s2_res.to_string(index=False))

# ─── 3. BOOTSTRAP SIGNIFICANCE TESTS WITH BONFERRONI CORRECTION ────────────
print("\n" + "=" * 95)
print("  1,000-ITERATION BOOTSTRAP SIGNIFICANCE TESTS (M=7 Tests, Bonferroni alpha_adj = 0.00714)")
print("=" * 95)

np.random.seed(42)
ALPHA_RAW = 0.05
TOTAL_TESTS = 7
ALPHA_BONF = ALPHA_RAW / TOTAL_TESTS

sig_results = []

# --- Stage 1 Comparisons vs Logistic Regression ---
base_s1_name = 'Logistic Regression'
candidates_s1 = [m for m in models_s1 if m != base_s1_name]

for cand in candidates_s1:
    boot_diffs_prauc = []
    for _ in range(1000):
        yr_prauc_diffs = []
        for yr in test_years_s1:
            yt  = s1_fold_preds[base_s1_name][yr]['y_true']
            yp0 = s1_fold_preds[base_s1_name][yr]['y_prob']
            ypC = s1_fold_preds[cand][yr]['y_prob']
            n   = len(yt)
            
            idx = np.random.choice(n, size=n, replace=True)
            while len(np.unique(yt[idx])) < 2:
                idx = np.random.choice(n, size=n, replace=True)
                
            pa0 = average_precision_score(yt[idx], yp0[idx])
            paC = average_precision_score(yt[idx], ypC[idx])
            yr_prauc_diffs.append(paC - pa0)
            
        boot_diffs_prauc.append(np.mean(yr_prauc_diffs))
        
    mean_d = np.mean(boot_diffs_prauc)
    ci_low = np.percentile(boot_diffs_prauc, 2.5)
    ci_high = np.percentile(boot_diffs_prauc, 97.5)
    p_val  = 2 * min(np.mean(np.array(boot_diffs_prauc) <= 0), np.mean(np.array(boot_diffs_prauc) >= 0))
    
    sig_bonf = "SIGNIFICANT (p < 0.00714)" if p_val < ALPHA_BONF else "NOT Significant (Noise)"
    
    sig_results.append({
        'Stage': 'Stage 1 (PR-AUC)',
        'Comparison': f'{cand} vs {base_s1_name}',
        'Mean Delta': round(mean_d, 6),
        '95% CI': f'[{ci_low:+.6f}, {ci_high:+.6f}]',
        'Raw p-value': round(p_val, 4),
        'Bonferroni Status (alpha=0.00714)': sig_bonf
    })

# --- Stage 2 Comparisons vs Random Forest ---
base_s2_name = 'Random Forest'
candidates_s2 = [m for m in models_s2 if m != base_s2_name]

for cand in candidates_s2:
    boot_diffs_f1 = []
    for _ in range(1000):
        yr_f1_diffs = []
        for yr in valid_test_years_s2:
            yt  = s2_fold_preds[base_s2_name][yr]['y_true']
            pb  = s2_fold_preds[base_s2_name][yr]['y_pred']
            pc  = s2_fold_preds[cand][yr]['y_pred']
            n   = len(yt)
            
            idx = np.random.choice(n, size=n, replace=True)
            while len(np.unique(yt[idx])) < 2:
                idx = np.random.choice(n, size=n, replace=True)
                
            f1_b = f1_score(yt[idx], pb[idx], average='macro', zero_division=0)
            f1_c = f1_score(yt[idx], pc[idx], average='macro', zero_division=0)
            yr_f1_diffs.append(f1_c - f1_b)
            
        boot_diffs_f1.append(np.mean(yr_f1_diffs))
        
    mean_d  = np.mean(boot_diffs_f1)
    ci_low  = np.percentile(boot_diffs_f1, 2.5)
    ci_high = np.percentile(boot_diffs_f1, 97.5)
    p_val   = 2 * min(np.mean(np.array(boot_diffs_f1) <= 0), np.mean(np.array(boot_diffs_f1) >= 0))
    
    sig_bonf = "SIGNIFICANT (p < 0.00714)" if p_val < ALPHA_BONF else "NOT Significant (Noise)"
    
    sig_results.append({
        'Stage': 'Stage 2 (Macro F1)',
        'Comparison': f'{cand} vs {base_s2_name}',
        'Mean Delta': round(mean_d, 6),
        '95% CI': f'[{ci_low:+.6f}, {ci_high:+.6f}]',
        'Raw p-value': round(p_val, 4),
        'Bonferroni Status (alpha=0.00714)': sig_bonf
    })

df_sig = pd.DataFrame(sig_results)
print(df_sig.to_string(index=False))

# Save Benchmark Results to CSV
df_s1_res.to_csv(os.path.join(OUTPUT_DIR, 'phase6_stage1_benchmark.csv'), index=False)
df_s2_res.to_csv(os.path.join(OUTPUT_DIR, 'phase6_stage2_benchmark.csv'), index=False)
df_sig.to_csv(os.path.join(OUTPUT_DIR, 'phase6_significance_tests.csv'), index=False)

print("\n" + "=" * 60)
print("  PHASE 6 COMPLETE!")
print("=" * 60)
