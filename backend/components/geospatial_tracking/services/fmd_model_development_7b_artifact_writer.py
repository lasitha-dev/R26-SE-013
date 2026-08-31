"""Deterministic serializer for the ten canonical FMD-07B artifacts.

This module is deliberately a writer only.  Its inputs are already-finalized
in-memory artifact payloads, including the externally supplied final-refit
state.  It does not load partial artifacts, execute candidates, fit/refit a
model, calculate metrics, or choose a candidate.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CHECKPOINT = "FMD-07B"
SERIALIZATION_FORMAT = "FMD07B_CANONICAL_ARTIFACT_SERIALIZATION_V1"

FMD07B_CANDIDATE_ELIGIBILITY = "fmd07b_candidate_eligibility.json"
FMD07B_CANDIDATE_REGISTRY = "fmd07b_candidate_registry.json"
FMD07B_CHRONOLOGICAL_FOLD_MANIFEST = "fmd07b_chronological_fold_manifest.json"
FMD07B_FOLD_PREDICTIONS = "fmd07b_fold_predictions.csv"
FMD07B_FOLD_CANDIDATE_METRICS = "fmd07b_fold_candidate_metrics.csv"
FMD07B_FOLD_SUMMARY_METRICS = "fmd07b_fold_summary_metrics.csv"
FMD07B_PREPROCESSING_CALIBRATION_AUDIT = "fmd07b_preprocessing_calibration_audit.json"
FMD07B_CANDIDATE_SELECTION_SUMMARY = "fmd07b_candidate_selection_summary.json"
FMD07B_FROZEN_MODEL_SPEC = "fmd07b_frozen_model_spec.json"
FMD07B_MANIFEST = "fmd07b_manifest.json"

CANONICAL_ARTIFACT_FILENAMES = (
    FMD07B_CANDIDATE_ELIGIBILITY,
    FMD07B_CANDIDATE_REGISTRY,
    FMD07B_CHRONOLOGICAL_FOLD_MANIFEST,
    FMD07B_FOLD_PREDICTIONS,
    FMD07B_FOLD_CANDIDATE_METRICS,
    FMD07B_FOLD_SUMMARY_METRICS,
    FMD07B_PREPROCESSING_CALIBRATION_AUDIT,
    FMD07B_CANDIDATE_SELECTION_SUMMARY,
    FMD07B_FROZEN_MODEL_SPEC,
    FMD07B_MANIFEST,
)
ARTIFACT_COUNT = len(CANONICAL_ARTIFACT_FILENAMES)

JSON_ARTIFACT_FILENAMES = (
    FMD07B_CANDIDATE_ELIGIBILITY,
    FMD07B_CANDIDATE_REGISTRY,
    FMD07B_CHRONOLOGICAL_FOLD_MANIFEST,
    FMD07B_PREPROCESSING_CALIBRATION_AUDIT,
    FMD07B_CANDIDATE_SELECTION_SUMMARY,
    FMD07B_FROZEN_MODEL_SPEC,
    FMD07B_MANIFEST,
)

FOLD_PREDICTION_COLUMNS = (
    "fold_id",
    "experiment_id",
    "candidate_id",
    "forecast_origin_id",
    "true_label",
    "predicted_score",
    "status",
)
FOLD_CANDIDATE_METRIC_COLUMNS = (
    "fold_id",
    "experiment_id",
    "candidate_id",
    "n_scored",
    "n_unscored",
    "unscored_reason_counts",
    "pr_auc",
    "auroc",
    "brier_score",
    "selected_threshold",
    "f1_at_selected_threshold",
    "precision_at_selected_threshold",
    "recall_at_selected_threshold",
    "specificity_at_selected_threshold",
)
FOLD_SUMMARY_METRIC_COLUMNS = (
    "experiment_id",
    "candidate_id",
    "n_usable_folds",
    "n_contributing_folds",
    "primary_selection_metric_name",
    "primary_metric_aggregation_rule",
    "primary_selection_metric_value",
    "median_pr_auc",
    "mean_auroc",
    "mean_brier_score",
    "median_selected_threshold",
)

_CSV_SCHEMAS = {
    FMD07B_FOLD_PREDICTIONS: FOLD_PREDICTION_COLUMNS,
    FMD07B_FOLD_CANDIDATE_METRICS: FOLD_CANDIDATE_METRIC_COLUMNS,
    FMD07B_FOLD_SUMMARY_METRICS: FOLD_SUMMARY_METRIC_COLUMNS,
}
_CSV_SORT_KEYS = {
    FMD07B_FOLD_PREDICTIONS: (
        "experiment_id",
        "candidate_id",
        "fold_id",
        "forecast_origin_id",
    ),
    FMD07B_FOLD_CANDIDATE_METRICS: ("experiment_id", "candidate_id", "fold_id"),
    FMD07B_FOLD_SUMMARY_METRICS: ("experiment_id", "candidate_id"),
}

_FIREWALL_FIELDS = ("held_out_used", "sri_lanka_used", "locked_test_used")
_PROVENANCE_FIELDS = (
    "input_artifact_sha256",
    "implementation_identity",
    "python_version",
    "resolved_direct_dependency_versions",
)
_FROZEN_MODEL_SPEC_FIELDS = (
    "selected_candidate_id",
    "model",
    "preprocessing",
    "calibration",
    "threshold",
    "final_refit_state",
    "implementation_identity",
    "resolved_direct_dependency_versions",
)
_WRITER_CONTROLLED_MANIFEST_FIELDS = (
    "artifact_count",
    "artifact_filenames",
    "output_artifact_sha256",
    "output_artifact_sha256_scope",
    "serialization",
)
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class CanonicalArtifactValidationError(ValueError):
    """A canonical writer input is incomplete, ambiguous, or non-finite."""


@dataclass(frozen=True)
class CanonicalArtifactWriteResult:
    """Paths and byte hashes resulting from one canonical writer call."""

    output_dir: Path
    artifact_paths: tuple[Path, ...]
    artifact_sha256: Mapping[str, str]
    artifact_count: int = ARTIFACT_COUNT


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _required_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CanonicalArtifactValidationError(f"{label} must be a mapping")
    return value


def _require_fields(value: Mapping[str, object], required: Sequence[str], label: str) -> None:
    missing = sorted(set(required) - set(value))
    if missing:
        raise CanonicalArtifactValidationError(f"{label} is missing required field(s): {missing}")


def _normalize_json(value: object, *, location: str) -> Any:
    """Return a JSON-native copy while rejecting ambiguous/non-finite values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalArtifactValidationError(f"{location} contains a non-finite float")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise CanonicalArtifactValidationError(f"{location} contains a non-string JSON key")
            normalized[key] = _normalize_json(child, location=f"{location}.{key}")
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _normalize_json(child, location=f"{location}[{index}]")
            for index, child in enumerate(value)
        ]
    raise CanonicalArtifactValidationError(
        f"{location} contains unsupported value type {type(value).__name__}"
    )


