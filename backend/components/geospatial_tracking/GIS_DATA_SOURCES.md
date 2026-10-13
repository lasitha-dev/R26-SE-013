# GIS / Environmental Data Sources — Checkpoint 5

Narrative companion to the machine-readable registry at
`local_data/manifests/gis_source_registry.json` (generated directly from
`services/geospatial/source_registry.py` — the two files are always kept
in sync; if they ever disagree, the Python module is authoritative).

**Permanent scientific rule in force for every source below**: no
fallback/fabricated values. Every extraction returns a status of REAL,
MISSING, BLOCKED, or DEMO. DEMO is never used for scientific validation.
A source that cannot be verified/retrieved returns BLOCKED or MISSING —
never an invented number.

---

## 1. Land cover — ESA WorldCover

- **Provider / official source**: ESA / VITO consortium; public COG
  tiles at `esa-worldcover.s3.eu-central-1.amazonaws.com` (no auth).
- **Versions**: v100 (2020) and v200 (2021). Different algorithm
  versions — **never mixed silently or compared as real land-cover
  change**. Every result records its own `dataset_version`.
- **Resolution / CRS**: 10m, EPSG:4326.
- **Retrieval**: windowed `GDAL /vsicurl/` reads via `rasterio` — only
  the small AOI window is fetched, never a full ~100+MB tile.
- **License**: CC BY 4.0.
- **Scientific role**: contextual land-cover covariate — per-class
  PIXEL-COUNT zonal fraction over the AOI window (Checkpoint 5.5
  correction: `count(class pixels)/count(valid pixels)` on the COG's
  native EPSG:4326 grid, not a true metric/equal-area computation —
  accepted at this checkpoint's small ~10-20km AOI scale, where ground
  area per pixel varies by well under 0.1% across the window's latitude
  span; a larger or high-latitude AOI would need real projected
  zonal-area weighting instead). Official class legend only (11
  classes); no invented "attractiveness score."
- **Temporal role**: resolved per-AOI via `resolve_landcover_temporal_role`
  — `YEAR_MATCHED_REFERENCE` when the AOI's real event year is exactly
  2020 or 2021 (matching `worldcover_year`), `STATIC_REFERENCE_PROXY`
  otherwise. Never silently presented as time-matched when it is not.
  v100/v200 differ in algorithm as well as year — a difference between
  them is never interpreted as real land-cover change, and neither
  version is chosen based on later model performance.
- **Status**: REAL (verified against both Sri Lanka [WorldCover 2020
  v100, YEAR_MATCHED_REFERENCE for the real 2020 event] and Thailand
  [WorldCover 2021 v200, YEAR_MATCHED_REFERENCE for the real 2021
  event] smoke AOIs).

## 2. Host density — FAO GLW4 (cattle, buffalo)

- **Provider / official source**: FAO / Gates Foundation / Univ.
  Liverpool GLW4 consortium; hosted on Harvard Dataverse.
- **Reference year**: **2015** — verified directly from the dataset's
  own metadata document. This was originally assumed (incorrectly) to
  be 2020 before verification; the corrected value is what ships in
  code and docs.
- **Critical unit correction**: the shipped `5_*_2015_Da.tif` raster is
  **animal COUNT per pixel**, not a density — confirmed from the
  dataset's own metadata text ("This geotif layer contains the DA
  animal numbers per pixel"). An earlier draft of the adapter read this
  raster and reported it directly as `animals_per_km2`, which produced
  an implausible ~3785 animals/km² for the Sri Lanka smoke AOI. Fixed
  by using GLW4's companion `8_Areakm.tif` (real per-pixel area in km²,
  accounting for latitude-dependent pixel-area shrinkage) and deriving
  density as `sum(count) / sum(real pixel area)` over the AOI window.
  Re-verified value: ~44.6 animals/km² for the same Sri Lanka AOI —
  plausible for a real cattle-farming region.
- **Resolution / CRS**: 0.083333 decimal degrees (~10km at equator), EPSG:4326.
- **License**: CC0 1.0.
- **Scientific role**: regional livestock host-density proxy, RAW value
  — never normalized by the current AOI's maximum.
