"""
LSD (Lumpy Skin Disease) Risk Forecasting Service.
Handles Platt-calibrated 28-feature Elastic Net inference for LSD Stage 1,
Logistic Regression quiet-period suppressor for Stage 2, honest non-numeric conformal UQ,
and climatological forecasting.
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
)
from backend.components.risk_forecasting.config import (
    LSD_DATASET_FILE,
    LSD_STAGE1_MODEL, LSD_STAGE1_SCALER, LSD_STAGE1_COLS,
    LSD_STAGE1_27FEAT_MODEL, LSD_STAGE1_27FEAT_SCALER, LSD_STAGE1_27FEAT_COLS, LSD_STAGE1_27FEAT_META,
    LSD_STAGE2_MODEL, LSD_STAGE2_LABEL_ENCODER, LSD_STAGE2_FEATURE_COLS,
    GLOBAL_DECISION_THRESHOLD, HIGH_RISK_THRESHOLD,
    SRI_LANKA_DISTRICTS, MONTH_NAMES
)
from backend.components.risk_forecasting.schemas import (
    LSDOutbreakPredictRequest, LSDOutbreakPredictResponse,
    Stage1Prediction, Stage2Prediction, CalibrationInfo, UncertaintyInfo, DataProvenance, LSDDataProvenance,
    DistrictForecastResponse, LSDDistrictForecastResponse, DistrictForecastItem
)

logger = logging.getLogger(__name__)


class LSDService:
    def __init__(self, data_provider: Optional[ForecastDataProvider] = None):
        self.data_provider = data_provider or CsvForecastDataProvider()
        self.models_loaded = False
        self.loaded_artifacts = []
        self.models: Dict[str, Any] = {}
        self._load_resources()

    @property
    def df(self) -> pd.DataFrame:
        if isinstance(self.data_provider, CsvForecastDataProvider):
            return self.data_provider._get_dataset("LSD")
        return getattr(self, "_df", pd.DataFrame())

    @df.setter
    def df(self, value: pd.DataFrame):
        if isinstance(self.data_provider, CsvForecastDataProvider):
            self.data_provider._datasets["LSD"] = value
        else:
            self._df = value

    @df.deleter
    def df(self):
        if isinstance(self.data_provider, CsvForecastDataProvider):
            self.data_provider._load_datasets()
        if hasattr(self, "_df"):
            del self._df

    def _load_resources(self):
        """Loads LSD model artifacts and feature dataset via provider."""
        try:
            # Stage 1 28-feature Elastic Net baseline
            if LSD_STAGE1_MODEL.exists():
                self.models["stage1_model"] = joblib.load(LSD_STAGE1_MODEL)
                self.models["stage1_scaler"] = joblib.load(LSD_STAGE1_SCALER)
                self.models["stage1_cols"] = joblib.load(LSD_STAGE1_COLS)
                self.loaded_artifacts.append("stage1_elastic_net_28feat")

            # Stage 1 27-feature Elastic Net fallback model
            if LSD_STAGE1_27FEAT_MODEL.exists():
                self.models["stage1_27feat_model"] = joblib.load(LSD_STAGE1_27FEAT_MODEL)
                self.models["stage1_27feat_scaler"] = joblib.load(LSD_STAGE1_27FEAT_SCALER)
                self.models["stage1_27feat_cols"] = joblib.load(LSD_STAGE1_27FEAT_COLS)
                self.loaded_artifacts.append("stage1_elastic_net_27feat_fallback")

            # Stage 2 Logistic Regression quiet-period suppressor model
            if LSD_STAGE2_MODEL.exists():
                self.models["stage2_model"] = joblib.load(LSD_STAGE2_MODEL)
                self.models["stage2_encoder"] = joblib.load(LSD_STAGE2_LABEL_ENCODER)
                self.models["stage2_cols"] = joblib.load(LSD_STAGE2_FEATURE_COLS)
                self.loaded_artifacts.append("stage2_lr_quiet_period_suppressor")

            # Dataset indicator via CSV provider
            if isinstance(self.data_provider, CsvForecastDataProvider) and self.data_provider.lsd_dataset_path.exists():
                self.loaded_artifacts.append("LSD_dataset")

            self.models_loaded = ("stage1_model" in self.models) or ("stage1_27feat_model" in self.models)
            logger.info(f"LSDService successfully loaded {len(self.loaded_artifacts)} artifacts.")
        except Exception as e:
            logger.error(f"Error loading LSD resources: {e}")
            self.models_loaded = False

    def _get_valid_lag1(self, district: str, year: int, month: int) -> Optional[float]:
        """Delegates ground-truth t-1 lag observation lookup to data_provider."""
        return self.data_provider.get_valid_lag1("LSD", district, year, month)

    def _get_feature_row(self, district: str, month_num: int, year: int, feature_cols: List[str]) -> Tuple[pd.DataFrame, bool, str, Optional[int], Optional[int], Optional[int], str]:
        """Delegates feature row extraction and provenance to data_provider."""
        district_enc_val = 0.0
        if "stage2_encoder" in self.models:
            try:
                district_enc_val = float(self.models["stage2_encoder"].transform([district])[0])
            except Exception:
                district_enc_val = 0.0

        return self.data_provider.get_feature_row(
            disease="LSD",
            district=district,
            month_num=month_num,
            year=year,
            feature_cols=feature_cols,
            district_enc_val=district_enc_val
        )

    def _decode_severity(self, pred_val: int) -> str:
        """Decodes Stage 2 quiet-period suppressor output."""
        mapping = {0: "LOW", 1: "MOD_HIGH", 2: "HIGH"}
        return mapping.get(pred_val, "LOW")

    def _generate_recommendations(self, risk_level: str, probability: float) -> List[str]:
        """Generates actionable field-veterinary recommendations based on Stage 1 outbreak risk."""
        if risk_level == "HIGH":
            return [
                "HIGH LSD OUTBREAK RISK DETECTED",
                "Immediately alert district veterinary officers and DAPH Animal Health Division",
                "Activate local vector control programs (biting flies, ticks, mosquitoes)",
                "Prepare LSD vaccination supplies for surrounding livestock herds",
                "Implement cattle movement controls across district borders"
            ]
        elif risk_level == "MEDIUM":
            return [
                "INCREASED LSD SURVEILLANCE RECOMMENDED",
                "Elevated LSD outbreak probability detected above operational decision threshold (t=0.40)",
                "Review local vector control protocols and district vaccination readiness",
                "Increase farm surveillance frequency in high cattle density sectors",
                "Note: Stage 2 severity predictions serve as quiet-period suppression only"
            ]
        else:
            return [
                "ROUTINE MONITORING",
                "Standard LSD surveillance protocols apply",
                "No immediate intervention required",
                "Maintain regular livestock health checks and reporting"
            ]

    def predict(self, request: LSDOutbreakPredictRequest) -> LSDOutbreakPredictResponse:
        """Executes full LSD prediction using 28-feature model when lag-1 is verified, or 27-feature fallback model when lag-1 is unavailable."""
        if not self.models_loaded:
            raise RuntimeError("LSD model artifacts not loaded. Check model paths.")

        # Target autocorrelation lag-1 observation retrieval
        lag1_val = self._get_valid_lag1(request.district, request.year, request.month)

        model_fallback_applied = False
        model_fallback_reason = None

        if lag1_val is not None:
            lag1_status = "VERIFIED_OBSERVATION"
            lag1_value = lag1_val
            lag1_msg = f"Verified t-1 ground-truth surveillance observation used for own_outbreak_lag1 ({lag1_val})."
            
            if "stage1_model" in self.models:
                model_variant = "28_feature_autocorrelation"
                model = self.models["stage1_model"]
                scaler = self.models["stage1_scaler"]
                feat_cols = list(self.models["stage1_cols"])
                use_28_model = True
            elif "stage1_27feat_model" in self.models:
                model_variant = "27_feature_fallback"
                model = self.models["stage1_27feat_model"]
                scaler = self.models["stage1_27feat_scaler"]
                feat_cols = list(self.models["stage1_27feat_cols"])
                use_28_model = False
                model_fallback_applied = True
                model_fallback_reason = "Executed 27-feature fallback model because 28-feature runtime model artifacts were missing."
            else:
                raise RuntimeError("No LSD Stage 1 model artifacts available.")
        else:
            lag1_status = "UNAVAILABLE"
            lag1_value = None
            lag1_msg = f"Previous-month surveillance data was unavailable for {request.district} ({request.year}-{request.month:02d}). Executed validated 27-feature fallback model without target autocorrelation."
            
            if "stage1_27feat_model" in self.models:
                model_variant = "27_feature_fallback"
                model = self.models["stage1_27feat_model"]
                scaler = self.models["stage1_27feat_scaler"]
                feat_cols = list(self.models["stage1_27feat_cols"])
                use_28_model = False
            else:
                raise RuntimeError("LSD 27-feature fallback artifacts missing and previous-month surveillance data is unavailable.")

        # Extract Environmental Feature Row with data freshness provenance
        feature_row, fallback_applied, fallback_msg, src_yr, src_m, data_age, data_qual = self._get_feature_row(
            district=request.district,
            month_num=request.month,
            year=request.year,
            feature_cols=feat_cols
        )

        # Inject lag-1 into feature row ONLY if using 28-feature model
        if use_28_model:
            feature_row["own_outbreak_lag1"] = lag1_val

        for col in feat_cols:
            if col not in feature_row.columns:
                feature_row[col] = 0.0

        # Stage 1 Inference
        x_stage1 = feature_row[feat_cols].fillna(0.0).astype(float)
        x_stage1_scaled = scaler.transform(x_stage1)
        prob = float(model.predict_proba(x_stage1_scaled)[:, 1][0])
        prob_pct = round(prob * 100, 1)

        # Risk level mapping based on audited t = 0.40 boundary
        if prob >= HIGH_RISK_THRESHOLD:
            risk_level = "HIGH"
        elif prob >= GLOBAL_DECISION_THRESHOLD:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Stage 2 Quiet-Period Suppressor Inference
        severity_pred_str = "LOW"
        severity_code = 0
        evaluated = False

        if lag1_status == "UNAVAILABLE":
            notes = "Stage 2 evaluation bypassed because previous-month target autocorrelation lag-1 surveillance data is unavailable."
        elif prob < GLOBAL_DECISION_THRESHOLD:
            notes = "Stage 2 evaluation bypassed because Stage 1 outbreak risk is below decision threshold (t=0.40)."
        elif "stage2_model" in self.models:
            evaluated = True
            notes = "Stage 2 quiet-period suppressor model explicitly evaluated."
            stage2_cols = list(self.models["stage2_cols"])
            
            # Inject lag-1 into Stage 2 feature row if lag was verified
            if "own_outbreak_lag1" in stage2_cols and lag1_val is not None:
                feature_row["own_outbreak_lag1"] = lag1_val

            for col in stage2_cols:
                if col not in feature_row.columns:
                    feature_row[col] = 0.0
            x_stage2 = feature_row[stage2_cols].fillna(0.0).astype(float)
            severity_code = int(self.models["stage2_model"].predict(x_stage2)[0])
            severity_pred_str = self._decode_severity(severity_code)
        else:
            notes = "Stage 2 model artifacts unavailable."

        month_name = MONTH_NAMES[request.month - 1]
        recommendations = self._generate_recommendations(risk_level, prob)

        disclaimer_text = (
            "LSD Stage 2 binary severity predictions serve strictly as a quiet-period false-alarm "
            "suppressor (LOW vs MOD/HIGH) and are NOT statistically validated to discriminate severity "
            "during active outbreak waves (0% specificity during 2023 wave)."
        )

        return LSDOutbreakPredictResponse(
            disease="LSD",
            district=request.district,
            year=request.year,
            month=request.month,
            month_name=month_name,
            stage1=Stage1Prediction(
                probability=prob,
                probability_pct=prob_pct,
                risk_level=risk_level,
                decision_threshold=GLOBAL_DECISION_THRESHOLD,
                model_variant=model_variant
            ),
            stage2=Stage2Prediction(
                severity_predicted=severity_pred_str,
                severity_code=severity_code,
                model_name="LogisticRegression (Quiet-Period Suppressor)",
                evaluated=evaluated,
                discriminator_validated=False,
                action_required=False,
                notes=notes
            ),
            calibration_info=CalibrationInfo(
                is_calibrated=True,
                calibration_method="Inner-CV Platt Scaling (CalibratedClassifierCV, cv=4)",
                ece_score=0.0212 if use_28_model else 0.0511,
                notes="Probability calibration significantly reduced full-dataset out-of-fold ECE. Evaluated under time-isolated LOYO validation protocol."
            ),
            uncertainty=UncertaintyInfo(
                method="Mondrian Conformal Prediction (Class-Conditional)",
                status="UNRELIABLE_INSUFFICIENT_DATA",
                reliability="LOW",
                prediction_set=None,
                empirical_coverage_pct=None,
                notes="Numeric conformal coverage bounds omitted due to small positive sample size (N_pos ~ 20)."
            ),
            recommendations=recommendations,
            disclaimer=disclaimer_text,
            provenance=LSDDataProvenance(
                fallback_applied=fallback_applied,
                fallback_message=fallback_msg,
                requested_year=request.year,
                requested_month=request.month,
                source_year=src_yr,
                source_month=src_m,
                data_age_months=data_age,
                data_quality=data_qual,
                lag1_status=lag1_status,
                lag1_value=lag1_value,
                lag1_message=lag1_msg,
                model_fallback_applied=model_fallback_applied,
                model_fallback_reason=model_fallback_reason
            )
        )

    def get_feature_row(self, district: str, month_num: int, year: int, feature_cols: List[str]) -> Tuple[pd.DataFrame, bool, str, Optional[int], Optional[int], Optional[int], str]:
        return self._get_feature_row(district, month_num, year, feature_cols)

    def compute_forecast(self, target_month: int, year: int = 2024) -> LSDDistrictForecastResponse:
        """Computes all-district LSD risk forecast for a given month with data quality summary."""
        results: List[DistrictForecastItem] = []
        high_cnt, med_cnt, low_cnt = 0, 0, 0
        verified_cnt, unavailable_cnt = 0, 0
        exact_cnt, proxy_cnt, median_cnt = 0, 0, 0

        for district in SRI_LANKA_DISTRICTS:
            req = LSDOutbreakPredictRequest(
                district=district,
                year=year,
                month=target_month
            )
            res = self.predict(req)

            if res.provenance.data_quality == "EXACT_REQUESTED_PERIOD":
                exact_cnt += 1
            elif res.provenance.data_quality == "HISTORICAL_SAME_MONTH_PROXY":
                proxy_cnt += 1
            else:
                median_cnt += 1

            if res.provenance.lag1_status == "VERIFIED_OBSERVATION":
                verified_cnt += 1
            else:
                unavailable_cnt += 1

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

        if verified_cnt == total_d:
            lag1_data_status = "VERIFIED_OBSERVATION"
            top_lag1_msg = f"Verified t-1 surveillance ground truth available for all {verified_cnt} forecasted districts."
        elif unavailable_cnt == total_d:
            lag1_data_status = "UNAVAILABLE"
            top_lag1_msg = f"Target month forecast executed using 27-feature fallback model for all {unavailable_cnt} districts due to unavailable t-1 surveillance data."
        else:
            lag1_data_status = "MIXED"
            top_lag1_msg = f"Target month forecast executed with mixed lag-1 availability ({verified_cnt} verified using 28-feature model, {unavailable_cnt} unavailable using 27-feature fallback model)."

        if exact_cnt == total_d:
            dq_status = "EXACT"
            dq_msg = f"All {total_d} districts evaluated using exact requested period ({year}-{target_month:02d}) feature rows."
        elif proxy_cnt == total_d:
            dq_status = "HISTORICAL_PROXY"
            dq_msg = f"All {total_d} districts evaluated using historical same-month proxy rows for target period ({year}-{target_month:02d})."
        else:
            dq_status = "MIXED"
            dq_msg = f"Forecast evaluated using mixed feature data quality: {exact_cnt} exact, {proxy_cnt} historical proxy, {median_cnt} historical median districts."

        return LSDDistrictForecastResponse(
            disease="LSD",
            target_year=year,
            target_month=target_month,
            target_month_name=month_name,
            total_districts=total_d,
            high_risk_count=high_cnt,
            medium_risk_count=med_cnt,
            low_risk_count=low_cnt,
            districts=results,
            lag1_data_status=lag1_data_status,
            lag1_verified_district_count=verified_cnt,
            lag1_unavailable_district_count=unavailable_cnt,
            lag1_message=top_lag1_msg,
            exact_data_district_count=exact_cnt,
            historical_proxy_district_count=proxy_cnt,
            historical_median_district_count=median_cnt,
            data_quality_status=dq_status,
            data_quality_message=dq_msg
        )


# Singleton Instance
lsd_service = LSDService()
