import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

# Ensure app directory is in path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "app") not in sys.path:
    sys.path.append(str(ROOT_DIR / "app"))

from utils import (
    load_data, load_models, load_shap_values, load_bootstrap_intervals,
    get_feature_row, build_top_shap_chart, decode_severity,
    DISTRICTS, MONTH_NAMES, apply_custom_css
)

st.set_page_config(page_title="Predict Outbreak | FMD Early Warning", page_icon="🔍", layout="wide")
apply_custom_css()

st.title("🔍 Predict FMD Outbreak Risk")
st.markdown("Select a district and time period to predict outbreak risk using the two-stage model.")
st.divider()

# Load data
with st.spinner("Loading models and data..."):
    df = load_data()
    models = load_models()
    stage1_shap_df, stage2_shap_df = load_shap_values()
    bootstrap_intervals_df = load_bootstrap_intervals()

if df.empty or "stage1_model" not in models:
    st.error("Failed to load required models or data. Please check the project structure.")
    st.stop()

# Sidebar for inputs
st.sidebar.title("Input Parameters")
selected_district = st.sidebar.selectbox("District", DISTRICTS)
selected_month_name = st.sidebar.selectbox("Month", MONTH_NAMES)
month_num = MONTH_NAMES.index(selected_month_name) + 1
selected_year = st.sidebar.slider("Year", min_value=2017, max_value=2024, value=2024, step=1)

st.sidebar.divider()
st.sidebar.subheader("⚙️ Model Variant Selection")
model_variant = st.sidebar.radio(
    "Select Stage 1 Model Architecture:",
    options=[
        "🛡️ Parsimonious Production Baseline (30 Features — Recommended Default)",
        "⚡ Stage 1 ROC-AUC Optimized Variant (31 Features — Target Autocorrelation)"
    ],
    index=0,
    help=(
        "• Recommended Default (30 Feat): Primary validated model relying strictly on spatial neighbor and climate drivers.\n"
        "• ROC-AUC Optimized (31 Feat): Adds raw own-district prior outbreak lag (+0.0286 ROC-AUC boost, p=0.0000)."
    )
)

predict_clicked = st.sidebar.button("Predict FMD Risk", width='stretch', type="primary")

if not predict_clicked:
    st.info("Choose district/month/year and model variant from the sidebar, then click Predict FMD Risk.")
    st.stop()

# Prediction Logic
use_31feat = "31 Features" in model_variant
stage1_features = list(models["stage1_features"])
if use_31feat and "own_outbreak_lag1" not in stage1_features:
    stage1_features.append("own_outbreak_lag1")

stage2_features = list(models.get("stage2_features", []))

feature_row, fallback_msg = get_feature_row(
    df=df, district=selected_district, month_num=month_num,
    year=selected_year, feature_cols=stage1_features,
)

if fallback_msg != "Exact match found":
    st.info(fallback_msg)

if use_31feat and "own_outbreak_lag1" not in feature_row.columns:
    df_sorted = df.sort_values(["district", "year", "month_num"])
    df_sorted["own_outbreak_lag1"] = df_sorted.groupby("district")["Outbreak status"].shift(1).fillna(0)
    match_val = df_sorted[(df_sorted["district"] == selected_district) & (df_sorted["year"] == selected_year) & (df_sorted["month_num"] == month_num)]
    feature_row["own_outbreak_lag1"] = float(match_val["own_outbreak_lag1"].iloc[0]) if not match_val.empty else 0.0

for col in stage1_features:
    if col not in feature_row.columns:
        feature_row[col] = 0.0

x_stage1 = feature_row[stage1_features].fillna(0.0).astype(float)

# Scale & predict using saved .pkl artifacts
if use_31feat and "stage1_31feat_model" in models:
    feat_cols_31 = models["stage1_31feat_features"]
    x31 = feature_row[feat_cols_31].fillna(0.0).astype(float)
    x31_scaled = models["stage1_31feat_scaler"].transform(x31)
    probability = float(models["stage1_31feat_model"].predict_proba(x31_scaled)[:, 1][0])
else:
    feat_cols_30 = models["stage1_features"]
    x30 = feature_row[feat_cols_30].fillna(0.0).astype(float)
    x30_scaled = models["stage1_scaler"].transform(x30)
    probability = float(models["stage1_model"].predict_proba(x30_scaled)[:, 1][0])

if probability >= 0.60:
    risk_level = "HIGH"
elif probability >= 0.35:
    risk_level = "MEDIUM"
else:
    risk_level = "LOW"

severity = "LOW"
if probability >= 0.35 and "stage2_model" in models:
    for col in stage2_features:
        if col not in feature_row.columns:
            feature_row[col] = 0.0
    x_stage2 = feature_row[stage2_features].fillna(0.0).astype(float)
    severity_pred = int(models["stage2_model"].predict(x_stage2)[0])
    severity = decode_severity(models["stage2_encoder"], severity_pred)

