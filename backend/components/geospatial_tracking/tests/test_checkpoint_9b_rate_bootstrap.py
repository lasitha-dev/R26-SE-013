"""Checkpoint 9B: formal freeze of the predeclared S0 estimated apparent
local spread-front rate, with pre-9B numeric exposure disclosed,
canonical input-dataset identity, pre-execution bootstrap freeze, and
target-event-level percentile bootstrap uncertainty.

PRE-EXECUTION TESTS ONLY (Part 14). The real 371-target, 1000-replicate
bootstrap is NEVER executed in this file -- `run_bootstrap`/
`compute_bootstrap_uncertainty` are only exercised on small toy vectors
for algorithm-correctness/reproducibility proofs. No DB/repository
access, no geodesic distance computation, no direction/wind input, no
held-out/Sri Lanka artifact anywhere in this file."""

from __future__ import annotations

import ast
import csv
import inspect
import json
import math
from pathlib import Path

import pytest

from components.geospatial_tracking.services.model_development import (
    rate_input_identity_9b,
    rate_protocol_9b,
    rate_s0_bootstrap_9b,
)
from components.geospatial_tracking.services.model_development.rate_input_identity_9b import (
    TargetLevelRow,
    canonical_payload_hash_from_persisted_text,
    compute_dataset_identity,
    raw_csv_sha256,
    validate_rows,
)
from components.geospatial_tracking.services.model_development.rate_protocol_9b import (
    DEFAULT_9A_TARGET_LEVEL_CSV_PATH,
    EXPOSED_ESTIMATOR_VALUE_9B,
    HISTORICAL_9A_PROTOCOL_HASH_9B,
    NINE_A1_EXPOSURE_CLASSIFICATION_9B,
    RATE_LABEL_9B,
    TARGET_LEVEL_ESTIMATOR_FORMULA_9B,
    bootstrap_implementation_source_sha256,
    s0_bootstrap_protocol_dict_9b,
    s0_bootstrap_protocol_hash_9b,
)
from components.geospatial_tracking.services.model_development.rate_s0_bootstrap_9b import (
    BOOTSTRAP_CI_TYPE_9B,
    BOOTSTRAP_INTERVAL_LEVEL_9B,
    BOOTSTRAP_N_RESAMPLES_9B,
    BOOTSTRAP_SEED_9B,
    BOOTSTRAP_UNIT_9B,
    Q_LOWER_9B,
    Q_UPPER_9B,
    compute_bootstrap_uncertainty,
    linear_quantile,
    run_bootstrap,
)

_LOCAL_9A_DIR = DEFAULT_9A_TARGET_LEVEL_CSV_PATH.parent
_LOCAL_9A_AVAILABLE = _LOCAL_9A_DIR.exists()
_skip_no_local_9a = pytest.mark.skipif(not _LOCAL_9A_AVAILABLE, reason="local_data/model_development/9a_rate absent (clean clone)")


def _toy_rows(pairs: list[tuple[str, str]]) -> list[TargetLevelRow]:
    return [TargetLevelRow(target_event_id=tid, rate_text=text, rate_value=float(text)) for tid, text in pairs]


# ---------------------------------------------------------------------------
# 9B-PARENT-01, 9B-EXP-01
# ---------------------------------------------------------------------------


def test_9b_parent_01_historical_9a_hash_exact():
    assert HISTORICAL_9A_PROTOCOL_HASH_9B == "326427b08f5c43b9708409ae112460e8f0804db0c972a007caaae8ffca3b58ac"


def test_9b_exp_01_pre_9b_exposure_explicitly_declared():
    assert NINE_A1_EXPOSURE_CLASSIFICATION_9B == "PRE_9B_S0_NUMERIC_ESTIMATOR_EXPOSURE_IN_9A_DIAGNOSTIC_DISCLOSED"
    assert EXPOSED_ESTIMATOR_VALUE_9B == 3.946421443154751


# ---------------------------------------------------------------------------
# 9B-DATA-01..05
# ---------------------------------------------------------------------------


