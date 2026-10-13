"""Endpoint tests for the v2 API.

NOT in the safe-execution allowlist: importing `routes` loads core.database (reads backend/.env and
builds a lazy Motor client). Run only in an environment where that is acceptable. The service logic
these endpoints delegate to is covered by test_v2_service.py (pure)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.risk_forecasting.repositories.forecast_record_repository import InMemoryForecastRecordRepository
from components.risk_forecasting.tests.test_v2_service import make_service, old_record

URL = "/api/v1/risk-forecasting/v2/forecasts/generate"


def _app(role, repo=None):
    from components.risk_forecasting import routes
    from components.risk_forecasting.integration.auth_adapter import (
        ViewerContextAuthorization, ViewerContextPermissions, ViewerContextResponse, get_viewer_context,
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1/risk-forecasting")
    viewer = ViewerContextResponse(
        userId="u1", role=role,
        authorization=ViewerContextAuthorization(scopeLevel="NATIONAL", authorizedDistricts=["Colombo"], assignedFarmIds=[]),
        permissions=ViewerContextPermissions(viewDataQuality=True, viewModelTransparency=True, manageAlerts=False,
                                             recordResponse=False, viewReports=False))
    app.dependency_overrides[get_viewer_context] = lambda: viewer
    service = make_service(repo or InMemoryForecastRecordRepository())
    app.dependency_overrides[routes.get_forecast_v2_service] = lambda: service
    return TestClient(app)


def test_generate_endpoint_requires_daph():
    response = _app("VETERINARY_OFFICER").post(URL, json={"year": 2026, "month": 10, "dry_run": True})
    assert response.status_code == 403


def test_generate_endpoint_dry_run_for_daph():
    response = _app("DAPH_OFFICIAL").post(URL, json={"year": 2026, "month": 10, "diseases": ["LSD"], "dry_run": True})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["records"] == 25 and body["summary"]["dry_run"] is True
    assert body["summary"]["status"] == "PREVIEW"
    assert body["records"][0]["generated_by"] == "u1"


def test_real_run_that_would_supersede_needs_the_previewed_count():
    repo = InMemoryForecastRecordRepository()
    repo.save(old_record("fdr_v1_old"))
    client = _app("DAPH_OFFICIAL", repo)
    body = {"year": 2026, "month": 10, "diseases": ["FMD"]}

    missing = client.post(URL, json=body)
    assert missing.status_code == 400 and "preview" in missing.json()["detail"].lower()
    stale = client.post(URL, json={**body, "expected_supersede_count": 9})
    assert stale.status_code == 409
    assert repo.list(limit=200)[1] == 1  # neither attempt wrote anything

    ok = client.post(URL, json={**body, "expected_supersede_count": 1})
    assert ok.status_code == 200 and ok.json()["summary"]["superseded"] == 1


def test_model_card_endpoint():
    response = _app("DAPH_OFFICIAL").get("/api/v1/risk-forecasting/v2/model-card")
    assert response.status_code == 200
    card = response.json()
    assert card["FMD"]["deployment"]["surveillance_known"]["status"] == "back_tested"
    assert card["LSD"]["deployment"]["surveillance_known"]["status"] == "exploratory"
