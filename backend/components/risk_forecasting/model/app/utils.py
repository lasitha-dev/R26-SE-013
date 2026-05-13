from pathlib import Path
import datetime
import numpy as np
import io

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import os

def apply_custom_css():
    st.markdown("""
        <style>
        /* Hide Streamlit Branding */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Modern Typography & Card Styling */
        h1, h2, h3 {
            font-weight: 600 !important;
            letter-spacing: -0.5px;
        }
        
        /* Premium metric card styling */
        div[data-testid="metric-container"] {
            background-color: #1e293b;
            border: 1px solid #334155;
            padding: 1rem 1.5rem;
            border-radius: 0.75rem;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            transition: all 0.2s ease-in-out;
        }
        div[data-testid="metric-container"]:hover {
            transform: translateY(-2px);
            border-color: #3b82f6;
            box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
        }
        
        /* Style standard info/warning/error boxes */
        div.stAlert {
            border-radius: 0.5rem;
            border: none;
            box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
        }
        
        /* Primary button styling */
        button[data-testid="baseButton-primary"] {
            font-weight: 600;
            border-radius: 0.5rem;
            box-shadow: 0 4px 6px -1px rgb(59 130 246 / 0.5);
            transition: all 0.2s;
        }
        button[data-testid="baseButton-primary"]:hover {
            box-shadow: 0 6px 8px -1px rgb(59 130 246 / 0.6);
            transform: translateY(-1px);
        }
        </style>
    """, unsafe_allow_html=True)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "processed" / "FMD_model_ready_main refined_final_dataset.csv"
MODEL_DIR = ROOT_DIR / "models"
STAGE1_SHAP_PATH = ROOT_DIR / "data" / "processed" / "stage1_shap_values.csv"
STAGE2_SHAP_PATH = ROOT_DIR / "data" / "processed" / "stage2_shap_values.csv"
BOOTSTRAP_INTERVALS_PATH = ROOT_DIR / "data" / "processed" / "bootstrap_intervals.csv"

DISTRICTS = sorted(
    [
        "Ampara", "Anuradhapura", "Badulla", "Batticaloa", "Colombo", "Galle",
        "Gampaha", "Hambantota", "Jaffna", "Kalutara", "Kandy", "Kegalle",
        "Kilinochchi", "Kurunegala", "Mannar", "Matale", "Matara", "Monaragala",
        "Mullaitivu", "Nuwara Eliya", "Polonnaruwa", "Puttalam", "Ratnapura",
        "Trincomalee", "Vavuniya",
    ]
)

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

@st.cache_data
def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        st.error(f"Data file not found at {DATA_PATH}")
        return pd.DataFrame()
    return pd.read_csv(DATA_PATH)

@st.cache_data
def load_shap_values() -> tuple[pd.DataFrame, pd.DataFrame]:
    stage1 = pd.read_csv(STAGE1_SHAP_PATH) if STAGE1_SHAP_PATH.exists() else pd.DataFrame()
    stage2 = pd.read_csv(STAGE2_SHAP_PATH) if STAGE2_SHAP_PATH.exists() else pd.DataFrame()
    return stage1, stage2

@st.cache_data
def load_bootstrap_intervals() -> pd.DataFrame:
    if BOOTSTRAP_INTERVALS_PATH.exists():
        return pd.read_csv(BOOTSTRAP_INTERVALS_PATH)
    return pd.DataFrame()

@st.cache_resource
def load_models() -> dict:
    models = {}
    try:
        models["stage1_model"] = joblib.load(MODEL_DIR / "stage1_lr_model.pkl")
        models["stage1_scaler"] = joblib.load(MODEL_DIR / "stage1_scaler.pkl")
        models["stage1_features"] = joblib.load(MODEL_DIR / "stage1_feature_cols.pkl")
        models["stage2_model"] = joblib.load(MODEL_DIR / "stage2_rf_model.pkl")
        models["stage2_encoder"] = joblib.load(MODEL_DIR / "stage2_label_encoder.pkl")
        models["stage2_features"] = joblib.load(MODEL_DIR / "stage2_feature_cols.pkl")
    except Exception as e:
        st.error(f"Error loading models: {e}")
    return models

def display_image_gracefully(path: Path, caption: str = "", use_column_width: bool = True):
    if path.exists():
        st.image(str(path), caption=caption, use_container_width=use_column_width)
    else:
        st.warning(f"Image not found: {path.name}")

def get_feature_row(df: pd.DataFrame, district: str, month_num: int, year: int, feature_cols: list[str]) -> tuple[pd.DataFrame, str]:
    exact = df[(df["district"] == district) & (df["month_num"] == month_num) & (df["year"] == year)]
    if not exact.empty:
        return exact.iloc[[0]], "Exact match found"

    district_month = df[(df["district"] == district) & (df["month_num"] == month_num)]
    if not district_month.empty:
        latest = district_month.sort_values("year", ascending=False).iloc[[0]]
        latest_year = int(latest["year"].iloc[0])
        return latest, f"No exact year match. Using latest available year: {latest_year}"

    district_rows = df[df["district"] == district]
    if not district_rows.empty:
        medians = district_rows[feature_cols].median(numeric_only=True)
        medians = medians.reindex(feature_cols).fillna(0.0)
        return pd.DataFrame([medians], columns=feature_cols), "No month-level record found. Using district medians"

    global_medians = df[feature_cols].median(numeric_only=True)
    global_medians = global_medians.reindex(feature_cols).fillna(0.0)
    return pd.DataFrame([global_medians], columns=feature_cols), "District not found in data. Using global medians"

