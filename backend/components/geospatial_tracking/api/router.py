"""Checkpoint 10A/10B: read-only FastAPI router, prefix
`/api/geospatial`, plus real-time TRANSPORT (WebSocket) over the same
frozen historical-retrospective scientific snapshot.

The router NEVER contains scientific computation, NEVER queries SQLite
directly, and NEVER reads a gitignored research artifact (10A-ROUTER-01/02,
10A-FIREWALL-01, 10B-FIREWALL-01..07). HTTP route handlers are plain
synchronous `def` (Part 15, Checkpoint 10A) so FastAPI runs each one in
its threadpool; the WebSocket handler is necessarily `async def` (a
FastAPI/Starlette requirement for WebSocket support), but the
CPU/GIS-heavy scientific computation inside it is still offloaded to a
thread via `run_in_threadpool` -- never executed directly on the event
loop.

Checkpoint 10B Part 8: `summary`/`cells`/`sources` no longer each
independently call the full scientific computation -- they all resolve
ONE shared `GeospatialSnapshot10B` through `SNAPSHOT_STORE_10B`
(Checkpoint 10B). `/origins` and the repository `Depends` factory are
unchanged from Checkpoint 10A -- they never touch the snapshot cache.
"""

from __future__ import annotations

import json
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from ..repositories.base import OutbreakRepository
from ..repositories.provider import create_outbreak_repository
from ..services.application.frozen_geospatial_analysis_10a import (
    ACTIVE_SOURCE_WINDOW_DAYS_10A1,
    ACTIVE_SOURCE_WINDOW_ORIGINAL_PROVENANCE_10A1,
    ACTIVE_SOURCE_WINDOW_RUNTIME_STATUS_10A1,
    ANALYSIS_INTERNAL_ERROR_10A,
    AVAILABILITY_MODE_10A1,
    ERROR_HTTP_STATUS_MAP_10A2,
    ERROR_STATUS_TAXONOMY_10A2,
    LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1,
    RECORD_DOMAIN_SCOPE_10A1,
    RUNTIME_DATA_MODE_10A1,
    RUNTIME_LIMITATIONS_10A,
    UNSUPPORTED_DISEASE_10A,
    RuntimeAnalysisError10A,
)
from ..services.application.frozen_fmd_risk_analysis_9 import FmdRiskAnalysisError9, run_frozen_fmd_risk_runtime_analysis_9
from ..services.direction.c0_cell_local_tendency_8b3 import ACTIVE_OUTPUT_SEMANTICS_8B3, DIRECTION_EVALUATION_TRUTH_STATUS_8B3
from ..services.disease import UnsupportedDiseaseError, resolve_disease_selection
from ..services.forecast_origin import build_forecast_origin_ledger
from ..services.integration.geospatial_api_protocol_10a import (
    ERROR_HTTP_STATUS_MAP_10A,
    ERROR_STATUS_TAXONOMY_10A,
    geospatial_api_protocol_hash_10a,
)
from ..services.integration.geospatial_api_protocol_10a1 import API_VERSION_10A1, geospatial_api_protocol_hash_10a1
from ..services.integration.geospatial_intelligence_contract_9c import (
    NEAREST_SOURCE_SEMANTICS_9C,
    RATE_STATUS_9C,
    RISK_SCORE_SEMANTICS_9C,
    RISK_SURFACE_TEMPORAL_SEMANTICS_9C,
)
from ..services.integration.geospatial_intelligence_protocol_9c import integration_protocol_hash_9c
from ..services.integration.geospatial_transport_protocol_10b import (
    AUTOMATIC_SCIENTIFIC_UPDATE_STATUS_10B,
    REALTIME_TRANSPORT_STATUS_10B,
    REPOSITORY_REVISION_TOKEN_STATUS_10B,
    RUNTIME_SNAPSHOT_REUSE_STATUS_10B,
    SNAPSHOT_CACHE_SCOPE_10B,
    TRANSPORT_VERSION_10B,
    geospatial_transport_protocol_hash_10b,
)
from ..services.integration.geospatial_transport_protocol_10b1 import (
    MESSAGE_TOO_LARGE_10B1,
    SNAPSHOT_CONTENT_INTEGRITY_MISMATCH_10B1,
    WS_MAX_INBOUND_MESSAGE_BYTES_10B1,
    geospatial_transport_protocol_hash_10b1,
)
from ..services.integration.geospatial_transport_protocol_10b1a import geospatial_transport_protocol_hash_10b1a
from ..services.integration.nominal_reach_9c import NOMINAL_REACH_SEMANTICS_9C, PRIMARY_HORIZON_DAYS_9C
from ..services.model_development.local_evaluation_scope import PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
from ..services.model_development.rate_scope_conditioning_9c1 import RATE_SCOPE_CONDITIONING_LABEL_9C1
from ..services.model_development.rate_scope_conditioning_protocol_9c1 import rate_scope_conditioning_protocol_hash_9c1
from ..services.transport.chunking_10b import WS_CELL_CHUNK_SIZE_10B, chunk_cells_10b
from ..services.transport.geospatial_snapshot_10b import (
    GeospatialSnapshot10B,
    compute_snapshot_with_managed_repository_10b,
    verify_snapshot_integrity_10b,
)
from ..services.transport.snapshot_store_10b import (
    SNAPSHOT_CACHE_MAX_ENTRIES_10B,
    SNAPSHOT_CACHE_TTL_SECONDS_10B,
    SnapshotStore10B,
)
from .schemas import (
    GEOJSON_COORDINATE_ORDER_10A,
    GEOJSON_CRS_10A,
    AnalysisMetadataSchema,
    AnalysisSummaryResponse,
    ApparentRateContextSchema,
    CellFeature,
    CellFeatureCollection,
    CellFeatureProperties,
    DirectionSchema,
    FmdRiskAnalysisResponse,
    GeoJSONPointGeometry,
    NominalReachDaySchema,
    OriginsResponse,
    OriginSummarySchema,
    OriginTriggerSourcesResponse,
    ProtocolResponse,
    RiskSchema,
    SourceFeature,
    SourceFeatureCollection,
    SourceFeatureProperties,
    TriggerSourceFeature,
    TriggerSourceFeatureProperties,
)
from .websocket_schemas import (
    INBOUND_MESSAGE_MODELS_10B,
    PingMessage,
    SnapshotRefreshMessage,
)

