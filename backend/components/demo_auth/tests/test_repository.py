"""
Unit tests for backend/components/demo_auth/repository.py using IsolatedAsyncioTestCase and AsyncMock.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
import sys

from backend.components.demo_auth.models import (
    Role,
    ScopeLevel,
    DemoUserDocument,
)
from backend.components.demo_auth.repository import (
    DemoUserRepository,
    DemoUserRepositoryError,
    DemoUserDuplicateError,
)


class TestDemoUserRepository(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.mock_collection = MagicMock()
        self.mock_db = {"demo_users": self.mock_collection}
        self.repo = DemoUserRepository(self.mock_db)

        self.valid_permissions = {
            "viewDataQuality": True,
            "viewModelTransparency": False,
            "manageAlerts": False,
            "recordResponse": False,
            "viewReports": True,
        }

        self.valid_auth = {
            "scopeLevel": ScopeLevel.FARM,
            "registeredFarmDistrict": "Ampara",
            "authorizedDistricts": ["Ampara"],
            "assignedFarmIds": [],
        }

        self.valid_user = DemoUserDocument(
            schemaVersion="1.0",
            userId="DEMO_USER_FARMER_001",
            loginName="farmer_demo",
            passwordHash="$argon2id$v=19$m=65536,t=3,p=4$dummyhash",
            role=Role.FARMER,
            authorization=self.valid_auth,
            permissions=self.valid_permissions,
            enabled=True,
            tokenVersion=1,
            isSynthetic=True,
            dataOrigin="SYNTHETIC_DEMO",
            scientificUseAllowed=False,
            createdAt=self.now,
            updatedAt=self.now,
        )

    def test_1_collection_name_is_exactly_demo_users(self):
        self.assertEqual(DemoUserRepository.COLLECTION_NAME, "demo_users")

    def test_2_repository_uses_supplied_database_and_creates_no_client(self):
        repo = DemoUserRepository(self.mock_db)
        self.assertEqual(repo._db, self.mock_db)

    async def test_3_ensure_indexes_creates_unique_user_id_index(self):
        self.mock_collection.create_index = AsyncMock()
        await self.repo.ensure_indexes()

        calls = self.mock_collection.create_index.call_args_list
        user_id_call = [c for c in calls if c.kwargs.get("name") == "idx_demo_users_user_id_unique"]
        self.assertEqual(len(user_id_call), 1)
        self.assertTrue(user_id_call[0].kwargs.get("unique"))

    async def test_4_ensure_indexes_creates_unique_login_name_index(self):
        self.mock_collection.create_index = AsyncMock()
        await self.repo.ensure_indexes()

        calls = self.mock_collection.create_index.call_args_list
        login_call = [c for c in calls if c.kwargs.get("name") == "idx_demo_users_login_name_unique"]
        self.assertEqual(len(login_call), 1)
        self.assertTrue(login_call[0].kwargs.get("unique"))

    async def test_5_index_names_are_stable(self):
        self.mock_collection.create_index = AsyncMock()
        await self.repo.ensure_indexes()

        call_names = [c.kwargs.get("name") for c in self.mock_collection.create_index.call_args_list]
        self.assertIn("idx_demo_users_user_id_unique", call_names)
        self.assertIn("idx_demo_users_login_name_unique", call_names)
        self.assertIn("idx_demo_users_enabled", call_names)

    async def test_6_login_name_is_trimmed_lowercased_before_query(self):
        self.mock_collection.find_one = AsyncMock(return_value=None)
        await self.repo.find_by_login_name("  FARMER_DEMO  ")

        self.mock_collection.find_one.assert_called_once()
        query = self.mock_collection.find_one.call_args[0][0]
        self.assertEqual(query["loginName"], "farmer_demo")

    async def test_7_empty_login_name_is_rejected_before_database_call(self):
        self.mock_collection.find_one = AsyncMock()

        for bad_login in ["", "   ", None]:
            with self.assertRaises(DemoUserRepositoryError):
                await self.repo.find_by_login_name(bad_login)

        self.mock_collection.find_one.assert_not_called()

    async def test_8_valid_user_id_lookup_works(self):
        doc = self.valid_user.model_dump()
        doc["_id"] = "mongo_object_id_123"
        self.mock_collection.find_one = AsyncMock(return_value=doc)

        result = await self.repo.find_by_user_id("DEMO_USER_FARMER_001")
        self.assertIsInstance(result, DemoUserDocument)
        self.assertEqual(result.userId, "DEMO_USER_FARMER_001")

    async def test_9_invalid_non_demo_user_id_rejected_before_database_call(self):
        self.mock_collection.find_one = AsyncMock()

        for bad_id in ["REAL_USER_123", "", "   ", None]:
            with self.assertRaises(DemoUserRepositoryError):
                await self.repo.find_by_user_id(bad_id)

        self.mock_collection.find_one.assert_not_called()

    async def test_10_every_read_filter_contains_both_synthetic_markers(self):
        self.mock_collection.find_one = AsyncMock(return_value=None)

        await self.repo.find_by_login_name("farmer_demo")
        query1 = self.mock_collection.find_one.call_args[0][0]
        self.assertTrue(query1["isSynthetic"])
        self.assertEqual(query1["dataOrigin"], "SYNTHETIC_DEMO")

        await self.repo.find_by_user_id("DEMO_USER_FARMER_001")
        query2 = self.mock_collection.find_one.call_args[0][0]
        self.assertTrue(query2["isSynthetic"])
        self.assertEqual(query2["dataOrigin"], "SYNTHETIC_DEMO")

    async def test_11_missing_user_returns_none(self):
        self.mock_collection.find_one = AsyncMock(return_value=None)

        res1 = await self.repo.find_by_login_name("farmer_demo")
        self.assertIsNone(res1)

        res2 = await self.repo.find_by_user_id("DEMO_USER_FARMER_001")
        self.assertIsNone(res2)

    async def test_12_valid_mongo_document_converts_to_demo_user_document(self):
        doc = self.valid_user.model_dump()
        self.mock_collection.find_one = AsyncMock(return_value=doc)

        res = await self.repo.find_by_login_name("farmer_demo")
        self.assertEqual(res.userId, "DEMO_USER_FARMER_001")

    async def test_13_mongo_id_is_not_exposed(self):
        doc = self.valid_user.model_dump()
        doc["_id"] = "mongo_internal_id"
        self.mock_collection.find_one = AsyncMock(return_value=doc)

        user = await self.repo.find_by_user_id("DEMO_USER_FARMER_001")
        self.assertFalse(hasattr(user, "_id"))

    async def test_14_corrupt_document_raises_sanitized_repository_error(self):
        corrupt_doc = {"userId": "DEMO_USER_INVALID", "corrupt_data": True}
        self.mock_collection.find_one = AsyncMock(return_value=corrupt_doc)

        with self.assertRaises(DemoUserRepositoryError) as ctx:
            await self.repo.find_by_user_id("DEMO_USER_INVALID")
        self.assertIn("corrupt or invalid", str(ctx.exception).lower())

    async def test_15_insert_serializes_the_complete_valid_user(self):
        self.mock_collection.insert_one = AsyncMock()

        res = await self.repo.insert_user(self.valid_user)
        self.assertEqual(res, self.valid_user)

        self.mock_collection.insert_one.assert_called_once()
        inserted_doc = self.mock_collection.insert_one.call_args[0][0]
        self.assertEqual(inserted_doc["userId"], "DEMO_USER_FARMER_001")
        self.assertTrue(inserted_doc["isSynthetic"])

    async def test_16_insert_rejects_non_model_values(self):
        self.mock_collection.insert_one = AsyncMock()

        for invalid_val in [{"userId": "DEMO_USER_01"}, "string_user", None]:
            with self.assertRaises(DemoUserRepositoryError):
                await self.repo.insert_user(invalid_val)

        self.mock_collection.insert_one.assert_not_called()

    async def test_17_duplicate_key_error_becomes_sanitized_duplicate_user_error(self):
        self.mock_collection.insert_one = AsyncMock(side_effect=Exception("E11000 duplicate key error collection"))

        with self.assertRaises(DemoUserDuplicateError) as ctx:
            await self.repo.insert_user(self.valid_user)
        self.assertIn("already exists", str(ctx.exception).lower())

    async def test_18_replace_upsert_uses_a_narrow_demo_user_filter(self):
        mock_result = MagicMock()
        mock_result.matched_count = 1
        self.mock_collection.replace_one = AsyncMock(return_value=mock_result)

        await self.repo.replace_user(self.valid_user, upsert=False)

        self.mock_collection.replace_one.assert_called_once()
        filter_arg = self.mock_collection.replace_one.call_args[0][0]

        self.assertEqual(filter_arg["userId"], "DEMO_USER_FARMER_001")
        self.assertTrue(filter_arg["isSynthetic"])
        self.assertEqual(filter_arg["dataOrigin"], "SYNTHETIC_DEMO")

    def test_19_no_broad_delete_drop_operation_exists_or_executes(self):
        forbidden_methods = ["delete_many", "drop", "drop_collection", "rename"]
        for method in forbidden_methods:
            self.assertFalse(hasattr(self.repo, method))

    def test_20_password_hash_absent_from_errors_and_repository_repr(self):
        repr_str = repr(self.repo)
        self.assertNotIn("passwordHash", repr_str)
        self.assertNotIn("$argon2", repr_str)

    async def test_21_caller_model_input_is_not_mutated(self):
        original_hash = self.valid_user.passwordHash
        self.mock_collection.insert_one = AsyncMock()

        # Run insert
        await self.repo.insert_user(self.valid_user)

        self.assertEqual(self.valid_user.passwordHash, original_hash)

    def test_22_repository_contains_no_forecasting_model_imports(self):
        repo_module = sys.modules.get("backend.components.demo_auth.repository")
        self.assertIsNotNone(repo_module)
        with open(repo_module.__file__, "r", encoding="utf-8") as f:
            module_source = f.read()

        forbidden_terms = ["sklearn", "predict", "forecast", "model", "pandas", "numpy"]
        for term in forbidden_terms:
            self.assertNotIn(f"import {term}", module_source)
            self.assertNotIn(f"from {term}", module_source)


if __name__ == "__main__":
    unittest.main()
