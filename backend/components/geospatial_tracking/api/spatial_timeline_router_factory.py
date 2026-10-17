"""`GET /api/geospatial/spatial-timeline` -- day-indexed (D0..D14) relative
spatial risk, nominal reach and geometric direction, built from the frozen
C0 / 8B.3 / 9C models over traceable historical and vet-verified sources.

Veterinarian-only (401 without a session, 403 for non-vet roles) because the
response contains operational source positions (farm GPS). Dependencies are
injected by the host composition root (`backend/main.py`); no parameter has
an insecure default.
"""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ..domain.operational_models import AuthenticatedVetContext
from ..repositories.operational_port import OperationalDataPort
from ..services.spatial_timeline.engine import MAX_HORIZON_DAYS
from ..services.spatial_timeline.service import (
    SPATIAL_TIMELINE_CACHE_TTL_SECONDS,
    SpatialTimelineError,
    SpatialTimelineService,
)
from ..services.spatial_timeline.sources import HistoricalSourceReader
from ..services.transport.snapshot_store_10b import SnapshotStore10B
from fastapi.concurrency import run_in_threadpool

from ..repositories.provider import ScientificDatasetUnavailableError
from ..services.disease import SUPPORTED_DISEASES, UnsupportedDiseaseError, resolve_disease_selection
from datetime import date

from ..services.spatial_timeline.districts import find_district
from ..services.spatial_timeline.environment import environment_at_sources
from ..services.spatial_timeline.clusters import EXPLORATORY_CONFIG, operational_case_points, run_runtime_st_clustering
from ..services.spatial_timeline.service import parse_as_of, today_in_sri_lanka

SPATIAL_TIMELINE_ROUTE_PATH = "/spatial-timeline"
ST_CLUSTERS_ROUTE_PATH = "/st-clusters"
ENVIRONMENT_ROUTE_PATH = "/environment"


