"""
Unit tests for DemoOperationalAuthorizationService.
Mocks operational repositories completely.
Verifies RBAC, scope filtering, defence-in-depth, empty-scope short-circuiting, and sanitized error handling.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from backend.components.demo_auth.models import (
    Role,
    ScopeLevel,
    DemoAuthorization,
    DemoPermissions,
    DemoUserDocument,
)
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
from backend.components.demo_operational.repositories import (
    DemoOperationalRepositoryError,
)
from backend.components.demo_operational.service import (
    DemoOperationalAuthorizationService,
    DemoOperationalForbiddenError,
    DemoOperationalUnavailableError,
)


class TestDemoOperationalAuthorizationService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_farm_repo = MagicMock()
        self.mock_surv_repo = MagicMock()
        self.mock_alert_repo = MagicMock()
        self.mock_task_repo = MagicMock()

        self.service = DemoOperationalAuthorizationService(
            self.mock_farm_repo,
            self.mock_surv_repo,
            self.mock_alert_repo,
            self.mock_task_repo,
        )

        self.now_utc = datetime.now(timezone.utc)

        # Mock User Documents
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
                authorizedDistricts=["Jaffna", "Kilinochchi", "Vavuniya"],
                assignedFarmIds=[
                    "DEMO_FARM_JAFFNA_001",
                    "DEMO_FARM_KILINOCHCHI_001",
                    "DEMO_FARM_VAVUNIYA_001",
                ],
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

        # Mock Domain Records
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

        self.other_farmer_farm = DemoFarm(
            farmId="DEMO_FARM_JAFFNA_OTHER",
            displayName="Other Jaffna Farm",
            district="Jaffna",
            ownerUserId="DEMO_USER_OTHER_FARMER",
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

    # --- Farmer Tests (1 to 7) ---

    async def test_01_farmer_sees_only_owned_farm_in_registered_district(self):
        self.mock_farm_repo.list_by_owner_user_id = AsyncMock(
            return_value=[self.jaffna_farm]
        )
        farms = await self.service.get_accessible_farms(self.farmer_user)
        self.assertEqual(len(farms), 1)
        self.assertEqual(farms[0].farmId, "DEMO_FARM_JAFFNA_001")
        self.mock_farm_repo.list_by_owner_user_id.assert_called_once_with(
            "DEMO_USER_FARMER_JAFFNA", skip=0, limit=50
        )

    async def test_02_farmer_cannot_see_another_farm_in_same_district(self):
        self.mock_farm_repo.list_by_owner_user_id = AsyncMock(
            return_value=[self.jaffna_farm, self.other_farmer_farm]
        )
        farms = await self.service.get_accessible_farms(self.farmer_user)
        self.assertEqual(len(farms), 1)
        self.assertEqual(farms[0].farmId, "DEMO_FARM_JAFFNA_001")

    async def test_03_farmer_surveillance_is_forbidden(self):
        with self.assertRaises(DemoOperationalForbiddenError):
            await self.service.get_accessible_surveillance_records(self.farmer_user)

    async def test_04_farmer_alerts_queried_only_by_owned_farm_ids(self):
        self.mock_farm_repo.list_by_owner_user_id = AsyncMock(
            return_value=[self.jaffna_farm]
        )
        self.mock_alert_repo.list_by_farm_ids = AsyncMock(
            return_value=[self.alert_record]
        )
        alerts = await self.service.get_accessible_alerts(self.farmer_user)
        self.assertEqual(len(alerts), 1)
        self.mock_alert_repo.list_by_farm_ids.assert_called_once_with(
            ["DEMO_FARM_JAFFNA_001"], skip=0, limit=50
        )

    async def test_05_farmer_alerts_outside_registered_district_post_filtered(self):
        out_district_alert = self.alert_record.model_copy(update={"district": "Colombo"})
        self.mock_farm_repo.list_by_owner_user_id = AsyncMock(
            return_value=[self.jaffna_farm]
        )
        self.mock_alert_repo.list_by_farm_ids = AsyncMock(
            return_value=[out_district_alert]
        )
        alerts = await self.service.get_accessible_alerts(self.farmer_user)
        self.assertEqual(alerts, [])

    async def test_06_farmer_response_tasks_forbidden(self):
        with self.assertRaises(DemoOperationalForbiddenError):
            await self.service.get_accessible_response_tasks(self.farmer_user)

    async def test_07_farmer_with_no_farm_returns_empty_alerts_without_alert_db_query(self):
        self.mock_farm_repo.list_by_owner_user_id = AsyncMock(return_value=[])
        self.mock_alert_repo.list_by_farm_ids = AsyncMock()
        alerts = await self.service.get_accessible_alerts(self.farmer_user)
        self.assertEqual(alerts, [])
        self.mock_alert_repo.list_by_farm_ids.assert_not_called()

    # --- Vet Tests (8 to 20) ---

    async def test_08_vet_farms_query_only_assigned_farm_ids(self):
        self.mock_farm_repo.list_by_farm_ids = AsyncMock(
            return_value=[self.jaffna_farm]
        )
        farms = await self.service.get_accessible_farms(self.vet_user)
        self.assertEqual(len(farms), 1)
        self.mock_farm_repo.list_by_farm_ids.assert_called_once_with(
            self.vet_user.authorization.assignedFarmIds, skip=0, limit=50
        )

    async def test_09_empty_assigned_farm_ids_returns_empty_without_unscoped_query(self):
        no_farm_vet = self.vet_user.model_copy(
            update={"authorization": self.vet_user.authorization.model_copy(update={"assignedFarmIds": []})}
        )
        self.mock_farm_repo.list_by_farm_ids = AsyncMock()
        farms = await self.service.get_accessible_farms(no_farm_vet)
        self.assertEqual(farms, [])
        self.mock_farm_repo.list_by_farm_ids.assert_not_called()

    async def test_10_unassigned_farm_returned_by_repo_excluded(self):
        unassigned_farm = self.jaffna_farm.model_copy(update={"farmId": "UNASSIGNED_FARM"})
        self.mock_farm_repo.list_by_farm_ids = AsyncMock(return_value=[unassigned_farm])
        farms = await self.service.get_accessible_farms(self.vet_user)
        self.assertEqual(farms, [])

    async def test_11_farm_outside_authorized_district_excluded(self):
        colombo_farm = self.jaffna_farm.model_copy(update={"district": "Colombo"})
        self.mock_farm_repo.list_by_farm_ids = AsyncMock(return_value=[colombo_farm])
        farms = await self.service.get_accessible_farms(self.vet_user)
        self.assertEqual(farms, [])

    async def test_12_farm_not_containing_vet_in_assigned_vets_excluded(self):
        other_vet_farm = self.jaffna_farm.model_copy(update={"assignedVetUserIds": ["OTHER_VET"]})
        self.mock_farm_repo.list_by_farm_ids = AsyncMock(return_value=[other_vet_farm])
        farms = await self.service.get_accessible_farms(self.vet_user)
        self.assertEqual(farms, [])

    async def test_13_surveillance_uses_only_accessible_farm_ids(self):
        self.mock_farm_repo.list_by_farm_ids = AsyncMock(return_value=[self.jaffna_farm])
        self.mock_surv_repo.list_by_farm_ids = AsyncMock(return_value=[self.surv_record])
        records = await self.service.get_accessible_surveillance_records(self.vet_user)
        self.assertEqual(len(records), 1)
        self.mock_surv_repo.list_by_farm_ids.assert_called_once_with(
            ["DEMO_FARM_JAFFNA_001"], skip=0, limit=50
        )

    async def test_14_surveillance_outside_authorized_districts_excluded(self):
        self.mock_farm_repo.list_by_farm_ids = AsyncMock(return_value=[self.jaffna_farm])
        colombo_surv = self.surv_record.model_copy(update={"district": "Colombo"})
        self.mock_surv_repo.list_by_farm_ids = AsyncMock(return_value=[colombo_surv])
        records = await self.service.get_accessible_surveillance_records(self.vet_user)
        self.assertEqual(records, [])

    async def test_15_alerts_use_only_accessible_farm_ids(self):
        self.mock_farm_repo.list_by_farm_ids = AsyncMock(return_value=[self.jaffna_farm])
        self.mock_alert_repo.list_by_farm_ids = AsyncMock(return_value=[self.alert_record])
        alerts = await self.service.get_accessible_alerts(self.vet_user)
        self.assertEqual(len(alerts), 1)

    async def test_16_alerts_outside_scope_excluded(self):
        self.mock_farm_repo.list_by_farm_ids = AsyncMock(return_value=[self.jaffna_farm])
        colombo_alert = self.alert_record.model_copy(update={"district": "Colombo"})
        self.mock_alert_repo.list_by_farm_ids = AsyncMock(return_value=[colombo_alert])
        alerts = await self.service.get_accessible_alerts(self.vet_user)
        self.assertEqual(alerts, [])

    async def test_17_tasks_use_only_current_vet_user_id(self):
        self.mock_task_repo.list_by_assigned_officer_user_id = AsyncMock(return_value=[self.task_record])
        tasks = await self.service.get_accessible_response_tasks(self.vet_user)
        self.assertEqual(len(tasks), 1)
        self.mock_task_repo.list_by_assigned_officer_user_id.assert_called_once_with(
            "DEMO_USER_VET_NORTH", skip=0, limit=50
        )

    async def test_18_tasks_outside_authorized_districts_excluded(self):
        colombo_task = self.task_record.model_copy(update={"district": "Colombo"})
        self.mock_task_repo.list_by_assigned_officer_user_id = AsyncMock(return_value=[colombo_task])
        tasks = await self.service.get_accessible_response_tasks(self.vet_user)
        self.assertEqual(tasks, [])

    async def test_19_record_response_false_forbids_tasks(self):
        no_perm_vet = self.vet_user.model_copy(
            update={"permissions": self.vet_user.permissions.model_copy(update={"recordResponse": False})}
        )
        with self.assertRaises(DemoOperationalForbiddenError):
            await self.service.get_accessible_response_tasks(no_perm_vet)

    async def test_20_manage_alerts_view_transparency_do_not_expand_scope(self):
        # Even with manageAlerts=True, unassigned farms or districts remain excluded
        self.mock_farm_repo.list_by_farm_ids = AsyncMock(return_value=[self.other_farmer_farm])
        farms = await self.service.get_accessible_farms(self.vet_user)
        self.assertEqual(farms, [])

    # --- DAPH Tests (21 to 28) ---

    async def test_21_daph_farms_forbidden(self):
        with self.assertRaises(DemoOperationalForbiddenError):
            await self.service.get_accessible_farms(self.daph_user)

    async def test_22_surveillance_queried_only_by_explicit_authorized_districts(self):
        self.mock_surv_repo.list_by_districts = AsyncMock(return_value=[self.surv_record])
        records = await self.service.get_accessible_surveillance_records(self.daph_user)
        self.assertEqual(len(records), 1)
        self.mock_surv_repo.list_by_districts.assert_called_once_with(
            ["Jaffna", "Kilinochchi", "Vavuniya"], skip=0, limit=50
        )

    async def test_23_alerts_queried_only_by_explicit_authorized_districts(self):
        self.mock_alert_repo.list_by_districts = AsyncMock(return_value=[self.alert_record])
        alerts = await self.service.get_accessible_alerts(self.daph_user)
        self.assertEqual(len(alerts), 1)
        self.mock_alert_repo.list_by_districts.assert_called_once_with(
            ["Jaffna", "Kilinochchi", "Vavuniya"], skip=0, limit=50
        )

    async def test_24_tasks_queried_only_by_explicit_authorized_districts(self):
        self.mock_task_repo.list_by_districts = AsyncMock(return_value=[self.task_record])
        tasks = await self.service.get_accessible_response_tasks(self.daph_user)
        self.assertEqual(len(tasks), 1)
        self.mock_task_repo.list_by_districts.assert_called_once_with(
            ["Jaffna", "Kilinochchi", "Vavuniya"], skip=0, limit=50
        )

    async def test_25_empty_districts_returns_empty_without_db_query(self):
        no_dist_daph = self.daph_user.model_copy(
            update={"authorization": self.daph_user.authorization.model_copy(update={"authorizedDistricts": []})}
        )
        self.mock_surv_repo.list_by_districts = AsyncMock()
        records = await self.service.get_accessible_surveillance_records(no_dist_daph)
        self.assertEqual(records, [])
        self.mock_surv_repo.list_by_districts.assert_not_called()

    async def test_26_national_does_not_auto_expand_districts(self):
        # Scope NATIONAL with explicit 1 district should only query that 1 district
        single_dist_daph = self.daph_user.model_copy(
            update={"authorization": self.daph_user.authorization.model_copy(update={"authorizedDistricts": ["Jaffna"]})}
        )
        self.mock_surv_repo.list_by_districts = AsyncMock(return_value=[self.surv_record])
        records = await self.service.get_accessible_surveillance_records(single_dist_daph)
        self.assertEqual(len(records), 1)
        self.mock_surv_repo.list_by_districts.assert_called_once_with(["Jaffna"], skip=0, limit=50)

    async def test_27_outside_district_records_post_filtered(self):
        colombo_surv = self.surv_record.model_copy(update={"district": "Colombo"})
        self.mock_surv_repo.list_by_districts = AsyncMock(return_value=[colombo_surv])
        records = await self.service.get_accessible_surveillance_records(self.daph_user)
        self.assertEqual(records, [])

    async def test_28_record_response_false_forbids_daph_tasks(self):
        no_perm_daph = self.daph_user.model_copy(
            update={"permissions": self.daph_user.permissions.model_copy(update={"recordResponse": False})}
        )
        with self.assertRaises(DemoOperationalForbiddenError):
            await self.service.get_accessible_response_tasks(no_perm_daph)

    # --- General Tests (29 to 36) ---

    async def test_29_disabled_user_rejected(self):
        disabled_user = self.farmer_user.model_copy(update={"enabled": False})
        with self.assertRaises(DemoOperationalForbiddenError):
            await self.service.get_accessible_farms(disabled_user)

    async def test_30_invalid_role_scope_rejected(self):
        incompatible_user = self.farmer_user.model_copy(
            update={"authorization": self.farmer_user.authorization.model_copy(update={"scopeLevel": ScopeLevel.NATIONAL})}
        )
        with self.assertRaises(DemoOperationalForbiddenError):
            await self.service.get_accessible_farms(incompatible_user)

    def test_31_caller_input_remains_unchanged(self):
        original_user_dump = self.farmer_user.model_dump()
        _ = self.service.get_accessible_farms
        self.assertEqual(self.farmer_user.model_dump(), original_user_dump)

    async def test_32_repository_errors_sanitized(self):
        self.mock_farm_repo.list_by_owner_user_id = AsyncMock(
            side_effect=DemoOperationalRepositoryError("Internal database connection error: mongodb://secret@host:27017")
        )
        with self.assertRaises(DemoOperationalUnavailableError) as ctx:
            await self.service.get_accessible_farms(self.farmer_user)
        self.assertNotIn("mongodb://", str(ctx.exception))
        self.assertNotIn("secret", str(ctx.exception))
        self.assertEqual(str(ctx.exception), "Operational data service is currently unavailable.")

    def test_33_repr_and_errors_are_clean(self):
        err = DemoOperationalForbiddenError()
        self.assertNotIn("password", str(err))
        self.assertNotIn("mongodb://", str(err))
        repr_str = repr(self.service)
        self.assertEqual(repr_str, "DemoOperationalAuthorizationService()")

    def test_34_no_mongo_client_instantiation(self):
        import backend.components.demo_operational.service as service_mod

        mod_file = service_mod.__file__
        with open(mod_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("AsyncMongoClient", content)
        self.assertNotIn("MongoClient", content)

    def test_35_no_forecasting_imports(self):
        import backend.components.demo_operational.service as service_mod

        mod_file = service_mod.__file__
        with open(mod_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("risk_forecasting", content)
        self.assertNotIn("sklearn", content)
        self.assertNotIn("torch", content)


if __name__ == "__main__":
    unittest.main()
