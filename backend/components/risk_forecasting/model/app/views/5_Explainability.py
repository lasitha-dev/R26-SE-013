import streamlit as st
from pathlib import Path
import sys

# Ensure app directory is in path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "app") not in sys.path:
    sys.path.append(str(ROOT_DIR / "app"))

from utils import display_image_gracefully, apply_custom_css

st.set_page_config(page_title="Explainability | FMD Early Warning", page_icon="🧠", layout="wide")
apply_custom_css()

st.title("🧠 AI Explainability (XAI)")
st.markdown("Understanding *why* the model makes specific predictions using SHapley Additive exPlanations (SHAP).")
st.divider()

PLOTS_DIR = ROOT_DIR / "plots" / "08_shap"

# ─── SECTION 1: Global Explainability ──────────────────────────────────────────
st.header("1. Global Explainability")
st.markdown("These charts show which features are most important across all districts and time periods.")

st.subheader("Stage 1 (Outbreak Occurrence)")
col1, col2 = st.columns(2)
with col1:
    display_image_gracefully(PLOTS_DIR / "stage1_shap_importance.png", "Stage 1: Feature Importance (Mean |SHAP|)")
with col2:
    display_image_gracefully(PLOTS_DIR / "stage1_shap_summary.png", "Stage 1: SHAP Summary (Impact Direction)")

st.info("💡 **How to explain this:** The bar chart (left) shows the overall most important variables for predicting IF an outbreak will happen. The summary plot (right) shows how the values affect the risk: for example, high cattle density (red dots) strongly pushes the risk higher (to the right).")

st.divider()

st.subheader("Stage 2 (Severity Classification)")
col3, col4 = st.columns(2)
with col3:
    display_image_gracefully(PLOTS_DIR / "stage2_shap_importance.png", "Stage 2: Feature Importance (Mean |SHAP|)")
with col4:
    display_image_gracefully(PLOTS_DIR / "stage2_shap_summary.png", "Stage 2: SHAP Summary (Impact Direction)")

st.info("💡 **How to explain this:** Here we see what drives the severity of an outbreak once it has already started. We can see that specific climate conditions like Temperature and certain Monsoon phases have the strongest impact on whether the outbreak will be minor or severe.")

st.divider()

# ─── SECTION 2: Local Explainability ───────────────────────────────────────────
st.header("2. Local Explainability (Case Study)")
st.markdown("A deep-dive into a single prediction to understand how individual features pushed the risk up or down.")

st.subheader("Case Study: Anuradhapura (January 2024)")
st.markdown("""
In January 2024, the model successfully predicted a **HIGH RISK** of outbreak for Anuradhapura. 
The waterfall plot below explains exactly how the model arrived at that specific conclusion, starting from the baseline probability and adding/subtracting the impact of each local weather variable.
""")

col5, col6, col7 = st.columns([1, 2, 1])
with col6:
    display_image_gracefully(PLOTS_DIR / "stage1_shap_waterfall_anuradhapura_jan2024.png", "Anuradhapura Jan 2024 Local SHAP Waterfall")

st.info("💡 **How to explain this:** This is a real-world case study for Anuradhapura. The model started at a baseline average expectation (at the bottom of the chart), but the specific local conditions—such as the active North-East Monsoon and local cattle density—combined to push the final prediction all the way up to a High Risk probability.")

st.divider()
st.caption("Research Component - IT22221414 - Kumarasinghe S.S | 2026")