# Display Results
top_meta_col1, top_meta_col2, top_meta_col3 = st.columns(3)
top_meta_col1.metric("Selected District", selected_district)
top_meta_col2.metric("Selected Month/Year", f"{selected_month_name} {selected_year}")
top_meta_col3.metric("Data Source", "DAPH + CHIRPS + NASA POWER")

if use_31feat:
    lag1_val = feature_row.get("own_outbreak_lag1", pd.Series([0.0])).iloc[0]
    if fallback_msg != "Exact match found":
        st.warning(
            "⚠️ **Forward Prediction / Reporting Lag Notice:** Verified prior-month surveillance data "
            f"was unavailable for {selected_month_name} {selected_year}. `own_outbreak_lag1` defaulted to `0.0` (No Outbreak). "
            "Note: The 31-feature model's ROC-AUC boost relies on verified recent historical ground truth."
        )
    else:
        status_str = "🔴 Outbreak Active (1.0)" if lag1_val == 1.0 else "🟢 No Outbreak (0.0)"
        st.info(
            f"ℹ️ **Target Autocorrelation Ground Truth Verified:** Prior-month outbreak status (`own_outbreak_lag1`) "
            f"retrieved as **{status_str}** from historical DAPH surveillance records."
        )

st.subheader("Stage 1 — Outbreak Risk Prediction")
row2_left, row2_right = st.columns([1, 1])

with row2_left:
    st.metric("Outbreak Probability", f"{probability * 100:.1f}%")
    st.progress(probability)

    if risk_level == "HIGH":
        st.error("🔴 HIGH RISK — Outbreak Likely")
    elif risk_level == "MEDIUM":
        st.warning("🟠 MEDIUM RISK — Elevated Risk")
    else:
        st.success("🟢 LOW RISK — Routine Monitoring")

with row2_right:
    fig1 = build_top_shap_chart(stage1_shap_df, "Top Climate Risk Drivers")
    st.pyplot(fig1, width='stretch')
    plt.close(fig1)

if probability >= 0.35:
    st.subheader("Stage 2 — Severity Prediction")
    row3_left, row3_right = st.columns([1, 1])

    with row3_left:
        st.metric("Predicted Severity", severity)
        if severity == "LOW":
            st.success("🟢 LOW Severity")
            st.write("Minor outbreak expected. Standard monitoring protocols apply.")
        elif severity == "MEDIUM":
            st.warning("🟠 MEDIUM Severity")
            st.write("Moderate outbreak. Targeted vaccination and surveillance recommended.")
        else:
            st.error("🔴 HIGH Severity")
            st.write("Severe outbreak expected. Emergency response protocols required.")

        bootstrap_match = pd.DataFrame()
        if not bootstrap_intervals_df.empty:
            bootstrap_match = bootstrap_intervals_df[
                (bootstrap_intervals_df["district"] == selected_district)
                & (bootstrap_intervals_df["year"] == selected_year)
                & (bootstrap_intervals_df["month_num"] == month_num)
            ]

        if not bootstrap_match.empty:
            bootstrap_row = bootstrap_match.iloc[0]
            confidence_pct = float(bootstrap_row["confidence_pct"])

            bootstrap_interval_col1, bootstrap_interval_col2 = st.columns(2)
            bootstrap_interval_col1.metric("95% Prediction Interval", str(bootstrap_row["interval_label"]))
            bootstrap_interval_col2.metric("Model Confidence", f"{confidence_pct:.0f}%")

            if confidence_pct >= 70:
                st.success("High confidence bootstrap estimate")
            elif confidence_pct >= 50:
                st.warning("Moderate confidence bootstrap estimate")
            else:
                st.error("Low confidence bootstrap estimate")
        else:
            st.info("Bootstrap interval not available for this selection")

    with row3_right:
        fig2 = build_top_shap_chart(stage2_shap_df, "Top Severity Drivers")
        st.pyplot(fig2, width='stretch')
        plt.close(fig2)

st.subheader("Recommendation")

if risk_level == "HIGH" and severity == "HIGH":
    st.error("""
EMERGENCY RESPONSE REQUIRED
- Immediately notify DAPH Animal Health Division
- Activate emergency vaccination campaign
- Impose movement restrictions on livestock
- Deploy rapid response veterinary teams
- Isolate affected farms within 24 hours
""")
elif risk_level == "HIGH" and severity == "MEDIUM":
    st.warning("""
TARGETED RESPONSE REQUIRED
- Alert district veterinary surgeons
- Begin targeted vaccination in high-risk areas
- Increase farm surveillance frequency
- Prepare movement restriction protocols
""")
elif risk_level == "HIGH" and severity == "LOW":
    st.warning("""
ELEVATED MONITORING REQUIRED
- Increase surveillance frequency
- Prepare vaccination supplies
- Monitor livestock movement
- Alert local veterinary officers
""")
elif risk_level == "MEDIUM":
    st.info("""
INCREASED SURVEILLANCE RECOMMENDED
- Standard monitoring with increased frequency
- Review vaccination records in district
- Monitor climate conditions closely
""")
else:
    st.success("""
ROUTINE MONITORING
- Standard surveillance protocols apply
- No immediate intervention required
- Continue regular farm visits
""")
