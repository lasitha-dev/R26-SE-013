"""
FMD (Foot-and-Mouth Disease) Risk Forecasting Service.
Handles two-stage inference for FMD (Stage 1 Logistic Regression with 30/31-feature model variants,
Stage 2 Random Forest severity classification, Mondrian Conformal Prediction UQ, and climatological forecasting).
"""

import logging
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

import joblib
import numpy as np
import pandas as pd

from backend.components.risk_forecasting.integrations import (
    ForecastDataProvider,
    CsvForecastDataProvider,
    create_forecast_data_provider,
)
from backend.components.risk_forecasting.config import (
    FMD_DATASET_FILE,
    FMD_STAGE1_30FEAT_MODEL, FMD_STAGE1_30FEAT_SCALER, FMD_STAGE1_30FEAT_COLS,
    FMD_STAGE1_31FEAT_MODEL, FMD_STAGE1_31FEAT_SCALER, FMD_STAGE1_31FEAT_COLS,
    FMD_STAGE2_RF_MODEL, FMD_STAGE2_LABEL_ENCODER, FMD_STAGE2_FEATURE_COLS,
    GLOBAL_DECISION_THRESHOLD, HIGH_RISK_THRESHOLD,
    SRI_LANKA_DISTRICTS, MONTH_NAMES
)
from backend.components.risk_forecasting.schemas import (
    FMDOutbreakPredictRequest, FMDOutbreakPredictResponse,
    Stage1Prediction, Stage2Prediction, CalibrationInfo, UncertaintyInfo, DataProvenance, FMDDataProvenance,
    DistrictForecastResponse, FMDDistrictForecastResponse, DistrictForecastItem,
    FeatureContribution, ExplanationInfo
)

logger = logging.getLogger(__name__)


FMD_FEATURE_DISPLAY_LABELS = {
    "own_outbreak_lag1": "Previous-Month Same-District Outbreak Status",
    "neighbor_outbreak_lag1": "Previous-Month Neighboring-District Outbreak Status",
    "neighbor_outbreak_count_lag1": "Previous-Month Neighboring-District Outbreak Count",
    "neighbor_outbreak_fraction_lag1": "Previous-Month Neighboring-District Outbreak Fraction",
    "neighbor_outbreak_lag2": "Outbreak Status in Neighboring Districts (2-Month Lag)",
    "rainfall_mm": "Monthly Rainfall (mm)",
    "rain_lag1": "Previous-Month Rainfall (mm)",
    "rain_lag2": "Rainfall 2 Months Prior (mm)",
    "r3h": "3-Hour Relative Humidity (%)",
    "rfq": "Rainfall Frequency Quantity Index",
    "rfq_lag1": "Previous-Month Rainfall Frequency Index",
    "humidity": "Average Relative Humidity (%)",
    "humidity_lag1": "Previous-Month Relative Humidity (%)",
    "temp_lag1": "Previous-Month Mean Temperature (°C)",
    "wind_speed": "Mean Wind Speed (m/s)",
    "wind_lag1": "Previous-Month Mean Wind Speed (m/s)",
    "cattle_density": "Cattle Population Density (heads/km²)",
    "buffalo_density": "Buffalo Population Density (heads/km²)",
    "goat_density": "Goat Population Density (heads/km²)",
    "livestock_density": "Total Livestock Population Density (heads/km²)",
    "nino34": "El Niño-Southern Oscillation (NINO3.4 Index)",
    "nino34_lag3": "El Niño Index (3-Month Lag)",
    "iod_dmi": "Indian Ocean Dipole (Dipole Mode Index)",
    "iod_dmi_lag2": "Indian Ocean Dipole Index (2-Month Lag)",
    "sin_month": "Seasonal Cycle Component A (Sine)",
    "cos_month": "Seasonal Cycle Component B (Cosine)",
    "monsoon_phase_First_Inter_Monsoon": "First Inter-Monsoon Season (Mar–Apr)",
    "monsoon_phase_SW_Monsoon": "Southwest Monsoon Season (May–Sep)",
    "monsoon_phase_Second_Inter_Monsoon": "Second Inter-Monsoon Season (Oct–Nov)",
    "monsoon_phase_NE_Monsoon": "Northeast Monsoon Season (Dec–Feb)",
    "district_enc": "District Baseline Susceptibility Code"
}


