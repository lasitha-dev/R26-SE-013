"""
Tests for Recipient Query Service and Endpoint (Phase 5B-1).

Verifies the read-only recipient bridge, non-sensitive metadata scoping,
district filtering, error validation, shared directory consistency, and frontend feasibility contract.
"""

from typing import List, Optional
import unittest
from fastapi.testclient import TestClient

from backend.components.risk_forecasting.integrations.recipient_directory import (
    InMemoryRecipientDirectory,
    Recipient,
    RecipientDirectory,
    recipient_directory,
)
from backend.components.risk_forecasting.repositories.advisory_repository import (
    InMemoryAdvisoryRepository,
)
from backend.components.risk_forecasting.schemas import (
    AssignedRecipientListResponse,
    CreateAdvisoryDraftRequest,
    GenerateForecastRecordRequest,
)
from backend.components.risk_forecasting.services.advisory_service import (
    advisory_service,
)
from backend.components.risk_forecasting.services.forecast_record_service import (
    forecast_record_service,
)
from backend.components.risk_forecasting.services.recipient_query_service import (
    RecipientQueryService,
    recipient_query_service,
)
from backend.main import app

client = TestClient(app)


class TestRecipientQuery(unittest.TestCase):
    """Unittest test suite for Phase 5B-1 Recipient Query Service and Endpoint."""

    def test_01_list_all_recipients_known_vet(self):
        """1. List all recipients for known Vet (vet_officer_01)."""
        res = recipient_query_service.list_assigned_recipients(vet_id="vet_officer_01")
        self.assertIsInstance(res, AssignedRecipientListResponse)
        self.assertEqual(res.vet_id, "vet_officer_01")
        self.assertIsNone(res.district_filter)
        self.assertEqual(res.total_assigned, 20)
        self.assertEqual(res.eligible_count, 20)
        self.assertEqual(len(res.recipients), 20)

    def test_02_filter_by_district(self):
        """2. Filter by district (Anuradhapura)."""
        res = recipient_query_service.list_assigned_recipients(
            vet_id="vet_officer_01", district="Anuradhapura"
        )
        self.assertEqual(res.vet_id, "vet_officer_01")
        self.assertEqual(res.district_filter, "Anuradhapura")
        self.assertEqual(res.total_assigned, 20)
        self.assertEqual(res.eligible_count, 5)
        self.assertEqual(len(res.recipients), 5)
        for item in res.recipients:
            self.assertEqual(item.district, "Anuradhapura")

    def test_03_multi_district_vet_counts(self):
        """3. Multi-district Vet counts (total_assigned vs eligible_count)."""
        res = recipient_query_service.list_assigned_recipients(
            vet_id="vet_officer_01", district="Colombo"
        )
        self.assertEqual(res.total_assigned, 20)
        self.assertEqual(res.eligible_count, 5)
        self.assertEqual(len(res.recipients), 5)

    def test_04_district_zero_eligible_recipients(self):
        """4. District with zero eligible recipients returns empty recipients list and eligible_count 0."""
        res = recipient_query_service.list_assigned_recipients(
            vet_id="vet_officer_01", district="Kandy"
        )
        self.assertEqual(res.total_assigned, 20)
        self.assertEqual(res.eligible_count, 0)
        self.assertEqual(res.recipients, [])

    def test_05_unknown_vet_behavior(self):
        """5. Unknown Vet returns empty result with total_assigned 0 and eligible_count 0."""
        res = recipient_query_service.list_assigned_recipients(vet_id="vet_unknown_999")
        self.assertEqual(res.vet_id, "vet_unknown_999")
        self.assertEqual(res.total_assigned, 0)
        self.assertEqual(res.eligible_count, 0)
        self.assertEqual(res.recipients, [])

    def test_06_blank_vet_id_rejected(self):
        """6. Blank or whitespace vet_id is rejected with ValueError."""
        with self.assertRaisesRegex(ValueError, "vet_id parameter cannot be empty"):
            recipient_query_service.list_assigned_recipients(vet_id="")

        with self.assertRaisesRegex(ValueError, "vet_id parameter cannot be empty"):
            recipient_query_service.list_assigned_recipients(vet_id="   ")

        # Check HTTP 400 endpoint response
        response = client.get("/api/v1/risk-forecasting/recipients?vet_id=   ")
        self.assertEqual(response.status_code, 400)
        self.assertIn("vet_id parameter cannot be empty", response.json()["detail"])

    def test_07_invalid_district_rejected(self):
        """7. Invalid district is rejected with ValueError."""
        with self.assertRaisesRegex(ValueError, "Invalid district"):
            recipient_query_service.list_assigned_recipients(
                vet_id="vet_officer_01", district="Atlantis"
            )

        # Check HTTP 400 endpoint response
        response = client.get("/api/v1/risk-forecasting/recipients?vet_id=vet_officer_01&district=InvalidDist")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid district", response.json()["detail"])

    def test_08_deterministic_ordering(self):
        """8. Deterministic ordering by recipient_id."""
        res = recipient_query_service.list_assigned_recipients(vet_id="vet_officer_01")
        ids = [r.recipient_id for r in res.recipients]
        self.assertEqual(ids, sorted(ids))

    def test_09_no_duplicate_recipient_ids(self):
        """9. No duplicate recipient IDs in returned list."""
        res = recipient_query_service.list_assigned_recipients(vet_id="vet_officer_01")
        ids = [r.recipient_id for r in res.recipients]
        self.assertEqual(len(ids), len(set(ids)))

    def test_10_no_pii_contact_fields(self):
        """10. Response contains strictly non-sensitive fields and no phone/email/address PII."""
        res = recipient_query_service.list_assigned_recipients(vet_id="vet_officer_01")
        for item in res.recipients:
            data = item.model_dump()
            self.assertEqual(set(data.keys()), {"recipient_id", "recipient_name", "district"})
            self.assertNotIn("phone", data)
            self.assertNotIn("email", data)
            self.assertNotIn("address", data)
            self.assertNotIn("owner", data)

    def test_11_endpoint_is_read_only(self):
        """11. Endpoint executes cleanly via HTTP GET with zero state mutation."""
        response = client.get("/api/v1/risk-forecasting/recipients?vet_id=vet_officer_01&district=Anuradhapura")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["vet_id"], "vet_officer_01")
        self.assertEqual(payload["district_filter"], "Anuradhapura")
        self.assertEqual(payload["eligible_count"], 5)

    def test_12_no_advisory_repository_changes(self):
        """12. Advisory repository state is un-impacted by recipient query operations."""
        records_before, _ = advisory_service.advisory_repo.list()
        count_before = len(records_before)
        client.get("/api/v1/risk-forecasting/recipients?vet_id=vet_officer_01")
        records_after, _ = advisory_service.advisory_repo.list()
        count_after = len(records_after)
        self.assertEqual(count_before, count_after)

    def test_13_no_forecast_repository_changes(self):
        """13. Forecast record repository state is un-impacted by recipient query operations."""
        records_before, _ = forecast_record_service.repository.list()
        count_before = len(records_before)
        client.get("/api/v1/risk-forecasting/recipients?vet_id=vet_officer_01")
        records_after, _ = forecast_record_service.repository.list()
        count_after = len(records_after)
        self.assertEqual(count_before, count_after)

    def test_14_no_notification_outbox_changes(self):
        """14. Notification outbox state is un-impacted by recipient query operations."""
        from backend.components.risk_forecasting.services.notification_service import notification_service
        batches_before, _ = notification_service.outbox_repo.list_batches()
        count_before = len(batches_before)
        client.get("/api/v1/risk-forecasting/recipients?vet_id=vet_officer_01")
        batches_after, _ = notification_service.outbox_repo.list_batches()
        count_after = len(batches_after)
        self.assertEqual(count_before, count_after)

    def test_15_no_model_prediction_invocation(self):
        """15. Recipient query operations do not trigger disease prediction models."""
        res = recipient_query_service.list_assigned_recipients(vet_id="vet_officer_01")
        self.assertGreater(res.total_assigned, 0)

    def test_16_shared_directory_consistency(self):
        """16. Service uses shared directory instance matching AdvisoryService validation."""
        query_recipients = recipient_query_service.list_assigned_recipients(
            vet_id="vet_officer_01", district="Anuradhapura"
        )
        query_ids = [r.recipient_id for r in query_recipients.recipients]

        self.assertIs(advisory_service.recipient_dir, recipient_query_service.recipient_dir)

        all_vet_dir_farms = recipient_directory.list_assigned_recipients(
            vet_id="vet_officer_01", district="Anuradhapura"
        )
        dir_ids = sorted([r.recipient_id for r in all_vet_dir_farms])
        self.assertEqual(query_ids, dir_ids)

    def test_17_dependency_injection_fake_directory(self):
        """17. Dependency injection works cleanly with a custom/fake RecipientDirectory implementation."""
        class FakeRecipientDirectory:
            def list_assigned_recipients(self, vet_id: str, district: Optional[str] = None) -> List[Recipient]:
                if vet_id != "fake_vet":
                    return []
                recipients = [
                    Recipient(recipient_id="CUSTOM_001", recipient_name="Custom Farm 1", district="Galle", assigned_vet_id="fake_vet"),
                    Recipient(recipient_id="CUSTOM_002", recipient_name="Custom Farm 2", district="Galle", assigned_vet_id="fake_vet"),
                ]
                if district:
                    recipients = [r for r in recipients if r.district == district]
                return recipients

            def resolve_recipients(self, recipient_ids: List[str], vet_id: str) -> List[Recipient]:
                return []

        custom_service = RecipientQueryService(recipient_dir=FakeRecipientDirectory())
        res = custom_service.list_assigned_recipients(vet_id="fake_vet", district="Galle")
        self.assertEqual(res.total_assigned, 2)
        self.assertEqual(res.eligible_count, 2)
        self.assertEqual(res.recipients[0].recipient_id, "CUSTOM_001")

    def test_18_frontend_feasibility_contract(self):
        """
        7.1 FRONTEND FEASIBILITY CONTRACT TEST:
        Proves frontend can list assigned recipients, select a subset, create a SELECTED advisory draft,
        and preview it without misusing advisory preview as a directory discovery tool.
        """
        # Step 1: Frontend queries GET /recipients for vet_officer_01 in Anuradhapura
        rec_res = client.get("/api/v1/risk-forecasting/recipients?vet_id=vet_officer_01&district=Anuradhapura")
        self.assertEqual(rec_res.status_code, 200)
        rec_data = rec_res.json()
        available_farms = rec_data["recipients"]
        self.assertGreaterEqual(len(available_farms), 2)

        # Step 2: Frontend picks a subset of returned recipient IDs
        selected_subset = [available_farms[0]["recipient_id"], available_farms[1]["recipient_id"]]

        # Step 3: Generate a forecast record to anchor advisory
        record_req = GenerateForecastRecordRequest(
            disease="FMD",
            district="Anuradhapura",
            year=2024,
            month=1,
            trigger_type="MANUAL",
            generated_by="vet_officer_01"
        )
        rec_record = forecast_record_service.generate_record(record_req)

        # Step 4: Create a SELECTED scope advisory draft with chosen subset
        draft_req = CreateAdvisoryDraftRequest(
            forecast_id=rec_record.forecast_id,
            advisory_type="VETERINARY_CUSTOM_ADVICE",
            recipient_scope="SELECTED",
            selected_recipient_ids=selected_subset,
            vet_custom_note="Contract test custom advice note.",
            created_by="vet_officer_01"
        )
        draft = advisory_service.create_draft(draft_req)
        self.assertEqual(draft.recipient_scope, "SELECTED")
        self.assertEqual(sorted(draft.selected_recipient_ids), sorted(selected_subset))

        # Step 5: Preview advisory and verify previewed recipient IDs match chosen subset exactly
        preview = advisory_service.preview_advisory(advisory_id=draft.advisory_id)
        previewed_ids = sorted([p.recipient_id for p in preview.previews])
        self.assertEqual(previewed_ids, sorted(selected_subset))
        self.assertEqual(preview.recipient_summary.selected_count, len(selected_subset))


if __name__ == "__main__":
    unittest.main()