@_skip_no_local_9a
def test_9b_data_01_input_csv_has_371_rows():
    identity, rows = compute_dataset_identity(DEFAULT_9A_TARGET_LEVEL_CSV_PATH)
    assert identity.n_rows == 371
    assert len(rows) == 371


@_skip_no_local_9a
def test_9b_data_02_371_unique_target_event_id():
    identity, _rows = compute_dataset_identity(DEFAULT_9A_TARGET_LEVEL_CSV_PATH)
    assert identity.n_unique_target_event_id == 371


def test_9b_data_03_duplicate_target_event_id_hard_fails():
    rows = _toy_rows([("A", "1.0"), ("B", "2.0"), ("A", "3.0")])
    with pytest.raises(ValueError, match="duplicate target_event_id"):
        validate_rows(rows)


def test_9b_data_04_negative_rate_hard_fails():
    rows = _toy_rows([("A", "1.0"), ("B", "-2.0")])
    with pytest.raises(ValueError, match="negative rate"):
        validate_rows(rows)


def test_9b_data_05_nan_inf_rate_hard_fails():
    nan_rows = [TargetLevelRow("A", "nan", float("nan"))]
    with pytest.raises(ValueError, match="non-finite"):
        validate_rows(nan_rows)
    inf_rows = [TargetLevelRow("A", "inf", float("inf"))]
    with pytest.raises(ValueError, match="non-finite"):
        validate_rows(inf_rows)


# ---------------------------------------------------------------------------
# 9B-HASH-01..04
# ---------------------------------------------------------------------------


@_skip_no_local_9a
def test_9b_hash_01_raw_csv_sha256_deterministic():
    assert raw_csv_sha256(DEFAULT_9A_TARGET_LEVEL_CSV_PATH) == raw_csv_sha256(DEFAULT_9A_TARGET_LEVEL_CSV_PATH)


def test_9b_hash_02_canonical_payload_hash_deterministic():
    rows = _toy_rows([("B", "2.0"), ("A", "1.0")])
    assert canonical_payload_hash_from_persisted_text(rows) == canonical_payload_hash_from_persisted_text(rows)


def test_9b_hash_03_reordering_rows_leaves_canonical_hash_unchanged():
    rows_a = _toy_rows([("A", "1.0"), ("B", "2.0"), ("C", "3.0")])
    rows_b = _toy_rows([("C", "3.0"), ("A", "1.0"), ("B", "2.0")])
    assert canonical_payload_hash_from_persisted_text(rows_a) == canonical_payload_hash_from_persisted_text(rows_b)


def test_9b_hash_04_changing_persisted_numeric_text_changes_canonical_hash():
    rows_a = _toy_rows([("A", "1.0"), ("B", "2.0")])
    rows_b = _toy_rows([("A", "1.0"), ("B", "2.0000001")])
    assert canonical_payload_hash_from_persisted_text(rows_a) != canonical_payload_hash_from_persisted_text(rows_b)


# ---------------------------------------------------------------------------
# 9B-S0-01/02
# ---------------------------------------------------------------------------


@_skip_no_local_9a
def test_9b_s0_01_median_of_frozen_371_values_equals_exposed_value():
    import statistics

    _identity, rows = compute_dataset_identity(DEFAULT_9A_TARGET_LEVEL_CSV_PATH)
    values = [r.rate_value for r in rows]
    assert statistics.median(values) == 3.946421443154751


def test_9b_s0_02_estimator_uses_target_level_values_not_origin_target_rows():
    assert "target_level_v" in TARGET_LEVEL_ESTIMATOR_FORMULA_9B
    assert "never the median of raw origin-target rows" in TARGET_LEVEL_ESTIMATOR_FORMULA_9B


# ---------------------------------------------------------------------------
# 9B-ZERO-01/02
# ---------------------------------------------------------------------------


