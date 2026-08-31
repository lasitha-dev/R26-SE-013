"""GEO-ANALYSIS-01 Section 26: secure router factory for the future
Page-3 "Analysis & Trends" endpoint. Mirrors `my_area_router_factory.py`'s
exact convention (no module-level `router` instance, dependency REQUIRED
with no default, never mounted here) -- but needs no
`OperationalDataPort` at all (Section 27: no farm identity, no vet-owned
data; this is disease/origin-scoped national analysis, not a
farm-authorization boundary), so auth here is a simple 401/403 gate
performed directly in the route, never delegated to a service that also
has to re-check it.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from ..domain.analysis_trends_models import AnalysisTrendsContext
from ..domain.analysis_trends_enums import AnalysisTrendsStatus
from ..domain.operational_models import AuthenticatedVetContext
from ..repositories.scientific_read_port import ScientificReadPort
from ..services.analysis_trends.context_service import AnalysisTrendsService

ANALYSIS_TRENDS_ROUTE_PATH = "/analysis-trends"
"""Mounted under the existing `/api/geospatial` prefix -- full path
`/api/geospatial/analysis-trends`."""

# Section 29: statuses that mean "the request never reached a usable
# result" get their own HTTP code; everything else (including PARTIAL
# and NO_HISTORICAL_DATA) is a normal 200 body -- honest, expected DATA
# states, not transport errors (mirrors `my_area_router_factory.py`'s
# own split).
_HTTP_STATUS_BY_ANALYSIS_TRENDS_STATUS = {
    AnalysisTrendsStatus.UNSUPPORTED_DISEASE.value: 422,
    AnalysisTrendsStatus.ORIGIN_NOT_FOUND.value: 404,
    AnalysisTrendsStatus.ANALYSIS_INTERNAL_ERROR.value: 500,
}


def create_analysis_trends_router(
    *,
    get_authenticated_vet_context: Callable[..., AuthenticatedVetContext | None],
    get_scientific_read_port: Callable[..., ScientificReadPort],
) -> APIRouter:
    """The SAME host-supplied `get_authenticated_vet_context` shape
    `operational_router_factory`/`my_area_router_factory` already require
    (no second JWT wiring). No default value on either parameter --
    calling this factory with either omitted is a `TypeError`, never a
    router with an insecure fallback."""

    router = APIRouter(prefix="/api/geospatial", tags=["geospatial-analysis-trends"])

    @router.get(ANALYSIS_TRENDS_ROUTE_PATH)
    def get_analysis_trends(
        # Section 8: REQUIRED, exactly like My Area -- a missing/blank
        # value is a client error (422), never a silent LSD default.
        # `services/disease.py` and the other pre-existing routes
        # (`/origins`, `/analysis/*`) are untouched.
        disease: str = Query(..., description="Required disease selector (e.g. 'lsd', 'fmd', or a canonical name) -- never omitted, never defaulted to Lumpy skin disease."),
        origin_id: str | None = Query(default=None, description="Optional real forecast_origin_id. Omitted -> national/disease-level analytics only; never auto-selected."),
        vet: AuthenticatedVetContext | None = Depends(get_authenticated_vet_context),
        scientific_port: ScientificReadPort = Depends(get_scientific_read_port),
    ) -> dict:
        if vet is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if not vet.is_vet():
            raise HTTPException(status_code=403, detail="Veterinarian account required.")

        context: AnalysisTrendsContext = AnalysisTrendsService(scientific_port).get_analysis_trends(disease=disease, origin_id=origin_id)

        http_status = _HTTP_STATUS_BY_ANALYSIS_TRENDS_STATUS.get(context.status)
        if http_status is not None:
            # Never leak the underlying exception -- the service already
            # reduced it to one of AnalysisTrendsStatus's values; only
            # that status crosses here.
            raise HTTPException(status_code=http_status, detail={"status": context.status})

        return asdict(context)

    return router
