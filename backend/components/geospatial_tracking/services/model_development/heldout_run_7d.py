"""Checkpoint 7D: frozen held-out-from-fitting evaluation of the
Checkpoint 7C-selected C0 model.

**Not single-shot (Checkpoint 7D.1 correction)**: a 40-origin predictive
sanity subset was scored with this same function and inspected before
the final full 229-origin run -- see
`local_data/model_evaluation/7d/pre_final_40_origin_sanity_exposure.json`
and `heldout_protocol_7d.EVALUATION_LABEL_7D1_CORRECTED`. This module's
own code is unretuned across that exposure
(`NO_POST_EXPOSURE_NUMERICALLY_LOAD_BEARING_CODE_CHANGE_DETECTED_IN_RECORDED_SESSION`),
but calling any single real invocation of it "the first look" would be
false.

Mirrors `development_run_7b.py`/`development_run_7c.py` structurally
(same firewall pattern, same origin-completeness hard-stop, same
target-scope/coverage machinery, same primary metric/tie
semantics/bootstrap convention) but is radically simpler: no folds (one
evaluation set), no candidate registry (exactly one frozen candidate),
no host/wind (C0 needs neither). `assert_frozen_c0_model` (Part 2) is
called by the real-run script BEFORE each real scoring invocation of
this module.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ..forecast_target import build_forecast_targets
from ..geospatial.scientific_domain import build_scientific_evaluation_domain
from ..geospatial.scientific_grid import ScientificGridConfig
from ..model_fitting_exposure import assert_held_out_only
from .baseline_scoring import SCORED, CandidateCoverageRecord, compute_area_weighted_percentiles, compute_coverage_record, compute_target_cell_ranks
from .candidate_registry_7c import C0_FAMILY, Candidate7CSpec
from .development_run_7b import VALIDATION_ORIGIN_GRID_UNAVAILABLE, VALIDATION_ORIGIN_NO_ELIGIBLE_SOURCE, VALIDATION_ORIGIN_READY, _eligible_source_points, dedupe_targets_by_origin_and_event
from .development_run_7c import _grid_cell_dicts
from .evaluation_protocol_7b import (
    PRIMARY_SELECTION_ELIGIBLE,
    TOP5_THRESHOLD_PERCENTILE,
    TOP10_THRESHOLD_PERCENTILE,
    assess_candidate_coverage_eligibility,
)
from .local_evaluation_scope import (
    LOCAL_SCOPE_UNRESOLVED,
    OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE,
    WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE,
    classify_target_primary_scope,
)
from .selection_7b import clustered_bootstrap_ci, fold_origin_balanced_metrics, summarize_by_cluster
from .wind_scoring_7c import score_origin_candidates_7c

HELDOUT_EVALUATION_KEY = "HELD_OUT_FROM_MODEL_FITTING"


class HeldoutOriginCompletenessGateError(RuntimeError):
    """Part 5/17: raised the instant any held-out origin is not
    `VALIDATION_ORIGIN_READY`, or C0's coverage is unexpectedly
    incomplete -- never a silent drop, never a favorable denominator
    computed from scored cells only."""


class HeldoutCoverageIncompleteError(RuntimeError):
    """Part 17: C0 is a pure distance-geometry model and is expected to
    have complete domain coverage everywhere -- any real incompleteness
    is treated as a hard stop, never silently reported as if it were
    fine."""


@dataclass(frozen=True)
class TargetEvaluationRecord7D:
    forecast_origin_id: str
    country: str
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
            "forecast_origin_id": self.forecast_origin_id, "country": self.country, "candidate_id": self.candidate_id,
            "target_event_id": self.target_event_id, "target_id": self.target_id, "lead_days": self.lead_days,
            "target_grid_cell_id": self.target_grid_cell_id, "target_score": self.target_score,
            "area_weighted_target_percentile": self.area_weighted_target_percentile,
            "top5_capture": self.top5_capture, "top10_capture": self.top10_capture,
            "target_cell_rank": self.target_cell_rank, "valid_domain_area_km2": self.valid_domain_area_km2,
            "scored_domain_area_km2": self.scored_domain_area_km2, "model_input_status": self.model_input_status,
        }


@dataclass(frozen=True)
class OriginEvaluationOutcome7D:
    forecast_origin_id: str
    country: str
    status: str
    target_records: tuple
    coverage_records: tuple
    n_all_d1d7_target_rows: int
    n_within: int
    n_outside: int
    n_unresolved: int
    n_within_without_cell: int


def _evaluate_heldout_origin(
    repo, origin, *, disease: str, active_window_days: int, grid_config: ScientificGridConfig, c0_spec: Candidate7CSpec,
) -> OriginEvaluationOutcome7D:
    source_points = _eligible_source_points(repo, origin, disease=disease, active_window_days=active_window_days)
    if not source_points:
        return OriginEvaluationOutcome7D(origin.forecast_origin_id, origin.country, VALIDATION_ORIGIN_NO_ELIGIBLE_SOURCE, (), (), 0, 0, 0, 0, 0)

    evaluation_domain = build_scientific_evaluation_domain(
        forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, sources=source_points, grid_config=grid_config,
        primary_local_evaluation_distance_km=grid_config.domain_distance_km,
    )
    grid_cells = _grid_cell_dicts(evaluation_domain)
    if not grid_cells:
        return OriginEvaluationOutcome7D(origin.forecast_origin_id, origin.country, VALIDATION_ORIGIN_GRID_UNAVAILABLE, (), (), 0, 0, 0, 0, 0)

    targets = build_forecast_targets(repo, origin, disease=disease, source_ids_at_origin={s.source_id for s in source_points}, horizon_days=7)
    targets = dedupe_targets_by_origin_and_event([t for t in targets if t.risk_target_eligible])
    n_all = len(targets)

    within_targets, n_outside, n_unresolved = [], 0, 0
    for t in targets:
        scope = classify_target_primary_scope(target=t, sources=source_points, evaluation_domain=evaluation_domain)
        if scope.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE:
            within_targets.append((t, scope))
        elif scope.scope_status == OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE:
            n_outside += 1
        elif scope.scope_status == LOCAL_SCOPE_UNRESOLVED:
            n_unresolved += 1

    n_within_without_cell = sum(1 for _t, scope in within_targets if scope.target_grid_cell_id is None)
    if n_within_without_cell:
        # Part 9: every WITHIN target must have a valid scientific grid cell.
        raise HeldoutOriginCompletenessGateError(
            f"origin {origin.forecast_origin_id}: {n_within_without_cell} WITHIN-scope target(s) lack a valid "
            "scientific grid cell -- primary evaluation must STOP (Part 9)"
        )

    if not within_targets:
        return OriginEvaluationOutcome7D(
            origin.forecast_origin_id, origin.country, VALIDATION_ORIGIN_READY, (), (), n_all, 0, n_outside, n_unresolved, 0,
        )

    candidate_scores = score_origin_candidates_7c(grid_cells=grid_cells, sources=source_points, candidates=(c0_spec,), wind=None)
    cell_scores = candidate_scores[c0_spec.candidate_id]
    coverage = compute_coverage_record(cell_scores, forecast_origin_id=origin.forecast_origin_id, fold_id=HELDOUT_EVALUATION_KEY, candidate_id=c0_spec.candidate_id)
    percentiles = compute_area_weighted_percentiles(cell_scores)
    ranks = compute_target_cell_ranks(cell_scores)
    by_id = {c.grid_cell_id: c for c in cell_scores}

    records: list[TargetEvaluationRecord7D] = []
    for target, scope in within_targets:
        gcid = scope.target_grid_cell_id
        cell = by_id.get(gcid)
        if cell is None or cell.status != SCORED:
            records.append(TargetEvaluationRecord7D(
                forecast_origin_id=origin.forecast_origin_id, country=origin.country, candidate_id=c0_spec.candidate_id,
                target_event_id=target.target_event_id, target_id=target.target_id, lead_days=target.lead_days,
                target_grid_cell_id=gcid, target_score=None, area_weighted_target_percentile=None,
                top5_capture=None, top10_capture=None, target_cell_rank=None,
                valid_domain_area_km2=coverage.declared_domain_area_km2, scored_domain_area_km2=coverage.scored_domain_area_km2,
                model_input_status="TARGET_SCORE_UNAVAILABLE",
            ))
            continue
        pct = percentiles.get(gcid)
        records.append(TargetEvaluationRecord7D(
            forecast_origin_id=origin.forecast_origin_id, country=origin.country, candidate_id=c0_spec.candidate_id,
            target_event_id=target.target_event_id, target_id=target.target_id, lead_days=target.lead_days,
            target_grid_cell_id=gcid, target_score=cell.score, area_weighted_target_percentile=pct,
            top5_capture=(pct >= TOP5_THRESHOLD_PERCENTILE) if pct is not None else None,
            top10_capture=(pct >= TOP10_THRESHOLD_PERCENTILE) if pct is not None else None,
            target_cell_rank=ranks.get(gcid), valid_domain_area_km2=coverage.declared_domain_area_km2,
            scored_domain_area_km2=coverage.scored_domain_area_km2, model_input_status=SCORED,
        ))

    return OriginEvaluationOutcome7D(
        origin.forecast_origin_id, origin.country, VALIDATION_ORIGIN_READY, tuple(records), (coverage,), n_all, len(within_targets), n_outside, n_unresolved, 0,
    )


@dataclass(frozen=True)
class Checkpoint7DResult:
    origin_completeness: dict
    target_scope_audit: dict
    coverage_summary: dict
    d1_d7_metrics: dict
    bootstrap_by_origin: dict
    bootstrap_by_target_event: dict
    country_diagnostic_metrics: list
    n_unique_heldout_target_events: int
    n_target_score_unavailable_rows: int
    coverage_records: list
    all_records: list
    runtime_seconds: float


def run_checkpoint_7d_heldout_evaluation(
    repo, *, heldout_origins: list, disease: str, active_window_days: int, grid_config: ScientificGridConfig, c0_spec: Candidate7CSpec,
) -> Checkpoint7DResult:
    assert_held_out_only(heldout_origins, caller="run_checkpoint_7d_heldout_evaluation")
    t_start = time.monotonic()

    ready_ids: list = []
    blocked: dict = {}
    all_records: list[TargetEvaluationRecord7D] = []
    all_coverage: list[CandidateCoverageRecord] = []
    n_all_target_rows = n_within_total = n_outside_total = n_unresolved_total = 0

    for origin in heldout_origins:
        outcome = _evaluate_heldout_origin(repo, origin, disease=disease, active_window_days=active_window_days, grid_config=grid_config, c0_spec=c0_spec)
        if outcome.status == VALIDATION_ORIGIN_READY:
            ready_ids.append(outcome.forecast_origin_id)
        else:
            blocked[outcome.forecast_origin_id] = outcome.status
        all_records.extend(outcome.target_records)
        all_coverage.extend(outcome.coverage_records)
        n_all_target_rows += outcome.n_all_d1d7_target_rows
        n_within_total += outcome.n_within
        n_outside_total += outcome.n_outside
        n_unresolved_total += outcome.n_unresolved

    assert len(ready_ids) + len(blocked) == len(heldout_origins)
    origin_completeness = {
        HELDOUT_EVALUATION_KEY: {
            "intended_evaluation_origin_count": len(heldout_origins), "ready_origin_count": len(ready_ids),
            "blocked_origin_count": len(blocked), "blocked_origins": blocked,
        }
    }
    if blocked:
        detail = "; ".join(f"{oid}={status}" for oid, status in sorted(blocked.items()))
        raise HeldoutOriginCompletenessGateError(f"{len(blocked)} blocked held-out origin(s), no silent drop allowed: {detail}")

    n_unique_target_events = len({(r.forecast_origin_id, r.target_event_id) for r in all_records})
    n_unavailable = sum(1 for r in all_records if r.model_input_status != SCORED)

    max_missing = max((c.missing_domain_area_km2 for c in all_coverage), default=0.0)
    eligibility = assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=n_unavailable, max_missing_domain_area_km2=max_missing)
    coverage_summary = {c0_spec.candidate_id: {"max_missing_domain_area_km2": max_missing, "n_target_score_unavailable_rows": n_unavailable, "eligibility": eligibility}}
    if eligibility != PRIMARY_SELECTION_ELIGIBLE:
        # Part 17: C0 is expected to have complete domain support -- any
        # real incompleteness is a hard stop, never a favorable
        # denominator computed from scored cells only.
        raise HeldoutCoverageIncompleteError(
            f"C0's held-out coverage is unexpectedly incomplete: {coverage_summary[c0_spec.candidate_id]} -- STOP, per Part 17"
        )

    target_scope_audit = {
        "n_all_d1d7_target_rows": n_all_target_rows, "n_within": n_within_total, "n_outside": n_outside_total,
        "n_unresolved": n_unresolved_total, "n_within_targets_without_grid_cell": 0,
        "n_unique_heldout_target_events": n_unique_target_events,
    }

    d1_d7_metrics: dict = {}
    for lead in range(1, 8):
        lead_records = [r for r in all_records if r.lead_days == lead]
        origin_summaries = summarize_by_cluster(lead_records, cluster_key_fn=lambda r: r.forecast_origin_id)
        d1_d7_metrics[f"D{lead}"] = {
            **fold_origin_balanced_metrics(origin_summaries), "n_target_rows": len(lead_records),
            "n_scored": sum(1 for r in lead_records if r.model_input_status == SCORED),
            "n_target_score_unavailable": sum(1 for r in lead_records if r.model_input_status != SCORED),
        }
    pooled_summaries = summarize_by_cluster(all_records, cluster_key_fn=lambda r: r.forecast_origin_id)
    d1_d7_metrics["POOLED_D1_D7"] = {
        **fold_origin_balanced_metrics(pooled_summaries), "n_target_rows": len(all_records),
        "n_scored": sum(1 for r in all_records if r.model_input_status == SCORED),
        "n_target_score_unavailable": sum(1 for r in all_records if r.model_input_status != SCORED),
    }

    bootstrap_by_origin = clustered_bootstrap_ci(cluster_summaries=pooled_summaries)
    event_summaries = summarize_by_cluster(all_records, cluster_key_fn=lambda r: r.target_event_id)
    bootstrap_by_target_event = clustered_bootstrap_ci(cluster_summaries=event_summaries)

    # Part 16: country-level diagnostic, computed AFTER the pooled result
    # is fixed -- descriptive only, never used to modify the model.
    countries = sorted({r.country for r in all_records})
    country_diagnostic_metrics: list = []
    for country in countries:
        c_records = [r for r in all_records if r.country == country]
        c_origins = sorted({r.forecast_origin_id for r in c_records})
        c_summaries = summarize_by_cluster(c_records, cluster_key_fn=lambda r: r.forecast_origin_id)
        m = fold_origin_balanced_metrics(c_summaries)
        country_diagnostic_metrics.append({
            "country": country, "n_origins": len(c_origins), "n_targets": len({(r.forecast_origin_id, r.target_event_id) for r in c_records}),
            "mean_target_percentile": m["mean_target_percentile"], "top5_capture_rate": m["top5_capture_rate"], "top10_capture_rate": m["top10_capture_rate"],
            "descriptive_only": True,
        })

    return Checkpoint7DResult(
        origin_completeness=origin_completeness, target_scope_audit=target_scope_audit, coverage_summary=coverage_summary,
        d1_d7_metrics=d1_d7_metrics, bootstrap_by_origin=bootstrap_by_origin, bootstrap_by_target_event=bootstrap_by_target_event,
        country_diagnostic_metrics=country_diagnostic_metrics, n_unique_heldout_target_events=n_unique_target_events,
        n_target_score_unavailable_rows=n_unavailable, coverage_records=[c.as_dict() for c in all_coverage],
        all_records=[r.as_dict() for r in all_records], runtime_seconds=time.monotonic() - t_start,
    )
