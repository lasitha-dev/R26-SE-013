"""
Notification Outbox Repository Boundary (Phase 4).

Defines the NotificationOutboxRepository protocol and thread-safe in-memory implementation
for atomic batch and delivery persistence, concurrency control, and status tracking.

NON-DURABILITY NOTICE:
InMemoryNotificationOutboxRepository stores outbox data in-memory only.
In production, this repository will be replaced by a shared persistent database adapter.
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Protocol, Set, Tuple

from backend.components.risk_forecasting.schemas import (
    NotificationBatch,
    NotificationDelivery,
)


class NotificationOutboxRepository(Protocol):
    """Protocol defining the Notification Outbox Repository contract."""

    def create_batch(
        self, batch: NotificationBatch, deliveries: List[NotificationDelivery]
    ) -> Tuple[NotificationBatch, List[NotificationDelivery]]:
        ...

    def get_batch_by_id(self, batch_id: str) -> Optional[NotificationBatch]:
        ...

    def find_batch_by_idempotency_key(self, idempotency_key: str) -> Optional[NotificationBatch]:
        ...

    def find_batch_by_advisory_version(
        self, advisory_id: str, advisory_version: int
    ) -> Optional[NotificationBatch]:
        ...

    def list_batches(
        self,
        advisory_id: Optional[str] = None,
        forecast_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[NotificationBatch], int]:
        ...

    def get_delivery_by_id(self, delivery_id: str) -> Optional[NotificationDelivery]:
        ...

    def list_deliveries_by_batch(
        self,
        batch_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[NotificationDelivery], int]:
        ...

    def claim_delivery_for_processing(
        self, delivery_id: str, expected_version: int, updated_at: str
    ) -> Optional[NotificationDelivery]:
        ...

    def record_delivery_success(
        self,
        delivery_id: str,
        expected_version: int,
        provider_reference: str,
        attempted_at: str,
        updated_at: str,
    ) -> NotificationDelivery:
        ...

    def record_delivery_failure(
        self,
        delivery_id: str,
        expected_version: int,
        error_code: str,
        error_message: str,
        attempted_at: str,
        updated_at: str,
    ) -> NotificationDelivery:
        ...

    def refresh_batch_status(self, batch_id: str, updated_at: str) -> NotificationBatch:
        ...

    def cancel_queued_batch(
        self, batch_id: str, updated_at: str
    ) -> Tuple[NotificationBatch, List[NotificationDelivery]]:
        ...


class InMemoryNotificationOutboxRepository:
    """
    Thread-safe in-memory implementation of NotificationOutboxRepository.
    Enforces atomic batch creation, defensive copying, optimistic concurrency, and aggregate status calculation.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._batches: Dict[str, NotificationBatch] = {}
        self._deliveries: Dict[str, NotificationDelivery] = {}
        self._batch_deliveries: Dict[str, List[str]] = {}  # batch_id -> list of delivery_id
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> batch_id
        self._advisory_version_index: Dict[Tuple[str, int], str] = {}  # (advisory_id, version) -> batch_id

    def create_batch(
        self, batch: NotificationBatch, deliveries: List[NotificationDelivery]
    ) -> Tuple[NotificationBatch, List[NotificationDelivery]]:
        with self._lock:
            if batch.batch_id in self._batches:
                raise ValueError(f"Notification batch with ID '{batch.batch_id}' already exists.")

            if batch.idempotency_key:
                if batch.idempotency_key in self._idempotency_index:
                    existing_id = self._idempotency_index[batch.idempotency_key]
                    existing_b = self._batches[existing_id].model_copy(deep=True)
                    existing_d = [
                        self._deliveries[did].model_copy(deep=True)
                        for did in self._batch_deliveries.get(existing_id, [])
                    ]
                    return existing_b, existing_d

            stored_b = batch.model_copy(deep=True)
            stored_d_list: List[NotificationDelivery] = []

            self._batches[batch.batch_id] = stored_b
            self._batch_deliveries[batch.batch_id] = []

            for d in deliveries:
                if d.delivery_id in self._deliveries:
                    raise ValueError(f"Notification delivery with ID '{d.delivery_id}' already exists.")
                sd = d.model_copy(deep=True)
                self._deliveries[d.delivery_id] = sd
                self._batch_deliveries[batch.batch_id].append(d.delivery_id)
                stored_d_list.append(sd.model_copy(deep=True))

            if batch.idempotency_key:
                self._idempotency_index[batch.idempotency_key] = batch.batch_id

            # Register semantic index (advisory_id, advisory_version - retrieved via batch version 1)
            # Note: We track by advisory_id in helper if needed
            return stored_b.model_copy(deep=True), stored_d_list

    def get_batch_by_id(self, batch_id: str) -> Optional[NotificationBatch]:
        with self._lock:
            b = self._batches.get(batch_id)
            return b.model_copy(deep=True) if b else None

    def find_batch_by_idempotency_key(self, idempotency_key: str) -> Optional[NotificationBatch]:
        with self._lock:
            b_id = self._idempotency_index.get(idempotency_key)
            if b_id:
                b = self._batches.get(b_id)
                return b.model_copy(deep=True) if b else None
            return None

    def find_batch_by_advisory_version(
        self, advisory_id: str, advisory_version: int
    ) -> Optional[NotificationBatch]:
        with self._lock:
            b_id = self._advisory_version_index.get((advisory_id, advisory_version))
            if b_id:
                b = self._batches.get(b_id)
                return b.model_copy(deep=True) if b else None
            # Fallback search
            for b in self._batches.values():
                if b.advisory_id == advisory_id:
                    return b.model_copy(deep=True)
            return None

    def register_advisory_version_index(self, advisory_id: str, advisory_version: int, batch_id: str):
        with self._lock:
            self._advisory_version_index[(advisory_id, advisory_version)] = batch_id

    def list_batches(
        self,
        advisory_id: Optional[str] = None,
        forecast_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[NotificationBatch], int]:
        with self._lock:
            filtered = list(self._batches.values())
            if advisory_id:
                filtered = [b for b in filtered if b.advisory_id == advisory_id]
            if forecast_id:
                filtered = [b for b in filtered if b.forecast_id == forecast_id]
            if status:
                st_upper = status.upper()
                filtered = [b for b in filtered if b.status == st_upper]

            filtered.sort(key=lambda b: b.created_at, reverse=True)
            total_count = len(filtered)
            paginated = [b.model_copy(deep=True) for b in filtered[offset : offset + limit]]
            return paginated, total_count

    def get_delivery_by_id(self, delivery_id: str) -> Optional[NotificationDelivery]:
        with self._lock:
            d = self._deliveries.get(delivery_id)
            return d.model_copy(deep=True) if d else None

    def list_deliveries_by_batch(
        self,
        batch_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[NotificationDelivery], int]:
        with self._lock:
            d_ids = self._batch_deliveries.get(batch_id, [])
            items = [self._deliveries[did] for did in d_ids if did in self._deliveries]

            if status:
                st_upper = status.upper()
                items = [d for d in items if d.status == st_upper]

            items.sort(key=lambda d: d.created_at)
            total_count = len(items)
            paginated = [d.model_copy(deep=True) for d in items[offset : offset + limit]]
            return paginated, total_count

    def claim_delivery_for_processing(
        self, delivery_id: str, expected_version: int, updated_at: str
    ) -> Optional[NotificationDelivery]:
        with self._lock:
            d = self._deliveries.get(delivery_id)
            if not d:
                return None
            if d.version != expected_version:
                return None
            if d.status not in {"PENDING", "FAILED"}:
                return None

            dict_d = d.model_dump()
            dict_d["status"] = "PROCESSING"
            dict_d["version"] = d.version + 1
            dict_d["updated_at"] = updated_at

            updated_d = NotificationDelivery(**dict_d)
            self._deliveries[delivery_id] = updated_d

            # Update batch processing count
            self._internal_refresh_batch_status(d.batch_id, updated_at)

            return updated_d.model_copy(deep=True)

    def record_delivery_success(
        self,
        delivery_id: str,
        expected_version: int,
        provider_reference: str,
        attempted_at: str,
        updated_at: str,
    ) -> NotificationDelivery:
        with self._lock:
            d = self._deliveries.get(delivery_id)
            if not d:
                raise KeyError(f"Notification delivery with ID '{delivery_id}' not found.")
            if d.version != expected_version:
                raise ValueError(
                    f"Optimistic lock conflict for delivery '{delivery_id}': "
                    f"Expected version {expected_version}, but stored version is {d.version}."
                )

            dict_d = d.model_dump()
            dict_d["status"] = "SUCCEEDED"
            dict_d["attempt_count"] = d.attempt_count + 1
            dict_d["provider_reference"] = provider_reference
            dict_d["last_error"] = None
            dict_d["last_attempted_at"] = attempted_at
            if not dict_d.get("first_attempted_at"):
                dict_d["first_attempted_at"] = attempted_at
            dict_d["succeeded_at"] = attempted_at
            dict_d["version"] = d.version + 1
            dict_d["updated_at"] = updated_at

            updated_d = NotificationDelivery(**dict_d)
            self._deliveries[delivery_id] = updated_d

            self._internal_refresh_batch_status(d.batch_id, updated_at)
            return updated_d.model_copy(deep=True)

    def record_delivery_failure(
        self,
        delivery_id: str,
        expected_version: int,
        error_code: str,
        error_message: str,
        attempted_at: str,
        updated_at: str,
    ) -> NotificationDelivery:
        with self._lock:
            d = self._deliveries.get(delivery_id)
            if not d:
                raise KeyError(f"Notification delivery with ID '{delivery_id}' not found.")
            if d.version != expected_version:
                raise ValueError(
                    f"Optimistic lock conflict for delivery '{delivery_id}': "
                    f"Expected version {expected_version}, but stored version is {d.version}."
                )

            dict_d = d.model_dump()
            dict_d["status"] = "FAILED"
            dict_d["attempt_count"] = d.attempt_count + 1
            dict_d["last_error"] = f"[{error_code}] {error_message}"
            dict_d["last_attempted_at"] = attempted_at
            if not dict_d.get("first_attempted_at"):
                dict_d["first_attempted_at"] = attempted_at
            dict_d["version"] = d.version + 1
            dict_d["updated_at"] = updated_at

            updated_d = NotificationDelivery(**dict_d)
            self._deliveries[delivery_id] = updated_d

            self._internal_refresh_batch_status(d.batch_id, updated_at)
            return updated_d.model_copy(deep=True)

    def refresh_batch_status(self, batch_id: str, updated_at: str) -> NotificationBatch:
        with self._lock:
            return self._internal_refresh_batch_status(batch_id, updated_at)

    def _internal_refresh_batch_status(self, batch_id: str, updated_at: str) -> NotificationBatch:
        b = self._batches.get(batch_id)
        if not b:
            raise KeyError(f"Notification batch with ID '{batch_id}' not found.")

        d_ids = self._batch_deliveries.get(batch_id, [])
        deliveries = [self._deliveries[did] for did in d_ids if did in self._deliveries]

        total = len(deliveries)
        pending = sum(1 for d in deliveries if d.status == "PENDING")
        processing = sum(1 for d in deliveries if d.status == "PROCESSING")
        succeeded = sum(1 for d in deliveries if d.status == "SUCCEEDED")
        failed = sum(1 for d in deliveries if d.status == "FAILED")
        cancelled = sum(1 for d in deliveries if d.status == "CANCELLED")

        # Determine batch status
        if b.status == "CANCELLED":
            new_status = "CANCELLED"
        elif total == 0:
            new_status = "COMPLETED"
        elif cancelled == total:
            new_status = "CANCELLED"
        elif succeeded == total:
            new_status = "COMPLETED"
        elif failed == total:
            new_status = "FAILED"
        elif (succeeded + failed + cancelled) == total and (succeeded > 0 or failed > 0):
            new_status = "PARTIALLY_FAILED" if failed > 0 else "COMPLETED"
        elif processing > 0 or (succeeded + failed) > 0:
            new_status = "PROCESSING"
        else:
            new_status = "QUEUED"

        completed_at = b.completed_at
        if new_status in {"QUEUED", "PROCESSING"}:
            completed_at = None
        elif new_status in {"COMPLETED", "PARTIALLY_FAILED", "FAILED", "CANCELLED"}:
            if not completed_at or b.status in {"QUEUED", "PROCESSING"}:
                completed_at = updated_at
            else:
                completed_at = updated_at

        dict_b = b.model_dump()
        dict_b["recipient_count"] = total
        dict_b["pending_count"] = pending
        dict_b["processing_count"] = processing
        dict_b["succeeded_count"] = succeeded
        dict_b["failed_count"] = failed
        dict_b["cancelled_count"] = cancelled
        dict_b["status"] = new_status
        dict_b["completed_at"] = completed_at
        dict_b["version"] = b.version + 1
        dict_b["updated_at"] = updated_at

        updated_b = NotificationBatch(**dict_b)
        self._batches[batch_id] = updated_b
        return updated_b.model_copy(deep=True)

    def cancel_queued_batch(
        self, batch_id: str, updated_at: str
    ) -> Tuple[NotificationBatch, List[NotificationDelivery]]:
        with self._lock:
            b = self._batches.get(batch_id)
            if not b:
                raise KeyError(f"Notification batch with ID '{batch_id}' not found.")

            d_ids = self._batch_deliveries.get(batch_id, [])
            deliveries = [self._deliveries[did] for did in d_ids if did in self._deliveries]

            # Reject if any provider attempt has occurred
            attempted = any(
                d.attempt_count > 0 or d.status in {"PROCESSING", "SUCCEEDED", "FAILED"}
                for d in deliveries
            )
            if attempted or b.succeeded_count > 0 or b.failed_count > 0:
                raise ValueError("Cannot cancel notification batch after delivery attempts have commenced.")

            # Update batch
            dict_b = b.model_dump()
            dict_b["status"] = "CANCELLED"
            dict_b["completed_at"] = updated_at
            dict_b["version"] = b.version + 1
            dict_b["updated_at"] = updated_at

            updated_b = NotificationBatch(**dict_b)
            self._batches[batch_id] = updated_b

            # Cancel all child deliveries
            updated_deliveries: List[NotificationDelivery] = []
            for d in deliveries:
                dict_d = d.model_dump()
                dict_d["status"] = "CANCELLED"
                dict_d["version"] = d.version + 1
                dict_d["updated_at"] = updated_at
                ud = NotificationDelivery(**dict_d)
                self._deliveries[d.delivery_id] = ud
                updated_deliveries.append(ud.model_copy(deep=True))

            refreshed_b = self._internal_refresh_batch_status(batch_id, updated_at)

            return refreshed_b, updated_deliveries