- **Temporal role**: `STATIC_REFERENCE_PROXY`.
- **Checkpoint 5.6 correction — grid-cell-aligned extraction replaces an
  arbitrary AOI-window radius**: Checkpoint 5.5's `extract_density`
  showed the Sri Lanka cattle density swing from 0.0/km² (5km window) to
  ~44.6/km² (10km window) around the SAME centroid, with no principled
  reason to prefer either radius. `extract_grid_cell_density` (the
  feature now used for the actual computational risk grid) instead
  computes an OVERLAP-AREA-WEIGHTED mean across whichever real GLW4
  source pixels intersect a computational grid cell's own bounds — a
  cell fully inside one source pixel inherits exactly that pixel's own
  density (proven algebraically and by test, HOST-GRID-02), never an
  arbitrary-radius average. `source_resolution` (GLW4's real ~10km) and
  `target_grid_resolution` (the cell's own size) are always reported
  together: a finer computational grid never implies a finer livestock
  measurement than GLW4 actually contains.
- **Status**: REAL. Real per-cell verification, Sri Lanka Chavakachcheri
  smoke grid (25 cells, 2.5km): densities range 0.0-77.4 cattle/km²
  across cells (some cells legitimately `MISSING` — no valid GLW4 pixel
  overlap, e.g. open water), reflecting genuine spatial structure rather
  than one constant AOI-wide value. Thailand Muang Suang center cell:
  cattle 26.1/km², buffalo 6.7/km² — consistent with the earlier
  AOI-window result at that same location (a single source pixel
  dominates there), confirming the new method doesn't silently change
  values where the old method already happened to be locally accurate.

## 3. Historical weather — ERA5, explicitly selected (via Open-Meteo)

- **Provider vs. model (stated separately, always)**: `WEATHER_PROVIDER`
  is the Open-Meteo Historical Weather API, a free no-auth intermediary —
  NOT a direct Copernicus Climate Data Store (CDS) call (CDS requires
  registered credentials not available in this environment).
  `WEATHER_MODEL` is **`era5`**, passed explicitly via the API's own
  `models=` parameter on every request — never the unset default
  (`best_match`), which resolves silently and inconsistently by
  date/location.
- **Checkpoint 5.5 correction — why `era5`, not `era5_land`**: the
  Checkpoint 5 adapter described its data as "ERA5/ERA5-Land" without
  ever passing `models=`, so it was actually served by whatever
  `best_match` picked. Re-verified directly against Open-Meteo (live
  requests + official docs, 2026-08-19), not from memory:
  - `era5_land` (0.1°/~11km) does **not** provide `wind_speed_10m`,
    `wind_direction_10m`, or `precipitation` through this API at all —
    a real request for those variables returns HTTP 200 with every
    value `null`. Disqualified: cannot supply required variables.
  - `era5_seamless` and the unset `best_match` default both silently
    blend ERA5-Land (temperature/dewpoint) with ERA5 (wind/precipitation)
    per grid cell/date — confirmed by byte-identical values against pure
    `era5_land`/`era5` requests at the same coordinates. Disqualified:
    exactly the "silently mixing sources" this checkpoint forbids.
  - `ecmwf_ifs` (2017-present, ~9km) has every required variable and
    covers this corpus's real date range (earliest real outbreak date:
    2018-02-01), but Open-Meteo's own documentation states it is an
    operational analysis archive using "the most up-to-date version of
    IFS" at each date — not a fixed-version reanalysis — and explicitly
    recommends ERA5/ERA5-Land instead "to ensure data consistency" across
    multi-year studies. Disqualified: not temporally consistent.
  - `cerra` (5km, Europe-only) returns `"No data is available for this
    location"` for both real smoke AOIs. Disqualified: no coverage.
  - `era5` (0.25°/~25km, 1940-present) is the only model confirmed to
    provide `temperature_2m`, `dew_point_2m`, `precipitation`,
    `wind_speed_10m`, and `wind_direction_10m` together, as a single
    fixed-version reanalysis, covering the corpus's full real date
    range. Selected for variable coherence and temporal consistency —
    explicitly NOT for any performance reason (no model exists yet).
  Full evidence trail: `services/geospatial/weather/era5.py` module
  docstring.
- **Variables**: `temperature_2m`, `dew_point_2m`, `relative_humidity_2m`
  (derived per-hour via Magnus-Tetens, then averaged — never averaging
  already-averaged T/Td), `precipitation`, and `mean_u10`/`mean_v10`.
- **Checkpoint 5.5 correction — hourly-paired wind, not daily-max +
  dominant-direction**: the Checkpoint 5 adapter derived `u10`/`v10`
  from `wind_speed_10m_max` paired with `wind_direction_10m_dominant` —
  two independent daily summary statistics that do not describe one
  coherent wind vector. `build_pre_t0_weather_summary` now retrieves
  PAIRED HOURLY `wind_speed_10m`/`wind_direction_10m`, converts each
  hour's own pair to `(u, v)` independently (`aggregate_hourly_wind`),
  and averages the COMPONENTS — never averaging compass bearings
  arithmetically (350°+10° never becomes 180°). Optional
  `vector_resultant_speed`/`directional_persistence` are reported only
  when mathematically defined. Wind direction is **never** treated as
  disease-spread direction.
- **Checkpoint 5.6 correction — date-only t0 uses the AOI's own
  source-local civil date, not an unconditional UTC date**: Checkpoint
  5.5's `T0Precision.DATE_ONLY` cut off at midnight UTC — defensible
  only if the source date field is itself a UTC calendar date, which
  this corpus's fields are not. `t0_resolution.py` now resolves the
  AOI's real IANA timezone OFFLINE (`timezonefinder`, no network call)
  and converts local midnight to UTC via `zoneinfo`, which applies the
  HISTORICALLY correct offset for that specific date (verified
  empirically necessary: Sri Lanka's real UTC offset was different
  before ~2006 than it is today — `zoneinfo` gets this right, a
  hardcoded "+5:30 always" rule would not). If no IANA timezone can be
  defensibly resolved, every result is BLOCKED, never silently UTC.
  `T0Precision.TIMESTAMP` relaxes to `weather_timestamp_utc <=
  exact_t0_utc` when a real exact instant is known (a naive input is
  used but stamped `ASSUMED_UTC_NAIVE_TIMESTAMP_INPUT`, never a silent
  default). `WEATHER_LOOKBACK_HOURS_DEV_DEFAULT=24` remains an
  `UNFROZEN_DEVELOPMENT_PARAMETER` (`config.py`).
- **Checkpoint 5.6 correction — valid-time vs. availability-time,
  explicitly separated**: `RETROSPECTIVE_REANALYSIS_STATE_PROXY`
  (renamed from the overclaiming `OBSERVED_REANALYSIS_AT_T0`) answers
  only "was this value's meteorological valid_time pre-t0?" — it is
  never a claim that the value was operationally available by t0.
  `WeatherAvailabilityQuality.UNKNOWN` by default; a `LAG_RULE_PROXY`
  value is only produced under the optional, citation-backed
  `strict_operational_availability=True` mode (official ERA5T ~5-day
  preliminary-release lag, ECMWF/Copernicus documentation), never
  `ACTUAL`. `REALIZED_FUTURE_REANALYSIS` remains hard-gated behind
  `allow_future_reanalysis=True`, defaulting to BLOCKED.
  `build_pre_t0_weather_summary` structurally cannot leak future data —
  it never requests or considers a timestamp at/after its own cutoff.
  See `ENVIRONMENTAL_FEATURE_PROTOCOL.md`.
- **Status**: REAL — re-verified with real Sri Lanka Chavakachcheri
  data, timezone-corrected pre-t0 window 2020-09-07T18:30Z..2020-09-08T18:30Z
  (Asia/Colombo local midnight 2020-09-09T00:00+05:30, 24 real hourly
  samples): mean_T=28.9°C, derived mean_RH≈80.0%, precip_accum=1.0mm,
  mean_u10≈3.66 m/s, mean_v10≈4.63 m/s, directional_persistence≈0.98.
  Values shifted from Checkpoint 5.5's UTC-midnight-based window, as
  expected from the timezone correction (full before/after regression:
  `DATA_AUDIT.md` §67).

## 4. Hydrology — HydroRIVERS (rivers); HydroLAKES (lakes, deferred)

- **HydroRIVERS v1.0** (HydroSHEDS): continental shapefile
  distribution, Asia ("as") region — the only region integrated, since
  both smoke AOIs fall within it. Distance computed the geodesic-safe
  way: AOI point and candidate river reaches are reprojected into the
  AOI's own UTM analysis CRS (`crs.analysis_crs_for`, never one
  hardcoded country CRS) and the minimum planar distance is taken there
  — never raw lat/lon degree differences. License: HydroSHEDS Data
  License Agreement, free for non-commercial/scientific use.
  - Verified: Sri Lanka 4.33km (UTM 44N), Thailand 3.01km (UTM 48N).
