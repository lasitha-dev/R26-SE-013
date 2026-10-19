"""Spatial timeline application service: authorisation, district scope,
traceable source collection and snapshot caching around `engine.py`.

Authorisation: only an authenticated veterinarian. A district scope must
be the vet's registered district, the district of one of their assigned
farms, or any district for an ALL_DISTRICTS account.

Source selection is a scientific question, not an authorisation one: the
operational pool is every vet-verified ADRS case nationwide
(`collect_national_operational_sources`), privacy-reduced for farms outside
the vet's own authorised set. National scope uses every eligible source;
district scope uses every eligible source (either record domain) within the
frozen 25 km local evaluation distance of the district boundary -- the same
distance that bounds the scored C0 domain around a source -- so an outside
farm near the border is considered and a distant one is not. If the port has
no national reader, the pool falls back to the vet's authorised farms and
`source_statuses.operational` says so.

Caching: keyed by the snapshot identity, which hashes the model/engine
versions, disease, scope, as-of date, horizon AND the exact authorised
source set. A newly verified case changes the source set and therefore the
key (automatic invalidation), and a cached snapshot can only be served to a
request whose own authorised sources are identical.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.concurrency import run_in_threadpool

from ...domain.operational_enums import OperationalStatus
from ...domain.operational_models import AuthenticatedVetContext
from ...repositories.operational_port import OperationalDataPort
from ...repositories.provider import ScientificDatasetUnavailableError
from ..disease import SUPPORTED_DISEASES, UnsupportedDiseaseError, resolve_disease_selection
from ..model_development.local_evaluation_scope import PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
from ..operational.context_service import OperationalContextService
from ..sri_lanka_time import HOST_NAIVE_TIMESTAMP_BASIS, SRI_LANKA_TIMEZONE
from ..transport.snapshot_store_10b import SnapshotStore10B
from .districts import distance_to_district_km, find_district, normalize_district_name
from .engine import (
    ACTIVE_SOURCE_WINDOW_DAYS_10A,
    MAX_HORIZON_DAYS,
    TimelineScope,
    build_spatial_timeline,
    max_influence_distance_km,
    disease_model_ready,
    snapshot_identity,
)

from .wind_field import daily_wind
from .sources import (
    OPERATIONAL_POOL_AUTHORISED_ONLY,
    OPERATIONAL_POOL_NATIONAL,
    HistoricalSourceReader,
    SourceCollection,
    TimelineSource,
    authorised_farm_ids,
    collect_national_operational_sources,
    collect_operational_sources,
    historical_to_timeline_sources,
)

STUDY_COUNTRY = "Sri Lanka"
EXCLUDED_BEYOND_DISTRICT_RELEVANCE = "BEYOND_MODEL_REACH_OF_DISTRICT"


def district_relevance_distance_km(horizon_days: int = MAX_HORIZON_DAYS) -> float:
    """How far from a district a source can be and still colour it within the
    horizon: the model's own largest risk-kernel radius (engine)."""
    return max_influence_distance_km(horizon_days)


def district_relevant_sources(sources: list[TimelineSource], scope: TimelineScope, horizon_days: int = MAX_HORIZON_DAYS) -> tuple[list[TimelineSource], dict]:
    """National scope: every source. District scope: every source whose risk
    can reach the district within the horizon (inside = 0) -- so the district
    view draws the same risk surface as the national view inside the district."""
    if scope.kind != SCOPE_DISTRICT:
        return list(sources), {}
    limit_km = district_relevance_distance_km(horizon_days)
    kept, dropped = [], {}
    for source in sources:
        if distance_to_district_km(scope.district, source.latitude, source.longitude) <= limit_km:
            kept.append(source)
        else:
            key = f"{source.record_domain.lower()}:{EXCLUDED_BEYOND_DISTRICT_RELEVANCE}"
            dropped[key] = dropped.get(key, 0) + 1
    return kept, dropped
SCOPE_NATIONAL = "national"
SCOPE_DISTRICT = "district"
SPATIAL_TIMELINE_CACHE_TTL_SECONDS = 900.0

_DISEASE_CODE_BY_DISPLAY = {display: abbreviation.upper() for abbreviation, display in SUPPORTED_DISEASES.items()}


class SpatialTimelineError(Exception):
    def __init__(self, status: str, http_status: int, message: str):
        super().__init__(message)
        self.status = status
        self.http_status = http_status


