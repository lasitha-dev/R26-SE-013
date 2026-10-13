"""GEO-INT-02 Section 11/12: secure router factory for the future
operational-context endpoint.

`create_operational_context_router` is the ONLY way to obtain this router
-- there is no module-level `router` instance (contrast with `router.py`'s
`router = APIRouter(prefix="/api/geospatial", ...)`, deliberate here:
Section 13 requires this NOT be importable-and-already-wired). Both
dependencies are REQUIRED constructor arguments with no default, so it is
structurally impossible to obtain a working router without the host
application supplying its own real authenticated-identity dependency --
there is no anonymous fallback, no fake user, no hard-coded vet anywhere
in this module (Section 11/12).

This module is built, tested, and NOT mounted (Section 13): nothing here
is imported by `api/router.py` or `main.py`. A later host-composition
checkpoint calls `create_operational_context_router(...)` with the host's
real auth dependency and Mongo-backed
`repositories.host_operational_adapter.MongoOperationalDataPort` and
`app.include_router()`s the result -- not this checkpoint.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from ..domain.operational_enums import OperationalStatus
from ..domain.operational_models import AuthenticatedVetContext, OperationalGeospatialContext
from ..repositories.operational_port import OperationalDataPort
from ..services.operational.context_service import OperationalContextService

OPERATIONAL_CONTEXT_ROUTE_PATH = "/operational-context"
"""Mounted under the existing `/api/geospatial` prefix (matches
`router.py`'s `APIRouter(prefix="/api/geospatial", ...)` convention) --
full path `/api/geospatial/operational-context`."""

_OPERATIONAL_DATA_UNAVAILABLE_HTTP_STATUS = 409
"""Matches this component's existing convention for an "*_UNAVAILABLE"
status (see `services/application/frozen_geospatial_analysis_10a.py`'s
`ERROR_HTTP_STATUS_MAP_10A2[ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY_10A]
== 409`) rather than inventing a new convention for this endpoint."""


def create_operational_context_router(
    *,
    get_authenticated_vet_context: Callable[..., AuthenticatedVetContext | None],
    get_operational_data_port: Callable[..., OperationalDataPort],
) -> APIRouter:
    """Builds the operational-context router. Both parameters are FastAPI
    dependency callables supplied by the HOST application (Section 11):

    - `get_authenticated_vet_context`: resolves the caller's already-
      verified identity (however the host does that -- JWT header, cookie
      session, etc.) and returns `AuthenticatedVetContext | None`. This
      component never parses a token itself (Section 4/11).
    - `get_operational_data_port`: yields a concrete `OperationalDataPort`
      (e.g. `repositories.host_operational_adapter.MongoOperationalDataPort`
      wired to the host's real collections). Not constructed here.

    Neither parameter has a default -- calling this factory with no
    arguments is a `TypeError`, not a router with an insecure fallback.
    """

    router = APIRouter(prefix="/api/geospatial", tags=["geospatial-operational"])

    @router.get(OPERATIONAL_CONTEXT_ROUTE_PATH)
    async def get_operational_context(
        vet: AuthenticatedVetContext | None = Depends(get_authenticated_vet_context),
        port: OperationalDataPort = Depends(get_operational_data_port),
    ) -> dict:
        if vet is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if not vet.is_vet():
            raise HTTPException(status_code=403, detail="Veterinarian account required.")

        context: OperationalGeospatialContext = await OperationalContextService(port).get_operational_context(vet)

        if context.status == OperationalStatus.OPERATIONAL_DATA_UNAVAILABLE.value:
            # Section 12: never leak the underlying host/DB exception --
            # OperationalContextService already caught it and mapped it to
            # this status; only that status (not the raw error) reaches here.
            raise HTTPException(
                status_code=_OPERATIONAL_DATA_UNAVAILABLE_HTTP_STATUS,
                detail="Operational data source unavailable.",
            )

        return asdict(context)

    return router
