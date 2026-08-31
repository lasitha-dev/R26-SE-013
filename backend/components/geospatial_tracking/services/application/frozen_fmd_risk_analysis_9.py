"""Checkpoint FMD-09: production-safe frozen FMD risk runtime analysis
application service.

Per `AGENTS.md`'s Scientific Workflow, FMD-09 is "backend/API
integration" for the single FMD-08-locked RISK model -- this is a
DIFFERENT checkpoint from the pre-registered `FMD-EXP-09` (SPEED task),
which stays `BLOCKED` in `FMD_EXPERIMENT_REGISTRY.json` for an
unrelated GPS-quality/geometry reason untouched by this module.

**Deliberately NOT a branch inside `frozen_geospatial_analysis_10a.py`**:
that module's `run_frozen_geospatial_runtime_analysis_10a` unconditionally
scores every requested origin with LSD's own frozen C0 candidate
(`_c0_candidate_spec`), LSD's own frozen 8B.3 direction method, and LSD's
own frozen 9B/9C apparent-rate/nominal-reach constants -- flipping
`DISEASE_MODEL_READINESS_10A["Foot and mouth disease"]` to ready without
also branching every one of those calls would silently apply LSD's
fitted parameters to FMD requests, exactly the cross-disease parameter
conflation `AGENTS.md`'s FMD/LSD Isolation rules forbid. This module is
therefore its own, additive, FMD-only runtime path with its own frozen
constants -- `DISEASE_MODEL_READINESS_10A` is intentionally left
unchanged (Checkpoint 10A's generic `/summary`/`/cells`/`/sources`
endpoints keep returning `ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY`
for FMD, which is correct: those endpoints expose a spatial C0
grid/direction/rate contract FMD's frozen model never produced).

**FMD's own frozen local evaluation domain is 200km, not LSD's 25km**:
`fmd_calibration.FMD_SPATIAL_EVALUATION_RADIUS_KM` (the
`FMD-06C-PA POST_FEASIBILITY_PROTOCOL_AMENDMENT` value) is imported
directly and is never conflated with
`model_development.local_evaluation_scope.PRIMARY_LOCAL_EVALUATION_DISTANCE_KM`
(LSD's own, separately-calibrated 25km constant). The "100KM" in the
FMD-10B corrected frozen candidate id
`FMD07B:SPATIAL:B0_DISTANCE_ONLY:GAUSSIAN:100KM:NONE:...`
is the Gaussian kernel's distance-decay SCALE parameter (part of
`BaselineCandidateSpec`), a different quantity from the domain radius.

**Output is a single origin-level RISK score, never a spatial grid**:
the frozen FMD-07B/FMD-08 candidate produces one scalar
`predicted_score` per forecast origin (`Exp02OriginCandidatePrediction`,
via `aggregate_exp02_origin_cell_scores`'s frozen origin-scalar rule) --
this reflects the FMD RISK task definition itself (binary D1-D7
presence/absence within the local domain), not an LSD-style per-cell
spatial rank surface. No direction, apparent rate, or nominal reach is
attached: none of those are frozen for FMD (`FMD_TARGET_PROTOCOL.md`
Section 4 -- Tier-A GPS quality gap; no RATE experiment was ever
pre-registered for FMD).
"""

from __future__ import annotations

from dataclasses import dataclass

from ...repositories.base import OutbreakRepository
from ...schemas import ValidationMode
from ...domain.enums import RecordDomainScope
from ..disease import SUPPORTED_DISEASES
from ..fmd_calibration import FMD_SPATIAL_EVALUATION_RADIUS_KM
from ..fmd_model_development_8_heldout import Fmd08IntegrityError, resolve_frozen_candidate_spec, score_heldout_origin_frozen_candidate
from ..forecast_origin import ForecastOrigin, build_forecast_origin_ledger
from ..geospatial.scientific_domain import build_scientific_evaluation_domain
from ..geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
from ..geospatial.source_geometry import EligibleSourcePoint
from ..model_development.baseline_scoring import SCORED
from ..model_development.fmd_frozen_model_9 import FROZEN_THRESHOLD_FMD09, FROZEN_MODEL_SPEC_SHA256_FMD09, SELECTED_CANDIDATE_ID_FMD09
from ..model_development.local_evaluation_scope import SCIENTIFIC_GRID_CELL_SIZE_KM
from ..source_selector import get_eligible_sources

FMD_DISEASE_NAME_9 = SUPPORTED_DISEASES["fmd"]

