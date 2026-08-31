# Direction-related code inventory (Checkpoint 8A / 8A.1, Part 3)

Audit only — nothing in this document was changed as production
scoring logic except the two new, isolated, non-predictive readiness
modules listed last (`direction_readiness_8a.py`,
`direction_protocol_8a.py`), which are not imported by, and do not
import, any C0/CW scoring path.

**Checkpoint 8B / 8B.1 / 8B.2 / 8B.3** (the reusable direction-field
SERVICE built on top of this inventory —
`services/direction/{c0_geometric_tendency.py,c0_cell_local_tendency_8b3.py}`
+ `services/model_development/direction_protocol_8b.py` — including
8B.2's analytical proof (later found approximate) and 8B.3's
cell-local tangent-frame correction, `services/geospatial/distance.py::source_to_cell_tangent_at_cell`)
is documented separately in `DIRECTION_8B_PROTOCOL.md` — not
duplicated here.

## `services/geospatial/distance.py`

| Field | Value |
|---|---|
| Function | `source_to_cell_unit_vector(source_lat, source_lon, cell_lat, cell_lon)` |
| Equation | geodesic forward azimuth `az` (WGS84, `pyproj.Geod`) from source to cell; `t_hat_east = sin(az)`, `t_hat_north = cos(az)` |
| Inputs | source lat/lon, cell lat/lon (degrees) |
| Outputs | `distance_km`, `t_hat_east`, `t_hat_north` (dimensionless unit-vector components) |
| Units | km; unit-vector components, no unit |
| Coordinate convention | Geodesic (real ellipsoid), never planar lat/lon distance |
| Orientation | **SOURCE -> CELL**, never the reverse (docstring-enforced, re-verified 8A-GEO-01/02) |
| Temporal semantics | None — pure geometry, time-independent |
| Used by C0? | Yes — every per-source kernel term in `wind_scoring_7c.score_origin_candidates_7c` calls this |
| Scientifically selected? | N/A — geometry, not a fitted parameter |
| Tested? | Yes (existing distance/geometry tests) + 8A-GEO-01/02 (new) |
| Safe to reuse? | Yes |

## `services/geospatial/source_geometry.py`

| Field | Value |
|---|---|
| Functions | `build_geometry_by_source`, `build_geometry_for_grid`, `nearest_source_id` |
| Equation | Thin batching layer over `source_to_cell_unit_vector` — one entry per (cell, source) pair, never collapsed |
| Inputs | `GridCell`, `list[EligibleSourcePoint]` |
| Outputs | `{source_id: SourceToCellVector}` — every eligible source kept individually |
| `nearest_source_id` | Display/reference convenience ONLY, derived from the full per-source dict, never a replacement for it — never used by any scoring path (8A-SOURCE-02 confirms `wind_scoring_7c.py` never references it) |
| Used by C0? | Yes, indirectly (same per-source geometry construction pattern) |
| Tested? | Yes + 8A-SOURCE-01/02 (new) |
| Safe to reuse? | Yes |

## `services/geospatial/weather/wind.py`

