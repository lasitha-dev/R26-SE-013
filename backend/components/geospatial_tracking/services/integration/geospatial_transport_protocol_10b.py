"""Checkpoint 10B Part 19: deterministic transport protocol identity.

Binds the active 10A.1 API protocol hash, the transport version,
runtime data mode, live operational status, the snapshot scientific-
content-hash rule, cache scope/capacity/TTL, the WebSocket cell chunk
size, the message type/version schema, the GeoJSON rule, the HTTP<->WS
equivalence rule, the full error taxonomy, and the no-auto-polling
status into one deterministic hash. Deliberately excludes any
`generated_at`, request/connection id, localhost URL, port, machine
path, actual cache hit/miss outcome, or UI/frontend styling.

Changing `WS_CELL_CHUNK_SIZE_10B` changes THIS hash -- it never changes
`geospatial_snapshot_10b.compute_snapshot_id_10b`'s scientific
`snapshot_id` (10B-SNAPSHOT-03).
"""

from __future__ import annotations

import hashlib
import json

from .geospatial_api_protocol_10a import (
    COORDINATE_ORDER_RULE_10A,
    ERROR_STATUS_TAXONOMY_10A,
    GEOJSON_CRS_RULE_10A,
)
from .geospatial_api_protocol_10a1 import geospatial_api_protocol_hash_10a1
from ..application.frozen_geospatial_analysis_10a import (
    LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1,
    RUNTIME_DATA_MODE_10A1,
)
from ..transport.chunking_10b import CHUNK_PARAMETER_CLASSIFICATION_10B, WS_CELL_CHUNK_SIZE_10B
from ..transport.geospatial_snapshot_10b import SNAPSHOT_SCIENTIFIC_CONTENT_HASH_RULE_10B
from ..transport.snapshot_store_10b import (
    CACHE_PARAMETER_CLASSIFICATION_10B,
    REPOSITORY_REVISION_TOKEN_STATUS_10B,
    SNAPSHOT_CACHE_MAX_ENTRIES_10B,
    SNAPSHOT_CACHE_SCOPE_10B,
    SNAPSHOT_CACHE_TTL_SECONDS_10B,
)

TRANSPORT_VERSION_10B = "10B"

REALTIME_TRANSPORT_MODE_10B = "HISTORICAL_RETROSPECTIVE_REPLAY_SNAPSHOT_TRANSPORT"
REALTIME_TRANSPORT_STATUS_10B = "IMPLEMENTED_FOR_HISTORICAL_RETROSPECTIVE_REPLAY_SNAPSHOTS_ONLY"
RUNTIME_SNAPSHOT_REUSE_STATUS_10B = "IMPLEMENTED_IN_10B"
AUTOMATIC_SCIENTIFIC_UPDATE_STATUS_10B = "NOT_IMPLEMENTED"
NO_AUTO_POLLING_STATEMENT_10B = "NO_AUTOMATIC_SCIENTIFIC_UPDATE_SOURCE_IN_10B"

HTTP_WS_EQUIVALENCE_RULE_10B = (
    "WebSocket is only another DELIVERY mechanism: HTTP summary payload == WS summary payload; "
    "HTTP sources FeatureCollection == WS sources payload; concatenate(WS cells_chunk features in "
    "chunk_index order) == HTTP cells FeatureCollection features, in exactly the same deterministic "
    "order -- no alternate WebSocket-specific formula, normalization, or rounding"
)

WS_MESSAGE_TYPES_INBOUND_10B = ("snapshot_request", "snapshot_refresh", "ping")
WS_MESSAGE_TYPES_OUTBOUND_10B = (
    "transport_ready", "snapshot_begin", "summary", "sources", "cells_chunk", "snapshot_end", "pong", "error",
)

WS_ERROR_STATUS_TAXONOMY_10B = (
    "INVALID_MESSAGE",
    "UNSUPPORTED_MESSAGE_TYPE",
    "INVALID_FORECAST_ORIGIN_ID",
) + ERROR_STATUS_TAXONOMY_10A


def geospatial_transport_protocol_dict_10b() -> dict:
    return {
        "transport_version": TRANSPORT_VERSION_10B,
        "active_api_protocol_hash_10a1": geospatial_api_protocol_hash_10a1(),
        "runtime_data_mode": RUNTIME_DATA_MODE_10A1,
        "live_operational_analysis_status": LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1,
        "realtime_transport_mode": REALTIME_TRANSPORT_MODE_10B,
        "realtime_transport_status": REALTIME_TRANSPORT_STATUS_10B,
        "runtime_snapshot_reuse_status": RUNTIME_SNAPSHOT_REUSE_STATUS_10B,
        "snapshot_scientific_content_hash_rule": SNAPSHOT_SCIENTIFIC_CONTENT_HASH_RULE_10B,
        "snapshot_cache_scope": SNAPSHOT_CACHE_SCOPE_10B,
        "repository_revision_token_status": REPOSITORY_REVISION_TOKEN_STATUS_10B,
        "snapshot_cache_max_entries": SNAPSHOT_CACHE_MAX_ENTRIES_10B,
        "snapshot_cache_ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS_10B,
        "cache_parameter_classification": CACHE_PARAMETER_CLASSIFICATION_10B,
        "ws_cell_chunk_size": WS_CELL_CHUNK_SIZE_10B,
        "chunk_parameter_classification": CHUNK_PARAMETER_CLASSIFICATION_10B,
        "ws_message_types_inbound": list(WS_MESSAGE_TYPES_INBOUND_10B),
        "ws_message_types_outbound": list(WS_MESSAGE_TYPES_OUTBOUND_10B),
        "geojson_crs_rule": GEOJSON_CRS_RULE_10A,
        "coordinate_order_rule": COORDINATE_ORDER_RULE_10A,
        "http_ws_equivalence_rule": HTTP_WS_EQUIVALENCE_RULE_10B,
        "ws_error_status_taxonomy": list(WS_ERROR_STATUS_TAXONOMY_10B),
        "automatic_scientific_update_status": AUTOMATIC_SCIENTIFIC_UPDATE_STATUS_10B,
        "no_auto_polling_statement": NO_AUTO_POLLING_STATEMENT_10B,
    }


def geospatial_transport_protocol_hash_10b() -> str:
    canonical = json.dumps(geospatial_transport_protocol_dict_10b(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
