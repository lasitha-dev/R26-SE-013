# Geospatial API Protocol (Checkpoint 10A)

Checkpoint 10A adds a production-safe, read-only HTTP boundary over the
already-frozen scientific components (7C risk, 8B.3 direction, 9B
rate, 9C integration, 9C.1 rate-scope conditioning). It fits nothing,
retunes nothing, and evaluates no new research metric — every value
served here is either a frozen constant or computed by an
already-frozen canonical function against the current eligible-source
set at a requested origin's real `t0`.

## 1. Architecture

```
HTTP Router (api/router.py)
        |
Runtime Application Service (services/application/frozen_geospatial_analysis_10a.py)
        |
OutbreakRepository abstraction (repositories/base.py)
        |
Frozen scientific services (get_eligible_sources, build_scientific_evaluation_domain,
score_origin_candidates_7c, compute_cell_direction_tendency_8b3,
default_apparent_rate_component_9c, build_nominal_reach_by_day_9c)
        |
Pydantic response schemas (api/schemas.py)
```

The router contains **no scientific computation**: no copied
C0/kernel/direction/rate formula, no direct SQLite query (it only
opens/closes `SQLiteOutbreakRepository` via a `Depends` factory), and
no read of a gitignored `local_data` research artifact at request time
— verified structurally (AST import/call scans, 10A-ROUTER-01/02,
10A-FIREWALL-01). The application service types against
`OutbreakRepository` (the Protocol in `repositories/base.py`)
everywhere it accepts a repository, so a future
`MongoOutbreakRepository` needs no route/service rewrite (Part 14).

## 2. Runtime application service

`run_frozen_geospatial_runtime_analysis_10a(repo, forecast_origin_id)`
returns one deterministic `FrozenGeospatialRuntimeAnalysis10A`:

1. Resolves the real `ForecastOrigin` (real `t0`/`temporal_mode`
   preserved exactly) by enumerating the runtime-derived origin ledger
   (`build_forecast_origin_ledger`) — never a hardcoded/cached list.
2. Obtains the frozen eligible source set via `get_eligible_sources`,
   using the frozen 14-day development source window
   (`ACTIVE_SOURCE_WINDOW_DAYS_10A = ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT`,
   labeled `UNFROZEN_DEVELOPMENT_PARAMETER` exactly as its historical
   provenance already states — never re-labeled "frozen science").
3. Builds the projection-safe scientific domain
   (`build_scientific_evaluation_domain`) using the frozen 5km grid
   (`SCIENTIFIC_GRID_CELL_SIZE_KM`) and the frozen 25km operational
   local evaluation envelope (`PRIMARY_LOCAL_EVALUATION_DISTANCE_KM`)
   — both imported directly, never a second hardcoded literal.
4. Computes frozen C0 cell scores by calling
   `score_origin_candidates_7c` — the exact frozen kernel scorer, never
   reimplemented, over **all** eligible sources (never nearest-source-
   only).
5. Derives 8B.3 cell-local direction tendencies by calling
   `compute_cell_direction_tendency_8b3` — the exact frozen active
   direction implementation.
6. Attaches the frozen 9C apparent-rate component
   (`default_apparent_rate_component_9c()`, zero arguments — a single
   frozen global scalar, structurally incapable of reading a
   bearing/clarity value) plus the 9C.1 rate-scope-conditioning
   disclosure.
7. Attaches the frozen 9C D1-D7 nominal reach
   (`build_nominal_reach_by_day_9c()`) unchanged.
8. Attaches provenance (every frozen parent hash) and limitations.

Cells are sorted by `scientific_cell_id`, sources by `source_id`,
before being returned — deterministic response ordering never relies
on dict/hash iteration order (Part 16).

## 3. Repository lifecycle

`api/router.py::get_repository` is a FastAPI `yield` dependency: opens
exactly one `SQLiteOutbreakRepository` per request, closes it in a
`finally` block — no unmanaged global connection.

## 4. CRS / GeoJSON convention

- `EPSG:4326` (WGS84), coordinate order **`[longitude, latitude]`**
  (RFC 7946) — `GeoJSONPointGeometry.coordinates` is a
  `(longitude, latitude)` tuple.
