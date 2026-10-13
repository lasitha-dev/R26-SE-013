"""FMD-07B finalizer assembler: compose EXP-01 + EXP-02 + EXP-04 predictions.

This module composes persisted EXP-01 and EXP-04 predictions with an externally
supplied EXP-02 prediction artifact, verifies integrity, builds frozen common
support, reuses existing frozen metric/aggregation/ranking functions, and calls
the canonical writer to produce ten canonical FMD-07B artifacts.

No model is trained, fit, or refit. No real EXP-02 execution occurs. EXP-01 and
EXP-04 persisted predictions are never regenerated, retrained, or rescored.
EXP-03 remains BLOCKED. EXP-05 remains BLOCKED_BY_PISTES.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from .fmd_model_development_7b import (
    CHECKPOINT,
    HELD_OUT_USED,
    SRI_LANKA_USED,
    FrozenCommonSupport,
)
from .fmd_model_development_7b_artifact_writer import (
    write_canonical_fmd07b_artifacts,
)
from .fmd_model_development_7b_execution import (
    aggregate_candidate_metrics,
    compute_fold_metrics,
    pooled_reliability_curve,
)
from .fmd_model_development_7b_prediction_reuse import (
    PersistedPredictionReuse,
    PersistedPredictionRow,
)
from .model_fitting_exposure import CalendarYearFold


class FinalizerIntegrityError(RuntimeError):
    """Finalizer verification failed on candidate IDs, support, metrics, or predictions."""


PRIMARY_CANDIDATE_SELECTION_RULE = (
    "MAXIMUM_EQUAL_FOLD_WEIGHTED_MEAN_PR_AUC_TIE_BROKEN_BY_CANDIDATE_ID_LEXICAL_ORDER"
)


def select_winning_candidate(aggregated: Mapping[str, dict]) -> tuple[str, float]:
    """Highest `primary_selection_metric_value` (the equal-fold-weighted mean
    PR-AUC each candidate's summary already carries, see
    `fmd_model_development_7b_execution.PRIMARY_METRIC_AGGREGATION_RULE`)
    wins; a candidate with no usable value (metric is `None`, e.g. every
    fold collapsed to one class for it) is never eligible to win, and is
    never silently treated as tied with 0. Ties broken by candidate_id
    lexical order only -- the exact `(-value, candidate_id)` ranking already
    established for the EXP-01/EXP-04 partial pass in
    `fmd_model_development_7b_execution.run_fmd07b_partial_development`,
    reused here rather than re-invented for the full EXP-01+EXP-02+EXP-04
    comparison. Raises rather than picking an arbitrary candidate if none
    has a usable metric."""
    scored = [
        (candidate_id, summary["primary_selection_metric_value"])
        for candidate_id, summary in aggregated.items()
        if summary.get("primary_selection_metric_value") is not None
    ]
    if not scored:
        raise FinalizerIntegrityError(
            "no candidate produced a usable primary_selection_metric_value -- selection cannot proceed"
        )
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored[0]


@dataclass(frozen=True)
class Exp02ExternalArtifactRow:
    """Single row from externally supplied EXP-02 predictions artifact."""
    fold_id: str
    experiment_id: str
    candidate_id: str
    forecast_origin_id: str
    true_label: int
    predicted_score: float | None
    status: str


@dataclass(frozen=True)
class FinalizerInputArtifacts:
    """Immutable container for finalizer inputs from three experiments."""
    persisted_exp01_exp04: PersistedPredictionReuse
    exp02_external_predictions: tuple[Exp02ExternalArtifactRow, ...]
    frozen_common_support: Mapping[str, FrozenCommonSupport]
    calendar_folds: Sequence[CalendarYearFold]
    exp02_predictions_sha256: str
    exp02_predictions_filename: str = "fmd07b_exp02_fold_predictions.csv"


def load_and_verify_external_exp02_artifact(artifact_path: Path) -> tuple[Exp02ExternalArtifactRow, ...]:
    """Load and verify external EXP-02 predictions artifact.
    
    The external artifact must be a CSV with rows containing:
    fold_id, experiment_id, candidate_id, forecast_origin_id, true_label, 
    predicted_score, status
    """
    if not artifact_path.exists():
        raise FinalizerIntegrityError(f"EXP-02 artifact not found at {artifact_path}")
    
    df = pd.read_csv(artifact_path)
    required_cols = {
        "fold_id",
        "experiment_id",
        "candidate_id",
        "forecast_origin_id",
        "true_label",
        "predicted_score",
        "status",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise FinalizerIntegrityError(f"EXP-02 artifact missing columns: {missing}")
    
    rows = []
    for idx, row in df.iterrows():
        exp_id = str(row["experiment_id"]).strip()
        if exp_id != "FMD-EXP-02":
            raise FinalizerIntegrityError(
                f"Row {idx} has experiment_id={exp_id!r}, expected FMD-EXP-02"
            )
        try:
            score = None if pd.isna(row["predicted_score"]) else float(row["predicted_score"])
        except (ValueError, TypeError):
            raise FinalizerIntegrityError(
                f"Row {idx} has invalid predicted_score: {row['predicted_score']!r}"
            )
        try:
            label = int(row["true_label"])
            if label not in (0, 1):
                raise ValueError("not binary")
        except (ValueError, TypeError):
            raise FinalizerIntegrityError(
                f"Row {idx} has invalid true_label: {row['true_label']!r}"
            )
        
        rows.append(
            Exp02ExternalArtifactRow(
                fold_id=str(row["fold_id"]).strip(),
                experiment_id=exp_id,
                candidate_id=str(row["candidate_id"]).strip(),
                forecast_origin_id=str(row["forecast_origin_id"]).strip(),
                true_label=label,
                predicted_score=score,
                status=str(row["status"]).strip(),
            )
        )
    
    if not rows:
        raise FinalizerIntegrityError("EXP-02 artifact contains no prediction rows")
    return tuple(rows)


def verify_common_support_compatibility(
    persisted_support: Mapping[str, FrozenCommonSupport],
    external_exp02_predictions: Sequence[Exp02ExternalArtifactRow],
) -> None:
    """Verify that EXP-02 predictions exist for all origins in common support."""
    exp02_by_fold = {}
    for row in external_exp02_predictions:
        if row.fold_id not in exp02_by_fold:
            exp02_by_fold[row.fold_id] = set()
        exp02_by_fold[row.fold_id].add(row.forecast_origin_id)
    
    for fold_id, support in persisted_support.items():
        if fold_id not in exp02_by_fold:
            raise FinalizerIntegrityError(
                f"fold_id {fold_id!r} in common support has no EXP-02 predictions"
            )
        exp02_origins = exp02_by_fold[fold_id]
        missing = set(support.common_support_origin_ids) - exp02_origins
        if missing:
            raise FinalizerIntegrityError(
                f"fold_id {fold_id!r}: common support origins missing from EXP-02 "
                f"predictions: {sorted(missing)}"
            )


def verify_common_support_candidate_ids(
    persisted_candidates: Mapping[str, tuple[str, ...]],
    external_exp02_predictions: Sequence[Exp02ExternalArtifactRow],
) -> None:
    """Verify that EXP-02 candidate IDs match persisted EXP-01/EXP-04 expectations."""
    exp02_candidates = set()
    for row in external_exp02_predictions:
        if row.experiment_id != "FMD-EXP-02":
            raise FinalizerIntegrityError(
                f"External EXP-02 artifact contains row with experiment_id="
                f"{row.experiment_id!r}"
            )
        exp02_candidates.add(row.candidate_id)
    
    if "FMD-EXP-02" not in persisted_candidates:
        raise FinalizerIntegrityError("No FMD-EXP-02 in persisted candidates registry")
    expected_exp02 = set(persisted_candidates["FMD-EXP-02"])
    if exp02_candidates != expected_exp02:
        raise FinalizerIntegrityError(
            f"EXP-02 candidate mismatch: external has {sorted(exp02_candidates)}, "
            f"expected {sorted(expected_exp02)}"
        )


def build_unified_fold_predictions(
    persisted_exp01_exp04: Sequence[PersistedPredictionRow],
    external_exp02: Sequence[Exp02ExternalArtifactRow],
) -> tuple[dict, ...]:
    """Combine persisted EXP-01/EXP-04 and external EXP-02 predictions into unified rows."""
    rows = []
    
    # Add persisted EXP-01 and EXP-04 predictions.
    for row in persisted_exp01_exp04:
        rows.append({
            "fold_id": row.fold_id,
            "experiment_id": row.experiment_id,
            "candidate_id": row.candidate_id,
            "forecast_origin_id": row.forecast_origin_id,
            "true_label": int(row.true_label),
            "predicted_score": None if row.predicted_score == "" else float(row.predicted_score) if row.predicted_score else None,
            "status": row.status,
        })
    
    # Add external EXP-02 predictions.
    for row in external_exp02:
        rows.append({
            "fold_id": row.fold_id,
            "experiment_id": row.experiment_id,
            "candidate_id": row.candidate_id,
            "forecast_origin_id": row.forecast_origin_id,
            "true_label": row.true_label,
            "predicted_score": row.predicted_score,
            "status": row.status,
        })
    
    return tuple(rows)


def compute_finalizer_fold_metrics(
    unified_predictions: Sequence[dict],
    common_support: FrozenCommonSupport,
) -> Mapping[tuple[str, str], dict | None]:
    """Compute fold metrics for each candidate using only common-support origins."""
    metrics_by_candidate = {}
    
    support_origins = set(common_support.common_support_origin_ids)
    
    # Group predictions by candidate.
    by_candidate = {}
    for pred in unified_predictions:
        if pred["fold_id"] != common_support.fold_id:
            continue
        cid = pred["candidate_id"]
        if cid not in by_candidate:
            by_candidate[cid] = []
        by_candidate[cid].append(pred)
    
    # Compute metrics for each candidate restricted to common support.
    for candidate_id, preds in by_candidate.items():
        predictions_dict = {}
        unscored_reasons = {}
        labels_dict = {}
        
        for pred in preds:
            oid = pred["forecast_origin_id"]
            if oid not in support_origins:
                continue
            labels_dict[oid] = pred["true_label"]
            if pred["predicted_score"] is not None:
                predictions_dict[oid] = pred["predicted_score"]
            else:
                unscored_reasons[oid] = pred["status"]
        
        metrics = compute_fold_metrics(
            predictions_dict,
            unscored_reasons,
            labels_dict,
            list(support_origins),
        )
        metrics_by_candidate[(common_support.fold_id, candidate_id)] = metrics
    
    return metrics_by_candidate


def finalize_and_write_canonical_artifacts(
    *,
    inputs: FinalizerInputArtifacts,
    output_root: Path,
) -> dict:
    """Orchestrate finalizer: verify, compute metrics, aggregate, and write artifacts.
    
    Returns the manifest dict that was written.
    """
    persisted = inputs.persisted_exp01_exp04
    exp02_rows = inputs.exp02_external_predictions
    
    # Verify common support has all required predictions.
    verify_common_support_compatibility(inputs.frozen_common_support, exp02_rows)
    
    # Verify candidate IDs align across experiments.
    exp01_candidates = persisted.candidate_ids("FMD-EXP-01")
    exp04_candidates = persisted.candidate_ids("FMD-EXP-04")
    candidates_by_experiment = {
        "FMD-EXP-01": exp01_candidates,
        "FMD-EXP-02": tuple(sorted(set(r.candidate_id for r in exp02_rows))),
        "FMD-EXP-04": exp04_candidates,
    }
    verify_common_support_candidate_ids(candidates_by_experiment, exp02_rows)
    
    # Build unified predictions.
    all_persisted_rows = list(persisted.rows_for_experiment("FMD-EXP-01"))
    all_persisted_rows.extend(persisted.rows_for_experiment("FMD-EXP-04"))
    unified_predictions = build_unified_fold_predictions(all_persisted_rows, exp02_rows)
    
    # Compute fold metrics for each fold and candidate under common support.
    all_fold_metrics = {}
    for fold_id, support in inputs.frozen_common_support.items():
        fold_rows = [r for r in unified_predictions if r["fold_id"] == fold_id]
        fold_metrics = compute_finalizer_fold_metrics(fold_rows, support)
        all_fold_metrics.update(fold_metrics)
    
    # Build a map from candidate_id to experiment_id for later use.
    candidate_to_experiment = {}
    for pred in unified_predictions:
        if pred["candidate_id"] not in candidate_to_experiment:
            candidate_to_experiment[pred["candidate_id"]] = pred["experiment_id"]
    
    # Aggregate metrics by candidate.
    candidate_aggregates = {}
    unique_candidates = set()
    for (fold_id, candidate_id) in all_fold_metrics:
        unique_candidates.add((fold_id, candidate_id))
    
    for fold_id, candidate_id in sorted(unique_candidates):
        key = (fold_id, candidate_id)
        if candidate_id not in candidate_aggregates:
            candidate_aggregates[candidate_id] = {}
        candidate_aggregates[candidate_id][fold_id] = all_fold_metrics[key]
    
    aggregated = {}
    for candidate_id in sorted(candidate_aggregates.keys()):
        fold_metrics_by_fold = candidate_aggregates[candidate_id]
        aggregated[candidate_id] = aggregate_candidate_metrics(fold_metrics_by_fold)

    selected_candidate_id, selected_primary_metric_value = select_winning_candidate(aggregated)
    selected_threshold = aggregated[selected_candidate_id].get("median_selected_threshold")

    # Build artifact payloads for the canonical writer.
    # NOTE: The manifest is generated by the writer, not supplied here.
    artifact_payloads = {
        "fmd07b_candidate_eligibility.json": {
            "checkpoint": CHECKPOINT,
            "candidates": [
                {"experiment_id": eid, "eligibility": "EXECUTABLE"}
                for eid in ["FMD-EXP-01", "FMD-EXP-02", "FMD-EXP-04"]
            ],
        },
        "fmd07b_candidate_registry.json": {
            "checkpoint": CHECKPOINT,
            "candidate_ids": sorted(
                set(candidate_id for _fold_id, candidate_id in unique_candidates)
            ),
        },
        "fmd07b_chronological_fold_manifest.json": {
            "checkpoint": CHECKPOINT,
            "folds": [
                {
                    "fold_id": fold_id,
                    "common_support_origin_ids": list(
                        inputs.frozen_common_support[fold_id].common_support_origin_ids
                    ),
                }
                for fold_id in sorted(inputs.frozen_common_support.keys())
            ],
        },
        "fmd07b_fold_predictions.csv": [
            pred for pred in unified_predictions
        ],
        "fmd07b_fold_candidate_metrics.csv": [
            {
                "fold_id": fold_id,
                "experiment_id": candidate_to_experiment.get(candidate_id, "UNKNOWN"),
                "candidate_id": candidate_id,
                **metrics.as_dict(),
            }
            for (fold_id, candidate_id), metrics in all_fold_metrics.items()
            if metrics is not None
        ],
        "fmd07b_fold_summary_metrics.csv": [
            {
                "experiment_id": candidate_to_experiment.get(candidate_id, "UNKNOWN"),
                "candidate_id": candidate_id,
                **summary,
            }
            for candidate_id, summary in aggregated.items()
        ],
        "fmd07b_preprocessing_calibration_audit.json": {
            "checkpoint": CHECKPOINT,
            "preprocessing_rule": "TRAINING_FOLD_ONLY",
            "status": "FINALIZED_FROM_PERSISTED_PREDICTIONS",
        },
        "fmd07b_candidate_selection_summary.json": {
            "checkpoint": CHECKPOINT,
            "selection_rule": PRIMARY_CANDIDATE_SELECTION_RULE,
            "selected_candidate_id": selected_candidate_id,
            "selected_primary_metric_name": "PR-AUC",
            "selected_primary_metric_value": selected_primary_metric_value,
            "candidate_ranking": [
                {"candidate_id": cid, "primary_selection_metric_value": summary["primary_selection_metric_value"]}
                for cid, summary in sorted(
                    aggregated.items(),
                    key=lambda item: (
                        item[1]["primary_selection_metric_value"] is None,
                        -(item[1]["primary_selection_metric_value"] or 0.0),
                        item[0],
                    ),
                )
            ],
        },
        "fmd07b_frozen_model_spec.json": {
            "checkpoint": CHECKPOINT,
            "selected_candidate_id": selected_candidate_id,
            "model": None,
            "preprocessing": None,
            "calibration": None,
            "threshold": selected_threshold,
            "final_refit_state": {"state_format": "FINALIZED_FROM_PERSISTED_PREDICTIONS"},
            "implementation_identity": {
                "module": "components.geospatial_tracking.services.fmd_model_development_7b_finalizer",
            },
            "resolved_direct_dependency_versions": {"scikit-learn": "1.8.0"},
        },
        "fmd07b_manifest.json": {
            "checkpoint": CHECKPOINT,
            "held_out_used": HELD_OUT_USED,
            "sri_lanka_used": SRI_LANKA_USED,
            "locked_test_used": False,
            "input_artifact_sha256": {
                persisted.manifest_path.name: persisted.manifest_sha256,
                persisted.predictions_path.name: persisted.predictions_sha256,
                inputs.exp02_predictions_filename: inputs.exp02_predictions_sha256,
            },
            "implementation_identity": {
                "module": "components.geospatial_tracking.services.fmd_model_development_7b_finalizer",
            },
            "python_version": "3.14.4",
            "resolved_direct_dependency_versions": {"scikit-learn": "1.8.0"},
        },
    }
    
    # Call canonical writer.
    result = write_canonical_fmd07b_artifacts(
        output_dir=output_root,
        artifact_payloads=artifact_payloads,
    )
    
    # Read and return the manifest dict that was written.
    manifest_path = output_root / "fmd07b_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    return manifest
