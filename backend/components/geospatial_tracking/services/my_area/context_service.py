"""GEO-AREA-01 Section 21: the My Area orchestrator -- composes the
existing GEO-INT-01/02 `OperationalDataPort` with the new read-only
`ScientificReadPort`. No Mongo/JWT/SQLite-connection concern belongs
here (both are injected).

Async boundary (Section 22): `OperationalDataPort`'s methods are async
(GEO-INT-02); the scientific read services are synchronous (mirrors
`api/router.py`'s own plain `def` route handlers, which FastAPI runs in
its threadpool). This service's own method is `async def` (it awaits the
operational port) and runs every scientific-port call through
`fastapi.concurrency.run_in_threadpool` -- the SAME helper already used
elsewhere in this component (`api/router.py`'s WebSocket handler) to
offload blocking work off the event loop, never a second ad-hoc
threading convention, and never `asyncio.run` inside production code.

**GEO-AREA-01S country/study-scope firewall**: every `list_origins` call
this service makes is scoped to `domain.my_area_enums.
GEOSPATIAL_STUDY_COUNTRY` ("Sri Lanka" -- the SAME real application
scope Page 1/Page 3 already enforce). The original implementation called
`list_origins(disease=..., country=None)` in the relevant-origins
listing path, and -- more critically -- the selected-origin path
(`origin_id` provided) never loaded the origin ledger AT ALL before
calling `get_origin_analysis`, so ANY real origin id for the requested
disease (regardless of country) could be selected. Both paths now load
the Sri-Lanka-scoped ledger and a caller-supplied `origin_id` is checked
against it (`allowed_origin_ids`) BEFORE `get_origin_analysis` is ever
called -- a real origin belonging to a different country is
indistinguishable, from the caller's perspective, from one that does
not exist at all; both return the same `ORIGIN_NOT_FOUND`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.concurrency import run_in_threadpool

from ...domain.my_area_enums import GEOSPATIAL_STUDY_COUNTRY, MyAreaStatus
from ...domain.my_area_models import MyAreaContext, SelectedOriginContext
from ...domain.operational_models import AuthenticatedVetContext
from ...repositories.operational_port import OperationalDataPort
from ...repositories.scientific_read_port import ScientificReadPort
from ...services.application.frozen_geospatial_analysis_10a import RuntimeAnalysisError10A
from ...services.disease import SUPPORTED_DISEASES, UnsupportedDiseaseError, resolve_disease_selection
from ..operational.clinical_context import build_verified_clinical_context
from ..operational.farm_normalization import normalize_assigned_farm
from .nearest_source import find_nearest_historical_source
from .nominal_reach_context import build_nominal_reach_context
from .relative_spatial_score import build_relative_spatial_score_context
from .relevant_origins import rank_relevant_origins

# The scientific disease registry (`services.disease.SUPPORTED_DISEASES`)
# and the operational one (`VerifiedClinicalContext.disease`, GEO-INT-01)
# represent the same two diseases with different string shapes ("Lumpy
# skin disease" vs "LSD"). Computed once from the single source of truth
# -- never a second hardcoded alias table.
_DISEASE_CODE_BY_DISPLAY = {display: abbreviation.upper() for abbreviation, display in SUPPORTED_DISEASES.items()}

# Section 20: only the origin-analysis failure statuses this service
# knows how to represent as a `MyAreaStatus` are mapped explicitly;
# anything else (a real but unanticipated `RuntimeAnalysisError10A`
# status) falls back to `ANALYSIS_INTERNAL_ERROR` -- never silently
# treated as `OK`.
_KNOWN_ORIGIN_ERROR_STATUSES = {
    "ORIGIN_NOT_FOUND": MyAreaStatus.ORIGIN_NOT_FOUND,
    "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY": MyAreaStatus.ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MyAreaContextService:
    def __init__(self, operational_port: OperationalDataPort, scientific_port: ScientificReadPort) -> None:
        self._operational_port = operational_port
        self._scientific_port = scientific_port

    async def get_my_area_context(
        self,
        vet: AuthenticatedVetContext | None,
        *,
        farm_id: str,
        disease: str | None,
        origin_id: str | None = None,
        forecast_day: int = 0,
    ) -> MyAreaContext:
        generated_at = _now_iso()

        if vet is None:
            return MyAreaContext(status=MyAreaStatus.UNAUTHORIZED.value, generated_at=generated_at)
        if not vet.is_vet():
            return MyAreaContext(status=MyAreaStatus.NON_VET_FORBIDDEN.value, generated_at=generated_at)

        # GEO-AREA-01H Section 11: My Area REQUIRES an explicit disease --
        # `resolve_disease_selection(None)` silently returns
        # `DEFAULT_DISEASE` (LSD), which is the correct behavior for the
        # generic `/origins`/`/analysis` routes (reproducing pre-FMD-02
        # behavior) but wrong here: the frontend always has an explicit
        # selected disease for this page, so a missing/blank value is
        # treated as an invalid selector, never silently turned into LSD.
        # `services/disease.py` itself is untouched -- this guard runs
        # BEFORE calling it, only for this checkpoint's own boundary.
        if not disease or not disease.strip():
            return MyAreaContext(status=MyAreaStatus.UNSUPPORTED_DISEASE.value, generated_at=generated_at)

        try:
            resolved_display = resolve_disease_selection(disease)
        except UnsupportedDiseaseError:
            return MyAreaContext(status=MyAreaStatus.UNSUPPORTED_DISEASE.value, generated_at=generated_at)
        disease_code = _DISEASE_CODE_BY_DISPLAY[resolved_display]

        # --- Section 5: assigned-farm authorization -- a caller-supplied
        # farm_id is a SELECTION, never authorization. ---
        try:
            raw_farms = await self._operational_port.get_assigned_farms(vet)
        except Exception:
            return MyAreaContext(status=MyAreaStatus.OPERATIONAL_DATA_UNAVAILABLE.value, disease=disease_code, generated_at=generated_at)

        farms = sorted((normalize_assigned_farm(f) for f in raw_farms), key=lambda f: f.farm_id)
        if not farms:
            return MyAreaContext(status=MyAreaStatus.NO_ASSIGNED_FARMS.value, disease=disease_code, generated_at=generated_at)

        area = next((f for f in farms if f.farm_id == farm_id), None)
        if area is None:
            # Section 5: identical status whether farm_id belongs to
            # another vet or doesn't exist at all -- never reveals which.
            return MyAreaContext(status=MyAreaStatus.ASSIGNED_AREA_NOT_FOUND.value, disease=disease_code, generated_at=generated_at)

        # --- Section 6: the farm's own stored GPS is authoritative. ---
        if area.location_status != "VALID":
            return MyAreaContext(status=MyAreaStatus.LOCATION_REQUIRED.value, disease=disease_code, area=area, generated_at=generated_at)

        # --- Section 18: verified clinical context for this farm+disease
        # only -- a separate, additive field; non-fatal on its own
        # failure since the area/origin context is still valid without it. ---
        clinical_contexts: list = []
        try:
            raw_cases = await self._operational_port.get_verified_clinical_cases(vet)
            farms_by_id = {area.farm_id: area}
            clinical_contexts = sorted(
                (
                    ctx
                    for ctx in (build_verified_clinical_context(c, assigned_farms_by_id=farms_by_id) for c in raw_cases)
                    if ctx is not None and ctx.disease == disease_code
                ),
                key=lambda ctx: ctx.case_id,
            )
        except Exception:
            clinical_contexts = []

        # --- Section 9: no silent origin auto-selection. ---
        if origin_id is None:
            try:
                origins = await run_in_threadpool(self._scientific_port.list_origins, disease=resolved_display, country=GEOSPATIAL_STUDY_COUNTRY)
                pairs = []
                for origin in origins:
                    locations = await run_in_threadpool(self._scientific_port.get_origin_trigger_locations, origin)
                    pairs.append((origin, locations))
            except Exception:
                return MyAreaContext(
                    status=MyAreaStatus.ANALYSIS_INTERNAL_ERROR.value,
                    disease=disease_code, area=area, verified_clinical_contexts=clinical_contexts, generated_at=generated_at,
                )

            relevant_origins = rank_relevant_origins(
                pairs, area_latitude=area.latitude, area_longitude=area.longitude, disease=disease_code,
            )
            status = MyAreaStatus.OK.value if relevant_origins else MyAreaStatus.NO_RELEVANT_ORIGINS.value
            return MyAreaContext(
                status=status, disease=disease_code, area=area, relevant_origins=relevant_origins,
                verified_clinical_contexts=clinical_contexts, generated_at=generated_at,
            )

        # --- Section 12 (GEO-AREA-01), GEO-AREA-01S Section 6: origin_id
        # provided -- FIRST validate it against the real, disease-matched,
        # Sri-Lanka-scoped origin ledger (never a string-prefix parse of
        # `origin_id` itself); only a real ledger member may reach
        # `get_origin_analysis`. ---
        try:
            scoped_origins = await run_in_threadpool(self._scientific_port.list_origins, disease=resolved_display, country=GEOSPATIAL_STUDY_COUNTRY)
        except Exception:
            return MyAreaContext(
                status=MyAreaStatus.ANALYSIS_INTERNAL_ERROR.value,
                disease=disease_code, area=area, verified_clinical_contexts=clinical_contexts, generated_at=generated_at,
            )

        allowed_origin_ids = {o.forecast_origin_id for o in scoped_origins}
        if origin_id not in allowed_origin_ids:
            # A real origin that exists for a DIFFERENT country (or does
            # not exist at all) is indistinguishable to the caller --
            # both return the same safe ORIGIN_NOT_FOUND, and
            # `get_origin_analysis` is never even called for it.
            return MyAreaContext(
                status=MyAreaStatus.ORIGIN_NOT_FOUND.value,
                disease=disease_code, area=area, verified_clinical_contexts=clinical_contexts, generated_at=generated_at,
            )

        try:
            snapshot = await run_in_threadpool(self._scientific_port.get_origin_analysis, origin_id, disease=resolved_display)
        except UnsupportedDiseaseError:
            return MyAreaContext(
                status=MyAreaStatus.UNSUPPORTED_DISEASE.value,
                disease=disease_code, area=area, verified_clinical_contexts=clinical_contexts, generated_at=generated_at,
            )
        except RuntimeAnalysisError10A as exc:
            mapped = _KNOWN_ORIGIN_ERROR_STATUSES.get(exc.status)
            status = mapped.value if mapped is not None else MyAreaStatus.ANALYSIS_INTERNAL_ERROR.value
            return MyAreaContext(
                status=status, disease=disease_code, area=area, verified_clinical_contexts=clinical_contexts, generated_at=generated_at,
            )
        except Exception:
            return MyAreaContext(
                status=MyAreaStatus.ANALYSIS_INTERNAL_ERROR.value,
                disease=disease_code, area=area, verified_clinical_contexts=clinical_contexts, generated_at=generated_at,
            )

        analysis = snapshot.analysis
        t0 = snapshot.transport_metadata.get("t0")

        # --- Section 13: nearest real historical source -- ITS OWN
        # concept (Section 9), computed from `analysis.eligible_sources`
        # (matching the existing `/sources`/`NEAREST_SOURCE_SEMANTICS_9C`
        # meaning of "nearest eligible source"). GEO-AREA-01H Section 2/9:
        # this value is NEVER reused below as a stand-in for "distance to
        # origin" -- no such field exists anymore (see nominal-reach
        # context, which carries no distance parameter at all). ---
        eligible_sources = [
            (s.source_id, s.latitude, s.longitude, s.availability_quality, s.gps_quality) for s in analysis.eligible_sources
        ]
        nearest_source = find_nearest_historical_source(eligible_sources, area_latitude=area.latitude, area_longitude=area.longitude)

        # --- Section 15/16: nominal-reach context for the requested day.
        # GEO-AREA-01H: no distance is passed in -- see
        # nominal_reach_context.py's module docstring for why no
        # scientifically defined anchor exists to measure one against. ---
        nominal_reach_entries = [d.as_dict() for d in analysis.nominal_reach_by_day]
        nominal_reach_ctx = build_nominal_reach_context(day=forecast_day, t0=t0, nominal_reach_entries=nominal_reach_entries)
        if nominal_reach_ctx is None:
            return MyAreaContext(
                status=MyAreaStatus.FORECAST_FRAME_UNAVAILABLE.value,
                disease=disease_code, area=area, verified_clinical_contexts=clinical_contexts, generated_at=generated_at,
            )

        # --- Section 14: Relative Spatial Score (always honestly
        # unavailable this checkpoint -- see relative_spatial_score.py). ---
        relative_spatial_score = build_relative_spatial_score_context()

        selected_origin_context = SelectedOriginContext(
            origin_id=origin_id,
            disease=disease_code,
            forecast_day=forecast_day,
            forecast_date=nominal_reach_ctx.forecast_date,
            t0=t0,
            nearest_historical_source=nearest_source,
            relative_spatial_score=relative_spatial_score,
            nominal_reach_context=nominal_reach_ctx,
        )

        return MyAreaContext(
            status=MyAreaStatus.OK.value,
            disease=disease_code,
            area=area,
            selected_origin_context=selected_origin_context,
            verified_clinical_contexts=clinical_contexts,
            generated_at=generated_at,
        )
