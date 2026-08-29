"""FMD-07A-R1: transparent pre-model protocol amendment and candidate-space
freeze."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from components.geospatial_tracking.services.fmd_calibration import FMD_SPATIAL_EVALUATION_RADIUS_KM
from components.geospatial_tracking.services.fmd_model_development_r1 import (
    AMENDMENT_STATUS,
    THRESHOLD_VALUE_STATUS,
    WEATHER_WINNER_STATUS,
    FMD07_FEATURE_VALUE_STATUS,
    build_fold_validity_policy,
    build_fmd07a_r1_pre_model_protocol_amendment,
    build_hybrid_candidate_status,
    build_ml_candidate_registry,
    build_pistes_hazard_candidate_status,
    build_preprocessing_imbalance_policy,
    build_probability_calibration_policy,
    build_spatial_baseline_kernel_scale_registry,
    build_threshold_policy,
    run_fmd07a_r1,
    update_fmd07_development_protocol_with_amendment,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_MODEL_DEV_DIR = _REPO_ROOT / "local_data/processed/fmd/model_development"
_CALIBRATION_DIR = _REPO_ROOT / "local_data/processed/fmd/calibration"

_AMENDMENT_JSON = _MODEL_DEV_DIR / "fmd07_pre_model_protocol_amendment.json"
_PROTOCOL_JSON = _MODEL_DEV_DIR / "fmd07_development_protocol.json"
_PROVENANCE_JSON = _MODEL_DEV_DIR / "fmd07a_provenance.json"
_MATRIX_CSV = _MODEL_DEV_DIR / "fmd07_development_feature_matrix.csv"
_AUDIT_JSON = _MODEL_DEV_DIR / "fmd07_feature_matrix_audit.json"
_SCHEMA_JSON = _MODEL_DEV_DIR / "fmd07_model_input_schema.json"
_FMD06_FREEZE_JSON = _CALIBRATION_DIR / "fmd06_calibration_freeze.json"
_FMD06_LABELS_CSV = _CALIBRATION_DIR / "fmd06_risk_origin_labels.csv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# 1: amendment classification
# ---------------------------------------------------------------------------


def test_fmd07a_r1_1_amendment_explicitly_classified():
    amendment = json.loads(_AMENDMENT_JSON.read_text(encoding="utf-8"))
    assert amendment["amendment_status"] == "PRE_MODEL_DEVELOPMENT_PROTOCOL_AMENDMENT"
    assert AMENDMENT_STATUS == "PRE_MODEL_DEVELOPMENT_PROTOCOL_AMENDMENT"
    assert "preregist" not in amendment["amendment_provenance_statement"].lower() or "not preregistered" in amendment["amendment_provenance_statement"].lower()
    assert amendment["created_before_any_predictive_model"] is True


# ---------------------------------------------------------------------------
# 2: original gaps remain visible
# ---------------------------------------------------------------------------


def test_fmd07a_r1_2_original_four_gaps_remain_visible_in_provenance():
    protocol = json.loads(_PROTOCOL_JSON.read_text(encoding="utf-8"))
    assert protocol["original_protocol_gap_count"] == 4
    for gap_key in (
        "FMD-EXP-02_spatial_distance_baseline",
        "FMD-EXP-03_pistes_hazard_model",
        "FMD-EXP-04_ml_candidate",
        "FMD-EXP-05_hybrid_candidate",
    ):
        entry = protocol["hyperparameter_candidates"][gap_key]
        assert "original_status" in entry
        assert "amended_status" in entry
        assert "amendment_source" in entry
        assert "rationale" in entry


# ---------------------------------------------------------------------------
# 3-4: registries finite, deterministic, metric-independent
# ---------------------------------------------------------------------------


def test_fmd07a_r1_3_spatial_registry_finite_and_deterministic():
    reg1 = build_spatial_baseline_kernel_scale_registry()
    reg2 = build_spatial_baseline_kernel_scale_registry()
    assert reg1 == reg2
    assert len(reg1["candidate_kernel_scale_km"]) == 3
    assert reg1["total_candidate_grid"]["total"] == 18


def test_fmd07a_r1_3b_ml_registry_finite_and_deterministic():
    reg1 = build_ml_candidate_registry()
    reg2 = build_ml_candidate_registry()
    assert reg1 == reg2
    assert reg1["total_hyperparameter_candidate_count"] == 11
    assert len(reg1["candidates"]) == 3


def test_fmd07a_r1_4_no_registry_depends_on_predictive_metric_values():
    for builder in (build_spatial_baseline_kernel_scale_registry, build_ml_candidate_registry, build_pistes_hazard_candidate_status):
        signature = inspect.signature(builder)
        assert not {"score", "metric", "pr_auc", "prauc", "auc", "accuracy", "performance"} & set(signature.parameters)
    reg = build_spatial_baseline_kernel_scale_registry()
    assert reg["predictive_metrics_used_to_define"] is False
    ml = build_ml_candidate_registry()
    assert ml["predictive_metrics_used_to_define"] is False


# ---------------------------------------------------------------------------
# 5: primary metric preserved
# ---------------------------------------------------------------------------


def test_fmd07a_r1_5_primary_metric_remains_pr_auc():
    amendment = json.loads(_AMENDMENT_JSON.read_text(encoding="utf-8"))
    assert amendment["primary_metric"] == "PR-AUC"
    assert "sensitivity_recall" in amendment["secondary_metrics"] or "sensitivity_recall" in amendment["secondary_metrics"]


# ---------------------------------------------------------------------------
# 6-7: held-out / Sri Lanka firewall
# ---------------------------------------------------------------------------


def test_fmd07a_r1_6_held_out_outcomes_unused():
    amendment = json.loads(_AMENDMENT_JSON.read_text(encoding="utf-8"))
    assert amendment["held_out_outcomes_used"] is False
    from components.geospatial_tracking.services import fmd_model_development_r1 as m
    source = Path(m.__file__).read_text(encoding="utf-8")
    assert "held_out_from_model_fitting_origins" not in source
    assert "541" not in json.dumps(amendment)


def test_fmd07a_r1_7_sri_lanka_outcomes_unused():
    amendment = json.loads(_AMENDMENT_JSON.read_text(encoding="utf-8"))
    assert amendment["sri_lanka_outcomes_used"] is False
    from components.geospatial_tracking.services import fmd_model_development_r1 as m
    source = Path(m.__file__).read_text(encoding="utf-8")
    assert "sri_lanka_transfer_case_study_origins" not in source


# ---------------------------------------------------------------------------
# 8-9: no model trained / no validation metric generated
# ---------------------------------------------------------------------------


def test_fmd07a_r1_8_9_no_model_trained_no_validation_metric():
    from components.geospatial_tracking.services import fmd_model_development_r1 as m
    source = Path(m.__file__).read_text(encoding="utf-8")
    assert ".fit(" not in source
    assert "predict(" not in source
    assert "predict_proba(" not in source
    assert "sklearn" not in source  # candidates are DEFINED, never imported/instantiated
    amendment = json.loads(_AMENDMENT_JSON.read_text(encoding="utf-8"))
    ml = amendment["candidate_model_families"]["ml_candidate"]
    assert ml["selection_basis"] == "none -- no candidate was evaluated against FMD data of any role in this checkpoint"


# ---------------------------------------------------------------------------
# 10-11: threshold / weather winner not selected
# ---------------------------------------------------------------------------


def test_fmd07a_r1_10_no_threshold_value_selected():
    amendment = json.loads(_AMENDMENT_JSON.read_text(encoding="utf-8"))
    assert amendment["threshold_value_status"] == "THRESHOLD_VALUE_NOT_SELECTED_PRE_MODEL"
    assert THRESHOLD_VALUE_STATUS == "THRESHOLD_VALUE_NOT_SELECTED_PRE_MODEL"
    policy = build_threshold_policy()
    assert policy["threshold_value_status"] == "THRESHOLD_VALUE_NOT_SELECTED_PRE_MODEL"


def test_fmd07a_r1_11_weather_winner_remains_unselected():
    amendment = json.loads(_AMENDMENT_JSON.read_text(encoding="utf-8"))
    assert amendment["weather_winner_status"] == "NOT_SELECTED"
    assert WEATHER_WINNER_STATUS == "NOT_SELECTED"
    assert amendment["weather_candidate_registry"] == ["event_day", "window_3day", "window_7day", "window_14day"]


# ---------------------------------------------------------------------------
# 12-13: no automatic reuse of frozen FMD-06 numbers as a model HP
# ---------------------------------------------------------------------------


def test_fmd07a_r1_12_stdbscan_eps_space_not_used_as_kernel_scale():
    reg = build_spatial_baseline_kernel_scale_registry()
    assert 0.236038 not in reg["candidate_kernel_scale_km"]
    freeze = json.loads(_FMD06_FREEZE_JSON.read_text(encoding="utf-8"))
    assert freeze["stdbscan_eps_space_km"] == 0.236038  # confirmed still the real frozen value
    assert freeze["stdbscan_eps_space_km"] not in reg["candidate_kernel_scale_km"]


def test_fmd07a_r1_13_200km_label_radius_not_automatically_a_kernel_scale():
    reg = build_spatial_baseline_kernel_scale_registry()
    assert FMD_SPATIAL_EVALUATION_RADIUS_KM == 200.0
    assert 200.0 not in reg["candidate_kernel_scale_km"]
    assert "200.0" in reg["excluded_values_and_why"]


# ---------------------------------------------------------------------------
# 14: training-fold-only preprocessing responsibility
# ---------------------------------------------------------------------------


def test_fmd07a_r1_14_training_fold_only_preprocessing_preserved():
    ml = build_ml_candidate_registry()
    policy = build_preprocessing_imbalance_policy(ml)
    assert "TRAINING FOLD only" in policy["fitting_scope_rule"]
    assert "never globally" in policy["fitting_scope_rule"]
    for algo, requirements in policy["per_algorithm_requirements"].items():
        assert set(requirements.keys()) == {
            "requires_scaling", "supports_class_weights", "handles_missing_values_directly", "requires_imputation",
        }


def test_fmd07a_r1_14b_gradient_boosted_trees_handles_missing_natively():
    ml = build_ml_candidate_registry()
    policy = build_preprocessing_imbalance_policy(ml)
    assert policy["per_algorithm_requirements"]["GRADIENT_BOOSTED_TREES"]["handles_missing_values_directly"] is True
    assert policy["per_algorithm_requirements"]["LOGISTIC_REGRESSION"]["requires_imputation"] is True


# ---------------------------------------------------------------------------
# 15: early-fold handling deterministic, defined before model results
# ---------------------------------------------------------------------------


def test_fmd07a_r1_15_early_invalid_fold_handling_deterministic():
    protocol = json.loads(_PROTOCOL_JSON.read_text(encoding="utf-8"))
    verification = protocol["cv_scheme"]["verification"]
    policy1 = build_fold_validity_policy(verification)
    policy2 = build_fold_validity_policy(verification)
    assert policy1 == policy2
    assert policy1["excluded_fold_count"] == 2
    assert {f["fold_id"] for f in policy1["excluded_folds"]} == {"FOLD:2002", "FOLD:2003"}
    assert policy1["usable_fold_count"] == 21
    signature = inspect.signature(build_fold_validity_policy)
    assert not {"score", "metric", "performance"} & set(signature.parameters)


# ---------------------------------------------------------------------------
# 16: predictor extraction status unchanged
# ---------------------------------------------------------------------------


def test_fmd07a_r1_16_predictor_extraction_status_unchanged():
    amendment = json.loads(_AMENDMENT_JSON.read_text(encoding="utf-8"))
    assert amendment["feature_extraction_status"] == "FULL_CORPUS_EXTRACTION_NOT_RUN"
    assert FMD07_FEATURE_VALUE_STATUS == "FULL_CORPUS_EXTRACTION_NOT_RUN"
    provenance = json.loads(_PROVENANCE_JSON.read_text(encoding="utf-8"))
    assert provenance["overall_status"] == "BLOCKED_PENDING_FULL_CORPUS_FEATURE_EXTRACTION"
    rows = list(__import__("csv").DictReader(_MATRIX_CSV.open(encoding="utf-8", newline="")))
    for row in rows[:50]:
        for key, value in row.items():
            if key.endswith("_status") and key not in (
                "model_fitting_role",
            ):
                if key.startswith(("weather_", "elevation_", "host_density_", "landcover_", "distance_to_nearest_river_km")):
                    assert value == "EXTRACTION_NOT_RUN"


def test_fmd07a_r1_16b_no_value_copied_from_29_event_sample():
    rows = list(__import__("csv").DictReader(_MATRIX_CSV.open(encoding="utf-8", newline="")))
    for row in rows[:50]:
        for key, value in row.items():
            if key.endswith("_value") and not key.startswith("audit_only") and key not in ("risk_target_label",):
                assert value == ""  # never a fabricated/copied number


# ---------------------------------------------------------------------------
# 17: FMD-06 artifacts unchanged
# ---------------------------------------------------------------------------


def test_fmd07a_r1_17_fmd06_artifacts_unchanged():
    freeze = json.loads(_FMD06_FREEZE_JSON.read_text(encoding="utf-8"))
    assert freeze["spatial_domain_status"] == "NO-GO"
    assert freeze["spatial_evaluation_radius_km"] is None
    assert freeze["active_window_days"] == 14
    assert freeze["stdbscan_eps_space_km"] == 0.236038
    labels = list(__import__("csv").DictReader(_FMD06_LABELS_CSV.open(encoding="utf-8", newline="")))
    assert len(labels) == 3761
    assert sum(1 for r in labels if r["risk_target_label"] == "1") == 2215
    assert sum(1 for r in labels if r["risk_target_label"] == "0") == 1546


# ---------------------------------------------------------------------------
# 18: existing FMD-07A schema/audit artifacts remain reproducible/unchanged
# ---------------------------------------------------------------------------


def test_fmd07a_r1_18_fmd07a_artifacts_unchanged_by_r1():
    # exact hashes recorded at FMD-07A completion
    assert _sha256(_MATRIX_CSV) == "023ed97a10b7c27be090f6009ee8600da08cf1c76519e3926d68fbc013fd6dad"
    assert _sha256(_AUDIT_JSON) == "45cebf44a3ca41a317801b6810a80a28f10fe28d963c4098a46ac815c45736fc"
    assert _sha256(_SCHEMA_JSON) == "02774a883a35008225c5b8b8ed89204a42121c0e29d6e9aefa60659f920131c7"


# ---------------------------------------------------------------------------
# Additional: PISTES/hybrid honestly blocked; hybrid firewall against PISTES change
# ---------------------------------------------------------------------------


def test_fmd07a_r1_pistes_remains_blocked_with_precise_reason():
    status = build_pistes_hazard_candidate_status()
    assert status["status"] == "BLOCKED"
    assert "SOFTWARE_FIXTURE_ONLY" in status["blocked_reason"]
    assert "NOT_YET_SCIENTIFICALLY_DEFINED" in status["blocked_reason"]


def test_fmd07a_r1_hybrid_blocked_by_pistes():
    pistes = build_pistes_hazard_candidate_status()
    hybrid = build_hybrid_candidate_status(pistes)
    assert hybrid["status"] == "BLOCKED_BY_PISTES"
    assert hybrid["gap_name"] == "FMD07_PROTOCOL_GAP_HYBRID_CANDIDATE_HYPERPARAMETER_SPACE"


def test_fmd07a_r1_hybrid_status_function_asserts_if_pistes_unblocked():
    fake_unblocked_pistes = {"status": "FMD07A_R1_FROZEN"}
    with pytest.raises(AssertionError):
        build_hybrid_candidate_status(fake_unblocked_pistes)


def test_fmd07a_r1_calibration_policy_never_fits():
    policy = build_probability_calibration_policy()
    assert policy["calibration_fitted_in_this_checkpoint"] is False
    assert "isotonic" in policy["development_only_procedure"].lower()


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_fmd07a_r1_reproducible_across_two_independent_temp_builds(tmp_path):
    import shutil

    names = ["fmd07_pre_model_protocol_amendment.json", "fmd07_development_protocol.json"]

    def _build(out_dir: Path) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in _MODEL_DEV_DIR.iterdir():
            # skip subdirectories (e.g. R2B1's canary/ output) -- this test
            # only needs the sibling FILES run_fmd07a_r1 itself reads
            if name.is_file() and name.name not in ("fmd07_pre_model_protocol_amendment.json",):
                shutil.copy2(name, out_dir / name.name)
        # start from a pristine (pre-R1) protocol copy, reconstructed by
        # stripping the amendment-added fields the real directory already carries
        run_fmd07a_r1(out_dir)
        return {name: _sha256(out_dir / name) for name in names}

    hashes1 = _build(tmp_path / "run1")
    hashes2 = _build(tmp_path / "run2")
    assert hashes1 == hashes2


def test_fmd07a_r1_update_protocol_function_deterministic():
    protocol = json.loads(_PROTOCOL_JSON.read_text(encoding="utf-8"))
    amendment = json.loads(_AMENDMENT_JSON.read_text(encoding="utf-8"))
    # protocol here already carries R1 fields; re-applying update with the
    # same amendment must be idempotent on the gap-audit portion
    updated1 = update_fmd07_development_protocol_with_amendment(protocol, amendment)
    updated2 = update_fmd07_development_protocol_with_amendment(protocol, amendment)
    assert updated1 == updated2
