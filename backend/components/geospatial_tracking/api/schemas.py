"""Checkpoint 10A Part 11: read-only API response schemas.

Pure serialization contracts -- no field here computes a scientific
value; every schema is populated from an already-built
`FrozenGeospatialRuntimeAnalysis10A` (or a frozen protocol/ledger
constant). No field is named `risk_probability`/
`infection_probability`/`accuracy`/`chance_of_infection`/
`direction_confidence`/`transmission_speed`/`disease_velocity` --
`raw_c0_score` and `directional_clarity` carry their semantics as an
explicit sibling field, never folded into the name itself.

Coordinates follow RFC 7946 GeoJSON: `[longitude, latitude]`, EPSG:4326
-- `GeoJSONPointGeometry.coordinates` is a `(longitude, latitude)` tuple,
never the reverse. `scientific_crs` (the component-local AOI-UTM CRS
used internally for area/geometry) is exposed as a SEPARATE field,
never conflated with the WGS84 output coordinates.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

GEOJSON_CRS_10A = "EPSG:4326"
GEOJSON_COORDINATE_ORDER_10A = "[longitude, latitude]"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RiskSchema(_StrictModel):
    raw_c0_score: float | None
    score_status: str
    semantics: str
    risk_surface_temporal_semantics: str


class DirectionSchema(_StrictModel):
    method_id: str | None
    method_version: str | None
    bearing_deg: float | None
    directional_clarity: float | None
    directional_input_coverage: float | None
    direction_status: str
    direction_semantics: str | None


class GeoJSONPointGeometry(_StrictModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]  # (longitude, latitude) -- RFC 7946


class CellFeatureProperties(_StrictModel):
    scientific_cell_id: str
    scientific_crs: str
    risk: RiskSchema
    direction: DirectionSchema


class CellFeature(_StrictModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONPointGeometry
    properties: CellFeatureProperties


class AnalysisMetadataSchema(_StrictModel):
    forecast_origin_id: str
    country: str
    t0: str
    temporal_mode: str
    disease: str
    active_source_window_days: int
    active_source_window_days_label: str
    status: str
    # Checkpoint 10A.1 additive fields (Part 6-7) -- historical replay /
    # source-window provenance made explicit, never silently implied.
    runtime_data_mode: str
    availability_mode: str
    record_domain_scope: str
    active_source_window_original_provenance: str
    active_source_window_runtime_status: str
    live_operational_analysis_status: str
    # Checkpoint 10B Part 1 pre-flight fix -- both protocol identities
    # now appear on every serialized analysis metadata payload
    # (summary/cells/sources), not only on the standalone /protocol
    # response.
    historical_api_protocol_hash_10a: str
    active_api_protocol_hash_10a1: str


class CellFeatureCollection(_StrictModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[CellFeature]
    analysis_metadata: AnalysisMetadataSchema
    geojson_crs: str = GEOJSON_CRS_10A
    coordinate_order: str = GEOJSON_COORDINATE_ORDER_10A
    # Checkpoint 10B.1a Part 2: the transport snapshot IDENTITY envelope
    # -- `snapshot_id` is the OUTPUT identity of the scientific payload
    # (never a new scientific input); `generated_at_utc` is transport/
    # process metadata and never enters `snapshot_id`.
    snapshot_id: str
    generated_at_utc: str


class SourceFeatureProperties(_StrictModel):
    source_id: str
    availability_quality: str
    gps_quality: str
    nearest_source_semantics: str


class SourceFeature(_StrictModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONPointGeometry
    properties: SourceFeatureProperties


class SourceFeatureCollection(_StrictModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[SourceFeature]
    analysis_metadata: AnalysisMetadataSchema
    geojson_crs: str = GEOJSON_CRS_10A
    coordinate_order: str = GEOJSON_COORDINATE_ORDER_10A
    snapshot_id: str
    generated_at_utc: str


class ApparentRateContextSchema(_StrictModel):
    apparent_rate_km_day: float
    apparent_rate_label: str
    rate_interval_lower_km_day: float
    rate_interval_upper_km_day: float
    rate_status: str
    rate_scope: str
    rate_validation_status: str
    sri_lanka_rate_status: str
    rate_estimand_conditioning: str
    conditioning_limitation: str
    conditioning_statement: str
    rate_scope_conditioning_label: str
    lead_dependent_truncation_mechanism_label: str


class NominalReachDaySchema(_StrictModel):
    day: int
    nominal_reach_km: float
    derived_interval_lower_km: float | None
    derived_interval_upper_km: float | None


class AnalysisSummaryResponse(_StrictModel):
    analysis_metadata: AnalysisMetadataSchema
    n_eligible_sources: int
    apparent_rate_context: ApparentRateContextSchema
    nominal_reach_by_day: list[NominalReachDaySchema]
    nominal_reach_semantics: str
    operational_evaluation_envelope_km: float
    provenance: dict
    limitations: list[str]
    snapshot_id: str
    generated_at_utc: str


class OriginSummarySchema(_StrictModel):
    forecast_origin_id: str
    country: str
    t0: str
    trigger_source_count: int


class OriginsResponse(_StrictModel):
    origins: list[OriginSummarySchema]
    n_origins: int


class ProtocolResponse(_StrictModel):
    api_version: str
    historical_api_protocol_hash_10a: str
    active_api_protocol_hash_10a1: str
    integration_protocol_hash_9c: str
    rate_scope_conditioning_protocol_hash_9c1: str
    risk_score_semantics: str
    risk_surface_temporal_semantics: str
    direction_semantics: str
    direction_evaluation_truth_status: str
    rate_status: str
    rate_scope_conditioning_label: str
    nominal_reach_semantics: str
    operational_evaluation_envelope_km: float
    geojson_crs: str
    coordinate_order: str
    primary_horizon_days: list[int]
    error_statuses: list[str]
    limitations: list[str]
    # Checkpoint 10A.1 additive fields (Part 7)
    runtime_data_mode: str
    availability_mode: str
    record_domain_scope: str
    active_source_window_days: int
    active_source_window_original_provenance: str
    active_source_window_runtime_status: str
    live_operational_analysis_status: str
    realtime_transport_status: str
    runtime_snapshot_reuse_status: str
    # Checkpoint 10B additive fields (Part 20)
    transport_version: str
    # Checkpoint 10B/10B.1/10B.1a transport identity chronology -- each
    # is a real, historical fact, never overwritten by the next. A
    # future frontend should consume the newest ACTIVE identity
    # (`active_transport_protocol_hash_10b1a`).
    historical_transport_protocol_hash_10b: str
    historical_transport_protocol_hash_10b1: str
    active_transport_protocol_hash_10b1a: str
    snapshot_cache_scope: str
    repository_revision_token_status: str
    cell_chunk_size: int
    automatic_scientific_update_status: str


# ---------------------------------------------------------------------------
# Checkpoint FMD-09: backend/API integration for the single FMD-08-locked
# frozen RISK model. Deliberately its own response shape, never a variant
# of `AnalysisSummaryResponse`/`CellFeatureCollection` -- those carry an
# LSD-shaped spatial C0/direction/rate contract that FMD's frozen model
# never produced (see `frozen_fmd_risk_analysis_9.py`'s module docstring).
# ---------------------------------------------------------------------------


class FmdRiskAnalysisResponse(_StrictModel):
    forecast_origin_id: str
    country: str
    t0: str
    temporal_mode: str
    disease: str
    status: str
    risk_score: float | None
    risk_score_status: str
    threshold: float
    above_threshold: bool | None
    n_eligible_sources: int
    active_source_window_days: int
    local_evaluation_radius_km: float
    frozen_candidate_id: str
    frozen_model_spec_sha256: str
    risk_score_semantics: str
    risk_task_semantics: str
    limitations: list[str]


# ---------------------------------------------------------------------------
# Checkpoint FMD-10C1: real, OBSERVED historical T0 trigger-source geometry
# for one forecast origin -- disease-neutral (LSD and FMD both resolve
# through the same `/origins` ledger this reuses). Deliberately its own
# response shape, never a variant of `SourceFeatureCollection` (that one is
# gated behind the LSD-shaped `DISEASE_MODEL_READINESS_10A` snapshot
# machinery and still 409s for FMD -- see `frozen_fmd_risk_analysis_9.py`).
# This is a GeoJSON `FeatureCollection` shape for frontend-rendering
# convenience only; `geometry_semantics` on every feature/the envelope
# makes explicit that a point here is an OBSERVED historical trigger
# source -- never a risk cell, forecast point, predicted spread location,
# disease boundary, nominal reach, or trajectory point.
# ---------------------------------------------------------------------------


class TriggerSourceFeatureProperties(_StrictModel):
    source_id: str
    forecast_origin_id: str
    geometry_semantics: str


class TriggerSourceFeature(_StrictModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONPointGeometry
    properties: TriggerSourceFeatureProperties


class OriginTriggerSourcesResponse(_StrictModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[TriggerSourceFeature]
    forecast_origin_id: str
    country: str
    t0: str
    disease: str
    n_points: int
    geometry_semantics: str
    geojson_crs: str = GEOJSON_CRS_10A
    coordinate_order: str = GEOJSON_COORDINATE_ORDER_10A


class ErrorResponse(_StrictModel):
    status: str
    message: str
