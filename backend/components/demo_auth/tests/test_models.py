"""
Unit tests for backend/components/demo_auth/models.py
"""

import unittest
from datetime import datetime, timezone
import copy
from pydantic import ValidationError

from backend.components.demo_auth.models import (
    Role,
    ScopeLevel,
    DemoAuthorization,
    DemoPermissions,
    DemoUserDocument,
    ViewerContextResponse,
    demo_user_to_viewer_context,
)


class TestDemoAuthModels(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)

        self.valid_permissions_dict = {
            "viewDataQuality": True,
            "viewModelTransparency": False,
            "manageAlerts": False,
            "recordResponse": False,
            "viewReports": True,
        }

    def _create_user_data(self, **kwargs):
        base_authorization = {
            "scopeLevel": ScopeLevel.FARM,
            "registeredFarmDistrict": "Ampara",
            "authorizedDistricts": ["Ampara"],
            "assignedFarmIds": [],
        }
        data = {
            "schemaVersion": "1.0",
            "userId": "DEMO_USER_FARMER_001",
            "loginName": "farmer_demo",
            "passwordHash": "$argon2id$v=19$m=65536,t=3,p=4$dummyhash",
            "role": Role.FARMER,
            "authorization": kwargs.pop("authorization", base_authorization),
            "permissions": kwargs.pop("permissions", self.valid_permissions_dict),
            "enabled": True,
            "tokenVersion": 1,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
            "scientificUseAllowed": False,
            "createdAt": self.now,
            "updatedAt": self.now,
        }
        data.update(kwargs)
        return data

    def test_1_valid_farmer_contract_and_exact_viewer_context_output(self):
        data = self._create_user_data()
        user = DemoUserDocument(**data)
        self.assertEqual(user.role, Role.FARMER)

        vc = demo_user_to_viewer_context(user)
        self.assertIsInstance(vc, ViewerContextResponse)

        vc_dict = vc.model_dump()
        self.assertIn("userId", vc_dict)
        self.assertIn("role", vc_dict)
        self.assertIn("authorization", vc_dict)
        self.assertIn("permissions", vc_dict)
        self.assertNotIn("passwordHash", vc_dict)
        self.assertNotIn("loginName", vc_dict)
        self.assertNotIn("isSynthetic", vc_dict)
        self.assertEqual(vc_dict["authorization"]["registeredFarmDistrict"], "Ampara")
        self.assertEqual(vc_dict["authorization"]["authorizedDistricts"], ["Ampara"])

    def test_2_valid_district_vet(self):
        auth = {
            "scopeLevel": ScopeLevel.DISTRICT,
            "authorizedDistricts": ["Gampaha"],
            "assignedFarmIds": ["FARM_101", "FARM_102"],
        }
        data = self._create_user_data(
            userId="DEMO_USER_VET_001",
            role=Role.VETERINARY_OFFICER,
            authorization=auth,
        )
        user = DemoUserDocument(**data)
        self.assertEqual(user.authorization.registeredFarmDistrict, None)
        self.assertEqual(user.authorization.authorizedDistricts, ["Gampaha"])
        self.assertEqual(user.authorization.assignedFarmIds, ["FARM_101", "FARM_102"])

    def test_3_valid_province_vet(self):
        auth = {
            "scopeLevel": ScopeLevel.PROVINCE,
            "authorizedDistricts": ["Colombo", "Gampaha", "Kalutara"],
            "assignedFarmIds": [],
        }
        data = self._create_user_data(
            userId="DEMO_USER_VET_002",
            role=Role.VETERINARY_OFFICER,
            authorization=auth,
        )
        user = DemoUserDocument(**data)
        self.assertEqual(user.authorization.scopeLevel, ScopeLevel.PROVINCE)
        self.assertEqual(len(user.authorization.authorizedDistricts), 3)

    def test_4_valid_district_daph(self):
        auth = {
            "scopeLevel": ScopeLevel.DISTRICT,
            "authorizedDistricts": ["Kandy"],
            "assignedFarmIds": [],
        }
        data = self._create_user_data(
            userId="DEMO_USER_DAPH_001",
            role=Role.DAPH_OFFICIAL,
            authorization=auth,
        )
        user = DemoUserDocument(**data)
        self.assertEqual(user.authorization.scopeLevel, ScopeLevel.DISTRICT)
        self.assertEqual(user.authorization.assignedFarmIds, [])

    def test_5_valid_province_daph(self):
        auth = {
            "scopeLevel": ScopeLevel.PROVINCE,
            "authorizedDistricts": ["Kandy", "Matale", "Nuwara Eliya"],
            "assignedFarmIds": [],
        }
        data = self._create_user_data(
            userId="DEMO_USER_DAPH_002",
            role=Role.DAPH_OFFICIAL,
            authorization=auth,
        )
        user = DemoUserDocument(**data)
        self.assertEqual(user.authorization.scopeLevel, ScopeLevel.PROVINCE)

    def test_6_valid_national_daph_with_explicit_districts(self):
        explicit_districts = ["Ampara", "Batticaloa", "Trincomalee"]
        auth = {
            "scopeLevel": ScopeLevel.NATIONAL,
            "authorizedDistricts": explicit_districts,
            "assignedFarmIds": [],
        }
        data = self._create_user_data(
            userId="DEMO_USER_DAPH_003",
            role=Role.DAPH_OFFICIAL,
            authorization=auth,
        )
        user = DemoUserDocument(**data)
        self.assertEqual(user.authorization.scopeLevel, ScopeLevel.NATIONAL)
        self.assertEqual(user.authorization.authorizedDistricts, explicit_districts)

    def test_7_every_incompatible_role_scope_combination_fails(self):
        incompatible_pairs = [
            (Role.FARMER, ScopeLevel.DISTRICT),
            (Role.FARMER, ScopeLevel.PROVINCE),
            (Role.FARMER, ScopeLevel.NATIONAL),
            (Role.VETERINARY_OFFICER, ScopeLevel.FARM),
            (Role.VETERINARY_OFFICER, ScopeLevel.NATIONAL),
            (Role.DAPH_OFFICIAL, ScopeLevel.FARM),
        ]
        for role, scope in incompatible_pairs:
            auth = {
                "scopeLevel": scope,
                "registeredFarmDistrict": "Ampara" if role == Role.FARMER else None,
                "authorizedDistricts": ["Ampara"],
                "assignedFarmIds": [],
            }
            data = self._create_user_data(role=role, authorization=auth)
            with self.assertRaises(ValidationError):
                DemoUserDocument(**data)

    def test_8_farmer_missing_registered_district_fails(self):
        auth = {
            "scopeLevel": ScopeLevel.FARM,
            "registeredFarmDistrict": None,
            "authorizedDistricts": ["Ampara"],
            "assignedFarmIds": [],
        }
        data = self._create_user_data(role=Role.FARMER, authorization=auth)
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data)

    def test_9_farmer_cannot_gain_extra_districts(self):
        auth = {
            "scopeLevel": ScopeLevel.FARM,
            "registeredFarmDistrict": "Ampara",
            "authorizedDistricts": ["Ampara", "Colombo", "Kandy"],
            "assignedFarmIds": [],
        }
        data = self._create_user_data(role=Role.FARMER, authorization=auth)
        user = DemoUserDocument(**data)
        self.assertEqual(user.authorization.authorizedDistricts, ["Ampara"])

    def test_10_farmer_cannot_gain_assigned_farm_ids(self):
        auth = {
            "scopeLevel": ScopeLevel.FARM,
            "registeredFarmDistrict": "Ampara",
            "authorizedDistricts": ["Ampara"],
            "assignedFarmIds": ["FARM_999"],
        }
        data = self._create_user_data(role=Role.FARMER, authorization=auth)
        user = DemoUserDocument(**data)
        self.assertEqual(user.authorization.assignedFarmIds, [])

    def test_11_vet_requires_at_least_one_authorized_district(self):
        auth = {
            "scopeLevel": ScopeLevel.DISTRICT,
            "authorizedDistricts": [],
            "assignedFarmIds": [],
        }
        data = self._create_user_data(role=Role.VETERINARY_OFFICER, authorization=auth)
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data)

    def test_12_vet_registered_farm_district_becomes_null(self):
        auth = {
            "scopeLevel": ScopeLevel.DISTRICT,
            "registeredFarmDistrict": "Colombo",
            "authorizedDistricts": ["Colombo"],
            "assignedFarmIds": [],
        }
        data = self._create_user_data(role=Role.VETERINARY_OFFICER, authorization=auth)
        user = DemoUserDocument(**data)
        self.assertIsNone(user.authorization.registeredFarmDistrict)

    def test_13_daph_requires_explicit_authorized_districts(self):
        auth = {
            "scopeLevel": ScopeLevel.DISTRICT,
            "authorizedDistricts": [],
            "assignedFarmIds": [],
        }
        data = self._create_user_data(role=Role.DAPH_OFFICIAL, authorization=auth)
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data)

    def test_14_national_daph_does_not_auto_create_25_districts(self):
        explicit = ["Ampara", "Kandy"]
        auth = {
            "scopeLevel": ScopeLevel.NATIONAL,
            "authorizedDistricts": explicit,
            "assignedFarmIds": [],
        }
        data = self._create_user_data(role=Role.DAPH_OFFICIAL, authorization=auth)
        user = DemoUserDocument(**data)
        self.assertEqual(user.authorization.authorizedDistricts, explicit)

    def test_15_daph_cannot_gain_assigned_farm_ids(self):
        auth = {
            "scopeLevel": ScopeLevel.DISTRICT,
            "authorizedDistricts": ["Kandy"],
            "assignedFarmIds": ["FARM_100"],
        }
        data = self._create_user_data(role=Role.DAPH_OFFICIAL, authorization=auth)
        user = DemoUserDocument(**data)
        self.assertEqual(user.authorization.assignedFarmIds, [])

    def test_16_arrays_are_trimmed_and_deduplicated(self):
        auth = DemoAuthorization(
            scopeLevel=ScopeLevel.DISTRICT,
            authorizedDistricts=[" Kandy ", "Gampaha ", "Kandy", "   "],
            assignedFarmIds=[" FARM_1 ", "FARM_2", " FARM_1 "],
        )
        self.assertEqual(auth.authorizedDistricts, ["Kandy", "Gampaha"])
        self.assertEqual(auth.assignedFarmIds, ["FARM_1", "FARM_2"])

    def test_17_non_array_authorization_fields_fail(self):
        for bad_val in ["string_not_list", 123, {"key": "val"}]:
            with self.assertRaises(ValidationError):
                DemoAuthorization(
                    scopeLevel=ScopeLevel.DISTRICT,
                    authorizedDistricts=bad_val,
                )

    def test_18_string_or_number_permission_values_fail(self):
        invalid_permissions = [
            {"viewDataQuality": "true", "viewModelTransparency": False, "manageAlerts": False, "recordResponse": False, "viewReports": True},
            {"viewDataQuality": 1, "viewModelTransparency": False, "manageAlerts": False, "recordResponse": False, "viewReports": True},
        ]
        for p in invalid_permissions:
            with self.assertRaises(ValidationError):
                DemoPermissions(**p)

    def test_19_unknown_role_or_scope_fails(self):
        data1 = self._create_user_data(role="INVALID_ROLE")
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data1)

        auth = {"scopeLevel": "INVALID_SCOPE", "authorizedDistricts": ["Ampara"]}
        data2 = self._create_user_data(authorization=auth)
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data2)

    def test_20_unknown_fields_fail(self):
        data = self._create_user_data(extra_unknown_field="unauthorized")
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data)

    def test_21_invalid_synthetic_marker_fails(self):
        data = self._create_user_data(isSynthetic=False)
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data)

    def test_22_scientific_use_allowed_true_fails(self):
        data = self._create_user_data(scientificUseAllowed=True)
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data)

    def test_23_non_demo_user_id_fails(self):
        data = self._create_user_data(userId="REAL_USER_123")
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data)

    def test_24_empty_login_name_or_password_hash_fails(self):
        data1 = self._create_user_data(loginName="   ")
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data1)

        data2 = self._create_user_data(passwordHash="")
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data2)

    def test_25_naive_timestamps_fail_utc_aware_succeed(self):
        naive_dt = datetime.now()  # No tzinfo
        data1 = self._create_user_data(createdAt=naive_dt)
        with self.assertRaises(ValidationError):
            DemoUserDocument(**data1)

        data2 = self._create_user_data(createdAt=self.now)
        user = DemoUserDocument(**data2)
        self.assertEqual(user.createdAt, self.now)

    def test_26_password_hash_absent_from_repr_and_str(self):
        data = self._create_user_data(passwordHash="SECRET_ARGON2_HASH_STRING")
        user = DemoUserDocument(**data)
        repr_str = repr(user)
        str_str = str(user)

        self.assertNotIn("SECRET_ARGON2_HASH_STRING", repr_str)
        self.assertNotIn("SECRET_ARGON2_HASH_STRING", str_str)
        self.assertIn("[REDACTED]", repr_str)

    def test_27_password_hash_and_internal_fields_absent_from_viewer_context(self):
        data = self._create_user_data()
        user = DemoUserDocument(**data)
        vc = demo_user_to_viewer_context(user)
        vc_dict = vc.model_dump()

        internal_fields = [
            "passwordHash",
            "loginName",
            "tokenVersion",
            "isSynthetic",
            "dataOrigin",
            "scientificUseAllowed",
            "createdAt",
            "updatedAt",
            "schemaVersion",
        ]
        for field in internal_fields:
            self.assertNotIn(field, vc_dict)

    def test_28_caller_input_remains_unchanged(self):
        raw_auth = {
            "scopeLevel": ScopeLevel.FARM,
            "registeredFarmDistrict": " Ampara ",
            "authorizedDistricts": ["Ampara ", " Colombo "],
            "assignedFarmIds": [],
        }
        original_copy = copy.deepcopy(raw_auth)

        data = self._create_user_data(authorization=raw_auth)
        DemoUserDocument(**data)

        self.assertEqual(raw_auth, original_copy)


if __name__ == "__main__":
    unittest.main()