router = APIRouter(prefix="/api/geospatial", tags=["geospatial"])

# Checkpoint 10B Part 3/8: ONE shared snapshot store backs both HTTP and
# WebSocket -- a snapshot computed by one transport is immediately
# reusable by the other, inside its TTL/capacity bounds.
SNAPSHOT_STORE_10B = SnapshotStore10B()

# GEO-VISUAL-POLISH-02: `SnapshotStore10B` is a GENERIC bounded LRU+TTL
# cache (its own docstring: "knows nothing about scientific content -- key
# is any hashable tuple the caller builds") -- reused here verbatim for a
# SECOND, unrelated key space rather than inventing a new caching
# primitive. This fixes a real, measured backend bottleneck: `/origins`
# and `/origins/{id}/trigger-sources` both call `build_forecast_origin_
# ledger`, which does a FULL `repo.list_historical_records(...)` scan --
# and the frontend's Page-1 national-outbreak layer calls
# `/origins/{id}/trigger-sources` ONCE PER REAL ORIGIN (e.g. 16 separate
# requests for the real Sri Lanka FMD corpus today), each of which
# rebuilds the ENTIRE disease ledger from scratch even though `disease`
# (and, for `/origins`, `country`) is identical across every one of those
# calls in a single page load. Confirmed live (2026-08-31): one such
# request took >30s and appears to serialize with the others.
#
# Caching the deterministic ledger by `(disease, country_scope)` makes the
# FIRST request in a burst pay the real scan cost once; every other
# request for the SAME disease/country within the TTL is an in-memory
# hit. This changes NOTHING about what data is returned -- same
# deterministic function, same real repository, only reused across calls
# that would otherwise recompute an identical result. Never applied to
# `repo.get_historical_record(source_id)` (the per-source-id lookup after
# the ledger is resolved) -- that read is already a single cheap
# `find_one`, not the O(collection) scan this cache targets.
ORIGIN_LEDGER_STORE_10C = SnapshotStore10B()


def _cached_forecast_origin_ledger(repo: OutbreakRepository, *, disease: str, country_scope: str | None = None):
    value, _cache_status = ORIGIN_LEDGER_STORE_10C.get_or_compute(
        (disease, country_scope),
        lambda: build_forecast_origin_ledger(repo, disease=disease, country_scope=country_scope),
    )
    return value


def get_repository() -> Generator[OutbreakRepository, None, None]:
    """Opens exactly one repository per request (via the shared
    `repositories.provider.create_outbreak_repository()` boundary,
    Checkpoint 10B.1 Part 8 -- never `SQLiteOutbreakRepository`
    directly) and closes it deterministically in `finally`. Used only
    by `/origins` -- the analysis routes resolve a shared snapshot
    instead (Checkpoint 10B: no repository is opened at all on a cache
    hit)."""
    repo = create_outbreak_repository()
    try:
        yield repo
    finally:
        repo.close()


