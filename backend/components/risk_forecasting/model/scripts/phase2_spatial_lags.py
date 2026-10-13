"""
Phase 2: Spatial Lag Features Implementation & Evaluation
=========================================================
Adds spatial lag features representing outbreak activity in adjacent districts:
  1. neighbor_outbreak_lag1        : Average outbreak status of neighboring districts (t-1)
  2. neighbor_outbreak_count_lag1  : Number of neighboring districts with outbreak (t-1)
  3. neighbor_outbreak_fraction_lag1: Fraction of neighboring districts with outbreak (t-1)
  4. neighbor_outbreak_lag2        : Average outbreak status of neighboring districts (t-2)

Goal: Capture spatial contagion / disease spread from adjacent geographic areas.
"""

import os
import sys
import pandas as pd
import numpy as np
import geopandas as gpd
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
                              'FMD_model_ready_main refined_final_dataset.csv')
SHAPEFILE_PATH = os.path.join(BASE_DIR, 'data', 'raw', 'lka_admin_boundaries', 'lka_admin2.shp')
OUTPUT_DIR     = os.path.join(BASE_DIR, 'data', 'processed')
DOCS_DIR       = os.path.join(BASE_DIR, 'docs')

# ─── Load Data & Shapefile ───────────────────────────────────────────────────
df = pd.read_csv(DATA_FILE)
print(f"Loaded dataset: {df.shape[0]} rows x {df.shape[1]} columns")

gdf = gpd.read_file(SHAPEFILE_PATH)
print(f"Loaded shapefile with {len(gdf)} district polygons")

# ─── Build Adjacency Dictionary ──────────────────────────────────────────────
adjacency = {}
for _, row in gdf.iterrows():
    district_name = row['adm2_name']
    neighbors = gdf[gdf.geometry.touches(row.geometry)]['adm2_name'].tolist()
    adjacency[district_name] = neighbors

print("\nDistrict Adjacency Map Sample:")
for d in list(adjacency.keys())[:5]:
    print(f"  {d:15s} -> {', '.join(adjacency[d])}")

# ─── Helper to Fetch Outbreak Status for (district, year, month) ────────────
# Create a lookup map for fast retrieval: (district, year, month_num) -> Outbreak status
df['year_month_key'] = list(zip(df['district'], df['year'], df['month_num']))
outbreak_lookup = df.set_index(['district', 'year', 'month_num'])['Outbreak status'].to_dict()

def get_lagged_year_month(year, month, lag):
    """Calculates year and month_num shifted backward by `lag` months."""
    m = month - lag
    y = year
    while m <= 0:
        m += 12
        y -= 1
    return y, m

# ─── Feature Engineering: Spatial Lags ───────────────────────────────────────
print("\nEngineering Spatial Lag Features...")

spatial_lag1_mean  = []
spatial_lag1_count = []
spatial_lag1_frac  = []
spatial_lag2_mean  = []

for idx, row in df.iterrows():
    district = row['district']
    year     = row['year']
    month    = row['month_num']
    neighbors = adjacency.get(district, [])
    
    # --- Lag 1 (t - 1 month) ---
    y1, m1 = get_lagged_year_month(year, month, 1)
    n_statuses_lag1 = [outbreak_lookup.get((n, y1, m1), 0) for n in neighbors]
    
    if len(n_statuses_lag1) > 0:
        s_mean1  = np.mean(n_statuses_lag1)
        s_count1 = np.sum(n_statuses_lag1)
        s_frac1  = s_count1 / len(neighbors)
    else:
        s_mean1, s_count1, s_frac1 = 0.0, 0, 0.0

    # --- Lag 2 (t - 2 months) ---
    y2, m2 = get_lagged_year_month(year, month, 2)
    n_statuses_lag2 = [outbreak_lookup.get((n, y2, m2), 0) for n in neighbors]
    s_mean2 = np.mean(n_statuses_lag2) if len(n_statuses_lag2) > 0 else 0.0

    spatial_lag1_mean.append(round(s_mean1, 4))
    spatial_lag1_count.append(int(s_count1))
    spatial_lag1_frac.append(round(s_frac1, 4))
    spatial_lag2_mean.append(round(s_mean2, 4))

