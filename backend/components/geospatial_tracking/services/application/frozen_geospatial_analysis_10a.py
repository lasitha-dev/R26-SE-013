"""Checkpoint 10A: production-safe frozen geospatial runtime analysis
application service.

**Orchestration only** -- every scientific value here is either a
frozen constant read verbatim, or computed by an already-frozen
canonical function imported from its historical module. No formula is
reimplemented: `get_eligible_sources` (source eligibility),
`build_scientific_evaluation_domain`/`ScientificGridConfig` (projection
-safe domain + frozen 5km grid), `score_origin_candidates_7c` (frozen
C0), `compute_cell_direction_tendency_8b3` (frozen 8B.3 direction),
`default_apparent_rate_component_9c`/`build_nominal_reach_by_day_9c`
(frozen 9C rate/reach). This mirrors the same computation
`smoke_tests/run_direction_structural_audit_8b3.py` already performs
across the whole FIT_DEVELOPMENT corpus for structural readiness --
here it runs for exactly one requested `forecast_origin_id` on demand.

**Not model evaluation** (Part 4): this module never touches held-out/
Sri Lanka evaluation code, never reruns the 9B bootstrap, and computes
no new research metric (accuracy, percentile, TOP5/TOP10, a new S0, a
new kernel scale, a new evaluation radius). C0 remains
`STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT` -- rate/reach are attached
as read-only context, never multiplied into the cell score.

**Repository abstraction** (Part 14): every function here types against
`OutbreakRepository` (the Protocol in `repositories/base.py`), never
`SQLiteOutbreakRepository` directly -- swapping in a future
`MongoOutbreakRepository` requires no change here.

**Explicit, never-fabricated unavailability** (Part 13): a missing
origin, zero eligible sources, or an empty scientific domain/grid each
raise `RuntimeAnalysisError10A` with one of the explicit status
constants below -- never a fabricated score/bearing/source count.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...config import ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT
from ...domain.enums import RecordDomainScope
from ...repositories.base import OutbreakRepository
from ...schemas import ValidationMode
from ..direction.c0_cell_local_tendency_8b3 import CellDirectionTendency8B3, compute_cell_direction_tendency_8b3
from ..disease import DEFAULT_DISEASE, UnsupportedDiseaseError, resolve_disease_selection
from ..forecast_origin import ForecastOrigin, build_forecast_origin_ledger
from ..geospatial.scientific_domain import build_scientific_evaluation_domain
from ..geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
from ..geospatial.source_geometry import EligibleSourcePoint
from ..integration.geospatial_intelligence_contract_9c import (
    RISK_SCORE_SEMANTICS_9C,
    RISK_SURFACE_TEMPORAL_SEMANTICS_9C,
    ApparentRateComponent9C,
    default_apparent_rate_component_9c,
)
from ..integration.nominal_reach_9c import NOMINAL_REACH_SEMANTICS_9C, NominalReachDay9C, build_nominal_reach_by_day_9c
from ..model_development.direction_protocol_8b import direction_method_protocol_hash_8b3
from ..model_development.heldout_protocol_7d import FROZEN_7C_SPEC_HASH, SELECTED_CANDIDATE_ID
from ..model_development.local_evaluation_scope import PRIMARY_LOCAL_EVALUATION_DISTANCE_KM, SCIENTIFIC_GRID_CELL_SIZE_KM
from ..model_development.rate_protocol_9b import HISTORICAL_9A_PROTOCOL_HASH_9B, NINE_A1_EXPOSURE_CLASSIFICATION_9B
from ..model_development.rate_scope_conditioning_9c1 import (
    LEAD_DEPENDENT_TRUNCATION_MECHANISM_LABEL_9C1,
    RATE_ESTIMAND_CONDITIONING_9C1,
    RATE_ESTIMAND_STATEMENT_9C1,
    RATE_SCOPE_CONDITIONING_LABEL_9C1,
)
from ..model_development.rate_scope_conditioning_protocol_9c1 import (
    HISTORICAL_9B_PROTOCOL_HASH_9C1,
    HISTORICAL_9C_INTEGRATION_PROTOCOL_HASH_9C1,
    rate_scope_conditioning_protocol_hash_9c1,
)
from ..model_development.candidate_registry_7c import C0_FAMILY, build_candidate_registry_7c
from ..model_development.wind_scoring_7c import score_origin_candidates_7c
from ..source_selector import get_eligible_sources

ACTIVE_SOURCE_WINDOW_DAYS_10A = ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT
ACTIVE_SOURCE_WINDOW_DAYS_LABEL_10A = "UNFROZEN_DEVELOPMENT_PARAMETER"

RUNTIME_GRID_CONFIG_10A = ScientificGridConfig(
    cell_size_km=SCIENTIFIC_GRID_CELL_SIZE_KM,
    domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION,
    domain_distance_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
)

ANALYSIS_STATUS_ANALYZED_10A = "ANALYZED"
ORIGIN_NOT_FOUND_10A = "ORIGIN_NOT_FOUND"
ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_10A = "ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE"
ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN_10A = "ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN"
ANALYSIS_UNAVAILABLE_GRID_10A = "ANALYSIS_UNAVAILABLE_GRID"
ANALYSIS_INTERNAL_ERROR_10A = "ANALYSIS_INTERNAL_ERROR"  # never raised by this service itself -- reserved for the router's catch-all on a genuinely unexpected exception

SCORE_STATUS_MODEL_INPUT_INCOMPLETE_10A = "MODEL_INPUT_INCOMPLETE"
DIRECTION_STATUS_UNAVAILABLE_10A = "DIRECTION_UNAVAILABLE_NO_CELL_RESULT"

# --- FMD-02 (additive only; every historical 10A/10A.1 status constant
# above is unchanged in name and value) ---
#
# Two new explicit, never-fabricated failure statuses -- mirroring the
# existing `ORIGIN_NOT_FOUND_10A`/`ANALYSIS_UNAVAILABLE_*_10A` pattern
# exactly (Part 13's rule: an unresolvable request raises
# `RuntimeAnalysisError10A` with an explicit status, never a fabricated
# score/bearing/source).
UNSUPPORTED_DISEASE_10A = "UNSUPPORTED_DISEASE"
ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY_10A = "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"

# Deliberately declared here, NOT added to `ERROR_STATUS_TAXONOMY_10A`/
# `ERROR_HTTP_STATUS_MAP_10A` in `integration/geospatial_api_protocol_10a.py`
# -- those two constants are bound into the FROZEN, historically-verified
# `geospatial_api_protocol_hash_10a()` (== the exact hex string re-verified
# unchanged through Checkpoints 10A.1/10B/10B.1/10B.1a). Mutating either
# constant would change that hash. `api/router.py` merges this additive
# map with the historical one at HTTP-dispatch time instead -- the
# historical dict object itself is never touched.
ERROR_STATUS_TAXONOMY_10A2 = (UNSUPPORTED_DISEASE_10A, ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY_10A)
ERROR_HTTP_STATUS_MAP_10A2 = {
    UNSUPPORTED_DISEASE_10A: 422,  # bad client input -- matches FastAPI's own validation-error convention
    ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY_10A: 409,  # matches the sibling ANALYSIS_UNAVAILABLE_* -> 409 convention
}

DISEASE_MODEL_STATUS_READY_10A = "MODEL_READY_FROZEN_SCIENTIFIC_PARAMETERS_AVAILABLE"
DISEASE_MODEL_STATUS_NOT_READY_10A = "MODEL_NOT_READY_NO_FROZEN_SCIENTIFIC_PARAMETERS"

DISEASE_MODEL_READINESS_10A: dict[str, str] = {
    DEFAULT_DISEASE: DISEASE_MODEL_STATUS_READY_10A,
    # "Foot and mouth disease" is deliberately ABSENT, not mapped to
    # DISEASE_MODEL_STATUS_NOT_READY_10A -- absence is read the same way
    # (via .get(...) below) but keeps this registry additive-only: a
    # future model-development checkpoint adds a new entry, it never
    # flips an existing one. Being accepted by
    # `services.disease.SUPPORTED_DISEASES` (an identifier-level fact)
    # never implies an entry exists here (a scientific-availability
    # fact) -- see that module's docstring addendum.
}
"""Disease-level scientific-model-readiness registry. Only a disease whose
own Checkpoint 7B-9C-equivalent candidate-selection and S0 rate-estimation
have actually been run and frozen may be marked ready. LSD's frozen
`FROZEN_KERNEL_FAMILY`/`FROZEN_KERNEL_SCALE_KM`/`EXPOSED_ESTIMATOR_VALUE_9B`
must never be reused for a different disease -- this registry is the
single gate that enforces that (checked before ANY repository access,
see `run_frozen_geospatial_runtime_analysis_10a` below)."""

# --- Checkpoint 10A.1 (additive only; historical 10A behavior/values above unchanged) ---
#
# Part 1: the 14-day active source window is numerically load-bearing
# (it changes the eligible-source set feeding C0) and is reused EXACTLY
# from the historical 10A constant above -- never duplicated as a
# second literal, never retuned, never tested at an alternate value.
# Its ORIGINAL provenance (`config.py`) is `UNFROZEN_DEVELOPMENT_PARAMETER`
# -- explicitly NOT a scientifically validated biological/infectious-
# duration constant. `ACTIVE_SOURCE_WINDOW_RUNTIME_STATUS_10A1` states
# plainly that 14 days is retained only for reproducibility/compatibility
# with the historical model-development/evaluation pipeline (Part 2:
# `evaluation_protocol_7c.ACTIVE_SOURCE_WINDOW_DAYS_7C`,
# `heldout_protocol_7d.ACTIVE_SOURCE_WINDOW_DAYS_7D`,
# `sri_lanka_protocol_7e.ACTIVE_SOURCE_WINDOW_DAYS_7E`, and
# `rate_protocol_9a`'s explicit `reused_from` all trace back to this
# SAME `config.ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT` -- verified by
# direct import inspection, never by rerunning any model).
ACTIVE_SOURCE_WINDOW_DAYS_10A1 = ACTIVE_SOURCE_WINDOW_DAYS_10A
ACTIVE_SOURCE_WINDOW_ORIGINAL_PROVENANCE_10A1 = "UNFROZEN_DEVELOPMENT_PARAMETER"
ACTIVE_SOURCE_WINDOW_RUNTIME_STATUS_10A1 = "FIXED_HISTORICAL_DEVELOPMENT_PROTOCOL_VALUE_NOT_SCIENTIFICALLY_VALIDATED"

# Part 3-4: current 10A/10A.1 runtime analysis calls source selection
# with `ValidationMode.RETROSPECTIVE_PROXY` / `RecordDomainScope.HISTORICAL_ONLY`
# (see `run_frozen_geospatial_runtime_analysis_10a` below, unchanged) --
# this is a HISTORICAL REPLAY over the retrospective research ledger,
# never live surveillance data, never strict operational availability,
# never real-time epidemiological forecasting. Adding an HTTP/FastAPI
# boundary in Checkpoint 10A did not make the underlying evidence
# real-time.
RUNTIME_DATA_MODE_10A1 = "HISTORICAL_RETROSPECTIVE_REPLAY"
AVAILABILITY_MODE_10A1 = "RETROSPECTIVE_PROXY"  # == ValidationMode.RETROSPECTIVE_PROXY.value, the SAME enum used below
RECORD_DOMAIN_SCOPE_10A1 = "HISTORICAL_ONLY"  # == RecordDomainScope.HISTORICAL_ONLY.value, the SAME enum used below
LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1 = "NOT_IMPLEMENTED_NO_ACTUAL_OPERATIONAL_AVAILABILITY_PIPELINE"
REALTIME_TRANSPORT_STATUS_10A1 = "NOT_IMPLEMENTED"

# Part 12: `/summary`, `/cells`, `/sources` each independently call the
# full runtime analysis today -- scientifically correct but potentially
# redundant GIS/C0/direction work if a caller requests all three for
# the same origin. No caching is introduced in 10A.1; this status is
# carried explicitly into Checkpoint 10B.
RUNTIME_SNAPSHOT_REUSE_STATUS_10A1 = "NOT_IMPLEMENTED_IN_10A1"

RATE_CONDITIONING_LIMITATION_10A = (
    "Rate estimate is conditional on target events contributing at least one valid observation inside the "
    "frozen 25-km local evaluation scope."
)

RUNTIME_LIMITATIONS_10A = (
    "RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY",
    "STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT_NOT_A_DAY_VARYING_PREDICTION",
    "C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY_NOT_DISEASE_SPREAD_DIRECTION",
    "DIRECTIONAL_CLARITY_IS_NORMALIZED_GEOMETRIC_RESULTANT_COHERENCE_NEVER_CONFIDENCE",
    "DEVELOPMENT_HISTORICAL_APPARENT_RATE_ESTIMATION_NOT_BIOLOGICAL_TRANSMISSION_SPEED",
    RATE_CONDITIONING_LIMITATION_10A,
    "NOMINAL_REACH_IS_VISUALIZATION_ONLY_NOT_A_HARD_DISEASE_BOUNDARY_NEVER_RECONCILED_WITH_25KM_ENVELOPE",
    "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE_NEVER_CAUSAL_TRANSMISSION_SOURCE",
)


class RuntimeAnalysisError10A(Exception):
    """Carries one of the explicit `*_10A` status constants -- the
    router maps this to a deliberate HTTP status, never a fabricated
    200 response."""

    def __init__(self, status: str, message: str):
        self.status = status
        super().__init__(message)


@dataclass(frozen=True)
class RuntimeSourcePoint10A:
    source_id: str
    longitude: float
    latitude: float
    availability_quality: str
    gps_quality: str

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id, "longitude": self.longitude, "latitude": self.latitude,
            "availability_quality": self.availability_quality, "gps_quality": self.gps_quality,
        }


@dataclass(frozen=True)
class RuntimeCellRisk10A:
    raw_c0_score: float | None
    score_status: str
    semantics: str
    risk_surface_temporal_semantics: str

    def as_dict(self) -> dict:
        return {
            "raw_c0_score": self.raw_c0_score, "score_status": self.score_status,
            "semantics": self.semantics, "risk_surface_temporal_semantics": self.risk_surface_temporal_semantics,
        }


@dataclass(frozen=True)
class RuntimeCellDirection10A:
    method_id: str | None
    method_version: str | None
    bearing_deg: float | None
    directional_clarity: float | None
    directional_input_coverage: float | None
    direction_status: str
    direction_semantics: str | None

    def as_dict(self) -> dict:
        return {
            "method_id": self.method_id, "method_version": self.method_version, "bearing_deg": self.bearing_deg,
            "directional_clarity": self.directional_clarity, "directional_input_coverage": self.directional_input_coverage,
            "direction_status": self.direction_status, "direction_semantics": self.direction_semantics,
        }


@dataclass(frozen=True)
class RuntimeCell10A:
    scientific_cell_id: str
    centroid_longitude: float
    centroid_latitude: float
    scientific_crs: str
    risk: RuntimeCellRisk10A
    direction: RuntimeCellDirection10A

    def as_dict(self) -> dict:
        return {
            "scientific_cell_id": self.scientific_cell_id,
            "centroid": {"longitude": self.centroid_longitude, "latitude": self.centroid_latitude},
            "scientific_crs": self.scientific_crs,
            "risk": self.risk.as_dict(), "direction": self.direction.as_dict(),
        }


@dataclass(frozen=True)
class RuntimeAnalysisMetadata10A:
    forecast_origin_id: str
    country: str
    t0: str
    temporal_mode: str
    disease: str
    active_source_window_days: int
    active_source_window_days_label: str
    status: str
    # Checkpoint 10A.1 additive fields -- surface the mode/provenance
    # facts that were already true of the 10A computation but not yet
    # exposed explicitly (Part 6-7).
    runtime_data_mode: str
    availability_mode: str
    record_domain_scope: str
    active_source_window_original_provenance: str
    active_source_window_runtime_status: str
    live_operational_analysis_status: str

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id, "country": self.country, "t0": self.t0,
            "temporal_mode": self.temporal_mode, "disease": self.disease,
            "active_source_window_days": self.active_source_window_days,
            "active_source_window_days_label": self.active_source_window_days_label, "status": self.status,
            "runtime_data_mode": self.runtime_data_mode, "availability_mode": self.availability_mode,
            "record_domain_scope": self.record_domain_scope,
            "active_source_window_original_provenance": self.active_source_window_original_provenance,
            "active_source_window_runtime_status": self.active_source_window_runtime_status,
            "live_operational_analysis_status": self.live_operational_analysis_status,
        }


@dataclass(frozen=True)
class FrozenGeospatialRuntimeAnalysis10A:
    analysis_metadata: RuntimeAnalysisMetadata10A
    eligible_sources: tuple
    cells: tuple
    apparent_rate_context: dict
    nominal_reach_by_day: tuple
    provenance: dict
    limitations: tuple

    def as_dict(self) -> dict:
        return {
            "analysis_metadata": self.analysis_metadata.as_dict(),
            "eligible_sources": [s.as_dict() for s in self.eligible_sources],
            "cells": [c.as_dict() for c in self.cells],
            "apparent_rate_context": self.apparent_rate_context,
            "nominal_reach_by_day": [d.as_dict() for d in self.nominal_reach_by_day],
            "provenance": self.provenance,
            "limitations": list(self.limitations),
        }


def _c0_candidate_spec():
    return next(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)


def resolve_forecast_origin_10a(repo: OutbreakRepository, disease: str, forecast_origin_id: str) -> ForecastOrigin | None:
    """Enumerates the real, runtime-derived origin ledger for the given
    (already-resolved, canonical) `disease` (never a hardcoded/cached
    list) and returns the one matching origin, preserving its real
    `t0`/`temporal_mode` exactly -- `None` if it does not exist.

    FMD-02: `disease` is now a required explicit parameter -- this
    function never reads the old module-level `DISEASE` constant."""
    origins = build_forecast_origin_ledger(repo, disease=disease)
    for origin in origins:
        if origin.forecast_origin_id == forecast_origin_id:
            return origin
    return None


def apparent_rate_context_10a() -> dict:
    """Reuses the frozen 9C rate component builder verbatim (takes no
    arguments -- a single frozen global scalar, never per-cell), then
    additively attaches the 9C.1 rate-scope-conditioning disclosure."""
    rate: ApparentRateComponent9C = default_apparent_rate_component_9c()
    payload = rate.as_dict()
    payload["rate_estimand_conditioning"] = RATE_ESTIMAND_CONDITIONING_9C1
    payload["conditioning_limitation"] = RATE_CONDITIONING_LIMITATION_10A
    payload["conditioning_statement"] = RATE_ESTIMAND_STATEMENT_9C1
    payload["rate_scope_conditioning_label"] = RATE_SCOPE_CONDITIONING_LABEL_9C1
    payload["lead_dependent_truncation_mechanism_label"] = LEAD_DEPENDENT_TRUNCATION_MECHANISM_LABEL_9C1
    return payload


def runtime_provenance_10a() -> dict:
    return {
        "frozen_c0_candidate_id": SELECTED_CANDIDATE_ID,
        "frozen_7c_spec_hash": FROZEN_7C_SPEC_HASH,
        "direction_method_protocol_hash_8b3": direction_method_protocol_hash_8b3(),
        "historical_9a_protocol_hash": HISTORICAL_9A_PROTOCOL_HASH_9B,
        "nine_a1_exposure_classification": NINE_A1_EXPOSURE_CLASSIFICATION_9B,
        "s0_bootstrap_protocol_hash_9b": HISTORICAL_9B_PROTOCOL_HASH_9C1,
        "integration_protocol_hash_9c": HISTORICAL_9C_INTEGRATION_PROTOCOL_HASH_9C1,
        "rate_scope_conditioning_protocol_hash_9c1": rate_scope_conditioning_protocol_hash_9c1(),
        "risk_score_semantics": RISK_SCORE_SEMANTICS_9C,
        "risk_surface_temporal_semantics": RISK_SURFACE_TEMPORAL_SEMANTICS_9C,
        "nominal_reach_semantics": NOMINAL_REACH_SEMANTICS_9C,
    }


def run_frozen_geospatial_runtime_analysis_10a(
    repo: OutbreakRepository, forecast_origin_id: str, *, disease: str | None = None,
) -> FrozenGeospatialRuntimeAnalysis10A:
    """The single runtime application-service entry point (Part 3).
    Raises `RuntimeAnalysisError10A` with an explicit status for every
    non-analyzable state -- never fabricates a score/bearing/source.

    FMD-02: `disease` is a new, keyword-only, OPTIONAL parameter.
    `disease=None` (the default -- every pre-FMD-02 caller/test passing
    only `(repo, forecast_origin_id)` positionally) resolves to
    `DEFAULT_DISEASE` ("Lumpy skin disease") via `resolve_disease_selection`,
    reproducing the exact pre-FMD-02 analysis unchanged. An unrecognized
    disease raises `RuntimeAnalysisError10A(UNSUPPORTED_DISEASE_10A, ...)`
    before any repository access.

    The disease-model-readiness gate below runs BEFORE origin resolution
    or any repository query, deliberately: whether a disease has frozen
    scientific parameters (kernel scale/family, apparent spread rate) is
    a fact about the DISEASE, not about any particular
    `forecast_origin_id` or about whether historical data happens to
    exist for it yet. Gating here produces one clear, deterministic,
    data-independent `ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY_10A`
    signal instead of a data-dependent `ORIGIN_NOT_FOUND_10A` that would
    look identical to "this specific origin id is wrong" and would stay
    misleading even after FMD historical data is eventually loaded
    (FMD-03) but before its own model is frozen (a later checkpoint) --
    and it structurally guarantees LSD's frozen values are never reached
    on an FMD code path (Invariant 3)."""
    try:
        resolved_disease = resolve_disease_selection(disease)
    except UnsupportedDiseaseError as exc:
        raise RuntimeAnalysisError10A(UNSUPPORTED_DISEASE_10A, str(exc)) from exc

    if DISEASE_MODEL_READINESS_10A.get(resolved_disease) != DISEASE_MODEL_STATUS_READY_10A:
        raise RuntimeAnalysisError10A(
            ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY_10A,
            f"disease={resolved_disease!r} is a recognized disease identifier but has no frozen "
            f"scientific parameters (kernel family/scale, apparent spread rate) yet -- "
            f"{DEFAULT_DISEASE!r}'s frozen Checkpoint 7B-9C values are never substituted for another "
            f"disease; a dedicated model-development checkpoint (re-running candidate selection and "
            f"S0 rate estimation against this disease's own historical corpus) is required first",
        )

    origin = resolve_forecast_origin_10a(repo, resolved_disease, forecast_origin_id)
    if origin is None:
        raise RuntimeAnalysisError10A(
            ORIGIN_NOT_FOUND_10A, f"no forecast origin with id {forecast_origin_id!r} for disease={resolved_disease!r}"
        )

    # Checkpoint 10A.1 Part 3-4/10A1-MODE-05: the SAME enum members feed
    # both the real source-selection call and the metadata mode fields
    # below -- never two independently-declared values that could drift.
    _availability_mode_used = ValidationMode.RETROSPECTIVE_PROXY
    _record_domain_scope_used = RecordDomainScope.HISTORICAL_ONLY

    eligible_result = get_eligible_sources(
        repo, disease=resolved_disease, t0=origin.t0, active_window_days=ACTIVE_SOURCE_WINDOW_DAYS_10A,
        temporal_mode=_availability_mode_used, country_scope=origin.country,
        domain_scope=_record_domain_scope_used,
    )
    eligible_sources_raw = eligible_result.sources
    if not eligible_sources_raw:
        raise RuntimeAnalysisError10A(
            ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_10A,
            f"forecast_origin_id={forecast_origin_id!r} has zero eligible sources at t0={origin.t0!r}",
        )

    source_points = [EligibleSourcePoint(source_id=s.source_id, latitude=s.latitude, longitude=s.longitude) for s in eligible_sources_raw]

    try:
        evaluation_domain = build_scientific_evaluation_domain(
            forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, sources=source_points,
            grid_config=RUNTIME_GRID_CONFIG_10A, primary_local_evaluation_distance_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
        )
    except Exception as exc:  # genuine scientific-domain construction failure, never masked as a fabricated result
        raise RuntimeAnalysisError10A(
            ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN_10A,
            f"forecast_origin_id={forecast_origin_id!r}: scientific domain construction failed: {exc}",
        ) from exc

    if not evaluation_domain.components:
        raise RuntimeAnalysisError10A(
            ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN_10A,
            f"forecast_origin_id={forecast_origin_id!r}: zero scientific domain components",
        )

    cells_raw = evaluation_domain.all_cells()
    if not cells_raw:
        raise RuntimeAnalysisError10A(
            ANALYSIS_UNAVAILABLE_GRID_10A,
            f"forecast_origin_id={forecast_origin_id!r}: scientific domain built but produced zero grid cells "
            f"(n_unsafe_components={evaluation_domain.n_unsafe_components()})",
        )

    grid_cell_dicts = [cell.as_dict() for cell in cells_raw]
    grid_cell_dicts.sort(key=lambda c: c["scientific_cell_id"] or c["grid_cell_id"])
    cells_by_grid_cell_id = {cell.grid_cell_id: cell for cell in cells_raw}

    c0_spec = _c0_candidate_spec()
    c0_scores = score_origin_candidates_7c(grid_cells=grid_cell_dicts, sources=source_points, candidates=(c0_spec,), wind=None)
    c0_by_cell = {c.grid_cell_id: c for c in c0_scores[c0_spec.candidate_id]}

    runtime_cells: list[RuntimeCell10A] = []
    for cell_dict in grid_cell_dicts:
        gcid = cell_dict["grid_cell_id"]
        cell_score = c0_by_cell.get(gcid)
        tendency: CellDirectionTendency8B3 = compute_cell_direction_tendency_8b3(cell_dict, source_points)
        source_cell = cells_by_grid_cell_id[gcid]
        runtime_cells.append(RuntimeCell10A(
            scientific_cell_id=cell_dict["scientific_cell_id"] or gcid,
            centroid_longitude=cell_dict["centroid_lon"], centroid_latitude=cell_dict["centroid_lat"],
            scientific_crs=source_cell.analysis_crs,
            risk=RuntimeCellRisk10A(
                raw_c0_score=cell_score.score if cell_score else None,
                score_status=cell_score.status if cell_score else SCORE_STATUS_MODEL_INPUT_INCOMPLETE_10A,
                semantics=RISK_SCORE_SEMANTICS_9C, risk_surface_temporal_semantics=RISK_SURFACE_TEMPORAL_SEMANTICS_9C,
            ),
            direction=RuntimeCellDirection10A(
                method_id=tendency.method_id, method_version=tendency.method_version, bearing_deg=tendency.bearing_deg,
                directional_clarity=tendency.directional_clarity, directional_input_coverage=tendency.directional_input_coverage,
                direction_status=tendency.direction_status, direction_semantics=tendency.direction_semantics,
            ),
        ))

    runtime_sources = tuple(sorted(
        (
            RuntimeSourcePoint10A(
                source_id=s.source_id, longitude=s.longitude, latitude=s.latitude,
                availability_quality=s.availability_quality, gps_quality=s.gps_quality,
            )
            for s in eligible_sources_raw
        ),
        key=lambda s: s.source_id,
    ))

    metadata = RuntimeAnalysisMetadata10A(
        forecast_origin_id=origin.forecast_origin_id, country=origin.country, t0=origin.t0,
        temporal_mode=origin.temporal_mode, disease=resolved_disease,
        active_source_window_days=ACTIVE_SOURCE_WINDOW_DAYS_10A,
        active_source_window_days_label=ACTIVE_SOURCE_WINDOW_DAYS_LABEL_10A, status=ANALYSIS_STATUS_ANALYZED_10A,
        runtime_data_mode=RUNTIME_DATA_MODE_10A1, availability_mode=_availability_mode_used.value,
        record_domain_scope=_record_domain_scope_used.value,
        active_source_window_original_provenance=ACTIVE_SOURCE_WINDOW_ORIGINAL_PROVENANCE_10A1,
        active_source_window_runtime_status=ACTIVE_SOURCE_WINDOW_RUNTIME_STATUS_10A1,
        live_operational_analysis_status=LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1,
    )

    return FrozenGeospatialRuntimeAnalysis10A(
        analysis_metadata=metadata, eligible_sources=runtime_sources, cells=tuple(runtime_cells),
        apparent_rate_context=apparent_rate_context_10a(), nominal_reach_by_day=build_nominal_reach_by_day_9c(),
        provenance=runtime_provenance_10a(), limitations=RUNTIME_LIMITATIONS_10A,
    )