def today_in_sri_lanka() -> date:
    return datetime.now(SRI_LANKA_TIMEZONE).date()


def parse_as_of(raw: str | None, *, today: date) -> date:
    if raw is None or not raw.strip():
        return today
    try:
        value = date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise SpatialTimelineError("INVALID_AS_OF_DATE", 422, "as_of must be an ISO date (YYYY-MM-DD)") from exc
    if value > today:
        raise SpatialTimelineError("AS_OF_DATE_IN_FUTURE", 422, "as_of cannot be after today -- no future observations exist")
    return value


def _is_national_account(vet_district: str | None) -> bool:
    return isinstance(vet_district, str) and vet_district.strip().casefold() == "all_districts"


def resolve_scope(*, scope: str, requested_district: str | None, vet_district: str | None, assigned_farm_districts: list[str | None]) -> TimelineScope:
    if scope == SCOPE_NATIONAL:
        return TimelineScope(kind=SCOPE_NATIONAL)
    if scope != SCOPE_DISTRICT:
        raise SpatialTimelineError("INVALID_SCOPE", 422, "scope must be 'national' or 'district'")

    target = requested_district
    if not target:
        if not vet_district:
            raise SpatialTimelineError("NO_AUTHORISED_DISTRICT", 409, "no district is registered on this veterinarian profile")
        if _is_national_account(vet_district):
            raise SpatialTimelineError("DISTRICT_REQUIRED", 422, "an ALL_DISTRICTS account must name a district")
        target = vet_district
    district = find_district(target)
    if district is None:
        raise SpatialTimelineError("DISTRICT_NOT_FOUND", 404, "no Sri Lanka district boundary matches that name")

    allowed = {normalize_district_name(d) for d in assigned_farm_districts if d}
    if vet_district and not _is_national_account(vet_district):
        allowed.add(normalize_district_name(vet_district))
    if not _is_national_account(vet_district) and district.name.casefold() not in allowed:
        raise SpatialTimelineError("DISTRICT_NOT_AUTHORISED", 403, "this district is outside the veterinarian's authorised scope")
    return TimelineScope(kind=SCOPE_DISTRICT, district=district)


