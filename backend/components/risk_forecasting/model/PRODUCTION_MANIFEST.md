# Risk Forecasting Production Artifact Manifest

## Runtime Architecture
The production FastAPI application loads only explicitly configured runtime artifacts and inference datasets via `backend/components/risk_forecasting/config.py`.

---

## FMD Stage 1 — 30 Feature Baseline
- **Files:** `stage1_lr_model.pkl` (1,103 bytes), `stage1_scaler.pkl` (2,055 bytes), `stage1_feature_cols.pkl` (520 bytes)
- **Role:** PRIMARY / BASELINE
- **Feature Count:** 30
- **Model Type:** Logistic Regression with StandardScaler

---

## FMD Stage 1 — 31 Feature Autocorrelation
- **Files:** `stage1_31feat_lr_model.pkl` (1,119 bytes), `stage1_31feat_scaler.pkl` (2,079 bytes), `stage1_31feat_feature_cols.pkl` (540 bytes)
- **Role:** CONDITIONAL PRIMARY VARIANT
- **Feature Count:** 31
- **Model Type:** Logistic Regression with StandardScaler
- **Condition:** Requires verified `own_outbreak_lag1` (previous-month same-district outbreak status)

---

## FMD Stage 2 — Severity Classifier
- **Files:** `stage2_rf_model.pkl` (2,122,033 bytes), `stage2_label_encoder.pkl` (756 bytes), `stage2_feature_cols.pkl` (520 bytes)
- **Role:** ADVISORY SEVERITY CLASSIFIER
- **Validation Status:** `discriminator_validated = False` (Advisory ONLY)
- **Condition:** Executes when Stage 1 outbreak probability >= 0.40

---

## LSD Stage 1 — 28 Feature Baseline
- **Files:** `lsd_stage1_elasticnet.pkl` (3,764 bytes), `lsd_stage1_scaler.pkl` (1,255 bytes), `lsd_stage1_feature_cols.pkl` (513 bytes)
- **Role:** PRIMARY
- **Feature Count:** 28
- **Model Type:** ElasticNet + Platt Scaler
- **Condition:** Requires verified `own_outbreak_lag1`

---

## LSD Stage 1 — 27 Feature Fallback
- **Files:** `lsd_stage1_27feat_elasticnet.pkl` (3,764 bytes), `lsd_stage1_27feat_scaler.pkl` (1,215 bytes), `lsd_stage1_27feat_cols.pkl` (493 bytes)
- **Role:** DEGRADED FALLBACK
- **Feature Count:** 27
- **Model Type:** Dedicated 27-feature ElasticNet
- **Condition:** Used when `own_outbreak_lag1` is unavailable
- **Note:** `lsd_stage1_27feat_metadata.json` (3,402 bytes) is export/research metadata and is NOT required for inference.

---

## LSD Stage 2 — Suppressor Model
- **Files:** `lsd_stage2_lr.pkl` (1,087 bytes), `lsd_stage2_label_encoder.pkl` (391 bytes), `lsd_stage2_feature_cols.pkl` (513 bytes)
- **Role:** QUIET-PERIOD SUPPRESSOR
- **Model Type:** Logistic Regression
- **Validation Status:** Suppressor only; not a validated multi-class severity discriminator

---

## Required Runtime Datasets
- `FMD_dataset_with_spatial_and_climate_indices.csv` (622,432 bytes)
- `LSD_dataset_with_spatial_and_climate_indices.csv` (444,709 bytes)
- **Role:** Both CSVs are required by the current CSV-backed inference architecture for feature retrieval, lag checking, and historical proxy/median calculations.

---

## Runtime Resource Count
- **Required `.pkl` Model Artifacts:** 18
- **Required `.csv` Inference Datasets:** 2
- **Total Required Runtime Resources:** 20
*(Note: Metadata JSON files such as `lsd_stage1_27feat_metadata.json` are research export records and are NOT counted as runtime inference resources).*

---

## Research / Legacy — DO NOT LOAD AT RUNTIME
The following files belong to research history or obsolete experiments and MUST NOT replace active runtime assets:
- `stage2_severity_model.pkl` (Obsolete 21-feature Stage 2 Random Forest)
- `final_model_stage1.pkl` (Legacy duplicate of 30-feature baseline)
- `scaler_stage1.pkl` (Legacy duplicate of 30-feature scaler)
- `stage2_rf_model_smote.pkl` (Duplicate SMOTE research artifact)
- `bootstrap_config.pkl` & `bootstrap_intervals.pkl` (Offline research bootstrap artifacts)
- `severity_thresholds.pkl` (Obsolete 21-feature thresholds)
- `stage1_shap_values.csv` & `stage2_shap_values.csv` (Obsolete 21-feature SHAP research outputs)

---

## Canonical Configuration
The executable source of runtime artifact paths is:
`backend/components/risk_forecasting/config.py`

This manifest documents that configuration; it does not override code.
