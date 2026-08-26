"""
Unit and Integration Tests for Forecast Decision Record Foundation (Phase 2).

Verifies domain schemas, repository boundaries, service layer idempotency,
API endpoints, immutability guarantees, and isolation rules.
"""

import concurrent.futures
from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.components.risk_forecasting.config import SRI_LANKA_DISTRICTS
from backend.components.risk_forecasting.repositories.forecast_record_repository import (
    InMemoryForecastRecordRepository,
)
from backend.components.risk_forecasting.routes import router
from backend.components.risk_forecasting.schemas import (
    FMDOutbreakPredictRequest,
    FMDOutbreakPredictResponse,
    ForecastDecisionRecord,
    GenerateForecastRecordRequest,
    LSDOutbreakPredictRequest,
    LSDOutbreakPredictResponse,
)
from backend.components.risk_forecasting.services.fmd_service import fmd_service
from backend.components.risk_forecasting.services.forecast_record_service import (
    ForecastRecordService,
)
from backend.components.risk_forecasting.services.lsd_service import lsd_service


class TestForecastRecordFoundation(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryForecastRecordRepository()
        self.service = ForecastRecordService(
            repository=self.repo,
            fmd_svc=fmd_service,
            lsd_svc=lsd_service,
        )

        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/risk-forecasting")
        self.client = TestClient(app)

    # 1. FMD Record Creation
    def test_01_fmd_record_creation(self):
        req = GenerateForecastRecordRequest(
            disease="FMD",
            district="Anuradhapura",
            year=2024,
            month=1,
            trigger_type="MANUAL",
            generated_by="vet_user_01",
        )
        record = self.service.generate_record(req)

        self.assertIsNotNone(record.forecast_id)
        self.assertTrue(record.forecast_id.startswith("fdr_"))
        self.assertEqual(record.disease, "FMD")
        self.assertEqual(record.district, "Anuradhapura")
        self.assertEqual(record.target_year, 2024)
        self.assertEqual(record.target_month, 1)
        self.assertEqual(record.status, "GENERATED")
        self.assertEqual(record.trigger_type, "MANUAL")
        self.assertEqual(record.generated_by, "vet_user_01")

    # 2. LSD Record Creation
    def test_02_lsd_record_creation(self):
        req = GenerateForecastRecordRequest(
            disease="LSD",
            district="Jaffna",
            year=2024,
            month=5,
            trigger_type="SCHEDULED",
        )
        record = self.service.generate_record(req)

        self.assertEqual(record.disease, "LSD")
        self.assertEqual(record.district, "Jaffna")
        self.assertEqual(record.target_year, 2024)
        self.assertEqual(record.target_month, 5)
        self.assertEqual(record.trigger_type, "SCHEDULED")

    # 3. Correct Mapping from Existing Prediction Response
    def test_03_correct_mapping_from_prediction_response(self):
        fmd_pred = fmd_service.predict(
            FMDOutbreakPredictRequest(district="Colombo", year=2024, month=1)
        )
        req = GenerateForecastRecordRequest(
            disease="FMD", district="Colombo", year=2024, month=1
        )
        record = self.service.generate_record(req)

        self.assertEqual(record.probability, fmd_pred.stage1.probability)
        self.assertEqual(record.probability_pct, fmd_pred.stage1.probability_pct)
        self.assertEqual(record.risk_level, fmd_pred.stage1.risk_level)
        if fmd_pred.stage2.evaluated:
            self.assertEqual(record.predicted_severity, fmd_pred.stage2.severity_predicted)
        else:
            self.assertIsNone(record.predicted_severity)
        self.assertEqual(record.model_variant, fmd_pred.stage1.model_variant)
        self.assertEqual(record.fallback_applied, fmd_pred.provenance.fallback_applied)
        self.assertEqual(record.data_quality, fmd_pred.provenance.data_quality)

    # 4. Stable Unique forecast_id
    def test_04_stable_unique_forecast_id(self):
        req1 = GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=1)
        req2 = GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=1)
        rec1 = self.service.generate_record(req1)
        rec2 = self.service.generate_record(req2)

        self.assertNotEqual(rec1.forecast_id, rec2.forecast_id)

    # 5. Timezone-Aware Generated Timestamp
    def test_05_timezone_aware_generated_timestamp(self):
        fixed_now = datetime(2026, 8, 22, 17, 30, 0, tzinfo=timezone.utc)
        svc = ForecastRecordService(
            repository=self.repo,
            fmd_svc=fmd_service,
            lsd_svc=lsd_service,
            clock=lambda: fixed_now,
        )
        req = GenerateForecastRecordRequest(disease="FMD", district="Kandy", year=2024, month=2)
        rec = svc.generate_record(req)

        self.assertIn("+00:00", rec.generated_at)
        self.assertTrue(rec.generated_at.startswith("2026-08-22T17:30:00"))

    # 6. Required Disclaimer Mapping
    def test_06_required_disclaimer_mapping(self):
        req_fmd = GenerateForecastRecordRequest(disease="FMD", district="Galle", year=2024, month=3)
        rec_fmd = self.service.generate_record(req_fmd)
        self.assertIn("FMD Stage 1 and Stage 2 model predictions", rec_fmd.disclaimer)

        req_lsd = GenerateForecastRecordRequest(disease="LSD", district="Galle", year=2024, month=3)
        rec_lsd = self.service.generate_record(req_lsd)
        self.assertIn("LSD Stage 2 binary severity predictions", rec_lsd.disclaimer)

    # 7. Exact Provenance Mapping
    def test_07_exact_provenance_mapping(self):
        req = GenerateForecastRecordRequest(disease="FMD", district="Batticaloa", year=2024, month=6)
        rec = self.service.generate_record(req)

        self.assertIsNotNone(rec.data_quality)
        self.assertIsNotNone(rec.fallback_message)
        self.assertIsInstance(rec.fallback_applied, bool)

    # 8. Idempotent Retry Returns Existing Record
    def test_08_idempotent_retry_returns_existing(self):
        req1 = GenerateForecastRecordRequest(
            disease="FMD",
            district="Kegalle",
            year=2024,
            month=4,
            idempotency_key="idemp_kegalle_001",
        )
        rec1 = self.service.generate_record(req1)

        req2 = GenerateForecastRecordRequest(
            disease="FMD",
            district="Kegalle",
            year=2024,
            month=4,
            idempotency_key="idemp_kegalle_001",
        )
        rec2 = self.service.generate_record(req2)

        self.assertEqual(rec1.forecast_id, rec2.forecast_id)
        self.assertEqual(rec1.generated_at, rec2.generated_at)

    # 9. Same Idempotency Key Plus Different Request Rejected
    def test_09_idempotency_conflict_rejected(self):
        req1 = GenerateForecastRecordRequest(
            disease="FMD",
            district="Matara",
            year=2024,
            month=1,
            idempotency_key="shared_idemp_key",
        )
        self.service.generate_record(req1)

        # Different district with same key
        req2 = GenerateForecastRecordRequest(
            disease="FMD",
            district="Jaffna",
            year=2024,
            month=1,
            idempotency_key="shared_idemp_key",
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.generate_record(req2)
        self.assertIn("Idempotency key collision", str(ctx.exception))

    # 10. Unknown forecast_id Returns Correct Error
    def test_10_unknown_forecast_id(self):
        with self.assertRaises(KeyError):
            self.service.get_record("non_existent_fdr_id")

        res = self.client.get("/api/v1/risk-forecasting/records/non_existent_fdr_id")
        self.assertEqual(res.status_code, 404)

    # 11. Disease Filtering
    def test_11_disease_filtering(self):
        self.service.generate_record(GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=1))
        self.service.generate_record(GenerateForecastRecordRequest(disease="LSD", district="Colombo", year=2024, month=1))

        res_fmd = self.service.list_records(disease="FMD")
        self.assertEqual(res_fmd.total_count, 1)
        self.assertEqual(res_fmd.records[0].disease, "FMD")

        res_lsd = self.service.list_records(disease="LSD")
        self.assertEqual(res_lsd.total_count, 1)
        self.assertEqual(res_lsd.records[0].disease, "LSD")

    # 12. District Filtering
    def test_12_district_filtering(self):
        self.service.generate_record(GenerateForecastRecordRequest(disease="FMD", district="Jaffna", year=2024, month=1))
        self.service.generate_record(GenerateForecastRecordRequest(disease="FMD", district="Kandy", year=2024, month=1))

        res = self.service.list_records(district="Jaffna")
        self.assertEqual(res.total_count, 1)
        self.assertEqual(res.records[0].district, "Jaffna")

    # 13. Target-Period Filtering
    def test_13_target_period_filtering(self):
        self.service.generate_record(GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=1))
        self.service.generate_record(GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=2))
        self.service.generate_record(GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2025, month=1))

        res_yr = self.service.list_records(target_year=2024)
        self.assertEqual(res_yr.total_count, 2)

        res_mo = self.service.list_records(target_year=2024, target_month=2)
        self.assertEqual(res_mo.total_count, 1)
        self.assertEqual(res_mo.records[0].target_month, 2)

    # 14. Status Filtering
    def test_14_status_filtering(self):
        rec = self.service.generate_record(GenerateForecastRecordRequest(disease="FMD", district="Gampaha", year=2024, month=1))
        self.repo.update_status(rec.forecast_id, "SUPERSEDED")

        self.service.generate_record(GenerateForecastRecordRequest(disease="FMD", district="Gampaha", year=2024, month=2))

        res_gen = self.service.list_records(status="GENERATED")
        self.assertEqual(res_gen.total_count, 1)

        res_sup = self.service.list_records(status="SUPERSEDED")
        self.assertEqual(res_sup.total_count, 1)
        self.assertEqual(res_sup.records[0].status, "SUPERSEDED")

    # 15. Pagination / Maximum-Limit Enforcement
    def test_15_pagination_limit_enforcement(self):
        for i in range(1, 11):
            self.service.generate_record(GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=(i % 12) + 1))

        res_page1 = self.service.list_records(limit=3, offset=0)
        self.assertEqual(len(res_page1.records), 3)
        self.assertEqual(res_page1.total_count, 10)

        # Enforce max limit of 200
        res_overflow = self.service.list_records(limit=500)
        self.assertEqual(res_overflow.limit, 200)

    # 16. Invalid Disease / District / Month / Year Validation
    def test_16_validation_failures(self):
        # Invalid district
        with self.assertRaises(ValueError):
            GenerateForecastRecordRequest(disease="FMD", district="NonExistentDistrict", year=2024, month=1)

        # Invalid month
        with self.assertRaises(ValueError):
            GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=13)

        # Invalid year
        with self.assertRaises(ValueError):
            GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2010, month=1)

    # 17. Repository Dependency Injection
    def test_17_repository_dependency_injection(self):
        mock_repo = MagicMock(spec=InMemoryForecastRecordRepository)
        mock_repo.find_by_idempotency_key.return_value = None
        mock_repo.save.side_effect = lambda rec: rec

        custom_svc = ForecastRecordService(repository=mock_repo, fmd_svc=fmd_service, lsd_svc=lsd_service)
        req = GenerateForecastRecordRequest(disease="FMD", district="Ampara", year=2024, month=1)
        rec = custom_svc.generate_record(req)

        self.assertEqual(rec.district, "Ampara")
        mock_repo.save.assert_called_once()

    # 18. Prediction Service Dependency Injection
    def test_18_prediction_service_dependency_injection(self):
        mock_fmd = MagicMock()
        fake_response = fmd_service.predict(FMDOutbreakPredictRequest(district="Colombo", year=2024, month=1))
        mock_fmd.predict.return_value = fake_response

        custom_svc = ForecastRecordService(repository=self.repo, fmd_svc=mock_fmd, lsd_svc=lsd_service)
        req = GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=1)
        rec = custom_svc.generate_record(req)

        self.assertEqual(rec.probability, fake_response.stage1.probability)
        mock_fmd.predict.assert_called_once()

    # 19. Prediction Service Failure Does Not Create Partial Record
    def test_19_prediction_service_failure_atomic(self):
        mock_fmd = MagicMock()
        mock_fmd.predict.side_effect = RuntimeError("FMD model failure")

        custom_svc = ForecastRecordService(repository=self.repo, fmd_svc=mock_fmd, lsd_svc=lsd_service)
        req = GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=1)

        with self.assertRaises(RuntimeError):
            custom_svc.generate_record(req)

        # Confirm repository remains empty
        res = self.repo.list()
        self.assertEqual(res[1], 0)

    # 20. Existing Prediction Endpoint Outputs Remain Unchanged
    def test_20_existing_prediction_endpoints_unchanged(self):
        fmd_res = self.client.post("/api/v1/risk-forecasting/predict/fmd", json={"district": "Colombo", "year": 2024, "month": 1})
        self.assertEqual(fmd_res.status_code, 200)
        self.assertIn("stage1", fmd_res.json())

        lsd_res = self.client.post("/api/v1/risk-forecasting/predict/lsd", json={"district": "Colombo", "year": 2024, "month": 1})
        self.assertEqual(lsd_res.status_code, 200)
        self.assertIn("stage1", lsd_res.json())

    # 21. Concurrent Duplicate Idempotency Attempts
    def test_21_concurrent_duplicate_idempotency(self):
        idemp_key = "concurrent_key_999"
        req = GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=1, idempotency_key=idemp_key)

        def worker():
            return self.service.generate_record(req)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker) for _ in range(5)]
            results = [f.result() for f in futures]

        forecast_ids = {r.forecast_id for r in results}
        self.assertEqual(len(forecast_ids), 1)

    # 22. Immutability of Scientific Prediction Fields
    def test_22_scientific_immutability(self):
        req = GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=1)
        rec = self.service.generate_record(req)

        orig_prob = rec.probability
        orig_risk = rec.risk_level

        # Update status
        updated = self.repo.update_status(rec.forecast_id, "AVAILABLE")

        self.assertEqual(updated.status, "AVAILABLE")
        self.assertEqual(updated.probability, orig_prob)
        self.assertEqual(updated.risk_level, orig_risk)

    # 23. API Route Endpoints Integration
    def test_23_api_records_flow(self):
        # Create record via API
        payload = {"disease": "FMD", "district": "Polonnaruwa", "year": 2024, "month": 10}
        headers = {"Idempotency-Key": "api_idemp_100"}
        res_create = self.client.post("/api/v1/risk-forecasting/records", json=payload, headers=headers)
        self.assertEqual(res_create.status_code, 201)
        data = res_create.json()
        fdr_id = data["forecast_id"]
        self.assertEqual(data["district"], "Polonnaruwa")
        self.assertEqual(data["idempotency_key"], "api_idemp_100")

        # Idempotent retry via API
        res_retry = self.client.post("/api/v1/risk-forecasting/records", json=payload, headers=headers)
        self.assertEqual(res_retry.status_code, 201)
        self.assertEqual(res_retry.json()["forecast_id"], fdr_id)

        # Retrieve by ID via API
        res_get = self.client.get(f"/api/v1/risk-forecasting/records/{fdr_id}")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["forecast_id"], fdr_id)

        # List records via API
        res_list = self.client.get("/api/v1/risk-forecasting/records?district=Polonnaruwa")
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(res_list.json()["total_count"], 1)

    # 24. Confirm No Trend Route or TrendService Created
    def test_24_no_trend_route_or_service(self):
        res_trend = self.client.get("/api/v1/risk-forecasting/trends")
        self.assertEqual(res_trend.status_code, 404)

        import sys
        self.assertNotIn("backend.components.risk_forecasting.services.trend_service", sys.modules)

    # 25. Idempotency Header/Body Conflict Scenarios API Test
    def test_25_idempotency_header_body_conflict_scenarios(self):
        payload = {"disease": "FMD", "district": "Colombo", "year": 2024, "month": 1}

        # Case A: Only header supplied -> Uses header
        res_a = self.client.post("/api/v1/risk-forecasting/records", json=payload, headers={"Idempotency-Key": "key_header_only"})
        self.assertEqual(res_a.status_code, 201)
        self.assertEqual(res_a.json()["idempotency_key"], "key_header_only")

        # Case B: Only body supplied -> Uses body
        payload_b = {**payload, "idempotency_key": "key_body_only"}
        res_b = self.client.post("/api/v1/risk-forecasting/records", json=payload_b)
        self.assertEqual(res_b.status_code, 201)
        self.assertEqual(res_b.json()["idempotency_key"], "key_body_only")

        # Case C: Both supplied with SAME value -> Accept
        payload_c = {**payload, "idempotency_key": "key_matching"}
        res_c = self.client.post("/api/v1/risk-forecasting/records", json=payload_c, headers={"Idempotency-Key": "key_matching"})
        self.assertEqual(res_c.status_code, 201)
        self.assertEqual(res_c.json()["idempotency_key"], "key_matching")

        # Case D: Both supplied with DIFFERENT values -> Reject HTTP 409 Conflict
        payload_d = {**payload, "idempotency_key": "key_body_val"}
        res_d = self.client.post("/api/v1/risk-forecasting/records", json=payload_d, headers={"Idempotency-Key": "key_header_val"})
        self.assertEqual(res_d.status_code, 409)
        self.assertIn("Idempotency key mismatch", res_d.json()["detail"])

        # Case E: Neither supplied -> Normal record generation (no idempotency key)
        res_e = self.client.post("/api/v1/risk-forecasting/records", json=payload)
        self.assertEqual(res_e.status_code, 201)
        self.assertIsNone(res_e.json()["idempotency_key"])

    # 26. Repository Copy Safety
    def test_26_defensive_repository_copy_safety(self):
        req = GenerateForecastRecordRequest(disease="FMD", district="Colombo", year=2024, month=1)
        rec = self.service.generate_record(req)

        # Mutate object returned from get_by_id
        fetched = self.repo.get_by_id(rec.forecast_id)
        fetched.probability = 0.99
        fetched.risk_level = "HIGH"

        # Re-fetch from repository and verify original values remain untouched
        refetched = self.repo.get_by_id(rec.forecast_id)
        self.assertNotEqual(refetched.probability, 0.99)
        self.assertEqual(refetched.probability, rec.probability)
        self.assertEqual(refetched.risk_level, rec.risk_level)


if __name__ == "__main__":
    unittest.main()
