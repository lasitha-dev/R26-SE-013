# Feature Assembly Protocol — Checkpoint 6A / 6A.5

**Checkpoint 6A.5 permanent rule**: if changing a `FeaturePolicy` field
changes any hash, that field must either (A) actually change feature-
assembly behavior, or (B) be rejected as unsupported by
`FeaturePolicy.__post_init__`. No field exists purely to be hashed. This
checkpoint also fixed a real reproducibility bug (§2.1 below) and split
snapshot identity into three explicit, separately-meaningful values
(§3.1).

This document describes `services/features/` — the deterministic
environmental/geometry feature-assembly layer that a later PISTES risk
engine will consume. **No risk score, probability, direction, or speed
exists anywhere in this checkpoint.** This is the assembly layer that
sits *before* any of that:

```
Prediction context (a ForecastOrigin)
    -> eligible sources (source_selector.get_eligible_sources)
    -> grid (geospatial.grid.build_smoke_grid)
    -> geospatial/environmental adapters (host density, land cover,
       hydrology per policy; weather once at the AOI center)
    -> FeatureSnapshot
    -> LATER PISTES engine (not built here — it will receive a
       FeatureSnapshot, never call WorldCover/GLW/ERA5/HydroRIVERS
       directly)
```

## 1. Package layout

```
services/features/
    __init__.py
    contracts.py                 FeatureSnapshot, GridCellFeatures, SnapshotReadiness, compute_snapshot_id
    feature_policy.py            FeaturePolicy, LandCoverFeaturePolicy, FEATURE_PROTOCOL_VERSION, protocol_hash()
    resolved_data_signature.py   compute_resolved_data_signature, landcover_comparability_group, compare_feature_compatibility
    cache.py                     FileWeatherCache (local, gitignored, duck-typed — era5.py never imports it)
    assembler.py                  assemble_feature_snapshot(...) — the only entry point
```

No `services/features/api.py` or similar exists — Checkpoint 6A does not
build any API/frontend surface (explicitly out of scope).

## 2. FeaturePolicy — the explicit, hashable scientific configuration

`FeaturePolicy` (`feature_policy.py`) is the ONLY place scientific
feature-assembly parameters live. It has no defaults for the fields
that materially change scientific output (`disease`,
`active_window_days`, grid resolution, `weather_model`,
`weather_lookback_hours`, `landcover_policy`) — a caller must state
them explicitly, mirroring `source_selector.get_eligible_sources`'s
own no-default convention for `active_window_days`/`domain_scope`.

```python
FeaturePolicy(
    disease="Lumpy skin disease",
    active_window_days=14,                 # UNFROZEN_DEVELOPMENT_PARAMETER (config.py)
    grid_half_extent_km=5.0,
    grid_cell_size_km=2.5,
    weather_model="era5",                  # ONLY "era5" is accepted — see §2.1
    weather_lookback_hours=24,              # UNFROZEN_DEVELOPMENT_PARAMETER
    landcover_policy=LandCoverFeaturePolicy(mode="YEAR_MATCHED_REFERENCE"),
    host_density_species=("cattle", "buffalo"),
    hydrology_include=True,
    hydrorivers_search_radius_km=25.0,      # GEOSPATIAL_QUERY_LIMIT, only used when hydrology_include=True
    elevation_include=False,                # `True` is REJECTED at construction — see §2.2
)
```

`__post_init__` validates every field before construction can succeed
(POLICY-01..06, HYDRO-POLICY-01/02): `active_window_days >= 0`,
`grid_half_extent_km/grid_cell_size_km/weather_lookback_hours` positive
finite, `weather_model in {"era5"}`, `host_density_species` a subset of
the real GLW4 species this pipeline extracts (`cattle`, `buffalo`),
`hydrorivers_search_radius_km` positive finite when
`hydrology_include=True`, `elevation_include` must be `False`, and
`LandCoverFeaturePolicy`'s `frozen_worldcover_year` must be exactly
`"2020"` or `"2021"` for `FROZEN_STATIC_REFERENCE`. An invalid
`FeaturePolicy` cannot be constructed at all — it never reaches
`assembler.py`.

### 2.1 Checkpoint 6A.5 bug fix: declared weather model could disagree with the actual request

