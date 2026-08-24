import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from main import create_app
from core.database import farms_collection, vets_collection, cattles_collection
from core.security import create_access_token, get_password_hash
from bson import ObjectId

@pytest.mark.asyncio
async def test_farm_vet_linking_flow():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Setup test farm and test vet in DB
        farm_email = "test_farm_linking@example.com"
        vet_email = "test_vet_linking@example.com"
        unassigned_vet_email = "unassigned_vet@example.com"

        await farms_collection.delete_many({"email": farm_email})
        await vets_collection.delete_many({"email": {"$in": [vet_email, unassigned_vet_email]}})
        await cattles_collection.delete_many({"owner_email": farm_email})

        # Insert Farm
        farm_doc = {
            "owner_name": "Test Farmer Linking",
            "email": farm_email,
            "password": get_password_hash("password123"),
            "location_district": "6.9271, 79.8612 (Colombo)",
            "latitude": 6.9271,
            "longitude": 79.8612,
            "registration_number": "REG-TEST-99",
            "veterinarian_name": "Dr. Placeholder",
            "total_animals": 2,
            "assigned_vet_ids": []
        }
        res_farm = await farms_collection.insert_one(farm_doc)
        farm_id = str(res_farm.inserted_id)

        # Insert Vet 1 (Colombo)
        vet_doc = {
            "full_name": "Dr. Kasun Perera",
            "email": vet_email,
            "password": get_password_hash("password123"),
            "license_number": "SLVC-9912",
            "phone": "0771234567",
            "district": "Colombo",
            "role": "vet",
            "assigned_farms": [],
            "assigned_farm_ids": []
        }
        res_vet = await vets_collection.insert_one(vet_doc)
        vet_id = str(res_vet.inserted_id)

        # Insert Vet 2 (Kandy)
        unassigned_vet_doc = {
            "full_name": "Dr. Samantha Silva",
            "email": unassigned_vet_email,
            "password": get_password_hash("password123"),
            "license_number": "SLVC-4412",
            "phone": "0719876543",
            "district": "Kandy",
            "role": "vet",
            "assigned_farms": [],
            "assigned_farm_ids": []
        }
        res_unassigned = await vets_collection.insert_one(unassigned_vet_doc)
        unassigned_vet_id = str(res_unassigned.inserted_id)

        # Insert Cattle for Farm
        await cattles_collection.insert_one({
            "identifier": "COW-TEST-01",
            "gender": "Female",
            "dob": "2022-01-01",
            "breed": "Holstein-Friesian",
            "weight": 520.0,
            "health_status": "Alert",
            "status": "Alert",
            "bcs_score": 3.2,
            "owner_email": farm_email
        })

        farm_token = create_access_token({"sub": farm_email, "owner_name": "Test Farmer Linking"})
        vet_token = create_access_token({"sub": vet_email, "role": "vet", "full_name": "Dr. Kasun Perera"})
        unassigned_vet_token = create_access_token({"sub": unassigned_vet_email, "role": "vet", "full_name": "Dr. Samantha Silva"})

        # 2. Test Search Vets with District Filter
        resp = await client.get("/api/vet/search?district=Colombo", headers={"Authorization": f"Bearer {farm_token}"})
        assert resp.status_code == 200
        vets = resp.json()
        assert any(v["email"] == vet_email for v in vets)
        assert not any(v["email"] == unassigned_vet_email for v in vets)

        # Search with text query
        resp = await client.get("/api/vet/search?q=Kasun", headers={"Authorization": f"Bearer {farm_token}"})
        assert resp.status_code == 200
        vets = resp.json()
        assert any(v["email"] == vet_email for v in vets)

        # 3. Test Assign Vet
        assign_resp = await client.post(
            "/api/farms/assign-vet",
            json={"vet_id": vet_id},
            headers={"Authorization": f"Bearer {farm_token}"}
        )
        assert assign_resp.status_code == 200
        assert "assigned to your farm" in assign_resp.json()["message"]

        # 4. Check assigned vets list
        assigned_list_resp = await client.get("/api/farms/assigned-vets", headers={"Authorization": f"Bearer {farm_token}"})
        assert assigned_list_resp.status_code == 200
        assigned_vets = assigned_list_resp.json()
        assert len(assigned_vets) >= 1
        assert any(v["id"] == vet_id and v["assigned"] is True for v in assigned_vets)

        # 5. Check Vet's my-farms endpoint
        my_farms_resp = await client.get("/api/vet/my-farms", headers={"Authorization": f"Bearer {vet_token}"})
        assert my_farms_resp.status_code == 200
        my_farms = my_farms_resp.json()
        assert len(my_farms) >= 1
        farm_match = next((f for f in my_farms if f["id"] == farm_id), None)
        assert farm_match is not None
        assert farm_match["latitude"] == 6.9271
        assert farm_match["longitude"] == 79.8612
        assert farm_match["total_animals"] == 1
        assert farm_match["alert_count"] == 1

        # 6. Test RBAC on Cattle Endpoint:
        # Assigned Vet can access cattle
        cattle_resp = await client.get(f"/api/vet/farms/{farm_id}/cattle", headers={"Authorization": f"Bearer {vet_token}"})
        assert cattle_resp.status_code == 200
        cattle_data = cattle_resp.json()
        assert len(cattle_data["cattle"]) == 1
        assert cattle_data["cattle"][0]["identifier"] == "COW-TEST-01"

        # Unassigned Vet is rejected with 403 Forbidden
        unassigned_resp = await client.get(f"/api/vet/farms/{farm_id}/cattle", headers={"Authorization": f"Bearer {unassigned_vet_token}"})
        assert unassigned_resp.status_code == 403

        # 7. Test Unassign Vet
        unassign_resp = await client.post(
            "/api/farms/unassign-vet",
            json={"vet_id": vet_id},
            headers={"Authorization": f"Bearer {farm_token}"}
        )
        assert unassign_resp.status_code == 200

        # Now vet should no longer be authorized
        cattle_resp_after = await client.get(f"/api/vet/farms/{farm_id}/cattle", headers={"Authorization": f"Bearer {vet_token}"})
        assert cattle_resp_after.status_code == 403

        # 8. Test Vet Registration with District & Persistence
        registered_vet_email = "new_reg_vet@example.com"
        await vets_collection.delete_many({"email": registered_vet_email})

        reg_resp = await client.post("/api/vet/register", json={
            "full_name": "Dr. Nimal Wickrema",
            "email": registered_vet_email,
            "password": "password123",
            "license_number": "SLVC-TEST-REG-101",
            "phone": "0771122334",
            "district": "Galle",
            "role": "vet",
            "assigned_farms": []
        })
        assert reg_resp.status_code == 201

        # Test Vet Login returns district
        login_resp = await client.post("/api/vet/login", json={
            "email": registered_vet_email,
            "password": "password123"
        })
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        assert login_data["district"] == "Galle"
        assert login_data["full_name"] == "Dr. Nimal Wickrema"
        reg_vet_token = login_data["access_token"]

        # Test GET /api/vet/profile
        profile_resp = await client.get("/api/vet/profile", headers={"Authorization": f"Bearer {reg_vet_token}"})
        assert profile_resp.status_code == 200
        profile_data = profile_resp.json()
        assert profile_data["district"] == "Galle"
        assert profile_data["license_number"] == "SLVC-TEST-REG-101"

        # Test PUT /api/vet/profile (update district and name)
        update_resp = await client.put(
            "/api/vet/profile",
            json={
                "full_name": "Dr. Nimal Wickrema Senior",
                "license_number": "SLVC-TEST-REG-101",
                "phone": "0779988776",
                "district": "Matara"
            },
            headers={"Authorization": f"Bearer {reg_vet_token}"}
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["district"] == "Matara"
        assert update_resp.json()["full_name"] == "Dr. Nimal Wickrema Senior"

        # Verify updated profile persists on fresh fetch
        fresh_profile_resp = await client.get("/api/vet/profile", headers={"Authorization": f"Bearer {reg_vet_token}"})
        assert fresh_profile_resp.status_code == 200
        fresh_data = fresh_profile_resp.json()
        assert fresh_data["district"] == "Matara"
        assert fresh_data["phone"] == "0779988776"
        assert fresh_data["full_name"] == "Dr. Nimal Wickrema Senior"

        # Verify search by new district finds the updated vet
        search_matara = await client.get("/api/vet/search?district=Matara", headers={"Authorization": f"Bearer {farm_token}"})
        assert search_matara.status_code == 200
        assert any(v["email"] == registered_vet_email for v in search_matara.json())

        # Cleanup
        await farms_collection.delete_many({"email": farm_email})
        await vets_collection.delete_many({"email": {"$in": [vet_email, unassigned_vet_email, registered_vet_email]}})
        await cattles_collection.delete_many({"owner_email": farm_email})
        print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_farm_vet_linking_flow())
