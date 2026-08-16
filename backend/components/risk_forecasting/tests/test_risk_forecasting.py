"""
Test Suite for the Risk Forecasting Component API using Python's standard unittest.
Verifies health status, district listing, FMD prediction (30 & 31 feature variants),
LSD Platt-calibrated prediction, all-district climatological forecasts, and schema validations.
"""

import unittest
from fastapi.testclient import TestClient
from backend.main import app


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
        self.assertFalse(data["calibration_info"]["is_calibrated"])
        self.assertEqual(data["uncertainty"]["status"], "VALIDATED")
        self.assertEqual(data["uncertainty"]["empirical_coverage_pct"], 94.9)
        self.assertGreater(len(data["recommendations"]), 0)

    def test_fmd_predict_31_feature_autocorrelation(self):
        """Verifies FMD prediction with 31-feature target autocorrelation variant."""
        payload = {
            "district": "Anuradhapura",
            "year": 2024,
            "month": 1,
            "model_variant": "31_feature_autocorrelation"
        }
        response = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["stage1"]["model_variant"], "31_feature_autocorrelation")
        self.assertEqual(data["stage1"]["decision_threshold"], 0.40)

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
        self.assertEqual(data["stage1"]["model_variant"], "28_feature_elastic_net")
        self.assertTrue(data["calibration_info"]["is_calibrated"])
        self.assertEqual(data["calibration_info"]["ece_score"], 0.0212)


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

    def test_fmd_forecast(self):
        """Verifies all-district FMD forecast."""
        payload = {
            "target_month": 1,
            "year": 2024
        }
        response = self.client.post("/api/v1/risk-forecasting/forecast/fmd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["disease"], "FMD")
        self.assertEqual(data["target_month"], 1)
        self.assertEqual(data["total_districts"], 25)
        self.assertEqual(len(data["districts"]), 25)

    def test_lsd_forecast(self):
        """Verifies all-district LSD forecast."""
        payload = {
            "target_month": 1,
            "year": 2024
        }
        response = self.client.post("/api/v1/risk-forecasting/forecast/lsd", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["disease"], "LSD")
        self.assertEqual(data["target_month"], 1)
        self.assertEqual(data["total_districts"], 25)
        self.assertEqual(len(data["districts"]), 25)

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


if __name__ == "__main__":
    unittest.main()
