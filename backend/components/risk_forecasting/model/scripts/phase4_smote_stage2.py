"""
Phase 4: SMOTE & ADASYN Class Imbalance Resolution for Stage 2 Severity Model
================================================================================
Stage 2 predicts outbreak severity level (LOW, MEDIUM, HIGH).
Due to severe class imbalance (only 12 HIGH severity records), the baseline Stage 2
model achieves a low Macro F1 score (0.398).

This script compares 4 sampling strategies using Leave-One-Year-Out (LOYO) CV:
  1. Baseline (No oversampling, class_weight='balanced')
  2. SMOTE (Synthetic Minority Over-sampling Technique)
  3. ADASYN (Adaptive Synthetic Sampling)
  4. SMOTE-Tomek (SMOTE + Tomek Links cleaning)

Resampling is applied STRICTLY within each training fold to prevent data leakage.
"""

import os
import sys
import re
import joblib
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from imblearn.over_sampling import SMOTE, ADASYN
from imblearn.combine import SMOTETomek

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURE_FILE   = os.path.join(BASE_DIR, 'data', 'processed',
                              'FMD_dataset_with_spatial_and_climate_indices.csv')
DAPH_FILE      = os.path.join(BASE_DIR, 'data', 'raw', 'daph',
                              'DAPH_Islandwide_FMD_Cases_2017_2024.xlsx')
OUTPUT_DIR     = os.path.join(BASE_DIR, 'data', 'processed')
MODEL_DIR      = os.path.join(BASE_DIR, 'models')
DOCS_DIR       = os.path.join(BASE_DIR, 'docs')

os.makedirs(MODEL_DIR, exist_ok=True)

# ─── 1. Load Severity Labels ────────────────────────────────────────────────
DAPH_FILE = os.path.join(BASE_DIR, 'data', 'processed', 'severity_labels.csv')
print(f"Loading severity labels: {DAPH_FILE}")
daph = pd.read_csv(DAPH_FILE)
daph['District'] = daph['District'].astype(str).str.strip().str.title()
daph['Year']     = pd.to_numeric(daph['Year'], errors='coerce')

# ─── 2. Merge Severity Labels with Feature Dataset ───────────────────────────
feat = pd.read_csv(FEATURE_FILE)
feat['district'] = feat['district'].astype(str).str.strip().str.title()
feat['year']     = pd.to_numeric(feat['year'], errors='coerce')
feat['Outbreak status'] = pd.to_numeric(feat['Outbreak status'], errors='coerce').fillna(0).astype(int)

severity_lookup = daph[['District', 'Year', 'severity_score', 'severity_class']].copy()

merged = feat.merge(
    severity_lookup,
    left_on=['district', 'year'],
    right_on=['District', 'Year'],
    how='left'
)

outbreak_df = merged[merged['Outbreak status'] == 1].dropna(subset=['severity_class']).copy()

LABELS = ['LOW', 'MEDIUM', 'HIGH']
class_to_int = {label: i for i, label in enumerate(LABELS)}
outbreak_df['severity_encoded'] = outbreak_df['severity_class'].map(class_to_int).astype(int)

# Identify feature columns
drop_cols = {'district', 'year', 'month_num', 'Outbreak status', 'PCODE',
             'District', 'Year', 'severity_score', 'severity_class', 'severity_encoded'}
candidate_cols = [c for c in outbreak_df.columns if c not in drop_cols]
FEATURE_COLS   = outbreak_df[candidate_cols].select_dtypes(include=[np.number, 'bool']).columns.tolist()
FEATURE_COLS   = [c for c in FEATURE_COLS if c not in ['Cases', 'Deaths', 'Outbreak_Months']]

print(f"Stage 2 Outbreak Dataset: {len(outbreak_df)} rows x {len(FEATURE_COLS)} features")
print("Class Distribution:\n", outbreak_df['severity_class'].value_counts().to_dict())

# ─── 3. Leave-One-Year-Out (LOYO) Resampling Comparison ────────────────────
valid_test_years = [2018, 2019, 2021, 2022]

resampling_methods = {
    'Baseline (No SMOTE)': None,
    'SMOTE': SMOTE(random_state=42, k_neighbors=2),
    'ADASYN': ADASYN(random_state=42, n_neighbors=2),
    'SMOTE-Tomek': SMOTETomek(random_state=42)
}

loyo_results = []

