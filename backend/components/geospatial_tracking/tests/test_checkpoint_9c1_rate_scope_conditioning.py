"""Checkpoint 9C.1: post-freeze rate-scope conditioning diagnostic.

READ-ONLY over the already-persisted Checkpoint 9A CSVs. No DB query,
no geodesic recomputation, no 9B bootstrap rerun, no S0/CI change, no
alternate radius, no alternate pooled S0, no held-out/Sri Lanka rate
inspection anywhere in this file."""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from components.geospatial_tracking.services.integration.nominal_reach_9c import build_nominal_reach_by_day_9c
from components.geospatial_tracking.services.model_development import (
    rate_scope_conditioning_9c1,
    rate_scope_conditioning_protocol_9c1,
)
from components.geospatial_tracking.services.model_development.rate_protocol_9b import (
    DEFAULT_9A_TARGET_LEVEL_CSV_PATH,
    EXPOSED_ESTIMATOR_VALUE_9B,
    HISTORICAL_9A_PROTOCOL_HASH_9B,
)
from components.geospatial_tracking.services.model_development.rate_scope_conditioning_9c1 import (
    NO_ALTERNATE_S0_STATUS_9C1,
    PRIMARY_HORIZON_RANGE_9C1,
    RATE_ESTIMAND_STATEMENT_9C1,
    field_completeness_by_scope,
    gps_quality_by_lead_audit,
    load_csv_rows,
    load_target_level_ids,
    reconcile_by_lead_day,
    s0_vs_theoretical_ceiling,
    target_event_inclusion_audit,
    theoretical_ceiling_km_day,
    theoretical_ceiling_table,
    within_rate_distribution_by_lead,
)
from components.geospatial_tracking.services.model_development.rate_scope_conditioning_protocol_9c1 import (
    HISTORICAL_9B_PROTOCOL_HASH_9C1,
    HISTORICAL_9C_INTEGRATION_PROTOCOL_HASH_9C1,
    rate_scope_conditioning_protocol_hash_9c1,
)

_9A_DIR = DEFAULT_9A_TARGET_LEVEL_CSV_PATH.parent
_OBS_CSV = _9A_DIR / "rate_origin_target_observations_9a.csv"
_LOCAL_9A_AVAILABLE = _OBS_CSV.exists()
_skip_no_local_9a = pytest.mark.skipif(not _LOCAL_9A_AVAILABLE, reason="local_data/model_development/9a_rate absent (clean clone)")

_9C1_OUT_DIR = _9A_DIR.parent / "9c1_rate_scope"
_LOCAL_9C1_RESULT_AVAILABLE = _9C1_OUT_DIR.exists()
_skip_no_local_9c1_result = pytest.mark.skipif(
    not _LOCAL_9C1_RESULT_AVAILABLE, reason="local_data/model_development/9c1_rate_scope absent (clean clone) -- skips ONLY the local-artifact hash verification"
)

_9C1_MODULES = (rate_scope_conditioning_9c1, rate_scope_conditioning_protocol_9c1)


def _direct_imports(module) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


@pytest.fixture(scope="module")
def _rows():
    return load_csv_rows(_OBS_CSV)


@pytest.fixture(scope="module")
def _frozen_target_ids():
    return load_target_level_ids(DEFAULT_9A_TARGET_LEVEL_CSV_PATH)


# ---------------------------------------------------------------------------
# 9C1-PARENT-01..03
# ---------------------------------------------------------------------------


def test_9c1_parent_01_historical_9a_hash_exact():
    assert HISTORICAL_9A_PROTOCOL_HASH_9B == "326427b08f5c43b9708409ae112460e8f0804db0c972a007caaae8ffca3b58ac"


def test_9c1_parent_02_9b_hash_exact():
    assert HISTORICAL_9B_PROTOCOL_HASH_9C1 == "969161e318508edfa2465d2f4598dbca17fcf29ef01bba2df42bec8093835d28"


def test_9c1_parent_03_9c_integration_hash_exact():
    assert HISTORICAL_9C_INTEGRATION_PROTOCOL_HASH_9C1 == "cec826a26c860c752d1fa32d94edcdfba2e0186950cdccfc96067fef2ce51a90"


# ---------------------------------------------------------------------------
# 9C1-MATH-01/02
# ---------------------------------------------------------------------------


