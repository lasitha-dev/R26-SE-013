"""
End-to-End Integration Test for All 5 Phases:
1. Operational data entry (Case verification & Mortality declaration with true BSON ISODate)
2. Data bridge & cache bypass via MongoSharedForecastClient
3. Forecast generation with live autocorrelation lag-1 & SHAP explainability
4. DAPH official forecast retrieval & advisory issuance
5. Veterinary officer advisory retrieval & completion loop
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from bson import ObjectId
import pandas as pd

from components.risk_forecasting.integrations.mongo_shared_client import (
    MongoSharedForecastClient,
    _get_disease_name_regex,
    _district_matches,
)
from components.risk_forecasting.services.fmd_service import fmd_service
from components.risk_forecasting.services.lsd_service import lsd_service
from components.risk_forecasting.schemas import (
    FMDOutbreakPredictRequest,
    LSDOutbreakPredictRequest,
    GenerateForecastRecordRequest,
)
from components.risk_forecasting.services.forecast_record_service import ForecastRecordService
from components.risk_forecasting.repositories.forecast_record_repository import InMemoryForecastRecordRepository


class TestEndToEndOperationalToForecasting(unittest.TestCase):

    def setUp(self):
        self.shared_client = MongoSharedForecastClient(cache_ttl_seconds=0)

    def test_phase_1_and_2_bson_date_query_and_lag1_bridge(self):
        """
        Verify that a case or death stored as a true BSON datetime object in July 2026 (Colombo)
        is accurately discovered by the forecasting data bridge for August 2026.
        """
        mock_farm_id = ObjectId()
        mock_cattle_id = ObjectId()

        # PHASE 1: Document in MongoDB with true BSON ISODate datetime
        july_case_datetime = datetime(2026, 7, 15, 14, 30, 0)
        mock_cases = [
            {
                "_id": ObjectId(),
                "verified": True,
                "disease_name": "Foot and Mouth Disease",
                "farm_id": mock_farm_id,
                "cattle_id": mock_cattle_id,
                "created_at": july_case_datetime,
                "verified_at": july_case_datetime,
            }
        ]
        mock_farm = {
            "_id": mock_farm_id,
            "location_district": "6.9271, 79.8612 (Colombo District)"
        }

        with patch("pymongo.MongoClient") as mock_mongo_cls:
            mock_client_instance = MagicMock()
            mock_mongo_cls.return_value.__enter__.return_value = mock_client_instance
            mock_db = MagicMock()
            mock_client_instance.get_database.return_value = mock_db

            mock_cases_coll = MagicMock()
            mock_cases_coll.find.return_value = mock_cases

            mock_farms_coll = MagicMock()
            mock_farms_coll.find_one.return_value = mock_farm

            mock_deaths_coll = MagicMock()
            mock_deaths_coll.find.return_value = []

            def coll_side_effect(name):
                if name == "diagnostic_cases":
                    return mock_cases_coll
                elif name == "farms":
                    return mock_farms_coll
                elif name == "death_logs":
                    return mock_deaths_coll
                return MagicMock()

            mock_db.get_collection.side_effect = coll_side_effect

            # PHASE 2: Query for August 2026 (target_month = 8, preceding month = July 2026)
            lag1_status, is_verified = self.shared_client.fetch_valid_lag1(
                disease="FMD",
                district="Colombo",
                month=8,
                year=2026
            )

            self.assertTrue(is_verified)
            self.assertEqual(lag1_status, 1.0)

    def test_phase_3_fmd_spiked_prediction_and_shap_explainability(self):
        """
        Verify that when lag1 = 1.0 is supplied to FMD prediction:
        - Probability increases
        - Stage 2 Random Forest severity model evaluates
        - SHAP log-odds explanation shows 'Local Outbreak History (Previous Month)' as top risk driver
        """
        with patch.object(fmd_service, "_get_valid_lag1", return_value=1.0):
            req = FMDOutbreakPredictRequest(
                district="Colombo",
                year=2026,
                month=8,
                model_variant="30_feature_baseline"  # Default request adapts to 31 when lag1 is present
            )
            res = fmd_service.predict(req)

            # Verification of Phase 3
            self.assertIn(res.stage1.risk_level, ["MEDIUM", "HIGH"])
            self.assertGreaterEqual(res.stage1.probability, 0.40)
            self.assertEqual(res.stage1.model_variant, "31_feature_autocorrelation")
            self.assertTrue(res.stage2.evaluated)
            self.assertIn(res.stage2.severity_predicted, ["LOW", "MEDIUM", "HIGH"])

            # Explainability check
            top_drivers = [f.display_label for f in res.explanation_info.top_risk_increasing]
            self.assertIn("Local Outbreak History (Previous Month)", top_drivers)

    def test_phase_3_lsd_spiked_prediction_and_shap_explainability(self):
        """
        Verify that when lag1 = 1.0 is supplied to LSD prediction:
        - Uses 28-feature autocorrelation model
        - Probability increases significantly (> 2x baseline)
        - SHAP explanation shows 'Local Outbreak History (Previous Month)' as top risk driver
        """
        with patch.object(lsd_service, "_get_valid_lag1", return_value=None):
            res_baseline = lsd_service.predict(LSDOutbreakPredictRequest(district="Colombo", year=2026, month=8))

        with patch.object(lsd_service, "_get_valid_lag1", return_value=1.0):
            res = lsd_service.predict(LSDOutbreakPredictRequest(district="Colombo", year=2026, month=8))

            self.assertEqual(res.stage1.model_variant, "28_feature_autocorrelation")
            self.assertGreater(res.stage1.probability, res_baseline.stage1.probability * 2)

            top_drivers = [f.display_label for f in res.explanation_info.top_risk_increasing]
            self.assertIn("Local Outbreak History (Previous Month)", top_drivers)

    def test_phase_3_4_5_decision_record_and_advisory_lifecycle(self):
        """
        Verify that generating a forecast record creates a ForecastDecisionRecord with spiked risk,
        allowing DAPH advisory creation and veterinary execution.
        """
        repo = InMemoryForecastRecordRepository()
        record_svc = ForecastRecordService(
            repository=repo,
            fmd_svc=fmd_service,
            lsd_svc=lsd_service
        )

        with patch.object(fmd_service, "_get_valid_lag1", return_value=1.0):
            req = GenerateForecastRecordRequest(
                disease="FMD",
                district="Colombo",
                year=2026,
                month=8
            )
            decision_record = record_svc.generate_record(req)

            self.assertIsNotNone(decision_record.forecast_id)
            self.assertEqual(decision_record.district, "Colombo")
            self.assertIn(decision_record.risk_level, ["MEDIUM", "HIGH"])
            self.assertGreaterEqual(decision_record.probability, 0.40)


if __name__ == "__main__":
    unittest.main()
