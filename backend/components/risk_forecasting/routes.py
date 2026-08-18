"""
FastAPI Router for the Risk Forecasting Component.
Defines endpoints for FMD and LSD outbreak risk prediction, severity classification,
all-district climatological forecasts, district metadata, and health checks.
"""

from fastapi import APIRouter, HTTPException, status
from backend.components.risk_forecasting.config import SRI_LANKA_DISTRICTS, MONTH_NAMES
from backend.components.risk_forecasting.schemas import (
    FMDOutbreakPredictRequest, FMDOutbreakPredictResponse,
    LSDOutbreakPredictRequest, LSDOutbreakPredictResponse,
    FMDForecastRequest, LSDForecastRequest,
    DistrictForecastResponse, FMDDistrictForecastResponse, LSDDistrictForecastResponse,
    HealthCheckResponse, DistrictListResponse
)
from backend.components.risk_forecasting.services.fmd_service import fmd_service
from backend.components.risk_forecasting.services.lsd_service import lsd_service

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse, summary="Component Health Check")
def health_check():
    """Returns component operational health status and loaded model artifacts."""
    loaded_artifacts = fmd_service.loaded_artifacts + lsd_service.loaded_artifacts
    models_ready = fmd_service.models_loaded and lsd_service.models_loaded
    return HealthCheckResponse(
        status="ok" if models_ready else "degraded",
        component="risk_forecasting",
        version="1.0.0",
        models_loaded=models_ready,
        loaded_artifacts=loaded_artifacts
    )


@router.get("/districts", response_model=DistrictListResponse, summary="List Supported Sri Lankan Districts")
def list_districts():
    """Returns the list of 25 supported Sri Lankan administrative districts and 12 month names."""
    return DistrictListResponse(
        total_districts=len(SRI_LANKA_DISTRICTS),
        districts=list(SRI_LANKA_DISTRICTS),
        month_names=list(MONTH_NAMES)
    )


@router.post("/predict/fmd", response_model=FMDOutbreakPredictResponse, summary="Predict FMD Outbreak Risk & Severity")
def predict_fmd(request: FMDOutbreakPredictRequest):
    """
    Predicts Foot-and-Mouth Disease (FMD) outbreak probability (Stage 1) and severity classification (Stage 2)
    with operational decision thresholding (t=0.40), Mondrian conformal uncertainty coverage, and actionable recommendations.
    """
    try:
        return fmd_service.predict(request)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"FMD service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FMD prediction failed: {str(e)}"
        )


@router.post("/predict/lsd", response_model=LSDOutbreakPredictResponse, summary="Predict LSD Outbreak Risk & Severity")
def predict_lsd(request: LSDOutbreakPredictRequest):
    """
    Predicts Lumpy Skin Disease (LSD) Platt-calibrated outbreak probability, risk tier (t=0.40),
    Stage 2 quiet-period suppressor severity, honest non-numeric conformal UQ, and scientific disclaimers.
    """
    try:
        return lsd_service.predict(request)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LSD service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LSD prediction failed: {str(e)}"
        )


@router.post("/forecast/fmd", response_model=FMDDistrictForecastResponse, summary="FMD All-District Forecast")
def forecast_fmd(request: FMDForecastRequest):
    """Generates an all-district climatological FMD risk forecast for the specified month."""
    try:
        year = request.year or 2024
        return fmd_service.compute_forecast(
            target_month=request.target_month,
            year=year,
            model_variant="30_feature_baseline"
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"FMD forecast service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FMD forecast failed: {str(e)}"
        )


@router.post("/forecast/lsd", response_model=LSDDistrictForecastResponse, summary="LSD All-District Forecast")
def forecast_lsd(request: LSDForecastRequest):
    """Generates an all-district climatological LSD risk forecast for the specified month."""
    try:
        year = request.year or 2024
        return lsd_service.compute_forecast(
            target_month=request.target_month,
            year=year
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LSD forecast service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LSD forecast failed: {str(e)}"
        )