@_skip_no_local_9a
def test_9b_zero_01_origin_target_zero_distance_count_remains_12():
    import csv

    obs_path = _LOCAL_9A_DIR / "rate_origin_target_observations_9a.csv"
    with obs_path.open(encoding="utf-8") as f:
        n_zero = sum(1 for row in csv.DictReader(f) if row["is_zero_distance"] == "True")
    assert n_zero == 12
    assert rate_protocol_9b.N_ZERO_DISTANCE_ORIGIN_TARGET_9B == 12


@_skip_no_local_9a
def test_9b_zero_02_target_level_zero_median_count_remains_4():
    _identity, rows = compute_dataset_identity(DEFAULT_9A_TARGET_LEVEL_CSV_PATH)
    n_zero = sum(1 for r in rows if r.rate_value == 0.0)
    assert n_zero == 4
    assert rate_protocol_9b.N_ZERO_TARGET_LEVEL_MEDIAN_9B == 4


# ---------------------------------------------------------------------------
# 9B-BOOT-01..07
# ---------------------------------------------------------------------------


def test_9b_boot_01_bootstrap_unit_is_target_event_id():
    assert BOOTSTRAP_UNIT_9B == "UNIQUE_TARGET_EVENT_ID"


def test_9b_boot_02_sample_size_per_replicate_is_n_target_events():
    src = inspect.getsource(rate_s0_bootstrap_9b.run_bootstrap)
    assert "for _ in range(n)" in src  # exactly n draws per replicate


def test_9b_boot_03_sampling_is_with_replacement():
    src = inspect.getsource(rate_s0_bootstrap_9b.run_bootstrap)
    assert "rng.randrange(n)" in src  # randrange allows repeated indexes -- with replacement
    assert "shuffle" not in src.lower()
    assert "sample(" not in src  # random.sample is WITHOUT replacement -- never used here


def test_9b_boot_04_seed_is_exactly_42():
    assert BOOTSTRAP_SEED_9B == 42


def test_9b_boot_05_n_resamples_exactly_1000():
    assert BOOTSTRAP_N_RESAMPLES_9B == 1000


def test_9b_boot_06_95_percent_percentile_interval_frozen():
    assert BOOTSTRAP_INTERVAL_LEVEL_9B == 0.95
    assert Q_LOWER_9B == 0.025
    assert Q_UPPER_9B == 0.975
    assert BOOTSTRAP_CI_TYPE_9B == "PERCENTILE_INTERVAL"


def test_9b_boot_07_toy_deterministic_vector_reproducible():
    toy = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    draws_a = run_bootstrap(toy, seed=42, n_resamples=50)
    draws_b = run_bootstrap(toy, seed=42, n_resamples=50)
    assert draws_a == draws_b  # exact reproducibility for a fixed seed

    result_a, raw_draws_a = compute_bootstrap_uncertainty(toy, seed=42, n_resamples=50)
    result_b, raw_draws_b = compute_bootstrap_uncertainty(toy, seed=42, n_resamples=50)
    assert result_a == result_b
    assert raw_draws_a == raw_draws_b


# ---------------------------------------------------------------------------
# 9B-QUANT-01
# ---------------------------------------------------------------------------


def test_9b_quant_01_explicit_linear_quantile_on_toy_vector():
    sorted_toy = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert linear_quantile(sorted_toy, 0.5) == 3.0  # median, position=(5-1)*0.5=2.0 exactly -> b[2]
    assert linear_quantile(sorted_toy, 0.25) == 2.0  # position=(5-1)*0.25=1.0 exactly -> b[1]
    assert linear_quantile(sorted_toy, 0.75) == 4.0  # position=3.0 exactly -> b[3]
    # a position that is NOT an exact integer -- proves real interpolation, not just indexing
    assert linear_quantile(sorted_toy, 0.1) == pytest.approx(1.4)  # position=0.4 -> 1 + 0.4*(2-1) = 1.4


# ---------------------------------------------------------------------------
# 9B-IMPL-01
# ---------------------------------------------------------------------------


