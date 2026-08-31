"""GEO-AREA-01 Section 23: secure router factory for the future Page-2
"My Area" endpoint. Mirrors `operational_router_factory.py`'s exact
convention (Section 3's "reuse, don't duplicate" applied to this
checkpoint's own prior work): no module-level `router` instance, both
dependencies REQUIRED with no default, never mounted here.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from ..domain.my_area_enums import MyAreaStatus
from ..domain.my_area_models import MyAreaContext
from ..domain.operational_models import AuthenticatedVetContext
from ..repositories.operational_port import OperationalDataPort
from ..repositories.scientific_read_port import ScientificReadPort
from ..services.my_area.context_service import MyAreaContextService

MY_AREA_ROUTE_PATH = "/my-area"
"""Mounted under the existing `/api/geospatial` prefix -- full path
`/api/geospatial/my-area`."""

# Section 25: statuses that mean "the request never reached a usable
# result" get their own HTTP code; every other status (including
# LOCATION_REQUIRED/NO_ASSIGNED_FARMS/NO_RELEVANT_ORIGINS/
# FORECAST_FRAME_UNAVAILABLE) is a normal 200 body -- these are honest,
# expected DATA states, not transport errors (mirrors
# `operational_router_factory.py`'s OPERATIONAL_DATA_UNAVAILABLE -> 409
# convention for exactly the "real failure" vs "real empty state" split).
_HTTP_STATUS_BY_MY_AREA_STATUS = {
    MyAreaStatus.ASSIGNED_AREA_NOT_FOUND.value: 404,
    MyAreaStatus.ORIGIN_NOT_FOUND.value: 404,
    MyAreaStatus.UNSUPPORTED_DISEASE.value: 422,
    MyAreaStatus.ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY.value: 409,
    MyAreaStatus.OPERATIONAL_DATA_UNAVAILABLE.value: 409,
    MyAreaStatus.ANALYSIS_INTERNAL_ERROR.value: 500,
}


def create_my_area_router(
    *,
    get_authenticated_vet_context: Callable[..., AuthenticatedVetContext | None],
    get_operational_data_port: Callable[..., OperationalDataPort],
    get_scientific_read_port: Callable[..., ScientificReadPort],
) -> APIRouter:
    """Both `get_authenticated_vet_context` and `get_operational_data_port`
    are the SAME host-supplied dependency shapes
    `operational_router_factory.create_operational_context_router` already
    requires (Section 4: no second JWT/Mongo wiring). No default value on
    any parameter -- calling this factory with none supplied is a
    `TypeError`, never a router with an insecure fallback."""

    router = APIRouter(prefix="/api/geospatial", tags=["geospatial-my-area"])

    @router.get(MY_AREA_ROUTE_PATH)
    async def get_my_area(
        farm_id: str = Query(..., description="One of the authenticated veterinarian's assigned farm ids -- a SELECTION only, authorization is always re-checked server-side."),
        # GEO-AREA-01H Section 11: REQUIRED, unlike /origins and
        # /analysis/*, which reproduce pre-FMD-02 "omitted -> LSD"
        # behavior for backward compatibility. My Area has no such
        # history to preserve and the frontend always has an explicit
        # selected disease, so a missing value is a client error (422),
        # never a silent LSD default. `services/disease.py` and the
        # other routes are untouched.
        disease: str = Query(..., description="Required disease selector (e.g. 'lsd', 'fmd', or a canonical name) -- never omitted, never defaulted to Lumpy skin disease."),
        origin_id: str | None = Query(default=None, description="Optional real forecast_origin_id. Omitted -> a ranked list of relevant real origins is returned instead of auto-selecting one."),
        day: int = Query(default=0, ge=0, le=7, description="Forecast day 0 (observed/origin context) through 7."),
        vet: AuthenticatedVetContext | None = Depends(get_authenticated_vet_context),
        operational_port: OperationalDataPort = Depends(get_operational_data_port),
        scientific_port: ScientificReadPort = Depends(get_scientific_read_port),
    ) -> dict:
        if vet is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if not vet.is_vet():
            raise HTTPException(status_code=403, detail="Veterinarian account required.")

        context: MyAreaContext = await MyAreaContextService(operational_port, scientific_port).get_my_area_context(
            vet, farm_id=farm_id, disease=disease, origin_id=origin_id, forecast_day=day,
        )

        http_status = _HTTP_STATUS_BY_MY_AREA_STATUS.get(context.status)
        if http_status is not None:
            # Section 25: never leak the underlying exception -- the
            # service already reduced it to one of MyAreaStatus's values;
            # only that status (plus its own non-secret detail) crosses here.
            raise HTTPException(status_code=http_status, detail={"status": context.status})

        return asdict(context)

    return router
