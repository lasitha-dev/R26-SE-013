# Scientific Grid Protocol — Checkpoint 7A / 7A.5 / 7A.6.1 / 7A.6.2

Defines the production-grade `SCIENTIFIC_EVALUATION_GRID` — metric-safe,
AOI-aware, t0-safe by construction — that replaces `build_smoke_grid`
(Checkpoint 5) for all model-development work from Checkpoint 7A onward.
`build_smoke_grid` remains a degree-approximated smoke/test-scale fixture
ONLY; the model-development pipeline (`services/model_development/`) never
imports it (verified structurally by `GRID7A-02`).

## 1. Three spatial concepts (Part 4)

Kept structurally distinct even though this checkpoint implements only the
first:

- **`SCIENTIFIC_EVALUATION_GRID`** — this protocol; used for
  development/validation metrics from 7A onward.
- **`HAZARD_COMPUTATION_GRID`** — future: the real PISTES mathematical
  engine's own grid. May reuse this protocol later; not wired to
  `services/hazard/` in this checkpoint.
- **`DISPLAY_RASTER`** — future: frontend rendering only. A visually denser
  display raster must never create independent scientific evidence.

## 2. Grid resolution != data accuracy (Part 3)

A computational cell size (e.g. 2.5km or 5km) is an ENGINEERING resolution
choice. It never implies GLW4 (~10km), ERA5 (~25km), GPS-precision, or
prediction accuracy at that resolution. Source-resolution metadata is
preserved independently by each adapter (`FeatureResult.dataset_name`,
etc.) and never overwritten by this protocol.

## 3. CRS / metric strategy (`services/geospatial/scientific_grid.py`)

- **Storage/interchange CRS**: WGS84 (`EPSG:4326`) — unchanged from every
  other coordinate in this codebase.
- **Analysis CRS**: AOI-local UTM, chosen from the AOI's own centroid via
  `services.geospatial.crs.analysis_crs_for` (reused unchanged from
  Checkpoint 5) — never one hardcoded EPSG code for the whole system. This
  correctly resolves e.g. Sri Lanka to UTM 44N and Thailand to UTM 47N/48N,
  and was verified across 5 real countries during the 7A audit (Afghanistan
  EPSG:32642, Bangladesh EPSG:32646, Russian Federation EPSG:32639, Bhutan
  EPSG:32645 — see `local_data/model_development/scientific_grid_audit.json`).
- Grid cells are REAL square `shapely` polygons built in that UTM
  projection (meters), never approximated in degrees — `area_km2` is a
  genuine planar-metric area (`polygon.area / 1e6`). Verified real-data
  spot check: every sampled cell (Afghanistan/Bangladesh/Russia/Bhutan,
  spanning ~24N to ~60N+) reported `area_km2` exactly matching
  `cell_size_km^2` (25.0 km² for a 5km cell) — a naive degrees-squared
  approximation would have varied sharply with latitude instead.

## 4. `ScientificGridConfig`

Every field is feature/model-affecting and participates in
`scientific_grid_config_hash()` (never `generated_at`):

