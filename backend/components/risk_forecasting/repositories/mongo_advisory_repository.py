"""
MongoDB implementation of AdvisoryRepository.
"""
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import pymongo

from components.risk_forecasting.repositories.advisory_repository import AdvisoryRepository
from components.risk_forecasting.schemas import FarmerAdvisoryRecord, PersonalizedOverride, RecipientSummary
from core.database import MONGODB_URL, MONGODB_DB_NAME

class MongoAdvisoryRepository(AdvisoryRepository):
    def __init__(self):
        self.client = pymongo.MongoClient(MONGODB_URL, serverSelectionTimeoutMS=2000, connect=False)
        self.collection = self.client[MONGODB_DB_NAME].forecast_advisories

    def save(self, advisory: FarmerAdvisoryRecord) -> FarmerAdvisoryRecord:
        doc = advisory.model_dump()
        doc["_id"] = doc["advisory_id"]
        
        # Check idempotency
        if advisory.idempotency_key:
            existing = self.collection.find_one({"idempotency_key": advisory.idempotency_key})
            if existing:
                return FarmerAdvisoryRecord(**existing)
                
        try:
            self.collection.insert_one(doc)
            return advisory
        except Exception as e:
            if "duplicate key error" in str(e).lower():
                raise ValueError(f"Advisory with ID '{advisory.advisory_id}' already exists.")
            raise

    def get_by_id(self, advisory_id: str) -> Optional[FarmerAdvisoryRecord]:
        doc = self.collection.find_one({"_id": advisory_id})
        return FarmerAdvisoryRecord(**doc) if doc else None

    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[FarmerAdvisoryRecord]:
        doc = self.collection.find_one({"idempotency_key": idempotency_key})
        return FarmerAdvisoryRecord(**doc) if doc else None

    def list(
        self,
        forecast_id: Optional[str] = None,
        disease: Optional[str] = None,
        district: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[FarmerAdvisoryRecord], int]:
        query = {}
        if forecast_id:
            query["forecast_id"] = forecast_id
        if disease:
            query["disease"] = disease.upper()
        if district:
            dist_title = district.strip().title()
            if dist_title in ["Moneragala", "Monaragala"]:
                dist_title = "Monaragala"
            elif dist_title in ["Nuwaraeliya", "Nuwara Eliya"]:
                dist_title = "Nuwara Eliya"
            query["district"] = dist_title
        if status:
            query["status"] = status.upper()

        total_count = self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("created_at", -1).skip(offset).limit(limit)
        
        results = []
        for doc in cursor:
            results.append(FarmerAdvisoryRecord(**doc))
            
        return results, total_count

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
        stored_doc = self.collection.find_one({"_id": advisory_id})
        if not stored_doc:
            raise KeyError(f"Advisory record with ID '{advisory_id}' not found.")
            
        stored = FarmerAdvisoryRecord(**stored_doc)
        
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
        
        update_fields = {}
        if recipient_scope is not None:
            update_fields["recipient_scope"] = recipient_scope
        if selected_recipient_ids is not None:
            update_fields["selected_recipient_ids"] = selected_recipient_ids
        if vet_custom_note is not None:
            update_fields["vet_custom_note"] = vet_custom_note
        if personalized_overrides is not None:
            update_fields["personalized_overrides"] = [
                po.model_dump() if isinstance(po, PersonalizedOverride) else po
                for po in personalized_overrides
            ]
        if recipient_summary is not None:
            update_fields["recipient_summary"] = (
                recipient_summary.model_dump()
                if isinstance(recipient_summary, RecipientSummary)
                else recipient_summary
            )

        if stored.status == "REVIEW_READY":
            update_fields["status"] = "DRAFT"

        update_fields["version"] = stored.version + 1
        update_fields["updated_at"] = now_iso

        result = self.collection.find_one_and_update(
            {"_id": advisory_id, "version": expected_version},
            {"$set": update_fields},
            return_document=pymongo.ReturnDocument.AFTER
        )
        
        if not result:
            raise ValueError(
                f"Optimistic lock conflict for advisory '{advisory_id}': "
                f"Expected version {expected_version}, but stored version was different."
            )
            
        return FarmerAdvisoryRecord(**result)

    def update_status(
        self,
        advisory_id: str,
        expected_version: int,
        new_status: str,
        approved_by: Optional[str] = None,
        approved_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> FarmerAdvisoryRecord:
        stored_doc = self.collection.find_one({"_id": advisory_id})
        if not stored_doc:
            raise KeyError(f"Advisory record with ID '{advisory_id}' not found.")
            
        stored = FarmerAdvisoryRecord(**stored_doc)
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
        
        update_fields = {
            "status": status_upper,
            "version": stored.version + 1,
            "updated_at": now_iso
        }

        if status_upper == "APPROVED":
            if not approved_by:
                raise ValueError("Field 'approved_by' is required when approving an advisory.")
            update_fields["approved_by"] = approved_by
            update_fields["approved_at"] = approved_at or now_iso

        result = self.collection.find_one_and_update(
            {"_id": advisory_id, "version": expected_version},
            {"$set": update_fields},
            return_document=pymongo.ReturnDocument.AFTER
        )
        
        if not result:
            raise ValueError(
                f"Optimistic lock conflict for advisory '{advisory_id}': "
                f"Expected version {expected_version}, but stored version was different."
            )
            
        return FarmerAdvisoryRecord(**result)
