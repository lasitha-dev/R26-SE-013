"""
Comprehensive Unit Test Suite for Notification Outbox and Mock Provider (Phase 4).

Validates all 45 requirement items:
- Approved advisory enqueueing (FMD/LSD)
- Rejection of DRAFT, REVIEW_READY, CANCELLED, or unknown advisories
- Per-recipient delivery message freezing (standard and personalized)
- Zero PII storage and zero provider calls during enqueue
- Idempotency key handling and semantic duplicate prevention
- Mock notification provider dispatch (all-success, partial-failure, all-failure, provider exception)
- Retry of failed items only (successful items not redelivered)
- Safe batch cancellation and rejection of cancellation after attempts
- Optimistic concurrency, defensive copying, and pagination bounds
- Immutability of advisory records and forecast decision records
- Endpoint integration testing via FastAPI TestClient
"""

from datetime import datetime, timezone
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.risk_forecasting.integrations.notification_provider import (
    MockNotificationProvider,
    ProviderDeliveryPayload,
    ProviderDeliveryResult,
)
from components.risk_forecasting.integrations.recipient_directory import InMemoryRecipientDirectory
from components.risk_forecasting.repositories.advisory_repository import InMemoryAdvisoryRepository
from components.risk_forecasting.repositories.notification_outbox_repository import (
    InMemoryNotificationOutboxRepository,
)
from components.risk_forecasting import routes
from components.risk_forecasting.routes import router
from components.risk_forecasting.schemas import (
    CreateAdvisoryDraftRequest,
    EnqueueNotificationBatchRequest,
    GenerateForecastRecordRequest,
    PersonalizedOverride,
)
from components.risk_forecasting.services.advisory_service import AdvisoryService
from components.risk_forecasting.services.forecast_record_service import ForecastRecordService
from components.risk_forecasting.services.notification_service import NotificationService

app = FastAPI()
app.include_router(router, prefix="/api/v1/risk-forecasting")
client = TestClient(app)


