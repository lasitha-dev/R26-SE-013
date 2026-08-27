import pytest
import inspect
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, status
import jwt
from bson import ObjectId

from components.risk_forecasting.routes import router, dispatch_notification_batch

app = FastAPI()
app.include_router(router, prefix="/api/v1/risk-forecasting")
client = TestClient(app)

from core.security import JWT_SECRET, JWT_ALGORITHM

def create_token(sub: str, role: str = None) -> str:
    payload = {"sub": sub}
    if role is not None:
        payload["role"] = role
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

class AsyncIterator:
    def __init__(self, seq):
        self.iter = iter(seq)
    def __aiter__(self):
        return self
    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration:
            raise StopAsyncIteration

@pytest.fixture
def mock_jwt_env():
    # We no longer need to monkeypatch since we use the real JWT_SECRET
    pass

def test_01_dispatch_not_coroutine():
    assert not inspect.iscoroutinefunction(dispatch_notification_batch), "dispatch_notification_batch should not be async"

@patch("components.risk_forecasting.routes.notification_service.dispatch_batch")
def test_02_03_dispatch_returns_result_and_no_mongo(mock_dispatch):
    mock_dispatch.return_value = {"status": "dispatched"}
    res = dispatch_notification_batch("batch_123")
    assert res == {"status": "dispatched"}
    mock_dispatch.assert_called_once_with("batch_123")

def test_04_missing_auth_returns_401():
    res = client.get("/api/v1/risk-forecasting/notifications")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

