"""FMD-07A-R2B3: offline source-to-origin matrix population.

This module is deliberately a thin orchestration layer around the frozen R2A
aggregation implementation.  It consumes only completed local R2B2 artifacts,
constructs predictors before reading the label-bearing matrix scaffold, and
never performs extraction, retry, imputation, model fitting, prediction, or
evaluation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import tempfile
from collections import Counter
from pathlib import Path

from ..data_processing.fmd_feature_status import SOURCE_VALUE_AVAILABLE
from .fmd_model_development import (
    IDENTIFIER_COLUMNS,
    METADATA_COLUMNS,
    NON_PREDICTOR_AUDIT_ONLY_COLUMNS,
    TARGET_COLUMN,
    matrix_fieldnames,
)
from .fmd_model_development_r2a import (
    NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0,
    NUMERIC_AGGREGATION_RULE,
    ORIGIN_AGGREGATE_ALL_VALID,
    ORIGIN_AGGREGATE_NO_VALID_VALUE,
    ORIGIN_AGGREGATE_PARTIAL_VALID,
    aggregate_origin_feature_status,
    build_origin_feature_row_from_source_features,
)
from .model_fitting_exposure import FIT_DEVELOPMENT

CHECKPOINT = "FMD-07A-R2B3"
CONTRACT_STATUS = "PRE_IMPLEMENTATION_SOFTWARE_DATA_PIPELINE_PROTOCOL_FREEZE"
COMPLETION_TOKEN = "FMD-07A-R2B3_COMPLETE_READY_FOR_FMD-07B"
NEXT_CHECKPOINT = "FMD-07B"

EXPECTED_ORIGIN_COUNT = 3761
EXPECTED_SOURCE_COUNT = 6799
EXPECTED_ORIGIN_SOURCE_APPEARANCE_COUNT = 41684
EXPECTED_FEATURE_COUNT = 47
EXPECTED_MATRIX_COLUMN_COUNT = 105
EXPECTED_AUDIT_ROW_COUNT = EXPECTED_ORIGIN_COUNT * EXPECTED_FEATURE_COUNT

MATRIX_FILENAME = "fmd07_r2b3_development_feature_matrix.csv"
AUDIT_FILENAME = "fmd07_r2b3_origin_feature_aggregation_audit.csv"
MANIFEST_FILENAME = "fmd07_r2b3_manifest.json"

SOURCE_TABLE_FILENAME = "fmd07_full_source_features.csv"
R2B2_MANIFEST_FILENAME = "fmd07_full_source_extraction_manifest.json"
R2B2_PROGRESS_FILENAME = "fmd07_feature_extraction_progress.json"
R2B2_FAILURE_LEDGER_FILENAME = "fmd07_feature_extraction_failure_ledger.json"
ORIGIN_SOURCE_MAP_FILENAME = "fmd07_origin_source_map.json"
UNIQUE_SOURCE_INDEX_FILENAME = "fmd07_unique_source_extraction_index.csv"
R2A_PROTOCOL_FILENAME = "fmd07_origin_feature_assembly_protocol.json"
SCHEMA_MATRIX_FILENAME = "fmd07_development_feature_matrix.csv"
MODEL_INPUT_SCHEMA_FILENAME = "fmd07_model_input_schema.json"
FMD07A_PROVENANCE_FILENAME = "fmd07a_provenance.json"

AUDIT_FIELDNAMES = [
    "forecast_origin_id",
    "feature_name",
    "total_source_count",
    "valid_source_count",
    "invalid_source_count",
    "valid_source_fraction",
    "underlying_status_counts_json",
]

VALUE_PRESENT_STATUSES = {
    ORIGIN_AGGREGATE_ALL_VALID,
    ORIGIN_AGGREGATE_PARTIAL_VALID,
}
VALUE_BLANK_STATUSES = {
    ORIGIN_AGGREGATE_NO_VALID_VALUE,
    NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0,
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def _atomic_write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def _atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _atomic_copy_bytes(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    tmp.write_bytes(source.read_bytes())
    tmp.replace(destination)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"FMD-07A-R2B3 invariant failed: {message}")


def _unique_by(rows: list[dict], field: str, *, artifact: str) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    duplicates: list[str] = []
    for row in rows:
        key = row.get(field, "")
        _require(bool(key), f"{artifact} contains a blank {field}")
        if key in indexed:
            duplicates.append(key)
        else:
            indexed[key] = row
    _require(not duplicates, f"{artifact} contains duplicate {field} values: {duplicates[:5]}")
    return indexed


def _validate_available_values(source_rows: list[dict], feature_names: list[str]) -> None:
    for feature_name in feature_names:
        value_key = f"{feature_name}_value"
        status_key = f"{feature_name}_status"
        for row in source_rows:
            _require(value_key in row and status_key in row, f"source table is missing {value_key}/{status_key}")
            if row[status_key] != SOURCE_VALUE_AVAILABLE:
                continue
            raw_value = row[value_key]
            try:
                finite = raw_value not in (None, "") and math.isfinite(float(raw_value))
            except (TypeError, ValueError):
                finite = False
            _require(
                finite,
                f"source {row.get('source_id')!r} feature {feature_name!r} is "
                f"{SOURCE_VALUE_AVAILABLE!r} without a finite numeric value",
            )


def load_and_validate_predictor_inputs(model_dev_dir: str | Path) -> dict:
    """Load only label-free R2B2/R2A artifacts and enforce the entry gate."""
    base = Path(model_dev_dir)
    paths = {
        SOURCE_TABLE_FILENAME: base / SOURCE_TABLE_FILENAME,
        R2B2_MANIFEST_FILENAME: base / R2B2_MANIFEST_FILENAME,
        R2B2_PROGRESS_FILENAME: base / R2B2_PROGRESS_FILENAME,
        R2B2_FAILURE_LEDGER_FILENAME: base / R2B2_FAILURE_LEDGER_FILENAME,
        ORIGIN_SOURCE_MAP_FILENAME: base / ORIGIN_SOURCE_MAP_FILENAME,
        UNIQUE_SOURCE_INDEX_FILENAME: base / UNIQUE_SOURCE_INDEX_FILENAME,
        R2A_PROTOCOL_FILENAME: base / R2A_PROTOCOL_FILENAME,
    }
    for name, path in paths.items():
        _require(path.is_file(), f"required predictor input {name} does not exist")

    source_rows, source_fieldnames = _read_csv(paths[SOURCE_TABLE_FILENAME])
    r2b2_manifest = _read_json(paths[R2B2_MANIFEST_FILENAME])
    progress = _read_json(paths[R2B2_PROGRESS_FILENAME])
    failure_ledger = _read_json(paths[R2B2_FAILURE_LEDGER_FILENAME])
    origin_source_map = _read_json(paths[ORIGIN_SOURCE_MAP_FILENAME])
    source_index_rows, _ = _read_csv(paths[UNIQUE_SOURCE_INDEX_FILENAME])
    r2a_protocol = _read_json(paths[R2A_PROTOCOL_FILENAME])

    _require(r2b2_manifest.get("checkpoint") == "FMD-07A-R2B2", "R2B2 manifest checkpoint mismatch")
    _require(r2b2_manifest.get("sources_total") == EXPECTED_SOURCE_COUNT, "R2B2 total source count is not 6799")
    _require(r2b2_manifest.get("sources_complete") == EXPECTED_SOURCE_COUNT, "R2B2 complete source count is not 6799")
    _require(r2b2_manifest.get("sources_remaining") == 0, "R2B2 has remaining sources")
    _require(r2b2_manifest.get("unique_source_count") == EXPECTED_SOURCE_COUNT, "R2B2 unique source count is not 6799")
    _require(r2b2_manifest.get("full_source_table_row_count") == EXPECTED_SOURCE_COUNT, "R2B2 table row count mismatch")
    _require(r2b2_manifest.get("held_out_used") is False, "R2B2 manifest reports held-out use")
    _require(r2b2_manifest.get("sri_lanka_used") is False, "R2B2 manifest reports Sri Lanka use")
    _require(r2b2_manifest.get("model_trained") is False, "R2B2 manifest reports model training")
    _require(r2b2_manifest.get("predictive_metrics_used") is False, "R2B2 manifest reports predictive metric use")
    _require(
        sha256_file(paths[SOURCE_TABLE_FILENAME]) == r2b2_manifest.get("full_source_table_sha256"),
        "R2B2 source-table SHA-256 does not match its manifest",
    )

    _require(progress.get("checkpoint") == "FMD-07A-R2B2", "R2B2 progress checkpoint mismatch")
    _require(progress.get("sources_total") == EXPECTED_SOURCE_COUNT, "progress total source count mismatch")
    _require(progress.get("sources_complete") == EXPECTED_SOURCE_COUNT, "progress complete source count mismatch")
    _require(progress.get("sources_remaining") == 0, "progress has remaining sources")
    _require(progress.get("sources_terminal_accounted") == EXPECTED_SOURCE_COUNT, "not every source is terminal-accounted")
    _require(progress.get("sources_terminal_remaining") == 0, "progress has terminal-remaining sources")
    _require(progress.get("held_out_included") is False, "progress includes held-out data")
    _require(progress.get("sri_lanka_included") is False, "progress includes Sri Lanka data")
    _require(progress.get("model_trained") is False, "progress reports model training")
    _require(progress.get("predictive_metrics_used") is False, "progress reports predictive metrics")

    _require(isinstance(failure_ledger, list), "R2B2 failure ledger is not a list")
    retryable_entries = [entry for entry in failure_ledger if entry.get("retry_eligible") is True]
    _require(not retryable_entries, f"R2B2 failure ledger has {len(retryable_entries)} retryable entries")

    _require(len(source_rows) == EXPECTED_SOURCE_COUNT, "source table does not contain 6799 rows")
    _require(not any(name.startswith("_") for name in source_fieldnames), "source table exposes a cache-private field")
    source_by_id = _unique_by(source_rows, "source_id", artifact=SOURCE_TABLE_FILENAME)
    _require(len(source_by_id) == EXPECTED_SOURCE_COUNT, "source table does not contain 6799 unique source ids")
    _require(
        [row["source_id"] for row in source_rows] == sorted(source_by_id),
        "source table is not deterministically ordered by source_id",
    )

    source_index_by_id = _unique_by(source_index_rows, "source_id", artifact=UNIQUE_SOURCE_INDEX_FILENAME)
    _require(set(source_index_by_id) == set(source_by_id), "source index and source table id sets differ")

    _require(origin_source_map.get("checkpoint") == "FMD-07A-R2B2", "origin-source map checkpoint mismatch")
    _require(origin_source_map.get("development_origin_count") == EXPECTED_ORIGIN_COUNT, "origin-source map origin count mismatch")
    _require(origin_source_map.get("unique_required_source_count") == EXPECTED_SOURCE_COUNT, "origin-source map source count mismatch")
    mapping = origin_source_map.get("origin_to_source_ids")
    _require(isinstance(mapping, dict), "origin-source map payload is not an object")
    _require(len(mapping) == EXPECTED_ORIGIN_COUNT, "origin-source map does not contain 3761 origins")
    _require(list(mapping) == sorted(mapping), "origin-source map keys are not deterministically ordered")
    duplicate_mappings = [origin_id for origin_id, ids in mapping.items() if len(ids) != len(set(ids))]
    _require(not duplicate_mappings, f"origin-source map has duplicate ids inside origins: {duplicate_mappings[:5]}")
    appearance_count = sum(len(ids) for ids in mapping.values())
    _require(
        appearance_count == EXPECTED_ORIGIN_SOURCE_APPEARANCE_COUNT,
        f"origin-source appearance count is {appearance_count}, expected 41684",
    )
    mapped_ids = {source_id for ids in mapping.values() for source_id in ids}
    _require(mapped_ids == set(source_by_id), "mapped source-id union does not equal the source-table id set")

    _require(r2a_protocol.get("checkpoint") == "FMD-07A-R2A", "R2A protocol checkpoint mismatch")
    feature_names = r2a_protocol.get("eligible_predictor_features")
    _require(isinstance(feature_names, list), "R2A protocol feature list is absent")
    _require(len(feature_names) == EXPECTED_FEATURE_COUNT, "R2A protocol does not contain 47 features")
    _require(len(set(feature_names)) == EXPECTED_FEATURE_COUNT, "R2A protocol feature list contains duplicates")
    _require(r2a_protocol.get("numeric_aggregation_rule") == NUMERIC_AGGREGATION_RULE, "R2A numeric rule mismatch")
    _require(r2a_protocol.get("held_out_outcomes_used") is False, "R2A protocol reports held-out use")
    _require(r2a_protocol.get("sri_lanka_outcomes_used") is False, "R2A protocol reports Sri Lanka use")
    _require(r2a_protocol.get("model_trained") is False, "R2A protocol reports model training")
    _validate_available_values(source_rows, feature_names)

    return {
        "source_rows": source_rows,
        "source_by_id": source_by_id,
        "source_fieldnames": source_fieldnames,
        "origin_source_map": origin_source_map,
        "feature_names": feature_names,
        "input_sha256": {name: sha256_file(path) for name, path in sorted(paths.items())},
        "appearance_count": appearance_count,
    }


def build_origin_predictor_rows(
    source_rows: list[dict],
    origin_to_source_ids: dict[str, list[str]],
    feature_names: list[str],
) -> tuple[list[dict], list[dict]]:
    """Build predictors without accepting labels, outcomes, or matrix rows."""
    source_by_id = _unique_by(source_rows, "source_id", artifact="source_rows")
    _validate_available_values(source_rows, feature_names)

    mapped_ids = {source_id for ids in origin_to_source_ids.values() for source_id in ids}
    _require(mapped_ids <= set(source_by_id), "origin map references a source absent from source_rows")

    predictor_rows: list[dict] = []
    audit_rows: list[dict] = []
    for origin_id in sorted(origin_to_source_ids):
        source_records = [source_by_id[source_id] for source_id in origin_to_source_ids[origin_id]]
        result = build_origin_feature_row_from_source_features(origin_id, source_records, feature_names)
        predictor_rows.append(result["row"])
        for feature_name in feature_names:
            audit = result["audit"][feature_name]
            audit_rows.append(
                {
                    "forecast_origin_id": origin_id,
                    "feature_name": feature_name,
                    "total_source_count": audit["total_source_count"],
                    "valid_source_count": audit["valid_source_count"],
                    "invalid_source_count": audit["invalid_source_count"],
                    "valid_source_fraction": (
                        audit["valid_source_fraction"]
                        if audit["valid_source_fraction"] is not None
                        else ""
                    ),
                    "underlying_status_counts_json": json.dumps(
                        audit["underlying_status_counts"],
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )
    return predictor_rows, audit_rows


def load_and_validate_join_inputs(
    model_dev_dir: str | Path,
    feature_names: list[str],
    predictor_origin_ids: set[str],
) -> dict:
    """Read the label-bearing scaffold only after predictors already exist."""
    base = Path(model_dev_dir)
    paths = {
        SCHEMA_MATRIX_FILENAME: base / SCHEMA_MATRIX_FILENAME,
        MODEL_INPUT_SCHEMA_FILENAME: base / MODEL_INPUT_SCHEMA_FILENAME,
        FMD07A_PROVENANCE_FILENAME: base / FMD07A_PROVENANCE_FILENAME,
    }
    for name, path in paths.items():
        _require(path.is_file(), f"required join input {name} does not exist")

    scaffold_rows, scaffold_fieldnames = _read_csv(paths[SCHEMA_MATRIX_FILENAME])
    schema = _read_json(paths[MODEL_INPUT_SCHEMA_FILENAME])
    provenance = _read_json(paths[FMD07A_PROVENANCE_FILENAME])

    recorded_matrix_hash = provenance.get("artifact_sha256", {}).get(SCHEMA_MATRIX_FILENAME)
    _require(
        sha256_file(paths[SCHEMA_MATRIX_FILENAME]) == recorded_matrix_hash,
        "schema-freeze matrix SHA-256 does not match fmd07a_provenance.json",
    )
    predictor_columns = schema.get("predictor_columns_ordered")
    _require(isinstance(predictor_columns, list), "model-input schema predictor column list is absent")
    expected_predictor_columns = [column for feature in feature_names for column in (f"{feature}_value", f"{feature}_status")]
    _require(predictor_columns == expected_predictor_columns, "model-input schema and R2A feature order differ")
    expected_fieldnames = matrix_fieldnames(feature_names)
    _require(scaffold_fieldnames == expected_fieldnames, "schema-freeze matrix field order has drifted")
    _require(len(scaffold_fieldnames) == EXPECTED_MATRIX_COLUMN_COUNT, "schema-freeze matrix does not have 105 fields")
    _require(len(scaffold_rows) == EXPECTED_ORIGIN_COUNT, "schema-freeze matrix does not have 3761 rows")
    scaffold_by_id = _unique_by(scaffold_rows, "forecast_origin_id", artifact=SCHEMA_MATRIX_FILENAME)
    _require(set(scaffold_by_id) == predictor_origin_ids, "predictor and scaffold origin-id sets differ")
    _require(
        [row["forecast_origin_id"] for row in scaffold_rows] == sorted(scaffold_by_id),
        "schema-freeze matrix is not ordered by forecast_origin_id",
    )
    _require(
        all(row.get("model_fitting_role") == FIT_DEVELOPMENT for row in scaffold_rows),
        "schema-freeze matrix contains a non-FIT_DEVELOPMENT role",
    )
    _require(
        all(row.get("country") != "Sri Lanka" for row in scaffold_rows),
        "schema-freeze matrix contains a Sri Lanka row",
    )

    return {
        "scaffold_rows": scaffold_rows,
        "scaffold_fieldnames": scaffold_fieldnames,
        "predictor_columns": predictor_columns,
        "input_sha256": {name: sha256_file(path) for name, path in sorted(paths.items())},
    }


def join_predictors_to_scaffold(
    predictor_rows: list[dict],
    scaffold_rows: list[dict],
    fieldnames: list[str],
    predictor_columns: list[str],
) -> list[dict]:
    predictor_by_id = _unique_by(predictor_rows, "forecast_origin_id", artifact="predictor_rows")
    scaffold_by_id = _unique_by(scaffold_rows, "forecast_origin_id", artifact="scaffold_rows")
    _require(set(predictor_by_id) == set(scaffold_by_id), "predictor/scaffold origin-id sets differ")

    non_predictor_columns = [name for name in fieldnames if name not in predictor_columns]
    expected_non_predictors = (
        list(IDENTIFIER_COLUMNS)
        + list(METADATA_COLUMNS)
        + [TARGET_COLUMN]
        + list(NON_PREDICTOR_AUDIT_ONLY_COLUMNS)
    )
    _require(non_predictor_columns == expected_non_predictors, "non-predictor schema has drifted")

    rows: list[dict] = []
    for origin_id in sorted(predictor_by_id):
        scaffold = scaffold_by_id[origin_id]
        _require(scaffold.get("model_fitting_role") == FIT_DEVELOPMENT, f"origin {origin_id} is not FIT_DEVELOPMENT")
        _require(scaffold.get("country") != "Sri Lanka", f"origin {origin_id} is a Sri Lanka row")
        predictor = predictor_by_id[origin_id]
        _require(
            set(predictor) == {"forecast_origin_id", *predictor_columns},
            f"origin {origin_id} predictor row contains a forbidden or missing field",
        )
        row = {name: scaffold[name] for name in non_predictor_columns}
        row.update({name: predictor[name] for name in predictor_columns})
        rows.append({name: row[name] for name in fieldnames})
    return rows


def _validate_built_outputs(
    matrix_rows: list[dict],
    audit_rows: list[dict],
    scaffold_rows: list[dict],
    fieldnames: list[str],
    predictor_columns: list[str],
    feature_names: list[str],
) -> dict:
    _require(len(matrix_rows) == EXPECTED_ORIGIN_COUNT, "populated matrix does not have 3761 rows")
    matrix_by_id = _unique_by(matrix_rows, "forecast_origin_id", artifact=MATRIX_FILENAME)
    scaffold_by_id = _unique_by(scaffold_rows, "forecast_origin_id", artifact=SCHEMA_MATRIX_FILENAME)
    _require(len(matrix_by_id) == EXPECTED_ORIGIN_COUNT, "populated matrix does not have 3761 unique origins")
    _require([row["forecast_origin_id"] for row in matrix_rows] == sorted(matrix_by_id), "populated matrix is not ordered")
    _require(len(fieldnames) == EXPECTED_MATRIX_COLUMN_COUNT, "populated matrix does not have 105 fields")

    non_predictor_columns = [name for name in fieldnames if name not in predictor_columns]
    for origin_id, row in matrix_by_id.items():
        for column in non_predictor_columns:
            _require(
                row[column] == scaffold_by_id[origin_id][column],
                f"non-predictor {column} changed for {origin_id}",
            )

    _require(len(audit_rows) == EXPECTED_AUDIT_ROW_COUNT, "aggregation audit does not have 176767 rows")
    audit_keys = {(row["forecast_origin_id"], row["feature_name"]) for row in audit_rows}
    _require(len(audit_keys) == EXPECTED_AUDIT_ROW_COUNT, "aggregation audit contains duplicate origin-feature rows")
    expected_audit_order = [
        (origin_id, feature_name)
        for origin_id in sorted(matrix_by_id)
        for feature_name in feature_names
    ]
    _require(
        [(row["forecast_origin_id"], row["feature_name"]) for row in audit_rows] == expected_audit_order,
        "aggregation audit ordering is not deterministic",
    )

    per_feature: dict[str, dict] = {}
    for feature_name in feature_names:
        statuses = Counter(row[f"{feature_name}_status"] for row in matrix_rows)
        blank_values = sum(1 for row in matrix_rows if row[f"{feature_name}_value"] in (None, ""))
        _require("EXTRACTION_NOT_RUN" not in statuses, f"{feature_name} retains EXTRACTION_NOT_RUN")
        per_feature[feature_name] = {
            "status_counts": dict(sorted(statuses.items())),
            "blank_value_count": blank_values,
        }

    audit_by_key = {(row["forecast_origin_id"], row["feature_name"]): row for row in audit_rows}
    for origin_id, matrix_row in matrix_by_id.items():
        for feature_name in feature_names:
            audit = audit_by_key[(origin_id, feature_name)]
            total = int(audit["total_source_count"])
            valid = int(audit["valid_source_count"])
            invalid = int(audit["invalid_source_count"])
            _require(valid + invalid == total, f"audit counts do not reconcile for {origin_id}/{feature_name}")
            expected_status = aggregate_origin_feature_status(total, valid)
            actual_status = matrix_row[f"{feature_name}_status"]
            value = matrix_row[f"{feature_name}_value"]
            _require(actual_status == expected_status, f"matrix/audit status mismatch for {origin_id}/{feature_name}")
            if actual_status in VALUE_PRESENT_STATUSES:
                try:
                    finite = value not in (None, "") and math.isfinite(float(value))
                except (TypeError, ValueError):
                    finite = False
                _require(finite, f"valid aggregate is not finite for {origin_id}/{feature_name}")
            else:
                _require(actual_status in VALUE_BLANK_STATUSES, f"unknown aggregate status {actual_status!r}")
                _require(value in (None, ""), f"missing aggregate carries a value for {origin_id}/{feature_name}")

    return {
        "origin_rows": len(matrix_rows),
        "unique_origin_ids": len(matrix_by_id),
        "duplicate_origin_ids": len(matrix_rows) - len(matrix_by_id),
        "matrix_column_count": len(fieldnames),
        "audit_rows": len(audit_rows),
        "per_feature_output": per_feature,
        "non_predictor_cells_unchanged": True,
        "origin_ordering_deterministic": True,
        "audit_ordering_deterministic": True,
    }


def build_r2b3_once(model_dev_dir: str | Path, out_dir: str | Path) -> dict:
    predictor_inputs = load_and_validate_predictor_inputs(model_dev_dir)
    mapping = predictor_inputs["origin_source_map"]["origin_to_source_ids"]
    feature_names = predictor_inputs["feature_names"]
    predictor_rows, audit_rows = build_origin_predictor_rows(
        predictor_inputs["source_rows"],
        mapping,
        feature_names,
    )

    predictor_origin_ids = {row["forecast_origin_id"] for row in predictor_rows}
    join_inputs = load_and_validate_join_inputs(model_dev_dir, feature_names, predictor_origin_ids)
    matrix_rows = join_predictors_to_scaffold(
        predictor_rows,
        join_inputs["scaffold_rows"],
        join_inputs["scaffold_fieldnames"],
        join_inputs["predictor_columns"],
    )
    summary = _validate_built_outputs(
        matrix_rows,
        audit_rows,
        join_inputs["scaffold_rows"],
        join_inputs["scaffold_fieldnames"],
        join_inputs["predictor_columns"],
        feature_names,
    )

    output = Path(out_dir)
    matrix_path = output / MATRIX_FILENAME
    audit_path = output / AUDIT_FILENAME
    _atomic_write_csv(matrix_path, matrix_rows, join_inputs["scaffold_fieldnames"])
    _atomic_write_csv(audit_path, audit_rows, AUDIT_FIELDNAMES)

    return {
        "matrix_path": matrix_path,
        "audit_path": audit_path,
        "matrix_sha256": sha256_file(matrix_path),
        "audit_sha256": sha256_file(audit_path),
        "input_sha256": predictor_inputs["input_sha256"] | join_inputs["input_sha256"],
        "feature_names": feature_names,
        "source_mapping_checkpoint": predictor_inputs["origin_source_map"]["checkpoint"],
        "source_mapping_appearance_count": predictor_inputs["appearance_count"],
        "summary": summary,
    }


def run_fmd07a_r2b3(model_dev_dir: str | Path) -> dict:
    """Build twice offline, require byte identity, then publish atomically."""
    output = Path(model_dev_dir)
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".fmd07a_r2b3_run1_", dir=output) as run1_dir:
        run1 = build_r2b3_once(output, run1_dir)
        with tempfile.TemporaryDirectory(prefix=".fmd07a_r2b3_run2_", dir=output) as run2_dir:
            run2 = build_r2b3_once(output, run2_dir)

            _require(run1["input_sha256"] == run2["input_sha256"], "independent builds read different input hashes")
            _require(run1["summary"] == run2["summary"], "independent build summaries differ")
            _require(run1["matrix_sha256"] == run2["matrix_sha256"], "independent matrix SHA-256 values differ")
            _require(run1["audit_sha256"] == run2["audit_sha256"], "independent audit SHA-256 values differ")
            _require(run1["matrix_path"].read_bytes() == run2["matrix_path"].read_bytes(), "independent matrix bytes differ")
            _require(run1["audit_path"].read_bytes() == run2["audit_path"].read_bytes(), "independent audit bytes differ")

            canonical_matrix = output / MATRIX_FILENAME
            canonical_audit = output / AUDIT_FILENAME
            _atomic_copy_bytes(run1["matrix_path"], canonical_matrix)
            _atomic_copy_bytes(run1["audit_path"], canonical_audit)

    summary = run1["summary"]
    manifest = {
        "checkpoint": CHECKPOINT,
        "contract_status": CONTRACT_STATUS,
        "purpose": "OFFLINE_FIT_DEVELOPMENT_SOURCE_TO_ORIGIN_MATRIX_POPULATION",
        "primary_row_unit": "FORECAST_ORIGIN",
        "aggregation_rule": NUMERIC_AGGREGATION_RULE,
        "source_mapping_reused": True,
        "source_mapping_provenance": {
            "artifact": ORIGIN_SOURCE_MAP_FILENAME,
            "checkpoint": run1["source_mapping_checkpoint"],
            "origin_source_appearance_count": run1["source_mapping_appearance_count"],
            "unique_source_count": EXPECTED_SOURCE_COUNT,
        },
        "input_artifact_sha256": run1["input_sha256"],
        "output_artifact_sha256": {
            MATRIX_FILENAME: sha256_file(canonical_matrix),
            AUDIT_FILENAME: sha256_file(canonical_audit),
        },
        "origin_rows": summary["origin_rows"],
        "unique_origin_ids": summary["unique_origin_ids"],
        "duplicate_origin_ids": summary["duplicate_origin_ids"],
        "source_rows": EXPECTED_SOURCE_COUNT,
        "unique_source_ids": EXPECTED_SOURCE_COUNT,
        "origin_source_appearance_count": run1["source_mapping_appearance_count"],
        "eligible_predictor_feature_count": len(run1["feature_names"]),
        "matrix_column_count": summary["matrix_column_count"],
        "aggregation_audit_row_count": summary["audit_rows"],
        "per_feature_output": summary["per_feature_output"],
        "non_predictor_cells_unchanged": summary["non_predictor_cells_unchanged"],
        "deterministic_ordering": {
            "origin_order": "LEXICAL_FORECAST_ORIGIN_ID",
            "source_sum_order": "LEXICAL_SOURCE_ID",
            "feature_order": "FROZEN_R2A_PROTOCOL_ORDER",
            "matrix_columns": "FROZEN_FMD07A_SCHEMA_ORDER",
            "origin_ordering_verified": summary["origin_ordering_deterministic"],
            "audit_ordering_verified": summary["audit_ordering_deterministic"],
        },
        "determinism": {
            "run1_matrix_sha256": run1["matrix_sha256"],
            "run2_matrix_sha256": run2["matrix_sha256"],
            "matrix_sha_match": run1["matrix_sha256"] == run2["matrix_sha256"],
            "run1_audit_sha256": run1["audit_sha256"],
            "run2_audit_sha256": run2["audit_sha256"],
            "audit_sha_match": run1["audit_sha256"] == run2["audit_sha256"],
            "independent_offline_builds": 2,
        },
        "network_used": False,
        "held_out_used": False,
        "sri_lanka_used": False,
        "labels_used_for_predictor_construction": False,
        "predictive_outcomes_used": False,
        "imputation_applied": False,
        "model_trained": False,
        "predictive_metrics_computed": False,
        "completion_token_when_test_gates_pass": COMPLETION_TOKEN,
        "next_checkpoint": NEXT_CHECKPOINT,
    }
    manifest_path = output / MANIFEST_FILENAME
    _atomic_write_json(manifest_path, manifest)

    return {
        "matrix_path": str(canonical_matrix),
        "audit_path": str(canonical_audit),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
    }

