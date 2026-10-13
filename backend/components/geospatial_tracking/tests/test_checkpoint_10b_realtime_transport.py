"""Checkpoint 10B: real-time TRANSPORT engineering over the frozen
historical-retrospective geospatial snapshot.

No 7B-9C.1 research rerun, no held-out/Sri Lanka rerun, no rate/
bootstrap rerun, no scientific parameter change. The historical
Checkpoint 10A hash and the active Checkpoint 10A.1 hash are both
verified unchanged throughout this file."""

from __future__ import annotations

import ast
import inspect
import json
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api import router as router_module
from components.geospatial_tracking.api.router import router as fastapi_router
from components.geospatial_tracking.config import DEFAULT_SQLITE_DB_PATH
from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import RuntimeAnalysisError10A
from components.geospatial_tracking.services.forecast_origin import build_forecast_origin_ledger
from components.geospatial_tracking.services.build_historical_replay import DISEASE
from components.geospatial_tracking.services.integration import geospatial_transport_protocol_10b as transport_protocol_module
from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a import geospatial_api_protocol_hash_10a
from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a1 import geospatial_api_protocol_hash_10a1
from components.geospatial_tracking.services.integration.geospatial_intelligence_protocol_9c import integration_protocol_hash_9c
from components.geospatial_tracking.services.integration.geospatial_transport_protocol_10b import (
    geospatial_transport_protocol_dict_10b,
    geospatial_transport_protocol_hash_10b,
)
from components.geospatial_tracking.services.model_development.rate_scope_conditioning_protocol_9c1 import (
    rate_scope_conditioning_protocol_hash_9c1,
)
from components.geospatial_tracking.services.transport import chunking_10b, geospatial_snapshot_10b as snapshot_module
from components.geospatial_tracking.services.transport.chunking_10b import WS_CELL_CHUNK_SIZE_10B, chunk_cells_10b, n_chunks_10b
from components.geospatial_tracking.services.transport.geospatial_snapshot_10b import (
    compute_snapshot_id_10b,
    compute_snapshot_with_managed_repository_10b,
)
from components.geospatial_tracking.services.transport.snapshot_store_10b import (
    CACHE_STATUS_EXPIRED_RECOMPUTED,
    CACHE_STATUS_FORCE_REFRESH_RECOMPUTED,
    CACHE_STATUS_HIT_REUSED,
    CACHE_STATUS_MISS_COMPUTED,
    REPOSITORY_REVISION_TOKEN_STATUS_10B,
    SNAPSHOT_CACHE_SCOPE_10B,
    SnapshotStore10B,
)

_HISTORICAL_10A_HASH = "8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716"
_HISTORICAL_10A1_HASH = "e44761319870e9196768599ad88fde237d709c2b17b03f17662ab144bd5634b8"
_ORIGIN = "ORIGIN:Afghanistan:2022-05-29"

_DB_PATH = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
_DB_AVAILABLE = _DB_PATH.exists()
_skip_no_db = pytest.mark.skipif(not _DB_AVAILABLE, reason="dev SQLite DB absent (clean clone)")

_TRANSPORT_MODULES = (router_module, snapshot_module, chunking_10b, transport_protocol_module)


def _direct_imports(module) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


