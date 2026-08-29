"""
MongoDB-backed SharedForecastDataClient implementation.
Aggregates verified diagnostic cases and death logs to compute district-wise outbreak status.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
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


class MongoSharedForecastClient(SharedForecastDataClient):
    """
    MongoDB-backed implementation of SharedForecastDataClient.
    Computes district-wise outbreak status by aggregating verified diagnostic cases
    and death logs from the live MongoDB collections.
    """

    def __init__(self, cache_ttl_seconds: int = 3600):
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
        return (datetime.utcnow().timestamp() - cached_at) < self._cache_ttl_seconds

    async def get_district_status_async(
        self, disease: str, district: str, year: int, month: int
    ) -> Tuple[float, int, int]:
        """
        Retrieves the outbreak status, cases count, and deaths count for a specific month.
        This queries the DB and uses a 1-hour in-memory cache.
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

        # Date range for target month
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        # Count verified diagnostic cases
        cases_count = 0
        async for case in diagnostic_cases_collection.find({
            "verified": True,
            "disease_name": {"$regex": f"^{disease_upper}$", "$options": "i"},
            "created_at": {"$gte": start_date, "$lt": end_date}
        }):
            farm_id = case.get("farm_id")
            if farm_id:
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
                
                if farm and farm.get("location_district") == formatted_district:
                    cases_count += 1

        # Count deaths logs
        deaths_count = 0
        async for death in death_logs_collection.find({
            "cause": disease_upper,
            "district": formatted_district,
            "date_of_death": {"$gte": start_date, "$lt": end_date}
        }):
            deaths_count += 1

        outbreak_status = 1.0 if (cases_count >= 1 or deaths_count >= 1) else 0.0

        # Update cache
        self._status_cache[cache_key] = (
            outbreak_status,
            cases_count,
            deaths_count,
            datetime.utcnow().timestamp()
        )

        return (outbreak_status, cases_count, deaths_count)

    def fetch_valid_lag1(
        self, disease: str, district: str, month: int, year: int
    ) -> Optional[Tuple[float, bool]]:
        """
        Retrieves ground-truth outbreak status for preceding month (t-1).
        Synchronous fallback interface required by the Protocol.
        """
        import asyncio
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
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return self._fetch_from_cache_or_default(disease, district, target_year, target_month)
            else:
                outbreak_status, _, _ = loop.run_until_complete(
                    self.get_district_status_async(disease, district, target_year, target_month)
                )
                return (outbreak_status, True)
        except Exception as e:
            logger.error(f"Error executing synch fetch_valid_lag1 wrapper: {e}")
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
