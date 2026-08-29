"""Checkpoint 7B Part 44: SELECT7B-01..06 selection-rule tests."""

from __future__ import annotations

import inspect

import pytest

from components.geospatial_tracking.services.model_development.protocol_7b import FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION, FrozenBaselineModelSpecification
from components.geospatial_tracking.services.model_development.selection_7b import PRIMARY_SELECTION_METRIC, select_candidate


def _m(mean, top10=0.5, top5=0.5):
    return {"n_origins": 10, "mean_target_percentile": mean, "top5_capture_rate": top5, "top10_capture_rate": top10}


def test_select7b_01_primary_metric_is_a_frozen_module_constant():
    assert isinstance(PRIMARY_SELECTION_METRIC, str)
    assert PRIMARY_SELECTION_METRIC == "MEAN_ORIGIN_BALANCED_AREA_WEIGHTED_TARGET_PERCENTILE"
    # frozen: calling select_candidate never mutates the module constant
    select_candidate({"A": _m(10.0), "B": _m(90.0)})
    assert PRIMARY_SELECTION_METRIC == "MEAN_ORIGIN_BALANCED_AREA_WEIGHTED_TARGET_PERCENTILE"


def test_select7b_02_highest_primary_metric_wins():
    metrics = {"LOW": _m(20.0), "HIGH": _m(80.0), "MID": _m(50.0)}
    winner, reason = select_candidate(metrics)
    assert winner == "HIGH"
    assert reason == "UNIQUE_MAXIMUM_PRIMARY_METRIC"


def test_select7b_03_exact_tie_uses_top10_then_top5_then_candidate_id():
    # exact tie on primary metric -- broken by TOP10
    metrics = {"A": _m(50.0, top10=0.9, top5=0.1), "B": _m(50.0, top10=0.95, top5=0.1)}
    winner, reason = select_candidate(metrics)
    assert winner == "B"
    assert reason == "TIE_BROKEN_BY_TOP10_CAPTURE"

    # tie on primary AND top10 -- broken by TOP5
    metrics = {"A": _m(50.0, top10=0.9, top5=0.2), "B": _m(50.0, top10=0.9, top5=0.3)}
    winner, reason = select_candidate(metrics)
    assert winner == "B"
    assert reason == "TIE_BROKEN_BY_TOP5_CAPTURE"

    # tie on all three numeric fields -- broken by candidate_id lexical order
    metrics = {"ZZZ": _m(50.0, top10=0.9, top5=0.2), "AAA": _m(50.0, top10=0.9, top5=0.2)}
    winner, reason = select_candidate(metrics)
    assert winner == "AAA"
    assert reason == "TIE_BROKEN_BY_CANDIDATE_ID_LEXICAL_ORDER"

    # never an invented "approximately tied" tolerance -- a tiny numeric
    # difference must NOT be treated as a tie at all.
    metrics = {"A": _m(50.0000001), "B": _m(50.0)}
    winner, reason = select_candidate(metrics)
    assert winner == "A"
    assert reason == "UNIQUE_MAXIMUM_PRIMARY_METRIC"


def test_select7b_04_no_lead_day_specific_selection_parameter_exists():
    params = set(inspect.signature(select_candidate).parameters)
    forbidden = {"lead_days", "lead_day", "horizon", "d1", "d7"}
    assert not (params & forbidden)


def test_select7b_05_selection_is_pure_over_precomputed_metrics_no_repo_or_origin_access():
    params = set(inspect.signature(select_candidate).parameters)
    forbidden = {"repo", "origin", "origins", "held_out_origins", "sri_lanka_origins"}
    assert not (params & forbidden)
    # cannot select from an empty/None-only metrics set -- never silently
    # picks an arbitrary candidate when nothing was ever evaluated
    with pytest.raises(ValueError):
        select_candidate({"A": {"n_origins": 0, "mean_target_percentile": None, "top5_capture_rate": None, "top10_capture_rate": None}})


def test_select7b_06_frozen_spec_never_claims_final_validation():
    spec = FrozenBaselineModelSpecification(
        baseline_family="B1_HOST_DISTANCE_LOG1P", kernel_family="EXPONENTIAL", kernel_scale_km=10.0,
        host_transform="LOG1P_ROBUST_REFERENCE_SCALE", equal_source_semantics="EQUAL_SOURCE_BASELINE",
        scientific_grid_config_hash="x", scientific_domain_protocol_hash="d", scientific_domain_protocol_version="7A.6.2",
        model_development_protocol_hash_7a62="y", evaluation_protocol_hash="e", evaluation_protocol_version="7B.2",
        candidate_registry_hash="z", selection_protocol_hash="w", development_fold_manifest_hash="v",
        selection_metric=PRIMARY_SELECTION_METRIC,
        development_selection_result={}, final_host_reference_decision={}, parameter_status=FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION,
    )
    assert spec.parameter_status == "FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION"
    d = spec.as_dict()
    for forbidden in ("FINAL_PISTES_MODEL", "VALIDATED_PRODUCTION_MODEL", "INFECTION_PROBABILITY_MODEL"):
        assert forbidden not in str(d.values())