| field | meaning |
|---|---|
| `cell_size_km` | computational/engineering resolution |
| `domain_mode` | `SOURCE_BUFFER_UNION_TRUE_DOMAIN` (7A.5 — renamed from 7A's `..._BOUNDING_BOX`; see §10) |
| `domain_distance_km` | the evaluation-domain extent parameter (see `MODEL_DEVELOPMENT_PROTOCOL.md`) |
| `crs_strategy` | `AOI_LOCAL_UTM` |
| `geometry_version` | `7A.5.1` |
| `parameter_status` | `UNFROZEN_DOMAIN_CANDIDATE` until a domain rule is frozen |
| `projection_tolerance_version` | `7A.5.1` (7A.5 — see §11) |

## 5. T0-safety (Part 6)

`build_source_buffer_union_domain`/`build_scientific_grid` accept ONLY
eligible active-source coordinates and a predeclared `domain_distance_km`.
Neither function's signature has any parameter that could carry a future
target coordinate, envelope, or centroid at all — enforced structurally
(`DOMAIN-01`, verified by inspecting every function actually defined in
`scientific_grid.py`).

## 6. Domain construction (Parts 1, 9) — corrected in 7A.5, see §10

`build_source_buffer_union_domain(sources, domain_distance_km)`:

1. Centers the AOI on the unweighted centroid of ALL eligible active
   sources (never just the nearest/trigger source).
2. Buffers each source by `domain_distance_km` in that single AOI-wide UTM
   projection and unions the buffers (`shapely.ops.unary_union`) — a
   `PROJECTED_METRIC_BUFFER_UNION` (7A.5 Part 16 — never called "geodesic";
   see §11).
3. **(7A.5 correction — see §10)** Grid tiling no longer uses the
   rectangular bounding box of that union. The ACTUAL union geometry is
   preserved (`DomainGeometry.union_geometry` in-process,
   `union_geometry_digest` for identity) and tiled component-by-component.
   `bounding_box_area_km2()` remains available as a legacy comparison
   figure only — never used for grid construction.
4. `domain_geometry_digest` is a deterministic SHA256 over the sorted
   source ids/coordinates + `domain_distance_km` + `domain_mode`.

## 7. Grid tiling and cell identity — corrected in 7A.5, see §10

`build_scientific_grid(domain, config)` tiles EACH true-domain component's
own local bounding box with real square cells of edge `cell_size_km`,
keeps ONLY cells with positive intersection against that component,
transforms each cell centroid back to WGS84, and assigns `grid_cell_id`
deterministically from `(component_index, row, col)` — never insertion
order.

`ScientificGridSnapshot` (Part 14, extended 7A.5 Part 11) is the full
per-origin identity: `grid_snapshot_id` is a SHA256 over
`forecast_origin_id`, `t0`, sorted `active_source_ids`,
`domain_geometry_digest`, **`union_geometry_digest`**, `domain_mode`,
`domain_distance_km`, `cell_size_km`, `crs_strategy`, SORTED `cell_ids`,
`cell_count`, `total_area_km2`, `total_domain_overlap_area_km2`, and
`scientific_grid_config_hash` — `generated_at` never participates.
Verified: identical inputs produce an identical id (`GRID7A-03`,
`TRUEGRID-06`); a changed cell size or domain distance changes it
(`GRID7A-04/05`); cell/source-id/MultiPolygon-component ORDERING never
changes it (`GRID7A-10`, `TRUEGRID-07`).

## 8. Real-data engineering finding (Checkpoint 7A, superseded by 7A.5's local-context correction)

The real 7A audit found that unioning buffers around EVERY COUNTRY-ELIGIBLE
active source produced very large bounding boxes when a forecast origin's
sources were geographically dispersed. Checkpoint 7A.5 addresses the root
cause at the SOURCE level (`LOCAL_FORECAST_CONTEXT`, trigger-anchored —
see `MODEL_DEVELOPMENT_PROTOCOL.md`) rather than only the grid-tiling
level — real local contexts are far smaller than 7A's country-wide source
sets. See `MODEL_DEVELOPMENT_PROTOCOL.md` for the resulting real counts.

## 9. Test coverage

`GRID7A-01..10` (`tests/test_scientific_grid.py`) + `DOMAIN-01`/`DOMAIN-05`
structural checks; `TRUEGRID-01..08`/`CRS7A5-01..05`
(`tests/test_true_domain_grid.py`, Checkpoint 7A.5). All pass against both
synthetic fixtures and real multi-country data executed during the audits.

## 10. Checkpoint 7A.5 — true-domain grid masking (Parts 10-15)

**The gap**: 7A's `build_scientific_grid` tiled the COMPLETE rectangular
bounding box of the source-buffer union — including empty space between
geographically disconnected source-buffer components, and the "corner"
gaps between a circular buffer and its own bounding square. That
rectangular tiling was never actually the true evaluation domain.

**The fix**: the TRUE evaluation domain is the buffer union itself.
`DomainGeometry` now preserves the ACTUAL union geometry (not just its
bounds) via an in-process `union_geometry` object plus a deterministic,
MultiPolygon-component-order-independent `union_geometry_digest`
(`union_geometry_digest()`, canonicalized by rounding UTM coordinates to
millimeter precision and sorting components before hashing — a documented
SOFTWARE numerical tolerance for the identity digest only, never for any
returned area/coordinate value). If the union is a `MultiPolygon`
(geographically disconnected source groups — e.g. two independent trigger
situations), each component is tiled INDEPENDENTLY over its own local
bounding box — never one rectangle spanning every component, which would
silently fill the gap between disconnected outbreak situations with grid
cells (`TRUEGRID-02`). A cell is only ever returned if it has POSITIVE
intersection area with the true domain (`domain_overlap_area_km2 > 0`,
`TRUEGRID-01/04`) — this is enforced structurally inside
`build_scientific_grid` (a filter before `cells.append(...)`), not a flag
a caller could ignore. `ScientificGridCell.area_km2` still reports the
FULL square-cell area (an unchanged engineering fact); the new
`domain_overlap_area_km2`/`domain_overlap_fraction` fields report exactly
how much of that square lies inside the true domain — an edge cell is
never silently treated as though it were fully inside (Part 13). The sum
of every returned cell's `domain_overlap_area_km2` reproduces the domain's
true `union_area_km2` within a 1% documented geometry tolerance
(`TRUEGRID-03`, verified against real fine-grained tiling).

## 11. Checkpoint 7A.5 — projection-safety hardening (Parts 16-18)

**Terminology correction (Part 16)**: every buffer here is built by
projecting a source point into a local UTM CRS and buffering there —
`BUFFER_METHOD_PROJECTED_METRIC_UNION`. It is NEVER a "geodesic buffer
union" (which would trace constant geodesic distance on the ellipsoid
itself); no docstring or label in this module uses that term
(`CRS7A5-01`).

