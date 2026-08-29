"""Checkpoint 7D.1.2 / 7D.1.2a: dynamic fail-closed label audit (tracked
vs. local split), scope/participation rate consistency, tracked-
evidence-summary consistency + SHA256 verification, and core C0
scientific-invariant reconfirmation -- all NON-PREDICTIVE, no held-out
scoring anywhere in this file.

**Checkpoint 7D.1.2a correction**: the original single `_CLASSIFICATION`
dict mixed TRACKED files (ship in git) with LOCAL gitignored artifacts
(`local_data/model_evaluation/7d/...`). Its `missing_expected` check
would have FAILED (not skipped) on a genuine clean clone, because the
local entries would be classified but never discovered -- contradicting
the claim that the label audit "never skips on a clean clone." Fixed by
splitting into `_TRACKED_LABEL_CLASSIFICATION` (audited unconditionally,
never skips) and `_LOCAL_LABEL_CLASSIFICATION` (audited only when
`local_data/model_evaluation/7d` actually exists; skipped with an
explicit reason otherwise -- never silently weakened to "just don't
check").

Reproducibility groups in this file:

- FULLY REPRODUCIBLE FROM TRACKED CODE/EVIDENCE (never skip on a clean
  clone): the TRACKED label-occurrence audit, the tracked-evidence-
  summary self-consistency check, the C0 invariant reconfirmation, and
  the simulated-clean-clone proof test.
- REQUIRE THE REAL, GITIGNORED `local_data/model_evaluation/7d/`
  ARTIFACTS (skip gracefully, with an explicit reason, on a clean clone
  that never ran the real checkpoint): the LOCAL label-occurrence audit,
  the scope/participation-summary consistency check, and the
  evidence-summary-to-local-file SHA256 verification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_TRACKED_DIR = _REPO_ROOT / "backend" / "components" / "geospatial_tracking"
_OUT_DIR = _REPO_ROOT / "local_data" / "model_evaluation" / "7d"

_ORIGINAL_LABEL = "PRE_SPECIFIED_HELD_OUT_FROM_FITTING_EVALUATION_WITH_PRIOR_DATASET_EXPOSURE_DISCLOSED"
_CORRECTED_LABEL = "FROZEN_HELD_OUT_FROM_FITTING_EVALUATION_WITH_PRIOR_DATASET_AND_PRE_FINAL_PREDICTIVE_SUBSET_EXPOSURE_DISCLOSED"

_TRACKED_SEARCH_ROOTS = [_TRACKED_DIR, _TRACKED_DIR / "services", _TRACKED_DIR / "tests"]

# TRACKED: files that ship in Git -- audited unconditionally, this half
# of the audit must never skip.
_TRACKED_LABEL_CLASSIFICATION = {
    "backend/components/geospatial_tracking/DATA_EXPOSURE_AUDIT.md": "CURRENT_REPORTING_MUST_USE_7D1_CORRECTED_LABEL",
    "backend/components/geospatial_tracking/MODEL_DEVELOPMENT_PROTOCOL.md": "CURRENT_REPORTING_MUST_USE_7D1_CORRECTED_LABEL",
    "backend/components/geospatial_tracking/VALIDATION_PROTOCOL.md": "CURRENT_REPORTING_MUST_USE_7D1_CORRECTED_LABEL",
    "backend/components/geospatial_tracking/DATA_AUDIT.md": "MIXED_BY_DESIGN",
    "backend/components/geospatial_tracking/services/model_development/heldout_protocol_7d.py": "MIXED_BY_DESIGN",
    "backend/components/geospatial_tracking/CHECKPOINT_7D_EVIDENCE_SUMMARY.json": "CURRENT_REPORTING_MUST_USE_7D1_CORRECTED_LABEL",
    # this test module itself defines both label constants for the
    # discovery function below -- legitimately contains both by design.
    "backend/components/geospatial_tracking/tests/test_checkpoint_7d12_evidence_seal.py": "MIXED_BY_DESIGN",
}

# LOCAL: gitignored artifacts under local_data/model_evaluation/7d/ --
# audited ONLY when that directory actually exists (real checkpoint was
# run in this environment); never claimed to ship in Git.
_LOCAL_LABEL_CLASSIFICATION = {
    "local_data/model_evaluation/7d/pre_evaluation_freeze_manifest.json": "HISTORICAL_7D_PROTOCOL_ALLOWED",
    "local_data/model_evaluation/7d/checkpoint_7d_audit.json": "CURRENT_REPORTING_MUST_USE_7D1_CORRECTED_LABEL",
    "local_data/model_evaluation/7d/heldout_exposure_disclosure.json": "CURRENT_REPORTING_MUST_USE_7D1_CORRECTED_LABEL",
    "local_data/model_evaluation/7d/procedural_exposure_correction_7d1.json": "CURRENT_REPORTING_MUST_USE_7D1_CORRECTED_LABEL",
    "local_data/model_evaluation/7d/evaluation_label_provenance_audit_7d11.json": "MIXED_BY_DESIGN",
}


def _discover(label: str, roots: list[Path]) -> set:
    found: set = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.suffix not in (".md", ".py", ".json"):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if label in text:
                found.add(str(path.resolve().relative_to(_REPO_ROOT)).replace("\\", "/"))
    return found


def _audit(roots: list[Path], classification: dict) -> dict:
    """Pure: fail-closed comparison of dynamically-discovered label
    occurrences (under `roots`) against a hand-reviewed `classification`
    map. Returns the discrepancy sets -- callers assert on them."""
    discovered = _discover(_ORIGINAL_LABEL, roots) | _discover(_CORRECTED_LABEL, roots)
    classified = set(classification.keys())
    return {
        "unclassified": discovered - classified,
        "missing_expected": classified - discovered,
    }


def _local_artifacts_present(out_dir: Path) -> bool:
    return out_dir.exists()


def test_7d12a_tracked_label_audit_is_fail_closed_and_never_skips():
    """Checkpoint 7D.1.2a Part 2: TRACKED-only audit -- independent of
    whether local_data/ exists at all. Must never skip."""
    result = _audit(_TRACKED_SEARCH_ROOTS, _TRACKED_LABEL_CLASSIFICATION)
    assert not result["unclassified"], f"undiscovered/unclassified TRACKED label occurrence(s): {sorted(result['unclassified'])}"
    assert not result["missing_expected"], f"classified TRACKED file(s) no longer contain the expected label: {sorted(result['missing_expected'])}"


@pytest.mark.skipif(not _local_artifacts_present(_OUT_DIR), reason="local_data/model_evaluation/7d absent (clean clone) -- local-artifact label audit skipped, never counted as a tracked-audit failure")
def test_7d12a_local_label_audit_is_fail_closed_when_local_data_exists():
    """Checkpoint 7D.1.2a Part 2: LOCAL-only audit, gated on the real
    gitignored directory actually existing. A missing local_data/ must
    NEVER make the tracked audit above fail -- this is why it is a
    separate test with its own skip condition."""
    result = _audit([_OUT_DIR], _LOCAL_LABEL_CLASSIFICATION)
    assert not result["unclassified"], f"undiscovered/unclassified LOCAL label occurrence(s): {sorted(result['unclassified'])}"
    assert not result["missing_expected"], f"classified LOCAL file(s) no longer contain the expected label: {sorted(result['missing_expected'])}"


def test_7d12a_simulated_clean_clone_tracked_audit_and_evidence_summary_still_pass():
    """Checkpoint 7D.1.2a Part 7: proves clean-clone behavior WITHOUT
    physically deleting local_data -- points the local-artifact presence
    check at a deliberately nonexistent directory and confirms (a) that
    check correctly reports absence, while (b) the TRACKED audit and (c)
    the tracked evidence-summary check are completely unaffected by it,
    since neither one's logic ever reads from the simulated path."""
    simulated_missing_local_dir = _REPO_ROOT / "local_data" / "model_evaluation" / "__7d_clean_clone_simulation_never_created__"
    assert not simulated_missing_local_dir.exists()
    assert _local_artifacts_present(simulated_missing_local_dir) is False

    # (b) tracked audit is untouched by the simulated local path
    tracked_result = _audit(_TRACKED_SEARCH_ROOTS, _TRACKED_LABEL_CLASSIFICATION)
    assert not tracked_result["unclassified"] and not tracked_result["missing_expected"]

    # (c) tracked evidence summary check reads only the tracked file, also untouched
    path = _TRACKED_DIR / "CHECKPOINT_7D_EVIDENCE_SUMMARY.json"
    assert path.exists()
    d = json.loads(path.read_text(encoding="utf-8"))
    assert d["label"] == "TRACKED_AGGREGATE_RESEARCH_EVIDENCE_SUMMARY"

    # and an audit pointed AT the simulated-missing directory correctly
    # yields "everything expected is missing" (i.e. it would legitimately
    # skip, not fail) -- proving the LOCAL test's skip condition is sound.
    simulated_local_result = _audit([simulated_missing_local_dir], _LOCAL_LABEL_CLASSIFICATION)
    assert simulated_local_result["missing_expected"] == set(_LOCAL_LABEL_CLASSIFICATION.keys())
    assert simulated_local_result["unclassified"] == set()


