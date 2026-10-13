"""Checkpoint 4 Part 15: dataset freeze / reproducibility metadata.

Records exactly what inputs and code versions produced a given generation
run, so the historical candidate dataset can be regenerated and verified
later, and so anyone auditing it knows precisely which data/code state to
trust. Never pretends an uncommitted working tree has a stable commit
hash — see `_git_commit_hash`.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PARSER_VERSION = "checkpoint2-2026-08-18"  # kept in sync with data_processing/manifest.py's PARSER_VERSION
DEDUP_POLICY_VERSION = "checkpoint2.5-conservative-v1"  # HIGH-only auto-merge; see model_candidate.py
EPISODE_BUILDER_VERSION = "checkpoint3.5-v1"  # live-domain aggregation; see aggregation.py


def _file_hash(path: str | Path) -> str | None:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git_commit_hash(repo_root: str | Path) -> str:
    """Never fabricates a commit hash for an uncommitted/dirty tree —
    returns an explicit marker instead (master-prompt Part 15)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        commit = result.stdout.strip()
    except Exception:
        return "NO_COMMIT_AVAILABLE"

    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        if status.stdout.strip():
            return f"{commit}-DIRTY_WORKING_TREE"
    except Exception:
        pass
    return commit


def build_dataset_freeze_manifest(
    *,
    raw_dir: str | Path,
    conservative_csv_path: str | Path,
    model_candidate_report_path: str | Path,
    repo_root: str | Path,
) -> dict:
    raw_path = Path(raw_dir)
    input_file_hashes = {
        p.name: _file_hash(p) for p in sorted(raw_path.glob("*")) if p.is_file()
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit_hash(repo_root),
        "parser_version": PARSER_VERSION,
        "dedup_policy_version": DEDUP_POLICY_VERSION,
        "episode_builder_version": EPISODE_BUILDER_VERSION,
        "input_file_hashes": input_file_hashes,
        "conservative_dataset_hash": _file_hash(conservative_csv_path),
        "model_candidate_manifest_hash": _file_hash(model_candidate_report_path),
    }


def write_dataset_freeze_manifest(path: str | Path, **kwargs) -> dict:
    manifest = build_dataset_freeze_manifest(**kwargs)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
