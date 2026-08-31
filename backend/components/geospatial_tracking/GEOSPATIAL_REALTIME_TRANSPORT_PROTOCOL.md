# Geospatial Real-Time Transport Protocol (Checkpoint 10B)

Checkpoint 10B implements **REAL_TIME_TRANSPORT_ENGINEERING** over the
already-frozen Checkpoint 10A/10A.1 historical-retrospective replay
snapshot. It does **not** implement live epidemiological surveillance,
prospective real-time forecasting, strict operational availability,
automatic new-outbreak detection, or validated live disease
prediction.

**Real-time transport != real-time scientific data.** A WebSocket
connection does not upgrade retrospective scientific evidence into
prospective evidence. `REALTIME_TRANSPORT_MODE_10B =
HISTORICAL_RETROSPECTIVE_REPLAY_SNAPSHOT_TRANSPORT`;
`LIVE_OPERATIONAL_ANALYSIS_STATUS` remains
`NOT_IMPLEMENTED_NO_ACTUAL_OPERATIONAL_AVAILABILITY_PIPELINE`,
unchanged from Checkpoint 10A.1.

## 1. Snapshot architecture

```
HTTP route / WebSocket handler
        |
SNAPSHOT_STORE_10B (bounded LRU+TTL cache, single-flight)
        |  (on miss/expiry/force-refresh)
compute_snapshot_with_managed_repository_10b
        |
run_frozen_geospatial_runtime_analysis_10a   <- the ONLY scientific producer (Checkpoint 10A, unchanged)
        |
GeospatialSnapshot10B (immutable)
        |
served repeatedly by HTTP (summary/cells/sources) and WebSocket (snapshot_begin/summary/sources/cells_chunk*/snapshot_end)
```

`services/transport/geospatial_snapshot_10b.py` never recomputes C0,
direction, rate, or reach itself — `run_frozen_geospatial_runtime_analysis_10a`
is called exactly once per snapshot build.

## 2. Snapshot identity

`compute_snapshot_id_10b()` = SHA256 of the canonical JSON payload:
`forecast_origin_id`, `t0`, `runtime_data_mode`,
`active_api_protocol_hash_10a1`, `eligible_sources` (already sorted by
`source_id`), `cells` (already sorted by `scientific_cell_id`),
`apparent_rate_context`, `nominal_reach_by_day`, `provenance`,
`limitations`.

**Excluded**: `generated_at`, cache hit/miss, connection/request id,
WebSocket chunk index/size, localhost URL, port, machine path. Verified
(10B-SNAPSHOT-01/02/03): recomputing identical scientific content at a
later wall-clock time produces the same `snapshot_id`; chunking the
same cell list at a different chunk size never touches
`compute_snapshot_id_10b`'s output.

## 3. Cache scope, honestly stated

The current `OutbreakRepository` abstraction exposes no real data
revision/version token, so none is invented.
`SNAPSHOT_CACHE_SCOPE_10B = "PROCESS_LOCAL_EPHEMERAL_HISTORICAL_REPLAY_ONLY"`;
`REPOSITORY_REVISION_TOKEN_STATUS_10B = "NOT_AVAILABLE"`. This cache is
permissible only because the active scientific mode is
`HISTORICAL_RETROSPECTIVE_REPLAY` — it is never proof of cross-process
consistency or live-data freshness. A future `LIVE_OPERATIONAL` mode
must disable this reuse or add a real invalidation mechanism.

## 4. Cache constants and behaviors

`SNAPSHOT_CACHE_MAX_ENTRIES_10B = 8`, `SNAPSHOT_CACHE_TTL_SECONDS_10B = 60.0`
— both `ENGINEERING_TRANSPORT_PARAMETERS_NOT_SCIENTIFIC_PARAMETERS`,
never tuned against outbreak outcomes. Cache key binds:
`forecast_origin_id`, `active_api_protocol_hash_10a1`,
`runtime_data_mode`, `availability_mode`, `record_domain_scope`,
`active_source_window_days`. Behaviors: `MISS_COMPUTED`,
`HIT_REUSED`, `FORCE_REFRESH_RECOMPUTED`, `EXPIRED_RECOMPUTED`,
`EVICTED_LRU`. Bounded (`OrderedDict` + LRU eviction), thread-safe
(`threading.Lock`), deterministic. `SnapshotStore10B.clear()`/
`.invalidate(key)` provided for tests and future transport use.

