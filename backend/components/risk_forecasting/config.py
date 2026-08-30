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

LSD_STAGE1_27FEAT_MODEL = MODELS_PATH / "lsd_stage1_27feat_elasticnet.pkl"  # Dedicated 27-feature Elastic Net Fallback Model
LSD_STAGE1_27FEAT_SCALER = MODELS_PATH / "lsd_stage1_27feat_scaler.pkl"
LSD_STAGE1_27FEAT_COLS = MODELS_PATH / "lsd_stage1_27feat_cols.pkl"
LSD_STAGE1_27FEAT_META = MODELS_PATH / "lsd_stage1_27feat_metadata.json"

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

SRI_LANKA_DISTRICT_CENTROIDS = {
    "Ampara": {"lat": 7.3018, "lon": 81.6747},
    "Anuradhapura": {"lat": 8.3122, "lon": 80.4131},
    "Badulla": {"lat": 6.9934, "lon": 81.0550},
    "Batticaloa": {"lat": 7.7102, "lon": 81.6924},
    "Colombo": {"lat": 6.9271, "lon": 79.8612},
    "Galle": {"lat": 6.0535, "lon": 80.2210},
    "Gampaha": {"lat": 7.0840, "lon": 80.0098},
    "Hambantota": {"lat": 6.1249, "lon": 81.1185},
    "Jaffna": {"lat": 9.6615, "lon": 80.0255},
    "Kalutara": {"lat": 6.5854, "lon": 79.9607},
    "Kandy": {"lat": 7.2906, "lon": 80.6337},
    "Kegalle": {"lat": 7.2513, "lon": 80.3464},
    "Kilinochchi": {"lat": 9.3803, "lon": 80.3847},
    "Kurunegala": {"lat": 7.4863, "lon": 80.3647},
    "Mannar": {"lat": 9.0594, "lon": 79.9142},
    "Matale": {"lat": 7.4675, "lon": 80.6234},
    "Matara": {"lat": 5.9549, "lon": 80.5550},
    "Monaragala": {"lat": 6.8724, "lon": 81.3507},
    "Mullaitivu": {"lat": 9.2668, "lon": 80.8143},
    "Nuwara Eliya": {"lat": 6.9497, "lon": 80.7891},
    "Polonnaruwa": {"lat": 7.9403, "lon": 81.0186},
    "Puttalam": {"lat": 8.0330, "lon": 79.8291},
    "Ratnapura": {"lat": 6.6828, "lon": 80.3992},
    "Trincomalee": {"lat": 8.5873, "lon": 81.2152},
    "Vavuniya": {"lat": 8.7542, "lon": 80.4982},
}
