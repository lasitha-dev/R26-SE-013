"""GEO-AREA-01/01H Section 23/25: `create_my_area_router` HTTP-boundary
tests via FastAPI's `TestClient` against a throwaway `FastAPI()` app
built only for this test module -- never `main.py`/`api/router.py`
(Section 23: this router is not globally mounted). Injected fake
dependencies only; no real Mongo/SQLite, no network.

GEO-AREA-01H note: `disease` is now a REQUIRED query parameter (Section
11) -- FastAPI validates required query params before the route body
runs, so every test below that exercises auth/status logic supplies an
explicit `disease` so the request actually reaches that logic; the
dedicated "missing disease" test asserts the 422 short-circuit itself.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api.my_area_router_factory import create_my_area_router
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext, HostFarmRecord

from ._my_area_fakes import FakeScientificReadPort, make_forecast_origin
from ._operational_fakes import FakeOperationalDataPort

_VET = AuthenticatedVetContext(email="vet@example.com", role="vet")
_NON_VET = AuthenticatedVetContext(email="farm@example.com", role="farm")


def _build_client(*, vet, operational_port=None, scientific_port=None) -> TestClient:
    def get_vet():
        return vet

    def get_port():
        return operational_port or FakeOperationalDataPort()

    def get_sci():
        return scientific_port or FakeScientificReadPort()

    router = create_my_area_router(
        get_authenticated_vet_context=get_vet, get_operational_data_port=get_port, get_scientific_read_port=get_sci,
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestAuthentication:
    def test_missing_authenticated_context_returns_401(self):
        client = _build_client(vet=None)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": "lsd"})
        assert response.status_code == 401

    def test_non_vet_returns_403(self):
        client = _build_client(vet=_NON_VET)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": "lsd"})
        assert response.status_code == 403

    def test_valid_vet_with_assigned_farm_returns_200(self):
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
        client = _build_client(vet=_VET, operational_port=port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": "lsd"})
        assert response.status_code == 200


class TestStatusMapping:
    def test_unassigned_farm_returns_404(self):
        # NO_ASSIGNED_FARMS (empty list) is its own honest 200 state
        # (mirrors GEO-INT-01's OperationalStatus precedent) -- this
        # tests ASSIGNED_AREA_NOT_FOUND specifically: the vet HAS an
        # assigned farm, just not the one requested.
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
        client = _build_client(vet=_VET, operational_port=port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F-GHOST", "disease": "lsd"})
        assert response.status_code == 404

    def test_unsupported_disease_returns_422(self):
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
        client = _build_client(vet=_VET, operational_port=port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": "rabies"})
        assert response.status_code == 422

    def test_missing_disease_query_parameter_returns_422(self):
        # GEO-AREA-01H Section 11: disease is required -- omitting it
        # entirely must be a client error, never a silent LSD default.
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
        client = _build_client(vet=_VET, operational_port=port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1"})
        assert response.status_code == 422

    def test_blank_disease_query_parameter_rejected(self):
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
        client = _build_client(vet=_VET, operational_port=port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": ""})
        assert response.status_code in (400, 422)

    def test_day_out_of_range_rejected_by_query_validation(self):
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
        client = _build_client(vet=_VET, operational_port=port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": "lsd", "day": 8})
        assert response.status_code == 422

    def test_negative_day_rejected(self):
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
        client = _build_client(vet=_VET, operational_port=port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": "lsd", "day": -1})
        assert response.status_code == 422

    def test_location_required_still_returns_200_with_status_in_body(self):
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=None, longitude=None)])
        client = _build_client(vet=_VET, operational_port=port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": "lsd"})
        assert response.status_code == 200
        assert response.json()["status"] == "LOCATION_REQUIRED"

    def test_response_never_leaks_raw_exception_text(self):
        port = FakeOperationalDataPort(raise_on_farms=True)
        client = _build_client(vet=_VET, operational_port=port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": "lsd"})
        assert response.status_code == 409
        assert "RuntimeError" not in response.text
        assert "Traceback" not in response.text


class TestResponseSelfDescribing:
    """GEO-AREA-01H Section 13: a frontend developer must be unable to
    mistake nearest-source distance for origin distance, or a nominal-
    reach relation for a containment/infection boundary."""

    def test_no_ambiguous_distance_to_origin_field_in_response_body(self):
        origin_snapshot_port = FakeScientificReadPort()
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
        client = _build_client(vet=_VET, operational_port=port, scientific_port=origin_snapshot_port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": "lsd"})
        assert "distance_to_origin_km" not in response.text
        assert "distance_area_to_origin_km" not in response.text


class TestRequestParameters:
    def test_no_vet_id_or_email_or_role_accepted_as_query_params(self):
        # FastAPI ignores unknown query params by default -- assert the
        # route signature itself never declares them, so no client can
        # ever influence authorization via the query string.
        import inspect

        from components.geospatial_tracking.api import my_area_router_factory

        source = inspect.getsource(my_area_router_factory)
        assert "vet_id" not in source
        assert "vet_email" not in source
        # 'role' only appears in prose/comments about NOT accepting it -- never as a Query(...) parameter name.
        assert "role: " not in source

    def test_disease_query_parameter_is_required_no_default(self):
        import inspect

        from components.geospatial_tracking.api import my_area_router_factory

        source = inspect.getsource(my_area_router_factory.create_my_area_router)
        # The disease Query(...) declaration must use the required-value
        # ellipsis, never `default=None`/`default="lsd"`.
        assert "disease: str = Query(...," in source

    def test_router_signature_declares_no_country_query_parameter(self):
        import inspect

        from components.geospatial_tracking.api import my_area_router_factory

        source = inspect.getsource(my_area_router_factory.create_my_area_router)
        assert "country: " not in source
        assert "country = Query" not in source


class TestCountryScopeIsServerControlled:
    """GEO-AREA-01S Section 19: the browser must not be able to
    influence which real country's origin ledger My Area draws from."""

    def test_client_supplied_country_query_parameter_is_ignored_not_honored(self):
        # FastAPI silently drops unknown query params -- this proves the
        # route accepts no `country` parameter to even read from.
        origin = make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")
        port = FakeScientificReadPort(origins=[origin], trigger_locations_by_origin_id={"ORIGIN:Sri Lanka:2020-09-07": [("S1", 6.93, 79.85)]})
        operational_port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9271, longitude=79.8612)])
        client = _build_client(vet=_VET, operational_port=operational_port, scientific_port=port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": "lsd", "country": "Afghanistan"})
        assert response.status_code == 200
        assert port.list_origins_calls[0]["country"] == "Sri Lanka"
        assert response.json()["relevant_origins"][0]["origin_id"] == "ORIGIN:Sri Lanka:2020-09-07"

    def test_a_real_foreign_origin_id_via_the_router_is_rejected(self):
        origin = make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")
        port = FakeScientificReadPort(origins=[origin])
        operational_port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9271, longitude=79.8612)])
        client = _build_client(vet=_VET, operational_port=operational_port, scientific_port=port)
        response = client.get("/api/geospatial/my-area", params={"farm_id": "F1", "disease": "lsd", "origin_id": "ORIGIN:Afghanistan:2022-05-29"})
        assert response.status_code == 404
        assert response.json()["detail"]["status"] == "ORIGIN_NOT_FOUND"
