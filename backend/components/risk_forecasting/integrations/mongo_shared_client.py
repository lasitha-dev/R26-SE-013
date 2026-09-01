"""
MongoDB-backed SharedForecastDataClient implementation.
Aggregates verified diagnostic cases and death logs to compute district-wise outbreak status.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any
from bson import ObjectId

from core.database import db
from components.risk_forecasting.integrations.shared_forecast_client import (
    SharedForecastDataClient,
    SharedForecastRecord,
)
from components.risk_forecasting.config import SRI_LANKA_DISTRICTS

logger = logging.getLogger(__name__)

diagnostic_cases_collection = db.diagnostic_cases
death_logs_collection = db.death_logs
farms_collection = db.farms
cattles_collection = db.cattle


def _get_disease_name_regex(disease_upper: str) -> str:
    """Returns regex pattern matching disease name variants, display names, and acronyms."""
    if disease_upper == "FMD":
        return r"FMD|Foot[- ]?and[- ]?Mouth|foot_and_mouth"
    elif disease_upper == "LSD":
        return r"LSD|Lumpy[- ]?Skin|lumpy_skin|lumpy"
    return f"^{disease_upper}$"


def _district_matches(target_district: str, candidate_location: Optional[Any]) -> bool:
    """Case-insensitive substring match for farm location strings (handling coordinates, suffixes)."""
    if not target_district or not candidate_location:
        return False
    target_clean = target_district.strip().lower()
    candidate_clean = str(candidate_location).strip().lower()
    return target_clean in candidate_clean


class MongoSharedForecastClient(SharedForecastDataClient):
    """
    MongoDB-backed implementation of SharedForecastDataClient.
    Computes district-wise outbreak status by aggregating verified diagnostic cases
    and death logs from the live MongoDB collections.
    """

    def __init__(self, cache_ttl_seconds: int = 0):
        # Default cache_ttl_seconds is 0 so live queries always run against MongoDB instantly
        self._cache_ttl_seconds = cache_ttl_seconds
        # Maps cache_key -> (outbreak_status, cases_count, deaths_count, cached_timestamp)
        self._status_cache: Dict[str, Tuple[float, int, int, float]] = {}

    def _get_cache_key(self, disease: str, district: str, year: int, month: int) -> str:
        disease_upper = disease.strip().upper()
        formatted_district = district.strip().title()
        if formatted_district in ["Moneragala", "Monaragala"]:
            formatted_district = "Monaragala"
        elif formatted_district in ["Nuwaraeliya", "Nuwara Eliya"]:
            formatted_district = "Nuwara Eliya"
        return f"{disease_upper}|{formatted_district}|{year}|{month}"

    def _is_cache_valid(self, cached_at: float) -> bool:
        if self._cache_ttl_seconds <= 0:
            return False
        return (datetime.now(timezone.utc).timestamp() - cached_at) < self._cache_ttl_seconds

    async def get_district_status_async(
        self, disease: str, district: str, year: int, month: int
    ) -> Tuple[float, int, int]:
        """
        Retrieves the outbreak status, cases count, and deaths count for a specific month.
        Queries the DB directly.
        """
        cache_key = self._get_cache_key(disease, district, year, month)
        cached = self._status_cache.get(cache_key)
        if cached and self._is_cache_valid(cached[3]):
            return (cached[0], cached[1], cached[2])

        # Query Database
        disease_upper = disease.strip().upper()
        formatted_district = district.strip().title()
        if formatted_district in ["Moneragala", "Monaragala"]:
            formatted_district = "Monaragala"
        elif formatted_district in ["Nuwaraeliya", "Nuwara Eliya"]:
            formatted_district = "Nuwara Eliya"

        if formatted_district not in SRI_LANKA_DISTRICTS:
            return (0.0, 0, 0)

        # Date range for target month (both BSON ISODate and ISO string)
        start_dt = datetime(year, month, 1, 0, 0, 0)
        if month == 12:
            end_dt = datetime(year + 1, 1, 1, 0, 0, 0)
        else:
            end_dt = datetime(year, month + 1, 1, 0, 0, 0)

        start_date_str = start_dt.strftime("%Y-%m-%d")
        end_date_str = end_dt.strftime("%Y-%m-%d")

        disease_name_regex = _get_disease_name_regex(disease_upper)

        # Count verified diagnostic cases
        cases_count = 0
        case_query = {
            "verified": True,
            "disease_name": {"$regex": disease_name_regex, "$options": "i"},
            "$or": [
                {"created_at": {"$gte": start_dt, "$lt": end_dt}},
                {"verified_at": {"$gte": start_dt, "$lt": end_dt}},
                {"created_at": {"$gte": start_date_str, "$lt": end_date_str}},
                {"verified_at": {"$gte": start_date_str, "$lt": end_date_str}},
            ]
        }

        async for case in diagnostic_cases_collection.find(case_query):
            district_matched = False
            # Direct case district
            if case.get("district") and _district_matches(formatted_district, case.get("district")):
                district_matched = True

            # Resolve farm via farm_id
            farm_id = case.get("farm_id")
            if not district_matched and farm_id:
                farm = None
                try:
                    if isinstance(farm_id, ObjectId):
                        farm = await farms_collection.find_one({"_id": farm_id})
                    elif ObjectId.is_valid(str(farm_id)):
                        farm = await farms_collection.find_one({"_id": ObjectId(farm_id)})
                    else:
                        farm = await farms_collection.find_one({"_id": farm_id})
                except Exception:
                    farm = None

                if farm and _district_matches(formatted_district, farm.get("location_district") or farm.get("district")):
                    district_matched = True

            # Fallback: resolve farm via cattle_id
            if not district_matched and case.get("cattle_id") and ObjectId.is_valid(str(case.get("cattle_id"))):
                try:
                    cattle = await cattles_collection.find_one({"_id": ObjectId(str(case["cattle_id"]))})
                    if cattle and cattle.get("owner_email"):
                        farm = await farms_collection.find_one({"email": cattle["owner_email"]})
                        if farm and _district_matches(formatted_district, farm.get("location_district") or farm.get("district")):
                            district_matched = True
                except Exception:
                    pass

            if district_matched:
                cases_count += 1

        # Count death logs
        deaths_count = 0
        death_query = {
            "cause": {"$regex": disease_name_regex, "$options": "i"},
            "$or": [
                {"date_of_death": {"$gte": start_dt, "$lt": end_dt}},
                {"created_at": {"$gte": start_dt, "$lt": end_dt}},
                {"date_of_death": {"$gte": start_date_str, "$lt": end_date_str}},
                {"created_at": {"$gte": start_date_str, "$lt": end_date_str}},
            ]
        }

        async for death in death_logs_collection.find(death_query):
            death_district = death.get("district")
            if death_district and _district_matches(formatted_district, death_district):
                deaths_count += 1
            elif death.get("farm_id"):
                farm_id = death["farm_id"]
                farm = None
                try:
                    if isinstance(farm_id, ObjectId):
                        farm = await farms_collection.find_one({"_id": farm_id})
                    elif ObjectId.is_valid(str(farm_id)):
                        farm = await farms_collection.find_one({"_id": ObjectId(farm_id)})
                    else:
                        farm = await farms_collection.find_one({"_id": farm_id})
                except Exception:
                    farm = None
                if farm and _district_matches(formatted_district, farm.get("location_district") or farm.get("district")):
                    deaths_count += 1

        outbreak_status = 1.0 if (cases_count >= 1 or deaths_count >= 1) else 0.0

        # Update cache
        self._status_cache[cache_key] = (
            outbreak_status,
            cases_count,
            deaths_count,
            datetime.now(timezone.utc).timestamp()
        )

        return (outbreak_status, cases_count, deaths_count)

    def fetch_valid_lag1(
        self, disease: str, district: str, month: int, year: int
    ) -> Optional[Tuple[float, bool]]:
        """
        Retrieves ground-truth outbreak status for preceding month (t-1).
        Synchronous interface using PyMongo for runtime ML model execution.
        """
        if month == 1:
            target_year = year - 1
            target_month = 12
        else:
            target_year = year
            target_month = month - 1

        cache_key = self._get_cache_key(disease, district, target_year, target_month)
        cached = self._status_cache.get(cache_key)
        if cached and self._is_cache_valid(cached[3]):
            return (cached[0], True)

        try:
            import pymongo
            from bson import ObjectId
            from core.database import MONGODB_URL, MONGODB_DB_NAME

            disease_upper = disease.strip().upper()
            formatted_district = district.strip().title()
            if formatted_district in ["Moneragala", "Monaragala"]:
                formatted_district = "Monaragala"
            elif formatted_district in ["Nuwaraeliya", "Nuwara Eliya"]:
                formatted_district = "Nuwara Eliya"

            if formatted_district not in SRI_LANKA_DISTRICTS:
                return (0.0, True)

            start_dt = datetime(target_year, target_month, 1, 0, 0, 0)
            if target_month == 12:
                end_dt = datetime(target_year + 1, 1, 1, 0, 0, 0)
            else:
                end_dt = datetime(target_year, target_month + 1, 1, 0, 0, 0)

            start_date_str = start_dt.strftime("%Y-%m-%d")
            end_date_str = end_dt.strftime("%Y-%m-%d")

            disease_name_regex = _get_disease_name_regex(disease_upper)

            with pymongo.MongoClient(MONGODB_URL, serverSelectionTimeoutMS=2000) as client:
                sync_db = client.get_database(MONGODB_DB_NAME)
                diag_cases_coll = sync_db.get_collection("diagnostic_cases")
                sync_farms_coll = sync_db.get_collection("farms")
                sync_cattles_coll = sync_db.get_collection("cattle")
                sync_death_logs_coll = sync_db.get_collection("death_logs")

                cases_count = 0
                case_query = {
                    "verified": True,
                    "disease_name": {"$regex": disease_name_regex, "$options": "i"},
                    "$or": [
                        {"created_at": {"$gte": start_dt, "$lt": end_dt}},
                        {"verified_at": {"$gte": start_dt, "$lt": end_dt}},
                        {"created_at": {"$gte": start_date_str, "$lt": end_date_str}},
                        {"verified_at": {"$gte": start_date_str, "$lt": end_date_str}},
                    ]
                }

                for case in diag_cases_coll.find(case_query):
                    district_matched = False
                    if case.get("district") and _district_matches(formatted_district, case.get("district")):
                        district_matched = True

                    farm_id = case.get("farm_id")
                    if not district_matched and farm_id:
                        farm = None
                        try:
                            if isinstance(farm_id, ObjectId):
                                farm = sync_farms_coll.find_one({"_id": farm_id})
                            elif ObjectId.is_valid(str(farm_id)):
                                farm = sync_farms_coll.find_one({"_id": ObjectId(farm_id)})
                            else:
                                farm = sync_farms_coll.find_one({"_id": farm_id})
                        except Exception:
                            farm = None

                        if farm and _district_matches(formatted_district, farm.get("location_district") or farm.get("district")):
                            district_matched = True

                    if not district_matched and case.get("cattle_id") and ObjectId.is_valid(str(case.get("cattle_id"))):
                        try:
                            cattle = sync_cattles_coll.find_one({"_id": ObjectId(str(case["cattle_id"]))})
                            if cattle and cattle.get("owner_email"):
                                farm = sync_farms_coll.find_one({"email": cattle["owner_email"]})
                                if farm and _district_matches(formatted_district, farm.get("location_district") or farm.get("district")):
                                    district_matched = True
                        except Exception:
                            pass

                    if district_matched:
                        cases_count += 1

                # Count deaths
                deaths_count = 0
                death_query = {
                    "cause": {"$regex": disease_name_regex, "$options": "i"},
                    "$or": [
                        {"date_of_death": {"$gte": start_dt, "$lt": end_dt}},
                        {"created_at": {"$gte": start_dt, "$lt": end_dt}},
                        {"date_of_death": {"$gte": start_date_str, "$lt": end_date_str}},
                        {"created_at": {"$gte": start_date_str, "$lt": end_date_str}},
                    ]
                }

                for death in sync_death_logs_coll.find(death_query):
                    death_district = death.get("district")
                    if death_district and _district_matches(formatted_district, death_district):
                        deaths_count += 1
                    elif death.get("farm_id"):
                        farm_id = death["farm_id"]
                        farm = None
                        try:
                            if isinstance(farm_id, ObjectId):
                                farm = sync_farms_coll.find_one({"_id": farm_id})
                            elif ObjectId.is_valid(str(farm_id)):
                                farm = sync_farms_coll.find_one({"_id": ObjectId(farm_id)})
                            else:
                                farm = sync_farms_coll.find_one({"_id": farm_id})
                        except Exception:
                            farm = None
                        if farm and _district_matches(formatted_district, farm.get("location_district") or farm.get("district")):
                            deaths_count += 1

                outbreak_status = 1.0 if (cases_count >= 1 or deaths_count >= 1) else 0.0

                self._status_cache[cache_key] = (
                    outbreak_status,
                    cases_count,
                    deaths_count,
                    datetime.now(timezone.utc).timestamp()
                )

            return (outbreak_status, True)
        except Exception as e:
            logger.error(f"Error executing sync fetch_valid_lag1 wrapper via PyMongo: {e}")
            return self._fetch_from_cache_or_default(disease, district, target_year, target_month)

    def _fetch_from_cache_or_default(
        self, disease: str, district: str, year: int, month: int
    ) -> Optional[Tuple[float, bool]]:
        cache_key = self._get_cache_key(disease, district, year, month)
        cached = self._status_cache.get(cache_key)
        if cached and self._is_cache_valid(cached[3]):
            return (cached[0], True)
        # Safe default if entirely uncached and synchronous query is not possible
        return (0.0, True)

    async def fetch_valid_lag1_async(
        self, disease: str, district: str, month: int, year: int
    ) -> Optional[Tuple[float, bool]]:
        """
        Async implementation of lag1 lookup.
        """
        if month == 1:
            target_year = year - 1
            target_month = 12
        else:
            target_year = year
            target_month = month - 1

        outbreak_status, _, _ = await self.get_district_status_async(disease, district, target_year, target_month)
        return (outbreak_status, True)

    def fetch_feature_record(
        self, disease: str, district: str, month: int, year: int
    ) -> Optional[SharedForecastRecord]:
        """
        Returns None to delegate feature queries to CSV fallback. Only lag1 is live DB updated.
        """
        return None

    def invalidate_cache(self, disease: Optional[str] = None, district: Optional[str] = None):
        """Clear cache entries, optionally filtered by disease and/or district."""
        if disease is None and district is None:
            self._status_cache.clear()
            return

        keys_to_remove = []
        for key in self._status_cache.keys():
            parts = key.split("|")
            if len(parts) >= 4:
                key_disease, key_district = parts[0], parts[1]
                if disease and key_disease != disease.upper():
                    continue
                if district and key_district != district.title():
                    continue
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._status_cache[key]
