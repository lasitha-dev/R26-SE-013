"""Checkpoint 10A.1: historical-replay / live-operational semantic
separation, active-source-window provenance hardening, and API-protocol
identity correction.

No 7B-9C.1 rerun, no source-window tuning (14 days is read, never
changed or tested at an alternate value), no rate/bootstrap rerun, no
held-out/Sri Lanka inspection. The historical Checkpoint 10A API
protocol hash is verified unchanged throughout this file."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.services.application import frozen_geospatial_analysis_10a as app_service
from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import (
    ACTIVE_SOURCE_WINDOW_DAYS_10A,
    ACTIVE_SOURCE_WINDOW_DAYS_10A1,
    ACTIVE_SOURCE_WINDOW_ORIGINAL_PROVENANCE_10A1,
    ACTIVE_SOURCE_WINDOW_RUNTIME_STATUS_10A1,
    AVAILABILITY_MODE_10A1,
    LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1,
    RECORD_DOMAIN_SCOPE_10A1,
    RUNTIME_DATA_MODE_10A1,
    RUNTIME_SNAPSHOT_REUSE_STATUS_10A1,
)
from components.geospatial_tracking.config import ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT
from components.geospatial_tracking.domain.enums import RecordDomainScope
from components.geospatial_tracking.schemas import ValidationMode
from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a import (
    geospatial_api_protocol_dict_10a,
    geospatial_api_protocol_hash_10a,
)
from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a1 import (
    HISTORICAL_10A_API_PROTOCOL_HASH_10A1,
    HISTORICAL_API_IDENTITY_CLASSIFICATION_10A1,
    geospatial_api_protocol_dict_10a1,
    geospatial_api_protocol_hash_10a1,
)

_HISTORICAL_10A_HASH = "8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716"


def _hash_dict(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 10A1-HIST-01
# ---------------------------------------------------------------------------


def test_10a1_hist_01_historical_10a_hash_unchanged():
    assert geospatial_api_protocol_hash_10a() == _HISTORICAL_10A_HASH
    assert HISTORICAL_10A_API_PROTOCOL_HASH_10A1 == _HISTORICAL_10A_HASH
    assert geospatial_api_protocol_dict_10a1()["historical_10a_api_protocol_hash"] == _HISTORICAL_10A_HASH


# ---------------------------------------------------------------------------
# 10A1-WINDOW-01..05
# ---------------------------------------------------------------------------


def test_10a1_window_01_runtime_source_window_exactly_14():
    assert ACTIVE_SOURCE_WINDOW_DAYS_10A1 == 14
    assert ACTIVE_SOURCE_WINDOW_DAYS_10A1 == ACTIVE_SOURCE_WINDOW_DAYS_10A == ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT


def test_10a1_window_02_original_provenance_unfrozen_development_parameter():
    assert ACTIVE_SOURCE_WINDOW_ORIGINAL_PROVENANCE_10A1 == "UNFROZEN_DEVELOPMENT_PARAMETER"


def test_10a1_window_03_runtime_status_states_compatibility_not_validation():
    status = ACTIVE_SOURCE_WINDOW_RUNTIME_STATUS_10A1
    assert "FIXED" in status and "HISTORICAL" in status
    assert "NOT_SCIENTIFICALLY_VALIDATED" in status


def test_10a1_window_04_protocol_identity_binds_source_window():
    d = geospatial_api_protocol_dict_10a1()
    assert d["active_source_window_days"] == 14
    assert d["active_source_window_original_provenance"] == "UNFROZEN_DEVELOPMENT_PARAMETER"
    assert d["active_source_window_runtime_status"] == ACTIVE_SOURCE_WINDOW_RUNTIME_STATUS_10A1


def test_10a1_window_05_toy_dict_source_window_change_alters_hash():
    real_hash = geospatial_api_protocol_hash_10a1()
    toy = geospatial_api_protocol_dict_10a1()
    toy["active_source_window_days"] = 21  # a TOY value in a copied dict only -- never the real constant
    toy_hash = _hash_dict(toy)
    assert toy_hash != real_hash
    # the real constant remains untouched
    assert ACTIVE_SOURCE_WINDOW_DAYS_10A1 == 14


# ---------------------------------------------------------------------------
# 10A1-MODE-01..05
# ---------------------------------------------------------------------------


def test_10a1_mode_01_runtime_data_mode_historical_retrospective_replay():
    assert RUNTIME_DATA_MODE_10A1 == "HISTORICAL_RETROSPECTIVE_REPLAY"


def test_10a1_mode_02_availability_mode_retrospective_proxy():
    assert AVAILABILITY_MODE_10A1 == "RETROSPECTIVE_PROXY" == ValidationMode.RETROSPECTIVE_PROXY.value


def test_10a1_mode_03_record_domain_scope_historical_only():
    assert RECORD_DOMAIN_SCOPE_10A1 == "HISTORICAL_ONLY" == RecordDomainScope.HISTORICAL_ONLY.value


def test_10a1_mode_04_live_operational_status_not_implemented():
    assert LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1.startswith("NOT_IMPLEMENTED")


def test_10a1_mode_05_runtime_service_passes_the_same_enums_to_source_selection():
    tree = ast.parse(inspect.getsource(app_service))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_frozen_geospatial_runtime_analysis_10a")
    call = next(
        n for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "get_eligible_sources"
    )
    kw_by_name = {kw.arg: kw.value for kw in call.keywords}
    temporal_mode_src = ast.dump(kw_by_name["temporal_mode"])
    domain_scope_src = ast.dump(kw_by_name["domain_scope"])
    assert "_availability_mode_used" in temporal_mode_src
    assert "_record_domain_scope_used" in domain_scope_src
    # and those local variables are assigned from the real frozen enums, not a re-declared literal
    assigns = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)]
    availability_assign = next(a for a in assigns if any(isinstance(t, ast.Name) and t.id == "_availability_mode_used" for t in a.targets))
    domain_assign = next(a for a in assigns if any(isinstance(t, ast.Name) and t.id == "_record_domain_scope_used" for t in a.targets))
    assert "RETROSPECTIVE_PROXY" in ast.dump(availability_assign.value)
    assert "HISTORICAL_ONLY" in ast.dump(domain_assign.value)


# ---------------------------------------------------------------------------
# 10A1-PROTOCOL-01/02
# ---------------------------------------------------------------------------


def test_10a1_protocol_01_hash_sensitive_to_runtime_data_mode():
    real_hash = geospatial_api_protocol_hash_10a1()
    toy = geospatial_api_protocol_dict_10a1()
    toy["runtime_data_mode"] = "LIVE_OPERATIONAL"  # toy value, never the real constant
    assert _hash_dict(toy) != real_hash


def test_10a1_protocol_02_hash_sensitive_to_availability_and_domain_scope():
    real_hash = geospatial_api_protocol_hash_10a1()
    toy_a = geospatial_api_protocol_dict_10a1()
    toy_a["availability_mode"] = "ACTUAL"
    assert _hash_dict(toy_a) != real_hash

    toy_b = geospatial_api_protocol_dict_10a1()
    toy_b["record_domain_scope"] = "LIVE_ONLY"
    assert _hash_dict(toy_b) != real_hash


# ---------------------------------------------------------------------------
# Part 6: prove the historical 10A identity lacked these semantics
# ---------------------------------------------------------------------------


def test_10a1_gap_01_historical_10a_dict_lacked_runtime_input_semantics():
    historical = geospatial_api_protocol_dict_10a()
    for missing_key in ("active_source_window_days", "availability_mode", "record_domain_scope", "runtime_data_mode"):
        assert missing_key not in historical
    assert HISTORICAL_API_IDENTITY_CLASSIFICATION_10A1 == "HISTORICAL_API_IDENTITY_WITH_RUNTIME_INPUT_SEMANTICS_NOT_YET_BOUND"


# ---------------------------------------------------------------------------
# 10A1-SEM-01/02
# ---------------------------------------------------------------------------


def test_10a1_sem_01_14_days_never_called_biologically_validated():
    for module in (app_service,):
        src = inspect.getsource(module).lower()
        for forbidden in ("biologically validated infectious period", "validated biological window", "biological infectious duration"):
            assert forbidden not in src
    from components.geospatial_tracking.services.integration import geospatial_api_protocol_10a1 as protocol_module

    src = inspect.getsource(protocol_module).lower()
    for forbidden in ("biologically validated infectious period", "validated biological window"):
        assert forbidden not in src


def _string_constant_values(module) -> list[str]:
    """Only real string literals assigned to module-level constants --
    excludes the module docstring and inline comments entirely, so a
    legitimate NEGATED mention ("never real-time epidemiological
    forecasting") in prose documentation never false-positives this
    check. What must be structurally absent is an AFFIRMATIVE claim
    living in an actual constant VALUE (the kind of string that could
    end up in a real API response)."""
    tree = ast.parse(inspect.getsource(module))
    values: list[str] = []
    for node in tree.body:
        target_node = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
        if isinstance(target_node, ast.Constant) and isinstance(target_node.value, str):
            values.append(target_node.value)
    return values


def test_10a1_sem_02_never_described_as_prospective_live_forecasting():
    from components.geospatial_tracking.services.integration import geospatial_api_protocol_10a1 as protocol_module

    for module in (app_service, protocol_module):
        for value in _string_constant_values(module):
            lowered = value.lower()
            for forbidden in ("prospective real-time prediction", "live operational scientific forecasting", "real-time epidemiological forecasting"):
                assert forbidden not in lowered, (module.__name__, value)


# ---------------------------------------------------------------------------
# 10A1-EVIDENCE-01
# ---------------------------------------------------------------------------


def test_10a1_evidence_01_10a_evidence_summary_test_count_reconciled():
    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_10A_API_EVIDENCE_SUMMARY.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    fc = d["final_test_count"]
    assert fc["baseline_before_10a"] == 1489
    assert fc["10a_route_unit_structural_tests"] == 41
    assert fc["10a_evidence_summary_consistency_tests"] == 1
    assert fc["total_after_10a"] == 1531
    assert fc["failed"] == 0
    assert fc["skipped"] == 0
    assert fc["warning_count"] == 1
    assert fc["warning_type"] == "StarletteDeprecationWarning"


# ---------------------------------------------------------------------------
# 10A1-MAIN-01
# ---------------------------------------------------------------------------


def test_10a1_main_01_app_http_integration_verified_safely():
    import main as main_module

    client = TestClient(main_module.app)
    r_root = client.get("/")
    assert r_root.status_code == 200
    r_protocol = client.get("/api/geospatial/protocol")
    assert r_protocol.status_code == 200
    # safe route introspection -- never assumes every route object has `.path`
    paths = [getattr(route, "path", None) for route in main_module.app.routes]
    assert "/" in paths
    non_none = [p for p in paths if p is not None]
    assert len(non_none) >= 1


# ---------------------------------------------------------------------------
# 10A1-SNAPSHOT-01
# ---------------------------------------------------------------------------


def test_10a1_snapshot_01_reuse_status_not_implemented():
    assert RUNTIME_SNAPSHOT_REUSE_STATUS_10A1 == "NOT_IMPLEMENTED_IN_10A1"


# ---------------------------------------------------------------------------
# tracked evidence summary
# ---------------------------------------------------------------------------


def test_10a1_evidence_summary_internally_consistent():
    """Never skips -- tracked evidence summary consistency check."""
    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_10A1_API_OPERATIONAL_SEMANTICS_EVIDENCE_SUMMARY.json"
    assert path.exists(), "CHECKPOINT_10A1_API_OPERATIONAL_SEMANTICS_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = json.loads(path.read_text(encoding="utf-8"))

    assert d["historical_10a_api_protocol_hash"] == _HISTORICAL_10A_HASH
    assert d["active_10a1_api_protocol_hash"] == geospatial_api_protocol_hash_10a1()
    assert d["active_source_window_days"] == 14
    assert d["active_source_window_original_provenance"] == "UNFROZEN_DEVELOPMENT_PARAMETER"
    assert d["runtime_data_mode"] == "HISTORICAL_RETROSPECTIVE_REPLAY"
    assert d["availability_mode"] == "RETROSPECTIVE_PROXY"
    assert d["record_domain_scope"] == "HISTORICAL_ONLY"
    assert d["live_operational_analysis_status"].startswith("NOT_IMPLEMENTED")
    assert d["runtime_snapshot_reuse_status"] == "NOT_IMPLEMENTED_IN_10A1"
    assert d["final_classification"] == (
        "FROZEN_GEOSPATIAL_HISTORICAL_REPLAY_API_WITH_EXPLICIT_RETROSPECTIVE_AND_SOURCE_WINDOW_PROVENANCE_"
        "READY_FOR_REALTIME_TRANSPORT_ENGINEERING"
    )
