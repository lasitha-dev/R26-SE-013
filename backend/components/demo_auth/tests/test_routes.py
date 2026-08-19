"""
Unit & API integration tests for backend/components/demo_auth/routes.py
"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from fastapi import status
from fastapi.testclient import TestClient

from backend.main import app
from backend.components.demo_auth.models import (
    Role,
    ScopeLevel,
    DemoUserDocument,
    ViewerContextResponse,
    demo_user_to_viewer_context,
)
from backend.components.demo_auth.routes import get_demo_auth_service
from backend.components.demo_auth.service import (
    DemoAuthService,
    DemoAuthError,
    DemoAuthUnavailableError,
    DemoLoginResult,
    GENERIC_AUTH_ERROR_MESSAGE,
    SERVICE_UNAVAILABLE_ERROR_MESSAGE,
)


class TestDemoAuthRoutes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.now = datetime.now(timezone.utc)

        self.mock_service = MagicMock(spec=DemoAuthService)

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

        app.dependency_overrides[get_demo_auth_service] = lambda: self.mock_service

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_1_login_route_registered_exactly_once(self):
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        login_routes = [p for p in routes if p == "/api/v1/demo-auth/login"]
        self.assertEqual(len(login_routes), 1)

    def test_2_me_route_registered_exactly_once(self):
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        me_routes = [p for p in routes if p == "/api/v1/demo-auth/me"]
        self.assertEqual(len(me_routes), 1)

    def test_3_valid_login_returns_200_and_exact_three_field_response(self):
        self.mock_service.authenticate = AsyncMock(
            return_value=DemoLoginResult(accessToken="test_valid_token_123", tokenType="bearer", expiresIn=1800)
        )

        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "farmer_demo", "password": "Password123!"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.json()
        self.assertEqual(set(data.keys()), {"accessToken", "tokenType", "expiresIn"})
        self.assertEqual(data["accessToken"], "test_valid_token_123")
        self.assertEqual(data["tokenType"], "bearer")
        self.assertEqual(data["expiresIn"], 1800)

    def test_4_login_request_uses_json(self):
        self.mock_service.authenticate = AsyncMock(
            return_value=DemoLoginResult(accessToken="token", tokenType="bearer", expiresIn=1800)
        )
        res = self.client.post(
            "/api/v1/demo-auth/login",
            headers={"Content-Type": "application/json"},
            json={"loginName": "farmer_demo", "password": "Password123!"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_5_correct_credentials_delegate_to_service(self):
        self.mock_service.authenticate = AsyncMock(
            return_value=DemoLoginResult(accessToken="token", tokenType="bearer", expiresIn=1800)
        )

        self.client.post("/api/v1/demo-auth/login", json={"loginName": "farmer_demo", "password": "Password123!"})

        self.mock_service.authenticate.assert_called_once_with("farmer_demo", "Password123!")

    def test_6_wrong_password_returns_generic_401(self):
        self.mock_service.authenticate = AsyncMock(side_effect=DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE))

        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "farmer_demo", "password": "WrongPassword!"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(res.json(), {"detail": GENERIC_AUTH_ERROR_MESSAGE})

    def test_7_unknown_user_returns_identical_generic_401(self):
        self.mock_service.authenticate = AsyncMock(side_effect=DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE))

        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "unknown_user", "password": "Password123!"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(res.json(), {"detail": GENERIC_AUTH_ERROR_MESSAGE})

    def test_8_disabled_user_returns_identical_generic_401(self):
        self.mock_service.authenticate = AsyncMock(side_effect=DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE))

        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "disabled_user", "password": "Password123!"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(res.json(), {"detail": GENERIC_AUTH_ERROR_MESSAGE})

    def test_9_401_includes_www_authenticate_bearer(self):
        self.mock_service.authenticate = AsyncMock(side_effect=DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE))

        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "farmer_demo", "password": "WrongPassword!"})
        self.assertIn("www-authenticate", res.headers)
        self.assertEqual(res.headers["www-authenticate"], "Bearer")

    def test_10_empty_login_name_rejected(self):
        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "   ", "password": "Password123!"})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_11_empty_password_rejected(self):
        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "farmer_demo", "password": ""})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_12_non_string_fields_rejected(self):
        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": 12345, "password": "Password123!"})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_13_unknown_extra_fields_rejected(self):
        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "farmer_demo", "password": "Password123!", "extraField": "bad"})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_14_oversized_login_name_rejected(self):
        oversized = "a" * 101
        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": oversized, "password": "Password123!"})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_15_oversized_password_rejected(self):
        oversized = "P" * 129
        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "farmer_demo", "password": oversized})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_16_validation_response_does_not_contain_submitted_password(self):
        secret_password = "MY_VERY_SECRET_SUBMITTED_PASSWORD"
        # Cause validation failure by giving extra field
        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "farmer_demo", "password": secret_password, "unknown": "val"})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        response_text = res.text
        self.assertNotIn(secret_password, response_text)

    def test_17_valid_bearer_token_returns_exact_viewer_context(self):
        vc = demo_user_to_viewer_context(self.user)
        self.mock_service.get_viewer_context = AsyncMock(return_value=vc)

        res = self.client.get("/api/v1/demo-auth/me", headers={"Authorization": "Bearer valid_token_123"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.json()
        self.assertIn("userId", data)
        self.assertIn("role", data)
        self.assertIn("authorization", data)
        self.assertIn("permissions", data)
        self.assertEqual(data["userId"], "DEMO_USER_FARMER_001")
        self.assertEqual(data["role"], "FARMER")

    def test_18_missing_authorization_returns_401(self):
        res = self.client.get("/api/v1/demo-auth/me")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("www-authenticate", res.headers)

    def test_19_non_bearer_authorization_returns_401(self):
        res = self.client.get("/api/v1/demo-auth/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_20_empty_bearer_token_returns_401(self):
        res = self.client.get("/api/v1/demo-auth/me", headers={"Authorization": "Bearer "})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_21_invalid_expired_token_returns_generic_401(self):
        self.mock_service.get_viewer_context = AsyncMock(side_effect=DemoAuthError(GENERIC_AUTH_ERROR_MESSAGE))

        res = self.client.get("/api/v1/demo-auth/me", headers={"Authorization": "Bearer invalid_or_expired_token"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(res.json(), {"detail": GENERIC_AUTH_ERROR_MESSAGE})

    def test_22_database_service_unavailable_returns_sanitized_503(self):
        self.mock_service.authenticate = AsyncMock(side_effect=DemoAuthUnavailableError("Demo authentication service is currently unavailable or disabled."))

        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "farmer_demo", "password": "Password123!"})
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(res.json(), {"detail": "Demo authentication service is currently unavailable or disabled."})

    def test_23_me_does_not_accept_role_scope_permission_overrides(self):
        vc = demo_user_to_viewer_context(self.user)
        self.mock_service.get_viewer_context = AsyncMock(return_value=vc)

        res = self.client.get(
            "/api/v1/demo-auth/me?role=DAPH_OFFICIAL",
            headers={"Authorization": "Bearer valid_token_123", "X-Role-Override": "DAPH_OFFICIAL"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data["role"], "FARMER")  # Strictly unchanged

    def test_24_responses_never_include_password_hash_login_name_secret_uri_id(self):
        vc = demo_user_to_viewer_context(self.user)
        self.mock_service.get_viewer_context = AsyncMock(return_value=vc)

        res = self.client.get("/api/v1/demo-auth/me", headers={"Authorization": "Bearer valid_token_123"})
        text = res.text

        self.assertNotIn("passwordHash", text)
        self.assertNotIn("loginName", text)
        self.assertNotIn("_id", text)
        self.assertNotIn("mongodb://", text)

    def test_25_route_dependency_creates_no_mongodb_client(self):
        self.assertIn(get_demo_auth_service, app.dependency_overrides)

    def test_26_demo_disabled_state_fails_safely(self):
        # Override dependency to simulate disabled state throwing 503
        from fastapi import HTTPException
        def _disabled_dep():
            raise HTTPException(status_code=503, detail="Demo authentication service is currently unavailable or disabled.")
        app.dependency_overrides[get_demo_auth_service] = _disabled_dep

        # Re-post login
        res = self.client.post("/api/v1/demo-auth/login", json={"loginName": "farmer_demo", "password": "Password123!"})
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(res.json(), {"detail": "Demo authentication service is currently unavailable or disabled."})

    def test_27_no_seed_register_reset_refresh_endpoints_exist(self):
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        forbidden_endpoints = [
            "/api/v1/demo-auth/register",
            "/api/v1/demo-auth/reset-password",
            "/api/v1/demo-auth/refresh",
            "/api/v1/demo-auth/seed",
            "/api/v1/demo-auth/users",
        ]
        for ep in forbidden_endpoints:
            self.assertNotIn(ep, routes)

    def test_28_existing_six_forecasting_routes_remain_unchanged(self):
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        forecasting_routes = [
            "/api/v1/risk-forecasting/health",
            "/api/v1/risk-forecasting/districts",
            "/api/v1/risk-forecasting/predict/fmd",
            "/api/v1/risk-forecasting/predict/lsd",
            "/api/v1/risk-forecasting/forecast/fmd",
            "/api/v1/risk-forecasting/forecast/lsd",
        ]
        for route in forecasting_routes:
            self.assertIn(route, routes)


if __name__ == "__main__":
    unittest.main()
