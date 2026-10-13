import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Ensure app directory is in path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "app") not in sys.path:
    sys.path.append(str(ROOT_DIR / "app"))

from utils import load_data, display_image_gracefully, apply_custom_css

st.set_page_config(page_title="Data Explorer | FMD Early Warning", page_icon="📈", layout="wide")
apply_custom_css()

st.title("📈 Data Explorer & EDA")
st.markdown("Explore the final engineered dataset and view Exploratory Data Analysis (EDA) visualizations.")
st.divider()

PLOTS_DIR = ROOT_DIR / "plots" / "03_eda"

# ─── SECTION 1: Interactive Dataset ───────────────────────────────────────────
st.header("1. Interactive Dataset")
st.markdown("The final aligned dataset combining DAPH outbreak records, CHIRPS rainfall, NASA POWER climate, and FAO GLW livestock densities.")

with st.spinner("Loading dataset..."):
    df = load_data()

if not df.empty:
    st.dataframe(df, use_container_width=True, height=300)
    
    # Dataset statistics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Records", f"{len(df):,}")
    col2.metric("Features", f"{len(df.columns)}")
    col3.metric("Districts", f"{df['district'].nunique()}")
    col4.metric("Years", f"{df['year'].min()} – {df['year'].max()}")
else:
    st.error("Could not load the dataset.")

st.divider()

# ─── SECTION 2: Exploratory Data Analysis ─────────────────────────────────────
st.header("2. Exploratory Data Analysis (EDA)")

st.subheader("Disease Distribution")
col5, col6 = st.columns(2)
with col5:
    display_image_gracefully(PLOTS_DIR / "class_balance.png", "Stage 1 Class Balance (Outbreak vs No Outbreak)")
with col6:
    display_image_gracefully(PLOTS_DIR / "outbreaks_by_year.png", "FMD Outbreaks by Year (2017-2024)")

st.info("💡 **How to explain this:** The Class Balance chart (left) shows that actual Outbreaks (1) are much rarer than non-outbreak months (0), which is standard for disease data. The Outbreaks by Year chart (right) highlights the overall historical trend of FMD cases over the 8-year study period.")

st.markdown("<br>", unsafe_allow_html=True)

display_image_gracefully(PLOTS_DIR / "outbreak_distribution.png", "FMD Outbreaks by District and Month")

st.info("💡 **How to explain this:** This heatmap identifies historical outbreak hotspots. We can clearly point out that certain districts and specific months have consistently higher occurrences of FMD, mathematically proving there is a strong spatial and seasonal pattern to the disease.")

st.divider()

st.subheader("Feature Relationships")
st.markdown("Correlation matrix highlighting the relationship between climate variables and outbreak occurrence.")

col7, col8, col9 = st.columns([1, 4, 1])
with col8:
    display_image_gracefully(PLOTS_DIR / "correlation_heatmap.png", "Spearman Correlation Heatmap")

st.info("💡 **How to explain this:** The Correlation Heatmap shows how different climate variables relate to each other and to the actual disease outbreak. Darker red and blue spots indicate strong correlations, proving that specific weather patterns are statistically linked to higher FMD risk before we even train the AI.")

st.divider()
st.caption("Research Component - IT22221414 - Kumarasinghe S.S | 2026")
