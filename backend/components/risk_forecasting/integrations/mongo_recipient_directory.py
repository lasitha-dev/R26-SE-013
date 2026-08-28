import threading
from typing import List, Optional

import pymongo
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId
from bson.errors import InvalidId

from components.risk_forecasting.integrations.recipient_directory import (
    RecipientDirectory,
    Recipient,
)
from core.database import MONGODB_URL, MONGODB_DB_NAME

class MongoRecipientDirectory(RecipientDirectory):
    """
    Synchronous MongoDB adapter for RecipientDirectory.
    Provides read-only queries against the live adrs_core.farms collection.
    Converts MongoDB _id to string for the canonical recipient_id.
    """

    def __init__(self, client: Optional[MongoClient] = None, collection: Optional[pymongo.collection.Collection] = None):
        self._lock = threading.Lock()
        self._indexes_initialized = False

        if collection is not None:
            self.collection = collection
        else:
            if client is None:
                self.client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=2000, connect=False)
            else:
                self.client = client
            self.db = self.client[MONGODB_DB_NAME]
            self.collection = self.db["farms"]

    def _init_indexes_once(self):
        if self._indexes_initialized:
            return

        with self._lock:
            if self._indexes_initialized:
                return
            try:
                self._indexes_initialized = True
            except PyMongoError as e:
                raise RuntimeError("Recipient directory is temporarily unavailable.") from e

    def list_assigned_recipients(
        self, vet_id: str, district: Optional[str] = None
    ) -> List[Recipient]:
        self._init_indexes_once()
        if not vet_id or not vet_id.strip():
            return []

        clean_vet_id = vet_id.strip()
        
        # Build query according to proven live schema for farm-vet assignment
        query: dict = {
            "$or": [
                {"assigned_vet_ids": clean_vet_id}
            ]
        }
        
        # We don't have vet's email here easily without querying vets,
        # but the assignment route /farms/assign-vet modifies assigned_vet_ids with vet_id.
        # We also might have email in assigned_vet_emails, but we don't have the vet email.
        # Assuming the vet_id is the primary assignment key used by list_assigned_recipients.

        if district:
            raw_district = district.strip()
            formatted = raw_district.title()
            if formatted in ["Moneragala", "Monaragala"]:
                formatted = "Monaragala"
            elif formatted in ["Nuwaraeliya", "Nuwara Eliya"]:
                formatted = "Nuwara Eliya"
            query["location_district"] = formatted

        try:
            cursor = self.collection.find(query)
            # Deterministic sorting by _id
            cursor = cursor.sort("_id", pymongo.ASCENDING)
            
            results = []
            seen = set()
            for doc in cursor:
                recipient_id = str(doc.get("_id", ""))
                if not recipient_id or recipient_id in seen:
                    continue
                    
                seen.add(recipient_id)
                recipient_name = str(doc.get("owner_name") or doc.get("email") or "Unknown Farm").strip()
                farm_district = str(doc.get("location_district", "")).strip()
                
                results.append(Recipient(
                    recipient_id=recipient_id,
                    recipient_name=recipient_name,
                    district=farm_district,
                    assigned_vet_id=clean_vet_id
                ))
            return results
        except PyMongoError as e:
            raise RuntimeError("Recipient directory is temporarily unavailable.") from e

    def resolve_recipients(
        self, recipient_ids: List[str], vet_id: str
    ) -> List[Recipient]:
        self._init_indexes_once()
        if not vet_id or not vet_id.strip() or not recipient_ids:
            return []
            
        clean_vet_id = vet_id.strip()
        
        clean_ids = []
        for rid in recipient_ids:
            try:
                clean_ids.append(ObjectId(rid.strip()))
            except InvalidId:
                continue

        if not clean_ids:
            return []

        query = {
            "_id": {"$in": clean_ids},
            "$or": [
                {"assigned_vet_ids": clean_vet_id}
            ]
        }

        try:
            cursor = self.collection.find(query)
            cursor = cursor.sort("_id", pymongo.ASCENDING)
            
            results = []
            seen = set()
            for doc in cursor:
                recipient_id = str(doc.get("_id", ""))
                if not recipient_id or recipient_id in seen:
                    continue
                    
                seen.add(recipient_id)
                recipient_name = str(doc.get("owner_name") or doc.get("email") or "Unknown Farm").strip()
                farm_district = str(doc.get("location_district", "")).strip()
                
                results.append(Recipient(
                    recipient_id=recipient_id,
                    recipient_name=recipient_name,
                    district=farm_district,
                    assigned_vet_id=clean_vet_id
                ))
            return results
        except PyMongoError as e:
            raise RuntimeError("Recipient directory is temporarily unavailable.") from e
