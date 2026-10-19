"""
Risk Forecasting Component Package.
Provides FastAPI routes, schemas, and prediction services for FMD and LSD epidemiological risk forecasting.
"""

__version__ = "1.0.0"

# Code walkthrough:
# 1. routes.py exposes prediction and decision-management endpoints.
# 2. pipeline/features.py builds lagged inputs; predictor.py selects a v2 model.
# 3. services/forecast_v2_service.py generates traceable monthly decision records.
# 4. Advisory, notification and follow-up services turn records into reviewed actions.
# 5. repositories/ persists those records independently of the forecasting maths.
