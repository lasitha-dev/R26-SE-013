import pytest
from pydantic import ValidationError
from components.health_anomaly.schemas import VetRegister, VetTokenResponse

def test_vet_register_schema_default_role():
    vet = VetRegister(
        full_name="Dr. Sam",
        email="sam@example.com",
        password="password123",
        license_number="VET123",
        phone="1234567"
    )
    assert vet.role == "vet"

def test_vet_register_schema_daph_role():
    vet = VetRegister(
        full_name="Dr. Sam",
        email="sam@example.com",
        password="password123",
        license_number="VET123",
        phone="1234567",
        role="daph"
    )
    assert vet.role == "daph"

def test_vet_register_schema_invalid_role():
    with pytest.raises(ValidationError):
        VetRegister(
            full_name="Dr. Sam",
            email="sam@example.com",
            password="password123",
            license_number="VET123",
            phone="1234567",
            role="admin"
        )
