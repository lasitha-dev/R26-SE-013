"""
Advisory Repository Boundary (Phase 3).

Defines the AdvisoryRepository protocol and thread-safe in-memory implementation
for managing FarmerAdvisoryRecord persistence, optimistic locking, and lifecycle status.

NON-DURABILITY NOTICE:
InMemoryAdvisoryRepository stores data in-memory only. All advisory records will be reset on application restart.
In production, this repository will be replaced by a persistent database adapter (e.g. PostgreSQL or MongoDB).
"""

from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Protocol, Tuple

from components.risk_forecasting.schemas import (
    FarmerAdvisoryRecord,
    PersonalizedOverride,
    RecipientSummary,
)


class AdvisoryRepository(Protocol):
    """Protocol defining the Advisory Repository contract."""

    def save(self, advisory: FarmerAdvisoryRecord) -> FarmerAdvisoryRecord:
        ...

    def get_by_id(self, advisory_id: str) -> Optional[FarmerAdvisoryRecord]:
        ...

    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[FarmerAdvisoryRecord]:
        ...

    def list(
        self,
        forecast_id: Optional[str] = None,
        disease: Optional[str] = None,
        district: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[FarmerAdvisoryRecord], int]:
        ...

    def update_draft(
        self,
        advisory_id: str,
        expected_version: int,
        recipient_scope: Optional[str] = None,
        selected_recipient_ids: Optional[List[str]] = None,
        vet_custom_note: Optional[str] = None,
        personalized_overrides: Optional[List[PersonalizedOverride]] = None,
        recipient_summary: Optional[RecipientSummary] = None,
        updated_at: Optional[str] = None,
    ) -> FarmerAdvisoryRecord:
        ...

    def update_status(
        self,
        advisory_id: str,
        expected_version: int,
        new_status: str,
        approved_by: Optional[str] = None,
        approved_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> FarmerAdvisoryRecord:
        ...


class InMemoryAdvisoryRepository:
    """
    Thread-safe, in-memory implementation of AdvisoryRepository.
    Enforces deep defensive copying, optimistic version checking, and status immutability rules.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._advisories: Dict[str, FarmerAdvisoryRecord] = {}
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> advisory_id

    def save(self, advisory: FarmerAdvisoryRecord) -> FarmerAdvisoryRecord:
        with self._lock:
            if advisory.advisory_id in self._advisories:
                raise ValueError(f"Advisory with ID '{advisory.advisory_id}' already exists.")

            if advisory.idempotency_key:
                if advisory.idempotency_key in self._idempotency_index:
                    existing_id = self._idempotency_index[advisory.idempotency_key]
                    return self._advisories[existing_id].model_copy(deep=True)

            stored = advisory.model_copy(deep=True)
            self._advisories[advisory.advisory_id] = stored
            if advisory.idempotency_key:
                self._idempotency_index[advisory.idempotency_key] = advisory.advisory_id

            return stored.model_copy(deep=True)

    def get_by_id(self, advisory_id: str) -> Optional[FarmerAdvisoryRecord]:
        with self._lock:
            adv = self._advisories.get(advisory_id)
            return adv.model_copy(deep=True) if adv else None

    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[FarmerAdvisoryRecord]:
        with self._lock:
            adv_id = self._idempotency_index.get(idempotency_key)
            if adv_id:
                adv = self._advisories.get(adv_id)
                return adv.model_copy(deep=True) if adv else None
            return None

    def list(
        self,
        forecast_id: Optional[str] = None,
        disease: Optional[str] = None,
        district: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[FarmerAdvisoryRecord], int]:
        with self._lock:
            filtered = list(self._advisories.values())

            if forecast_id:
                filtered = [a for a in filtered if a.forecast_id == forecast_id]

            if disease:
                disease_upper = disease.upper()
                filtered = [a for a in filtered if a.disease == disease_upper]

            if district:
                dist_title = district.strip().title()
                if dist_title in ["Moneragala", "Monaragala"]:
                    dist_title = "Monaragala"
                elif dist_title in ["Nuwaraeliya", "Nuwara Eliya"]:
                    dist_title = "Nuwara Eliya"
                filtered = [a for a in filtered if a.district == dist_title]

            if status:
                status_upper = status.upper()
                filtered = [a for a in filtered if a.status == status_upper]

            # Sort by created_at descending
            filtered.sort(key=lambda a: a.created_at, reverse=True)

            total_count = len(filtered)
            paginated = [a.model_copy(deep=True) for a in filtered[offset : offset + limit]]

            return paginated, total_count

    def update_draft(
        self,
        advisory_id: str,
        expected_version: int,
        recipient_scope: Optional[str] = None,
        selected_recipient_ids: Optional[List[str]] = None,
        vet_custom_note: Optional[str] = None,
        personalized_overrides: Optional[List[PersonalizedOverride]] = None,
        recipient_summary: Optional[RecipientSummary] = None,
        updated_at: Optional[str] = None,
    ) -> FarmerAdvisoryRecord:
        with self._lock:
            stored = self._advisories.get(advisory_id)
            if not stored:
                raise KeyError(f"Advisory record with ID '{advisory_id}' not found.")

            if stored.status == "APPROVED":
                raise ValueError("Approved advisories are immutable and cannot be edited.")
            if stored.status == "CANCELLED":
                raise ValueError("Cancelled advisories cannot be edited.")
            if stored.status not in {"DRAFT", "REVIEW_READY"}:
                raise ValueError(f"Advisory in status '{stored.status}' cannot be updated.")

            if stored.version != expected_version:
                raise ValueError(
                    f"Optimistic lock conflict for advisory '{advisory_id}': "
                    f"Expected version {expected_version}, but stored version is {stored.version}."
                )

            now_iso = updated_at or datetime.now(timezone.utc).isoformat()
            updated_dict = stored.model_dump()

            if recipient_scope is not None:
                updated_dict["recipient_scope"] = recipient_scope
            if selected_recipient_ids is not None:
                updated_dict["selected_recipient_ids"] = selected_recipient_ids
            if vet_custom_note is not None:
                updated_dict["vet_custom_note"] = vet_custom_note
            if personalized_overrides is not None:
                updated_dict["personalized_overrides"] = [
                    po.model_dump() if isinstance(po, PersonalizedOverride) else po
                    for po in personalized_overrides
                ]
            if recipient_summary is not None:
                updated_dict["recipient_summary"] = (
                    recipient_summary.model_dump()
                    if isinstance(recipient_summary, RecipientSummary)
                    else recipient_summary
                )

            # Rule: Content edits while in REVIEW_READY status reset the advisory status back to DRAFT
            if stored.status == "REVIEW_READY":
                updated_dict["status"] = "DRAFT"

            updated_dict["version"] = stored.version + 1
            updated_dict["updated_at"] = now_iso

            new_record = FarmerAdvisoryRecord(**updated_dict)
            self._advisories[advisory_id] = new_record
            return new_record.model_copy(deep=True)

    def update_status(
        self,
        advisory_id: str,
        expected_version: int,
        new_status: str,
        approved_by: Optional[str] = None,
        approved_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> FarmerAdvisoryRecord:
        with self._lock:
            stored = self._advisories.get(advisory_id)
            if not stored:
                raise KeyError(f"Advisory record with ID '{advisory_id}' not found.")

            valid_statuses = {"DRAFT", "REVIEW_READY", "APPROVED", "CANCELLED"}
            status_upper = new_status.upper()
            if status_upper not in valid_statuses:
                raise ValueError(f"Invalid status '{new_status}'. Allowed: {valid_statuses}")

            if stored.status == "CANCELLED":
                raise ValueError("Cancelled advisories cannot undergo status transitions.")
            if stored.status == "APPROVED" and status_upper == "APPROVED":
                raise ValueError("Advisory is already APPROVED.")
            if stored.status == "APPROVED" and status_upper != "CANCELLED":
                raise ValueError("Approved advisories are immutable and can only be cancelled.")
            if stored.status == "DRAFT" and status_upper == "APPROVED":
                raise ValueError("Direct approval from DRAFT status is forbidden. Advisory must be in REVIEW_READY status to be approved.")

            if stored.version != expected_version:
                raise ValueError(
                    f"Optimistic lock conflict for advisory '{advisory_id}': "
                    f"Expected version {expected_version}, but stored version is {stored.version}."
                )

            now_iso = updated_at or datetime.now(timezone.utc).isoformat()
            updated_dict = stored.model_dump()
            updated_dict["status"] = status_upper
            updated_dict["version"] = stored.version + 1
            updated_dict["updated_at"] = now_iso

            if status_upper == "APPROVED":
                if not approved_by:
                    raise ValueError("Field 'approved_by' is required when approving an advisory.")
                updated_dict["approved_by"] = approved_by
                updated_dict["approved_at"] = approved_at or now_iso

            new_record = FarmerAdvisoryRecord(**updated_dict)
            self._advisories[advisory_id] = new_record
            return new_record.model_copy(deep=True)
