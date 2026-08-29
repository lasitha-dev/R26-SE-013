"""Checkpoint 9A.1: pre-9B S0 numeric-exposure disclosure, arbitrary
sample-threshold removal, temporal-semantic hardening.

DOCUMENTATION/PROVENANCE HARDENING ONLY. Every test here reads
already-persisted local_data artifacts, tracked evidence/protocol
files, or frozen source constants -- no real 9A geometry (`d_min`,
`v_obs`, eligible-source selection, target construction) is executed
or recomputed anywhere in this module, and no held-out/Sri Lanka rate
artifact is ever loaded."""

from __future__ import annotations

import csv
import inspect
import json
import statistics
from pathlib import Path

import pytest

from components.geospatial_tracking.services.model_development import rate_readiness_9a
from components.geospatial_tracking.services.model_development.rate_protocol_9a import (
    FUTURE_S0_FORMULA_9A,
    rate_readiness_protocol_hash_9a,
)

HISTORICAL_9A_PROTOCOL_HASH = "326427b08f5c43b9708409ae112460e8f0804db0c972a007caaae8ffca3b58ac"

_COMPONENT_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[4]
_LOCAL_9A_DIR = _REPO_ROOT / "local_data" / "model_development" / "9a_rate"

_local_data_present = _LOCAL_9A_DIR.exists()
_skip_no_local_data = pytest.mark.skipif(
    not _local_data_present, reason="local_data/model_development/9a_rate absent (clean clone)"
)


def _load_json(name: str) -> dict:
    return json.loads((_LOCAL_9A_DIR / name).read_text(encoding="utf-8"))


