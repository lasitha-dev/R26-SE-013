"""
Unit test suite verifying MongoSharedForecastClient regex matching,
district parsing with coordinates, death_logs queries, and cache invalidation.
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from bson import ObjectId
import asyncio

from components.risk_forecasting.integrations.mongo_shared_client import (
    MongoSharedForecastClient,
    _get_disease_name_regex,
    _district_matches,
)


class TestMongoSharedForecastClient(unittest.TestCase):

    def setUp(self):
        self.client = MongoSharedForecastClient(cache_ttl_seconds=3600)

    def test_disease_name_regex(self):
        """Test disease regex matching against various display names and aliases."""
        import re

        fmd_pattern = re.compile(_get_disease_name_regex("FMD"), re.IGNORECASE)
        self.assertTrue(fmd_pattern.search("FMD"))
        self.assertTrue(fmd_pattern.search("Foot and Mouth Disease"))
        self.assertTrue(fmd_pattern.search("Foot-and-Mouth Disease"))
        self.assertTrue(fmd_pattern.search("Foot-and-Mouth Disease (FMD)"))
        self.assertTrue(fmd_pattern.search("foot_and_mouth"))
        self.assertFalse(fmd_pattern.search("Lumpy Skin Disease"))
        self.assertFalse(fmd_pattern.search("Mastitis"))

        lsd_pattern = re.compile(_get_disease_name_regex("LSD"), re.IGNORECASE)
        self.assertTrue(lsd_pattern.search("LSD"))
        self.assertTrue(lsd_pattern.search("Lumpy Skin Disease"))
        self.assertTrue(lsd_pattern.search("Lumpy-Skin Disease"))
        self.assertTrue(lsd_pattern.search("Lumpy Skin Disease (LSD)"))
        self.assertTrue(lsd_pattern.search("lumpy_skin"))
        self.assertTrue(lsd_pattern.search("lumpy"))
        self.assertFalse(lsd_pattern.search("Foot and Mouth Disease"))
        self.assertFalse(lsd_pattern.search("Mastitis"))

    def test_district_matches(self):
        """Test case-insensitive substring matching on farm location strings."""
        self.assertTrue(_district_matches("Anuradhapura", "8.4162, 80.0261 (Anuradhapura District)"))
        self.assertTrue(_district_matches("Anuradhapura", "Anuradhapura"))
        self.assertTrue(_district_matches("Anuradhapura", "anuradhapura"))
        self.assertTrue(_district_matches("Kurunegala", "Kurunegala District, North Western Province"))
        self.assertFalse(_district_matches("Anuradhapura", "Colombo"))
        self.assertFalse(_district_matches("Anuradhapura", None))

    def test_cache_invalidation(self):
        """Test that invalidate_cache clears cached status records immediately."""
        self.client._status_cache["FMD|Anuradhapura|2026|8"] = (1.0, 5, 2, 9999999999.0)
        self.client._status_cache["LSD|Colombo|2026|8"] = (0.0, 0, 0, 9999999999.0)

        # Invalidate specific disease/district
        self.client.invalidate_cache(disease="FMD", district="Anuradhapura")
        self.assertNotIn("FMD|Anuradhapura|2026|8", self.client._status_cache)
        self.assertIn("LSD|Colombo|2026|8", self.client._status_cache)

        # Invalidate all
        self.client.invalidate_cache()
        self.assertEqual(len(self.client._status_cache), 0)

    def test_fetch_valid_lag1_sync_matching(self):
        """Test synchronous fetch_valid_lag1 with mock PyMongo client."""
        mock_farm_id = ObjectId()
        mock_cases = [
            {
                "verified": True,
                "disease_name": "Foot and Mouth Disease",
                "farm_id": mock_farm_id,
                "created_at": "2026-08-15 10:00:00"
            }
        ]
        mock_farm = {
            "_id": mock_farm_id,
            "location_district": "8.4162, 80.0261 (Anuradhapura District)"
        }
        mock_deaths = [
            {
                "cause": "Foot-and-Mouth Disease (FMD)",
                "district": "8.4162, 80.0261 (Anuradhapura District)",
                "date_of_death": "2026-08-20"
            }
        ]

        with patch("pymongo.MongoClient") as mock_mongo_cls:
            mock_client_instance = MagicMock()
            mock_mongo_cls.return_value.__enter__.return_value = mock_client_instance
            mock_db = MagicMock()
            mock_client_instance.get_database.return_value = mock_db

            mock_cases_coll = MagicMock()
            mock_cases_coll.find.return_value = mock_cases

            mock_farms_coll = MagicMock()
            mock_farms_coll.find_one.return_value = mock_farm

            mock_deaths_coll = MagicMock()
            mock_deaths_coll.find.return_value = mock_deaths

            def coll_side_effect(name):
                if name == "diagnostic_cases":
                    return mock_cases_coll
                elif name == "farms":
                    return mock_farms_coll
                elif name == "death_logs":
                    return mock_deaths_coll
                return MagicMock()

            mock_db.get_collection.side_effect = coll_side_effect

            # Query lag1 for September 2026 (preceding month is August 2026)
            status, valid = self.client.fetch_valid_lag1("FMD", "Anuradhapura", 9, 2026)

            self.assertTrue(valid)
            self.assertEqual(status, 1.0)
            self.assertIn("FMD|Anuradhapura|2026|8", self.client._status_cache)
            cached_status, cached_cases, cached_deaths, _ = self.client._status_cache["FMD|Anuradhapura|2026|8"]
            self.assertEqual(cached_status, 1.0)
            self.assertEqual(cached_cases, 1)
            self.assertEqual(cached_deaths, 1)


if __name__ == "__main__":
    unittest.main()