def test_9c1_math_01_theoretical_ceiling_exact():
    expected = {1: 25.0, 2: 12.5, 3: 8.333333333333334, 4: 6.25, 5: 5.0, 6: 4.166666666666667, 7: 3.5714285714285716}
    for h, ceiling in expected.items():
        assert theoretical_ceiling_km_day(h) == pytest.approx(ceiling, rel=1e-15)
    table = theoretical_ceiling_table()
    for h, ceiling in expected.items():
        assert table[str(h)] == pytest.approx(ceiling, rel=1e-15)


def test_9c1_math_02_d7_ceiling_strictly_less_than_s0():
    assert EXPOSED_ESTIMATOR_VALUE_9B == 3.946421443154751
    assert theoretical_ceiling_km_day(7) < EXPOSED_ESTIMATOR_VALUE_9B
    cmp = s0_vs_theoretical_ceiling(EXPOSED_ESTIMATOR_VALUE_9B)
    assert cmp["7"]["s0_below_or_equal_theoretical_ceiling"] is False
    for h in range(1, 7):
        assert cmp[str(h)]["s0_below_or_equal_theoretical_ceiling"] is True


# ---------------------------------------------------------------------------
# 9C1-COUNT-01/02
# ---------------------------------------------------------------------------


@_skip_no_local_9a
def test_9c1_count_01_pooled_totals_reconcile(_rows):
    recon = reconcile_by_lead_day(_rows)
    total = sum(v["n_total_origin_target_rows"] for v in recon.values())
    within = sum(v["n_within_25km"] for v in recon.values())
    outside = sum(v["n_outside_25km"] for v in recon.values())
    unresolved = sum(v["n_unresolved"] for v in recon.values())
    assert (total, within, outside, unresolved) == (3947, 1387, 2560, 0)


@_skip_no_local_9a
def test_9c1_count_02_every_per_lead_total_reconciles(_rows):
    recon = reconcile_by_lead_day(_rows)
    assert set(recon.keys()) == {str(h) for h in PRIMARY_HORIZON_RANGE_9C1}
    for lead, entry in recon.items():
        assert entry["n_total_origin_target_rows"] == entry["n_within_25km"] + entry["n_outside_25km"] + entry["n_unresolved"]
        n_lead_rows = sum(1 for r in _rows if r["lead_days"] == lead)
        assert entry["n_total_origin_target_rows"] == n_lead_rows


# ---------------------------------------------------------------------------
# 9C1-RATE-01/02
# ---------------------------------------------------------------------------


@_skip_no_local_9a
def test_9c1_rate_01_v_obs_equals_d_min_over_lead_days(_rows):
    within = [r for r in _rows if r["scope_status"] == "WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE"]
    assert len(within) == 1387
    for r in within:
        expected = float(r["d_min_km"]) / int(r["lead_days"])
        assert float(r["v_obs_km_day"]) == pytest.approx(expected, rel=1e-9, abs=1e-9)


@_skip_no_local_9a
def test_9c1_rate_02_every_within_v_obs_within_theoretical_ceiling(_rows):
    dist = within_rate_distribution_by_lead(_rows)  # raises AssertionError (STOP) internally on violation
    for h in PRIMARY_HORIZON_RANGE_9C1:
        entry = dist[str(h)]
        if entry["observed_max"] is not None:
            assert entry["observed_max"] <= theoretical_ceiling_km_day(h) + 1e-6
    within = [r for r in _rows if r["scope_status"] == "WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE"]
    for r in within:
        ceiling = theoretical_ceiling_km_day(int(r["lead_days"]))
        assert float(r["v_obs_km_day"]) <= ceiling + 1e-6


# ---------------------------------------------------------------------------
# 9C1-TARGET-01
# ---------------------------------------------------------------------------


@_skip_no_local_9a
def test_9c1_target_01_included_target_set_matches_frozen_target_level_csv(_rows, _frozen_target_ids):
    audit = target_event_inclusion_audit(_rows, _frozen_target_ids)  # raises AssertionError (STOP) on mismatch
    assert audit["n_unique_target_event_id_with_at_least_one_WITHIN"] == 371
    assert len(_frozen_target_ids) == 371
    assert audit["target_event_ids_match_frozen_s0_dataset"] is True