def _load_target_level_csv_medians() -> list[float]:
    values = []
    with (_LOCAL_9A_DIR / "rate_target_level_readiness_9a.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            values.append(float(row["target_level_median_v_km_day"]))
    return values


# ---------------------------------------------------------------------------
# 9A1-EXP-01/02/03: exposure identity, extraction, and CSV consistency
# ---------------------------------------------------------------------------


@_skip_no_local_data
def test_9a1_exp_01_diagnostic_median_is_same_estimator_as_frozen_s0():
    """The 9A smoke-test runner already fed the 371 target-level medians
    into statistics.median() (via _percentiles) -- the exact estimator
    FUTURE_S0_FORMULA_9A defines as S0."""
    src = inspect.getsource(rate_readiness_9a)
    assert "def target_level_medians" in src
    assert "statistics.median(values)" in src  # per-target median, reused unchanged

    runner_src = (_COMPONENT_ROOT / "smoke_tests" / "run_rate_readiness_9a.py").read_text(encoding="utf-8")
    assert "target_level_values = list(target_medians.values())" in runner_src
    assert "target_level_median_v_km_day_distribution" in runner_src
    assert "statistics.median(s)" in runner_src  # _percentiles' median call, same statistics.median primitive

    assert "MEDIAN of target_level_v across UNIQUE target_event_id" in FUTURE_S0_FORMULA_9A


@_skip_no_local_data
def test_9a1_exp_02_exact_persisted_diagnostic_median_extracted_without_recomputing_geometry():
    diag = _load_json("rate_diagnostic_distributions_9a.json")
    exposed = diag["target_level_median_v_km_day_distribution"]["median"]
    assert exposed == 3.946421443154751
    assert diag["target_level_median_v_km_day_distribution"]["n"] == 371


@_skip_no_local_data
def test_9a1_exp_03_target_level_csv_median_agrees_with_persisted_diagnostic_median():
    diag = _load_json("rate_diagnostic_distributions_9a.json")
    exposed = diag["target_level_median_v_km_day_distribution"]["median"]
    csv_values = _load_target_level_csv_medians()
    assert len(csv_values) == 371
    assert statistics.median(csv_values) == exposed  # exact machine-precision match


# ---------------------------------------------------------------------------
# 9A1-HIST-01/02: historical 9A protocol preserved exactly
# ---------------------------------------------------------------------------


def test_9a1_hist_01_historical_protocol_hash_unchanged():
    assert rate_readiness_protocol_hash_9a() == HISTORICAL_9A_PROTOCOL_HASH


def test_9a1_hist_02_historical_formula_unchanged():
    assert FUTURE_S0_FORMULA_9A == (
        "S0 = MEDIAN of target_level_v across UNIQUE target_event_id values -- "
        "never the median of raw origin-target rows"
    )


# ---------------------------------------------------------------------------
# 9A1-N-01: arbitrary sufficiency cutoff removed
# ---------------------------------------------------------------------------


def test_9a1_n_01_no_arbitrary_sufficiency_cutoff_in_active_readiness_logic():
    runner_src = (_COMPONENT_ROOT / "smoke_tests" / "run_rate_readiness_9a.py").read_text(encoding="utf-8")
    assert "n_unique_targets < 10" not in runner_src
    assert "RATE_SAMPLE_SIZE_REQUIRES_METHODOLOGICAL_REVIEW" not in runner_src
    assert "SAMPLE_SIZE_NOMINALLY_SUFFICIENT_FOR_MEDIAN_ESTIMATION" not in runner_src
    assert "SAMPLE_SIZE_REPORTED_WITHOUT_ARBITRARY_SUFFICIENCY_THRESHOLD" in runner_src
    # no replacement magic-number cutoff was substituted for the removed one
    assert "n_unique_targets <" not in runner_src


# ---------------------------------------------------------------------------
# 9A1-TEMP-01: temporal wording corrected
# ---------------------------------------------------------------------------


def test_9a1_temp_01_documentation_does_not_claim_exact_biological_infection_time():
    doc = (_COMPONENT_ROOT / "RATE_MODEL_PROTOCOL.md").read_text(encoding="utf-8")
    normalized = " ".join(doc.split())
    assert "the SAME biological/target-occurrence-time field" not in normalized
    assert "recorded historical event-date / target-occurrence proxy field" in normalized
    assert "never described as exact biological/infection/transmission time" in normalized
    assert "APPARENT_RATE_FROM_RECORDED_EVENT_CHRONOLOGY_NOT_TRUE_INFECTION_TIME" in doc


# ---------------------------------------------------------------------------
# 9A1-QUALITY-01: explicit denominator semantics
# ---------------------------------------------------------------------------


@_skip_no_local_data
def test_9a1_quality_01_denominator_semantics_explicit():
    exposure = _load_json("s0_pre_9b_exposure_audit_9a1.json")
    denom = exposure["quality_count_denominator_semantics"]
    for key in (
        "target_gps_quality_counts",
        "nearest_source_gps_quality_counts",
        "all_eligible_source_gps_quality_counts",
        "all_eligible_source_availability_counts",
        "primary_valid_1387_v_obs_quality_counts",
    ):
        assert key in denom
        assert "denominator_population" in denom[key]
        assert denom[key]["denominator_population"]  # non-empty


# ---------------------------------------------------------------------------
# 9A1-ZERO-01: zero-distance observations preserved
# ---------------------------------------------------------------------------


@_skip_no_local_data
def test_9a1_zero_01_twelve_zero_distance_observations_preserved_not_dropped():
    exposure = _load_json("s0_pre_9b_exposure_audit_9a1.json")
    zero = exposure["zero_distance_audit"]
    assert zero["n_zero_distance"] == 12
    assert zero["epsilon_substituted"] is False
    assert zero["dropped"] is False
    assert zero["winsorized"] is False
    assert zero["asserted_as_proof_of_zero_biological_spread"] is False

    n_zero_in_csv = 0
    with (_LOCAL_9A_DIR / "rate_origin_target_observations_9a.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["is_zero_distance"] == "True":
                n_zero_in_csv += 1
    assert n_zero_in_csv == 12


# ---------------------------------------------------------------------------
# 9A1-FIREWALL-01: no held-out/Sri Lanka rate artifact loaded
# ---------------------------------------------------------------------------


def test_9a1_firewall_01_no_held_out_or_sri_lanka_rate_artifact_loaded():
    import ast

    this_module_tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported_names = [
        alias.name
        for node in ast.walk(this_module_tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    ] + [node.module for node in ast.walk(this_module_tree) if isinstance(node, ast.ImportFrom) and node.module]
    for forbidden in ("held_out", "sri_lanka"):
        assert not any(forbidden in name.lower() for name in imported_names), imported_names

    runner_src = (_COMPONENT_ROOT / "smoke_tests" / "run_rate_readiness_9a.py").read_text(encoding="utf-8")
    assert "held_out" not in runner_src.lower().replace("no_held_out_or_sri_lanka_origins_used", "")

    if _local_data_present:
        exposure = _load_json("s0_pre_9b_exposure_audit_9a1.json")
        assert exposure["no_heldout_rate_inspected"] is True
        assert exposure["no_sri_lanka_rate_inspected"] is True