class FMDService:
    def __init__(self, data_provider: Optional[ForecastDataProvider] = None):
        self.data_provider = data_provider or create_forecast_data_provider()
        self.models_loaded = False
        self.loaded_artifacts = []
        self.models: Dict[str, Any] = {}
        self._load_resources()

    @property
    def df(self) -> pd.DataFrame:
        if isinstance(self.data_provider, CsvForecastDataProvider):
            return self.data_provider._get_dataset("FMD")
        return getattr(self, "_df", pd.DataFrame())

    @df.setter
    def df(self, value: pd.DataFrame):
        if isinstance(self.data_provider, CsvForecastDataProvider):
            self.data_provider._datasets["FMD"] = value
        else:
            self._df = value

    @df.deleter
    def df(self):
        if isinstance(self.data_provider, CsvForecastDataProvider):
            self.data_provider._load_datasets()
        if hasattr(self, "_df"):
            del self._df

    def _load_resources(self):
        """Loads FMD model artifacts and feature dataset via provider."""
        try:
            # Stage 1 30-feature baseline
            if FMD_STAGE1_30FEAT_MODEL.exists():
                self.models["stage1_30_model"] = joblib.load(FMD_STAGE1_30FEAT_MODEL)
                self.models["stage1_30_scaler"] = joblib.load(FMD_STAGE1_30FEAT_SCALER)
                self.models["stage1_30_cols"] = joblib.load(FMD_STAGE1_30FEAT_COLS)
                self.loaded_artifacts.append("stage1_lr_model_30feat")

            # Stage 1 31-feature ROC-AUC variant
            if FMD_STAGE1_31FEAT_MODEL.exists():
                self.models["stage1_31_model"] = joblib.load(FMD_STAGE1_31FEAT_MODEL)
                self.models["stage1_31_scaler"] = joblib.load(FMD_STAGE1_31FEAT_SCALER)
                self.models["stage1_31_cols"] = joblib.load(FMD_STAGE1_31FEAT_COLS)
                self.loaded_artifacts.append("stage1_lr_model_31feat")

            # Stage 2 Random Forest severity model
            if FMD_STAGE2_RF_MODEL.exists():
                self.models["stage2_model"] = joblib.load(FMD_STAGE2_RF_MODEL)
                self.models["stage2_encoder"] = joblib.load(FMD_STAGE2_LABEL_ENCODER)
                self.models["stage2_cols"] = joblib.load(FMD_STAGE2_FEATURE_COLS)
                self.loaded_artifacts.append("stage2_rf_model")

            # Dataset indicator via CSV provider
            if isinstance(self.data_provider, CsvForecastDataProvider) and self.data_provider.fmd_dataset_path.exists():
                self.loaded_artifacts.append("FMD_dataset")

            self.models_loaded = "stage1_30_model" in self.models
            logger.info(f"FMDService successfully loaded {len(self.loaded_artifacts)} artifacts.")
        except Exception as e:
            logger.error(f"Error loading FMD resources: {e}")
            self.models_loaded = False

    def _get_valid_lag1(self, district: str, year: int, month: int) -> Optional[float]:
        """Delegates ground-truth t-1 lag observation lookup to data_provider."""
        return self.data_provider.get_valid_lag1("FMD", district, year, month)

    def _get_feature_row(self, district: str, month_num: int, year: int, feature_cols: List[str]) -> Tuple[pd.DataFrame, bool, str, Optional[int], Optional[int], Optional[int], str]:
        """Delegates feature row extraction and provenance to data_provider."""
        district_enc_val = 0.0
        if "stage2_encoder" in self.models:
            try:
                district_enc_val = float(self.models["stage2_encoder"].transform([district])[0])
            except Exception:
                district_enc_val = 0.0

        return self.data_provider.get_feature_row(
            disease="FMD",
            district=district,
            month_num=month_num,
            year=year,
            feature_cols=feature_cols,
            district_enc_val=district_enc_val
        )

    def _decode_severity(self, pred_val: int) -> str:
        """Decodes Stage 2 severity prediction integer code (0: LOW, 1: MEDIUM, 2: HIGH)."""
        mapping = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
        return mapping.get(pred_val, "LOW")


    def _generate_recommendations(self, risk_level: str, severity: str) -> List[str]:
        """Generates actionable field-veterinary recommendations based on risk and severity."""
        if risk_level == "HIGH" and severity == "HIGH":
            return [
                "ADVISORY DECISION SUPPORT — Veterinary/DAPH confirmation required before intervention",
                "Notify DAPH Animal Health Division for field evaluation",
                "Consider activating emergency vaccination campaign in high-risk zones",
                "Evaluate livestock movement restrictions within district",
                "Deploy rapid response veterinary officer teams for field investigation"
            ]
        elif risk_level == "HIGH":
            return [
                "ADVISORY DECISION SUPPORT — Veterinary/DAPH confirmation required before intervention",
                "Alert district veterinary surgeons for advisory review",
                "Consider targeted ring vaccination in high-density livestock zones",
                "Increase farm biosecurity and active surveillance frequency"
            ]
        elif risk_level == "MEDIUM":
            return [
                "INCREASED SURVEILLANCE RECOMMENDED",
                "Routine monitoring with increased inspection frequency",
                "Review district vaccination coverage and vaccine cold-chain readiness",
                "Monitor regional livestock movement and market entry points"
            ]
        else:
            return [
                "ROUTINE MONITORING",
                "Standard surveillance protocols apply",
                "Maintain baseline disease reporting and farm biosecurity awareness"
            ]

    def predict(self, request: FMDOutbreakPredictRequest) -> FMDOutbreakPredictResponse:
        """Executes full FMD prediction using selected 30-feature or 31-feature model variant."""
        if not self.models_loaded:
            raise RuntimeError("FMD model artifacts not loaded. Check model paths.")

        use_31feat_requested = (request.model_variant == "31_feature_autocorrelation")
        has_31feat_artifacts = (
            "stage1_31_model" in self.models and
            "stage1_31_scaler" in self.models and
            "stage1_31_cols" in self.models
        )

        model_fallback_applied = False
        model_fallback_reason = None
        lag1_val = None

        if use_31feat_requested:
            lag1_val = self._get_valid_lag1(request.district, request.year, request.month)
            if lag1_val is None:
                model = self.models["stage1_30_model"]
                scaler = self.models["stage1_30_scaler"]
                feat_cols = list(self.models["stage1_30_cols"])
                variant_name = "30_feature_baseline"
                model_fallback_applied = True
                model_fallback_reason = f"Requested 31_feature_autocorrelation, but previous-month surveillance data was unavailable for {request.district} ({request.year}-{request.month:02d}). Automatically executed 30_feature_baseline."
            elif not has_31feat_artifacts:
                model = self.models["stage1_30_model"]
                scaler = self.models["stage1_30_scaler"]
                feat_cols = list(self.models["stage1_30_cols"])
                variant_name = "30_feature_baseline"
                model_fallback_applied = True
                model_fallback_reason = "Requested 31_feature_autocorrelation, but required 31-feature model runtime artifacts (stage1_31_model/scaler/cols) were not loaded. Automatically executed 30_feature_baseline."
            else:
                model = self.models["stage1_31_model"]
                scaler = self.models["stage1_31_scaler"]
                feat_cols = list(self.models["stage1_31_cols"])
                variant_name = "31_feature_autocorrelation"
        else:
            model = self.models["stage1_30_model"]
            scaler = self.models["stage1_30_scaler"]
            feat_cols = list(self.models["stage1_30_cols"])
            variant_name = "30_feature_baseline"

        # Feature retrieval with data freshness provenance
        x_raw, fallback_applied, fallback_msg, src_yr, src_m, data_age, data_qual = self._get_feature_row(
            district=request.district,
            month_num=request.month,
            year=request.year,
            feature_cols=feat_cols
        )

        # Inject lag1 for 31-feature variant if present
        if variant_name == "31_feature_autocorrelation" and lag1_val is not None:
            x_raw["own_outbreak_lag1"] = lag1_val

        for col in feat_cols:
            if col not in x_raw.columns:
                x_raw[col] = 0.0

        x_stage1 = x_raw[feat_cols].fillna(0.0).astype(float)
        x_stage1_scaled = scaler.transform(x_stage1)

        # Stage 1 prediction
        prob = float(model.predict_proba(x_stage1_scaled)[0, 1])
        prob_pct = round(prob * 100.0, 1)

        if prob >= HIGH_RISK_THRESHOLD:
            risk_level = "HIGH"
        elif prob >= GLOBAL_DECISION_THRESHOLD:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Stage 2 severity prediction
        evaluated = False
        severity_code = 0
        severity_pred_str = "LOW"
        notes = "Stage 2 evaluation bypassed because Stage 1 outbreak risk is below decision threshold (t=0.40)."

        if prob >= GLOBAL_DECISION_THRESHOLD and "stage2_model" in self.models:
            evaluated = True
            s2_cols = list(self.models["stage2_cols"])
            x_s2_raw, _, _, _, _, _, _ = self._get_feature_row(
                district=request.district,
                month_num=request.month,
                year=request.year,
                feature_cols=s2_cols
            )
            for col in s2_cols:
                if col not in x_s2_raw.columns:
                    x_s2_raw[col] = 0.0
            x_s2 = x_s2_raw[s2_cols].fillna(0.0).astype(float)
            severity_code = int(self.models["stage2_model"].predict(x_s2)[0])
            severity_pred_str = self._decode_severity(severity_code)
            notes = f"Stage 2 Random Forest severity model evaluated (predicted {severity_pred_str}). ADVISORY ONLY: Stage 2 has limited multi-class severity discrimination; veterinary/DAPH review is required prior to operational intervention."

        recommendations = self._generate_recommendations(risk_level, severity_pred_str)
        month_name = MONTH_NAMES[request.month - 1]

        if risk_level == "MEDIUM":
            prediction_set = ["MEDIUM", "HIGH"]
        else:
            prediction_set = [risk_level]

        # Local Explainability (Closed-Form Linear Log-Odds Decomposition)
        explanation_info = self._compute_explanation(
            model=model,
            scaler=scaler,
            feat_cols=feat_cols,
            x_stage1=x_stage1,
            x_stage1_scaled=x_stage1_scaled,
            variant_name=variant_name,
            fallback_applied=fallback_applied,
            data_quality=data_qual,
            requested_year=request.year,
            requested_month=request.month,
            source_year=src_yr,
            source_month=src_m
        )

        return FMDOutbreakPredictResponse(
            disease="FMD",
            district=request.district,
            year=request.year,
            month=request.month,
            month_name=month_name,
            stage1=Stage1Prediction(
                probability=prob,
                probability_pct=prob_pct,
                risk_level=risk_level,
                decision_threshold=GLOBAL_DECISION_THRESHOLD,
                model_variant=variant_name
            ),
            stage2=Stage2Prediction(
                severity_predicted=severity_pred_str if evaluated else "N/A",
                severity_code=severity_code,
                model_name="RandomForestClassifier",
                evaluated=evaluated,
                discriminator_validated=False,
                action_required=(severity_pred_str in ["MEDIUM", "HIGH"]) if evaluated else False,
                notes=notes
            ),
            calibration_info=CalibrationInfo(
                is_calibrated=False,
                calibration_method="Uncalibrated Raw Logistic Regression",
                ece_score=None,
                notes="FMD uses raw walk-forward logistic regression probabilities per validated baseline."
            ),
            uncertainty=UncertaintyInfo(
                method="Rule-Based Risk Tier Uncertainty",
                status="HEURISTIC",
                reliability="MEDIUM",
                prediction_set=prediction_set,
                empirical_coverage_pct=None,
                notes="Prediction sets are generated using a heuristic risk-tier mapping. Offline Phase 7 research demonstrated 95.3% overall coverage (94.9% outbreak class) for Split Conformal Prediction, but live conformal calibration is not currently deployed."
            ),
            recommendations=recommendations,
            provenance=FMDDataProvenance(
                fallback_applied=fallback_applied,
                fallback_message=fallback_msg,
                requested_year=request.year,
                requested_month=request.month,
                source_year=src_yr,
                source_month=src_m,
                data_age_months=data_age,
                data_quality=data_qual,
                model_fallback_applied=model_fallback_applied,
                model_fallback_reason=model_fallback_reason
            ),
            explanation_info=explanation_info
        )

    def _compute_explanation(
        self,
        model: Any,
        scaler: Any,
        feat_cols: List[str],
        x_stage1: pd.DataFrame,
        x_stage1_scaled: np.ndarray,
        variant_name: str,
        fallback_applied: bool,
        data_quality: str,
        requested_year: int,
        requested_month: int,
        source_year: Optional[int],
        source_month: Optional[int]
    ) -> ExplanationInfo:
        intercept = float(model.intercept_[0])
        coefs = model.coef_[0]

        contributions = coefs * x_stage1_scaled[0]
        reconstructed_score = float(intercept + np.sum(contributions))
        reconstructed_prob = float(1.0 / (1.0 + np.exp(-reconstructed_score)))

        items: List[FeatureContribution] = []
        for i, col in enumerate(feat_cols):
            val = float(x_stage1[col].iloc[0])
            c_val = float(contributions[i])

            label = FMD_FEATURE_DISPLAY_LABELS.get(col, col.replace("_", " ").title())

            if c_val > 1e-6:
                direction = "RISK_INCREASING"
            elif c_val < -1e-6:
                direction = "RISK_DECREASING"
            else:
                direction = "NEUTRAL"

            items.append(FeatureContribution(
                feature=col,
                display_label=label,
                raw_value=round(val, 4),
                contribution_log_odds=round(c_val, 4),
                direction=direction
            ))

        positives = sorted([it for it in items if it.direction == "RISK_INCREASING"], key=lambda x: x.contribution_log_odds, reverse=True)[:5]
        negatives = sorted([it for it in items if it.direction == "RISK_DECREASING"], key=lambda x: x.contribution_log_odds)[:5]

        provenance_warning = None
        if fallback_applied:
            if data_quality == "HISTORICAL_SAME_MONTH_PROXY" and source_year is not None and source_month is not None:
                src_m_name = MONTH_NAMES[source_month - 1]
                req_m_name = MONTH_NAMES[requested_month - 1]
                provenance_warning = f"This explanation uses a {src_m_name} {source_year} historical feature row as a proxy for the requested {req_m_name} {requested_year} period."
            else:
                provenance_warning = "This explanation uses aggregated historical median feature values."

        notes = "Feature contributions represent additive impacts on Logistic Regression log-odds score relative to training-mean baseline. Factors influencing this model prediction."

        return ExplanationInfo(
            method="Linear Log-Odds Decomposition",
            model_variant=variant_name,
            explanation_scope="LOCAL_PREDICTION",
            contribution_unit="LOG_ODDS",
            baseline_description="Model decision score relative to training-mean standardized baseline.",
            top_risk_increasing=positives,
            top_risk_decreasing=negatives,
            decision_score=round(reconstructed_score, 6),
            reconstructed_probability=round(reconstructed_prob, 6),
            provenance_warning=provenance_warning,
            notes=notes
        )

    def get_feature_row(self, district: str, month_num: int, year: int, feature_cols: List[str]) -> Tuple[pd.DataFrame, bool, str, Optional[int], Optional[int], Optional[int], str]:
        return self._get_feature_row(district, month_num, year, feature_cols)

    def compute_forecast(self, target_month: int, year: int = 2024, model_variant: str = "30_feature_baseline") -> FMDDistrictForecastResponse:
        """Computes all-district FMD risk forecast for a given month using 30_feature_baseline with data quality summary."""
        results: List[DistrictForecastItem] = []
        high_cnt, med_cnt, low_cnt = 0, 0, 0
        exact_cnt, proxy_cnt, median_cnt = 0, 0, 0
        executed_variant = "30_feature_baseline"

        for district in SRI_LANKA_DISTRICTS:
            req = FMDOutbreakPredictRequest(
                district=district,
                year=year,
                month=target_month,
                model_variant=executed_variant
            )
            res = self.predict(req)

            if res.provenance.data_quality == "EXACT_REQUESTED_PERIOD":
                exact_cnt += 1
            elif res.provenance.data_quality == "HISTORICAL_SAME_MONTH_PROXY":
                proxy_cnt += 1
            else:
                median_cnt += 1

            if res.stage1.risk_level == "HIGH":
                high_cnt += 1
            elif res.stage1.risk_level == "MEDIUM":
                med_cnt += 1
            else:
                low_cnt += 1

            results.append(DistrictForecastItem(
                district=district,
                probability_pct=res.stage1.probability_pct,
                risk_level=res.stage1.risk_level,
                predicted_severity=res.stage2.severity_predicted
            ))

        results.sort(key=lambda x: x.probability_pct, reverse=True)
        month_name = MONTH_NAMES[target_month - 1]
        total_d = len(results)

        if exact_cnt == total_d:
            dq_status = "EXACT"
            dq_msg = f"All {total_d} districts evaluated using exact requested period ({year}-{target_month:02d}) feature rows."
        elif proxy_cnt == total_d:
            dq_status = "HISTORICAL_PROXY"
            dq_msg = f"All {total_d} districts evaluated using historical same-month proxy rows for target period ({year}-{target_month:02d})."
        else:
            dq_status = "MIXED"
            dq_msg = f"Forecast evaluated using mixed feature data quality: {exact_cnt} exact, {proxy_cnt} historical proxy, {median_cnt} historical median districts."

        return FMDDistrictForecastResponse(
            disease="FMD",
            target_year=year,
            target_month=target_month,
            target_month_name=month_name,
            model_variant=executed_variant,
            total_districts=total_d,
            high_risk_count=high_cnt,
            medium_risk_count=med_cnt,
            low_risk_count=low_cnt,
            districts=results,
            exact_data_district_count=exact_cnt,
            historical_proxy_district_count=proxy_cnt,
            historical_median_district_count=median_cnt,
            data_quality_status=dq_status,
            data_quality_message=dq_msg
        )


# Singleton Instance
fmd_service = FMDService()
