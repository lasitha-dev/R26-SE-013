import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Ensure app directory is in path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "app") not in sys.path:
    sys.path.append(str(ROOT_DIR / "app"))

from utils import display_image_gracefully, apply_custom_css

st.set_page_config(page_title="Model Performance | FMD Early Warning", page_icon="📊", layout="wide")
apply_custom_css()

st.title("📊 Model Performance & Validation")
st.markdown("Detailed validation metrics and evaluation plots for the two-stage prediction pipeline.")
st.divider()

# Paths
PLOTS_DIR = ROOT_DIR / "plots"
DATA_DIR = ROOT_DIR / "data" / "processed"

# ─── SECTION 1: Walk-Forward Validation ────────────────────────────────────────
st.header("1. Walk-Forward Validation Results (Stage 1)")
st.markdown("""
To prevent data leakage in time-series data, models were evaluated using **Walk-Forward Validation**:
- **Fold 1:** Train 2017–2021 → Test 2022
- **Fold 2:** Train 2017–2022 → Test 2023
- **Fold 3:** Train 2017–2023 → Test 2024
""")

col1_1, col1_2 = st.columns(2)
with col1_1:
    display_image_gracefully(
        PLOTS_DIR / "04_model_comparison" / "model_comparison_chart.png", 
        "Model Comparison across Walk-Forward Folds"
    )
with col1_2:
    display_image_gracefully(
        PLOTS_DIR / "04_model_comparison" / "f1_per_split.png", 
        "F1 Score Stability across Folds"
    )

st.info("💡 **How to explain this:** These charts show that Logistic Regression consistently outperformed other algorithms across all three time-splits. The F1 score stability chart on the right proves the model is robust and doesn't overfit to any specific year.")

st.markdown("### Model Comparison Metrics (Averaged across folds)")
comparison_csv = DATA_DIR / "model_comparison.csv"
if comparison_csv.exists():
    comp_df = pd.read_csv(comparison_csv)
    st.dataframe(comp_df, hide_index=True, use_container_width=True)
    st.info("💡 **Selection Rationale:** Logistic Regression was chosen for Stage 1 as it achieved the highest stable Recall, prioritizing the capture of actual outbreaks (minimizing false negatives).")
else:
    st.warning("model_comparison.csv not found.")

st.divider()

# ─── SECTION 2: Final Model Testing (2024 Unseen Data) ────────────────────────
st.header("2. Final Model Testing (2024 Data)")
st.markdown("Performance of the chosen Logistic Regression model tested purely on 2024 data.")

final_metrics_csv = DATA_DIR / "model_comparison_final_model result.csv"
if final_metrics_csv.exists():
    final_df = pd.read_csv(final_metrics_csv)
    st.dataframe(final_df, hide_index=True, use_container_width=True)

col2_1, col2_2 = st.columns(2)
with col2_1:
    display_image_gracefully(
        PLOTS_DIR / "05_final_predictions" / "confusion_matrix.png", 
        "Confusion Matrix (2024 Test Set)"
    )
with col2_2:
    display_image_gracefully(
        PLOTS_DIR / "05_final_predictions" / "model_confidence_metrics.png", 
        "Overall Confidence Metrics"
    )

st.info("💡 **How to explain this:** The Confusion Matrix reveals our model's strong ability to catch actual outbreaks (high True Positives), which is the most critical requirement for an early warning system. The Confidence Metrics on the right confirm the strong overall accuracy on completely unseen 2024 test data.")

st.markdown("### Spatial & Temporal Predictions vs Reality")
display_image_gracefully(
    PLOTS_DIR / "05_final_predictions" / "actual_vs_predicted.png", 
    "Actual vs Predicted Heatmaps (2024)"
)

st.info("💡 **How to explain this:** This heatmap visually compares what actually happened in 2024 (top) versus what our model predicted (bottom). The strong alignment between the dark red spots proves the model successfully identifies both the exact timing and spatial location of outbreaks.")

col2_3, col2_4 = st.columns(2)
with col2_3:
    display_image_gracefully(
        PLOTS_DIR / "05_final_predictions" / "outbreak_probability.png", 
        "Outbreak Probability by District & Month"
    )
with col2_4:
    display_image_gracefully(
        PLOTS_DIR / "05_final_predictions" / "district_risk_ranking.png", 
        "District Risk Ranking (Mean Probability)"
    )

st.info("💡 **How to explain this:** These plots break down the model's risk predictions. The left plot shows the probability of an outbreak for every district across all 12 months, while the right plot ranks the districts by their overall average risk throughout the year.")

st.divider()
st.caption("Research Component - IT22221414 - Kumarasinghe S.S | 2026")
