import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Ensure app directory is in path so we can import utils
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "app") not in sys.path:
    sys.path.append(str(ROOT_DIR / "app"))

from utils import load_data, load_models, apply_custom_css

st.set_page_config(page_title="Dashboard | FMD Early Warning", page_icon="🏠", layout="wide")
apply_custom_css()

st.title("🏠 FMD Early Warning System — Sri Lanka")
st.markdown("### Climate-Informed Seasonal Disease Forecasting")
st.divider()

# Load data to show accurate metrics if available
df = load_data()
models = load_models()

# Key Metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Districts Monitored", "25")
with col2:
    st.metric("Data Period", "2017–2024 (8 Years)")
with col3:
    num_features = len(models.get("stage1_features", [])) if "stage1_features" in models else "21"
    st.metric("Predictive Features", str(num_features))

st.markdown("---")

# System Architecture (Text/Column based to avoid missing images)
st.subheader("⚙️ How It Works (System Architecture)")

flow_col1, flow_col2, flow_col3 = st.columns(3)
with flow_col1:
    st.info("**1. Data Inputs**\n\nWeather (Rainfall, Humidity, Temp) + Livestock Density")
with flow_col2:
    st.warning("**2. Stage 1: Occurrence**\n\nPredicts IF an outbreak will happen (Logistic Regression)")
with flow_col3:
    st.error("**3. Stage 2: Severity**\n\nPredicts HOW BAD it will be (Random Forest Severity)")

st.markdown("---")

# Data Sources
st.subheader("📚 Data Sources")
st.markdown("""
* **DAPH**: Historical Foot-and-Mouth Disease outbreak records (Sri Lanka)
* **CHIRPS**: Satellite-derived high-resolution daily rainfall data
* **NASA POWER**: Meteorological features (Temperature, Humidity, Wind Speed)
* **FAO GLW**: Gridded Livestock of the World (Cattle & Buffalo Density)
* **OCHA**: District Administrative Boundaries
""")

st.divider()
st.caption("Research Component - IT22221414 - Kumarasinghe S.S | 2026")
