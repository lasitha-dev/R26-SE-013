"""GEO-ANALYSIS-01 Section 34/36: pure Relative Spatial Score
distribution tests -- order statistics only, computed from real per-cell
`raw_c0_score` values, never a fabricated/interpolated number.
"""

from __future__ import annotations

from components.geospatial_tracking.domain.analysis_trends_enums import (
    CROSS_SNAPSHOT_SCORE_COMPARISON_STATUS,
    RELATIVE_SPATIAL_SCORE_LABEL,
    RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS,
)
from components.geospatial_tracking.services.analysis_trends.score_distribution import build_relative_spatial_score_distribution


class TestEmptyOrAllNoneScores:
    def test_no_scores_returns_unavailable_never_zero(self):
        dist = build_relative_spatial_score_distribution([])
        assert dist.status == "UNAVAILABLE_RUNTIME_METRIC"
        assert dist.min_score is None
        assert dist.median_score is None
        assert dist.max_score is None
        assert dist.n_cells_scored == 0

    def test_all_none_scores_returns_unavailable(self):
        dist = build_relative_spatial_score_distribution([None, None, None])
        assert dist.status == "UNAVAILABLE_RUNTIME_METRIC"
        assert dist.n_cells_scored == 0


class TestRealScoreDistribution:
    def test_min_median_max_computed_from_real_scores_only(self):
        dist = build_relative_spatial_score_distribution([0.2, 0.5, 0.8, None])
        assert dist.status == "AVAILABLE"
        assert dist.min_score == 0.2
        assert dist.max_score == 0.8
        assert dist.median_score == 0.5
        assert dist.n_cells_scored == 3  # the None is excluded, never counted as a scored cell

    def test_even_count_median_is_averaged_between_the_two_middle_values(self):
        dist = build_relative_spatial_score_distribution([0.1, 0.3, 0.5, 0.7])
        assert dist.median_score == 0.4

    def test_label_and_temporal_basis_preserved_exactly(self):
        dist = build_relative_spatial_score_distribution([0.5])
        assert dist.label == RELATIVE_SPATIAL_SCORE_LABEL
        assert dist.temporal_basis == RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS

    def test_never_converted_to_a_percentage_or_probability_string(self):
        dist = build_relative_spatial_score_distribution([0.82])
        for value in (dist.min_score, dist.median_score, dist.max_score):
            assert not isinstance(value, str)
        assert dist.min_score == 0.82  # the raw score itself, never "82%"

    def test_cross_snapshot_comparison_always_marked_unsupported(self):
        dist = build_relative_spatial_score_distribution([0.5])
        assert dist.cross_snapshot_comparison_status == CROSS_SNAPSHOT_SCORE_COMPARISON_STATUS
        dist_empty = build_relative_spatial_score_distribution([])
        assert dist_empty.cross_snapshot_comparison_status == CROSS_SNAPSHOT_SCORE_COMPARISON_STATUS

    def test_single_score_all_three_statistics_equal_it(self):
        dist = build_relative_spatial_score_distribution([0.42])
        assert dist.min_score == dist.median_score == dist.max_score == 0.42
        assert dist.n_cells_scored == 1