def _resolve_disease_or_http_error(disease: str | None) -> str:
    """FMD-02: the ONE place an HTTP request's raw `disease` query param
    is resolved -- `None` (omitted) reproduces pre-FMD-02 LSD-only
    behavior; anything unrecognized becomes a clear 422, never a
    fabricated analysis or a silent fallback to LSD."""
    try:
        return resolve_disease_selection(disease)
    except UnsupportedDiseaseError as exc:
        raise HTTPException(status_code=422, detail={"status": UNSUPPORTED_DISEASE_10A, "message": str(exc)}) from exc


def _snapshot_cache_key_10b(forecast_origin_id: str, disease: str | None = None) -> tuple:
    """Checkpoint 10B Part 6 / FMD-02: binds every input that could
    change the scientific content behind this key -- `disease` (resolved
    to its canonical form, so "LSD"/"Lumpy skin disease"/omitted all
    bind the SAME key, while a genuinely different disease always binds
    a DIFFERENT key) is now the first element, closing the FMD-01 gap
    where an LSD and an FMD request for the same `forecast_origin_id`
    could otherwise resolve to the same cached `SnapshotStore10B` entry."""
    resolved_disease = resolve_disease_selection(disease)
    return (
        resolved_disease, forecast_origin_id, geospatial_api_protocol_hash_10a1(), RUNTIME_DATA_MODE_10A1,
        AVAILABILITY_MODE_10A1, RECORD_DOMAIN_SCOPE_10A1, ACTIVE_SOURCE_WINDOW_DAYS_10A1,
    )


def _get_snapshot_10b(
    forecast_origin_id: str, disease: str | None = None, *, force_refresh: bool = False,
) -> tuple[GeospatialSnapshot10B, str]:
    key = _snapshot_cache_key_10b(forecast_origin_id, disease)
    return SNAPSHOT_STORE_10B.get_or_compute(
        key, lambda: compute_snapshot_with_managed_repository_10b(forecast_origin_id, disease=disease), force_refresh=force_refresh,
    )


def _get_snapshot_or_http_error(
    forecast_origin_id: str, disease: str | None = None, *, force_refresh: bool = False,
) -> tuple[GeospatialSnapshot10B, str]:
    try:
        return _get_snapshot_10b(forecast_origin_id, disease, force_refresh=force_refresh)
    except UnsupportedDiseaseError as exc:
        raise HTTPException(status_code=422, detail={"status": UNSUPPORTED_DISEASE_10A, "message": str(exc)}) from exc
    except RuntimeAnalysisError10A as exc:
        http_status = {**ERROR_HTTP_STATUS_MAP_10A, **ERROR_HTTP_STATUS_MAP_10A2}.get(
            exc.status, ERROR_HTTP_STATUS_MAP_10A[ANALYSIS_INTERNAL_ERROR_10A]
        )
        raise HTTPException(status_code=http_status, detail={"status": exc.status, "message": str(exc)}) from exc
    except Exception as exc:  # unexpected software failure -- never a raw stack trace to the client
        raise HTTPException(
            status_code=ERROR_HTTP_STATUS_MAP_10A[ANALYSIS_INTERNAL_ERROR_10A],
            detail={"status": ANALYSIS_INTERNAL_ERROR_10A, "message": "internal analysis failure"},
        ) from exc


def _metadata_schema(snapshot: GeospatialSnapshot10B) -> AnalysisMetadataSchema:
    return AnalysisMetadataSchema(**snapshot.transport_metadata)


def _summary_response(snapshot: GeospatialSnapshot10B) -> AnalysisSummaryResponse:
    analysis = snapshot.analysis
    return AnalysisSummaryResponse(
        analysis_metadata=_metadata_schema(snapshot),
        n_eligible_sources=len(analysis.eligible_sources),
        apparent_rate_context=ApparentRateContextSchema(**analysis.apparent_rate_context),
        nominal_reach_by_day=[NominalReachDaySchema(**d.as_dict()) for d in analysis.nominal_reach_by_day],
        nominal_reach_semantics=NOMINAL_REACH_SEMANTICS_9C,
        operational_evaluation_envelope_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
        provenance=analysis.provenance,
        limitations=list(analysis.limitations),
        snapshot_id=snapshot.snapshot_id, generated_at_utc=snapshot.generated_at_utc,
    )