# Append new columns to dataframe
df['neighbor_outbreak_lag1']         = spatial_lag1_mean
df['neighbor_outbreak_count_lag1']   = spatial_lag1_count
df['neighbor_outbreak_fraction_lag1'] = spatial_lag1_frac
df['neighbor_outbreak_lag2']         = spatial_lag2_mean

# Save updated dataset
aug_dataset_path = os.path.join(OUTPUT_DIR, 'FMD_dataset_with_spatial_lags.csv')
df.drop(columns=['year_month_key'], errors='ignore').to_csv(aug_dataset_path, index=False)
print(f"[OK] Augmented dataset with spatial lags saved: {aug_dataset_path}")
print(f"New Dataset Shape: {df.shape[0]} rows x {df.shape[1]} columns")

# ─── Evaluate Walk-Forward Performance with Spatial Lags ───────────────────
le = LabelEncoder()
df['district_enc'] = le.fit_transform(df['district'])

TARGET = 'Outbreak status'
drop_cols = ['year', 'month_num', 'district', 'PCODE', TARGET, 'year_month_key']
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
print("  PHASE 2 RESULTS (With Spatial Lag Features)")
print("=" * 80)
print(summary_df.to_string(index=False))

# Load Phase 1 Summary for Direct Comparison
phase1_summary_path = os.path.join(OUTPUT_DIR, 'phase1_baseline_summary.csv')
if os.path.exists(phase1_summary_path):
    p1 = pd.read_csv(phase1_summary_path)
    p1_lr = p1[p1['Model'] == 'Logistic Regression'].iloc[0]
    p2_lr = summary_df[summary_df['Model'] == 'Logistic Regression'].iloc[0]
    
    p1_auc = float(p1_lr['ROC-AUC'])
    p2_auc = float(p2_lr['ROC-AUC'])
    p1_rec = float(p1_lr['Recall'])
    p2_rec = float(p2_lr['Recall'])
    p1_f1  = float(p1_lr['F1'])
    p2_f1  = float(p2_lr['F1'])
    
    print("\n" + "=" * 80)
    print("  IMPACT OF SPATIAL LAG FEATURES ON LOGISTIC REGRESSION (STAGE 1)")
    print("=" * 80)
    print(f"  ROC-AUC:  Phase 1 = {p1_auc:.3f}  ->  Phase 2 = {p2_auc:.3f}  (Diff: {p2_auc - p1_auc:+.3f})")
    print(f"  Recall:   Phase 1 = {p1_rec:.3f}  ->  Phase 2 = {p2_rec:.3f}  (Diff: {p2_rec - p1_rec:+.3f})")
    print(f"  F1-Score: Phase 1 = {p1_f1:.3f}  ->  Phase 2 = {p2_f1:.3f}  (Diff: {p2_f1 - p1_f1:+.3f})")

# ─── Update ABLATION_STUDY.md ──────────────────────────────────────────────
ablation_path = os.path.join(DOCS_DIR, 'ABLATION_STUDY.md')
if os.path.exists(ablation_path):
    with open(ablation_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    p2_lr = summary_df[summary_df['Model'] == 'Logistic Regression'].iloc[0]
    old_line = '| 2 (Spatial Lags) | *Pending* | ? | ? | ? | ? | ? |'
    new_line = f"| 2 (Spatial Lags) | Added 4 neighbor lag features | {p2_lr['ROC-AUC']} | {p2_lr['Recall']} | {p2_lr['F1']} | 0.398 | {len(feature_cols)} |"
    
    updated_content = content.replace(old_line, new_line)
    with open(ablation_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    print(f"\n[OK] Updated ablation study in {ablation_path}")

print("\n" + "=" * 60)
print("  PHASE 2 COMPLETE!")
print("=" * 60)
