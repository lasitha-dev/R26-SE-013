"""GEO-INT-02 Section 16: `create_operational_context_router` tests via
FastAPI's `TestClient` against a throwaway `FastAPI()` app built only for
this test module (never `main.py`/`api/router.py` — Section 13: this
router is not globally mounted). Injected fake dependencies only; no real
Mongo, no network."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api.operational_router_factory import create_operational_context_router
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext, HostDiagnosticCase, HostFarmRecord

from ._operational_fakes import FakeOperationalDataPort

_VET = AuthenticatedVetContext(email="vet@example.com", role="vet")
_NON_VET = AuthenticatedVetContext(email="farm@example.com", role="farm")


def _build_client(*, vet: AuthenticatedVetContext | None, port: FakeOperationalDataPort) -> TestClient:
    def get_authenticated_vet_context() -> AuthenticatedVetContext | None:
        return vet

    def get_operational_data_port() -> FakeOperationalDataPort:
        return port

    router = create_operational_context_router(
        get_authenticated_vet_context=get_authenticated_vet_context,
        get_operational_data_port=get_operational_data_port,
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestAuthenticationAndAuthorization:
    def test_missing_authenticated_context_returns_401(self):
        client = _build_client(vet=None, port=FakeOperationalDataPort())
        response = client.get("/api/geospatial/operational-context")
        assert response.status_code == 401

    def test_non_vet_returns_403(self):
        client = _build_client(vet=_NON_VET, port=FakeOperationalDataPort())
        response = client.get("/api/geospatial/operational-context")
        assert response.status_code == 403

    def test_valid_vet_returns_200(self):
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
        client = _build_client(vet=_VET, port=port)
        response = client.get("/api/geospatial/operational-context")
        assert response.status_code == 200


class TestResponseContent:
    def _qualifying_port(self) -> FakeOperationalDataPort:
        return FakeOperationalDataPort(
            farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)],
            cases=[
                HostDiagnosticCase(
                    case_id="C1",
                    farm_id="F1",
                    disease_name="Lumpy Skin Disease",
                    verified=True,
                    created_at="2026-01-01 09:00:00",
                    verified_at="2026-01-02 10:00:00",
                )
            ],
        )

    def test_response_contains_only_authorized_farms(self):
        port = FakeOperationalDataPort(
            farms=[
                HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8),
                HostFarmRecord(farm_id="F2", latitude=7.0, longitude=80.0),
            ]
        )
        client = _build_client(vet=_VET, port=port)
        body = client.get("/api/geospatial/operational-context").json()
        assert {f["farm_id"] for f in body["farms"]} == {"F1", "F2"}

    def test_unverified_cases_absent(self):
        port = FakeOperationalDataPort(
            farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)],
            cases=[HostDiagnosticCase(case_id="C1", farm_id="F1", disease_name="Lumpy Skin Disease", verified=False)],
        )
        client = _build_client(vet=_VET, port=port)
        body = client.get("/api/geospatial/operational-context").json()
        assert body["clinical_contexts"] == []

    def test_unrelated_farm_cases_absent(self):
        port = FakeOperationalDataPort(
            farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)],
            cases=[
                HostDiagnosticCase(
                    case_id="C1",
                    farm_id="F-NOT-ASSIGNED",
                    disease_name="Lumpy Skin Disease",
                    verified=True,
                    verified_at="2026-01-02 10:00:00",
                )
            ],
        )
        client = _build_client(vet=_VET, port=port)
        body = client.get("/api/geospatial/operational-context").json()
        assert body["clinical_contexts"] == []

    def test_semantic_class_is_verified_clinical_context(self):
        client = _build_client(vet=_VET, port=self._qualifying_port())
        body = client.get("/api/geospatial/operational-context").json()
        assert body["clinical_contexts"][0]["semantic_class"] == "VERIFIED_CLINICAL_CONTEXT"

    def test_no_confirmed_outbreak_wording_anywhere_in_response(self):
        client = _build_client(vet=_VET, port=self._qualifying_port())
        raw_text = client.get("/api/geospatial/operational-context").text
        assert "CONFIRMED_OUTBREAK" not in raw_text
        assert "Confirmed Outbreak" not in raw_text
        assert "outbreak" not in raw_text.lower()

    def test_verification_timestamp_semantics_preserved(self):
        client = _build_client(vet=_VET, port=self._qualifying_port())
        body = client.get("/api/geospatial/operational-context").json()
        clinical = body["clinical_contexts"][0]
        assert clinical["timestamp_basis"] == "VERIFICATION_TIME"
        assert clinical["verification_time"] == "2026-01-02 10:00:00"


class TestErrorHandlingDoesNotLeakDetails:
    def test_host_port_failure_does_not_leak_stack_or_database_details(self):
        port = FakeOperationalDataPort(raise_on_farms=True)
        client = _build_client(vet=_VET, port=port)
        response = client.get("/api/geospatial/operational-context")
        assert response.status_code == 409
        body_text = response.text
        assert "RuntimeError" not in body_text
        assert "Traceback" not in body_text
        assert "simulated host data source outage" not in body_text