def create_spatial_timeline_router(
    *,
    get_authenticated_vet_context: Callable[..., AuthenticatedVetContext | None],
    get_operational_data_port: Callable[..., OperationalDataPort],
    get_historical_source_reader: Callable[..., HistoricalSourceReader],
    snapshot_store: SnapshotStore10B | None = None,
) -> APIRouter:
    # `is None`, not `or`: an empty SnapshotStore10B is falsy (it defines __len__).
    store = snapshot_store if snapshot_store is not None else SnapshotStore10B(ttl_seconds=SPATIAL_TIMELINE_CACHE_TTL_SECONDS)
    router = APIRouter(prefix="/api/geospatial", tags=["geospatial-spatial-timeline"])

    @router.get(SPATIAL_TIMELINE_ROUTE_PATH)
    async def get_spatial_timeline(
        response: Response,
        disease: str = Query(..., description="Required disease selector ('lsd', 'fmd' or a canonical name)."),
        scope: str = Query(default="district", description="'district' (default: the vet's registered district) or 'national'."),
        district: str | None = Query(default=None, description="District name for scope=district; must be within the vet's authorised scope."),
        as_of: str | None = Query(default=None, description="ISO date the source set is fixed at; default today (Asia/Colombo). Never in the future."),
        horizon_days: int = Query(default=MAX_HORIZON_DAYS, ge=0, le=MAX_HORIZON_DAYS, description="Frames D0..horizon_days (max 14; D8-D14 exploratory)."),
        vet: AuthenticatedVetContext | None = Depends(get_authenticated_vet_context),
        operational_port: OperationalDataPort = Depends(get_operational_data_port),
        historical_reader: HistoricalSourceReader = Depends(get_historical_source_reader),
    ) -> dict:
        if vet is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if not vet.is_vet():
            raise HTTPException(status_code=403, detail="Veterinarian account required.")
        service = SpatialTimelineService(operational_port, historical_reader, store)
        try:
            timeline, cache_status = await service.get_timeline(
                vet, disease=disease, scope=scope, district=district, as_of=as_of, horizon_days=horizon_days,
            )
        except SpatialTimelineError as exc:
            raise HTTPException(status_code=exc.http_status, detail={"status": exc.status, "message": str(exc)}) from exc
        except Exception as exc:  # never a raw stack trace or database message to the client
            raise HTTPException(
                status_code=500, detail={"status": "ANALYSIS_INTERNAL_ERROR", "message": "spatial timeline computation failed"},
            ) from exc
        response.headers["X-Spatial-Timeline-Cache"] = cache_status
        response.headers["X-Spatial-Timeline-Snapshot"] = timeline["snapshot_id"]
        return timeline

    @router.get(ENVIRONMENT_ROUTE_PATH)
    async def get_environment(
        disease: str = Query(...),
        scope: str = Query(default="district"),
        district: str | None = Query(default=None),
        as_of: str | None = Query(default=None),
        vet: AuthenticatedVetContext | None = Depends(get_authenticated_vet_context),
        operational_port: OperationalDataPort = Depends(get_operational_data_port),
        historical_reader: HistoricalSourceReader = Depends(get_historical_source_reader),
    ) -> dict:
        """Real ERA5 observations at the SAME eligible sources the spatial timeline uses. Display only."""
        if vet is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if not vet.is_vet():
            raise HTTPException(status_code=403, detail="Veterinarian account required.")
        service = SpatialTimelineService(operational_port, historical_reader, store)
        try:
            timeline, _ = await service.get_timeline(vet, disease=disease, scope=scope, district=district, as_of=as_of, horizon_days=0)
        except SpatialTimelineError as exc:
            raise HTTPException(status_code=exc.http_status, detail={"status": exc.status, "message": str(exc)}) from exc
        reference = None
        if timeline["scope"].get("kind") == "district" and timeline["scope"].get("district"):
            found = find_district(timeline["scope"]["district"])
            if found is not None:
                point = found.geometry.representative_point()  # always inside the district polygon
                reference = (found.name, point.y, point.x)
        result = await run_in_threadpool(lambda: environment_at_sources(timeline["sources"], as_of=date.fromisoformat(timeline["as_of"]), district_reference=reference))
        result["timeline_status"] = timeline["status"]
        result["source_count"] = len(timeline["sources"])
        return result

    @router.get(ST_CLUSTERS_ROUTE_PATH)
    async def get_st_clusters(
        disease: str = Query(..., description="'lsd' or 'fmd'."),
        as_of: str | None = Query(default=None, description="ISO date; default today (Asia/Colombo)."),
        vet: AuthenticatedVetContext | None = Depends(get_authenticated_vet_context),
        operational_port: OperationalDataPort = Depends(get_operational_data_port),
        historical_reader: HistoricalSourceReader = Depends(get_historical_source_reader),
    ) -> dict:
        """EXPLORATORY runtime ST-DBSCAN over real eligible case records (read-only)."""
        if vet is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if not vet.is_vet():
            raise HTTPException(status_code=403, detail="Veterinarian account required.")
        try:
            disease_display = resolve_disease_selection(disease)
        except UnsupportedDiseaseError as exc:
            raise HTTPException(status_code=422, detail={"status": "UNSUPPORTED_DISEASE", "message": str(exc)}) from exc
        try:
            as_of_date = parse_as_of(as_of, today=today_in_sri_lanka())
        except SpatialTimelineError as exc:
            raise HTTPException(status_code=exc.http_status, detail={"status": exc.status, "message": str(exc)}) from exc
        reader = getattr(operational_port, "get_national_case_documents", None)
        if reader is None:
            raise HTTPException(status_code=409, detail={"status": "NATIONAL_CASE_READER_UNAVAILABLE"})
        try:
            cases, farms = await reader()
        except Exception as exc:
            raise HTTPException(status_code=503, detail={"status": "OPERATIONAL_DATA_UNAVAILABLE"}) from exc
        disease_code = {display: code.upper() for code, display in SUPPORTED_DISEASES.items()}[disease_display]
        points, excluded = operational_case_points(cases, farms, disease_code=disease_code, as_of=as_of_date,
                                                   window_days=EXPLORATORY_CONFIG.active_window_days)
        historical: list = []
        historical_status = "OK"
        try:
            historical = await run_in_threadpool(historical_reader.eligible_sources, disease=disease_display, as_of=as_of_date.isoformat(),
                                                 window_days=EXPLORATORY_CONFIG.active_window_days, country="Sri Lanka")
        except ScientificDatasetUnavailableError:
            historical_status = "SCIENTIFIC_DATASET_UNAVAILABLE"
        result = await run_in_threadpool(lambda: run_runtime_st_clustering(
            operational_points=points, historical_sources=historical, as_of=as_of_date, disease_display=disease_display))
        result["operational_exclusions"] = dict(excluded)
        result["historical_status"] = historical_status
        return result

    return router
