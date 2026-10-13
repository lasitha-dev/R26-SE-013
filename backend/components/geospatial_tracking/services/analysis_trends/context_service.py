"""GEO-ANALYSIS-01 Section 2/22: the Page-3 "Analysis & Trends"
orchestrator. Composes the existing read-only `ScientificReadPort`
exactly as `services/my_area/context_service.py` composes it with the
operational port -- no farm/vet authorization concern belongs here
(Section 27: "no farm identity needed for national analysis"); auth is a
router-level 401/403 concern only (`api/analysis_trends_router_factory.py`),
mirrored from `my_area_router_factory.py`'s own auth-before-service
pattern.

**GEO-ANALYSIS-01H country/study-scope firewall**: every scientific read
this service performs is scoped to `domain.analysis_trends_enums.
ANALYSIS_TRENDS_COUNTRY` ("Sri Lanka" -- verified read-only against Page
1's own hardcoded `const COUNTRY = 'Sri Lanka'`,
`OutbreakMapPage.jsx`/`useNationalOutbreaks.js`). The original
GEO-ANALYSIS-01 implementation called both `list_historical_trigger_
candidates` and `list_origins` with `country=None`, producing GLOBAL
aggregates (e.g. a real `ORIGIN:Afghanistan:...` reachable from the
"Sri Lanka application"). This is corrected here, and a caller-supplied
`origin_id` is additionally checked against the already-loaded,
country-scoped `origins` ledger (`allowed_origin_ids`) BEFORE
`get_origin_analysis` is ever called -- a real origin belonging to a
different country is indistinguishable, from the caller's perspective,
from one that does not exist at all; both return the same
`ORIGIN_NOT_FOUND`. The country scope itself is never accepted from a
query parameter, header, or request body -- it is a server/application
constant (Section 14/15).

**No scientific computation lives here.** Every number either comes
straight from a real `ScientificReadPort` read, or is a pure order-
statistic/grouping over that real data (`historical_trend.py`,
`score_distribution.py`) -- never a re-derivation of C0, direction, rate,
or reach.

**Why `model_evaluation`/`model_run_comparison`/`confidence`/`drivers`
are always unavailable this checkpoint** (real-metric audit, Section 3-4,
performed by inspecting `services/model_development/*` and
`services/application/*` directly before writing this file):

  - No MAE/RMSE/bearing-error metric of any kind exists anywhere in
    `services/`. The held-out evaluation pipeline that DOES exist
    (`services/model_development/heldout_run_7d.py`,
    `heldout_protocol_7d.py`) computes percentile-based capture-rate
    metrics (`mean_target_percentile`, `top5_capture_rate`,
    `top10_capture_rate`) -- a different metric family, and one that is
    OFFLINE/development-time only: its outputs are written to
    `local_data/model_evaluation/7d/*.json` research-evidence files,
    never read back by any runtime service or `api/` route. Per the
    checkpoint's own Section 5 rule ("do NOT build a production API that
    scrapes checkpoint report text"; Section 18: "if no suitable
    runtime-ready artifact exists, do NOT create one for this checkpoint"),
    `model_evaluation.status` is `EVALUATION_METRICS_NOT_AVAILABLE` for a
    model-ready disease, or `ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY`
    for one that is not.
  - `services/model_development/paired_comparison_7c.py` computes a
    candidate-vs-anchor comparison, but only between C0 CANDIDATE
    FORMULAS during Checkpoint 7C's own offline model SELECTION -- not
    between two stored, runtime-addressable "model runs" with stable ids.
    There is exactly one frozen, selected C0 model
    (`SELECTED_CANDIDATE_ID`, `heldout_protocol_7d.py`); no second stored
    run exists to compare it against, so `model_run_comparison.status`
    is always `MODEL_RUN_COMPARISON_UNAVAILABLE`.
  - No runtime scientific output anywhere (`FrozenGeospatialRuntimeAnalysis10A`
    and everything it composes) returns an explicitly documented
    "confidence" field. `directional_clarity` exists but is explicitly
    documented, in its own frozen limitation string
    (`RUNTIME_LIMITATIONS_10A`), as "normalized geometric resultant
    coherence, NEVER confidence" -- so `confidence.status` is always
    `CONFIDENCE_NOT_AVAILABLE`.
  - The frozen C0 model uses NONE of the environmental/host/wind/water
    factors: `heldout_protocol_7d.py`'s own freeze manifest fields
    (`host_factor_status`, `wind_anisotropy_status`,
    `environmental_suitability_status`, `water_context_status`,
    `source_strength_status`) are all `"NOT_SELECTED"` /
    `"NOT_YET_SCIENTIFICALLY_DEFINED"`, and the runtime computation itself
    (`frozen_geospatial_analysis_10a.run_frozen_geospatial_runtime_
    analysis_10a`) calls `score_origin_candidates_7c(..., wind=None)` --
    no environmental component vector is ever assembled at runtime. There
    is therefore no "environmental variables used by the model" metadata
    to expose even as metadata-only (Section 21's one allowed exception
    does not apply, because the frozen model does not actually use any),
    and certainly no validated decomposition -- `drivers.status` is
    always `DRIVER_DECOMPOSITION_NOT_AVAILABLE`.

**Why `direction_context` (selected-origin bearing) is always
`UNAVAILABLE_RUNTIME_METRIC`**: `RuntimeCellDirection10A.bearing_deg` is a
PER-GRID-CELL value (`frozen_geospatial_analysis_10a.py`'s `runtime_cells`
loop calls `compute_cell_direction_tendency_8b3` once per cell) -- there
is no single scientifically-defined origin-level bearing scalar to
report, and averaging bearings (circular/angular data) with a plain
arithmetic mean would be a mathematically invalid aggregation this
checkpoint does not invent (Section 4's "do not implement a metric
merely because a related field exists" applies directly here).
"""