def test_9b_impl_01_bootstrap_implementation_source_sha_bound_into_protocol():
    sha = bootstrap_implementation_source_sha256()
    assert sha == bootstrap_implementation_source_sha256()  # deterministic
    d = s0_bootstrap_protocol_dict_9b()
    assert d["bootstrap_implementation_source_sha256"] == sha


# ---------------------------------------------------------------------------
# 9B-FIREWALL-01..05
# ---------------------------------------------------------------------------


def _direct_imports(module) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


def test_9b_firewall_01_no_db_repository_dependency():
    for module in (rate_s0_bootstrap_9b, rate_input_identity_9b):
        imports = _direct_imports(module)
        for forbidden in ("repositories", "sqlite", "repository"):
            assert not any(forbidden in m.lower() for m in imports), imports


def test_9b_firewall_02_no_geodesic_distance_dependency():
    for module in (rate_s0_bootstrap_9b, rate_input_identity_9b):
        imports = _direct_imports(module)
        for forbidden in ("distance", "pyproj", "geospatial"):
            assert not any(forbidden in m.lower() for m in imports), imports


def test_9b_firewall_03_no_direction_wind_dependency():
    for module in (rate_s0_bootstrap_9b, rate_input_identity_9b):
        imports = _direct_imports(module)
        for forbidden in ("direction", "wind", "weather"):
            assert not any(forbidden in m.lower() for m in imports), imports


def test_9b_firewall_04_no_held_out_rate_artifact_or_path_used():
    # the frozen firewall STATUS strings legitimately say "held-out rate
    # not evaluated" -- what must be structurally absent is any import of
    # a held-out data/run module, or a local_data path referencing 7d/
    # held-out evaluation artifacts.
    for module in (rate_s0_bootstrap_9b, rate_input_identity_9b, rate_protocol_9b):
        imports = _direct_imports(module)
        assert not any("heldout" in m.lower() or "held_out" in m.lower() for m in imports), imports
        src = inspect.getsource(module)
        assert "model_evaluation/7d" not in src and "model_evaluation\\7d" not in src
        assert "heldout_run_7d" not in src and "heldout_protocol_7d" not in src


def test_9b_firewall_05_no_sri_lanka_rate_artifact_or_path_used():
    for module in (rate_s0_bootstrap_9b, rate_input_identity_9b, rate_protocol_9b):
        imports = _direct_imports(module)
        assert not any("sri_lanka" in m.lower() for m in imports), imports
        src = inspect.getsource(module)
        assert "7e_sri_lanka" not in src
        assert "sri_lanka_run_7e" not in src and "sri_lanka_protocol_7e" not in src


# ---------------------------------------------------------------------------
# 9B-OUTLIER-01
# ---------------------------------------------------------------------------


def test_9b_outlier_01_no_clipping_winsorization_log_transform_path():
    src = inspect.getsource(rate_s0_bootstrap_9b)
    for forbidden in ("winsoriz", "clip(", "np.clip", "log1p", "math.log(", "log10("):
        assert forbidden not in src.lower()


# ---------------------------------------------------------------------------
# 9B-SEM-01/02
# ---------------------------------------------------------------------------


def test_9b_sem_01_rate_label_exact():
    assert RATE_LABEL_9B == "Estimated apparent local spread-front rate (km/day)"


def test_9b_sem_02_no_biological_transmission_speed_accuracy_claim():
    d = s0_bootstrap_protocol_dict_9b()
    blob = str(d).lower()
    for forbidden in ("biological transmission speed", "viral velocity", "transmission accuracy"):
        idx = blob.find(forbidden)
        if idx != -1:
            preceding = blob[max(0, idx - 30):idx]
            assert "not" in preceding


# ---------------------------------------------------------------------------
# 9B-MANIFEST-01
# ---------------------------------------------------------------------------


@_skip_no_local_9a
def test_9b_manifest_01_protocol_fields_deterministic_timestamp_free():
    d1 = s0_bootstrap_protocol_dict_9b()
    d2 = s0_bootstrap_protocol_dict_9b()
    assert d1 == d2
    assert "generated_at" not in d1
    assert "timestamp" not in d1
    assert "execution_timestamp" not in d1
    assert s0_bootstrap_protocol_hash_9b() == s0_bootstrap_protocol_hash_9b()


