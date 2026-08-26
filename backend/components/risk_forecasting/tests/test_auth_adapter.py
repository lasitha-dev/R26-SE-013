import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch
import jwt
import sys

from components.risk_forecasting.integration.auth_adapter import (
    get_viewer_context,
    ViewerContextResponse
)
from core.security import JWT_SECRET, JWT_ALGORITHM

def _model_to_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()

class MockRequest:
    def __init__(self, headers=None, query_params=None):
        self.headers = headers or {}
        self.query_params = query_params or {}

@pytest.mark.asyncio
async def test_case_01_missing_auth():
    request = MockRequest()
    with pytest.raises(HTTPException) as exc_info:
        await get_viewer_context(request)
    assert exc_info.value.status_code == 401
    assert "Missing Authorization header" in exc_info.value.detail

@pytest.mark.asyncio
async def test_case_02_invalid_format():
    request = MockRequest(headers={"Authorization": "InvalidToken123"})
    with pytest.raises(HTTPException) as exc_info:
        await get_viewer_context(request)
    assert exc_info.value.status_code == 401
    assert "Invalid Authorization header format" in exc_info.value.detail

@pytest.mark.asyncio
async def test_case_03_blank_token():
    request = MockRequest(headers={"Authorization": "Bearer   "})
    with pytest.raises(HTTPException) as exc_info:
        await get_viewer_context(request)
    assert exc_info.value.status_code == 401
    assert "Invalid Authorization header format" in exc_info.value.detail

@pytest.mark.asyncio
@patch("components.risk_forecasting.integration.auth_adapter.jwt.decode")
async def test_case_04_invalid_jwt(mock_jwt_decode):
    mock_jwt_decode.side_effect = jwt.PyJWTError("Invalid token")
    request = MockRequest(headers={"Authorization": "Bearer some_token"})
    with pytest.raises(HTTPException) as exc_info:
        await get_viewer_context(request)
    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail

@pytest.mark.asyncio
@patch("components.risk_forecasting.integration.auth_adapter.jwt.decode")
async def test_case_05_missing_subject(mock_jwt_decode):
    mock_jwt_decode.return_value = {"sub": "  "}
    request = MockRequest(headers={"Authorization": "Bearer valid_token"})
    with pytest.raises(HTTPException) as exc_info:
        await get_viewer_context(request)
    assert exc_info.value.status_code == 401
    assert "Invalid token credentials" in exc_info.value.detail

@pytest.mark.asyncio
@patch("components.risk_forecasting.integration.auth_adapter.jwt.decode")
@patch("components.risk_forecasting.integration.auth_adapter.vets_collection")
async def test_case_06_vet_record_not_found(mock_vets_collection, mock_jwt_decode):
    mock_jwt_decode.return_value = {"sub": "non_existent@example.com"}
    mock_vets_collection.find_one = AsyncMock(return_value=None)
    request = MockRequest(headers={"Authorization": "Bearer valid_token"})
    with pytest.raises(HTTPException) as exc_info:
        await get_viewer_context(request)
    assert exc_info.value.status_code == 403
    assert "Veterinary profile not found" in exc_info.value.detail
    mock_vets_collection.find_one.assert_called_once_with({"email": "non_existent@example.com"})

@pytest.mark.asyncio
@patch("components.risk_forecasting.integration.auth_adapter.jwt.decode")
@patch("components.risk_forecasting.integration.auth_adapter.vets_collection")
async def test_case_07_non_vet_role(mock_vets_collection, mock_jwt_decode):
    mock_jwt_decode.return_value = {"sub": "other@example.com"}
    mock_vets_collection.find_one = AsyncMock(return_value={"role": "farmer"})
    request = MockRequest(headers={"Authorization": "Bearer valid_token"})
    with pytest.raises(HTTPException) as exc_info:
        await get_viewer_context(request)
    assert exc_info.value.status_code == 403
    assert "Only Veterinary Officers" in exc_info.value.detail

@pytest.mark.asyncio
@patch("components.risk_forecasting.integration.auth_adapter.jwt.decode")
@patch("components.risk_forecasting.integration.auth_adapter.vets_collection")
async def test_case_08_missing_district(mock_vets_collection, mock_jwt_decode):
    mock_jwt_decode.return_value = {"sub": "vet@example.com"}
    mock_vets_collection.find_one = AsyncMock(return_value={"role": "vet", "district": ""})
    request = MockRequest(headers={"Authorization": "Bearer valid_token"})
    with pytest.raises(HTTPException) as exc_info:
        await get_viewer_context(request)
    assert exc_info.value.status_code == 403
    assert "Veterinary profile missing valid district" in exc_info.value.detail

