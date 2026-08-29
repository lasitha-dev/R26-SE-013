"""Focused temp-directory tests for the canonical FMD-07B writer only."""

from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from components.geospatial_tracking.services import fmd_model_development_7b_artifact_writer as writer


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prediction(candidate_id: str, score: str) -> dict:
    return {
        "fold_id": "FOLD:2020",
        "experiment_id": "FMD-EXP-04",
        "candidate_id": candidate_id,
        "forecast_origin_id": f"ORIGIN:{candidate_id[-1]}",
        "true_label": 1,
        "predicted_score": score,
        "status": "SCORED",
    }


def _fold_metric(candidate_id: str, pr_auc: float) -> dict:
    return {
        "fold_id": "FOLD:2020",
        "experiment_id": "FMD-EXP-04",
        "candidate_id": candidate_id,
        "n_scored": 1,
        "n_unscored": 0,
        "unscored_reason_counts": {},
        "pr_auc": pr_auc,
        "auroc": 0.75,
        "brier_score": 0.2,
        "selected_threshold": 0.4,
        "f1_at_selected_threshold": 0.8,
        "precision_at_selected_threshold": 0.75,
        "recall_at_selected_threshold": 1.0,
        "specificity_at_selected_threshold": 0.5,
    }


def _fold_summary(candidate_id: str, primary_value: float) -> dict:
    return {
        "experiment_id": "FMD-EXP-04",
        "candidate_id": candidate_id,
        "n_usable_folds": 1,
        "n_contributing_folds": 1,
        "primary_selection_metric_name": "PR-AUC",
        "primary_metric_aggregation_rule": (
            "EQUAL_FOLD_WEIGHTED_MEAN_PR_AUC_OVER_CONTRIBUTING_USABLE_FOLDS"
        ),
        "primary_selection_metric_value": primary_value,
        "median_pr_auc": primary_value,
        "mean_auroc": 0.75,
        "mean_brier_score": 0.2,
        "median_selected_threshold": 0.4,
    }


@pytest.fixture
def canonical_payloads() -> dict[str, object]:
    selected_candidate_id = "FMD07B:ML:CANDIDATE-A"
    return {
        writer.FMD07B_CANDIDATE_ELIGIBILITY: {
            "checkpoint": "FMD-07B",
            "candidates": [
                {"experiment_id": "FMD-EXP-04", "eligibility": "EXECUTABLE"}
            ],
        },
        writer.FMD07B_CANDIDATE_REGISTRY: {
            "checkpoint": "FMD-07B",
            "candidate_ids": [selected_candidate_id, "FMD07B:ML:CANDIDATE-B"],
        },
        writer.FMD07B_CHRONOLOGICAL_FOLD_MANIFEST: {
            "checkpoint": "FMD-07B",
            "folds": [
                {
                    "fold_id": "FOLD:2020",
                    "common_support_origin_ids": ["ORIGIN:A", "ORIGIN:B"],
                }
            ],
        },
        # Deliberately reverse candidate order; the writer owns canonical order.
        writer.FMD07B_FOLD_PREDICTIONS: [
            _prediction("FMD07B:ML:CANDIDATE-B", "0.25"),
            _prediction(selected_candidate_id, "0.75"),
        ],
        writer.FMD07B_FOLD_CANDIDATE_METRICS: [
            _fold_metric("FMD07B:ML:CANDIDATE-B", 0.6),
            _fold_metric(selected_candidate_id, 0.8),
        ],
        writer.FMD07B_FOLD_SUMMARY_METRICS: [
            _fold_summary("FMD07B:ML:CANDIDATE-B", 0.6),
            _fold_summary(selected_candidate_id, 0.8),
        ],
        writer.FMD07B_PREPROCESSING_CALIBRATION_AUDIT: {
            "checkpoint": "FMD-07B",
            "training_fold_only": True,
            "audit": [{"candidate_id": selected_candidate_id, "calibration": "NONE"}],
        },
        writer.FMD07B_CANDIDATE_SELECTION_SUMMARY: {
            "checkpoint": "FMD-07B",
            "selected_candidate_id": selected_candidate_id,
            "selection_rule": "FROZEN_EXTERNAL_FINALIZER_RESULT",
            "deterministic_ranking": [selected_candidate_id, "FMD07B:ML:CANDIDATE-B"],
        },
        writer.FMD07B_FROZEN_MODEL_SPEC: {
            "checkpoint": "FMD-07B",
            "selected_candidate_id": selected_candidate_id,
            "model": {"algorithm_family": "LOGISTIC_REGRESSION", "parameters": {"C": 1.0}},
            "preprocessing": {"imputation": "TRAINING_MEDIAN", "scaling": "STANDARD"},
            "calibration": {"method": "NONE"},
            "threshold": 0.4,
            "final_refit_state": {
                "state_format": "TEST_FIXTURE_ONLY",
                "coefficients": [0.1, -0.2],
            },
            "implementation_identity": {
                "module": "components.geospatial_tracking.services.test_fixture"
            },
            "resolved_direct_dependency_versions": {"scikit-learn": "1.8.0"},
        },
        writer.FMD07B_MANIFEST: {
            "checkpoint": "FMD-07B",
            "completion_token": "FMD-07B_COMPLETE_READY_FOR_FMD-08",
            "held_out_used": False,
            "sri_lanka_used": False,
            "locked_test_used": False,
            "input_artifact_sha256": {
                "fmd07_r2b3_development_feature_matrix.csv": "a" * 64,
                "fmd07_r2b3_manifest.json": "b" * 64,
            },
            "implementation_identity": {
                "module": (
                    "components.geospatial_tracking.services."
                    "fmd_model_development_7b_artifact_writer"
                ),
                "serialization_format": writer.SERIALIZATION_FORMAT,
            },
            "python_version": "3.13.7",
            "resolved_direct_dependency_versions": {"scikit-learn": "1.8.0"},
        },
    }


