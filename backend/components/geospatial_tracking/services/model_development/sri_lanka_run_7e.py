"""Checkpoint 7E: frozen Sri Lanka geographic-transfer case study of the
Checkpoint 7C-selected C0 model.

Mirrors `heldout_run_7d.py` structurally (same firewall pattern, same
origin-completeness hard-stop, same target-scope/coverage machinery,
same primary metric/tie semantics) but adds: (a) the event-level
descriptive table (Part 17) carrying GPS-quality/availability-quality
metadata per origin, reused directly from the real historical records
rather than re-derived, and (b) the small-sample rule (Part 16) --
Sri Lanka's real 5-origin universe is expected to trigger it.

This is a CASE STUDY, never a validation: `run_checkpoint_7e_sri_lanka_case_study`
firewalls on `SRI_LANKA_TRANSFER_CASE_STUDY` alone (Part 3) and computes
descriptive metrics ONLY -- Sri Lanka data has zero path back into any
model parameter or candidate selection.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ..forecast_target import build_forecast_targets
from ..geospatial.distance import distance_km
from ..geospatial.scientific_domain import build_scientific_evaluation_domain
from ..geospatial.scientific_grid import ScientificGridConfig
from ..model_fitting_exposure import assert_sri_lanka_transfer_case_study_only
from .baseline_scoring import SCORED, CandidateCoverageRecord, compute_area_weighted_percentiles, compute_coverage_record, compute_target_cell_ranks
from .candidate_registry_7c import Candidate7CSpec
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
from .selection_7b import fold_origin_balanced_metrics, summarize_by_cluster

SRI_LANKA_EVALUATION_KEY = "SRI_LANKA_TRANSFER_CASE_STUDY"
SMALL_SAMPLE_THRESHOLD_ORIGINS = 10
SMALL_SAMPLE_DESCRIPTIVE_ONLY = "SMALL_SAMPLE_DESCRIPTIVE_ONLY"


class SriLankaOriginCompletenessGateError(RuntimeError):
    """Part 4/12: raised the instant any Sri Lanka origin is not
    `VALIDATION_ORIGIN_READY`, or C0's coverage is unexpectedly
    incomplete -- never a silent drop."""


class SriLankaCoverageIncompleteError(RuntimeError):
    """Part 12: a legitimate WITHIN target with no scientific grid cell,
    or any other unexpected coverage gap, is a hard stop -- 25km is never
    widened to rescue it."""


@dataclass(frozen=True)
class SriLankaEventLevelRecord:
    forecast_origin_id: str
    t0: str
    t0_precision: str
    availability_quality: str
    gps_quality: str
    eligible_source_count: int
    target_event_id: str | None
    lead_day: int | None
    target_scope_status: str | None
    target_distance_to_nearest_eligible_source_km: float | None
    target_percentile: float | None
    top5_capture: bool | None
    top10_capture: bool | None
    score_status: str | None

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id, "t0": self.t0, "t0_precision": self.t0_precision,
            "availability_quality": self.availability_quality, "gps_quality": self.gps_quality,
            "eligible_source_count": self.eligible_source_count, "target_event_id": self.target_event_id,
            "lead_day": self.lead_day, "target_scope_status": self.target_scope_status,
            "target_distance_to_nearest_eligible_source_km": self.target_distance_to_nearest_eligible_source_km,
            "target_percentile": self.target_percentile, "top5_capture": self.top5_capture, "top10_capture": self.top10_capture,
            "score_status": self.score_status,
        }


def _origin_quality_metadata(repo, source_points) -> tuple[str, str]:
    """Reuses the real, already-persisted `proxy_availability_quality`/
    `gps_quality` fields on the origin's own trigger/eligible source
    records -- never manufactured. Returns (availability_quality,
    gps_quality); if the sources disagree, both distinct values are
    joined (never silently collapsed to one)."""
    ids = {s.source_id for s in source_points}
    avail_qualities: set = set()
    gps_qualities: set = set()
    for record in repo.list_historical_records(country=None):
        if record.source_record_id in ids:
            avail_qualities.add(getattr(record, "proxy_availability_quality", "UNKNOWN") or "UNKNOWN")
            gps_qualities.add(getattr(record, "gps_quality", "UNKNOWN") or "UNKNOWN")
    avail = "|".join(sorted(avail_qualities)) if avail_qualities else "UNKNOWN"
    gps = "|".join(sorted(gps_qualities)) if gps_qualities else "UNKNOWN"
    return avail, gps


@dataclass(frozen=True)
class OriginEvaluationOutcome7E:
    forecast_origin_id: str
    status: str
    target_records: tuple
    coverage_records: tuple
    event_level_records: tuple
    n_within: int


def _evaluate_sri_lanka_origin(
    repo, origin, *, disease: str, active_window_days: int, grid_config: ScientificGridConfig, c0_spec: Candidate7CSpec,
) -> OriginEvaluationOutcome7E:
    source_points = _eligible_source_points(repo, origin, disease=disease, active_window_days=active_window_days)
    avail_quality, gps_quality = _origin_quality_metadata(repo, source_points) if source_points else ("UNKNOWN", "UNKNOWN")

    if not source_points:
        ev = SriLankaEventLevelRecord(origin.forecast_origin_id, origin.t0, "DATE_ONLY", "UNKNOWN", "UNKNOWN", 0, None, None, None, None, None, None, None, None)
        return OriginEvaluationOutcome7E(origin.forecast_origin_id, VALIDATION_ORIGIN_NO_ELIGIBLE_SOURCE, (), (), (ev,), 0)

    evaluation_domain = build_scientific_evaluation_domain(
        forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, sources=source_points, grid_config=grid_config,
        primary_local_evaluation_distance_km=grid_config.domain_distance_km,
    )
    grid_cells = _grid_cell_dicts(evaluation_domain)
    if not grid_cells:
        ev = SriLankaEventLevelRecord(origin.forecast_origin_id, origin.t0, "DATE_ONLY", avail_quality, gps_quality, len(source_points), None, None, None, None, None, None, None, None)
        return OriginEvaluationOutcome7E(origin.forecast_origin_id, VALIDATION_ORIGIN_GRID_UNAVAILABLE, (), (), (ev,), 0)

    targets = build_forecast_targets(repo, origin, disease=disease, source_ids_at_origin={s.source_id for s in source_points}, horizon_days=7)
    targets = dedupe_targets_by_origin_and_event([t for t in targets if t.risk_target_eligible])

    within_targets = []
    event_level: list[SriLankaEventLevelRecord] = []
    for t in targets:
        scope = classify_target_primary_scope(target=t, sources=source_points, evaluation_domain=evaluation_domain)
        nearest_km = min(distance_km(s.latitude, s.longitude, t.latitude, t.longitude) for s in source_points)
        if scope.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE:
            within_targets.append((t, scope))
        else:
            status = scope.scope_status if scope.scope_status != LOCAL_SCOPE_UNRESOLVED else LOCAL_SCOPE_UNRESOLVED
            event_level.append(SriLankaEventLevelRecord(
                origin.forecast_origin_id, origin.t0, "DATE_ONLY", avail_quality, gps_quality, len(source_points),
                t.target_event_id, t.lead_days, status, nearest_km, None, None, None, "OUT_OF_PRIMARY_SCOPE",
            ))

    n_within_without_cell = sum(1 for _t, scope in within_targets if scope.target_grid_cell_id is None)
    if n_within_without_cell:
        raise SriLankaCoverageIncompleteError(
            f"origin {origin.forecast_origin_id}: {n_within_without_cell} WITHIN-scope target(s) lack a valid scientific grid cell -- STOP (Part 12)"
        )

    if not within_targets:
        if not event_level:
            event_level.append(SriLankaEventLevelRecord(origin.forecast_origin_id, origin.t0, "DATE_ONLY", avail_quality, gps_quality, len(source_points), None, None, None, None, None, None, None, None))
        return OriginEvaluationOutcome7E(origin.forecast_origin_id, VALIDATION_ORIGIN_READY, (), (), tuple(event_level), 0)

    candidate_scores = _score(grid_cells=grid_cells, sources=source_points, c0_spec=c0_spec)
    cell_scores = candidate_scores
    coverage = compute_coverage_record(cell_scores, forecast_origin_id=origin.forecast_origin_id, fold_id=SRI_LANKA_EVALUATION_KEY, candidate_id=c0_spec.candidate_id)
    percentiles = compute_area_weighted_percentiles(cell_scores)
    ranks = compute_target_cell_ranks(cell_scores)
    by_id = {c.grid_cell_id: c for c in cell_scores}

    records = []
    for target, scope in within_targets:
        gcid = scope.target_grid_cell_id
        cell = by_id.get(gcid)
        nearest_km = min(distance_km(s.latitude, s.longitude, target.latitude, target.longitude) for s in source_points)
        if cell is None or cell.status != SCORED:
            records.append(_target_record(origin, c0_spec, target, gcid, None, None, coverage, "TARGET_SCORE_UNAVAILABLE"))
            event_level.append(SriLankaEventLevelRecord(
                origin.forecast_origin_id, origin.t0, "DATE_ONLY", avail_quality, gps_quality, len(source_points),
                target.target_event_id, target.lead_days, WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE, nearest_km, None, None, None, "TARGET_SCORE_UNAVAILABLE",
            ))
            continue
        pct = percentiles.get(gcid)
        top5 = (pct >= TOP5_THRESHOLD_PERCENTILE) if pct is not None else None
        top10 = (pct >= TOP10_THRESHOLD_PERCENTILE) if pct is not None else None
        records.append(_target_record(origin, c0_spec, target, gcid, cell.score, pct, coverage, SCORED, ranks.get(gcid), top5, top10))
        event_level.append(SriLankaEventLevelRecord(
            origin.forecast_origin_id, origin.t0, "DATE_ONLY", avail_quality, gps_quality, len(source_points),
            target.target_event_id, target.lead_days, WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE, nearest_km, pct, top5, top10, SCORED,
        ))

    return OriginEvaluationOutcome7E(origin.forecast_origin_id, VALIDATION_ORIGIN_READY, tuple(records), (coverage,), tuple(event_level), len(within_targets))


def _score(*, grid_cells, sources, c0_spec):
    from .wind_scoring_7c import score_origin_candidates_7c

    return score_origin_candidates_7c(grid_cells=grid_cells, sources=sources, candidates=(c0_spec,), wind=None)[c0_spec.candidate_id]


def _target_record(origin, c0_spec, target, gcid, score, pct, coverage, status, rank=None, top5=None, top10=None):
    from .heldout_run_7d import TargetEvaluationRecord7D

    return TargetEvaluationRecord7D(
        forecast_origin_id=origin.forecast_origin_id, country=origin.country, candidate_id=c0_spec.candidate_id,
        target_event_id=target.target_event_id, target_id=target.target_id, lead_days=target.lead_days,
        target_grid_cell_id=gcid, target_score=score, area_weighted_target_percentile=pct, top5_capture=top5, top10_capture=top10,
        target_cell_rank=rank, valid_domain_area_km2=coverage.declared_domain_area_km2, scored_domain_area_km2=coverage.scored_domain_area_km2,
        model_input_status=status,
    )


@dataclass(frozen=True)
class Checkpoint7EResult:
    origin_completeness: dict
    coverage_summary: dict
    event_level_records: list
    n_unique_evaluable_targets: int
    n_contributing_origins: int
    small_sample: bool
    pooled_summary: dict
    d1_d7_metrics: dict
    origin_level_summaries: list
    runtime_seconds: float


def run_checkpoint_7e_sri_lanka_case_study(
    repo, *, sri_lanka_origins: list, disease: str, active_window_days: int, grid_config: ScientificGridConfig, c0_spec: Candidate7CSpec,
) -> Checkpoint7EResult:
    assert_sri_lanka_transfer_case_study_only(sri_lanka_origins, caller="run_checkpoint_7e_sri_lanka_case_study")
    t_start = time.monotonic()

    ready_ids: list = []
    blocked: dict = {}
    all_records: list = []
    all_coverage: list[CandidateCoverageRecord] = []
    all_event_level: list = []

    for origin in sri_lanka_origins:
        outcome = _evaluate_sri_lanka_origin(repo, origin, disease=disease, active_window_days=active_window_days, grid_config=grid_config, c0_spec=c0_spec)
        if outcome.status == VALIDATION_ORIGIN_READY:
            ready_ids.append(outcome.forecast_origin_id)
        else:
            blocked[outcome.forecast_origin_id] = outcome.status
        all_records.extend(outcome.target_records)
        all_coverage.extend(outcome.coverage_records)
        all_event_level.extend(outcome.event_level_records)

    assert len(ready_ids) + len(blocked) == len(sri_lanka_origins)
    origin_completeness = {
        SRI_LANKA_EVALUATION_KEY: {
            "intended_case_study_origin_count": len(sri_lanka_origins), "ready_origin_count": len(ready_ids),
            "blocked_origin_count": len(blocked), "blocked_origins": blocked,
        }
    }
    if blocked:
        detail = "; ".join(f"{oid}={status}" for oid, status in sorted(blocked.items()))
        raise SriLankaOriginCompletenessGateError(f"{len(blocked)} blocked Sri Lanka origin(s), no silent drop allowed: {detail}")

    n_unavailable = sum(1 for r in all_records if r.model_input_status != SCORED)
    max_missing = max((c.missing_domain_area_km2 for c in all_coverage), default=0.0)
    eligibility = assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=n_unavailable, max_missing_domain_area_km2=max_missing)
    coverage_summary = {c0_spec.candidate_id: {"max_missing_domain_area_km2": max_missing, "n_target_score_unavailable_rows": n_unavailable, "eligibility": eligibility}}
    if all_records and eligibility != PRIMARY_SELECTION_ELIGIBLE:
        raise SriLankaCoverageIncompleteError(f"C0's Sri Lanka coverage is unexpectedly incomplete: {coverage_summary[c0_spec.candidate_id]} -- STOP, per Part 12")

    n_unique_targets = len({(r.forecast_origin_id, r.target_event_id) for r in all_records})
    contributing_origins = sorted({r.forecast_origin_id for r in all_records if r.model_input_status == SCORED})
    n_contributing = len(contributing_origins)
    small_sample = n_contributing < SMALL_SAMPLE_THRESHOLD_ORIGINS

    scored_records = [r for r in all_records if r.model_input_status == SCORED]
    percentiles = [r.area_weighted_target_percentile for r in scored_records]
    origin_summaries = summarize_by_cluster(scored_records, cluster_key_fn=lambda r: r.forecast_origin_id)
    origin_level_summaries = [
        {"forecast_origin_id": s.cluster_key, "n_evaluable_targets": s.n_evaluable_targets, "mean_target_percentile": s.mean_target_percentile,
         "top5_capture_rate": s.top5_capture_rate, "top10_capture_rate": s.top10_capture_rate}
        for s in origin_summaries
    ]

    if percentiles:
        sorted_p = sorted(percentiles)
        n = len(sorted_p)
        median = sorted_p[n // 2] if n % 2 == 1 else (sorted_p[n // 2 - 1] + sorted_p[n // 2]) / 2
        pooled_summary = {
            "n_evaluable_targets": len(percentiles), "n_contributing_origins": n_contributing,
            "mean_target_percentile": sum(percentiles) / len(percentiles), "median_target_percentile": median,
            "min_target_percentile": min(percentiles), "max_target_percentile": max(percentiles),
            "top5_capture_rate": sum(1 for r in scored_records if r.top5_capture) / len(scored_records),
            "top10_capture_rate": sum(1 for r in scored_records if r.top10_capture) / len(scored_records),
            "status": SMALL_SAMPLE_DESCRIPTIVE_ONLY if small_sample else "ORIGIN_CLUSTERED_DESCRIPTIVE",
        }
    else:
        pooled_summary = {
            "n_evaluable_targets": 0, "n_contributing_origins": 0, "mean_target_percentile": None, "median_target_percentile": None,
            "min_target_percentile": None, "max_target_percentile": None, "top5_capture_rate": None, "top10_capture_rate": None,
            "status": "INSUFFICIENT_EVALUABLE_SRI_LANKA_D1_D7_TRANSFER_TARGETS",
        }

    d1_d7_metrics: dict = {}
    for lead in range(1, 8):
        lead_records = [r for r in scored_records if r.lead_days == lead]
        d1_d7_metrics[f"D{lead}"] = {
            "n_target_rows": len(lead_records),
            "mean_target_percentile": (sum(r.area_weighted_target_percentile for r in lead_records) / len(lead_records)) if lead_records else None,
        }

    return Checkpoint7EResult(
        origin_completeness=origin_completeness, coverage_summary=coverage_summary,
        event_level_records=[r.as_dict() for r in all_event_level],
        n_unique_evaluable_targets=n_unique_targets, n_contributing_origins=n_contributing, small_sample=small_sample,
        pooled_summary=pooled_summary, d1_d7_metrics=d1_d7_metrics, origin_level_summaries=origin_level_summaries,
        runtime_seconds=time.monotonic() - t_start,
    )