- **HydroLAKES**: **deliberately deferred**. It ships as a single
  global file, which exceeds this checkpoint's "smallest real subset"
  scope. `distance_to_nearest_lake_km` always returns BLOCKED with that
  documented reason — never a fabricated distance.

## 5. Elevation — AWS "Terrain Tiles" (real, honestly-labeled, NOT NASADEM)

- **NASADEM** (the dataset usually meant by "elevation" in this
  context) requires a NASA Earthdata Login; no registered credentials
  are available in this environment. `elevation/nasadem.py` always
  returns BLOCKED with that reason rather than silently substituting
  another dataset under NASADEM's name.
- **AWS Terrain Tiles** (`elevation-tiles-prod`, Terrarium PNG
  encoding) is a real, separate, no-auth dataset (a mosaic of SRTM/NED/
  EU-DEM and other public DEMs) used as the actual smoke-test elevation
  source, explicitly labeled as a different dataset from NASADEM in
  every place it appears (module docstring, `dataset_name` field, and a
  dedicated test asserting "NASADEM" never appears in it).
- Elevation is a real single-pixel decode
  (`elevation_m = R*256 + G + B/256 - 32768`) via a windowed
  `/vsicurl/` read of one 256×256 PNG tile.
- **Slope is intentionally not computed** in this checkpoint — a
  geospatially-correct slope needs a real multi-pixel DEM window with a
  meter-based gradient; approximating it now would risk the
  degrees-as-meters error the master spec explicitly forbids.
