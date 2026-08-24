"""
Standalone Cross-Role End-to-End Integration Tests for DAPH–Vet Follow-Up Workflows (Phase 7).

TEST DATA DISCLAIMER:
All test records, forecast decision records, and follow-up data created within this test module
are operational workflow test fixtures ONLY. They must NEVER be used as model-training or
scientific-prediction data.

Tests complete multi-role happy paths, alternative paths (escalation, cancellation),
concurrency lock conflict resolution, idempotency deduplication, role-based authorization
isolation, record separation across Veterinary Officers, and scientific snapshot immutability.
"""

import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.components.risk_forecasting.routes import router
from backend.components.risk_forecasting.schemas import ForecastDecisionRecord
from backend.components.risk_forecasting.services.forecast_record_service import forecast_record_service
from backend.components.risk_forecasting.services.follow_up_service import forecast_follow_up_service

app = FastAPI()
app.include_router(router, prefix="/api/v1/risk-forecasting")


class TestFollowUpEndToEnd(unittest.TestCase):
    """Standalone cross-role E2E integration test suite for DAPH and Veterinary Officer workflows."""

    def setUp(self):
        """Reset repository state and seed test forecast decision records before each test."""
        # 1. Clear in-memory repositories safely
        forecast_record_service.repository._records.clear()
        forecast_record_service.repository._idempotency_index.clear()
        forecast_follow_up_service.follow_up_repo._records.clear()
        forecast_follow_up_service.follow_up_repo._idempotency_index.clear()

        # 2. Seed authoritative test forecast record (Anuradhapura, FMD, HIGH risk)
        self.forecast_anu_high = ForecastDecisionRecord(
            forecast_id="fdr_e2e_anu_001",
            disease="FMD",
            district="Anuradhapura",
            target_year=2026,
            target_month=9,
            risk_level="HIGH",
            probability=0.88,
            probability_pct=88.0,
            predicted_severity="HIGH",
            model_variant="30_feature_baseline",
            fallback_applied=False,
            data_quality="EXACT",
            disclaimer="Test forecast disclaimer for Anuradhapura",
            provenance="OFFICIAL_TEST",
            generated_at="2026-08-24T00:00:00Z",
            status="GENERATED",
            created_at="2026-08-24T00:00:00Z",
            updated_at="2026-08-24T00:00:00Z",
        )
        forecast_record_service.repository.save(self.forecast_anu_high)

        # 3. Seed second test forecast record (Kurunegala, LSD, MEDIUM risk)
        self.forecast_kuru_med = ForecastDecisionRecord(
            forecast_id="fdr_e2e_kuru_002",
            disease="LSD",
            district="Kurunegala",
            target_year=2026,
            target_month=9,
            risk_level="MEDIUM",
            probability=0.52,
            probability_pct=52.0,
            predicted_severity="MEDIUM",
            model_variant="28_feature_production",
            fallback_applied=False,
            data_quality="EXACT",
            disclaimer="Test forecast disclaimer for Kurunegala",
            provenance="OFFICIAL_TEST",
            generated_at="2026-08-24T00:00:00Z",
            status="GENERATED",
            created_at="2026-08-24T00:00:00Z",
            updated_at="2026-08-24T00:00:00Z",
        )
        forecast_record_service.repository.save(self.forecast_kuru_med)

        self.client = TestClient(app)

    def tearDown(self):
        """Clean repository state after each test."""
        forecast_record_service.repository._records.clear()
        forecast_record_service.repository._idempotency_index.clear()
        forecast_follow_up_service.follow_up_repo._records.clear()
        forecast_follow_up_service.follow_up_repo._idempotency_index.clear()

    def test_complete_daph_vet_daph_happy_path_e2e(self):
        """
        Tests complete Happy Path lifecycle:
        A. Authoritative forecast seeded
        B. DAPH lists eligible Vets for district -> sees vet_officer_01
        C. DAPH issues follow-up to vet_officer_01
        D. Verify snapshot copied, priority derived (HIGH), status ISSUED, version 1
        E. Assigned Vet lists follow-ups and sees new record
        F. Unassigned Vet (vet_officer_02) cannot read or transition record (403)
        G. Assigned Vet acknowledges (version 1 -> 2, ACKNOWLEDGED)
        H. Assigned Vet starts action (version 2 -> 3, ACTION_IN_PROGRESS)
        I. Assigned Vet completes action (version 3 -> 4, COMPLETED)
        J. DAPH lists/gets record and observes status COMPLETED
        K. Scientific snapshot remained unchanged throughout all transitions
        """
        # B. DAPH queries eligible Vets for Anuradhapura
        res_vets = self.client.get(
            "/api/v1/risk-forecasting/follow-up-vets?district=Anuradhapura",
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_vets.status_code, 200)
        vets_data = res_vets.json()
        eligible_vet_ids = [v["vet_id"] for v in vets_data["veterinary_officers"]]
        self.assertIn("vet_officer_01", eligible_vet_ids)

        # C. DAPH issues follow-up for forecast fdr_e2e_anu_001 assigned to vet_officer_01
        issue_payload = {
            "forecast_id": "fdr_e2e_anu_001",
            "assigned_vet_id": "vet_officer_01",
            "instruction_summary": "Initiate target ring vaccination and ring surveillance in Anuradhapura division 3.",
            "idempotency_key": "idemp_e2e_happy_001",
        }
        res_issue = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json=issue_payload,
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_issue.status_code, 201)
        fu_data = res_issue.json()
        fu_id = fu_data["follow_up_id"]

        # D. Verify initial record state
        self.assertEqual(fu_data["forecast_id"], "fdr_e2e_anu_001")
        self.assertEqual(fu_data["district"], "Anuradhapura")
        self.assertEqual(fu_data["disease"], "FMD")
        self.assertEqual(fu_data["target_year"], 2026)
        self.assertEqual(fu_data["target_month"], 9)
        self.assertEqual(fu_data["forecast_risk_level"], "HIGH")
        self.assertEqual(fu_data["operational_priority"], "HIGH")
        self.assertEqual(fu_data["assigned_vet_id"], "vet_officer_01")
        self.assertEqual(fu_data["issued_by_daph_id"], "daph_hq_01")
        self.assertEqual(fu_data["status"], "ISSUED")
        self.assertEqual(fu_data["version"], 1)

        # E. Assigned Vet (vet_officer_01) lists follow-ups and sees the new record
        res_vet_list = self.client.get(
            "/api/v1/risk-forecasting/follow-ups",
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_vet_list.status_code, 200)
        vet_records = res_vet_list.json()["follow_ups"]
        self.assertEqual(len(vet_records), 1)
        self.assertEqual(vet_records[0]["follow_up_id"], fu_id)

        # F. Unassigned Vet (vet_officer_02) cannot read or acknowledge this record (403 Forbidden)
        res_unassigned_get = self.client.get(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}",
            headers={"X-Actor-ID": "vet_officer_02", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_unassigned_get.status_code, 403)

        res_unassigned_ack = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/acknowledge",
            json={"version": 1},
            headers={"X-Actor-ID": "vet_officer_02", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_unassigned_ack.status_code, 403)

        # G & H. Assigned Vet acknowledges follow-up using version 1
        res_ack = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/acknowledge",
            json={"version": 1},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_ack.status_code, 200)
        ack_data = res_ack.json()
        self.assertEqual(ack_data["status"], "ACKNOWLEDGED")
        self.assertEqual(ack_data["version"], 2)

        # I & J. Assigned Vet starts action using version 2
        res_start = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/start",
            json={"version": 2},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_start.status_code, 200)
        start_data = res_start.json()
        self.assertEqual(start_data["status"], "ACTION_IN_PROGRESS")
        self.assertEqual(start_data["version"], 3)

        # K & L. Assigned Vet completes action using version 3
        res_complete = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/complete",
            json={"version": 3},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_complete.status_code, 200)
        complete_data = res_complete.json()
        self.assertEqual(complete_data["status"], "COMPLETED")
        self.assertEqual(complete_data["version"], 4)

        # M. DAPH lists/gets the record and sees status COMPLETED
        res_daph_get = self.client.get(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}",
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_daph_get.status_code, 200)
        final_daph_record = res_daph_get.json()
        self.assertEqual(final_daph_record["status"], "COMPLETED")
        self.assertEqual(final_daph_record["version"], 4)

        # N. Scientific snapshot remained completely unchanged throughout all transitions
        self.assertEqual(final_daph_record["district"], "Anuradhapura")
        self.assertEqual(final_daph_record["disease"], "FMD")
        self.assertEqual(final_daph_record["target_year"], 2026)
        self.assertEqual(final_daph_record["target_month"], 9)
        self.assertEqual(final_daph_record["forecast_risk_level"], "HIGH")
        self.assertEqual(final_daph_record["operational_priority"], "HIGH")

    def test_escalation_workflow_and_terminal_guard(self):
        """Tests assigned Vet escalation and proves terminal status denies further transitions."""
        # 1. DAPH issues follow-up
        res_issue = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={
                "forecast_id": "fdr_e2e_anu_001",
                "assigned_vet_id": "vet_officer_01",
                "instruction_summary": "Perform clinical inspection of dairy herds.",
            },
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        fu_id = res_issue.json()["follow_up_id"]

        # 2. Vet escalates with reason (version 1 -> 2, ESCALATED)
        res_esc = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/escalate",
            json={"version": 1, "reason": "Insufficient personal protective equipment and cold-chain storage."},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_esc.status_code, 200)
        esc_data = res_esc.json()
        self.assertEqual(esc_data["status"], "ESCALATED")
        self.assertEqual(esc_data["version"], 2)
        self.assertIn("Insufficient personal protective equipment", esc_data["escalation_reason"])

        # 3. DAPH sees ESCALATED status
        res_daph_get = self.client.get(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}",
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_daph_get.json()["status"], "ESCALATED")

        # 4. Terminal status guard: Submitting further transitions returns HTTP 409 Conflict
        res_denied_start = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/start",
            json={"version": 2},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_denied_start.status_code, 409)

    def test_cancellation_workflow_and_vet_preemption(self):
        """Tests DAPH cancellation of active task and proves Vet transitions are denied afterward."""
        # 1. DAPH issues follow-up
        res_issue = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={
                "forecast_id": "fdr_e2e_anu_001",
                "assigned_vet_id": "vet_officer_01",
                "instruction_summary": "Surveillance sampling instruction.",
            },
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        fu_id = res_issue.json()["follow_up_id"]

        # 2. DAPH cancels active task
        res_cancel = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/cancel",
            json={"version": 1, "reason": "Operational priority reassigned due to updated regional alert."},
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_cancel.status_code, 200)
        self.assertEqual(res_cancel.json()["status"], "CANCELLED")

        # 3. Vet sees CANCELLED status
        res_vet_get = self.client.get(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}",
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_vet_get.json()["status"], "CANCELLED")

        # 4. Vet cannot acknowledge or start cancelled follow-up (HTTP 409 Conflict)
        res_vet_ack = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/acknowledge",
            json={"version": 2},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_vet_ack.status_code, 409)

    def test_daph_authoritative_cancellation_contract_e2e(self):
        """
        Explicit E2E verification of DAPH cancellation contract:
        - DAPH uses authoritative forecast fixture
        - DAPH issues a follow-up
        - DAPH cancels using authoritative version 1 (reason is optional)
        - Returned status is CANCELLED, version increments exactly once (1 -> 2)
        - cancelled_at is populated
        - Assigned Vet lists/gets and observes status CANCELLED
        - Vet cannot acknowledge, start, or complete a cancelled follow-up (409 Conflict)
        - Scientific snapshot remains completely unchanged
        - Repository contains exactly one follow-up record
        """
        # 1. DAPH issues follow-up for authoritative forecast fdr_e2e_anu_001
        res_issue = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={
                "forecast_id": "fdr_e2e_anu_001",
                "assigned_vet_id": "vet_officer_01",
                "instruction_summary": "Authoritative cancellation test task.",
            },
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_issue.status_code, 201)
        fu_initial = res_issue.json()
        fu_id = fu_initial["follow_up_id"]
        self.assertEqual(fu_initial["version"], 1)
        self.assertEqual(fu_initial["status"], "ISSUED")

        # 2. DAPH cancels using authoritative version 1 (without optional reason)
        res_cancel = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/cancel",
            json={"version": 1},
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_cancel.status_code, 200)
        cancelled_data = res_cancel.json()

        # 3. Verify status, version, cancelled_at
        self.assertEqual(cancelled_data["status"], "CANCELLED")
        self.assertEqual(cancelled_data["version"], 2)  # Incremented exactly once
        self.assertIsNotNone(cancelled_data.get("cancelled_at"))
        self.assertTrue(len(cancelled_data["cancelled_at"]) > 0)

        # 4. Assigned Vet lists and gets record -> sees CANCELLED status
        res_vet_get = self.client.get(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}",
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_vet_get.status_code, 200)
        vet_record = res_vet_get.json()
        self.assertEqual(vet_record["status"], "CANCELLED")
        self.assertEqual(vet_record["version"], 2)

        res_vet_list = self.client.get(
            "/api/v1/risk-forecasting/follow-ups",
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_vet_list.status_code, 200)
        list_follow_ups = res_vet_list.json()["follow_ups"]
        self.assertEqual(len(list_follow_ups), 1)
        self.assertEqual(list_follow_ups[0]["status"], "CANCELLED")

        # 5. Vet cannot acknowledge, start, or complete afterward
        res_ack = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/acknowledge",
            json={"version": 2},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_ack.status_code, 409)

        res_start = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/start",
            json={"version": 2},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_start.status_code, 409)

        res_complete = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/complete",
            json={"version": 2},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_complete.status_code, 409)

        # 6. Scientific snapshot remains unchanged
        self.assertEqual(vet_record["district"], "Anuradhapura")
        self.assertEqual(vet_record["disease"], "FMD")
        self.assertEqual(vet_record["target_year"], 2026)
        self.assertEqual(vet_record["target_month"], 9)
        self.assertEqual(vet_record["forecast_risk_level"], "HIGH")
        self.assertEqual(vet_record["operational_priority"], "HIGH")

        # 7. Repository contains only the single expected follow-up record
        all_records = forecast_follow_up_service.follow_up_repo._records
        self.assertEqual(len(all_records), 1)

    def test_optimistic_concurrency_conflict(self):
        """Tests that stale version numbers return HTTP 409 Conflict without altering stored record state."""
        # 1. Create follow-up (version 1)
        res_issue = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={
                "forecast_id": "fdr_e2e_anu_001",
                "assigned_vet_id": "vet_officer_01",
                "instruction_summary": "Sample test instruction.",
            },
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        fu_id = res_issue.json()["follow_up_id"]

        # 2. Acknowledge (version 1 -> 2)
        self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/acknowledge",
            json={"version": 1},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )

        # 3. Submit stale version 1 to start action -> returns HTTP 409 Conflict
        res_stale = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/start",
            json={"version": 1},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_stale.status_code, 409)

        # 4. Verify authoritative record remains at version 2 and status ACKNOWLEDGED
        res_get = self.client.get(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}",
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        rec = res_get.json()
        self.assertEqual(rec["version"], 2)
        self.assertEqual(rec["status"], "ACKNOWLEDGED")

    def test_idempotency_deduplication_and_collision(self):
        """Tests idempotency key deduplication and collision detection."""
        key = "idemp_test_dedup_001"
        payload = {
            "forecast_id": "fdr_e2e_anu_001",
            "assigned_vet_id": "vet_officer_01",
            "instruction_summary": "Idempotent follow-up instruction.",
            "idempotency_key": key,
        }

        # 1. Initial request creates record
        res1 = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json=payload,
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res1.status_code, 201)
        rec1 = res1.json()

        # 2. Repeated identical request returns same record
        res2 = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json=payload,
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res2.status_code, 201)
        rec2 = res2.json()
        self.assertEqual(rec1["follow_up_id"], rec2["follow_up_id"])

        # 3. Request with same idempotency key but different parameters returns HTTP 409 Conflict
        colliding_payload = {
            **payload,
            "instruction_summary": "DIFFERENT instruction summary with same key.",
        }
        res_conflict = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json=colliding_payload,
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_conflict.status_code, 409)

    def test_role_authorization_isolation(self):
        """Tests strict role isolation rules across FARMER, VETERINARY_OFFICER, and DAPH_OFFICIAL."""
        # 1. FARMER role denied on issue (403)
        res_farmer_issue = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={"forecast_id": "fdr_e2e_anu_001", "assigned_vet_id": "vet_officer_01", "instruction_summary": "Test"},
            headers={"X-Actor-ID": "farmer_01", "X-Actor-Role": "FARMER"},
        )
        self.assertEqual(res_farmer_issue.status_code, 403)

        # 2. VETERINARY_OFFICER role denied on issue (403)
        res_vet_issue = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={"forecast_id": "fdr_e2e_anu_001", "assigned_vet_id": "vet_officer_01", "instruction_summary": "Test"},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_vet_issue.status_code, 403)

        # 3. Create valid follow-up as DAPH
        res_ok_issue = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={"forecast_id": "fdr_e2e_anu_001", "assigned_vet_id": "vet_officer_01", "instruction_summary": "Test"},
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        fu_id = res_ok_issue.json()["follow_up_id"]

        # 4. DAPH_OFFICIAL denied on acknowledge transition (403)
        res_daph_ack = self.client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/acknowledge",
            json={"version": 1},
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_daph_ack.status_code, 403)

    def test_record_separation_across_veterinary_officers(self):
        """Tests that follow-ups assigned to Vet A are not visible to Vet B."""
        # 1. Issue follow-up 1 for vet_officer_01 in Anuradhapura
        res1 = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={"forecast_id": "fdr_e2e_anu_001", "assigned_vet_id": "vet_officer_01", "instruction_summary": "Vet 1 task"},
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        fu1_id = res1.json()["follow_up_id"]

        # 2. Issue follow-up 2 for vet_officer_02 in Kurunegala
        res2 = self.client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={"forecast_id": "fdr_e2e_kuru_002", "assigned_vet_id": "vet_officer_02", "instruction_summary": "Vet 2 task"},
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        fu2_id = res2.json()["follow_up_id"]

        # 3. vet_officer_01 lists follow-ups -> sees ONLY fu1_id
        res_vet1_list = self.client.get(
            "/api/v1/risk-forecasting/follow-ups",
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        vet1_ids = [r["follow_up_id"] for r in res_vet1_list.json()["follow_ups"]]
        self.assertIn(fu1_id, vet1_ids)
        self.assertNotIn(fu2_id, vet1_ids)

        # 4. vet_officer_02 lists follow-ups -> sees ONLY fu2_id
        res_vet2_list = self.client.get(
            "/api/v1/risk-forecasting/follow-ups",
            headers={"X-Actor-ID": "vet_officer_02", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        vet2_ids = [r["follow_up_id"] for r in res_vet2_list.json()["follow_ups"]]
        self.assertIn(fu2_id, vet2_ids)
        self.assertNotIn(fu1_id, vet2_ids)


if __name__ == "__main__":
    unittest.main()
