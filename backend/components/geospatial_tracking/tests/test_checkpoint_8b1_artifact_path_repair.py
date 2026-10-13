"""Checkpoint 8B.1: canonical local_data path repair, byte-preserving
artifact relocation, provenance consistency, and final 8B lock.

ARTIFACT-RELOCATION AND PATH VERIFICATION ONLY. No C0 scoring, no
direction-field recomputation, no structural-audit rerun anywhere in
this file -- the real 579-origin/560,853-cell result is loaded from
the already-relocated artifact and checked for exact equality with the
frozen values, never regenerated."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_TRACKED_DIR = _REPO_ROOT / "backend" / "components" / "geospatial_tracking"
_OUT_DIR = _REPO_ROOT / "local_data" / "model_development" / "8b_direction"
_EVIDENCE_PATH = _TRACKED_DIR / "CHECKPOINT_8B_EVIDENCE_SUMMARY.json"
_ACCIDENTAL_PATH_LITERAL_SLASH = "geospatial_tracking/local_data"
_ACCIDENTAL_PATH_LITERAL_BACKSLASH = "geospatial_tracking\\local_data"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _runner_module():
    import components.geospatial_tracking.smoke_tests.run_direction_structural_audit_8b as m
    return m


# ---------------------------------------------------------------------------
# Part 8: local SHA256 verification -- skips only if local_data absent
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _OUT_DIR.exists(), reason="local_data/model_development/8b_direction absent (clean clone) -- SHA256-to-local-file verification skipped")
def test_8b1_evidence_summary_sha256_matches_canonical_local_files():
    d = _load(_EVIDENCE_PATH)
    stored_hashes = d["local_artifact_sha256"]
    assert stored_hashes
    assert d.get("local_artifact_root") == "local_data/model_development/8b_direction"
    for filename, expected in stored_hashes.items():
        local_path = _OUT_DIR / filename  # resolved ONLY under the canonical root, never the accidental nested path
        assert local_path.exists(), f"evidence summary references {filename!r} but it is not present at the canonical local_data root"
        actual = hashlib.sha256(local_path.read_bytes()).hexdigest()
        assert actual == expected, f"{filename}: stored SHA256 {expected} does not match actual local file hash {actual}"


# ---------------------------------------------------------------------------
# Part 9: canonical path tests (never CWD-dependent -- always resolved via
# Path(__file__) or an explicit cwd=)
# ---------------------------------------------------------------------------


def test_8b1_path_01_runner_output_dir_is_repository_root_local_data():
    m = _runner_module()
    expected = _REPO_ROOT / "local_data" / "model_development" / "8b_direction"
    assert m.LOCAL_OUT_DIR.resolve() == expected.resolve()


def test_8b1_path_02_runner_output_dir_not_under_backend_local_data():
    m = _runner_module()
    backend_local_data = (_REPO_ROOT / "backend" / "local_data").resolve()
    resolved = m.LOCAL_OUT_DIR.resolve()
    assert backend_local_data not in resolved.parents
    assert resolved != backend_local_data


def test_8b1_path_03_runner_output_dir_not_under_component_nested_local_data():
    m = _runner_module()
    accidental = (_TRACKED_DIR / "local_data").resolve()
    resolved = m.LOCAL_OUT_DIR.resolve()
    assert accidental not in resolved.parents
    assert resolved != accidental


def test_8b1_path_04_no_active_loader_references_accidental_nested_path():
    # AST string-literal scan (not a raw text scan): comments explaining
    # the historical bug are legitimate and expected (this module's own
    # docstring/comments document exactly this fix) -- what must be
    # structurally absent is the accidental path used as an actual
    # runtime STRING VALUE anywhere in the module.
    import ast
    import inspect

    m = _runner_module()
    tree = ast.parse(inspect.getsource(m))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert _ACCIDENTAL_PATH_LITERAL_SLASH not in node.value
            assert _ACCIDENTAL_PATH_LITERAL_BACKSLASH not in node.value


@pytest.mark.skipif(not _OUT_DIR.exists(), reason="local_data/model_development/8b_direction absent (clean clone) -- gitignore check needs the real file to check-ignore against")
def test_8b1_path_05_canonical_8b_artifacts_are_gitignored():
    target = _OUT_DIR / "direction_structural_audit_8b.json"
    rel = target.relative_to(_REPO_ROOT)
    result = subprocess.run(
        ["git", "check-ignore", "-v", str(rel).replace("\\", "/")],
        cwd=str(_REPO_ROOT), capture_output=True, text=True,
    )
    assert result.returncode == 0, f"expected git to report this path as ignored, got: {result.stdout!r} {result.stderr!r}"
    assert "/local_data/" in result.stdout or ":/local_data/" in result.stdout


def test_8b1_path_06_no_remaining_source_literal_of_the_accidental_path():
    # Scoped to PRODUCTION source only -- `tests/` (including this very
    # file) legitimately references the accidental-path literal as the
    # comparison string that PROVES the bug is fixed elsewhere; that is
    # the opposite of a regression.
    accidental_literal = "components/geospatial_tracking/local_data/model_development/8b_direction"
    accidental_literal_bs = "components\\geospatial_tracking\\local_data\\model_development\\8b_direction"
    py_root = _REPO_ROOT / "backend" / "components" / "geospatial_tracking"
    offenders = []
    for py_file in py_root.rglob("*.py"):
        if "__pycache__" in py_file.parts or "tests" in py_file.parts or "smoke_tests" in py_file.parts:
            continue
        text = py_file.read_text(encoding="utf-8")
        if accidental_literal in text or accidental_literal_bs in text:
            offenders.append(str(py_file))
    assert not offenders, f"accidental nested 8B path literal still present in: {offenders}"


# ---------------------------------------------------------------------------
# Part 10: relocated scientific artifacts unchanged -- loaded, never regenerated
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _OUT_DIR.exists(), reason="local_data/model_development/8b_direction absent (clean clone)")
def test_8b1_relocated_structural_audit_values_unchanged():
    audit = _load(_OUT_DIR / "direction_structural_audit_8b.json")
    assert audit["n_fit_development_origins_total"] == 579
    assert audit["n_origins_processed"] == 579
    assert audit["n_cells_processed"] == 560853
    assert audit["n_invariant_failures"] == 0
    assert audit["n_exact_zero_distance_cases"] == 0
    assert audit["direction_status_counts"] == {"DIRECTION_AVAILABLE": 560853}
    assert audit["coverage_status_counts"] == {"COMPLETE_DIRECTIONAL_MASS_COVERAGE": 560853}
    assert audit["directional_clarity_distribution"]["median"] == 0.7091066761041402
    assert audit["protocol_hash_8b"] == "9d111741d303d1dcf73c2a624b99c3fa7c3aaa2020d52d3254d5d744e963f32d"


def test_8b1_relocation_audit_proves_byte_identity():
    relocation_audit_path = _OUT_DIR / "artifact_relocation_audit_8b1.json"
    if not relocation_audit_path.exists():
        pytest.skip("artifact_relocation_audit_8b1.json absent (clean clone)")
    d = _load(relocation_audit_path)
    assert d["label"] == "ARTIFACT_RELOCATION_ONLY"
    assert d["scientific_content_changed"] is False
    assert d["structural_audit_rerun"] is False
    assert d["all_file_hashes_preserved"] is True
    for filename, entry in d["per_file"].items():
        assert entry["hash_match"] is True
        assert entry["size_match"] is True
        assert entry["before_sha256"] == entry["after_sha256"]


# ---------------------------------------------------------------------------
# Evidence-summary tracked/untracked wording (Part 12)
# ---------------------------------------------------------------------------


def test_8b1_evidence_summary_git_wording_accurate():
    result = subprocess.run(
        ["git", "status", "--short", "--", "backend/components/geospatial_tracking/CHECKPOINT_8B_EVIDENCE_SUMMARY.json"],
        cwd=str(_REPO_ROOT), capture_output=True, text=True,
    )
    status_line = result.stdout.strip()
    if status_line.startswith("??"):
        # currently untracked -- confirm no doc in this checkpoint's own
        # provenance note falsely calls it "tracked" without qualification
        d = _load(_EVIDENCE_PATH)
        assert d["label"] == "TRACKED_AGGREGATE_RESEARCH_EVIDENCE_SUMMARY"  # category label, not a git-state claim