- Scientific calculations keep their internal AOI-local UTM metric CRS
  (`ScientificGridCell.analysis_crs`, e.g. `EPSG:32642`) — surfaced
  separately as `scientific_crs` on every cell feature, never confused
  with the WGS84 output coordinates.
- Map heatmap cells are `Point` features at scientific-cell centroids
  (no polygon is invented from a bounding box).
- The 5km grid cell size is never presented as source-location GPS
  accuracy.

## 5. Risk semantics

`risk.raw_c0_score` — `RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY`.
`risk.risk_surface_temporal_semantics` —
`STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT`: rate/reach context is
attached but never multiplied into the cell score, and no day-varying
C0 surface is fabricated. No API field is named
`infection_probability`/`probability_of_infection`/
`transmission_probability`/`accuracy`/`chance_of_infection`.

## 6. Direction semantics

`direction.direction_semantics` —
`C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY`:
descriptive, t0-static, cell-local — never predicted disease direction,
wind direction, validated spread bearing, or causal transmission
direction. `directional_clarity` is normalized geometric resultant
coherence, never confidence — no field is named/aliased
`direction_confidence`. `bearing_deg` uses `is not None` throughout:
`0.0` (valid NORTH) always survives serialization; an undefined
direction serializes to `null`, never `0`.

## 7. Rate / reach semantics

`apparent_rate_context` exposes the frozen 9B point estimate
(`3.946421443154751` km/day) and 95% interval
(`[3.5491046170907765, 4.343077329563724]`), labeled
`FROZEN_DEVELOPMENT_HISTORICAL_APPARENT_RATE` — never current/predicted
outbreak speed, Sri Lanka rate, or transmission velocity. The 9C.1
conditioning disclosure is always attached:
`conditioning_limitation` = "Rate estimate is conditional on target
events contributing at least one valid observation inside the frozen
25-km local evaluation scope." `nominal_reach_by_day` is
`reach(day_h) = S0 * day_h` for D1-D7 only, labeled
`VISUALIZATION_ONLY_NOT_HARD_DISEASE_BOUNDARY` — D7 is never clipped to
25km. `operational_evaluation_envelope_km` (`25.0`) is always a
separate field from `nominal_reach_by_day`.

## 8. Source semantics

Eligible-source features expose `source_id`, `longitude`, `latitude`,
`availability_quality`, `gps_quality`, and
`nearest_source_semantics = NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE`
— never `causal_source`/`transmission_parent`/`infection_origin`. C0
scoring continues to use **all** eligible sources; the source feature
listing never implies a nearest-source replacement.

## 9. Error / unavailable semantics

No fallback data is ever fabricated:

| status | HTTP | meaning |
|---|---|---|
| `ORIGIN_NOT_FOUND` | 404 | the `forecast_origin_id` does not exist in the runtime-derived ledger |
| `ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE` | 409 | origin exists, zero eligible sources at its real `t0` |
| `ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN` | 409 | scientific domain construction failed or produced zero components |
| `ANALYSIS_UNAVAILABLE_GRID` | 409 | domain built, but produced zero grid cells (e.g. every component projection-unsafe) |
| `ANALYSIS_INTERNAL_ERROR` | 500 | unexpected software failure — no raw stack trace exposed to the client |

A missing origin/source/domain/grid never becomes `score = 0`,
`bearing = 0`, `source_count = 1`, or a dummy location.

## 10. Routes (prefix `/api/geospatial`)

| method | path | purpose |
|---|---|---|
| GET | `/protocol` | scientific/API protocol metadata and frozen semantics only, no repository opened |
| GET | `/origins` | lightweight origin metadata (`build_forecast_origin_ledger`), optional `country` filter — no scientific analysis for the whole DB |
| GET | `/analysis/{forecast_origin_id}/summary` | metadata, source count, rate context, nominal reach, provenance, limitations |
| GET | `/analysis/{forecast_origin_id}/cells` | GeoJSON `FeatureCollection` of cell `Point` features (raw C0 score, direction, scientific cell id) |
| GET | `/analysis/{forecast_origin_id}/sources` | GeoJSON `FeatureCollection` of eligible-source `Point` features |

