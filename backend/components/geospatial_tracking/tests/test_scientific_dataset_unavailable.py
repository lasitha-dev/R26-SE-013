"""An absent or 0-byte development SQLite dataset must surface as an explicit
503 `SCIENTIFIC_DATASET_UNAVAILABLE` -- never a 500, never an empty or
fabricated analysis. The live application reads the scientific dataset
from MongoDB; these tests never touch any real database."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api import router as router_module
from components.geospatial_tracking.api.analysis_trends_router_factory import _HTTP_STATUS_BY_ANALYSIS_TRENDS_STATUS
from components.geospatial_tracking.api.my_area_router_factory import _HTTP_STATUS_BY_MY_AREA_STATUS
from components.geospatial_tracking.domain.analysis_trends_enums import AnalysisTrendsStatus
from components.geospatial_tracking.domain.my_area_enums import MyAreaStatus
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext, HostFarmRecord
from components.geospatial_tracking.repositories import provider
from components.geospatial_tracking.services.analysis_trends.context_service import AnalysisTrendsService
from components.geospatial_tracking.services.my_area.context_service import MyAreaContextService

from ._my_area_fakes import FakeScientificReadPort
from ._operational_fakes import FakeOperationalDataPort

_VET = AuthenticatedVetContext(email="vet@example.com", role="vet")


@pytest.fixture()
def no_dataset_client(monkeypatch, tmp_path):
    empty = tmp_path / "pistes_dev.db"
    empty.write_bytes(b"")
    monkeypatch.setattr(provider, "default_sqlite_db_path", lambda: empty)
    provider.set_repository_factory_override(None)
    router_module.SNAPSHOT_STORE_10B.clear()
    router_module.ORIGIN_LEDGER_STORE_10C.clear()
    app = FastAPI()
    app.include_router(router_module.router)
    yield TestClient(app, raise_server_exceptions=False)
    router_module.SNAPSHOT_STORE_10B.clear()
    router_module.ORIGIN_LEDGER_STORE_10C.clear()


@pytest.mark.parametrize("path", [
    "/api/geospatial/origins?disease=lsd&country=Sri%20Lanka",
    "/api/geospatial/origins/ORIGIN:Sri%20Lanka:2020-09-07/trigger-sources?disease=lsd",
    "/api/geospatial/analysis/ORIGIN:Sri%20Lanka:2020-09-07/summary",
    "/api/geospatial/analysis/ORIGIN:Sri%20Lanka:2020-09-07/cells",
    "/api/geospatial/analysis/ORIGIN:Sri%20Lanka:2020-09-07/sources",
    "/api/geospatial/analysis/not-a-real-origin-id/fmd-risk",
])
def test_scientific_routes_return_503_not_500(no_dataset_client, path):
    response = no_dataset_client.get(path)
    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "SCIENTIFIC_DATASET_UNAVAILABLE"


def test_websocket_snapshot_request_reports_dataset_unavailable(no_dataset_client):
    with no_dataset_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()  # transport_ready
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": "ORIGIN:Sri Lanka:2020-09-07"})
        frame = ws.receive_json()
    assert frame["type"] == "error"
    assert frame["status"] == "SCIENTIFIC_DATASET_UNAVAILABLE"


def test_my_area_maps_missing_dataset_to_its_own_status():
    port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=5.95, longitude=80.54)])
    science = FakeScientificReadPort(raise_on_list_origins=provider.ScientificDatasetUnavailableError("no dataset"))
    result = asyncio.run(MyAreaContextService(port, science).get_my_area_context(_VET, farm_id="F1", disease="lsd"))
    assert result.status == MyAreaStatus.SCIENTIFIC_DATASET_UNAVAILABLE.value
    assert _HTTP_STATUS_BY_MY_AREA_STATUS[result.status] == 503


def test_my_area_other_scientific_failures_stay_internal_errors():
    port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=5.95, longitude=80.54)])
    science = FakeScientificReadPort(raise_on_list_origins=RuntimeError("unexpected"))
    result = asyncio.run(MyAreaContextService(port, science).get_my_area_context(_VET, farm_id="F1", disease="lsd"))
    assert result.status == MyAreaStatus.ANALYSIS_INTERNAL_ERROR.value


def test_analysis_trends_maps_missing_dataset_to_its_own_status():
    science = FakeScientificReadPort(raise_on_historical_candidates=provider.ScientificDatasetUnavailableError("no dataset"))
    result = AnalysisTrendsService(science).get_analysis_trends(disease="lsd")
    assert result.status == AnalysisTrendsStatus.SCIENTIFIC_DATASET_UNAVAILABLE.value
    assert _HTTP_STATUS_BY_ANALYSIS_TRENDS_STATUS[result.status] == 503
