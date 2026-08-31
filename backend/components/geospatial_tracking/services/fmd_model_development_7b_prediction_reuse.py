"""Read-only reuse of persisted FMD-07B EXP-01 and EXP-04 predictions.

This module verifies and loads the existing partial-development artifacts. It
does not fit, retrain, regenerate, score, or calculate metrics for any model.
Prediction-score fields remain strings so filtering cannot alter their
persisted decimal representation.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping, Sequence

from .fmd_model_development_7b import (
    CHECKPOINT,
    DEPENDENCY_REQUIREMENT,
    RANDOM_SEED,
    REQUIRED_SKLEARN_VERSION,
    FrozenCommonSupport,
    NaiveStatisticalCandidateSpec,
    build_ml_candidate_specs,
)
from .fmd_model_development_7b_execution import (
    DEFERRED_EXPERIMENT_IDS,
    EXECUTED_EXPERIMENT_IDS,
    NAIVE_SCORE_UNAVAILABLE,
    PARTIAL_EXECUTION_TOKEN,
    TRAINING_FOLD_SINGLE_CLASS_SKIPPED,
)
from .model_development.baseline_scoring import SCORED

PARTIAL_RESULTS_RELATIVE_DIR = Path(
    "local_data/processed/fmd/model_development/fmd07b_partial_exp01_exp04"
)
PERSISTED_MANIFEST_FILENAME = "fmd07b_partial_development_manifest.json"
PERSISTED_PREDICTIONS_FILENAME = "fmd07b_partial_fold_predictions.csv"
PERSISTED_PREDICTION_SCHEMA = (
    "fold_id",
    "experiment_id",
    "candidate_id",
    "forecast_origin_id",
    "true_label",
    "predicted_score",
    "status",
)


class PersistedPredictionIntegrityError(RuntimeError):
    """Persisted prediction reuse failed an identity or completeness check."""


@dataclass(frozen=True)
class PersistedPredictionRow:
    fold_id: str
    experiment_id: str
    candidate_id: str
    forecast_origin_id: str
    true_label: str
    predicted_score: str
    status: str

    def as_dict(self) -> dict[str, str]:
        return {
            "fold_id": self.fold_id,
            "experiment_id": self.experiment_id,
            "candidate_id": self.candidate_id,
            "forecast_origin_id": self.forecast_origin_id,
            "true_label": self.true_label,
            "predicted_score": self.predicted_score,
            "status": self.status,
        }


@dataclass(frozen=True)
class PersistedPredictionReuse:
    manifest_path: Path
    predictions_path: Path
    manifest_sha256: str
    predictions_sha256: str
    candidate_ids_by_experiment: tuple[tuple[str, tuple[str, ...]], ...]
    rows: tuple[PersistedPredictionRow, ...]
    provenance_verified: bool = True

    def candidate_ids(self, experiment_id: str) -> tuple[str, ...]:
        by_experiment = dict(self.candidate_ids_by_experiment)
        if experiment_id not in by_experiment:
            raise ValueError(f"unsupported persisted experiment_id {experiment_id!r}")
        return by_experiment[experiment_id]

    def rows_for_experiment(self, experiment_id: str) -> tuple[PersistedPredictionRow, ...]:
        self.candidate_ids(experiment_id)
        return tuple(row for row in self.rows if row.experiment_id == experiment_id)


def frozen_persisted_candidate_ids() -> dict[str, tuple[str, ...]]:
    """Return registry-derived IDs without constructing or fitting a runner."""
    return {
        "FMD-EXP-01": (NaiveStatisticalCandidateSpec().candidate_id,),
        "FMD-EXP-04": tuple(sorted(candidate.candidate_id for candidate in build_ml_candidate_specs())),
    }


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_sha256(label: str, value: object) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise PersistedPredictionIntegrityError(f"{label} must be a 64-character SHA-256")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PersistedPredictionIntegrityError(f"{label} is not hexadecimal") from exc
    return value.lower()


def _read_required_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise PersistedPredictionIntegrityError(f"required persisted {label} is missing: {path}") from exc
    except OSError as exc:
        raise PersistedPredictionIntegrityError(f"could not read persisted {label}: {path}") from exc


def _verify_manifest_identity(manifest: Mapping[str, object]) -> dict[str, tuple[str, ...]]:
    expected_candidates = frozen_persisted_candidate_ids()
    required_values = {
        "checkpoint": CHECKPOINT,
        "partial_execution_token": PARTIAL_EXECUTION_TOKEN,
        "dependency_requirement": DEPENDENCY_REQUIREMENT,
        "sklearn_version": REQUIRED_SKLEARN_VERSION,
        "random_seed": RANDOM_SEED,
        "held_out_used": False,
        "sri_lanka_used": False,
        "locked_test_used": False,
    }
    for field, expected in required_values.items():
        if manifest.get(field) != expected:
            raise PersistedPredictionIntegrityError(
                f"manifest provenance mismatch for {field}: expected {expected!r}, observed {manifest.get(field)!r}"
            )
    if tuple(manifest.get("executed_experiment_ids", ())) != EXECUTED_EXPERIMENT_IDS:
        raise PersistedPredictionIntegrityError("manifest executed_experiment_ids is not exactly EXP-01 and EXP-04")
    if tuple(manifest.get("deferred_experiment_ids", ())) != DEFERRED_EXPERIMENT_IDS:
        raise PersistedPredictionIntegrityError("manifest must preserve EXP-02 as deferred")

    naive_candidate = manifest.get("naive_candidate")
    if not isinstance(naive_candidate, Mapping):
        raise PersistedPredictionIntegrityError("manifest naive_candidate entry is missing")
    if naive_candidate.get("candidate_id") != expected_candidates["FMD-EXP-01"][0]:
        raise PersistedPredictionIntegrityError("manifest EXP-01 candidate ID does not match the frozen registry")

    ml_candidates = manifest.get("ml_candidates")
    if not isinstance(ml_candidates, Mapping):
        raise PersistedPredictionIntegrityError("manifest ml_candidates entry is missing")
    if set(ml_candidates) != set(expected_candidates["FMD-EXP-04"]):
        raise PersistedPredictionIntegrityError("manifest EXP-04 candidate IDs do not match the frozen registry")
    return expected_candidates


def _verify_upstream_provenance(artifact_dir: Path, manifest: Mapping[str, object]) -> None:
    input_hashes = manifest.get("input_artifact_sha256")
    if input_hashes is None:
        return
    if not isinstance(input_hashes, Mapping):
        raise PersistedPredictionIntegrityError("manifest input_artifact_sha256 must be a mapping")
    for filename, expected_hash_value in sorted(input_hashes.items()):
        if not isinstance(filename, str) or not filename or Path(filename).name != filename:
            raise PersistedPredictionIntegrityError(f"invalid input provenance filename {filename!r}")
        expected_hash = _require_sha256(f"input artifact {filename}", expected_hash_value)
        input_path = artifact_dir.parent / filename
        observed_hash = _sha256_bytes(_read_required_bytes(input_path, f"provenance input {filename}"))
        if observed_hash != expected_hash:
            raise PersistedPredictionIntegrityError(
                f"input artifact SHA-256 mismatch for {filename}: expected {expected_hash}, observed {observed_hash}"
            )


def _validate_prediction_score(row_number: int, status: str, persisted_value: str) -> None:
    if status != SCORED:
        if persisted_value != "":
            raise PersistedPredictionIntegrityError(
                f"prediction row {row_number} has a numeric value with unavailable status {status!r}"
            )
        return
    if not persisted_value or persisted_value != persisted_value.strip():
        raise PersistedPredictionIntegrityError(f"prediction row {row_number} has a missing/invalid score")
    try:
        numeric_value = Decimal(persisted_value)
    except InvalidOperation as exc:
        raise PersistedPredictionIntegrityError(f"prediction row {row_number} score is not numeric") from exc
    if not numeric_value.is_finite() or numeric_value < 0 or numeric_value > 1:
        raise PersistedPredictionIntegrityError(
            f"prediction row {row_number} score must be a finite value in [0, 1]"
        )


def _parse_prediction_rows(
    payload: bytes,
    *,
    expected_candidates: Mapping[str, Sequence[str]],
    usable_fold_ids: set[str],
) -> tuple[PersistedPredictionRow, ...]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PersistedPredictionIntegrityError("persisted prediction CSV is not valid UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != PERSISTED_PREDICTION_SCHEMA:
        raise PersistedPredictionIntegrityError(
            f"persisted prediction schema mismatch: expected {PERSISTED_PREDICTION_SCHEMA}, "
            f"observed {tuple(reader.fieldnames or ())}"
        )

    expected_candidate_keys = {
        (experiment_id, candidate_id)
        for experiment_id, candidate_ids in expected_candidates.items()
        for candidate_id in candidate_ids
    }
    allowed_statuses = {
        "FMD-EXP-01": {SCORED, NAIVE_SCORE_UNAVAILABLE},
        "FMD-EXP-04": {SCORED, TRAINING_FOLD_SINGLE_CLASS_SKIPPED},
    }
    seen_candidate_origins: set[tuple[str, str, str]] = set()
    seen_candidate_keys: set[tuple[str, str]] = set()
    origin_metadata: dict[str, tuple[str, str]] = {}
    rows: list[PersistedPredictionRow] = []
    for row_number, raw in enumerate(reader, start=2):
        if None in raw or any(raw.get(field) is None for field in PERSISTED_PREDICTION_SCHEMA):
            raise PersistedPredictionIntegrityError(f"prediction row {row_number} does not match the frozen schema")
        identity_values = tuple(raw[field] for field in PERSISTED_PREDICTION_SCHEMA[:4])
        if any(not value or value != value.strip() for value in identity_values):
            raise PersistedPredictionIntegrityError(f"prediction row {row_number} has an invalid identity")
        fold_id, experiment_id, candidate_id, origin_id = identity_values
        candidate_key = (experiment_id, candidate_id)
        if candidate_key not in expected_candidate_keys:
            raise PersistedPredictionIntegrityError(
                f"prediction row {row_number} has unexpected candidate {candidate_key!r}"
            )
        if fold_id not in usable_fold_ids:
            raise PersistedPredictionIntegrityError(
                f"prediction row {row_number} uses fold {fold_id!r} absent from manifest usable_fold_ids"
            )
        if raw["true_label"] not in {"0", "1"}:
            raise PersistedPredictionIntegrityError(f"prediction row {row_number} true_label is not binary")
        if raw["status"] not in allowed_statuses[experiment_id]:
            raise PersistedPredictionIntegrityError(
                f"prediction row {row_number} has unexpected status {raw['status']!r}"
            )
        _validate_prediction_score(row_number, raw["status"], raw["predicted_score"])

        candidate_origin = (experiment_id, candidate_id, origin_id)
        if candidate_origin in seen_candidate_origins:
            raise PersistedPredictionIntegrityError(
                f"duplicate persisted candidate/origin row for {candidate_origin!r}"
            )
        seen_candidate_origins.add(candidate_origin)
        seen_candidate_keys.add(candidate_key)
        metadata = (fold_id, raw["true_label"])
        if origin_id in origin_metadata and origin_metadata[origin_id] != metadata:
            raise PersistedPredictionIntegrityError(
                f"inconsistent fold/label metadata across candidates for origin {origin_id!r}"
            )
        origin_metadata[origin_id] = metadata
        rows.append(
            PersistedPredictionRow(
                fold_id=fold_id,
                experiment_id=experiment_id,
                candidate_id=candidate_id,
                forecast_origin_id=origin_id,
                true_label=raw["true_label"],
                predicted_score=raw["predicted_score"],
                status=raw["status"],
            )
        )
    if seen_candidate_keys != expected_candidate_keys:
        missing = sorted(expected_candidate_keys - seen_candidate_keys)
        raise PersistedPredictionIntegrityError(f"persisted prediction CSV is missing candidate(s): {missing}")
    return tuple(
        sorted(
            rows,
            key=lambda row: (row.fold_id, row.experiment_id, row.candidate_id, row.forecast_origin_id),
        )
    )


def load_persisted_exp01_exp04_predictions(repo_root: Path) -> PersistedPredictionReuse:
    """Load and integrity-check the existing partial prediction artifacts."""
    artifact_dir = Path(repo_root) / PARTIAL_RESULTS_RELATIVE_DIR
    manifest_path = artifact_dir / PERSISTED_MANIFEST_FILENAME
    predictions_path = artifact_dir / PERSISTED_PREDICTIONS_FILENAME

    manifest_bytes = _read_required_bytes(manifest_path, "manifest")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PersistedPredictionIntegrityError("persisted prediction manifest is invalid") from exc
    if not isinstance(manifest, Mapping):
        raise PersistedPredictionIntegrityError("persisted prediction manifest must be a JSON object")

    expected_candidates = _verify_manifest_identity(manifest)
    _verify_upstream_provenance(artifact_dir, manifest)

    predictions_bytes = _read_required_bytes(predictions_path, "prediction CSV")
    observed_predictions_sha256 = _sha256_bytes(predictions_bytes)
    expected_predictions_sha256 = _require_sha256(
        "fold_predictions_csv_sha256_after_write",
        manifest.get("fold_predictions_csv_sha256_after_write"),
    )
    if observed_predictions_sha256 != expected_predictions_sha256:
        raise PersistedPredictionIntegrityError(
            "persisted prediction CSV SHA-256 mismatch: "
            f"expected {expected_predictions_sha256}, observed {observed_predictions_sha256}"
        )

    raw_usable_fold_ids = manifest.get("usable_fold_ids")
    if not isinstance(raw_usable_fold_ids, list) or not raw_usable_fold_ids:
        raise PersistedPredictionIntegrityError("manifest usable_fold_ids must be a non-empty list")
    if any(not isinstance(fold_id, str) or not fold_id for fold_id in raw_usable_fold_ids):
        raise PersistedPredictionIntegrityError("manifest usable_fold_ids contains an invalid fold ID")
    if len(raw_usable_fold_ids) != len(set(raw_usable_fold_ids)):
        raise PersistedPredictionIntegrityError("manifest usable_fold_ids contains duplicates")

    rows = _parse_prediction_rows(
        predictions_bytes,
        expected_candidates=expected_candidates,
        usable_fold_ids=set(raw_usable_fold_ids),
    )
    candidate_identity = tuple(
        (experiment_id, expected_candidates[experiment_id]) for experiment_id in EXECUTED_EXPERIMENT_IDS
    )
    return PersistedPredictionReuse(
        manifest_path=manifest_path,
        predictions_path=predictions_path,
        manifest_sha256=_sha256_bytes(manifest_bytes),
        predictions_sha256=observed_predictions_sha256,
        candidate_ids_by_experiment=candidate_identity,
        rows=rows,
    )


def filter_persisted_predictions_to_common_support(
    persisted: PersistedPredictionReuse,
    frozen_support: FrozenCommonSupport,
) -> tuple[PersistedPredictionRow, ...]:
    """Return exact persisted rows on one immutable per-fold common support."""
    persisted_candidates = dict(persisted.candidate_ids_by_experiment)
    support_reuse_candidates = {
        experiment_id: tuple(
            sorted(
                candidate_id
                for candidate_experiment_id, candidate_id in frozen_support.candidate_keys
                if candidate_experiment_id == experiment_id
            )
        )
        for experiment_id in EXECUTED_EXPERIMENT_IDS
    }
    if support_reuse_candidates != persisted_candidates:
        raise PersistedPredictionIntegrityError(
            "frozen common-support EXP-01/EXP-04 candidates do not match persisted registry"
        )

    by_candidate_origin = {
        (row.experiment_id, row.candidate_id, row.forecast_origin_id): row
        for row in persisted.rows
        if row.fold_id == frozen_support.fold_id
    }
    filtered: list[PersistedPredictionRow] = []
    missing_or_unavailable: list[str] = []
    for experiment_id in EXECUTED_EXPERIMENT_IDS:
        for candidate_id in persisted_candidates[experiment_id]:
            for origin_id in frozen_support.common_support_origin_ids:
                row = by_candidate_origin.get((experiment_id, candidate_id, origin_id))
                if row is None:
                    missing_or_unavailable.append(
                        f"{experiment_id}/{candidate_id}/{origin_id}:MISSING_ROW"
                    )
                elif row.status != SCORED or row.predicted_score == "":
                    missing_or_unavailable.append(
                        f"{experiment_id}/{candidate_id}/{origin_id}:{row.status}"
                    )
                else:
                    filtered.append(row)
    if missing_or_unavailable:
        raise PersistedPredictionIntegrityError(
            "persisted prediction reuse cannot shrink frozen common support: "
            + ", ".join(missing_or_unavailable)
        )
    return tuple(filtered)