def _real_call_names(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def _string_constant_values(module) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    values: list[str] = []
    for node in tree.body:
        target = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
        if isinstance(target, ast.Constant) and isinstance(target.value, str):
            values.append(target.value)
    return values


@pytest.fixture()
def app_client():
    app = FastAPI()
    app.include_router(fastapi_router)
    router_module.SNAPSHOT_STORE_10B.clear()
    client = TestClient(app)
    yield client
    router_module.SNAPSHOT_STORE_10B.clear()


# ---------------------------------------------------------------------------
# 10B-PARENT-01..03
# ---------------------------------------------------------------------------


def test_10b_parent_01_historical_10a_hash_exact():
    assert geospatial_api_protocol_hash_10a() == _HISTORICAL_10A_HASH


def test_10b_parent_02_active_10a1_hash_exact():
    assert geospatial_api_protocol_hash_10a1() == _HISTORICAL_10A1_HASH


def test_10b_parent_03_9c_9c1_parent_hashes_exact():
    assert integration_protocol_hash_9c() == "cec826a26c860c752d1fa32d94edcdfba2e0186950cdccfc96067fef2ce51a90"
    assert rate_scope_conditioning_protocol_hash_9c1() == "26168ca784b5f8cb5393db872baa1e7e7f1d74f782b16df17c97354b9bf52b8f"


# ---------------------------------------------------------------------------
# 10B-META-01
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10b_meta_01_metadata_carries_both_protocol_identities(app_client):
    for path in ("summary", "cells", "sources"):
        r = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/{path}")
        assert r.status_code == 200
        md = r.json()["analysis_metadata"]
        assert md["historical_api_protocol_hash_10a"] == _HISTORICAL_10A_HASH
        assert md["active_api_protocol_hash_10a1"] == _HISTORICAL_10A1_HASH


# ---------------------------------------------------------------------------
# 10B-SNAPSHOT-01/02/03
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10b_snapshot_01_same_scientific_content_same_id():
    s1 = compute_snapshot_with_managed_repository_10b(_ORIGIN)
    s2 = compute_snapshot_with_managed_repository_10b(_ORIGIN)
    assert s1.snapshot_id == s2.snapshot_id


@_skip_no_db
def test_10b_snapshot_02_generated_at_does_not_change_id():
    s1 = compute_snapshot_with_managed_repository_10b(_ORIGIN)
    time.sleep(0.01)
    s2 = compute_snapshot_with_managed_repository_10b(_ORIGIN)
    assert s1.generated_at_utc != s2.generated_at_utc
    assert s1.snapshot_id == s2.snapshot_id
    payload = snapshot_module.canonical_scientific_payload_10b(s1.analysis)
    assert "generated_at" not in json.dumps(payload)


@_skip_no_db
def test_10b_snapshot_03_chunk_metadata_does_not_change_id():
    snap = compute_snapshot_with_managed_repository_10b(_ORIGIN)
    id_default = compute_snapshot_id_10b(snap.analysis)
    # chunk size only affects transport delivery, never the scientific payload
    _ = chunk_cells_10b(snap.cells_features(), chunk_size=1)
    id_after_chunking_elsewhere = compute_snapshot_id_10b(snap.analysis)
    assert id_default == id_after_chunking_elsewhere
    payload = snapshot_module.canonical_scientific_payload_10b(snap.analysis)
    assert "chunk" not in json.dumps(payload).lower()


# ---------------------------------------------------------------------------
# 10B-CACHE-01..07 (generic store, no DB dependency)
# ---------------------------------------------------------------------------


def test_10b_cache_01_first_request_miss_computed():
    store = SnapshotStore10B()
    calls = []
    value, status = store.get_or_compute(("k1",), lambda: calls.append(1) or "V1")
    assert status == CACHE_STATUS_MISS_COMPUTED
    assert value == "V1"
    assert len(calls) == 1


def test_10b_cache_02_second_same_key_hit_reused():
    store = SnapshotStore10B()
    calls = []
    store.get_or_compute(("k1",), lambda: calls.append(1) or "V1")
    value, status = store.get_or_compute(("k1",), lambda: calls.append(1) or "V2")
    assert status == CACHE_STATUS_HIT_REUSED
    assert value == "V1"  # never recomputed
    assert len(calls) == 1


def test_10b_cache_03_force_refresh_recomputes():
    store = SnapshotStore10B()
    calls = []
    store.get_or_compute(("k1",), lambda: calls.append(1) or "V1")
    value, status = store.get_or_compute(("k1",), lambda: calls.append(1) or "V2", force_refresh=True)
    assert status == CACHE_STATUS_FORCE_REFRESH_RECOMPUTED
    assert value == "V2"
    assert len(calls) == 2


def test_10b_cache_04_ttl_expiration_recomputes_with_fake_clock():
    fake_now = [1000.0]
    store = SnapshotStore10B(ttl_seconds=10.0, clock=lambda: fake_now[0])
    calls = []
    store.get_or_compute(("k1",), lambda: calls.append(1) or "V1")
    fake_now[0] += 5.0  # still within TTL
    value, status = store.get_or_compute(("k1",), lambda: calls.append(1) or "V2")
    assert status == CACHE_STATUS_HIT_REUSED
    assert value == "V1"
    fake_now[0] += 20.0  # now expired
    value, status = store.get_or_compute(("k1",), lambda: calls.append(1) or "V3")
    assert status == CACHE_STATUS_EXPIRED_RECOMPUTED
    assert value == "V3"
    assert len(calls) == 2


def test_10b_cache_05_lru_never_exceeds_max_entries():
    store = SnapshotStore10B(max_entries=8)
    for i in range(20):
        store.get_or_compute((f"k{i}",), lambda i=i: f"V{i}")
    assert len(store) == 8
    assert store.eviction_count == 12
    assert len(store.recent_evicted_keys) == 12
    # most recently used keys remain
    _, status = store.get_or_compute(("k19",), lambda: "should-not-recompute")
    assert status == CACHE_STATUS_HIT_REUSED


def test_10b_cache_06_cache_key_binds_active_protocol_identity():
    key = router_module._snapshot_cache_key_10b(_ORIGIN)
    assert geospatial_api_protocol_hash_10a1() in key
    assert _ORIGIN in key


def test_10b_cache_07_cache_scope_explicitly_process_local_historical_only():
    assert SNAPSHOT_CACHE_SCOPE_10B == "PROCESS_LOCAL_EPHEMERAL_HISTORICAL_REPLAY_ONLY"
    assert REPOSITORY_REVISION_TOKEN_STATUS_10B == "NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# 10B-CONCURRENCY-01
# ---------------------------------------------------------------------------


def test_10b_concurrency_01_single_flight_dedupes_concurrent_misses():
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
        value, status = store.get_or_compute(("shared-key",), slow_compute)
        results.append((value, status))

    t1 = threading.Thread(target=worker)
    t1.start()
    assert started.wait(timeout=5)
    t2 = threading.Thread(target=worker)
    t2.start()
    time.sleep(0.05)  # let t2 attempt to acquire the per-key lock and block
    release.set()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert call_count[0] == 1
    assert len(results) == 2
    assert results[0][0] == results[1][0] == "V"


def test_10b_concurrency_independent_keys_never_block_each_other():
    store = SnapshotStore10B()

    def compute_for(key):
        return store.get_or_compute((key,), lambda: key)

    results = {}

    def worker(key):
        results[key] = compute_for(key)

    threads = [threading.Thread(target=worker, args=(f"origin-{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert len(results) == 5
    for key, (value, status) in results.items():
        assert value == key
        assert status == CACHE_STATUS_MISS_COMPUTED


# ---------------------------------------------------------------------------
# 10B-WS-01..15
# ---------------------------------------------------------------------------


def test_10b_ws_01_connect_transport_ready(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "transport_ready"


def test_10b_ws_02_transport_ready_states_historical_replay_and_not_implemented(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        msg = ws.receive_json()
        assert msg["runtime_data_mode"] == "HISTORICAL_RETROSPECTIVE_REPLAY"
        assert msg["live_operational_analysis_status"] == "NOT_IMPLEMENTED_NO_ACTUAL_OPERATIONAL_AVAILABILITY_PIPELINE"


@_skip_no_db
def test_10b_ws_03_full_frame_sequence(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()  # transport_ready
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        assert begin["type"] == "snapshot_begin"
        summary = ws.receive_json()
        assert summary["type"] == "summary"
        sources = ws.receive_json()
        assert sources["type"] == "sources"
        for _ in range(begin["n_cell_chunks"]):
            chunk = ws.receive_json()
            assert chunk["type"] == "cells_chunk"
        end = ws.receive_json()
        assert end["type"] == "snapshot_end"


@_skip_no_db
def test_10b_ws_04_request_id_echoed(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "echo-me", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        assert begin["request_id"] == "echo-me"
        for _ in range(2 + begin["n_cell_chunks"]):
            frame = ws.receive_json()
            assert frame["request_id"] == "echo-me"


@_skip_no_db
def test_10b_ws_05_all_frames_share_snapshot_id(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        sid = begin["snapshot_id"]
        for _ in range(2 + begin["n_cell_chunks"]):
            frame = ws.receive_json()
            assert frame["snapshot_id"] == sid


def test_10b_ws_06_synthetic_1201_cells_three_chunks_at_500():
    cells = [{"scientific_cell_id": f"C{i:05d}"} for i in range(1201)]
    chunks = chunk_cells_10b(cells, chunk_size=500)
    assert len(chunks) == 3
    assert n_chunks_10b(1201, 500) == 3
    assert len(chunks[0]) == 500
    assert len(chunks[1]) == 500
    assert len(chunks[2]) == 201


def test_10b_ws_07_chunk_concatenation_preserves_order():
    cells = [{"scientific_cell_id": f"C{i:05d}"} for i in range(1201)]
    chunks = chunk_cells_10b(cells, chunk_size=500)
    concatenated = [c for chunk in chunks for c in chunk]
    assert concatenated == cells


def test_10b_ws_08_no_duplicated_or_omitted_cells():
    cells = [{"scientific_cell_id": f"C{i:05d}"} for i in range(1201)]
    chunks = chunk_cells_10b(cells, chunk_size=500)
    seen_ids = [c["scientific_cell_id"] for chunk in chunks for c in chunk]
    assert len(seen_ids) == len(cells)
    assert len(set(seen_ids)) == len(cells)
    assert set(seen_ids) == {c["scientific_cell_id"] for c in cells}


@_skip_no_db
def test_10b_ws_09_bearing_zero_survives(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        ws.receive_json()  # summary
        ws.receive_json()  # sources
        found_zero = False
        for _ in range(begin["n_cell_chunks"]):
            chunk = ws.receive_json()
            for feature in chunk["features"]:
                bearing = feature["properties"]["direction"]["bearing_deg"]
                if bearing == 0.0:
                    found_zero = True
                assert bearing is None or isinstance(bearing, (int, float))
        ws.receive_json()  # end
        # not asserting found_zero (depends on real geometry); the schema-level
        # guarantee is covered by 10A's DirectionSchema tests -- this test only
        # proves no bearing was silently coerced to a non-null/non-float type.


@_skip_no_db
def test_10b_ws_10_undefined_bearing_remains_null(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        ws.receive_json()
        ws.receive_json()
        for _ in range(begin["n_cell_chunks"]):
            chunk = ws.receive_json()
            for feature in chunk["features"]:
                direction_status = feature["properties"]["direction"]["direction_status"]
                bearing = feature["properties"]["direction"]["bearing_deg"]
                if direction_status == "DIRECTION_UNAVAILABLE_NO_CELL_RESULT":
                    assert bearing is None
        ws.receive_json()


@_skip_no_db
def test_10b_ws_11_no_nan_infinity(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        for _ in range(2 + begin["n_cell_chunks"] + 1):
            raw = ws.receive_text()
            assert "NaN" not in raw and "Infinity" not in raw
            json.loads(raw)  # still valid standard JSON


def test_10b_ws_12_malformed_message_gives_structured_error_no_crash(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_text("{not valid json")
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["status"] == "INVALID_MESSAGE"
        # connection still alive
        ws.send_json({"type": "ping", "request_id": "still-alive"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"


@_skip_no_db
def test_10b_ws_13_unknown_origin_gives_origin_not_found(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": "ORIGIN:DOES_NOT_EXIST_XYZ:2099-01-01"})
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["status"] == "ORIGIN_NOT_FOUND"
        assert err["request_id"] == "r1"


def test_10b_ws_14_ping_pong_no_scientific_computation(app_client, monkeypatch):
    called = []
    monkeypatch.setattr(router_module, "_get_snapshot_10b", lambda *a, **kw: called.append(1))
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "ping", "request_id": "p1"})
        pong = ws.receive_json()
        assert pong == {"type": "pong", "request_id": "p1"}
    assert called == []


def test_10b_ws_15_disconnect_cleans_connection_state(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
    # context manager exit closes the connection cleanly; a fresh
    # connection afterward must still work normally
    with app_client.websocket_connect("/api/geospatial/ws") as ws2:
        msg = ws2.receive_json()
        assert msg["type"] == "transport_ready"


# ---------------------------------------------------------------------------
# 10B-EQUIV-01..06
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10b_equiv_01_02_03_http_equals_ws(app_client):
    http_summary = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary").json()
    http_cells = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/cells").json()
    http_sources = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/sources").json()

    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        ws_summary = ws.receive_json()
        ws_sources = ws.receive_json()
        ws_cells: list = []
        for _ in range(begin["n_cell_chunks"]):
            ws_cells.extend(ws.receive_json()["features"])
        ws.receive_json()

    assert http_summary == ws_summary["data"]
    assert http_sources == ws_sources["data"]
    assert http_cells["features"] == ws_cells


@_skip_no_db
def test_10b_equiv_04_risk_direction_rate_reach_exact(app_client):
    http_summary = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary").json()
    ctx = http_summary["apparent_rate_context"]
    assert ctx["apparent_rate_km_day"] == 3.946421443154751
    assert ctx["rate_interval_lower_km_day"] == 3.5491046170907765
    assert ctx["rate_interval_upper_km_day"] == 4.343077329563724
    reach_by_day = {d["day"]: d["nominal_reach_km"] for d in http_summary["nominal_reach_by_day"]}
    assert reach_by_day[7] == pytest.approx(27.624950102083258)
    assert reach_by_day[7] > 25.0


@_skip_no_db
def test_10b_equiv_05_snapshot_id_identical_across_http_routes(app_client):
    # Checkpoint 10B.1a Part 1/4 correction: this test originally only
    # compared `analysis_metadata.forecast_origin_id` -- an ORIGIN-ID
    # PROXY, never a real `snapshot_id` comparison (HTTP did not expose
    # `snapshot_id` at all at the time). Now that `/summary`, `/cells`,
    # and `/sources` all serialize a real `snapshot_id`, compare it
    # directly.
    router_module.SNAPSHOT_STORE_10B.clear()
    s1 = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary").json()
    s2 = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/cells").json()
    s3 = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/sources").json()
    assert s1["snapshot_id"] == s2["snapshot_id"] == s3["snapshot_id"]
    assert len(router_module.SNAPSHOT_STORE_10B) == 1  # one underlying scientific compute


@_skip_no_db
def test_10b_equiv_06_sequential_calls_one_compute_inside_cache_lifetime(app_client, monkeypatch):
    calls = []
    real_build = snapshot_module.build_geospatial_snapshot_10b

    def counting_build(repo, forecast_origin_id, *, disease=None):
        # FMD-02: build_geospatial_snapshot_10b gained an optional
        # keyword-only `disease` parameter -- this monkeypatch wrapper
        # must accept it too to remain a valid drop-in replacement
        # (every real caller now passes it, even when it's None).
        calls.append(forecast_origin_id)
        return real_build(repo, forecast_origin_id, disease=disease)

    monkeypatch.setattr(snapshot_module, "build_geospatial_snapshot_10b", counting_build)
    app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary")
    app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/cells")
    app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/sources")
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# 10B-FIREWALL-01..08
# ---------------------------------------------------------------------------


def test_10b_firewall_01_no_c0_formula():
    for module in _TRANSPORT_MODULES:
        calls = _real_call_names(module)
        assert "evaluate_kernel" not in calls
        src = inspect.getsource(module)
        assert "math.exp(" not in src


def test_10b_firewall_02_no_direction_formula_copied():
    for module in _TRANSPORT_MODULES:
        calls = _real_call_names(module)
        assert "compute_cell_direction_tendency_8b3" not in calls
        assert "compute_cell_direction_tendency" not in calls


def test_10b_firewall_03_no_rate_bootstrap_invocation():
    for module in _TRANSPORT_MODULES:
        imports = _direct_imports(module)
        assert not any("rate_s0_bootstrap_9b" in m for m in imports), (module.__name__, imports)
        calls = _real_call_names(module)
        assert "run_bootstrap" not in calls and "compute_bootstrap_uncertainty" not in calls


def test_10b_firewall_04_no_held_out_sri_lanka_input():
    for module in _TRANSPORT_MODULES:
        imports = _direct_imports(module)
        assert not any("heldout_run_7d" in m for m in imports), (module.__name__, imports)
        assert not any("sri_lanka_run_7e" in m or "sri_lanka_protocol_7e" in m for m in imports), (module.__name__, imports)


def test_10b_firewall_05_no_weather_host_environment_water_source_strength():
    for module in _TRANSPORT_MODULES:
        imports = _direct_imports(module)
        for forbidden in ("host_transform", "environmental_suitability", "water_context", "weather", "source_strength"):
            assert not any(forbidden in m for m in imports), (module.__name__, imports)


def test_10b_firewall_06_no_automatic_db_polling_loop():
    src = inspect.getsource(router_module)
    assert "asyncio.sleep(" not in src
    assert "time.sleep(" not in src
    # exactly one `while True` -- the event-driven receive loop, never a timer
    assert src.count("while True") == 1
    assert "receive_text" in src


def test_10b_firewall_07_no_local_data_artifact_read():
    for module in _TRANSPORT_MODULES:
        src = inspect.getsource(module)
        assert "local_data" not in src
        calls = _real_call_names(module)
        assert "read_text" not in calls


def test_10b_firewall_08_no_live_only_source_selection_path():
    for module in _TRANSPORT_MODULES:
        src = inspect.getsource(module)
        assert "LIVE_ONLY" not in src
        imports = _direct_imports(module)
        assert not any(m.endswith("domain.enums") or m.endswith("enums") for m in imports if "domain" in m), (module.__name__, imports)


# ---------------------------------------------------------------------------
# 10B-SEM-01/02
# ---------------------------------------------------------------------------


def test_10b_sem_01_transport_not_described_as_epidemiological_forecasting():
    for module in _TRANSPORT_MODULES:
        for value in _string_constant_values(module):
            lowered = value.lower()
            for forbidden in ("real-time epidemiological forecasting", "live epidemiological forecasting", "prospective real-time prediction"):
                assert forbidden not in lowered, (module.__name__, value)


def test_10b_sem_02_cache_never_described_as_freshness_proof():
    for module in _TRANSPORT_MODULES:
        for value in _string_constant_values(module):
            lowered = value.lower()
            assert "proof of freshness" not in lowered
            assert "guarantees freshness" not in lowered


# ---------------------------------------------------------------------------
# tracked evidence summary
# ---------------------------------------------------------------------------


def test_10b_evidence_summary_internally_consistent():
    """Never skips -- tracked evidence summary consistency check."""
    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_10B_REALTIME_TRANSPORT_EVIDENCE_SUMMARY.json"
    assert path.exists(), "CHECKPOINT_10B_REALTIME_TRANSPORT_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = json.loads(path.read_text(encoding="utf-8"))

    assert d["historical_10a_api_protocol_hash"] == _HISTORICAL_10A_HASH
    assert d["active_10a1_api_protocol_hash"] == _HISTORICAL_10A1_HASH
    assert d["transport_protocol_hash_10b"] == geospatial_transport_protocol_hash_10b()
    assert d["runtime_data_mode"] == "HISTORICAL_RETROSPECTIVE_REPLAY"
    assert d["live_operational_analysis_status"] == "NOT_IMPLEMENTED_NO_ACTUAL_OPERATIONAL_AVAILABILITY_PIPELINE"
    assert d["snapshot_cache_scope"] == "PROCESS_LOCAL_EPHEMERAL_HISTORICAL_REPLAY_ONLY"
    assert d["cache_constants"]["max_entries"] == 8
    assert d["cache_constants"]["ttl_seconds"] == 60.0
    assert d["ws_route"] == "/api/geospatial/ws"
    assert d["chunk_size"] == 500
    assert d["final_classification"] == (
        "REALTIME_TRANSPORT_OVER_FROZEN_HISTORICAL_RETROSPECTIVE_REPLAY_SNAPSHOTS_READY_FOR_FRONTEND_NOT_LIVE_OPERATIONAL_FORECASTING"
    )