@pytest.mark.skipif(not (_OUT_DIR / "scope_and_participation_summary_7d12.json").exists(), reason="real 7D local artifacts not present in this environment")
def test_7d12_scope_and_participation_rates_consistent_with_frozen_counts():
    d = json.loads((_OUT_DIR / "scope_and_participation_summary_7d12.json").read_text(encoding="utf-8"))
    assert d["n_all_d1d7_targets"] == 588 and d["n_within_targets"] == 323 and d["n_outside_targets"] == 265
    assert d["n_within_targets"] + d["n_outside_targets"] == d["n_all_d1d7_targets"]
    assert d["n_heldout_origins"] == 229 and d["n_contributing_origins"] == 126 and d["n_zero_primary_target_origins"] == 103
    assert d["n_contributing_origins"] + d["n_zero_primary_target_origins"] == d["n_heldout_origins"]
    assert d["target_scope_inclusion_rate"] == pytest.approx(323 / 588)
    assert d["target_scope_outside_rate"] == pytest.approx(265 / 588)
    assert d["origin_primary_metric_participation_rate"] == pytest.approx(126 / 229)
    assert d["origin_zero_primary_target_rate"] == pytest.approx(103 / 229)


def test_7d12_tracked_evidence_summary_exists_and_is_internally_consistent():
    """Fully reproducible from tracked code -- CHECKPOINT_7D_EVIDENCE_SUMMARY.json
    is itself tracked (not gitignored), so this never skips on a clean clone."""
    path = _TRACKED_DIR / "CHECKPOINT_7D_EVIDENCE_SUMMARY.json"
    assert path.exists(), "CHECKPOINT_7D_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = json.loads(path.read_text(encoding="utf-8"))

    assert d["label"] == "TRACKED_AGGREGATE_RESEARCH_EVIDENCE_SUMMARY"
    assert d["selected_candidate_id"] == "C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8"
    assert d["frozen_7c_spec_hash"] == "ef3511d3527da6d85598846c0d828509ed07f134ac8d987c3d5702b507505a6d"
    assert d["historical_7d_protocol_hash"] == "74be1d652fff4739ddeb612dd21a273004d35117bedc718981c5e7636ce6cb90"
    assert d["corrected_7d1_evidence_label"] == _CORRECTED_LABEL

    oc = d["origin_counts"]
    assert oc["n_heldout_origins"] == 229 and oc["n_contributing_origins"] == 126 and oc["n_zero_primary_target_origins"] == 103 and oc["n_blocked_origins"] == 0
    assert oc["n_contributing_origins"] + oc["n_zero_primary_target_origins"] == oc["n_heldout_origins"]

    tc = d["target_counts"]
    assert tc["n_all_d1d7_targets"] == 588 and tc["n_within_targets"] == 323 and tc["n_outside_targets"] == 265
    assert tc["n_within_targets"] + tc["n_outside_targets"] == tc["n_all_d1d7_targets"]

    pm = d["pooled_metrics"]
    assert pm["mean_target_percentile"] == 73.84712361066521
    assert pm["top5_capture_rate"] == 0.17389455782312924
    assert pm["top10_capture_rate"] == 0.29191232048374904

    assert d["evidence_bounded_no_retuning_status"] == "NO_POST_EXPOSURE_NUMERICALLY_LOAD_BEARING_CODE_CHANGE_DETECTED_IN_RECORDED_SESSION"
    assert d["availability_protocol_identity"] == "RETROSPECTIVE_PROXY_T0_INVARIANT"

    # sanity: does NOT leak raw outbreak data / origin-level records / local machine paths
    blob = json.dumps(d)
    for forbidden_path_marker in ("C:\\Users", "/home/", "C:/Users"):
        assert forbidden_path_marker not in blob
    assert "forecast_origin_id" not in blob  # no origin-level records


