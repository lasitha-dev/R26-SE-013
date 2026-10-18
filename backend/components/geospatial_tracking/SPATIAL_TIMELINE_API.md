# Spatial Timeline API (`SPATIAL_TIMELINE_1.0`)

`GET /api/geospatial/spatial-timeline` returns a day-indexed (D0..D14) relative spatial-risk snapshot built only
from the frozen, evaluated geospatial models. Code: `services/spatial_timeline/` (engine, sources, service, districts)
and `api/spatial_timeline_router_factory.py`; registered in `backend/main.py`.

## Access
Veterinarian JWT required (`401` without a session, `403` for non-vet roles). The response contains operational
source positions (farm GPS), so it is never public. Operational sources are only the requesting vet's own
authorised cases (assigned farms + registered-district surveillance, `OperationalContextService`).

## Query parameters
| Name | Default | Rules |
|---|---|---|
| `disease` | required | `lsd`, `fmd` or canonical name; unknown -> `422 UNSUPPORTED_DISEASE` |
| `scope` | `district` | `district` or `national` (`422 INVALID_SCOPE` otherwise) |
| `district` | vet's registered district | must be the vet's district, an assigned farm's district, or any district for `ALL_DISTRICTS` accounts -> else `403 DISTRICT_NOT_AUTHORISED`; unknown -> `404 DISTRICT_NOT_FOUND`; none on profile -> `409 NO_AUTHORISED_DISTRICT`; `ALL_DISTRICTS` without a name -> `422 DISTRICT_REQUIRED` |
| `as_of` | today (Asia/Colombo) | ISO date; the source set is fixed at this date. Invalid -> `422 INVALID_AS_OF_DATE`; future -> `422 AS_OF_DATE_IN_FUTURE` |
| `horizon_days` | 14 | 0..14 |

Other errors: `503 OPERATIONAL_DATA_UNAVAILABLE`, `500 ANALYSIS_INTERNAL_ERROR` (never a raw exception).
Response headers: `X-Spatial-Timeline-Snapshot` (snapshot id) and `X-Spatial-Timeline-Cache` (`MISS_COMPUTED` / `HIT_REUSED` / ...).

## Sources (traceable, never invented)
- `HISTORICAL`: scientific repository (MongoDB at runtime) via the frozen 10A eligibility rule
  (`get_eligible_sources`, 14-day window ending at `as_of`, RETROSPECTIVE_PROXY, HISTORICAL_ONLY, Sri Lanka).
- `OPERATIONAL`: vet-verified ADRS cases verified within the same 14-day window, positioned at the validated
  farm GPS. One source per farm and disease (repeat cases are listed in `member_record_ids`, never counted twice).
- An operational farm coordinate outside Sri Lanka (land boundary + ~5.5 km coastal tolerance) -- e.g. a 0,0 default or
  swapped lat/lon -- is excluded as `FARM_COORDINATES_OUTSIDE_SRI_LANKA`, never scored.
- Dropped records are counted in `source_exclusions` by reason; `source_statuses` reports each domain's availability.

## Science (reused, not re-implemented)
- Relative spatial score: `C0(x) = sum_j exp(-d(x, source_j) / 25 km)` on the frozen 5 km scientific grid over
  25 km source buffers (`score_origin_candidates_7c`, candidate `C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8`).
- Tiers: snapshot quartiles of raw C0 (>=Q3 highest, >=median high, >=Q1 moderate, else lower), the same rule as the
  existing Risk Zones map layer. Relative within one snapshot; not probabilities.
- Direction: 8B.3 C0 negative-gradient tendency per cell, and evaluated at each source location (a lone source has no
  directional mass -> `INDETERMINATE_NO_DIRECTIONAL_MASS`, never a fabricated bearing).
- Reach: 9C `nominal_reach_km(d) = 3.946 x d` with the 9B bootstrap interval; D8-D14 extrapolate the D1-D7 formula.
- FMD has no frozen spatial surface -> `status: ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY` (LSD parameters are never reused).

## Response (top level)
`contract_version, status (OK | NO_ELIGIBLE_SOURCES | ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY | ANALYSIS_UNAVAILABLE_GRID),
snapshot_id, disease, disease_code, scope, as_of, horizon_days, evaluated_horizon_days, time_window, model, provenance,
sources[], source_exclusions{}, source_statuses{}, tier_thresholds{q1,median,q3}, cells[], risk_zones (FeatureCollection),
source_directions[], district_summaries[], frames[], environment, limitations[], scientific_domain_id`

