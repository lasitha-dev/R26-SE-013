"""Focused tests for read-only EXP-01/EXP-04 persisted prediction reuse."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

import components.geospatial_tracking.services.fmd_model_development_7b as development_mod
from components.geospatial_tracking.services.fmd_model_development_7b import build_frozen_common_support
from components.geospatial_tracking.services.fmd_model_development_7b_prediction_reuse import (
    PARTIAL_RESULTS_RELATIVE_DIR,
    PERSISTED_MANIFEST_FILENAME,
    PERSISTED_PREDICTION_SCHEMA,
    PERSISTED_PREDICTIONS_FILENAME,
    PersistedPredictionIntegrityError,
    filter_persisted_predictions_to_common_support,
    frozen_persisted_candidate_ids,
    load_persisted_exp01_exp04_predictions,
)
from components.geospatial_tracking.services.fmd_model_development_7b_execution import (
    DEFERRED_EXPERIMENT_IDS,
    EXECUTED_EXPERIMENT_IDS,
    PARTIAL_EXECUTION_TOKEN,
)
from components.geospatial_tracking.services.model_development.baseline_scoring import SCORED

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ORIGIN_SCORE_TEXT = {
    "ORIGIN:2": "0.90000000000000001",
    "ORIGIN:1": "0.12345000000000000",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _default_rows() -> list[dict[str, str]]:
    candidates = frozen_persisted_candidate_ids()
    rows = []
    for experiment_id in reversed(EXECUTED_EXPERIMENT_IDS):
        for candidate_id in reversed(candidates[experiment_id]):
            for origin_id, score_text in _ORIGIN_SCORE_TEXT.items():
                rows.append(
                    {
                        "fold_id": "FOLD:SYNTHETIC",
                        "experiment_id": experiment_id,
                        "candidate_id": candidate_id,
                        "forecast_origin_id": origin_id,
                        "true_label": "1" if origin_id == "ORIGIN:2" else "0",
                        "predicted_score": score_text,
                        "status": SCORED,
                    }
                )
    return rows


def _write_artifacts(repo_root: Path, *, rows: list[dict[str, str]] | None = None) -> tuple[Path, list[dict[str, str]]]:
    model_dir = repo_root / PARTIAL_RESULTS_RELATIVE_DIR.parent
    artifact_dir = repo_root / PARTIAL_RESULTS_RELATIVE_DIR
    artifact_dir.mkdir(parents=True)

    input_payloads = {
        "synthetic_matrix.csv": b"frozen synthetic matrix\n",
        "synthetic_audit.csv": b"frozen synthetic audit\n",
    }
    for filename, payload in input_payloads.items():
        (model_dir / filename).write_bytes(payload)

    persisted_rows = _default_rows() if rows is None else rows
    predictions_path = artifact_dir / PERSISTED_PREDICTIONS_FILENAME
    with predictions_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PERSISTED_PREDICTION_SCHEMA)
        writer.writeheader()
        writer.writerows(persisted_rows)
    predictions_sha256 = _sha256(predictions_path.read_bytes())

    candidates = frozen_persisted_candidate_ids()
    manifest = {
        "checkpoint": development_mod.CHECKPOINT,
        "partial_execution_token": PARTIAL_EXECUTION_TOKEN,
        "dependency_requirement": development_mod.DEPENDENCY_REQUIREMENT,
        "sklearn_version": development_mod.REQUIRED_SKLEARN_VERSION,
        "random_seed": development_mod.RANDOM_SEED,
        "held_out_used": False,
        "sri_lanka_used": False,
        "locked_test_used": False,
        "executed_experiment_ids": list(EXECUTED_EXPERIMENT_IDS),
        "deferred_experiment_ids": list(DEFERRED_EXPERIMENT_IDS),
        "usable_fold_ids": ["FOLD:SYNTHETIC"],
        "naive_candidate": {"candidate_id": candidates["FMD-EXP-01"][0]},
        "ml_candidates": {candidate_id: {} for candidate_id in candidates["FMD-EXP-04"]},
        "input_artifact_sha256": {
            filename: _sha256(payload) for filename, payload in input_payloads.items()
        },
        "fold_predictions_csv_sha256_after_write": predictions_sha256,
    }
    (artifact_dir / PERSISTED_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return artifact_dir, persisted_rows


def _support():
    persisted_candidates = frozen_persisted_candidate_ids()
    all_candidates = {
        "FMD-EXP-01": persisted_candidates["FMD-EXP-01"],
        "FMD-EXP-02": ("EXP02:SYNTHETIC",),
        "FMD-EXP-04": persisted_candidates["FMD-EXP-04"],
    }
    structural_rows = [
        {
            "experiment_id": experiment_id,
            "candidate_id": candidate_id,
            "forecast_origin_id": origin_id,
            "structurally_scoreable": True,
        }
        for experiment_id, candidate_ids in all_candidates.items()
        for candidate_id in candidate_ids
        for origin_id in reversed(tuple(_ORIGIN_SCORE_TEXT))
    ]
    return build_frozen_common_support(
        fold_id="FOLD:SYNTHETIC",
        validation_origin_ids=tuple(_ORIGIN_SCORE_TEXT),
        candidate_ids_by_experiment=all_candidates,
        structural_availability_rows=list(reversed(structural_rows)),
    )


@pytest.fixture
def synthetic_artifacts(tmp_path):
    _artifact_dir, rows = _write_artifacts(tmp_path)
    return tmp_path, rows


def test_repository_exp01_and_all_exp04_persisted_rows_load_with_verified_provenance():
    persisted = load_persisted_exp01_exp04_predictions(_REPO_ROOT)
    expected_candidates = frozen_persisted_candidate_ids()

    assert persisted.provenance_verified is True
    assert {row.candidate_id for row in persisted.rows_for_experiment("FMD-EXP-01")} == set(
        expected_candidates["FMD-EXP-01"]
    )
    assert persisted.candidate_ids("FMD-EXP-04") == expected_candidates["FMD-EXP-04"]
    assert {row.candidate_id for row in persisted.rows_for_experiment("FMD-EXP-04")} == set(
        expected_candidates["FMD-EXP-04"]
    )


def test_loading_never_invokes_training_or_fitting(synthetic_artifacts, monkeypatch):
    repo_root, _rows = synthetic_artifacts

    def forbidden(*args, **kwargs):
        raise AssertionError("training/fitting path was invoked")

    monkeypatch.setattr(development_mod.NaiveStatisticalRunner, "fit_training_fold", forbidden)
    monkeypatch.setattr(development_mod.MlEstimatorRunner, "fit_training_fold", forbidden)

    persisted = load_persisted_exp01_exp04_predictions(repo_root)
    assert persisted.provenance_verified is True


def test_common_support_filter_is_deterministic_and_preserves_exact_prediction_text(synthetic_artifacts):
    repo_root, source_rows = synthetic_artifacts
    persisted = load_persisted_exp01_exp04_predictions(repo_root)
    support = _support()

    first = filter_persisted_predictions_to_common_support(persisted, support)
    second = filter_persisted_predictions_to_common_support(persisted, support)
    source_score_by_key = {
        (row["experiment_id"], row["candidate_id"], row["forecast_origin_id"]): row["predicted_score"]
        for row in source_rows
    }

    assert first == second
    assert len(first) == 2 * sum(len(ids) for ids in frozen_persisted_candidate_ids().values())
    assert [
        (row.experiment_id, row.candidate_id, row.forecast_origin_id) for row in first
    ] == sorted(
        (row.experiment_id, row.candidate_id, row.forecast_origin_id) for row in first
    )
    for row in first:
        key = (row.experiment_id, row.candidate_id, row.forecast_origin_id)
        source_row = next(
            persisted_row
            for persisted_row in persisted.rows
            if (persisted_row.experiment_id, persisted_row.candidate_id, persisted_row.forecast_origin_id) == key
        )
        assert row is source_row
        assert row.predicted_score == source_score_by_key[key]


def test_unexpected_candidate_id_fails_closed(tmp_path):
    rows = _default_rows()
    rows[0] = {**rows[0], "candidate_id": "FMD07B:ML:UNEXPECTED"}
    _write_artifacts(tmp_path, rows=rows)

    with pytest.raises(PersistedPredictionIntegrityError, match="unexpected candidate"):
        load_persisted_exp01_exp04_predictions(tmp_path)


def test_duplicate_candidate_origin_row_fails_closed(tmp_path):
    rows = _default_rows()
    rows.append(dict(rows[0]))
    _write_artifacts(tmp_path, rows=rows)

    with pytest.raises(PersistedPredictionIntegrityError, match="duplicate persisted candidate/origin"):
        load_persisted_exp01_exp04_predictions(tmp_path)


def test_missing_frozen_support_row_fails_closed(tmp_path):
    rows = _default_rows()
    exp01_candidate = frozen_persisted_candidate_ids()["FMD-EXP-01"][0]
    rows = [
        row
        for row in rows
        if not (
            row["experiment_id"] == "FMD-EXP-01"
            and row["candidate_id"] == exp01_candidate
            and row["forecast_origin_id"] == "ORIGIN:2"
        )
    ]
    _write_artifacts(tmp_path, rows=rows)
    persisted = load_persisted_exp01_exp04_predictions(tmp_path)

    with pytest.raises(PersistedPredictionIntegrityError, match="cannot shrink frozen common support"):
        filter_persisted_predictions_to_common_support(persisted, _support())


@pytest.mark.parametrize("corruption", ("prediction_csv", "upstream_input"))
def test_bad_manifest_backed_hash_fails_closed(tmp_path, corruption):
    artifact_dir, _rows = _write_artifacts(tmp_path)
    if corruption == "prediction_csv":
        with (artifact_dir / PERSISTED_PREDICTIONS_FILENAME).open("ab") as handle:
            handle.write(b"\n")
        expected_message = "prediction CSV SHA-256 mismatch"
    else:
        (artifact_dir.parent / "synthetic_matrix.csv").write_bytes(b"drifted\n")
        expected_message = "input artifact SHA-256 mismatch"

    with pytest.raises(PersistedPredictionIntegrityError, match=expected_message):
        load_persisted_exp01_exp04_predictions(tmp_path)


@pytest.mark.parametrize("missing_filename", (PERSISTED_MANIFEST_FILENAME, PERSISTED_PREDICTIONS_FILENAME))
def test_required_persisted_artifact_missing_fails_closed(tmp_path, missing_filename):
    artifact_dir, _rows = _write_artifacts(tmp_path)
    (artifact_dir / missing_filename).unlink()

    with pytest.raises(PersistedPredictionIntegrityError, match="required persisted"):
        load_persisted_exp01_exp04_predictions(tmp_path)