@pytest.mark.skipif(not _OUT_DIR.exists(), reason="local_data/model_evaluation/7d absent (clean clone) -- SHA256-to-local-file verification skipped")
def test_7d12a_evidence_summary_sha256_matches_actual_local_files():
    """Checkpoint 7D.1.2a Part 5: verifies the SHA256 values stored in
    CHECKPOINT_7D_EVIDENCE_SUMMARY.json actually match the real local
    artifact bytes -- never recomputes/replaces a stored hash, only
    checks it."""
    path = _TRACKED_DIR / "CHECKPOINT_7D_EVIDENCE_SUMMARY.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    stored_hashes = summary["local_artifact_sha256"]
    assert stored_hashes, "expected at least one stored local-artifact hash"
    for filename, expected_sha256 in stored_hashes.items():
        local_path = _OUT_DIR / filename
        assert local_path.exists(), f"evidence summary references {filename!r} but it is not present locally"
        actual_sha256 = hashlib.sha256(local_path.read_bytes()).hexdigest()
        assert actual_sha256 == expected_sha256, f"{filename}: stored SHA256 {expected_sha256} does not match actual local file hash {actual_sha256}"


# ---------------------------------------------------------------------------
# Part 9 (7D.1.2): core C0 scientific invariants, reconfirmed from code
# only -- no held-out scoring is executed anywhere below.
# ---------------------------------------------------------------------------


