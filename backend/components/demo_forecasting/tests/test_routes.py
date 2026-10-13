"""
Unit tests for protected role-scoped demo forecasting routes.
Uses FastAPI TestClient and mocks auth_service and forecasting services.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from datetime import datetime, timezone
from backend.components.demo_auth.models import DemoUserDocument, DemoAuthorization, DemoPermissions, Role, ScopeLevel
from backend.components.demo_auth.routes import extract_bearer_token, get_demo_auth_service
from backend.components.demo_auth.service import DemoAuthService, DemoAuthError, DemoAuthUnavailableError
from backend.components.demo_forecasting.routes import router as demo_forecasting_router, get_current_demo_user
from backend.components.risk_forecasting.schemas import (
    FMDDistrictForecastResponse,
    LSDDistrictForecastResponse,
    DistrictForecastItem,
)
from backend.main import app as main_app


def _create_mock_user(
    user_id: str,
    role: str,
    scope_level: str,
    registered_farm_district: str = None,
    authorized_districts: list = None,
    assigned_farm_ids: list = None,
) -> DemoUserDocument:
    role_enum = Role(role) if role in Role.__members__ else role
    scope_enum = ScopeLevel(scope_level) if scope_level in ScopeLevel.__members__ else scope_level
    now = datetime.now(timezone.utc)

    if role == "FARMER":
        auth_districts = [registered_farm_district] if registered_farm_district else []
        assigned_farms = []
    elif role == "VETERINARY_OFFICER":
        auth_districts = authorized_districts if authorized_districts is not None else ["Jaffna"]
        assigned_farms = assigned_farm_ids or []
    else:  # DAPH_OFFICIAL
        auth_districts = authorized_districts if authorized_districts is not None else ["Jaffna"]
        assigned_farms = []

    auth = DemoAuthorization.model_construct(
        scopeLevel=scope_enum,
        registeredFarmDistrict=registered_farm_district,
        authorizedDistricts=auth_districts,
        assignedFarmIds=assigned_farms,
    )

    perms = DemoPermissions.model_construct(
        viewDataQuality=True,
        viewModelTransparency=True,
        manageAlerts=False,
        recordResponse=False,
        viewReports=True,
    )

    return DemoUserDocument.model_construct(
        schemaVersion="1.0",
        userId=f"DEMO_USER_{user_id}",
        loginName=f"{user_id.lower()}@demo.local",
        role=role_enum,
        passwordHash="$argon2id$v=19$m=65536,t=3,p=4$dummy$dummy",
        authorization=auth,
        permissions=perms,
        enabled=True,
        tokenVersion=1,
        isSynthetic=True,
        dataOrigin="SYNTHETIC_DEMO",
        scientificUseAllowed=False,
        createdAt=now,
        updatedAt=now,
    )




class TestDemoForecastingRoutes(unittest.TestCase):

    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(demo_forecasting_router, prefix="/api/v1/demo-forecasting")
        self.client = TestClient(self.app)

        self.mock_auth_service = AsyncMock(spec=DemoAuthService)
        self.app.dependency_overrides[get_demo_auth_service] = lambda: self.mock_auth_service

        self.mock_fmd_res = FMDDistrictForecastResponse(
            disease="FMD",
            target_year=2024,
            target_month=1,
            target_month_name="January",
            model_variant="30_feature_baseline",
            total_districts=2,
            high_risk_count=1,
            medium_risk_count=1,
            low_risk_count=0,
            districts=[
                DistrictForecastItem(district="Jaffna", probability_pct=65.0, risk_level="HIGH", predicted_severity="MEDIUM"),
                DistrictForecastItem(district="Kilinochchi", probability_pct=45.0, risk_level="MEDIUM", predicted_severity="LOW"),
            ],
            exact_data_district_count=2,
            historical_proxy_district_count=0,
            historical_median_district_count=0,
            data_quality_status="EXACT",
            data_quality_message="All exact",
        )

        self.mock_lsd_res = LSDDistrictForecastResponse(
            disease="LSD",
            target_year=2024,
            target_month=1,
            target_month_name="January",
            total_districts=2,
            high_risk_count=1,
            medium_risk_count=0,
            low_risk_count=1,
            districts=[
                DistrictForecastItem(district="Jaffna", probability_pct=72.0, risk_level="HIGH", predicted_severity="HIGH"),
                DistrictForecastItem(district="Kilinochchi", probability_pct=15.0, risk_level="LOW", predicted_severity="LOW"),
            ],
            lag1_data_status="UNAVAILABLE",
            lag1_verified_district_count=0,
            lag1_unavailable_district_count=2,
            lag1_message="Unavailable",
            exact_data_district_count=2,
            historical_proxy_district_count=0,
            historical_median_district_count=0,
            data_quality_status="EXACT",
            data_quality_message="All exact",
        )

    def tearDown(self):
        self.app.dependency_overrides.clear()

    # 1. Registration tests
    def test_01_protected_routes_registered_on_main_app(self):
        routes = [route.path for route in main_app.routes]
        self.assertIn("/api/v1/demo-forecasting/forecast/fmd", routes)
        self.assertIn("/api/v1/demo-forecasting/forecast/lsd", routes)

    # 2. Existing six routes preservation
    def test_02_existing_risk_forecasting_routes_retained(self):
        routes = [route.path for route in main_app.routes]
        self.assertIn("/api/v1/risk-forecasting/health", routes)
        self.assertIn("/api/v1/risk-forecasting/districts", routes)
        self.assertIn("/api/v1/risk-forecasting/predict/fmd", routes)
        self.assertIn("/api/v1/risk-forecasting/predict/lsd", routes)
        self.assertIn("/api/v1/risk-forecasting/forecast/fmd", routes)
        self.assertIn("/api/v1/risk-forecasting/forecast/lsd", routes)

    # 3, 4, 5. Missing / Malformed / Invalid Bearer token
    def test_03_missing_token_returns_401(self):
        res = self.client.post("/api/v1/demo-forecasting/forecast/fmd", json={"target_month": 1})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json(), {"detail": "Invalid authentication credentials."})
        self.assertEqual(res.headers.get("WWW-Authenticate"), "Bearer")

    def test_04_malformed_token_returns_401(self):
        res = self.client.post(
            "/api/v1/demo-forecasting/forecast/fmd",
            json={"target_month": 1},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json(), {"detail": "Invalid authentication credentials."})

    def test_05_invalid_token_returns_401(self):
        self.mock_auth_service.resolve_current_user.side_effect = DemoAuthError("Token invalid")
        res = self.client.post(
            "/api/v1/demo-forecasting/forecast/fmd",
            json={"target_month": 1},
            headers={"Authorization": "Bearer invalid_token"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json(), {"detail": "Invalid authentication credentials."})

    # 6. Auth reloads current user on every request
    def test_06_auth_reloads_current_user_on_every_request(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast", return_value=self.mock_fmd_res):
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "district": "Jaffna"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 200)
            self.mock_auth_service.resolve_current_user.assert_called_once_with("valid_token")

    # 7. Farmer can forecast registeredFarmDistrict
    def test_07_farmer_can_forecast_registered_farm_district(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast", return_value=self.mock_fmd_res) as mock_fc:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "district": "Jaffna"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("X-Demo-Authorization"), "role-scoped")
            data = res.json()
            self.assertEqual(data["total_districts"], 1)
            self.assertEqual(data["districts"][0]["district"], "Jaffna")
            mock_fc.assert_called_once()

    # 8. Farmer cannot forecast another district
    def test_08_farmer_cannot_forecast_another_district(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast") as mock_fc:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "district": "Colombo"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 403)
            self.assertEqual(res.json(), {"detail": "Forecast access to the requested district is forbidden."})
            mock_fc.assert_not_called()

    # 9. Vet can forecast explicitly authorized districts
    def test_09_vet_can_forecast_authorized_districts(self):
        user = _create_mock_user("VET_1", "VETERINARY_OFFICER", "PROVINCE", authorized_districts=["Jaffna", "Kilinochchi"])
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast", return_value=self.mock_fmd_res):
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "districts": ["Jaffna", "Kilinochchi"]},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["total_districts"], 2)

    # 10. Vet cannot forecast district outside authorizedDistricts
    def test_10_vet_cannot_forecast_unauthorized_district(self):
        user = _create_mock_user("VET_1", "VETERINARY_OFFICER", "PROVINCE", authorized_districts=["Jaffna", "Kilinochchi"])
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast") as mock_fc:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "district": "Kandy"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 403)
            mock_fc.assert_not_called()

    # 11. Vet assignedFarmIds do not expand district forecasting scope
    def test_11_vet_assigned_farm_ids_do_not_expand_district_scope(self):
        user = _create_mock_user(
            "VET_1", "VETERINARY_OFFICER", "DISTRICT",
            authorized_districts=["Jaffna"],
            assigned_farm_ids=["FARM_COLOMBO_001"]
        )
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast") as mock_fc:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "district": "Colombo"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 403)
            mock_fc.assert_not_called()

    # 12. DAPH can forecast explicitly authorized districts
    def test_12_daph_can_forecast_authorized_districts(self):
        user = _create_mock_user("DAPH_1", "DAPH_OFFICIAL", "PROVINCE", authorized_districts=["Jaffna", "Kilinochchi"])
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.lsd_service.compute_forecast", return_value=self.mock_lsd_res):
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/lsd",
                json={"target_month": 1, "districts": ["Jaffna"]},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("X-Demo-Authorization"), "role-scoped")

    # 13. NATIONAL DAPH does not auto-expand empty/partial array
    def test_13_national_daph_does_not_auto_expand(self):
        user = _create_mock_user("DAPH_1", "DAPH_OFFICIAL", "NATIONAL", authorized_districts=["Jaffna"])
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.lsd_service.compute_forecast") as mock_fc:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/lsd",
                json={"target_month": 1, "district": "Colombo"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 403)
            mock_fc.assert_not_called()

    # 14. Empty district authorization fails closed
    def test_14_empty_district_authorization_fails_closed(self):
        user = _create_mock_user("VET_1", "VETERINARY_OFFICER", "DISTRICT", authorized_districts=[])
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast") as mock_fc:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 403)
            mock_fc.assert_not_called()

    # 15. Invalid role/scope combination fails closed
    def test_15_invalid_role_scope_combination_fails_closed(self):
        user = _create_mock_user("FARMER_1", "FARMER", "NATIONAL", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast") as mock_fc:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "district": "Jaffna"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 403)
            mock_fc.assert_not_called()

    # 16. Multi-district request rejects if even one district is unauthorized
    def test_16_multi_district_request_rejects_if_one_unauthorized(self):
        user = _create_mock_user("VET_1", "VETERINARY_OFFICER", "PROVINCE", authorized_districts=["Jaffna", "Kilinochchi"])
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast") as mock_fc:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "districts": ["Jaffna", "Colombo"]},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 403)
            mock_fc.assert_not_called()

    # 17. Unauthorized requests never invoke forecasting/model functions
    def test_17_unauthorized_requests_never_invoke_forecast_functions(self):
        self.mock_auth_service.resolve_current_user.side_effect = DemoAuthError("Unauthorized")

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast") as mock_fmd, \
             patch("backend.components.demo_forecasting.routes.lsd_service.compute_forecast") as mock_lsd:
            self.client.post("/api/v1/demo-forecasting/forecast/fmd", json={"target_month": 1})
            self.client.post("/api/v1/demo-forecasting/forecast/lsd", json={"target_month": 1})
            mock_fmd.assert_not_called()
            mock_lsd.assert_not_called()

    # 18. FMD route invokes only FMD forecasting
    def test_18_fmd_route_invokes_only_fmd_forecasting(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast", return_value=self.mock_fmd_res) as mock_fmd, \
             patch("backend.components.demo_forecasting.routes.lsd_service.compute_forecast") as mock_lsd:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "district": "Jaffna"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 200)
            mock_fmd.assert_called_once()
            mock_lsd.assert_not_called()

    # 19. LSD route invokes only LSD forecasting
    def test_19_lsd_route_invokes_only_lsd_forecasting(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast") as mock_fmd, \
             patch("backend.components.demo_forecasting.routes.lsd_service.compute_forecast", return_value=self.mock_lsd_res) as mock_lsd:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/lsd",
                json={"target_month": 1, "district": "Jaffna"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 200)
            mock_lsd.assert_called_once()
            mock_fmd.assert_not_called()

    # 20. Frontend-supplied role/scope overrides ignored
    def test_20_frontend_role_scope_override_ignored(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast") as mock_fc:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={
                    "target_month": 1,
                    "district": "Colombo",
                    "role": "DAPH_OFFICIAL",
                    "authorizedDistricts": ["Colombo", "Jaffna"],
                },
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 403)
            mock_fc.assert_not_called()

    # 21. Operational record fields ignored and never reach forecast service
    def test_21_operational_record_fields_ignored(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast", return_value=self.mock_fmd_res) as mock_fc:
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={
                    "target_month": 1,
                    "district": "Jaffna",
                    "demo_farms": [{"farmId": "FARM_1"}],
                    "demo_surveillance_records": [{"recordId": "REC_1"}],
                },
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 200)
            # Verify compute_forecast received only standard target_month, year, model_variant kwargs
            kwargs = mock_fc.call_args.kwargs
            self.assertNotIn("demo_farms", kwargs)
            self.assertNotIn("demo_surveillance_records", kwargs)

    # 22. Existing request validation still returns 422
    def test_22_request_validation_failure_returns_422(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        res = self.client.post(
            "/api/v1/demo-forecasting/forecast/fmd",
            json={"target_month": 13},  # Invalid month > 12
            headers={"Authorization": "Bearer valid_token"},
        )
        self.assertEqual(res.status_code, 422)

    # 23. Scientific response shape preserved
    def test_23_scientific_response_shape_preserved(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast", return_value=self.mock_fmd_res):
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "district": "Jaffna"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["disease"], "FMD")
            self.assertEqual(data["target_year"], 2024)
            self.assertEqual(data["target_month"], 1)
            self.assertIn("districts", data)

    # 24. X-Demo-Authorization header present
    def test_24_demo_authorization_header_present(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast", return_value=self.mock_fmd_res):
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "district": "Jaffna"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("X-Demo-Authorization"), "role-scoped")

    # 25. Errors sanitization check
    def test_25_sanitized_errors_no_secrets_or_ids(self):
        self.mock_auth_service.resolve_current_user.side_effect = DemoAuthError("Secret MongoDB URI error")
        res = self.client.post(
            "/api/v1/demo-forecasting/forecast/fmd",
            json={"target_month": 1},
            headers={"Authorization": "Bearer secret_token_xyz"},
        )
        self.assertEqual(res.status_code, 401)
        body = res.text
        self.assertNotIn("secret_token_xyz", body)
        self.assertNotIn("MongoDB", body)
        self.assertEqual(res.json(), {"detail": "Invalid authentication credentials."})

    # 26, 27, 28. Implementation code inspection assertions
    def test_26_no_async_mongo_client_in_routes(self):
        import backend.components.demo_forecasting.routes as routes_module
        source = routes_module.__file__
        with open(source, "r") as f:
            code = f.read()
        self.assertNotIn("AsyncMongoClient", code)
        self.assertNotIn("motor", code)

    def test_27_no_operational_imports_in_demo_forecasting_routes(self):
        import backend.components.demo_forecasting.routes as routes_module
        source = routes_module.__file__
        with open(source, "r") as f:
            code = f.read()
        self.assertNotIn("demo_farms", code)
        self.assertNotIn("demo_surveillance_records", code)
        self.assertNotIn("DemoFarmRepository", code)

    def test_28_no_database_write_operations(self):
        import backend.components.demo_forecasting.routes as routes_module
        source = routes_module.__file__
        with open(source, "r") as f:
            code = f.read()
        self.assertNotIn("insert_one", code)
        self.assertNotIn("update_one", code)
        self.assertNotIn("delete_one", code)

    # 29. Service unavailable handled gracefully
    def test_29_service_unavailable_handled_gracefully(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast", side_effect=RuntimeError("Model not loaded")):
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "district": "Jaffna"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 503)
            self.assertEqual(res.json(), {"detail": "Forecast service is currently unavailable."})

    # 30. Internal error handled gracefully
    def test_30_internal_error_handled_gracefully(self):
        user = _create_mock_user("FARMER_1", "FARMER", "FARM", registered_farm_district="Jaffna")
        self.mock_auth_service.resolve_current_user.return_value = user

        with patch("backend.components.demo_forecasting.routes.fmd_service.compute_forecast", side_effect=ValueError("Unexpected Error")):
            res = self.client.post(
                "/api/v1/demo-forecasting/forecast/fmd",
                json={"target_month": 1, "district": "Jaffna"},
                headers={"Authorization": "Bearer valid_token"},
            )
            self.assertEqual(res.status_code, 500)
            self.assertEqual(res.json(), {"detail": "FMD forecast failed."})


if __name__ == "__main__":
    unittest.main()
