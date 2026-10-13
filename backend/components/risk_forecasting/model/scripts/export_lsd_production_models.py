"""
Export Dedicated LSD Production Models (Stage 1 Elastic Net + Platt Scaling & Stage 2 Quiet-Period Suppressor).
Saves dedicated LSD model artifacts to models/ directory.
"""

import os
import joblib
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import LabelEncoder, StandardScaler
from imblearn.over_sampling import SMOTE

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')
SEV_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_severity_labels.csv')
MODEL_DIR = os.path.join(BASE_DIR, 'models')


print("=== EXPORTING DEDICATED LSD PRODUCTION MODEL ARTIFACTS ===")

# ─── 1. STAGE 1: 28-FEATURE ELASTIC NET + PLATT SCALED MODEL ───────────────
df_lsd = pd.read_csv(DATA_PATH)
df_lsd['date'] = pd.to_datetime(df_lsd['date'])
df_lsd = df_lsd.sort_values(['district', 'date']).reset_index(drop=True)
if 'own_outbreak_lag1' not in df_lsd.columns:
    df_lsd['own_outbreak_lag1'] = df_lsd.groupby('district')['Outbreak status'].shift(1).fillna(0.0)

lsd_features_s1 = [
    'sin_month', 'cos_month',
    'monsoon_phase_First_Inter_Monsoon', 'monsoon_phase_SW_Monsoon',
    'monsoon_phase_Second_Inter_Monsoon', 'monsoon_phase_NE_Monsoon',
    'rainfall_mm', 'r3h', 'rfq', 'rain_lag1', 'rain_lag2', 'rfq_lag1',
    'humidity', 'wind_speed', 'temp_lag1', 'humidity_lag1', 'wind_lag1',
    'buffalo_density', 'livestock_density',
    'nino34', 'nino34_lag3', 'iod_dmi', 'iod_dmi_lag2',
    'neighbor_outbreak_lag1', 'neighbor_outbreak_count_lag1',
    'neighbor_outbreak_fraction_lag1', 'neighbor_outbreak_lag2',
    'own_outbreak_lag1'
]

X_lsd_s1 = df_lsd[lsd_features_s1].values
y_lsd_s1 = df_lsd['Outbreak status'].values

scaler_lsd_s1 = StandardScaler()
X_lsd_s1_scaled = scaler_lsd_s1.fit_transform(X_lsd_s1)

base_en = LogisticRegression(
    penalty='elasticnet',
    solver='saga',
    l1_ratio=0.5,
    C=0.1,
    class_weight='balanced',
    max_iter=1000,
    random_state=42
)

# Platt Calibration Wrapper (CalibratedClassifierCV)
platt_lsd_s1 = CalibratedClassifierCV(estimator=base_en, method='sigmoid', cv=4)
platt_lsd_s1.fit(X_lsd_s1_scaled, y_lsd_s1)

joblib.dump(platt_lsd_s1, os.path.join(MODEL_DIR, 'lsd_stage1_elasticnet.pkl'))
joblib.dump(scaler_lsd_s1, os.path.join(MODEL_DIR, 'lsd_stage1_scaler.pkl'))
joblib.dump(lsd_features_s1, os.path.join(MODEL_DIR, 'lsd_stage1_feature_cols.pkl'))

print(f"[OK] Exported LSD Stage 1 Elastic Net + Platt Scaled Model ({len(lsd_features_s1)} features).")


# ─── 2. STAGE 2: LOGISTIC REGRESSION QUIET-PERIOD SUPPRESSOR MODEL ───────────
df_sev = pd.read_csv(SEV_PATH)
df_sev['District'] = df_sev['district'].astype(str).str.strip().str.title()
df_sev['Year'] = pd.to_numeric(df_sev['year'], errors='coerce')

df_annual_feats = df_lsd.groupby(['district', 'year'])[lsd_features_s1].mean().reset_index()
df_merged = pd.merge(df_sev, df_annual_feats, left_on=['District', 'Year'], right_on=['district', 'year'], how='inner')

df_merged['severity_class'] = (df_merged['Cases'] > 57.0).astype(int)  # 0: LOW, 1: MOD_HIGH

drop_cols_s2 = {'district', 'year', 'date', 'District', 'Year', 'Cases', 'Deaths', 'Outbreak_Months', 'severity_score', 'severity_class'}
lsd_features_s2 = [c for c in df_merged.columns if c not in drop_cols_s2 and c in lsd_features_s1]

X_lsd_s2 = df_merged[lsd_features_s2].fillna(0.0).values
y_lsd_s2 = df_merged['severity_class'].values

smote = SMOTE(random_state=42, k_neighbors=2)
X_lsd_s2_sm, y_lsd_s2_sm = smote.fit_resample(X_lsd_s2, y_lsd_s2)

lr_s2 = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
lr_s2.fit(X_lsd_s2_sm, y_lsd_s2_sm)

le_sev = LabelEncoder()
le_sev.fit(["LOW", "MOD_HIGH"])

joblib.dump(lr_s2, os.path.join(MODEL_DIR, 'lsd_stage2_lr.pkl'))
joblib.dump(le_sev, os.path.join(MODEL_DIR, 'lsd_stage2_label_encoder.pkl'))
joblib.dump(lsd_features_s2, os.path.join(MODEL_DIR, 'lsd_stage2_feature_cols.pkl'))

print(f"[OK] Exported LSD Stage 2 Logistic Regression Quiet-Period Suppressor ({len(lsd_features_s2)} features).")
print("Dedicated LSD production artifacts successfully created and saved!")
