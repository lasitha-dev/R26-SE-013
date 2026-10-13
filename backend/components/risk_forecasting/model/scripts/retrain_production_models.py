"""
Retrain Production Stage 1 (30-Feature Baseline & 31-Feature Phase 9 Variant) & Stage 2 Models.
Saves model artifacts to models/ directory for backend & Streamlit app deployment.
"""
import os
import joblib
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from imblearn.over_sampling import SMOTE

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_P3  = os.path.join(BASE_DIR, 'data', 'processed', 'FMD_dataset_with_spatial_and_climate_indices.csv')
DAPH_FILE = os.path.join(BASE_DIR, 'data', 'processed', 'severity_labels.csv')
MODEL_DIR = os.path.join(BASE_DIR, 'models')

# ─── 1. STAGE 1: 30-FEATURE PRODUCTION BASELINE ────────────────────────────
df_s1 = pd.read_csv(DATA_P3)
le_dist = LabelEncoder()
df_s1['district_enc'] = le_dist.fit_transform(df_s1['district'])

TARGET_S1 = 'Outbreak status'
drop_cols_s1 = ['year', 'month_num', 'district', 'PCODE', TARGET_S1]
feature_cols_s1 = [c for c in df_s1.columns if c not in drop_cols_s1]

print(f"Stage 1 Feature Count: {len(feature_cols_s1)}")
print(f"district_enc included: {'district_enc' in feature_cols_s1}")

# Fit on all pre-2024 data (2017-2023)
train_s1 = df_s1[df_s1['year'] < 2024]
scaler_s1 = StandardScaler()
Xtr_s1 = scaler_s1.fit_transform(train_s1[feature_cols_s1].values)
ytr_s1 = train_s1[TARGET_S1].values

model_s1 = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
model_s1.fit(Xtr_s1, ytr_s1)

# Save Stage 1 artifacts (30 features)
joblib.dump(model_s1, os.path.join(MODEL_DIR, 'stage1_lr_model.pkl'))
joblib.dump(model_s1, os.path.join(MODEL_DIR, 'final_model_stage1.pkl'))
joblib.dump(scaler_s1, os.path.join(MODEL_DIR, 'stage1_scaler.pkl'))
joblib.dump(scaler_s1, os.path.join(MODEL_DIR, 'scaler_stage1.pkl'))
joblib.dump(feature_cols_s1, os.path.join(MODEL_DIR, 'stage1_feature_cols.pkl'))

print("[OK] Saved Stage 1 production baseline artifacts (30 features).")

# ─── 1b. STAGE 1: 31-FEATURE PHASE 9 ROC-AUC OPTIMIZED MODEL ───────────────
df_s1_31 = df_s1.copy()
df_s1_31['own_outbreak_lag1'] = df_s1_31.groupby('district')['Outbreak status'].shift(1).fillna(0)
feature_cols_s1_31 = feature_cols_s1 + ['own_outbreak_lag1']

train_s1_31 = df_s1_31[df_s1_31['year'] < 2024]
scaler_s1_31 = StandardScaler()
Xtr_s1_31 = scaler_s1_31.fit_transform(train_s1_31[feature_cols_s1_31].values)
ytr_s1_31 = train_s1_31[TARGET_S1].values

model_s1_31 = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
model_s1_31.fit(Xtr_s1_31, ytr_s1_31)

joblib.dump(model_s1_31, os.path.join(MODEL_DIR, 'stage1_31feat_lr_model.pkl'))
joblib.dump(scaler_s1_31, os.path.join(MODEL_DIR, 'stage1_31feat_scaler.pkl'))
joblib.dump(feature_cols_s1_31, os.path.join(MODEL_DIR, 'stage1_31feat_feature_cols.pkl'))

print("[OK] Saved Stage 1 Phase 9 ROC-AUC optimized model artifacts (31 features).")

# ─── 2. STAGE 2: SEVERITY MODEL WITH SMOTE ────────────────────────────────
if os.path.exists(DAPH_FILE):
    daph_df = pd.read_csv(DAPH_FILE)
    df_s1['district_clean'] = df_s1['district'].astype(str).str.strip().str.title()
    daph_df['District']     = daph_df['District'].astype(str).str.strip().str.title()
    df_s1['year']           = pd.to_numeric(df_s1['year'], errors='coerce')
    daph_df['Year']         = pd.to_numeric(daph_df['Year'], errors='coerce')

    merged = df_s1.merge(daph_df[['District', 'Year', 'severity_class']], left_on=['district_clean', 'year'], right_on=['District', 'Year'], how='left')
    outbreak_df = merged[merged['Outbreak status'] == 1].dropna(subset=['severity_class']).copy()
    if 'Cases' in outbreak_df.columns:
        outbreak_df['severity_bin'] = (outbreak_df['Cases'] > 30.0).astype(int)
    else:
        outbreak_df['severity_bin'] = (outbreak_df['severity_class'].astype(str).str.upper().isin(['MODERATE', 'HIGH', '1'])).astype(int)
else:
    # Fallback to LSD dataset with embedded Cases column
    lsd_path = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')
    df_lsd = pd.read_csv(lsd_path)
    df_lsd['district_clean'] = df_lsd['district'].astype(str).str.strip().str.title()
    df_lsd['district_enc'] = le_dist.transform(df_lsd['district'])
    df_lsd['year'] = pd.to_numeric(df_lsd['year'], errors='coerce')
    outbreak_df = df_lsd[df_lsd['Outbreak status'] == 1].dropna(subset=['Cases']).copy()
    outbreak_df['severity_bin'] = (outbreak_df['Cases'] > 30.0).astype(int)

drop_cols_s2 = {'district', 'district_clean', 'year', 'month_num', 'Outbreak status', 'PCODE', 'District', 'Year', 'severity_score', 'severity_class', 'severity_encoded', 'severity_bin'}
candidate_cols = [c for c in outbreak_df.columns if c not in drop_cols_s2]
feature_cols_s2 = outbreak_df[candidate_cols].select_dtypes(include=[np.number, 'bool']).columns.tolist()
feature_cols_s2 = [c for c in feature_cols_s2 if c not in ['Cases', 'Deaths', 'Outbreak_Months']]

print(f"Stage 2 Feature Count: {len(feature_cols_s2)}")

X_s2 = outbreak_df[feature_cols_s2].fillna(0).values
y_s2 = outbreak_df['severity_bin'].values

if len(np.unique(y_s2)) > 1 and np.min(np.bincount(y_s2)) >= 2:
    k_nn = min(2, np.min(np.bincount(y_s2)) - 1)
    smote = SMOTE(random_state=42, k_neighbors=k_nn)
    X_s2_sm, y_s2_sm = smote.fit_resample(X_s2, y_s2)
else:
    X_s2_sm, y_s2_sm = X_s2, y_s2

rf_s2 = RandomForestClassifier(n_estimators=200, max_depth=10, min_samples_leaf=2, random_state=42)
rf_s2.fit(X_s2_sm, y_s2_sm)

joblib.dump(rf_s2, os.path.join(MODEL_DIR, 'stage2_rf_model.pkl'))
joblib.dump(rf_s2, os.path.join(MODEL_DIR, 'stage2_rf_model_smote.pkl'))
joblib.dump(feature_cols_s2, os.path.join(MODEL_DIR, 'stage2_feature_cols.pkl'))
joblib.dump(le_dist, os.path.join(MODEL_DIR, 'stage2_label_encoder.pkl'))

print("[OK] Saved Stage 2 production artifacts.")
print("All production model artifacts successfully synchronized!")
