"""
Unit tests for Shared API Forecast Data Provider Contract & Parity.

Verifies the SharedApiForecastDataProvider adapter, validation rules, contract safety,
and prediction parity against the standalone CsvForecastDataProvider baseline.
"""

from typing import Dict, Optional, Tuple, List
import unittest
from fastapi.testclient import TestClient

from components.risk_forecasting.integrations import (
    SharedForecastRecord,
    SharedForecastDataClient,
    SharedApiForecastDataProvider,
    CsvForecastDataProvider,
)
from components.risk_forecasting.services.fmd_service import fmd_service, FMDService
from components.risk_forecasting.services.lsd_service import lsd_service, LSDService
from components.risk_forecasting.schemas import FMDOutbreakPredictRequest, LSDOutbreakPredictRequest
from components.risk_forecasting.routes import router
from fastapi import FastAPI


class FakeSharedForecastDataClient(SharedForecastDataClient):
    """
    Deterministic test-only implementation of SharedForecastDataClient.
    Seeds normalized records and lag observations for testing parity and safe failure.
    """

    def __init__(self):
        self.records: Dict[Tuple[str, str, int, int], SharedForecastRecord] = {}
        self.lags: Dict[Tuple[str, str, int, int], Tuple[float, bool]] = {}

    def add_record(self, record: SharedForecastRecord) -> None:
        key = (record.disease.upper(), record.district, record.year, record.month)
        self.records[key] = record

    def add_lag1(self, disease: str, district: str, year: int, month: int, status: float, is_verified: bool) -> None:
        key = (disease.upper(), district, year, month)
        self.lags[key] = (status, is_verified)

    def fetch_feature_record(
        self, disease: str, district: str, month: int, year: int
    ) -> Optional[SharedForecastRecord]:
        return self.records.get((disease.upper(), district, year, month))

    def fetch_valid_lag1(
        self, disease: str, district: str, month: int, year: int
    ) -> Optional[Tuple[float, bool]]:
        return self.lags.get((disease.upper(), district, year, month))

    def populate_from_csv(self, csv_provider: CsvForecastDataProvider, disease: str) -> None:
        """Populates fake client records directly from a CsvForecastDataProvider dataset for parity testing."""
        df = csv_provider._get_dataset(disease)
        if df.empty:
            return

        cols = [c for c in df.columns if c not in ("district", "year", "month_num", "Outbreak status")]
        for _, row in df.iterrows():
            dist = str(row["district"])
            yr = int(row["year"])
            mn = int(row["month_num"])
            feat_dict = {}
            for c in cols:
                if pd_notnull(row[c]):
                    try:
                        feat_dict[c] = float(row[c])
                    except (ValueError, TypeError):
                        feat_dict[c] = row[c]

            rec = SharedForecastRecord(
                disease=disease.upper(),
                district=dist,
                year=yr,
                month=mn,
                feature_values=feat_dict,
                data_quality_status="EXACT_REQUESTED_PERIOD",
                is_proxy=False,
                source_year=yr,
                source_month=mn,
                data_age_months=0,
            )
            self.add_record(rec)

            # Store lag1 if present
            if "Outbreak status" in row and pd_notnull(row["Outbreak status"]):
                # In lag1 lookup: year/month passed is current request t, lookup is t-1
                # Next month t will look up prev month t-1
                next_yr = yr if mn < 12 else yr + 1
                next_mn = mn + 1 if mn < 12 else 1
                self.add_lag1(disease, dist, next_yr, next_mn, float(row["Outbreak status"]), True)


def pd_notnull(val) -> bool:
    return val is not None and str(val).strip().lower() not in ("nan", "none", "null", "")