## 5. Single-flight computation

`SnapshotStore10B` serializes access per-key via a `threading.Lock`
keyed by the cache key tuple — two near-simultaneous same-key requests
result in exactly one `compute_fn()` call; the second observer blocks
until the first stores its result, then sees a cache hit. Different
keys use different locks and never block each other
(10B-CONCURRENCY-01, verified with a controlled `threading.Event`).

## 6. HTTP snapshot reuse

`GET /api/geospatial/analysis/{id}/summary`, `/cells`, `/sources` all
resolve the SAME `GeospatialSnapshot10B` through `SNAPSHOT_STORE_10B` —
verified (10B-EQUIV-06): three sequential calls for one origin inside
the cache TTL trigger exactly one scientific compute. `/protocol` and
`/origins` are unchanged from Checkpoint 10A (no snapshot involved).

## 7. WebSocket transport: `/api/geospatial/ws`

Not named a "live disease feed." On connect, sends `transport_ready`
(`transport_version`, `transport_protocol_hash_10b`, `runtime_data_mode`,
`live_operational_analysis_status`, `active_api_protocol_hash_10a1`).

**Inbound** (strict Pydantic validation, `extra="forbid"`,
`forecast_origin_id` bounded to 256 chars, never interpreted as a
filesystem path): `snapshot_request`, `snapshot_refresh` (explicit
client-requested cache bypass only), `ping`.

**Outbound**, deterministic order, for a successful snapshot request:
`snapshot_begin` (`request_id`, `snapshot_id`, `forecast_origin_id`,
`active_api_protocol_hash_10a1`, `transport_protocol_hash_10b`,
`runtime_data_mode`, `live_operational_analysis_status`, `n_sources`,
`n_cells`, `cell_chunk_size`, `n_cell_chunks`, `cache_status`,
`generated_at_utc`) -> `summary` -> `sources` -> `cells_chunk`
(one or more) -> `snapshot_end` (`n_sources_sent`, `n_cells_sent`,
`n_cell_chunks_sent`, `scientific_content_hash_verified=true`).

The scientific computation (on cache miss) runs off the event loop via
`fastapi.concurrency.run_in_threadpool` — never blocking other
connections.

## 8. Cell chunking / backpressure

`WS_CELL_CHUNK_SIZE_10B = 500`
(`ENGINEERING_TRANSPORT_PARAMETER_NOT_SCIENTIFIC_PARAMETER`). Cells
arrive already sorted by `scientific_cell_id`; `chunk_cells_10b` only
slices — never reorders, duplicates, or omits. `n_chunks =
ceil(N/500)`; every non-final chunk has exactly 500 cells, the final
chunk 1..500. Proven with a synthetic 1201-cell fixture (3 chunks:
500/500/201) — no expensive real-origin scan required.

## 9. HTTP <-> WebSocket scientific equivalence (load-bearing)

WebSocket is only another DELIVERY mechanism — verified exactly, for
the same `snapshot_id`: HTTP `/summary` JSON == WS `summary` frame's
`data`; HTTP `/sources` FeatureCollection == WS `sources` frame's
`data`; `concatenate(WS cells_chunk features in chunk_index order)` ==
HTTP `/cells` FeatureCollection `features`, same order. Both transports
call the exact same `_summary_response`/`_cell_features`/
`_source_features` construction functions — no WebSocket-specific
formula, normalization, or rounding exists anywhere.

## 10. GeoJSON / numerical safety (unchanged)

`EPSG:4326`, `[longitude, latitude]`. No NaN/Infinity — every outbound
WS frame is serialized via a `json.dumps(..., allow_nan=False)` helper
that raises rather than silently emitting invalid JSON. Undefined
bearing -> `null`; valid NORTH -> `0.0`, never coerced to `0`. Risk
remains `raw_c0_score`, never `probability`/`infection_probability`/
`accuracy`/`chance_of_infection`.