Route handlers are plain synchronous `def` (Part 15) — FastAPI runs
each in its threadpool rather than blocking the event loop with the
CPU/GIS-heavy analysis. No WebSocket, no polling, no background task,
no frontend in this checkpoint.

## 11. Protocol identity

`services/integration/geospatial_api_protocol_10a.py::geospatial_api_protocol_hash_10a()`
binds the parent `integration_protocol_hash_9c` and
`rate_scope_conditioning_protocol_hash_9c1`, the API version, the
GeoJSON/coordinate-order rule, every response-semantic rule above, the
D1-D7 primary horizon, and the error-status taxonomy — never a
localhost URL, port, `generated_at` timestamp, absolute machine path,
or UI styling.

Real computed value:
`geospatial_api_protocol_hash_10a() = 8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716`.

## 12. Scientific limitations (inherited, unchanged)

Every limitation frozen at 9B/9C/9C.1 is inherited unchanged and
exposed via `limitations`/`apparent_rate_context`: apparent rate is not
biological transmission speed; recorded event dates are proxies;
nearest source is a geometric reference, not a causal parent; the
bootstrap interval is conditional target-event resampling uncertainty,
not complete epidemiological uncertainty; the rate estimate is
conditional on the frozen 25-km local-scope inclusion mechanism
(lead-dependent truncation); this is development historical evidence,
not a held-out or Sri Lanka-specific result.

## 13. Real smoke-test result

One controlled runtime analysis (`ORIGIN:Afghanistan:2022-05-29`,
chosen as the first analyzable origin in ledger order, before
inspecting any output value): HTTP 200 on `/summary`, `/cells`,
`/sources`; 1 eligible source; 88 scientific cells; all GeoJSON
coordinates finite and in valid WGS84 range; runtime 0.18s;
combined response size 68,621 bytes. Not reported as accuracy or
performance validation — a structural smoke check only.

## 14. Tests

41 new (`tests/test_checkpoint_10a_runtime_api.py` —
10A-PARENT-01/02, 10A-SCI-01..05, 10A-DIR-01..04, 10A-RATE-01..04,
10A-REACH-01..03, 10A-CRS-01/02, 10A-JSON-01, 10A-ORDER-01/02,
10A-ERROR-01/02, 10A-ROUTER-01/02, 10A-FIREWALL-01..03, 10A-SEM-01..03,
10A-PROTOCOL-01, plus FastAPI `TestClient` integration tests for every
route). Full backend regression: **1530/1530 passed, 0 failed, 0
skipped** (1489 baseline + 41 new).

**Final Checkpoint 10A classification:
`FROZEN_GEOSPATIAL_SCIENTIFIC_RUNTIME_AND_READ_ONLY_API_READY_FOR_REALTIME_LAYER`.**

## 15. Checkpoint 10A.1 — historical-replay / live-operational semantic separation, source-window provenance, API-protocol correction

**Nothing scientific changed.** C0, S0, the 9B CI, the 25km envelope,
the 5km grid, D1-D7, and the 14-day active source window are all
byte/numerically unchanged. This checkpoint corrects *labeling and
disclosure*, not computation.

**14-day source-window provenance hardened**: `ACTIVE_SOURCE_WINDOW_DAYS_10A1
= ACTIVE_SOURCE_WINDOW_DAYS_10A` (still `14`, reused verbatim, never a
second literal, never tested at an alternate value).
`active_source_window_original_provenance = "UNFROZEN_DEVELOPMENT_PARAMETER"`
(the config.py fact, unchanged) and
`active_source_window_runtime_status = "FIXED_HISTORICAL_DEVELOPMENT_PROTOCOL_VALUE_NOT_SCIENTIFICALLY_VALIDATED"`
are now both exposed explicitly — 14 days is retained only for
reproducibility/compatibility with the historical development/
evaluation pipeline, never claimed as a biologically validated
infectious period. A code/protocol-identity audit (never a model
rerun) traced `ACTIVE_SOURCE_WINDOW_DAYS_7C`/`_7D`/`_7E` and
`rate_protocol_9a`'s explicit `reused_from` back to the SAME single
canonical `config.ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT` — Checkpoint
7B's own real-run invocation script is not present in the current tree
to re-verify independently, honestly disclosed rather than assumed.