def _canonical_json_bytes(value: object, *, location: str) -> bytes:
    normalized = _normalize_json(value, location=location)
    try:
        text = json.dumps(
            normalized,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:  # defensive after normalization
        raise CanonicalArtifactValidationError(f"{location} is not canonical JSON") from exc
    return (text + "\n").encode("utf-8")


def _canonical_csv_cell(value: object, *, location: str) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalArtifactValidationError(f"{location} contains a non-finite float")
        return repr(value)
    if isinstance(value, (Mapping, Sequence)) and not isinstance(value, (str, bytes, bytearray)):
        return _canonical_json_bytes(value, location=location).decode("utf-8").rstrip("\n")
    raise CanonicalArtifactValidationError(
        f"{location} contains unsupported CSV value type {type(value).__name__}"
    )


def _canonical_csv_bytes(filename: str, value: object) -> bytes:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise CanonicalArtifactValidationError(f"{filename} payload must be a sequence of row mappings")

    columns = _CSV_SCHEMAS[filename]
    expected_columns = set(columns)
    sort_keys = _CSV_SORT_KEYS[filename]
    canonical_rows: list[dict[str, str]] = []
    seen_identities: set[tuple[str, ...]] = set()

    for row_index, raw_row in enumerate(value):
        if not isinstance(raw_row, Mapping):
            raise CanonicalArtifactValidationError(f"{filename} row {row_index} must be a mapping")
        observed_columns = set(raw_row)
        if observed_columns != expected_columns:
            missing = sorted(expected_columns - observed_columns)
            unexpected = sorted(observed_columns - expected_columns, key=str)
            raise CanonicalArtifactValidationError(
                f"{filename} row {row_index} schema mismatch; missing={missing}, unexpected={unexpected}"
            )
        canonical_row = {
            column: _canonical_csv_cell(
                raw_row[column], location=f"{filename}[{row_index}].{column}"
            )
            for column in columns
        }
        identity = tuple(canonical_row[key] for key in sort_keys)
        if any(not component for component in identity):
            raise CanonicalArtifactValidationError(
                f"{filename} row {row_index} has an empty deterministic identity field"
            )
        if identity in seen_identities:
            raise CanonicalArtifactValidationError(
                f"{filename} contains duplicate deterministic row identity {identity!r}"
            )
        seen_identities.add(identity)
        canonical_rows.append(canonical_row)

    canonical_rows.sort(key=lambda row: tuple(row[key] for key in sort_keys))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=columns,
        extrasaction="raise",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(canonical_rows)
    return buffer.getvalue().encode("utf-8")


def _validate_sha256_mapping(value: object, label: str) -> None:
    hashes = _required_mapping(value, label)
    if not hashes:
        raise CanonicalArtifactValidationError(f"{label} must not be empty")
    for artifact_name, digest in hashes.items():
        if not isinstance(artifact_name, str) or not artifact_name:
            raise CanonicalArtifactValidationError(f"{label} contains an invalid artifact name")
        if not isinstance(digest, str) or _SHA256_PATTERN.fullmatch(digest) is None:
            raise CanonicalArtifactValidationError(
                f"{label}.{artifact_name} must be a lowercase 64-character SHA-256"
            )


def _validate_nonempty_string_mapping(value: object, label: str) -> None:
    mapping = _required_mapping(value, label)
    if not mapping:
        raise CanonicalArtifactValidationError(f"{label} must not be empty")
    for key, item in mapping.items():
        if not isinstance(key, str) or not key or not isinstance(item, str) or not item:
            raise CanonicalArtifactValidationError(f"{label} must map non-empty strings to non-empty strings")


def _validate_manifest_payload(value: object) -> dict[str, Any]:
    manifest = _required_mapping(value, FMD07B_MANIFEST)
    _require_fields(
        manifest,
        ("checkpoint", *_FIREWALL_FIELDS, *_PROVENANCE_FIELDS),
        FMD07B_MANIFEST,
    )
    if manifest["checkpoint"] != CHECKPOINT:
        raise CanonicalArtifactValidationError(f"{FMD07B_MANIFEST}.checkpoint must be {CHECKPOINT}")
    for field in _FIREWALL_FIELDS:
        if manifest[field] is not False:
            raise CanonicalArtifactValidationError(f"{FMD07B_MANIFEST}.{field} must be false")
    controlled = sorted(set(manifest) & set(_WRITER_CONTROLLED_MANIFEST_FIELDS))
    if controlled:
        raise CanonicalArtifactValidationError(
            f"{FMD07B_MANIFEST} contains writer-controlled field(s): {controlled}"
        )
    _validate_sha256_mapping(manifest["input_artifact_sha256"], "input_artifact_sha256")
    implementation_identity = _required_mapping(
        manifest["implementation_identity"], "implementation_identity"
    )
    if not implementation_identity:
        raise CanonicalArtifactValidationError("implementation_identity must not be empty")
    if not isinstance(manifest["python_version"], str) or not manifest["python_version"]:
        raise CanonicalArtifactValidationError("python_version must be a non-empty string")
    _validate_nonempty_string_mapping(
        manifest["resolved_direct_dependency_versions"],
        "resolved_direct_dependency_versions",
    )
    return _normalize_json(manifest, location=FMD07B_MANIFEST)


def _validate_frozen_model_spec(value: object) -> None:
    frozen_spec = _required_mapping(value, FMD07B_FROZEN_MODEL_SPEC)
    _require_fields(frozen_spec, _FROZEN_MODEL_SPEC_FIELDS, FMD07B_FROZEN_MODEL_SPEC)
    if not isinstance(frozen_spec["selected_candidate_id"], str) or not frozen_spec[
        "selected_candidate_id"
    ]:
        raise CanonicalArtifactValidationError(
            f"{FMD07B_FROZEN_MODEL_SPEC}.selected_candidate_id must be a non-empty string"
        )
    if frozen_spec["final_refit_state"] is None:
        raise CanonicalArtifactValidationError(
            f"{FMD07B_FROZEN_MODEL_SPEC}.final_refit_state must be supplied externally"
        )


def _validate_payloads(artifact_payloads: object) -> Mapping[str, object]:
    payloads = _required_mapping(artifact_payloads, "artifact_payloads")
    expected = set(CANONICAL_ARTIFACT_FILENAMES)
    observed = set(payloads)
    if observed != expected:
        missing = sorted(expected - observed)
        unexpected = sorted(observed - expected, key=str)
        raise CanonicalArtifactValidationError(
            f"artifact_payloads must contain exactly the ten canonical names; "
            f"missing={missing}, unexpected={unexpected}"
        )
    for filename in JSON_ARTIFACT_FILENAMES:
        _required_mapping(payloads[filename], filename)
    _validate_frozen_model_spec(payloads[FMD07B_FROZEN_MODEL_SPEC])
    return payloads


def _build_serialized_artifacts(artifact_payloads: object) -> dict[str, bytes]:
    payloads = _validate_payloads(artifact_payloads)
    serialized: dict[str, bytes] = {}

    for filename in CANONICAL_ARTIFACT_FILENAMES:
        if filename == FMD07B_MANIFEST:
            continue
        if filename in _CSV_SCHEMAS:
            serialized[filename] = _canonical_csv_bytes(filename, payloads[filename])
        else:
            serialized[filename] = _canonical_json_bytes(payloads[filename], location=filename)

    non_manifest_hashes = {
        filename: _sha256_bytes(serialized[filename])
        for filename in CANONICAL_ARTIFACT_FILENAMES
        if filename != FMD07B_MANIFEST
    }
    manifest = _validate_manifest_payload(payloads[FMD07B_MANIFEST])
    manifest.update(
        {
            "artifact_count": ARTIFACT_COUNT,
            "artifact_filenames": list(CANONICAL_ARTIFACT_FILENAMES),
            "output_artifact_sha256": non_manifest_hashes,
            "output_artifact_sha256_scope": "ALL_CANONICAL_OUTPUTS_EXCEPT_SELF_REFERENTIAL_MANIFEST",
            "serialization": {
                "atomic_write": "SAME_DIRECTORY_TEMP_FILE_FSYNC_THEN_OS_REPLACE",
                "csv": "UTF-8_FIXED_COLUMNS_STABLE_ROW_ORDER_LF",
                "format": SERIALIZATION_FORMAT,
                "json": "UTF-8_SORTED_KEYS_COMPACT_FINITE_VALUES_LF",
                "manifest_sha256": "RETURNED_BY_WRITER_NOT_SELF_EMBEDDED",
            },
        }
    )
    serialized[FMD07B_MANIFEST] = _canonical_json_bytes(manifest, location=FMD07B_MANIFEST)
    return {filename: serialized[filename] for filename in CANONICAL_ARTIFACT_FILENAMES}


def _stage_temp_file(output_dir: Path, filename: str, payload: bytes) -> Path:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{filename}.",
            suffix=".tmp",
            dir=output_dir,
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        return temp_path
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def write_canonical_fmd07b_artifacts(
    output_dir: str | Path,
    artifact_payloads: Mapping[str, object],
) -> CanonicalArtifactWriteResult:
    """Validate and atomically write exactly the ten canonical artifacts.

    All payloads are serialized and hashed before any target is replaced.  The
    manifest is replaced last, so it cannot advertise artifact hashes before
    the nine artifacts it describes have reached their final paths.
    """
    serialized = _build_serialized_artifacts(artifact_payloads)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if not destination.is_dir():
        raise NotADirectoryError(destination)

    staged: dict[str, Path] = {}
    try:
        for filename in CANONICAL_ARTIFACT_FILENAMES:
            staged[filename] = _stage_temp_file(destination, filename, serialized[filename])
        for filename in CANONICAL_ARTIFACT_FILENAMES:
            temp_path = staged[filename]
            os.replace(temp_path, destination / filename)
            del staged[filename]
    finally:
        for temp_path in staged.values():
            temp_path.unlink(missing_ok=True)

    paths = tuple(destination / filename for filename in CANONICAL_ARTIFACT_FILENAMES)
    hashes = {filename: _sha256_bytes(serialized[filename]) for filename in CANONICAL_ARTIFACT_FILENAMES}
    return CanonicalArtifactWriteResult(
        output_dir=destination,
        artifact_paths=paths,
        artifact_sha256=hashes,
    )


__all__ = [
    "ARTIFACT_COUNT",
    "CANONICAL_ARTIFACT_FILENAMES",
    "CanonicalArtifactValidationError",
    "CanonicalArtifactWriteResult",
    "FOLD_CANDIDATE_METRIC_COLUMNS",
    "FOLD_PREDICTION_COLUMNS",
    "FOLD_SUMMARY_METRIC_COLUMNS",
    "write_canonical_fmd07b_artifacts",
]
