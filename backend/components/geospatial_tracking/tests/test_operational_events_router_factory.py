"""GEO-LIVE-05 Section 15: `create_operational_events_router` tests via
FastAPI's `TestClient` against a throwaway `FastAPI()` app (never
`main.py`/`api/router.py` -- this router is not globally mounted). Injected
fake dependencies only; no real Mongo, no network, no real waiting (the
fake service's stream is always finite so the SSE response terminates on
its own)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api.operational_events_router_factory import create_operational_events_router
from components.geospatial_tracking.domain.operational_events import VerifiedClinicalEvent
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext

_VET = AuthenticatedVetContext(email="vet@example.com", role="vet")
_NON_VET = AuthenticatedVetContext(email="farm@example.com", role="farm")

_EVENT = VerifiedClinicalEvent(
    event_id="vcc:C1:2026-01-02 10:00:00",
    event_type="VERIFIED_CLINICAL_CONTEXT_CREATED",
    case_id="C1",
    farm_id="F1",
    disease="LSD",
    verified_at="2026-01-02 10:00:00",
    event_generated_at="2026-01-02 10:00:01+00:00",
    deep_link_context={"target": "geospatial_clinical_case", "case_id": "C1", "farm_id": "F1", "disease": "LSD"},
)


class _FiniteFakeService:
    """A `stream_events(vet)` that yields a fixed, finite list of events
    then stops -- so the SSE response completes on its own without needing
    a real disconnect/timeout, keeping these tests instant."""

    def __init__(self, events: list[VerifiedClinicalEvent], *, transport: str = "push") -> None:
        self._events = events
        self._transport = transport
        self.stream_calls: list[AuthenticatedVetContext] = []

    def transport_mode(self) -> str:
        return self._transport

    async def stream_events(self, vet: AuthenticatedVetContext):
        self.stream_calls.append(vet)
        for event in self._events:
            yield event


def _build_client(*, vet: AuthenticatedVetContext | None, service: _FiniteFakeService) -> TestClient:
    def get_authenticated_vet_context() -> AuthenticatedVetContext | None:
        return vet

    def get_event_stream_service() -> _FiniteFakeService:
        return service

    router = create_operational_events_router(
        get_authenticated_vet_context=get_authenticated_vet_context,
        get_event_stream_service=get_event_stream_service,
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestAuthenticationAndAuthorization:
    def test_missing_authenticated_context_returns_401(self):
        client = _build_client(vet=None, service=_FiniteFakeService([]))
        response = client.get("/api/geospatial/operational-events/stream")
        assert response.status_code == 401

    def test_non_vet_returns_403(self):
        client = _build_client(vet=_NON_VET, service=_FiniteFakeService([]))
        response = client.get("/api/geospatial/operational-events/stream")
        assert response.status_code == 403

    def test_valid_vet_returns_200_and_sse_content_type(self):
        client = _build_client(vet=_VET, service=_FiniteFakeService([]))
        response = client.get("/api/geospatial/operational-events/stream")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")


class TestStreamContent:
    def test_ready_frame_reports_the_real_transport_mode_push(self):
        client = _build_client(vet=_VET, service=_FiniteFakeService([], transport="push"))
        body = client.get("/api/geospatial/operational-events/stream").text
        assert "event: ready" in body
        assert '"transport": "push"' in body

    def test_ready_frame_reports_the_real_transport_mode_delta_refresh(self):
        """Section 4/9: the frame the frontend uses to decide whether
        showing "LIVE" wording would be honest -- never hardcoded to
        "push" regardless of what the service actually reports."""
        client = _build_client(vet=_VET, service=_FiniteFakeService([], transport="delta_refresh"))
        body = client.get("/api/geospatial/operational-events/stream").text
        assert '"transport": "delta_refresh"' in body

    def test_a_delivered_event_appears_as_a_clinical_event_frame(self):
        client = _build_client(vet=_VET, service=_FiniteFakeService([_EVENT]))
        body = client.get("/api/geospatial/operational-events/stream").text
        assert "event: clinical_event" in body
        assert '"case_id": "C1"' in body
        assert '"event_id": "vcc:C1:2026-01-02 10:00:00"' in body

    def test_no_confirmed_outbreak_wording_anywhere_in_the_stream(self):
        client = _build_client(vet=_VET, service=_FiniteFakeService([_EVENT]))
        body = client.get("/api/geospatial/operational-events/stream").text
        assert "CONFIRMED_OUTBREAK" not in body
        assert "outbreak" not in body.lower()

    def test_the_vets_authenticated_identity_is_the_only_thing_passed_to_the_service(self):
        service = _FiniteFakeService([])
        client = _build_client(vet=_VET, service=service)
        client.get("/api/geospatial/operational-events/stream")
        assert service.stream_calls == [_VET]