- `cells[]`: `cell_id, centroid{longitude,latitude}, raw_c0_score, score_status, tier, domain_overlap_area_km2, direction{bearing_deg, directional_clarity, direction_status}, in_scope`.
- `risk_zones`: one MultiPolygon/Polygon per tier (WGS84, valid, clipped to Sri Lanka land or the district), `properties{tier,label,semantics,area_km2}`. Identical for every day.
- `frames[d]`: `day, date (as_of + d), horizon_status (AS_OF_OBSERVED_CONTEXT | WITHIN_D1_D7_REACH_HORIZON | EXPLORATORY_BEYOND_D7_REACH_HORIZON), active_source_ids, reach{nominal_reach_km, interval_km, rate_km_day, semantics, note}, reach_envelope (geodesic discs, clipped), reach_limited_risk_zones (risk_zones ∩ envelope), source_corridors[] (bearing, length_km, land-clipped LineString), district_summaries[] (area_within_reach_km2, highest_tier_within_reach)`.
- `frames[d].risk_field` (engine 2.2, the Risk Zones surface): the day-d practical field
  `F_d(x) = sum_j exp(-r_j/25 km) * min(g_path_j, g_reach_j)`, display score `1 - exp(-F_d)` on the fixed bands.
  `g_path` = Gaussian tube around the case's day-d spread path (sd = 2.5 km resolution (+) sigma x sqrt(s x S0 x 1 day),
  sigma = circular std of the 3-hour winds met); `g_reach` = the 9C nominal reach S0 x d with the 9B bootstrap
  half-interval as its fringe. Every gate is <= 1, so the field never exceeds the frozen C0; the source set is the
  as-of set on every day (STATIC-T0). `kernels[]` = per-case parameters (`source_id, origin, reach_km, fringe_km,
  spine[[lon, lat, core_km, sd_km]], age_days`); `raster` = the field on a 0.015 deg grid (`window, drawn_cells,
  mask, pixels`; layout in `provenance.risk_field_rule.raster` and `services/spatial_timeline/risk_raster.py`), with
  the score, contributing-case count and top two cases per drawn cell. The map colours only this raster.
- `frames[d].source_paths[]` / `source_paths[]` (engine 3.1, Trajectory): one path per case. Once a day at the front,
  `spread_direction.daily_heading` scores 36 directions by land ahead, FAO GLW4 cattle ahead, the day's NET wind (vector mean of
  24 h; sea/land breezes cancel) and the frozen 8B.3 push of nearby eligible cases, plus the previous course; the heading turns
  gradually within the day and the front moves S0 km/day. Wind and cattle are labelled extensions (7C/7D not selected); rain and
  humidity are not used. A step that would reach the sea ends the day's movement (`heading_basis.held_at_coast`); a path never
  slides along the shore or places a point at sea. `stop_reason`: `REACHED_25KM_LOCAL_DOMAIN` (the evaluated distance) |
  `NO_DIRECTIONAL_EVIDENCE` (no preferred direction at all) | `HORIZON_END`. Per day: `heading_basis` (bearing, confidence, each
  factor), `origin_basis`, `distance_check` (drawn and straight-line km vs the 9C reach and its 9B interval), `plume`.
  `sources_without_path[]` lists cases with no preferred direction, with the reason -- no path is invented for them.
- `district_summaries[]`: per-tier area, scored area, max raw C0 and its tier, cells and sources in the district.
- `environment`: `status: NOT_INTEGRATED, used_in_score: false`, with the candidate ERA5 variables described (no values, no forecasts).

## Caching
In-process `SnapshotStore10B` (TTL 900 s) keyed by the snapshot identity, a SHA-256 over model/engine versions,
disease, scope, as-of date, horizon and the exact authorised source set. A newly verified case changes the key.
Authorisation runs before any cache lookup.

## Interpretation limits
Relative spatial association only: not infection probability, not incidence, not a quarantine/vaccination boundary,
not a predicted case location. Corridors are geometric tendencies, not transmission routes. See `limitations[]`.
