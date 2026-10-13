"""Checkpoint 7B Parts 7-9, 12-21: baseline candidate scoring, area-weighted
ranking metrics.

Score semantics (Part 7, 12, 13, 16):

    B0: score_i = sum_j K(d_j_i)
    B1: score_i = Host_LOG1P_i * sum_j K(d_j_i)
    B2: score_i = Host_ECDF_i   * sum_j K(d_j_i)

ALWAYS over the COMPLETE eligible-source set at that origin (Part 8) --
never nearest-source-only, never gated by computational-component or ST
cluster membership. The score surface is spatially STATIC across D1-D7 for
one t0 (`STATIC_T0_SPATIAL_BASELINE`, Part 12) -- no learned temporal
spread mechanism exists yet. Raw scores are never AOI-normalized (Part 13)
-- ranking metrics read the raw positive score directly.

Missing host input is NEVER converted to zero (Part 15): a cell whose host
transform is unusable is `MODEL_INPUT_INCOMPLETE`; if that happens to be a
target's own assigned cell, its own percentile is `TARGET_SCORE_UNAVAILABLE`
-- both are preserved in the audit, never silently dropped.

Area-weighted percentile (Part 18-19): uses `domain_overlap_area_km2`
(the REAL clipped-edge-cell area, never the full square `area_km2`) as the
cell weight, with explicit MIDRANK tie semantics -- grid-cell iteration
order never changes the result (METRIC7B-03).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..factors.contracts import COMPLETE_DIAGNOSTIC, HostTransformFamily, RAW_REAL_COMPONENT
from ..factors.host_transform import compute_host_density_total, transform_empirical_cdf_reference, transform_log1p_robust_reference_scale
from ..factors.transform_config import FactorTransformConfig
from ..geospatial.distance import distance_km
from ..geospatial.source_geometry import EligibleSourcePoint
from ..hazard.kernels import evaluate_kernel
from .candidate_registry_7b import BaselineCandidateSpec
from .evaluation_protocol_7b import AREA_WEIGHTED_METRIC_VERSION, AREA_WEIGHTED_MIDRANK  # noqa: F401 -- re-exported for backward compatibility

SCORED = "SCORED"
MODEL_INPUT_INCOMPLETE = "MODEL_INPUT_INCOMPLETE"
TARGET_SCORE_UNAVAILABLE = "TARGET_SCORE_UNAVAILABLE"


@dataclass(frozen=True)
class CellScore:
    grid_cell_id: str
    scientific_cell_id: str | None
    area_km2: float
    domain_overlap_area_km2: float
    score: float | None
    status: str  # SCORED | MODEL_INPUT_INCOMPLETE

    def as_dict(self) -> dict:
        return {
            "grid_cell_id": self.grid_cell_id, "scientific_cell_id": self.scientific_cell_id,
            "area_km2": self.area_km2, "domain_overlap_area_km2": self.domain_overlap_area_km2,
            "score": self.score, "status": self.status,
        }


def _host_factor(*, raw, host_factor_candidate: str, reference_profile, transform_config: FactorTransformConfig) -> float | None:
    """Returns `None` (never 0/1) if a scientifically usable host factor
    cannot be produced -- degenerate/incompatible reference profile,
    unusable raw host value, or a degenerate transform span (Part 15)."""
    if reference_profile is None or reference_profile.status != COMPLETE_DIAGNOSTIC:
        return None
    if raw.host_density_total_status != RAW_REAL_COMPONENT:
        return None
    if host_factor_candidate == HostTransformFamily.LOG1P_ROBUST_REFERENCE_SCALE.value:
        z, _clip, _status = transform_log1p_robust_reference_scale(
            host_density_total=raw.host_density_total,
            reference_log1p_lower=reference_profile.host_density_total_log1p_quantiles["lower"],
            reference_log1p_upper=reference_profile.host_density_total_log1p_quantiles["upper"],
        )
        return z
    if host_factor_candidate == HostTransformFamily.EMPIRICAL_CDF_REFERENCE.value:
        return transform_empirical_cdf_reference(
            host_density_total=raw.host_density_total, sorted_reference_values=reference_profile.host_density_total_reference_values,
            tie_convention=transform_config.ecdf_tie_convention,
        )
    raise ValueError(f"unknown host_factor_candidate {host_factor_candidate!r}")


def score_origin_all_candidates(
    *, grid_cells: list[dict], sources: list[EligibleSourcePoint], candidates: tuple[BaselineCandidateSpec, ...],
    reference_profile=None, transform_config: FactorTransformConfig | None = None,
    unsafe_component_count: int = 0,
) -> dict:
    """`grid_cells`: the raw host-only snapshot's `grid_cells` list for ONE
    origin (each dict has `grid_cell_id`, `centroid_lat/lon`, `area_km2`,
    `domain_overlap_area_km2`, `host_density`). Returns
    `{candidate_id: [CellScore, ...]}` for every candidate in `candidates`.
    Distance-kernel sums are computed ONCE per (kernel_family, kernel_scale_km)
    combination and reused across every baseline family that shares it
    (Part 35: vectorized/cached, never recomputed redundantly per
    candidate) -- geodesic distance itself is computed exactly once per
    (cell, source) pair, regardless of how many of the 24 candidates share
    it. If the upstream grid reports any unsafe component, the safe-subset
    cells remain visible for coverage accounting but every candidate/cell is
    returned as `MODEL_INPUT_INCOMPLETE`; numeric scoring is not entered."""
    if isinstance(unsafe_component_count, bool) or not isinstance(unsafe_component_count, int) or unsafe_component_count < 0:
        raise ValueError("unsafe_component_count must be a non-negative integer")
    if unsafe_component_count > 0:
        return {
            candidate.candidate_id: [
                CellScore(
                    grid_cell_id=cell["grid_cell_id"], scientific_cell_id=cell.get("scientific_cell_id"),
                    area_km2=cell["area_km2"], domain_overlap_area_km2=cell["domain_overlap_area_km2"],
                    score=None, status=MODEL_INPUT_INCOMPLETE,
                )
                for cell in grid_cells
            ]
            for candidate in candidates
        }

    kernel_combos = sorted({(c.kernel_family, c.kernel_scale_km) for c in candidates})
    kernel_sums_by_cell: dict[str, dict] = {}
    host_raw_by_cell: dict[str, object] = {}

    for cell in grid_cells:
        gcid = cell["grid_cell_id"]
        distances = [distance_km(s.latitude, s.longitude, cell["centroid_lat"], cell["centroid_lon"]) for s in sources]
        sums = {}
        for family, scale in kernel_combos:
            sums[(family, scale)] = sum(evaluate_kernel(d, family=family, distance_scale_km=scale) for d in distances)
        kernel_sums_by_cell[gcid] = sums
        host_raw_by_cell[gcid] = compute_host_density_total(cell)

    results: dict[str, list[CellScore]] = {}
    for candidate in candidates:
        cell_scores: list[CellScore] = []
        for cell in grid_cells:
            gcid = cell["grid_cell_id"]
            kernel_sum = kernel_sums_by_cell[gcid][(candidate.kernel_family, candidate.kernel_scale_km)]
            if candidate.host_factor_candidate is None:
                score, status = kernel_sum, SCORED
            else:
                factor = _host_factor(
                    raw=host_raw_by_cell[gcid], host_factor_candidate=candidate.host_factor_candidate,
                    reference_profile=reference_profile, transform_config=transform_config or FactorTransformConfig(),
                )
                if factor is None:
                    score, status = None, MODEL_INPUT_INCOMPLETE
                else:
                    score, status = factor * kernel_sum, SCORED
            cell_scores.append(CellScore(
                grid_cell_id=gcid, scientific_cell_id=cell.get("scientific_cell_id"),
                area_km2=cell["area_km2"], domain_overlap_area_km2=cell["domain_overlap_area_km2"],
                score=score, status=status,
            ))
        results[candidate.candidate_id] = cell_scores
    return results


def compute_area_weighted_percentiles(cell_scores: list[CellScore]) -> dict:
    """`AREA_WEIGHTED_TARGET_PERCENTILE` (Part 18) for every SCORED cell,
    `= 100 * (area(score < S) + 0.5 * area(score == S)) / total_valid_domain_area`.
    `total_valid_domain_area` is the `domain_overlap_area_km2` sum over
    EVERY cell in the domain (scored or `MODEL_INPUT_INCOMPLETE`) -- an
    incomplete cell still occupies real declared-domain area, it is just
    never counted in the numerator; this makes a material missing-area
    fraction visibly suppress percentiles rather than silently shrinking
    the denominator to hide it. O(n log n): cells are sorted once and
    walked in tied score-groups -- grid iteration order never affects the
    result (METRIC7B-03), and duplicating a zero-overlap cell contributes
    zero area to both numerator and denominator (METRIC7B-04)."""
    total_valid_domain_area = sum(c.domain_overlap_area_km2 for c in cell_scores)
    scored = [c for c in cell_scores if c.status == SCORED]
    if total_valid_domain_area <= 0 or not scored:
        return {}
    ordered = sorted(scored, key=lambda c: c.score)
    percentiles: dict[str, float] = {}
    i, n = 0, len(ordered)
    cumulative_area_before = 0.0
    while i < n:
        j = i
        group_area = 0.0
        score_val = ordered[i].score
        while j < n and ordered[j].score == score_val:
            group_area += ordered[j].domain_overlap_area_km2
            j += 1
        pct = 100.0 * (cumulative_area_before + 0.5 * group_area) / total_valid_domain_area
        for k in range(i, j):
            percentiles[ordered[k].grid_cell_id] = pct
        cumulative_area_before += group_area
        i = j
    return percentiles


def compute_target_cell_ranks(cell_scores: list[CellScore]) -> dict:
    """Secondary diagnostic `TARGET_CELL_RANK` (Part 20) -- deterministic
    ties resolved by score descending, then `scientific_cell_id` ascending
    (METRIC7B-07); never called classification accuracy."""
    scored = [c for c in cell_scores if c.status == SCORED]
    ordered = sorted(scored, key=lambda c: (-c.score, c.scientific_cell_id or ""))
    return {c.grid_cell_id: i + 1 for i, c in enumerate(ordered)}


@dataclass(frozen=True)
class CandidateCoverageRecord:
    """Part 3: per (origin, fold, candidate) domain-coverage audit --
    computed ALWAYS, never discarded after computation (the original 7B
    pass computed `missing_area_fraction` and then threw it away)."""

    forecast_origin_id: str
    fold_id: str
    candidate_id: str
    declared_domain_area_km2: float
    scored_domain_area_km2: float
    missing_domain_area_km2: float
    missing_domain_area_fraction: float
    n_scientific_cells: int
    n_scored_cells: int
    n_incomplete_cells: int
    unsafe_component_count: int = 0
    model_input_status: str = SCORED

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id, "fold_id": self.fold_id, "candidate_id": self.candidate_id,
            "declared_domain_area_km2": self.declared_domain_area_km2, "scored_domain_area_km2": self.scored_domain_area_km2,
            "missing_domain_area_km2": self.missing_domain_area_km2, "missing_domain_area_fraction": self.missing_domain_area_fraction,
            "n_scientific_cells": self.n_scientific_cells, "n_scored_cells": self.n_scored_cells,
            "n_incomplete_cells": self.n_incomplete_cells, "unsafe_component_count": self.unsafe_component_count,
            "model_input_status": self.model_input_status,
        }


def compute_coverage_record(
    cell_scores: list[CellScore], *, forecast_origin_id: str, fold_id: str, candidate_id: str,
    unsafe_component_count: int = 0,
) -> CandidateCoverageRecord:
    """Uses `domain_overlap_area_km2` throughout (Part 3) -- never the
    full square `area_km2`. An upstream unsafe component is an explicit
    incomplete-input guard even if a caller supplies scored safe-subset
    cells; coverage must never report that subset as complete."""
    if isinstance(unsafe_component_count, bool) or not isinstance(unsafe_component_count, int) or unsafe_component_count < 0:
        raise ValueError("unsafe_component_count must be a non-negative integer")
    declared = sum(c.domain_overlap_area_km2 for c in cell_scores)
    if unsafe_component_count > 0:
        scored_area = 0.0
        n_incomplete = len(cell_scores)
    else:
        scored_area = sum(c.domain_overlap_area_km2 for c in cell_scores if c.status == SCORED)
        n_incomplete = sum(1 for c in cell_scores if c.status != SCORED)
    missing = declared - scored_area
    fraction = (missing / declared) if declared > 0 else 0.0
    return CandidateCoverageRecord(
        forecast_origin_id=forecast_origin_id, fold_id=fold_id, candidate_id=candidate_id,
        declared_domain_area_km2=declared, scored_domain_area_km2=scored_area, missing_domain_area_km2=missing,
        missing_domain_area_fraction=fraction, n_scientific_cells=len(cell_scores),
        n_scored_cells=len(cell_scores) - n_incomplete, n_incomplete_cells=n_incomplete,
        unsafe_component_count=unsafe_component_count,
        model_input_status=MODEL_INPUT_INCOMPLETE if unsafe_component_count > 0 or n_incomplete > 0 else SCORED,
    )
