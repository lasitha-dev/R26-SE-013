"""FMD-07A: leakage-safe development feature matrix, model-development
protocol audit, and pre-training freeze."""

from __future__ import annotations

import csv
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from components.geospatial_tracking.services.fmd_calibration import (
    FMD_DISEASE,
    FMD_MODEL_FITTING_CUTOFF,
    FMD_SPATIAL_EVALUATION_RADIUS_KM,
    SPATIAL_PROTOCOL_AMENDMENT_STATUS,
    SPATIAL_REFERENCE_SOURCE_SET,
)
from components.geospatial_tracking.services.fmd_model_development import (
    NON_PREDICTOR_AUDIT_ONLY_COLUMNS,
    PROHIBITED_PREDICTOR_SUBSTRINGS,
    TARGET_COLUMN,
    audit_predictor_columns_for_leakage,
    build_fmd07a_development_feature_matrix,
    build_fmd07a_development_protocol_freeze,
    build_fmd07a_feature_matrix_audit,
    build_fmd07a_model_input_schema,
    derive_eligible_predictor_features,
    matrix_fieldnames,
    predictor_columns,
    run_fmd07a,
    verify_fmd07a_cv_folds,
)
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.model_fitting_exposure import (
    FIT_DEVELOPMENT,
    HELD_OUT_FROM_MODEL_FITTING,
    SRI_LANKA_TRANSFER_CASE_STUDY,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_COHORT_DIR = _REPO_ROOT / "local_data/processed/fmd/cohort"
_CALIBRATION_DIR = _REPO_ROOT / "local_data/processed/fmd/calibration"
_FEATURES_DIR = _REPO_ROOT / "local_data/processed/fmd/features"
_MODEL_DEV_DIR = _REPO_ROOT / "local_data/processed/fmd/model_development"
_PROTOCOL_DIR = _REPO_ROOT / "backend/components/geospatial_tracking"

_ORIGINS_CSV = _COHORT_DIR / "fmd_historical_forecast_origins.csv"
_RISK_LABELS_CSV = _CALIBRATION_DIR / "fmd06_risk_origin_labels.csv"
_FEATURE_ELIGIBILITY_CSV = _PROTOCOL_DIR / "FMD_FEATURE_ELIGIBILITY.csv"
_FEATURE_TABLE_CSV = _FEATURES_DIR / "fmd_feature_table.csv"
_EXPERIMENT_REGISTRY_JSON = _PROTOCOL_DIR / "FMD_EXPERIMENT_REGISTRY.json"
_CALENDAR_FOLDS_JSON = _COHORT_DIR / "fmd_calendar_year_folds.json"
_EXPOSURE_MANIFEST_CSV = _COHORT_DIR / "fmd_model_fitting_exposure_manifest.csv"

_MATRIX_CSV = _MODEL_DEV_DIR / "fmd07_development_feature_matrix.csv"
_AUDIT_JSON = _MODEL_DEV_DIR / "fmd07_feature_matrix_audit.json"
_SCHEMA_JSON = _MODEL_DEV_DIR / "fmd07_model_input_schema.json"
_PROTOCOL_JSON = _MODEL_DEV_DIR / "fmd07_development_protocol.json"
_CALIBRATION_FREEZE_JSON = _CALIBRATION_DIR / "fmd06_calibration_freeze.json"
_FMD06_MANIFEST_JSON = _CALIBRATION_DIR / "fmd06_calibration_manifest.json"


def _csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _origin(**overrides) -> ForecastOrigin:
    fields = {
        "forecast_origin_id": "ORIGIN:Example:2025-06-10",
        "country": "Example",
        "t0": "2025-06-10",
        "temporal_mode": "RETROSPECTIVE_PROXY",
        "trigger_source_ids_at_t0": ["AT_T0"],
        "trigger_source_count": 1,
    }
    fields.update(overrides)
    return ForecastOrigin(**fields)


def _run(out_dir: Path) -> dict:
    return run_fmd07a(
        _ORIGINS_CSV, _RISK_LABELS_CSV, _FEATURE_ELIGIBILITY_CSV, _FEATURE_TABLE_CSV,
        _EXPERIMENT_REGISTRY_JSON, _CALENDAR_FOLDS_JSON, _EXPOSURE_MANIFEST_CSV, out_dir,
    )


# ---------------------------------------------------------------------------
# 1-4: shape / role invariants
# ---------------------------------------------------------------------------


def test_fmd07a_1_matrix_row_count_is_3761():
    rows = _csv_rows(_MATRIX_CSV)
    assert len(rows) == 3761


def test_fmd07a_2_forecast_origin_id_is_unique():
    rows = _csv_rows(_MATRIX_CSV)
    ids = [row["forecast_origin_id"] for row in rows]
    assert len(ids) == len(set(ids))


def test_fmd07a_3_exactly_one_row_per_forecast_origin():
    rows = _csv_rows(_MATRIX_CSV)
    label_rows = _csv_rows(_RISK_LABELS_CSV)
    assert {r["forecast_origin_id"] for r in rows} == {r["forecast_origin_id"] for r in label_rows}
    assert len(rows) == len(label_rows) == 3761


def test_fmd07a_4_all_rows_are_fit_development():
    rows = _csv_rows(_MATRIX_CSV)
    assert {row["model_fitting_role"] for row in rows} == {FIT_DEVELOPMENT}


# ---------------------------------------------------------------------------
# 5-6: held-out / Sri Lanka firewall
# ---------------------------------------------------------------------------


def test_fmd07a_5_held_out_origins_are_rejected():
    held_out = _origin(forecast_origin_id="HELD", t0=FMD_MODEL_FITTING_CUTOFF)
    label_row = {
        "forecast_origin_id": "HELD", "country": "Example", "t0": FMD_MODEL_FITTING_CUTOFF,
        "model_fitting_role": FIT_DEVELOPMENT, "risk_target_label": "0",
        "has_eligible_d1_d7_target": "False", "outside_domain_target_present": "False",
        "local_evaluation_radius_km": "200.0", "target_horizon": "D1-D7",
        "spatial_reference_source_set": "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0",
        "spatial_protocol_amendment_status": "POST_FEASIBILITY_PROTOCOL_AMENDMENT",
    }
    with pytest.raises(ValueError, match=HELD_OUT_FROM_MODEL_FITTING):
        build_fmd07a_development_feature_matrix([held_out], [label_row], [])


def test_fmd07a_6_sri_lanka_origins_are_rejected():
    sri_lanka = _origin(forecast_origin_id="SL", country="Sri Lanka")
    label_row = {
        "forecast_origin_id": "SL", "country": "Sri Lanka", "t0": "2025-06-10",
        "model_fitting_role": FIT_DEVELOPMENT, "risk_target_label": "0",
        "has_eligible_d1_d7_target": "False", "outside_domain_target_present": "False",
        "local_evaluation_radius_km": "200.0", "target_horizon": "D1-D7",
        "spatial_reference_source_set": "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0",
        "spatial_protocol_amendment_status": "POST_FEASIBILITY_PROTOCOL_AMENDMENT",
    }
    with pytest.raises(ValueError, match=SRI_LANKA_TRANSFER_CASE_STUDY):
        build_fmd07a_development_feature_matrix([sri_lanka], [label_row], [])


def test_fmd07a_6b_no_feature_rows_generated_for_rejected_roles():
    # the matrix must never even be attempted for held-out/Sri-Lanka --
    # confirmed by the ValueError firing before any row is returned.
    held_out = _origin(forecast_origin_id="HELD", t0=FMD_MODEL_FITTING_CUTOFF)
    label_row = {
        "forecast_origin_id": "HELD", "country": "Example", "t0": FMD_MODEL_FITTING_CUTOFF,
        "model_fitting_role": FIT_DEVELOPMENT, "risk_target_label": "0",
        "has_eligible_d1_d7_target": "False", "outside_domain_target_present": "False",
        "local_evaluation_radius_km": "200.0", "target_horizon": "D1-D7",
        "spatial_reference_source_set": "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0",
        "spatial_protocol_amendment_status": "POST_FEASIBILITY_PROTOCOL_AMENDMENT",
    }
    try:
        build_fmd07a_development_feature_matrix([held_out], [label_row], [])
        raised = False
    except ValueError:
        raised = True
    assert raised


# ---------------------------------------------------------------------------
# 7-8: label reconciliation
# ---------------------------------------------------------------------------


def test_fmd07a_7_label_counts_remain_2215_1546():
    rows = _csv_rows(_MATRIX_CSV)
    positive = sum(1 for row in rows if row["risk_target_label"] == "1")
    negative = sum(1 for row in rows if row["risk_target_label"] == "0")
    assert positive == 2215
    assert negative == 1546
    assert positive + negative == 3761


def test_fmd07a_8_label_values_exactly_match_fmd06_label_artifact():
    matrix_by_id = {row["forecast_origin_id"]: row for row in _csv_rows(_MATRIX_CSV)}
    for label_row in _csv_rows(_RISK_LABELS_CSV):
        matrix_row = matrix_by_id[label_row["forecast_origin_id"]]
        assert matrix_row["risk_target_label"] == label_row["risk_target_label"]
        assert matrix_row["country"] == label_row["country"]
        assert matrix_row["t0"] == label_row["t0"]
        assert matrix_row["audit_only_has_eligible_d1_d7_target"] == label_row["has_eligible_d1_d7_target"]
        assert matrix_row["audit_only_outside_domain_target_present"] == label_row["outside_domain_target_present"]


# ---------------------------------------------------------------------------
# 9: repeated-target semantics
# ---------------------------------------------------------------------------


def test_fmd07a_9_no_target_appearance_becomes_a_model_row():
    rows = _csv_rows(_MATRIX_CSV)
    distance_rows = _csv_rows(_CALIBRATION_DIR / "fmd06_spatial_target_distance_audit.csv")
    assert len(rows) == 3761
    assert len(distance_rows) == 17965
    assert len(rows) != len(distance_rows)
    unique_events = len({row["target_event_id"] for row in distance_rows})
    assert unique_events == 4906
    assert len(rows) != unique_events


# ---------------------------------------------------------------------------
# 10-13: predictor leakage exclusions
# ---------------------------------------------------------------------------


def test_fmd07a_10_predictor_list_excludes_target_label():
    audit = json.loads(_AUDIT_JSON.read_text(encoding="utf-8"))
    predictor_names = set(audit["predictor_feature_names"])
    assert TARGET_COLUMN not in predictor_names
    assert not any("risk_target_label" in f"{name}_value" for name in predictor_names)


@pytest.mark.parametrize("prohibited", PROHIBITED_PREDICTOR_SUBSTRINGS)
def test_fmd07a_11_12_13_predictor_list_excludes_prohibited_columns(prohibited):
    audit = json.loads(_AUDIT_JSON.read_text(encoding="utf-8"))
    columns = predictor_columns(audit["predictor_feature_names"])
    assert not any(prohibited in column for column in columns)
    assert audit["label_leakage_audit_status"] == "PASS"
    assert audit["label_leakage_violating_columns"] == []


def test_fmd07a_11b_leakage_audit_function_catches_a_deliberately_injected_violation():
    # proves the guard is real, not vacuous -- if a prohibited name WERE
    # present, it would be caught.
    columns = ["weather_event_day_mean_temperature_2m_value", "risk_target_label_leaked_value"]
    result = audit_predictor_columns_for_leakage(columns)
    assert result["predictor_leakage_status"] == "BLOCKED"
    assert "risk_target_label_leaked_value" in result["violating_columns"]


# ---------------------------------------------------------------------------
# 14-16: temporal availability / leakage safety
# ---------------------------------------------------------------------------


def test_fmd07a_14_all_predictors_satisfy_availability_at_t0_rule():
    schema = json.loads(_SCHEMA_JSON.read_text(encoding="utf-8"))
    assert "<= t0" in schema["availability_at_t0_rule"]
    audit = json.loads(_AUDIT_JSON.read_text(encoding="utf-8"))
    assert audit["temporal_availability_validation_result"].startswith("PASS")


def test_fmd07a_15_future_outbreak_does_not_alter_earlier_predictors(tmp_path):
    # predictor assignment has no dependency on other origins' data at all
    # (every value is the constant EXTRACTION_NOT_RUN placeholder) -- proven
    # by building the matrix with an EXTRA future origin present in
    # all_origins (never in the label set) and confirming every existing
    # row's predictor columns are byte-identical.
    eligible, _ = derive_eligible_predictor_features(_FEATURE_TABLE_CSV)
    label_rows = _csv_rows(_RISK_LABELS_CSV)
    from components.geospatial_tracking.services.fmd_calibration import load_forecast_origins
    all_origins = load_forecast_origins(_ORIGINS_CSV)
    baseline = {row["forecast_origin_id"]: row for row in build_fmd07a_development_feature_matrix(all_origins, label_rows, eligible)}

    future_origin = _origin(forecast_origin_id="ORIGIN:Example:2099-01-01", t0="2099-01-01")
    with_future = {
        row["forecast_origin_id"]: row
        for row in build_fmd07a_development_feature_matrix(all_origins + [future_origin], label_rows, eligible)
    }
    for origin_id, row in baseline.items():
        assert with_future[origin_id] == row


def test_fmd07a_16_future_weather_or_label_shuffling_does_not_alter_predictors(tmp_path):
    eligible, _ = derive_eligible_predictor_features(_FEATURE_TABLE_CSV)
    label_rows = _csv_rows(_RISK_LABELS_CSV)
    from components.geospatial_tracking.services.fmd_calibration import load_forecast_origins
    all_origins = load_forecast_origins(_ORIGINS_CSV)
    forward = build_fmd07a_development_feature_matrix(all_origins, label_rows, eligible)
    reversed_rows = build_fmd07a_development_feature_matrix(all_origins, list(reversed(label_rows)), eligible)
    forward_by_id = {r["forecast_origin_id"]: r for r in forward}
    reversed_by_id = {r["forecast_origin_id"]: r for r in reversed_rows}
    assert forward_by_id == reversed_by_id
    # no predictor-assignment code path reads any label/target field at all
    source = inspect.getsource(build_fmd07a_development_feature_matrix)
    assert "risk_target_label" not in source.split("for feature_name in eligible_predictor_features:")[1]


# ---------------------------------------------------------------------------
# 17-19: determinism
# ---------------------------------------------------------------------------


def test_fmd07a_17_18_19_matrix_schema_audit_deterministic_across_rebuilds(tmp_path):
    result1 = _run(tmp_path / "run1")
    result2 = _run(tmp_path / "run2")
    hash1 = {
        "matrix": _sha256(tmp_path / "run1" / "fmd07_development_feature_matrix.csv"),
        "schema": _sha256(tmp_path / "run1" / "fmd07_model_input_schema.json"),
    }
    hash2 = {
        "matrix": _sha256(tmp_path / "run2" / "fmd07_development_feature_matrix.csv"),
        "schema": _sha256(tmp_path / "run2" / "fmd07_model_input_schema.json"),
    }
    assert hash1 == hash2
    audit1 = json.loads((tmp_path / "run1" / "fmd07_feature_matrix_audit.json").read_text(encoding="utf-8"))
    audit2 = json.loads((tmp_path / "run2" / "fmd07_feature_matrix_audit.json").read_text(encoding="utf-8"))
    assert audit1 == audit2


# ---------------------------------------------------------------------------
# 20-24: FMD-06 frozen-value provenance
# ---------------------------------------------------------------------------


def test_fmd07a_20_fmd06_frozen_values_unchanged():
    manifest = json.loads(_FMD06_MANIFEST_JSON.read_text(encoding="utf-8"))
    assert manifest["development_origin_count"] == 3761
    assert manifest["risk_label_row_count"] == 3761
    assert manifest["risk_label_positive_count"] == 2215
    assert manifest["risk_label_negative_count"] == 1546
    assert manifest["active_window_days"] == 14
    assert manifest["stdbscan_eps_space_km"] == 0.236038
    assert manifest["stdbscan_eps_time_days"] == 13.5
    assert manifest["stdbscan_min_core_supports"] == 4
    assert manifest["spatial_reference_source_set"] == "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"


def test_fmd07a_21_original_spatial_no_go_provenance_retained():
    manifest = json.loads(_FMD06_MANIFEST_JSON.read_text(encoding="utf-8"))
    freeze = json.loads(_CALIBRATION_FREEZE_JSON.read_text(encoding="utf-8"))
    assert manifest["original_spatial_domain_status"] == "NO-GO"
    assert manifest["original_spatial_evaluation_radius_km"] is None
    assert freeze["spatial_domain_status"] == "NO-GO"
    assert freeze["spatial_evaluation_radius_km"] is None


def test_fmd07a_22_amendment_provenance_retained():
    manifest = json.loads(_FMD06_MANIFEST_JSON.read_text(encoding="utf-8"))
    assert manifest["spatial_protocol_amendment_status"] == SPATIAL_PROTOCOL_AMENDMENT_STATUS
    assert manifest["amended_spatial_selection_rule"] == "MAXIMUM_PREDECLARED_LOCAL_EVALUATION_DOMAIN"
    assert manifest["amended_spatial_evaluation_radius_km"] == 200.0
    rows = _csv_rows(_MATRIX_CSV)
    assert {row["audit_only_spatial_protocol_amendment_status"] for row in rows} == {SPATIAL_PROTOCOL_AMENDMENT_STATUS}


def test_fmd07a_23_200km_local_domain_value_is_not_a_predictor():
    schema = json.loads(_SCHEMA_JSON.read_text(encoding="utf-8"))
    assert "audit_only_local_evaluation_radius_km" not in schema["predictor_columns_ordered"]
    assert "audit_only_local_evaluation_radius_km" in schema["non_predictor_audit_only_columns"]
    rows = _csv_rows(_MATRIX_CSV)
    assert {row["audit_only_local_evaluation_radius_km"] for row in rows} == {str(FMD_SPATIAL_EVALUATION_RADIUS_KM)}


def test_fmd07a_24_stdbscan_parameters_not_recalibrated():
    protocol = json.loads(_PROTOCOL_JSON.read_text(encoding="utf-8"))
    manifest = json.loads(_FMD06_MANIFEST_JSON.read_text(encoding="utf-8"))
    pistes_entry = protocol["hyperparameter_candidates"]["FMD-EXP-03_pistes_hazard_model"]
    assert "eps_space_km=0.236038" in pistes_entry["definition"]
    assert manifest["stdbscan_eps_space_km"] == 0.236038  # unchanged from FMD-06B-R
    assert manifest["stdbscan_eps_time_days"] == 13.5
    assert manifest["stdbscan_min_core_supports"] == 4


# ---------------------------------------------------------------------------
# 25-28: no fitting/selection happened
# ---------------------------------------------------------------------------


def test_fmd07a_25_weather_window_winner_not_selected():
    protocol = json.loads(_PROTOCOL_JSON.read_text(encoding="utf-8"))
    assert protocol["weather_window_candidates"]["status"] == "CANDIDATES_ONLY_NO_WINNER_SELECTED"
    assert protocol["weather_window_candidates"]["value"] == ["event_day", "window_3day", "window_7day", "window_14day"]


def test_fmd07a_26_27_28_no_model_threshold_or_predictive_metric():
    from components.geospatial_tracking.services import fmd_model_development as m
    for name in ("run_fmd07a", "build_fmd07a_development_feature_matrix", "build_fmd07a_feature_matrix_audit", "build_fmd07a_model_input_schema", "build_fmd07a_development_protocol_freeze"):
        signature = inspect.signature(getattr(m, name))
        assert not {"model", "threshold", "auc", "accuracy", "prauc", "pr_auc", "prediction", "fitted_model"} & set(signature.parameters)
    source = Path(m.__file__).read_text(encoding="utf-8")
    assert "sklearn" not in source
    assert ".fit(" not in source


# ---------------------------------------------------------------------------
# 29-31: pre-existing protocol identification
# ---------------------------------------------------------------------------


def test_fmd07a_29_exact_primary_metric_identified():
    protocol = json.loads(_PROTOCOL_JSON.read_text(encoding="utf-8"))
    assert protocol["primary_selection_metric"]["value"] == "PR-AUC"
    assert "FMD_EVALUATION_PROTOCOL.md" in protocol["primary_selection_metric"]["source"]


def test_fmd07a_30_exact_candidate_model_registry_identified():
    protocol = json.loads(_PROTOCOL_JSON.read_text(encoding="utf-8"))
    families = protocol["candidate_model_families"]
    experiment_ids = {entry["experiment_id"] for entry in families}
    assert experiment_ids == {"FMD-EXP-01", "FMD-EXP-02", "FMD-EXP-03", "FMD-EXP-04", "FMD-EXP-05"}
    assert all(entry["status"] == "NOT_STARTED" for entry in families)


def test_fmd07a_31_exact_cv_purge_embargo_specification_identified():
    protocol = json.loads(_PROTOCOL_JSON.read_text(encoding="utf-8"))
    assert "calendar-year expanding-window" in protocol["cv_scheme"]["value"]
    assert "PURGED_7_DAY_HORIZON_POLICY" in protocol["purge_embargo"]["value"]
    verification = protocol["cv_scheme"]["verification"]
    assert verification["fold_count"] == 23
    assert verification["verification_status"] == "PASS"
    assert verification["overlap_violations"] == []
    assert verification["role_violations"] == []
    assert verification["date_order_violations"] == []
    assert {f["fold_id"] for f in verification["insufficient_folds"]} == {"FOLD:2002", "FOLD:2003"}


def test_fmd07a_31b_cv_fold_verification_function_direct():
    fold_rows = json.loads(_CALENDAR_FOLDS_JSON.read_text(encoding="utf-8"))
    exposure_rows = _csv_rows(_EXPOSURE_MANIFEST_CSV)
    label_rows = _csv_rows(_RISK_LABELS_CSV)
    result = verify_fmd07a_cv_folds(fold_rows, exposure_rows, label_rows)
    assert result["fold_count"] == 23
    assert result["usable_fold_count"] == 21
    assert result["verification_status"] == "PASS"


# ---------------------------------------------------------------------------
# 32: locked-test firewall
# ---------------------------------------------------------------------------


def test_fmd07a_32_no_locked_test_outcome_accessed():
    audit = json.loads(_AUDIT_JSON.read_text(encoding="utf-8"))
    assert audit["held_out_rows_present"] is False
    assert audit["sri_lanka_rows_present"] is False
    # structural: this module never imports the held-out/Sri-Lanka selector
    # helpers at all
    from components.geospatial_tracking.services import fmd_model_development as m
    source = Path(m.__file__).read_text(encoding="utf-8")
    assert "held_out_from_model_fitting_origins" not in source
    assert "sri_lanka_transfer_case_study_origins" not in source
    protocol = json.loads(_PROTOCOL_JSON.read_text(encoding="utf-8"))
    # no held-out/Sri-Lanka count, prevalence, or performance field anywhere
    # in the protocol freeze -- 541/20 (locked-group origin counts) and any
    # held-out-labeled prevalence/metric key never surface here.
    protocol_text = json.dumps(protocol)
    assert "541" not in protocol_text  # held-out origin count never surfaces here
    assert "held_out_prevalence" not in protocol_text.lower()
    assert "sri_lanka_prevalence" not in protocol_text.lower()
    assert "held_out_positive" not in protocol_text.lower()
    assert "held_out_negative" not in protocol_text.lower()


# ---------------------------------------------------------------------------
# Blocker / eligibility registry / eligibility-derivation correctness
# ---------------------------------------------------------------------------


def test_fmd07a_blocker_is_explicit_and_no_value_is_fabricated():
    provenance = json.loads((_MODEL_DEV_DIR / "fmd07a_provenance.json").read_text(encoding="utf-8"))
    assert provenance["overall_status"] == "BLOCKED_PENDING_FULL_CORPUS_FEATURE_EXTRACTION"
    rows = _csv_rows(_MATRIX_CSV)
    eligible, _ = derive_eligible_predictor_features(_FEATURE_TABLE_CSV)
    for name in eligible:
        statuses = {row[f"{name}_status"] for row in rows}
        values = {row[f"{name}_value"] for row in rows}
        assert statuses == {"EXTRACTION_NOT_RUN"}
        assert values == {""}  # never fabricated


def test_fmd07a_unavailable_features_excluded_from_matrix_entirely():
    fieldnames = set(_csv_rows(_MATRIX_CSV)[0].keys())
    for species in ("swine", "sheep", "goat"):
        assert f"host_density_{species}_value" not in fieldnames
        assert f"host_density_{species}_status" not in fieldnames


def test_fmd07a_eligibility_registry_has_no_unknown_source():
    audit = json.loads(_AUDIT_JSON.read_text(encoding="utf-8"))
    registry = audit["feature_eligibility_registry"]
    assert len(registry) == 50  # 47 eligible + 3 unavailable
    unknown = [row for row in registry if row["source"] == "UNKNOWN_SOURCE"]
    assert unknown == []


def test_fmd07a_reproducibility_across_two_independent_temp_builds(tmp_path):
    names = [
        "fmd07_development_feature_matrix.csv",
        "fmd07_feature_matrix_audit.json",
        "fmd07_model_input_schema.json",
        "fmd07_development_protocol.json",
    ]
    _run(tmp_path / "runA")
    _run(tmp_path / "runB")
    for name in names:
        hash_a = _sha256(tmp_path / "runA" / name)
        hash_b = _sha256(tmp_path / "runB" / name)
        assert hash_a == hash_b, f"{name} not reproducible"


def test_fmd07a_canonical_fmd_input_unchanged():
    manifest = json.loads((_COHORT_DIR / "FMD_COHORT_MANIFEST.json").read_text(encoding="utf-8"))
    canonical = _REPO_ROOT / "local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
    assert _sha256(canonical) == manifest["source_canonical_csv_sha256"]


def test_fmd07a_canonical_lsd_input_unchanged():
    lsd = _REPO_ROOT / "local_data/processed/canonical_outbreaks_conservative.csv"
    if lsd.exists():
        assert _sha256(lsd) == "fa8e77d81b48af6bc2839deb4be9d4046d502ab948ce8e4e67a02a84c281d7f7"