def _cell_features(snapshot: GeospatialSnapshot10B) -> list[CellFeature]:
    """GeoJSON `Point` features at scientific-cell centroids --
    `[longitude, latitude]`, EPSG:4326. Already deterministically
    ordered by `scientific_cell_id` at the Checkpoint 10A application
    layer -- this function performs no re-sort."""
    return [
        CellFeature(
            geometry=GeoJSONPointGeometry(coordinates=(cell.centroid_longitude, cell.centroid_latitude)),
            properties=CellFeatureProperties(
                scientific_cell_id=cell.scientific_cell_id, scientific_crs=cell.scientific_crs,
                risk=RiskSchema(**cell.risk.as_dict()), direction=DirectionSchema(**cell.direction.as_dict()),
            ),
        )
        for cell in snapshot.analysis.cells
    ]


def _source_features(snapshot: GeospatialSnapshot10B) -> list[SourceFeature]:
    """Already deterministically ordered by `source_id`. C0 scoring
    continues to use ALL of these sources -- this listing never implies
    a nearest-source replacement."""
    return [
        SourceFeature(
            geometry=GeoJSONPointGeometry(coordinates=(source.longitude, source.latitude)),
            properties=SourceFeatureProperties(
                source_id=source.source_id, availability_quality=source.availability_quality,
                gps_quality=source.gps_quality, nearest_source_semantics=NEAREST_SOURCE_SEMANTICS_9C,
            ),
        )
        for source in snapshot.analysis.eligible_sources
    ]


@router.get("/protocol", response_model=ProtocolResponse)
def get_protocol() -> ProtocolResponse:
    """Scientific/API/transport protocol metadata and frozen semantics
    only -- performs no analysis, opens no repository."""
    return ProtocolResponse(
        api_version=API_VERSION_10A1,
        historical_api_protocol_hash_10a=geospatial_api_protocol_hash_10a(),
        active_api_protocol_hash_10a1=geospatial_api_protocol_hash_10a1(),
        integration_protocol_hash_9c=integration_protocol_hash_9c(),
        rate_scope_conditioning_protocol_hash_9c1=rate_scope_conditioning_protocol_hash_9c1(),
        risk_score_semantics=RISK_SCORE_SEMANTICS_9C,
        risk_surface_temporal_semantics=RISK_SURFACE_TEMPORAL_SEMANTICS_9C,
        direction_semantics=ACTIVE_OUTPUT_SEMANTICS_8B3,
        direction_evaluation_truth_status=DIRECTION_EVALUATION_TRUTH_STATUS_8B3,
        rate_status=RATE_STATUS_9C,
        rate_scope_conditioning_label=RATE_SCOPE_CONDITIONING_LABEL_9C1,
        nominal_reach_semantics=NOMINAL_REACH_SEMANTICS_9C,
        operational_evaluation_envelope_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
        geojson_crs=GEOJSON_CRS_10A,
        coordinate_order=GEOJSON_COORDINATE_ORDER_10A,
        primary_horizon_days=list(PRIMARY_HORIZON_DAYS_9C),
        # FMD-02: the additive UNSUPPORTED_DISEASE/DISEASE_MODEL_NOT_READY
        # statuses are appended to the RESPONSE only -- ERROR_STATUS_TAXONOMY_10A
        # itself (imported unchanged above) is never mutated, so
        # geospatial_api_protocol_hash_10a()/_10a1() stay byte-identical.
        error_statuses=list(ERROR_STATUS_TAXONOMY_10A) + list(ERROR_STATUS_TAXONOMY_10A2),
        limitations=list(RUNTIME_LIMITATIONS_10A),
        runtime_data_mode=RUNTIME_DATA_MODE_10A1, availability_mode=AVAILABILITY_MODE_10A1,
        record_domain_scope=RECORD_DOMAIN_SCOPE_10A1, active_source_window_days=ACTIVE_SOURCE_WINDOW_DAYS_10A1,
        active_source_window_original_provenance=ACTIVE_SOURCE_WINDOW_ORIGINAL_PROVENANCE_10A1,
        active_source_window_runtime_status=ACTIVE_SOURCE_WINDOW_RUNTIME_STATUS_10A1,
        live_operational_analysis_status=LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1,
        realtime_transport_status=REALTIME_TRANSPORT_STATUS_10B,
        runtime_snapshot_reuse_status=RUNTIME_SNAPSHOT_REUSE_STATUS_10B,
        transport_version=TRANSPORT_VERSION_10B,
        historical_transport_protocol_hash_10b=geospatial_transport_protocol_hash_10b(),
        historical_transport_protocol_hash_10b1=geospatial_transport_protocol_hash_10b1(),
        active_transport_protocol_hash_10b1a=geospatial_transport_protocol_hash_10b1a(),
        snapshot_cache_scope=SNAPSHOT_CACHE_SCOPE_10B, repository_revision_token_status=REPOSITORY_REVISION_TOKEN_STATUS_10B,
        cell_chunk_size=WS_CELL_CHUNK_SIZE_10B, automatic_scientific_update_status=AUTOMATIC_SCIENTIFIC_UPDATE_STATUS_10B,
    )


