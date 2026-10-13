"""Checkpoint 10B.1a Part 8: additive active transport CONTRACT
identity -- HTTP snapshot-identity envelope correction.

The Checkpoint 10B.1 active contract
(`geospatial_transport_protocol_hash_10b1()`, UNCHANGED by this
module, now itself treated as a historical/parent identity for this
additive correction) did not bind the HTTP snapshot-identity envelope
fields (`snapshot_id`/`generated_at_utc` on `/summary`, `/cells`,
`/sources`) or the pre-send integrity-verification-timing rule.
`geospatial_transport_protocol_hash_10b1a()` is the newest ACTIVE,
frontend-facing transport contract identity -- it binds the 10B.1 hash
(read-only) plus every fact above. A future frontend should consume
THIS identity.
"""

from __future__ import annotations

import hashlib
import json

from .geospatial_transport_protocol_10b1 import (
    HISTORICAL_10B_TRANSPORT_PROTOCOL_HASH,
    geospatial_transport_protocol_hash_10b1,
)

# Historical facts, never recomputed or superseded.
HISTORICAL_10B1_TRANSPORT_PROTOCOL_HASH = "476a7593aafd4011eec840a7ca60cb339302c037f4e00dd7ba11a239ff153a25"
HISTORICAL_10B1_HASH_CLASSIFICATION_10B1A = "HISTORICAL_10B1_TRANSPORT_CONTRACT_IDENTITY"
ACTIVE_10B1A_HASH_CLASSIFICATION = "ACTIVE_TRANSPORT_PROTOCOL_HASH_FOR_FRONTEND"

# Part 6: the prior Checkpoint 10B smoke print labeled
# "snapshot_id_http_vs_ws_equal" actually compared only
# `analysis_metadata.forecast_origin_id == origin` -- never a
# serialized HTTP `snapshot_id`. Preserved here for provenance, never
# silently erased.
PREVIOUS_10B_SMOKE_SNAPSHOT_ID_EQUALITY_CHECK_WAS_AN_ORIGIN_ID_PROXY_NOT_A_SERIALIZED_HTTP_SNAPSHOT_ID_CHECK = True

# Part 2: HTTP snapshot-identity envelope, now present on all three
# analysis routes. `snapshot_id` is the OUTPUT identity of the frozen
# scientific payload (never a new scientific input, never inside
# `canonical_scientific_payload_10b`); `generated_at_utc` is transport/
# process metadata and never enters `snapshot_id`.
HTTP_SNAPSHOT_ENVELOPE_FIELDS_10B1A = ("snapshot_id", "generated_at_utc")
HTTP_SNAPSHOT_ENVELOPE_ROUTES_10B1A = (
    "GET /api/geospatial/analysis/{forecast_origin_id}/summary",
    "GET /api/geospatial/analysis/{forecast_origin_id}/cells",
    "GET /api/geospatial/analysis/{forecast_origin_id}/sources",
)

HTTP_WS_SNAPSHOT_ID_EQUALITY_RULE_10B1A = (
    "for a reused snapshot: HTTP summary.snapshot_id == HTTP cells.snapshot_id == HTTP sources.snapshot_id == "
    "WS snapshot_begin.snapshot_id == WS summary.snapshot_id == WS sources.snapshot_id == every WS "
    "cells_chunk.snapshot_id == WS snapshot_end.snapshot_id"
)

PRE_SEND_INTEGRITY_VERIFICATION_RULE_10B1A = (
    "verify_snapshot_integrity_10b(snapshot) is evaluated BEFORE any scientific snapshot frame "
    "(snapshot_begin/summary/sources/cells_chunk) is sent over WebSocket -- on failure, only a "
    "SNAPSHOT_CONTENT_INTEGRITY_MISMATCH error frame is sent, never partial scientific data first"
)


def geospatial_transport_protocol_dict_10b1a() -> dict:
    return {
        "historical_10b1_transport_protocol_hash": geospatial_transport_protocol_hash_10b1(),
        "historical_10b1_hash_classification": HISTORICAL_10B1_HASH_CLASSIFICATION_10B1A,
        "historical_10b_transport_protocol_hash": HISTORICAL_10B_TRANSPORT_PROTOCOL_HASH,
        "http_snapshot_envelope_fields": list(HTTP_SNAPSHOT_ENVELOPE_FIELDS_10B1A),
        "http_snapshot_envelope_routes": list(HTTP_SNAPSHOT_ENVELOPE_ROUTES_10B1A),
        "http_ws_snapshot_id_equality_rule": HTTP_WS_SNAPSHOT_ID_EQUALITY_RULE_10B1A,
        "pre_send_integrity_verification_rule": PRE_SEND_INTEGRITY_VERIFICATION_RULE_10B1A,
    }


def geospatial_transport_protocol_hash_10b1a() -> str:
    canonical = json.dumps(geospatial_transport_protocol_dict_10b1a(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
