"""GEO-INT-01: vet authorization, GPS validation, and disease normalization
— the three independent gate functions, tested in isolation from the
service that composes them (that composition is covered in
`test_operational_context_service.py`)."""

import math

import pytest

from components.geospatial_tracking.domain.operational_enums import LocationStatus, OperationalDisease
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext, HostFarmRecord
from components.geospatial_tracking.services.operational.disease_normalization import resolve_operational_disease
from components.geospatial_tracking.services.operational.farm_normalization import normalize_assigned_farm


class TestVetAuthorization:
    def test_vet_role_accepted(self):
        assert AuthenticatedVetContext(email="v@example.com", role="vet").is_vet() is True

    def test_non_vet_role_rejected(self):
        assert AuthenticatedVetContext(email="f@example.com", role="farm").is_vet() is False

    def test_empty_role_rejected(self):
        assert AuthenticatedVetContext(email="x@example.com", role="").is_vet() is False


class TestFarmGpsValidation:
    def test_valid_coordinates(self):
        farm = normalize_assigned_farm(HostFarmRecord(farm_id="F1", latitude=6.9271, longitude=79.8612))
        assert farm.location_status == LocationStatus.VALID.value
        assert farm.latitude == 6.9271
        assert farm.longitude == 79.8612

    def test_missing_latitude(self):
        farm = normalize_assigned_farm(HostFarmRecord(farm_id="F1", latitude=None, longitude=79.8612))
        assert farm.location_status == LocationStatus.LOCATION_REQUIRED.value

    def test_missing_longitude(self):
        farm = normalize_assigned_farm(HostFarmRecord(farm_id="F1", latitude=6.9271, longitude=None))
        assert farm.location_status == LocationStatus.LOCATION_REQUIRED.value

    def test_invalid_latitude_out_of_range(self):
        farm = normalize_assigned_farm(HostFarmRecord(farm_id="F1", latitude=91.0, longitude=79.8612))
        assert farm.location_status == LocationStatus.LOCATION_REQUIRED.value

    def test_invalid_longitude_out_of_range(self):
        farm = normalize_assigned_farm(HostFarmRecord(farm_id="F1", latitude=6.9271, longitude=181.0))
        assert farm.location_status == LocationStatus.LOCATION_REQUIRED.value

    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf"), "6.9271", object()])
    def test_non_numeric_or_non_finite_coordinate_rejected(self, bad_value):
        farm = normalize_assigned_farm(HostFarmRecord(farm_id="F1", latitude=bad_value, longitude=79.8612))
        assert farm.location_status == LocationStatus.LOCATION_REQUIRED.value

    def test_never_invents_a_coordinate(self):
        # A farm with only a district name and no lat/lon must stay
        # LOCATION_REQUIRED -- never guessed from location_district.
        farm = normalize_assigned_farm(
            HostFarmRecord(farm_id="F1", latitude=None, longitude=None, location_district="Colombo")
        )
        assert farm.latitude is None
        assert farm.longitude is None
        assert farm.location_status == LocationStatus.LOCATION_REQUIRED.value

    def test_minimal_pii_fields_only(self):
        farm = normalize_assigned_farm(HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8))
        field_names = {f for f in farm.__dataclass_fields__}
        forbidden = {"owner_name", "email", "phone", "password", "owner_email"}
        assert field_names.isdisjoint(forbidden)


class TestDiseaseNormalization:
    def test_verified_lsd_case_accepted_independently(self):
        assert resolve_operational_disease("Lumpy Skin Disease") == OperationalDisease.LSD

    def test_verified_fmd_case_accepted_independently(self):
        assert resolve_operational_disease("Foot and Mouth Disease") == OperationalDisease.FMD

    def test_raw_classifier_key_lumpy_skin(self):
        assert resolve_operational_disease("lumpy_skin") == OperationalDisease.LSD

    def test_raw_classifier_key_foot_and_mouth(self):
        assert resolve_operational_disease("foot_and_mouth") == OperationalDisease.FMD

    def test_unsupported_disease_mastitis(self):
        assert resolve_operational_disease("Mastitis") is None

    def test_unsupported_disease_healthy_cattle(self):
        assert resolve_operational_disease("Cattle (Healthy)") is None

    def test_unknown_disease_never_becomes_lsd(self):
        result = resolve_operational_disease("Some Completely Unrecognized Condition")
        assert result != OperationalDisease.LSD
        assert result is None

    def test_unknown_disease_never_becomes_fmd(self):
        result = resolve_operational_disease("Some Completely Unrecognized Condition")
        assert result != OperationalDisease.FMD
        assert result is None

    def test_missing_disease_name_is_unsupported_not_a_default(self):
        # None must never silently resolve to LSD (unlike
        # services.disease.resolve_disease_selection's DEFAULT_DISEASE
        # behavior, which is intentionally NOT reused here).
        assert resolve_operational_disease(None) is None
        assert resolve_operational_disease("") is None
        assert resolve_operational_disease("   ") is None