@router.get("/origins", response_model=OriginsResponse)
def list_origins(
    disease: str | None = Query(
        default=None,
        description="Optional disease selector (e.g. 'lsd', 'fmd', or a canonical name) -- "
                     "omitted defaults to Lumpy skin disease, reproducing pre-FMD-02 behavior",
    ),
    country: str | None = Query(default=None, description="Optional safe filter -- exact country match"),
    repo: OutbreakRepository = Depends(get_repository),
) -> OriginsResponse:
    """Lightweight available-origin metadata -- reuses the existing
    origin-ledger builder verbatim; performs NO scientific analysis for
    the whole database here."""
    resolved_disease = _resolve_disease_or_http_error(disease)
    origins = _cached_forecast_origin_ledger(repo, disease=resolved_disease, country_scope=country)
    summaries = [
        OriginSummarySchema(
            forecast_origin_id=o.forecast_origin_id, country=o.country, t0=o.t0,
            trigger_source_count=o.trigger_source_count,
        )
        for o in origins
    ]
    return OriginsResponse(origins=summaries, n_origins=len(summaries))


# ---------------------------------------------------------------------------
# Checkpoint FMD-10C1: real, OBSERVED historical T0 trigger-source geometry
# for Page 1's map markers -- disease-neutral, reuses the SAME runtime path
# `/origins` and `/analysis/{id}/fmd-risk` already use
# (`build_forecast_origin_ledger` + a plain `repo.get_historical_record`
# read per real trigger-source id -- the identical logic
# `repositories/scientific_read_port.py::RepositoryScientificReadPort.
# get_origin_trigger_locations` already applies for My Area's relevant-
# origin ranking, reused here against the router's own already-open
# repository rather than opening a second one). Never touches the
# LSD-shaped, `DISEASE_MODEL_READINESS_10A`-gated `/summary`/`/cells`/
# `/sources` snapshot machinery, and never reads the gitignored research
# corpus (10A-FIREWALL-01 still holds).
#
# A trigger source lacking a stored coordinate is simply absent from
# `features` -- never a fabricated/default/centroid point. In practice
# every `trigger_source_ids_at_t0` entry already passed the same valid-
# coordinate gate `historical_trigger.list_historical_trigger_candidates`
# applies when the origin was first built, so this is a defensive check,
# not the primary filter.
# ---------------------------------------------------------------------------

_TRIGGER_SOURCE_GEOMETRY_SEMANTICS_FMD10C1 = (
    "OBSERVED_HISTORICAL_TRIGGER_SOURCE_ONLY_NOT_A_RISK_CELL_FORECAST_POINT_"
    "DISEASE_BOUNDARY_NOMINAL_REACH_OR_TRAJECTORY_POINT"
)


@router.get("/origins/{forecast_origin_id}/trigger-sources", response_model=OriginTriggerSourcesResponse)
def get_origin_trigger_sources(
    forecast_origin_id: str,
    disease: str | None = Query(
        default=None,
        description="Optional disease selector (e.g. 'lsd', 'fmd', or a canonical name) -- "
                     "omitted defaults to Lumpy skin disease, matching every other route.",
    ),
    repo: OutbreakRepository = Depends(get_repository),
) -> OriginTriggerSourcesResponse:
    resolved_disease = _resolve_disease_or_http_error(disease)
    # Mirrors `frozen_fmd_risk_analysis_9.py::_resolve_fmd_forecast_origin_9`
    # exactly: the ledger is looked up unscoped by country because
    # `forecast_origin_id` itself already encodes the country
    # (`ORIGIN:{country}:{t0}`) -- only the ONE matching origin's own data
    # ever reaches the response, so this can never leak the global ledger.
    # GEO-VISUAL-POLISH-02: cached by `(disease, None)` -- every real
    # origin for this disease resolves through the SAME cache entry, so a
    # page load's N independent per-origin requests rebuild the full
    # ledger at most once per TTL window instead of N times.
    origins = _cached_forecast_origin_ledger(repo, disease=resolved_disease)
    origin = next((o for o in origins if o.forecast_origin_id == forecast_origin_id), None)
    if origin is None:
        raise HTTPException(
            status_code=404,
            detail={"status": "ORIGIN_NOT_FOUND", "message": f"no forecast origin with id {forecast_origin_id!r} for disease {resolved_disease!r}"},
        )

    features: list[TriggerSourceFeature] = []
    for source_id in origin.trigger_source_ids_at_t0:
        record = repo.get_historical_record(source_id)
        if record is None or not isinstance(record.latitude, (int, float)) or not isinstance(record.longitude, (int, float)):
            continue
        features.append(
            TriggerSourceFeature(
                geometry=GeoJSONPointGeometry(coordinates=(record.longitude, record.latitude)),
                properties=TriggerSourceFeatureProperties(
                    source_id=source_id,
                    forecast_origin_id=origin.forecast_origin_id,
                    geometry_semantics=_TRIGGER_SOURCE_GEOMETRY_SEMANTICS_FMD10C1,
                ),
            )
        )

    return OriginTriggerSourcesResponse(
        features=features,
        forecast_origin_id=origin.forecast_origin_id,
        country=origin.country,
        t0=origin.t0,
        disease=resolved_disease,
        n_points=len(features),
        geometry_semantics=_TRIGGER_SOURCE_GEOMETRY_SEMANTICS_FMD10C1,
    )