class SpatialTimelineService:
    def __init__(self, operational_port: OperationalDataPort, historical_reader: HistoricalSourceReader, store: SnapshotStore10B) -> None:
        self._operational_port = operational_port
        self._historical_reader = historical_reader
        self._store = store

    async def get_timeline(
        self, vet: AuthenticatedVetContext, *, disease: str, scope: str, district: str | None, as_of: str | None,
        horizon_days: int, today: date | None = None,
    ) -> tuple[dict, str]:
        try:
            disease_display = resolve_disease_selection(disease)
        except UnsupportedDiseaseError as exc:
            raise SpatialTimelineError("UNSUPPORTED_DISEASE", 422, str(exc)) from exc
        disease_code = _DISEASE_CODE_BY_DISPLAY[disease_display]
        if not 0 <= horizon_days <= MAX_HORIZON_DAYS:
            raise SpatialTimelineError("INVALID_HORIZON", 422, f"horizon_days must be 0..{MAX_HORIZON_DAYS}")
        # as_of fixes the evidence cutoff; horizon_days controls subsequent display
        # frames. Future frames must not import future verified observations.
        as_of_date = parse_as_of(as_of, today=today or today_in_sri_lanka())

        context = await OperationalContextService(self._operational_port).get_operational_context(vet)
        if context.status == OperationalStatus.OPERATIONAL_DATA_UNAVAILABLE.value:
            raise SpatialTimelineError("OPERATIONAL_DATA_UNAVAILABLE", 503, "operational data source unavailable")

        timeline_scope = resolve_scope(
            scope=scope, requested_district=district, vet_district=context.vet_district,
            assigned_farm_districts=[farm.location_district for farm in context.farms],
        )

        collection = SourceCollection()
        national_reader = getattr(self._operational_port, "get_national_case_documents", None)
        if national_reader is not None:
            try:
                case_documents, farm_documents = await national_reader()
            except Exception as exc:  # never a raw database message to the client
                raise SpatialTimelineError("OPERATIONAL_DATA_UNAVAILABLE", 503, "operational data source unavailable") from exc
            operational_sources, operational_exclusions = collect_national_operational_sources(
                case_documents, farm_documents, disease_code=disease_code, disease_display=disease_display,
                as_of=as_of_date, window_days=ACTIVE_SOURCE_WINDOW_DAYS_10A, authorised_farms=authorised_farm_ids(context),
            )
            collection.operational_status = "OK"
            operational_pool = OPERATIONAL_POOL_NATIONAL
        else:
            operational_sources, operational_exclusions = collect_operational_sources(
                context, disease_code=disease_code, disease_display=disease_display, as_of=as_of_date,
                window_days=ACTIVE_SOURCE_WINDOW_DAYS_10A,
            )
            collection.operational_status = OPERATIONAL_POOL_AUTHORISED_ONLY
            operational_pool = OPERATIONAL_POOL_AUTHORISED_ONLY
        collection.sources.extend(operational_sources)
        collection.exclusions.update({f"operational:{k}": v for k, v in operational_exclusions.items()})

        if not disease_model_ready(disease_display):
            collection.historical_status = "NOT_REQUESTED_DISEASE_MODEL_NOT_READY"
        else:
            try:
                eligible = await run_in_threadpool(
                    self._historical_reader.eligible_sources, disease=disease_display, as_of=as_of_date.isoformat(), window_days=ACTIVE_SOURCE_WINDOW_DAYS_10A,
                    country=STUDY_COUNTRY,
                )
                historical_sources, historical_exclusions = historical_to_timeline_sources(eligible)
                collection.sources.extend(historical_sources)
                collection.exclusions.update({f"historical:{k}": v for k, v in historical_exclusions.items()})
                collection.historical_status = "OK"
            except ScientificDatasetUnavailableError:
                collection.historical_status = "SCIENTIFIC_DATASET_UNAVAILABLE"

        # A source just outside a district can still influence cells inside it.
        # Relevance uses model reach, rather than requiring the farm to be inside.
        collection.sources, relevance_exclusions = district_relevant_sources(collection.sources, timeline_scope, horizon_days)
        collection.exclusions.update(relevance_exclusions)
        selection = {
            "operational_pool": operational_pool,
            "operational_evidence": "VET_VERIFIED_DIAGNOSTIC_CASE_NOT_OFFICIAL_OUTBREAK_CONFIRMATION",
            "scope_rule": ("ALL_ELIGIBLE_SOURCES" if timeline_scope.kind == SCOPE_NATIONAL
                           else "ELIGIBLE_SOURCES_WITHIN_DISTRICT_RELEVANCE_DISTANCE"),
            "district_relevance_distance_km": round(district_relevance_distance_km(horizon_days), 3) if timeline_scope.kind == SCOPE_DISTRICT else None,
            "verification_date_basis": "ASIA_COLOMBO_CALENDAR_DATE_OF_VERIFICATION_INSTANT",
            "host_timestamp_basis": HOST_NAIVE_TIMESTAMP_BASIS,
            "external_source_detail": "PRIVACY_REDUCED_GPS_DATE_AND_ONE_WAY_RECORD_KEYS_ONLY",
        }

        # The response also reports why records were excluded (pending, no GPS,
        # other disease...), so a change there is a new snapshot too.
        # Source content and selection statuses participate in cache identity so
        # a changed evidence set cannot reuse an older timeline accidentally.
        key = (snapshot_identity(disease_display=disease_display, scope=timeline_scope, as_of=as_of_date,
                                 horizon_days=horizon_days, sources=collection.sources),
               collection.historical_status, collection.operational_status,
               tuple(sorted(collection.exclusions_dict().items())))
        statuses = {"historical": collection.historical_status, "operational": collection.operational_status}
        # Net daily wind at each case (Trajectory heading only, labelled
        # extension; never the score).
        today = today or today_in_sri_lanka()
        wind_lookup = (lambda lat, lon: daily_wind(lat, lon, as_of_date, horizon_days, today=today)) if horizon_days > 0 else None
        return await run_in_threadpool(self._store.get_or_compute, key, lambda: build_spatial_timeline(
            sources=collection.sources, disease_display=disease_display, disease_code=disease_code, as_of=as_of_date,
            horizon_days=horizon_days, scope=timeline_scope, source_exclusions=collection.exclusions_dict(),
            source_statuses=statuses, source_selection=selection, wind_lookup=wind_lookup,
        ))
