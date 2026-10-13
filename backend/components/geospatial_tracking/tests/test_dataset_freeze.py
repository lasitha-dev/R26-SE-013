"""FREEZE-01."""

import json

from components.geospatial_tracking.services.dataset_freeze import (
    build_dataset_freeze_manifest,
    write_dataset_freeze_manifest,
)


def _make_inputs(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "a.csv").write_text("Event ID,Country\n1,Thailand\n", encoding="utf-8")
    (raw_dir / "b.pdf").write_bytes(b"%PDF-fake-content")
    conservative_csv = tmp_path / "canonical_outbreaks_conservative.csv"
    conservative_csv.write_text("source_record_id\nH1\n", encoding="utf-8")
    model_candidate_csv = tmp_path / "model_candidate_report.csv"
    model_candidate_csv.write_text("source_record_id,model_candidate\nH1,True\n", encoding="utf-8")
    return raw_dir, conservative_csv, model_candidate_csv


def test_freeze_01_hashes_deterministic_for_unchanged_inputs(tmp_path):
    raw_dir, conservative_csv, model_candidate_csv = _make_inputs(tmp_path)

    m1 = build_dataset_freeze_manifest(
        raw_dir=raw_dir,
        conservative_csv_path=conservative_csv,
        model_candidate_report_path=model_candidate_csv,
        repo_root=tmp_path,
    )
    m2 = build_dataset_freeze_manifest(
        raw_dir=raw_dir,
        conservative_csv_path=conservative_csv,
        model_candidate_report_path=model_candidate_csv,
        repo_root=tmp_path,
    )

    assert m1["input_file_hashes"] == m2["input_file_hashes"]
    assert m1["conservative_dataset_hash"] == m2["conservative_dataset_hash"]
    assert m1["model_candidate_manifest_hash"] == m2["model_candidate_manifest_hash"]
    assert m1["parser_version"] == m2["parser_version"]
    assert m1["dedup_policy_version"] == m2["dedup_policy_version"]
    assert m1["episode_builder_version"] == m2["episode_builder_version"]
    # generated_at is allowed to differ (it's a timestamp), everything
    # content-derived must not
    assert m1["conservative_dataset_hash"] is not None


def test_hash_changes_when_input_content_changes(tmp_path):
    raw_dir, conservative_csv, model_candidate_csv = _make_inputs(tmp_path)
    m1 = build_dataset_freeze_manifest(
        raw_dir=raw_dir, conservative_csv_path=conservative_csv,
        model_candidate_report_path=model_candidate_csv, repo_root=tmp_path,
    )
    conservative_csv.write_text("source_record_id\nH1\nH2\n", encoding="utf-8")
    m2 = build_dataset_freeze_manifest(
        raw_dir=raw_dir, conservative_csv_path=conservative_csv,
        model_candidate_report_path=model_candidate_csv, repo_root=tmp_path,
    )
    assert m1["conservative_dataset_hash"] != m2["conservative_dataset_hash"]


def test_uncommitted_or_dirty_tree_never_gets_a_fabricated_clean_commit_marker(tmp_path):
    raw_dir, conservative_csv, model_candidate_csv = _make_inputs(tmp_path)
    # tmp_path is not a git repo at all -> must not silently invent a hash
    manifest = build_dataset_freeze_manifest(
        raw_dir=raw_dir, conservative_csv_path=conservative_csv,
        model_candidate_report_path=model_candidate_csv, repo_root=tmp_path,
    )
    assert manifest["git_commit"] == "NO_COMMIT_AVAILABLE"


def test_write_dataset_freeze_manifest_produces_valid_json(tmp_path):
    raw_dir, conservative_csv, model_candidate_csv = _make_inputs(tmp_path)
    out_path = tmp_path / "manifests" / "dataset_freeze_manifest.json"
    write_dataset_freeze_manifest(
        out_path, raw_dir=raw_dir, conservative_csv_path=conservative_csv,
        model_candidate_report_path=model_candidate_csv, repo_root=tmp_path,
    )
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert "conservative_dataset_hash" in loaded
    assert "git_commit" in loaded