| Field | Value |
|---|---|
| Functions | `wind_components_from_speed_direction(speed_m_s, direction_from_deg)`, `wind_speed_from_components(u10, v10)` |
| Equation | `u10 = -speed*sin(direction_from)`, `v10 = -speed*cos(direction_from)` |
| Inputs | speed (m/s), meteorological FROM-direction (degrees clockwise from north) |
| Outputs | `u10` (eastward m/s), `v10` (northward m/s) |
| Coordinate convention | Meteorological FROM-direction on input; standard `u`/`v` eastward/northward components on output — explicitly the OPPOSITE sense from the geodesic source->cell bearing in `distance.py` (module docstring's own warning) |
| Temporal semantics | None — pure unit conversion |
| Used by C0? | No — C0 never reads wind at all |
| Used by CW (wind candidates)? | Indirectly — `u10`/`v10` values themselves come from ERA5 (era5.py), not from this function in the real pipeline; this function is the reverse direction (speed/direction -> components), used for synthetic/test construction |
| Scientifically selected? | N/A — physical unit conversion, not fit |
| Tested? | Yes (WX-01/03) + 8A-WIND-01..05 (new, cardinal/round-trip proofs) |
| Safe to reuse? | Yes, with the FROM/TO distinction respected |

## `services/hazard/anisotropy.py`

| Field | Value |
|---|---|
| Functions | `compute_meteorological_alignment`, `compute_anisotropy_factor` |
| Equation (alignment) | `alignment = t_hat_east*wind_unit_east + t_hat_north*wind_unit_north`, clamped to `[-1,1]` |
| Equation (anisotropy) | `MODULATING: A = exp(kappa*alignment)`; `ANGULAR_NORMALIZED: A = exp(kappa*alignment) / I0(kappa)` |
| Inputs | per-source `t_hat_east`/`t_hat_north`, `WindVector(u10, v10)`, `kappa >= 0`, `mode` |
| Outputs | `alignment` (`[-1,1]` or `None`), `anisotropy_factor` (`>=0`) |
| Zero-wind behavior | `magnitude < 1e-6` -> `alignment=None`, `status=CALM_NEUTRAL`, `anisotropy_factor=1.0` exactly — never a fabricated direction, never a `ZeroDivisionError` |
| Missing-wind behavior | Not this module's concern — caller (`wind_scoring_7c.py`) marks the whole cell `MODEL_INPUT_INCOMPLETE` before ever calling this function when `wind is None` |
| Normalization | `ANGULAR_NORMALIZED` divides by `I0(kappa)` (self-contained Bessel series) so direction-averaged mass stays 1 regardless of `kappa`; `MODULATING` does not normalize — a genuinely different, never-mixed semantic |
| Source-specific before summation? | This module computes ONE source's alignment/factor per call; source-specificity is enforced by the CALLER (`wind_scoring_7c.py`) invoking it once per (source, cell) pair inside its per-source loop, before the `total +=` accumulation — confirmed by direct code read and 8A-SOURCE-02 |
| Used by C0? | No |
| Scientifically selected? | No — `kappa` and `mode` are `UNFROZEN`/audited-only candidates (Checkpoint 7C found all 8 wind candidates `PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE`) |
| Tested? | Yes (ANISO-01..08, `test_hazard_anisotropy.py`) + 8A-WIND-05 (new, calm-wind re-confirmation) |
| Safe to reuse? | Yes, as an audited (not selected) primitive |

## `services/hazard/contracts.py`

| Field | Value |
|---|---|
| Classes | `WindVector(u10, v10)`, `SourceGeometry(source_id, grid_cell_id, distance_km, t_hat_east, t_hat_north)`, `AnisotropyMode(MODULATING, ANGULAR_NORMALIZED)` |
| Note | `WindVector` docstring: "Never converted to/reconstructed from a compass bearing" within the hazard package itself — bearing conversion is a Checkpoint 8A readiness concern (`direction_readiness_8a.py`), never mixed into the hazard contract layer |
| Used by C0? | `WindVector`/`SourceGeometry` types are used by the CW pathway only |
| Safe to reuse? | Yes |

## `services/model_development/wind_scoring_7c.py`

| Field | Value |
|---|---|
| Function | `score_origin_candidates_7c(grid_cells, sources, candidates, wind)` |
| Equation (C0) | `score_i = SUM_j K_EXPONENTIAL(d_j_i; 25km)` |
| Equation (CW) | `score_i = SUM_j [K_EXPONENTIAL(d_j_i; 25km) * A(alignment_j_i, kappa; mode)]` — alignment/anisotropy computed **inside** the per-source loop, accumulated into `total` **before** moving to the next cell — confirmed source-specific-before-summation, no aggregate-then-apply defect found (Part 9 requirement satisfied) |
| Wind resolution | ONE `WindVector` per origin (AOI-center), shared across all sources/cells at that origin — NOT source-specific wind acquisition (real limitation, see `wind_readiness_7c.py` below) |
| Missing wind | `wind is None` -> every CW candidate cell is `MODEL_INPUT_INCOMPLETE` for every cell; C0 entirely unaffected |
| Used by C0? | This module IS the C0/CW scorer |
| Scientifically selected? | C0: yes (frozen). CW: no (never primary-eligible in 7C) |
| Tested? | Yes (7C-MATH-01..05 and others) |
| Safe to reuse? | Yes, unchanged in 8A |

## `services/model_development/candidate_registry_7c.py`

| Field | Value |
|---|---|
| Constants | `ANISOTROPY_STRENGTH_CANDIDATES = (0.25, 0.50, 1.00, 2.00)`, `ANISOTROPY_MODE_CANDIDATES = (MODULATING, ANGULAR_NORMALIZED)` |
| Frozen C0 | `anisotropy_mode=None`, `anisotropy_kappa=None` for the `C0_FAMILY` entry — no directional parameter (re-confirmed, 8A-C0-01) |
| Used by C0? | Defines C0's own spec (with null direction fields) |
| Safe to reuse? | Yes, unchanged |

## `services/model_development/wind_readiness_7c.py`

| Field | Value |
|---|---|
| Function | `resolve_origin_wind(forecast_origin_id, t0, trigger_source_ids_at_t0, sources, weather_cache)` |
| Data source | `services.geospatial.weather.era5.build_pre_t0_weather_summary` — pre-t0 only, `t0_precision=DATE_ONLY` |
| AOI center | Centroid of the origin's own trigger sources (or all eligible sources) — ONE point per origin, reused for every source's alignment computation at that origin |
| Temporal gate | Requires `temporal_role == RETROSPECTIVE_REANALYSIS_STATE_PROXY` exactly; `UNKNOWN` or any other role -> `WEATHER_TEMPORAL_ROLE_UNAVAILABLE`, never admitted as REAL (Checkpoint 7C.1 hardening) |
| Missing wind | `WEATHER_INPUT_UNAVAILABLE` — never replaced with 0 m/s, north, or a previous value |
| Real coverage (7C.1, 579-origin run) | 192/277 (~69.3%) REAL wind; 85/277 (~30.7%) `WEATHER_INPUT_UNAVAILABLE` — all 8 CW candidates `PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE` as a direct result |
| Used by C0? | No — C0 never calls this |
| Safe to reuse? | Yes, as a pre-t0-safe wind resolver, with its real coverage gap explicitly carried forward (Part 18) |

## `services/geospatial/weather/era5.py`

| Field | Value |
|---|---|
| Function | `build_pre_t0_weather_summary`, `_classify_temporal_role` |
| Temporal roles | `RETROSPECTIVE_REANALYSIS_STATE_PROXY` (real, safely pre-t0), `REALIZED_FUTURE_REANALYSIS` (blocked unless `allow_future_reanalysis`, never used by 7C/8A), `UNKNOWN` (blocked before reaching wind resolution) |
| ERA5T sensitivity | `strict_operational_availability=True` applies a 5-day preliminary-release lag filter — an **approximation of** historical operational availability, never real-time operational weather, and never used to select the primary direction/wind method |
| Used by C0? | No |
| Safe to reuse? | Yes, unchanged |

## `services/hazard/source_hazard.py` (Checkpoint 6C general hazard-mix pathway — not the 7C candidate scorer)

| Field | Value |
|---|---|
| Note | Computes per-source `meteorological_alignment`/anisotropy exactly the same way as `wind_scoring_7c.py` (same `compute_meteorological_alignment`/`compute_anisotropy_factor` calls, same `t_hat_east`/`t_hat_north` geometry), but as part of the general `HazardMixConfig` (`H = a*L + b*W`) pathway-mixing framework, which is `UNFROZEN_DEVELOPMENT_CANDIDATE` and not the same code path that produced any frozen 7B-7E result |
| Used by C0? | No |
| Scientifically selected? | No |
| Safe to reuse? | As an audited primitive only, not as a frozen pathway |

## New Checkpoint 8A / 8A.1 readiness modules (not predictive, not wired into any scoring path)

| Field | Value |
|---|---|
| `services/model_development/direction_readiness_8a.py` | `bearing_deg_from_components`, `wind_to_bearing_from_components`, `wind_from_bearing_deg`, `DirectionalMassTerm`, `compute_resultant_vector` — pure math, freezes the Part 6/11-14 conventions, imported by no predictive code |
| `services/model_development/direction_protocol_8a.py` | Frozen semantic constants + `direction_readiness_protocol_hash_8a()` (unchanged, historical) + `direction_readiness_protocol_hash_8a1()` (new, hardened) — binds convention/semantics text only, never a timestamp, never a fitted parameter |
| Used by C0/CW? | No, by design (import graph is one-directional: tests import these two modules; these two modules import `hazard/anisotropy.py`/`hazard/contracts.py` only for shared constants/`reject_non_finite`, never `wind_scoring_7c.py` or any candidate/evaluation module) |
| Tested? | Yes — `tests/test_checkpoint_8a_direction_readiness.py` (26 tests) + `tests/test_checkpoint_8a1_direction_hardening.py` (44 tests), all passing |

### Checkpoint 8A.1 hardening detail

| Field | Value |
|---|---|
| Scale invariance | `compute_resultant_vector` now bases bearing-availability/clarity on `magnitude / total_mass` only — proven invariant under any common positive weight rescaling (`1e-12`..`1e12` tested) |
| Non-finite rejection | `DirectionalMassTerm.__post_init__` and every bearing function call `services.hazard.contracts.reject_non_finite` on every numerical input — no second implementation, no silent NaN-as-zero |
| Unit-vector validation | Usable terms (`distance_km > 0`) validated against `UNIT_VECTOR_NORM_TOLERANCE=1e-6`, fails closed (never renormalizes); zero-distance terms must carry exactly `(0.0, 0.0)` |
| Clarity range guarantee | `[0,1]` proven by construction; only sub-`1e-9` float overshoot clamped, material overshoot raises `ValueError` |
| Calm-wind consistency | `wind_to_bearing_from_components` imports and reuses `hazard.anisotropy.CALM_WIND_EPSILON_M_S` directly (no duplicated literal), same `<` comparison, verified to agree with `compute_meteorological_alignment` at/above/below the boundary |
| Method-A matrix | Restructured into `geometry_definition_status`/`aggregation_framework_status`/`directional_weight_status`/`complete_method_specification_status` — resolves the prior `scientifically_defined=True` vs. `DIRECTION_WEIGHT_NOT_YET_SCIENTIFICALLY_DEFINED` contradiction |
| Hash | Old `direction_readiness_protocol_hash_8a()` verified byte-identical to its historical value; new `direction_readiness_protocol_hash_8a1()` binds the hardened semantics separately |
