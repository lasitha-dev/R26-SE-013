import pytest
from httpx import AsyncClient
from main import app
from components.health_anomaly.database import diagnostic_cases_collection, vets_collection, cattles_collection, farms_collection
from core.security import create_access_token
from bson import ObjectId

@pytest.mark.asyncio
async def test_diagnostic_case_flow():
    # Setup test vet token
    vet_email = "test_case_vet@adrs.lk"
    vet_doc = {
        "full_name": "Dr. Case Tester",
        "email": vet_email,
        "password": "hashed_pw",
        "license_number": "VET-CASE-2026",
        "phone": "+94771239999",
        "district": "Kandy",
        "role": "vet"
    }
    await vets_collection.delete_many({"email": vet_email})
    vet_res = await vets_collection.insert_one(vet_doc)
    vet_id = str(vet_res.inserted_id)

    token = create_access_token(data={"sub": vet_email, "role": "vet", "full_name": "Dr. Case Tester"})
    headers = {"Authorization": f"Bearer {token}"}

    # Setup dummy cattle
    cattle_doc = {
        "identifier": "COW-TEST-99",
        "owner_email": "farm_owner@test.lk",
        "breed": "Jersey",
        "gender": "Female",
        "dob": "2022-01-01",
        "weight": 450.0,
        "health_status": "Healthy",
        "status": "Healthy"
    }
    c_res = await cattles_collection.insert_one(cattle_doc)
    cattle_id = str(c_res.inserted_id)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 1. Report new diagnostic case
        report_payload = {
            "cattle_id": cattle_id,
            "animal_identifier": "COW-TEST-99",
            "breed": "Jersey",
            "disease_name": "Lumpy Skin Disease",
            "confidence": 94.5,
            "severity": "High",
            "stage": "Acute Phase",
            "prognosis": "Guarded",
            "rationale": "Circumscribed nodular cutaneous lesions observed.",
            "spatial_correlation": "Dermal layer pathology matches nodular dermis pattern.",
            "clinical_notes": "Immediate quarantine recommended.",
            "verified": False
        }
        res = await ac.post("/api/vet/cases", json=report_payload, headers=headers)
        assert res.status_code == 201, res.text
        case_data = res.json()
        assert case_data["disease_name"] == "Lumpy Skin Disease"
        assert case_data["confidence"] == 94.5
        assert case_data["status"] == "Pending Verification"
        assert case_data["verified"] is False
        case_id = case_data["id"]

        # 2. List cases
        res_list = await ac.get("/api/vet/cases", headers=headers)
        assert res_list.status_code == 200
        cases_list = res_list.json()
        assert len(cases_list) >= 1
        assert any(c["id"] == case_id for c in cases_list)

        # 3. Verify case
        verify_payload = {
            "clinical_notes": "Verified by clinical veterinary inspection. Isolation confirmed.",
            "prescription": "Antiseptic wash + Enrofloxacin",
            "health_status": "Alert"
        }
        res_verify = await ac.put(f"/api/vet/cases/{case_id}/verify", json=verify_payload, headers=headers)
        assert res_verify.status_code == 200, res_verify.text
        verified_data = res_verify.json()
        assert verified_data["status"] == "Verified"
        assert verified_data["verified"] is True
        assert verified_data["vet_name"] == "Dr. Case Tester"
        assert verified_data["vet_license"] == "VET-CASE-2026"

        # 4. Update case for the same cattle (upsert verification)
        update_payload = {
            "cattle_id": cattle_id,
            "animal_identifier": "COW-TEST-99",
            "breed": "Jersey",
            "disease_name": "Cattle (Healthy)",
            "confidence": 98.2,
            "severity": "Low",
            "stage": "Recovery",
            "prognosis": "Good",
            "rationale": "Lesions fully resolved.",
            "clinical_notes": "Recovery confirmed.",
            "verified": True
        }
        res_update = await ac.post("/api/vet/cases", json=update_payload, headers=headers)
        assert res_update.status_code == 201
        updated_data = res_update.json()
        assert updated_data["id"] == case_id  # Same case ID preserved!
        assert updated_data["disease_name"] == "Cattle (Healthy)"
        assert updated_data["confidence"] == 98.2
        assert updated_data["status"] == "Verified"

        # Ensure no duplicate cases exist for this cattle
        count = await diagnostic_cases_collection.count_documents({"cattle_id": cattle_id})
        assert count == 1

        # Check cattle updated status to Healthy
        # 5. Delete diagnostic case
        res_del = await ac.delete(f"/api/vet/cases/{case_id}", headers=headers)
        assert res_del.status_code == 200, res_del.text
        del_data = res_del.json()
        assert del_data["id"] == case_id

        # Verify case is removed from DB
        deleted_check = await diagnostic_cases_collection.find_one({"_id": ObjectId(case_id)})
        assert deleted_check is None

    # Cleanup
    await vets_collection.delete_many({"email": vet_email})
    await cattles_collection.delete_many({"_id": ObjectId(cattle_id)})
    await diagnostic_cases_collection.delete_many({"_id": ObjectId(case_id)})