from __future__ import annotations

from datetime import datetime, timezone

from ...domain.analysis_trends_enums import (
    ANALYSIS_TRENDS_COUNTRY,
    AREA_SCORE_AVAILABILITY_STATUS,
    HISTORICAL_COUNT_BASIS,
    NOMINAL_REACH_DISCLAIMER,
    AnalysisTrendsStatus,
    ApparentRateStatus,
    ConfidenceStatus,
    DirectionContextStatus,
    DriversStatus,
    EvaluationStatus,
    HistoricalDataStatus,
    ModelRunComparisonStatus,
    SelectedOriginAnalyticsStatus,
)
from ...domain.analysis_trends_models import (
    AnalysisTrendsContext,
    ApparentRateAnalytics,
    ConfidenceAnalytics,
    DirectionContext,
    DriversAnalytics,
    HistoricalSummary,
    ModelEvaluationAnalytics,
    ModelRunComparisonAnalytics,
    NominalReachAnalytics,
    NominalReachDayAnalytics,
    SelectedOriginAnalytics,
)
from ...repositories.scientific_read_port import ScientificReadPort
from ...services.application.frozen_geospatial_analysis_10a import (
    DISEASE_MODEL_READINESS_10A,
    DISEASE_MODEL_STATUS_READY_10A,
    RuntimeAnalysisError10A,
)
from ...services.disease import SUPPORTED_DISEASES, UnsupportedDiseaseError, resolve_disease_selection
from .historical_trend import build_historical_trend
from .score_distribution import build_relative_spatial_score_distribution