**The gate (Parts 17-18)**: `assess_projection_safety` computes REAL
diagnostics for every domain — max pairwise geodesic distance among its
sources, UTM zones touched, and (the actual gate) the measured relative
distortion between real WGS84 geodesic distance and the projected planar
distance for the domain's own most widely separated source pair — compared
against a PREDECLARED SOFTWARE geometry tolerance
(`PROJECTION_DISTORTION_REL_TOL = 0.01`, i.e. 1%, versioned as
`PROJECTION_TOLERANCE_VERSION = "7A.5.1"`, never retuned using predictive
performance). A compact, genuinely local source group passes trivially
(`CRS7A5-02`, verified real-data: single/near-source local contexts from
the real audit all report `PROJECTION_CONTEXT_SAFE` with near-zero
distortion). An artificially wide multi-zone source spread — verified with
a real ~4,000km-East-West synthetic case spanning multiple UTM zones —
correctly reports `PROJECTION_CONTEXT_UNSAFE` (`CRS7A5-03`), and
`build_scientific_grid` REFUSES (`ValueError`) to tile an unsafe domain —
never silently continuing with a distorted grid (Part 18's "OR" clause:
this checkpoint chooses to BLOCK an unsafe context rather than implement an
automatic alternative local-projection fallback, since real
trigger-anchored local contexts are expected to be tight and rarely
approach the tolerance in practice — confirmed by the real audit, see
`MODEL_DEVELOPMENT_PROTOCOL.md`). Both `crs_strategy` and
`projection_tolerance_version` participate in `scientific_grid_config_hash()`
(`CRS7A5-04/05`).

## 12. Checkpoint 7A.6.1 — one origin, one CRS was itself unsafe; geodesic componentization corrects it

**The gap**: everything in §1-11 above still assumed ONE forecast
origin's ENTIRE eligible-source set could share ONE AOI-local UTM CRS
(chosen from their combined mean coordinate). The real Checkpoint 7A.6
audit found 9 real origins where that assumption was itself
`PROJECTION_CONTEXT_UNSAFE` — a country can easily have eligible active
sources scattered far enough apart that no single UTM zone represents
them all safely.

**The fix**: new `services/geospatial/scientific_domain.py`. Sources are
first grouped into `SCIENTIFIC_DOMAIN_COMPONENTS` via a geodesic
connectivity graph (edge iff real distance `<= 50km = 2 x 25km`, since
two 25km buffers can only touch within that separation) — purely
computational geometry, never ST-DBSCAN. EACH component then gets its
OWN local CRS from ONLY its own sources
(`services.geospatial.crs.analysis_crs_for`, reused unchanged) and its
own `DomainGeometry`/grid, built via the UNCHANGED §1-11 primitives
(`build_source_buffer_union_domain`/`build_scientific_grid`) applied at
component scope. A `ScientificEvaluationDomain` aggregates components
for one origin but never claims a global CRS/bounds/geometry of its own.
A component additionally requires passing a NEW buffer-radial distortion
check (8 real geodesic test points at 25km from each source, compared
against their own projected planar distance, same 1% tolerance) before
being `is_safe` — source-source distance safety alone was not sufficient
proof the 25km BUFFER itself was well-represented.