## 11. Rate / direction / reach (unchanged, frozen)

Direction remains `C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY`,
descriptive, not predictive; `directional_clarity` is not confidence.
Rate remains `3.946421443154751` km/day,
`[3.5491046170907765, 4.343077329563724]`, `FROZEN_DEVELOPMENT_HISTORICAL_APPARENT_RATE`,
conditioned by the 25-km rate-scope inclusion mechanism. Nominal reach
D1-D7 exact, D7 = `27.624950102083258` km, never clipped to 25km,
`VISUALIZATION_ONLY_NOT_HARD_DISEASE_BOUNDARY`. No day-varying C0
surface is fabricated by any transport code.

## 12. Error semantics

WS error frame: `{"type": "error", "request_id", "status", "message"}`
— never a stack trace, file path, or SQL fragment. Malformed JSON ->
`INVALID_MESSAGE`; unknown `type` -> `UNSUPPORTED_MESSAGE_TYPE`; a
`forecast_origin_id` failing schema validation ->
`INVALID_FORECAST_ORIGIN_ID`; unknown origin -> `ORIGIN_NOT_FOUND`;
scientific unavailability -> the same
`ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE`/`_SCIENTIFIC_DOMAIN`/`_GRID`
statuses HTTP already uses; unexpected failure ->
`ANALYSIS_INTERNAL_ERROR`. A malformed message never crashes the
connection — verified by sending invalid JSON and then a `ping` on the
same still-open socket.

## 13. Connection lifecycle / no automatic polling

Repository connections are opened only for the duration of a
cache-miss computation and closed immediately after (`managed_repository_10b`)
— never held open for an entire WebSocket connection, and never
queried at all on a cache hit. There is exactly one `while True` loop
in the router (the event-driven `receive_text` loop) — no
`asyncio.sleep`/`time.sleep`-driven timer, no background DB polling, no
file watching, no fake refresh timer anywhere in this checkpoint.
`AUTOMATIC_SCIENTIFIC_UPDATE_STATUS_10B = "NOT_IMPLEMENTED"`;
`NO_AUTOMATIC_SCIENTIFIC_UPDATE_SOURCE_IN_10B` is stated explicitly,
because the actual operational ingestion/availability pipeline does
not exist yet.

## 14. Transport protocol identity

`services/integration/geospatial_transport_protocol_10b.py::geospatial_transport_protocol_hash_10b()`
binds the active 10A.1 API protocol hash, transport version, runtime
data mode, live operational status, the snapshot scientific-content-hash
rule, cache scope/capacity/TTL, the WS cell chunk size, the message
type/version schema, the GeoJSON rule, the HTTP<->WS equivalence rule,
the full error taxonomy, and the no-auto-polling status — excluding any
`generated_at`, request/connection id, localhost URL, port, machine
path, actual cache hit/miss outcome, or UI/frontend styling. Changing
`WS_CELL_CHUNK_SIZE_10B` changes this hash; it never changes the
scientific `snapshot_id`.

Real computed value:
`geospatial_transport_protocol_hash_10b() = 071dbd1baebfa18d30626a39b218287bb25269a0ec1e61b809a955b31191f657`.

**Historical hashes preserved exactly, never rewritten**:
`geospatial_api_protocol_hash_10a() = 8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716`;
`geospatial_api_protocol_hash_10a1() = e44761319870e9196768599ad88fde237d709c2b17b03f17662ab144bd5634b8`.

## 15. `/api/geospatial/protocol` additive disclosure

Now also exposes: `transport_version`, `transport_protocol_hash_10b`,
`realtime_transport_status = "IMPLEMENTED_FOR_HISTORICAL_RETROSPECTIVE_REPLAY_SNAPSHOTS_ONLY"`,
`runtime_snapshot_reuse_status = "IMPLEMENTED_IN_10B"`,
`snapshot_cache_scope`, `repository_revision_token_status`,
`cell_chunk_size`, `automatic_scientific_update_status`. Every
serialized analysis-metadata payload (summary/cells/sources, HTTP and
WS) also carries `historical_api_protocol_hash_10a` and
`active_api_protocol_hash_10a1` (Part 1 pre-flight fix) — attached at
the transport/serialization boundary in
`geospatial_snapshot_10b.transport_analysis_metadata_10b`, never inside
the frozen Checkpoint 10A `RuntimeAnalysisMetadata10A` dataclass itself
(avoiding an `application` <-> `integration/protocol` import cycle).

