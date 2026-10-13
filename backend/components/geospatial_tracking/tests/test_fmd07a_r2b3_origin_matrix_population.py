"""Focused offline gate for FMD-07A-R2B3 origin-matrix population."""

from __future__ import annotations

import csv
import inspect
import json
import shutil
from pathlib import Path

import pytest

from components.geospatial_tracking.services import fmd_model_development_r2b3 as m
from components.geospatial_tracking.services.fmd_model_development import (
    IDENTIFIER_COLUMNS,
    METADATA_COLUMNS,
    NON_PREDICTOR_AUDIT_ONLY_COLUMNS,
    TARGET_COLUMN,
)
from components.geospatial_tracking.services.fmd_model_development_r2a import (
    NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0,
    ORIGIN_AGGREGATE_ALL_VALID,
    ORIGIN_AGGREGATE_NO_VALID_VALUE,
    ORIGIN_AGGREGATE_PARTIAL_VALID,
)
from components.geospatial_tracking.services.model_fitting_exposure import (
    FIT_DEVELOPMENT,
    HELD_OUT_FROM_MODEL_FITTING,
    SRI_LANKA_TRANSFER_CASE_STUDY,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_MODEL_DEV_DIR = _REPO_ROOT / "local_data/processed/fmd/model_development"

_ALL_INPUT_FILENAMES = [
    m.SOURCE_TABLE_FILENAME,
    m.R2B2_MANIFEST_FILENAME,
    m.R2B2_PROGRESS_FILENAME,
    m.R2B2_FAILURE_LEDGER_FILENAME,
    m.ORIGIN_SOURCE_MAP_FILENAME,
    m.UNIQUE_SOURCE_INDEX_FILENAME,
    m.R2A_PROTOCOL_FILENAME,
    m.SCHEMA_MATRIX_FILENAME,
    m.MODEL_INPUT_SCHEMA_FILENAME,
    m.FMD07A_PROVENANCE_FILENAME,
]


def _csv_rows(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _scaffold(origin_id: str, *, country: str = "Example", role: str = FIT_DEVELOPMENT, label: str = "0") -> dict:
    row = {
        "forecast_origin_id": origin_id,
        "country": country,
        "t0": "2025-01-01",
        "model_fitting_role": role,
        "risk_target_label": label,
    }
    for field in NON_PREDICTOR_AUDIT_ONLY_COLUMNS:
        row[field] = f"audit:{field}"
    return row


@pytest.fixture(scope="module")
def real_r2b3_run(tmp_path_factory):
    work_dir = tmp_path_factory.mktemp("r2b3_real")
    for filename in _ALL_INPUT_FILENAMES:
        shutil.copyfile(_MODEL_DEV_DIR / filename, work_dir / filename)

    upstream_hashes_before = {name: m.sha256_file(work_dir / name) for name in _ALL_INPUT_FILENAMES}
    result = m.run_fmd07a_r2b3(work_dir)
    upstream_hashes_after = {name: m.sha256_file(work_dir / name) for name in _ALL_INPUT_FILENAMES}
    return {
        "work_dir": work_dir,
        "result": result,
        "upstream_hashes_before": upstream_hashes_before,
        "upstream_hashes_after": upstream_hashes_after,
    }


def test_r2b3_reuses_r2a_and_has_no_extraction_or_model_path():
    module_source = inspect.getsource(m)
    predictor_source = inspect.getsource(m.build_origin_predictor_rows)
    assert "build_origin_feature_row_from_source_features(" in predictor_source
    assert "risk_target_label" not in predictor_source
    assert "local_domain_positive" not in predictor_source
    assert "import requests" not in module_source
    assert "run_full_r2b2_extraction" not in module_source
    assert "extract_source_features" not in module_source
    assert "sklearn" not in module_source
    assert "fit(" not in module_source
    assert "predict(" not in module_source


def test_r2b3_inherited_aggregation_all_partial_none_zero_and_dedup():
    rows = [
        {"source_id": "s1", "x_value": "2.0", "x_status": "SOURCE_VALUE_AVAILABLE"},
        {"source_id": "s2", "x_value": "4.0", "x_status": "SOURCE_VALUE_AVAILABLE"},
        {"source_id": "s3", "x_value": "", "x_status": "EXTRACTION_FAILED"},
    ]
    mapping = {
        "ORIGIN:ALL": ["s2", "s1", "s1"],
        "ORIGIN:NONE": ["s3"],
        "ORIGIN:PARTIAL": ["s3", "s1"],
        "ORIGIN:ZERO": [],
    }
    predictors, audit = m.build_origin_predictor_rows(rows, mapping, ["x"])
    by_id = {row["forecast_origin_id"]: row for row in predictors}
    audit_by_id = {row["forecast_origin_id"]: row for row in audit}

    assert [row["forecast_origin_id"] for row in predictors] == sorted(mapping)
    assert by_id["ORIGIN:ALL"]["x_value"] == 3.0
    assert by_id["ORIGIN:ALL"]["x_status"] == ORIGIN_AGGREGATE_ALL_VALID
    assert audit_by_id["ORIGIN:ALL"]["total_source_count"] == 2
    assert audit_by_id["ORIGIN:ALL"]["valid_source_count"] == 2

    assert by_id["ORIGIN:PARTIAL"]["x_value"] == 2.0
    assert by_id["ORIGIN:PARTIAL"]["x_status"] == ORIGIN_AGGREGATE_PARTIAL_VALID
    assert audit_by_id["ORIGIN:PARTIAL"]["valid_source_count"] == 1
    assert audit_by_id["ORIGIN:PARTIAL"]["invalid_source_count"] == 1

    assert by_id["ORIGIN:NONE"]["x_value"] == ""
    assert by_id["ORIGIN:NONE"]["x_status"] == ORIGIN_AGGREGATE_NO_VALID_VALUE
    assert by_id["ORIGIN:ZERO"]["x_value"] == ""
    assert by_id["ORIGIN:ZERO"]["x_status"] == NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0


@pytest.mark.parametrize("bad_value", ["", "nan", "inf", "-inf", "not-a-number"])
def test_r2b3_rejects_available_status_without_finite_numeric_value(bad_value):
    rows = [{"source_id": "s1", "x_value": bad_value, "x_status": "SOURCE_VALUE_AVAILABLE"}]
    with pytest.raises(ValueError, match="without a finite numeric value"):
        m.build_origin_predictor_rows(rows, {"ORIGIN:1": ["s1"]}, ["x"])


def test_r2b3_predictor_construction_is_label_independent():
    base = {"source_id": "s1", "x_value": "7.5", "x_status": "SOURCE_VALUE_AVAILABLE"}
    row_a = dict(base, risk_target_label="0", local_domain_positive="False")
    row_b = dict(base, risk_target_label="1", local_domain_positive="True")
    predictors_a, audit_a = m.build_origin_predictor_rows([row_a], {"ORIGIN:1": ["s1"]}, ["x"])
    predictors_b, audit_b = m.build_origin_predictor_rows([row_b], {"ORIGIN:1": ["s1"]}, ["x"])
    assert predictors_a == predictors_b
    assert audit_a == audit_b


def test_r2b3_join_preserves_non_predictors_but_never_uses_them_for_predictors():
    predictor_columns = ["x_value", "x_status"]
    fieldnames = (
        list(IDENTIFIER_COLUMNS)
        + list(METADATA_COLUMNS)
        + [TARGET_COLUMN]
        + list(NON_PREDICTOR_AUDIT_ONLY_COLUMNS)
        + predictor_columns
    )
    predictor = [{"forecast_origin_id": "ORIGIN:1", "x_value": 7.5, "x_status": ORIGIN_AGGREGATE_ALL_VALID}]
    scaffold_zero = [_scaffold("ORIGIN:1", label="0")]
    scaffold_one = [_scaffold("ORIGIN:1", label="1")]
    joined_zero = m.join_predictors_to_scaffold(predictor, scaffold_zero, fieldnames, predictor_columns)
    joined_one = m.join_predictors_to_scaffold(predictor, scaffold_one, fieldnames, predictor_columns)
    assert joined_zero[0]["risk_target_label"] == "0"
    assert joined_one[0]["risk_target_label"] == "1"
    assert joined_zero[0]["x_value"] == joined_one[0]["x_value"] == 7.5
    assert joined_zero[0]["x_status"] == joined_one[0]["x_status"] == ORIGIN_AGGREGATE_ALL_VALID


@pytest.mark.parametrize(
    ("country", "role"),
    [
        ("Example", HELD_OUT_FROM_MODEL_FITTING),
        ("Sri Lanka", SRI_LANKA_TRANSFER_CASE_STUDY),
    ],
)
def test_r2b3_join_rejects_held_out_and_sri_lanka(country, role):
    predictor_columns = ["x_value", "x_status"]
    fieldnames = (
        list(IDENTIFIER_COLUMNS)
        + list(METADATA_COLUMNS)
        + [TARGET_COLUMN]
        + list(NON_PREDICTOR_AUDIT_ONLY_COLUMNS)
        + predictor_columns
    )
    predictor = [{"forecast_origin_id": "ORIGIN:1", "x_value": 1.0, "x_status": ORIGIN_AGGREGATE_ALL_VALID}]
    with pytest.raises(ValueError, match="not FIT_DEVELOPMENT"):
        m.join_predictors_to_scaffold(
            predictor,
            [_scaffold("ORIGIN:1", country=country, role=role)],
            fieldnames,
            predictor_columns,
        )


def test_r2b3_rejects_upstream_hash_drift(tmp_path):
    for filename in [
        m.SOURCE_TABLE_FILENAME,
        m.R2B2_MANIFEST_FILENAME,
        m.R2B2_PROGRESS_FILENAME,
        m.R2B2_FAILURE_LEDGER_FILENAME,
        m.ORIGIN_SOURCE_MAP_FILENAME,
        m.UNIQUE_SOURCE_INDEX_FILENAME,
        m.R2A_PROTOCOL_FILENAME,
    ]:
        shutil.copyfile(_MODEL_DEV_DIR / filename, tmp_path / filename)
    manifest_path = tmp_path / m.R2B2_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["full_source_table_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="source-table SHA-256"):
        m.load_and_validate_predictor_inputs(tmp_path)


def test_r2b3_real_outputs_have_exact_shape_and_firewalls(real_r2b3_run):
    work_dir = real_r2b3_run["work_dir"]
    manifest = real_r2b3_run["result"]["manifest"]
    matrix_rows, matrix_fields = _csv_rows(work_dir / m.MATRIX_FILENAME)
    audit_rows, audit_fields = _csv_rows(work_dir / m.AUDIT_FILENAME)

    assert len(matrix_rows) == m.EXPECTED_ORIGIN_COUNT == 3761
    assert len({row["forecast_origin_id"] for row in matrix_rows}) == 3761
    assert len(matrix_fields) == m.EXPECTED_MATRIX_COLUMN_COUNT == 105
    assert [row["forecast_origin_id"] for row in matrix_rows] == sorted(row["forecast_origin_id"] for row in matrix_rows)
    assert all(row["model_fitting_role"] == FIT_DEVELOPMENT for row in matrix_rows)
    assert all(row["country"] != "Sri Lanka" for row in matrix_rows)
    assert not any(value == "EXTRACTION_NOT_RUN" for row in matrix_rows for key, value in row.items() if key.endswith("_status"))

    assert audit_fields == m.AUDIT_FIELDNAMES
    assert len(audit_rows) == m.EXPECTED_AUDIT_ROW_COUNT == 176767
    assert len({(row["forecast_origin_id"], row["feature_name"]) for row in audit_rows}) == 176767

    assert manifest["checkpoint"] == m.CHECKPOINT
    assert manifest["origin_rows"] == 3761
    assert manifest["unique_origin_ids"] == 3761
    assert manifest["duplicate_origin_ids"] == 0
    assert manifest["network_used"] is False
    assert manifest["held_out_used"] is False
    assert manifest["sri_lanka_used"] is False
    assert manifest["labels_used_for_predictor_construction"] is False
    assert manifest["predictive_outcomes_used"] is False
    assert manifest["imputation_applied"] is False
    assert manifest["model_trained"] is False
    assert manifest["predictive_metrics_computed"] is False


def test_r2b3_real_join_preserves_every_non_predictor_cell(real_r2b3_run):
    work_dir = real_r2b3_run["work_dir"]
    matrix_rows, _ = _csv_rows(work_dir / m.MATRIX_FILENAME)
    scaffold_rows, _ = _csv_rows(work_dir / m.SCHEMA_MATRIX_FILENAME)
    matrix_by_id = {row["forecast_origin_id"]: row for row in matrix_rows}
    non_predictors = (
        list(IDENTIFIER_COLUMNS)
        + list(METADATA_COLUMNS)
        + [TARGET_COLUMN]
        + list(NON_PREDICTOR_AUDIT_ONLY_COLUMNS)
    )
    for scaffold in scaffold_rows:
        populated = matrix_by_id[scaffold["forecast_origin_id"]]
        assert {field: populated[field] for field in non_predictors} == {
            field: scaffold[field] for field in non_predictors
        }


def test_r2b3_two_independent_real_builds_are_sha_identical(real_r2b3_run):
    manifest = real_r2b3_run["result"]["manifest"]
    determinism = manifest["determinism"]
    assert determinism["independent_offline_builds"] == 2
    assert determinism["matrix_sha_match"] is True
    assert determinism["audit_sha_match"] is True
    assert determinism["run1_matrix_sha256"] == determinism["run2_matrix_sha256"]
    assert determinism["run1_audit_sha256"] == determinism["run2_audit_sha256"]
    assert manifest["output_artifact_sha256"][m.MATRIX_FILENAME] == m.sha256_file(
        real_r2b3_run["work_dir"] / m.MATRIX_FILENAME
    )
    assert manifest["output_artifact_sha256"][m.AUDIT_FILENAME] == m.sha256_file(
        real_r2b3_run["work_dir"] / m.AUDIT_FILENAME
    )


def test_r2b3_real_run_does_not_mutate_any_upstream_artifact(real_r2b3_run):
    assert real_r2b3_run["upstream_hashes_before"] == real_r2b3_run["upstream_hashes_after"]