def test_writer_emits_exactly_ten_canonical_files_with_fixed_csv_order(
    tmp_path, canonical_payloads
):
    result = writer.write_canonical_fmd07b_artifacts(tmp_path, canonical_payloads)

    assert result.artifact_count == writer.ARTIFACT_COUNT == 10
    assert tuple(path.name for path in result.artifact_paths) == writer.CANONICAL_ARTIFACT_FILENAMES
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(
        writer.CANONICAL_ARTIFACT_FILENAMES
    )

    with (tmp_path / writer.FMD07B_FOLD_PREDICTIONS).open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0]) == writer.FOLD_PREDICTION_COLUMNS
    assert [row["candidate_id"] for row in rows] == [
        "FMD07B:ML:CANDIDATE-A",
        "FMD07B:ML:CANDIDATE-B",
    ]


def test_same_input_produces_byte_identical_artifacts_across_two_runs(
    tmp_path, canonical_payloads
):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = writer.write_canonical_fmd07b_artifacts(first_dir, canonical_payloads)
    second = writer.write_canonical_fmd07b_artifacts(second_dir, canonical_payloads)

    assert first.artifact_sha256 == second.artifact_sha256
    for filename in writer.CANONICAL_ARTIFACT_FILENAMES:
        assert (first_dir / filename).read_bytes() == (second_dir / filename).read_bytes()