## 16. Real controlled engineering smoke

`ORIGIN:Afghanistan:2022-05-29` (the already-known controlled
structural smoke origin — never searched for a favorable one): cold
snapshot compute `0.094s`, warm cache-hit `0.003s`, HTTP `/summary`
200, 88 cells, 1 source, WS time-to-`snapshot_begin` `0.007s`,
time-to-`snapshot_end` `0.008s`, 6 WS frames (1 chunk), largest frame
`63,235` bytes, total `71,175` bytes, `snapshot_id` identical across
HTTP and WS
(`cc92c6f716b7c2d04a2f4c18a893e87757876611e1068d9b0c526ae8853e8598`).
**This controlled engineering smoke completed under 3 seconds** — not
generalized to every origin, model performance, or production
deployment.

## 17. Tests

46 new (`tests/test_checkpoint_10b_realtime_transport.py` —
10B-PARENT-01..03, 10B-META-01, 10B-SNAPSHOT-01..03, 10B-CACHE-01..07,
10B-CONCURRENCY-01 (+1 independent-keys check), 10B-WS-01..15,
10B-EQUIV-01..06, 10B-FIREWALL-01..08, 10B-SEM-01/02, plus a
never-skipping evidence-summary consistency check). One pre-existing
Checkpoint 10A test required a one-line fix (`SNAPSHOT_STORE_10B.clear()`
before asserting a monkeypatched failure) since HTTP routes now
resolve a persistent process-wide cache instead of recomputing on
every call — a genuine, disclosed interaction between 10A's test and
10B's new caching behavior, not a science change. Full backend
regression: **1597/1597 passed, 0 failed, 0 skipped, 1 warning**
(`StarletteDeprecationWarning`, unchanged, honestly reported)
(1551 baseline + 46 new).

**Final Checkpoint 10B classification:
`REALTIME_TRANSPORT_OVER_FROZEN_HISTORICAL_RETROSPECTIVE_REPLAY_SNAPSHOTS_READY_FOR_FRONTEND_NOT_LIVE_OPERATIONAL_FORECASTING`.**

## 18. Checkpoint 10B.1 addendum — transport hardening (memory safety, complete contract identity, integrity, provider consolidation)

**Hash chronology, made unambiguous** (Part 12): an intermediate value
computed during Checkpoint 10B's own implementation,
`104d8d94d3aa53ce372fa90b1189c7bb472d3eadc94552b832bd3a93af5afdb9`,
is `INTERMEDIATE_10B_IMPLEMENTATION_HASH_NOT_FINAL_PROTOCOL` — it was
superseded within Checkpoint 10B itself, before that checkpoint's own
STOP AND REPORT, and was never active or historical. The historical,
final hash is `geospatial_transport_protocol_hash_10b() =
071dbd1baebfa18d30626a39b218287bb25269a0ec1e61b809a955b31191f657`
(`HISTORICAL_FINAL_10B_TRANSPORT_PROTOCOL_HASH`, re-verified unchanged,
10B1-PARENT-01). No field anywhere treats `104d8d94...` as active.

**Auxiliary memory safety** (Part 2): `SnapshotStore10B` now uses
reference-counted per-key `_KeySlot` objects (`lock` + `refcount`)
instead of an ever-growing `_key_locks` dict. A slot is created the
first time a key is seen and reclaimed the instant its `refcount`
reaches zero — in a `finally` block, so this happens whether
`compute_fn()` succeeds, raises, or the caller is cancelled. Because a
new slot object is only created when none exists, and the refcount
increment happens under the store's own lock, two concurrent callers
for the SAME key always share the SAME slot/lock — reclamation never
invalidates a slot a waiting thread is holding a reference to.
`n_active_key_slots()` proves this stays bounded even across thousands
of distinct successful AND failing keys (10B1-MEM-01..06). Eviction
diagnostics are now `eviction_count: int` (O(1) memory) and
`recent_evicted_keys: deque(maxlen=50)` — never an unbounded historical
list.

