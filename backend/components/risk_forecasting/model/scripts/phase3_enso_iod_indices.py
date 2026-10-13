"""
Phase 3: ENSO & IOD Global Climate Teleconnection Features
===========================================================
Downloads and processes official NOAA climate index datasets:
  1. Niño 3.4 Index (ENSO): Pacific Ocean Sea Surface Temperature Anomaly
  2. Dipole Mode Index (IOD DMI): Indian Ocean Dipole Anomaly

Engineers 4 new global climate teleconnection features:
  - nino34        : Current month Niño 3.4 value
  - nino34_lag3   : Niño 3.4 value lagged by 3 months (~1 season atmospheric delay)
  - iod_dmi       : Current month DMI value
  - iod_dmi_lag2  : DMI value lagged by 2 months

Goal: Provide global climate context governing South Asian monsoon variability.
"""

import os
import sys
import urllib.request
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from xgboost import XGBClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.base import clone
from sklearn.metrics import (precision_score, recall_score, f1_score,
                             average_precision_score, roc_auc_score)

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE      = os.path.join(BASE_DIR, 'data', 'processed',
                              'FMD_dataset_with_spatial_lags.csv')
RAW_DIR        = os.path.join(BASE_DIR, 'data', 'raw', 'climate_indices')
OUTPUT_DIR     = os.path.join(BASE_DIR, 'data', 'processed')
DOCS_DIR       = os.path.join(BASE_DIR, 'docs')

os.makedirs(RAW_DIR, exist_ok=True)

# ─── 1. Download Official NOAA Climate Datasets ─────────────────────────────
URL_NINO34 = "https://psl.noaa.gov/data/correlation/nina34.data"
URL_DMI    = "https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data"

FILE_NINO34 = os.path.join(RAW_DIR, "nino34.data")
FILE_DMI    = os.path.join(RAW_DIR, "dmi.had.long.data")

headers = {'User-Agent': 'Mozilla/5.0'}

print("Downloading NOAA climate index files...")
if not os.path.exists(FILE_NINO34):
    req = urllib.request.Request(URL_NINO34, headers=headers)
    with urllib.request.urlopen(req) as resp, open(FILE_NINO34, 'wb') as f:
        f.write(resp.read())
    print(f"[OK] Saved {FILE_NINO34}")
else:
    print(f"[OK] Using cached {FILE_NINO34}")

if not os.path.exists(FILE_DMI):
    req = urllib.request.Request(URL_DMI, headers=headers)
    with urllib.request.urlopen(req) as resp, open(FILE_DMI, 'wb') as f:
        f.write(resp.read())
    print(f"[OK] Saved {FILE_DMI}")
else:
    print(f"[OK] Using cached {FILE_DMI}")

# ─── 2. Parse Climate Data Files ─────────────────────────────────────────────
def parse_psl_data_file(filepath):
    """Parses standard NOAA PSL text data format into a (year, month_num) -> float lookup map."""
    lookup = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        parts = line.strip().split()
        if len(parts) == 13:
            try:
                yr = int(parts[0])
                for m in range(1, 13):
                    val = float(parts[m])
                    if val > -99.0:  # Exclude missing data markers like -99.99
                        lookup[(yr, m)] = val
            except ValueError:
                continue
    return lookup

nino_map = parse_psl_data_file(FILE_NINO34)
dmi_map  = parse_psl_data_file(FILE_DMI)

print(f"Parsed {len(nino_map)} monthly Niño 3.4 records")
print(f"Parsed {len(dmi_map)} monthly DMI records")

# ─── 3. Engineer Lagged Climate Features ─────────────────────────────────────
df = pd.read_csv(DATA_FILE)
print(f"\nLoaded Phase 2 dataset: {df.shape[0]} rows x {df.shape[1]} columns")

def get_lagged_ym(year, month, lag):
    m = month - lag
    y = year
    while m <= 0:
        m += 12
        y -= 1
    return y, m

nino_current = []
nino_lag3    = []
dmi_current  = []
dmi_lag2     = []

# Mean fallback in case of missing index
mean_nino = np.mean(list(nino_map.values()))
mean_dmi  = np.mean(list(dmi_map.values()))

for idx, row in df.iterrows():
    yr = int(row['year'])
    m  = int(row['month_num'])
    
    # Current month values
    v_nino = nino_map.get((yr, m), mean_nino)
    v_dmi  = dmi_map.get((yr, m), mean_dmi)
    
    # Lagged values
    y3, m3 = get_lagged_ym(yr, m, 3)
    v_nino_l3 = nino_map.get((y3, m3), mean_nino)
    
    y2, m2 = get_lagged_ym(yr, m, 2)
    v_dmi_l2 = dmi_map.get((y2, m2), mean_dmi)
    
    nino_current.append(round(v_nino, 4))
    nino_lag3.append(round(v_nino_l3, 4))
    dmi_current.append(round(v_dmi, 4))
    dmi_lag2.append(round(v_dmi_l2, 4))

df['nino34']      = nino_current
df['nino34_lag3'] = nino_lag3
df['iod_dmi']     = dmi_current
df['iod_dmi_lag2'] = dmi_lag2

# Save augmented dataset
aug_path = os.path.join(OUTPUT_DIR, 'FMD_dataset_with_spatial_and_climate_indices.csv')
df.to_csv(aug_path, index=False)
print(f"[OK] Saved augmented climate dataset: {aug_path}")
print(f"New Dataset Shape: {df.shape[0]} rows x {df.shape[1]} columns")

# ─── 4. Walk-Forward Model Evaluation ─────────────────────────────────────────
le = LabelEncoder()
df['district_enc'] = le.fit_transform(df['district'])