- **Status**: `AVAILABLE_NOT_YET_SELECTED` — real values were retrieved
  and verified (Sri Lanka 9.0m, Thailand 160.0m, both plausible), but
  elevation is not automatically included in PISTES; no scientific-role
  justification has been decided in this checkpoint.

---

## Package architecture (Part 4)

```
services/geospatial/
  crs.py              AOI-aware CRS policy (UTM zone/hemisphere from centroid)
  distance.py         Geodesic distance/bearing (pyproj.Geod, WGS84)
  grid.py             Smoke-test computational grid generator
  raster.py           Shared bbox + download/cache helpers
  source_geometry.py  geometry_by_source[source_id] per grid cell
  source_registry.py  Machine-readable registry (this document's source of truth)
  feature_result.py   Common FeatureResult contract (REAL/MISSING/BLOCKED/DEMO)
  temporal_leakage.py Leakage guard functions (Part 16)
  landcover/           base.py, esa_worldcover.py
  host_density/         base.py, fao_glw.py
  weather/              base.py, era5.py, t0_resolution.py, humidity.py, wind.py
  hydrology/             base.py, hydrosheds.py
  elevation/             base.py, nasadem.py, terrain_tiles.py
```

## Local data caching (Part 20)

All real downloads are cached under the repo-root `local_data/gis/`
(covered by the existing root `.gitignore` — never committed):

```
local_data/gis/glw/5_Ct_2015_Da.tif           (cattle count raster, ~10MB)
local_data/gis/glw/5_Bf_2015_Da.tif           (buffalo count raster, ~5MB)
local_data/gis/glw/8_Areakm_cattle.tif        (real per-pixel area raster)
local_data/gis/glw/8_Areakm_buffalo.tif       (identical grid, cached per-species)
local_data/gis/hydrosheds/HydroRIVERS_v10_as_shp.zip  (Asia rivers, ~90.5MB)
```

ESA WorldCover and AWS Terrain Tiles are read via windowed `vsicurl`
requests and are never cached as full files locally. SHA-256 hashes for
every cached static file are recorded in
`local_data/manifests/gis_source_registry.json`.
