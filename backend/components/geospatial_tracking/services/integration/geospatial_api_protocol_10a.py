"""Checkpoint 10A Part 17: read-only API protocol identity.

Binds the parent Checkpoint 9C integration protocol hash, the
Checkpoint 9C.1 rate-scope-conditioning protocol hash, the API version,
every response-semantic field identity/rule, the GeoJSON EPSG:4326/
longitude-latitude-order rule, and the D1-D7 primary API reach horizon
into one deterministic hash. Deliberately excludes any localhost URL,
port, `generated_at` timestamp, absolute machine path, or UI styling --
none of those are scientific/API-contract facts.
"""

from __future__ import annotations

import hashlib
import json

from .geospatial_intelligence_protocol_9c import integration_protocol_hash_9c
from .nominal_reach_9c import PRIMARY_HORIZON_DAYS_9C
from ..application.frozen_geospatial_analysis_10a import (
    ANALYSIS_INTERNAL_ERROR_10A,
    ANALYSIS_UNAVAILABLE_GRID_10A,
    ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_10A,
    ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN_10A,
    ORIGIN_NOT_FOUND_10A,
)
from ..model_development.rate_scope_conditioning_9c1 import RATE_SCOPE_CONDITIONING_LABEL_9C1
from ..model_development.rate_scope_conditioning_protocol_9c1 import rate_scope_conditioning_protocol_hash_9c1

API_VERSION_10A = "10A"

GEOJSON_CRS_RULE_10A = "EPSG:4326"
COORDINATE_ORDER_RULE_10A = "[longitude, latitude]"
RAW_C0_NOT_PROBABILITY_RULE_10A = "raw_c0_score is a relative spatial score, never infection_probability/accuracy/chance_of_infection"
STATIC_T0_RISK_RULE_10A = "STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT -- no day-varying C0 surface is fabricated"
DIRECTION_DESCRIPTIVE_RULE_10A = "direction is a descriptive C0-derived cell-local geometric tendency, never predicted/wind/validated-spread/causal direction"
CLARITY_NOT_CONFIDENCE_RULE_10A = "directional_clarity is normalized geometric resultant coherence, never confidence, never aliased direction_confidence"
RATE_DEVELOPMENT_DERIVED_RULE_10A = "apparent rate is DEVELOPMENT_HISTORICAL_APPARENT_RATE_ESTIMATION, never current/predicted outbreak speed, Sri Lanka rate, or transmission velocity"
RATE_SCOPE_CONDITIONING_RULE_10A = RATE_SCOPE_CONDITIONING_LABEL_9C1
NOMINAL_REACH_VISUALIZATION_ONLY_RULE_10A = "VISUALIZATION_ONLY_NOT_HARD_DISEASE_BOUNDARY -- D7 nominal reach may exceed the 25km envelope, never clipped"
ENVELOPE_VS_REACH_SEPARATION_RULE_10A = "operational_evaluation_envelope_km (25.0) and nominal_reach_by_day are always separate fields, never reconciled"
NEAREST_SOURCE_GEOMETRIC_ONLY_RULE_10A = "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE -- never causal_source/transmission_parent/infection_origin"

RESPONSE_SEMANTIC_FIELD_IDENTITIES_10A = (
    "risk.raw_c0_score", "risk.score_status", "risk.semantics", "risk.risk_surface_temporal_semantics",
    "direction.bearing_deg", "direction.directional_clarity", "direction.directional_input_coverage",
    "direction.direction_status", "direction.direction_semantics",
    "apparent_rate_context.apparent_rate_km_day", "apparent_rate_context.rate_interval_lower_km_day",
    "apparent_rate_context.rate_interval_upper_km_day", "apparent_rate_context.rate_status",
    "nominal_reach_by_day.day", "nominal_reach_by_day.nominal_reach_km",
)

ERROR_STATUS_TAXONOMY_10A = (
    ORIGIN_NOT_FOUND_10A,
    ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_10A,
    ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN_10A,
    ANALYSIS_UNAVAILABLE_GRID_10A,
    ANALYSIS_INTERNAL_ERROR_10A,
)

ERROR_HTTP_STATUS_MAP_10A = {
    ORIGIN_NOT_FOUND_10A: 404,
    ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_10A: 409,
    ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN_10A: 409,
    ANALYSIS_UNAVAILABLE_GRID_10A: 409,
    ANALYSIS_INTERNAL_ERROR_10A: 500,
}


def geospatial_api_protocol_dict_10a() -> dict:
    return {
        "api_version": API_VERSION_10A,
        "integration_protocol_hash_9c": integration_protocol_hash_9c(),
        "rate_scope_conditioning_protocol_hash_9c1": rate_scope_conditioning_protocol_hash_9c1(),
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


def geospatial_api_protocol_hash_10a() -> str:
    canonical = json.dumps(geospatial_api_protocol_dict_10a(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