# Cited exactly as the FMD-08 locked-evaluation batch script
# (`scratch_run_fmd08_heldout.py`) declares it: "frozen FMD-06B-R
# calibration value, applied unchanged" -- reused here verbatim, never
# retuned or re-derived for the runtime API path.
FMD_ACTIVE_SOURCE_WINDOW_DAYS_9 = 14

FMD_RUNTIME_GRID_CONFIG_9 = ScientificGridConfig(
    cell_size_km=SCIENTIFIC_GRID_CELL_SIZE_KM,
    domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION,
    domain_distance_km=FMD_SPATIAL_EVALUATION_RADIUS_KM,
)

ANALYSIS_STATUS_SCORED_9 = "SCORED"
ANALYSIS_STATUS_UNAVAILABLE_9 = "UNAVAILABLE"

ORIGIN_NOT_FOUND_9 = "ORIGIN_NOT_FOUND"
ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_9 = "ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE"
ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN_9 = "ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN"
ANALYSIS_INTERNAL_ERROR_9 = "ANALYSIS_INTERNAL_ERROR"

RISK_SCORE_SEMANTICS_9 = "RELATIVE_ORIGIN_LEVEL_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY"
RISK_TASK_SEMANTICS_9 = "D1_D7_BINARY_LOCAL_DOMAIN_PRESENCE_ABSENCE_NOT_A_SPATIAL_RISK_SURFACE"

FMD_RUNTIME_LIMITATIONS_9 = (
    RISK_SCORE_SEMANTICS_9,
    RISK_TASK_SEMANTICS_9,
    "HISTORICAL_RETROSPECTIVE_REPLAY_NOT_LIVE_SURVEILLANCE",
    "DIRECTION_NOT_FROZEN_FOR_FMD_TIER_A_GPS_QUALITY_GAP",
    "APPARENT_RATE_NOT_FROZEN_FOR_FMD_NO_RATE_EXPERIMENT_REGISTERED",
    "FMD_SPATIAL_EVALUATION_RADIUS_KM_IS_A_FIXED_COMPUTATIONAL_DOMAIN_NOT_A_BIOLOGICAL_TRANSMISSION_DISTANCE",
)


class FmdRiskAnalysisError9(Exception):
    """Carries one of the explicit `*_9` status constants -- never a
    fabricated score. Mirrors `RuntimeAnalysisError10A`'s pattern for the
    LSD path, kept as its own type so an FMD failure can never be caught
    by an LSD-scoped `except RuntimeAnalysisError10A`."""

    def __init__(self, status: str, message: str):
        self.status = status
        super().__init__(message)


@dataclass(frozen=True)
class FrozenFmdRiskAnalysis9:
    forecast_origin_id: str
    country: str
    t0: str
    temporal_mode: str
    disease: str
    status: str
    risk_score: float | None
    risk_score_status: str
    threshold: float
    above_threshold: bool | None
    n_eligible_sources: int
    active_source_window_days: int
    local_evaluation_radius_km: float
    frozen_candidate_id: str
    frozen_model_spec_sha256: str
    risk_score_semantics: str
    risk_task_semantics: str
    limitations: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id, "country": self.country, "t0": self.t0,
            "temporal_mode": self.temporal_mode, "disease": self.disease, "status": self.status,
            "risk_score": self.risk_score, "risk_score_status": self.risk_score_status,
            "threshold": self.threshold, "above_threshold": self.above_threshold,
            "n_eligible_sources": self.n_eligible_sources,
            "active_source_window_days": self.active_source_window_days,
            "local_evaluation_radius_km": self.local_evaluation_radius_km,
            "frozen_candidate_id": self.frozen_candidate_id,
            "frozen_model_spec_sha256": self.frozen_model_spec_sha256,
            "risk_score_semantics": self.risk_score_semantics, "risk_task_semantics": self.risk_task_semantics,
            "limitations": list(self.limitations),
        }


def _resolve_fmd_forecast_origin_9(repo: OutbreakRepository, forecast_origin_id: str) -> ForecastOrigin | None:
    origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9)
    for origin in origins:
        if origin.forecast_origin_id == forecast_origin_id:
            return origin
    return None


