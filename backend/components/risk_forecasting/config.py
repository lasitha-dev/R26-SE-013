"""
Configuration settings for the Risk Forecasting component.
Defines model artifact paths, data source locations, decision thresholds, and district constants.
"""

from pathlib import Path

# Paths
COMPONENT_DIR = Path(__file__).resolve().parent
MODEL_DIR = COMPONENT_DIR / "model"
MODELS_PATH = MODEL_DIR / "models"
DATA_PATH = MODEL_DIR / "data" / "processed"

# Primary Dataset Paths
FMD_DATASET_FILE = DATA_PATH / "FMD_dataset_with_spatial_and_climate_indices.csv"
LSD_DATASET_FILE = DATA_PATH / "LSD_dataset_with_spatial_and_climate_indices.csv"
BOOTSTRAP_INTERVALS_FILE = DATA_PATH / "bootstrap_intervals.csv"

STAGE1_SHAP_FILE = DATA_PATH / "stage1_shap_values.csv"
STAGE2_SHAP_FILE = DATA_PATH / "stage2_shap_values.csv"

# Model File Names - FMD
FMD_STAGE1_30FEAT_MODEL = MODELS_PATH / "stage1_lr_model.pkl"
FMD_STAGE1_30FEAT_SCALER = MODELS_PATH / "stage1_scaler.pkl"
FMD_STAGE1_30FEAT_COLS = MODELS_PATH / "stage1_feature_cols.pkl"

FMD_STAGE1_31FEAT_MODEL = MODELS_PATH / "stage1_31feat_lr_model.pkl"
FMD_STAGE1_31FEAT_SCALER = MODELS_PATH / "stage1_31feat_scaler.pkl"
FMD_STAGE1_31FEAT_COLS = MODELS_PATH / "stage1_31feat_feature_cols.pkl"

FMD_STAGE2_RF_MODEL = MODELS_PATH / "stage2_rf_model.pkl"
FMD_STAGE2_LABEL_ENCODER = MODELS_PATH / "stage2_label_encoder.pkl"
FMD_STAGE2_FEATURE_COLS = MODELS_PATH / "stage2_feature_cols.pkl"

# Model File Names - LSD
LSD_STAGE1_MODEL = MODELS_PATH / "lsd_stage1_elasticnet.pkl"  # Dedicated 28-feature Elastic Net + Platt Scaled Model
LSD_STAGE1_SCALER = MODELS_PATH / "lsd_stage1_scaler.pkl"
LSD_STAGE1_COLS = MODELS_PATH / "lsd_stage1_feature_cols.pkl"

LSD_STAGE2_MODEL = MODELS_PATH / "lsd_stage2_lr.pkl"  # Dedicated Logistic Regression Quiet-Period Suppressor Model
LSD_STAGE2_LABEL_ENCODER = MODELS_PATH / "lsd_stage2_label_encoder.pkl"
LSD_STAGE2_FEATURE_COLS = MODELS_PATH / "lsd_stage2_feature_cols.pkl"


# Decision Thresholds (Audited & Bootstrap-Tested)
GLOBAL_DECISION_THRESHOLD = 0.40  # Verified t = 0.40 boundary
HIGH_RISK_THRESHOLD = 0.60         # High risk confidence boundary

# Sri Lanka 25 Administrative Districts
SRI_LANKA_DISTRICTS = sorted([
    "Ampara", "Anuradhapura", "Badulla", "Batticaloa", "Colombo", "Galle",
    "Gampaha", "Hambantota", "Jaffna", "Kalutara", "Kandy", "Kegalle",
    "Kilinochchi", "Kurunegala", "Mannar", "Matale", "Matara", "Monaragala",
    "Mullaitivu", "Nuwara Eliya", "Polonnaruwa", "Puttalam", "Ratnapura",
    "Trincomalee", "Vavuniya",
])

# Month Names
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