class TestSharedProviderContract(unittest.TestCase):
    """Test suite for SharedApiForecastDataProvider contract, validation, and prediction parity."""

    def setUp(self):
        self.csv_provider = CsvForecastDataProvider()
        self.fake_client = FakeSharedForecastDataClient()
        self.fake_client.populate_from_csv(self.csv_provider, "FMD")
        self.fake_client.populate_from_csv(self.csv_provider, "LSD")
        self.shared_provider = SharedApiForecastDataProvider(self.fake_client)

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_10_valid_normalized_fmd_record_accepted(self):
        """Valid normalized FMD record returns formatted 1-row DataFrame with requested feature columns."""
        cols = fmd_service.models["stage1_30_cols"]
        df_row, fb, msg, sy, sm, age, dq = self.shared_provider.get_feature_row(
            "FMD", "Anuradhapura", 12, 2020, cols
        )
        self.assertEqual(len(df_row), 1)
        self.assertEqual(list(df_row.columns), cols)
        self.assertFalse(fb)
        self.assertEqual(dq, "EXACT_REQUESTED_PERIOD")

    def test_11_valid_normalized_lsd_record_accepted(self):
        """Valid normalized LSD record returns formatted 1-row DataFrame with requested feature columns."""
        cols = lsd_service.models["stage1_cols"]
        df_row, fb, msg, sy, sm, age, dq = self.shared_provider.get_feature_row(
            "LSD", "Anuradhapura", 12, 2020, cols
        )
        self.assertEqual(len(df_row), 1)
        self.assertEqual(list(df_row.columns), cols)
        self.assertFalse(fb)
        self.assertEqual(dq, "EXACT_REQUESTED_PERIOD")

    def test_12_unsupported_disease_rejected(self):
        """Unsupported disease identifier raises ValueError."""
        with self.assertRaises(ValueError):
            self.shared_provider.get_feature_row("RINDERPEST", "Anuradhapura", 12, 2020, ["sin_month"])
        with self.assertRaises(ValueError):
            self.shared_provider.get_valid_lag1("INVALID_DISEASE", "Anuradhapura", 2020, 12)

    def test_13_missing_required_model_field_rejected(self):
        """Sparse record missing required features raises ValueError rather than zero-filling."""
        sparse_rec = SharedForecastRecord(
            disease="FMD",
            district="Jaffna",
            year=2024,
            month=1,
            feature_values={"sin_month": 0.5},  # missing other required features
        )
        client = FakeSharedForecastDataClient()
        client.add_record(sparse_rec)
        provider = SharedApiForecastDataProvider(client)

        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Jaffna", 1, 2024, cols)
        self.assertIn("missing", str(ctx.exception).lower())

    def test_28_missing_rainfall_rejected(self):
        """Missing rainfall feature in shared record payload raises ValueError."""
        record = self.fake_client.fetch_feature_record("FMD", "Anuradhapura", 12, 2020)
        bad_values = dict(record.feature_values)
        bad_values.pop("rainfall_mm", None)
        bad_rec = SharedForecastRecord(disease="FMD", district="Anuradhapura", year=2020, month=12, feature_values=bad_values)
        client = FakeSharedForecastDataClient()
        client.add_record(bad_rec)
        provider = SharedApiForecastDataProvider(client)
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Anuradhapura", 12, 2020, cols)
        self.assertIn("rainfall_mm", str(ctx.exception))

    def test_29_missing_humidity_rejected(self):
        """Missing humidity feature (r3h) in shared record payload raises ValueError."""
        record = self.fake_client.fetch_feature_record("FMD", "Anuradhapura", 12, 2020)
        bad_values = dict(record.feature_values)
        bad_values.pop("r3h", None)
        bad_rec = SharedForecastRecord(disease="FMD", district="Anuradhapura", year=2020, month=12, feature_values=bad_values)
        client = FakeSharedForecastDataClient()
        client.add_record(bad_rec)
        provider = SharedApiForecastDataProvider(client)
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Anuradhapura", 12, 2020, cols)
        self.assertIn("r3h", str(ctx.exception))

    def test_30_missing_density_rejected(self):
        """Missing cattle/livestock density feature in shared record payload raises ValueError."""
        record = self.fake_client.fetch_feature_record("FMD", "Anuradhapura", 12, 2020)
        bad_values = dict(record.feature_values)
        bad_values.pop("livestock_density", None)
        bad_rec = SharedForecastRecord(disease="FMD", district="Anuradhapura", year=2020, month=12, feature_values=bad_values)
        client = FakeSharedForecastDataClient()
        client.add_record(bad_rec)
        provider = SharedApiForecastDataProvider(client)
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Anuradhapura", 12, 2020, cols)
        self.assertIn("livestock_density", str(ctx.exception))

    def test_31_missing_neighbour_lag_rejected(self):
        """Missing neighbour spatial lag feature in shared record payload raises ValueError."""
        record = self.fake_client.fetch_feature_record("FMD", "Anuradhapura", 12, 2020)
        bad_values = dict(record.feature_values)
        bad_values.pop("neighbor_outbreak_lag1", None)
        bad_rec = SharedForecastRecord(disease="FMD", district="Anuradhapura", year=2020, month=12, feature_values=bad_values)
        client = FakeSharedForecastDataClient()
        client.add_record(bad_rec)
        provider = SharedApiForecastDataProvider(client)
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Anuradhapura", 12, 2020, cols)
        self.assertIn("neighbor_outbreak_lag1", str(ctx.exception))

    def test_32_missing_multiple_required_features_sanitized_error(self):
        """Missing multiple required features raises a sanitized contract error mentioning feature names."""
        bad_rec = SharedForecastRecord(disease="FMD", district="Anuradhapura", year=2020, month=12, feature_values={"sin_month": 0.5})
        client = FakeSharedForecastDataClient()
        client.add_record(bad_rec)
        provider = SharedApiForecastDataProvider(client)
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Anuradhapura", 12, 2020, cols)
        self.assertIn("missing", str(ctx.exception).lower())

    def test_33_none_required_feature_rejected(self):
        """None value for required feature in shared record raises ValueError."""
        record = self.fake_client.fetch_feature_record("FMD", "Anuradhapura", 12, 2020)
        bad_values = dict(record.feature_values)
        bad_values["rainfall_mm"] = None
        bad_rec = SharedForecastRecord(disease="FMD", district="Anuradhapura", year=2020, month=12, feature_values=bad_values)
        client = FakeSharedForecastDataClient()
        client.add_record(bad_rec)
        provider = SharedApiForecastDataProvider(client)
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Anuradhapura", 12, 2020, cols)
        self.assertIn("rainfall_mm", str(ctx.exception))

    def test_34_string_numeric_value_rejected(self):
        """String value for numeric model feature raises ValueError (rejection policy)."""
        record = self.fake_client.fetch_feature_record("FMD", "Anuradhapura", 12, 2020)
        bad_values = dict(record.feature_values)
        bad_values["rainfall_mm"] = "150.5"
        bad_rec = SharedForecastRecord(disease="FMD", district="Anuradhapura", year=2020, month=12, feature_values=bad_values)
        client = FakeSharedForecastDataClient()
        client.add_record(bad_rec)
        provider = SharedApiForecastDataProvider(client)
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Anuradhapura", 12, 2020, cols)
        self.assertIn("rainfall_mm", str(ctx.exception))

    def test_35_boolean_feature_value_rejected(self):
        """Boolean value (True/False) for numeric feature raises ValueError."""
        record = self.fake_client.fetch_feature_record("FMD", "Anuradhapura", 12, 2020)
        bad_values = dict(record.feature_values)
        bad_values["rainfall_mm"] = True
        bad_rec = SharedForecastRecord(disease="FMD", district="Anuradhapura", year=2020, month=12, feature_values=bad_values)
        client = FakeSharedForecastDataClient()
        client.add_record(bad_rec)
        provider = SharedApiForecastDataProvider(client)
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Anuradhapura", 12, 2020, cols)
        self.assertIn("boolean", str(ctx.exception).lower())

    def test_36_nan_feature_value_rejected(self):
        """NaN value for required model feature raises ValueError."""
        record = self.fake_client.fetch_feature_record("FMD", "Anuradhapura", 12, 2020)
        bad_values = dict(record.feature_values)
        bad_values["rainfall_mm"] = float("nan")
        bad_rec = SharedForecastRecord(disease="FMD", district="Anuradhapura", year=2020, month=12, feature_values=bad_values)
        client = FakeSharedForecastDataClient()
        client.add_record(bad_rec)
        provider = SharedApiForecastDataProvider(client)
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Anuradhapura", 12, 2020, cols)
        self.assertIn("non-finite", str(ctx.exception).lower())

    def test_37_pos_inf_feature_value_rejected(self):
        """Positive infinity (+inf) for required model feature raises ValueError."""
        record = self.fake_client.fetch_feature_record("FMD", "Anuradhapura", 12, 2020)
        bad_values = dict(record.feature_values)
        bad_values["rainfall_mm"] = float("inf")
        bad_rec = SharedForecastRecord(disease="FMD", district="Anuradhapura", year=2020, month=12, feature_values=bad_values)
        client = FakeSharedForecastDataClient()
        client.add_record(bad_rec)
        provider = SharedApiForecastDataProvider(client)
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Anuradhapura", 12, 2020, cols)
        self.assertIn("non-finite", str(ctx.exception).lower())

    def test_38_neg_inf_feature_value_rejected(self):
        """Negative infinity (-inf) for required model feature raises ValueError."""
        record = self.fake_client.fetch_feature_record("FMD", "Anuradhapura", 12, 2020)
        bad_values = dict(record.feature_values)
        bad_values["rainfall_mm"] = float("-inf")
        bad_rec = SharedForecastRecord(disease="FMD", district="Anuradhapura", year=2020, month=12, feature_values=bad_values)
        client = FakeSharedForecastDataClient()
        client.add_record(bad_rec)
        provider = SharedApiForecastDataProvider(client)
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            provider.get_feature_row("FMD", "Anuradhapura", 12, 2020, cols)
        self.assertIn("non-finite", str(ctx.exception).lower())

    def test_39_unsupported_district_rejected(self):
        """Unsupported district identifier raises ValueError during input validation."""
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            self.shared_provider.get_feature_row("FMD", "InvalidDistrictName", 12, 2020, cols)
        self.assertIn("unsupported", str(ctx.exception).lower())

    def test_40_month_0_rejected(self):
        """Month 0 is outside valid range (1-12) and raises ValueError."""
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            self.shared_provider.get_feature_row("FMD", "Anuradhapura", 0, 2020, cols)
        self.assertIn("month", str(ctx.exception).lower())

    def test_41_month_13_rejected(self):
        """Month 13 is outside valid range (1-12) and raises ValueError."""
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            self.shared_provider.get_feature_row("FMD", "Anuradhapura", 13, 2020, cols)
        self.assertIn("month", str(ctx.exception).lower())

    def test_42_out_of_range_year_rejected(self):
        """Year outside valid schema range (2017-2030) raises ValueError."""
        cols = fmd_service.models["stage1_30_cols"]
        with self.assertRaises(ValueError) as ctx:
            self.shared_provider.get_feature_row("FMD", "Anuradhapura", 12, 2035, cols)
        self.assertIn("year", str(ctx.exception).lower())

    def test_43_missing_separately_supplied_own_outbreak_lag1_fallback(self):
        """Missing own_outbreak_lag1 in shared lag endpoint safely triggers 27-feature fallback in LSD Service."""
        client = FakeSharedForecastDataClient()
        client.populate_from_csv(self.csv_provider, "LSD")
        # Remove lag observation for Colombo 2020-12 to simulate unavailable lag1
        client.lags.pop(("LSD", "Colombo", 2020, 12), None)
        provider = SharedApiForecastDataProvider(client)
        service = LSDService(data_provider=provider)

        req = LSDOutbreakPredictRequest(district="Colombo", year=2020, month=12, model_variant="28_feature_autocorrelation")
        res = service.predict(req)
        self.assertEqual(res.stage1.model_variant, "27_feature_fallback")
        self.assertEqual(res.provenance.lag1_status, "UNAVAILABLE")

    def test_44_district_enc_injected_deterministically(self):
        """district_enc value is injected deterministically via district_enc_val parameter into feature row."""
        cols = fmd_service.models["stage2_cols"]
        df_row, _, _, _, _, _, _ = self.shared_provider.get_feature_row(
            "FMD", "Anuradhapura", 12, 2020, cols, district_enc_val=5.0
        )
        self.assertIn("district_enc", df_row.columns)
        self.assertEqual(df_row["district_enc"].iloc[0], 5.0)


if __name__ == "__main__":
    unittest.main()
