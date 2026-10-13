"""
Unit tests for CLI seed script backend/scripts/seed_demo_users.py
Uses mocks to test safety guardrails and idempotency without connecting to Atlas.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
import io

from backend.scripts.seed_demo_users import run_seed, parse_args, SEED_USERS
from backend.components.demo_auth.models import Role, ScopeLevel, DemoUserDocument
from backend.components.demo_auth.repository import DemoUserRepository
from backend.core.demo_security import hash_password, verify_password
from backend.components.risk_forecasting.config import SRI_LANKA_DISTRICTS
from backend.main import app


class TestSeedDemoUsers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.valid_env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_MONGODB_URI": "mongodb://localhost:27017",
            "FORECASTING_DEMO_DATABASE": "r26_disease_forecasting_demo",
            "FORECASTING_DEMO_FARMER_PASSWORD": "FarmerPassword123!",
            "FORECASTING_DEMO_VET_PASSWORD": "VetPassword123!",
            "FORECASTING_DEMO_DAPH_PASSWORD": "DaphPassword123!",
        }

    def test_1_default_mode_is_dry_run_and_makes_zero_writes(self):
        args = parse_args([])
        self.assertFalse(args.apply)

    def test_2_apply_is_required_for_writes(self):
        args = parse_args(["--apply"])
        self.assertTrue(args.apply)

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_3_production_prod_test_environment_refuses_writes(self, mock_mgr):
        for bad_env in ["production", "prod", "test"]:
            env = dict(self.valid_env)
            env["APP_ENV"] = bad_env
            code = await run_seed(apply=True, env_dict=env)
            self.assertEqual(code, 1)
            mock_mgr.assert_not_called()

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_4_disabled_demo_mode_refuses_writes(self, mock_mgr):
        env = dict(self.valid_env)
        env["FORECASTING_DEMO_ENABLED"] = "false"
        code = await run_seed(apply=True, env_dict=env)
        self.assertEqual(code, 1)

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_5_wrong_database_name_refuses_writes(self, mock_mgr):
        env = dict(self.valid_env)
        env["FORECASTING_DEMO_DATABASE"] = "wrong_db_name"
        code = await run_seed(apply=True, env_dict=env)
        self.assertEqual(code, 1)

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_6_missing_empty_password_variable_refuses_writes(self, mock_mgr):
        env = dict(self.valid_env)
        env["FORECASTING_DEMO_FARMER_PASSWORD"] = ""
        code = await run_seed(apply=True, env_dict=env)
        self.assertEqual(code, 1)

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_7_no_secret_appears_in_output_or_errors(self, mock_mgr, mock_stderr, mock_stdout):
        mock_instance = MagicMock()
        mock_instance.connect = AsyncMock()
        mock_instance.ping = AsyncMock()
        mock_instance.get_database = MagicMock()
        mock_instance.close = AsyncMock()
        mock_mgr.return_value = mock_instance

        mock_repo = MagicMock(spec=DemoUserRepository)
        mock_repo.ensure_indexes = AsyncMock()
        mock_repo.find_by_user_id = AsyncMock(return_value=None)
        mock_repo.insert_user = AsyncMock()

        with patch("backend.scripts.seed_demo_users.DemoUserRepository", return_value=mock_repo):
            await run_seed(apply=True, env_dict=self.valid_env)

        output = mock_stdout.getvalue() + mock_stderr.getvalue()
        self.assertNotIn("FarmerPassword123!", output)
        self.assertNotIn("VetPassword123!", output)
        self.assertNotIn("DaphPassword123!", output)

    def test_8_exactly_three_canonical_users_are_built(self):
        self.assertEqual(len(SEED_USERS), 3)
        user_ids = {u["userId"] for u in SEED_USERS}
        self.assertEqual(
            user_ids,
            {"DEMO_USER_FARMER_JAFFNA", "DEMO_USER_VET_NORTH", "DEMO_USER_DAPH_OFFICIAL"},
        )

    def test_9_farmer_contract_is_exact(self):
        farmer = next(u for u in SEED_USERS if u["userId"] == "DEMO_USER_FARMER_JAFFNA")
        self.assertEqual(farmer["role"], Role.FARMER)
        self.assertEqual(farmer["authorization"]["scopeLevel"], ScopeLevel.FARM)
        self.assertEqual(farmer["authorization"]["registeredFarmDistrict"], "Jaffna")
        self.assertEqual(farmer["authorization"]["authorizedDistricts"], ["Jaffna"])

    def test_10_vet_contract_and_five_districts_are_exact(self):
        vet = next(u for u in SEED_USERS if u["userId"] == "DEMO_USER_VET_NORTH")
        self.assertEqual(vet["role"], Role.VETERINARY_OFFICER)
        self.assertEqual(vet["authorization"]["scopeLevel"], ScopeLevel.PROVINCE)
        self.assertEqual(
            vet["authorization"]["authorizedDistricts"],
            ["Jaffna", "Kilinochchi", "Mannar", "Mullaitivu", "Vavuniya"],
        )
        self.assertEqual(
            vet["authorization"]["assignedFarmIds"],
            ["DEMO_FARM_JAFFNA_001", "DEMO_FARM_KILINOCHCHI_001", "DEMO_FARM_VAVUNIYA_001"],
        )

    def test_11_daph_explicitly_contains_the_exact_25_backend_districts(self):
        daph = next(u for u in SEED_USERS if u["userId"] == "DEMO_USER_DAPH_OFFICIAL")
        self.assertEqual(daph["role"], Role.DAPH_OFFICIAL)
        self.assertEqual(daph["authorization"]["scopeLevel"], ScopeLevel.NATIONAL)
        self.assertEqual(daph["authorization"]["authorizedDistricts"], list(SRI_LANKA_DISTRICTS))
        self.assertEqual(len(daph["authorization"]["authorizedDistricts"]), 25)

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_12_all_records_contain_synthetic_and_scientific_markers(self, mock_mgr):
        mock_instance = MagicMock()
        mock_instance.connect = AsyncMock()
        mock_instance.ping = AsyncMock()
        mock_instance.get_database = MagicMock()
        mock_instance.close = AsyncMock()
        mock_mgr.return_value = mock_instance

        mock_repo = MagicMock(spec=DemoUserRepository)
        mock_repo.ensure_indexes = AsyncMock()
        mock_repo.find_by_user_id = AsyncMock(return_value=None)
        mock_repo.insert_user = AsyncMock()

        with patch("backend.scripts.seed_demo_users.DemoUserRepository", return_value=mock_repo):
            await run_seed(apply=True, env_dict=self.valid_env)

        inserted_users = [call.args[0] for call in mock_repo.insert_user.call_args_list]
        self.assertEqual(len(inserted_users), 3)
        for user in inserted_users:
            self.assertTrue(user.isSynthetic)
            self.assertEqual(user.dataOrigin, "SYNTHETIC_DEMO")
            self.assertFalse(user.scientificUseAllowed)

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_13_passwords_are_argon2_hashes_not_plaintext(self, mock_mgr):
        mock_instance = MagicMock()
        mock_instance.connect = AsyncMock()
        mock_instance.ping = AsyncMock()
        mock_instance.get_database = MagicMock()
        mock_instance.close = AsyncMock()
        mock_mgr.return_value = mock_instance

        mock_repo = MagicMock(spec=DemoUserRepository)
        mock_repo.ensure_indexes = AsyncMock()
        mock_repo.find_by_user_id = AsyncMock(return_value=None)
        mock_repo.insert_user = AsyncMock()

        with patch("backend.scripts.seed_demo_users.DemoUserRepository", return_value=mock_repo):
            await run_seed(apply=True, env_dict=self.valid_env)

        inserted_users = [call.args[0] for call in mock_repo.insert_user.call_args_list]
        for user in inserted_users:
            self.assertTrue(user.passwordHash.startswith("$argon2id$"))
            self.assertNotIn("FarmerPassword123!", user.passwordHash)

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_14_first_apply_creates_three_users(self, mock_mgr):
        mock_instance = MagicMock()
        mock_instance.connect = AsyncMock()
        mock_instance.ping = AsyncMock()
        mock_instance.get_database = MagicMock()
        mock_instance.close = AsyncMock()
        mock_mgr.return_value = mock_instance

        mock_repo = MagicMock(spec=DemoUserRepository)
        mock_repo.ensure_indexes = AsyncMock()
        mock_repo.find_by_user_id = AsyncMock(return_value=None)
        mock_repo.insert_user = AsyncMock()

        with patch("backend.scripts.seed_demo_users.DemoUserRepository", return_value=mock_repo):
            code = await run_seed(apply=True, env_dict=self.valid_env)

        self.assertEqual(code, 0)
        self.assertEqual(mock_repo.insert_user.call_count, 3)

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_15_second_equivalent_apply_reports_unchanged_and_preserves_hashes(self, mock_mgr):
        mock_instance = MagicMock()
        mock_instance.connect = AsyncMock()
        mock_instance.ping = AsyncMock()
        mock_instance.get_database = MagicMock()
        mock_instance.close = AsyncMock()
        mock_mgr.return_value = mock_instance

        # Create pre-existing users with valid hashes matching test passwords
        pre_existing = {}
        for user_def in SEED_USERS:
            pass_var = user_def["password_env_var"]
            plain_pass = self.valid_env[pass_var]
            u_hash = hash_password(plain_pass)
            doc = DemoUserDocument(
                schemaVersion="1.0",
                userId=user_def["userId"],
                loginName=user_def["loginName"],
                passwordHash=u_hash,
                role=user_def["role"],
                authorization=user_def["authorization"],
                permissions=user_def["permissions"],
                enabled=True,
                tokenVersion=1,
                isSynthetic=True,
                dataOrigin="SYNTHETIC_DEMO",
                scientificUseAllowed=False,
                createdAt=self.now,
                updatedAt=self.now,
            )
            pre_existing[user_def["userId"]] = doc

        mock_repo = MagicMock(spec=DemoUserRepository)
        mock_repo.ensure_indexes = AsyncMock()
        mock_repo.find_by_user_id = AsyncMock(side_effect=lambda uid: pre_existing.get(uid))
        mock_repo.insert_user = AsyncMock()
        mock_repo.replace_user = AsyncMock()

        with patch("backend.scripts.seed_demo_users.DemoUserRepository", return_value=mock_repo):
            code = await run_seed(apply=True, env_dict=self.valid_env)

        self.assertEqual(code, 0)
        mock_repo.insert_user.assert_not_called()
        mock_repo.replace_user.assert_not_called()

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_16_changed_password_narrowly_updates_one_user(self, mock_mgr):
        mock_instance = MagicMock()
        mock_instance.connect = AsyncMock()
        mock_instance.ping = AsyncMock()
        mock_instance.get_database = MagicMock()
        mock_instance.close = AsyncMock()
        mock_mgr.return_value = mock_instance

        pre_existing = {}
        for user_def in SEED_USERS:
            pass_var = user_def["password_env_var"]
            plain_pass = self.valid_env[pass_var]
            u_hash = hash_password(plain_pass)
            doc = DemoUserDocument(
                schemaVersion="1.0",
                userId=user_def["userId"],
                loginName=user_def["loginName"],
                passwordHash=u_hash,
                role=user_def["role"],
                authorization=user_def["authorization"],
                permissions=user_def["permissions"],
                enabled=True,
                tokenVersion=1,
                isSynthetic=True,
                dataOrigin="SYNTHETIC_DEMO",
                scientificUseAllowed=False,
                createdAt=self.now,
                updatedAt=self.now,
            )
            pre_existing[user_def["userId"]] = doc

        # Change password for farmer only
        changed_env = dict(self.valid_env)
        changed_env["FORECASTING_DEMO_FARMER_PASSWORD"] = "NewFarmerPassword999!"

        mock_repo = MagicMock(spec=DemoUserRepository)
        mock_repo.ensure_indexes = AsyncMock()
        mock_repo.find_by_user_id = AsyncMock(side_effect=lambda uid: pre_existing.get(uid))
        mock_repo.insert_user = AsyncMock()
        mock_repo.replace_user = AsyncMock()

        with patch("backend.scripts.seed_demo_users.DemoUserRepository", return_value=mock_repo):
            code = await run_seed(apply=True, env_dict=changed_env)

        self.assertEqual(code, 0)
        mock_repo.insert_user.assert_not_called()
        self.assertEqual(mock_repo.replace_user.call_count, 1)

        replaced_user = mock_repo.replace_user.call_args[0][0]
        self.assertEqual(replaced_user.userId, "DEMO_USER_FARMER_JAFFNA")
        self.assertTrue(verify_password("NewFarmerPassword999!", replaced_user.passwordHash))

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_17_duplicate_users_are_not_created(self, mock_mgr):
        mock_instance = MagicMock()
        mock_instance.connect = AsyncMock()
        mock_instance.ping = AsyncMock()
        mock_instance.get_database = MagicMock()
        mock_instance.close = AsyncMock()
        mock_mgr.return_value = mock_instance

        mock_repo = MagicMock(spec=DemoUserRepository)
        mock_repo.ensure_indexes = AsyncMock()
        mock_repo.find_by_user_id = AsyncMock(return_value=None)
        mock_repo.insert_user = AsyncMock()

        with patch("backend.scripts.seed_demo_users.DemoUserRepository", return_value=mock_repo):
            await run_seed(apply=True, env_dict=self.valid_env)

        inserted_ids = [call.args[0].userId for call in mock_repo.insert_user.call_args_list]
        self.assertEqual(len(inserted_ids), len(set(inserted_ids)))

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_18_ensure_indexes_is_called_only_during_apply(self, mock_mgr):
        mock_instance = MagicMock()
        mock_instance.connect = AsyncMock()
        mock_instance.ping = AsyncMock()
        mock_instance.get_database = MagicMock()
        mock_instance.close = AsyncMock()
        mock_mgr.return_value = mock_instance

        mock_repo = MagicMock(spec=DemoUserRepository)
        mock_repo.ensure_indexes = AsyncMock()
        mock_repo.find_by_user_id = AsyncMock(return_value=None)

        with patch("backend.scripts.seed_demo_users.DemoUserRepository", return_value=mock_repo):
            # Dry run
            await run_seed(apply=False, env_dict=self.valid_env)
            mock_repo.ensure_indexes.assert_not_called()

            # Apply
            await run_seed(apply=True, env_dict=self.valid_env)
            mock_repo.ensure_indexes.assert_called_once()

    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    async def test_19_connection_always_closes_after_success_or_failure(self, mock_mgr):
        mock_instance = MagicMock()
        mock_instance.connect = AsyncMock()
        mock_instance.ping = AsyncMock()
        mock_instance.get_database = MagicMock()
        mock_instance.close = AsyncMock()
        mock_mgr.return_value = mock_instance

        mock_repo = MagicMock(spec=DemoUserRepository)
        mock_repo.ensure_indexes = AsyncMock()
        mock_repo.find_by_user_id = AsyncMock(side_effect=RuntimeError("Unexpected DB crash"))

        with patch("backend.scripts.seed_demo_users.DemoUserRepository", return_value=mock_repo):
            await run_seed(apply=True, env_dict=self.valid_env)

        mock_instance.close.assert_called_once()

    def test_20_no_delete_drop_broad_operation_exists(self):
        import inspect
        from backend.scripts import seed_demo_users
        source = inspect.getsource(seed_demo_users)

        self.assertNotIn("delete_many", source)
        self.assertNotIn("drop_collection", source)
        self.assertNotIn("drop_database", source)

    def test_21_no_http_seed_route_exists(self):
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        for route in routes:
            self.assertNotIn("seed", route)

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("backend.scripts.seed_demo_users.DemoDatabaseConnectionManager")
    @patch("backend.scripts.seed_demo_users.DemoUserRepository")
    @patch("backend.scripts.seed_demo_users.hash_password")
    async def test_22_dry_run_is_completely_offline_and_makes_zero_network_secret_or_db_calls(
        self, mock_hash, mock_repo, mock_mgr, mock_stdout
    ):
        offline_env = {
            "APP_ENV": "development",
            "FORECASTING_DEMO_ENABLED": "true",
            "FORECASTING_DEMO_DATABASE": "r26_disease_forecasting_demo",
        }
        code = await run_seed(apply=False, env_dict=offline_env)

        self.assertEqual(code, 0)
        mock_mgr.assert_not_called()
        mock_repo.assert_not_called()
        mock_hash.assert_not_called()

        out = mock_stdout.getvalue()
        self.assertIn("WOULD CREATE OR UPDATE", out)
        self.assertIn("Summary: Planned accounts=3, Database writes=0, Network calls=0", out)
        self.assertNotIn("Created=3", out)

    def test_23_no_insecure_tls_or_list_database_code_in_script(self):
        import inspect
        from backend.scripts import seed_demo_users
        source = inspect.getsource(seed_demo_users)

        self.assertNotIn("tlsAllowInvalidCertificates", source)
        self.assertNotIn("tlsAllowInvalidHostnames", source)
        self.assertNotIn("list_database_names", source)
        self.assertNotIn("list_collection_names", source)


if __name__ == "__main__":
    unittest.main()