# ---------------------------------------------------------------------------
# Part 21: post-run artifact tests -- READ-ONLY, never regenerate the
# real 1000-replicate bootstrap.
# ---------------------------------------------------------------------------

_9B_OUT_DIR = _LOCAL_9A_DIR.parent / "9b_rate"
_9B_RESULT_AVAILABLE = (_9B_OUT_DIR / "checkpoint_9b_audit.json").exists()
_skip_no_9b_result = pytest.mark.skipif(not _9B_RESULT_AVAILABLE, reason="local_data/model_development/9b_rate result absent (clean clone)")


def _load_9b_json(name: str) -> dict:
    return json.loads((_9B_OUT_DIR / name).read_text(encoding="utf-8"))


@_skip_no_9b_result
def test_9b_post_01_persisted_draw_count_is_1000():
    with (_9B_OUT_DIR / "s0_bootstrap_draws_9b.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1000


@_skip_no_9b_result
def test_9b_post_02_ci_recomputed_only_from_persisted_draws_matches_exactly():
    with (_9B_OUT_DIR / "s0_bootstrap_draws_9b.csv").open(encoding="utf-8") as f:
        draws = [float(row["bootstrap_median_km_day"]) for row in csv.DictReader(f)]
    sorted_draws = sorted(draws)
    recomputed_lower = linear_quantile(sorted_draws, Q_LOWER_9B)
    recomputed_upper = linear_quantile(sorted_draws, Q_UPPER_9B)

    uncertainty = _load_9b_json("s0_bootstrap_uncertainty_9b.json")
    assert recomputed_lower == uncertainty["ci_lower_km_day"]
    assert recomputed_upper == uncertainty["ci_upper_km_day"]


@_skip_no_9b_result
def test_9b_post_03_persisted_point_estimate_matches_exposed_value():
    uncertainty = _load_9b_json("s0_bootstrap_uncertainty_9b.json")
    assert uncertainty["point_estimate_km_day"] == 3.946421443154751
    spec = _load_9b_json("frozen_s0_apparent_rate_spec_9b.json")
    assert spec["point_estimate_km_day"] == 3.946421443154751


@_skip_no_9b_result
def test_9b_post_04_result_protocol_hash_matches_pre_run_manifest():
    manifest = _load_9b_json("pre_bootstrap_freeze_manifest_9b.json")
    audit = _load_9b_json("checkpoint_9b_audit.json")
    assert manifest["s0_bootstrap_protocol_hash_9b"] == audit["s0_bootstrap_protocol_hash_9b"]
    assert audit["s0_bootstrap_protocol_hash_9b"] == s0_bootstrap_protocol_hash_9b()


@_skip_no_9b_result
def test_9b_post_05_manifest_sha_in_execution_record_matches_sidecar():
    sidecar_sha = (_9B_OUT_DIR / "pre_bootstrap_freeze_manifest_9b.sha256").read_text(encoding="utf-8").strip()
    execution_record = _load_9b_json("bootstrap_execution_record_9b.json")
    assert execution_record["manifest_file_sha256_loaded_before_execution"] == sidecar_sha
    # independently recompute the manifest file's SHA256 -- proves the sidecar itself is honest
    import hashlib

    actual_manifest_sha = hashlib.sha256((_9B_OUT_DIR / "pre_bootstrap_freeze_manifest_9b.json").read_bytes()).hexdigest()
    assert actual_manifest_sha == sidecar_sha


@_skip_no_9b_result
def test_9b_post_06_input_csv_and_canonical_dataset_hashes_match():
    identity = _load_9b_json("rate_input_dataset_identity_9b.json")
    execution_record = _load_9b_json("bootstrap_execution_record_9b.json")
    assert identity["input_csv_sha256"] == execution_record["input_target_level_csv_sha256"]
    assert identity["canonical_payload_hash_from_persisted_text"] == execution_record["canonical_dataset_identity_hash"]
    # cross-check against a fresh independent read of the real CSV
    fresh_identity, _rows = compute_dataset_identity(DEFAULT_9A_TARGET_LEVEL_CSV_PATH)
    assert fresh_identity.input_csv_sha256 == identity["input_csv_sha256"]


@_skip_no_9b_result
def test_9b_post_07_result_artifact_sha_values_match_actual_files():
    import hashlib

    audit = _load_9b_json("checkpoint_9b_audit.json")
    for filename, expected_sha in audit["result_artifact_sha256"].items():
        actual_sha = hashlib.sha256((_9B_OUT_DIR / filename).read_bytes()).hexdigest()
        assert actual_sha == expected_sha, f"{filename}: expected {expected_sha}, got {actual_sha}"


def test_9b_evidence_summary_internally_consistent():
    """Never skips -- tracked evidence summary consistency check."""
    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_9B_EVIDENCE_SUMMARY.json"
    assert path.exists(), "CHECKPOINT_9B_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = json.loads(path.read_text(encoding="utf-8"))

    assert d["parent_historical_9a_protocol_hash"] == "326427b08f5c43b9708409ae112460e8f0804db0c972a007caaae8ffca3b58ac"
    assert d["nine_a1_exposure_classification"] == "PRE_9B_S0_NUMERIC_ESTIMATOR_EXPOSURE_IN_9A_DIAGNOSTIC_DISCLOSED"
    assert d["n_target_events"] == 371
    assert d["zero_count_distinction"]["n_zero_distance_origin_target_observations"] == 12
    assert d["zero_count_distinction"]["n_zero_target_level_median_rates"] == 4
    assert d["point_estimate_km_day"] == 3.946421443154751
    assert d["seed"] == 42
    assert d["n_resamples"] == 1000
    assert d["bootstrap_interval_km_day"]["lower"] < d["point_estimate_km_day"] < d["bootstrap_interval_km_day"]["upper"]
    assert d["held_out_rate_status"] == "NOT_EVALUATED_IN_9B"
    assert d["sri_lanka_rate_status"] == "NOT_EVALUATED_IN_9B"
    assert d["s1_status"] == "NOT_SELECTED"
    assert d["nominal_reach_status"] == "NOT_COMPUTED_IN_9B"
    assert d["final_classification"] == "FROZEN_DEVELOPMENT_DERIVED_S0_ESTIMATED_APPARENT_LOCAL_SPREAD_FRONT_RATE_WITH_PRE_9B_NUMERIC_EXPOSURE_DISCLOSED_AND_TARGET_EVENT_BOOTSTRAP_UNCERTAINTY"


@_skip_no_9b_result
def test_9b_evidence_summary_local_artifacts_sha256_match():
    import hashlib

    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_9B_EVIDENCE_SUMMARY.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    for filename, expected in d["local_artifact_sha256"].items():
        local_path = _9B_OUT_DIR / filename
        assert local_path.exists(), f"{filename} referenced in evidence summary but missing locally"
        actual = hashlib.sha256(local_path.read_bytes()).hexdigest()
        assert actual == expected, f"{filename}: stored {expected} != actual {actual}"


def test_9b_post_08_no_test_regenerates_real_bootstrap_draws():
    # AST-based: find every actual CALL to compute_bootstrap_uncertainty/
    # run_bootstrap in this module and check its first argument is never
    # the real full-dataset variable name -- excludes this function's own
    # source, since its assertion text legitimately quotes those forbidden
    # call patterns as strings (not as real calls).
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for func in tree.body:
        if isinstance(func, ast.FunctionDef) and func.name != "test_9b_post_08_no_test_regenerates_real_bootstrap_draws":
            for node in ast.walk(func):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("compute_bootstrap_uncertainty", "run_bootstrap"):
                    if node.args and isinstance(node.args[0], ast.Name):
                        assert node.args[0].id != "target_level_rates", f"real dataset passed to {node.func.id} outside the toy-vector test"
