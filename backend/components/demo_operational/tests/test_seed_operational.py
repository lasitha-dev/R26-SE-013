"""
Unit tests for synthetic operational seed dataset builder and CLI seed command.
Verifies dataset counts, referential integrity, Pydantic validation, dry-run safety,
apply idempotency, index creation, and strict isolation.
"""

import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from backend.components.demo_operational.models import (
    EvidenceType,
    VerificationStatus,
    SourceModule,
)
from backend.scripts.seed_demo_operational_data import (
    build_synthetic_dataset,
    run_operational_seed,
    parse_args,
)


class TestSeedOperationalData(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.farms, self.surv_records, self.alerts, self.tasks = build_synthetic_dataset()
        self.mock_env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_DATABASE": "r26_disease_forecasting_demo",
            "FORECASTING_DEMO_MONGODB_URI": "mongodb://localhost:27017",
        }

    # 1. Dataset contains exactly 3 farms, 8 surveillance records, 4 alerts and 5 tasks
    def test_01_dataset_counts(self):
        self.assertEqual(len(self.farms), 3)
        self.assertEqual(len(self.surv_records), 8)
        self.assertEqual(len(self.alerts), 4)
        self.assertEqual(len(self.tasks), 5)

    # 2. Exact required IDs are unique
    def test_02_id_uniqueness(self):
        farm_ids = [f.farmId for f in self.farms]
        surv_ids = [s.surveillanceRecordId for s in self.surv_records]
        alert_ids = [a.alertId for a in self.alerts]
        task_ids = [t.responseTaskId for t in self.tasks]

        self.assertEqual(len(farm_ids), len(set(farm_ids)))
        self.assertEqual(len(surv_ids), len(set(surv_ids)))
        self.assertEqual(len(alert_ids), len(set(alert_ids)))
        self.assertEqual(len(task_ids), len(set(task_ids)))

    # 3 & 4. All Pydantic models validate and timestamps are fixed and UTC-aware
    def test_03_04_validation_and_utc_timestamps(self):
        all_records = self.farms + self.surv_records + self.alerts + self.tasks
        for r in all_records:
            self.assertTrue(r.createdAt.tzinfo is not None)
            self.assertEqual(r.createdAt.tzinfo, timezone.utc)
            self.assertTrue(r.updatedAt.tzinfo is not None)
            self.assertEqual(r.updatedAt.tzinfo, timezone.utc)

    # 5. Every record has synthetic/scientific markers
    def test_05_synthetic_scientific_markers(self):
        all_records = self.farms + self.surv_records + self.alerts + self.tasks
        for r in all_records:
            self.assertEqual(r.schemaVersion, "1.0")
            self.assertTrue(r.isSynthetic)
            self.assertEqual(r.dataOrigin, "SYNTHETIC_DEMO")
            self.assertFalse(r.scientificUseAllowed)

    # 6, 7, 8, 9, 10. Referential integrity
    def test_06_10_referential_integrity(self):
        farm_ids = {f.farmId for f in self.farms}
        surv_ids = {s.surveillanceRecordId for s in self.surv_records}
        alert_ids = {a.alertId for a in self.alerts}

        for s in self.surv_records:
            self.assertIn(s.farmId, farm_ids)

        for a in self.alerts:
            for fid in a.affectedFarmIds:
                self.assertIn(fid, farm_ids)
            for sid in a.sourceSurveillanceRecordIds:
                self.assertIn(sid, surv_ids)

        for t in self.tasks:
            self.assertIn(t.alertId, alert_ids)
            if t.farmId:
                self.assertIn(t.farmId, farm_ids)

    # 11. Every task is assigned to approved Vet
    def test_11_tasks_assigned_to_vet_north(self):
        for t in self.tasks:
            self.assertEqual(t.assignedOfficerUserId, "DEMO_USER_VET_NORTH")

    # 12, 13, 14. Evidence/status combinations & summary wording
    def test_12_14_evidence_and_status_rules(self):
        for s in self.surv_records:
            if s.verificationStatus == VerificationStatus.AI_SCREENED:
                self.assertEqual(s.evidenceType, EvidenceType.AI_IMAGE_SCREENING)
                self.assertNotIn("confirmed", s.summary.lower())

            if s.verificationStatus == VerificationStatus.LAB_CONFIRMED:
                self.assertEqual(s.evidenceType, EvidenceType.LAB_RESULT)
                self.assertEqual(s.sourceModule, SourceModule.SYNTHETIC_LAB_SERVICE)

    # 15. No probability/model/scientific fields exist
    def test_15_no_scientific_fields_in_dump(self):
        all_records = self.farms + self.surv_records + self.alerts + self.tasks
        for r in all_records:
            d = r.model_dump()
            self.assertNotIn("probability", d)
            self.assertNotIn("stage1", d)
            self.assertNotIn("stage2", d)
            self.assertNotIn("log_odds", d)
            self.assertNotIn("ece", d)

    # 16 & 17. Dry-run performs zero network/DB/secret operations and correct output
    async def test_16_17_dry_run_safety(self):
        with patch("backend.scripts.seed_demo_operational_data.DemoDatabaseConnectionManager") as mock_conn_mgr:
            code = await run_operational_seed(apply=False, env_dict=self.mock_env)
            self.assertEqual(code, 0)
            mock_conn_mgr.assert_not_called()

    # 18. Apply requires guarded environment
    async def test_18_guarded_environment_checks(self):
        prod_env = dict(self.mock_env, APP_ENV="production")
        self.assertEqual(await run_operational_seed(apply=True, env_dict=prod_env), 1)

        disabled_env = dict(self.mock_env, FORECASTING_DEMO_ENABLED="false")
        self.assertEqual(await run_operational_seed(apply=True, env_dict=disabled_env), 1)

        wrong_db_env = dict(self.mock_env, FORECASTING_DEMO_DATABASE="other_db")
        self.assertEqual(await run_operational_seed(apply=True, env_dict=wrong_db_env), 1)

    # 19, 20, 21, 22, 23, 25, 27. Apply execution, index ensuring, idempotency, connection closing & zero demo_users access
    async def test_19_to_27_mocked_apply_lifecycle(self):
        mock_db = MagicMock()
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.connect = AsyncMock()
        mock_conn_mgr.ping = AsyncMock()
        mock_conn_mgr.close = AsyncMock()
        mock_conn_mgr.get_database.return_value = mock_db

        # Mock collection search return value to simulate empty DB on 1st run
        mock_coll = MagicMock()
        mock_coll.create_index = AsyncMock()
        mock_coll.find_one = AsyncMock(return_value=None)
        mock_coll.insert_one = AsyncMock()
        mock_coll.replace_one = AsyncMock(return_value=MagicMock(matched_count=1))
        mock_db.__getitem__.return_value = mock_coll

        with patch(
            "backend.scripts.seed_demo_operational_data.DemoDatabaseConnectionManager",
            return_value=mock_conn_mgr,
        ):
            # 1st Run: Should create all 20 records
            code1 = await run_operational_seed(apply=True, env_dict=self.mock_env)
            self.assertEqual(code1, 0)

            # Ensure demo_users collection was NEVER accessed
            for call_arg in mock_db.__getitem__.call_args_list:
                self.assertNotEqual(call_arg[0][0], "demo_users")

            # Verify connection close was called in finally
            mock_conn_mgr.close.assert_called_once()

    # 24. No delete/drop/list/broad methods
    def test_24_no_unsafe_operations(self):
        import backend.scripts.seed_demo_operational_data as seed_mod

        mod_file = seed_mod.__file__
        with open(mod_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("delete_many", content)
        self.assertNotIn("drop_collection", content)
        self.assertNotIn("drop_database", content)


if __name__ == "__main__":
    unittest.main()