# ---------------------------------------------------------------------------
# 9C1-GPS-01
# ---------------------------------------------------------------------------


@_skip_no_local_9a
def test_9c1_gps_01_quality_audit_descriptive_only_no_inclusion_change(_rows):
    gps = gps_quality_by_lead_audit(_rows)
    n_from_gps_audit = sum(entry["n"] for entry in gps["by_lead_within_primary_valid_rows"].values())
    n_within_actual = sum(1 for r in _rows if r["scope_status"] == "WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE")
    assert n_from_gps_audit == n_within_actual == 1387
    # structural: the audit function takes only rows and returns counts -- it has no filter/exclude parameter
    params = list(inspect.signature(gps_quality_by_lead_audit).parameters)
    assert params == ["rows"]


# ---------------------------------------------------------------------------
# 9C1-ZERO-01
# ---------------------------------------------------------------------------


@_skip_no_local_9a
def test_9c1_zero_01_zero_distance_records_preserved(_rows):
    gps = gps_quality_by_lead_audit(_rows)
    zero = gps["zero_distance_diagnostic"]
    assert zero["n_zero_distance_rows"] == 12
    assert zero["n_unique_target_events"] == 4
    assert zero["all_zero_distance_target_gps_quality_unknown"] is True
    assert zero["all_zero_distance_collision_status_unknown"] is True


# ---------------------------------------------------------------------------
# 9C1-NOALT-01
# ---------------------------------------------------------------------------


def test_9c1_noalt_01_no_alternate_pooled_s0_estimator():
    for module in _9C1_MODULES:
        src = inspect.getsource(module)
        for forbidden in ("statistics.median", "statistics.mean", "import statistics"):
            assert forbidden not in src
    src = inspect.getsource(rate_scope_conditioning_9c1)
    assert "def run_bootstrap" not in src and "def compute_bootstrap_uncertainty" not in src


# ---------------------------------------------------------------------------
# 9C1-FIREWALL-01..04
# ---------------------------------------------------------------------------


def _real_calls(module) -> set[str]:
    """Function/attribute names actually CALLED in real code -- ignores
    docstrings/comments/string literals entirely, so a module's own
    negated disclaimer text ("No import of X...") never false-positives
    this check."""
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def test_9c1_firewall_01_no_db_repository_query():
    for module in _9C1_MODULES:
        imports = _direct_imports(module)
        for forbidden in ("repositories", "repository", "sqlite", "SQLiteOutbreakRepository"):
            assert not any(forbidden in m for m in imports), (module.__name__, imports)
        calls = _real_calls(module)
        for forbidden in (
            "SQLiteOutbreakRepository", "build_forecast_origin_ledger", "build_forecast_targets",
            "get_eligible_sources", "derive_fit_development_rate_observations", "distance_km",
            "Geod", "classify_target_primary_scope",
        ):
            assert forbidden not in calls, (module.__name__, forbidden, calls)


def test_9c1_firewall_02_no_held_out_rate_input():
    for module in _9C1_MODULES:
        imports = _direct_imports(module)
        assert not any("heldout_run_7d" in m for m in imports), (module.__name__, imports)
        src = inspect.getsource(module)
        assert "heldout_run_7d" not in src


def test_9c1_firewall_03_no_sri_lanka_rate_input():
    for module in _9C1_MODULES:
        imports = _direct_imports(module)
        assert not any("sri_lanka_run_7e" in m or "sri_lanka_protocol_7e" in m for m in imports), (module.__name__, imports)
        src = inspect.getsource(module)
        assert "sri_lanka_run_7e" not in src and "sri_lanka_protocol_7e" not in src


def test_9c1_firewall_04_no_9b_bootstrap_invocation():
    for module in _9C1_MODULES:
        imports = _direct_imports(module)
        assert not any("rate_s0_bootstrap_9b" in m for m in imports), (module.__name__, imports)


# ---------------------------------------------------------------------------
# 9C1-REACH-01
# ---------------------------------------------------------------------------


def test_9c1_reach_01_historical_9c_nominal_reach_unchanged():
    expected = {
        1: 3.946421443154751, 2: 7.892842886309502, 3: 11.839264329464253, 4: 15.785685772619004,
        5: 19.732107215773755, 6: 23.678528658928506, 7: 27.624950102083258,
    }
    for entry in build_nominal_reach_by_day_9c():
        assert entry.nominal_reach_km == pytest.approx(expected[entry.day], rel=1e-15)


