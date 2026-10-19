# Geospatial Frontend API Contract (frozen for UI hand-off)

Backend: FastAPI, prefix `/api/geospatial`. Spatial engine `SPATIAL_TIMELINE_ENGINE_1.3`,
contract `SPATIAL_TIMELINE_1.0`. All data is real (MongoDB `adrs_core`, read-only); the UI must
never invent scientific values or geometry.

## Authentication (every endpoint)

`Authorization: Bearer <JWT>` (the host login token, `localStorage.token`). Role must be `vet`.
`401` = no/invalid session · `403` = not a veterinarian (e.g. `daph`). The vet, their district and
their authorised farms are resolved server-side from the token; the client never sends a vet id.

## 1. `GET /operational-context` — the vet's own context

Fields: `status` (`OK`/`NO_ASSIGNED_FARMS`/...), `vet_district`, `farms[]` (assigned),
`surveillance_farms[]` (same-district), `clinical_contexts[]`, `surveillance_contexts[]`,
`surveillance_status`, `generated_at`. Farm: `farm_id, latitude, longitude, location_status
(VALID|LOCATION_REQUIRED), location_district, total_animals (assigned only), personally_assigned`.
Context (vet-verified only): `case_id, farm_id, disease (LSD|FMD), verification_time (UTC ISO
+00:00), case_creation_time`. `409` = operational data unavailable.

## 2. `GET /national-cases` — privacy-reduced national case markers

`records[]`: `record_key` (one-way `CASE:…`), `disease`, `verification_status`
(`VERIFIED`|`PENDING_VERIFICATION` — never "confirmed outbreak"), `reported_at`, `verified_at`
(UTC ISO), `district` (text), `latitude/longitude` (farm GPS or null), `location_status`,
`clinical_summary {severity, stage, model_confidence}`. `summary {returned, mappable,
by_verification_status, by_disease, excluded}`. Records without GPS: list them, never place them.

## 3. `GET /spatial-timeline` — frozen C0 relative score, reach, direction (Day 0–14)

