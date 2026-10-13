import streamlit as st
import datetime
from pathlib import Path
import sys

# Ensure app directory is in path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "app") not in sys.path:
    sys.path.append(str(ROOT_DIR / "app"))

from utils import (
    load_data, load_models, compute_climatological_forecast,
    render_forecast_table, generate_forecast_csv,
    DISTRICTS, MONTH_NAMES, apply_custom_css
)

st.set_page_config(page_title="District Forecast | FMD Early Warning", page_icon="🗺️", layout="wide")
apply_custom_css()

st.title("🗺️ District Forecast")
st.markdown("Monthly risk forecast for all 25 districts using Climatological Mean estimation.")
st.divider()

# Load data
with st.spinner("Loading models and data..."):
    df = load_data()
    models = load_models()

if df.empty or "stage1_model" not in models:
    st.error("Failed to load required models or data. Please check the project structure.")
    st.stop()

# Default to next calendar month
current_month = datetime.datetime.now().month
default_target_month = (current_month % 12) + 1
default_target_month_name = MONTH_NAMES[default_target_month - 1]

# Month selector
target_month_name = st.selectbox(
    "Select Forecast Month", 
    MONTH_NAMES, 
    index=MONTH_NAMES.index(default_target_month_name)
)
target_month = MONTH_NAMES.index(target_month_name) + 1

st.info(
    f"""
**Climatological Mean Method:** Climate inputs are estimated using 2017–2024 historical {target_month_name} averages per district. 
This provides a true forward-looking forecast when real weather data is not yet available.
    """
)

with st.spinner(f"Computing forecast for {target_month_name}..."):
    forecast_df = compute_climatological_forecast(
        df=df,
        models=models,
        districts=DISTRICTS,
        target_month=target_month,
    )

if forecast_df.empty:
    st.warning(f"No data available to compute forecast for {target_month_name}.")
else:
    # Summary statistics
    st.markdown("### Forecast Summary")
    col1, col2, col3 = st.columns(3)
    
    high_count = len(forecast_df[forecast_df["Risk Level"] == "HIGH"])
    medium_count = len(forecast_df[forecast_df["Risk Level"] == "MEDIUM"])
    low_count = len(forecast_df[forecast_df["Risk Level"] == "LOW"])
    
    col1.metric("🔴 HIGH Risk Districts", high_count)
    col2.metric("🟠 MEDIUM Risk Districts", medium_count)
    col3.metric("🟢 LOW Risk Districts", low_count)
    
    st.markdown("---")
    
    # Ranked Table
    st.markdown("### Ranked Risk Table")
    render_forecast_table(forecast_df)
    
    # Download button
    csv_data = generate_forecast_csv(forecast_df)
    st.download_button(
        label=f"📥 Download {target_month_name} Forecast as CSV",
        data=csv_data,
        file_name=f"fmd_forecast_{target_month_name}.csv",
        mime="text/csv",
        width="stretch",
    )
    
    st.markdown("---")
    
    # Dynamic Visualization
    st.markdown(f"### Visual Risk Distribution ({target_month_name})")
    
    # Prepare data for chart: Sort by probability (ascending for horizontal bar chart if we used altair, 
    # but for st.bar_chart it's vertical. Let's keep it sorted descending as it is in the dataframe).
    chart_df = forecast_df.set_index("District")[["Outbreak Probability (%)"]]
    
    # Use native Streamlit bar chart
    st.bar_chart(chart_df, color="#E8593C")
