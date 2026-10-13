import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from components.health_anomaly.database import (
    diagnostic_cases_collection, vets_collection, cattles_collection,
    farms_collection, vet_notifications_collection
)
from core.security import create_access_token
from bson import ObjectId

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_diagnostic_case_flow():
    # Setup dummy farm
    farm_email = "farm_owner@test.lk"
    await farms_collection.delete_many({"email": farm_email})
    farm_doc = {
        "owner_name": "Dr. Tester Assigned Farm",
        "email": farm_email,
        "registration_number": "REG-TEST-FARM-99",
        "assigned_vet_ids": []
    }
    farm_res = await farms_collection.insert_one(farm_doc)
    farm_id = str(farm_res.inserted_id)

    # Setup test vet token
    vet_email = "test_case_vet@adrs.lk"
    vet_doc = {
        "full_name": "Dr. Case Tester",
        "email": vet_email,
        "password": "hashed_pw",
        "license_number": "VET-CASE-2026",
        "phone": "+94771239999",
        "district": "Kandy",
        "role": "vet",
        "assigned_farm_ids": [farm_id]
    }
    await vets_collection.delete_many({"email": vet_email})
    vet_res = await vets_collection.insert_one(vet_doc)
    vet_id = str(vet_res.inserted_id)

    # Link vet to farm
    await farms_collection.update_one({"_id": ObjectId(farm_id)}, {"$set": {"assigned_vet_ids": [vet_id]}})

    vet_token = create_access_token(data={"sub": vet_email, "role": "vet", "full_name": "Dr. Case Tester"})
    vet_headers = {"Authorization": f"Bearer {vet_token}"}

    farmer_token = create_access_token(data={"sub": farm_email, "role": "farmer", "owner_name": "Dr. Tester Assigned Farm"})
    farmer_headers = {"Authorization": f"Bearer {farmer_token}"}

    # Setup dummy cattle
    cattle_doc = {
        "identifier": "COW-TEST-99",
        "owner_email": farm_email,
        "breed": "Jersey",
        "gender": "Female",
        "dob": "2022-01-01",
        "weight": 450.0,
        "health_status": "Healthy",
        "status": "Healthy"
    }
    c_res = await cattles_collection.insert_one(cattle_doc)
    cattle_id = str(c_res.inserted_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Farmer reports new diagnostic case (verified: False enforced even if requested True)
        farmer_report_payload = {
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
            "verified": True  # Farmer tries to set True, but backend should force False
        }
        res = await ac.post("/api/vet/cases", json=farmer_report_payload, headers=farmer_headers)
        assert res.status_code == 201, res.text
        farmer_case_data = res.json()
        assert farmer_case_data["disease_name"] == "Lumpy Skin Disease"
        assert farmer_case_data["confidence"] == 94.5
        assert farmer_case_data["status"] == "Pending Verification"
        assert farmer_case_data["verified"] is False
        assert farmer_case_data["reported_by"] == "farmer"
        farmer_case_id = farmer_case_data["id"]

        # Notification should have been generated for the assigned vet
        notifs = []
        async for n in vet_notifications_collection.find({"case_id": farmer_case_id}):
            notifs.append(n)
        assert len(notifs) >= 1
        assert notifs[0]["type"] == "FARMER_DISEASE_REPORT"

        # 2. Farmer CANNOT verify case
        verify_payload = {
            "clinical_notes": "Farmer trying to self-verify",
            "health_status": "Alert"
        }
        res_farmer_verify = await ac.put(f"/api/vet/cases/{farmer_case_id}/verify", json=verify_payload, headers=farmer_headers)
        assert res_farmer_verify.status_code == 403

        # 3. Farmer CANNOT delete case
        res_farmer_del = await ac.delete(f"/api/vet/cases/{farmer_case_id}", headers=farmer_headers)
        assert res_farmer_del.status_code == 403

        # 4. Vet verifies farmer's case
        vet_verify_payload = {
            "clinical_notes": "Verified by Dr. Case Tester after inspecting lesions.",
            "prescription": "Antiseptic wash + Enrofloxacin",
            "health_status": "Alert"
        }
        res_vet_verify = await ac.put(f"/api/vet/cases/{farmer_case_id}/verify", json=vet_verify_payload, headers=vet_headers)
        assert res_vet_verify.status_code == 200, res_vet_verify.text
        verified_data = res_vet_verify.json()
        assert verified_data["status"] == "Verified"
        assert verified_data["verified"] is True
        assert verified_data["vet_name"] == "Dr. Case Tester"
        assert verified_data["vet_license"] == "VET-CASE-2026"

        # 5. Multiple disease cases can be created for the same cattle
        vet_second_report = {
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
        res_second = await ac.post("/api/vet/cases", json=vet_second_report, headers=vet_headers)
        assert res_second.status_code == 201
        second_case_data = res_second.json()
        assert second_case_data["id"] != farmer_case_id  # Unique second case ID!
        assert second_case_data["status"] == "Verified"
        assert second_case_data["reported_by"] == "vet"

        # Both cases exist in DB
        count = await diagnostic_cases_collection.count_documents({"cattle_id": cattle_id})
        assert count == 2

        # 6. List cases by reported_by
        res_farmer_cases = await ac.get("/api/vet/cases?reported_by=farmer", headers=vet_headers)
        assert res_farmer_cases.status_code == 200
        farmer_list = res_farmer_cases.json()
        assert any(c["id"] == farmer_case_id for c in farmer_list)

        res_vet_cases = await ac.get("/api/vet/cases?reported_by=vet", headers=vet_headers)
        assert res_vet_cases.status_code == 200
        vet_list = res_vet_cases.json()
        assert any(c["id"] == second_case_data["id"] for c in vet_list)

        # 7. Vet notifications endpoint
        res_notifs = await ac.get("/api/vet/notifications", headers=vet_headers)
        assert res_notifs.status_code == 200
        notif_list = res_notifs.json()
        assert len(notif_list) >= 1

        # Cleanup created cases
        await ac.delete(f"/api/vet/cases/{farmer_case_id}", headers=vet_headers)
        await ac.delete(f"/api/vet/cases/{second_case_data['id']}", headers=vet_headers)

    # Cleanup DB
    await vets_collection.delete_many({"email": vet_email})
    await farms_collection.delete_many({"email": farm_email})
    await cattles_collection.delete_many({"_id": ObjectId(cattle_id)})
    await vet_notifications_collection.delete_many({"vet_id": vet_id})
