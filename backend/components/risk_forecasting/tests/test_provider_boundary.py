"""
Characterization and ForecastDataProvider Contract Test Suite.
Verifies deterministic characterization baselines, CsvForecastDataProvider contract,
dependency injection into FMD and LSD services, and preservation of feature contracts.
"""

import unittest
from pathlib import Path
import pandas as pd

from backend.components.risk_forecasting.config import (
    FMD_DATASET_FILE,
    LSD_DATASET_FILE,
)
from backend.components.risk_forecasting.integrations import (
    ForecastDataProvider,
    CsvForecastDataProvider,
)
from backend.components.risk_forecasting.services.fmd_service import FMDService, fmd_service
from backend.components.risk_forecasting.services.lsd_service import LSDService, lsd_service
from backend.components.risk_forecasting.schemas import (
    FMDOutbreakPredictRequest,
    LSDOutbreakPredictRequest,
)


class MockForecastDataProvider(ForecastDataProvider):
    """Custom mock provider for dependency injection testing."""

    def __init__(self, mock_row_df=None, mock_lag1=None):
        self.mock_row_df = mock_row_df
        self.mock_lag1 = mock_lag1

    def get_feature_row(self, disease, district, month_num, year, feature_cols, district_enc_val=0.0):
        if self.mock_row_df is not None:
            res_df = self.mock_row_df.copy()
            for col in feature_cols:
                if col not in res_df.columns:
                    res_df[col] = 0.0
            return (
                res_df[feature_cols],
                False,
                f"Mock feature row for {district}.",
                year,
                month_num,
                0,
                "EXACT_REQUESTED_PERIOD",
            )
        # Default fallback dataframe
        df = pd.DataFrame([[0.0] * len(feature_cols)], columns=feature_cols)
        return (df, False, "Mock row", year, month_num, 0, "EXACT_REQUESTED_PERIOD")

    def get_valid_lag1(self, disease, district, year, month):
        return self.mock_lag1


