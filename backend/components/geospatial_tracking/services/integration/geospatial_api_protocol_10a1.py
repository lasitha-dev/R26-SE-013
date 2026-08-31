"""Checkpoint 10A.1 Part 5-6: additive API protocol identity correction.

The historical `geospatial_api_protocol_dict_10a()`
(`geospatial_api_protocol_10a.py`, UNCHANGED by this module) did not
bind the active source window, availability mode, record domain scope,
or runtime data mode -- even though the active source window is
numerically load-bearing (it changes the eligible-source set feeding
C0) and the availability/domain-scope mode determines whether the
analysis is a historical replay or (not yet implemented) live
operational analysis. This is classified
`HISTORICAL_API_IDENTITY_WITH_RUNTIME_INPUT_SEMANTICS_NOT_YET_BOUND` --
never "fraudulent" or "invalid"; it was a genuine, real protocol
identity, just incomplete for these particular runtime-input semantics.

`geospatial_api_protocol_hash_10a1()` is strictly ADDITIVE: it binds
the historical `geospatial_api_protocol_hash_10a()` (verified to
remain exactly `8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716`,
never recomputed differently) plus the parent 9C/9C.1 hashes plus every
missing semantic identified above. No historical hash is changed by
this module.
"""

from __future__ import annotations

import hashlib
import json

from ..application.frozen_geospatial_analysis_10a import (
    ACTIVE_SOURCE_WINDOW_DAYS_10A1,
    ACTIVE_SOURCE_WINDOW_ORIGINAL_PROVENANCE_10A1,
    ACTIVE_SOURCE_WINDOW_RUNTIME_STATUS_10A1,
    AVAILABILITY_MODE_10A1,
    LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1,
    REALTIME_TRANSPORT_STATUS_10A1,
    RECORD_DOMAIN_SCOPE_10A1,
    RUNTIME_DATA_MODE_10A1,
    RUNTIME_SNAPSHOT_REUSE_STATUS_10A1,
)
from .geospatial_api_protocol_10a import (
    CLARITY_NOT_CONFIDENCE_RULE_10A,
    COORDINATE_ORDER_RULE_10A,
    DIRECTION_DESCRIPTIVE_RULE_10A,
    ENVELOPE_VS_REACH_SEPARATION_RULE_10A,
    ERROR_HTTP_STATUS_MAP_10A,
    ERROR_STATUS_TAXONOMY_10A,
    GEOJSON_CRS_RULE_10A,
    NEAREST_SOURCE_GEOMETRIC_ONLY_RULE_10A,
    NOMINAL_REACH_VISUALIZATION_ONLY_RULE_10A,
    RATE_DEVELOPMENT_DERIVED_RULE_10A,
    RATE_SCOPE_CONDITIONING_RULE_10A,
    RAW_C0_NOT_PROBABILITY_RULE_10A,
    RESPONSE_SEMANTIC_FIELD_IDENTITIES_10A,
    STATIC_T0_RISK_RULE_10A,
    geospatial_api_protocol_hash_10a,
)
from .geospatial_intelligence_protocol_9c import integration_protocol_hash_9c
from .nominal_reach_9c import PRIMARY_HORIZON_DAYS_9C
from ..model_development.rate_scope_conditioning_protocol_9c1 import rate_scope_conditioning_protocol_hash_9c1

API_VERSION_10A1 = "10A.1"

# The exact frozen historical value -- verified never to change (10A1-HIST-01).
HISTORICAL_10A_API_PROTOCOL_HASH_10A1 = "8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716"

HISTORICAL_API_IDENTITY_CLASSIFICATION_10A1 = "HISTORICAL_API_IDENTITY_WITH_RUNTIME_INPUT_SEMANTICS_NOT_YET_BOUND"


def geospatial_api_protocol_dict_10a1() -> dict:
    return {
        "api_version": API_VERSION_10A1,
        "historical_10a_api_protocol_hash": geospatial_api_protocol_hash_10a(),
        "historical_api_identity_classification": HISTORICAL_API_IDENTITY_CLASSIFICATION_10A1,
        "integration_protocol_hash_9c": integration_protocol_hash_9c(),
        "rate_scope_conditioning_protocol_hash_9c1": rate_scope_conditioning_protocol_hash_9c1(),
        "active_source_window_days": ACTIVE_SOURCE_WINDOW_DAYS_10A1,
        "active_source_window_original_provenance": ACTIVE_SOURCE_WINDOW_ORIGINAL_PROVENANCE_10A1,
        "active_source_window_runtime_status": ACTIVE_SOURCE_WINDOW_RUNTIME_STATUS_10A1,
        "runtime_data_mode": RUNTIME_DATA_MODE_10A1,
        "availability_mode": AVAILABILITY_MODE_10A1,
        "record_domain_scope": RECORD_DOMAIN_SCOPE_10A1,
        "live_operational_analysis_status": LIVE_OPERATIONAL_ANALYSIS_STATUS_10A1,
        "realtime_transport_status": REALTIME_TRANSPORT_STATUS_10A1,
        "runtime_snapshot_reuse_status": RUNTIME_SNAPSHOT_REUSE_STATUS_10A1,
        "geojson_crs_rule": GEOJSON_CRS_RULE_10A,
        "coordinate_order_rule": COORDINATE_ORDER_RULE_10A,
        "raw_c0_not_probability_rule": RAW_C0_NOT_PROBABILITY_RULE_10A,
        "static_t0_risk_rule": STATIC_T0_RISK_RULE_10A,
        "direction_descriptive_rule": DIRECTION_DESCRIPTIVE_RULE_10A,
        "clarity_not_confidence_rule": CLARITY_NOT_CONFIDENCE_RULE_10A,
        "rate_development_derived_rule": RATE_DEVELOPMENT_DERIVED_RULE_10A,
        "rate_scope_conditioning_rule": RATE_SCOPE_CONDITIONING_RULE_10A,
        "nominal_reach_visualization_only_rule": NOMINAL_REACH_VISUALIZATION_ONLY_RULE_10A,
        "envelope_vs_reach_separation_rule": ENVELOPE_VS_REACH_SEPARATION_RULE_10A,
        "nearest_source_geometric_only_rule": NEAREST_SOURCE_GEOMETRIC_ONLY_RULE_10A,
        "primary_horizon_days": list(PRIMARY_HORIZON_DAYS_9C),
        "response_semantic_field_identities": list(RESPONSE_SEMANTIC_FIELD_IDENTITIES_10A),
        "error_status_taxonomy": list(ERROR_STATUS_TAXONOMY_10A),
        "error_http_status_map": dict(ERROR_HTTP_STATUS_MAP_10A),
    }


def geospatial_api_protocol_hash_10a1() -> str:
    canonical = json.dumps(geospatial_api_protocol_dict_10a1(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