def build_top_shap_chart(shap_df: pd.DataFrame, title: str):
    if shap_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4.8))
        ax.text(0.5, 0.5, 'SHAP data not available', ha='center', va='center')
        ax.set_title(title)
        return fig
    
    top = shap_df.sort_values("mean_abs_shap", ascending=False).head(8).copy()
    top = top.iloc[::-1]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(top["feature"], top["mean_abs_shap"], color="#E8593C")
    ax.set_title(title)
    ax.set_xlabel("Mean |SHAP| Value")
    ax.set_ylabel("Feature")
    fig.tight_layout()
    return fig

def decode_severity(encoder, pred_value: int) -> str:
    try:
        decoded = encoder.inverse_transform([int(pred_value)])[0]
        return str(decoded).upper()
    except Exception:
        mapping = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
        return mapping.get(int(pred_value), "UNKNOWN")

def compute_climatological_forecast(df: pd.DataFrame, models: dict, districts: list[str], target_month: int) -> pd.DataFrame:
    if "stage1_features" not in models or df.empty:
        return pd.DataFrame()
        
    stage1_features = list(models["stage1_features"])
    stage2_features = list(models.get("stage2_features", []))
    
    monsoon_mappings = {
        1: {"NE": 1, "SW": 0, "FIM": 0, "SIM": 0},
        2: {"NE": 1, "SW": 0, "FIM": 0, "SIM": 0},
        3: {"NE": 0, "SW": 0, "FIM": 1, "SIM": 0},
        4: {"NE": 0, "SW": 0, "FIM": 1, "SIM": 0},
        5: {"NE": 0, "SW": 1, "FIM": 0, "SIM": 0},
        6: {"NE": 0, "SW": 1, "FIM": 0, "SIM": 0},
        7: {"NE": 0, "SW": 1, "FIM": 0, "SIM": 0},
        8: {"NE": 0, "SW": 1, "FIM": 0, "SIM": 0},
        9: {"NE": 0, "SW": 0, "FIM": 0, "SIM": 1},
        10: {"NE": 0, "SW": 0, "FIM": 0, "SIM": 1},
        11: {"NE": 1, "SW": 0, "FIM": 0, "SIM": 0},
        12: {"NE": 1, "SW": 0, "FIM": 0, "SIM": 0},
    }
    
    results = []
    
    for district in districts:
        district_month_data = df[(df["district"] == district) & (df["month_num"] == target_month)]
        if district_month_data.empty: continue
        
        mean_row = district_month_data[stage1_features].mean(numeric_only=True)
        feature_row = pd.DataFrame([mean_row], columns=stage1_features)
        
        if "lat" in stage1_features and not district_month_data["lat"].isna().all():
            feature_row["lat"] = district_month_data["lat"].iloc[0]
        if "lon" in stage1_features and not district_month_data["lon"].isna().all():
            feature_row["lon"] = district_month_data["lon"].iloc[0]
        
        if "sin_month" in stage1_features: feature_row["sin_month"] = np.sin(2 * np.pi * target_month / 12)
        if "cos_month" in stage1_features: feature_row["cos_month"] = np.cos(2 * np.pi * target_month / 12)
        
        monsoon_map = monsoon_mappings.get(target_month, {})
        if "monsoon_phase_First_Inter_Monsoon" in stage1_features: feature_row["monsoon_phase_First_Inter_Monsoon"] = monsoon_map.get("FIM", 0)
        if "monsoon_phase_SW_Monsoon" in stage1_features: feature_row["monsoon_phase_SW_Monsoon"] = monsoon_map.get("SW", 0)
        if "monsoon_phase_Second_Inter_Monsoon" in stage1_features: feature_row["monsoon_phase_Second_Inter_Monsoon"] = monsoon_map.get("SIM", 0)
        if "monsoon_phase_NE_Monsoon" in stage1_features: feature_row["monsoon_phase_NE_Monsoon"] = monsoon_map.get("NE", 0)
        
        feature_row = feature_row.fillna(0.0)
        
        x_stage1 = feature_row[stage1_features].astype(float)
        x_stage1_scaled = models["stage1_scaler"].transform(x_stage1)
        probability = float(models["stage1_model"].predict_proba(x_stage1_scaled)[:, 1][0])
        
        if probability >= 0.60: risk_level = "HIGH"
        elif probability >= 0.35: risk_level = "MEDIUM"
        else: risk_level = "LOW"
        
        severity = "No Outbreak Predicted"
        if probability >= 0.35 and "stage2_model" in models:
            for col in stage2_features:
                if col not in feature_row.columns: feature_row[col] = 0.0
            x_stage2 = feature_row[stage2_features].fillna(0.0).astype(float)
            severity_pred = int(models["stage2_model"].predict(x_stage2)[0])
            severity = decode_severity(models["stage2_encoder"], severity_pred)
        
        results.append({
            "District": district,
            "Outbreak Probability (%)": round(probability * 100, 1),
            "Risk Level": risk_level,
            "Predicted Severity": severity,
        })
    
    if results:
        results_df = pd.DataFrame(results).sort_values("Outbreak Probability (%)", ascending=False)
        return results_df
    return pd.DataFrame()

def render_forecast_table(forecast_df: pd.DataFrame) -> None:
    def risk_color(risk_level: str) -> str:
        if risk_level == "HIGH": return "background-color: #ffcccc; color: black;"
        elif risk_level == "MEDIUM": return "background-color: #ffe6cc; color: black;"
        else: return "background-color: #ccffcc; color: black;"
    
    styled_df = forecast_df.style.map(
        lambda x: risk_color(x) if isinstance(x, str) else "",
        subset=["Risk Level"]
    )
    st.dataframe(styled_df, width=1000, hide_index=True)

def generate_forecast_csv(forecast_df: pd.DataFrame) -> bytes:
    csv_buffer = io.StringIO()
    forecast_df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue().encode()
