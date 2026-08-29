"""GEO-ANALYSIS-01 Section 35/37: `create_analysis_trends_router`
HTTP-boundary tests via FastAPI's `TestClient` against a throwaway
`FastAPI()` app built only for this test module -- never `main.py`
(Section 26/29: this router is not globally mounted). Injected fake
dependencies only; no real Mongo/SQLite, no network.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api.analysis_trends_router_factory import create_analysis_trends_router
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext

from ._my_area_fakes import FakeScientificReadPort, make_historical_trigger_candidate

_VET = AuthenticatedVetContext(email="vet@example.com", role="vet")
_NON_VET = AuthenticatedVetContext(email="farm@example.com", role="farm")


def _build_client(*, vet, scientific_port=None) -> TestClient:
    def get_vet():
        return vet

    def get_sci():
        return scientific_port or FakeScientificReadPort()

    router = create_analysis_trends_router(get_authenticated_vet_context=get_vet, get_scientific_read_port=get_sci)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestAuthentication:
    def test_missing_authenticated_context_returns_401(self):
        client = _build_client(vet=None)
        response = client.get("/api/geospatial/analysis-trends", params={"disease": "lsd"})
        assert response.status_code == 401

    def test_non_vet_returns_403(self):
        client = _build_client(vet=_NON_VET)
        response = client.get("/api/geospatial/analysis-trends", params={"disease": "lsd"})
        assert response.status_code == 403

    def test_valid_vet_plus_lsd_returns_structured_200_response(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        client = _build_client(vet=_VET, scientific_port=port)
        response = client.get("/api/geospatial/analysis-trends", params={"disease": "lsd"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("OK", "PARTIAL", "NO_HISTORICAL_DATA")
        assert body["disease"] == "LSD"
        assert "historical_summary" in body
        assert "historical_trend" in body
        assert "model_evaluation" in body


class TestStatusMapping:
    def test_missing_disease_query_parameter_returns_422(self):
        client = _build_client(vet=_VET)
        response = client.get("/api/geospatial/analysis-trends")
        assert response.status_code == 422

    def test_unsupported_disease_handled_cleanly(self):
        client = _build_client(vet=_VET)
        response = client.get("/api/geospatial/analysis-trends", params={"disease": "rabies"})
        assert response.status_code == 422
        assert response.json()["detail"]["status"] == "UNSUPPORTED_DISEASE"

    def test_blank_disease_rejected(self):
        client = _build_client(vet=_VET)
        response = client.get("/api/geospatial/analysis-trends", params={"disease": ""})
        assert response.status_code == 422

    def test_origin_not_found_handled_safely(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[])
        client = _build_client(vet=_VET, scientific_port=port)
        response = client.get("/api/geospatial/analysis-trends", params={"disease": "lsd", "origin_id": "ORIGIN:GHOST:1999-01-01"})
        assert response.status_code == 404
        assert response.json()["detail"]["status"] == "ORIGIN_NOT_FOUND"

    def test_no_historical_data_still_returns_200_with_status_in_body(self):
        port = FakeScientificReadPort(historical_candidates=[], origins=[])
        client = _build_client(vet=_VET, scientific_port=port)
        response = client.get("/api/geospatial/analysis-trends", params={"disease": "lsd"})
        assert response.status_code == 200
        assert response.json()["status"] == "NO_HISTORICAL_DATA"

    def test_fmd_partial_response_correct(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate(disease="Foot and mouth disease")], origins=[])
        client = _build_client(vet=_VET, scientific_port=port)
        response = client.get("/api/geospatial/analysis-trends", params={"disease": "fmd", "origin_id": "ORIGIN:X:2020-01-01"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "PARTIAL"
        assert body["historical_summary"]["status"] == "AVAILABLE"
        assert body["selected_origin_analytics"]["status"] == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"

    def test_response_never_leaks_raw_exception_text(self):
        port = FakeScientificReadPort(raise_on_historical_candidates=RuntimeError("boom traceback secret"))
        client = _build_client(vet=_VET, scientific_port=port)
        response = client.get("/api/geospatial/analysis-trends", params={"disease": "lsd"})
        assert response.status_code == 500
        assert "boom traceback secret" not in response.text
        assert "RuntimeError" not in response.text
        assert "Traceback" not in response.text


class TestRequestParameters:
    def test_no_vet_id_or_email_or_role_accepted_as_query_params(self):
        import inspect

        from components.geospatial_tracking.api import analysis_trends_router_factory

        source = inspect.getsource(analysis_trends_router_factory)
        assert "vet_id" not in source
        assert "vet_email" not in source
        assert "role: " not in source

    def test_disease_query_parameter_is_required_no_default(self):
        import inspect

        from components.geospatial_tracking.api import analysis_trends_router_factory

        source = inspect.getsource(analysis_trends_router_factory.create_analysis_trends_router)
        assert "disease: str = Query(...," in source

    def test_no_farm_id_or_coordinate_query_parameter(self):
        import inspect

        from components.geospatial_tracking.api import analysis_trends_router_factory

        source = inspect.getsource(analysis_trends_router_factory.create_analysis_trends_router)
        assert "farm_id" not in source
        assert "latitude" not in source
        assert "longitude" not in source


class TestCountryScopeInResponse:
    """GEO-ANALYSIS-01H Section 18/21-23."""

    def test_response_explicitly_states_sri_lanka_scope(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        client = _build_client(vet=_VET, scientific_port=port)
        response = client.get("/api/geospatial/analysis-trends", params={"disease": "lsd"})
        assert response.json()["scope_country"] == "Sri Lanka"

    def test_client_supplied_country_query_parameter_is_ignored_not_honored(self):
        # FastAPI silently drops unknown query params -- this proves the
        # route accepts no `country` parameter to even read from, so a
        # client cannot influence scope by trying to supply one.
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        client = _build_client(vet=_VET, scientific_port=port)
        response = client.get("/api/geospatial/analysis-trends", params={"disease": "lsd", "country": "Afghanistan"})
        assert response.status_code == 200
        assert response.json()["scope_country"] == "Sri Lanka"
        assert port.historical_candidates_calls[0]["country"] == "Sri Lanka"

    def test_router_signature_declares_no_country_query_parameter(self):
        import inspect

        from components.geospatial_tracking.api import analysis_trends_router_factory

        source = inspect.getsource(analysis_trends_router_factory.create_analysis_trends_router)
        assert "country: " not in source
        assert "country = Query" not in source
        assert "country: str" not in source


class TestNotGloballyMounted:
    def test_main_module_never_imports_the_analysis_trends_router_factory(self):
        import pathlib

        # tests/ -> geospatial_tracking/ -> components/ -> backend/
        main_path = pathlib.Path(__file__).resolve().parents[3] / "main.py"
        assert main_path.is_file(), f"expected {main_path} to exist"
        source = main_path.read_text(encoding="utf-8")
        assert "analysis_trends_router_factory" not in source
        assert "create_analysis_trends_router" not in source