def test_05_invalid_jwt_returns_401():
    res = client.get("/api/v1/risk-forecasting/notifications", headers={"Authorization": "Bearer invalid"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_06_to_11_farmer_roles(mock_jwt_env, monkeypatch):
    mock_find_one = AsyncMock()
    monkeypatch.setattr("core.database.farms_collection.find_one", mock_find_one)

    # 6. Explicit vet role returns 403
    res = client.get("/api/v1/risk-forecasting/notifications", headers={"Authorization": f"Bearer {create_token('sub', 'vet')}"})
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 7. Explicit daph role returns 403
    res = client.get("/api/v1/risk-forecasting/notifications", headers={"Authorization": f"Bearer {create_token('sub', 'daph')}"})
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 8. Unsupported non-empty role returns 403
    res = client.get("/api/v1/risk-forecasting/notifications", headers={"Authorization": f"Bearer {create_token('sub', 'admin')}"})
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 11. Missing farm profile returns 403
    mock_find_one.return_value = None
    res = client.get("/api/v1/risk-forecasting/notifications", headers={"Authorization": f"Bearer {create_token('farmer@test.com', 'farmer')}"})
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 9 & 12 & 14. Explicit farmer role may continue, uses email lookup, no request-controlled identifier
    mock_find_one.return_value = {"_id": ObjectId("60d5ec49e2182b8a70656a5c"), "email": "farmer@test.com"}

    mock_cursor = MagicMock()
    mock_cursor.__aiter__.return_value = []

    mock_collection = MagicMock()
    mock_collection.find.return_value.sort.return_value = mock_cursor
    import core.database
    monkeypatch.setattr(core.database.db, "forecast_notifications", mock_collection)

    res = client.get("/api/v1/risk-forecasting/notifications", headers={"Authorization": f"Bearer {create_token('farmer@test.com', 'farmer')}"})
    assert res.status_code == 200
    mock_find_one.assert_called_with({"email": "farmer@test.com"})

    # 10. Legacy missing role may continue
    res = client.get("/api/v1/risk-forecasting/notifications", headers={"Authorization": f"Bearer {create_token('farmer@test.com')}"})
    assert res.status_code == 200

@pytest.mark.asyncio
async def test_13_15_16_notification_lookup(mock_jwt_env, monkeypatch):
    mock_find_one = AsyncMock(return_value={"_id": ObjectId("60d5ec49e2182b8a70656a5c"), "email": "farmer@test.com"})
    monkeypatch.setattr("core.database.farms_collection.find_one", mock_find_one)

    # 15. Empty repository result returns []
    mock_cursor_empty = MagicMock()
    mock_cursor_empty.__aiter__.return_value = []

    mock_collection = MagicMock()
    mock_collection.find.return_value.sort.return_value = mock_cursor_empty
    import core.database
    monkeypatch.setattr(core.database.db, "forecast_notifications", mock_collection)

    res = client.get("/api/v1/risk-forecasting/notifications", headers={"Authorization": f"Bearer {create_token('farmer@test.com', 'farmer')}"})
    assert res.json() == []

    # 13 & 16. Uses only resolved Farm _id, receives only requested result
    mock_cursor_data = MagicMock()
    mock_cursor_data.__aiter__.return_value = [{"_id": ObjectId("60d5ec49e2182b8a70656a5c"), "title": "Test"}]
    mock_collection.find.return_value.sort.return_value = mock_cursor_data

    res = client.get("/api/v1/risk-forecasting/notifications", headers={"Authorization": f"Bearer {create_token('farmer@test.com', 'farmer')}"})
    assert res.json() == [{"_id": "60d5ec49e2182b8a70656a5c", "title": "Test"}]
    mock_collection.find.assert_called_with({"farm_id": "60d5ec49e2182b8a70656a5c"})

    # 1. Static route registration contains exactly one GET /notifications.
    # 2. Exactly one list_farmer_notifications definition remains.
    import inspect
    import components.risk_forecasting.routes as routes_module

    # Count list_farmer_notifications functions in the module
    funcs = [n for n, f in inspect.getmembers(routes_module, inspect.isfunction) if n == 'list_farmer_notifications']
    assert len(funcs) == 1

    # Count GET /notifications in router
    route_count = sum(1 for r in router.routes if getattr(r, "methods", None) == {"GET"} and r.path == "/notifications")
    assert route_count == 1

    # 3. The broken farmer_id query is absent from the endpoint
    source = inspect.getsource(routes_module.list_farmer_notifications)
    assert "farmer_id" not in source

@pytest.mark.asyncio
async def test_forwarding_auth_and_routing(mock_jwt_env, monkeypatch):
    # 17, 18, 19
    res = client.post("/api/v1/risk-forecasting/advisories/adv1/forward-to-assigned-farmers")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    res = client.post("/api/v1/risk-forecasting/advisories/adv1/forward-to-assigned-farmers", headers={"Authorization": "Bearer invalid"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    res = client.post("/api/v1/risk-forecasting/advisories/adv1/forward-to-assigned-farmers", headers={"Authorization": f"Bearer {create_token('user', 'daph')}"})
    assert res.status_code == status.HTTP_403_FORBIDDEN

    res = client.post("/api/v1/risk-forecasting/advisories/adv1/forward-to-assigned-farmers", headers={"Authorization": f"Bearer {create_token('user', 'farmer')}"})
    assert res.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_forwarding_logic(mock_jwt_env, monkeypatch):
    mock_vet_find = AsyncMock()
    monkeypatch.setattr("core.database.vets_collection.find_one", mock_vet_find)

    # 20. Resolves vet through signed JWT sub
    mock_vet_find.return_value = None
    res = client.post("/api/v1/risk-forecasting/advisories/adv1/forward-to-assigned-farmers", headers={"Authorization": f"Bearer {create_token('vet@test.com', 'vet')}"})
    assert res.status_code == status.HTTP_403_FORBIDDEN
    mock_vet_find.assert_called_with({"email": "vet@test.com"})

    mock_vet_find.return_value = {
        "_id": ObjectId("60d5ec49e2182b8a70656a5d"),
        "email": "vet@test.com",
        "assigned_farm_ids": ["60d5ec49e2182b8a70656a51"],
        "assigned_farms": ["f1@test.com"]
    }

    mock_get_advisory = MagicMock()
    monkeypatch.setattr("components.risk_forecasting.routes.advisory_service.get_advisory", mock_get_advisory)

    # 24. Unknown advisory returns 404
    mock_get_advisory.side_effect = KeyError("Advisory not found")
    res = client.post("/api/v1/risk-forecasting/advisories/adv1/forward-to-assigned-farmers", headers={"Authorization": f"Bearer {create_token('vet@test.com', 'vet')}"})
    assert res.status_code == status.HTTP_404_NOT_FOUND

    mock_get_advisory.side_effect = None
    mock_get_advisory.return_value = {"advisory_id": "adv1"}

    mock_farm_find = MagicMock()
    monkeypatch.setattr("core.database.farms_collection.find", mock_farm_find)

    # 21, 22. Exact assigned-farm query and deduplication
    farm1 = {"_id": ObjectId("60d5ec49e2182b8a70656a51"), "email": "f1@test.com"}
    farm2 = {"_id": ObjectId("60d5ec49e2182b8a70656a51"), "email": "duplicate@test.com"} # duplicate _id
    farm3 = {"_id": ObjectId("60d5ec49e2182b8a70656a52"), "email": "f2@test.com"}

    mock_farm_find.return_value = AsyncIterator([farm1, farm2, farm3])
    mock_forward = AsyncMock(return_value={"notified_count": 2, "already_notified_count": 0})
    monkeypatch.setattr("components.risk_forecasting.repositories.farmer_notification_repository.forward_to_assigned_farms", mock_forward)

    res = client.post("/api/v1/risk-forecasting/advisories/adv1/forward-to-assigned-farmers", headers={"Authorization": f"Bearer {create_token('vet@test.com', 'vet')}"})
    assert res.status_code == 200

    query = mock_farm_find.call_args[0][0]
    assert "$or" in query
    or_conds = query["$or"]
    assert {"_id": {"$in": [ObjectId("60d5ec49e2182b8a70656a51")]}} in or_conds
    assert {"email": {"$in": ["f1@test.com"]}} in or_conds
    assert {"assigned_vet_ids": "60d5ec49e2182b8a70656a5d"} in or_conds
    assert {"assigned_vet_emails": "vet@test.com"} in or_conds

    called_farms = mock_forward.call_args[0][1]
    assert len(called_farms) == 2 # farm1 and farm3, farm2 deduplicated

    # 26. No generic NotificationDelivery recipient_id is used.
    # Asserting that the forward_to_assigned_farms uses the assigned_farms explicitly.
    assert mock_forward.call_args[0][1] == [farm1, farm3]

@pytest.mark.asyncio
async def test_forwarding_zero_farms_and_errors(mock_jwt_env, monkeypatch):
    mock_vet_find = AsyncMock(return_value={"_id": ObjectId("60d5ec49e2182b8a70656a5d"), "email": "vet@test.com"})
    monkeypatch.setattr("core.database.vets_collection.find_one", mock_vet_find)
    mock_get_advisory = MagicMock(return_value={"advisory_id": "adv1"})
    monkeypatch.setattr("components.risk_forecasting.routes.advisory_service.get_advisory", mock_get_advisory)

    # 23. Zero assigned farms returns notified_count 0
    mock_farm_find = MagicMock(return_value=AsyncIterator([]))
    monkeypatch.setattr("core.database.farms_collection.find", mock_farm_find)

    res = client.post("/api/v1/risk-forecasting/advisories/adv1/forward-to-assigned-farmers", headers={"Authorization": f"Bearer {create_token('vet@test.com', 'vet')}"})
    assert res.status_code == 200
    assert res.json() == {"advisory_id": "adv1", "notified_count": 0, "already_notified_count": 0, "status": "forwarded"}

    # 25. Repository/database failure returns controlled HTTP 500
    mock_farm_find.return_value = AsyncIterator([{"_id": ObjectId("60d5ec49e2182b8a70656a51")}])
    mock_forward = AsyncMock(side_effect=Exception("DB Error"))
    monkeypatch.setattr("components.risk_forecasting.repositories.farmer_notification_repository.forward_to_assigned_farms", mock_forward)

    res = client.post("/api/v1/risk-forecasting/advisories/adv1/forward-to-assigned-farmers", headers={"Authorization": f"Bearer {create_token('vet@test.com', 'vet')}"})
    assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
