"""Checkpoint 10B.1 Part 4: additive active transport CONTRACT
identity.

The historical `geospatial_transport_protocol_hash_10b()`
(`geospatial_transport_protocol_10b.py`, UNCHANGED by this module,
`= 071dbd1baebfa18d30626a39b218287bb25269a0ec1e61b809a955b31191f657`,
classified `HISTORICAL_FINAL_10B_TRANSPORT_PROTOCOL_HASH`) bound
message TYPES and high-level rules, but not the exact inbound/outbound
message FIELD contract, the WebSocket inbound byte-size limit, or the
`generated_at_utc` field semantic. `geospatial_transport_protocol_hash_10b1()`
is the ACTIVE, frontend-facing transport contract identity -- it binds
the historical 10B hash (read-only, never recomputed differently) plus
every field-level contract fact above. A future frontend should consume
THIS identity, not the historical one.

An earlier intermediate value computed during Checkpoint 10B's own
implementation, `104d8d94d3aa53ce372fa90b1189c7bb472d3eadc94552b832bd3a93af5afdb9`,
is classified `INTERMEDIATE_10B_IMPLEMENTATION_HASH_NOT_FINAL_PROTOCOL`
-- it was superseded within Checkpoint 10B itself (before that
checkpoint's STOP AND REPORT) by the addition of
`runtime_snapshot_reuse_status` to the bound dict, and was never the
historical or active identity. No current API field treats it as
active.
"""

from __future__ import annotations

import hashlib
import json

from .geospatial_api_protocol_10a1 import geospatial_api_protocol_hash_10a1
from .geospatial_transport_protocol_10b import (
    AUTOMATIC_SCIENTIFIC_UPDATE_STATUS_10B,
    NO_AUTO_POLLING_STATEMENT_10B,
    REALTIME_TRANSPORT_MODE_10B,
    REPOSITORY_REVISION_TOKEN_STATUS_10B,
    RUNTIME_SNAPSHOT_REUSE_STATUS_10B,
    SNAPSHOT_CACHE_SCOPE_10B,
    TRANSPORT_VERSION_10B,
    WS_ERROR_STATUS_TAXONOMY_10B,
    geospatial_transport_protocol_hash_10b,
)
from ..application.frozen_geospatial_analysis_10a import LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1, RUNTIME_DATA_MODE_10A1
from ..transport.chunking_10b import WS_CELL_CHUNK_SIZE_10B
from ..transport.snapshot_store_10b import SNAPSHOT_CACHE_MAX_ENTRIES_10B, SNAPSHOT_CACHE_TTL_SECONDS_10B

# Historical facts, never recomputed or superseded (Part 12).
HISTORICAL_10B_TRANSPORT_PROTOCOL_HASH = "071dbd1baebfa18d30626a39b218287bb25269a0ec1e61b809a955b31191f657"
HISTORICAL_10B_HASH_CLASSIFICATION_10B1 = "HISTORICAL_FINAL_10B_TRANSPORT_PROTOCOL_HASH"
INTERMEDIATE_10B_IMPLEMENTATION_HASH = "104d8d94d3aa53ce372fa90b1189c7bb472d3eadc94552b832bd3a93af5afdb9"
INTERMEDIATE_10B_HASH_CLASSIFICATION_10B1 = "INTERMEDIATE_10B_IMPLEMENTATION_HASH_NOT_FINAL_PROTOCOL"
ACTIVE_10B1_HASH_CLASSIFICATION = "ACTIVE_TRANSPORT_PROTOCOL_HASH_FOR_FRONTEND"

WS_MAX_INBOUND_MESSAGE_BYTES_10B1 = 16 * 1024  # 16 KiB
WS_MAX_INBOUND_MESSAGE_CLASSIFICATION_10B1 = "ENGINEERING_TRANSPORT_SAFETY_LIMIT_NOT_SCIENTIFIC_PARAMETER"

MESSAGE_TOO_LARGE_10B1 = "MESSAGE_TOO_LARGE"
SNAPSHOT_CONTENT_INTEGRITY_MISMATCH_10B1 = "SNAPSHOT_CONTENT_INTEGRITY_MISMATCH"

GENERATED_AT_UTC_SEMANTICS_10B1 = (
    "time this immutable runtime snapshot object was generated in this process -- NEVER outbreak "
    "observation time, data freshness time, operational notification time, or scientific t0; the "
    "field's PRESENCE in the message schema participates in this contract hash, its runtime VALUE never does"
)

SCIENTIFIC_CONTENT_HASH_VERIFIED_SEMANTICS_10B1 = (
    "recomputed in-memory via the canonical compute_snapshot_id_10b(snapshot.analysis) and compared "
    "against snapshot.snapshot_id before snapshot_end is ever sent; verifies in-memory transport "
    "consistency ONLY -- NOT cryptographic authenticity, database freshness, or external data "
    "provenance certification. A mismatch produces a SNAPSHOT_CONTENT_INTEGRITY_MISMATCH error frame, "
    "never a snapshot_end claiming verified=true"
)

