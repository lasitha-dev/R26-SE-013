"""
MongoDB implementation of FollowUpRepository.
"""
import os
from typing import List, Optional, Tuple
import pymongo
from components.risk_forecasting.repositories.follow_up_repository import FollowUpRepository
from components.risk_forecasting.schemas import ForecastFollowUpRecord

class MongoFollowUpRepository(FollowUpRepository):
    def __init__(self):
        mongodb_url = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017")
        db_name = os.getenv("MONGODB_DB_NAME", "adrs_core")
        self.client = pymongo.MongoClient(mongodb_url)
        self.collection = self.client[db_name].forecast_follow_ups

    def save(self, record: ForecastFollowUpRecord) -> ForecastFollowUpRecord:
        doc = record.model_dump()
        doc["_id"] = doc["follow_up_id"]
        
        if record.idempotency_key:
            existing = self.collection.find_one({"idempotency_key": record.idempotency_key})
            if existing:
                return ForecastFollowUpRecord(**existing)
                
        try:
            self.collection.insert_one(doc)
            return record
        except Exception as e:
            if "duplicate key error" in str(e).lower():
                raise ValueError(f"Follow-up record with ID '{record.follow_up_id}' already exists.")
            raise

    def get_by_id(self, follow_up_id: str) -> Optional[ForecastFollowUpRecord]:
        doc = self.collection.find_one({"_id": follow_up_id})
        return ForecastFollowUpRecord(**doc) if doc else None

    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[ForecastFollowUpRecord]:
        doc = self.collection.find_one({"idempotency_key": idempotency_key})
        return ForecastFollowUpRecord(**doc) if doc else None

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
        query = {}
        if forecast_id:
            query["forecast_id"] = forecast_id
        if district:
            dist_title = district.strip().title()
            if dist_title in ["Moneragala", "Monaragala"]:
                dist_title = "Monaragala"
            elif dist_title in ["Nuwaraeliya", "Nuwara Eliya"]:
                dist_title = "Nuwara Eliya"
            query["district"] = dist_title
        if disease:
            query["disease"] = disease.strip().upper()
        if assigned_vet_id:
            query["assigned_vet_id"] = assigned_vet_id.strip()
        if issued_by_daph_id:
            query["issued_by_daph_id"] = issued_by_daph_id.strip()
        if status:
            query["status"] = status.strip().upper()
        if target_year is not None:
            query["target_year"] = target_year
        if target_month is not None:
            query["target_month"] = target_month

        total_count = self.collection.count_documents(query)
        bounded_limit = min(max(1, limit), 200)
        bounded_offset = max(0, offset)
        
        cursor = self.collection.find(query).sort("created_at", -1).skip(bounded_offset).limit(bounded_limit)
        
        results = []
        for doc in cursor:
            results.append(ForecastFollowUpRecord(**doc))
            
        return results, total_count

    def update_record(self, record: ForecastFollowUpRecord) -> ForecastFollowUpRecord:
        doc = record.model_dump()
        result = self.collection.find_one_and_replace(
            {"_id": record.follow_up_id},
            doc,
            return_document=pymongo.ReturnDocument.AFTER
        )
        if not result:
            raise KeyError(f"Follow-up record with ID '{record.follow_up_id}' not found.")
            
        return ForecastFollowUpRecord(**result)