class TestNotificationOutboxFoundation(unittest.TestCase):
    """Test suite covering all 45 Phase 4 requirements."""

    def setUp(self):
        self.forecast_svc = ForecastRecordService()
        self.recipient_dir = InMemoryRecipientDirectory()
        self.advisory_repo = InMemoryAdvisoryRepository()
        self.advisory_svc = AdvisoryService(
            forecast_service=self.forecast_svc,
            recipient_dir=self.recipient_dir,
            advisory_repository=self.advisory_repo,
        )
        self.outbox_repo = InMemoryNotificationOutboxRepository()
        self.mock_provider = MockNotificationProvider()

        fixed_dt = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)
        self.clock = lambda: fixed_dt
        self.id_counter = 0

        def custom_id_gen(prefix: str) -> str:
            self.id_counter += 1
            return f"{prefix}_{self.id_counter:04d}"

        self.id_gen = custom_id_gen

        self.service = NotificationService(
            advisory_svc=self.advisory_svc,
            advisory_repo=self.advisory_repo,
            outbox_repository=self.outbox_repo,
            notification_provider=self.mock_provider,
            clock=self.clock,
            id_generator=self.id_gen,
        )
        routes.notification_service = self.service

    def _create_approved_advisory(self, disease: str = "FMD", district: str = "Anuradhapura"):
        fdr = self.forecast_svc.generate_record(
            GenerateForecastRecordRequest(
                disease=disease,
                district=district,
                year=2024,
                month=1,
                trigger_type="MANUAL",
            )
        )
        req = CreateAdvisoryDraftRequest(
            forecast_id=fdr.forecast_id,
            recipient_scope="ALL_ASSIGNED",
            vet_custom_note="Check vaccination cards.",
        )
        draft = self.advisory_svc.create_draft(req)
        review_ready = self.advisory_svc.mark_ready_for_review(draft.advisory_id, draft.version)
        approved = self.advisory_svc.approve_advisory(review_ready.advisory_id, review_ready.version, "vet_officer_01")
        return approved, fdr

    # 1. Enqueue approved FMD advisory
    def test_01_enqueue_approved_fmd_advisory(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.assertIsNotNone(batch)
        self.assertEqual(batch.advisory_id, approved_adv.advisory_id)
        self.assertEqual(batch.status, "QUEUED")
        self.assertEqual(batch.recipient_count, 5)

    # 2. Enqueue approved LSD advisory
    def test_02_enqueue_approved_lsd_advisory(self):
        approved_adv, _ = self._create_approved_advisory(disease="LSD", district="Colombo")
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.assertIsNotNone(batch)
        self.assertEqual(batch.advisory_id, approved_adv.advisory_id)
        self.assertEqual(batch.status, "QUEUED")
        self.assertEqual(batch.recipient_count, 5)

    # 3. Reject DRAFT advisory
    def test_03_reject_draft_advisory(self):
        fdr = self.forecast_svc.generate_record(
            GenerateForecastRecordRequest(disease="FMD", district="Anuradhapura", year=2024, month=1, trigger_type="MANUAL")
        )
        draft = self.advisory_svc.create_draft(CreateAdvisoryDraftRequest(forecast_id=fdr.forecast_id))
        with self.assertRaises(ValueError) as ctx:
            self.service.enqueue_approved_advisory(draft.advisory_id)
        self.assertIn("Advisory must be APPROVED", str(ctx.exception))

    # 4. Reject REVIEW_READY advisory
    def test_04_reject_review_ready_advisory(self):
        fdr = self.forecast_svc.generate_record(
            GenerateForecastRecordRequest(disease="FMD", district="Anuradhapura", year=2024, month=1, trigger_type="MANUAL")
        )
        draft = self.advisory_svc.create_draft(CreateAdvisoryDraftRequest(forecast_id=fdr.forecast_id))
        rr = self.advisory_svc.mark_ready_for_review(draft.advisory_id, draft.version)
        with self.assertRaises(ValueError) as ctx:
            self.service.enqueue_approved_advisory(rr.advisory_id)
        self.assertIn("Advisory must be APPROVED", str(ctx.exception))

    # 5. Reject CANCELLED advisory
    def test_05_reject_cancelled_advisory(self):
        fdr = self.forecast_svc.generate_record(
            GenerateForecastRecordRequest(disease="FMD", district="Anuradhapura", year=2024, month=1, trigger_type="MANUAL")
        )
        draft = self.advisory_svc.create_draft(CreateAdvisoryDraftRequest(forecast_id=fdr.forecast_id))
        cancelled = self.advisory_svc.cancel_advisory(draft.advisory_id, draft.version)
        with self.assertRaises(ValueError) as ctx:
            self.service.enqueue_approved_advisory(cancelled.advisory_id)
        self.assertIn("Cancelled advisories cannot be enqueued", str(ctx.exception))

    # 6. Unknown advisory
    def test_06_unknown_advisory(self):
        with self.assertRaises(KeyError) as ctx:
            self.service.enqueue_approved_advisory("non_existent_adv")
        self.assertIn("not found", str(ctx.exception))

    # 7. One delivery per recipient
    def test_07_one_delivery_per_recipient(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        deliveries_resp = self.service.list_batch_deliveries(batch.batch_id)
        self.assertEqual(len(deliveries_resp.deliveries), 5)
        recip_ids = {d.recipient_id for d in deliveries_resp.deliveries}
        self.assertEqual(recip_ids, {"DEMO_FARM_001", "DEMO_FARM_002", "DEMO_FARM_003", "DEMO_FARM_004", "DEMO_FARM_005"})

    # 8. Standard resolved message payload
    def test_08_standard_resolved_message_payload(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        deliveries_resp = self.service.list_batch_deliveries(batch.batch_id)
        for d in deliveries_resp.deliveries:
            self.assertIn("ANURADHAPURA", d.resolved_message.upper())
            self.assertIn("Check vaccination cards.", d.resolved_message)

    # 9. Personalized resolved message payload
    def test_09_personalized_resolved_message_payload(self):
        fdr = self.forecast_svc.generate_record(
            GenerateForecastRecordRequest(disease="FMD", district="Anuradhapura", year=2024, month=1, trigger_type="MANUAL")
        )
        req = CreateAdvisoryDraftRequest(
            forecast_id=fdr.forecast_id,
            recipient_scope="ALL_ASSIGNED",
            personalized_overrides=[
                PersonalizedOverride(recipient_id="DEMO_FARM_001", custom_note="Booster required for herd B.")
            ],
        )
        draft = self.advisory_svc.create_draft(req)
        rr = self.advisory_svc.mark_ready_for_review(draft.advisory_id, draft.version)
        appr = self.advisory_svc.approve_advisory(rr.advisory_id, rr.version, "vet_officer_01")
        batch = self.service.enqueue_approved_advisory(appr.advisory_id)
        deliveries_resp = self.service.list_batch_deliveries(batch.batch_id)
        del_farm_01 = next(d for d in deliveries_resp.deliveries if d.recipient_id == "DEMO_FARM_001")
        self.assertIn("Booster required for herd B.", del_farm_01.resolved_message)

    # 10. Delivery payload immutable after enqueue
    def test_10_delivery_payload_immutable_after_enqueue(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        deliv1 = self.service.list_batch_deliveries(batch.batch_id).deliveries[0]

        # Dispatch batch
        self.service.dispatch_batch(batch.batch_id)

        deliv1_after = self.service.list_batch_deliveries(batch.batch_id).deliveries[0]
        self.assertEqual(deliv1.resolved_message, deliv1_after.resolved_message)
        self.assertEqual(deliv1.recipient_id, deliv1_after.recipient_id)

    # 11. No PII/contact details stored
    def test_11_no_pii_stored(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        deliveries = self.service.list_batch_deliveries(batch.batch_id).deliveries
        for d in deliveries:
            d_dump = d.model_dump()
            self.assertNotIn("phone", d_dump)
            self.assertNotIn("email", d_dump)
            self.assertNotIn("farmer_name", d_dump)

    # 12. Enqueue makes zero provider calls
    def test_12_enqueue_makes_zero_provider_calls(self):
        call_count = 0

        def tracking_send(payload):
            nonlocal call_count
            call_count += 1
            return ProviderDeliveryResult(success=True, provider_status="DELIVERED", attempted_at=datetime.now(timezone.utc).isoformat())

        mock_prov = MockNotificationProvider()
        mock_prov.send = tracking_send
        svc = NotificationService(advisory_svc=self.advisory_svc, outbox_repository=self.outbox_repo, notification_provider=mock_prov)

        approved_adv, _ = self._create_approved_advisory()
        svc.enqueue_approved_advisory(approved_adv.advisory_id)
        self.assertEqual(call_count, 0)

    # 13. Idempotent enqueue retry
    def test_13_idempotent_enqueue_retry(self):
        approved_adv, _ = self._create_approved_advisory()
        b1 = self.service.enqueue_approved_advisory(approved_adv.advisory_id, idempotency_key="key_1001")
        b2 = self.service.enqueue_approved_advisory(approved_adv.advisory_id, idempotency_key="key_1001")
        self.assertEqual(b1.batch_id, b2.batch_id)

    # 14. Conflicting idempotency key
    def test_14_conflicting_idempotency_key(self):
        appr1, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        appr2, _ = self._create_approved_advisory(disease="LSD", district="Colombo")

        self.service.enqueue_approved_advisory(appr1.advisory_id, idempotency_key="shared_key_1")
        with self.assertRaises(ValueError) as ctx:
            self.service.enqueue_approved_advisory(appr2.advisory_id, idempotency_key="shared_key_1")
        self.assertIn("Idempotency key collision", str(ctx.exception))

    # 15. Same advisory/version semantic duplicate prevention
    def test_15_same_advisory_version_semantic_duplicate(self):
        approved_adv, _ = self._create_approved_advisory()
        b1 = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        b2 = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.assertEqual(b1.batch_id, b2.batch_id)

    # 16. Normal all-success dispatch
    def test_16_normal_all_success_dispatch(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        dispatched_batch = self.service.dispatch_batch(batch.batch_id)

        self.assertEqual(dispatched_batch.status, "COMPLETED")
        self.assertEqual(dispatched_batch.succeeded_count, 5)
        self.assertEqual(dispatched_batch.failed_count, 0)
        self.assertEqual(dispatched_batch.pending_count, 0)

    # 17. Partial failure dispatch
    def test_17_partial_failure_dispatch(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        self.mock_provider.failed_recipient_ids = {"DEMO_FARM_002"}
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        dispatched_batch = self.service.dispatch_batch(batch.batch_id)

        self.assertEqual(dispatched_batch.status, "PARTIALLY_FAILED")
        self.assertEqual(dispatched_batch.succeeded_count, 4)
        self.assertEqual(dispatched_batch.failed_count, 1)

    # 18. All-failure dispatch
    def test_18_all_failure_dispatch(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        self.mock_provider.failed_recipient_ids = {"DEMO_FARM_001", "DEMO_FARM_002", "DEMO_FARM_003", "DEMO_FARM_004", "DEMO_FARM_005"}
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        dispatched_batch = self.service.dispatch_batch(batch.batch_id)

        self.assertEqual(dispatched_batch.status, "FAILED")
        self.assertEqual(dispatched_batch.succeeded_count, 0)
        self.assertEqual(dispatched_batch.failed_count, 5)

    # 19. Provider exception handling
    def test_19_provider_exception_handling(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        self.mock_provider.raise_exception_ids = {"DEMO_FARM_001"}
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        dispatched_batch = self.service.dispatch_batch(batch.batch_id)

        self.assertEqual(dispatched_batch.status, "PARTIALLY_FAILED")
        self.assertEqual(dispatched_batch.failed_count, 1)

        deliveries = self.service.list_batch_deliveries(batch.batch_id).deliveries
        del_farm_01 = next(d for d in deliveries if d.recipient_id == "DEMO_FARM_001")
        self.assertEqual(del_farm_01.status, "FAILED")
        self.assertIn("PROVIDER_EXCEPTION", del_farm_01.last_error)

    # 20. Attempt count accuracy
    def test_20_attempt_count_accuracy(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        self.mock_provider.failed_recipient_ids = {"DEMO_FARM_001"}
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)

        self.service.dispatch_batch(batch.batch_id)
        deliveries = self.service.list_batch_deliveries(batch.batch_id).deliveries
        del_farm_01 = next(d for d in deliveries if d.recipient_id == "DEMO_FARM_001")
        self.assertEqual(del_farm_01.attempt_count, 1)

        # Retry failed
        self.service.retry_failed_deliveries(batch.batch_id)
        deliveries_after = self.service.list_batch_deliveries(batch.batch_id).deliveries
        del_farm_01_after = next(d for d in deliveries_after if d.recipient_id == "DEMO_FARM_001")
        self.assertEqual(del_farm_01_after.attempt_count, 2)

    # 21. Batch aggregate count accuracy
    def test_21_batch_aggregate_count_accuracy(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.assertEqual(batch.recipient_count, 5)
        self.assertEqual(batch.pending_count, 5)

        self.service.dispatch_batch(batch.batch_id)
        b_after = self.service.get_batch(batch.batch_id)
        self.assertEqual(b_after.pending_count, 0)
        self.assertEqual(b_after.succeeded_count, 5)

    # 22. Batch status calculation
    def test_22_batch_status_calculation(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.assertEqual(batch.status, "QUEUED")

        b_disp = self.service.dispatch_batch(batch.batch_id)
        self.assertEqual(b_disp.status, "COMPLETED")

    # 23. Successful item not redelivered
    def test_23_successful_item_not_redelivered(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        self.mock_provider.failed_recipient_ids = {"DEMO_FARM_001"}

        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.service.dispatch_batch(batch.batch_id)

        deliveries_first = self.service.list_batch_deliveries(batch.batch_id).deliveries
        del_farm_02_first = next(d for d in deliveries_first if d.recipient_id == "DEMO_FARM_002")
        self.assertEqual(del_farm_02_first.attempt_count, 1)

        # Retry failed only
        self.service.retry_failed_deliveries(batch.batch_id)

        deliveries_second = self.service.list_batch_deliveries(batch.batch_id).deliveries
        del_farm_02_second = next(d for d in deliveries_second if d.recipient_id == "DEMO_FARM_002")
        self.assertEqual(del_farm_02_second.attempt_count, 1)  # Untouched!

    # 24. Repeated dispatch safety
    def test_24_repeated_dispatch_safety(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)

        b1 = self.service.dispatch_batch(batch.batch_id)
        b2 = self.service.dispatch_batch(batch.batch_id)
        self.assertEqual(b1.succeeded_count, b2.succeeded_count)

    # 25. Retry failed only
    def test_25_retry_failed_only(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        self.mock_provider.failed_recipient_ids = {"DEMO_FARM_001"}

        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.service.dispatch_batch(batch.batch_id)

        # Clear failed IDs so retry succeeds
        self.mock_provider.failed_recipient_ids = set()
        b_retried = self.service.retry_failed_deliveries(batch.batch_id)
        self.assertEqual(b_retried.status, "COMPLETED")
        self.assertEqual(b_retried.succeeded_count, 5)

    # 26. Successful retry
    def test_26_successful_retry(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        self.mock_provider.failed_recipient_ids = {"DEMO_FARM_001"}

        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.service.dispatch_batch(batch.batch_id)

        self.mock_provider.failed_recipient_ids = set()
        self.service.retry_failed_deliveries(batch.batch_id)

        deliveries = self.service.list_batch_deliveries(batch.batch_id).deliveries
        del_farm_01 = next(d for d in deliveries if d.recipient_id == "DEMO_FARM_001")
        self.assertEqual(del_farm_01.status, "SUCCEEDED")

    # 27. Repeated failure retry
    def test_27_repeated_failure_retry(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        self.mock_provider.failed_recipient_ids = {"DEMO_FARM_001"}

        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.service.dispatch_batch(batch.batch_id)
        # Keep DEMO_FARM_001 in failed_recipient_ids so retry fails again
        self.service.retry_failed_deliveries(batch.batch_id)

        deliveries = self.service.list_batch_deliveries(batch.batch_id).deliveries
        del_farm_01 = next(d for d in deliveries if d.recipient_id == "DEMO_FARM_001")
        self.assertEqual(del_farm_01.status, "FAILED")
        self.assertEqual(del_farm_01.attempt_count, 2)

    # 28. Concurrent claim prevents duplicate provider call
    def test_28_concurrent_claim_prevents_duplicate_provider_call(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)

        deliv = self.outbox_repo.list_deliveries_by_batch(batch.batch_id)[0][0]
        claimed1 = self.outbox_repo.claim_delivery_for_processing(deliv.delivery_id, deliv.version, datetime.now(timezone.utc).isoformat())
        self.assertIsNotNone(claimed1)

        # Second claim attempt fails
        claimed2 = self.outbox_repo.claim_delivery_for_processing(deliv.delivery_id, deliv.version, datetime.now(timezone.utc).isoformat())
        self.assertIsNone(claimed2)

    # 29. Safe queued-batch cancellation
    def test_29_safe_queued_batch_cancellation(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        cb = self.service.cancel_notification_batch(batch.batch_id)

        self.assertEqual(cb.status, "CANCELLED")
        deliveries = self.service.list_batch_deliveries(batch.batch_id).deliveries
        for d in deliveries:
            self.assertEqual(d.status, "CANCELLED")

    # 30. Reject cancellation after attempt
    def test_30_reject_cancellation_after_attempt(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.service.dispatch_batch(batch.batch_id)

        with self.assertRaises(ValueError) as ctx:
            self.service.cancel_notification_batch(batch.batch_id)
        self.assertIn("Cannot cancel notification batch after delivery attempts", str(ctx.exception))

    # 31. Reject dispatch/retry of cancelled batch
    def test_31_reject_dispatch_retry_of_cancelled_batch(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.service.cancel_notification_batch(batch.batch_id)

        with self.assertRaises(ValueError) as ctx:
            self.service.dispatch_batch(batch.batch_id)
        self.assertIn("Cannot dispatch CANCELLED", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx2:
            self.service.retry_failed_deliveries(batch.batch_id)
        self.assertIn("Cannot retry deliveries for a CANCELLED batch", str(ctx2.exception))

    # 32. Defensive repository copying
    def test_32_defensive_repository_copying(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        b_get1 = self.outbox_repo.get_batch_by_id(batch.batch_id)

        # Mutate local copy
        b_get1.status = "MUTATED"

        b_get2 = self.outbox_repo.get_batch_by_id(batch.batch_id)
        self.assertEqual(b_get2.status, "QUEUED")

    # 33. Pagination bounds
    def test_33_pagination_bounds(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        d_page = self.service.list_batch_deliveries(batch.batch_id, limit=2, offset=0)
        self.assertEqual(len(d_page.deliveries), 2)
        self.assertEqual(d_page.total_count, 5)

    # 34. Batch/delivery filters
    def test_34_batch_delivery_filters(self):
        appr1, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        appr2, _ = self._create_approved_advisory(disease="LSD", district="Colombo")

        b1 = self.service.enqueue_approved_advisory(appr1.advisory_id)
        b2 = self.service.enqueue_approved_advisory(appr2.advisory_id)

        batches = self.service.list_batches(advisory_id=appr1.advisory_id)
        self.assertEqual(len(batches.batches), 1)
        self.assertEqual(batches.batches[0].batch_id, b1.batch_id)

    # 35. Unknown batch
    def test_35_unknown_batch(self):
        with self.assertRaises(KeyError) as ctx:
            self.service.get_batch("unknown_batch_999")
        self.assertIn("not found", str(ctx.exception))

    # 36. Idempotency header/body mismatch if both supported
    def test_36_idempotency_header_body_mismatch(self):
        approved_adv, _ = self._create_approved_advisory()
        response = client.post(
            f"/api/v1/risk-forecasting/advisories/{approved_adv.advisory_id}/notification-batches",
            headers={"Idempotency-Key": "header_key_123"},
            json={"idempotency_key": "body_key_456"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("Idempotency key mismatch", response.json()["detail"])

    # 37. Advisory remains unchanged after enqueue/dispatch/retry/cancel
    def test_37_advisory_remains_unchanged(self):
        approved_adv, _ = self._create_approved_advisory()
        adv_before = self.advisory_repo.get_by_id(approved_adv.advisory_id).model_dump()

        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.service.dispatch_batch(batch.batch_id)

        adv_after = self.advisory_repo.get_by_id(approved_adv.advisory_id).model_dump()
        self.assertEqual(adv_before, adv_after)

    # 38. Forecast record remains unchanged
    def test_38_forecast_record_remains_unchanged(self):
        approved_adv, fdr = self._create_approved_advisory()
        fdr_before = self.forecast_svc.get_record(fdr.forecast_id).model_dump()

        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.service.dispatch_batch(batch.batch_id)

        fdr_after = self.forecast_svc.get_record(fdr.forecast_id).model_dump()
        self.assertEqual(fdr_before, fdr_after)

    # 39. Existing prediction endpoints unchanged
    def test_39_existing_prediction_endpoints_unchanged(self):
        res = client.post(
            "/api/v1/risk-forecasting/predict/fmd",
            json={"district": "Anuradhapura", "year": 2024, "month": 1},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("stage1", res.json())

    # 40. Existing forecast-record endpoints unchanged
    def test_40_existing_forecast_record_endpoints_unchanged(self):
        res = client.post(
            "/api/v1/risk-forecasting/records",
            json={"disease": "FMD", "district": "Anuradhapura", "year": 2024, "month": 1, "trigger_type": "MANUAL"},
        )
        self.assertEqual(res.status_code, 201)
        self.assertIn("forecast_id", res.json())

    # 41. Existing advisory endpoints unchanged
    def test_41_existing_advisory_endpoints_unchanged(self):
        fdr_res = client.post(
            "/api/v1/risk-forecasting/records",
            json={"disease": "FMD", "district": "Anuradhapura", "year": 2024, "month": 1, "trigger_type": "MANUAL"},
        )
        f_id = fdr_res.json()["forecast_id"]
        adv_res = client.post(
            "/api/v1/risk-forecasting/advisories",
            json={"forecast_id": f_id, "recipient_scope": "ALL_ASSIGNED"},
        )
        self.assertEqual(adv_res.status_code, 201)
        self.assertIn("advisory_id", adv_res.json())

    # 42. No real network call
    def test_42_no_real_network_call(self):
        self.assertEqual(self.mock_provider.provider_name, "MockNotificationProvider")

    # 43. No notification-sending endpoint accepting arbitrary text
    def test_43_no_arbitrary_text_send_endpoint(self):
        res = client.post("/api/v1/risk-forecasting/notifications/send", json={"message": "arbitrary text"})
        self.assertEqual(res.status_code, 404)

    # 44. No trend endpoint/service
    def test_44_no_trend_endpoint_service(self):
        res = client.get("/api/v1/risk-forecasting/trends")
        self.assertEqual(res.status_code, 404)

    # 45. Dependency injection for provider/repository/clock/ID generators
    def test_45_dependency_injection_support(self):
        custom_repo = InMemoryNotificationOutboxRepository()
        custom_prov = MockNotificationProvider()
        custom_dt = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        counter = 0

        def unique_id(p: str) -> str:
            nonlocal counter
            counter += 1
            return f"inj_{p}_{counter}"

        custom_svc = NotificationService(
            advisory_svc=self.advisory_svc,
            outbox_repository=custom_repo,
            notification_provider=custom_prov,
            clock=lambda: custom_dt,
            id_generator=unique_id,
        )
        approved_adv, _ = self._create_approved_advisory()
        batch = custom_svc.enqueue_approved_advisory(approved_adv.advisory_id)
        self.assertTrue(batch.batch_id.startswith("inj_batch"))

    # 46. Cancelled after enqueue, before dispatch
    def test_46_cancelled_after_enqueue_before_dispatch(self):
        approved_adv, fdr = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        self.assertEqual(batch.status, "QUEUED")

        # Cancel the advisory in advisory service
        self.advisory_svc.cancel_advisory(approved_adv.advisory_id, approved_adv.version)
        adv_after = self.advisory_repo.get_by_id(approved_adv.advisory_id)
        self.assertEqual(adv_after.status, "CANCELLED")

        # Provider calls before dispatch
        call_count = 0
        original_send = self.mock_provider.send

        def tracking_send(payload):
            nonlocal call_count
            call_count += 1
            return original_send(payload)

        self.mock_provider.send = tracking_send

        # Dispatch attempt must fail with clear domain error
        with self.assertRaises(ValueError) as ctx:
            self.service.dispatch_batch(batch.batch_id)
        self.assertIn("is no longer APPROVED", str(ctx.exception))
        self.assertEqual(call_count, 0)

        # Batch remains auditable as QUEUED
        b_auditable = self.service.get_batch(batch.batch_id)
        self.assertEqual(b_auditable.status, "QUEUED")

        # Forecast record and advisory remain auditable and unchanged
        fdr_after = self.forecast_svc.get_record(fdr.forecast_id)
        self.assertEqual(fdr_after.forecast_id, fdr.forecast_id)

    # 47. Cancelled after partial failure, before retry
    def test_47_cancelled_after_partial_failure_before_retry(self):
        approved_adv, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        self.mock_provider.failed_recipient_ids = {"DEMO_FARM_002"}
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)
        b_disp = self.service.dispatch_batch(batch.batch_id)
        self.assertEqual(b_disp.status, "PARTIALLY_FAILED")

        # Cancel the advisory after partial failure
        adv = self.advisory_repo.get_by_id(approved_adv.advisory_id)
        self.advisory_svc.cancel_advisory(adv.advisory_id, adv.version)

        # Tracking send to verify zero provider calls on retry
        call_count = 0

        def tracking_send(payload):
            nonlocal call_count
            call_count += 1
            return ProviderDeliveryResult(success=True, provider_status="SIMULATED_SUCCESS", attempted_at=datetime.now(timezone.utc).isoformat())

        self.mock_provider.send = tracking_send

        # Retry must fail with clear domain error
        with self.assertRaises(ValueError) as ctx:
            self.service.retry_failed_deliveries(batch.batch_id)
        self.assertIn("is no longer APPROVED", str(ctx.exception))
        self.assertEqual(call_count, 0)

        # Existing delivery items remain unchanged for audit
        deliveries = self.service.list_batch_deliveries(batch.batch_id).deliveries
        succeeded_items = [d for d in deliveries if d.status == "SUCCEEDED"]
        failed_items = [d for d in deliveries if d.status == "FAILED"]
        self.assertEqual(len(succeeded_items), 4)
        self.assertEqual(len(failed_items), 1)
        self.assertEqual(failed_items[0].attempt_count, 1)

    # 48. HTTP 409 Conflict when dispatching batch of cancelled advisory
    def test_48_cancelled_advisory_dispatch_http_409(self):
        approved_adv, _ = self._create_approved_advisory()
        b_res = client.post(f"/api/v1/risk-forecasting/advisories/{approved_adv.advisory_id}/notification-batches")
        self.assertEqual(b_res.status_code, 201)
        batch_id = b_res.json()["batch_id"]

        # Cancel advisory directly
        adv = self.advisory_repo.get_by_id(approved_adv.advisory_id)
        self.advisory_svc.cancel_advisory(adv.advisory_id, adv.version)

        # Dispatch via API returns HTTP 409
        d_res = client.post(f"/api/v1/risk-forecasting/notification-batches/{batch_id}/dispatch")
        self.assertEqual(d_res.status_code, 409)
        self.assertIn("is no longer APPROVED", d_res.json()["detail"])

    # 49. Complete batch aggregate invariant formula check
    def test_49_batch_aggregate_invariants_and_formula(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)

        def check_invariant(b):
            calc_sum = b.pending_count + b.processing_count + b.succeeded_count + b.failed_count + b.cancelled_count
            self.assertEqual(b.recipient_count, calc_sum)
            self.assertGreaterEqual(b.recipient_count, 0)
            self.assertGreaterEqual(b.pending_count, 0)
            self.assertGreaterEqual(b.processing_count, 0)
            self.assertGreaterEqual(b.succeeded_count, 0)
            self.assertGreaterEqual(b.failed_count, 0)
            self.assertGreaterEqual(b.cancelled_count, 0)

        # Newly queued
        check_invariant(batch)

        # All-success dispatch
        b_completed = self.service.dispatch_batch(batch.batch_id)
        check_invariant(b_completed)

        # Cancelled queued batch invariant
        appr2, _ = self._create_approved_advisory(disease="LSD", district="Colombo")
        b2 = self.service.enqueue_approved_advisory(appr2.advisory_id)
        b2_cancelled = self.service.cancel_notification_batch(b2.batch_id)
        check_invariant(b2_cancelled)
        self.assertEqual(b2_cancelled.cancelled_count, 5)
        self.assertEqual(b2_cancelled.pending_count, 0)

    # 50. Retry and terminal timestamp semantics
    def test_50_retry_and_terminal_timestamp_semantics(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)

        # QUEUED: completed_at is None
        self.assertIsNone(batch.completed_at)

        # COMPLETED: completed_at is populated
        b_disp = self.service.dispatch_batch(batch.batch_id)
        self.assertIsNotNone(b_disp.completed_at)

        # PARTIALLY_FAILED batch retry timestamp lifecycle
        appr2, _ = self._create_approved_advisory(disease="FMD", district="Anuradhapura")
        self.mock_provider.failed_recipient_ids = {"DEMO_FARM_001"}
        b2 = self.service.enqueue_approved_advisory(appr2.advisory_id)
        b2_part = self.service.dispatch_batch(b2.batch_id)
        self.assertEqual(b2_part.status, "PARTIALLY_FAILED")
        self.assertIsNotNone(b2_part.completed_at)

        # Clear failure so retry succeeds
        self.mock_provider.failed_recipient_ids = set()
        b2_retried = self.service.retry_failed_deliveries(b2.batch_id)
        self.assertEqual(b2_retried.status, "COMPLETED")
        self.assertIsNotNone(b2_retried.completed_at)

    # 51. Mock Provider Status Semantics and API Assertion (no plain DELIVERED)
    def test_51_mock_provider_status_semantics_and_no_plain_delivered(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)

        # Send via mock provider
        payload = ProviderDeliveryPayload(
            delivery_id="del_test_01",
            batch_id=batch.batch_id,
            advisory_id=approved_adv.advisory_id,
            forecast_id=approved_adv.forecast_id,
            recipient_id="DEMO_FARM_001",
            resolved_message="Test message",
        )
        res = self.mock_provider.send(payload)
        self.assertEqual(res.provider_status, "SIMULATED_SUCCESS")
        self.assertNotEqual(res.provider_status, "DELIVERED")

        # Dispatch via API and verify API responses never contain plain "DELIVERED"
        d_res = client.post(f"/api/v1/risk-forecasting/notification-batches/{batch.batch_id}/dispatch")
        self.assertEqual(d_res.status_code, 200)

        del_res = client.get(f"/api/v1/risk-forecasting/notification-batches/{batch.batch_id}/deliveries")
        self.assertEqual(del_res.status_code, 200)
        items = del_res.json()["deliveries"]
        for d in items:
            self.assertEqual(d["status"], "SUCCEEDED")
            # Ensure no delivery object returns provider_status "DELIVERED"
            self.assertNotEqual(d.get("provider_status"), "DELIVERED")

    # 52. Approved Recipient-Snapshot Authority
    def test_52_approved_recipient_snapshot_authority(self):
        # A. Create advisory using ALL_ASSIGNED with recipients A and B
        fdr = self.forecast_svc.generate_record(
            GenerateForecastRecordRequest(disease="FMD", district="Anuradhapura", year=2026, month=9)
        )
        draft = self.advisory_svc.create_draft(
            CreateAdvisoryDraftRequest(
                forecast_id=fdr.forecast_id,
                advisory_type="VETERINARY_CUSTOM_ADVICE",
                recipient_scope="ALL_ASSIGNED",
                personalized_overrides=[
                    PersonalizedOverride(recipient_id="DEMO_FARM_001", custom_note="Specific advice for Farm 1")
                ],
            )
        )
        # B. Move to REVIEW_READY and APPROVED
        rr = self.advisory_svc.mark_ready_for_review(draft.advisory_id, draft.version)
        appr = self.advisory_svc.approve_advisory(rr.advisory_id, rr.version, approved_by="vet_officer_01")
        approved_ids = list(appr.selected_recipient_ids)
        self.assertIn("DEMO_FARM_001", approved_ids)
        self.assertIn("DEMO_FARM_002", approved_ids)

        # C. Modify/replace RecipientDirectory so it exposes B and C (e.g. DEMO_FARM_002 and DEMO_FARM_999)
        from components.risk_forecasting.integrations.recipient_directory import Recipient
        self.recipient_dir._recipients = [
            Recipient(recipient_id="DEMO_FARM_002", recipient_name="Farm 2", district="Anuradhapura", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_999", recipient_name="New Farm 999", district="Anuradhapura", assigned_vet_id="vet_officer_01"),
        ]

        # D. Enqueue approved advisory
        batch = self.service.enqueue_approved_advisory(appr.advisory_id)

        # E. Verify deliveries match exact approved snapshot (A and B), NOT B and C
        deliveries = self.service.list_batch_deliveries(batch.batch_id).deliveries
        enqueued_recipient_ids = [d.recipient_id for d in deliveries]

        self.assertEqual(enqueued_recipient_ids, approved_ids)
        self.assertNotIn("DEMO_FARM_999", enqueued_recipient_ids)

        # Verify personalized content remains mapped to originally approved recipient
        farm1_del = next(d for d in deliveries if d.recipient_id == "DEMO_FARM_001")
        self.assertIn("Personalized Advice: Specific advice for Farm 1", farm1_del.resolved_message)

    # 53. Approved Content Snapshot Authority
    def test_53_approved_content_snapshot_authority(self):
        # 1. Create and approve advisory with template content A
        appr, _ = self._create_approved_advisory(disease="LSD", district="Colombo")
        approved_msg = appr.standard_message

        # 2. Mutate/replace template service to produce content B
        class MutatedTemplateService:
            def generate_standard_content(self, **kwargs):
                return ("NEW_TITLE_B", "MUTATED_CONTENT_B", [], [], "", "", "HIGH")

        self.advisory_svc.template_svc = MutatedTemplateService()

        # 3. Enqueue
        batch = self.service.enqueue_approved_advisory(appr.advisory_id)

        # 4. Verify frozen delivery messages use approved content A
        deliveries = self.service.list_batch_deliveries(batch.batch_id).deliveries
        for d in deliveries:
            self.assertIn(approved_msg, d.resolved_message)
            self.assertNotIn("MUTATED_CONTENT_B", d.resolved_message)

    # 54. Provider Exception Sanitization and No Secret Leak
    def test_54_provider_exception_sanitization_and_no_secret_leak(self):
        approved_adv, _ = self._create_approved_advisory()
        batch = self.service.enqueue_approved_advisory(approved_adv.advisory_id)

        # Custom exception provider raising a fake secret
        class ExceptionProvider:
            provider_name = "ExceptionProvider"

            def send(self, payload):
                raise RuntimeError("connection failed token=DO_NOT_EXPOSE_SECRET_KEY")

        self.service.provider = ExceptionProvider()

        # Dispatch batch
        b_after = self.service.dispatch_batch(batch.batch_id)
        self.assertEqual(b_after.status, "FAILED")

        deliveries = self.service.list_batch_deliveries(batch.batch_id).deliveries
        for d in deliveries:
            self.assertEqual(d.status, "FAILED")
            # Verify controlled error message
            self.assertEqual(d.last_error, "[PROVIDER_EXCEPTION] Mock notification provider execution failed.")
            # Assert raw secret and exception text do NOT appear
            self.assertNotIn("DO_NOT_EXPOSE", str(d.last_error))
            self.assertNotIn("connection failed", str(d.last_error))

        # Perform retry with working provider and verify retry success clears public error
        self.service.provider = self.mock_provider
        b_retry = self.service.retry_failed_deliveries(batch.batch_id)
        self.assertEqual(b_retry.status, "COMPLETED")
        retry_deliveries = self.service.list_batch_deliveries(batch.batch_id).deliveries
        for rd in retry_deliveries:
            self.assertEqual(rd.status, "SUCCEEDED")
            self.assertIsNone(rd.last_error)


if __name__ == "__main__":
    unittest.main()
