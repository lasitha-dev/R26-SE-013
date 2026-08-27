"""
Comprehensive Unit & Integration Test Suite for Forecast-Linked DAPH–Vet Follow-Up Backend Foundation (Phase 6B-1).

Tests domain schemas, priority derivation, snapshot immutability, Veterinary Officer directory verification,
optimistic concurrency locking, actor authorization boundaries, repository defensive copies, idempotency,
and HTTP API endpoints via FastAPI TestClient.
"""

from datetime import datetime, timezone
import unittest
from fastapi.testclient import TestClient

from components.risk_forecasting.integrations.vet_directory import (
    InMemoryVeterinaryOfficerDirectory,
    VeterinaryOfficerSummary,
)
from components.risk_forecasting.repositories.forecast_record_repository import (
    InMemoryForecastRecordRepository,
)
from components.risk_forecasting.repositories.follow_up_repository import (
    InMemoryFollowUpRepository,
)
from components.risk_forecasting.routes import router
from components.risk_forecasting.schemas import (
    CreateFollowUpRequest,
    FollowUpActorContext,
    ForecastDecisionRecord,
    ForecastFollowUpRecord,
    LinkExternalResourceRequest,
    TransitionFollowUpRequest,
)
from components.risk_forecasting.services.forecast_record_service import (
    ForecastRecordService,
    forecast_record_service,
)
from components.risk_forecasting.services.follow_up_service import (
    ForecastFollowUpService,
)
from fastapi import FastAPI

# App test wrapper
app = FastAPI()
app.include_router(router, prefix="/api/v1/risk-forecasting")