`FeaturePolicy.weather_model` was passed to
`build_pre_t0_weather_summary(model=...)`, but `era5.py`'s
`_hourly_request_params` hardcoded the module-level `WEATHER_MODEL`
constant (`"era5"`) into the actual HTTP request regardless of what
`model` was passed — so a caller could declare `weather_model="era5_land"`
in a `FeaturePolicy`/`FeatureSnapshot` while the real Open-Meteo request
silently still fetched `era5` data. Fixed in two layers:

1. `era5.py`'s `_hourly_request_params` now uses its caller's own
   `model` argument for the `models=` request parameter — it can no
   longer diverge from what's reported in metadata.
2. `build_pre_t0_weather_summary` now refuses (`BLOCKED`, not a silent
   substitution) any `model` other than `WEATHER_MODEL` — no other
   model's provenance constants (resolution, temporal coverage) have
   been investigated/verified, so nothing is fabricated for them.
3. `FeaturePolicy.__post_init__` additionally restricts `weather_model`
   to `{"era5"}` — the only historical model this pipeline has ever
   investigated (Checkpoint 5.5's full model-selection evidence).

Verified directly: `build_pre_t0_weather_summary(..., model="era5_land")`
now returns `BLOCKED` for every feature, quoting the unsupported model
name; `model="era5"` still produces real results with
`request_parameters["models"] == "era5"` exactly matching
`window.weather_model`.

### 2.2 Checkpoint 6A.5: no hash-only no-op fields

Two fields that previously changed `protocol_hash()` without changing
any assembled feature are now either removed or hard-rejected:

- **`environment_temporal_mode`** (removed entirely) — Checkpoint 6A
  had this as a free-form string field, but the historical assembler
  only ever has ONE legal weather temporal role
  (`PRIMARY_WEATHER_TEMPORAL_ROLE = "RETROSPECTIVE_REANALYSIS_STATE_PROXY"`,
  a module constant, not a policy field) — there being only one legal
  value makes it a fixed fact of the checkpoint, not a configuration
  choice. It was also easily confused with the separate, correctly-named
  `outbreak`/`source`-availability `RETROSPECTIVE_PROXY` temporal mode
  (`ValidationMode`) — conflating the two was itself a real risk.
- **`elevation_include=True`** — the assembler still does not assemble
  elevation into any snapshot field (Part 14 status unchanged), so
  `True` is now a construction-time `ValueError`
  (`"Elevation is not selected/implemented in FeatureSnapshot assembly."`)
  rather than a value that silently produced an identical
  (elevation-free) snapshot under a different hash.

### 2.3 HydroRIVERS search radius — an explicit GEOSPATIAL_QUERY_LIMIT

Checkpoint 6A hardcoded `search_radius_km=25.0` inside the assembler's
hydrology call — a hidden parameter that could change whether a river
distance was found or reported `MISSING`, without appearing anywhere in
`FeaturePolicy` or its hash. Now `FeaturePolicy.hydrorivers_search_radius_km`
(default `25.0`, `DEFAULT_HYDRORIVERS_SEARCH_RADIUS_KM`) is explicit,
validated, included in the hash ONLY when `hydrology_include=True`
(HYDRO-POLICY-02; when hydrology is excluded, changing the radius is
correctly a no-op and correctly does NOT change the hash), and labeled
`GEOSPATIAL_QUERY_LIMIT` — never a biological transmission-distance
claim. `distance_to_nearest_river_km` (unchanged, Checkpoint 5) already
returns `MISSING` — never a fabricated `distance == radius` boundary
value — when no river falls within the limit (HYDRO-POLICY-03, verified
directly: a `1.0km` limit around Chavakachcheri, whose real nearest
river is ~4.3km away, correctly returns `MISSING`, not `1.0`).

### Land-cover modes (Part 12)

| Mode | Behavior |
|---|---|
| `OMIT` (default) | Land cover is not computed at all. Every cell's `landcover` field is `None`. |
| `YEAR_MATCHED_REFERENCE` | Land cover is computed ONLY if the AOI's real event year (`t0[:4]`) is exactly `"2020"` or `"2021"` (the only years WorldCover ships) — the matching product is used and every result is a genuine `YEAR_MATCHED_REFERENCE`. Any other year: `landcover` stays `None` (`NOT_SELECTED`) — never a silent "nearest available year" substitution. |
| `FROZEN_STATIC_REFERENCE` | Caller explicitly freezes one `frozen_worldcover_year` (`"2020"` or `"2021"`), used regardless of the AOI's real event year, always labeled as a static proxy via `esa_worldcover.py`'s own `resolve_landcover_temporal_role`. |

v100 (2020) and v200 (2021) are never both present in one snapshot's
`landcover` blocks (LC-ASSEMBLY-02) — a snapshot always resolves to
exactly one WorldCover product or `NOT_SELECTED`, per the policy above.

### `FeaturePolicy.protocol_hash()` → `feature_policy_hash` (Part 20)

```python
payload = {"feature_protocol_version": FEATURE_PROTOCOL_VERSION, "config": self.config_dict()}
sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")))
```

Covers every scientific parameter (`weather_model`,
`weather_temporal_role` — the fixed constant, included for hash
completeness even though not independently configurable,
`weather_lookback_hours`, `landcover_policy`, `host_density_species`,
`hydrology_include`, `hydrorivers_search_radius_km` when relevant, grid
resolution) — never `generated_at`. Identical `FeaturePolicy` →
identical hash (ASSEMBLY-02); changing any one field → a different hash
(ASSEMBLY-03/04). This is what was DECLARED — see §3.1 for what
ACTUALLY resolved.

## 3. FeatureSnapshot contract (Part 3)

```python
FeatureSnapshot(
    snapshot_id, forecast_origin_id, t0, t0_precision, temporal_mode,
    country_scope, disease,
    active_source_ids, active_source_count,
    grid_meta, grid_cells,           # grid_cells: list[GridCellFeatures]
    weather, weather_sampling_location,
    feature_status_summary,
    source_dataset_versions, landcover_comparability_group,
    source_timezone, t0_timezone_quality, resolved_t0_cutoff_utc,
    feature_protocol_version, feature_protocol_config,
    feature_policy_hash, resolved_data_signature_hash,
    readiness, readiness_notes,
    generated_at,
)
```

`GridCellFeatures` per cell: `grid_cell_id`, centroid/size/area,
`geometry_by_source` (EVERY active source's own `{distance_km,
t_hat_east, t_hat_north}` — never nearest-only), `host_density` (per
species), `landcover` (per class, or `None`), `hydrology` (or `None`).

No field is named `risk`, `probability`, `confidence`,
`spread_direction`, or `speed` (Part 3) — `NORM-02`/`ASSEMBLY-05/06`
enforce this isn't merely a naming convention but a structural fact:
`assemble_feature_snapshot`'s signature accepts no target/outcome
parameter at all.

### 3.1 Three explicit identities (Checkpoint 6A.5 Parts 7, 9)

| Identity | Meaning | Computed from |
|---|---|---|
| `feature_policy_hash` | What the researcher DECLARED/configured | `FeaturePolicy.config_dict()` only |
| `resolved_data_signature_hash` | What datasets/methods ACTUALLY resolved for this one snapshot | real `landcover`/`host_density`/`weather`/`hydrology` dataset versions, weather provider/model/resolution/temporal role/sampling strategy, resolved t0 cutoff + timezone, plus `feature_policy_hash` itself |
| `snapshot_id` | This snapshot's full scientific identity | `forecast_origin_id`, `t0`, `t0_precision`, `temporal_mode`, `country_scope`, `disease`, sorted `active_source_ids`, grid config, `feature_policy_hash`, `resolved_data_signature_hash` |

None of the three ever includes `generated_at` or any adapter's
`retrieved_at`. `t0_precision` is included directly in `snapshot_id`
(Checkpoint 6A left it out) — `DATE_ONLY` and `TIMESTAMP` resolve to
genuinely different weather-cutoff semantics for the same nominal `t0`
string (`t0_resolution.py`), so they must never collide on one ID
(SNAPSHOT-ID-01, verified directly: the two modes resolve different
`resolved_t0_cutoff_utc` values and different `snapshot_id`s for an
otherwise-identical call).

**Why two hashes are necessary, not one — real proof, not a
hypothetical**: Sri Lanka (a 2020 event) and Thailand (a 2021 event),
assembled under the IDENTICAL `FeaturePolicy`
(`YEAR_MATCHED_REFERENCE`), share the exact same `feature_policy_hash`
(`d03f51adb722d7fd...`) but resolve to DIFFERENT
`resolved_data_signature_hash`es (`4cd6c828...` vs. `0eb8c687...`)
because one resolves WorldCover v100 and the other v200 — a real
algorithm-version difference the declared policy alone cannot see.
`compare_feature_compatibility(sl_snapshot, th_snapshot)` correctly
reports `['LANDCOVER_VERSION_MISMATCH']` for this real pair (§12).

Deterministic from scientific inputs only — never a random UUID.
Verified directly: assembling the same (`forecast_origin`, `policy`)
twice produces identical `snapshot_id`, `feature_policy_hash`, and
`resolved_data_signature_hash`; only `generated_at` and per-adapter
`retrieved_at` timestamps (each real API/file call stamps its own
retrieval instant, an expected and correct source of variation) differ
between the two runs.

### 3.2 Timezone/cutoff identity surfaced explicitly (Part 10)

`source_timezone`, `t0_timezone_quality`, and `resolved_t0_cutoff_utc`
are now top-level `FeatureSnapshot` fields (previously only nested
inside `weather["window"]`) — their relationship to snapshot identity
is visible without digging into the weather block, and
`resolved_t0_cutoff_utc` is one of the inputs to
`resolved_data_signature_hash`, so a different resolved cutoff (e.g. a
timezone-resolution change) changes both the resolved signature and,
transitively, the snapshot ID.

## 4. Weather spatial sampling (Part 10) — `AOI_CENTER`, once per snapshot

**Decision: weather is evaluated ONCE, at the AOI center, and shared by
every grid cell.** Not per-cell-centroid, not per-source.

**Why**: ERA5's real resolution (`WEATHER_MODEL_RESOLUTION` = 0.25°,
~25km) is coarser than this checkpoint's entire smoke-grid extent (a
5-10km half-extent with 2.5km cells). Sampling separately per cell or
per source would not add real spatial information — most or all cells
fall inside the exact same ERA5 grid box — it would only multiply
redundant API calls and imply a precision the data does not have
(exactly what the master spec's "do NOT pretend ERA5 ~25km resolution
becomes fine-resolution weather simply because the risk grid is
smaller" forbids). `grid_meta["weather_source_resolution"]` is always
recorded so this is never silently mistaken for per-cell-resolved
weather (WX-ASSEMBLY-04).

**AOI center definition**: the centroid of the forecast origin's own
TRIGGER sources (`trigger_source_ids_at_t0` — the real reason this
forecast origin exists), falling back to the centroid of the full
active-source set if no trigger source is present in the active window.
Recorded as `grid_meta["aoi_anchor_source_ids"]` for full traceability.

This design was chosen BEFORE implementation by inspecting which
structure best supports later PISTES: a future risk engine that wants
finer per-cell environmental precision only needs to look at
`grid_meta["weather_source_resolution"]` to know how much (if any)
additional spatial resolution weather can honestly provide — the
snapshot never hides that limitation.

## 5. Weather cache (Part 11)

`services/features/cache.FileWeatherCache` — one JSON file per cache
key under `local_data/cache/weather/` (gitignored). The cache key is a
SHA-256 hash of the EXACT hourly request-parameter dict `era5.py`
already builds (`_hourly_request_params`): `models`, `latitude`,
`longitude`, `start_date`/`end_date`, `hourly` (requested variables),
`wind_speed_unit`, `timezone`. Part 11's required key material (model,
lat/lon, window, variables, timezone semantics) falls out of that dict
directly — the key can never silently drift from what was actually
requested. A cache entry is only ever read back for an identical
request; a cache MISS always falls through to a real API call (never a
fabricated fallback value).

`era5.build_pre_t0_weather_summary` accepts an optional `cache=` object
and only ever calls `.get(key)`/`.set(key, payload)` on it — this
module is duck-typed on purpose so `services/geospatial/weather` never
imports the higher-level `services/features` package (the dependency
injection keeps the architecture diagram in §1 strictly one-directional).

Verified directly: a repeated real request for the same AOI/window/model
returned in ~30ms from cache vs. ~1.1s for the original network call,
with byte-identical values.

## 6. Missingness contract (Part 15)

Every feature value carries `REAL`/`MISSING`/`BLOCKED`/`DEMO` (the
existing `FeatureResult` contract, Checkpoint 5 Part 15, unmodified) or
is `None` with the cell/snapshot-level equivalent `NOT_SELECTED` when a
policy simply excludes that feature family entirely (land cover under
`OMIT`, hydrology when `hydrology_include=False`, elevation always by
default). **`MISSING` is never converted to `0` anywhere in
`assembler.py`** — no mean/median/nearest-neighbor imputation exists in
this checkpoint (`MISS-01/02/03`, verified against the real Sri Lanka
smoke grid, which genuinely contains 8 `MISSING` host-density results
alongside 269 `REAL` ones, none silently zero-filled).

`SnapshotReadiness` (never called "model confidence" — Part 15):

- `COMPLETE_FOR_ASSEMBLY` — every required structural input succeeded
  and every candidate feature that was computed came back `REAL`.
- `INCOMPLETE_REQUIRED_FEATURE` — a REQUIRED structural input failed:
  no valid-coordinate active source, or a source's geometry could not
  be computed for one or more cells (Part 6's hard invariant violated —
  the source is excluded from `geometry_by_source` and this is recorded
  in `readiness_notes`, never silently dropped without a trace).
- `CANDIDATE_FEATURE_MISSING` — structural inputs are fine, but at
  least one CANDIDATE environmental feature (host density, weather,
  land cover, hydrology) came back `MISSING`/`BLOCKED`/`DEMO` somewhere
  in the snapshot. The real Sri Lanka smoke snapshot is exactly this
  case.

## 7. Required vs. candidate feature families (Part 16)

**REQUIRED structural inputs** (a failure here means
`INCOMPLETE_REQUIRED_FEATURE`): valid grid geometry, the eligible
active-source set, `geometry_by_source` for every active source in
every cell.

**CANDIDATE feature families** (never declared "required" merely
because an adapter exists — Part 16 explicitly warns against circularly
defining the future full model before development): host density,
weather, land cover, hydrology, elevation. Elevation defaults to
excluded entirely (`elevation_include=False`) per Part 14 — a real
adapter existing (`geospatial/elevation/terrain_tiles.py`, Checkpoint 5)
is not by itself a reason to include it in feature assembly.

## 8. Host density (Part 5)

Uses ONLY `host_density.fao_glw.extract_grid_cell_density` — the
Checkpoint 5.6 grid-cell-aligned overlap-area-weighted method. The
legacy `extract_density` (AOI-window radius) function still exists in
`fao_glw.py` but `assembler.py` never calls it (HOST-ASSEMBLY-01 greps
the assembled result's `analysis_method` string for
`"overlap-area-weighted"` and `"target_grid_resolution"` to prove this
directly). Every cell result preserves `value`, `units`
(`animals_per_km2`), `status`, `dataset_version` (`"2015"`),
`source_resolution` (GLW4's real ~10km), and `analysis_method`
(embedding `target_grid_resolution`) — a `MISSING` cell (no valid GLW4
pixel overlap) always carries `value=None` (HOST-ASSEMBLY-02).

## 9. Hydrology / elevation status (Parts 13-14)

Hydrology, when `hydrology_include=True`, assembles ONLY
`distance_to_nearest_river_km` (real HydroRIVERS distance, Asia region,
geodesic-safe method) per grid-cell centroid — never labeled "water
exposure probability" or "vector attraction" anywhere in this codebase.
HydroLAKES is never called by the assembler at all (it remains globally
`BLOCKED` per Checkpoint 5 — `distance_to_nearest_lake_km` is simply not
wired in); `HYDRO-ASSEMBLY-01` confirms no assembled hydrology block
ever contains anything lake-related.

Elevation remains `AVAILABLE_NOT_YET_SELECTED` and is excluded from
every Checkpoint 6A snapshot by the policy default (`elevation_include=False`).
Slope remains unbuilt.

## 10. Sri Lanka case-study discipline (Part 23)

Sri Lanka Event_3473 is a `GEOGRAPHIC_TRANSFER_CASE_STUDY`. Its 6
outbreaks remain limited case-study evidence. This checkpoint's
`FeaturePolicy` (grid resolution, lookback, land-cover mode, species
list, hydrology inclusion) is IDENTICAL for the Sri Lanka and Thailand
smoke snapshots — chosen once, before either snapshot was assembled,
never adjusted because of anything specific to Sri Lanka's real
outbreak locations or any outcome data. No performance/validation
signal exists yet to have influenced it even if the discipline were
relaxed (Checkpoint 6A never inspects validation performance — Part 24).

## 11. What this checkpoint deliberately does NOT do

- No normalization of any kind (min-max, z-score, AOI-max, global,
  log-transform, winsorization, clipping) — `NORM-01/02` verify raw
  interpretable values only (`assembler.py`'s source contains no such
  logic, and real assembled cattle-density values exceed `1.0`, proving
  they were never rescaled into a bounded range).
- No source-strength formula (`S_j`) — `affected_animals`, DQS, host
  density, and status are never combined into a source weight anywhere
  in `assembler.py`.
- No access to any future target/label/lead_days/outcome data —
  `assemble_feature_snapshot`'s signature has no such parameter
  (ASSEMBLY-05/06), and a synthetic future-dated source injected into a
  test repository is verified to never appear in `active_source_ids` or
  any cell's `geometry_by_source` (LEAK-ASSEMBLY-01/02).
- No split-boundary freeze, no development/evaluation fold usage
  decision (Part 24 — deferred to a future checkpoint, before any
  ST-DBSCAN/model-parameter tuning begins).
- No ST-DBSCAN, no model training, no PISTES risk/direction/speed
  equation, no API/frontend.

## 12. WorldCover mixing safety and cross-snapshot compatibility (Checkpoint 6A.5 Parts 8, 11)

**Permanent rule**: `YEAR_MATCHED_REFERENCE` snapshots that resolve to
WorldCover v100 (2020) and v200 (2021) must NOT be silently combined
into one primary model matrix as if the algorithm-version difference
were pure environmental change. `landcover_comparability_group`
(`resolved_data_signature.py`) reports `WORLDCOVER_V100`,
`WORLDCOVER_V200`, or `NOT_SELECTED` for every snapshot — before
building a model matrix spanning multiple snapshots, the caller must
choose one of: land cover `OMIT`, a single `FROZEN_STATIC_REFERENCE`
year for every snapshot in the matrix, or a separately-justified
version-harmonization protocol (not designed here, and never chosen
using model performance).

`compare_feature_compatibility(snapshot_a, snapshot_b)` reports plain
warning labels — `POLICY_MISMATCH`, `LANDCOVER_VERSION_MISMATCH`,
`WEATHER_MODEL_MISMATCH`, `HOST_DATASET_MISMATCH`,
`HYDROLOGY_DATASET_MISMATCH`, `GRID_PROTOCOL_MISMATCH` — never an
automatic "invalid" verdict (a caller decides what to do with the
information). Verified directly against the two real Checkpoint 6A.5
smoke snapshots: `compare_feature_compatibility(sri_lanka, thailand) ==
["LANDCOVER_VERSION_MISMATCH"]` — the only real difference between them
given their identical declared policy.

## Checkpoint 6C — raw features vs. dimensionless hazard factors

`FeatureSnapshot`/`GridCellFeatures` continue to preserve RAW,
provenance-carrying values only (cattle density, humidity,
precipitation, `mean_u10`/`mean_v10`, HydroRIVERS distance, etc.) —
Checkpoint 6C's hazard engine (`services/hazard/`, see
`HAZARD_ENGINE_PROTOCOL.md`) never imports this module or multiplies
these raw values directly into one equation; their scales are
incompatible and no normalization/transformation protocol has been
frozen. The engine instead consumes its own explicit, dimensionless factor
contracts, populated only by software fixtures in this checkpoint — the
real feature->factor transformer is a distinct, future piece of work.
`geometry_by_source[source_id]` (`distance_km`/`t_hat_east`/`t_hat_north`)
is mirrored (not imported) by the hazard package's own `SourceGeometry`
contract for the same independence reason.

**Checkpoint 6C.5 correction**: the future transformer must map raw
`GridCellFeatures` values to a `CellHazardFactors` object (one per
grid cell — `host_factor`/`environmental_suitability_factor`/
`water_context_factor` are CELL properties, e.g. derived from that
cell's own `host_density`/`landcover`/`hydrology` values), and
separately map each active source's own raw attributes to a
`SourceHazardFactors` object (one per source — only
`source_strength_factor` is source-indexed). The original Checkpoint
6C design conflated these under one per-source bag, which would have
made a future transformer read the SAME cell's environmental raw
values once per source and risk them silently disagreeing — the split
contracts make that structurally impossible. Similarly,
`mean_u10`/`mean_v10` (currently sampled once at `AOI_CENTER` per
`FeatureSnapshot`) must be mapped into a `CellMeteorology` per grid
cell — via `hazard.meteorology.expand_uniform_meteorology` for the
current AOI-center-only sampling, or genuine per-cell values if a
future checkpoint adds finer-grained wind sampling.

**Checkpoint 6D delivered this transformer's DEVELOPMENT half**
(`services/factors/`, see `FACTOR_TRANSFORMATION_PROTOCOL.md`) — real
`FeatureSnapshot`s (this module's own output, read via `.as_dict()`,
never mutated) feed a `FactorReferenceProfile` and candidate
transforms, producing `FactorSnapshot`s. `environmental_suitability_factor`/
`water_context_factor`/`source_strength_factor` remain
`NOT_YET_SCIENTIFICALLY_DEFINED` — only `host_density_total` has real
candidate transforms (`LOG1P_ROBUST_REFERENCE_SCALE`/
`EMPIRICAL_CDF_REFERENCE`), and neither is scientifically selected yet.
Real meteorology is adapted with explicit spatial provenance
(`AOI_CENTER_UNIFORM_REAL_PROXY`) via `services/factors/meteorology_adapter.py`
— a factors-package-native object, never a hazard-engine
`CellMeteorology` with a real status (the hazard contracts still refuse
that structurally).

**Checkpoint 6D.5**: `services/geospatial/feature_result.py`'s
`FeatureResult` gained an OPTIONAL `sample_identity` field (default
`None`, fully backward-compatible with every existing adapter/caller).
`services/geospatial/host_density/fao_glw.py`'s
`extract_grid_cell_density` now populates it on every REAL result — a
deterministic hash of the real contributing GLW4 pixel center(s)
(derived from the raster's own affine transform, using the exact same
overlap/nodata filter the density value itself was computed from) —
giving `services/factors/` a true underlying-raster-observation
identity instead of relying primarily on the query grid cell's own
centroid. No raw density VALUE changed; this is purely additive
provenance.

**Checkpoint 6D.6 correction**: 6D.5's `sample_identity` identified
only the SET of contributing pixels, not their normalized overlap
weights — two cells sharing a pixel set but blending it with different
weights would wrongly alias to the same identity. **CONTRIBUTING PIXEL
SET != EFFECTIVE AREA-WEIGHTED RASTER OBSERVATION unless the
contribution weights are also equivalent.** `fao_glw.py` gained
`contributing_pixel_sample_support`, mirroring the exact filter and
weighting (`frac * area_km2`) the real density computation itself uses,
and hashing the dataset/version/asset/species/protocol-version plus
`sorted(pixel_center, normalized_weight)` into
`FeatureResult.sample_support_digest` (new optional field,
backward-compatible; `sampling_protocol_version`/`n_contributing_pixels`
also added). `resolve_static_observation_identity` now prefers this
digest, falling back to the old pixel-set-only `sample_identity`, then
to the rounded query centroid — labeled explicitly
(`RASTER_EFFECTIVE_SAMPLE_IDENTITY` | `QUERY_CENTROID_FALLBACK`).
`FeatureSnapshot` remains RAW — no normalized host factor value belongs
in `FeatureResult`.

**Same identity, different value = conflict, not duplicate**: this is
now a firewall, not a passive assumption — see
`FACTOR_TRANSFORMATION_PROTOCOL.md` §21 for the value-conflict
detection and the real, empirically-derived floating-point tolerance
correction it required.