_DISEASE_CODE_BY_DISPLAY = {display: abbreviation.upper() for abbreviation, display in SUPPORTED_DISEASES.items()}
"""The same computed-once alias table `services/my_area/context_service.py`
uses -- never a second hardcoded copy."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unavailable_model_blocks(*, model_ready: bool) -> tuple[ModelEvaluationAnalytics, ModelRunComparisonAnalytics, ConfidenceAnalytics, DriversAnalytics]:
    """Section 9/23: every one of these four blocks is unavailable this
    checkpoint regardless of disease (see module docstring) -- but a
    disease with NO frozen scientific parameters at all gets the more
    specific `ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY` status on the
    evaluation block rather than the generic "no pipeline exists" status,
    since for that disease nothing scientific is ready yet at all."""
    evaluation_status = EvaluationStatus.EVALUATION_METRICS_NOT_AVAILABLE.value if model_ready else EvaluationStatus.ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY.value
    return (
        ModelEvaluationAnalytics(status=evaluation_status, metrics=[]),
        ModelRunComparisonAnalytics(status=ModelRunComparisonStatus.MODEL_RUN_COMPARISON_UNAVAILABLE.value),
        ConfidenceAnalytics(status=ConfidenceStatus.CONFIDENCE_NOT_AVAILABLE.value),
        DriversAnalytics(status=DriversStatus.DRIVER_DECOMPOSITION_NOT_AVAILABLE.value),
    )


class AnalysisTrendsService:
    def __init__(self, scientific_port: ScientificReadPort) -> None:
        self._scientific_port = scientific_port

    def get_analysis_trends(self, *, disease: str | None, origin_id: str | None = None) -> AnalysisTrendsContext:
        generated_at = _now_iso()

        # Section 8: disease is explicit and required at THIS boundary --
        # never silently defaulted to LSD, mirroring GEO-AREA-01H's own
        # guard (`services/disease.py` itself is untouched).
        if not disease or not disease.strip():
            return AnalysisTrendsContext(status=AnalysisTrendsStatus.UNSUPPORTED_DISEASE.value, generated_at=generated_at)
        try:
            resolved_display = resolve_disease_selection(disease)
        except UnsupportedDiseaseError:
            return AnalysisTrendsContext(status=AnalysisTrendsStatus.UNSUPPORTED_DISEASE.value, generated_at=generated_at)
        disease_code = _DISEASE_CODE_BY_DISPLAY[resolved_display]

        model_ready = DISEASE_MODEL_READINESS_10A.get(resolved_display) == DISEASE_MODEL_STATUS_READY_10A
        model_evaluation, model_run_comparison, confidence, drivers = _unavailable_model_blocks(model_ready=model_ready)

        # --- Section 5/6 (GEO-ANALYSIS-01H): historical trend, always
        # attempted, independent of model readiness (Section 9: FMD
        # historical data availability != FMD model readiness) -- and
        # ALWAYS scoped to the application's own real Sri Lanka study
        # scope, never `country=None` (the original GEO-ANALYSIS-01
        # defect this hardening checkpoint corrects). Both reads use the
        # SAME `ANALYSIS_TRENDS_COUNTRY` value so historical counts and
        # the origin ledger can never numerically disagree about scope. ---
        try:
            candidates = self._scientific_port.list_historical_trigger_candidates(disease=resolved_display, country=ANALYSIS_TRENDS_COUNTRY)
            origins = self._scientific_port.list_origins(disease=resolved_display, country=ANALYSIS_TRENDS_COUNTRY)
        except Exception:
            return AnalysisTrendsContext(
                status=AnalysisTrendsStatus.ANALYSIS_INTERNAL_ERROR.value, disease=disease_code, scope_country=ANALYSIS_TRENDS_COUNTRY,
                model_evaluation=model_evaluation, model_run_comparison=model_run_comparison,
                confidence=confidence, drivers=drivers, generated_at=generated_at,
            )

        historical_source_count = len(candidates)
        forecast_origin_count = len(origins)
        historical_trend = build_historical_trend(candidates)
        # Section 6 (GEO-ANALYSIS-01H): the real, already-loaded,
        # disease-matched, country-scoped origin ledger is the ONLY
        # authority a caller-supplied origin_id is checked against --
        # never a string-prefix parse of the id itself (Section 7).
        allowed_origin_ids = {origin.forecast_origin_id for origin in origins}

        if candidates:
            dates_sorted = sorted(c.effective_availability_date for c in candidates)
            first_observed_date, last_observed_date = dates_sorted[0], dates_sorted[-1]
            historical_status = HistoricalDataStatus.AVAILABLE.value
        else:
            first_observed_date = last_observed_date = None
            historical_status = HistoricalDataStatus.NO_HISTORICAL_DATA.value

        historical_summary = HistoricalSummary(
            status=historical_status, historical_source_count=historical_source_count,
            forecast_origin_count=forecast_origin_count, first_observed_date=first_observed_date,
            last_observed_date=last_observed_date, count_basis=HISTORICAL_COUNT_BASIS,
        )

        # --- Section 11/12/20 (GEO-ANALYSIS-01), Section 6 (GEO-ANALYSIS-01H):
        # selected-origin analytics -- ONLY when the caller supplies a real,
        # Sri-Lanka-scoped origin_id; never auto-selected, never accepted
        # from outside the loaded ledger. ---
        selected_origin_analytics = None
        if origin_id is not None:
            if not model_ready:
                selected_origin_analytics = SelectedOriginAnalytics(
                    status=SelectedOriginAnalyticsStatus.ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY.value,
                    origin_id=origin_id, disease=disease_code, area_score_availability=AREA_SCORE_AVAILABILITY_STATUS,
                )
            elif origin_id not in allowed_origin_ids:
                # Section 6/7: a real origin that exists for a DIFFERENT
                # country (or does not exist at all) is indistinguishable
                # to the caller -- both return the same safe
                # ORIGIN_NOT_FOUND, and `get_origin_analysis` is never
                # even called for it.
                return AnalysisTrendsContext(
                    status=AnalysisTrendsStatus.ORIGIN_NOT_FOUND.value, disease=disease_code, scope_country=ANALYSIS_TRENDS_COUNTRY,
                    historical_summary=historical_summary, historical_trend=historical_trend,
                    model_evaluation=model_evaluation, model_run_comparison=model_run_comparison,
                    confidence=confidence, drivers=drivers, generated_at=generated_at,
                )
            else:
                try:
                    snapshot = self._scientific_port.get_origin_analysis(origin_id, disease=resolved_display)
                except UnsupportedDiseaseError:
                    return AnalysisTrendsContext(
                        status=AnalysisTrendsStatus.UNSUPPORTED_DISEASE.value, disease=disease_code, scope_country=ANALYSIS_TRENDS_COUNTRY,
                        historical_summary=historical_summary, historical_trend=historical_trend,
                        model_evaluation=model_evaluation, model_run_comparison=model_run_comparison,
                        confidence=confidence, drivers=drivers, generated_at=generated_at,
                    )
                except RuntimeAnalysisError10A as exc:
                    if exc.status == "ORIGIN_NOT_FOUND":
                        return AnalysisTrendsContext(
                            status=AnalysisTrendsStatus.ORIGIN_NOT_FOUND.value, disease=disease_code, scope_country=ANALYSIS_TRENDS_COUNTRY,
                            historical_summary=historical_summary, historical_trend=historical_trend,
                            model_evaluation=model_evaluation, model_run_comparison=model_run_comparison,
                            confidence=confidence, drivers=drivers, generated_at=generated_at,
                        )
                    if exc.status == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY":
                        selected_origin_analytics = SelectedOriginAnalytics(
                            status=SelectedOriginAnalyticsStatus.ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY.value,
                            origin_id=origin_id, disease=disease_code, area_score_availability=AREA_SCORE_AVAILABILITY_STATUS,
                        )
                    else:
                        # Section 20 (`MyAreaContextService`'s own precedent):
                        # every OTHER real RuntimeAnalysisError10A status
                        # (e.g. no eligible source, scientific-domain/grid
                        # failure) is a genuine but unanticipated-by-this-
                        # checkpoint failure -- never silently treated as OK.
                        return AnalysisTrendsContext(
                            status=AnalysisTrendsStatus.ANALYSIS_INTERNAL_ERROR.value, disease=disease_code, scope_country=ANALYSIS_TRENDS_COUNTRY,
                            historical_summary=historical_summary, historical_trend=historical_trend,
                            model_evaluation=model_evaluation, model_run_comparison=model_run_comparison,
                            confidence=confidence, drivers=drivers, generated_at=generated_at,
                        )
                except Exception:
                    return AnalysisTrendsContext(
                        status=AnalysisTrendsStatus.ANALYSIS_INTERNAL_ERROR.value, disease=disease_code, scope_country=ANALYSIS_TRENDS_COUNTRY,
                        historical_summary=historical_summary, historical_trend=historical_trend,
                        model_evaluation=model_evaluation, model_run_comparison=model_run_comparison,
                        confidence=confidence, drivers=drivers, generated_at=generated_at,
                    )
                else:
                    selected_origin_analytics = self._build_selected_origin_analytics(origin_id, disease_code, snapshot)

        overall_status = AnalysisTrendsStatus.OK.value
        if historical_source_count == 0:
            overall_status = AnalysisTrendsStatus.NO_HISTORICAL_DATA.value
        elif selected_origin_analytics is not None and selected_origin_analytics.status != SelectedOriginAnalyticsStatus.AVAILABLE.value:
            overall_status = AnalysisTrendsStatus.PARTIAL.value

        return AnalysisTrendsContext(
            status=overall_status, disease=disease_code, scope_country=ANALYSIS_TRENDS_COUNTRY, historical_summary=historical_summary,
            historical_trend=historical_trend, selected_origin_analytics=selected_origin_analytics,
            model_evaluation=model_evaluation, model_run_comparison=model_run_comparison,
            confidence=confidence, drivers=drivers, generated_at=generated_at,
        )

    @staticmethod
    def _build_selected_origin_analytics(origin_id: str, disease_code: str, snapshot) -> SelectedOriginAnalytics:
        analysis = snapshot.analysis

        rate_ctx = analysis.apparent_rate_context or {}
        apparent_rate = ApparentRateAnalytics(
            status=ApparentRateStatus.AVAILABLE.value if rate_ctx else ApparentRateStatus.UNAVAILABLE_RUNTIME_METRIC.value,
            apparent_rate_km_day=rate_ctx.get("apparent_rate_km_day"), context=dict(rate_ctx) if rate_ctx else None,
        )

        direction_context = DirectionContext(
            status=DirectionContextStatus.UNAVAILABLE_RUNTIME_METRIC.value,
            reason=(
                "bearing_deg/directional_clarity are computed per grid cell only; no single "
                "scientifically defined origin-level bearing exists to report, and averaging "
                "per-cell bearings (circular data) would not be a valid aggregation"
            ),
        )

        reach_days = [
            NominalReachDayAnalytics(
                day=d.day, nominal_reach_km=d.nominal_reach_km,
                derived_interval_lower_km=d.derived_interval_lower_km, derived_interval_upper_km=d.derived_interval_upper_km,
            )
            for d in analysis.nominal_reach_by_day
        ]
        nominal_reach = NominalReachAnalytics(
            status=ApparentRateStatus.AVAILABLE.value if reach_days else ApparentRateStatus.UNAVAILABLE_RUNTIME_METRIC.value,
            disclaimer=NOMINAL_REACH_DISCLAIMER, days=reach_days,
        )

        rss_distribution = build_relative_spatial_score_distribution([cell.risk.raw_c0_score for cell in analysis.cells])

        return SelectedOriginAnalytics(
            status=SelectedOriginAnalyticsStatus.AVAILABLE.value,
            origin_id=origin_id, disease=disease_code,
            t0=analysis.analysis_metadata.t0, scientific_mode=analysis.analysis_metadata.temporal_mode,
            eligible_source_count=len(analysis.eligible_sources),
            apparent_rate=apparent_rate, direction_context=direction_context, nominal_reach=nominal_reach,
            relative_spatial_score_distribution=rss_distribution, area_score_availability=AREA_SCORE_AVAILABILITY_STATUS,
        )