class TestForecastFollowUpFoundation(unittest.TestCase):
    """Full unit and integration test suite for DAPH–Vet follow-up backend foundation."""

    def setUp(self):
        self.forecast_repo = InMemoryForecastRecordRepository()
        self.forecast_svc = ForecastRecordService(repository=self.forecast_repo)
        self.follow_up_repo = InMemoryFollowUpRepository()
        self.vet_dir = InMemoryVeterinaryOfficerDirectory()
        self.service = ForecastFollowUpService(
            forecast_service=self.forecast_svc,
            follow_up_repository=self.follow_up_repo,
            vet_directory=self.vet_dir,
        )

        # Seed sample official forecast record
        self.sample_forecast = ForecastDecisionRecord(
            forecast_id="fdr_test_fmd_001",
            disease="FMD",
            district="Anuradhapura",
            target_year=2026,
            target_month=8,
            risk_level="HIGH",
            probability=0.87,
            probability_pct=87.0,
            predicted_severity="HIGH",
            model_variant="30_feature_baseline",
            fallback_applied=False,
            data_quality="EXACT",
            disclaimer="Test forecast disclaimer",
            provenance="OFFICIAL_TEST",
            generated_at="2026-08-23T10:00:00Z",
            status="GENERATED",
            created_at="2026-08-23T10:00:00Z",
            updated_at="2026-08-23T10:00:00Z",
        )
        self.forecast_repo.save(self.sample_forecast)
        if not forecast_record_service.repository.get_by_id(self.sample_forecast.forecast_id):
            forecast_record_service.repository.save(self.sample_forecast)

        # Pre-seed second forecast (MEDIUM risk)
        self.medium_forecast = ForecastDecisionRecord(
            forecast_id="fdr_test_lsd_002",
            disease="LSD",
            district="Colombo",
            target_year=2026,
            target_month=8,
            risk_level="MEDIUM",
            probability=0.45,
            probability_pct=45.0,
            predicted_severity="MEDIUM",
            model_variant="28_feature_production",
            fallback_applied=False,
            data_quality="EXACT",
            disclaimer="Test LSD disclaimer",
            provenance="OFFICIAL_TEST",
            generated_at="2026-08-23T10:00:00Z",
            status="GENERATED",
            created_at="2026-08-23T10:00:00Z",
            updated_at="2026-08-23T10:00:00Z",
        )
        self.forecast_repo.save(self.medium_forecast)
        if not forecast_record_service.repository.get_by_id(self.medium_forecast.forecast_id):
            forecast_record_service.repository.save(self.medium_forecast)

        self.daph_actor = FollowUpActorContext(actor_id="daph_hq_01", role="DAPH_OFFICIAL", scope_level="NATIONAL")
        self.vet_actor = FollowUpActorContext(actor_id="vet_officer_01", role="VETERINARY_OFFICER", authorized_districts=["Anuradhapura", "Colombo"])
        self.other_vet_actor = FollowUpActorContext(actor_id="vet_officer_02", role="VETERINARY_OFFICER", authorized_districts=["Kurunegala"])
        self.farmer_actor = FollowUpActorContext(actor_id="farmer_01", role="FARMER")

    # ─── 1. Schema & Validation Tests ──────────────────────────────────────────

    def test_create_request_rejects_scientific_snapshot_tampering(self):
        """Ensures CreateFollowUpRequest accepts no scientific snapshot inputs from client."""
        fields = CreateFollowUpRequest.model_fields.keys()
        self.assertNotIn("district", fields)
        self.assertNotIn("disease", fields)
        self.assertNotIn("target_year", fields)
        self.assertNotIn("target_month", fields)
        self.assertNotIn("forecast_risk_level", fields)
        self.assertNotIn("operational_priority", fields)
        self.assertNotIn("stock_quantity", fields)
        self.assertNotIn("vaccine_inventory", fields)

    def test_instruction_summary_validation(self):
        """Validates min length and max length constraint on instruction_summary."""
        with self.assertRaises(ValueError):
            CreateFollowUpRequest(
                forecast_id="fdr_test_fmd_001",
                assigned_vet_id="vet_officer_01",
                instruction_summary="",
            )

    # ─── 2. Follow-Up Issue Tests ──────────────────────────────────────────────

    def test_successful_issue_follow_up(self):
        """Verifies successful issuance by DAPH with correct scientific snapshot copying and priority derivation."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Deploy active ring vaccination around Maha Illuppallama.",
        )
        record = self.service.issue_follow_up(req, actor=self.daph_actor)

        self.assertTrue(record.follow_up_id.startswith("ffu_"))
        self.assertEqual(record.forecast_id, "fdr_test_fmd_001")
        self.assertEqual(record.district, "Anuradhapura")
        self.assertEqual(record.disease, "FMD")
        self.assertEqual(record.target_year, 2026)
        self.assertEqual(record.target_month, 8)
        self.assertEqual(record.forecast_risk_level, "HIGH")
        self.assertEqual(record.operational_priority, "HIGH")
        self.assertEqual(record.status, "ISSUED")
        self.assertEqual(record.version, 1)
        self.assertEqual(record.assigned_vet_id, "vet_officer_01")

    def test_priority_derivation_from_medium_forecast(self):
        """Verifies MEDIUM risk level derives MEDIUM operational priority."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_lsd_002",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Monitor vector control in Colombo district.",
        )
        record = self.service.issue_follow_up(req, actor=self.daph_actor)
        self.assertEqual(record.forecast_risk_level, "MEDIUM")
        self.assertEqual(record.operational_priority, "MEDIUM")

    def test_issue_denied_for_missing_forecast(self):
        """Rejects issuance when referenced forecast ID does not exist."""
        req = CreateFollowUpRequest(
            forecast_id="non_existent_fdr",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Check district status.",
        )
        with self.assertRaises(KeyError):
            self.service.issue_follow_up(req, actor=self.daph_actor)

    def test_issue_denied_for_superseded_forecast(self):
        """Rejects issuance for superseded forecast records."""
        self.forecast_repo.update_status("fdr_test_fmd_001", "SUPERSEDED")
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Check district status.",
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.issue_follow_up(req, actor=self.daph_actor)
        self.assertIn("superseded", str(ctx.exception).lower())

    def test_issue_denied_for_inactive_or_unassigned_vet(self):
        """Rejects issuance when assigned Vet is inactive or not assigned to forecast district."""
        # Unassigned Vet (vet_officer_02 is assigned to Kurunegala, forecast is Anuradhapura)
        req_unassigned = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_02",
            instruction_summary="Check district status.",
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.issue_follow_up(req_unassigned, actor=self.daph_actor)
        self.assertIn("not assigned to district", str(ctx.exception))

        # Inactive Vet
        req_inactive = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_inactive_01",
            instruction_summary="Check district status.",
        )
        with self.assertRaises(ValueError) as ctx2:
            self.service.issue_follow_up(req_inactive, actor=self.daph_actor)
        self.assertIn("inactive", str(ctx2.exception).lower())

    def test_issue_denied_for_non_daph_actors(self):
        """Rejects follow-up issuance when initiated by a Vet or Farmer actor."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Self-issued task attempt.",
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.issue_follow_up(req, actor=self.vet_actor)
        self.assertIn("not authorized", str(ctx.exception))

    def test_issue_idempotency_behavior(self):
        """Verifies idempotent record retrieval vs collision handling."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Deploy active ring vaccination.",
            idempotency_key="idemp_ffu_100",
        )
        first = self.service.issue_follow_up(req, actor=self.daph_actor)
        second = self.service.issue_follow_up(req, actor=self.daph_actor)
        self.assertEqual(first.follow_up_id, second.follow_up_id)

        # Idempotency collision with modified parameter
        req_diff = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="DIFFERENT INSTRUCTION TEXT",
            idempotency_key="idemp_ffu_100",
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.issue_follow_up(req_diff, actor=self.daph_actor)
        self.assertIn("collision", str(ctx.exception).lower())

    # ─── 3. Repository Defensive Copy & Query Tests ────────────────────────────

    def test_repository_defensive_copies(self):
        """Verifies repository returns deep copies that cannot mutate internal store."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Defensive copy test.",
        )
        saved = self.service.issue_follow_up(req, actor=self.daph_actor)
        fetched = self.service.get_follow_up(saved.follow_up_id)

        # Mutate fetched object locally
        fetched.instruction_summary = "MUTATED LOCALLY"

        re_fetched = self.service.get_follow_up(saved.follow_up_id)
        self.assertEqual(re_fetched.instruction_summary, "Defensive copy test.")

    def test_list_follow_ups_scoping_and_pagination(self):
        """Verifies list filters, pagination limit/offset, and actor scoping."""
        req1 = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Task 1",
        )
        req2 = CreateFollowUpRequest(
            forecast_id="fdr_test_lsd_002",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Task 2",
        )
        self.service.issue_follow_up(req1, actor=self.daph_actor)
        self.service.issue_follow_up(req2, actor=self.daph_actor)

        # List all as DAPH
        res_daph = self.service.list_follow_ups(actor=self.daph_actor)
        self.assertEqual(res_daph.total_count, 2)

        # List filtered by district
        res_dist = self.service.list_follow_ups(district="Anuradhapura", actor=self.daph_actor)
        self.assertEqual(res_dist.total_count, 1)
        self.assertEqual(res_dist.follow_ups[0].district, "Anuradhapura")

        # Farmer denied access
        with self.assertRaises(ValueError):
            self.service.list_follow_ups(actor=self.farmer_actor)

    # ─── 4. Lifecycle Transition Tests ─────────────────────────────────────────

    def test_complete_lifecycle_happy_path(self):
        """Tests ISSUED -> ACKNOWLEDGED -> ACTION_IN_PROGRESS -> COMPLETED transition chain."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Complete lifecycle test.",
        )
        rec = self.service.issue_follow_up(req, actor=self.daph_actor)
        self.assertEqual(rec.status, "ISSUED")
        self.assertEqual(rec.version, 1)

        # 1. Vet Acknowledges
        ack = self.service.acknowledge_follow_up(rec.follow_up_id, expected_version=1, actor=self.vet_actor)
        self.assertEqual(ack.status, "ACKNOWLEDGED")
        self.assertEqual(ack.version, 2)
        self.assertIsNotNone(ack.acknowledged_at)

        # 2. Vet Starts Action
        start = self.service.start_follow_up_action(rec.follow_up_id, expected_version=2, actor=self.vet_actor)
        self.assertEqual(start.status, "ACTION_IN_PROGRESS")
        self.assertEqual(start.version, 3)
        self.assertIsNotNone(start.action_started_at)

        # 3. Vet Completes Action
        comp = self.service.complete_follow_up(rec.follow_up_id, expected_version=3, actor=self.vet_actor)
        self.assertEqual(comp.status, "COMPLETED")
        self.assertEqual(comp.version, 4)
        self.assertIsNotNone(comp.completed_at)

        # Verify scientific snapshot fields remain untouched
        self.assertEqual(comp.district, "Anuradhapura")
        self.assertEqual(comp.disease, "FMD")
        self.assertEqual(comp.target_year, 2026)
        self.assertEqual(comp.target_month, 8)
        self.assertEqual(comp.forecast_risk_level, "HIGH")

    def test_unassigned_vet_cannot_acknowledge(self):
        """Rejects acknowledgement attempts by an unassigned Veterinary Officer."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Targeted to vet 01.",
        )
        rec = self.service.issue_follow_up(req, actor=self.daph_actor)

        with self.assertRaises(ValueError) as ctx:
            self.service.acknowledge_follow_up(rec.follow_up_id, expected_version=1, actor=self.other_vet_actor)
        self.assertIn("not the assigned officer", str(ctx.exception))

    def test_daph_cannot_acknowledge_as_vet(self):
        """Rejects DAPH official attempting to perform Vet acknowledgement action."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Targeted to vet 01.",
        )
        rec = self.service.issue_follow_up(req, actor=self.daph_actor)

        with self.assertRaises(ValueError) as ctx:
            self.service.acknowledge_follow_up(rec.follow_up_id, expected_version=1, actor=self.daph_actor)
        self.assertIn("Only a Veterinary Officer", str(ctx.exception))

    def test_stale_version_optimistic_locking_conflict(self):
        """Rejects status transition when expected version does not match current version."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Concurrency test.",
        )
        rec = self.service.issue_follow_up(req, actor=self.daph_actor)

        # Attempt transition with wrong version (expected version 99 instead of 1)
        with self.assertRaises(ValueError) as ctx:
            self.service.acknowledge_follow_up(rec.follow_up_id, expected_version=99, actor=self.vet_actor)
        self.assertIn("Optimistic lock conflict", str(ctx.exception))

    def test_daph_cancellation_flow(self):
        """Tests DAPH official cancelling an ISSUED follow-up instruction."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Cancellation test.",
        )
        rec = self.service.issue_follow_up(req, actor=self.daph_actor)

        cancelled = self.service.cancel_follow_up(
            rec.follow_up_id, expected_version=1, reason="Risk re-assessed by DAPH HQ.", actor=self.daph_actor
        )
        self.assertEqual(cancelled.status, "CANCELLED")
        self.assertEqual(cancelled.cancellation_reason, "Risk re-assessed by DAPH HQ.")
        self.assertIsNotNone(cancelled.cancelled_at)

        # Vet cannot cancel
        with self.assertRaises(ValueError):
            self.service.cancel_follow_up(rec.follow_up_id, expected_version=2, reason="Vet cancel attempt", actor=self.vet_actor)

    def test_escalation_flow(self):
        """Tests escalating a follow-up instruction with explicit reason requirement."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Escalation test.",
        )
        rec = self.service.issue_follow_up(req, actor=self.daph_actor)

        # Empty reason rejected
        with self.assertRaises(ValueError):
            self.service.escalate_follow_up(rec.follow_up_id, expected_version=1, reason="", actor=self.vet_actor)

        # Valid escalation
        esc = self.service.escalate_follow_up(
            rec.follow_up_id, expected_version=1, reason="Outbreak spread beyond regional vaccine quota.", actor=self.vet_actor
        )
        self.assertEqual(esc.status, "ESCALATED")
        self.assertEqual(esc.escalation_reason, "Outbreak spread beyond regional vaccine quota.")
        self.assertIsNotNone(esc.escalated_at)

    def test_external_resource_reference_linking(self):
        """Tests associating an opaque external supply chain resource request reference ID."""
        req = CreateFollowUpRequest(
            forecast_id="fdr_test_fmd_001",
            assigned_vet_id="vet_officer_01",
            instruction_summary="Resource reference test.",
        )
        rec = self.service.issue_follow_up(req, actor=self.daph_actor)

        linked = self.service.link_external_resource_request(
            rec.follow_up_id, expected_version=1, external_resource_request_id="ext_res_req_9988", actor=self.daph_actor
        )
        self.assertEqual(linked.external_resource_request_id, "ext_res_req_9988")
        self.assertEqual(linked.version, 2)

    # ─── 5. FastAPI Route Integration Tests ────────────────────────────────────

    def test_api_issue_and_read_roundtrip(self):
        """Tests HTTP POST /follow-ups and GET /follow-ups/{id} endpoints via TestClient."""
        client = TestClient(app)

        payload = {
            "forecast_id": "fdr_test_fmd_001",
            "assigned_vet_id": "vet_officer_01",
            "instruction_summary": "HTTP API roundtrip test instruction.",
        }
        headers = {
            "X-Actor-ID": "daph_hq_01",
            "X-Actor-Role": "DAPH_OFFICIAL",
        }

        # POST /follow-ups
        res_post = client.post("/api/v1/risk-forecasting/follow-ups", json=payload, headers=headers)
        self.assertEqual(res_post.status_code, 201)
        data = res_post.json()
        self.assertEqual(data["district"], "Anuradhapura")
        self.assertEqual(data["status"], "ISSUED")
        self.assertEqual(data["issued_by_daph_id"], "daph_hq_01")
        follow_up_id = data["follow_up_id"]

        # GET /follow-ups/{follow_up_id}
        res_get = client.get(f"/api/v1/risk-forecasting/follow-ups/{follow_up_id}", headers=headers)
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["follow_up_id"], follow_up_id)

    def test_api_idempotency_header_body_mismatch(self):
        """Verifies HTTP 409 Conflict when Header and Body idempotency keys mismatch."""
        client = TestClient(app)

        payload = {
            "forecast_id": "fdr_test_fmd_001",
            "assigned_vet_id": "vet_officer_01",
            "instruction_summary": "Mismatch test.",
            "idempotency_key": "body_key_001",
        }
        headers = {
            "Idempotency-Key": "header_key_999",
            "X-Actor-ID": "daph_hq_01",
            "X-Actor-Role": "DAPH_OFFICIAL",
        }

        res = client.post("/api/v1/risk-forecasting/follow-ups", json=payload, headers=headers)
        self.assertEqual(res.status_code, 409)
        self.assertIn("mismatch", res.json()["detail"].lower())

    def test_api_transitions_and_optimistic_lock_conflicts(self):
        """Tests HTTP POST transition endpoints and HTTP 409 conflict handling."""
        client = TestClient(app)

        # Issue follow-up
        res_post = client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={
                "forecast_id": "fdr_test_fmd_001",
                "assigned_vet_id": "vet_officer_01",
                "instruction_summary": "Transition test.",
            },
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        fu_id = res_post.json()["follow_up_id"]

        # Acknowledge with correct version (1)
        res_ack = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/acknowledge?version=1",
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_ack.status_code, 200)
        self.assertEqual(res_ack.json()["status"], "ACKNOWLEDGED")
        self.assertEqual(res_ack.json()["version"], 2)

        # Acknowledge again with stale version (1) -> 409 Conflict
        res_ack_stale = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/acknowledge?version=1",
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_ack_stale.status_code, 409)

        # Start action with version 2
        res_start = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/start?version=2",
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_start.status_code, 200)
        self.assertEqual(res_start.json()["status"], "ACTION_IN_PROGRESS")
        self.assertEqual(res_start.json()["version"], 3)

    # ─── 6. Client Identity Spoofing & Security Boundary Tests ─────────────────

    def test_api_rejects_issued_by_daph_id_in_request_body(self):
        """
        Verifies HTTP 422 when client submits issued_by_daph_id in request body.
        Issuer identity MUST be derived only from trusted actor context / X-Actor-ID header.
        NOTE: Standalone X-Actor headers represent the request boundary; in production these are injected via verified JWT / shared IAM claims.
        """
        client = TestClient(app)
        payload = {
            "forecast_id": "fdr_test_fmd_001",
            "assigned_vet_id": "vet_officer_01",
            "instruction_summary": "Spoofed issuer attempt.",
            "issued_by_daph_id": "daph_spoofed_999",
        }
        res = client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json=payload,
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res.status_code, 422)

    def test_api_rejects_actor_id_in_transition_request_body(self):
        """
        Verifies HTTP 422 when client submits actor_id in transition request body.
        Transition actor identity MUST be derived only from trusted actor context / X-Actor-ID header.
        NOTE: Standalone X-Actor headers represent the request boundary; in production these are injected via verified JWT / shared IAM claims.
        """
        client = TestClient(app)
        # Issue valid follow-up
        res_issue = client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={
                "forecast_id": "fdr_test_fmd_001",
                "assigned_vet_id": "vet_officer_01",
                "instruction_summary": "Transition spoof test.",
            },
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        fu_id = res_issue.json()["follow_up_id"]

        # Attempt acknowledge with spoofed body actor_id
        res_ack = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/acknowledge",
            json={"version": 1, "actor_id": "vet_officer_spoofed_888"},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_ack.status_code, 422)

    def test_farmer_cannot_issue_or_transition_follow_up(self):
        """
        Verifies Farmers cannot issue or execute transitions even with spoofed body headers/payloads.
        """
        client = TestClient(app)
        # Farmer issue attempt -> 403
        res_issue = client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={
                "forecast_id": "fdr_test_fmd_001",
                "assigned_vet_id": "vet_officer_01",
                "instruction_summary": "Farmer issue attempt.",
            },
            headers={"X-Actor-ID": "farmer_999", "X-Actor-Role": "FARMER"},
        )
        self.assertEqual(res_issue.status_code, 403)

    def test_unassigned_vet_denied_transition(self):
        """Verifies unassigned Vet (vet_officer_02) is denied acknowledgement of vet_officer_01's follow-up."""
        client = TestClient(app)
        res_issue = client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={
                "forecast_id": "fdr_test_fmd_001",
                "assigned_vet_id": "vet_officer_01",
                "instruction_summary": "Unassigned vet test.",
            },
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        fu_id = res_issue.json()["follow_up_id"]

        res_ack = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/acknowledge?version=1",
            headers={"X-Actor-ID": "vet_officer_02", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_ack.status_code, 403)

    # ─── 7. Resource-Link Authorization Tests ──────────────────────────────────

    def test_resource_link_authorization_boundary(self):
        """
        Confirms resource link request contains only version and external_resource_request_id (extra fields forbidden),
        and verifies authorization scoping for assigned Vet vs unassigned Vet vs Farmer vs DAPH.
        """
        client = TestClient(app)
        res_issue = client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={
                "forecast_id": "fdr_test_fmd_001",
                "assigned_vet_id": "vet_officer_01",
                "instruction_summary": "Resource link auth test.",
            },
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        fu_id = res_issue.json()["follow_up_id"]

        # Reject payload containing actor_id in body (422)
        res_extra = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/external-resource-reference",
            json={"version": 1, "external_resource_request_id": "req_ext_100", "actor_id": "vet_officer_01"},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_extra.status_code, 422)

        # Farmer denied (403)
        res_farmer = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/external-resource-reference",
            json={"version": 1, "external_resource_request_id": "req_ext_100"},
            headers={"X-Actor-ID": "farmer_01", "X-Actor-Role": "FARMER"},
        )
        self.assertEqual(res_farmer.status_code, 403)

        # Unassigned Vet denied (403)
        res_unassigned = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/external-resource-reference",
            json={"version": 1, "external_resource_request_id": "req_ext_100"},
            headers={"X-Actor-ID": "vet_officer_02", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_unassigned.status_code, 403)

        # Assigned Vet succeeds (200)
        res_assigned = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/external-resource-reference",
            json={"version": 1, "external_resource_request_id": "req_ext_100"},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_assigned.status_code, 200)
        rec_data = res_assigned.json()
        self.assertEqual(rec_data["external_resource_request_id"], "req_ext_100")
        self.assertEqual(rec_data["version"], 2)
        # Verify NO stock/inventory/quantities fields present in response
        self.assertNotIn("stock_quantity", rec_data)
        self.assertNotIn("vaccine_inventory", rec_data)
        self.assertNotIn("warehouse_id", rec_data)

    def test_list_eligible_follow_up_vets_endpoint(self):
        """Tests GET /api/v1/risk-forecasting/follow-up-vets authorization, district filtering, sorting, and PII protection."""
        client = TestClient(app)
        _, initial_follow_ups_count = self.follow_up_repo.list()

        # 1. Authorized DAPH receives active Vets for requested district ("Anuradhapura")
        res_daph = client.get(
            "/api/v1/risk-forecasting/follow-up-vets?district=Anuradhapura",
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_daph.status_code, 200)
        data = res_daph.json()
        self.assertEqual(data["district"], "Anuradhapura")
        self.assertGreaterEqual(data["total_count"], 2)

        vet_list = data["veterinary_officers"]
        vet_ids = [v["vet_id"] for v in vet_list]
        self.assertIn("vet_officer_01", vet_ids)
        self.assertIn("DEMO_USER_VET_NORTH", vet_ids)

        # 2. Other-district Vets excluded (e.g. vet_officer_02 assigned only to Kurunegala, Puttalam, Gampaha, Kegalle)
        self.assertNotIn("vet_officer_02", vet_ids)

        # 3. Inactive Vet excluded (vet_inactive_01 has assigned_districts ["Anuradhapura"] but active=False)
        self.assertNotIn("vet_inactive_01", vet_ids)

        # 4. Deterministic ordering: display_name ascending, then vet_id
        display_names = [v["display_name"] for v in vet_list]
        self.assertEqual(display_names, sorted(display_names))

        # 5. Empty eligible list returns 200 and [] for a valid Sri Lankan district with no assigned Vets (e.g., Ampara)
        res_empty = client.get(
            "/api/v1/risk-forecasting/follow-up-vets?district=Ampara",
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_empty.status_code, 200)
        empty_data = res_empty.json()
        self.assertEqual(empty_data["district"], "Ampara")
        self.assertEqual(empty_data["total_count"], 0)
        self.assertEqual(empty_data["veterinary_officers"], [])

        # 5b. Canonical district handling for "Nuwara Eliya" and whitespace/casing normalization
        res_nuwara = client.get(
            "/api/v1/risk-forecasting/follow-up-vets?district=nuwara%20eliya",
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_nuwara.status_code, 200)
        self.assertEqual(res_nuwara.json()["district"], "Nuwara Eliya")

        # 6. SYSTEM role explicitly denied (403)
        res_system = client.get(
            "/api/v1/risk-forecasting/follow-up-vets?district=Anuradhapura",
            headers={"X-Actor-ID": "sys_bot", "X-Actor-Role": "SYSTEM"},
        )
        self.assertEqual(res_system.status_code, 403)
        self.assertIn("not authorized", res_system.json()["detail"])

        # 7. Farmer denied (403)
        res_farmer = client.get(
            "/api/v1/risk-forecasting/follow-up-vets?district=Anuradhapura",
            headers={"X-Actor-ID": "farmer_01", "X-Actor-Role": "FARMER"},
        )
        self.assertEqual(res_farmer.status_code, 403)
        self.assertIn("not authorized", res_farmer.json()["detail"])

        # 8. Vet denied (403)
        res_vet = client.get(
            "/api/v1/risk-forecasting/follow-up-vets?district=Anuradhapura",
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        self.assertEqual(res_vet.status_code, 403)
        self.assertIn("not authorized", res_vet.json()["detail"])

        # 8b. Unknown role denied (403)
        res_unknown_role = client.get(
            "/api/v1/risk-forecasting/follow-up-vets?district=Anuradhapura",
            headers={"X-Actor-ID": "user_99", "X-Actor-Role": "UNKNOWN_ROLE"},
        )
        self.assertEqual(res_unknown_role.status_code, 403)
        self.assertIn("not authorized", res_unknown_role.json()["detail"])

        # 9. Missing/blank actor context denied (403)
        res_no_actor = client.get("/api/v1/risk-forecasting/follow-up-vets?district=Anuradhapura")
        self.assertEqual(res_no_actor.status_code, 403)

        res_blank_actor = client.get(
            "/api/v1/risk-forecasting/follow-up-vets?district=Anuradhapura",
            headers={"X-Actor-ID": "   ", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_blank_actor.status_code, 403)

        # 10. District validation: missing district parameter (422) & blank/invalid district (400)
        res_missing_dist = client.get(
            "/api/v1/risk-forecasting/follow-up-vets",
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_missing_dist.status_code, 422)

        res_blank_dist = client.get(
            "/api/v1/risk-forecasting/follow-up-vets?district=%20%20",
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_blank_dist.status_code, 400)

        res_invalid_dist = client.get(
            "/api/v1/risk-forecasting/follow-up-vets?district=InvalidDistrictName",
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_invalid_dist.status_code, 400)

        # 11. No PII/contact/auth fields in response
        for vet in vet_list:
            self.assertNotIn("phone", vet)
            self.assertNotIn("email", vet)
            self.assertNotIn("password", vet)
            self.assertNotIn("token", vet)
            self.assertNotIn("farmer_id", vet)
            self.assertNotIn("stock_quantity", vet)

        # 12. Zero repository side effects
        self.assertEqual(self.follow_up_repo.list()[1], initial_follow_ups_count)

    def test_list_eligible_vets_with_custom_injected_directory(self):
        """Tests that ForecastFollowUpService respects custom injected VeterinaryOfficerDirectory."""
        custom_dir = InMemoryVeterinaryOfficerDirectory()
        custom_dir.add_vet(
            VeterinaryOfficerSummary(
                vet_id="custom_vet_99",
                display_name="Dr. Custom Officer",
                assigned_districts=["Ampara"],
                active=True,
            )
        )
        custom_service = ForecastFollowUpService(
            forecast_service=self.forecast_svc,
            follow_up_repository=self.follow_up_repo,
            vet_directory=custom_dir,
        )

        daph_actor = FollowUpActorContext(actor_id="daph_hq_01", role="DAPH_OFFICIAL")
        res = custom_service.list_eligible_vets(district="Ampara", actor=daph_actor)

        self.assertEqual(res.district, "Ampara")
        self.assertEqual(res.total_count, 1)
        self.assertEqual(res.veterinary_officers[0].vet_id, "custom_vet_99")

    def _issue_sample_follow_up(self):
        daph_actor = FollowUpActorContext(actor_id="daph_hq_01", role="DAPH_OFFICIAL")
        req = CreateFollowUpRequest(
            forecast_id=self.sample_forecast.forecast_id,
            assigned_vet_id="vet_officer_01",
            instruction_summary="Operational follow-up instruction test.",
        )
        rec = self.service.issue_follow_up(req, actor=daph_actor)
        from components.risk_forecasting.services.follow_up_service import forecast_follow_up_service
        forecast_follow_up_service.follow_up_repo.save(rec)
        return rec

    def test_cancellation_allowed_source_states_and_terminal_guards(self):
        """Phase 7A: Proves cancellation succeeds from ISSUED, ACKNOWLEDGED, ACTION_IN_PROGRESS, fails from terminal states."""
        client = TestClient(app)

        # 1. Cancel from ISSUED -> Succeeds (status CANCELLED, version 2)
        rec_issued = self._issue_sample_follow_up()
        res_cancel_issued = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{rec_issued.follow_up_id}/cancel",
            json={"version": 1, "reason": "Operational priority changed"},
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_cancel_issued.status_code, 200)
        self.assertEqual(res_cancel_issued.json()["status"], "CANCELLED")
        self.assertEqual(res_cancel_issued.json()["version"], 2)
        self.assertEqual(res_cancel_issued.json()["cancellation_reason"], "Operational priority changed")
        self.assertIsNotNone(res_cancel_issued.json()["cancelled_at"])

        # 2. Cancel from ACKNOWLEDGED -> Succeeds
        rec_ack = self._issue_sample_follow_up()
        client.post(
            f"/api/v1/risk-forecasting/follow-ups/{rec_ack.follow_up_id}/acknowledge",
            json={"version": 1},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        res_cancel_ack = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{rec_ack.follow_up_id}/cancel",
            json={"version": 2},
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_cancel_ack.status_code, 200)
        self.assertEqual(res_cancel_ack.json()["status"], "CANCELLED")
        self.assertEqual(res_cancel_ack.json()["version"], 3)

        # 3. Cancel from ACTION_IN_PROGRESS -> Succeeds
        rec_prog = self._issue_sample_follow_up()
        client.post(
            f"/api/v1/risk-forecasting/follow-ups/{rec_prog.follow_up_id}/acknowledge",
            json={"version": 1},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        client.post(
            f"/api/v1/risk-forecasting/follow-ups/{rec_prog.follow_up_id}/start",
            json={"version": 2},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        res_cancel_prog = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{rec_prog.follow_up_id}/cancel",
            json={"version": 3},
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_cancel_prog.status_code, 200)
        self.assertEqual(res_cancel_prog.json()["status"], "CANCELLED")
        self.assertEqual(res_cancel_prog.json()["version"], 4)

        # 4. Cancel from COMPLETED -> Fails (409 Conflict)
        rec_comp = self._issue_sample_follow_up()
        client.post(
            f"/api/v1/risk-forecasting/follow-ups/{rec_comp.follow_up_id}/acknowledge",
            json={"version": 1},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        client.post(
            f"/api/v1/risk-forecasting/follow-ups/{rec_comp.follow_up_id}/start",
            json={"version": 2},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        client.post(
            f"/api/v1/risk-forecasting/follow-ups/{rec_comp.follow_up_id}/complete",
            json={"version": 3},
            headers={"X-Actor-ID": "vet_officer_01", "X-Actor-Role": "VETERINARY_OFFICER"},
        )
        res_cancel_comp = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{rec_comp.follow_up_id}/cancel",
            json={"version": 4},
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_cancel_comp.status_code, 409)

        # 5. Re-cancel CANCELLED -> Fails (409 Conflict)
        res_recancel = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{rec_issued.follow_up_id}/cancel",
            json={"version": 2},
            headers={"X-Actor-ID": "daph_hq_01", "X-Actor-Role": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res_recancel.status_code, 409)

    def test_system_role_denied_on_public_http_routes(self):
        """Phase 7A: Proves callers sending X-Actor-Role: SYSTEM receive 403 Forbidden across all public HTTP endpoints."""
        client = TestClient(app)
        rec = self._issue_sample_follow_up()
        fu_id = rec.follow_up_id
        sys_headers = {"X-Actor-ID": "sys_bot", "X-Actor-Role": "SYSTEM"}

        # 1. Cancel
        res_cancel = client.post(f"/api/v1/risk-forecasting/follow-ups/{fu_id}/cancel", json={"version": 1}, headers=sys_headers)
        self.assertEqual(res_cancel.status_code, 403)

        # 2. Issue
        res_issue = client.post(
            "/api/v1/risk-forecasting/follow-ups",
            json={"forecast_id": self.sample_forecast.forecast_id, "assigned_vet_id": "vet_officer_01", "instruction_summary": "Test"},
            headers=sys_headers,
        )
        self.assertEqual(res_issue.status_code, 403)

        # 3. List
        res_list = client.get("/api/v1/risk-forecasting/follow-ups", headers=sys_headers)
        self.assertEqual(res_list.status_code, 403)

        # 4. Get
        res_get = client.get(f"/api/v1/risk-forecasting/follow-ups/{fu_id}", headers=sys_headers)
        self.assertEqual(res_get.status_code, 403)

        # 5. Escalate
        res_esc = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/escalate",
            json={"version": 1, "reason": "Test escalation"},
            headers=sys_headers,
        )
        self.assertEqual(res_esc.status_code, 403)

        # 6. External reference
        res_ext = client.post(
            f"/api/v1/risk-forecasting/follow-ups/{fu_id}/external-resource-reference",
            json={"version": 1, "external_resource_request_id": "req_1"},
            headers=sys_headers,
        )
        self.assertEqual(res_ext.status_code, 403)


if __name__ == "__main__":
    unittest.main()
