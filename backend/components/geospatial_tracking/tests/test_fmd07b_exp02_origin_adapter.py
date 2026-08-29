"""Focused synthetic tests for the FMD-07B EXP-02 origin adapter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from components.geospatial_tracking.services.fmd_model_development_7b import (
    Fmd07bFoldInput,
    SpatialDistanceRunner,
)
from components.geospatial_tracking.services.fmd_model_development_7b_exp02_origin import (
    AREA_WEIGHTED_MEAN_OVER_COMPLETE_ORIGIN_DOMAIN,
    FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM,
    Exp02OriginExecutionAdapter,
    aggregate_exp02_origin_cell_scores,
)
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.model_development.baseline_scoring import (
    CellScore,
    MODEL_INPUT_INCOMPLETE,
    SCORED,
)
from components.geospatial_tracking.services.model_development.candidate_registry_7b import (
    BaselineCandidateSpec,
)


def _cell_score(
    cell_id: str,
    *,
    score: float | None,
    overlap_area: float,
    status: str = SCORED,
) -> CellScore:
    return CellScore(
        grid_cell_id=cell_id,
        scientific_cell_id=f"SCI:{cell_id}",
        area_km2=900.0,
        domain_overlap_area_km2=overlap_area,
        score=score,
        status=status,
    )


def _fold() -> Fmd07bFoldInput:
    return Fmd07bFoldInput(
        fold_id="FOLD:SYNTHETIC",
        training_origin_ids=("ORIGIN:TRAIN",),
        validation_origin_ids=("ORIGIN:VALIDATION",),
        purged_origin_ids=(),
    )


def _candidate() -> BaselineCandidateSpec:
    return BaselineCandidateSpec(
        candidate_id="FMD07B:SPATIAL:SYNTHETIC",
        baseline_family="B0_DISTANCE_ONLY",
        host_factor_candidate=None,
        kernel_family="EXPONENTIAL",
        kernel_scale_km=10.0,
        source_weighting="EQUAL_SOURCE_BASELINE",
        output_label="RELATIVE_SPATIAL_SCORE",
    )


def _grid_cells() -> list[dict]:
    return [
        {
            "grid_cell_id": "CELL:B",
            "scientific_cell_id": "SCI:CELL:B",
            "centroid_lat": 15.1,
            "centroid_lon": 101.0,
            "area_km2": 900.0,
            "domain_overlap_area_km2": 300.0,
        },
        {
            "grid_cell_id": "CELL:A",
            "scientific_cell_id": "SCI:CELL:A",
            "centroid_lat": 15.0,
            "centroid_lon": 101.0,
            "area_km2": 900.0,
            "domain_overlap_area_km2": 100.0,
        },
    ]


def test_complete_multicell_origin_uses_nonuniform_true_domain_area_weights():
    result = aggregate_exp02_origin_cell_scores(
        fold_id="FOLD:SYNTHETIC",
        candidate_id="CANDIDATE:1",
        forecast_origin_id="ORIGIN:1",
        cell_scores=(
            _cell_score("B", score=3.0, overlap_area=3.0),
            _cell_score("A", score=1.0, overlap_area=1.0),
        ),
    )

    assert result.status == SCORED
    assert result.score == pytest.approx((1.0 * 1.0 + 3.0 * 3.0) / 4.0)
    assert result.score != pytest.approx(2.0)  # not an unweighted cell mean
    assert result.origin_scalar_rule == AREA_WEIGHTED_MEAN_OVER_COMPLETE_ORIGIN_DOMAIN
    assert result.engineering_grid_size_km == FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM == 30.0


def test_incomplete_origin_returns_none_and_preserves_existing_incomplete_status():
    result = aggregate_exp02_origin_cell_scores(
        fold_id="FOLD:SYNTHETIC",
        candidate_id="CANDIDATE:1",
        forecast_origin_id="ORIGIN:1",
        cell_scores=(
            _cell_score("A", score=None, overlap_area=1.0, status=MODEL_INPUT_INCOMPLETE),
        ),
    )

    assert result.status == MODEL_INPUT_INCOMPLETE
    assert result.score is None


def test_mixed_safe_and_incomplete_cells_never_produce_a_partial_domain_scalar():
    result = aggregate_exp02_origin_cell_scores(
        fold_id="FOLD:SYNTHETIC",
        candidate_id="CANDIDATE:1",
        forecast_origin_id="ORIGIN:1",
        cell_scores=(
            _cell_score("A", score=7.0, overlap_area=99.0),
            _cell_score("B", score=None, overlap_area=1.0, status=MODEL_INPUT_INCOMPLETE),
        ),
    )

    assert result.status == MODEL_INPUT_INCOMPLETE
    assert result.score is None


def test_unsafe_component_count_reaches_adapter_and_blocks_even_scored_safe_subset():
    captured = {}
    original_cell_score = _cell_score("A", score=4.0, overlap_area=1.0)

    class CapturingRunner:
        experiment_id = "FMD-EXP-02"
        candidates = (SimpleNamespace(candidate_id="CANDIDATE:1"),)

        def score_validation_origin(self, fold, **kwargs):
            captured.update(kwargs)
            return {"CANDIDATE:1": [original_cell_score]}

    adapter = Exp02OriginExecutionAdapter(CapturingRunner())
    result = adapter.execute_validation_origin(
        _fold(),
        forecast_origin_id="ORIGIN:VALIDATION",
        grid_cells=[],
        sources=[],
        reference_profile=None,
        unsafe_component_count=3,
    )[0]

    assert captured["unsafe_component_count"] == 3
    assert result.unsafe_component_count == 3
    assert result.status == MODEL_INPUT_INCOMPLETE
    assert result.score is None


def test_aggregation_is_deterministic_under_cell_reordering():
    cells = (
        _cell_score("C", score=0.3, overlap_area=0.7),
        _cell_score("A", score=0.1, overlap_area=0.2),
        _cell_score("B", score=0.2, overlap_area=0.1),
    )
    kwargs = {
        "fold_id": "FOLD:SYNTHETIC",
        "candidate_id": "CANDIDATE:1",
        "forecast_origin_id": "ORIGIN:1",
    }

    first = aggregate_exp02_origin_cell_scores(cell_scores=cells, **kwargs)
    second = aggregate_exp02_origin_cell_scores(cell_scores=tuple(reversed(cells)), **kwargs)

    assert first == second
    assert tuple(cell.grid_cell_id for cell in first.per_cell_scores) == ("A", "B", "C")


def test_aggregation_retains_the_exact_per_cell_objects_and_values():
    cells = (
        _cell_score("B", score=2.5, overlap_area=3.0),
        _cell_score("A", score=1.25, overlap_area=1.0),
    )
    before = tuple(cell.as_dict() for cell in cells)

    result = aggregate_exp02_origin_cell_scores(
        fold_id="FOLD:SYNTHETIC",
        candidate_id="CANDIDATE:1",
        forecast_origin_id="ORIGIN:1",
        cell_scores=cells,
    )

    assert tuple(cell.as_dict() for cell in cells) == before
    assert {id(cell) for cell in result.per_cell_scores} == {id(cell) for cell in cells}
    assert {cell.score for cell in result.per_cell_scores} == {1.25, 2.5}


def test_complete_adapter_output_reuses_unchanged_spatial_runner_cell_scores():
    runner = SpatialDistanceRunner(candidates=(_candidate(),))
    adapter = Exp02OriginExecutionAdapter(runner)
    sources = [EligibleSourcePoint(source_id="SOURCE:1", latitude=15.0, longitude=101.0)]
    call = {
        "forecast_origin_id": "ORIGIN:VALIDATION",
        "grid_cells": _grid_cells(),
        "sources": sources,
        "reference_profile": None,
        "unsafe_component_count": 0,
    }

    direct = runner.score_validation_origin(_fold(), **call)[_candidate().candidate_id]
    adapted = adapter.execute_validation_origin(_fold(), **call)[0]
    expected = sum(
        cell.score * cell.domain_overlap_area_km2 for cell in direct
    ) / sum(cell.domain_overlap_area_km2 for cell in direct)

    assert adapted.status == SCORED
    assert adapted.score == pytest.approx(expected)
    assert adapted.per_cell_scores == tuple(
        sorted(direct, key=lambda cell: (cell.scientific_cell_id or "", cell.grid_cell_id))
    )
    assert [cell.score for cell in adapted.per_cell_scores] == [
        cell.score
        for cell in sorted(direct, key=lambda cell: (cell.scientific_cell_id or "", cell.grid_cell_id))
    ]


def test_adapter_rejects_any_grid_size_other_than_frozen_30km():
    with pytest.raises(ValueError, match="30.0 km"):
        Exp02OriginExecutionAdapter(
            SpatialDistanceRunner(candidates=(_candidate(),)),
            engineering_grid_size_km=5.0,
        )