print("\n" + "=" * 80)
print("  LEAVE-ONE-YEAR-OUT (LOYO) SAMPLING COMPARISON FOR STAGE 2")
print("=" * 80)

for method_name, resampler in resampling_methods.items():
    f1_scores  = []
    acc_scores = []
    
    print(f"\nEvaluating: {method_name}")
    print("-" * 50)
    
    for test_year in valid_test_years:
        train = outbreak_df[outbreak_df['year'] != test_year]
        test  = outbreak_df[outbreak_df['year'] == test_year]
        
        if train.empty or test.empty or test['severity_class'].nunique() < 2:
            continue
            
        X_train = train[FEATURE_COLS].fillna(0)
        y_train = train['severity_encoded']
        X_test  = test[FEATURE_COLS].fillna(0)
        y_test  = test['severity_encoded']
        
        # Apply resampling strictly to training fold
        if resampler is not None:
            try:
                X_train_res, y_train_res = resampler.fit_resample(X_train, y_train)
            except Exception as e:
                X_train_res, y_train_res = X_train, y_train
        else:
            X_train_res, y_train_res = X_train, y_train
            
        # Train Random Forest classifier
        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_leaf=2,
            class_weight='balanced' if resampler is None else None,
            random_state=42
        )
        
        rf.fit(X_train_res, y_train_res)
        y_pred = rf.predict(X_test)
        
        acc = accuracy_score(y_test, y_pred)
        f1  = f1_score(y_test, y_pred, average='macro', zero_division=0)
        
        acc_scores.append(acc)
        f1_scores.append(f1)
        
        print(f"  Year {test_year}: Accuracy={acc:.3f}, Macro F1={f1:.3f}")
        
    mean_acc = np.mean(acc_scores)
    mean_f1  = np.mean(f1_scores)
    
    loyo_results.append({
        'Sampling Method': method_name,
        'Mean Accuracy': round(mean_acc, 3),
        'Mean Macro F1': round(mean_f1, 3)
    })
    print(f"  ==> Mean Macro F1 for {method_name}: {mean_f1:.3f}")

results_df = pd.DataFrame(loyo_results).sort_values('Mean Macro F1', ascending=False)

print("\n" + "=" * 80)
print("  STAGE 2 RESAMPLING RESULTS SUMMARY")
print("=" * 80)
print(results_df.to_string(index=False))

# Save results
csv_path = os.path.join(OUTPUT_DIR, 'stage2_smote_comparison.csv')
results_df.to_csv(csv_path, index=False)
print(f"\n[OK] Results saved: {csv_path}")

# ─── 4. Retrain Best Model on All Outbreak Data & Save ──────────────────────
best_method = results_df.iloc[0]['Sampling Method']
best_f1     = results_df.iloc[0]['Mean Macro F1']

print(f"\n[BEST STRATEGY SELECTED]: {best_method} with Macro F1 = {best_f1:.3f}")

X_all = outbreak_df[FEATURE_COLS].fillna(0)
y_all = outbreak_df['severity_encoded']

best_resampler = resampling_methods[best_method]
if best_resampler is not None:
    X_all_res, y_all_res = best_resampler.fit_resample(X_all, y_all)
else:
    X_all_res, y_all_res = X_all, y_all

final_rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    min_samples_leaf=2,
    class_weight='balanced' if best_resampler is None else None,
    random_state=42
)
final_rf.fit(X_all_res, y_all_res)

model_path = os.path.join(MODEL_DIR, 'stage2_rf_model_smote.pkl')
joblib.dump(final_rf, model_path)
print(f"[OK] Saved trained Stage 2 model: {model_path}")

# ─── 5. Update ABLATION_STUDY.md ───────────────────────────────────────────
ablation_path = os.path.join(DOCS_DIR, 'ABLATION_STUDY.md')
if os.path.exists(ablation_path):
    with open(ablation_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    old_line = '| 4 (SMOTE) | *Pending* | — | — | — | ? | — |'
    new_line = f"| 4 (SMOTE) | Applied {best_method} to Stage 2 | — | — | — | {best_f1:.3f} | {len(FEATURE_COLS)} |"
    
    updated_content = content.replace(old_line, new_line).replace('*Last updated: Phase 3 completion*', '*Last updated: Phase 4 completion*')
    with open(ablation_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    print(f"[OK] Updated ablation study in {ablation_path}")

print("\n" + "=" * 60)
print("  PHASE 4 COMPLETE!")
print("=" * 60)
