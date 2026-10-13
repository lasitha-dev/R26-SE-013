"""
Notification Service & Outbox Dispatcher (Phase 4).

Orchestrates approved advisory enqueueing, payload freezing, mock notification dispatching,
failure retry, batch cancellation, and optimistic concurrency tracking.

ARCHITECTURAL RULES:
1. Approved Advisory Provenance: Enqueues ONLY advisories with status APPROVED.
2. Frozen Payload: Resolves per-recipient final messages at enqueue time. Stores NO PII (phone/email).
3. Outbox Isolation: Enqueueing creates outbox records without invoking the provider.
4. Concurrency Safety: Uses atomic delivery claiming to prevent duplicate provider invocation.
5. Standalone Execution: Provider calls are explicitly triggered for testing; zero external network calls.
"""

from datetime import datetime, timezone
import uuid
from typing import Callable, List, Optional, Tuple

from components.risk_forecasting.integrations.notification_provider import (
    MockNotificationProvider,
    NotificationProvider,
    ProviderDeliveryPayload,
    mock_notification_provider,
)
from components.risk_forecasting.repositories.advisory_repository import (
    AdvisoryRepository,
    InMemoryAdvisoryRepository,
)
from components.risk_forecasting.repositories.notification_outbox_repository import (
    InMemoryNotificationOutboxRepository,
    NotificationOutboxRepository,
)
from components.risk_forecasting.schemas import (
    EnqueueNotificationBatchRequest,
    NotificationBatch,
    NotificationBatchListResponse,
    NotificationDelivery,
    NotificationDeliveryListResponse,
)
from components.risk_forecasting.services.advisory_service import (
    AdvisoryService,
    advisory_service,
)


