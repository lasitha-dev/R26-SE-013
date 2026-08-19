"""
Unit tests for synthetic operational MongoDB repositories.
Mocks PyMongo database/collection calls completely.
Verifies collection names, indexes, filters, pagination, empty-scope short-circuiting,
error sanitization, and isolation.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from backend.components.demo_operational.models import (
    DemoFarm,
    DemoSurveillanceRecord,
    DemoAlert,
    DemoResponseTask,
)
from backend.components.demo_operational.repositories import (
    DemoOperationalRepositoryError,
    DemoOperationalDuplicateError,
    DemoFarmRepository,
    DemoSurveillanceRepository,
    DemoAlertRepository,
    DemoResponseTaskRepository,
)


class TestDemoOperationalRepositories(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_farm_coll = MagicMock()
        self.mock_surv_coll = MagicMock()
        self.mock_alert_coll = MagicMock()
        self.mock_task_coll = MagicMock()

        def get_item(name):
            if name == "demo_farms":
                return self.mock_farm_coll
            elif name == "demo_surveillance_records":
                return self.mock_surv_coll
            elif name == "demo_alerts":
                return self.mock_alert_coll
            elif name == "demo_response_tasks":
                return self.mock_task_coll
            return MagicMock()

        self.mock_db.__getitem__.side_effect = get_item

        self.farm_repo = DemoFarmRepository(self.mock_db)
        self.surv_repo = DemoSurveillanceRepository(self.mock_db)
        self.alert_repo = DemoAlertRepository(self.mock_db)
        self.task_repo = DemoResponseTaskRepository(self.mock_db)

        self.now_utc = datetime.now(timezone.utc)

        self.valid_farm = DemoFarm(
            farmId="DEMO_FARM_JAFFNA_001",
            displayName="Jaffna Synthetic Farm",
            district="Jaffna",
            ownerUserId="DEMO_USER_FARMER_JAFFNA",
            assignedVetUserIds=["DEMO_USER_VET_NORTH"],
            livestockTypes=["CATTLE"],
            active=True,
            createdAt=self.now_utc,
            updatedAt=self.now_utc,
        )

        self.valid_surv = DemoSurveillanceRecord(
            surveillanceRecordId="DEMO_SURV_001",
            farmId="DEMO_FARM_JAFFNA_001",
            district="Jaffna",
            diseaseCode="FMD",
            observedAt=self.now_utc,
            evidenceType="FARMER_REPORT",
            verificationStatus="REPORTED",
            sourceModule="SYNTHETIC_FARM_REPORTING",
            sourceRecordId="DEMO_SOURCE_001",
            summary="Test report",
            createdAt=self.now_utc,
            updatedAt=self.now_utc,
        )

        self.valid_alert = DemoAlert(
            alertId="DEMO_ALERT_001",
            district="Jaffna",
            diseaseCode="FMD",
            status="OPEN",
            priority="HIGH",
            issuedAt=self.now_utc,
            sourceSurveillanceRecordIds=["DEMO_SURV_001"],
            affectedFarmIds=["DEMO_FARM_JAFFNA_001"],
            title="Test Alert",
            message="Test message",
            createdAt=self.now_utc,
            updatedAt=self.now_utc,
        )

        self.valid_task = DemoResponseTask(
            responseTaskId="DEMO_TASK_001",
            alertId="DEMO_ALERT_001",
            assignedOfficerUserId="DEMO_USER_VET_NORTH",
            district="Jaffna",
            farmId="DEMO_FARM_JAFFNA_001",
            taskType="FIELD_REVIEW",
            status="ASSIGNED",
            dueAt=self.now_utc,
            notes="Test notes",
            createdAt=self.now_utc,
            updatedAt=self.now_utc,
        )

    # 1. Exact four collection names
    def test_01_collection_names(self):
        self.assertEqual(DemoFarmRepository.COLLECTION_NAME, "demo_farms")
        self.assertEqual(DemoSurveillanceRepository.COLLECTION_NAME, "demo_surveillance_records")
        self.assertEqual(DemoAlertRepository.COLLECTION_NAME, "demo_alerts")
        self.assertEqual(DemoResponseTaskRepository.COLLECTION_NAME, "demo_response_tasks")

    # 2. Repositories use supplied database and create no clients
    def test_02_use_supplied_db(self):
        self.mock_db.__getitem__.assert_any_call("demo_farms")
        self.mock_db.__getitem__.assert_any_call("demo_surveillance_records")
        self.mock_db.__getitem__.assert_any_call("demo_alerts")
        self.mock_db.__getitem__.assert_any_call("demo_response_tasks")

    # 3. Index definitions and unique constraints
    async def test_03_indexes(self):
        self.mock_farm_coll.create_index = AsyncMock()
        await self.farm_repo.ensure_indexes()
        self.assertEqual(self.mock_farm_coll.create_index.call_count, 4)

        self.mock_surv_coll.create_index = AsyncMock()
        await self.surv_repo.ensure_indexes()
        self.assertEqual(self.mock_surv_coll.create_index.call_count, 4)

        self.mock_alert_coll.create_index = AsyncMock()
        await self.alert_repo.ensure_indexes()
        self.assertEqual(self.mock_alert_coll.create_index.call_count, 4)

        self.mock_task_coll.create_index = AsyncMock()
        await self.task_repo.ensure_indexes()
        self.assertEqual(self.mock_task_coll.create_index.call_count, 4)

    # 5 & 6. Every read and replace filter contains synthetic markers
    async def test_05_06_synthetic_markers_in_filters(self):
        self.mock_farm_coll.find_one = AsyncMock(return_value=None)
        await self.farm_repo.find_by_farm_id("DEMO_FARM_001")
        filter_used = self.mock_farm_coll.find_one.call_args[0][0]
        self.assertEqual(filter_used["isSynthetic"], True)
        self.assertEqual(filter_used["dataOrigin"], "SYNTHETIC_DEMO")

        self.mock_surv_coll.replace_one = AsyncMock(return_value=MagicMock(matched_count=1))
        await self.surv_repo.replace_record(self.valid_surv)
        replace_filter = self.mock_surv_coll.replace_one.call_args[0][0]
        self.assertEqual(replace_filter["isSynthetic"], True)
        self.assertEqual(replace_filter["dataOrigin"], "SYNTHETIC_DEMO")
        self.assertEqual(replace_filter["surveillanceRecordId"], "DEMO_SURV_001")

    # 7. Invalid IDs fail before database calls
    async def test_07_invalid_ids_fail_before_db(self):
        with self.assertRaises(DemoOperationalRepositoryError):
            await self.farm_repo.find_by_farm_id("INVALID_FARM")

        with self.assertRaises(DemoOperationalRepositoryError):
            await self.surv_repo.find_by_record_id("INVALID_SURV")

        with self.assertRaises(DemoOperationalRepositoryError):
            await self.alert_repo.find_by_alert_id("INVALID_ALERT")

        with self.assertRaises(DemoOperationalRepositoryError):
            await self.task_repo.find_by_task_id("INVALID_TASK")

    # 8. Empty scope lists return [] with zero DB calls
    async def test_08_empty_scope_lists_return_empty_without_db(self):
        self.mock_farm_coll.find = MagicMock()
        res = await self.farm_repo.list_by_farm_ids([])
        self.assertEqual(res, [])
        self.mock_farm_coll.find.assert_not_called()

        self.mock_surv_coll.find = MagicMock()
        res2 = await self.surv_repo.list_by_districts([])
        self.assertEqual(res2, [])
        self.mock_surv_coll.find.assert_not_called()

    # 9. Lists trim/deduplicate without input mutation
    async def test_09_lists_trim_dedup_without_mutation(self):
        farm_ids = ["DEMO_FARM_001", " DEMO_FARM_001 ", "DEMO_FARM_002"]
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=[])
        self.mock_farm_coll.find.return_value = mock_cursor

        await self.farm_repo.list_by_farm_ids(farm_ids)
        self.assertEqual(farm_ids, ["DEMO_FARM_001", " DEMO_FARM_001 ", "DEMO_FARM_002"])
        query_filter = self.mock_farm_coll.find.call_args[0][0]
        self.assertEqual(query_filter["farmId"]["$in"], ["DEMO_FARM_001", "DEMO_FARM_002"])

    # 10 & 11. Pagination bounds (negative skip/limit, limit > 100)
    async def test_10_11_pagination_bounds(self):
        with self.assertRaises(DemoOperationalRepositoryError):
            await self.farm_repo.list_by_owner_user_id("DEMO_USER_001", skip=-1)

        with self.assertRaises(DemoOperationalRepositoryError):
            await self.farm_repo.list_by_owner_user_id("DEMO_USER_001", limit=0)

        with self.assertRaises(DemoOperationalRepositoryError):
            await self.farm_repo.list_by_owner_user_id("DEMO_USER_001", limit=101)

    # 12. Stable sort definitions
    async def test_12_sort_definitions(self):
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=[])

        self.mock_surv_coll.find.return_value = mock_cursor
        await self.surv_repo.list_by_districts(["Jaffna"])
        sort_arg = mock_cursor.sort.call_args[0][0]
        self.assertEqual(sort_arg, [("observedAt", -1), ("surveillanceRecordId", 1)])

        self.mock_alert_coll.find.return_value = mock_cursor
        await self.alert_repo.list_by_districts(["Jaffna"])
        sort_arg2 = mock_cursor.sort.call_args[0][0]
        self.assertEqual(sort_arg2, [("issuedAt", -1), ("alertId", 1)])

        self.mock_task_coll.find.return_value = mock_cursor
        await self.task_repo.list_by_districts(["Jaffna"])
        sort_arg3 = mock_cursor.sort.call_args[0][0]
        self.assertEqual(sort_arg3, [("dueAt", 1), ("responseTaskId", 1)])

    # 13, 14, 15. Mongo doc parsing, _id stripping, missing returns None
    async def test_13_14_15_parsing_and_id_stripping(self):
        doc = self.valid_farm.model_dump()
        doc["_id"] = "mongo_object_id_123"
        self.mock_farm_coll.find_one = AsyncMock(return_value=doc)

        res = await self.farm_repo.find_by_farm_id("DEMO_FARM_JAFFNA_001")
        self.assertIsNotNone(res)
        self.assertEqual(res.farmId, "DEMO_FARM_JAFFNA_001")
        self.assertFalse(hasattr(res, "_id"))

        self.mock_farm_coll.find_one = AsyncMock(return_value=None)
        res_none = await self.farm_repo.find_by_farm_id("DEMO_FARM_JAFFNA_001")
        self.assertIsNone(res_none)

    # 16 & 17. Corrupt documents & duplicate key errors raise sanitized exceptions
    async def test_16_17_sanitized_errors(self):
        corrupt_doc = {"farmId": "DEMO_FARM_001", "isSynthetic": False}
        self.mock_farm_coll.find_one = AsyncMock(return_value=corrupt_doc)
        with self.assertRaises(DemoOperationalRepositoryError) as ctx:
            await self.farm_repo.find_by_farm_id("DEMO_FARM_001")
        self.assertIn("corrupt or invalid", str(ctx.exception))

        self.mock_farm_coll.insert_one = AsyncMock(side_effect=Exception("E11000 duplicate key error collection"))
        with self.assertRaises(DemoOperationalDuplicateError):
            await self.farm_repo.insert_farm(self.valid_farm)

    # 18. Wrong model type rejected
    async def test_18_wrong_model_type_rejected(self):
        with self.assertRaises(DemoOperationalRepositoryError):
            await self.farm_repo.insert_farm(self.valid_surv)

    # 19. No delete/drop/list methods
    def test_19_no_unsafe_methods(self):
        for repo in [self.farm_repo, self.surv_repo, self.alert_repo, self.task_repo]:
            self.assertFalse(hasattr(repo, "delete_many"))
            self.assertFalse(hasattr(repo, "drop"))
            self.assertFalse(hasattr(repo, "rename"))
            self.assertFalse(hasattr(repo, "list_databases"))
            self.assertFalse(hasattr(repo, "list_collections"))

    # 20. Secrets absent from repr
    def test_20_repr_is_clean(self):
        for repo in [self.farm_repo, self.surv_repo, self.alert_repo, self.task_repo]:
            repr_str = repr(repo)
            self.assertNotIn("password", repr_str)
            self.assertNotIn("secret", repr_str)
            self.assertNotIn("mongodb://", repr_str)

    # 21. No forecasting / scientific model imports
    def test_21_no_forecasting_imports(self):
        import backend.components.demo_operational.repositories as repo_mod

        mod_file = repo_mod.__file__
        with open(mod_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("risk_forecasting", content)
        self.assertNotIn("sklearn", content)
        self.assertNotIn("torch", content)


if __name__ == "__main__":
    unittest.main()