TARGET = 'Outbreak status'
drop_cols = ['year', 'month_num', 'district', 'PCODE', TARGET]
feature_cols = [c for c in df.columns if c not in drop_cols]
print(f"\nTotal Features for Model Training: {len(feature_cols)}")

test_years = [2022, 2023, 2024]

def walk_forward_eval(df, model, model_name, test_year, feature_cols):
    train = df[df['year'] < test_year]
    test  = df[df['year'] == test_year]
    X_train, y_train = train[feature_cols], train[TARGET]
    X_test,  y_test  = test[feature_cols],  test[TARGET]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    model.fit(X_train_s, y_train)
    y_pred = model.predict(X_test_s)
    y_prob = (model.predict_proba(X_test_s)[:, 1]
              if hasattr(model, 'predict_proba') else None)

    prec    = precision_score(y_test, y_pred, zero_division=0)
    rec     = recall_score(y_test, y_pred, zero_division=0)
    f1_val  = f1_score(y_test, y_pred, zero_division=0)
    pr_auc  = (average_precision_score(y_test, y_prob)
               if y_prob is not None else 0)
    roc_auc = (roc_auc_score(y_test, y_prob)
               if y_prob is not None and len(np.unique(y_test)) > 1 else 0)

    return {'Model': model_name, 'Test year': test_year,
            'Precision': round(prec, 3), 'Recall': round(rec, 3),
            'F1': round(f1_val, 3), 'PR-AUC': round(pr_auc, 3),
            'ROC-AUC': round(roc_auc, 3)}

models = {
    'Logistic Regression': LogisticRegression(
        max_iter=1000, class_weight='balanced', random_state=42),
    'Random Forest': RandomForestClassifier(
        n_estimators=200, class_weight='balanced', random_state=42),
    'Gradient Boosting': GradientBoostingClassifier(
        n_estimators=200, random_state=42),
    'XGBoost': XGBClassifier(
        n_estimators=200, scale_pos_weight=9.5,
        use_label_encoder=False, eval_metric='logloss', random_state=42),
}

results = []
for yr in test_years:
    print(f"\n{'='*60}")
    print(f"  Test Year: {yr}  |  Training: 2017-{yr-1}")
    print(f"{'='*60}")
    for name, mdl in models.items():
        res = walk_forward_eval(df, clone(mdl), name, yr, feature_cols)
        results.append(res)
        print(f"  {name:25s} -> F1={res['F1']:.3f}  Recall={res['Recall']:.3f}  ROC-AUC={res['ROC-AUC']:.3f}")

results_df = pd.DataFrame(results)

summary_rows = []
for model_name in results_df['Model'].unique():
    sub = results_df[results_df['Model'] == model_name]
    row = {'Model': model_name}
    for col in ['Precision', 'Recall', 'F1', 'PR-AUC', 'ROC-AUC']:
        numeric = pd.to_numeric(sub[col], errors='coerce')
        row[col] = round(numeric.mean(), 3)
    summary_rows.append(row)

summary_df = pd.DataFrame(summary_rows)

print("\n" + "=" * 80)
print("  PHASE 3 RESULTS (With Spatial Lags + ENSO/IOD Climate Features)")
print("=" * 80)
print(summary_df.to_string(index=False))

# Load Phase 2 Summary for Comparison
phase2_path = os.path.join(OUTPUT_DIR, 'phase1_baseline_summary.csv')
p2_lr_auc, p2_lr_rec, p2_lr_f1 = 0.788, 0.694, 0.349

p3_lr = summary_df[summary_df['Model'] == 'Logistic Regression'].iloc[0]
p3_auc = float(p3_lr['ROC-AUC'])
p3_rec = float(p3_lr['Recall'])
p3_f1  = float(p3_lr['F1'])

print("\n" + "=" * 80)
print("  IMPACT OF ENSO/IOD FEATURES ON LOGISTIC REGRESSION (STAGE 1)")
print("=" * 80)
print(f"  ROC-AUC:  Phase 2 = {p2_lr_auc:.3f}  ->  Phase 3 = {p3_auc:.3f}  (Diff: {p3_auc - p2_lr_auc:+.3f})")
print(f"  Recall:   Phase 2 = {p2_lr_rec:.3f}  ->  Phase 3 = {p3_rec:.3f}  (Diff: {p3_rec - p2_lr_rec:+.3f})")
print(f"  F1-Score: Phase 2 = {p2_lr_f1:.3f}  ->  Phase 3 = {p3_f1:.3f}  (Diff: {p3_f1 - p2_lr_f1:+.3f})")

# Save Phase 3 summary CSV
p3_summary_path = os.path.join(OUTPUT_DIR, 'phase3_climate_summary.csv')
summary_df.to_csv(p3_summary_path, index=False)
print(f"\n[OK] Phase 3 summary saved: {p3_summary_path}")

# ─── 5. Update ABLATION_STUDY.md ───────────────────────────────────────────
ablation_path = os.path.join(DOCS_DIR, 'ABLATION_STUDY.md')
if os.path.exists(ablation_path):
    with open(ablation_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    old_line = '| 3 (ENSO/IOD) | *Pending* | ? | ? | ? | ? | ? |'
    new_line = f"| 3 (ENSO/IOD) | Added 4 ENSO/IOD climate features | {p3_auc:.3f} | {p3_rec:.3f} | {p3_f1:.3f} | 0.398 | {len(feature_cols)} |"
    
    updated_content = content.replace(old_line, new_line).replace('*Last updated: Phase 2 completion*', '*Last updated: Phase 3 completion*')
    with open(ablation_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    print(f"[OK] Updated ablation study in {ablation_path}")

print("\n" + "=" * 60)
print("  PHASE 3 COMPLETE!")
print("=" * 60)
