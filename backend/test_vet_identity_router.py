import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from main import create_app
from unittest.mock import AsyncMock, patch
from core.security import get_password_hash

@pytest.fixture
def app():
    return create_app()

@pytest.mark.asyncio
async def test_vet_register_daph_role(app):
    with patch("components.health_anomaly.router.vets_collection.find_one", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = None
        with patch("components.health_anomaly.router.vets_collection.insert_one", new_callable=AsyncMock) as mock_insert:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                reg_resp = await client.post("/api/vet/register", json={
                    "full_name": "DAPH User",
                    "email": "daph@example.com",
                    "password": "password123",
                    "license_number": "DAPH-001",
                    "phone": "0771122334",
                    "district": "ALL_DISTRICTS",
                    "role": "daph",
                    "assigned_farms": []
                })
                
                assert reg_resp.status_code == 201
                
                # Check that insert_one was called with role "daph"
                called_args = mock_insert.call_args[0][0]
                assert called_args["role"] == "daph"
                assert called_args["email"] == "daph@example.com"
                assert called_args["district"] == "ALL_DISTRICTS"

@pytest.mark.asyncio
async def test_vet_register_daph_rejects_single_district(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_resp = await client.post("/api/vet/register", json={
            "full_name": "DAPH User",
            "email": "daph@example.com",
            "password": "password123",
            "license_number": "DAPH-001",
            "phone": "0771122334",
            "district": "Colombo",
            "role": "daph",
            "assigned_farms": []
        })
        
        assert reg_resp.status_code == 400
        assert "DAPH Official cannot be restricted to a single district" in reg_resp.json()["detail"]

@pytest.mark.asyncio
async def test_vet_register_vet_rejects_all_districts(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_resp = await client.post("/api/vet/register", json={
            "full_name": "Vet User",
            "email": "vet@example.com",
            "password": "password123",
            "license_number": "VET-001",
            "phone": "0771122334",
            "district": "ALL_DISTRICTS",
            "role": "vet",
            "assigned_farms": []
        })
        
        assert reg_resp.status_code == 400
        assert "Veterinary Officer must select a valid district jurisdiction" in reg_resp.json()["detail"]

@pytest.mark.asyncio
async def test_vet_login_daph_role(app):
    with patch("components.health_anomaly.router.vets_collection.find_one", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = {
            "email": "daph@example.com",
            "password": get_password_hash("password123"),
            "full_name": "DAPH User",
            "role": "daph",
            "district": "Galle"
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login_resp = await client.post("/api/vet/login", json={
                "email": "daph@example.com",
                "password": "password123"
            })
            
            assert login_resp.status_code == 200
            data = login_resp.json()
            assert data["role"] == "daph"
            assert data["full_name"] == "DAPH User"

@pytest.mark.asyncio
async def test_vet_login_vet_role(app):
    with patch("components.health_anomaly.router.vets_collection.find_one", new_callable=AsyncMock) as mock_find:
        # DB doc with no role, defaults to vet
        mock_find.return_value = {
            "email": "vet@example.com",
            "password": get_password_hash("password123"),
            "full_name": "Vet User",
            "district": "Galle"
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login_resp = await client.post("/api/vet/login", json={
                "email": "vet@example.com",
                "password": "password123"
            })
            
            assert login_resp.status_code == 200
            data = login_resp.json()
            assert data["role"] == "vet"

@pytest.mark.asyncio
async def test_vet_login_corrupted_role(app):
    with patch("components.health_anomaly.router.vets_collection.find_one", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = {
            "email": "bad@example.com",
            "password": get_password_hash("password123"),
            "full_name": "Bad User",
            "role": "admin",
            "district": "Galle"
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login_resp = await client.post("/api/vet/login", json={
                "email": "bad@example.com",
                "password": "password123"
            })
            
            assert login_resp.status_code == 403
            assert "corrupted" in login_resp.json()["detail"]

@pytest.mark.asyncio
async def test_vet_login_invalid_password(app):
    with patch("components.health_anomaly.router.vets_collection.find_one", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = {
            "email": "vet@example.com",
            "password": get_password_hash("password123"),
            "full_name": "Vet User",
            "role": "vet",
            "district": "Galle"
        }
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login_resp = await client.post("/api/vet/login", json={
                "email": "vet@example.com",
                "password": "wrongpassword"
            })
            
            assert login_resp.status_code == 401
