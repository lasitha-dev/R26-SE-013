"""Synthetic-safe FMD-07B EXP-02 origin execution boundary.

The adapter delegates all per-cell mathematics to ``SpatialDistanceRunner``
and adds only the frozen complete-domain origin scalar. It does not enumerate
origins, execute a real workload, calculate candidate metrics, or write an
artifact.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .fmd_model_development_7b import Fmd07bFoldInput, SpatialDistanceRunner
from .model_development.baseline_scoring import CellScore, MODEL_INPUT_INCOMPLETE, SCORED

AREA_WEIGHTED_MEAN_OVER_COMPLETE_ORIGIN_DOMAIN = (
    "AREA_WEIGHTED_MEAN_OVER_COMPLETE_ORIGIN_DOMAIN"
)
EXP02_ORIGIN_SCALAR_RULE = AREA_WEIGHTED_MEAN_OVER_COMPLETE_ORIGIN_DOMAIN
FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM = 30.0


@dataclass(frozen=True)
class Exp02OriginCandidatePrediction:
    fold_id: str
    experiment_id: str
    candidate_id: str
    forecast_origin_id: str
    score: float | None
    status: str
    unsafe_component_count: int
    origin_scalar_rule: str
    engineering_grid_size_km: float
    per_cell_scores: tuple[CellScore, ...]

    def as_dict(self) -> dict:
        return {
            "fold_id": self.fold_id,
            "experiment_id": self.experiment_id,
            "candidate_id": self.candidate_id,
            "forecast_origin_id": self.forecast_origin_id,
            "score": self.score,
            "status": self.status,
            "unsafe_component_count": self.unsafe_component_count,
            "origin_scalar_rule": self.origin_scalar_rule,
            "engineering_grid_size_km": self.engineering_grid_size_km,
            "per_cell_scores": [cell_score.as_dict() for cell_score in self.per_cell_scores],
        }


def _canonical_cell_scores(cell_scores: Sequence[CellScore]) -> tuple[CellScore, ...]:
    return tuple(
        sorted(
            cell_scores,
            key=lambda cell_score: (
                cell_score.scientific_cell_id or "",
                cell_score.grid_cell_id,
            ),
        )
    )


def aggregate_exp02_origin_cell_scores(
    *,
    fold_id: str,
    candidate_id: str,
    forecast_origin_id: str,
    cell_scores: Sequence[CellScore],
    unsafe_component_count: int = 0,
    engineering_grid_size_km: float = FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM,
) -> Exp02OriginCandidatePrediction:
    """Aggregate unchanged per-cell scores over the complete origin domain."""
    if isinstance(unsafe_component_count, bool) or not isinstance(unsafe_component_count, int):
        raise ValueError("unsafe_component_count must be a non-negative integer")
    if unsafe_component_count < 0:
        raise ValueError("unsafe_component_count must be a non-negative integer")
    if engineering_grid_size_km != FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM:
        raise ValueError(
            "FMD-07B EXP-02 requires the selected 30.0 km engineering grid"
        )

    canonical_scores = _canonical_cell_scores(cell_scores)
    grid_cell_ids = tuple(cell_score.grid_cell_id for cell_score in canonical_scores)
    complete = (
        unsafe_component_count == 0
        and bool(canonical_scores)
        and len(grid_cell_ids) == len(set(grid_cell_ids))
        and all(
            cell_score.status == SCORED
            and cell_score.score is not None
            and math.isfinite(cell_score.score)
            and math.isfinite(cell_score.domain_overlap_area_km2)
            and cell_score.domain_overlap_area_km2 > 0.0
            for cell_score in canonical_scores
        )
    )
    if not complete:
        score, status = None, MODEL_INPUT_INCOMPLETE
    else:
        total_domain_area = math.fsum(
            cell_score.domain_overlap_area_km2 for cell_score in canonical_scores
        )
        weighted_score_sum = math.fsum(
            cell_score.score * cell_score.domain_overlap_area_km2
            for cell_score in canonical_scores
        )
        score, status = weighted_score_sum / total_domain_area, SCORED

    return Exp02OriginCandidatePrediction(
        fold_id=fold_id,
        experiment_id="FMD-EXP-02",
        candidate_id=candidate_id,
        forecast_origin_id=forecast_origin_id,
        score=score,
        status=status,
        unsafe_component_count=unsafe_component_count,
        origin_scalar_rule=EXP02_ORIGIN_SCALAR_RULE,
        engineering_grid_size_km=engineering_grid_size_km,
        per_cell_scores=canonical_scores,
    )


@dataclass(frozen=True)
class Exp02OriginExecutionAdapter:
    spatial_runner: SpatialDistanceRunner
    engineering_grid_size_km: float = FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM

    def __post_init__(self) -> None:
        if self.spatial_runner.experiment_id != "FMD-EXP-02":
            raise ValueError("EXP-02 origin adapter requires an FMD-EXP-02 spatial runner")
        if self.engineering_grid_size_km != FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM:
            raise ValueError("EXP-02 origin adapter is frozen to the selected 30.0 km engineering grid")

    def execute_validation_origin(
        self,
        fold: Fmd07bFoldInput,
        *,
        forecast_origin_id: str,
        grid_cells: list[dict],
        sources: list,
        reference_profile,
        transform_config=None,
        unsafe_component_count: int = 0,
    ) -> tuple[Exp02OriginCandidatePrediction, ...]:
        """Score one supplied validation origin; never discover or loop a corpus."""
        per_cell_by_candidate = self.spatial_runner.score_validation_origin(
            fold,
            forecast_origin_id=forecast_origin_id,
            grid_cells=grid_cells,
            sources=sources,
            reference_profile=reference_profile,
            transform_config=transform_config,
            unsafe_component_count=unsafe_component_count,
        )
        expected_candidate_ids = {
            candidate.candidate_id for candidate in self.spatial_runner.candidates
        }
        if set(per_cell_by_candidate) != expected_candidate_ids:
            raise RuntimeError("spatial runner result does not match the frozen EXP-02 candidate registry")
        return tuple(
            aggregate_exp02_origin_cell_scores(
                fold_id=fold.fold_id,
                candidate_id=candidate_id,
                forecast_origin_id=forecast_origin_id,
                cell_scores=per_cell_by_candidate[candidate_id],
                unsafe_component_count=unsafe_component_count,
                engineering_grid_size_km=self.engineering_grid_size_km,
            )
            for candidate_id in sorted(expected_candidate_ids)
        )