def test_7d12_c0_invariants_reconfirmed_without_rescoring():
    from components.geospatial_tracking.services.hazard.kernels import evaluate_kernel
    from components.geospatial_tracking.services.model_development.candidate_registry_7c import FROZEN_KERNEL_FAMILY, FROZEN_KERNEL_SCALE_KM
    from components.geospatial_tracking.services.model_development.heldout_protocol_7d import (
        ACTIVE_SOURCE_WINDOW_DAYS_7D,
        EVALUATION_DISTANCE_KM_7D,
        GRID_CELL_SIZE_KM_7D,
        HOST_FACTOR_NOT_SELECTED,
        WATER_CONTEXT_NOT_SELECTED,
        WIND_ANISOTROPY_NOT_SELECTED,
        ENVIRONMENTAL_SUITABILITY_NOT_SELECTED,
        SOURCE_STRENGTH_NOT_SELECTED,
    )

    # C0 formula: EXPONENTIAL kernel at 25.0 km
    assert FROZEN_KERNEL_FAMILY == "EXPONENTIAL"
    assert FROZEN_KERNEL_SCALE_KM == 25.0
    assert evaluate_kernel(0.0, family="EXPONENTIAL", distance_scale_km=25.0) == 1.0

    # frozen scientific geometry unchanged
    assert GRID_CELL_SIZE_KM_7D == 5.0
    assert EVALUATION_DISTANCE_KM_7D == 25.0
    assert ACTIVE_SOURCE_WINDOW_DAYS_7D == 14

    # no host/wind/environment/water/source-strength input
    assert HOST_FACTOR_NOT_SELECTED == "NOT_SELECTED"
    assert WIND_ANISOTROPY_NOT_SELECTED == "NOT_SELECTED"
    assert ENVIRONMENTAL_SUITABILITY_NOT_SELECTED == "NOT_SELECTED"
    assert WATER_CONTEXT_NOT_SELECTED == "NOT_SELECTED"
    assert SOURCE_STRENGTH_NOT_SELECTED == "NOT_SELECTED"

    # output label never claims probability
    from components.geospatial_tracking.services.model_development.candidate_registry_7c import build_candidate_registry_7c, C0_FAMILY
    c0 = next(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)
    assert c0.output_label == "RELATIVE_SPATIAL_SCORE"
    assert "PROBABILITY" not in c0.output_label.upper()