Params: `disease` (`lsd`|`fmd`, required) · `scope` (`district` default | `national`) ·
`district` (optional; must be the vet's own/assigned-farm district unless ALL_DISTRICTS) ·
`as_of` (`YYYY-MM-DD`, Asia/Colombo; default today; never future) · `horizon_days` (0–14).

Top level: `status` · `snapshot_id` (cache/identity; differs per authorised view) · `as_of` ·
`time_window {source_window_start, source_window_end, frame_start, frame_end}` ·
`scope {kind, district, district_geometry (GeoJSON, district scope), boundary_source}` ·
`model` (null fields when no model) · `provenance` (frozen ids/hashes, `engine_version`, `tier_rule`) ·
`sources[]` · `source_exclusions {reason: count}` · `source_statuses {historical, operational}` ·
`source_selection {operational_pool, scope_rule, district_relevance_distance_km, ...}` ·
`tier_thresholds {q1, median, q3}` · `cells[]` · `risk_zones` (FeatureCollection) ·
`source_directions[]` · `district_summaries[]` · `frames[]` · `environment` · `limitations[]`.

- `sources[]`: `source_id` (one-way `OP:<D>:F…` / `HIST:…`, stable), `record_domain`
  (`OPERATIONAL`|`HISTORICAL`), `latitude, longitude, observation_date` (Asia/Colombo),
  `member_count`, `member_record_ids` (raw case ids only for the vet's authorised farms, else
  `CASE:` keys), `farm_id` (authorised only, else null), `detail_access`
  (`AUTHORISED_FARM`|`PRIVACY_REDUCED_EXTERNAL_FARM`), `provenance`
  (`…VET_VERIFIED_DIAGNOSTIC_CASE…` — never an official outbreak).
- `cells[]`: `cell_id` (stable), `centroid`, `raw_c0_score`, `tier` (`lower|moderate|high|highest`
  or null), `tier_status` (`TIERED`|`OFF_LAND_NOT_TIERED`|`NOT_TIERED`), `on_land`, `geometry`
  (scope-clipped polygon; draw THIS, never a client square), `direction {bearing_deg,
  directional_clarity, direction_status}`, `in_scope`.
- `risk_zones.features[]`: `id = "zone:<tier>"`, properties `tier, label, area_km2, semantics`.
  Static for the whole snapshot (C0 does not change by day).
- `frames[d]` (d = 0..horizon): `day, date, horizon_status` (`AS_OF_OBSERVED_CONTEXT` |
  `WITHIN_D1_D7_REACH_HORIZON` | `EXPLORATORY_BEYOND_D7_REACH_HORIZON`), `reach
  {nominal_reach_km, interval_km, rate_km_day}` (null on Day 0 and when no model),
  `reach_envelope` (GeoJSON, clipped to scope), `reach_limited_risk_zones` (features
  `id = "reach:d<day>:<tier>"`, `area_km2` = scored land within reach), `source_corridors[]`
  (`corridor_id = "corridor:d<day>:<source_id>"`, `bearing_deg`, `length_km` ≤ 25 =
  `length_capped_at_km`, `nominal_reach_km`, `geometry` land-clipped), `district_summaries[]`
  (`area_within_reach_km2`, `scored_area_within_reach_km2`, `highest_tier_within_reach`).
- `source_directions[]`: `bearing_deg` null + `INDETERMINATE_NO_DIRECTIONAL_MASS` unless another
  eligible source lies within 25 km (geometric tendency only — never a spread route).
- Statuses: `OK` · `NO_ELIGIBLE_SOURCES` (valid empty state) ·
  `ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY` (FMD: no cells/zones/reach — never LSD values) ·
  `ANALYSIS_UNAVAILABLE_GRID`. HTTP: `422 INVALID_AS_OF_DATE | AS_OF_DATE_IN_FUTURE |
  UNSUPPORTED_DISEASE | INVALID_SCOPE | DISTRICT_REQUIRED`, `403 DISTRICT_NOT_AUTHORISED`,
  `404 DISTRICT_NOT_FOUND`, `409 NO_AUTHORISED_DISTRICT`, `503 OPERATIONAL_DATA_UNAVAILABLE`,
  `500 ANALYSIS_INTERNAL_ERROR`. Headers: `X-Spatial-Timeline-Cache`, `X-Spatial-Timeline-Snapshot`.

## 4. `GET /st-clusters` — ST-DBSCAN (EXPLORATORY)

Params: `disease`, `as_of`. National, privacy-reduced. Fields: `status` (`OK`|`NO_ELIGIBLE_POINTS`),
`evidence_status: EXPLORATORY`, `parameters` (eps_space_km 12.37, eps_time_days 3,
min_core_supports 2, active_window_days 14, `UNFROZEN_DEVELOPMENT_CANDIDATE`, `config_hash`),
`input {operational_case_points, historical_points, distinct_operational_farms}`, `role_counts`,
`cluster_count`, `noise_count`, `noise_locations [[lat, lon]]`, `clusters[] {cluster_id (stable),
member_count, distinct_farm_or_support_count, core/border_member_count, start_date, end_date,
centroid, member_locations[], hull_geometry, member_record_keys[]}`, `operational_exclusions`,
`limitations`. Zero clusters is a valid result.

## 5. `GET /environment` — real ERA5 observations (display only)

Params: `disease`, `scope`, `district`, `as_of` (same as the timeline). Fields: `status`,
`used_in_score: false`, `influence_status: NOT_EXECUTING_NO_SELECTED_ENVIRONMENTAL_MODEL`,
`forecast_context {status: NOT_AVAILABLE}`, `provider`, `model`, `kind:
REANALYSIS_HISTORICAL_NOT_LIVE_WEATHER`, `lookback_hours`, `observations[] {role
(DISTRICT_REFERENCE_POINT | ELIGIBLE_SOURCE_CELL), district, grid_cell {latitude, longitude}
(0.25° ERA5 cell), status, window {window_start, window_end, number_of_hourly_samples, ...},
features[] {feature_name, value, units, status (REAL|MISSING|BLOCKED), analysis_method}}`.
Features: `mean_temperature_2m` (degC), `mean_relative_humidity_2m` (%),
`precipitation_accumulation` (mm), `mean_wind_speed` (m/s), `mean_u10/mean_v10` (m/s),
`vector_resultant_speed`, `directional_persistence` (ratio), `vector_mean_wind_direction_from`
(deg). Recent dates return `MISSING` (ERA5 ~5-day lag) — show as unavailable, never fill.

## 6. `GET /operational-events/stream` — realtime (SSE)

Frames (`event:` name, JSON `data`):
- `ready` `{transport: "delta_refresh", data_version: "ds_…"}` — on (re)connect; if
  `data_version` differs from the client's last-seen value, refetch everything below.
- `heartbeat` `{}` — keep-alive (every 15 s without events).
- `clinical_event` — a vet-verified clinical context on the vet's own/district farms
  (`event_type VERIFIED_CLINICAL_CONTEXT_CREATED|UPDATED`, `case_id`, `farm_id`, `disease`,
  `verified_at`, `deep_link_context`).
- `geospatial_data_changed` — privacy-safe invalidation for EVERY vet: `change` (`CREATED`,
  `VERIFIED`, `UNVERIFIED`, `RECLASSIFIED`, `CORRECTED`, `DELETED`), `record_key`, `disease`,
  `previous_disease`, `verified`, `data_version`, `refetch` (`national-cases`,
  `operational-context`, `spatial-timeline`, `st-clusters`, `environment`).

Server polls `diagnostic_cases` every 15 s (projection only, no images); the first poll primes
silently. Client rule: on `geospatial_data_changed` (or a changed `ready.data_version`) debounce
and refetch the listed endpoints for the CURRENT disease/scope/date; discard responses whose
request scope no longer matches the UI selection; on session change, drop all cached data.

## Frozen scientific constants (do not override in the UI)

C0 = Σ exp(−d/25 km) (`C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8`), 5 km grid, 25 km source
domain, tier = within-snapshot quartiles over scored land cells, S0 = 3.946 km/day
(D1–D7; D8–D14 exploratory), 14-day source window, LSD only (FMD: no spatial model).
