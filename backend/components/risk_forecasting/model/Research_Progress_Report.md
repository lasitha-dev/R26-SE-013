# Research Progress Report: Climate-Informed Seasonal Livestock Disease Forecasting

**Component Phase 1:** FMD Outbreak Prediction — Sri Lanka (2017–2024)
**Prepared for:** Supervisor Review

---

## 1. Executive Summary
This document outlines the progress and methodologies established for the first phase of the **"Climate-Informed Seasonal Livestock Disease Forecasting"** project. We have successfully developed a robust, end-to-end machine learning pipeline to predict Foot-and-Mouth Disease (FMD) outbreaks across 25 districts in Sri Lanka. 

The pipeline spans raw environmental data ingestion, complex spatio-temporal feature engineering, walk-forward model validation, uncertainty quantification, and interactive visualization via a custom Streamlit application.

---

## 2. Technology Stack & Tooling
*   **Data Processing & Engineering:** Python, Pandas, NumPy, GeoPandas (for spatial data).
*   **Machine Learning Models:** Scikit-Learn, XGBoost, LightGBM.
*   **Model Explainability & Uncertainty:** SHAP (Shapley Additive exPlanations), Bootstrap Sampling.
*   **Dashboard & Visualization:** Streamlit, Matplotlib, Seaborn.
*   **Version Control & Architecture:** Git, Jupyter Notebooks (modularized 01 to 09), modular Python scripts.

---

## 3. The Research Pipeline: Step-by-Step

### Step 1: Data Collection & Understanding
To accurately model disease outbreaks, we integrated diverse datasets to capture environmental, spatial, and historical contexts:
*   **Outbreak Data:** Historical FMD records from the Department of Animal Production and Health (DAPH).
*   **Meteorological Data:** High-resolution rainfall data from CHIRPS.
*   **Livestock Demographics:** Cattle and buffalo density data from the Gridded Livestock of the World (GLW).
*   **Spatial Data:** Sri Lankan administrative boundaries for district-level aggregation.

### Step 2: Data Preprocessing & Feature Engineering
We applied advanced feature engineering to translate raw climatic variables into predictive signals, ultimately optimizing the dataset to **21 core features**.
*   **Cyclical Time Encoding:** Applied sine/cosine transformations to months to capture the cyclical nature of seasons.
*   **Monsoon Phases:** Engineered categorical representations of Sri Lanka's specific monsoon seasons (Yala, Maha, Inter-monsoonal).
*   **Weather Lags:** Created rolling averages and lagged features (e.g., rainfall 1 month or 2 months prior) to account for the incubation period and environmental persistence of the FMD virus.

### Step 3: Exploratory Data Analysis (EDA)
Comprehensive EDA was conducted to identify spatial hotspots, temporal trends, and correlations. We addressed extreme class imbalances (outbreak vs. non-outbreak months) and verified the distribution of our engineered weather lags against actual outbreak occurrences.

### Step 4: Model Selection & Training Strategy
Standard random train-test splitting causes data leakage in time-series data. Therefore, we implemented **expanding-window walk-forward validation** to simulate real-world forecasting:
*   **Fold 1:** Train 2017–2021 → Test 2022
*   **Fold 2:** Train 2017–2022 → Test 2023
*   **Fold 3:** Train 2017–2023 → Test 2024

**Models Evaluated:** We tested Logistic Regression, Random Forest, Gradient Boosting, and XGBoost against a Seasonal Naive baseline. Tree-based ensembles (like XGBoost/Random Forest) were ultimately selected for their ability to handle non-linear interactions between weather lags and livestock densities.

### Step 5: Model Performance (Stage 1)
The optimized Stage 1 model demonstrated high predictive capability, achieving the following metrics:
*   **ROC-AUC:** 0.843
*   **Recall (Sensitivity):** 76.9% (Crucial for an early warning system to catch the majority of outbreaks)
*   **Precision:** 52.6%
*   **F1-Score:** 0.625

### Step 6: Model Explainability & Uncertainty Quantification
To build trust in the model's predictions:
*   **SHAP Analysis:** We implemented SHAP values to identify feature importance, determining exactly how much rainfall lags and livestock density contribute to specific district predictions.
*   **Bootstrap Uncertainty:** We applied bootstrap sampling techniques to quantify the confidence intervals of our predictions, ensuring the model's robustness against data variance.

### Step 7: Interactive Dashboard & Climatological Forecasting
We developed a fully interactive, multi-page Streamlit application (`app/`) to serve as the prototype for the end-user early warning system.
*   **Modules Built:** Data Explorer, Model Performance Visualizer, Live Outbreak Predictor, and Model Explainability.
*   **Climatological Forecasts:** Integrated a *District Forecast* module capable of projecting risks based on future climatological data (e.g., Jan 2025 forecasts).

---

## 4. Immediate Next Steps & Future Work

With the methodology proven on FMD, the immediate next steps are two-fold:

**1. Expanding Research to Lumpy Skin Disease (LSD)**
*   Replicate and adapt the established machine learning pipeline to analyze and predict **Lumpy Skin Disease (LSD)**.
*   Investigate the unique meteorological and environmental drivers specific to the transmission of LSD in Sri Lanka.

**2. Client-Facing System Implementation & Deployment**
Transitioning the Streamlit prototype into a scalable production system across 4 phases:
*   **Phase 1 (Core System):** Backend, API, and robust Database development.
*   **Phase 2 (Access & Interface):** User authentication, role-based access control (RBAC), and finalized dashboard UI.
*   **Phase 3 (Operational Features):** Automated alert notifications, action-taking/response logging, and automated PDF report generation.
*   **Phase 4 (Delivery):** Cloud deployment and hosting for high availability.