_DISEASE_QUERY_10A2 = Query(
    default=None,
    description="Optional disease selector (e.g. 'lsd', 'fmd', or a canonical name) -- "
                "omitted defaults to Lumpy skin disease, reproducing pre-FMD-02 behavior. "
                "A recognized disease with no frozen scientific parameters yet (e.g. FMD "
                "today) returns 409 ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY rather than "
                "an LSD-derived result.",
)


@router.get("/analysis/{forecast_origin_id}/summary", response_model=AnalysisSummaryResponse)
def get_analysis_summary(forecast_origin_id: str, disease: str | None = _DISEASE_QUERY_10A2) -> AnalysisSummaryResponse:
    snapshot, _cache_status = _get_snapshot_or_http_error(forecast_origin_id, disease)
    return _summary_response(snapshot)


@router.get("/analysis/{forecast_origin_id}/cells", response_model=CellFeatureCollection)
def get_analysis_cells(forecast_origin_id: str, disease: str | None = _DISEASE_QUERY_10A2) -> CellFeatureCollection:
    snapshot, _cache_status = _get_snapshot_or_http_error(forecast_origin_id, disease)
    return CellFeatureCollection(
        features=_cell_features(snapshot), analysis_metadata=_metadata_schema(snapshot),
        snapshot_id=snapshot.snapshot_id, generated_at_utc=snapshot.generated_at_utc,
    )


@router.get("/analysis/{forecast_origin_id}/sources", response_model=SourceFeatureCollection)
def get_analysis_sources(forecast_origin_id: str, disease: str | None = _DISEASE_QUERY_10A2) -> SourceFeatureCollection:
    snapshot, _cache_status = _get_snapshot_or_http_error(forecast_origin_id, disease)
    return SourceFeatureCollection(
        features=_source_features(snapshot), analysis_metadata=_metadata_schema(snapshot),
        snapshot_id=snapshot.snapshot_id, generated_at_utc=snapshot.generated_at_utc,
    )


# ---------------------------------------------------------------------------
# Checkpoint FMD-09: backend/API integration for the single FMD-08-locked
# frozen RISK model. Deliberately its own route -- never routed through
# `disease=fmd` on the LSD-shaped `/summary`/`/cells`/`/sources` endpoints
# above, which would require FMD to produce a spatial C0/direction/rate
# contract it never froze (see `frozen_fmd_risk_analysis_9.py`).
# ---------------------------------------------------------------------------

_FMD_ERROR_HTTP_STATUS_MAP_9 = {
    "ORIGIN_NOT_FOUND": 404,
    "ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE": 409,
    "ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN": 409,
    "ANALYSIS_INTERNAL_ERROR": 500,
}


