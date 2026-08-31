"""Checkpoint 7B Part 42: UNIT7B-01..04 pseudo-replication safety tests."""

from __future__ import annotations

import inspect
from dataclasses import dataclass

from components.geospatial_tracking.services.model_development.development_run_7b import dedupe_targets_by_origin_and_event
from components.geospatial_tracking.services.model_development.selection_7b import (
    fold_origin_balanced_metrics,
    overall_equal_origin_weighted,
    summarize_by_cluster,
)


@dataclass
class _FakeTarget:
    forecast_origin_id: str
    target_event_id: str
    target_id: str = ""


@dataclass
class _Rec:
    forecast_origin_id: str
    target_event_id: str
    area_weighted_target_percentile: float | None
    top5_capture: bool | None
    top10_capture: bool | None


def test_unit7b_01_duplicate_target_ledger_rows_count_once():
    targets = [
        _FakeTarget("O1", "E1"), _FakeTarget("O1", "E1"), _FakeTarget("O1", "E2"),
        _FakeTarget("O2", "E1"),  # same target_event_id, DIFFERENT origin -- must never collapse with O1's E1
    ]
    out = dedupe_targets_by_origin_and_event(targets)
    assert len(out) == 3
    assert [(t.forecast_origin_id, t.target_event_id) for t in out] == [("O1", "E1"), ("O1", "E2"), ("O2", "E1")]


def test_unit7b_02_grid_cells_never_used_as_independent_observation_count():
    for fn in (fold_origin_balanced_metrics, overall_equal_origin_weighted, summarize_by_cluster):
        params = set(inspect.signature(fn).parameters)
        forbidden = {"n_cells", "grid_cell_count", "cell_count", "n_grid_cells"}
        assert not (params & forbidden)
    src = inspect.getsource(fold_origin_balanced_metrics) + inspect.getsource(overall_equal_origin_weighted)
    assert "grid_cell" not in src


def test_unit7b_03_and_04_equal_origin_weight_not_target_weight():
    # Origin A: 20 targets, all percentile=10.0. Origin B: 1 target, percentile=90.0.
    records = [_Rec("A", f"EA{i}", 10.0, False, False) for i in range(20)]
    records += [_Rec("B", "EB1", 90.0, True, True)]

    origin_summaries = summarize_by_cluster(records, cluster_key_fn=lambda r: r.forecast_origin_id)
    assert len(origin_summaries) == 2
    fm = fold_origin_balanced_metrics(origin_summaries)

    # Equal-origin-weighted mean must be (10 + 90) / 2 = 50.0 -- NEVER the
    # target-weighted mean, which would be (20*10 + 1*90) / 21 =~ 14.29.
    target_weighted_mean = (20 * 10.0 + 1 * 90.0) / 21
    assert abs(fm["mean_target_percentile"] - 50.0) < 1e-9
    assert abs(fm["mean_target_percentile"] - target_weighted_mean) > 30.0  # origin A's 20 targets cannot dominate
