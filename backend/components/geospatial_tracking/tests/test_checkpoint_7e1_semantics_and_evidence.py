"""Checkpoint 7E.1: D8-D14 wording correction, temporal-language
hardening, quality-semantics separation, target-event-view derivation,
evidence-summary consistency/SHA256 verification, and the scientific-
interpretation lock -- all NON-PREDICTIVE, no Sri Lanka scoring
anywhere in this file."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_TRACKED_DIR = _REPO_ROOT / "backend" / "components" / "geospatial_tracking"
_OUT_DIR = _REPO_ROOT / "local_data" / "model_evaluation" / "7e_sri_lanka"
_EVIDENCE_PATH = _TRACKED_DIR / "CHECKPOINT_7E_EVIDENCE_SUMMARY.json"

# Phrases that must never appear as an AFFIRMATIVE claim. Note that
# "external validation" / "blind validation" / "independent validation" are
# deliberately NOT in this blanket list: the required allowed-statement
# wording legitimately contains them in NEGATED form ("...not an
# independent, blind, or external validation estimate"). Those three are
# checked separately below with negation awareness so a blanket substring
# scan doesn't false-positive on the mandated disclaimer itself.
_FORBIDDEN_INTERPRETATION_PHRASES = (
    "sri lanka accuracy", "validation score", "61% accurate", "validated in sri lanka",
    "externally validated", "prospective performance",
)

_NEGATION_CHECKED_PHRASES = ("external validation", "blind validation", "independent validation")
_NEGATION_WORDS = ("not ", "never ", "n't ")
_NEGATION_WINDOW = 40


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_only_negated_occurrences(blob: str, phrase: str, window: int = _NEGATION_WINDOW) -> None:
    for match in re.finditer(re.escape(phrase), blob):
        preceding = blob[max(0, match.start() - window):match.start()]
        assert any(neg in preceding for neg in _NEGATION_WORDS), (
            f"{phrase!r} appears without a preceding negation within {window} chars: ...{preceding!r}[{phrase}]"
        )


# ---------------------------------------------------------------------------
# Part 1: D8-D14 wording correction
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (_OUT_DIR / "sri_lanka_case_study_interpretation.json").exists(), reason="real 7E interpretation artifact not present")
def test_7e1_d8d14_wording_is_precise_not_overly_broad():
    d = _load(_OUT_DIR / "sri_lanka_case_study_interpretation.json")
    text = d["no_d8_d14_exploratory_reported"]
    assert "broader PISTES product/research roadmap" in text
    assert "preregistered before the Sri Lanka D1-D7 result" in text
    assert "no pre-existing D8-D14 exploratory protocol exists in this project" not in text  # the old, overly broad claim
    assert d["correction_status"] == "NON_NUMERICAL_7E_SEMANTIC_CORRECTION"
    # the frozen D1-D7 result must remain exactly as before
    assert d["final_classification"] == "SRI_LANKA_TRANSFER_CASE_STUDY_LIMITED_BY_SMALL_SAMPLE"
    assert "61.10374178249515" in d["allowed_statement"]


# ---------------------------------------------------------------------------
# Part 2: temporal language hardening
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (_OUT_DIR / "sri_lanka_temporal_availability_audit.json").exists(), reason="real 7E temporal audit not present")
def test_7e1_temporal_wording_never_claims_biological_certainty_or_causal_justification():
    d = _load(_OUT_DIR / "sri_lanka_temporal_availability_audit.json")
    note = d["note"].lower()
    conf_note = d["confirmation_date_note"].lower()
    assert "real biological" not in note
    assert "recorded outbreak/event start date" in d["note"] or "recorded event-start" in d["note"]
    assert "genuinely unknown" in note
    # confirmation-date reasoning must be descriptive, not a "because"-style protocol justification
    assert "this is exactly why" not in conf_note
    assert "already-frozen retrospective availability-proxy protocol" in d["confirmation_date_note"]
    assert "descriptive" in conf_note
    # no availability_quality value in the rows may be ACTUAL
    for row in d["rows"]:
        assert row["availability_quality"] != "ACTUAL"


# ---------------------------------------------------------------------------
# Part 3: origin-trigger vs eligible-source quality separation
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (_OUT_DIR / "sri_lanka_quality_semantics_audit_7e1.json").exists(), reason="real 7E.1 quality-semantics audit not present")
def test_7e1_origin_trigger_and_eligible_source_quality_are_separated():
    d = _load(_OUT_DIR / "sri_lanka_quality_semantics_audit_7e1.json")
    assert d["no_c0_scores_recomputed"] is True
    assert len(d["rows"]) == 5
    for row in d["rows"]:
        for key in ("origin_trigger_source_ids", "origin_trigger_availability_qualities", "origin_trigger_gps_qualities",
                    "eligible_source_ids", "eligible_source_availability_qualities", "eligible_source_gps_qualities"):
            assert key in row
        assert set(row["origin_trigger_source_ids"]) <= set(row["eligible_source_ids"])  # trigger sources are always eligible
        for q in row["origin_trigger_availability_qualities"] + row["eligible_source_availability_qualities"]:
            assert q != "ACTUAL"


# ---------------------------------------------------------------------------
# Part 4: target-event-only derived view
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (_OUT_DIR / "sri_lanka_target_event_view_7e1.json").exists(), reason="real 7E.1 target-event view not present")
def test_7e1_target_event_view_is_a_pure_filter_with_no_null_target_rows():
    view = _load(_OUT_DIR / "sri_lanka_target_event_view_7e1.json")
    assert view["classification_of_source_artifact"] == "ORIGIN_TARGET_AUDIT_WITH_ZERO_TARGET_PLACEHOLDERS"
    assert view["n_target_rows"] == len(view["rows"])
    for row in view["rows"]:
        assert row["target_event_id"] is not None

    source = _load(_OUT_DIR / "sri_lanka_target_evaluation_records.json")
    expected_target_ids = {r["target_event_id"] for r in source if r.get("target_event_id") is not None}
    view_target_ids = {r["target_event_id"] for r in view["rows"]}
    assert view_target_ids == expected_target_ids  # pure filter, nothing invented, nothing dropped

    statuses = {r["target_scope_status"] for r in view["rows"]}
    assert "WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE" in statuses
    assert "OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE" in statuses
    for row in view["rows"]:
        if row["target_scope_status"] == "OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE":
            assert row["target_percentile"] is None  # no primary percentile for an OUTSIDE target


# ---------------------------------------------------------------------------
# Part 7A: tracked evidence-summary internal consistency -- NEVER skips
# ---------------------------------------------------------------------------


def test_7e1_tracked_evidence_summary_internally_consistent():
    assert _EVIDENCE_PATH.exists(), "CHECKPOINT_7E_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = _load(_EVIDENCE_PATH)

    assert d["selected_candidate_id"] == "C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8"
    assert d["frozen_7c_spec_hash"] == "ef3511d3527da6d85598846c0d828509ed07f134ac8d987c3d5702b507505a6d"
    assert d["sri_lanka_case_study_protocol_hash_7e"] == "4e33483289e510ce76a96216ab04333f31673d0a5a7d5ee75e8601674f4c75ce"

    ou = d["origin_universe"]
    assert ou["n_raw_sri_lanka_historical_records"] == 7
    assert ou["n_model_candidate_dedup_resolved_records"] == 6
    assert ou["n_sri_lanka_transfer_case_study_origins"] == 5
    assert ou["n_ready_origins"] == 5
    assert ou["n_blocked_origins"] == 0

    ts = d["target_scope"]
    assert ts["n_unique_evaluable_targets"] == 1
    assert ts["n_contributing_origins"] == 1

    pdr = d["pooled_descriptive_result"]
    assert pdr["mean_target_percentile"] == 61.10374178249515
    assert pdr["status"] == "SMALL_SAMPLE_DESCRIPTIVE_ONLY"

    assert d["final_classification"] == "SRI_LANKA_TRANSFER_CASE_STUDY_LIMITED_BY_SMALL_SAMPLE"
    assert d["not_external_validation"] is True
    assert d["availability_protocol_identity"] == "RETROSPECTIVE_PROXY_T0_INVARIANT"

    blob = json.dumps(d).lower()
    for forbidden in _FORBIDDEN_INTERPRETATION_PHRASES:
        assert forbidden not in blob
    for phrase in _NEGATION_CHECKED_PHRASES:
        _assert_only_negated_occurrences(blob, phrase)


# ---------------------------------------------------------------------------
# Part 7B: local SHA256 verification -- skips only if local_data absent
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _OUT_DIR.exists(), reason="local_data/model_evaluation/7e_sri_lanka absent (clean clone) -- SHA256-to-local-file verification skipped")
def test_7e1_evidence_summary_sha256_matches_actual_local_files():
    d = _load(_EVIDENCE_PATH)
    stored_hashes = d["local_artifact_sha256"]
    assert stored_hashes
    for filename, expected in stored_hashes.items():
        local_path = _OUT_DIR / filename
        assert local_path.exists(), f"evidence summary references {filename!r} but it is not present locally"
        actual = hashlib.sha256(local_path.read_bytes()).hexdigest()
        assert actual == expected, f"{filename}: stored SHA256 {expected} does not match actual local file hash {actual}"


# ---------------------------------------------------------------------------
# Part 8/9: scientific interpretation lock + GPS wording
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (_OUT_DIR / "sri_lanka_case_study_interpretation.json").exists(), reason="real 7E interpretation artifact not present")
def test_7e1_interpretation_lock_forbids_accuracy_and_validation_language():
    d = _load(_OUT_DIR / "sri_lanka_case_study_interpretation.json")
    blob = json.dumps(d).lower()
    for forbidden in _FORBIDDEN_INTERPRETATION_PHRASES:
        assert forbidden not in blob
    for phrase in _NEGATION_CHECKED_PHRASES:
        _assert_only_negated_occurrences(blob, phrase)


@pytest.mark.skipif(not (_OUT_DIR / "sri_lanka_geolocation_quality_audit.json").exists(), reason="real 7E GPS audit not present")
def test_7e1_gps_wording_never_implies_survey_grade_precision():
    d = _load(_OUT_DIR / "sri_lanka_geolocation_quality_audit.json")
    blob = json.dumps(d).lower()
    for forbidden in ("survey-grade", "survey grade", "meter-level", "meter level"):
        assert forbidden not in blob
    shared = [r for r in d["rows"] if r["coordinate_collision_status"] == "SHARED_WITH_UNRESOLVED"]
    assert shared
    assert shared[0]["source_record_id"] == "WAHIS_PDF:Event_3473.pdf:002408"