# ---------------------------------------------------------------------------
# 9C1-SEM-01/02
# ---------------------------------------------------------------------------


def test_9c1_sem_01_s0_interpretation_contains_explicit_25km_conditioning():
    assert "25-km" in RATE_ESTIMAND_STATEMENT_9C1 or "25km" in RATE_ESTIMAND_STATEMENT_9C1
    assert "conditional" in RATE_ESTIMAND_STATEMENT_9C1.lower()
    assert "d_min" in RATE_ESTIMAND_STATEMENT_9C1 or "25 km" in RATE_ESTIMAND_STATEMENT_9C1


def test_9c1_sem_02_nominal_reach_not_described_as_validated_epidemic_front():
    from components.geospatial_tracking.services.model_development.rate_scope_conditioning_9c1 import (
        NOMINAL_REACH_D7_INTERPRETATION_NOTE_9C1,
    )
    lowered = NOMINAL_REACH_D7_INTERPRETATION_NOTE_9C1.lower()
    assert "not evidence" in lowered
    assert "empirically validated" in lowered


# ---------------------------------------------------------------------------
# protocol identity + tracked evidence summary
# ---------------------------------------------------------------------------


def test_9c1_protocol_hash_deterministic():
    assert rate_scope_conditioning_protocol_hash_9c1() == rate_scope_conditioning_protocol_hash_9c1()
    src = inspect.getsource(rate_scope_conditioning_protocol_9c1)
    for forbidden in ("import datetime", "import time", "os.getcwd", "Path.cwd"):
        assert forbidden not in src


def test_9c1_no_alternate_s0_status_string():
    assert NO_ALTERNATE_S0_STATUS_9C1 == "NO_ALTERNATE_POOLED_S0_CALCULATED_IN_9C1"


def test_9c1_evidence_summary_internally_consistent():
    """Never skips -- tracked evidence summary consistency check."""
    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_9C1_RATE_SCOPE_EVIDENCE_SUMMARY.json"
    assert path.exists(), "CHECKPOINT_9C1_RATE_SCOPE_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = json.loads(path.read_text(encoding="utf-8"))

    assert d["historical_9a_protocol_hash"] == HISTORICAL_9A_PROTOCOL_HASH_9B
    assert d["historical_9b_protocol_hash"] == HISTORICAL_9B_PROTOCOL_HASH_9C1
    assert d["historical_9c_integration_protocol_hash"] == HISTORICAL_9C_INTEGRATION_PROTOCOL_HASH_9C1
    assert d["rate_scope_conditioning_protocol_hash_9c1"] == rate_scope_conditioning_protocol_hash_9c1()
    assert d["frozen_s0_km_day"] == EXPOSED_ESTIMATOR_VALUE_9B
    assert d["pooled_reconciliation"] == {"n_total_origin_target_rows": 3947, "n_within_25km": 1387, "n_outside_25km": 2560, "n_unresolved": 0}
    assert d["d7_theoretical_ceiling_below_frozen_s0"] is True
    assert d["target_event_inclusion"]["n_unique_target_event_id_with_at_least_one_WITHIN"] == 371
    assert d["zero_distance_diagnostic"]["n_zero_distance_rows"] == 12
    assert d["zero_distance_diagnostic"]["n_unique_target_events"] == 4
    assert d["final_classification"] == "RATE_SCOPE_CONDITIONING_AUDIT_COMPLETE_PRIMARY_S0_RETAINED_WITH_EXPLICIT_CONDITIONAL_INTERPRETATION"


@_skip_no_local_9c1_result
def test_9c1_evidence_summary_local_artifacts_sha256_match():
    import hashlib

    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_9C1_RATE_SCOPE_EVIDENCE_SUMMARY.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    out_dir = _9C1_OUT_DIR
    for filename, expected in d["local_artifact_sha256"].items():
        local_path = out_dir / filename
        assert local_path.exists(), f"{filename} referenced in evidence summary but missing locally"
        actual = hashlib.sha256(local_path.read_bytes()).hexdigest()
        assert actual == expected, f"{filename}: stored {expected} != actual {actual}"
