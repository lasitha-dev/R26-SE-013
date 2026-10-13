"""Checkpoint 10B.1a: HTTP snapshot identity envelope correction and
true HTTP<->WebSocket snapshot-id proof.

No 7B-9C.1/10A/10A.1/10B/10B.1 research/science rerun. Every parent
hash (10A, 10A.1, historical 10B, historical 10B.1) is verified
unchanged throughout this file."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api import router as router_module
from components.geospatial_tracking.api.router import router as fastapi_router
from components.geospatial_tracking.config import DEFAULT_SQLITE_DB_PATH
from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a import geospatial_api_protocol_hash_10a
from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a1 import geospatial_api_protocol_hash_10a1
from components.geospatial_tracking.services.integration.geospatial_transport_protocol_10b import (
    geospatial_transport_protocol_hash_10b,
)
from components.geospatial_tracking.services.integration.geospatial_transport_protocol_10b1 import (
    geospatial_transport_protocol_hash_10b1,
)
from components.geospatial_tracking.services.integration.geospatial_transport_protocol_10b1a import (
    HISTORICAL_10B1_TRANSPORT_PROTOCOL_HASH,
    HTTP_SNAPSHOT_ENVELOPE_FIELDS_10B1A,
    PREVIOUS_10B_SMOKE_SNAPSHOT_ID_EQUALITY_CHECK_WAS_AN_ORIGIN_ID_PROXY_NOT_A_SERIALIZED_HTTP_SNAPSHOT_ID_CHECK,
    geospatial_transport_protocol_dict_10b1a,
    geospatial_transport_protocol_hash_10b1a,
)
from components.geospatial_tracking.services.transport.geospatial_snapshot_10b import (
    compute_snapshot_with_managed_repository_10b,
)

_HISTORICAL_10A_HASH = "8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716"
_HISTORICAL_10A1_HASH = "e44761319870e9196768599ad88fde237d709c2b17b03f17662ab144bd5634b8"
_HISTORICAL_10B_HASH = "071dbd1baebfa18d30626a39b218287bb25269a0ec1e61b809a955b31191f657"
_HISTORICAL_10B1_HASH = "476a7593aafd4011eec840a7ca60cb339302c037f4e00dd7ba11a239ff153a25"
_ORIGIN = "ORIGIN:Afghanistan:2022-05-29"
_EXPECTED_SNAPSHOT_ID = "cc92c6f716b7c2d04a2f4c18a893e87757876611e1068d9b0c526ae8853e8598"

_DB_PATH = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
_DB_AVAILABLE = _DB_PATH.exists()
_skip_no_db = pytest.mark.skipif(not _DB_AVAILABLE, reason="dev SQLite DB absent (clean clone)")


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
# 10B1A-PARENT-01
# ---------------------------------------------------------------------------


def test_10b1a_parent_01_all_historical_identities_exact():
    assert geospatial_api_protocol_hash_10a() == _HISTORICAL_10A_HASH
    assert geospatial_api_protocol_hash_10a1() == _HISTORICAL_10A1_HASH
    assert geospatial_transport_protocol_hash_10b() == _HISTORICAL_10B_HASH
    assert geospatial_transport_protocol_hash_10b1() == _HISTORICAL_10B1_HASH
    assert HISTORICAL_10B1_TRANSPORT_PROTOCOL_HASH == _HISTORICAL_10B1_HASH


# ---------------------------------------------------------------------------
# 10B1A-ID-01..06
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10b1a_id_01_http_summary_exposes_snapshot_id(app_client):
    r = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary")
    assert r.status_code == 200
    assert "snapshot_id" in r.json()
    assert isinstance(r.json()["snapshot_id"], str) and len(r.json()["snapshot_id"]) == 64


@_skip_no_db
def test_10b1a_id_02_http_cells_exposes_snapshot_id(app_client):
    r = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/cells")
    assert r.status_code == 200
    assert "snapshot_id" in r.json()


@_skip_no_db
def test_10b1a_id_03_http_sources_exposes_snapshot_id(app_client):
    r = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/sources")
    assert r.status_code == 200
    assert "snapshot_id" in r.json()


@_skip_no_db
def test_10b1a_id_04_all_three_http_snapshot_ids_equal(app_client):
    router_module.SNAPSHOT_STORE_10B.clear()
    s1 = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary").json()
    s2 = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/cells").json()
    s3 = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/sources").json()
    assert s1["snapshot_id"] == s2["snapshot_id"] == s3["snapshot_id"]
    assert len(router_module.SNAPSHOT_STORE_10B) == 1  # exactly one underlying scientific compute


@_skip_no_db
def test_10b1a_id_05_http_and_every_ws_frame_share_snapshot_id(app_client):
    router_module.SNAPSHOT_STORE_10B.clear()
    http_summary = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary").json()
    http_cells = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/cells").json()
    http_sources = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/sources").json()
    sid = http_summary["snapshot_id"]
    assert http_cells["snapshot_id"] == sid
    assert http_sources["snapshot_id"] == sid

    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        assert begin["snapshot_id"] == sid
        ws_summary = ws.receive_json()
        assert ws_summary["snapshot_id"] == sid
        assert ws_summary["data"]["snapshot_id"] == sid
        ws_sources = ws.receive_json()
        assert ws_sources["snapshot_id"] == sid
        assert ws_sources["data"]["snapshot_id"] == sid
        for _ in range(begin["n_cell_chunks"]):
            chunk = ws.receive_json()
            assert chunk["snapshot_id"] == sid
        end = ws.receive_json()
        assert end["snapshot_id"] == sid


@_skip_no_db
def test_10b1a_id_06_controlled_afghanistan_snapshot_id_unchanged():
    snapshot = compute_snapshot_with_managed_repository_10b(_ORIGIN)
    assert snapshot.snapshot_id == _EXPECTED_SNAPSHOT_ID


# ---------------------------------------------------------------------------
# 10B1A-GEN-01
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10b1a_gen_01_generated_at_exposed_consistently_never_alters_id(app_client):
    r1 = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary").json()
    r2 = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/cells").json()
    r3 = app_client.get(f"/api/geospatial/analysis/{_ORIGIN}/sources").json()
    for r in (r1, r2, r3):
        assert "generated_at_utc" in r
        assert isinstance(r["generated_at_utc"], str) and len(r["generated_at_utc"]) > 0
    # same cached snapshot -> identical generated_at_utc across all three
    assert r1["generated_at_utc"] == r2["generated_at_utc"] == r3["generated_at_utc"]
    # and the id is unaffected regardless
    assert r1["snapshot_id"] == r2["snapshot_id"] == r3["snapshot_id"] == _EXPECTED_SNAPSHOT_ID


# ---------------------------------------------------------------------------
# 10B1A-INTEGRITY-01/02
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10b1a_integrity_01_valid_snapshot_streams_normally(app_client):
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        begin = ws.receive_json()
        assert begin["type"] == "snapshot_begin"
        ws.receive_json()
        ws.receive_json()
        for _ in range(begin["n_cell_chunks"]):
            ws.receive_json()
        end = ws.receive_json()
        assert end["type"] == "snapshot_end"
        assert end["scientific_content_hash_verified"] is True


@_skip_no_db
def test_10b1a_integrity_02_tampered_snapshot_errors_before_snapshot_begin(app_client, monkeypatch):
    monkeypatch.setattr(router_module, "verify_snapshot_integrity_10b", lambda snapshot: False)
    with app_client.websocket_connect("/api/geospatial/ws") as ws:
        ws.receive_json()  # transport_ready
        ws.send_json({"type": "snapshot_request", "request_id": "r1", "forecast_origin_id": _ORIGIN})
        first_frame = ws.receive_json()
        assert first_frame["type"] == "error"
        assert first_frame["status"] == "SNAPSHOT_CONTENT_INTEGRITY_MISMATCH"
        # nothing else was queued -- confirm no snapshot_begin ever followed
        ws.send_json({"type": "ping", "request_id": "still-alive"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"


# ---------------------------------------------------------------------------
# 10B1A-CONTRACT-01/02
# ---------------------------------------------------------------------------


def test_10b1a_contract_01_binds_http_snapshot_envelope_fields():
    d = geospatial_transport_protocol_dict_10b1a()
    assert set(d["http_snapshot_envelope_fields"]) == set(HTTP_SNAPSHOT_ENVELOPE_FIELDS_10B1A)
    assert "snapshot_id" in d["http_snapshot_envelope_fields"]
    assert "generated_at_utc" in d["http_snapshot_envelope_fields"]
    assert len(d["http_snapshot_envelope_routes"]) == 3
    assert "pre_send_integrity_verification_rule" in d
    assert "http_ws_snapshot_id_equality_rule" in d


def test_10b1a_contract_02_toy_removal_of_snapshot_id_changes_hash():
    real_hash = geospatial_transport_protocol_hash_10b1a()
    toy = geospatial_transport_protocol_dict_10b1a()
    toy["http_snapshot_envelope_fields"] = [f for f in toy["http_snapshot_envelope_fields"] if f != "snapshot_id"]
    assert _hash_dict(toy) != real_hash

    toy2 = geospatial_transport_protocol_dict_10b1a()
    toy2["http_snapshot_envelope_fields"] = ["renamed_snapshot_id" if f == "snapshot_id" else f for f in toy2["http_snapshot_envelope_fields"]]
    assert _hash_dict(toy2) != real_hash


def test_10b1a_previous_smoke_interpretation_documented_not_erased():
    assert PREVIOUS_10B_SMOKE_SNAPSHOT_ID_EQUALITY_CHECK_WAS_AN_ORIGIN_ID_PROXY_NOT_A_SERIALIZED_HTTP_SNAPSHOT_ID_CHECK is True


# ---------------------------------------------------------------------------
# tracked evidence summary
# ---------------------------------------------------------------------------


def test_10b1a_evidence_summary_internally_consistent():
    """Never skips -- tracked evidence summary consistency check."""
    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_10B1A_HTTP_SNAPSHOT_IDENTITY_EVIDENCE_SUMMARY.json"
    assert path.exists(), "CHECKPOINT_10B1A_HTTP_SNAPSHOT_IDENTITY_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = json.loads(path.read_text(encoding="utf-8"))

    assert d["historical_10a_api_protocol_hash"] == _HISTORICAL_10A_HASH
    assert d["active_10a1_api_protocol_hash"] == _HISTORICAL_10A1_HASH
    assert d["historical_10b_transport_protocol_hash"] == _HISTORICAL_10B_HASH
    assert d["historical_10b1_transport_protocol_hash"] == _HISTORICAL_10B1_HASH
    assert d["active_10b1a_transport_protocol_hash"] == geospatial_transport_protocol_hash_10b1a()
    assert d["controlled_snapshot_id"] == _EXPECTED_SNAPSHOT_ID
    assert d["http_snapshot_id_exposure_status"] == "EXPOSED_ON_SUMMARY_CELLS_SOURCES"
    assert d["http_ws_identity_proof_status"] == "TRUE_SNAPSHOT_ID_EQUALITY_PROVEN"
    assert d["pre_send_integrity_verification_status"] == "VERIFIED_BEFORE_ANY_SCIENTIFIC_FRAME"
    assert d["runtime_historical_replay_mode"] == "HISTORICAL_RETROSPECTIVE_REPLAY"
    assert d["live_operational_status"] == "NOT_IMPLEMENTED_NO_ACTUAL_OPERATIONAL_AVAILABILITY_PIPELINE"
    assert d["final_classification"] == (
        "REALTIME_TRANSPORT_BACKEND_LOCKED_WITH_EXPLICIT_HTTP_WEBSOCKET_SNAPSHOT_IDENTITY_READY_FOR_FRONTEND_NOT_LIVE_OPERATIONAL_FORECASTING"
    )
