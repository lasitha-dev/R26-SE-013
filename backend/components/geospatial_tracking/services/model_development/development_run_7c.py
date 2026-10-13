"""Checkpoint 7C: top-level orchestration -- nested chronological
FIT_DEVELOPMENT-only wind-anisotropic augmentation of the frozen 7B
baseline.

Mirrors `development_run_7b.run_checkpoint_7b_development` structurally
(same firewall, same `build_calendar_year_folds` reuse, same blocked-
origin hard-stop gate, same coverage-eligibility philosophy) but is
HOST-FREE: no raw host snapshot cache, no fold-safe reference -- C0/CW
candidates never read `Host_i` (Part 5). The scientific grid itself
comes directly from `scientific_domain.build_scientific_evaluation_domain`
(the SAME frozen 5km/25km domain 7B used), never `services.features`'s
older `build_smoke_grid`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ...schemas import ValidationMode  # noqa: F401 -- re-exported for parity with development_run_7b's import surface
from ..forecast_target import build_forecast_targets
from ..geospatial.scientific_domain import build_scientific_evaluation_domain
from ..geospatial.scientific_grid import ScientificGridConfig
from ..model_fitting_exposure import assert_fit_development_only, build_calendar_year_folds
from .baseline_scoring import SCORED, CandidateCoverageRecord, compute_area_weighted_percentiles, compute_coverage_record, compute_target_cell_ranks
from .candidate_registry_7c import C0_FAMILY, Candidate7CSpec, build_candidate_registry_7c
from .development_run_7b import (
    VALIDATION_ORIGIN_GRID_UNAVAILABLE,
    VALIDATION_ORIGIN_NO_ELIGIBLE_SOURCE,
    VALIDATION_ORIGIN_READY,
    ValidationOriginCompletenessGateError,
    _eligible_source_points,
    assert_validation_origin_completeness,
    dedupe_targets_by_origin_and_event,
)
from .evaluation_protocol_7b import TOP10_THRESHOLD_PERCENTILE, TOP5_THRESHOLD_PERCENTILE, assess_candidate_coverage_eligibility
from .evaluation_protocol_7c import PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE, PRIMARY_SELECTION_ELIGIBLE, classify_selection_note_7c
from .local_evaluation_scope import WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE, classify_target_primary_scope
from .paired_comparison_7c import compute_paired_delta_vs_anchor, paired_bootstrap_ci
from .selection_7b import clustered_bootstrap_ci, fold_origin_balanced_metrics, overall_equal_origin_weighted, select_candidate, summarize_by_cluster
from .wind_readiness_7c import resolve_origin_wind
from .wind_scoring_7c import score_origin_candidates_7c

VALIDATION_ORIGIN_WEATHER_UNAVAILABLE = "VALIDATION_ORIGIN_WEATHER_UNAVAILABLE"


@dataclass(frozen=True)
class TargetEvaluationRecord7C:
    forecast_origin_id: str
    fold_id: str
    candidate_id: str
    target_event_id: str
    target_id: str
    lead_days: int
    target_grid_cell_id: str | None
    target_score: float | None
    area_weighted_target_percentile: float | None
    top5_capture: bool | None
    top10_capture: bool | None
    target_cell_rank: int | None
    valid_domain_area_km2: float
    scored_domain_area_km2: float
    model_input_status: str

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id, "fold_id": self.fold_id, "candidate_id": self.candidate_id,
            "target_event_id": self.target_event_id, "target_id": self.target_id, "lead_days": self.lead_days,
            "target_grid_cell_id": self.target_grid_cell_id, "target_score": self.target_score,
            "area_weighted_target_percentile": self.area_weighted_target_percentile,
            "top5_capture": self.top5_capture, "top10_capture": self.top10_capture,
            "target_cell_rank": self.target_cell_rank, "valid_domain_area_km2": self.valid_domain_area_km2,
            "scored_domain_area_km2": self.scored_domain_area_km2, "model_input_status": self.model_input_status,
        }


def _grid_cell_dicts(evaluation_domain) -> list[dict]:
    return [
        {
            "grid_cell_id": c.grid_cell_id, "scientific_cell_id": c.scientific_cell_id,
            "area_km2": c.area_km2, "domain_overlap_area_km2": c.domain_overlap_area_km2,
            "centroid_lat": c.centroid_lat, "centroid_lon": c.centroid_lon,
        }
        for c in evaluation_domain.all_cells()
    ]


@dataclass(frozen=True)
class OriginEvaluationOutcome7C:
    forecast_origin_id: str
    status: str
    target_records: tuple
    coverage_records: tuple
    n_within_scope_targets: int
    n_evaluable_target_events: int
    wind_status: str | None


def _evaluate_validation_origin_7c(
    repo, origin, *, fold_id: str, disease: str, active_window_days: int, grid_config: ScientificGridConfig,
    candidates: tuple[Candidate7CSpec, ...], weather_cache,
) -> OriginEvaluationOutcome7C:
    source_points = _eligible_source_points(repo, origin, disease=disease, active_window_days=active_window_days)
    if not source_points:
        return OriginEvaluationOutcome7C(origin.forecast_origin_id, VALIDATION_ORIGIN_NO_ELIGIBLE_SOURCE, (), (), 0, 0, None)

    evaluation_domain = build_scientific_evaluation_domain(
        forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, sources=source_points, grid_config=grid_config,
        primary_local_evaluation_distance_km=grid_config.domain_distance_km,
    )
    grid_cells = _grid_cell_dicts(evaluation_domain)
    if not grid_cells:
        return OriginEvaluationOutcome7C(origin.forecast_origin_id, VALIDATION_ORIGIN_GRID_UNAVAILABLE, (), (), 0, 0, None)

    targets = build_forecast_targets(repo, origin, disease=disease, source_ids_at_origin={s.source_id for s in source_points}, horizon_days=7)
    targets = dedupe_targets_by_origin_and_event([t for t in targets if t.risk_target_eligible])
    within_targets = []
    for t in targets:
        scope = classify_target_primary_scope(target=t, sources=source_points, evaluation_domain=evaluation_domain)
        if scope.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE:
            within_targets.append((t, scope))

    n_within = len(within_targets)
    n_evaluable_events = sum(1 for _t, scope in within_targets if scope.target_grid_cell_id is not None)

    if not within_targets:
        return OriginEvaluationOutcome7C(origin.forecast_origin_id, VALIDATION_ORIGIN_READY, (), (), n_within, n_evaluable_events, None)

    wind_result = resolve_origin_wind(
        forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, trigger_source_ids_at_t0=origin.trigger_source_ids_at_t0,
        sources=source_points, weather_cache=weather_cache,
    )
    candidate_scores = score_origin_candidates_7c(grid_cells=grid_cells, sources=source_points, candidates=candidates, wind=wind_result.wind)

    records: list[TargetEvaluationRecord7C] = []
    coverage_records: list[CandidateCoverageRecord] = []
    for candidate in candidates:
        cell_scores = candidate_scores[candidate.candidate_id]
        coverage = compute_coverage_record(cell_scores, forecast_origin_id=origin.forecast_origin_id, fold_id=fold_id, candidate_id=candidate.candidate_id)
        coverage_records.append(coverage)
        percentiles = compute_area_weighted_percentiles(cell_scores)
        ranks = compute_target_cell_ranks(cell_scores)
        by_id = {c.grid_cell_id: c for c in cell_scores}

        for target, scope in within_targets:
            gcid = scope.target_grid_cell_id
            cell = by_id.get(gcid) if gcid is not None else None
            if gcid is None or cell is None or cell.status != SCORED:
                records.append(TargetEvaluationRecord7C(
                    forecast_origin_id=origin.forecast_origin_id, fold_id=fold_id, candidate_id=candidate.candidate_id,
                    target_event_id=target.target_event_id, target_id=target.target_id, lead_days=target.lead_days,
                    target_grid_cell_id=gcid, target_score=None, area_weighted_target_percentile=None,
                    top5_capture=None, top10_capture=None, target_cell_rank=None,
                    valid_domain_area_km2=coverage.declared_domain_area_km2, scored_domain_area_km2=coverage.scored_domain_area_km2,
                    model_input_status="TARGET_SCORE_UNAVAILABLE",
                ))
                continue
            pct = percentiles.get(gcid)
            records.append(TargetEvaluationRecord7C(
                forecast_origin_id=origin.forecast_origin_id, fold_id=fold_id, candidate_id=candidate.candidate_id,
                target_event_id=target.target_event_id, target_id=target.target_id, lead_days=target.lead_days,
                target_grid_cell_id=gcid, target_score=cell.score, area_weighted_target_percentile=pct,
                top5_capture=(pct >= TOP5_THRESHOLD_PERCENTILE) if pct is not None else None,
                top10_capture=(pct >= TOP10_THRESHOLD_PERCENTILE) if pct is not None else None,
                target_cell_rank=ranks.get(gcid), valid_domain_area_km2=coverage.declared_domain_area_km2,
                scored_domain_area_km2=coverage.scored_domain_area_km2, model_input_status=SCORED,
            ))
    return OriginEvaluationOutcome7C(
        origin.forecast_origin_id, VALIDATION_ORIGIN_READY, tuple(records), tuple(coverage_records), n_within, n_evaluable_events, wind_result.status,
    )


@dataclass(frozen=True)
class Checkpoint7CResult:
    fold_manifest: list
    insufficient_history_folds: list
    validation_origin_completeness: dict
    candidate_overall_metrics: dict
    candidate_coverage_summary: dict
    eligible_candidate_ids: tuple
    ineligible_candidate_ids: tuple
    selection_note: str
    selected_candidate_id: str
    selection_tie_break_reason: str
    selected_candidate_spec: dict
    d1_d7_metrics: dict
    bootstrap_by_origin: dict
    bootstrap_by_target_event: dict
    paired_delta_vs_c0: dict  # candidate_id -> delta dict (eligible candidates only, excluding C0 itself)
    paired_delta_bootstrap_vs_c0: dict  # candidate_id -> paired bootstrap CI dict
    n_unique_validation_targets_within_scope: int
    n_unique_evaluable_origin_target_events: int
    n_candidate_target_evaluation_rows: int
    n_candidate_target_score_unavailable_rows: int
    per_candidate_evaluable_target_count: dict
    per_candidate_unavailable_target_count: dict
    coverage_records: list
    wind_status_by_origin: dict
    runtime_seconds: float
    per_fold_runtime_seconds: dict


def run_checkpoint_7c_development(
    repo, *, fit_development_origins: list, disease: str, active_window_days: int, grid_config: ScientificGridConfig, weather_cache=None,
) -> Checkpoint7CResult:
    assert_fit_development_only(fit_development_origins, caller="run_checkpoint_7c_development")
    t_start = time.monotonic()

    by_id = {o.forecast_origin_id: o for o in fit_development_origins}
    calendar_folds = build_calendar_year_folds(fit_development_origins)
    candidates = build_candidate_registry_7c()

    insufficient: list = []
    usable_folds: list = []
    for f in calendar_folds:
        if not f.training_origin_ids:
            insufficient.append(f.fold_id)
            continue
        usable_folds.append(f)

    fold_manifest = [
        {"fold_id": f.fold_id, "training_origin_ids": f.training_origin_ids, "validation_origin_ids": f.validation_origin_ids,
         "purged_origin_ids": f.purged_origin_ids}
        for f in calendar_folds
    ]

    all_records: list[TargetEvaluationRecord7C] = []
    all_coverage: list[CandidateCoverageRecord] = []
    validation_origin_completeness: dict = {}
    per_fold_runtime: dict = {}
    wind_status_by_origin: dict = {}
    n_unique_within_scope = 0
    n_unique_evaluable_events = 0

    for f in usable_folds:
        t_fold_start = time.monotonic()
        validation_origins = [by_id[oid] for oid in f.validation_origin_ids]

        ready_ids: list = []
        blocked: dict = {}
        for origin in validation_origins:
            outcome = _evaluate_validation_origin_7c(
                repo, origin, fold_id=f.fold_id, disease=disease, active_window_days=active_window_days,
                grid_config=grid_config, candidates=candidates, weather_cache=weather_cache,
            )
            if outcome.status == VALIDATION_ORIGIN_READY:
                ready_ids.append(outcome.forecast_origin_id)
            else:
                blocked[outcome.forecast_origin_id] = outcome.status
            all_records.extend(outcome.target_records)
            all_coverage.extend(outcome.coverage_records)
            n_unique_within_scope += outcome.n_within_scope_targets
            n_unique_evaluable_events += outcome.n_evaluable_target_events
            if outcome.wind_status is not None:
                wind_status_by_origin[outcome.forecast_origin_id] = outcome.wind_status

        assert len(ready_ids) + len(blocked) == len(f.validation_origin_ids)
        validation_origin_completeness[f.fold_id] = {
            "intended_validation_origin_count": len(f.validation_origin_ids), "ready_origin_count": len(ready_ids),
            "blocked_origin_count": len(blocked), "blocked_origins": blocked,
        }
        per_fold_runtime[f.fold_id] = time.monotonic() - t_fold_start

    assert_validation_origin_completeness(validation_origin_completeness)

    n_unavailable = sum(1 for r in all_records if r.model_input_status != SCORED)

    candidate_overall_metrics: dict = {}
    candidate_origin_summaries: dict = {}  # candidate_id -> ClusterSummary tuple (for paired-delta matching)
    per_candidate_evaluable: dict = {}
    per_candidate_unavailable: dict = {}
    candidate_coverage_summary: dict = {}
    for candidate in candidates:
        cand_records = [r for r in all_records if r.candidate_id == candidate.candidate_id]
        per_candidate_evaluable[candidate.candidate_id] = sum(1 for r in cand_records if r.model_input_status == SCORED)
        per_candidate_unavailable[candidate.candidate_id] = sum(1 for r in cand_records if r.model_input_status != SCORED)

        cand_coverage = [c for c in all_coverage if c.candidate_id == candidate.candidate_id]
        max_missing = max((c.missing_domain_area_km2 for c in cand_coverage), default=0.0)
        eligibility = assess_candidate_coverage_eligibility(
            n_target_score_unavailable_rows=per_candidate_unavailable[candidate.candidate_id], max_missing_domain_area_km2=max_missing,
        )
        candidate_coverage_summary[candidate.candidate_id] = {
            "max_missing_domain_area_km2": max_missing, "n_target_score_unavailable_rows": per_candidate_unavailable[candidate.candidate_id],
            "eligibility": eligibility,
        }

        fold_metrics = []
        for f in usable_folds:
            fold_records = [r for r in cand_records if r.fold_id == f.fold_id]
            origin_summaries = summarize_by_cluster(fold_records, cluster_key_fn=lambda r: r.forecast_origin_id)
            fold_metrics.append(fold_origin_balanced_metrics(origin_summaries))
        candidate_overall_metrics[candidate.candidate_id] = overall_equal_origin_weighted(fold_metrics)
        candidate_origin_summaries[candidate.candidate_id] = summarize_by_cluster(cand_records, cluster_key_fn=lambda r: r.forecast_origin_id)

    eligible_ids = tuple(sorted(cid for cid, s in candidate_coverage_summary.items() if s["eligibility"] == PRIMARY_SELECTION_ELIGIBLE))
    ineligible_ids = tuple(sorted(cid for cid in candidate_overall_metrics if cid not in eligible_ids))

    candidate_families_by_id = {c.candidate_id: c.family for c in candidates}
    selection_note = classify_selection_note_7c(
        candidate_families_by_id=candidate_families_by_id, eligible_candidate_ids=eligible_ids, ineligible_candidate_ids=ineligible_ids,
    )
    if selection_note == PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE:
        raise ValueError(
            f"{PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE}: 0 of {len(candidates)} candidates were "
            "PRIMARY_SELECTION_ELIGIBLE -- selection cannot proceed"
        )

    eligible_metrics = {cid: m for cid, m in candidate_overall_metrics.items() if cid in eligible_ids}
    selected_id, tie_reason = select_candidate(eligible_metrics)
    selected_spec = next(c for c in candidates if c.candidate_id == selected_id)

    c0_spec = next(c for c in candidates if c.family == C0_FAMILY)
    c0_summaries = candidate_origin_summaries[c0_spec.candidate_id]
    paired_delta_vs_c0: dict = {}
    paired_delta_bootstrap_vs_c0: dict = {}
    for cid in eligible_ids:
        if cid == c0_spec.candidate_id:
            continue
        delta = compute_paired_delta_vs_anchor(anchor_summaries=c0_summaries, candidate_summaries=candidate_origin_summaries[cid])
        paired_delta_vs_c0[cid] = {k: v for k, v in delta.items() if k != "per_origin_percentile_deltas"}
        paired_delta_bootstrap_vs_c0[cid] = paired_bootstrap_ci(delta["per_origin_percentile_deltas"])

    selected_records = [r for r in all_records if r.candidate_id == selected_id]
    d1_d7_metrics: dict = {}
    for lead in range(1, 8):
        lead_records = [r for r in selected_records if r.lead_days == lead]
        origin_summaries = summarize_by_cluster(lead_records, cluster_key_fn=lambda r: r.forecast_origin_id)
        d1_d7_metrics[f"D{lead}"] = {
            **fold_origin_balanced_metrics(origin_summaries), "n_target_rows": len(lead_records),
            "n_scored": sum(1 for r in lead_records if r.model_input_status == SCORED),
            "n_target_score_unavailable": sum(1 for r in lead_records if r.model_input_status != SCORED),
        }
    pooled_summaries = summarize_by_cluster(selected_records, cluster_key_fn=lambda r: r.forecast_origin_id)
    d1_d7_metrics["POOLED_D1_D7"] = {
        **fold_origin_balanced_metrics(pooled_summaries), "n_target_rows": len(selected_records),
        "n_scored": sum(1 for r in selected_records if r.model_input_status == SCORED),
        "n_target_score_unavailable": sum(1 for r in selected_records if r.model_input_status != SCORED),
    }

    bootstrap_by_origin = clustered_bootstrap_ci(cluster_summaries=pooled_summaries)
    event_summaries = summarize_by_cluster(selected_records, cluster_key_fn=lambda r: r.target_event_id)
    bootstrap_by_target_event = clustered_bootstrap_ci(cluster_summaries=event_summaries)

    return Checkpoint7CResult(
        fold_manifest=fold_manifest, insufficient_history_folds=insufficient,
        validation_origin_completeness=validation_origin_completeness,
        candidate_overall_metrics=candidate_overall_metrics, candidate_coverage_summary=candidate_coverage_summary,
        eligible_candidate_ids=eligible_ids, ineligible_candidate_ids=ineligible_ids, selection_note=selection_note,
        selected_candidate_id=selected_id, selection_tie_break_reason=tie_reason, selected_candidate_spec=selected_spec.as_dict(),
        d1_d7_metrics=d1_d7_metrics, bootstrap_by_origin=bootstrap_by_origin, bootstrap_by_target_event=bootstrap_by_target_event,
        paired_delta_vs_c0=paired_delta_vs_c0, paired_delta_bootstrap_vs_c0=paired_delta_bootstrap_vs_c0,
        n_unique_validation_targets_within_scope=n_unique_within_scope, n_unique_evaluable_origin_target_events=n_unique_evaluable_events,
        n_candidate_target_evaluation_rows=len(all_records), n_candidate_target_score_unavailable_rows=n_unavailable,
        per_candidate_evaluable_target_count=per_candidate_evaluable, per_candidate_unavailable_target_count=per_candidate_unavailable,
        coverage_records=[c.as_dict() for c in all_coverage], wind_status_by_origin=wind_status_by_origin,
        runtime_seconds=time.monotonic() - t_start, per_fold_runtime_seconds=per_fold_runtime,
    )