**Complete transport contract identity** (Part 4): new
`services/integration/geospatial_transport_protocol_10b1.py::geospatial_transport_protocol_hash_10b1()`
binds the historical 10B hash (read-only) plus the exact inbound
message field contract (`INBOUND_CONTRACT_10B1`, cross-checked against
the real `websocket_schemas.py` Pydantic `model_fields`,
10B1-CONTRACT-01), the exact outbound frame field SET per message type
(`OUTBOUND_CONTRACT_10B1`, cross-checked against real WS round-trip
frames, 10B1-CONTRACT-02), the WS inbound byte limit, the
`generated_at_utc` field semantic, the `scientific_content_hash_verified`
semantic, cache scope/capacity/TTL, cell chunk size, GeoJSON rule, and
the extended error taxonomy. Sensitive to a toy field-contract mutation
(10B1-CONTRACT-03); the field's own runtime timestamp VALUE never
participates (10B1-CONTRACT-04). Real value:
`geospatial_transport_protocol_hash_10b1() = 476a7593aafd4011eec840a7ca60cb339302c037f4e00dd7ba11a239ff153a25`.
Both `/api/geospatial/protocol` and `transport_ready`/`snapshot_begin`
now additively expose `active_transport_protocol_hash_10b1` alongside
the unchanged `transport_protocol_hash_10b`.

**`generated_at_utc` gap closed** (Part 5): `snapshot_begin` now
includes `generated_at_utc = snapshot.generated_at_utc` — documented
explicitly as "time this immutable runtime snapshot object was
generated in this process", never outbreak observation time, data
freshness time, operational notification time, or scientific t0. Its
FIELD PRESENCE is bound into the 10B.1 contract hash; its runtime VALUE
never is, and never enters `snapshot_id` (10B1-GEN-01/02).

**`scientific_content_hash_verified` is now a real check** (Part 6):
before `snapshot_end` is sent, the handler recomputes
`compute_snapshot_id_10b(snapshot.analysis)` (the SAME canonical
function `snapshot_id` was built from — no second formula) and compares
it against `snapshot.snapshot_id` via `verify_snapshot_integrity_10b`.
On a match, `snapshot_end` carries `scientific_content_hash_verified =
true`. On a mismatch, an `error` frame with status
`SNAPSHOT_CONTENT_INTEGRITY_MISMATCH` is sent INSTEAD of `snapshot_end`
— never a successful frame with a false integrity claim. Verified with
a controlled tamper fixture (`dataclasses.replace` on a copied snapshot
instance, real scientific artifacts untouched) and, at the WS level, a
monkeypatched integrity function (10B1-INTEGRITY-01/02). This verifies
in-memory transport consistency ONLY — not cryptographic authenticity,
database freshness, or external provenance certification.

**Bounded inbound message size** (Part 7):
`WS_MAX_INBOUND_MESSAGE_BYTES_10B1 = 16384` (16 KiB,
`ENGINEERING_TRANSPORT_SAFETY_LIMIT_NOT_SCIENTIFIC_PARAMETER`), measured
as UTF-8 byte length BEFORE `json.loads` is ever called — an oversized
frame returns `MESSAGE_TOO_LARGE` without being parsed (proven with a
deliberately-invalid-JSON oversized frame that would otherwise surface
as `INVALID_MESSAGE`, 10B1-INPUT-01). The connection remains usable
afterward. Bound into the 10B.1 contract hash.

