"""
Test Suite for the Risk Forecasting Component API using Python's standard unittest.
Verifies health status, district listing, FMD prediction (30 & 31 feature variants),
LSD Platt-calibrated prediction, all-district climatological forecasts, and schema validations.
"""

import unittest
from unittest.mock import patch
import pandas as pd
from fastapi.testclient import TestClient
from backend.main import app
from backend.components.risk_forecasting.services.fmd_service import fmd_service


class TestRiskForecastingAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_endpoint(self):
        """Verifies backend root endpoint."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")

    def test_health_endpoint(self):
        """Verifies component health check and model loading status."""
        response = self.client.get("/api/v1/risk-forecasting/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(data["status"], ["ok", "degraded"])
        self.assertEqual(data["component"], "risk_forecasting")
        self.assertTrue(data["models_loaded"])
        self.assertGreater(len(data["loaded_artifacts"]), 0)

    def test_list_districts_endpoint(self):
        """Verifies listing all 25 Sri Lankan administrative districts."""
        response = self.client.get("/api/v1/risk-forecasting/districts")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_districts"], 25)
        self.assertIn("Anuradhapura", data["districts"])
        self.assertIn("Jaffna", data["districts"])
        self.assertEqual(len(data["month_names"]), 12)

    def test_fmd_predict_30_feature_baseline(self):
        """Verifies FMD prediction with default 30-feature baseline model."""
        payload = {
            "district": "Anuradhapura",
            "year": 2024,
            "month": 1,
            "model_variant": "30_feature_baseline"
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["disease"], "FMD")
        self.assertEqual(data["district"], "Anuradhapura")
        self.assertEqual(data["stage1"]["decision_threshold"], 0.40)
        self.assertIn(data["stage1"]["risk_level"], ["LOW", "MEDIUM", "HIGH"])
        self.assertEqual(data["uncertainty"]["status"], "HEURISTIC")
        self.assertEqual(data["uncertainty"]["method"], "Rule-Based Risk Tier Uncertainty")
        self.assertNotIn("Conformal", data["uncertainty"]["method"])
        self.assertNotIn("Mondrian", data["uncertainty"]["method"])
        self.assertIsNone(data["uncertainty"]["empirical_coverage_pct"])
        self.assertGreater(len(data["recommendations"]), 0)

    def test_fmd_predict_31_feature_valid_may_2023(self):
        """Scenario A: May 2023 + request 31 -> valid April 2023 lag -> actual model = 31."""
        payload = {
            "district": "Anuradhapura",
            "year": 2023,
            "month": 5,
            "model_variant": "31_feature_autocorrelation"
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["stage1"]["model_variant"], "31_feature_autocorrelation")
        self.assertFalse(data["provenance"]["model_fallback_applied"])
        self.assertIsNone(data["provenance"]["model_fallback_reason"])

    def test_fmd_predict_31_feature_valid_jan_2025(self):
        """Scenario B: January 2025 + request 31 -> valid December 2024 lag -> actual model = 31."""
        payload = {
            "district": "Anuradhapura",
            "year": 2025,
            "month": 1,
            "model_variant": "31_feature_autocorrelation"
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["stage1"]["model_variant"], "31_feature_autocorrelation")
        self.assertFalse(data["provenance"]["model_fallback_applied"])
        self.assertIsNone(data["provenance"]["model_fallback_reason"])

    def test_fmd_predict_31_feature_jan_2017_fallback(self):
        """Scenario C: January 2017 + request 31 -> December 2016 unavailable -> actual model = 30 -> fallback reported."""
        payload = {
            "district": "Anuradhapura",
            "year": 2017,
            "month": 1,
            "model_variant": "31_feature_autocorrelation"
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["stage1"]["model_variant"], "30_feature_baseline")
        self.assertTrue(data["provenance"]["model_fallback_applied"])
        self.assertIn("previous-month surveillance data was unavailable", data["provenance"]["model_fallback_reason"])

    def test_fmd_predict_31_feature_sep_2026_fallback(self):
        """Scenario D: September 2026 + request 31 -> August 2026 unavailable -> actual model = 30 -> fallback reported."""
        payload = {
            "district": "Anuradhapura",
            "year": 2026,
            "month": 9,
            "model_variant": "31_feature_autocorrelation"
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["stage1"]["model_variant"], "30_feature_baseline")
        self.assertTrue(data["provenance"]["model_fallback_applied"])
        self.assertIn("previous-month surveillance data was unavailable", data["provenance"]["model_fallback_reason"])

    def test_fmd_predict_missing_31_feature_artifact_fallback(self):
        """Scenario E: Valid lag + missing 31-feature artifact -> actual model = 30 -> artifact fallback reported."""
        from backend.components.risk_forecasting.services.fmd_service import fmd_service

        original_31_model = fmd_service.models.pop("stage1_31_model", None)
        try:
            payload = {
                "district": "Anuradhapura",
                "year": 2023,
                "month": 5,
                "model_variant": "31_feature_autocorrelation"
            }
            response = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["stage1"]["model_variant"], "30_feature_baseline")
            self.assertTrue(data["provenance"]["model_fallback_applied"])
            self.assertIn("required 31-feature model runtime artifacts", data["provenance"]["model_fallback_reason"])
        finally:
            if original_31_model is not None:
                fmd_service.models["stage1_31_model"] = original_31_model

    def test_lsd_predict_platt_calibrated(self):
        """Verifies LSD Platt-calibrated prediction and honest UQ null-out schema."""
        payload = {
            "district": "Anuradhapura",
            "year": 2024,
            "month": 1
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/lsd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["disease"], "LSD")
        self.assertEqual(data["district"], "Anuradhapura")
        self.assertEqual(data["stage1"]["decision_threshold"], 0.40)
        self.assertEqual(data["stage1"]["model_variant"], "28_feature_autocorrelation")
        self.assertTrue(data["calibration_info"]["is_calibrated"])
        self.assertEqual(data["calibration_info"]["ece_score"], 0.0212)
        self.assertFalse(data["provenance"]["fallback_applied"])
        self.assertFalse(data["provenance"]["model_fallback_applied"])

        # Verify LSD Stage 2 quiet-period suppressor disclaimer & flags
        self.assertEqual(data["stage2"]["model_name"], "LogisticRegression (Quiet-Period Suppressor)")
        self.assertIn("evaluated", data["stage2"])
        self.assertIn("notes", data["stage2"])
        self.assertFalse(data["stage2"]["discriminator_validated"])
        self.assertFalse(data["stage2"]["action_required"])
        self.assertIn("quiet-period false-alarm suppressor", data["disclaimer"])

        # Verify LSD Honest UQ null-out schema
        self.assertEqual(data["uncertainty"]["status"], "UNRELIABLE_INSUFFICIENT_DATA")
        self.assertEqual(data["uncertainty"]["reliability"], "LOW")
        self.assertIsNone(data["uncertainty"]["prediction_set"])
        self.assertIsNone(data["uncertainty"]["empirical_coverage_pct"])

    def test_fmd_honest_uncertainty_metadata(self):
        """Issue 5A: Verifies FMD uncertainty metadata does NOT claim Conformal/Mondrian and reflects honest HEURISTIC status."""
        payload = {
            "district": "Anuradhapura",
            "year": 2024,
            "month": 1,
            "model_variant": "30_feature_baseline"
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        u = data["uncertainty"]
        self.assertEqual(u["method"], "Rule-Based Risk Tier Uncertainty")
        self.assertEqual(u["status"], "HEURISTIC")
        self.assertNotIn("Conformal", u["method"])
        self.assertNotIn("Mondrian", u["method"])
        self.assertIsNone(u["empirical_coverage_pct"])
        self.assertIn("heuristic risk-tier mapping", u["notes"])
        self.assertIn("live conformal calibration is not currently deployed", u["notes"])

        # Verify rule-based prediction set structure remains intact (MEDIUM -> ["MEDIUM", "HIGH"], otherwise [risk_level])
        risk_level = data["stage1"]["risk_level"]
        if risk_level == "MEDIUM":
            self.assertEqual(u["prediction_set"], ["MEDIUM", "HIGH"])
        else:
            self.assertEqual(u["prediction_set"], [risk_level])

    def test_fmd_stage2_honesty_and_advisory_safety(self):
        """Issue 6A: Verifies FMD Stage 2 returns discriminator_validated=False, advisory notes, and advisory recommendation framing."""
        payload = {
            "district": "Anuradhapura",
            "year": 2020,
            "month": 12,
            "model_variant": "30_feature_baseline"
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        s2 = data["stage2"]

        # Verify Stage 2 executed and returns discriminator_validated = False
        self.assertTrue(s2["evaluated"])
        self.assertFalse(s2["discriminator_validated"])
        self.assertEqual(s2["model_name"], "RandomForestClassifier")
        self.assertIn("ADVISORY ONLY", s2["notes"])
        self.assertIn("veterinary/DAPH review is required", s2["notes"])

        # Verify recommendations framing when risk_level is MEDIUM/HIGH
        if data["stage1"]["risk_level"] in ["MEDIUM", "HIGH"]:
            recs_text = " ".join(data["recommendations"])
            self.assertIn("ADVISORY DECISION SUPPORT", recs_text)
            self.assertIn("Veterinary/DAPH confirmation required", recs_text)

    def test_fmd_forecast(self):
        """Scenario F: Verifies all-district FMD forecast returns required model_variant = 30_feature_baseline and target_year."""
        payload = {
            "target_month": 1,
            "year": 2024
        }
        response = self.client.post("/api/v1/risk-forecasting/forecast/fmd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["disease"], "FMD")
        self.assertEqual(data["target_year"], 2024)
        self.assertEqual(data["target_month"], 1)
        self.assertEqual(data["model_variant"], "30_feature_baseline")
        self.assertEqual(data["total_districts"], 25)
        self.assertEqual(len(data["districts"]), 25)

    def test_fmd_forecast_rejects_explicit_31_feature(self):
        """Scenario G: Verifies all-district FMD forecast rejects explicit 31-feature request with HTTP 422 (schema validation)."""
        payload = {
            "target_month": 1,
            "year": 2024,
            "model_variant": "31_feature_autocorrelation"
        }
        response = self.client.post("/api/v1/risk-forecasting/forecast/fmd", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_lsd_forecast(self):
        """Scenario H: Verifies all-district LSD forecast returns LSDDistrictForecastResponse with target_year and summary lag1 fields."""
        payload = {
            "target_month": 1,
            "year": 2024
        }
        response = self.client.post("/api/v1/risk-forecasting/forecast/lsd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["disease"], "LSD")
        self.assertEqual(data["target_year"], 2024)
        self.assertEqual(data["target_month"], 1)
        self.assertNotIn("model_variant", data)
        self.assertEqual(data["total_districts"], 25)
        self.assertEqual(len(data["districts"]), 25)
        self.assertIn("lag1_data_status", data)
        self.assertIn("lag1_verified_district_count", data)
        self.assertIn("lag1_unavailable_district_count", data)

    def test_forecast_echoes_custom_target_year(self):
        """Verifies both FMD and LSD forecast endpoints accurately echo custom requested target_year."""
        fmd_res = self.client.post("/api/v1/risk-forecasting/forecast/fmd", json={"target_month": 9, "year": 2026})
        self.assertEqual(fmd_res.status_code, 200)
        self.assertEqual(fmd_res.json()["target_year"], 2026)

        lsd_res = self.client.post("/api/v1/risk-forecasting/forecast/lsd", json={"target_month": 9, "year": 2026})
        self.assertEqual(lsd_res.status_code, 200)
        self.assertEqual(lsd_res.json()["target_year"], 2026)

    def test_lsd_predict_positive_historical_lag_anuradhapura_dec2020(self):
        """Evidence A: Anuradhapura Dec 2020 -> Nov 2020 ground-truth lag = 1.0 -> MEDIUM risk (prob ~0.4002)."""
        payload = {
            "district": "Anuradhapura",
            "year": 2020,
            "month": 12
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/lsd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["provenance"]["lag1_status"], "VERIFIED_OBSERVATION")
        self.assertEqual(data["provenance"]["lag1_value"], 1.0)
        self.assertEqual(data["stage1"]["model_variant"], "28_feature_autocorrelation")
        self.assertEqual(data["stage1"]["probability_pct"], 40.0)
        self.assertEqual(data["stage1"]["risk_level"], "MEDIUM")

    def test_lsd_predict_jan2025_valid_lag_independent_fallback(self):
        """Evidence B: January 2025 -> valid Dec 2024 lag retrieved -> lag VERIFIED, 28-feature model executed."""
        payload = {
            "district": "Anuradhapura",
            "year": 2025,
            "month": 1
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/lsd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["provenance"]["lag1_status"], "VERIFIED_OBSERVATION")
        self.assertIsNotNone(data["provenance"]["lag1_value"])
        self.assertEqual(data["stage1"]["model_variant"], "28_feature_autocorrelation")
        self.assertTrue(data["provenance"]["fallback_applied"])
        self.assertIn("Used latest available surveillance year", data["provenance"]["fallback_message"])

    def test_lsd_predict_future_date_unavailable_lag_sep2026(self):
        """Evidence C: September 2026 -> Aug 2026 lag unavailable -> UNAVAILABLE, 27-feature fallback executed, Stage 2 bypassed."""
        payload = {
            "district": "Anuradhapura",
            "year": 2026,
            "month": 9
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/lsd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["provenance"]["lag1_status"], "UNAVAILABLE")
        self.assertIsNone(data["provenance"]["lag1_value"])
        self.assertEqual(data["stage1"]["model_variant"], "27_feature_fallback")
        self.assertIn("Executed validated 27-feature fallback model", data["provenance"]["lag1_message"])
        self.assertFalse(data["stage2"]["evaluated"])
        self.assertIn("surveillance data is unavailable", data["stage2"]["notes"])

    def test_lsd_forecast_future_date_unavailable_summary_sep2026(self):
        """Evidence D: September 2026 all-district forecast -> verified count = 0, unavailable count = 25."""
        payload = {
            "target_month": 9,
            "year": 2026
        }
        response = self.client.post("/api/v1/risk-forecasting/forecast/lsd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["lag1_data_status"], "UNAVAILABLE")
        self.assertEqual(data["lag1_verified_district_count"], 0)
        self.assertEqual(data["lag1_unavailable_district_count"], 25)
        self.assertIn("27-feature fallback model for all 25 districts", data["lag1_message"])

    def test_lsd_forecast_historical_all_verified(self):
        """Evidence E: Historical May 2023 forecast where all prior-month observations exist -> verified count = 25."""
        payload = {
            "target_month": 5,
            "year": 2023
        }
        response = self.client.post("/api/v1/risk-forecasting/forecast/lsd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["lag1_data_status"], "VERIFIED_OBSERVATION")
        self.assertEqual(data["lag1_verified_district_count"], 25)
        self.assertEqual(data["lag1_unavailable_district_count"], 0)

    def test_lsd_predict_28_feat_artifact_missing_fallback(self):
        """Scenario: Valid historical lag exists + 28-feature model artifact missing -> fallback to 27-feature model."""
        from backend.components.risk_forecasting.services.lsd_service import lsd_service
        
        # Save original 28-feature model artifact reference
        orig_model = lsd_service.models.pop("stage1_model", None)
        try:
            payload = {
                "district": "Anuradhapura",
                "year": 2020,
                "month": 12
            }
            response = self.client.post("/api/v1/risk-forecasting/predict/lsd", json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["provenance"]["lag1_status"], "VERIFIED_OBSERVATION")
            self.assertEqual(data["stage1"]["model_variant"], "27_feature_fallback")
            self.assertTrue(data["provenance"]["model_fallback_applied"])
            self.assertIn("Executed 27-feature fallback model", data["provenance"]["model_fallback_reason"])
        finally:
            if orig_model is not None:
                lsd_service.models["stage1_model"] = orig_model

    def test_invalid_district_validation(self):
        """Verifies HTTP 422 error for invalid district name."""
        payload = {
            "district": "NonExistentDistrict",
            "year": 2024,
            "month": 1
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_invalid_month_validation(self):
        """Verifies HTTP 422 error for month out of range."""
        payload = {
            "district": "Anuradhapura",
            "year": 2024,
            "month": 13
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_lsd_predict_missing_27_feat_artifact_failure(self):
        """Scenario: Lag unavailable + 27-feature model artifact missing -> returns HTTP 500 cleanly."""
        from backend.components.risk_forecasting.services.lsd_service import lsd_service

        orig_27_model = lsd_service.models.pop("stage1_27feat_model", None)
        try:
            payload = {
                "district": "Anuradhapura",
                "year": 2026,
                "month": 9
            }
            response = self.client.post("/api/v1/risk-forecasting/predict/lsd", json=payload)
            self.assertIn(response.status_code, [500, 503])
            data = response.json()
            self.assertIn("LSD 27-feature fallback artifacts missing", data["detail"])
        finally:
            if orig_27_model is not None:
                lsd_service.models["stage1_27feat_model"] = orig_27_model

    def test_fmd_stage1_local_explainability(self):
        """Issue 7B: Verifies FMD Stage 1 closed-form Linear Log-Odds Decomposition explainability for 30 and 31 feature variants."""
        # 1. Test FMD 30-feature baseline explainability
        payload_30 = {
            "district": "Anuradhapura",
            "year": 2020,
            "month": 12,
            "model_variant": "30_feature_baseline"
        }
        res_30 = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload_30)
        self.assertEqual(res_30.status_code, 200)
        data_30 = res_30.json()

        self.assertIn("explanation_info", data_30)
        exp_30 = data_30["explanation_info"]
        self.assertIsNotNone(exp_30)
        self.assertEqual(exp_30["method"], "Linear Log-Odds Decomposition")
        self.assertNotIn("SHAP", exp_30["method"])
        self.assertEqual(exp_30["model_variant"], "30_feature_baseline")
        self.assertEqual(exp_30["explanation_scope"], "LOCAL_PREDICTION")
        self.assertEqual(exp_30["contribution_unit"], "LOG_ODDS")
        self.assertIsNone(exp_30["provenance_warning"])
        self.assertNotIn("caused by", exp_30["notes"].lower())

        # Verify FMD 30 contains no own_outbreak_lag1
        pos_30_feats = [f["feature"] for f in exp_30["top_risk_increasing"]]
        neg_30_feats = [f["feature"] for f in exp_30["top_risk_decreasing"]]
        self.assertNotIn("own_outbreak_lag1", pos_30_feats)
        self.assertNotIn("own_outbreak_lag1", neg_30_feats)

        # Verify numerical reconstruction consistency
        reconstructed_p = exp_30["reconstructed_probability"]
        stage1_p = data_30["stage1"]["probability"]
        self.assertAlmostEqual(reconstructed_p, stage1_p, places=4)

        # Verify direction and ordering for positive contributions
        pos_contribs = [f["contribution_log_odds"] for f in exp_30["top_risk_increasing"]]
        for p_val in pos_contribs:
            self.assertGreater(p_val, 0)
        self.assertEqual(pos_contribs, sorted(pos_contribs, reverse=True))

        # Verify direction and ordering for negative contributions
        neg_contribs = [f["contribution_log_odds"] for f in exp_30["top_risk_decreasing"]]
        for n_val in neg_contribs:
            self.assertLess(n_val, 0)
        self.assertEqual(neg_contribs, sorted(neg_contribs))

        # 2. Test FMD 31-feature autocorrelation explainability
        payload_31 = {
            "district": "Anuradhapura",
            "year": 2020,
            "month": 12,
            "model_variant": "31_feature_autocorrelation"
        }
        res_31 = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload_31)
        self.assertEqual(res_31.status_code, 200)
        data_31 = res_31.json()

        exp_31 = data_31["explanation_info"]
        self.assertIsNotNone(exp_31)
        self.assertEqual(exp_31["model_variant"], "31_feature_autocorrelation")

        # Check if own_outbreak_lag1 is present in top drivers
        all_31_items = exp_31["top_risk_increasing"] + exp_31["top_risk_decreasing"]
        lag1_item = next((item for item in all_31_items if item["feature"] == "own_outbreak_lag1"), None)
        if lag1_item is not None:
            self.assertEqual(lag1_item["display_label"], "Previous-Month Same-District Outbreak Status")
            self.assertIn(lag1_item["raw_value"], [0.0, 1.0])

        # 3. Test fallback provenance warning (future date Sep 2026)
        payload_fallback = {
            "district": "Anuradhapura",
            "year": 2026,
            "month": 9,
            "model_variant": "30_feature_baseline"
        }
        res_fb = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload_fallback)
        self.assertEqual(res_fb.status_code, 200)
        data_fb = res_fb.json()
        exp_fb = data_fb["explanation_info"]
        self.assertIsNotNone(exp_fb["provenance_warning"])
        self.assertIn("September 2024 historical feature row", exp_fb["provenance_warning"])

        # 4. Test LSD remains unchanged
        payload_lsd = {
            "district": "Anuradhapura",
            "year": 2020,
            "month": 12
        }
        res_lsd = self.client.post("/api/v1/risk-forecasting/predict/lsd", json=payload_lsd)
        self.assertEqual(res_lsd.status_code, 200)
        data_lsd = res_lsd.json()
        self.assertNotIn("explanation_info", data_lsd)

    def test_data_freshness_provenance_and_safe_fallback(self):
        """
        ISSUE 8A Test Suite:
        Verifies explicit data freshness provenance, historical same-month proxy,
        district/national median fallback, data/model fallback independence,
        safe empty-dataset failure, and forecast data quality summaries.
        """
        # A. FMD exact row (2020-12)
        res_fmd_exact = self.client.post("/api/v1/risk-forecasting/predict/fmd", json={
            "district": "Anuradhapura", "year": 2020, "month": 12, "model_variant": "30_feature_baseline"
        })
        self.assertEqual(res_fmd_exact.status_code, 200)
        prov_fmd_exact = res_fmd_exact.json()["provenance"]
        self.assertFalse(prov_fmd_exact["fallback_applied"])
        self.assertEqual(prov_fmd_exact["requested_year"], 2020)
        self.assertEqual(prov_fmd_exact["requested_month"], 12)
        self.assertEqual(prov_fmd_exact["source_year"], 2020)
        self.assertEqual(prov_fmd_exact["source_month"], 12)
        self.assertEqual(prov_fmd_exact["data_age_months"], 0)
        self.assertEqual(prov_fmd_exact["data_quality"], "EXACT_REQUESTED_PERIOD")

        # B. LSD exact row (2020-12)
        res_lsd_exact = self.client.post("/api/v1/risk-forecasting/predict/lsd", json={
            "district": "Anuradhapura", "year": 2020, "month": 12
        })
        self.assertEqual(res_lsd_exact.status_code, 200)
        prov_lsd_exact = res_lsd_exact.json()["provenance"]
        self.assertFalse(prov_lsd_exact["fallback_applied"])
        self.assertEqual(prov_lsd_exact["source_year"], 2020)
        self.assertEqual(prov_lsd_exact["data_age_months"], 0)
        self.assertEqual(prov_lsd_exact["data_quality"], "EXACT_REQUESTED_PERIOD")

        # C. FMD future date (2026-09) historical proxy
        res_fmd_2026 = self.client.post("/api/v1/risk-forecasting/predict/fmd", json={
            "district": "Anuradhapura", "year": 2026, "month": 9, "model_variant": "30_feature_baseline"
        })
        self.assertEqual(res_fmd_2026.status_code, 200)
        data_fmd_2026 = res_fmd_2026.json()
        prov_fmd_2026 = data_fmd_2026["provenance"]
        self.assertTrue(prov_fmd_2026["fallback_applied"])
        self.assertEqual(prov_fmd_2026["source_year"], 2024)
        self.assertEqual(prov_fmd_2026["source_month"], 9)
        self.assertEqual(prov_fmd_2026["data_age_months"], 24)
        self.assertEqual(prov_fmd_2026["data_quality"], "HISTORICAL_SAME_MONTH_PROXY")

        # D. LSD future date (2026-09) historical proxy
        res_lsd_2026 = self.client.post("/api/v1/risk-forecasting/predict/lsd", json={
            "district": "Anuradhapura", "year": 2026, "month": 9
        })
        self.assertEqual(res_lsd_2026.status_code, 200)
        prov_lsd_2026 = res_lsd_2026.json()["provenance"]
        self.assertTrue(prov_lsd_2026["fallback_applied"])
        self.assertEqual(prov_lsd_2026["source_year"], 2024)
        self.assertEqual(prov_lsd_2026["data_age_months"], 24)
        self.assertEqual(prov_lsd_2026["data_quality"], "HISTORICAL_SAME_MONTH_PROXY")

        # E. FMD 31 requested with future date -> model fallback to 30
        res_fmd_31_future = self.client.post("/api/v1/risk-forecasting/predict/fmd", json={
            "district": "Anuradhapura", "year": 2026, "month": 9, "model_variant": "31_feature_autocorrelation"
        })
        self.assertEqual(res_fmd_31_future.status_code, 200)
        data_fmd_31_future = res_fmd_31_future.json()
        self.assertEqual(data_fmd_31_future["stage1"]["model_variant"], "30_feature_baseline")
        self.assertTrue(data_fmd_31_future["provenance"]["model_fallback_applied"])

        # F. LSD future unavailable lag -> selects 27 and bypasses Stage 2
        res_lsd_future = self.client.post("/api/v1/risk-forecasting/predict/lsd", json={
            "district": "Anuradhapura", "year": 2026, "month": 9
        })
        data_lsd_future = res_lsd_future.json()
        self.assertEqual(data_lsd_future["stage1"]["model_variant"], "27_feature_fallback")
        self.assertEqual(data_lsd_future["provenance"]["lag1_status"], "UNAVAILABLE")
        self.assertFalse(data_lsd_future["stage2"]["evaluated"])

        # G. Data fallback vs model fallback independence
        # (LSD 2020-12 has exact environmental row (data fallback=False) and verified lag)
        self.assertFalse(prov_lsd_exact["fallback_applied"])
        self.assertFalse(prov_lsd_exact["model_fallback_applied"])

        # H & I. District and national median provenance date nulls
        fake_df = pd.DataFrame([
            {"district": "Colombo", "year": 2020, "month_num": 1, "r3h": 80.0, "Outbreak status": 0.0}
        ])
        with patch.object(fmd_service, "df", fake_df):
            # District median (no month record for month 5)
            row_dm, fb_dm, _, sy_dm, sm_dm, age_dm, dq_dm = fmd_service.get_feature_row("Colombo", 5, 2026, ["r3h"])
            self.assertTrue(fb_dm)
            self.assertIsNone(sy_dm)
            self.assertIsNone(sm_dm)
            self.assertIsNone(age_dm)
            self.assertEqual(dq_dm, "DISTRICT_HISTORICAL_MEDIAN")

            # National median (unknown district)
            row_nm, fb_nm, _, sy_nm, sm_nm, age_nm, dq_nm = fmd_service.get_feature_row("UnknownDistrict", 5, 2026, ["r3h"])
            self.assertTrue(fb_nm)
            self.assertIsNone(sy_nm)
            self.assertIsNone(sm_nm)
            self.assertIsNone(age_nm)
            self.assertEqual(dq_nm, "NATIONAL_HISTORICAL_MEDIAN")

            # J & K. Safe failure when dataset is empty
            with patch.object(fmd_service, "df", pd.DataFrame()):
                res_empty = self.client.post("/api/v1/risk-forecasting/predict/fmd", json={
                    "district": "Anuradhapura", "year": 2024, "month": 1, "model_variant": "30_feature_baseline"
                })
                self.assertIn(res_empty.status_code, [500, 503])
                self.assertIn("empty or unavailable", res_empty.json()["detail"].lower())

        # L. FMD explanation provenance warning for historical proxy
        exp_warn = data_fmd_2026["explanation_info"]["provenance_warning"]
        self.assertIn("September 2024 historical feature row as a proxy for the requested September 2026 period", exp_warn)

        # O & P. Forecast data-quality summary (2026 forecast)
        res_fmd_fc = self.client.post("/api/v1/risk-forecasting/forecast/fmd", json={"target_month": 9, "year": 2026})
        self.assertEqual(res_fmd_fc.status_code, 200)
        fc_fmd_data = res_fmd_fc.json()
        self.assertEqual(fc_fmd_data["historical_proxy_district_count"], 25)
        self.assertEqual(fc_fmd_data["data_quality_status"], "HISTORICAL_PROXY")

        res_lsd_fc = self.client.post("/api/v1/risk-forecasting/forecast/lsd", json={"target_month": 9, "year": 2026})
        self.assertEqual(res_lsd_fc.status_code, 200)
        fc_lsd_data = res_lsd_fc.json()
        self.assertEqual(fc_lsd_data["historical_proxy_district_count"], 25)
        self.assertEqual(fc_lsd_data["data_quality_status"], "HISTORICAL_PROXY")
        self.assertEqual(fc_lsd_data["lag1_data_status"], "UNAVAILABLE")  # Separate lag summary preserved


if __name__ == "__main__":
    unittest.main()