**Runtime mode named honestly**: current 10A/10A.1 analysis calls
`get_eligible_sources` with `ValidationMode.RETROSPECTIVE_PROXY` /
`RecordDomainScope.HISTORICAL_ONLY` (unchanged, structurally verified
to be the SAME enum objects feeding both the real call and the exposed
metadata, 10A1-MODE-05) — this is `runtime_data_mode =
"HISTORICAL_RETROSPECTIVE_REPLAY"`, never live surveillance data,
never strict operational availability, never real-time epidemiological
forecasting. Adding an HTTP/FastAPI boundary in Checkpoint 10A did not
make the underlying evidence real-time.
`live_operational_analysis_status = "NOT_IMPLEMENTED_NO_ACTUAL_OPERATIONAL_AVAILABILITY_PIPELINE"`;
`realtime_transport_status = "NOT_IMPLEMENTED"`. All current routes
remain historical replay routes — `RecordDomainScope.LIVE_ONLY` is
never used anywhere in this checkpoint.

**Historical 10A hash preserved exactly, new additive identity created**:
`geospatial_api_protocol_hash_10a()` remains
`8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716`
(verified unchanged, 10A1-HIST-01). It never bound the active source
window, availability mode, record domain scope, or runtime data mode —
classified `HISTORICAL_API_IDENTITY_WITH_RUNTIME_INPUT_SEMANTICS_NOT_YET_BOUND`
(never "fraudulent" or "invalid" — a genuine, real, but incomplete-for-
these-semantics identity). New
`services/integration/geospatial_api_protocol_10a1.py::geospatial_api_protocol_hash_10a1()`
binds the historical 10A hash plus every semantic above, and remains
sensitive to a toy-dict change in any of them (10A1-WINDOW-05,
10A1-PROTOCOL-01/02) without ever touching the real runtime constants.
Real computed value:
`geospatial_api_protocol_hash_10a1() = e44761319870e9196768599ad88fde237d709c2b17b03f17662ab144bd5634b8`.

**`/api/geospatial/protocol` and analysis metadata now expose**
(additive fields, all prior 10A fields unchanged): `runtime_data_mode`,
`availability_mode`, `record_domain_scope`, `active_source_window_days`,
`active_source_window_original_provenance`,
`active_source_window_runtime_status`, `live_operational_analysis_status`,
`historical_api_protocol_hash_10a`, `active_api_protocol_hash_10a1`
(protocol endpoint only; the historical response field name
`api_protocol_hash_10a` is renamed to `historical_api_protocol_hash_10a`
in this additive response schema revision — the underlying HASH VALUE
it carries is unchanged).

**Recomputation limitation carried into 10B**: `/summary`, `/cells`,
`/sources` each independently call the full runtime analysis today
(`RUNTIME_SNAPSHOT_REUSE_STATUS_10A1 = "NOT_IMPLEMENTED_IN_10A1"`) — no
caching is introduced here; Checkpoint 10B must address one-analysis-
per-update/snapshot reuse before high-frequency realtime transport is
claimed.

**Stale evidence corrected transparently** (Part 9): the original
Checkpoint 10A evidence summary recorded `new=41, total=1530`, omitting
the 1 evidence-summary consistency test added afterward and never
recording the pre-existing `StarletteDeprecationWarning`. Corrected to
`baseline_before_10a=1489`, `10a_route_unit_structural_tests=41`,
`10a_evidence_summary_consistency_tests=1`, `total_after_10a=1531`,
`warning_count=1`, `warning_type=StarletteDeprecationWarning` — the
suite is never described as warning-free.

**Dependency warning investigated, not silenced**: `httpx2` was NOT
installed. Installed versions recorded: Python 3.14.4, FastAPI 0.141.1,
Starlette 1.6.0, Pydantic 2.13.4, httpx 0.28.1. Classified
`TEST_INFRASTRUCTURE_DEPRECATION_WARNING_PRESENT` — no safe
compatibility fix was obvious within this checkpoint's scope; left for
final dependency-freeze cleanup rather than destabilizing runtime
dependencies here.