class NotificationService:
    """Service orchestrating notification outbox enqueueing, dispatching, and retries."""

    def __init__(
        self,
        advisory_svc: Optional[AdvisoryService] = None,
        advisory_repo: Optional[AdvisoryRepository] = None,
        outbox_repository: Optional[NotificationOutboxRepository] = None,
        notification_provider: Optional[NotificationProvider] = None,
        clock: Optional[Callable[[], datetime]] = None,
        id_generator: Optional[Callable[[str], str]] = None,
    ):
        self.advisory_svc = advisory_svc or advisory_service
        self.advisory_repo = advisory_repo or self.advisory_svc.advisory_repo
        self.outbox_repo = outbox_repository or InMemoryNotificationOutboxRepository()
        self.provider = notification_provider or mock_notification_provider
        self.clock = clock or (lambda: datetime.now(timezone.utc))

        def default_id_gen(prefix: str) -> str:
            return f"{prefix}_{uuid.uuid4().hex[:12]}"

        self.id_generator = id_generator or default_id_gen

    def enqueue_approved_advisory(
        self,
        advisory_id: str,
        created_by: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> NotificationBatch:
        """
        Enqueues an APPROVED advisory into the notification outbox.
        Creates frozen delivery payloads for all resolved recipients.
        Makes ZERO provider calls.
        """
        # 1. Fetch Authoritative Advisory Record
        adv_record = self.advisory_repo.get_by_id(advisory_id)
        if not adv_record:
            raise KeyError(f"Advisory record with ID '{advisory_id}' not found.")

        # 2. Status Safeguard
        if adv_record.status == "CANCELLED":
            raise ValueError("Cancelled advisories cannot be enqueued for notification delivery.")
        if adv_record.status != "APPROVED":
            raise ValueError(
                f"Advisory must be APPROVED to enqueue for notification delivery (current status: '{adv_record.status}')."
            )

        # 3. Idempotency Check
        if idempotency_key:
            existing_by_key = self.outbox_repo.find_batch_by_idempotency_key(idempotency_key)
            if existing_by_key:
                if existing_by_key.advisory_id == advisory_id:
                    return existing_by_key
                else:
                    raise ValueError(
                        f"Idempotency key collision: Key '{idempotency_key}' "
                        f"was previously used with a different advisory ID."
                    )

        # 4. Semantic Deduplication Check for (advisory_id, version)
        if hasattr(self.outbox_repo, "find_batch_by_advisory_version"):
            existing_by_version = self.outbox_repo.find_batch_by_advisory_version(
                advisory_id, adv_record.version
            )
            if existing_by_version:
                return existing_by_version

        # 5. Resolve Frozen Delivery Messages via Advisory Preview
        preview = self.advisory_svc.preview_advisory(advisory_id=advisory_id)

        if not preview.previews:
            raise ValueError(f"Advisory '{advisory_id}' has zero targeted recipients.")

        now_dt = self.clock()
        now_iso = now_dt.isoformat()
        actor = created_by or adv_record.created_by
        batch_id = self.id_generator("batch")

        # 6. Construct Frozen Delivery Items (NO PII/phones/emails)
        deliveries: List[NotificationDelivery] = []
        for p in preview.previews:
            del_id = self.id_generator("del")
            delivery = NotificationDelivery(
                delivery_id=del_id,
                batch_id=batch_id,
                advisory_id=adv_record.advisory_id,
                forecast_id=adv_record.forecast_id,
                recipient_id=p.recipient_id,
                resolved_message=p.final_message,
                status="PENDING",
                attempt_count=0,
                provider_reference=None,
                last_error=None,
                created_at=now_iso,
                updated_at=now_iso,
                first_attempted_at=None,
                last_attempted_at=None,
                succeeded_at=None,
                next_retry_at=None,
                version=1,
            )
            deliveries.append(delivery)

        # 7. Construct NotificationBatch
        batch = NotificationBatch(
            batch_id=batch_id,
            advisory_id=adv_record.advisory_id,
            forecast_id=adv_record.forecast_id,
            provider_name=self.provider.provider_name,
            status="QUEUED",
            recipient_count=len(deliveries),
            pending_count=len(deliveries),
            processing_count=0,
            succeeded_count=0,
            failed_count=0,
            created_by=actor,
            idempotency_key=idempotency_key,
            created_at=now_iso,
            updated_at=now_iso,
            completed_at=None,
            version=1,
        )

        stored_batch, _ = self.outbox_repo.create_batch(batch, deliveries)
        if hasattr(self.outbox_repo, "register_advisory_version_index"):
            self.outbox_repo.register_advisory_version_index(
                advisory_id, adv_record.version, batch_id
            )
        return stored_batch

    def dispatch_batch(self, batch_id: str) -> NotificationBatch:
        """
        Dispatches all PENDING delivery items in a batch through the mock provider.
        Re-reads authoritative advisory state before dispatch.
        Uses atomic delivery claiming to ensure thread-safety and prevent double dispatch.
        """
        batch = self.outbox_repo.get_batch_by_id(batch_id)
        if not batch:
            raise KeyError(f"Notification batch with ID '{batch_id}' not found.")

        if batch.status == "CANCELLED":
            raise ValueError("Cannot dispatch CANCELLED notification batch.")

        adv_record = self.advisory_repo.get_by_id(batch.advisory_id)
        if not adv_record:
            raise KeyError(f"Authoritative advisory record '{batch.advisory_id}' not found.")
        if adv_record.status != "APPROVED":
            raise ValueError(
                f"Referenced advisory '{batch.advisory_id}' is no longer APPROVED (current status: '{adv_record.status}'). Dispatch is blocked."
            )

        deliveries, _ = self.outbox_repo.list_deliveries_by_batch(
            batch_id=batch_id, status="PENDING", limit=500
        )

        for d in deliveries:
            now_iso = self.clock().isoformat()
            claimed = self.outbox_repo.claim_delivery_for_processing(
                delivery_id=d.delivery_id,
                expected_version=d.version,
                updated_at=now_iso,
            )
            if not claimed:
                continue  # Already claimed or processed concurrently

            payload = ProviderDeliveryPayload(
                delivery_id=claimed.delivery_id,
                batch_id=claimed.batch_id,
                advisory_id=claimed.advisory_id,
                forecast_id=claimed.forecast_id,
                recipient_id=claimed.recipient_id,
                resolved_message=claimed.resolved_message,
            )

            try:
                result = self.provider.send(payload)
                exec_time = self.clock().isoformat()
                if result.success:
                    self.outbox_repo.record_delivery_success(
                        delivery_id=claimed.delivery_id,
                        expected_version=claimed.version,
                        provider_reference=result.provider_reference or "mock_ref",
                        attempted_at=result.attempted_at,
                        updated_at=exec_time,
                    )
                else:
                    self.outbox_repo.record_delivery_failure(
                        delivery_id=claimed.delivery_id,
                        expected_version=claimed.version,
                        error_code=result.error_code or "PROVIDER_FAILURE",
                        error_message=result.error_message or "Provider reported delivery failure",
                        attempted_at=result.attempted_at,
                        updated_at=exec_time,
                    )
            except Exception as exc:
                exec_time = self.clock().isoformat()
                self.outbox_repo.record_delivery_failure(
                    delivery_id=claimed.delivery_id,
                    expected_version=claimed.version,
                    error_code="PROVIDER_EXCEPTION",
                    error_message="Mock notification provider execution failed.",
                    attempted_at=exec_time,
                    updated_at=exec_time,
                )

        now_iso = self.clock().isoformat()
        return self.outbox_repo.refresh_batch_status(batch_id, now_iso)

    def retry_failed_deliveries(self, batch_id: str) -> NotificationBatch:
        """
        Retries all FAILED delivery items in a batch.
        Re-reads authoritative advisory state before retrying.
        Increments attempt counts and updates error details without touching SUCCEEDED items.
        """
        batch = self.outbox_repo.get_batch_by_id(batch_id)
        if not batch:
            raise KeyError(f"Notification batch with ID '{batch_id}' not found.")

        if batch.status == "CANCELLED":
            raise ValueError("Cannot retry deliveries for a CANCELLED batch.")

        adv_record = self.advisory_repo.get_by_id(batch.advisory_id)
        if not adv_record:
            raise KeyError(f"Authoritative advisory record '{batch.advisory_id}' not found.")
        if adv_record.status != "APPROVED":
            raise ValueError(
                f"Referenced advisory '{batch.advisory_id}' is no longer APPROVED (current status: '{adv_record.status}'). Retry is blocked."
            )

        deliveries, _ = self.outbox_repo.list_deliveries_by_batch(
            batch_id=batch_id, status="FAILED", limit=500
        )

        for d in deliveries:
            now_iso = self.clock().isoformat()
            claimed = self.outbox_repo.claim_delivery_for_processing(
                delivery_id=d.delivery_id,
                expected_version=d.version,
                updated_at=now_iso,
            )
            if not claimed:
                continue

            payload = ProviderDeliveryPayload(
                delivery_id=claimed.delivery_id,
                batch_id=claimed.batch_id,
                advisory_id=claimed.advisory_id,
                forecast_id=claimed.forecast_id,
                recipient_id=claimed.recipient_id,
                resolved_message=claimed.resolved_message,
            )

            try:
                result = self.provider.send(payload)
                exec_time = self.clock().isoformat()
                if result.success:
                    self.outbox_repo.record_delivery_success(
                        delivery_id=claimed.delivery_id,
                        expected_version=claimed.version,
                        provider_reference=result.provider_reference or "mock_ref",
                        attempted_at=result.attempted_at,
                        updated_at=exec_time,
                    )
                else:
                    self.outbox_repo.record_delivery_failure(
                        delivery_id=claimed.delivery_id,
                        expected_version=claimed.version,
                        error_code=result.error_code or "PROVIDER_FAILURE",
                        error_message=result.error_message or "Provider reported delivery failure",
                        attempted_at=result.attempted_at,
                        updated_at=exec_time,
                    )
            except Exception as exc:
                exec_time = self.clock().isoformat()
                self.outbox_repo.record_delivery_failure(
                    delivery_id=claimed.delivery_id,
                    expected_version=claimed.version,
                    error_code="PROVIDER_EXCEPTION",
                    error_message="Mock notification provider execution failed.",
                    attempted_at=exec_time,
                    updated_at=exec_time,
                )

        now_iso = self.clock().isoformat()
        return self.outbox_repo.refresh_batch_status(batch_id, now_iso)

    def cancel_notification_batch(self, batch_id: str) -> NotificationBatch:
        """Cancels a safe QUEUED notification batch prior to any delivery attempts."""
        now_iso = self.clock().isoformat()
        cancelled_batch, _ = self.outbox_repo.cancel_queued_batch(batch_id, now_iso)
        return cancelled_batch

    def get_batch(self, batch_id: str) -> NotificationBatch:
        """Retrieves notification batch by ID."""
        batch = self.outbox_repo.get_batch_by_id(batch_id)
        if not batch:
            raise KeyError(f"Notification batch with ID '{batch_id}' not found.")
        return batch

    def list_batches(
        self,
        advisory_id: Optional[str] = None,
        forecast_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> NotificationBatchListResponse:
        """Queries notification batches with bounded pagination."""
        bounded_limit = min(max(1, limit), 200)
        bounded_offset = max(0, offset)

        batches, total_count = self.outbox_repo.list_batches(
            advisory_id=advisory_id,
            forecast_id=forecast_id,
            status=status,
            limit=bounded_limit,
            offset=bounded_offset,
        )

        return NotificationBatchListResponse(
            total_count=total_count,
            limit=bounded_limit,
            offset=bounded_offset,
            batches=batches,
        )

    def list_batch_deliveries(
        self,
        batch_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> NotificationDeliveryListResponse:
        """Queries deliveries for a batch with bounded pagination."""
        # Verify batch exists
        self.get_batch(batch_id)

        bounded_limit = min(max(1, limit), 200)
        bounded_offset = max(0, offset)

        deliveries, total_count = self.outbox_repo.list_deliveries_by_batch(
            batch_id=batch_id,
            status=status,
            limit=bounded_limit,
            offset=bounded_offset,
        )

        return NotificationDeliveryListResponse(
            total_count=total_count,
            limit=bounded_limit,
            offset=bounded_offset,
            deliveries=deliveries,
        )


# Default Singleton Instance
notification_service = NotificationService()