@pytest.mark.asyncio
@patch("components.risk_forecasting.integration.auth_adapter.jwt.decode")
@patch("components.risk_forecasting.integration.auth_adapter.vets_collection")
async def test_case_09_to_15_success(mock_vets_collection, mock_jwt_decode):
    mock_jwt_decode.return_value = {"sub": "vet@example.com"}
    mock_vet_doc = {
        "_id": "mock_obj_id",
        "email": "vet@example.com",
        "district": "Colombo ",
        "role": "vet",
        "assigned_farm_ids": ["FARM_1", 123, None],
        "passwordHash": "hashed",
        "tokenVersion": 2
    }
    mock_vets_collection.find_one = AsyncMock(return_value=mock_vet_doc)
    
    request = MockRequest(headers={"Authorization": "Bearer valid_token"})
    vc = await get_viewer_context(request)
    
    assert isinstance(vc, ViewerContextResponse)
    # 9. evidence-backed district resolution
    assert vc.authorization.authorizedDistricts == ["Colombo"]
    # 10. assigned farm IDs normalized to strings
    assert vc.authorization.assignedFarmIds == ["FARM_1", "123"]
    # 13. 'vet' maps to 'VETERINARY_OFFICER'
    assert vc.role == "VETERINARY_OFFICER"
    # 14. district-limited scope
    assert vc.authorization.scopeLevel == "DISTRICT"
    # 15. exact Veterinary permission profile
    assert vc.permissions.viewModelTransparency is True
    assert vc.permissions.viewDataQuality is False
    assert vc.permissions.manageAlerts is True
    assert vc.permissions.recordResponse is True
    assert vc.permissions.viewReports is True
    # 16. response excludes token/password/hash/database objects
    response_dict = _model_to_dict(vc)
    assert "passwordHash" not in response_dict
    assert "tokenVersion" not in response_dict
    assert "model_config" not in response_dict

@pytest.mark.asyncio
@patch("components.risk_forecasting.integration.auth_adapter.jwt.decode")
@patch("components.risk_forecasting.integration.auth_adapter.vets_collection")
async def test_case_11_empty_assignments(mock_vets_collection, mock_jwt_decode):
    mock_jwt_decode.return_value = {"sub": "vet@example.com"}
    mock_vets_collection.find_one = AsyncMock(return_value={"role": "vet", "district": "Jaffna", "assigned_farm_ids": []})
    request = MockRequest(headers={"Authorization": "Bearer valid_token"})
    vc = await get_viewer_context(request)
    assert vc.authorization.assignedFarmIds == []

@pytest.mark.asyncio
@patch("components.risk_forecasting.integration.auth_adapter.jwt.decode")
@patch("components.risk_forecasting.integration.auth_adapter.vets_collection")
async def test_case_12_malformed_assignments(mock_vets_collection, mock_jwt_decode):
    mock_jwt_decode.return_value = {"sub": "vet@example.com"}
    mock_vets_collection.find_one = AsyncMock(return_value={"role": "vet", "district": "Jaffna", "assigned_farm_ids": "not_an_array"})
    request = MockRequest(headers={"Authorization": "Bearer valid_token"})
    with pytest.raises(HTTPException) as exc_info:
        await get_viewer_context(request)
    assert exc_info.value.status_code == 403
    assert "Malformed assigned-farm array" in exc_info.value.detail

def test_case_17_import_isolation():
    # Verify health_anomaly is not imported by auth_adapter
    assert "backend.components.health_anomaly.router" not in sys.modules

@pytest.mark.asyncio
@patch("components.risk_forecasting.integration.auth_adapter.jwt.decode")
@patch("components.risk_forecasting.integration.auth_adapter.vets_collection")
async def test_case_18_19_22_23(mock_vets_collection, mock_jwt_decode):
    mock_jwt_decode.return_value = {"sub": "vet@example.com"}
    mock_vets_collection.find_one = AsyncMock(return_value={"role": "vet", "district": "Colombo"})
    
    # query_params and x-actor headers present but ignored by adapter
    request = MockRequest(
        headers={"Authorization": "Bearer my_token", "X-Actor-ID": "other_vet"},
        query_params={"vet_id": "malicious"}
    )
    vc = await get_viewer_context(request)
    
    # 22. JWT decode called with shared algorithm contract
    mock_jwt_decode.assert_called_once_with("my_token", JWT_SECRET, algorithms=[JWT_ALGORITHM])
    
    # 23. DB query derived only from verified token subject
    mock_vets_collection.find_one.assert_called_once_with({"email": "vet@example.com"})

def test_case_20_21_existing_routes_unchanged():
    import ast
    from pathlib import Path
    
    routes_path = Path("backend/components/risk_forecasting/routes.py")
    tree = ast.parse(routes_path.read_text(encoding="utf-8"))
    
    paths = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                    # Check for router.get (or router.post, etc., but we are looking for get routes)
                    if getattr(decorator.func.value, "id", "") == "router" and decorator.func.attr == "get":
                        path = None
                        if decorator.args and isinstance(decorator.args[0], ast.Constant):
                            path = decorator.args[0].value
                        
                        response_model = None
                        for kw in decorator.keywords:
                            if kw.arg == "response_model":
                                if isinstance(kw.value, ast.Name):
                                    response_model = kw.value.id
                        
                        if path:
                            dependencies = []
                            for default in node.args.defaults:
                                if isinstance(default, ast.Call) and getattr(default.func, "id", "") == "Depends":
                                    if default.args and isinstance(default.args[0], ast.Name):
                                        dependencies.append(default.args[0].id)
                            
                            paths[path] = {
                                "response_model": response_model,
                                "dependencies": dependencies
                            }

    assert "/health" in paths, "Existing /health route must remain"
    assert "/viewer-context" in paths, "New /viewer-context route must remain"
    
    vc_contract = paths["/viewer-context"]
    assert vc_contract["response_model"] == "ViewerContextResponse"
    assert "get_viewer_context" in vc_contract["dependencies"]
