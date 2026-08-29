"""
Security and integration tests for FastAPI demo operational data routes.

Uses FastAPI TestClient with dependency overrides and mocked services/repositories.
Verifies HTTP status codes, envelope structures, auth token resolution, role permissions,
query parameter tampering immunity, and sanitized error mapping.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.components.demo_auth.models import (
    Role,
    ScopeLevel,
    DemoAuthorization,
    DemoPermissions,
    DemoUserDocument,
)
from backend.components.demo_auth.service import DemoAuthService, DemoAuthError
from backend.components.demo_operational.models import (
    LivestockType,
    DiseaseCode,
    EvidenceType,
    VerificationStatus,
    SourceModule,
    AlertStatus,
    AlertPriority,
    TaskType,
    TaskStatus,
    DemoFarm,
    DemoSurveillanceRecord,
    DemoAlert,
    DemoResponseTask,
)
from backend.components.demo_auth.routes import extract_bearer_token, get_demo_auth_service
from backend.components.demo_operational.routes import (
    get_current_demo_user,
    get_demo_operational_service,
)
from backend.components.demo_operational.service import (
    DemoOperationalAuthorizationService,
    DemoOperationalForbiddenError,
    DemoOperationalUnavailableError,
)


class TestDemoOperationalRoutes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)
        self.now_utc = datetime.now(timezone.utc)

        # Mock Users
        self.farmer_user = DemoUserDocument(
            userId="DEMO_USER_FARMER_JAFFNA",
            loginName="demo_farmer_jaffna",
            passwordHash="$argon2id$v=19$m=65536,t=3,p=4$dummyhash",
            role=Role.FARMER,
            authorization=DemoAuthorization(
                scopeLevel=ScopeLevel.FARM,
                registeredFarmDistrict="Jaffna",
                authorizedDistricts=["Jaffna"],
                assignedFarmIds=[],
            ),
            permissions=DemoPermissions(
                viewDataQuality=True,
                viewModelTransparency=False,
                manageAlerts=False,
                recordResponse=False,
                viewReports=True,
            ),
            enabled=True,
            createdAt=self.now_utc,
            updatedAt=self.now_utc,
        )

        self.vet_user = DemoUserDocument(
            userId="DEMO_USER_VET_NORTH",
            loginName="demo_vet_north",
            passwordHash="$argon2id$v=19$m=65536,t=3,p=4$dummyhash",
            role=Role.VETERINARY_OFFICER,
            authorization=DemoAuthorization(
                scopeLevel=ScopeLevel.PROVINCE,
                registeredFarmDistrict=None,
                authorizedDistricts=["Jaffna", "Kilinochchi"],
                assignedFarmIds=["DEMO_FARM_JAFFNA_001"],
            ),
            permissions=DemoPermissions(
                viewDataQuality=False,
                viewModelTransparency=True,
                manageAlerts=True,
                recordResponse=True,
                viewReports=True,
            ),
            enabled=True,
            createdAt=self.now_utc,
            updatedAt=self.now_utc,
        )

        self.daph_user = DemoUserDocument(
            userId="DEMO_USER_DAPH_OFFICIAL",
            loginName="demo_daph_official",
            passwordHash="$argon2id$v=19$m=65536,t=3,p=4$dummyhash",
            role=Role.DAPH_OFFICIAL,
            authorization=DemoAuthorization(
                scopeLevel=ScopeLevel.NATIONAL,
                registeredFarmDistrict=None,
                authorizedDistricts=["Jaffna", "Kilinochchi", "Vavuniya"],
                assignedFarmIds=[],
            ),
            permissions=DemoPermissions(
                viewDataQuality=True,
                viewModelTransparency=True,
                manageAlerts=True,
                recordResponse=True,
                viewReports=True,
            ),
            enabled=True,
            createdAt=self.now_utc,
            updatedAt=self.now_utc,
        )

        # Domain mock records
        self.jaffna_farm = DemoFarm(
            farmId="DEMO_FARM_JAFFNA_001",
            displayName="Synthetic Jaffna Farm",
            district="Jaffna",
            ownerUserId="DEMO_USER_FARMER_JAFFNA",
            assignedVetUserIds=["DEMO_USER_VET_NORTH"],
            livestockTypes=[LivestockType.CATTLE],
            active=True,
            createdAt=self.now_utc,
            updatedAt=self.now_utc,
        )

        self.surv_record = DemoSurveillanceRecord(
            surveillanceRecordId="DEMO_SURV_001",
            farmId="DEMO_FARM_JAFFNA_001",
            district="Jaffna",
            diseaseCode=DiseaseCode.FMD,
            observedAt=self.now_utc,
            evidenceType=EvidenceType.FARMER_REPORT,
            verificationStatus=VerificationStatus.REPORTED,
            sourceModule=SourceModule.SYNTHETIC_FARM_REPORTING,
            sourceRecordId="DEMO_SOURCE_001",
            summary="Test summary",
            createdAt=self.now_utc,
            updatedAt=self.now_utc,
        )

        self.alert_record = DemoAlert(
            alertId="DEMO_ALERT_001",
            district="Jaffna",
            diseaseCode=DiseaseCode.FMD,
            status=AlertStatus.OPEN,
            priority=AlertPriority.HIGH,
            issuedAt=self.now_utc,
            sourceSurveillanceRecordIds=["DEMO_SURV_001"],
            affectedFarmIds=["DEMO_FARM_JAFFNA_001"],
            title="Synthetic Alert",
            message="Synthetic alert message",
            createdAt=self.now_utc,
            updatedAt=self.now_utc,
        )

        self.task_record = DemoResponseTask(
            responseTaskId="DEMO_TASK_001",
            alertId="DEMO_ALERT_001",
            assignedOfficerUserId="DEMO_USER_VET_NORTH",
            district="Jaffna",
            farmId="DEMO_FARM_JAFFNA_001",
            taskType=TaskType.FIELD_REVIEW,
            status=TaskStatus.ASSIGNED,
            dueAt=self.now_utc,
            notes="Test notes",
            createdAt=self.now_utc,
            updatedAt=self.now_utc,
        )

    def tearDown(self):
        app.dependency_overrides.clear()

    # 1 & 17 & 18. Route registration verification
    def test_01_routes_registered_correctly(self):
        routes = [r.path for r in app.routes]
        self.assertIn("/api/v1/demo-operational/farms", routes)
        self.assertIn("/api/v1/demo-operational/surveillance-records", routes)
        self.assertIn("/api/v1/demo-operational/alerts", routes)
        self.assertIn("/api/v1/demo-operational/response-tasks", routes)

        # Existing routes remain registered
        self.assertIn("/api/v1/demo-auth/login", routes)
        self.assertIn("/api/v1/demo-auth/me", routes)
        self.assertIn("/api/v1/risk-forecasting/health", routes)

        # Ensure no seed/write/admin routes exist
        for r in routes:
            if r.startswith("/api/v1/demo-operational"):
                self.assertNotIn("seed", r.lower())
                self.assertNotIn("delete", r.lower())
                self.assertNotIn("create", r.lower())

    # 2 & 3. Missing bearer token returns 401 with WWW-Authenticate header
    def test_02_missing_token_returns_401(self):
        for path in [
            "/api/v1/demo-operational/farms",
            "/api/v1/demo-operational/surveillance-records",
            "/api/v1/demo-operational/alerts",
            "/api/v1/demo-operational/response-tasks",
        ]:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.headers.get("WWW-Authenticate"), "Bearer")
            self.assertEqual(res.json(), {"detail": "Invalid authentication credentials."})

    # 4. Invalid bearer token returns 401
    def test_04_invalid_token_returns_401(self):
        mock_auth_service = MagicMock(spec=DemoAuthService)
        mock_auth_service.resolve_current_user = AsyncMock(
            side_effect=DemoAuthError("Invalid authentication credentials.")
        )
        app.dependency_overrides[get_demo_auth_service] = lambda: mock_auth_service

        headers = {"Authorization": "Bearer invalid_token_value"}
        for path in [
            "/api/v1/demo-operational/farms",
            "/api/v1/demo-operational/surveillance-records",
            "/api/v1/demo-operational/alerts",
            "/api/v1/demo-operational/response-tasks",
        ]:
            res = self.client.get(path, headers=headers)
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.headers.get("WWW-Authenticate"), "Bearer")
            self.assertEqual(res.json(), {"detail": "Invalid authentication credentials."})

    # 6. Farmer behavior via API
    def test_06_farmer_routes_behavior(self):
        mock_service = MagicMock(spec=DemoOperationalAuthorizationService)
        mock_service.get_accessible_farms = AsyncMock(return_value=[self.jaffna_farm])
        mock_service.get_accessible_alerts = AsyncMock(return_value=[self.alert_record])
        mock_service.get_accessible_surveillance_records = AsyncMock(
            side_effect=DemoOperationalForbiddenError("Access to requested operational data is forbidden.")
        )
        mock_service.get_accessible_response_tasks = AsyncMock(
            side_effect=DemoOperationalForbiddenError("Access to requested operational data is forbidden.")
        )

        app.dependency_overrides[get_current_demo_user] = lambda: self.farmer_user
        app.dependency_overrides[get_demo_operational_service] = lambda: mock_service

        headers = {"Authorization": "Bearer valid_farmer_token"}

        # Farms -> 200 OK
        res = self.client.get("/api/v1/demo-operational/farms", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["farmId"], "DEMO_FARM_JAFFNA_001")
        self.assertEqual(data["dataOrigin"], "SYNTHETIC_DEMO")
        self.assertFalse(data["scientificUseAllowed"])

        # Alerts -> 200 OK
        res = self.client.get("/api/v1/demo-operational/alerts", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 1)

        # Surveillance -> 403 Forbidden
        res = self.client.get("/api/v1/demo-operational/surveillance-records", headers=headers)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json(), {"detail": "Access to requested operational data is forbidden."})

        # Tasks -> 403 Forbidden
        res = self.client.get("/api/v1/demo-operational/response-tasks", headers=headers)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json(), {"detail": "Access to requested operational data is forbidden."})

    # 7. Vet Officer behavior via API
    def test_07_vet_routes_behavior(self):
        mock_service = MagicMock(spec=DemoOperationalAuthorizationService)
        mock_service.get_accessible_farms = AsyncMock(return_value=[self.jaffna_farm])
        mock_service.get_accessible_surveillance_records = AsyncMock(return_value=[self.surv_record])
        mock_service.get_accessible_alerts = AsyncMock(return_value=[self.alert_record])
        mock_service.get_accessible_response_tasks = AsyncMock(return_value=[self.task_record])

        app.dependency_overrides[get_current_demo_user] = lambda: self.vet_user
        app.dependency_overrides[get_demo_operational_service] = lambda: mock_service

        headers = {"Authorization": "Bearer valid_vet_token"}

        for path in [
            "/api/v1/demo-operational/farms",
            "/api/v1/demo-operational/surveillance-records",
            "/api/v1/demo-operational/alerts",
            "/api/v1/demo-operational/response-tasks",
        ]:
            res = self.client.get(path, headers=headers)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["count"], 1)

    # 8. DAPH Official behavior via API
    def test_08_daph_routes_behavior(self):
        mock_service = MagicMock(spec=DemoOperationalAuthorizationService)
        mock_service.get_accessible_farms = AsyncMock(
            side_effect=DemoOperationalForbiddenError("Access to requested operational data is forbidden.")
        )
        mock_service.get_accessible_surveillance_records = AsyncMock(return_value=[self.surv_record])
        mock_service.get_accessible_alerts = AsyncMock(return_value=[self.alert_record])
        mock_service.get_accessible_response_tasks = AsyncMock(return_value=[self.task_record])

        app.dependency_overrides[get_current_demo_user] = lambda: self.daph_user
        app.dependency_overrides[get_demo_operational_service] = lambda: mock_service

        headers = {"Authorization": "Bearer valid_daph_token"}

        # Farms -> 403
        res = self.client.get("/api/v1/demo-operational/farms", headers=headers)
        self.assertEqual(res.status_code, 403)

        # Surveillance, Alerts, Tasks -> 200
        for path in [
            "/api/v1/demo-operational/surveillance-records",
            "/api/v1/demo-operational/alerts",
            "/api/v1/demo-operational/response-tasks",
        ]:
            res = self.client.get(path, headers=headers)
            self.assertEqual(res.status_code, 200)

    # 9. Query parameter tampering immunity
    def test_09_query_parameters_cannot_override_authorization(self):
        mock_service = MagicMock(spec=DemoOperationalAuthorizationService)
        mock_service.get_accessible_farms = AsyncMock(return_value=[self.jaffna_farm])

        app.dependency_overrides[get_current_demo_user] = lambda: self.farmer_user
        app.dependency_overrides[get_demo_operational_service] = lambda: mock_service

        headers = {"Authorization": "Bearer valid_token"}
        # Attempt to tamper with role/district in query parameters
        res = self.client.get(
            "/api/v1/demo-operational/farms?role=DAPH_OFFICIAL&district=Colombo&ownerUserId=ANY",
            headers=headers,
        )
        self.assertEqual(res.status_code, 200)
        # Service was called with current_user resolved from token, ignoring query params
        mock_service.get_accessible_farms.assert_called_once_with(self.farmer_user, skip=0, limit=50)

    # 10 & 11. Empty results envelope and count verification
    def test_10_empty_results_and_count_matching(self):
        mock_service = MagicMock(spec=DemoOperationalAuthorizationService)
        mock_service.get_accessible_farms = AsyncMock(return_value=[])

        app.dependency_overrides[get_current_demo_user] = lambda: self.farmer_user
        app.dependency_overrides[get_demo_operational_service] = lambda: mock_service

        headers = {"Authorization": "Bearer valid_token"}
        res = self.client.get("/api/v1/demo-operational/farms", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["items"], [])
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["count"], len(data["items"]))

    # 12. Invalid skip/limit returns 422
    def test_12_invalid_pagination_returns_422(self):
        app.dependency_overrides[get_current_demo_user] = lambda: self.farmer_user
        app.dependency_overrides[get_demo_operational_service] = lambda: MagicMock()

        headers = {"Authorization": "Bearer valid_token"}

        # Negative skip
        res = self.client.get("/api/v1/demo-operational/farms?skip=-1", headers=headers)
        self.assertEqual(res.status_code, 422)

        # Limit zero
        res = self.client.get("/api/v1/demo-operational/farms?limit=0", headers=headers)
        self.assertEqual(res.status_code, 422)

        # Limit > 100
        res = self.client.get("/api/v1/demo-operational/farms?limit=101", headers=headers)
        self.assertEqual(res.status_code, 422)

    # 13. Service / infrastructure error returns 503
    def test_13_service_failure_returns_503(self):
        mock_service = MagicMock(spec=DemoOperationalAuthorizationService)
        mock_service.get_accessible_farms = AsyncMock(
            side_effect=DemoOperationalUnavailableError("Operational data service is currently unavailable.")
        )

        app.dependency_overrides[get_current_demo_user] = lambda: self.farmer_user
        app.dependency_overrides[get_demo_operational_service] = lambda: mock_service

        headers = {"Authorization": "Bearer valid_token"}
        res = self.client.get("/api/v1/demo-operational/farms", headers=headers)
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json(), {"detail": "Operational data service is currently unavailable."})

    # 15. Secrets, hashes, _id, JWT secret omitted from responses
    def test_15_sensitive_fields_omitted_from_responses(self):
        mock_service = MagicMock(spec=DemoOperationalAuthorizationService)
        mock_service.get_accessible_farms = AsyncMock(return_value=[self.jaffna_farm])

        app.dependency_overrides[get_current_demo_user] = lambda: self.farmer_user
        app.dependency_overrides[get_demo_operational_service] = lambda: mock_service

        headers = {"Authorization": "Bearer valid_token"}
        res = self.client.get("/api/v1/demo-operational/farms", headers=headers)
        self.assertEqual(res.status_code, 200)
        res_text = res.text
        self.assertNotIn("_id", res_text)
        self.assertNotIn("passwordHash", res_text)
        self.assertNotIn("loginName", res_text)
        self.assertNotIn("secret", res_text)
        self.assertNotIn("mongodb://", res_text)

    # 16. No AsyncMongoClient creation in route module
    def test_16_no_mongo_client_instantiation_in_routes(self):
        import backend.components.demo_operational.routes as routes_mod

        mod_file = routes_mod.__file__
        with open(mod_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("AsyncMongoClient", content)
        self.assertNotIn("MongoClient", content)


if __name__ == "__main__":
    unittest.main()