def test_hashes_are_deterministic_and_manifest_records_all_non_self_hashes(
    tmp_path, canonical_payloads
):
    result = writer.write_canonical_fmd07b_artifacts(tmp_path, canonical_payloads)
    expected = {filename: _sha256(tmp_path / filename) for filename in writer.CANONICAL_ARTIFACT_FILENAMES}
    assert dict(result.artifact_sha256) == expected

    manifest = json.loads((tmp_path / writer.FMD07B_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["artifact_count"] == 10
    assert manifest["artifact_filenames"] == list(writer.CANONICAL_ARTIFACT_FILENAMES)
    assert manifest["output_artifact_sha256"] == {
        filename: expected[filename]
        for filename in writer.CANONICAL_ARTIFACT_FILENAMES
        if filename != writer.FMD07B_MANIFEST
    }
    assert (
        manifest["output_artifact_sha256_scope"]
        == "ALL_CANONICAL_OUTPUTS_EXCEPT_SELF_REFERENTIAL_MANIFEST"
    )


def test_atomic_temp_file_replace_path_is_used_for_every_artifact(
    tmp_path, canonical_payloads, monkeypatch
):
    observed: list[tuple[Path, Path]] = []
    real_replace = writer.os.replace

    def recording_replace(source, target):
        source_path = Path(source)
        target_path = Path(target)
        assert source_path.exists()
        assert source_path.parent == target_path.parent == tmp_path
        assert source_path.suffix == ".tmp"
        observed.append((source_path, target_path))
        real_replace(source_path, target_path)

    monkeypatch.setattr(writer.os, "replace", recording_replace)
    writer.write_canonical_fmd07b_artifacts(tmp_path, canonical_payloads)

    assert [target.name for _source, target in observed] == list(
        writer.CANONICAL_ARTIFACT_FILENAMES
    )
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize(
    "remove_required_input",
    [
        lambda payloads: payloads.pop(writer.FMD07B_CANDIDATE_REGISTRY),
        lambda payloads: payloads[writer.FMD07B_MANIFEST].pop("python_version"),
        lambda payloads: payloads[writer.FMD07B_FOLD_PREDICTIONS][0].pop("status"),
        lambda payloads: payloads[writer.FMD07B_FROZEN_MODEL_SPEC].pop("final_refit_state"),
    ],
)
def test_missing_required_input_fails_closed_without_writing(
    tmp_path, canonical_payloads, remove_required_input
):
    incomplete = deepcopy(canonical_payloads)
    remove_required_input(incomplete)

    with pytest.raises(writer.CanonicalArtifactValidationError):
        writer.write_canonical_fmd07b_artifacts(tmp_path, incomplete)
    assert not tmp_path.exists() or not list(tmp_path.iterdir())


def test_firewall_flags_are_preserved_and_must_remain_false(tmp_path, canonical_payloads):
    writer.write_canonical_fmd07b_artifacts(tmp_path, canonical_payloads)
    manifest = json.loads((tmp_path / writer.FMD07B_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["held_out_used"] is canonical_payloads[writer.FMD07B_MANIFEST][
        "held_out_used"
    ] is False
    assert manifest["sri_lanka_used"] is canonical_payloads[writer.FMD07B_MANIFEST][
        "sri_lanka_used"
    ] is False
    assert manifest["locked_test_used"] is canonical_payloads[writer.FMD07B_MANIFEST][
        "locked_test_used"
    ] is False

    contaminated = deepcopy(canonical_payloads)
    contaminated[writer.FMD07B_MANIFEST]["held_out_used"] = True
    with pytest.raises(writer.CanonicalArtifactValidationError, match="held_out_used must be false"):
        writer.write_canonical_fmd07b_artifacts(tmp_path / "contaminated", contaminated)


def test_writer_cannot_invoke_candidate_execution_training_or_scoring(
    tmp_path, canonical_payloads, monkeypatch
):
    from components.geospatial_tracking.services import fmd_model_development_7b as development
    from components.geospatial_tracking.services import fmd_model_development_7b_execution as execution

    calls: list[str] = []

    def forbidden(*_args, **_kwargs):
        calls.append("forbidden")
        raise AssertionError("canonical writer invoked candidate execution/training/scoring")

    monkeypatch.setattr(execution, "run_fmd07b_partial_development", forbidden)
    monkeypatch.setattr(execution, "run_naive_fold", forbidden)
    monkeypatch.setattr(execution, "run_ml_fold", forbidden)
    monkeypatch.setattr(development.NaiveStatisticalRunner, "fit_training_fold", forbidden)
    monkeypatch.setattr(development.SpatialDistanceRunner, "score_validation_origin", forbidden)
    monkeypatch.setattr(development.MlEstimatorRunner, "fit_training_fold", forbidden)

    writer.write_canonical_fmd07b_artifacts(tmp_path, canonical_payloads)
    assert calls == []

