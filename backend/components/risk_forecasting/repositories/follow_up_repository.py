"""
Forecast-Linked DAPH–Vet Follow-Up Repository Abstraction & In-Memory Implementation.

Provides a thread-safe repository contract for persisting and querying ForecastFollowUpRecord instances.

NOTE ON DURABILITY:
InMemoryFollowUpRepository is non-durable across process restarts. In production deployments,
this interface will be backed by a relational/document database adapter.
"""

from abc import ABC, abstractmethod
import threading
from typing import Dict, List, Optional, Tuple

from backend.components.risk_forecasting.schemas import ForecastFollowUpRecord


class FollowUpRepository(ABC):
    """Abstract Repository Interface for Forecast Follow-Up Records."""

    @abstractmethod
    def save(self, record: ForecastFollowUpRecord) -> ForecastFollowUpRecord:
        """Persists a new follow-up record."""
        pass

    @abstractmethod
    def get_by_id(self, follow_up_id: str) -> Optional[ForecastFollowUpRecord]:
        """Retrieves a follow-up record by ID."""
        pass

    @abstractmethod
    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[ForecastFollowUpRecord]:
        """Finds an existing record by client idempotency key."""
        pass

    @abstractmethod
    def list(
        self,
        forecast_id: Optional[str] = None,
        district: Optional[str] = None,
        disease: Optional[str] = None,
        assigned_vet_id: Optional[str] = None,
        issued_by_daph_id: Optional[str] = None,
        status: Optional[str] = None,
        target_year: Optional[int] = None,
        target_month: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ForecastFollowUpRecord], int]:
        """Queries stored follow-up records with bounded filters and pagination."""
        pass

    @abstractmethod
    def update_record(self, record: ForecastFollowUpRecord) -> ForecastFollowUpRecord:
        """Updates an existing follow-up record."""
        pass


class InMemoryFollowUpRepository(FollowUpRepository):
    """
    Thread-safe in-memory implementation of FollowUpRepository with defensive deep copies.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._records: Dict[str, ForecastFollowUpRecord] = {}
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> follow_up_id

    def save(self, record: ForecastFollowUpRecord) -> ForecastFollowUpRecord:
        with self._lock:
            if record.follow_up_id in self._records:
                raise ValueError(f"Follow-up record with ID '{record.follow_up_id}' already exists.")

            if record.idempotency_key:
                if record.idempotency_key in self._idempotency_index:
                    existing_id = self._idempotency_index[record.idempotency_key]
                    return self._records[existing_id].model_copy(deep=True)

            stored = record.model_copy(deep=True)
            self._records[record.follow_up_id] = stored
            if record.idempotency_key:
                self._idempotency_index[record.idempotency_key] = record.follow_up_id

            return stored.model_copy(deep=True)

    def get_by_id(self, follow_up_id: str) -> Optional[ForecastFollowUpRecord]:
        with self._lock:
            record = self._records.get(follow_up_id)
            return record.model_copy(deep=True) if record else None

    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[ForecastFollowUpRecord]:
        with self._lock:
            follow_up_id = self._idempotency_index.get(idempotency_key)
            if follow_up_id:
                record = self._records.get(follow_up_id)
                return record.model_copy(deep=True) if record else None
            return None

    def list(
        self,
        forecast_id: Optional[str] = None,
        district: Optional[str] = None,
        disease: Optional[str] = None,
        assigned_vet_id: Optional[str] = None,
        issued_by_daph_id: Optional[str] = None,
        status: Optional[str] = None,
        target_year: Optional[int] = None,
        target_month: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ForecastFollowUpRecord], int]:
        with self._lock:
            filtered = list(self._records.values())

            if forecast_id:
                filtered = [r for r in filtered if r.forecast_id == forecast_id]

            if district:
                dist_title = district.strip().title()
                if dist_title in ["Moneragala", "Monaragala"]:
                    dist_title = "Monaragala"
                elif dist_title in ["Nuwaraeliya", "Nuwara Eliya"]:
                    dist_title = "Nuwara Eliya"
                filtered = [r for r in filtered if r.district == dist_title]

            if disease:
                disease_upper = disease.strip().upper()
                filtered = [r for r in filtered if r.disease == disease_upper]

            if assigned_vet_id:
                filtered = [r for r in filtered if r.assigned_vet_id == assigned_vet_id.strip()]

            if issued_by_daph_id:
                filtered = [r for r in filtered if r.issued_by_daph_id == issued_by_daph_id.strip()]

            if status:
                status_upper = status.strip().upper()
                filtered = [r for r in filtered if r.status == status_upper]

            if target_year is not None:
                filtered = [r for r in filtered if r.target_year == target_year]

            if target_month is not None:
                filtered = [r for r in filtered if r.target_month == target_month]

            # Sort by created_at descending
            filtered.sort(key=lambda r: r.created_at, reverse=True)

            total_count = len(filtered)
            bounded_limit = min(max(1, limit), 200)
            bounded_offset = max(0, offset)

            paginated = [r.model_copy(deep=True) for r in filtered[bounded_offset : bounded_offset + bounded_limit]]

            return paginated, total_count

    def update_record(self, record: ForecastFollowUpRecord) -> ForecastFollowUpRecord:
        with self._lock:
            if record.follow_up_id not in self._records:
                raise KeyError(f"Follow-up record with ID '{record.follow_up_id}' not found.")

            stored = record.model_copy(deep=True)
            self._records[record.follow_up_id] = stored
            return stored.model_copy(deep=True)
