"""
Unit tests for synthetic operational demo data models.
Validates strict Pydantic v2 validation, ID prefixes, cross-field rules,
immutable caller inputs, synthetic markers, and strict isolation from scientific ML models.
"""

import sys
import unittest
from datetime import datetime, timezone
from pydantic import ValidationError

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


class TestDemoOperationalModels(unittest.TestCase):
    def setUp(self):
        self.now_utc = datetime.now(timezone.utc)
        self.valid_farm_dict = {
            "farmId": "DEMO_FARM_JAFFNA_001",
            "displayName": "Jaffna Synthetic Dairy Farm",
            "district": "Jaffna",
            "ownerUserId": "DEMO_USER_FARMER_JAFFNA",
            "assignedVetUserIds": ["DEMO_USER_VET_NORTH"],
            "livestockTypes": ["CATTLE", "GOAT"],
            "active": True,
            "createdAt": self.now_utc,
            "updatedAt": self.now_utc,
        }

        self.valid_surv_dict = {
            "surveillanceRecordId": "DEMO_SURV_001",
            "farmId": "DEMO_FARM_JAFFNA_001",
            "district": "Jaffna",
            "diseaseCode": "FMD",
            "observedAt": self.now_utc,
            "evidenceType": "FARMER_REPORT",
            "verificationStatus": "REPORTED",
            "sourceModule": "SYNTHETIC_FARM_REPORTING",
            "sourceRecordId": "DEMO_SOURCE_FARMER_001",
            "summary": "Farmer observed mild fever",
            "createdAt": self.now_utc,
            "updatedAt": self.now_utc,
        }

        self.valid_alert_dict = {
            "alertId": "DEMO_ALERT_001",
            "district": "Jaffna",
            "diseaseCode": "FMD",
            "status": "OPEN",
            "priority": "HIGH",
            "issuedAt": self.now_utc,
            "sourceSurveillanceRecordIds": ["DEMO_SURV_001"],
            "affectedFarmIds": ["DEMO_FARM_JAFFNA_001"],
            "title": "Synthetic High Risk FMD Operational Alert",
            "message": "FMD symptoms reported in 2 synthetic farms",
            "createdAt": self.now_utc,
            "updatedAt": self.now_utc,
        }

        self.valid_task_dict = {
            "responseTaskId": "DEMO_TASK_001",
            "alertId": "DEMO_ALERT_001",
            "assignedOfficerUserId": "DEMO_USER_VET_NORTH",
            "district": "Jaffna",
            "farmId": "DEMO_FARM_JAFFNA_001",
            "taskType": "FIELD_REVIEW",
            "status": "ASSIGNED",
            "dueAt": self.now_utc,
            "notes": "Conduct field inspection of reported synthetic symptoms",
            "createdAt": self.now_utc,
            "updatedAt": self.now_utc,
        }

    # 1. Valid DemoFarm
    def test_01_valid_demo_farm(self):
        farm = DemoFarm(**self.valid_farm_dict)
        self.assertEqual(farm.farmId, "DEMO_FARM_JAFFNA_001")
        self.assertEqual(farm.schemaVersion, "1.0")
        self.assertTrue(farm.isSynthetic)
        self.assertEqual(farm.dataOrigin, "SYNTHETIC_DEMO")
        self.assertFalse(farm.scientificUseAllowed)

    # 2. Invalid farm/user ID prefixes fail
    def test_02_invalid_farm_or_user_id_prefixes(self):
        bad_farm = dict(self.valid_farm_dict, farmId="INVALID_FARM_001")
        with self.assertRaises(ValidationError):
            DemoFarm(**bad_farm)

        bad_user = dict(self.valid_farm_dict, ownerUserId="INVALID_USER_001")
        with self.assertRaises(ValidationError):
            DemoFarm(**bad_user)

    # 3. Livestock types deduplicate
    def test_03_livestock_types_deduplicate(self):
        data = dict(self.valid_farm_dict, livestockTypes=["CATTLE", "GOAT", "CATTLE", "GOAT", "SHEEP"])
        farm = DemoFarm(**data)
        self.assertEqual(farm.livestockTypes, [LivestockType.CATTLE, LivestockType.GOAT, LivestockType.SHEEP])

    # 4. Farm cannot contain prediction percentage fields
    def test_04_farm_cannot_contain_prediction_percentage_fields(self):
        data = dict(self.valid_farm_dict, outbreak_probability=0.85)
        with self.assertRaises(ValidationError):
            DemoFarm(**data)

    # 5. Valid REPORTED farmer record
    def test_05_valid_reported_farmer_record(self):
        surv = DemoSurveillanceRecord(**self.valid_surv_dict)
        self.assertEqual(surv.verificationStatus, VerificationStatus.REPORTED)
        self.assertEqual(surv.evidenceType, EvidenceType.FARMER_REPORT)

    # 6. Valid AI_SCREENED AI image record
    def test_06_valid_ai_screened_record(self):
        data = dict(
            self.valid_surv_dict,
            evidenceType="AI_IMAGE_SCREENING",
            verificationStatus="AI_SCREENED",
            sourceModule="SYNTHETIC_AI_DIAGNOSIS",
        )
        surv = DemoSurveillanceRecord(**data)
        self.assertEqual(surv.verificationStatus, VerificationStatus.AI_SCREENED)

    # 7. Valid VET_REVIEWED record
    def test_07_valid_vet_reviewed_record(self):
        data = dict(
            self.valid_surv_dict,
            evidenceType="VET_FIELD_OBSERVATION",
            verificationStatus="VET_REVIEWED",
            sourceModule="SYNTHETIC_VETERINARY_SERVICE",
        )
        surv = DemoSurveillanceRecord(**data)
        self.assertEqual(surv.verificationStatus, VerificationStatus.VET_REVIEWED)

    # 8. Valid LAB_CONFIRMED lab record
    def test_08_valid_lab_confirmed_record(self):
        data = dict(
            self.valid_surv_dict,
            evidenceType="LAB_RESULT",
            verificationStatus="LAB_CONFIRMED",
            sourceModule="SYNTHETIC_LAB_SERVICE",
        )
        surv = DemoSurveillanceRecord(**data)
        self.assertEqual(surv.verificationStatus, VerificationStatus.LAB_CONFIRMED)

    # 9. Valid REJECTED record
    def test_09_valid_rejected_record(self):
        data = dict(
            self.valid_surv_dict,
            evidenceType="VET_FIELD_OBSERVATION",
            verificationStatus="REJECTED",
            sourceModule="SYNTHETIC_VETERINARY_SERVICE",
        )
        surv = DemoSurveillanceRecord(**data)
        self.assertEqual(surv.verificationStatus, VerificationStatus.REJECTED)

    # 10. AI screening cannot be LAB_CONFIRMED
    def test_10_ai_screening_cannot_be_lab_confirmed(self):
        data = dict(
            self.valid_surv_dict,
            evidenceType="AI_IMAGE_SCREENING",
            verificationStatus="LAB_CONFIRMED",
        )
        with self.assertRaises(ValidationError):
            DemoSurveillanceRecord(**data)

    # 11. LAB_CONFIRMED without LAB_RESULT fails
    def test_11_lab_confirmed_without_lab_result_fails(self):
        data = dict(
            self.valid_surv_dict,
            evidenceType="FARMER_REPORT",
            verificationStatus="LAB_CONFIRMED",
        )
        with self.assertRaises(ValidationError):
            DemoSurveillanceRecord(**data)

    # 12. REJECTED from invalid evidence type fails
    def test_12_rejected_from_invalid_evidence_type_fails(self):
        data = dict(
            self.valid_surv_dict,
            evidenceType="FARMER_REPORT",
            verificationStatus="REJECTED",
        )
        with self.assertRaises(ValidationError):
            DemoSurveillanceRecord(**data)

    # 13. Invalid disease/evidence/status/source fails
    def test_13_invalid_enums_fail(self):
        with self.assertRaises(ValidationError):
            DemoSurveillanceRecord(**dict(self.valid_surv_dict, diseaseCode="COVID19"))

        with self.assertRaises(ValidationError):
            DemoSurveillanceRecord(**dict(self.valid_surv_dict, evidenceType="INVALID_TYPE"))

        with self.assertRaises(ValidationError):
            DemoSurveillanceRecord(**dict(self.valid_surv_dict, verificationStatus="INVALID_STATUS"))

        with self.assertRaises(ValidationError):
            DemoSurveillanceRecord(**dict(self.valid_surv_dict, sourceModule="INVALID_MODULE"))

    # 14. Valid open alert
    def test_14_valid_open_alert(self):
        alert = DemoAlert(**self.valid_alert_dict)
        self.assertEqual(alert.status, AlertStatus.OPEN)
        self.assertIsNone(alert.closedAt)

    # 15. Valid acknowledged alert
    def test_15_valid_acknowledged_alert(self):
        data = dict(self.valid_alert_dict, status="ACKNOWLEDGED")
        alert = DemoAlert(**data)
        self.assertEqual(alert.status, AlertStatus.ACKNOWLEDGED)
        self.assertIsNone(alert.closedAt)

    # 16. Valid closed alert
    def test_16_valid_closed_alert(self):
        data = dict(self.valid_alert_dict, status="CLOSED", closedAt=self.now_utc)
        alert = DemoAlert(**data)
        self.assertEqual(alert.status, AlertStatus.CLOSED)
        self.assertIsNotNone(alert.closedAt)

    # 17. Closed alert without closedAt fails
    def test_17_closed_alert_without_closed_at_fails(self):
        data = dict(self.valid_alert_dict, status="CLOSED", closedAt=None)
        with self.assertRaises(ValidationError):
            DemoAlert(**data)

    # 18. Open alert with closedAt fails
    def test_18_open_alert_with_closed_at_fails(self):
        data = dict(self.valid_alert_dict, status="OPEN", closedAt=self.now_utc)
        with self.assertRaises(ValidationError):
            DemoAlert(**data)

    # 19. Alert source IDs deduplicate
    def test_19_alert_source_ids_deduplicate(self):
        data = dict(
            self.valid_alert_dict,
            sourceSurveillanceRecordIds=["DEMO_SURV_001", "DEMO_SURV_002", "DEMO_SURV_001"],
        )
        alert = DemoAlert(**data)
        self.assertEqual(alert.sourceSurveillanceRecordIds, ["DEMO_SURV_001", "DEMO_SURV_002"])

    # 20. Valid assigned task
    def test_20_valid_assigned_task(self):
        task = DemoResponseTask(**self.valid_task_dict)
        self.assertEqual(task.status, TaskStatus.ASSIGNED)
        self.assertIsNone(task.completedAt)

    # 21. Valid in-progress task
    def test_21_valid_in_progress_task(self):
        data = dict(self.valid_task_dict, status="IN_PROGRESS")
        task = DemoResponseTask(**data)
        self.assertEqual(task.status, TaskStatus.IN_PROGRESS)
        self.assertIsNone(task.completedAt)

    # 22. Valid completed task
    def test_22_valid_completed_task(self):
        data = dict(self.valid_task_dict, status="COMPLETED", completedAt=self.now_utc)
        task = DemoResponseTask(**data)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(task.completedAt)

    # 23. Completed task without completedAt fails
    def test_23_completed_task_without_completed_at_fails(self):
        data = dict(self.valid_task_dict, status="COMPLETED", completedAt=None)
        with self.assertRaises(ValidationError):
            DemoResponseTask(**data)

    # 24. Assigned/in-progress task with completedAt fails
    def test_24_assigned_or_in_progress_task_with_completed_at_fails(self):
        data = dict(self.valid_task_dict, status="ASSIGNED", completedAt=self.now_utc)
        with self.assertRaises(ValidationError):
            DemoResponseTask(**data)

        data2 = dict(self.valid_task_dict, status="IN_PROGRESS", completedAt=self.now_utc)
        with self.assertRaises(ValidationError):
            DemoResponseTask(**data2)

    # 25. Invalid ID prefixes fail across every model
    def test_25_invalid_id_prefixes_across_all_models(self):
        with self.assertRaises(ValidationError):
            DemoFarm(**dict(self.valid_farm_dict, farmId="FARM_001"))

        with self.assertRaises(ValidationError):
            DemoSurveillanceRecord(**dict(self.valid_surv_dict, surveillanceRecordId="SURV_001"))

        with self.assertRaises(ValidationError):
            DemoAlert(**dict(self.valid_alert_dict, alertId="ALERT_001"))

        with self.assertRaises(ValidationError):
            DemoResponseTask(**dict(self.valid_task_dict, responseTaskId="TASK_001"))

    # 26. Unknown fields fail
    def test_26_unknown_fields_fail(self):
        with self.assertRaises(ValidationError):
            DemoFarm(**dict(self.valid_farm_dict, unknown_field="test"))

        with self.assertRaises(ValidationError):
            DemoSurveillanceRecord(**dict(self.valid_surv_dict, stage1_probability=0.9))

        with self.assertRaises(ValidationError):
            DemoAlert(**dict(self.valid_alert_dict, ece=0.01))

        with self.assertRaises(ValidationError):
            DemoResponseTask(**dict(self.valid_task_dict, log_odds=1.5))

    # 27. Invalid synthetic/scientific markers fail
    def test_27_invalid_synthetic_scientific_markers_fail(self):
        with self.assertRaises(ValidationError):
            DemoFarm(**dict(self.valid_farm_dict, isSynthetic=False))

        with self.assertRaises(ValidationError):
            DemoFarm(**dict(self.valid_farm_dict, dataOrigin="REAL_ATLAS_DATA"))

        with self.assertRaises(ValidationError):
            DemoFarm(**dict(self.valid_farm_dict, scientificUseAllowed=True))

    # 28. Naive timestamps fail
    def test_28_naive_timestamps_fail(self):
        naive_dt = datetime.now()  # naive, no tzinfo
        with self.assertRaises(ValidationError):
            DemoFarm(**dict(self.valid_farm_dict, createdAt=naive_dt))

        with self.assertRaises(ValidationError):
            DemoSurveillanceRecord(**dict(self.valid_surv_dict, observedAt=naive_dt))

    # 29. Caller inputs remain unchanged
    def test_29_caller_inputs_remain_unchanged(self):
        vets = ["DEMO_USER_VET_NORTH", "DEMO_USER_VET_NORTH"]
        data = dict(self.valid_farm_dict, assignedVetUserIds=vets)
        farm = DemoFarm(**data)
        self.assertEqual(vets, ["DEMO_USER_VET_NORTH", "DEMO_USER_VET_NORTH"])
        self.assertEqual(farm.assignedVetUserIds, ["DEMO_USER_VET_NORTH"])

    # 30. Serialized records contain no forecasting/model fields
    def test_30_serialized_records_contain_no_forecasting_fields(self):
        farm = DemoFarm(**self.valid_farm_dict)
        farm_dump = farm.model_dump()
        self.assertNotIn("probability", farm_dump)
        self.assertNotIn("forecast", farm_dump)
        self.assertNotIn("stage1", farm_dump)
        self.assertNotIn("stage2", farm_dump)
        self.assertNotIn("log_odds", farm_dump)
        self.assertNotIn("uncertainty", farm_dump)

        surv = DemoSurveillanceRecord(**self.valid_surv_dict)
        surv_dump = surv.model_dump()
        self.assertNotIn("probability", surv_dump)
        self.assertNotIn("stage1", surv_dump)

    # 31. Module contains no forecasting/training imports
    def test_31_module_contains_no_forecasting_imports(self):
        import backend.components.demo_operational.models as models_mod

        mod_file = models_mod.__file__
        with open(mod_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("risk_forecasting", content)
        self.assertNotIn("sklearn", content)
        self.assertNotIn("numpy", content)
        self.assertNotIn("pandas", content)
        self.assertNotIn("torch", content)


if __name__ == "__main__":
    unittest.main()
