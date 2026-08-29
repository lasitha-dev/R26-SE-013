"""Checkpoint 7B Parts 1-3, 17, 22, 24, 28, 30-32 (+ finalization hardening
Parts 3-4, 6-7, 11-12): top-level orchestration -- nested chronological
FIT_DEVELOPMENT-only baseline development.

`run_checkpoint_7b_development` is the ONLY safe real entry point (mirrors
`host_reference_rebuild.build_scientific_grid_host_reference_development_report`):
firewalled at its OWN entry point (Part 2) before any repository/raster
access, builds calendar-year expanding-window folds (Part 3, reusing
`model_fitting_exposure.build_calendar_year_folds` -- never a random
split), builds the ONE raw host-observation pass over the whole
`FIT_DEVELOPMENT` universe (Part 5, disk-cached -- see `fold_reference.py`),
then for each fold builds a fold-safe training-only reference (Part 4) and
scores every WITHIN-scope D1-D7 validation target (Part 17) against all 24
frozen candidates (Part 28).

**Finalization hardening (Parts 3-4, 6-7, 12)**: every validation origin's
outcome is tracked explicitly (`VALIDATION_ORIGIN_READY` /
`_RAW_SNAPSHOT_MISSING` / `_NO_ELIGIBLE_SOURCE` / `_GRID_UNAVAILABLE`) so no
intended validation origin can silently vanish from the denominator; every
(origin, fold, candidate) domain-coverage record is preserved (never
computed-and-discarded); unique WITHIN-scope target counts are reported
separately from the 24x-multiplied candidate-target row counts; and
candidate selection is now restricted to `PRIMARY_SELECTION_ELIGIBLE`
candidates only (Part 4) -- a host-dependent candidate excluded for
incomplete domain coverage is never silently treated as having "lost" to
a fully-covered one.

`HELD_OUT_FROM_MODEL_FITTING`/`SRI_LANKA_TRANSFER_CASE_STUDY` predictive
performance is never computed anywhere in this module (Part 32) -- the
firewall accepts only an already-`FIT_DEVELOPMENT`-only origin list, and
every downstream fold is built exclusively from it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ...domain.enums import RecordDomainScope
from ...schemas import ValidationMode
from ..factors.transform_config import FactorTransformConfig
from ..forecast_origin import ForecastOrigin
from ..forecast_target import build_forecast_targets
from ..geospatial.raster import LOCAL_GIS_CACHE_DIR
from ..geospatial.scientific_domain import build_scientific_evaluation_domain
from ..geospatial.scientific_grid import ScientificGridConfig
from ..geospatial.source_geometry import EligibleSourcePoint
from ..model_fitting_exposure import assert_fit_development_only, build_calendar_year_folds
from ..source_selector import get_eligible_sources
from .baseline_scoring import (
    MODEL_INPUT_INCOMPLETE,
    SCORED,
    TARGET_SCORE_UNAVAILABLE,
    CandidateCoverageRecord,
    compute_area_weighted_percentiles,
    compute_coverage_record,
    compute_target_cell_ranks,
    score_origin_all_candidates,
)
from .candidate_registry_7b import build_candidate_registry
from .evaluation_protocol_7b import (
    PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE,
    PRIMARY_SELECTION_ELIGIBLE,
    TOP10_THRESHOLD_PERCENTILE,
    TOP5_THRESHOLD_PERCENTILE,
    assess_candidate_coverage_eligibility,
    classify_selection_note,
)
from .fold_reference import build_fold_safe_reference, build_raw_host_snapshots_cached, snapshot_unsafe_component_count
from .local_evaluation_scope import WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE, classify_target_primary_scope
from .selection_7b import (
    clustered_bootstrap_ci,
    fold_origin_balanced_metrics,
    overall_equal_origin_weighted,
    select_candidate,
    summarize_by_cluster,
)

INSUFFICIENT_PRIOR_TRAINING_HISTORY = "INSUFFICIENT_PRIOR_TRAINING_HISTORY"

VALIDATION_ORIGIN_READY = "VALIDATION_ORIGIN_READY"
VALIDATION_ORIGIN_RAW_SNAPSHOT_MISSING = "VALIDATION_ORIGIN_RAW_SNAPSHOT_MISSING"
VALIDATION_ORIGIN_NO_ELIGIBLE_SOURCE = "VALIDATION_ORIGIN_NO_ELIGIBLE_SOURCE"
VALIDATION_ORIGIN_GRID_UNAVAILABLE = "VALIDATION_ORIGIN_GRID_UNAVAILABLE"

# Part 3 (finalization hardening): CWD-independent -- derived from the
# SAME canonical, `__file__`-anchored repository-root local_data constant
# every other real GIS/model-development script already uses
# (`services/geospatial/raster.py`'s `LOCAL_GIS_CACHE_DIR`), never a bare
# `Path("local_data")` that silently resolves relative to whatever the
# current process's working directory happens to be.
DEFAULT_RAW_HOST_SNAPSHOT_CACHE_DIR = LOCAL_GIS_CACHE_DIR.parent / "model_development" / "7b" / "raw_host_snapshot_cache"

VALIDATION_ORIGIN_COMPLETENESS_GATE_FAILED = "VALIDATION_ORIGIN_COMPLETENESS_GATE_FAILED"


class ValidationOriginCompletenessGateError(RuntimeError):
    """Part 2 (finalization hardening): raised the instant ANY intended
    validation origin, in ANY usable fold, is not `VALIDATION_ORIGIN_READY`
    -- candidate selection, D1-D7 metrics, bootstrap uncertainty, and
    `FrozenBaselineModelSpecification` creation must never be reached
    while `total_blocked_validation_origins > 0`. The origin is never
    silently dropped and selection continued on the remainder."""

    def __init__(self, blocked_details: list):
        self.blocked_details = blocked_details
        super().__init__(
            f"{VALIDATION_ORIGIN_COMPLETENESS_GATE_FAILED}: {len(blocked_details)} blocked validation origin(s) -- "
            "selection cannot proceed until every intended validation origin is VALIDATION_ORIGIN_READY: "
            + "; ".join(f"{d['fold_id']}/{d['forecast_origin_id']}={d['status']}" for d in blocked_details)
        )


def assert_validation_origin_completeness(validation_origin_completeness: dict) -> None:
    """Pure: raises `ValidationOriginCompletenessGateError` (preserving
    `fold_id`/`forecast_origin_id`/block reason for every blocked origin)
    if any fold has a nonzero `blocked_origin_count`; otherwise returns
    `None`. `validation_origin_completeness`: the same
    `{fold_id: {..., "blocked_origins": {origin_id: status}}}` shape
    `run_checkpoint_7b_development` already builds."""
    blocked_details: list = []
    for fold_id, comp in sorted(validation_origin_completeness.items()):
        for origin_id, status in sorted((comp.get("blocked_origins") or {}).items()):
            blocked_details.append({"fold_id": fold_id, "forecast_origin_id": origin_id, "status": status})
    if blocked_details:
        raise ValidationOriginCompletenessGateError(blocked_details)


@dataclass(frozen=True)
class TargetEvaluationRecord:
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
    model_input_status: str  # SCORED | TARGET_SCORE_UNAVAILABLE (own cell incomplete or unassigned)

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


def dedupe_targets_by_origin_and_event(targets: list) -> list:
    """UNIT7B-01 / Part 11: primary uniqueness is
    (`forecast_origin_id`, `target_event_id`) -- NOT the `target_id`
    display string. `target_id` is built as `f"{forecast_origin_id}::{target_event_id}"`
    (`services/forecast_target.py`); a delimiter-based join is not a
    PROVEN collision-free 1:1 encoding in general (either field could in
    principle contain the `::` delimiter), so this function dedupes on
    the actual tuple directly rather than trusting the joined string.
    Order-preserving: the FIRST occurrence of a given
    (origin, event) pair is kept. Never collapses the same event across
    DIFFERENT forecast origins -- the origin id is always part of the key."""
    seen: set = set()
    out = []
    for t in targets:
        key = (t.forecast_origin_id, t.target_event_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _eligible_source_points(repo, origin: ForecastOrigin, *, disease: str, active_window_days: int) -> list:
    result = get_eligible_sources(
        repo, disease=disease, t0=origin.t0, active_window_days=active_window_days,
        temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=origin.country, domain_scope=RecordDomainScope.HISTORICAL_ONLY,
    )
    return [EligibleSourcePoint(source_id=s.source_id, latitude=s.latitude, longitude=s.longitude) for s in result.sources]


@dataclass(frozen=True)
class OriginEvaluationOutcome:
    forecast_origin_id: str
    status: str
    target_records: tuple
    coverage_records: tuple
    n_within_scope_targets: int
    n_evaluable_target_events: int  # WITHIN scope AND received a real target_grid_cell_id
    unsafe_component_count: int = 0


def _evaluate_validation_origin(
    repo, origin: ForecastOrigin, *, fold_id: str, disease: str, active_window_days: int, grid_config: ScientificGridConfig,
    raw_snapshot: dict | None, candidates: tuple, reference_profile, transform_config: FactorTransformConfig,
    reference_unsafe_component_count: int = 0,
) -> OriginEvaluationOutcome:
    if (
        isinstance(reference_unsafe_component_count, bool)
        or not isinstance(reference_unsafe_component_count, int)
        or reference_unsafe_component_count < 0
    ):
        raise ValueError("reference_unsafe_component_count must be a non-negative integer")
    if raw_snapshot is None:
        return OriginEvaluationOutcome(
            origin.forecast_origin_id, VALIDATION_ORIGIN_RAW_SNAPSHOT_MISSING, (), (), 0, 0,
            reference_unsafe_component_count,
        )

    raw_unsafe_component_count = snapshot_unsafe_component_count(raw_snapshot)
    unsafe_component_count = raw_unsafe_component_count + reference_unsafe_component_count

    source_points = _eligible_source_points(repo, origin, disease=disease, active_window_days=active_window_days)
    if not source_points:
        return OriginEvaluationOutcome(
            origin.forecast_origin_id, VALIDATION_ORIGIN_NO_ELIGIBLE_SOURCE, (), (), 0, 0, unsafe_component_count,
        )

    grid_cells = raw_snapshot.get("grid_cells", []) or []
    if not grid_cells:
        return OriginEvaluationOutcome(
            origin.forecast_origin_id, VALIDATION_ORIGIN_GRID_UNAVAILABLE, (), (), 0, 0, unsafe_component_count,
        )

    evaluation_domain = build_scientific_evaluation_domain(
        forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, sources=source_points, grid_config=grid_config,
        primary_local_evaluation_distance_km=grid_config.domain_distance_km,
    )

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
        status = VALIDATION_ORIGIN_GRID_UNAVAILABLE if unsafe_component_count > 0 else VALIDATION_ORIGIN_READY
        return OriginEvaluationOutcome(
            origin.forecast_origin_id, status, (), (), n_within, n_evaluable_events, unsafe_component_count,
        )

    candidate_scores = score_origin_all_candidates(
        grid_cells=grid_cells, sources=source_points, candidates=candidates,
        reference_profile=reference_profile, transform_config=transform_config,
        unsafe_component_count=unsafe_component_count,
    )

    records: list[TargetEvaluationRecord] = []
    coverage_records: list[CandidateCoverageRecord] = []
    for candidate in candidates:
        cell_scores = candidate_scores[candidate.candidate_id]
        coverage = compute_coverage_record(
            cell_scores, forecast_origin_id=origin.forecast_origin_id, fold_id=fold_id, candidate_id=candidate.candidate_id,
            unsafe_component_count=unsafe_component_count,
        )
        coverage_records.append(coverage)
        percentiles = compute_area_weighted_percentiles(cell_scores)
        ranks = compute_target_cell_ranks(cell_scores)
        by_id = {c.grid_cell_id: c for c in cell_scores}

        for target, scope in within_targets:
            gcid = scope.target_grid_cell_id
            cell = by_id.get(gcid) if gcid is not None else None
            if gcid is None or cell is None or cell.status != SCORED:
                records.append(TargetEvaluationRecord(
                    forecast_origin_id=origin.forecast_origin_id, fold_id=fold_id, candidate_id=candidate.candidate_id,
                    target_event_id=target.target_event_id, target_id=target.target_id, lead_days=target.lead_days,
                    target_grid_cell_id=gcid, target_score=None, area_weighted_target_percentile=None,
                    top5_capture=None, top10_capture=None, target_cell_rank=None,
                    valid_domain_area_km2=coverage.declared_domain_area_km2, scored_domain_area_km2=coverage.scored_domain_area_km2,
                    model_input_status=TARGET_SCORE_UNAVAILABLE,
                ))
                continue
            pct = percentiles.get(gcid)
            records.append(TargetEvaluationRecord(
                forecast_origin_id=origin.forecast_origin_id, fold_id=fold_id, candidate_id=candidate.candidate_id,
                target_event_id=target.target_event_id, target_id=target.target_id, lead_days=target.lead_days,
                target_grid_cell_id=gcid, target_score=cell.score, area_weighted_target_percentile=pct,
                top5_capture=(pct >= TOP5_THRESHOLD_PERCENTILE) if pct is not None else None,
                top10_capture=(pct >= TOP10_THRESHOLD_PERCENTILE) if pct is not None else None,
                target_cell_rank=ranks.get(gcid), valid_domain_area_km2=coverage.declared_domain_area_km2,
                scored_domain_area_km2=coverage.scored_domain_area_km2, model_input_status=SCORED,
            ))
    status = VALIDATION_ORIGIN_GRID_UNAVAILABLE if unsafe_component_count > 0 else VALIDATION_ORIGIN_READY
    return OriginEvaluationOutcome(
        origin.forecast_origin_id, status, tuple(records), tuple(coverage_records), n_within, n_evaluable_events,
        unsafe_component_count,
    )


@dataclass(frozen=True)
class Checkpoint7BResult:
    fold_manifest: list
    insufficient_history_folds: list
    fold_reference_summaries: list
    validation_origin_completeness: dict
    candidate_overall_metrics: dict
    candidate_fold_metrics: dict
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
    n_unique_validation_targets_within_scope: int
    n_unique_evaluable_origin_target_events: int
    n_candidate_target_evaluation_rows: int
    n_candidate_target_score_unavailable_rows: int
    per_candidate_evaluable_target_count: dict
    per_candidate_unavailable_target_count: dict
    coverage_records: list
    runtime_seconds: float
    per_fold_runtime_seconds: dict
    raw_snapshot_cache_stats: dict


def run_checkpoint_7b_development(
    repo, *, fit_development_origins: list, disease: str, active_window_days: int, grid_config: ScientificGridConfig,
    transform_config: FactorTransformConfig | None = None, generated_at: str = "",
    raw_snapshot_cache_dir: Path | None = DEFAULT_RAW_HOST_SNAPSHOT_CACHE_DIR,
) -> Checkpoint7BResult:
    assert_fit_development_only(fit_development_origins, caller="run_checkpoint_7b_development")
    transform_config = transform_config or FactorTransformConfig()
    t_start = time.monotonic()

    by_id = {o.forecast_origin_id: o for o in fit_development_origins}
    calendar_folds = build_calendar_year_folds(fit_development_origins)

    if raw_snapshot_cache_dir is not None:
        raw_snapshots, cache_stats = build_raw_host_snapshots_cached(
            repo, fit_development_origins=fit_development_origins, disease=disease, active_window_days=active_window_days,
            grid_config=grid_config, cache_dir=raw_snapshot_cache_dir,
        )
    else:
        from .fold_reference import build_raw_host_snapshots
        raw_snapshots = build_raw_host_snapshots(
            repo, fit_development_origins=fit_development_origins, disease=disease, active_window_days=active_window_days, grid_config=grid_config,
        )
        unsafe_component_count = sum(snapshot_unsafe_component_count(snapshot) for snapshot in raw_snapshots.values())
        cache_stats = {
            "n_cache_hits": 0, "n_cache_misses": len(raw_snapshots), "n_origins_no_eligible_source": None,
            "n_origins_with_unsafe_components": sum(
                1 for snapshot in raw_snapshots.values() if snapshot_unsafe_component_count(snapshot) > 0
            ),
            "unsafe_component_count": unsafe_component_count,
        }

    candidates = build_candidate_registry()

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

    all_records: list[TargetEvaluationRecord] = []
    all_coverage: list[CandidateCoverageRecord] = []
    fold_reference_summaries: list = []
    validation_origin_completeness: dict = {}
    per_fold_runtime: dict = {}
    n_unique_within_scope = 0
    n_unique_evaluable_events = 0

    for f in usable_folds:
        t_fold_start = time.monotonic()
        training_origins = [by_id[oid] for oid in f.training_origin_ids]
        validation_origins = [by_id[oid] for oid in f.validation_origin_ids]

        fold_ref = build_fold_safe_reference(
            fold_id=f.fold_id, training_origins=training_origins, validation_origins=validation_origins,
            raw_snapshots_by_origin_id=raw_snapshots, transform_config=transform_config, generated_at=generated_at,
        )
        fold_reference_summaries.append({
            "fold_id": f.fold_id, "training_origin_count": len(training_origins), "validation_origin_count": len(validation_origins),
            "fold_reference_identity_hash": fold_ref.fold_reference_identity_hash(),
            "reference_profile_hash": fold_ref.reference_profile.reference_profile_hash(),
            "reference_profile_status": fold_ref.reference_profile.status,
            "unsafe_component_count": fold_ref.unsafe_component_count,
            "model_input_status": fold_ref.model_input_status,
            "host_density_total_raw_appearances": fold_ref.reference_profile.host_density_total_raw_appearances,
            "host_density_total_unique_observations": fold_ref.reference_profile.host_density_total_unique_observations,
        })

        ready_ids: list = []
        blocked: dict = {}
        unsafe_component_count_by_origin: dict = {}
        for origin in validation_origins:
            outcome = _evaluate_validation_origin(
                repo, origin, fold_id=f.fold_id, disease=disease, active_window_days=active_window_days, grid_config=grid_config,
                raw_snapshot=raw_snapshots.get(origin.forecast_origin_id), candidates=candidates,
                reference_profile=fold_ref.reference_profile, transform_config=transform_config,
                reference_unsafe_component_count=fold_ref.unsafe_component_count,
            )
            unsafe_component_count_by_origin[outcome.forecast_origin_id] = outcome.unsafe_component_count
            if outcome.status == VALIDATION_ORIGIN_READY:
                ready_ids.append(outcome.forecast_origin_id)
            else:
                blocked[outcome.forecast_origin_id] = outcome.status
            all_records.extend(outcome.target_records)
            all_coverage.extend(outcome.coverage_records)
            n_unique_within_scope += outcome.n_within_scope_targets
            n_unique_evaluable_events += outcome.n_evaluable_target_events

        # Part 7: the denominator invariant holds by construction (every
        # validation origin is looped over exactly once, above) -- still
        # asserted explicitly so a future refactor cannot silently break it.
        assert len(ready_ids) + len(blocked) == len(f.validation_origin_ids)
        validation_origin_completeness[f.fold_id] = {
            "intended_validation_origin_count": len(f.validation_origin_ids), "ready_origin_count": len(ready_ids),
            "blocked_origin_count": len(blocked), "blocked_origins": blocked,
            "unsafe_component_count": sum(unsafe_component_count_by_origin.values()),
            "unsafe_component_count_by_origin": unsafe_component_count_by_origin,
            "model_input_status": MODEL_INPUT_INCOMPLETE if any(unsafe_component_count_by_origin.values()) else SCORED,
        }
        per_fold_runtime[f.fold_id] = time.monotonic() - t_fold_start

    # Part 2 (finalization hardening): hard gate -- BEFORE candidate
    # selection, D1-D7 metrics, bootstrap, and FrozenBaselineModelSpecification.
    assert_validation_origin_completeness(validation_origin_completeness)

    n_unavailable = sum(1 for r in all_records if r.model_input_status != SCORED)

    candidate_overall_metrics: dict = {}
    candidate_fold_metrics: dict = {}
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
        per_fold: dict = {}
        for f in usable_folds:
            fold_records = [r for r in cand_records if r.fold_id == f.fold_id]
            origin_summaries = summarize_by_cluster(fold_records, cluster_key_fn=lambda r: r.forecast_origin_id)
            fm = fold_origin_balanced_metrics(origin_summaries)
            fold_metrics.append(fm)
            per_fold[f.fold_id] = fm
        candidate_fold_metrics[candidate.candidate_id] = per_fold
        candidate_overall_metrics[candidate.candidate_id] = overall_equal_origin_weighted(fold_metrics)

    eligible_ids = tuple(sorted(cid for cid, s in candidate_coverage_summary.items() if s["eligibility"] == PRIMARY_SELECTION_ELIGIBLE))
    ineligible_ids = tuple(sorted(cid for cid in candidate_overall_metrics if cid not in eligible_ids))

    candidate_families_by_id = {c.candidate_id: c.baseline_family for c in candidates}
    selection_note = classify_selection_note(
        candidate_families_by_id=candidate_families_by_id, eligible_candidate_ids=eligible_ids, ineligible_candidate_ids=ineligible_ids,
    )
    if selection_note == PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE:
        # Part 7: select_candidate({}) must never be reached accidentally.
        raise ValueError(
            f"{PRIMARY_SELECTION_BLOCKED_NO_ELIGIBLE_CANDIDATE}: 0 of {len(candidates)} candidates were "
            "PRIMARY_SELECTION_ELIGIBLE -- selection cannot proceed"
        )

    eligible_metrics = {cid: m for cid, m in candidate_overall_metrics.items() if cid in eligible_ids}
    selected_id, tie_reason = select_candidate(eligible_metrics)
    selected_spec = next(c for c in candidates if c.candidate_id == selected_id)

    selected_records = [r for r in all_records if r.candidate_id == selected_id]
    d1_d7_metrics: dict = {}
    for lead in range(1, 8):
        lead_records = [r for r in selected_records if r.lead_days == lead]
        origin_summaries = summarize_by_cluster(lead_records, cluster_key_fn=lambda r: r.forecast_origin_id)
        d1_d7_metrics[f"D{lead}"] = {
            **fold_origin_balanced_metrics(origin_summaries),
            "n_target_rows": len(lead_records),
            "n_scored": sum(1 for r in lead_records if r.model_input_status == SCORED),
            "n_target_score_unavailable": sum(1 for r in lead_records if r.model_input_status != SCORED),
        }
    pooled_summaries = summarize_by_cluster(selected_records, cluster_key_fn=lambda r: r.forecast_origin_id)
    d1_d7_metrics["POOLED_D1_D7"] = {
        **fold_origin_balanced_metrics(pooled_summaries),
        "n_target_rows": len(selected_records),
        "n_scored": sum(1 for r in selected_records if r.model_input_status == SCORED),
        "n_target_score_unavailable": sum(1 for r in selected_records if r.model_input_status != SCORED),
    }

    bootstrap_by_origin = clustered_bootstrap_ci(cluster_summaries=pooled_summaries)
    event_summaries = summarize_by_cluster(selected_records, cluster_key_fn=lambda r: r.target_event_id)
    bootstrap_by_target_event = clustered_bootstrap_ci(cluster_summaries=event_summaries)

    return Checkpoint7BResult(
        fold_manifest=fold_manifest, insufficient_history_folds=insufficient, fold_reference_summaries=fold_reference_summaries,
        validation_origin_completeness=validation_origin_completeness,
        candidate_overall_metrics=candidate_overall_metrics, candidate_fold_metrics=candidate_fold_metrics,
        candidate_coverage_summary=candidate_coverage_summary, eligible_candidate_ids=eligible_ids, ineligible_candidate_ids=ineligible_ids,
        selection_note=selection_note,
        selected_candidate_id=selected_id, selection_tie_break_reason=tie_reason, selected_candidate_spec=selected_spec.as_dict(),
        d1_d7_metrics=d1_d7_metrics, bootstrap_by_origin=bootstrap_by_origin, bootstrap_by_target_event=bootstrap_by_target_event,
        n_unique_validation_targets_within_scope=n_unique_within_scope, n_unique_evaluable_origin_target_events=n_unique_evaluable_events,
        n_candidate_target_evaluation_rows=len(all_records), n_candidate_target_score_unavailable_rows=n_unavailable,
        per_candidate_evaluable_target_count=per_candidate_evaluable, per_candidate_unavailable_target_count=per_candidate_unavailable,
        coverage_records=[c.as_dict() for c in all_coverage],
        runtime_seconds=time.monotonic() - t_start, per_fold_runtime_seconds=per_fold_runtime, raw_snapshot_cache_stats=cache_stats,
    )
