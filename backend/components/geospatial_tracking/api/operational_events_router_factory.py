"""GEO-LIVE-05 Section 8: secure router factory for the future operational-
EVENTS endpoint (an authenticated server-sent-event stream), separate from
GEO-INT-02's operational-CONTEXT polling endpoint and from `router.py`'s
retrospective-snapshot `/api/geospatial/ws` WebSocket (Section 3: this
never reuses or overloads that historical protocol).

Same discipline as `operational_router_factory.py`: `create_operational_events_router`
is the ONLY way to obtain this router -- no module-level `router` instance,
both dependencies are REQUIRED constructor arguments with no default. This
module is built, tested, and NOT mounted (nothing here is imported by
`api/router.py` or `main.py`) -- a later host-composition checkpoint wires
a real auth dependency, a real `MongoOperationalDataPort`, and a real
`CaseEventSource` (Section 4/8) and `app.include_router()`s the result.

Transport (Section 8): a plain authenticated `fetch`-based SSE stream --
the browser can attach `Authorization: Bearer <token>` to a `fetch` the
same way it already does for `operationalApi.js`/`myAreaApi.js`, which a
plain `EventSource` cannot do (no custom-header support). `text/event-
stream` framing (`event: ...\\ndata: ...\\n\\n`) is emitted manually so no
new dependency is required.
"""

from __future__ import annotations

import asyncio
import json
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..domain.operational_events import VerifiedClinicalEvent
from ..domain.operational_models import AuthenticatedVetContext
from ..services.operational.event_stream_service import OperationalEventStreamService

OPERATIONAL_EVENTS_ROUTE_PATH = "/operational-events/stream"
"""Full path `/api/geospatial/operational-events/stream` -- a distinct
sub-path from `/operational-context` (GEO-INT-02) and from `/ws`
(`router.py`'s historical snapshot transport, Section 3)."""

_HEARTBEAT_INTERVAL_SECONDS = 15.0
"""Section 8 "heartbeat/keepalive aware": an idle connection still emits a
`event: heartbeat` frame on this cadence so an intermediary proxy never
times out an apparently-silent connection, and so the frontend can detect
a genuinely stalled connection (no bytes at all) apart from "no new
clinical events right now" (Section 9 `stale/fallback` state)."""


def _format_sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def create_operational_events_router(
    *,
    get_authenticated_vet_context: Callable[..., AuthenticatedVetContext | None],
    get_event_stream_service: Callable[..., OperationalEventStreamService],
    heartbeat_interval_seconds: float = _HEARTBEAT_INTERVAL_SECONDS,
) -> APIRouter:
    """Builds the operational-events SSE router. Both parameters are
    FastAPI dependency callables supplied by the HOST application:

    - `get_authenticated_vet_context`: identical contract to
      `operational_router_factory.create_operational_context_router`'s
      same-named parameter -- this component never parses a token itself.
    - `get_event_stream_service`: yields a constructed
      `OperationalEventStreamService` (wired to the host's real
      `MongoOperationalDataPort` and whichever `CaseEventSource` the host
      has decided to use -- Section 4/16 of this checkpoint's report).

    Neither parameter has a default -- calling this factory with no
    arguments is a `TypeError`, not a router with an insecure fallback.
    """

    router = APIRouter(prefix="/api/geospatial", tags=["geospatial-operational-events"])

    @router.get(OPERATIONAL_EVENTS_ROUTE_PATH)
    async def stream_operational_events(
        request: Request,
        vet: AuthenticatedVetContext | None = Depends(get_authenticated_vet_context),
        service: OperationalEventStreamService = Depends(get_event_stream_service),
    ) -> StreamingResponse:
        if vet is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if not vet.is_vet():
            raise HTTPException(status_code=403, detail="Veterinarian account required.")

        async def event_generator():
            # Section 9: told to the frontend up front so it never shows
            # "LIVE" wording while this connection is actually running on
            # the honest delta-refresh fallback (Section 4).
            yield _format_sse("ready", {"transport": service.transport_mode()})

            events = service.stream_events(vet)
            try:
                while True:
                    try:
                        event: VerifiedClinicalEvent = await asyncio.wait_for(
                            events.__anext__(), timeout=heartbeat_interval_seconds
                        )
                    except asyncio.TimeoutError:
                        if await request.is_disconnected():
                            break
                        yield _format_sse("heartbeat", {})
                        continue
                    except StopAsyncIteration:
                        break
                    if await request.is_disconnected():
                        break
                    yield _format_sse("clinical_event", event.as_dict())
            finally:
                # Section 8 disconnect cleanup: closes the underlying
                # service/source subscription (unregisters this
                # connection's queue) rather than leaving it registered
                # after the HTTP response ends.
                await events.aclose()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
