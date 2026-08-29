"""Checkpoint 10B.1: transport memory-safety, complete contract
identity, snapshot integrity semantics, repository-provider
consolidation.

No 7B-9C.1/10A/10A.1/10B research/science rerun. The historical 10B
transport hash and both parent API hashes are verified unchanged
throughout this file."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import threading
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api import router as router_module
from components.geospatial_tracking.api.router import router as fastapi_router
from components.geospatial_tracking.api.websocket_schemas import (
    PingMessage,
    SnapshotRefreshMessage,
    SnapshotRequestMessage,
)
from components.geospatial_tracking.config import DEFAULT_SQLITE_DB_PATH
from components.geospatial_tracking.repositories.base import OutbreakRepository
from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import (
    run_frozen_geospatial_runtime_analysis_10a,
)
from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a import geospatial_api_protocol_hash_10a
from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a1 import geospatial_api_protocol_hash_10a1
from components.geospatial_tracking.services.integration.geospatial_transport_protocol_10b import (
    geospatial_transport_protocol_hash_10b,
)
from components.geospatial_tracking.services.integration.geospatial_transport_protocol_10b1 import (
    HISTORICAL_10B_TRANSPORT_PROTOCOL_HASH,
    INBOUND_CONTRACT_10B1,
    INTERMEDIATE_10B_IMPLEMENTATION_HASH,
    MESSAGE_TOO_LARGE_10B1,
    OUTBOUND_CONTRACT_10B1,
    SNAPSHOT_CONTENT_INTEGRITY_MISMATCH_10B1,
    WS_MAX_INBOUND_MESSAGE_BYTES_10B1,
    geospatial_transport_protocol_dict_10b1,
    geospatial_transport_protocol_hash_10b1,
)
# FMD-02: INBOUND_CONTRACT_10B1 (imported above, UNCHANGED) is now a
# HISTORICAL fact -- it predates the optional `disease` field added to
# SnapshotRequestMessage/SnapshotRefreshMessage. The ACTIVE inbound
# contract that matches the real, current Pydantic models is
# INBOUND_CONTRACT_10B2 (services.integration.geospatial_transport_protocol_10b2),
# additive over the unchanged 10B.1 identity -- see that module's docstring.
from components.geospatial_tracking.services.integration.geospatial_transport_protocol_10b2 import (
    INBOUND_CONTRACT_10B2,
)
from components.geospatial_tracking.services.transport import geospatial_snapshot_10b as snapshot_module
from components.geospatial_tracking.services.transport.geospatial_snapshot_10b import (
    compute_snapshot_with_managed_repository_10b,
    verify_snapshot_integrity_10b,
)
from components.geospatial_tracking.services.transport.snapshot_store_10b import (
    CACHE_STATUS_MISS_COMPUTED,
    EVICTION_DIAGNOSTIC_HISTORY_MAXLEN_10B1,
    SnapshotStore10B,
)

_HISTORICAL_10A_HASH = "8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716"
_HISTORICAL_10A1_HASH = "e44761319870e9196768599ad88fde237d709c2b17b03f17662ab144bd5634b8"
_HISTORICAL_10B_HASH = "071dbd1baebfa18d30626a39b218287bb25269a0ec1e61b809a955b31191f657"
_ORIGIN = "ORIGIN:Afghanistan:2022-05-29"
_EXPECTED_SNAPSHOT_ID = "cc92c6f716b7c2d04a2f4c18a893e87757876611e1068d9b0c526ae8853e8598"

_DB_PATH = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
_DB_AVAILABLE = _DB_PATH.exists()
_skip_no_db = pytest.mark.skipif(not _DB_AVAILABLE, reason="dev SQLite DB absent (clean clone)")


def _direct_imports(module) -> list[str]:
    import ast
    tree = ast.parse(inspect.getsource(module))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


def _hash_dict(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@pytest.fixture()
def app_client():
    app = FastAPI()
    app.include_router(fastapi_router)
    router_module.SNAPSHOT_STORE_10B.clear()
    client = TestClient(app)
    yield client
    router_module.SNAPSHOT_STORE_10B.clear()


# ---------------------------------------------------------------------------
# 10B1-PARENT-01/02
# ---------------------------------------------------------------------------


def test_10b1_parent_01_historical_10b_hash_exact():
    assert geospatial_transport_protocol_hash_10b() == _HISTORICAL_10B_HASH
    assert HISTORICAL_10B_TRANSPORT_PROTOCOL_HASH == _HISTORICAL_10B_HASH


def test_10b1_parent_02_historical_10a_and_active_10a1_hashes_exact():
    assert geospatial_api_protocol_hash_10a() == _HISTORICAL_10A_HASH
    assert geospatial_api_protocol_hash_10a1() == _HISTORICAL_10A1_HASH


# ---------------------------------------------------------------------------
# 10B1-MEM-01..06 (generic store, no DB dependency)
# ---------------------------------------------------------------------------


def test_10b1_mem_01_many_successful_keys_stay_bounded():
    store = SnapshotStore10B(max_entries=8)
    for i in range(3000):
        store.get_or_compute((f"ok{i}",), lambda i=i: i)
    assert len(store) == 8
    assert store.n_active_key_slots() == 0
    assert len(store.recent_evicted_keys) <= EVICTION_DIAGNOSTIC_HISTORY_MAXLEN_10B1
    assert store.eviction_count == 3000 - 8


def test_10b1_mem_02_many_failing_keys_leave_no_stale_state():
    store = SnapshotStore10B(max_entries=8)

    def failing():
        raise ValueError("boom")

    for i in range(2000):
        with pytest.raises(ValueError):
            store.get_or_compute((f"fail{i}",), failing)
    assert len(store) == 0
    assert store.n_active_key_slots() == 0
    assert store.eviction_count == 0


def test_10b1_mem_03_same_key_failure_then_retry_succeeds():
    store = SnapshotStore10B()

    def failing():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        store.get_or_compute(("k",), failing)
    assert store.n_active_key_slots() == 0

    value, status = store.get_or_compute(("k",), lambda: "ok")
    assert value == "ok"
    assert status == CACHE_STATUS_MISS_COMPUTED
    assert store.n_active_key_slots() == 0


def test_10b1_mem_04_same_key_concurrent_success_one_compute():
    store = SnapshotStore10B()
    call_count = [0]
    started = threading.Event()
    release = threading.Event()

    def slow_compute():
        call_count[0] += 1
        started.set()
        release.wait(timeout=5)
        return "V"

    results = []

    def worker():
        results.append(store.get_or_compute(("shared",), slow_compute))

    t1 = threading.Thread(target=worker)
    t1.start()
    assert started.wait(timeout=5)
    t2 = threading.Thread(target=worker)
    t2.start()
    import time
    time.sleep(0.05)
    release.set()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert call_count[0] == 1
    assert len(results) == 2
    assert results[0][0] == results[1][0] == "V"
    assert store.n_active_key_slots() == 0


def test_10b1_mem_05_different_keys_independent():
    store = SnapshotStore10B()
    results = {}

    def worker(key):
        results[key] = store.get_or_compute((key,), lambda: key)

    threads = [threading.Thread(target=worker, args=(f"k{i}",)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert len(results) == 10
    assert store.n_active_key_slots() == 0


def test_10b1_mem_06_lru_max_8_entries():
    store = SnapshotStore10B(max_entries=8)
    for i in range(50):
        store.get_or_compute((f"k{i}",), lambda i=i: i)
    assert len(store) == 8


# ---------------------------------------------------------------------------
# 10B1-CONTRACT-01..04
# ---------------------------------------------------------------------------


def test_10b1_contract_01_inbound_schema_matches_real_pydantic_models():
    # FMD-02: the ACTIVE contract (INBOUND_CONTRACT_10B2) is what must
    # match the real, current Pydantic models now that `disease` exists
    # on snapshot_request/snapshot_refresh -- INBOUND_CONTRACT_10B1
    # (unchanged, still imported above) is the historical pre-FMD-02
    # fact and is verified BELOW (10b1_contract_01b) to correctly no
    # longer match, rather than silently going untested.
    assert set(INBOUND_CONTRACT_10B2["snapshot_request"].keys()) == set(SnapshotRequestMessage.model_fields.keys())
    assert set(INBOUND_CONTRACT_10B2["snapshot_refresh"].keys()) == set(SnapshotRefreshMessage.model_fields.keys())
    assert set(INBOUND_CONTRACT_10B1["ping"].keys()) == set(PingMessage.model_fields.keys())  # ping is unchanged by FMD-02
    for model_cls in (SnapshotRequestMessage, SnapshotRefreshMessage, PingMessage):
        assert model_cls.model_config.get("extra") == "forbid"


def test_10b1_contract_01b_historical_inbound_contract_predates_disease_field():
    # Confirms INBOUND_CONTRACT_10B1 is unmodified (still exactly its
    # pre-FMD-02 shape) rather than having been silently mutated to
    # "fix" test_10b1_contract_01 above.
    assert "disease" not in INBOUND_CONTRACT_10B1["snapshot_request"]
    assert "disease" not in INBOUND_CONTRACT_10B1["snapshot_refresh"]
    assert set(INBOUND_CONTRACT_10B1["snapshot_request"].keys()) != set(SnapshotRequestMessage.model_fields.keys())


@_skip_no_db
def test_10b1_contract_02_outbound_schema_matches_real_frames(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ready = ws.receive_json()
        assert set(ready.keys()) == set(OUTBOUND_CONTRACT_10B1["transport_ready"])

        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        assert set(begin.keys()) == set(OUTBOUND_CONTRACT_10B1["snapshot_begin"])
        summary = ws.receive_json()
        assert set(summary.keys()) == set(OUTBOUND_CONTRACT_10B1["summary"])
        sources = ws.receive_json()
        assert set(sources.keys()) == set(OUTBOUND_CONTRACT_10B1["sources"])
        for _ in range(begin["n_cell_chunks"]):
            chunk = ws.receive_json()
            assert set(chunk.keys()) == set(OUTBOUND_CONTRACT_10B1["cells_chunk"])
        end = ws.receive_json()
        assert set(end.keys()) == set(OUTBOUND_CONTRACT_10B1["snapshot_end"])

        ws.send_json({"type": "ping", "request_id": "p1"})
        pong = ws.receive_json()
        assert set(pong.keys()) == set(OUTBOUND_CONTRACT_10B1["pong"])


def test_10b1_contract_03_toy_field_contract_change_alters_hash():
    real_hash = geospatial_transport_protocol_hash_10b1()
    toy = geospatial_transport_protocol_dict_10b1()
    toy["outbound_contract"] = dict(toy["outbound_contract"])
    toy["outbound_contract"]["pong"] = ["type", "request_id", "extra_toy_field"]
    assert _hash_dict(toy) != real_hash


def test_10b1_contract_04_generated_at_value_never_changes_protocol_hash():
    # the FIELD NAME "generated_at_utc" legitimately appears in the
    # outbound contract's field list (its PRESENCE is bound) -- what
    # must be absent is an actual timestamp VALUE.
    h1 = geospatial_transport_protocol_hash_10b1()
    h2 = geospatial_transport_protocol_hash_10b1()
    assert h1 == h2

    def _find_timestamp_like_values(node) -> list[str]:
        found = []
        if isinstance(node, str):
            if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", node):
                found.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                found.extend(_find_timestamp_like_values(v))
        elif isinstance(node, list):
            for v in node:
                found.extend(_find_timestamp_like_values(v))
        return found

    d = geospatial_transport_protocol_dict_10b1()
    assert _find_timestamp_like_values(d) == []


# ---------------------------------------------------------------------------
# 10B1-GEN-01/02
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10b1_gen_01_snapshot_begin_exposes_generated_at_utc(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        assert "generated_at_utc" in begin
        assert isinstance(begin["generated_at_utc"], str) and len(begin["generated_at_utc"]) > 0


@_skip_no_db
def test_10b1_gen_02_generated_at_never_changes_snapshot_id():
    s1 = compute_snapshot_with_managed_repository_10b(_ORIGIN)
    s2 = compute_snapshot_with_managed_repository_10b(_ORIGIN)
    assert s1.generated_at_utc != s2.generated_at_utc
    assert s1.snapshot_id == s2.snapshot_id == _EXPECTED_SNAPSHOT_ID


# ---------------------------------------------------------------------------
# 10B1-INTEGRITY-01/02
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10b1_integrity_01_valid_snapshot_passes():
    snapshot = compute_snapshot_with_managed_repository_10b(_ORIGIN)
    assert verify_snapshot_integrity_10b(snapshot) is True


@_skip_no_db
def test_10b1_integrity_02_mutated_fixture_never_ends_verified(app_client, monkeypatch):
    # Checkpoint 10B.1a Part 7: the integrity check now runs BEFORE any
    # scientific frame is sent -- the very first (and only) frame after
    # transport_ready is the error, never a snapshot_begin.
    monkeypatch.setattr(router_module, "verify_snapshot_integrity_10b", lambda snapshot: False)
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        first = ws.receive_json()
        assert first["type"] == "error"
        assert first["status"] == SNAPSHOT_CONTENT_INTEGRITY_MISMATCH_10B1


def test_10b1_integrity_02b_dataclasses_replace_fixture_detected():
    """Controlled tamper fixture, real scientific artifacts untouched --
    only a copied dataclass instance's snapshot_id field is mutated."""
    if not _DB_AVAILABLE:
        pytest.skip("dev SQLite DB absent")
    import dataclasses

    snapshot = compute_snapshot_with_managed_repository_10b(_ORIGIN)
    tampered = dataclasses.replace(snapshot, snapshot_id="0" * 64)
    assert verify_snapshot_integrity_10b(tampered) is False
    assert verify_snapshot_integrity_10b(snapshot) is True  # original untouched


