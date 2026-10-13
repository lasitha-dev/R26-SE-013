"""Checkpoint 7B Part 41: METRIC7B-01..08 area-weighted ranking metric
tests."""

from __future__ import annotations

import random

from components.geospatial_tracking.services.model_development.baseline_scoring import (
    MODEL_INPUT_INCOMPLETE,
    SCORED,
    CellScore,
    compute_area_weighted_percentiles,
    compute_target_cell_ranks,
)


def _cs(gcid: str, *, score, area=10.0, overlap=10.0, status=SCORED, scientific_cell_id=None) -> CellScore:
    return CellScore(grid_cell_id=gcid, scientific_cell_id=scientific_cell_id or f"SCICELL:{gcid}", area_km2=area, domain_overlap_area_km2=overlap, score=score, status=status)


def test_metric7b_01_partial_edge_cell_uses_domain_overlap_area_not_full_area():
    # Two cells, equal full area, but cell A is a heavily-clipped edge
    # cell (small overlap) and cell B is fully interior (overlap==area).
    cells = [
        _cs("A", score=1.0, area=25.0, overlap=2.0),
        _cs("B", score=2.0, area=25.0, overlap=23.0),
    ]
    pct = compute_area_weighted_percentiles(cells)
    # total_valid_domain_area = 2 + 23 = 25 (never 25+25=50)
    # A: area_less=0, area_equal=2 -> 100*(0+1)/25 = 4.0
    # B: area_less=2, area_equal=23 -> 100*(2+11.5)/25 = 54.0
    assert abs(pct["A"] - 4.0) < 1e-9
    assert abs(pct["B"] - 54.0) < 1e-9


def test_metric7b_02_equal_scores_use_area_weighted_midrank():
    cells = [
        _cs("A", score=5.0, overlap=10.0),
        _cs("B", score=5.0, overlap=10.0),
        _cs("C", score=1.0, overlap=10.0),
    ]
    pct = compute_area_weighted_percentiles(cells)
    # total = 30; C: area_less=0, area_equal=10 -> 100*5/30=16.667
    # A,B tied group area=20; area_less=10(from C) area_equal=20 -> 100*(10+10)/30=66.667
    assert abs(pct["C"] - (100.0 * 5.0 / 30.0)) < 1e-9
    assert abs(pct["A"] - pct["B"]) < 1e-12
    assert abs(pct["A"] - (100.0 * 20.0 / 30.0)) < 1e-9


def test_metric7b_03_grid_cell_ordering_does_not_change_percentile():
    cells = [_cs(f"C{i}", score=float(i), overlap=1.0) for i in range(10)]
    pct_forward = compute_area_weighted_percentiles(cells)
    shuffled = list(cells)
    random.Random(7).shuffle(shuffled)
    pct_shuffled = compute_area_weighted_percentiles(shuffled)
    assert pct_forward == pct_shuffled


def test_metric7b_04_duplicating_a_zero_overlap_cell_cannot_change_metric():
    base = [
        _cs("A", score=1.0, overlap=10.0),
        _cs("B", score=2.0, overlap=10.0),
    ]
    pct_base = compute_area_weighted_percentiles(base)
    with_dup = base + [_cs("ZERO", score=999.0, overlap=0.0)]
    pct_with_dup = compute_area_weighted_percentiles(with_dup)
    assert pct_base["A"] == pct_with_dup["A"]
    assert pct_base["B"] == pct_with_dup["B"]


def test_metric7b_05_top5_iff_percentile_ge_95():
    # 20 equal-area cells, scores 1..20 -> top cell should sit at percentile >= 95
    cells = [_cs(f"C{i}", score=float(i), overlap=1.0) for i in range(1, 21)]
    pct = compute_area_weighted_percentiles(cells)
    top_cell_pct = pct["C20"]
    assert top_cell_pct >= 95.0
    low_cell_pct = pct["C1"]
    assert low_cell_pct < 95.0


def test_metric7b_06_top10_iff_percentile_ge_90():
    cells = [_cs(f"C{i}", score=float(i), overlap=1.0) for i in range(1, 21)]
    pct = compute_area_weighted_percentiles(cells)
    assert pct["C20"] >= 90.0
    assert pct["C1"] < 90.0


def test_metric7b_07_target_cell_rank_tiebreak_uses_scientific_cell_id():
    cells = [
        _cs("A", score=5.0, scientific_cell_id="SCICELL:zzz"),
        _cs("B", score=5.0, scientific_cell_id="SCICELL:aaa"),
        _cs("C", score=1.0, scientific_cell_id="SCICELL:mmm"),
    ]
    ranks = compute_target_cell_ranks(cells)
    # B (aaa) ties A (zzz) on score but sorts first lexicographically
    assert ranks["B"] == 1
    assert ranks["A"] == 2
    assert ranks["C"] == 3


def test_metric7b_08_metrics_never_emit_true_negative_semantics():
    import inspect

    from components.geospatial_tracking.services.model_development import baseline_scoring

    source = inspect.getsource(baseline_scoring)
    for forbidden in ("TRUE_NEGATIVE", "DISEASE_FREE", "HEALTHY_CELL"):
        assert forbidden not in source


def test_metric7b_incomplete_cells_still_occupy_denominator_area():
    cells = [
        _cs("A", score=1.0, overlap=10.0),
        _cs("B", score=None, overlap=10.0, status=MODEL_INPUT_INCOMPLETE),
    ]
    pct = compute_area_weighted_percentiles(cells)
    # only A is scored -- but denominator includes B's 10 km2 too
    assert "B" not in pct
    assert abs(pct["A"] - (100.0 * 0.5 * 10.0 / 20.0)) < 1e-9
