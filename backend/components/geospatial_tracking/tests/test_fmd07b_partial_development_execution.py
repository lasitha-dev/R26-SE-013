"""FMD-07B PARTIAL development execution (FMD-EXP-01 + FMD-EXP-04 only).

Lightweight structural/regression coverage for
`services/fmd_model_development_7b_execution.py`. Does not re-run the full
21-fold x 12-candidate real development pass (already executed directly and
persisted under
`local_data/processed/fmd/model_development/fmd07b_partial_exp01_exp04/`) --
covers input hash verification, fold-usability recomputation, per-fold naive/
ML scoring wiring, and the FMD-EXP-02-deferred/no-final-selection invariants
on small real slices of the frozen inputs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from components.geospatial_tracking.services.fmd_model_development_7b_execution import (
    DEFERRED_EXPERIMENT_IDS,
    EXECUTED_EXPERIMENT_IDS,
    FROZEN_EXCLUDED_FOLD_IDS,
    FROZEN_USABLE_FOLD_COUNT,
    NAIVE_SCORE_UNAVAILABLE,
    TRAINING_FOLD_SINGLE_CLASS_SKIPPED,
    classify_fold_usability,
    compute_fold_metrics,
    load_and_verify_r2b3_inputs,
    load_calendar_year_folds,
    run_naive_fold,
)
from components.geospatial_tracking.services.fmd_model_development_7b import validate_fmd07b_fold_input
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin

_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_r2b3_inputs_load_and_hash_verify_against_frozen_manifest():
    inputs = load_and_verify_r2b3_inputs(_REPO_ROOT)
    assert inputs.matrix.shape == (3761, 105)
    assert len(inputs.predictor_value_columns) == 47
    assert all(c.endswith("_value") for c in inputs.predictor_value_columns)
    assert set(inputs.matrix["model_fitting_role"].unique()) == {"FIT_DEVELOPMENT"}
    assert set(int(v) for v in inputs.matrix["risk_target_label"].unique()) == {0, 1}


def test_r2b3_hash_mismatch_is_a_hard_stop(tmp_path, monkeypatch):
    import components.geospatial_tracking.services.fmd_model_development_7b_execution as execmod

    monkeypatch.setattr(execmod, "R2B3_MATRIX_REL", "backend/requirements.txt")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_and_verify_r2b3_inputs(_REPO_ROOT)


def test_fold_usability_recomputation_matches_frozen_cv_validity_policy():
    inputs = load_and_verify_r2b3_inputs(_REPO_ROOT)
    labels_by_origin = {
        row.forecast_origin_id: int(row.risk_target_label) for row in inputs.matrix.itertuples(index=False)
    }
    folds = load_calendar_year_folds(_REPO_ROOT)
    usable_ids = []
    excluded_ids = []
    for fold in folds:
        usable, _reasons = classify_fold_usability(fold, labels_by_origin)
        (usable_ids if usable else excluded_ids).append(fold.fold_id)
    assert len(usable_ids) == FROZEN_USABLE_FOLD_COUNT
    assert set(excluded_ids) == set(FROZEN_EXCLUDED_FOLD_IDS)


def test_naive_fold_scoring_excludes_unseen_training_countries_never_fabricates():
    inputs = load_and_verify_r2b3_inputs(_REPO_ROOT)
    matrix = inputs.matrix
    countries_by_origin = {row.forecast_origin_id: row.country for row in matrix.itertuples(index=False)}
    labels_by_origin = {row.forecast_origin_id: int(row.risk_target_label) for row in matrix.itertuples(index=False)}

    origins = [
        ForecastOrigin(
            forecast_origin_id=row.forecast_origin_id,
            country=row.country,
            t0=row.t0,
            temporal_mode="RETROSPECTIVE_PROXY",
        )
        for row in matrix.itertuples(index=False)
    ]
    folds = {f.fold_id: f for f in load_calendar_year_folds(_REPO_ROOT)}
    fold_2010 = validate_fmd07b_fold_input(origins, folds["FOLD:2010"])

    predictions, unscored_reasons = run_naive_fold(
        fold_2010, countries_by_origin=countries_by_origin, labels_by_origin=labels_by_origin
    )
    assert set(predictions) | set(unscored_reasons) == set(fold_2010.validation_origin_ids)
    assert all(reason == NAIVE_SCORE_UNAVAILABLE for reason in unscored_reasons.values())
    training_countries = {countries_by_origin[oid] for oid in fold_2010.training_origin_ids}
    for oid in unscored_reasons:
        assert countries_by_origin[oid] not in training_countries
    for oid, rate in predictions.items():
        assert 0.0 <= rate <= 1.0


def test_compute_fold_metrics_returns_none_when_scorable_subset_is_single_class():
    predictions = {"A": 0.6, "B": 0.4}
    labels_by_origin = {"A": 1, "B": 1}
    assert compute_fold_metrics(predictions, {}, labels_by_origin, ["A", "B"]) is None


def test_compute_fold_metrics_pr_auc_is_bounded_and_deterministic():
    predictions = {"A": 0.9, "B": 0.1, "C": 0.8, "D": 0.2}
    labels_by_origin = {"A": 1, "B": 0, "C": 1, "D": 0}
    m1 = compute_fold_metrics(predictions, {}, labels_by_origin, ["A", "B", "C", "D"])
    m2 = compute_fold_metrics(predictions, {}, labels_by_origin, ["A", "B", "C", "D"])
    assert m1 is not None and m2 is not None
    assert m1.pr_auc == m2.pr_auc
    assert 0.0 <= m1.pr_auc <= 1.0
    assert 0.0 <= m1.auroc <= 1.0
    assert m1.pr_auc == 1.0  # perfectly separated scores


def test_partial_execution_scope_constants_reflect_deferred_fmd_exp02():
    assert EXECUTED_EXPERIMENT_IDS == ("FMD-EXP-01", "FMD-EXP-04")
    assert DEFERRED_EXPERIMENT_IDS == ("FMD-EXP-02",)


def test_partial_manifest_on_disk_declares_no_final_selection_and_no_forbidden_data_use():
    import json

    manifest_path = (
        _REPO_ROOT
        / "local_data/processed/fmd/model_development/fmd07b_partial_exp01_exp04"
        / "fmd07b_partial_development_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["held_out_used"] is False
    assert manifest["sri_lanka_used"] is False
    assert manifest["locked_test_used"] is False
    assert manifest["executed_experiment_ids"] == ["FMD-EXP-01", "FMD-EXP-04"]
    assert manifest["deferred_experiment_ids"] == ["FMD-EXP-02"]
    assert manifest["final_candidate_selection_status"].startswith("NOT_PERFORMED")
    assert manifest["completion_token"] == "FMD-07B_BLOCKED_MINIMUM_EXECUTABLE_COMPARISON_SET_NOT_READY"
    assert len(manifest["development_ranking_this_pass"]) == 12