**Repository construction centralized** (Part 8): new
`repositories/provider.py::create_outbreak_repository()` is the ONE
place that knows the concrete `SQLiteOutbreakRepository` class. Both
`api/router.py::get_repository` (`/origins`) and
`services/transport/geospatial_snapshot_10b.py::managed_repository_10b`
(snapshot cache-miss computation) now call it — neither constructs
`SQLiteOutbreakRepository` directly (10B1-PROVIDER-01). Scientific/
runtime functions remain typed against `OutbreakRepository`
(10B1-PROVIDER-02). Mongo is NOT implemented — `create_outbreak_repository()`
is the one function a future `MongoOutbreakRepository` provider would
need to change.

**Scientific identity and equivalence re-verified unchanged**: for
`ORIGIN:Afghanistan:2022-05-29`, `snapshot_id` remains exactly
`cc92c6f716b7c2d04a2f4c18a893e87757876611e1068d9b0c526ae8853e8598`
after every change above (10B1-GEN-02, 10B1 snapshot-id test);
HTTP == WS scientific equivalence re-verified exactly.

**Real controlled engineering smoke** (same
`ORIGIN:Afghanistan:2022-05-29`, never searched for a faster/favorable
origin): HTTP 200, WS `transport_ready`, identical `snapshot_id` across
HTTP/WS, HTTP == WS content equal, `generated_at_utc` present,
`scientific_content_hash_verified = true`, a second WS request for the
same origin observed `cache_status = HIT_REUSED`. Transport engineering
smoke only — no production SLA claimed.

**Tests**: 25 new
(`tests/test_checkpoint_10b1_transport_hardening.py` --
10B1-PARENT-01/02, 10B1-MEM-01..06, 10B1-CONTRACT-01..04,
10B1-GEN-01/02, 10B1-INTEGRITY-01/02 (+1 dataclasses-tamper variant),
10B1-INPUT-01 (+1 boundary check), 10B1-PROVIDER-01/02, plus an
intermediate-hash-never-active check, a snapshot-id-preservation check,
an HTTP<->WS re-verification, and a never-skipping evidence-summary
consistency check). Full backend regression: **1622/1622 passed, 0
failed, 0 skipped, 1 warning** (`StarletteDeprecationWarning`,
unchanged, honestly reported) (1597 baseline + 25 new).

**Final Checkpoint 10B.1 classification:
`REALTIME_TRANSPORT_HARDENED_OVER_FROZEN_HISTORICAL_REPLAY_SNAPSHOTS_READY_FOR_FRONTEND_NOT_LIVE_OPERATIONAL_FORECASTING`.**

## 19. Checkpoint 10B.1a addendum — HTTP snapshot identity envelope correction, true HTTP<->WebSocket snapshot-id proof

**The real remaining defect** (Part 1): `/summary`, `/cells`, `/sources`
reused the same internal `GeospatialSnapshot10B` since Checkpoint 10B,
but never serialized `snapshot_id` in the HTTP response body. The test
named `test_10b_equiv_05_snapshot_id_identical_across_http_routes`
therefore proved only that `analysis_metadata.forecast_origin_id`
matched across routes and that one cache entry existed -- an ORIGIN-ID
PROXY, never a real snapshot-identity comparison. Corrected, not
erased: documented as
`PREVIOUS_10B_SMOKE_SNAPSHOT_ID_EQUALITY_CHECK_WAS_AN_ORIGIN_ID_PROXY_NOT_A_SERIALIZED_HTTP_SNAPSHOT_ID_CHECK`,
and the same test now compares real `snapshot_id` values directly.

**HTTP snapshot-identity envelope added** (Part 2): `/summary`,
`/cells`, `/sources` all now additively serialize `snapshot_id: str`
and `generated_at_utc: str`. `snapshot_id` is the OUTPUT identity of
the already-frozen scientific payload -- it is never added as a new
INPUT to `canonical_scientific_payload_10b`/`compute_snapshot_id_10b`.
`generated_at_utc` remains transport/process metadata and never enters
`snapshot_id`. No scientific value changed.

**True HTTP route snapshot-id equality proven** (Part 4): after
`SNAPSHOT_STORE_10B.clear()`, sequential `/summary` -> `/cells` ->
`/sources` requests for the controlled origin now assert
`summary.snapshot_id == cells.snapshot_id == sources.snapshot_id`
directly from the serialized response bodies, plus exactly one
underlying scientific compute (`len(SNAPSHOT_STORE_10B) == 1`).

