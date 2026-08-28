import threading
from typing import List, Optional

import pymongo
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from components.risk_forecasting.integrations.vet_directory import (
    VeterinaryOfficerDirectory,
    VeterinaryOfficerSummary,
)
from core.database import MONGODB_URL, MONGODB_DB_NAME

class MongoVeterinaryOfficerDirectory(VeterinaryOfficerDirectory):
    """
    Synchronous MongoDB adapter for VeterinaryOfficerDirectory.
    Provides read-only queries against the live adrs_core.vets collection.
    Converts MongoDB _id to string for the canonical vet_id.
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
            self.collection = self.db["vets"]

    def _init_indexes_once(self):
        if self._indexes_initialized:
            return

        with self._lock:
            if self._indexes_initialized:
                return
            try:
                # We can create read indexes safely if needed, but for now just mark as initialized
                # We don't want to modify production collections unnecessarily.
                self._indexes_initialized = True
            except PyMongoError as e:
                raise RuntimeError("Veterinary Officer directory is temporarily unavailable.") from e

    def _normalize_district(self, district: str) -> str:
        formatted = district.strip().title()
        if formatted in ["Moneragala", "Monaragala"]:
            return "Monaragala"
        elif formatted in ["Nuwaraeliya", "Nuwara Eliya"]:
            return "Nuwara Eliya"
        return formatted

    def _to_summary(self, doc: dict) -> Optional[VeterinaryOfficerSummary]:
        if not doc:
            return None
            
        role = str(doc.get("role", "")).strip().lower()
        # Exclude DAPH, Farmer, SYSTEM and any non-vet roles
        if role != "vet":
            return None
            
        vet_id = str(doc.get("_id", ""))
        if not vet_id:
            return None
            
        display_name = str(doc.get("full_name") or doc.get("email") or "Unknown Officer").strip()
        
        district_raw = doc.get("district")
        assigned_districts = []
        if district_raw and isinstance(district_raw, str):
            assigned_districts.append(self._normalize_district(district_raw))
            
        return VeterinaryOfficerSummary(
            vet_id=vet_id,
            display_name=display_name,
            assigned_districts=assigned_districts,
            active=True
        )

    def get_vet(self, vet_id: str) -> Optional[VeterinaryOfficerSummary]:
        self._init_indexes_once()
        if not vet_id or not vet_id.strip():
            return None
            
        from bson.objectid import ObjectId
        from bson.errors import InvalidId
        try:
            obj_id = ObjectId(vet_id.strip())
        except InvalidId:
            return None

        try:
            doc = self.collection.find_one({"_id": obj_id, "role": "vet"})
            return self._to_summary(doc)
        except PyMongoError as e:
            raise RuntimeError("Veterinary Officer directory is temporarily unavailable.") from e

    def list_vets_by_district(self, district: str) -> List[VeterinaryOfficerSummary]:
        self._init_indexes_once()
        if not district or not district.strip():
            return []
            
        norm_dist = self._normalize_district(district)
        
        # In adrs_core.vets, district is stored as a string field.
        # We query for both normalized and unnormalized matches just in case.
        district_query = {
            "$in": [
                norm_dist,
                district.strip(),
                district.strip().title(),
                "Moneragala" if norm_dist == "Monaragala" else norm_dist,
                "Monaragala" if norm_dist == "Moneragala" else norm_dist,
                "Nuwaraeliya" if norm_dist == "Nuwara Eliya" else norm_dist,
                "Nuwara Eliya" if norm_dist == "Nuwaraeliya" else norm_dist
            ]
        }
        
        try:
            cursor = self.collection.find({"role": "vet", "district": district_query})
            # Deterministic ordering by _id
            cursor = cursor.sort("_id", pymongo.ASCENDING)
            results = []
            for doc in cursor:
                summary = self._to_summary(doc)
                if summary:
                    results.append(summary)
            return results
        except PyMongoError as e:
            raise RuntimeError("Veterinary Officer directory is temporarily unavailable.") from e

    def is_vet_assigned_to_district(self, vet_id: str, district: str) -> bool:
        vet = self.get_vet(vet_id)
        if not vet or not vet.active:
            return False
        norm_dist = self._normalize_district(district)
        return norm_dist in [self._normalize_district(d) for d in vet.assigned_districts]
