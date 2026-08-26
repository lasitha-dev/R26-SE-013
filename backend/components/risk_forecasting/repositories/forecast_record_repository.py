"""
Forecast Record Repository Abstraction & In-Memory Implementation.

Provides a thread-safe repository contract for storing and querying immutable
ForecastDecisionRecord instances.

NOTE ON DURABILITY:
The InMemoryForecastRecordRepository provides a thread-safe in-memory store suitable
for component-local standalone execution, testing, and microservice evaluation.
It is NON-DURABLE and does not persist records across application process restarts.
In production deployments, this repository interface can be replaced with a database-backed
adapter (e.g. MongoDB, PostgreSQL) without altering the service layer or model inference logic.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

from backend.components.risk_forecasting.schemas import ForecastDecisionRecord


class ForecastRecordRepository(ABC):
    """Abstract Repository Interface for Forecast Decision Records."""

    @abstractmethod
    def save(self, record: ForecastDecisionRecord) -> ForecastDecisionRecord:
        """Persists a new forecast decision record."""
        pass

    @abstractmethod
    def get_by_id(self, forecast_id: str) -> Optional[ForecastDecisionRecord]:
        """Retrieves a record by its unique forecast_id."""
        pass

    @abstractmethod
    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[ForecastDecisionRecord]:
        """Finds an existing record by client idempotency key."""
        pass

    @abstractmethod
    def list(
        self,
        disease: Optional[str] = None,
        district: Optional[str] = None,
        target_year: Optional[int] = None,
        target_month: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[ForecastDecisionRecord], int]:
        """Queries stored records with bounded filters and pagination."""
        pass

    @abstractmethod
    def update_status(self, forecast_id: str, new_status: str) -> Optional[ForecastDecisionRecord]:
        """
        Updates lifecycle status metadata of a record.
        IMMUTABILITY GUARANTEE: Scientific prediction values (probability, risk_level, severity)
        are immutable and cannot be altered by status updates.
        """
        pass


class InMemoryForecastRecordRepository(ForecastRecordRepository):
    """
    Thread-safe in-memory implementation of ForecastRecordRepository.

    LIMITATION: Non-durable across process restarts.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._records: Dict[str, ForecastDecisionRecord] = {}
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> forecast_id

    def save(self, record: ForecastDecisionRecord) -> ForecastDecisionRecord:
        with self._lock:
            # Enforce unique forecast_id
            if record.forecast_id in self._records:
                raise ValueError(f"Forecast record with ID '{record.forecast_id}' already exists.")

            # Enforce unique idempotency_key indexing if present
            if record.idempotency_key:
                if record.idempotency_key in self._idempotency_index:
                    existing_id = self._idempotency_index[record.idempotency_key]
                    return self._records[existing_id].model_copy(deep=True)

            stored = record.model_copy(deep=True)
            self._records[record.forecast_id] = stored
            if record.idempotency_key:
                self._idempotency_index[record.idempotency_key] = record.forecast_id

            return stored.model_copy(deep=True)

    def get_by_id(self, forecast_id: str) -> Optional[ForecastDecisionRecord]:
        with self._lock:
            record = self._records.get(forecast_id)
            return record.model_copy(deep=True) if record else None

    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[ForecastDecisionRecord]:
        with self._lock:
            forecast_id = self._idempotency_index.get(idempotency_key)
            if forecast_id:
                record = self._records.get(forecast_id)
                return record.model_copy(deep=True) if record else None
            return None

    def list(
        self,
        disease: Optional[str] = None,
        district: Optional[str] = None,
        target_year: Optional[int] = None,
        target_month: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[ForecastDecisionRecord], int]:
        with self._lock:
            filtered = list(self._records.values())

            if disease:
                disease_upper = disease.upper()
                filtered = [r for r in filtered if r.disease == disease_upper]

            if district:
                dist_title = district.strip().title()
                if dist_title in ["Moneragala", "Monaragala"]:
                    dist_title = "Monaragala"
                elif dist_title in ["Nuwaraeliya", "Nuwara Eliya"]:
                    dist_title = "Nuwara Eliya"
                filtered = [r for r in filtered if r.district == dist_title]

            if target_year is not None:
                filtered = [r for r in filtered if r.target_year == target_year]

            if target_month is not None:
                filtered = [r for r in filtered if r.target_month == target_month]

            if status:
                status_upper = status.upper()
                filtered = [r for r in filtered if r.status == status_upper]

            # Sort by created_at descending
            filtered.sort(key=lambda r: r.created_at, reverse=True)

            total_count = len(filtered)
            paginated = [r.model_copy(deep=True) for r in filtered[offset : offset + limit]]

            return paginated, total_count

    def update_status(self, forecast_id: str, new_status: str) -> Optional[ForecastDecisionRecord]:
        with self._lock:
            record = self._records.get(forecast_id)
            if not record:
                return None

            valid_statuses = {"GENERATED", "AVAILABLE", "REFERENCED", "SUPERSEDED"}
            status_upper = new_status.upper()
            if status_upper not in valid_statuses:
                raise ValueError(f"Invalid status '{new_status}'. Allowed: {valid_statuses}")

            now_iso = datetime.now(timezone.utc).isoformat()

            # Construct updated record preserving exact scientific prediction fields
            updated_dict = record.model_dump()
            updated_dict["status"] = status_upper
            updated_dict["updated_at"] = now_iso

            updated_record = ForecastDecisionRecord(**updated_dict)
            self._records[forecast_id] = updated_record
            return updated_record.model_copy(deep=True)