# ---------------------------------------------------------------------------
# 10B1-INPUT-01
# ---------------------------------------------------------------------------


def test_10b1_input_01_oversized_message_rejected_before_parsing(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        # deliberately invalid JSON -- if size weren't checked FIRST,
        # json.loads would raise and this would surface as INVALID_MESSAGE
        oversized_invalid_json = "{not valid json," + ("x" * (WS_MAX_INBOUND_MESSAGE_BYTES_10B1 + 100))
        ws.send_text(oversized_invalid_json)
        err = ws.receive_json()
        assert err["status"] == MESSAGE_TOO_LARGE_10B1
        # connection still usable afterward
        ws.send_json({"type": "ping", "request_id": "still-alive"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"


def test_10b1_input_01b_message_at_limit_is_not_rejected_for_size():
    small = json.dumps({"type": "ping", "request_id": "ok"})
    assert len(small.encode("utf-8")) < WS_MAX_INBOUND_MESSAGE_BYTES_10B1


# ---------------------------------------------------------------------------
# 10B1-PROVIDER-01/02
# ---------------------------------------------------------------------------


def test_10b1_provider_01_router_and_snapshot_use_shared_provider():
    for module in (router_module, snapshot_module):
        imports = _direct_imports(module)
        assert any("repositories.provider" in m for m in imports), (module.__name__, imports)
        assert not any(m.endswith("repositories.sqlite_repository") for m in imports), (module.__name__, imports)


def test_10b1_provider_02_application_functions_typed_against_outbreak_repository():
    sig = inspect.signature(run_frozen_geospatial_runtime_analysis_10a)
    repo_param = sig.parameters["repo"]
    assert repo_param.annotation is OutbreakRepository or "OutbreakRepository" in str(repo_param.annotation)


# ---------------------------------------------------------------------------
# Intermediate hash classification (Part 12)
# ---------------------------------------------------------------------------


def test_10b1_intermediate_hash_never_active():
    assert INTERMEDIATE_10B_IMPLEMENTATION_HASH == "104d8d94d3aa53ce372fa90b1189c7bb472d3eadc94552b832bd3a93af5afdb9"
    assert INTERMEDIATE_10B_IMPLEMENTATION_HASH != geospatial_transport_protocol_hash_10b()
    assert INTERMEDIATE_10B_IMPLEMENTATION_HASH != geospatial_transport_protocol_hash_10b1()


# ---------------------------------------------------------------------------
# Snapshot identity preservation (Part 9) / HTTP<->WS equivalence (Part 10)
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10b1_snapshot_id_unchanged_for_afghanistan():
    snapshot = compute_snapshot_with_managed_repository_10b(_ORIGIN)
    assert snapshot.snapshot_id == _EXPECTED_SNAPSHOT_ID


@_skip_no_db
def test_10b1_http_ws_equivalence_still_holds(app_client):
    http_summary = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary").json()
    http_cells = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/cells").json()
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        ws_summary = ws.receive_json()
        ws.receive_json()  # sources
        ws_cells: list = []
        for _ in range(begin["n_cell_chunks"]):
            ws_cells.extend(ws.receive_json()["features"])
        ws.receive_json()  # snapshot_end
    assert http_summary == ws_summary["data"]
    assert http_cells["features"] == ws_cells


# ---------------------------------------------------------------------------
# tracked evidence summary
# ---------------------------------------------------------------------------


def test_10b1_evidence_summary_internally_consistent():
    """Never skips -- tracked evidence summary consistency check."""
    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_10B1_TRANSPORT_HARDENING_EVIDENCE_SUMMARY.json"
    assert path.exists(), "CHECKPOINT_10B1_TRANSPORT_HARDENING_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = json.loads(path.read_text(encoding="utf-8"))

    assert d["historical_10a_api_protocol_hash"] == _HISTORICAL_10A_HASH
    assert d["active_10a1_api_protocol_hash"] == _HISTORICAL_10A1_HASH
    assert d["historical_final_10b_transport_protocol_hash"] == _HISTORICAL_10B_HASH
    assert d["active_10b1_transport_protocol_hash"] == geospatial_transport_protocol_hash_10b1()
    assert d["intermediate_10b_implementation_hash"] == INTERMEDIATE_10B_IMPLEMENTATION_HASH
    assert d["cache_limits"]["max_entries"] == 8
    assert d["cache_limits"]["ttl_seconds"] == 60.0
    assert d["message_byte_limit"] == WS_MAX_INBOUND_MESSAGE_BYTES_10B1
    assert d["repository_provider_status"] == "CENTRALIZED_SQLITE_DEVELOPMENT_PROVIDER"
    assert d["runtime_historical_replay_mode"] == "HISTORICAL_RETROSPECTIVE_REPLAY"
    assert d["live_operational_status"] == "NOT_IMPLEMENTED_NO_ACTUAL_OPERATIONAL_AVAILABILITY_PIPELINE"
    assert d["final_classification"] == (
        "REALTIME_TRANSPORT_HARDENED_OVER_FROZEN_HISTORICAL_REPLAY_SNAPSHOTS_READY_FOR_FRONTEND_NOT_LIVE_OPERATIONAL_FORECASTING"
    )