**Real result**: 0 of 3,147 real components across all 579 real
`FIT_DEVELOPMENT` origins were unsafe (max real distortion 0.151%
source-source, 0.165% buffer-radial) — see
`MODEL_DEVELOPMENT_PROTOCOL.md` §42 for the full real audit.

**Buffers built this way are `PROJECTION_SAFE_PROJECTED_APPROXIMATION_OF_25KM_GEODESIC_ENVELOPE`
— never "exact geodesic buffers."** Primary scientific SCOPE truth
(`services.model_development.local_evaluation_scope.classify_target_primary_scope`)
is computed directly from real WGS84 geodesic distance and never
depends on this projected grid geometry at all — see
`MODEL_DEVELOPMENT_PROTOCOL.md` §38.

## 13. Checkpoint 7A.6.2 — two-tier scientific identity (protocol vs. instance vs. cell)

**The gap**: §12's `ScientificEvaluationDomain.domain_protocol_hash` conflated
two different concepts under one weak name — it hashed only
`forecast_origin_id` + sorted `component_id`s, which is neither a real
RULE-level protocol identity (it varies per origin) nor a fully-specified
INSTANCE identity (it omits source coordinates, component CRS, component
geometry, and cell identities).

**The fix**: `services/geospatial/scientific_domain.py` now exposes three
explicit identities:

1. **`scientific_domain_protocol_hash(grid_config)`** — the RULES this
   domain was built under: `SCIENTIFIC_DOMAIN_PROTOCOL_VERSION`,
   `grid_config.config_dict()` (domain distance, cell size, CRS
   strategy, statuses, projection tolerance version),
   `scientific_grid_config_hash()`, `GEODESIC_BOUNDARY_TOLERANCE_KM`/
   `_VERSION`, `COMPONENT_EDGE_DISTANCE_KM_MULTIPLE`,
   `PROJECTION_DISTORTION_REL_TOL`/`PROJECTION_TOLERANCE_VERSION`,
   `RADIAL_DISTORTION_BEARINGS_DEG`, `BUFFER_METHOD_PROJECTED_APPROXIMATION`,
   `TRUE_DOMAIN_POSITIVE_OVERLAP_RULE_VERSION`. Contains NO
   `forecast_origin_id`/`t0`/source ID/`generated_at` — verified
   structurally (`DOMAINID-01`).
2. **`ScientificEvaluationDomain.scientific_evaluation_domain_id`** — THIS
   concrete prediction-time instance: `scientific_domain_protocol_hash`
   + `forecast_origin_id` + `t0` + sorted `all_eligible_source_ids` +
   each component's own `component_id`/`analysis_crs`/
   `union_geometry_digest`/sorted `scientific_cell_id`s +
   `scientific_grid_config_hash`. Deterministic regardless of source
   ordering (`DOMAINID-03`); changes with `t0`, source coordinates,
   domain distance, cell size, CRS strategy, projection tolerance
   version, or component geometry (`DOMAINID-04..10`).
3. **`scientific_cell_id(...)`** (new field on `ScientificGridCell`,
   `services/geospatial/scientific_grid.py`) — a deterministic,
   configuration/projection-sensitive identity for ONE cell:
   `scientific_domain_protocol_hash` + `component_id` + component
   `analysis_crs` + component `union_geometry_digest` +
   `scientific_grid_config_hash` + `domain_distance_km` + `cell_size_km`
   + canonical (mm-rounded) `bounds_utm` + the overlap-protocol version.
   Never depends only on the 8-character `component_id` prefix baked
   into the human-readable `grid_cell_id`. Cells from separate
   components can never collide (`CELLID-01/02`); a cell built under a
   different cell size/domain distance/CRS/geometry never silently
   shares an identity with one built under different settings
   (`CELLID-03`).

**Cache-identity audit (Part 5)**: searched every real persistent cache
in this codebase. `services.features.cache.FileWeatherCache` keys on the
real ERA5 request parameter dict (lat/lon/dates/model) — never on
`grid_cell_id`/`component_id`/any domain hash — so it re-keys correctly
on any query-geometry change automatically.
`services.geospatial.raster.download_and_cache` keys on the source
dataset URL, entirely independent of query/grid geometry. **No
scientifically under-specified cache key was found** — `grid_cell_id`/
`component_id` are used only as in-memory dict keys within one
already-computed result, never as a cross-run cache lookup key
(`CACHEID-01`).
