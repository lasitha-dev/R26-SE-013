"""
Unit tests for backend/components/demo_auth/service.py using IsolatedAsyncioTestCase and AsyncMock.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
import jwt

from backend.components.demo_auth.models import (
    Role,
    ScopeLevel,
    DemoUserDocument,
    ViewerContextResponse,
)
from backend.components.demo_auth.repository import (
    DemoUserRepository,
    DemoUserRepositoryError,
)
from backend.components.demo_auth.service import (
    DemoAuthService,
    DemoAuthError,
    DemoAuthUnavailableError,
    DemoLoginResult,
    GENERIC_AUTH_ERROR_MESSAGE,
    SERVICE_UNAVAILABLE_ERROR_MESSAGE,
)
from backend.core.demo_auth_config import DemoAuthConfig
from backend.core.demo_security import hash_password, create_access_token


class TestDemoAuthService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.config = DemoAuthConfig(
            enabled=True,
            jwt_secret="TEST_SECRET_KEY_FOR_DEMO_SERVICE_UNIT_TESTS_12345",
            jwt_algorithm="HS256",
            expire_minutes=30,
        )

        self.mock_repo = MagicMock(spec=DemoUserRepository)

        self.raw_password = "SecurePassword123!"
        self.password_hash = hash_password(self.raw_password)

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

        self.user = DemoUserDocument(
            schemaVersion="1.0",
            userId="DEMO_USER_FARMER_001",
            loginName="farmer_demo",
            passwordHash=self.password_hash,
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

        self.service = DemoAuthService(self.mock_repo, self.config)

    async def test_1_successful_login_returns_only_access_token_token_type_expires_in(self):
        self.mock_repo.find_by_login_name = AsyncMock(return_value=self.user)

        res = await self.service.authenticate("farmer_demo", self.raw_password)
        self.assertIsInstance(res, DemoLoginResult)

        res_dict = res.model_dump()
        self.assertEqual(set(res_dict.keys()), {"accessToken", "tokenType", "expiresIn"})
        self.assertEqual(res_dict["tokenType"], "bearer")
        self.assertEqual(res_dict["expiresIn"], 1800)

    async def test_2_login_name_is_trimmed_and_lowercased(self):
        self.mock_repo.find_by_login_name = AsyncMock(return_value=self.user)

        await self.service.authenticate("  FARMER_DEMO  ", self.raw_password)

        self.mock_repo.find_by_login_name.assert_called_once_with("farmer_demo")

    async def test_3_correct_password_succeeds(self):
        self.mock_repo.find_by_login_name = AsyncMock(return_value=self.user)

        res = await self.service.authenticate("farmer_demo", self.raw_password)
        self.assertTrue(len(res.accessToken) > 10)

    async def test_4_wrong_password_returns_generic_error(self):
        self.mock_repo.find_by_login_name = AsyncMock(return_value=self.user)

        with self.assertRaises(DemoAuthError) as ctx:
            await self.service.authenticate("farmer_demo", "WrongPassword123!")

        self.assertEqual(str(ctx.exception), GENERIC_AUTH_ERROR_MESSAGE)

    async def test_5_unknown_user_returns_the_same_generic_error(self):
        self.mock_repo.find_by_login_name = AsyncMock(return_value=None)

        with self.assertRaises(DemoAuthError) as ctx:
            await self.service.authenticate("unknown_user", self.raw_password)

        self.assertEqual(str(ctx.exception), GENERIC_AUTH_ERROR_MESSAGE)

    async def test_6_disabled_user_returns_the_same_generic_error(self):
        disabled_user = self.user.model_copy(update={"enabled": False})
        self.mock_repo.find_by_login_name = AsyncMock(return_value=disabled_user)

        with self.assertRaises(DemoAuthError) as ctx:
            await self.service.authenticate("farmer_demo", self.raw_password)

        self.assertEqual(str(ctx.exception), GENERIC_AUTH_ERROR_MESSAGE)

    @patch("backend.components.demo_auth.service.verify_password")
    async def test_7_missing_user_performs_dummy_password_verification(self, mock_verify):
        mock_verify.return_value = False
        self.mock_repo.find_by_login_name = AsyncMock(return_value=None)

        with self.assertRaises(DemoAuthError):
            await self.service.authenticate("nonexistent", self.raw_password)

        mock_verify.assert_called_once()

    async def test_8_empty_login_name_fails_before_repository_query(self):
        self.mock_repo.find_by_login_name = AsyncMock()

        for bad_login in ["", "   ", None, 123]:
            with self.assertRaises(DemoAuthError) as ctx:
                await self.service.authenticate(bad_login, self.raw_password)
            self.assertEqual(str(ctx.exception), GENERIC_AUTH_ERROR_MESSAGE)

        self.mock_repo.find_by_login_name.assert_not_called()

    async def test_9_empty_password_fails_safely(self):
        self.mock_repo.find_by_login_name = AsyncMock()

        for bad_pass in ["", None, 123]:
            with self.assertRaises(DemoAuthError) as ctx:
                await self.service.authenticate("farmer_demo", bad_pass)
            self.assertEqual(str(ctx.exception), GENERIC_AUTH_ERROR_MESSAGE)

        self.mock_repo.find_by_login_name.assert_not_called()

    async def test_10_password_hash_absent_from_login_result(self):
        self.mock_repo.find_by_login_name = AsyncMock(return_value=self.user)

        res = await self.service.authenticate("farmer_demo", self.raw_password)
        res_dict = res.model_dump()

        self.assertNotIn("password", res_dict)
        self.assertNotIn("passwordHash", res_dict)

    async def test_11_role_scope_permissions_absent_from_token_payload_and_result(self):
        self.mock_repo.find_by_login_name = AsyncMock(return_value=self.user)

        res = await self.service.authenticate("farmer_demo", self.raw_password)
        res_dict = res.model_dump()

        self.assertNotIn("role", res_dict)
        self.assertNotIn("permissions", res_dict)
        self.assertNotIn("authorization", res_dict)

        # Inspect raw JWT claims
        decoded_raw = jwt.decode(
            res.accessToken,
            self.config.jwt_secret,
            algorithms=[self.config.jwt_algorithm],
            audience="r26-disease-forecasting-frontend",
            issuer="r26-disease-forecasting-demo",
        )
        self.assertNotIn("role", decoded_raw)
        self.assertNotIn("permissions", decoded_raw)
        self.assertNotIn("authorization", decoded_raw)

    async def test_12_valid_token_reloads_user_by_decoded_user_id(self):
        token = create_access_token(self.user.userId, self.config)
        self.mock_repo.find_by_user_id = AsyncMock(return_value=self.user)

        resolved_user = await self.service.resolve_current_user(token)

        self.assertEqual(resolved_user.userId, self.user.userId)
        self.mock_repo.find_by_user_id.assert_called_once_with(self.user.userId)

    async def test_13_invalid_token_produces_generic_auth_error(self):
        with self.assertRaises(DemoAuthError) as ctx:
            await self.service.resolve_current_user("invalid.jwt.token")

        self.assertEqual(str(ctx.exception), GENERIC_AUTH_ERROR_MESSAGE)

    async def test_14_expired_token_produces_generic_auth_error(self):
        # Create expired token config
        expired_config = DemoAuthConfig(
            enabled=True,
            jwt_secret=self.config.jwt_secret,
            jwt_algorithm=self.config.jwt_algorithm,
            expire_minutes=5,
        )
        # Manually encode an expired token
        payload = {
            "sub": self.user.userId,
            "iss": "r26-disease-forecasting-demo",
            "aud": "r26-disease-forecasting-frontend",
            "exp": 1000000000,  # Expired timestamp
            "iat": 900000000,
            "jti": "test_jti",
        }
        expired_token = jwt.encode(payload, expired_config.jwt_secret, algorithm=expired_config.jwt_algorithm)

        with self.assertRaises(DemoAuthError) as ctx:
            await self.service.resolve_current_user(expired_token)

        self.assertEqual(str(ctx.exception), GENERIC_AUTH_ERROR_MESSAGE)

    async def test_15_missing_database_user_after_valid_token_is_rejected(self):
        token = create_access_token(self.user.userId, self.config)
        self.mock_repo.find_by_user_id = AsyncMock(return_value=None)

        with self.assertRaises(DemoAuthError) as ctx:
            await self.service.resolve_current_user(token)

        self.assertEqual(str(ctx.exception), GENERIC_AUTH_ERROR_MESSAGE)

    async def test_16_disabled_user_after_token_issuance_is_rejected(self):
        token = create_access_token(self.user.userId, self.config)
        disabled_user = self.user.model_copy(update={"enabled": False})
        self.mock_repo.find_by_user_id = AsyncMock(return_value=disabled_user)

        with self.assertRaises(DemoAuthError) as ctx:
            await self.service.resolve_current_user(token)

        self.assertEqual(str(ctx.exception), GENERIC_AUTH_ERROR_MESSAGE)

    async def test_17_get_viewer_context_returns_the_exact_canonical_shape(self):
        token = create_access_token(self.user.userId, self.config)
        self.mock_repo.find_by_user_id = AsyncMock(return_value=self.user)

        vc = await self.service.get_viewer_context(token)

        self.assertIsInstance(vc, ViewerContextResponse)
        self.assertEqual(vc.userId, self.user.userId)
        self.assertEqual(vc.role, Role.FARMER)

    async def test_18_changed_permissions_appear_on_next_viewer_context_request(self):
        token = create_access_token(self.user.userId, self.config)

        # Initial call
        self.mock_repo.find_by_user_id = AsyncMock(return_value=self.user)
        vc1 = await self.service.get_viewer_context(token)
        self.assertFalse(vc1.permissions.viewModelTransparency)

        # Update user permissions in repository
        updated_permissions = dict(self.valid_permissions)
        updated_permissions["viewModelTransparency"] = True
        updated_user = self.user.model_copy(update={"permissions": updated_permissions})

        self.mock_repo.find_by_user_id = AsyncMock(return_value=updated_user)

        # Second call with same token
        vc2 = await self.service.get_viewer_context(token)
        self.assertTrue(vc2.permissions.viewModelTransparency)

    async def test_19_changed_districts_appear_on_next_viewer_context_request(self):
        # Test with Vet role
        vet_auth = {
            "scopeLevel": ScopeLevel.DISTRICT,
            "registeredFarmDistrict": None,
            "authorizedDistricts": ["Gampaha"],
            "assignedFarmIds": [],
        }
        vet_user = self.user.model_copy(update={
            "userId": "DEMO_USER_VET_001",
            "role": Role.VETERINARY_OFFICER,
            "authorization": vet_auth,
        })
        token = create_access_token(vet_user.userId, self.config)

        self.mock_repo.find_by_user_id = AsyncMock(return_value=vet_user)
        vc1 = await self.service.get_viewer_context(token)
        self.assertEqual(vc1.authorization.authorizedDistricts, ["Gampaha"])

        # Update districts in database
        updated_auth = dict(vet_auth)
        updated_auth["authorizedDistricts"] = ["Gampaha", "Colombo"]
        updated_vet_user = vet_user.model_copy(update={"authorization": updated_auth})

        self.mock_repo.find_by_user_id = AsyncMock(return_value=updated_vet_user)
        vc2 = await self.service.get_viewer_context(token)
        self.assertEqual(vc2.authorization.authorizedDistricts, ["Gampaha", "Colombo"])

    async def test_20_service_does_not_trust_caller_token_role_or_scopes(self):
        # Token only contains sub (user_id), no role or scope
        token = create_access_token(self.user.userId, self.config)
        self.mock_repo.find_by_user_id = AsyncMock(return_value=self.user)

        user = await self.service.resolve_current_user(token)
        self.assertEqual(user.role, Role.FARMER)

    async def test_21_repository_infrastructure_error_becomes_sanitized_service_unavailable_error(self):
        self.mock_repo.find_by_login_name = AsyncMock(side_effect=DemoUserRepositoryError("DB connection failed"))

        with self.assertRaises(DemoAuthUnavailableError) as ctx:
            await self.service.authenticate("farmer_demo", self.raw_password)

        self.assertEqual(str(ctx.exception), SERVICE_UNAVAILABLE_ERROR_MESSAGE)

    def test_22_no_sensitive_value_appears_in_errors_or_service_repr(self):
        service_repr = repr(self.service)
        self.assertNotIn("TEST_SECRET", service_repr)
        self.assertNotIn("$argon2", service_repr)

    def test_23_service_creates_no_mongodb_client(self):
        # Verify repository was injected and service does not create any PyMongo client
        self.assertEqual(self.service._repository, self.mock_repo)


if __name__ == "__main__":
    unittest.main()
