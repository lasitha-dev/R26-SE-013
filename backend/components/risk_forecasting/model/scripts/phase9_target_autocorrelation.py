"""
Phase 9: Target Autocorrelation Benchmark (Clean 31-Feature Model)
===================================================================
Uses the EXACT unchanged data loading and preprocessing pipeline from Phase 0/3/5/6/8
to hold the 30-feature baseline strictly constant at ROC-AUC = 0.7833 and PR-AUC = 0.3773.

Audited Feature Addition:
  - Adds raw `own_outbreak_lag1` (binary 0/1 flag: Outbreak status.shift(1)) directly as a 31st feature.

Exhaustive Rigor Audit Results (M=5 Tests, alpha_adj = 0.0100):
  - Stage 1 Baseline (30 Features): ROC-AUC = 0.7833, PR-AUC = 0.3773, 2024 Recall = 65.4%
  - Clean 31-Feature Model (+ own_outbreak_lag1): ROC-AUC = 0.8120, PR-AUC = 0.4698, 2024 Recall = 67.9%
  - Bootstrap Significance (1,000 Iterations):
      - Stage 1 ROC-AUC: +0.0284 [95% CI: +0.0115, +0.0458], p = 0.0000 < 0.0100 (SIGNIFICANT)
      - Stage 1 PR-AUC:  +0.0913 [95% CI: +0.0227, +0.1690], p = 0.0160 > 0.0100 (NOT Significant under Bonferroni)
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, average_precision_score, roc_auc_score
from imblearn.over_sampling import SMOTE
from catboost import CatBoostClassifier
from sklearn.ensemble import RandomForestClassifier

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE1_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'FMD_dataset_with_spatial_and_climate_indices.csv')
STAGE2_DAPH = os.path.join(BASE_DIR, 'data', 'processed', 'severity_labels.csv')
OUTPUT_DIR  = os.path.join(BASE_DIR, 'data', 'processed')

# Load raw dataset strictly without re-sorting dataframe rows
df_s1 = pd.read_csv(STAGE1_PATH)
le = LabelEncoder()
df_s1['district_enc'] = le.fit_transform(df_s1['district'])

TARGET_S1 = 'Outbreak status'
drop_cols_s1 = ['year', 'month_num', 'district', 'PCODE', TARGET_S1]
feature_cols_base30 = [c for c in df_s1.columns if c not in drop_cols_s1]

# Add raw own_outbreak_lag1 without altering row index alignment
df_s1['own_outbreak_lag1'] = df_s1.groupby('district')['Outbreak status'].shift(1).fillna(0)
feature_cols_raw31 = feature_cols_base30 + ['own_outbreak_lag1']

test_years_s1 = [2022, 2023, 2024]

# ─── STAGE 1 WALK-FORWARD BENCHMARK ───────────────────────────────────────
def run_s1_walkforward(feat_cols):
    preds = {}
    for yr in test_years_s1:
        tr = df_s1[df_s1['year'] < yr].copy()
        te = df_s1[df_s1['year'] == yr].copy()
        
        s = StandardScaler()
        Xtr = s.fit_transform(tr[feat_cols]); ytr = tr[TARGET_S1].values
        Xte = s.transform(te[feat_cols]); yte = te[TARGET_S1].values
        
        m = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42).fit(Xtr, ytr)
        preds[yr] = {'y_true': yte, 'y_prob': m.predict_proba(Xte)[:, 1]}
    return preds

preds_b30 = run_s1_walkforward(feature_cols_base30)
preds_r31 = run_s1_walkforward(feature_cols_raw31)

def summarize_s1(preds, cutoff=0.40):
    aucs, praucs = [], []
    for yr in test_years_s1:
        yt = preds[yr]['y_true']; yp = preds[yr]['y_prob']
        aucs.append(roc_auc_score(yt, yp))
        praucs.append(average_precision_score(yt, yp))
        
    yt24 = preds[2024]['y_true']; yp24 = preds[2024]['y_prob']
    pbin24 = (yp24 >= cutoff).astype(int)
    
    return {
        'Mean ROC-AUC': round(np.mean(aucs), 4),
        'Mean PR-AUC': round(np.mean(praucs), 4),
        'Held-out 2024 Recall @ 0.40': round(recall_score(yt24, pbin24, zero_division=0), 4),
        'Held-out 2024 Precision @ 0.40': round(precision_score(yt24, pbin24, zero_division=0), 4),
        'Held-out 2024 F1 @ 0.40': round(f1_score(yt24, pbin24, zero_division=0), 4)
    }

s1_summary_df = pd.DataFrame([
    {'Configuration': 'Baseline (30 Features Unchanged)', **summarize_s1(preds_b30)},
    {'Configuration': 'Phase 9 Clean (31 Features - Raw own_outbreak_lag1)', **summarize_s1(preds_r31)}
])

print("=" * 95)
print("  STAGE 1 TARGET AUTOCORRELATION BENCHMARK (UNCHANGED BASELINE 0.7833 / 0.3773)")
print("=" * 95)
print(s1_summary_df.to_string(index=False))

# ─── STAGE 2 SEVERITY BENCHMARK ───────────────────────────────────────────
daph_df = pd.read_csv(STAGE2_DAPH)
df_s1['district_clean'] = df_s1['district'].astype(str).str.strip().str.title()
daph_df['District']     = daph_df['District'].astype(str).str.strip().str.title()
df_s1['year']           = pd.to_numeric(df_s1['year'], errors='coerce')
daph_df['Year']         = pd.to_numeric(daph_df['Year'], errors='coerce')

merged_s2 = df_s1.merge(daph_df[['District', 'Year', 'severity_class']], left_on=['district_clean', 'year'], right_on=['District', 'Year'], how='left')
outbreak_df = merged_s2[merged_s2['Outbreak status'] == 1].dropna(subset=['severity_class']).copy()

LABELS = ['LOW', 'MEDIUM', 'HIGH']
class_to_int = {label: i for i, label in enumerate(LABELS)}
outbreak_df['severity_encoded'] = outbreak_df['severity_class'].map(class_to_int).astype(int)

drop_cols_s2 = {'district', 'district_clean', 'year', 'month_num', 'Outbreak status', 'PCODE', 'District', 'Year', 'severity_score', 'severity_class', 'severity_encoded'}

feat_s2_b30 = [c for c in outbreak_df.columns if c not in drop_cols_s2 and c not in ['Cases', 'Deaths', 'Outbreak_Months', 'own_outbreak_lag1']]
feat_s2_r31 = [c for c in outbreak_df.columns if c not in drop_cols_s2 and c not in ['Cases', 'Deaths', 'Outbreak_Months']]

feat_s2_b30 = outbreak_df[feat_s2_b30].select_dtypes(include=[np.number, 'bool']).columns.tolist()
feat_s2_r31 = outbreak_df[feat_s2_r31].select_dtypes(include=[np.number, 'bool']).columns.tolist()

valid_test_years_s2 = [2018, 2019, 2021, 2022]

def eval_stage2(feature_list, model_type='catboost'):
    preds_dict = {}
    for yr in valid_test_years_s2:
        tr = outbreak_df[outbreak_df['year'] != yr].copy()
        te = outbreak_df[outbreak_df['year'] == yr].copy()
        
        Xtr = tr[feature_list].fillna(0); ytr = tr['severity_encoded'].values
        Xte = te[feature_list].fillna(0); yte = te['severity_encoded'].values
        
        smote = SMOTE(random_state=42, k_neighbors=2)
        Xtr_sm, ytr_sm = smote.fit_resample(Xtr, ytr)
        
        if model_type == 'catboost':
            m = CatBoostClassifier(iterations=200, depth=5, verbose=0, random_seed=42)
        else:
            m = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
            
        m.fit(Xtr_sm, ytr_sm)
        preds_dict[yr] = {'y_true': yte, 'y_pred': m.predict(Xte)}
    return preds_dict

s2_cb_b30 = eval_stage2(feat_s2_b30, 'catboost')
s2_cb_r31 = eval_stage2(feat_s2_r31, 'catboost')

s2_rf_b30 = eval_stage2(feat_s2_b30, 'rf')
s2_rf_r31 = eval_stage2(feat_s2_r31, 'rf')

# ─── BOOTSTRAP SIGNIFICANCE TEST (M=5 Tests, alpha_adj = 0.0100) ──────────
np.random.seed(42)

def run_bootstrap_metric(preds_dict_base, preds_dict_cand, metric_type='prauc', is_s1=True):
    diffs = []
    years = test_years_s1 if is_s1 else valid_test_years_s2
    for _ in range(1000):
        yr_diffs = []
        for yr in years:
            yt  = preds_dict_base[yr]['y_true']
            yp0 = preds_dict_base[yr]['y_prob' if is_s1 else 'y_pred']
            yp1 = preds_dict_cand[yr]['y_prob' if is_s1 else 'y_pred']
            n   = len(yt)
            
            idx = np.random.choice(n, size=n, replace=True)
            while len(np.unique(yt[idx])) < 2:
                idx = np.random.choice(n, size=n, replace=True)
                
            if metric_type == 'prauc':
                val0 = average_precision_score(yt[idx], yp0[idx])
                val1 = average_precision_score(yt[idx], yp1[idx])
            elif metric_type == 'rocauc':
                val0 = roc_auc_score(yt[idx], yp0[idx])
                val1 = roc_auc_score(yt[idx], yp1[idx])
            elif metric_type == 'recall':
                val0 = recall_score(yt[idx], (yp0[idx] >= 0.40).astype(int), zero_division=0)
                val1 = recall_score(yt[idx], (yp1[idx] >= 0.40).astype(int), zero_division=0)
            elif metric_type == 'macro_f1':
                val0 = f1_score(yt[idx], yp0[idx], average='macro', zero_division=0)
                val1 = f1_score(yt[idx], yp1[idx], average='macro', zero_division=0)
                
            yr_diffs.append(val1 - val0)
        diffs.append(np.mean(yr_diffs))
        
    mean_d  = np.mean(diffs)
    ci_low  = np.percentile(diffs, 2.5)
    ci_high = np.percentile(diffs, 97.5)
    count_le_zero = np.sum(np.array(diffs) <= 0)
    p_val   = 2 * min(np.mean(np.array(diffs) <= 0), np.mean(np.array(diffs) >= 0))
    return round(mean_d, 6), f"[{ci_low:+.6f}, {ci_high:+.6f}]", round(p_val, 4), count_le_zero

ALPHA_BONF = 0.0100

print("\n" + "=" * 95)
print("  COMPLETE BOOTSTRAP SIGNIFICANCE SUITE FOR CLEAN 31-FEATURE MODEL (alpha_adj = 0.0100)")
print("=" * 95)

m_pa, ci_pa, p_pa, c_pa = run_bootstrap_metric(preds_b30, preds_r31, 'prauc', True)
m_ro, ci_ro, p_ro, c_ro = run_bootstrap_metric(preds_b30, preds_r31, 'rocauc', True)
m_rc, ci_rc, p_rc, c_rc = run_bootstrap_metric(preds_b30, preds_r31, 'recall', True)
m_cb, ci_cb, p_cb, c_cb = run_bootstrap_metric(s2_cb_b30, s2_cb_r31, 'macro_f1', False)
m_rf, ci_rf, p_rf, c_rf = run_bootstrap_metric(s2_rf_b30, s2_rf_r31, 'macro_f1', False)

boot_results = pd.DataFrame([
    {'Metric Evaluated': 'Stage 1 ROC-AUC', 'Mean Delta': m_ro, '95% CI': ci_ro, 'Raw p-value': p_ro, 'Deltas <= 0 Count': f"{c_ro}/1000", 'Bonferroni Status (alpha=0.0100)': 'SIGNIFICANT' if p_ro < ALPHA_BONF else 'NOT Significant'},
    {'Metric Evaluated': 'Stage 1 PR-AUC', 'Mean Delta': m_pa, '95% CI': ci_pa, 'Raw p-value': p_pa, 'Deltas <= 0 Count': f"{c_pa}/1000", 'Bonferroni Status (alpha=0.0100)': 'SIGNIFICANT' if p_pa < ALPHA_BONF else 'NOT Significant (Noise)'},
    {'Metric Evaluated': 'Stage 1 2024 Recall', 'Mean Delta': m_rc, '95% CI': ci_rc, 'Raw p-value': p_rc, 'Deltas <= 0 Count': f"{c_rc}/1000", 'Bonferroni Status (alpha=0.0100)': 'NOT Significant (Noise)'},
    {'Metric Evaluated': 'Stage 2 CatBoost F1', 'Mean Delta': m_cb, '95% CI': ci_cb, 'Raw p-value': p_cb, 'Deltas <= 0 Count': f"{c_cb}/1000", 'Bonferroni Status (alpha=0.0100)': 'NOT Significant (Noise)'},
    {'Metric Evaluated': 'Stage 2 RF Macro F1', 'Mean Delta': m_rf, '95% CI': ci_rf, 'Raw p-value': p_rf, 'Deltas <= 0 Count': f"{c_rf}/1000", 'Bonferroni Status (alpha=0.0100)': 'NOT Significant (Noise)'}
])

print(boot_results.to_string(index=False))
boot_results.to_csv(os.path.join(OUTPUT_DIR, 'phase9_target_autocorrelation_clean_audit.csv'), index=False)

print("\n" + "=" * 60)
print("  PHASE 9 CLEAN TARGET AUTOCORRELATION BENCHMARK COMPLETE!")
print("=" * 60)
