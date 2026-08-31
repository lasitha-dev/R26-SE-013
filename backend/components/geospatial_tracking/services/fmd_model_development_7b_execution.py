"""FMD-07B PARTIAL development execution: FMD-EXP-01 + FMD-EXP-04 only.

Scope and why this is explicitly NOT a complete FMD-07B run
-------------------------------------------------------------
`FMD07B_PREEXECUTION_FEASIBILITY_PROTOCOL_AMENDMENT.md` Section 7 freezes the
minimum executable comparison set as exactly FMD-EXP-01, FMD-EXP-02, and
FMD-EXP-04. This module executes only FMD-EXP-01 (naive/statistical) and
FMD-EXP-04 (ML) against the real 3,761-row FIT_DEVELOPMENT feature matrix.

FMD-EXP-02 (spatial/distance baseline) is deliberately NOT executed here. Its
frozen mechanism (`services/model_development/baseline_scoring.py`) requires a
live geospatial pipeline per origin -- outbreak-repository source queries plus
real FAO-GLW raster host-density extraction over a scientific evaluation grid
-- which is outside the tabular `fmd07_r2b3_development_feature_matrix.csv`
input this pass is scoped to, and outside `FMD07B_MODEL_DEVELOPMENT_PROTOCOL.md`
Section 3's exact input-artifact list. This is a deliberate, disclosed scope
decision (confirmed with the operator), not a claim that FMD-EXP-02 is
scientifically `BLOCKED` the way PISTES/hybrid are.

Because the minimum executable set is therefore incomplete this pass, this
module never emits the ten canonical FMD-07B artifact names from
`FMD07B_MODEL_DEVELOPMENT_PROTOCOL.md` Section 9 (that section explicitly
reserves those names for a run where every required family participated) and
never emits the `FMD-07B_COMPLETE_READY_FOR_FMD-08` token. All outputs are
written under a `fmd07b_partial_exp01_exp04/` subdirectory with a `PARTIAL`
manifest, and no final candidate is selected across the full minimum set.

Held-out and Sri Lanka data are never read anywhere in this module.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from .fmd_model_development_7b import (
    CHECKPOINT,
    DEPENDENCY_REQUIREMENT,
    RANDOM_SEED,
    REQUIRED_SKLEARN_VERSION,
    Fmd07bFoldInput,
    assert_compatible_sklearn_runtime,
    build_ml_estimator_runner,
    build_naive_statistical_runner,
    validate_fmd07b_fold_input,
)
from .fmd_calibration import FMD_MODEL_FITTING_CUTOFF
from .forecast_origin import ForecastOrigin
from .model_fitting_exposure import CalendarYearFold, assert_fit_development_only

PARTIAL_EXECUTION_TOKEN = "FMD07B_PARTIAL_EXECUTION_FMD_EXP01_FMD_EXP04_ONLY"
EXECUTED_EXPERIMENT_IDS = ("FMD-EXP-01", "FMD-EXP-04")
DEFERRED_EXPERIMENT_IDS = ("FMD-EXP-02",)
DEFERRED_REASON = {
    "FMD-EXP-02": (
        "spatial/distance baseline requires a live geospatial pipeline (outbreak "
        "repository source queries + real FAO-GLW raster host-density extraction "
        "per origin) that falls outside this pass's tabular-feature-matrix-only "
        "scope and outside FMD07B_MODEL_DEVELOPMENT_PROTOCOL.md Section 3's exact "
        "input-artifact list; deferred by explicit operator decision this pass, "
        "not a scientific/software BLOCKED state like PISTES/hybrid."
    ),
}

_REPO_ROOT_PARENTS_FROM_THIS_FILE = 4  # services/ -> geospatial_tracking -> components -> backend -> repo root

R2B3_MANIFEST_REL = "local_data/processed/fmd/model_development/fmd07_r2b3_manifest.json"
R2B3_MATRIX_REL = "local_data/processed/fmd/model_development/fmd07_r2b3_development_feature_matrix.csv"
R2B3_AUDIT_REL = "local_data/processed/fmd/model_development/fmd07_r2b3_origin_feature_aggregation_audit.csv"
MODEL_INPUT_SCHEMA_REL = "local_data/processed/fmd/model_development/fmd07_model_input_schema.json"
CALENDAR_FOLDS_REL = "local_data/processed/fmd/cohort/fmd_calendar_year_folds.json"
RISK_LABELS_REL = "local_data/processed/fmd/calibration/fmd06_risk_origin_labels.csv"

FROZEN_MATRIX_SHAPE = (3761, 105)
FROZEN_USABLE_FOLD_COUNT = 21
FROZEN_EXCLUDED_FOLD_IDS = ("FOLD:2002", "FOLD:2003")

# Threshold grid + F1-maximizing selection + equal-fold-weighted median
# aggregation reuse the EXACT rule already frozen in
# fmd07_development_protocol.json's threshold_selection_procedure.
THRESHOLD_GRID = tuple(round(0.05 * i, 2) for i in range(1, 20))  # 0.05 .. 0.95

# No aggregation rule for the PRIMARY (PR-AUC) selection metric is frozen
# anywhere in the FMD-07 documents; this is a new, disclosed, non-performance
# rule fixed here (before reading any candidate's computed metric) that
# reuses the SAME "equal-fold-weighted" style already frozen for threshold
# selection, rather than inventing an unrelated convention.
PRIMARY_METRIC_AGGREGATION_RULE = "EQUAL_FOLD_WEIGHTED_MEAN_PR_AUC_OVER_CONTRIBUTING_USABLE_FOLDS"

TRAINING_FOLD_SINGLE_CLASS_SKIPPED = "TRAINING_FOLD_SINGLE_CLASS_SKIPPED"
NAIVE_SCORE_UNAVAILABLE = "NAIVE_SCORE_UNAVAILABLE_NO_TRAINING_FOLD_COUNTRY_HISTORY"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class R2B3Inputs:
    matrix: pd.DataFrame
    manifest: dict
    predictor_value_columns: tuple[str, ...]


def load_and_verify_r2b3_inputs(repo_root: Path) -> R2B3Inputs:
    """Hash-verifies the frozen matrix/audit against fmd07_r2b3_manifest.json
    before reading anything, per FMD07B_MODEL_DEVELOPMENT_PROTOCOL.md Section 3
    ("verify ... every upstream hash ... Hash drift ... is a hard stop")."""
    manifest_path = repo_root / R2B3_MANIFEST_REL
    matrix_path = repo_root / R2B3_MATRIX_REL
    audit_path = repo_root / R2B3_AUDIT_REL
    schema_path = repo_root / MODEL_INPUT_SCHEMA_REL

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    observed_matrix_sha = _sha256_file(matrix_path)
    expected_matrix_sha = manifest["output_artifact_sha256"]["fmd07_r2b3_development_feature_matrix.csv"]
    if observed_matrix_sha != expected_matrix_sha:
        raise ValueError(
            "fmd07_r2b3_development_feature_matrix.csv sha256 mismatch: "
            f"expected {expected_matrix_sha}, observed {observed_matrix_sha} -- refusing drifted input"
        )
    observed_audit_sha = _sha256_file(audit_path)
    expected_audit_sha = manifest["output_artifact_sha256"]["fmd07_r2b3_origin_feature_aggregation_audit.csv"]
    if observed_audit_sha != expected_audit_sha:
        raise ValueError(
            "fmd07_r2b3_origin_feature_aggregation_audit.csv sha256 mismatch: "
            f"expected {expected_audit_sha}, observed {observed_audit_sha} -- refusing drifted input"
        )

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    predictor_value_columns = tuple(
        col for col in schema["predictor_columns_ordered"] if col.endswith("_value")
    )
    if schema["target_column"] != "risk_target_label":
        raise ValueError(f"unexpected target_column in schema: {schema['target_column']!r}")

    matrix = pd.read_csv(matrix_path)
    if matrix.shape != FROZEN_MATRIX_SHAPE:
        raise ValueError(f"unexpected matrix shape {matrix.shape}, expected {FROZEN_MATRIX_SHAPE}")
    if not matrix["forecast_origin_id"].is_unique:
        raise ValueError("duplicate forecast_origin_id values in development feature matrix")
    bad_roles = sorted(set(matrix["model_fitting_role"].unique()) - {"FIT_DEVELOPMENT"})
    if bad_roles:
        raise ValueError(f"non-FIT_DEVELOPMENT model_fitting_role values present: {bad_roles}")
    bad_labels = sorted(set(int(v) for v in matrix["risk_target_label"].unique()) - {0, 1})
    if bad_labels:
        raise ValueError(f"risk_target_label must be binary 0/1, found: {bad_labels}")
    missing_cols = [c for c in predictor_value_columns if c not in matrix.columns]
    if missing_cols:
        raise ValueError(f"schema-declared predictor value columns missing from matrix: {missing_cols}")

    labels_path = repo_root / RISK_LABELS_REL
    labels_df = pd.read_csv(labels_path)[["forecast_origin_id", "risk_target_label"]]
    joined = matrix[["forecast_origin_id", "risk_target_label"]].merge(
        labels_df, on="forecast_origin_id", suffixes=("_matrix", "_labels"), how="left"
    )
    if joined["risk_target_label_labels"].isna().any():
        raise ValueError("matrix contains forecast_origin_id values absent from fmd06_risk_origin_labels.csv")
    if not (joined["risk_target_label_matrix"] == joined["risk_target_label_labels"]).all():
        raise ValueError("risk_target_label mismatch between the r2b3 matrix and fmd06_risk_origin_labels.csv")

    return R2B3Inputs(matrix=matrix, manifest=manifest, predictor_value_columns=predictor_value_columns)


def build_forecast_origins(matrix: pd.DataFrame) -> list[ForecastOrigin]:
    return [
        ForecastOrigin(
            forecast_origin_id=row.forecast_origin_id,
            country=row.country,
            t0=row.t0,
            temporal_mode="RETROSPECTIVE_PROXY",
        )
        for row in matrix.itertuples(index=False)
    ]


def load_calendar_year_folds(repo_root: Path) -> list[CalendarYearFold]:
    raw = json.loads((repo_root / CALENDAR_FOLDS_REL).read_text(encoding="utf-8"))
    return [
        CalendarYearFold(
            fold_id=f["fold_id"],
            validation_year=f["validation_year"],
            training_date_range_end=f["training_date_range_end"],
            validation_date_range_start=f["validation_date_range_start"],
            validation_date_range_end=f["validation_date_range_end"],
            training_origin_ids=list(f["training_origin_ids"]),
            validation_origin_ids=list(f["validation_origin_ids"]),
            purged_origin_ids=list(f["purged_origin_ids"]),
        )
        for f in raw
    ]


def classify_fold_usability(fold: CalendarYearFold, labels_by_origin: Mapping[str, int]) -> tuple[bool, tuple[str, ...]]:
    """Reproduces the frozen INSUFFICIENT_PRIOR_TRAINING_HISTORY_OR_SINGLE_CLASS_VALIDATION_EXCLUDED
    rule (fmd07_pre_model_protocol_amendment.json cv_validity_policy) structurally
    from the fold + label data, rather than trusting a hardcoded fold-id list."""
    reasons: list[str] = []
    if not fold.training_origin_ids:
        reasons.append("INSUFFICIENT_PRIOR_TRAINING_HISTORY")
    val_labels = [labels_by_origin[oid] for oid in fold.validation_origin_ids]
    n_pos = sum(val_labels)
    n_neg = len(val_labels) - n_pos
    if n_pos == 0:
        reasons.append("NO_POSITIVE_CLASS_IN_VALIDATION")
    if n_neg == 0:
        reasons.append("NO_NEGATIVE_CLASS_IN_VALIDATION")
    return (len(reasons) == 0, tuple(reasons))


@dataclass(frozen=True)
class FoldMetrics:
    n_scored: int
    n_unscored: int
    unscored_reason_counts: dict
    pr_auc: float
    auroc: float
    brier_score: float | None
    selected_threshold: float
    f1_at_selected_threshold: float
    precision_at_selected_threshold: float
    recall_at_selected_threshold: float
    specificity_at_selected_threshold: float | None

    def as_dict(self) -> dict:
        return {
            "n_scored": self.n_scored,
            "n_unscored": self.n_unscored,
            "unscored_reason_counts": self.unscored_reason_counts,
            "pr_auc": self.pr_auc,
            "auroc": self.auroc,
            "brier_score": self.brier_score,
            "selected_threshold": self.selected_threshold,
            "f1_at_selected_threshold": self.f1_at_selected_threshold,
            "precision_at_selected_threshold": self.precision_at_selected_threshold,
            "recall_at_selected_threshold": self.recall_at_selected_threshold,
            "specificity_at_selected_threshold": self.specificity_at_selected_threshold,
        }


def compute_fold_metrics(
    predictions: Mapping[str, float],
    unscored_reasons: Mapping[str, str],
    labels_by_origin: Mapping[str, int],
    validation_origin_ids: Sequence[str],
) -> FoldMetrics | None:
    scored_ids = [oid for oid in validation_origin_ids if oid in predictions]
    if len(scored_ids) < 2:
        return None
    y_true = [labels_by_origin[oid] for oid in scored_ids]
    y_score = [float(predictions[oid]) for oid in scored_ids]
    if len(set(y_true)) < 2:
        return None  # this candidate's own scorable subset collapsed to one class

    pr_auc = float(average_precision_score(y_true, y_score))
    auroc = float(roc_auc_score(y_true, y_score))
    try:
        brier = float(brier_score_loss(y_true, y_score))
    except ValueError:
        # brier_score_loss requires y_score in [0, 1]; a candidate whose frozen
        # score is not a probability (e.g. an unbounded spatial-kernel score)
        # cannot have a Brier score computed, but PR-AUC/AUROC/threshold
        # metrics are rank-based and remain valid.
        brier = None

    best_threshold, best_f1 = THRESHOLD_GRID[0], -1.0
    for t in THRESHOLD_GRID:
        y_pred = [1 if s >= t else 0 for s in y_score]
        f1 = f1_score(y_true, y_pred, zero_division=0)
        if f1 > best_f1:
            best_f1, best_threshold = f1, t

    y_pred_best = [1 if s >= best_threshold else 0 for s in y_score]
    precision = float(precision_score(y_true, y_pred_best, zero_division=0))
    recall = float(recall_score(y_true, y_pred_best, zero_division=0))
    tn = sum(1 for t, p in zip(y_true, y_pred_best) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred_best) if t == 0 and p == 1)
    specificity = (tn / (tn + fp)) if (tn + fp) > 0 else None

    reason_counts: dict = {}
    for oid in validation_origin_ids:
        if oid not in predictions:
            reason = unscored_reasons.get(oid, "UNKNOWN")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return FoldMetrics(
        n_scored=len(scored_ids),
        n_unscored=len(validation_origin_ids) - len(scored_ids),
        unscored_reason_counts=reason_counts,
        pr_auc=pr_auc,
        auroc=auroc,
        brier_score=brier,
        selected_threshold=float(best_threshold),
        f1_at_selected_threshold=float(best_f1),
        precision_at_selected_threshold=precision,
        recall_at_selected_threshold=recall,
        specificity_at_selected_threshold=specificity,
    )


def run_naive_fold(
    fold_input: Fmd07bFoldInput,
    *,
    countries_by_origin: Mapping[str, str],
    labels_by_origin: Mapping[str, int],
) -> tuple[dict, dict]:
    runner = build_naive_statistical_runner()
    fitted = runner.fit_training_fold(
        fold_input, countries_by_origin=countries_by_origin, labels_by_origin=labels_by_origin
    )
    predictions: dict = {}
    unscored_reasons: dict = {}
    for oid in fold_input.validation_origin_ids:
        try:
            predictions[oid] = fitted.rate_for_country(countries_by_origin[oid])
        except ValueError:
            unscored_reasons[oid] = NAIVE_SCORE_UNAVAILABLE
    return predictions, unscored_reasons


def run_ml_fold(
    runner,
    candidate_id: str,
    fold_input: Fmd07bFoldInput,
    *,
    features_by_origin: Mapping[str, Sequence[float | None]],
    labels_by_origin: Mapping[str, int],
) -> tuple[dict, dict, str | None]:
    training_labels = [labels_by_origin[oid] for oid in fold_input.training_origin_ids]
    if len(set(training_labels)) < 2:
        reasons = {oid: TRAINING_FOLD_SINGLE_CLASS_SKIPPED for oid in fold_input.validation_origin_ids}
        return {}, reasons, TRAINING_FOLD_SINGLE_CLASS_SKIPPED

    pipeline = runner.fit_training_fold(
        candidate_id, fold_input, features_by_origin=features_by_origin, labels_by_origin=labels_by_origin
    )
    classes = list(pipeline.classes_)
    positive_index = classes.index(1)
    x_val = [list(features_by_origin[oid]) for oid in fold_input.validation_origin_ids]
    proba = pipeline.predict_proba(x_val)[:, positive_index]
    predictions = dict(zip(fold_input.validation_origin_ids, (float(p) for p in proba)))
    return predictions, {}, None


def aggregate_candidate_metrics(fold_metrics_by_fold_id: Mapping[str, FoldMetrics | None]) -> dict:
    contributing = {fid: m for fid, m in fold_metrics_by_fold_id.items() if m is not None}
    n_usable = len(fold_metrics_by_fold_id)
    if not contributing:
        return {
            "n_usable_folds": n_usable,
            "n_contributing_folds": 0,
            "primary_selection_metric_name": "PR-AUC",
            "primary_metric_aggregation_rule": PRIMARY_METRIC_AGGREGATION_RULE,
            "primary_selection_metric_value": None,
            "median_pr_auc": None,
            "mean_auroc": None,
            "mean_brier_score": None,
            "median_selected_threshold": None,
        }
    pr_aucs = [m.pr_auc for m in contributing.values()]
    aurocs = [m.auroc for m in contributing.values()]
    briers = [m.brier_score for m in contributing.values() if m.brier_score is not None]
    thresholds = [m.selected_threshold for m in contributing.values()]
    return {
        "n_usable_folds": n_usable,
        "n_contributing_folds": len(contributing),
        "primary_selection_metric_name": "PR-AUC",
        "primary_metric_aggregation_rule": PRIMARY_METRIC_AGGREGATION_RULE,
        "primary_selection_metric_value": sum(pr_aucs) / len(pr_aucs),
        "median_pr_auc": statistics.median(pr_aucs),
        "mean_auroc": sum(aurocs) / len(aurocs),
        "mean_brier_score": (sum(briers) / len(briers)) if briers else None,
        # equal-fold-weighted median, reusing fmd07_development_protocol.json's
        # already-frozen threshold_selection_procedure verbatim.
        "median_selected_threshold": statistics.median(thresholds),
    }


def pooled_reliability_curve(pooled_labels: Sequence[int], pooled_scores: Sequence[float], *, n_bins: int = 5) -> dict:
    if len(set(pooled_labels)) < 2 or len(pooled_labels) < n_bins:
        return {"n_bins_requested": n_bins, "status": "INSUFFICIENT_POOLED_DATA", "bins": []}
    prob_true, prob_pred = calibration_curve(pooled_labels, pooled_scores, n_bins=n_bins, strategy="quantile")
    return {
        "n_bins_requested": n_bins,
        "status": "COMPUTED",
        "bins": [{"mean_predicted": float(p), "observed_frequency": float(t)} for p, t in zip(prob_pred, prob_true)],
    }


def run_fmd07b_partial_development(repo_root: Path) -> dict:
    """Orchestrates the real FMD-EXP-01 + FMD-EXP-04 development run over the
    real FIT_DEVELOPMENT feature matrix. Returns the full in-memory result
    dict; `write_partial_outputs` persists it under a non-canonical path."""
    assert_compatible_sklearn_runtime()

    inputs = load_and_verify_r2b3_inputs(repo_root)
    matrix = inputs.matrix
    origins = build_forecast_origins(matrix)
    assert_fit_development_only(
        origins, cutoff=FMD_MODEL_FITTING_CUTOFF, caller="run_fmd07b_partial_development"
    )

    countries_by_origin = {row.forecast_origin_id: row.country for row in matrix.itertuples(index=False)}
    labels_by_origin = {row.forecast_origin_id: int(row.risk_target_label) for row in matrix.itertuples(index=False)}
    features_by_origin = {
        row.forecast_origin_id: tuple(
            None if pd.isna(v) else float(v)
            for v in (getattr(row, col) for col in inputs.predictor_value_columns)
        )
        for row in matrix.itertuples(index=False)
    }

    folds = load_calendar_year_folds(repo_root)
    usability = {f.fold_id: classify_fold_usability(f, labels_by_origin) for f in folds}
    usable_fold_ids = tuple(sorted(fid for fid, (usable, _reasons) in usability.items() if usable))
    excluded_fold_ids = tuple(sorted(fid for fid, (usable, _reasons) in usability.items() if not usable))
    if len(usable_fold_ids) != FROZEN_USABLE_FOLD_COUNT or set(excluded_fold_ids) != set(FROZEN_EXCLUDED_FOLD_IDS):
        raise ValueError(
            "structurally recomputed fold usability does not match the frozen "
            f"cv_validity_policy audit: usable={usable_fold_ids} excluded={excluded_fold_ids}"
        )

    ml_runner = build_ml_estimator_runner()
    ml_candidate_ids = tuple(c.candidate_id for c in ml_runner.candidates)

    naive_fold_metrics: dict[str, FoldMetrics | None] = {}
    naive_oof_labels: list[int] = []
    naive_oof_scores: list[float] = []
    ml_fold_metrics: dict[str, dict[str, FoldMetrics | None]] = {cid: {} for cid in ml_candidate_ids}
    ml_oof: dict[str, tuple[list[int], list[float]]] = {cid: ([], []) for cid in ml_candidate_ids}
    ml_fold_status_notes: dict[str, dict[str, str]] = {cid: {} for cid in ml_candidate_ids}
    fold_predictions_rows: list[dict] = []

    for fold in folds:
        validated = validate_fmd07b_fold_input(origins, fold)
        usable, reasons = usability[fold.fold_id]
        if not usable:
            continue

        naive_predictions, naive_unscored = run_naive_fold(
            validated, countries_by_origin=countries_by_origin, labels_by_origin=labels_by_origin
        )
        naive_fold_metrics[fold.fold_id] = compute_fold_metrics(
            naive_predictions, naive_unscored, labels_by_origin, validated.validation_origin_ids
        )
        for oid in validated.validation_origin_ids:
            if oid in naive_predictions:
                naive_oof_labels.append(labels_by_origin[oid])
                naive_oof_scores.append(naive_predictions[oid])
            fold_predictions_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "experiment_id": "FMD-EXP-01",
                    "candidate_id": "FMD07B:FMD-EXP-01:COUNTRY_HISTORICAL_OCCURRENCE_RATE",
                    "forecast_origin_id": oid,
                    "true_label": labels_by_origin[oid],
                    "predicted_score": naive_predictions.get(oid),
                    "status": "SCORED" if oid in naive_predictions else naive_unscored.get(oid, "UNKNOWN"),
                }
            )

        for candidate_id in ml_candidate_ids:
            ml_predictions, ml_unscored, status_note = run_ml_fold(
                ml_runner,
                candidate_id,
                validated,
                features_by_origin=features_by_origin,
                labels_by_origin=labels_by_origin,
            )
            ml_fold_metrics[candidate_id][fold.fold_id] = compute_fold_metrics(
                ml_predictions, ml_unscored, labels_by_origin, validated.validation_origin_ids
            )
            if status_note:
                ml_fold_status_notes[candidate_id][fold.fold_id] = status_note
            oof_labels, oof_scores = ml_oof[candidate_id]
            for oid in validated.validation_origin_ids:
                if oid in ml_predictions:
                    oof_labels.append(labels_by_origin[oid])
                    oof_scores.append(ml_predictions[oid])
                fold_predictions_rows.append(
                    {
                        "fold_id": fold.fold_id,
                        "experiment_id": "FMD-EXP-04",
                        "candidate_id": candidate_id,
                        "forecast_origin_id": oid,
                        "true_label": labels_by_origin[oid],
                        "predicted_score": ml_predictions.get(oid),
                        "status": "SCORED" if oid in ml_predictions else ml_unscored.get(oid, "UNKNOWN"),
                    }
                )

    naive_summary = aggregate_candidate_metrics(naive_fold_metrics)
    naive_summary["reliability_curve"] = pooled_reliability_curve(naive_oof_labels, naive_oof_scores)

    ml_summaries: dict[str, dict] = {}
    for candidate_id in ml_candidate_ids:
        summary = aggregate_candidate_metrics(ml_fold_metrics[candidate_id])
        oof_labels, oof_scores = ml_oof[candidate_id]
        summary["reliability_curve"] = pooled_reliability_curve(oof_labels, oof_scores)
        summary["fold_status_notes"] = ml_fold_status_notes[candidate_id]
        ml_summaries[candidate_id] = summary

    all_candidate_summaries = {
        "FMD07B:FMD-EXP-01:COUNTRY_HISTORICAL_OCCURRENCE_RATE": {
            "experiment_id": "FMD-EXP-01",
            **{k: v for k, v in naive_summary.items()},
        },
        **{cid: {"experiment_id": "FMD-EXP-04", **summ} for cid, summ in ml_summaries.items()},
    }
    ranked = sorted(
        (
            (cid, summ["primary_selection_metric_value"])
            for cid, summ in all_candidate_summaries.items()
            if summ["primary_selection_metric_value"] is not None
        ),
        key=lambda item: (-item[1], item[0]),
    )

    return {
        "partial_execution_token": PARTIAL_EXECUTION_TOKEN,
        "checkpoint": CHECKPOINT,
        "executed_experiment_ids": list(EXECUTED_EXPERIMENT_IDS),
        "deferred_experiment_ids": list(DEFERRED_EXPERIMENT_IDS),
        "deferred_reason": DEFERRED_REASON,
        "dependency_requirement": DEPENDENCY_REQUIREMENT,
        "sklearn_version": REQUIRED_SKLEARN_VERSION,
        "random_seed": RANDOM_SEED,
        "input_artifact_sha256": {
            "fmd07_r2b3_development_feature_matrix.csv": inputs.manifest["output_artifact_sha256"][
                "fmd07_r2b3_development_feature_matrix.csv"
            ],
            "fmd07_r2b3_origin_feature_aggregation_audit.csv": inputs.manifest["output_artifact_sha256"][
                "fmd07_r2b3_origin_feature_aggregation_audit.csv"
            ],
        },
        "origin_rows": int(matrix.shape[0]),
        "predictor_value_column_count": len(inputs.predictor_value_columns),
        "predictor_value_columns": list(inputs.predictor_value_columns),
        "ml_predictor_scope_note": (
            "Only the 47 frozen *_value numeric predictor columns are fed to the "
            "FMD-EXP-04 estimators. The paired *_status categorical audit columns "
            "are listed as predictor_columns_ordered in fmd07_model_input_schema.json "
            "but the frozen FMD07A-R1 ML preprocessing registry "
            "(fmd_model_development_7b._ML_PREPROCESSING) defines only imputation/"
            "scaling/native-missing-value steps -- no ENCODING step -- for the "
            "three frozen algorithm families, so feeding a categorical status "
            "string into them would require inventing an unfrozen preprocessing "
            "step. Status columns remain unused this pass, not silently dropped "
            "from the schema."
        ),
        "usable_fold_ids": list(usable_fold_ids),
        "excluded_fold_ids": list(excluded_fold_ids),
        "excluded_fold_reasons": {fid: list(usability[fid][1]) for fid in excluded_fold_ids},
        "held_out_used": False,
        "sri_lanka_used": False,
        "locked_test_used": False,
        "naive_candidate": {
            "candidate_id": "FMD07B:FMD-EXP-01:COUNTRY_HISTORICAL_OCCURRENCE_RATE",
            "fold_metrics": {fid: (m.as_dict() if m else None) for fid, m in naive_fold_metrics.items()},
            "summary": naive_summary,
        },
        "ml_candidates": {
            cid: {
                "fold_metrics": {fid: (m.as_dict() if m else None) for fid, m in ml_fold_metrics[cid].items()},
                "summary": ml_summaries[cid],
            }
            for cid in ml_candidate_ids
        },
        "development_ranking_this_pass": [
            {"candidate_id": cid, "primary_selection_metric_value": value} for cid, value in ranked
        ],
        "final_candidate_selection_status": (
            "NOT_PERFORMED -- FMD-EXP-02 did not participate this pass, so a "
            "winner cannot be selected across the frozen minimum executable set "
            "(FMD07B_PREEXECUTION_FEASIBILITY_PROTOCOL_AMENDMENT.md Section 7). "
            "development_ranking_this_pass is diagnostic evidence only, never a "
            "selection."
        ),
        "fold_predictions_rows": fold_predictions_rows,
        "completion_token": "FMD-07B_BLOCKED_MINIMUM_EXECUTABLE_COMPARISON_SET_NOT_READY",
    }


PARTIAL_OUTPUT_DIR_REL = "local_data/processed/fmd/model_development/fmd07b_partial_exp01_exp04"


def write_partial_outputs(repo_root: Path, result: dict) -> dict:
    """Writes deliberately non-canonically-named output files (see module
    docstring) -- never the ten names reserved by
    FMD07B_MODEL_DEVELOPMENT_PROTOCOL.md Section 9 for a complete run."""
    out_dir = repo_root / PARTIAL_OUTPUT_DIR_REL
    out_dir.mkdir(parents=True, exist_ok=True)

    predictions_path = out_dir / "fmd07b_partial_fold_predictions.csv"
    predictions_df = pd.DataFrame(result["fold_predictions_rows"]).sort_values(
        ["experiment_id", "candidate_id", "fold_id", "forecast_origin_id"]
    )
    predictions_df.to_csv(predictions_path, index=False)

    manifest = {k: v for k, v in result.items() if k != "fold_predictions_rows"}
    manifest["fold_predictions_csv_sha256_after_write"] = None  # filled below
    manifest_path = out_dir / "fmd07b_partial_development_manifest.json"
    manifest_json = json.dumps(manifest, sort_keys=True, separators=(",", ":"), indent=2)
    manifest_path.write_text(manifest_json, encoding="utf-8")

    predictions_sha = _sha256_file(predictions_path)
    manifest["fold_predictions_csv_sha256_after_write"] = predictions_sha
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), indent=2), encoding="utf-8"
    )

    return {
        "predictions_path": str(predictions_path),
        "manifest_path": str(manifest_path),
        "predictions_sha256": predictions_sha,
    }


if __name__ == "__main__":
    _repo_root = Path(__file__).resolve().parents[_REPO_ROOT_PARENTS_FROM_THIS_FILE]
    _result = run_fmd07b_partial_development(_repo_root)
    _paths = write_partial_outputs(_repo_root, _result)
    print(json.dumps(_paths, indent=2))