@router.get("/analysis/{forecast_origin_id}/fmd-risk", response_model=FmdRiskAnalysisResponse)
def get_fmd_risk_analysis(forecast_origin_id: str, repo: OutbreakRepository = Depends(get_repository)) -> FmdRiskAnalysisResponse:
    """Scores one real FMD forecast origin against the single FMD-08-
    locked frozen candidate. Implicitly FMD-scoped (no `disease` query
    param -- the frozen candidate this route serves was fit and locked
    for FMD only)."""
    try:
        analysis = run_frozen_fmd_risk_runtime_analysis_9(repo, forecast_origin_id)
    except FmdRiskAnalysisError9 as exc:
        http_status = _FMD_ERROR_HTTP_STATUS_MAP_9.get(exc.status, 500)
        raise HTTPException(status_code=http_status, detail={"status": exc.status, "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail={"status": "ANALYSIS_INTERNAL_ERROR", "message": "internal FMD analysis failure"}
        ) from exc
    return FmdRiskAnalysisResponse(**analysis.as_dict())


# ---------------------------------------------------------------------------
# Checkpoint 10B: WebSocket transport (Part 9-18)
# ---------------------------------------------------------------------------


async def _send_json_safe(websocket: WebSocket, payload: dict) -> None:
    """Part 13: never sends NaN/Infinity -- `allow_nan=False` raises
    rather than silently emitting invalid-per-strict-JSON tokens."""
    text = json.dumps(payload, allow_nan=False, separators=(",", ":"), ensure_ascii=False)
    await websocket.send_text(text)


async def _send_error_10b(websocket: WebSocket, request_id: str | None, status: str, message: str) -> None:
    """Part 15: never a stack trace, file path, or SQL fragment."""
    await _send_json_safe(websocket, {"type": "error", "request_id": request_id, "status": status, "message": message})


def _snapshot_or_error_status_10b(
    forecast_origin_id: str, disease: str | None, *, force_refresh: bool,
) -> tuple[GeospatialSnapshot10B | None, str, str | None]:
    """Runs OFF the event loop via `run_in_threadpool` by the caller.
    Returns `(snapshot, cache_status, error)` -- `snapshot` is `None`
    and `error` is the exact `RuntimeAnalysisError10A.status` (or
    `UNSUPPORTED_DISEASE`/`ANALYSIS_INTERNAL_ERROR`) on failure, never a
    fabricated result. FMD-02: `disease` (already validated by the
    inbound Pydantic message, but resolved defensively here too, same
    as every other layer) reaches the exact same `_get_snapshot_10b`
    the HTTP routes use -- never a WebSocket-specific disease path."""
    try:
        snapshot, cache_status = _get_snapshot_10b(forecast_origin_id, disease, force_refresh=force_refresh)
        return snapshot, cache_status, None
    except UnsupportedDiseaseError:
        return None, "", UNSUPPORTED_DISEASE_10A
    except RuntimeAnalysisError10A as exc:
        return None, "", exc.status
    except Exception:
        return None, "", ANALYSIS_INTERNAL_ERROR_10A


async def _handle_snapshot_message_10b(
    websocket: WebSocket, request_id: str | None, forecast_origin_id: str, disease: str | None, *, force_refresh: bool,
) -> None:
    snapshot, cache_status, error_status = await run_in_threadpool(
        _snapshot_or_error_status_10b, forecast_origin_id, disease, force_refresh=force_refresh,
    )
    if snapshot is None:
        await _send_error_10b(websocket, request_id, error_status, f"forecast_origin_id={forecast_origin_id!r}: {error_status}")
        return

    # Checkpoint 10B.1a Part 7: verified BEFORE any scientific snapshot
    # frame is sent (snapshot_begin/summary/sources/cells_chunk) --
    # never after partial data has already reached the client. A REAL
    # in-memory recomputation via the canonical `compute_snapshot_id_10b`,
    # never a second hash formula and never an unconditional `True`.
    # This is an IN_MEMORY_TRANSPORT_CONSISTENCY_CHECK only -- not
    # cryptographic authenticity, database freshness, or external
    # provenance certification.
    if not verify_snapshot_integrity_10b(snapshot):
        await _send_error_10b(
            websocket, request_id, SNAPSHOT_CONTENT_INTEGRITY_MISMATCH_10B1,
            f"snapshot_id={snapshot.snapshot_id!r} did not match its recomputed scientific content hash",
        )
        return

    # Part 12: the SAME construction functions the HTTP routes use --
    # never a WebSocket-specific formula/normalization/rounding.
    cell_feature_dicts = [f.model_dump(mode="json") for f in _cell_features(snapshot)]
    source_collection = SourceFeatureCollection(
        features=_source_features(snapshot), analysis_metadata=_metadata_schema(snapshot),
        snapshot_id=snapshot.snapshot_id, generated_at_utc=snapshot.generated_at_utc,
    )
    summary = _summary_response(snapshot)
    chunks = chunk_cells_10b(cell_feature_dicts, WS_CELL_CHUNK_SIZE_10B)
    n_chunks = len(chunks)

    await _send_json_safe(websocket, {
        "type": "snapshot_begin", "request_id": request_id, "snapshot_id": snapshot.snapshot_id,
        "forecast_origin_id": forecast_origin_id, "active_api_protocol_hash_10a1": geospatial_api_protocol_hash_10a1(),
        "transport_protocol_hash_10b": geospatial_transport_protocol_hash_10b(),
        "active_transport_protocol_hash_10b1": geospatial_transport_protocol_hash_10b1(),
        "runtime_data_mode": RUNTIME_DATA_MODE_10A1, "live_operational_analysis_status": LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1,
        "n_sources": len(source_collection.features), "n_cells": len(cell_feature_dicts),
        "cell_chunk_size": WS_CELL_CHUNK_SIZE_10B, "n_cell_chunks": n_chunks, "cache_status": cache_status,
        "generated_at_utc": snapshot.generated_at_utc,
    })
    await _send_json_safe(websocket, {
        "type": "summary", "request_id": request_id, "snapshot_id": snapshot.snapshot_id,
        "data": summary.model_dump(mode="json"),
    })
    await _send_json_safe(websocket, {
        "type": "sources", "request_id": request_id, "snapshot_id": snapshot.snapshot_id,
        "data": source_collection.model_dump(mode="json"),
    })
    for chunk_index, chunk in enumerate(chunks):
        await _send_json_safe(websocket, {
            "type": "cells_chunk", "request_id": request_id, "snapshot_id": snapshot.snapshot_id,
            "chunk_index": chunk_index, "n_chunks": n_chunks, "features": chunk,
        })

    await _send_json_safe(websocket, {
        "type": "snapshot_end", "request_id": request_id, "snapshot_id": snapshot.snapshot_id,
        "n_sources_sent": len(source_collection.features), "n_cells_sent": len(cell_feature_dicts),
        "n_cell_chunks_sent": n_chunks, "scientific_content_hash_verified": True,
    })


async def _dispatch_ws_message_10b(websocket: WebSocket, raw_text: str) -> None:
    # Checkpoint 10B.1 Part 7: measured BEFORE json.loads -- an
    # oversized frame is never parsed at all.
    if len(raw_text.encode("utf-8")) > WS_MAX_INBOUND_MESSAGE_BYTES_10B1:
        await _send_error_10b(
            websocket, None, MESSAGE_TOO_LARGE_10B1,
            f"message exceeds the {WS_MAX_INBOUND_MESSAGE_BYTES_10B1}-byte limit",
        )
        return
    try:
        raw = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        await _send_error_10b(websocket, None, "INVALID_MESSAGE", "message body is not valid JSON")
        return
    if not isinstance(raw, dict) or "type" not in raw:
        await _send_error_10b(websocket, None, "INVALID_MESSAGE", "message must be a JSON object with a 'type' field")
        return

    request_id = raw.get("request_id")
    request_id = request_id if isinstance(request_id, str) or request_id is None else None
    msg_type = raw.get("type")

    model_cls = INBOUND_MESSAGE_MODELS_10B.get(msg_type) if isinstance(msg_type, str) else None
    if model_cls is None:
        await _send_error_10b(websocket, request_id, "UNSUPPORTED_MESSAGE_TYPE", f"unsupported message type {msg_type!r}")
        return

    try:
        message = model_cls.model_validate(raw)
    except ValidationError:
        status = "INVALID_FORECAST_ORIGIN_ID" if msg_type in ("snapshot_request", "snapshot_refresh") else "INVALID_MESSAGE"
        await _send_error_10b(websocket, request_id, status, "message failed validation")
        return

    if isinstance(message, PingMessage):
        await _send_json_safe(websocket, {"type": "pong", "request_id": message.request_id})
        return

    force_refresh = isinstance(message, SnapshotRefreshMessage)
    await _handle_snapshot_message_10b(
        websocket, message.request_id, message.forecast_origin_id, message.disease, force_refresh=force_refresh
    )


@router.websocket("/ws")
async def geospatial_websocket(websocket: WebSocket) -> None:
    """Checkpoint 10B Part 9: transport only -- never named a "live
    disease feed". No automatic DB polling, no background outbreak
    polling, no file watching, no fake refresh timer anywhere in this
    handler (Part 18)."""
    await websocket.accept()
    await _send_json_safe(websocket, {
        "type": "transport_ready", "transport_version": TRANSPORT_VERSION_10B,
        "transport_protocol_hash_10b": geospatial_transport_protocol_hash_10b(),
        "active_transport_protocol_hash_10b1": geospatial_transport_protocol_hash_10b1(),
        "runtime_data_mode": RUNTIME_DATA_MODE_10A1,
        "live_operational_analysis_status": LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1,
        "active_api_protocol_hash_10a1": geospatial_api_protocol_hash_10a1(),
    })
    try:
        while True:
            raw_text = await websocket.receive_text()
            await _dispatch_ws_message_10b(websocket, raw_text)
    except WebSocketDisconnect:
        return