# Part 4: the exact field contract per inbound message type (Pydantic
# `websocket_schemas.py`, `extra="forbid"`).
INBOUND_CONTRACT_10B1 = {
    "extra_field_policy": "forbid",
    "snapshot_request": {
        "type": "Literal['snapshot_request']",
        "request_id": "str|null, max_length=256, optional",
        "forecast_origin_id": "str, min_length=1, max_length=256, required",
    },
    "snapshot_refresh": {
        "type": "Literal['snapshot_refresh']",
        "request_id": "str|null, max_length=256, optional",
        "forecast_origin_id": "str, min_length=1, max_length=256, required",
    },
    "ping": {
        "type": "Literal['ping']",
        "request_id": "str|null, max_length=256, optional",
    },
}

# Part 4: the exact field SET per outbound frame type.
OUTBOUND_CONTRACT_10B1 = {
    "transport_ready": [
        "type", "transport_version", "transport_protocol_hash_10b", "active_transport_protocol_hash_10b1",
        "runtime_data_mode", "live_operational_analysis_status", "active_api_protocol_hash_10a1",
    ],
    "snapshot_begin": [
        "type", "request_id", "snapshot_id", "forecast_origin_id", "active_api_protocol_hash_10a1",
        "transport_protocol_hash_10b", "active_transport_protocol_hash_10b1", "runtime_data_mode",
        "live_operational_analysis_status", "n_sources", "n_cells", "cell_chunk_size", "n_cell_chunks",
        "cache_status", "generated_at_utc",
    ],
    "summary": ["type", "request_id", "snapshot_id", "data"],
    "sources": ["type", "request_id", "snapshot_id", "data"],
    "cells_chunk": ["type", "request_id", "snapshot_id", "chunk_index", "n_chunks", "features"],
    "snapshot_end": [
        "type", "request_id", "snapshot_id", "n_sources_sent", "n_cells_sent",
        "n_cell_chunks_sent", "scientific_content_hash_verified",
    ],
    "pong": ["type", "request_id"],
    "error": ["type", "request_id", "status", "message"],
}

WS_ERROR_STATUS_TAXONOMY_10B1 = WS_ERROR_STATUS_TAXONOMY_10B + (MESSAGE_TOO_LARGE_10B1, SNAPSHOT_CONTENT_INTEGRITY_MISMATCH_10B1)


def geospatial_transport_protocol_dict_10b1() -> dict:
    return {
        "historical_10b_transport_protocol_hash": geospatial_transport_protocol_hash_10b(),
        "historical_10b_hash_classification": HISTORICAL_10B_HASH_CLASSIFICATION_10B1,
        "transport_version": TRANSPORT_VERSION_10B,
        "active_api_protocol_hash_10a1": geospatial_api_protocol_hash_10a1(),
        "runtime_data_mode": RUNTIME_DATA_MODE_10A1,
        "live_operational_analysis_status": LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1,
        "realtime_transport_mode": REALTIME_TRANSPORT_MODE_10B,
        "runtime_snapshot_reuse_status": RUNTIME_SNAPSHOT_REUSE_STATUS_10B,
        "inbound_contract": INBOUND_CONTRACT_10B1,
        "outbound_contract": OUTBOUND_CONTRACT_10B1,
        "generated_at_utc_semantics": GENERATED_AT_UTC_SEMANTICS_10B1,
        "scientific_content_hash_verified_semantics": SCIENTIFIC_CONTENT_HASH_VERIFIED_SEMANTICS_10B1,
        "ws_cell_chunk_size": WS_CELL_CHUNK_SIZE_10B,
        "ws_max_inbound_message_bytes": WS_MAX_INBOUND_MESSAGE_BYTES_10B1,
        "ws_max_inbound_message_classification": WS_MAX_INBOUND_MESSAGE_CLASSIFICATION_10B1,
        "snapshot_cache_scope": SNAPSHOT_CACHE_SCOPE_10B,
        "repository_revision_token_status": REPOSITORY_REVISION_TOKEN_STATUS_10B,
        "snapshot_cache_max_entries": SNAPSHOT_CACHE_MAX_ENTRIES_10B,
        "snapshot_cache_ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS_10B,
        "ws_error_status_taxonomy": list(WS_ERROR_STATUS_TAXONOMY_10B1),
        "no_auto_polling_statement": NO_AUTO_POLLING_STATEMENT_10B,
        "automatic_scientific_update_status": AUTOMATIC_SCIENTIFIC_UPDATE_STATUS_10B,
    }


def geospatial_transport_protocol_hash_10b1() -> str:
    canonical = json.dumps(geospatial_transport_protocol_dict_10b1(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
