"""
Step 5: Phase 5 — Class-Conditional Mondrian Conformal Calibration for LSD
=============================================================================
Implements Class-Conditional Mondrian Conformal Uncertainty Quantification:
  1. Computes separate non-conformity quantiles q_hat_0 and q_hat_1 for Class 0 and Class 1.
  2. Guarantees 90% empirical coverage independently across majority (0) and minority (1) classes.
  3. Evaluates empirical test coverage and average prediction set size on held-out test data (2023-2024).
"""

import os
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from lightgbm import LGBMClassifier

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')

df = pd.read_csv(DATA_PATH)
print("=== STEP 5: PHASE 5 CLASS-CONDITIONAL MONDRIAN CONFORMAL CALIBRATION (LSD) ===")
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

# Expanding Window Forward Time-Series Split: Train/Calibrate on 2020-2022 (N=900), Test on 2023-2024 (N=600)
train_cal_df = df[df['year'].isin([2020, 2021, 2022])].copy()
test_df      = df[df['year'].isin([2023, 2024])].copy()

# Stratified Calibration Split (70/30)
np.random.seed(42)
cal_mask = np.random.rand(len(train_cal_df)) < 0.30
train_sub = train_cal_df[~cal_mask]
cal_sub   = train_cal_df[cal_mask]

X_train, y_train = train_sub[features].values, train_sub['Outbreak status'].values
X_cal,   y_cal   = cal_sub[features].values,   cal_sub['Outbreak status'].values
X_test,  y_test  = test_df[features].values,   test_df['Outbreak status'].values

# Fit LightGBM Model
lgb = LGBMClassifier(n_estimators=100, is_unbalance=True, max_depth=3, learning_rate=0.05, random_state=42, verbose=-1)
lgb.fit(X_train, y_train)

# Calibration probabilities
p_cal = lgb.predict_proba(X_cal)[:, 1]

# Non-conformity scores: s_i = 1 - p(y_i)
s_cal_0 = [1.0 - (1.0 - p_cal[i]) for i in range(len(y_cal)) if y_cal[i] == 0]
s_cal_1 = [1.0 - p_cal[i] for i in range(len(y_cal)) if y_cal[i] == 1]

alpha = 0.10 # Target 90% coverage

n0 = len(s_cal_0)
q0_level = np.ceil((n0 + 1) * (1.0 - alpha)) / n0
q_hat_0  = np.quantile(s_cal_0, q0_level, method='higher')

n1 = len(s_cal_1)
q1_level = np.ceil((n1 + 1) * (1.0 - alpha)) / n1
q_hat_1  = np.quantile(s_cal_1, q1_level, method='higher')

print(f"Mondrian Calibration Samples: N_cal(Class 0) = {n0}, N_cal(Class 1) = {n1}")
print(f"Class 0 Conformal Quantile (q_hat_0): {q_hat_0:.4f}")
print(f"Class 1 Conformal Quantile (q_hat_1): {q_hat_1:.4f}")

# Test Set Evaluation
p_test = lgb.predict_proba(X_test)[:, 1]

pred_sets = []
covered   = []
set_sizes = []

for i in range(len(y_test)):
    p1 = p_test[i]
    p0 = 1.0 - p1
    
    # Class-Conditional Prediction Set Construction
    S = []
    if (1.0 - p0) <= q_hat_0:
        S.append(0)
    if (1.0 - p1) <= q_hat_1:
        S.append(1)
        
    pred_sets.append(S)
    set_sizes.append(len(S))
    covered.append(1 if y_test[i] in S else 0)

empirical_coverage = np.mean(covered)
avg_set_size       = np.mean(set_sizes)

cov_pos = np.mean([covered[i] for i in range(len(y_test)) if y_test[i] == 1])
cov_neg = np.mean([covered[i] for i in range(len(y_test)) if y_test[i] == 0])

print("\n=== MONDRIAN CONFORMAL EVALUATION ON HELD-OUT TEST DATA (2023-2024, N=600) ===")
print(f"Overall Empirical Coverage:      {empirical_coverage * 100:.2f}% (Target: 90.0%)")
print(f"True Outbreak Class Coverage:    {cov_pos * 100:.2f}% (Target: 90.0%, N_pos={np.sum(y_test)})")
print(f"True No-Outbreak Class Coverage:  {cov_neg * 100:.2f}% (Target: 90.0%, N_neg={len(y_test) - np.sum(y_test)})")
print(f"Average Prediction Set Size:     {avg_set_size:.2f} classes")
print(f"Coverage Guarantee Met?          {cov_pos >= 0.90 and cov_neg >= 0.90}")