def run_frozen_fmd_risk_runtime_analysis_9(
    repo: OutbreakRepository, forecast_origin_id: str,
) -> FrozenFmdRiskAnalysis9:
    """The FMD-09 runtime application-service entry point: resolves one
    real forecast origin, scores it with the single FMD-08-locked frozen
    candidate, and returns a RISK-only result. Raises
    `FmdRiskAnalysisError9` with an explicit status for every
    non-analyzable state -- never fabricates a score.

    Never reads the gitignored evaluation-evidence tree at request time
    (matching the router's own 10A-FIREWALL-01 invariant): `SELECTED_CANDIDATE_ID_FMD09`/
    `FROZEN_THRESHOLD_FMD09`/`FROZEN_MODEL_SPEC_SHA256_FMD09` are literal
    constants promoted from the real, already-persisted FMD-07B/FMD-08
    artifacts (`fmd_frozen_model_9.py`), re-verified against those
    artifacts only by the offline freeze test, never re-read here."""
    try:
        frozen_candidate = resolve_frozen_candidate_spec(SELECTED_CANDIDATE_ID_FMD09)
    except Fmd08IntegrityError as exc:
        raise FmdRiskAnalysisError9(
            ANALYSIS_INTERNAL_ERROR_9, f"frozen FMD-07B candidate spec could not be resolved: {exc}"
        ) from exc

    origin = _resolve_fmd_forecast_origin_9(repo, forecast_origin_id)
    if origin is None:
        raise FmdRiskAnalysisError9(
            ORIGIN_NOT_FOUND_9, f"no FMD forecast origin with id {forecast_origin_id!r}"
        )

    eligible_result = get_eligible_sources(
        repo, disease=FMD_DISEASE_NAME_9, t0=origin.t0, active_window_days=FMD_ACTIVE_SOURCE_WINDOW_DAYS_9,
        temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=origin.country,
        domain_scope=RecordDomainScope.HISTORICAL_ONLY,
    )
    eligible_sources_raw = eligible_result.sources
    if not eligible_sources_raw:
        raise FmdRiskAnalysisError9(
            ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_9,
            f"forecast_origin_id={forecast_origin_id!r} has zero eligible FMD sources at t0={origin.t0!r}",
        )

    source_points = [
        EligibleSourcePoint(source_id=s.source_id, latitude=s.latitude, longitude=s.longitude)
        for s in eligible_sources_raw
    ]

    try:
        evaluation_domain = build_scientific_evaluation_domain(
            forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, sources=source_points,
            grid_config=FMD_RUNTIME_GRID_CONFIG_9, primary_local_evaluation_distance_km=FMD_SPATIAL_EVALUATION_RADIUS_KM,
        )
    except Exception as exc:
        raise FmdRiskAnalysisError9(
            ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN_9,
            f"forecast_origin_id={forecast_origin_id!r}: scientific domain construction failed: {exc}",
        ) from exc

    if not evaluation_domain.components:
        raise FmdRiskAnalysisError9(
            ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN_9,
            f"forecast_origin_id={forecast_origin_id!r}: zero scientific domain components",
        )

    grid_cell_dicts = [cell.as_dict() for cell in evaluation_domain.all_cells()]
    prediction = score_heldout_origin_frozen_candidate(
        forecast_origin_id=origin.forecast_origin_id, grid_cells=grid_cell_dicts, sources=source_points,
        frozen_candidate=frozen_candidate, unsafe_component_count=evaluation_domain.n_unsafe_components(),
    )

    risk_score = prediction.score if prediction.status == SCORED else None
    above_threshold = (risk_score >= FROZEN_THRESHOLD_FMD09) if risk_score is not None else None

    return FrozenFmdRiskAnalysis9(
        forecast_origin_id=origin.forecast_origin_id, country=origin.country, t0=origin.t0,
        temporal_mode=origin.temporal_mode, disease=FMD_DISEASE_NAME_9,
        status=ANALYSIS_STATUS_SCORED_9 if risk_score is not None else ANALYSIS_STATUS_UNAVAILABLE_9,
        risk_score=risk_score, risk_score_status=prediction.status, threshold=FROZEN_THRESHOLD_FMD09,
        above_threshold=above_threshold, n_eligible_sources=len(eligible_sources_raw),
        active_source_window_days=FMD_ACTIVE_SOURCE_WINDOW_DAYS_9,
        local_evaluation_radius_km=FMD_SPATIAL_EVALUATION_RADIUS_KM,
        frozen_candidate_id=frozen_candidate.candidate_id, frozen_model_spec_sha256=FROZEN_MODEL_SPEC_SHA256_FMD09,
        risk_score_semantics=RISK_SCORE_SEMANTICS_9, risk_task_semantics=RISK_TASK_SEMANTICS_9,
        limitations=FMD_RUNTIME_LIMITATIONS_9,
    )