**`main.app` HTTP integration re-verified safely**: `GET /` → 200,
`GET /api/geospatial/protocol` → 200, using `getattr(route, "path",
None)` for route introspection rather than assuming every route object
exposes `.path` (the earlier `AttributeError` was a diagnostic-script
bug, never a router-registration failure).

**Tests**: 20 new
(`tests/test_checkpoint_10a1_operational_semantics.py` —
10A1-HIST-01, 10A1-WINDOW-01..05, 10A1-MODE-01..05, 10A1-PROTOCOL-01/02,
10A1-SEM-01/02, 10A1-EVIDENCE-01, 10A1-MAIN-01, 10A1-SNAPSHOT-01, plus
a historical-gap structural proof and a never-skipping evidence-summary
consistency check). Full backend regression: **1551/1551 passed, 0
failed, 0 skipped, 1 warning** (`StarletteDeprecationWarning`, honestly
reported) (1531 baseline + 20 new).

**Final Checkpoint 10A.1 classification:
`FROZEN_GEOSPATIAL_HISTORICAL_REPLAY_API_WITH_EXPLICIT_RETROSPECTIVE_AND_SOURCE_WINDOW_PROVENANCE_READY_FOR_REALTIME_TRANSPORT_ENGINEERING`.**
This means the API architecture is ready to be used by a realtime
transport layer — it does NOT mean real-time operational scientific
forecasting is already validated.

## 16. Checkpoint 10B addendum — real-time transport implemented, science unchanged

The realtime transport layer promised above is now implemented over
this exact frozen API contract: one shared, bounded, single-flight
`GeospatialSnapshot10B` cache backs `summary`/`cells`/`sources` for
both HTTP and a new `/api/geospatial/ws` WebSocket endpoint. Every
serialized analysis-metadata payload now additionally carries
`historical_api_protocol_hash_10a` and `active_api_protocol_hash_10a1`
(both closed over — see §16 in `GEOSPATIAL_REALTIME_TRANSPORT_PROTOCOL.md`).
`/protocol` gains `transport_version`, `transport_protocol_hash_10b`,
`realtime_transport_status = "IMPLEMENTED_FOR_HISTORICAL_RETROSPECTIVE_REPLAY_SNAPSHOTS_ONLY"`,
`runtime_snapshot_reuse_status = "IMPLEMENTED_IN_10B"`,
`snapshot_cache_scope`, `repository_revision_token_status`,
`cell_chunk_size`, `automatic_scientific_update_status`. **Both
historical hashes above (`8485968a...`, `e4476131...`) are unchanged.**
Full transport design: `GEOSPATIAL_REALTIME_TRANSPORT_PROTOCOL.md`.

## 17. Checkpoint 10B.1 addendum — transport hardening, complete contract identity

`/api/geospatial/protocol` additively gains
`active_transport_protocol_hash_10b1` alongside the unchanged
`transport_protocol_hash_10b` — the ACTIVE, field-complete transport
contract identity a frontend should consume
(`GEOSPATIAL_REALTIME_TRANSPORT_PROTOCOL.md` §18). No historical hash
(`8485968a...`, `e4476131...`, `071dbd1b...`) changed. Repository
construction is now centralized in `repositories/provider.py`; the
snapshot cache's per-key auxiliary state is now reference-counted and
provably bounded; `snapshot_end`'s integrity flag is a real recomputed
check. Full design: `GEOSPATIAL_REALTIME_TRANSPORT_PROTOCOL.md` §18.

## 18. Checkpoint 10B.1a addendum — HTTP snapshot-identity envelope, true HTTP<->WS proof

`/summary`, `/cells`, `/sources` now additively serialize `snapshot_id`
and `generated_at_utc` (the transport identity of the already-frozen
scientific payload, never a new scientific input). `/protocol` now
exposes `historical_transport_protocol_hash_10b`,
`historical_transport_protocol_hash_10b1`, and
`active_transport_protocol_hash_10b1a` with unambiguous names — no
historical hash was rewritten. True HTTP-route and HTTP<->WebSocket
`snapshot_id` equality is now proven directly from serialized response
bodies, replacing a prior test that only compared `forecast_origin_id`.
Integrity verification now runs before any scientific frame is sent,
never after partial data. Full design:
`GEOSPATIAL_REALTIME_TRANSPORT_PROTOCOL.md` §19.
