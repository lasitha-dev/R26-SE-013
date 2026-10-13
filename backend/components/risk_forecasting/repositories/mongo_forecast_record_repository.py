from datetime import datetime, timezone
import threading
from typing import Dict, List, Optional, Tuple

import pymongo
from pymongo import MongoClient
from pymongo.errors import PyMongoError, DuplicateKeyError

from components.risk_forecasting.repositories.forecast_record_repository import ForecastRecordRepository
from components.risk_forecasting.schemas import ForecastDecisionRecord
from core.database import MONGODB_URL, MONGODB_DB_NAME

class MongoForecastRecordRepository(ForecastRecordRepository):
    """
    Synchronous MongoDB adapter for ForecastDecisionRecord storage.
    Satisfies exactly the existing thread-safe repository contract while persisting
    immutable prediction records to Atlas without blocking the async event loop (as it runs
    in FastAPI's threadpool during def route execution).
    """

    def __init__(self, client: Optional[MongoClient] = None, collection: Optional[pymongo.collection.Collection] = None):
        self._lock = threading.Lock()
        self._indexes_initialized = False
        
        if collection is not None:
            self.collection = collection
        else:
            if client is None:
                # connect=False defers network connection until first operation
                self.client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=2000, connect=False)
            else:
                self.client = client
            self.db = self.client[MONGODB_DB_NAME]
            self.collection = self.db["forecast_records"]

    def _init_indexes_once(self):
        if self._indexes_initialized:
            return
            
        with self._lock:
            if self._indexes_initialized:
                return
            try:
                self.collection.create_index(
                    [("idempotency_key", 1)],
                    unique=True,
                    partialFilterExpression={"idempotency_key": {"$type": "string"}},
                    name="idempotency_key_1"
                )
                # 2. Compound read index based on current list filters and sorting
                self.collection.create_index([
                    ("district", pymongo.ASCENDING),
                    ("disease", pymongo.ASCENDING),
                    ("target_year", pymongo.DESCENDING),
                    ("target_month", pymongo.DESCENDING),
                    ("created_at", pymongo.DESCENDING)
                ])
                self._indexes_initialized = True
            except PyMongoError as e:
                raise RuntimeError("Forecast record storage is temporarily unavailable.") from e

    def _to_bson(self, record: ForecastDecisionRecord) -> dict:
        """Serializes the flat domain model into a BSON document."""
        data = record.model_dump()
        # Enforce string forecast_id as _id
        data["_id"] = record.forecast_id
        if data.get("idempotency_key") is None:
            data.pop("idempotency_key", None)
        
        # Ensure enums remain strings (model_dump does this for string enums)
        
        # Convert ISO strings to timezone-aware BSON datetimes for accurate Mongo sorting
        def parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
            if not dt_str:
                return None
            try:
                # Handle Python 3.10+ fromisoformat with Z
                if dt_str.endswith('Z'):
                    dt_str = dt_str[:-1] + '+00:00'
                return datetime.fromisoformat(dt_str)
            except ValueError:
                return None

        data["generated_at"] = parse_iso(data.get("generated_at"))
        data["created_at"] = parse_iso(data.get("created_at"))
        data["updated_at"] = parse_iso(data.get("updated_at"))
        
        return data

    def _to_model(self, data: dict) -> ForecastDecisionRecord:
        """Deserializes a BSON document exactly into the ForecastDecisionRecord domain model."""
        data.pop("_id", None)
        
        # Pydantic V2 can validate datetime objects directly into fields typed as str (or datetime),
        # but for absolute strictness to match InMemory behavior, convert back to ISO strings.
        def to_iso(dt_obj) -> Optional[str]:
            if not dt_obj:
                return None
            if isinstance(dt_obj, datetime):
                # Ensure UTC timezone if naive
                if dt_obj.tzinfo is None:
                    dt_obj = dt_obj.replace(tzinfo=timezone.utc)
                return dt_obj.isoformat()
            return str(dt_obj)

        if "generated_at" in data and isinstance(data["generated_at"], datetime):
            data["generated_at"] = to_iso(data["generated_at"])
        if "created_at" in data and isinstance(data["created_at"], datetime):
            data["created_at"] = to_iso(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], datetime):
            data["updated_at"] = to_iso(data["updated_at"])

        return ForecastDecisionRecord.model_validate(data)

    def save(self, record: ForecastDecisionRecord) -> ForecastDecisionRecord:
        self._init_indexes_once()
        try:
            bson_data = self._to_bson(record)
            self.collection.insert_one(bson_data)
            return record.model_copy(deep=True)
        except DuplicateKeyError as e:
            if "idempotency_key" in str(e):
                # Check if it's an idempotency collision
                existing = self.find_by_idempotency_key(record.idempotency_key)
                if existing:
                    # In InMemory repository, it returns the existing record copy on idempotent collision
                    # but only if requested via generate_record (which handles idempotency logic).
                    # Actually, the InMemory repo directly returns the copy in save!
                    return existing
            elif "_id" in str(e):
                raise ValueError(f"Forecast record with ID '{record.forecast_id}' already exists.")
            raise RuntimeError("Forecast record storage is temporarily unavailable.") from e
        except PyMongoError as e:
            raise RuntimeError("Forecast record storage is temporarily unavailable.") from e

    def get_by_id(self, forecast_id: str) -> Optional[ForecastDecisionRecord]:
        try:
            doc = self.collection.find_one({"_id": forecast_id})
            if not doc:
                return None
            return self._to_model(doc)
        except PyMongoError as e:
            raise RuntimeError("Forecast record storage is temporarily unavailable.") from e

    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[ForecastDecisionRecord]:
        if not idempotency_key:
            return None
        try:
            doc = self.collection.find_one({"idempotency_key": idempotency_key})
            if not doc:
                return None
            return self._to_model(doc)
        except PyMongoError as e:
            raise RuntimeError("Forecast record storage is temporarily unavailable.") from e

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
        query = {}
        if disease:
            query["disease"] = disease.upper()
        if district:
            dist_title = district.strip().title()
            if dist_title in ["Moneragala", "Monaragala"]:
                dist_title = "Monaragala"
            elif dist_title in ["Nuwaraeliya", "Nuwara Eliya"]:
                dist_title = "Nuwara Eliya"
            query["district"] = dist_title
        if target_year is not None:
            query["target_year"] = target_year
        if target_month is not None:
            query["target_month"] = target_month
        if status:
            query["status"] = status.upper()

        try:
            total_count = self.collection.count_documents(query)
            # InMemory repo sorts by created_at DESC
            cursor = self.collection.find(query).sort("created_at", pymongo.DESCENDING).skip(offset).limit(limit)
            records = [self._to_model(doc) for doc in cursor]
            return records, total_count
        except PyMongoError as e:
            raise RuntimeError("Forecast record storage is temporarily unavailable.") from e

    def update_status(self, forecast_id: str, new_status: str) -> Optional[ForecastDecisionRecord]:
        valid_statuses = {"GENERATED", "AVAILABLE", "REFERENCED", "SUPERSEDED"}
        status_upper = new_status.upper()
        if status_upper not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Allowed: {valid_statuses}")

        now_iso = datetime.now(timezone.utc).isoformat()
        now_dt = datetime.fromisoformat(now_iso)

        try:
            result = self.collection.find_one_and_update(
                {"_id": forecast_id},
                {"$set": {"status": status_upper, "updated_at": now_dt}},
                return_document=pymongo.ReturnDocument.AFTER
            )
            if not result:
                return None
            return self._to_model(result)
        except PyMongoError as e:
            raise RuntimeError("Forecast record storage is temporarily unavailable.") from e
