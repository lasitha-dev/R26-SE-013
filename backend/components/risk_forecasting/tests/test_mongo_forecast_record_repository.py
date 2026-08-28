import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import pymongo
from pymongo.errors import PyMongoError, DuplicateKeyError
from pymongo import ReturnDocument

from components.risk_forecasting.repositories.mongo_forecast_record_repository import MongoForecastRecordRepository
from components.risk_forecasting.schemas import ForecastDecisionRecord


class FakeCursor:
    def __init__(self, items):
        self.items = items

    def sort(self, *args, **kwargs):
        return self

    def skip(self, *args, **kwargs):
        return self

    def limit(self, limit):
        return FakeCursor(self.items[:limit])

    def __iter__(self):
        return iter(self.items)


class FakeCollection:
    def __init__(self):
        self._data = {}  # _id -> dict
        self._indexes = []

    def create_index(self, keys, **kwargs):
        self._indexes.append((keys, kwargs))

    def insert_one(self, doc):
        _id = doc.get("_id")
        
        # Check idempotency unique mock
        idempotency_key = doc.get("idempotency_key")
        if idempotency_key:
            for existing in self._data.values():
                if existing.get("idempotency_key") == idempotency_key:
                    raise DuplicateKeyError("E11000 duplicate key error collection: idempotency_key")

        if _id in self._data:
            raise DuplicateKeyError("E11000 duplicate key error collection: _id")
        
        self._data[_id] = doc.copy()

    def find_one(self, filter_dict):
        for k, v in filter_dict.items():
            for doc in self._data.values():
                if doc.get(k) == v:
                    return doc.copy()
        return None

    def find(self, filter_dict):
        results = []
        for doc in self._data.values():
            match = True
            for k, v in filter_dict.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                results.append(doc.copy())
        # Sort by created_at DESC as expected
        results.sort(key=lambda x: x.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return FakeCursor(results)

    def count_documents(self, filter_dict):
        cursor = self.find(filter_dict)
        return len(cursor.items)

    def find_one_and_update(self, filter_dict, update_dict, return_document=False):
        doc = self.find_one(filter_dict)
        if not doc:
            return None
        _id = doc["_id"]
        set_ops = update_dict.get("$set", {})
        for k, v in set_ops.items():
            doc[k] = v
        self._data[_id] = doc.copy()
        return doc.copy() if return_document == ReturnDocument.AFTER else None


class TestMongoForecastRecordRepository(unittest.TestCase):
    def setUp(self):
        self.fake_collection = FakeCollection()
        self.repo = MongoForecastRecordRepository(collection=self.fake_collection)

    def _create_record(self, f_id="fdr_123", idemp_key=None):
        return ForecastDecisionRecord(
            forecast_id=f_id,
            disease="FMD",
            district="Colombo",
            target_year=2024,
            target_month=1,
            probability=0.75,
            probability_pct=75.0,
            risk_level="HIGH",
            model_variant="30_feature_baseline",
            status="GENERATED",
            trigger_type="MANUAL",
            fallback_applied=False,
            data_quality="EXACT",
            disclaimer="Test Disclaimer",
            updated_at=datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc).isoformat(),
            idempotency_key=idemp_key,
            generated_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
            created_at=datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc).isoformat(),
        )

    # 1. ForecastDecisionRecord serialization
    # 2. Enum serialization
    # 3. Timezone-aware datetime serialization
    def test_serialization_to_bson(self):
        rec = self._create_record()
        bson_data = self.repo._to_bson(rec)
        
        self.assertEqual(bson_data["_id"], "fdr_123")
        self.assertEqual(bson_data["disease"], "FMD")  # Enum -> String
        self.assertIsInstance(bson_data["generated_at"], datetime)
        self.assertIsNotNone(bson_data["generated_at"].tzinfo)
        
    # 4. Deserialization round-trip
    def test_deserialization_round_trip(self):
        rec = self._create_record()
        bson_data = self.repo._to_bson(rec)
        restored = self.repo._to_model(bson_data)
        
        self.assertEqual(restored.forecast_id, rec.forecast_id)
        self.assertEqual(restored.disease, rec.disease)
        self.assertEqual(restored.generated_at, rec.generated_at)
        
    # 5. save inserts one document
    def test_save_inserts_one_document(self):
        rec = self._create_record()
        self.repo.save(rec)
        self.assertEqual(len(self.fake_collection._data), 1)
        self.assertEqual(self.fake_collection._data["fdr_123"]["district"], "Colombo")
        
    # 6. get_by_id uses the string forecast ID
    def test_get_by_id(self):
        rec = self._create_record("fdr_999")
        self.repo.save(rec)
        fetched = self.repo.get_by_id("fdr_999")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.forecast_id, "fdr_999")
        
    # 7. find_by_idempotency_key
    def test_find_by_idempotency_key(self):
        rec = self._create_record(idemp_key="my_key_123")
        self.repo.save(rec)
        fetched = self.repo.find_by_idempotency_key("my_key_123")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.idempotency_key, "my_key_123")

    # 8. list filter mapping
    def test_list_filter_mapping(self):
        self.repo.save(self._create_record("fdr_1", idemp_key="k1"))
        # Add another with different district
        rec2 = self._create_record("fdr_2", idemp_key="k2")
        rec2.district = "Jaffna"
        self.repo.save(rec2)
        
        recs, total = self.repo.list(district="Jaffna")
        self.assertEqual(total, 1)
        self.assertEqual(recs[0].forecast_id, "fdr_2")
        
    # 9. list sorting and limit behavior
    def test_list_sorting_and_limit(self):
        for i in range(5):
            r = self._create_record(f"fdr_{i}", idemp_key=f"k_{i}")
            r.created_at = datetime(2024, 1, 1, 12, i, 0, tzinfo=timezone.utc).isoformat()
            self.repo.save(r)
            
        recs, total = self.repo.list(limit=2)
        self.assertEqual(total, 5)
        self.assertEqual(len(recs), 2)
        # Newest first
        self.assertEqual(recs[0].forecast_id, "fdr_4")
        self.assertEqual(recs[1].forecast_id, "fdr_3")

    # 10. update_status atomic behavior matching current contract
    def test_update_status(self):
        self.repo.save(self._create_record("fdr_1"))
        updated = self.repo.update_status("fdr_1", "AVAILABLE")
        self.assertEqual(updated.status, "AVAILABLE")
        self.assertIsNotNone(updated.updated_at)
        
        # Verify in DB
        doc = self.fake_collection._data["fdr_1"]
        self.assertEqual(doc["status"], "AVAILABLE")
        self.assertIsInstance(doc["updated_at"], datetime)

    # 11. unknown ID behavior
    def test_unknown_id_behavior(self):
        self.assertIsNone(self.repo.get_by_id("nonexistent"))
        # update_status raises KeyError or returns None according to contract?
        # Our update_status returns None if not found, like InMemory. Wait, InMemory returned None. Let's verify our code.
        # Yes, self.collection.find_one_and_update returns None, so we return None.
        res = self.repo.update_status("nonexistent", "AVAILABLE")
        self.assertIsNone(res)

    # 12. duplicate idempotency key returns the existing compatible record
    def test_duplicate_idempotency_key_returns_existing(self):
        rec = self._create_record("fdr_1", idemp_key="idem_1")
        self.repo.save(rec)
        
        # Second save attempt
        rec2 = self._create_record("fdr_2", idemp_key="idem_1")
        returned = self.repo.save(rec2)
        # Should return existing fdr_1
        self.assertEqual(returned.forecast_id, "fdr_1")
        self.assertEqual(len(self.fake_collection._data), 1)

    # 13. conflicting duplicate preserves existing service contract or raises conflict error
    def test_conflicting_duplicate_id_raises_error(self):
        rec1 = self._create_record("fdr_1", idemp_key="k1")
        self.repo.save(rec1)
        
        # Same ID, different idempotency key
        rec2 = self._create_record("fdr_1", idemp_key="k2")
        with self.assertRaises(ValueError) as ctx:
            self.repo.save(rec2)
        self.assertIn("already exists", str(ctx.exception))

    # 14. database failure is sanitized
    def test_database_failure_is_sanitized(self):
        mock_col = MagicMock()
        mock_col.insert_one.side_effect = PyMongoError("Mocked network error")
        bad_repo = MongoForecastRecordRepository(collection=mock_col)
        
        with self.assertRaises(RuntimeError) as ctx:
            bad_repo.save(self._create_record())
        self.assertIn("Database error during save", str(ctx.exception))

    # 15. index initialization occurs once
    def test_index_initialization_occurs_once(self):
        self.assertEqual(len(self.fake_collection._indexes), 0)
        self.repo.save(self._create_record())
        self.assertEqual(len(self.fake_collection._indexes), 2)
        # Save another, shouldn't add more indexes
        self.repo.save(self._create_record("fdr_2", idemp_key="k2"))
        self.assertEqual(len(self.fake_collection._indexes), 2)
        self.assertTrue(self.repo._indexes_initialized)

    # 16. a second repository instance reading the same fake collection simulates restart persistence
    def test_second_repository_simulates_restart(self):
        self.repo.save(self._create_record("fdr_1"))
        
        # New repo pointing to same fake_collection
        repo2 = MongoForecastRecordRepository(collection=self.fake_collection)
        fetched = repo2.get_by_id("fdr_1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.forecast_id, "fdr_1")

if __name__ == "__main__":
    unittest.main()
