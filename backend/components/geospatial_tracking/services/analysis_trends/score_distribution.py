"""GEO-ANALYSIS-01 Section 15: Relative Spatial Score descriptive
distribution over one selected origin's own real snapshot cells.

Order statistics (min/median/max) only -- scientifically safe regardless
of the underlying score scale, unlike a circular-mean-style aggregation
(see `context_service.py` for why bearing/direction has no equivalent
here). Computed only from `raw_c0_score` values the frozen 10A
computation actually produced for THIS snapshot; never interpolated,
never carried over from a different snapshot (`cross_snapshot_comparison_
status` always states this is unsupported).
"""

from __future__ import annotations

from ...domain.analysis_trends_enums import (
    CROSS_SNAPSHOT_SCORE_COMPARISON_STATUS,
    RELATIVE_SPATIAL_SCORE_LABEL,
    RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS,
    RelativeSpatialScoreDistributionStatus,
)
from ...domain.analysis_trends_models import RelativeSpatialScoreDistribution


def _median(sorted_values: list[float]) -> float:
    n = len(sorted_values)
    mid = n // 2
    if n % 2 == 1:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2.0


def build_relative_spatial_score_distribution(raw_c0_scores: list[float | None]) -> RelativeSpatialScoreDistribution:
    real_scores = sorted(s for s in raw_c0_scores if s is not None)
    if not real_scores:
        return RelativeSpatialScoreDistribution(
            status=RelativeSpatialScoreDistributionStatus.UNAVAILABLE_RUNTIME_METRIC.value,
            label=RELATIVE_SPATIAL_SCORE_LABEL, temporal_basis=RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS,
            min_score=None, median_score=None, max_score=None, n_cells_scored=0,
            cross_snapshot_comparison_status=CROSS_SNAPSHOT_SCORE_COMPARISON_STATUS,
        )
    return RelativeSpatialScoreDistribution(
        status=RelativeSpatialScoreDistributionStatus.AVAILABLE.value,
        label=RELATIVE_SPATIAL_SCORE_LABEL, temporal_basis=RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS,
        min_score=real_scores[0], median_score=_median(real_scores), max_score=real_scores[-1],
        n_cells_scored=len(real_scores), cross_snapshot_comparison_status=CROSS_SNAPSHOT_SCORE_COMPARISON_STATUS,
    )