**True HTTP<->WebSocket snapshot-id equality proven** (Part 5): for one
reused snapshot, `HTTP summary.snapshot_id == HTTP cells.snapshot_id ==
HTTP sources.snapshot_id == WS snapshot_begin.snapshot_id == WS
summary.snapshot_id == WS sources.snapshot_id == every WS
cells_chunk.snapshot_id == WS snapshot_end.snapshot_id` -- verified
against real serialized frames, not inferred from `forecast_origin_id`,
cache length, `generated_at`, or response timing.

**Corrected controlled smoke** (Part 6, same
`ORIGIN:Afghanistan:2022-05-29`, never searched for another origin):
HTTP `/summary`, `/cells`, `/sources` `snapshot_id` and WS
`snapshot_begin.snapshot_id` are all exactly
`cc92c6f716b7c2d04a2f4c18a893e87757876611e1068d9b0c526ae8853e8598` --
the controlled scientific snapshot ID, unchanged.

**Integrity verification moved earlier** (Part 7): `verify_snapshot_integrity_10b`
is now evaluated immediately after a snapshot is resolved, BEFORE
`snapshot_begin`/`summary`/`sources`/`cells_chunk` are ever sent -- a
mismatch now produces ONLY a `SNAPSHOT_CONTENT_INTEGRITY_MISMATCH`
error frame, never any partial scientific data first. `snapshot_id` is
unaffected by this timing change. Still an
`IN_MEMORY_TRANSPORT_CONSISTENCY_CHECK` only.

**New active transport contract identity** (Part 8): new
`services/integration/geospatial_transport_protocol_10b1a.py::geospatial_transport_protocol_hash_10b1a()=0549339d2d79659048e2d265403507b756b464d454419c28c295d005d8450f0e`
binds the (now historical) Checkpoint 10B.1 contract hash plus the
HTTP snapshot-identity envelope fields/routes, the HTTP<->WS equality
rule, and the pre-send integrity-verification-timing rule. Neither the
historical 10B hash (`071dbd1b...`) nor the historical 10B.1 hash
(`476a7593...`) was rewritten.

**`/protocol` disclosure clarified** (Part 9):
`historical_transport_protocol_hash_10b`,
`historical_transport_protocol_hash_10b1`, and
`active_transport_protocol_hash_10b1a` are all exposed with
unambiguous names -- a future frontend consumes the newest active
identity (`_10b1a`).

**All prior transport guarantees preserved** (Part 11): memory-safe
per-key slot cleanup, bounded LRU/eviction diagnostics, TTL,
single-flight, the 16 KiB inbound limit, strict `extra="forbid"`
Pydantic validation, HTTP/WS scientific content equality, 500-cell
chunking, `[longitude, latitude]`, null-vs-`0.0` bearing, NaN/Infinity
protection, no automatic polling, historical replay status, live
operational `NOT_IMPLEMENTED`, and the repository provider abstraction
are all unchanged and re-verified passing.

**Tests**: 14 new
(`tests/test_checkpoint_10b1a_snapshot_identity.py` --
10B1A-PARENT-01, 10B1A-ID-01..06, 10B1A-GEN-01, 10B1A-INTEGRITY-01/02,
10B1A-CONTRACT-01/02, plus a previous-smoke-interpretation-preserved
check and a never-skipping evidence-summary consistency check), plus
one existing Checkpoint 10B test corrected in place
(`test_10b_equiv_05_snapshot_id_identical_across_http_routes`, now a
real snapshot-id comparison). Full backend regression: **1636/1636
passed, 0 failed, 0 skipped, 1 warning** (`StarletteDeprecationWarning`,
unchanged, honestly reported) (1622 baseline + 14 new).

**Final Checkpoint 10B.1a classification:
`REALTIME_TRANSPORT_BACKEND_LOCKED_WITH_EXPLICIT_HTTP_WEBSOCKET_SNAPSHOT_IDENTITY_READY_FOR_FRONTEND_NOT_LIVE_OPERATIONAL_FORECASTING`.**
