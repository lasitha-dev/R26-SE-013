"""
Storage for SeasonalOutlookRecord (collection `forecast_outlooks`).

Safety rules (contract section 6):
- Reading never creates a collection or an index. `ensure_indexes()` is a separate, explicit step that is only
  run in an approved phase.
- The Mongo adapter does not open a connection until the first operation.
- Only `status` and `replaces_outlook_id` may change after issuance (void / correct); content never does.
"""

import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from components.risk_forecasting.schemas import SeasonalOutlookRecord

COLLECTION_NAME = "forecast_outlooks"


class OutlookRepository(ABC):
    @abstractmethod
    def save(self, record: SeasonalOutlookRecord) -> SeasonalOutlookRecord: ...

    @abstractmethod
    def get_by_key(self, idempotency_key: str) -> Optional[SeasonalOutlookRecord]: ...

    @abstractmethod
    def list(self, disease: Optional[str] = None, district: Optional[str] = None,
             target_year: Optional[int] = None, target_month: Optional[int] = None,
             limit: int = 50, offset: int = 0) -> Tuple[List[SeasonalOutlookRecord], int]: ...

    @abstractmethod
    def set_status(self, outlook_id: str, status: str) -> SeasonalOutlookRecord: ...

    def ensure_indexes(self) -> None:  # explicit, approved step only
        return None


def _matches(record: SeasonalOutlookRecord, disease, district, target_year, target_month) -> bool:
    return ((disease is None or record.disease == disease)
            and (district is None or record.district.lower() == district.lower())
            and (target_year is None or record.target_year == target_year)
            and (target_month is None or record.target_month == target_month))


class InMemoryOutlookRepository(OutlookRepository):
    def __init__(self):
        self._lock = threading.Lock()
        self._by_id: Dict[str, SeasonalOutlookRecord] = {}

    def save(self, record):
        with self._lock:
            if any(r.idempotency_key == record.idempotency_key and r.status == "ACTIVE" for r in self._by_id.values()):
                raise ValueError("An active outlook already exists for this key.")
            self._by_id[record.outlook_id] = record
            return record

    def get_by_key(self, idempotency_key):
        with self._lock:
            active = [r for r in self._by_id.values() if r.idempotency_key == idempotency_key and r.status == "ACTIVE"]
            return active[0] if active else None

    def list(self, disease=None, district=None, target_year=None, target_month=None, limit=50, offset=0):
        with self._lock:
            rows = sorted((r for r in self._by_id.values() if _matches(r, disease, district, target_year, target_month)),
                          key=lambda r: (r.target_year, r.target_month, r.disease, r.district, r.outlook_id))
            return rows[offset:offset + limit], len(rows)

    def set_status(self, outlook_id, status):
        with self._lock:
            record = self._by_id[outlook_id]
            self._by_id[outlook_id] = record.model_copy(update={"status": status})
            return self._by_id[outlook_id]


class MongoOutlookRepository(OutlookRepository):
    """Synchronous MongoDB adapter. Constructing it performs no I/O (no connection, no index, no collection)."""

    def __init__(self, collection=None):
        self._collection = collection

    @property
    def collection(self):
        if self._collection is None:
            from pymongo import MongoClient
            from core.database import MONGODB_URL, MONGODB_DB_NAME
            client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000, connect=False)
            self._collection = client[MONGODB_DB_NAME][COLLECTION_NAME]
        return self._collection

    @staticmethod
    def _to_document(record: SeasonalOutlookRecord) -> dict:
        document = record.model_dump(exclude={"probability_pct"})  # the percentage is derived, never stored
        document["_id"] = document["outlook_id"]
        return document

    @staticmethod
    def _from_document(document: dict) -> SeasonalOutlookRecord:
        document = dict(document)
        document.pop("_id", None)
        document.pop("probability_pct", None)
        return SeasonalOutlookRecord(**document)

    def save(self, record):
        from pymongo.errors import PyMongoError
        try:
            self.collection.insert_one(self._to_document(record))
        except PyMongoError as exc:
            raise RuntimeError("Outlook storage is temporarily unavailable.") from exc
        return record

    def get_by_key(self, idempotency_key):
        from pymongo.errors import PyMongoError
        try:
            document = self.collection.find_one({"idempotency_key": idempotency_key, "status": "ACTIVE"})
        except PyMongoError as exc:
            raise RuntimeError("Outlook storage is temporarily unavailable.") from exc
        return self._from_document(document) if document else None

    def list(self, disease=None, district=None, target_year=None, target_month=None, limit=50, offset=0):
        from pymongo.errors import PyMongoError
        query = {k: v for k, v in (("disease", disease), ("district", district),
                                   ("target_year", target_year), ("target_month", target_month)) if v is not None}
        try:
            total = self.collection.count_documents(query)
            cursor = (self.collection.find(query)
                      .sort([("target_year", 1), ("target_month", 1), ("disease", 1), ("district", 1)])
                      .skip(offset).limit(limit))
            return [self._from_document(d) for d in cursor], total
        except PyMongoError as exc:
            raise RuntimeError("Outlook storage is temporarily unavailable.") from exc

    def set_status(self, outlook_id, status):
        from pymongo.errors import PyMongoError
        try:
            document = self.collection.find_one_and_update({"_id": outlook_id}, {"$set": {"status": status}},
                                                           return_document=True)
        except PyMongoError as exc:
            raise RuntimeError("Outlook storage is temporarily unavailable.") from exc
        if not document:
            raise KeyError(outlook_id)
        return self._from_document(document)

    def ensure_indexes(self):
        """Creates the collection's indexes. Run only in the approved initialisation phase."""
        from pymongo.errors import PyMongoError
        try:
            self.collection.create_index(
                [("idempotency_key", 1)], unique=True, name="outlook_active_key_unique",
                partialFilterExpression={"status": "ACTIVE"})
            self.collection.create_index([("target_year", 1), ("target_month", 1), ("disease", 1), ("district", 1)],
                                         name="outlook_target_lookup")
        except PyMongoError as exc:
            raise RuntimeError("Outlook storage is temporarily unavailable.") from exc