class TestProviderBoundaryAndCharacterization(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.csv_provider = CsvForecastDataProvider()

    # --- SECTION 3: CHARACTERIZATION TESTS ---

    def test_characterization_fmd_exact_period(self):
        """1. FMD exact-period prediction characterization (Anuradhapura Dec 2020)."""
        req = FMDOutbreakPredictRequest(
            district="Anuradhapura", year=2020, month=12, model_variant="30_feature_baseline"
        )
        res = fmd_service.predict(req)
        self.assertEqual(res.disease, "FMD")
        self.assertEqual(res.district, "Anuradhapura")
        self.assertEqual(res.provenance.data_quality, "EXACT_REQUESTED_PERIOD")
        self.assertFalse(res.provenance.fallback_applied)
        self.assertAlmostEqual(res.stage1.probability, 0.85625, places=4)
        self.assertEqual(res.stage1.risk_level, "HIGH")

    def test_characterization_fmd_fallback_behavior(self):
        """2. FMD fallback behavior characterization (Anuradhapura Sep 2026)."""
        req = FMDOutbreakPredictRequest(
            district="Anuradhapura", year=2026, month=9, model_variant="30_feature_baseline"
        )
        res = fmd_service.predict(req)
        self.assertTrue(res.provenance.fallback_applied)
        self.assertEqual(res.provenance.data_quality, "HISTORICAL_SAME_MONTH_PROXY")
        self.assertEqual(res.provenance.source_year, 2024)
        self.assertEqual(res.provenance.source_month, 9)

    def test_characterization_lsd_verified_previous_month(self):
        """3. LSD prediction characterization with verified previous-month observation."""
        req = LSDOutbreakPredictRequest(district="Anuradhapura", year=2020, month=12)
        res = lsd_service.predict(req)
        self.assertEqual(res.disease, "LSD")
        self.assertEqual(res.provenance.lag1_status, "VERIFIED_OBSERVATION")
        self.assertEqual(res.provenance.lag1_value, 1.0)
        self.assertEqual(res.stage1.model_variant, "28_feature_autocorrelation")

    def test_characterization_lsd_unavailable_previous_month_fallback(self):
        """4. LSD 27-feature fallback characterization when previous observation is unavailable."""
        req = LSDOutbreakPredictRequest(district="Anuradhapura", year=2026, month=9)
        res = lsd_service.predict(req)
        self.assertEqual(res.provenance.lag1_status, "UNAVAILABLE")
        self.assertIsNone(res.provenance.lag1_value)
        self.assertEqual(res.stage1.model_variant, "27_feature_fallback")
        self.assertFalse(res.stage2.evaluated)

    def test_characterization_all_district_fmd_forecast(self):
        """5. All-district FMD forecast characterization."""
        res = fmd_service.compute_forecast(target_month=1, year=2024)
        self.assertEqual(res.disease, "FMD")
        self.assertEqual(res.total_districts, 25)
        self.assertEqual(len(res.districts), 25)
        self.assertEqual(res.model_variant, "30_feature_baseline")

    def test_characterization_all_district_lsd_forecast(self):
        """6. All-district LSD forecast characterization."""
        res = lsd_service.compute_forecast(target_month=1, year=2024)
        self.assertEqual(res.disease, "LSD")
        self.assertEqual(res.total_districts, 25)
        self.assertEqual(len(res.districts), 25)
        self.assertIn("lag1_data_status", res.model_dump())

    def test_characterization_provenance_and_fallback_messages(self):
        """7. Data provenance and fallback messages characterization."""
        req = FMDOutbreakPredictRequest(
            district="Anuradhapura", year=2026, month=9, model_variant="31_feature_autocorrelation"
        )
        res = fmd_service.predict(req)
        self.assertTrue(res.provenance.model_fallback_applied)
        self.assertIn("previous-month surveillance data was unavailable", res.provenance.model_fallback_reason)
        self.assertTrue(res.provenance.fallback_applied)
        self.assertIn("historical same-month proxy", res.provenance.fallback_message)

    def test_characterization_feature_column_order(self):
        """8. Feature-column order supplied to the models characterization."""
        cols_30 = fmd_service.models["stage1_30_cols"]
        self.assertEqual(len(cols_30), 30)
        self.assertEqual(cols_30[0], "sin_month")
        self.assertEqual(cols_30[-1], "district_enc")

        cols_lsd_28 = lsd_service.models["stage1_cols"]
        self.assertEqual(len(cols_lsd_28), 28)
        self.assertEqual(cols_lsd_28[0], "sin_month")

    # --- SECTION 6: PROVIDER ARCHITECTURE & CONTRACT TESTS ---

    def test_provider_configured_fmd_dataset_access(self):
        """Req 6.1: Configured FMD dataset access."""
        df = self.csv_provider._get_dataset("FMD")
        self.assertFalse(df.empty)
        self.assertIn("district", df.columns)
        self.assertIn("Outbreak status", df.columns)

    def test_provider_configured_lsd_dataset_access(self):
        """Req 6.2: Configured LSD dataset access."""
        df = self.csv_provider._get_dataset("LSD")
        self.assertFalse(df.empty)
        self.assertIn("district", df.columns)
        self.assertIn("Outbreak status", df.columns)

    def test_provider_exact_period_retrieval(self):
        """Req 6.3: Exact-period feature row retrieval."""
        cols = fmd_service.models["stage1_30_cols"]
        row, fb, msg, sy, sm, age, dq = self.csv_provider.get_feature_row(
            "FMD", "Anuradhapura", 12, 2020, cols
        )
        self.assertFalse(fb)
        self.assertEqual(sy, 2020)
        self.assertEqual(sm, 12)
        self.assertEqual(age, 0)
        self.assertEqual(dq, "EXACT_REQUESTED_PERIOD")
        self.assertEqual(len(row.columns), len(cols))

    def test_provider_historical_same_month_fallback(self):
        """Req 6.4: Historical same-month fallback retrieval."""
        cols = fmd_service.models["stage1_30_cols"]
        row, fb, msg, sy, sm, age, dq = self.csv_provider.get_feature_row(
            "FMD", "Anuradhapura", 9, 2026, cols
        )
        self.assertTrue(fb)
        self.assertEqual(sy, 2024)
        self.assertEqual(sm, 9)
        self.assertEqual(age, 24)
        self.assertEqual(dq, "HISTORICAL_SAME_MONTH_PROXY")

    def test_provider_district_historical_median_fallback(self):
        """Req 6.5: District historical median fallback."""
        cols = fmd_service.models["stage1_30_cols"]
        fake_df = pd.DataFrame([
            {"district": "Colombo", "year": 2020, "month_num": 1, "rainfall_mm": 100.0}
        ])
        provider = CsvForecastDataProvider()
        provider._datasets["FMD"] = fake_df
        row, fb, msg, sy, sm, age, dq = provider.get_feature_row(
            "FMD", "Colombo", 5, 2026, cols
        )
        self.assertTrue(fb)
        self.assertIsNone(sy)
        self.assertIsNone(sm)
        self.assertIsNone(age)
        self.assertEqual(dq, "DISTRICT_HISTORICAL_MEDIAN")

    def test_provider_national_historical_median_fallback(self):
        """Req 6.6: National historical median fallback."""
        cols = fmd_service.models["stage1_30_cols"]
        fake_df = pd.DataFrame([
            {"district": "Colombo", "year": 2020, "month_num": 1, "rainfall_mm": 100.0}
        ])
        provider = CsvForecastDataProvider()
        provider._datasets["FMD"] = fake_df
        row, fb, msg, sy, sm, age, dq = provider.get_feature_row(
            "FMD", "UnknownDistrict", 5, 2026, cols
        )
        self.assertTrue(fb)
        self.assertIsNone(sy)
        self.assertIsNone(sm)
        self.assertIsNone(age)
        self.assertEqual(dq, "NATIONAL_HISTORICAL_MEDIAN")

    def test_provider_available_previous_month_observation(self):
        """Req 6.7: Available previous-month outbreak observation."""
        lag1 = self.csv_provider.get_valid_lag1("LSD", "Anuradhapura", 2020, 12)
        self.assertEqual(lag1, 1.0)

    def test_provider_unavailable_previous_month_observation(self):
        """Req 6.8: Explicitly unavailable previous-month observation."""
        lag1 = self.csv_provider.get_valid_lag1("LSD", "Anuradhapura", 2026, 9)
        self.assertIsNone(lag1)

    def test_provider_invalid_disease_identifier_rejection(self):
        """Req 6.9: Invalid disease identifier rejection (ValueError)."""
        with self.assertRaises(ValueError):
            self.csv_provider.get_valid_lag1("Rabies", "Anuradhapura", 2024, 1)

        with self.assertRaises(ValueError):
            self.csv_provider.get_feature_row("Rabies", "Anuradhapura", 1, 2024, ["sin_month"])

        with self.assertRaises(ValueError):
            self.csv_provider.get_feature_row("", "Anuradhapura", 1, 2024, ["sin_month"])

    def test_provider_requested_source_period_provenance(self):
        """Req 6.10: Requested vs source period provenance reporting."""
        cols = fmd_service.models["stage1_30_cols"]
        row, fb, msg, sy, sm, age, dq = self.csv_provider.get_feature_row(
            "FMD", "Jaffna", 5, 2025, cols
        )
        self.assertTrue(fb)
        self.assertEqual(sy, 2024)
        self.assertEqual(sm, 5)
        self.assertEqual(age, 12)

    def test_fmd_service_with_injected_provider(self):
        """Req 6.11: FMD service with injected custom provider."""
        mock_provider = MockForecastDataProvider(mock_lag1=1.0)
        custom_fmd = FMDService(data_provider=mock_provider)
        self.assertIs(custom_fmd.data_provider, mock_provider)
        req = FMDOutbreakPredictRequest(
            district="Anuradhapura", year=2024, month=1, model_variant="30_feature_baseline"
        )
        res = custom_fmd.predict(req)
        self.assertEqual(res.disease, "FMD")

    def test_lsd_service_with_injected_provider(self):
        """Req 6.12: LSD service with injected custom provider."""
        mock_provider = MockForecastDataProvider(mock_lag1=1.0)
        custom_lsd = LSDService(data_provider=mock_provider)
        self.assertIs(custom_lsd.data_provider, mock_provider)
        req = LSDOutbreakPredictRequest(district="Anuradhapura", year=2024, month=1)
        res = custom_lsd.predict(req)
        self.assertEqual(res.disease, "LSD")

    def test_default_services_use_csv_provider(self):
        """Req 6.13: Default module instances use CsvForecastDataProvider."""
        self.assertIsInstance(fmd_service.data_provider, CsvForecastDataProvider)
        self.assertIsInstance(lsd_service.data_provider, CsvForecastDataProvider)

    def test_provider_cannot_add_extra_model_features(self):
        """Req 6.14: Provider returns DataFrame with strictly requested feature columns."""
        cols = ["rainfall_mm", "humidity"]
        row, _, _, _, _, _, _ = self.csv_provider.get_feature_row(
            "FMD", "Anuradhapura", 12, 2020, cols
        )
        self.assertEqual(list(row.columns), cols)
        self.assertNotIn("district", row.columns)
        self.assertNotIn("year", row.columns)

    def test_model_feature_column_order_remains_unchanged(self):
        """Req 6.15: Model feature-column order returned matches requested list order exactly."""
        cols = fmd_service.models["stage1_30_cols"]
        row, _, _, _, _, _, _ = self.csv_provider.get_feature_row(
            "FMD", "Anuradhapura", 12, 2020, cols
        )
        self.assertEqual(list(row.columns), list(cols))


if __name__ == "__main__":
    unittest.main()
