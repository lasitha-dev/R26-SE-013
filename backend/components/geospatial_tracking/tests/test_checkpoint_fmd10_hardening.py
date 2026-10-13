"""Checkpoint FMD-10: backend hardening/testing for the FMD-09 runtime
RISK path.

No frozen scientific model is modified, retrained, retuned, or
reselected anywhere in this file -- FMD-08's locked candidate/threshold
and FMD-09's runtime service are exercised exactly as frozen. This
checkpoint proves (a) FMD/LSD disease isolation holds structurally, not
just by observed value, (b) every FMD-09 error path is explicit and
never fabricates a score, (c) repeated/concurrent requests are
deterministic, (d) malformed input never 500s, (e) the response
contract is stable and LSD-shape-free, and (f) FMD-08's evaluation
evidence is unchanged.

Real-DB-dependent tests skip gracefully on a clean clone (no
`data/local/pistes_dev.db`) -- structural/unit tests never skip.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from components.geospatial_tracking.api.router import router
from components.geospatial_tracking.api.schemas import FmdRiskAnalysisResponse
from components.geospatial_tracking.config import DEFAULT_SQLITE_DB_PATH
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.services.application import frozen_fmd_risk_analysis_9 as app_service
from components.geospatial_tracking.services.application.frozen_fmd_risk_analysis_9 import (
    ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_9,
    ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN_9,
    ANALYSIS_INTERNAL_ERROR_9,
    FMD_DISEASE_NAME_9,
    FmdRiskAnalysisError9,
    ORIGIN_NOT_FOUND_9,
    run_frozen_fmd_risk_runtime_analysis_9,
)
from components.geospatial_tracking.services.fmd_model_development_8_heldout import Fmd08IntegrityError
from components.geospatial_tracking.services.forecast_origin import build_forecast_origin_ledger
from components.geospatial_tracking.services.model_development.fmd_frozen_model_9 import (
    FROZEN_MODEL_SPEC_SHA256_FMD09,
    FROZEN_THRESHOLD_FMD09,
    HELD_OUT_PREDICTIONS_SHA256_FMD08,
    SELECTED_CANDIDATE_ID_FMD09,
)

_DB_PATH = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
_DB_AVAILABLE = _DB_PATH.exists()
_skip_no_db = pytest.mark.skipif(not _DB_AVAILABLE, reason="dev SQLite DB absent (clean clone)")
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _open_repo() -> SQLiteOutbreakRepository:
    return SQLiteOutbreakRepository(_DB_PATH)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


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
def real_fmd_origin_id():
    if not _DB_AVAILABLE:
        pytest.skip("dev SQLite DB absent")
    repo = _open_repo()
    try:
        origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9)
        for o in origins[:100]:
            try:
                run_frozen_fmd_risk_runtime_analysis_9(repo, o.forecast_origin_id)
                return o.forecast_origin_id
            except FmdRiskAnalysisError9:
                continue
    finally:
        repo.close()
    pytest.skip("no analyzable FMD origin found among the first 100 in dev DB")


# ---------------------------------------------------------------------------
# FMD10-ISOLATION-01/02: structural (AST-level) disease isolation -- never
# reachable via LSD's own frozen scientific modules, and the response
# contract never grows LSD-shaped fields.
# ---------------------------------------------------------------------------


class TestFmd10DiseaseIsolation:
    _LSD_FROZEN_MODULES = (
        "heldout_protocol_7d", "candidate_registry_7c", "c0_cell_local_tendency_8b3",
        "rate_protocol_9a", "rate_protocol_9b", "rate_scope_conditioning_9c1",
        "nominal_reach_9c", "geospatial_intelligence_contract_9c", "wind_scoring_7c",
    )

    def test_fmd10_isolation_01_runtime_service_never_imports_lsd_frozen_modules(self):
        imports = _direct_imports(app_service)
        hit = [m for lsd_mod in self._LSD_FROZEN_MODULES for m in imports if lsd_mod in m]
        assert not hit, hit

    def test_fmd10_isolation_02_response_schema_has_no_lsd_shaped_fields(self):
        forbidden = {"direction", "apparent_rate_context", "nominal_reach_by_day", "cells", "bearing_deg", "raw_c0_score"}
        fields = set(FmdRiskAnalysisResponse.model_fields.keys())
        assert fields.isdisjoint(forbidden), fields & forbidden

    def test_fmd10_isolation_03_radius_constant_is_fmd_owned_not_lsd_25km(self):
        from components.geospatial_tracking.services.model_development.local_evaluation_scope import (
            PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
        )
        assert app_service.FMD_SPATIAL_EVALUATION_RADIUS_KM != PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
        assert app_service.FMD_SPATIAL_EVALUATION_RADIUS_KM == 200.0


# ---------------------------------------------------------------------------
# FMD10-FIREWALL-01/02: no request-time gitignored-artifact dependency --
# the frozen candidate identity is a literal constant, never re-read from
# `local_data` on a live request (matches the router's own 10A-FIREWALL-01
# invariant for the LSD path).
# ---------------------------------------------------------------------------


class TestFmd10Firewall:
    def test_fmd10_firewall_01_no_local_data_reference_in_runtime_service(self):
        src = inspect.getsource(app_service)
        assert "local_data" not in src

    def test_fmd10_firewall_02_no_file_io_calls_in_runtime_service(self):
        tree = ast.parse(inspect.getsource(app_service))
        call_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    call_names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    call_names.add(node.func.attr)
        assert not ({"open", "read_text", "read_bytes"} & call_names)


# ---------------------------------------------------------------------------
# FMD10-IDENTITY-01: the promoted frozen constants are still exactly what
# FMD-09 verified against the real FMD-07B/FMD-08 artifacts -- this test
# never re-reads `local_data` itself (that is
# `smoke_tests/run_fmd09_freeze_verification.py`'s job); it only proves
# internal consistency has not silently drifted since FMD-09.
# ---------------------------------------------------------------------------


class TestFmd10FrozenIdentityUnchanged:
    def test_fmd10_identity_01_candidate_threshold_hash_unchanged_since_fmd09(self):
        # FMD-10B: pinned to the corrected (post fold-retention-fix)
        # identity. The original EXPONENTIAL:25KM/0.8 identity was selected
        # under a since-fixed multi-fold aggregation defect and is
        # superseded; its evidence is preserved unmodified as historical
        # PRE_CORRECTION_HELDOUT_EVALUATION but no longer drives this pin.
        assert SELECTED_CANDIDATE_ID_FMD09 == "FMD07B:SPATIAL:B0_DISTANCE_ONLY:GAUSSIAN:100KM:NONE:2de049cf8eefe775"
        assert FROZEN_THRESHOLD_FMD09 == 0.05
        assert FROZEN_MODEL_SPEC_SHA256_FMD09 == "782ff86278a1a8899cf0f42f1aa910ddd993cc5621d12266a734e6349e8bc8f8"
        assert HELD_OUT_PREDICTIONS_SHA256_FMD08 == "783dbd1d2eb2bbc2526fb3cdc7672df2fd497b8ba7868fcd59ad4341dc4a868c"


# ---------------------------------------------------------------------------
# FMD10-ERROR-01..04: every non-analyzable state is explicit and never
# fabricates a score -- mirrors Checkpoint 10A's own error-path hardening
# pattern (`test_10a_error_02_no_eligible_source_never_fabricated`).
# ---------------------------------------------------------------------------


class TestFmd10ErrorSemantics:
    def test_fmd10_error_01_unknown_origin_is_404(self):
        r = _client().get("/api/geospatial/analysis/ORIGIN:DOES_NOT_EXIST_XYZ:2099-01-01/fmd-risk")
        assert r.status_code == 404
        assert r.json()["detail"]["status"] == ORIGIN_NOT_FOUND_9

    @_skip_no_db
    def test_fmd10_error_02_no_eligible_source_is_409_never_fabricated(self, monkeypatch, real_fmd_origin_id):
        class _EmptyResult:
            sources: list = []

        monkeypatch.setattr(app_service, "get_eligible_sources", lambda *a, **kw: _EmptyResult())
        repo = _open_repo()
        try:
            with pytest.raises(FmdRiskAnalysisError9) as exc_info:
                run_frozen_fmd_risk_runtime_analysis_9(repo, real_fmd_origin_id)
            assert exc_info.value.status == ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_9
        finally:
            repo.close()

        r = _client().get(f"/api/geospatial/analysis/{real_fmd_origin_id}/fmd-risk")
        assert r.status_code == 409
        assert r.json()["detail"]["status"] == ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_9

    @_skip_no_db
    def test_fmd10_error_03_scientific_domain_failure_is_409_never_fabricated(self, monkeypatch, real_fmd_origin_id):
        def _raise(*a, **kw):
            raise RuntimeError("synthetic domain construction failure")

        monkeypatch.setattr(app_service, "build_scientific_evaluation_domain", _raise)
        repo = _open_repo()
        try:
            with pytest.raises(FmdRiskAnalysisError9) as exc_info:
                run_frozen_fmd_risk_runtime_analysis_9(repo, real_fmd_origin_id)
            assert exc_info.value.status == ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN_9
        finally:
            repo.close()

    @_skip_no_db
    def test_fmd10_error_04_frozen_candidate_resolution_failure_is_500_never_fabricated(self, monkeypatch, real_fmd_origin_id):
        def _raise(candidate_id):
            raise Fmd08IntegrityError("synthetic candidate resolution failure")

        monkeypatch.setattr(app_service, "resolve_frozen_candidate_spec", _raise)
        repo = _open_repo()
        try:
            with pytest.raises(FmdRiskAnalysisError9) as exc_info:
                run_frozen_fmd_risk_runtime_analysis_9(repo, real_fmd_origin_id)
            assert exc_info.value.status == ANALYSIS_INTERNAL_ERROR_9
        finally:
            repo.close()


# ---------------------------------------------------------------------------
# FMD10-DET-01/02: repeated and concurrent requests are deterministic --
# no shared mutable state, no snapshot cache to go stale, no retuning.
# ---------------------------------------------------------------------------


class TestFmd10Determinism:
    @_skip_no_db
    def test_fmd10_det_01_repeated_requests_are_byte_identical(self, real_fmd_origin_id):
        client = _client()
        r1 = client.get(f"/api/geospatial/analysis/{real_fmd_origin_id}/fmd-risk")
        r2 = client.get(f"/api/geospatial/analysis/{real_fmd_origin_id}/fmd-risk")
        assert r1.status_code == r2.status_code == 200
        assert r1.content == r2.content

    @_skip_no_db
    def test_fmd10_det_02_concurrent_requests_are_consistent(self, real_fmd_origin_id):
        client = _client()

        def _call(_i):
            return client.get(f"/api/geospatial/analysis/{real_fmd_origin_id}/fmd-risk").content

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(_call, range(16)))
        assert all(r == results[0] for r in results)


# ---------------------------------------------------------------------------
# FMD10-VALID-01/02: malformed input never 500s -- an unresolvable id is
# always an explicit 404, never an unhandled exception.
# ---------------------------------------------------------------------------


class TestFmd10InputValidation:
    @pytest.mark.parametrize("bad_id", [
        "",
        "not-a-real-origin-id",
        "ORIGIN:" + "X" * 500,
        "../../../etc/passwd",
        "ORIGIN:Afghanistan:not-a-date",
        "ORIGIN%3AAfghanistan%3A2003-04-29%00",
    ])
    def test_fmd10_valid_01_malformed_origin_id_never_500s(self, bad_id):
        r = _client().get(f"/api/geospatial/analysis/{bad_id}/fmd-risk")
        assert r.status_code in (404, 422)


# ---------------------------------------------------------------------------
# FMD10-CONTRACT-01/02: the response contract is stable and strict.
# ---------------------------------------------------------------------------


class TestFmd10ContractStability:
    _EXPECTED_FIELDS = {
        "forecast_origin_id", "country", "t0", "temporal_mode", "disease", "status",
        "risk_score", "risk_score_status", "threshold", "above_threshold",
        "n_eligible_sources", "active_source_window_days", "local_evaluation_radius_km",
        "frozen_candidate_id", "frozen_model_spec_sha256", "risk_score_semantics",
        "risk_task_semantics", "limitations",
    }

    def test_fmd10_contract_01_field_set_unchanged(self):
        assert set(FmdRiskAnalysisResponse.model_fields.keys()) == self._EXPECTED_FIELDS

    def test_fmd10_contract_02_extra_field_rejected(self):
        base = {f: None for f in self._EXPECTED_FIELDS}
        base.update({
            "forecast_origin_id": "x", "country": "x", "t0": "x", "temporal_mode": "x", "disease": "x",
            "status": "x", "risk_score_status": "x", "threshold": 0.8, "n_eligible_sources": 1,
            "active_source_window_days": 14, "local_evaluation_radius_km": 200.0,
            "frozen_candidate_id": "x", "frozen_model_spec_sha256": "x", "risk_score_semantics": "x",
            "risk_task_semantics": "x", "limitations": [],
        })
        with pytest.raises(ValidationError):
            FmdRiskAnalysisResponse(**{**base, "unexpected_field": 1})
        FmdRiskAnalysisResponse(**base)  # no unexpected field -- must construct cleanly


# ---------------------------------------------------------------------------
# FMD10-EVIDENCE-01: FMD-08 held-out evaluation evidence is immutable.
# ---------------------------------------------------------------------------


class TestFmd10EvidenceImmutability:
    def test_fmd10_evidence_01_fmd08_artifacts_unchanged_since_freeze(self):
        # FMD-10B: re-pointed at the corrected evidence directories. The
        # original fmd07b_*/fmd08_* paths remain preserved, unmodified, as
        # PRE_CORRECTION_HELDOUT_EVALUATION historical evidence -- this
        # immutability check now verifies the current authoritative
        # (corrected) evidence instead.
        spec_path = _REPO_ROOT / "local_data/processed/fmd/model_development/fmd10a_corrected_selection/fmd07b_frozen_model_spec.json"
        manifest_path = _REPO_ROOT / "local_data/processed/fmd/model_evaluation/fmd10b_corrected_heldout/fmd08_manifest.json"
        if not (spec_path.exists() and manifest_path.exists()):
            pytest.skip("FMD-07B/FMD-08 local_data evidence absent (clean clone)")

        spec_bytes = spec_path.read_bytes()
        spec = json.loads(spec_bytes.decode("utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert hashlib.sha256(spec_bytes).hexdigest() == FROZEN_MODEL_SPEC_SHA256_FMD09
        assert spec["selected_candidate_id"] == SELECTED_CANDIDATE_ID_FMD09
        assert spec["threshold"] == FROZEN_THRESHOLD_FMD09
        assert manifest["frozen_model_spec_sha256"] == FROZEN_MODEL_SPEC_SHA256_FMD09
        assert manifest["predictions_sha256"] == HELD_OUT_PREDICTIONS_SHA256_FMD08
        assert manifest["held_out_used"] is True
        assert manifest["sri_lanka_used"] is False
        assert manifest["retuning_performed"] is False
        assert manifest["held_out_cohort_count"] == 541
        assert manifest["scored_count"] == 501
        assert manifest["unavailable_count"] == 40
