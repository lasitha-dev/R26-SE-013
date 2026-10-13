# Environmental Feature Protocol — Checkpoint 5 / 5.5 / 5.6

This document is a **decision gate**, not a decision. It records the
possible primary weather-feature formulations available once real ERA5
data is retrievable (`services/geospatial/weather/era5.py`), so that
when a formulation is eventually chosen, the choice is visible,
deliberate, and made **before** any model exists — never selected
retroactively because it happened to produce a better metric.

## PERMANENT RULE (Checkpoint 5.6)

**PRE-T0 REANALYSIS VALID TIME IS NOT THE SAME AS REAL-TIME DATA
AVAILABILITY.** A weather value has two separate timestamps: its
METEOROLOGICAL VALID TIME (the instant it describes) and its DATA
AVAILABILITY TIME (when it was actually published/computable). ERA5 is
a *retrospective* reanalysis — a value dated before t0 was, in almost
every real historical case, not actually published until much later
(official ECMWF/Copernicus documentation, confirmed 2026-08-19: ERA5T
preliminary release ~5 days after each day; final ERA5 ~2 months later,
https://confluence.ecmwf.int/spaces/CKB/pages/76414402/ERA5+data+documentation).
Checkpoint 5.5's wording ("information a real deployed forecaster would
have had") conflated these two questions and has been corrected
throughout this codebase (`weather/base.py`, `weather/era5.py`). See
"Valid-time vs. availability-time" below for the full corrected design.

## Checkpoint 5.6: timezone-safe t0 + explicit availability semantics

Two further corrections, both scientific-semantics fixes, not new
feature-engineering decisions:

1. **`DATE_ONLY` t0 now uses the AOI's own source-local civil date, not
   an unconditional UTC date.** Checkpoint 5.5 always cut off at
   midnight UTC — defensible only if the source date field were itself
   a UTC calendar date, which this corpus's date fields are not. The
   real IANA timezone is resolved OFFLINE (`timezonefinder`, no network
   call — see `weather/t0_resolution.py`) and the historically-correct
   UTC offset for that specific date is computed via `zoneinfo` (proven
   empirically necessary: Sri Lanka's real UTC offset differed before
   ~2006 from today's — a hardcoded "always +5:30" rule would silently
   misdate every pre-2006 record). If no timezone can be defensibly
   resolved, the result is unresolved (BLOCKED), never silently UTC.
2. **Valid-time and availability-time are now two separate, explicit
   fields**, never conflated. `WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY`
   (renamed from the overclaiming `OBSERVED_REANALYSIS_AT_T0`) answers
   only "was this value's valid_time pre-t0?" `WeatherAvailabilityQuality`
   (`UNKNOWN` by default, `LAG_RULE_PROXY` only under the optional,
   citation-backed `strict_operational_availability=True` sensitivity
   mode, never `ACTUAL`) answers the separate, harder "was this value
   actually available by t0?" question. See "Valid-time vs.
   availability-time" below.

## Checkpoint 5.5: the model itself, and the primary rule, are now frozen

Two things changed from Checkpoint 5, both corrections, not new
decisions about feature engineering:

1. **Weather model identity is now explicit and defensible.** Checkpoint
   5's adapter described its data as "ERA5/ERA5-Land" without ever
   passing Open-Meteo's `models=` parameter — meaning it was actually
   served by whichever model the unset `best_match` default silently
   picked for that date/location. Re-verified directly against
   Open-Meteo (live requests + official docs, 2026-08-19): `era5_land`
   cannot supply wind/precipitation through this API at all;
   `era5_seamless`/`best_match` silently blend ERA5-Land and ERA5 per
   grid cell/date; `ecmwf_ifs` is a temporally-inconsistent operational
   archive per Open-Meteo's own documentation; `cerra` doesn't cover
   either smoke AOI. **`models=era5` is now passed explicitly on every
   request** (`WEATHER_MODEL = "era5"` in `era5.py`) — a single,
   fixed-version reanalysis, never the unset default. Full evidence
   trail: `era5.py` module docstring, `GIS_DATA_SOURCES.md` §3.
2. **PRIMARY HISTORICAL WEATHER INFORMATION is now frozen as PRE-T0
   OBSERVED REANALYSIS HISTORY ONLY** — see "The frozen primary rule"
   below. This is a temporal-leakage-safety freeze, not a feature-
   engineering choice; it does not pick among formulations 1-3 below.

## Why this gate exists

`weather/era5.py` can retrieve real reanalysis for any date, including
dates after a hypothetical forecast origin `t0`. That capability must
not be conflated with what a deployed system could actually know at
prediction time. Temporal categories are hard-coded in `weather/base.py`:

- **`RETROSPECTIVE_REANALYSIS_STATE_PROXY`** (Checkpoint 5.6; renamed
  from `OBSERVED_REANALYSIS_AT_T0`) — reanalysis whose meteorological
  valid_time is on or before `t0`. This is a retrospective
  environmental-state proxy, acceptable for retrospective research —
  it is explicitly NOT a claim that a real deployed forecaster had this
  exact value at t0 (see "Valid-time vs. availability-time" below).
- **`REALIZED_FUTURE_REANALYSIS`** — reanalysis for a date after `t0`.
  This is real historical data, but from the *future* relative to the
  hypothetical prediction time. It is only valid for a clearly-labeled
  retrospective/oracle analysis (e.g. "how much would knowing the
  actual following week's weather have helped, as an upper bound") —
  **never** as a primary, deployable input feature. `fetch_daily_weather`
  hard-gates this behind `allow_future_reanalysis=True` (default
  `False`) and returns BLOCKED otherwise.
- **`OPERATIONALLY_AVAILABLE_REANALYSIS`**, **`LIVE_OPERATIONAL`**,
  **`UNKNOWN`** — reserved roles for future use (a genuine operational-
  availability-validated mode, and a real live-deployment adapter);
  never produced by this checkpoint's code.

## Valid-time vs. availability-time (Checkpoint 5.6)

Two SEPARATE safety questions, both explicit from this checkpoint on:

- **A. METEOROLOGICAL VALID-TIME SAFETY** — was this weather value's
  own valid_time strictly before t0? Enforced structurally by
  `t0_resolution.is_timestamp_eligible` — `build_pre_t0_weather_summary`
  never even requests a timestamp that could fail this check.
- **B. OPERATIONAL AVAILABILITY SAFETY** — was this exact reanalysis
  value actually published/computable by t0? A separate, harder
  question. `WeatherAvailabilityQuality.UNKNOWN` by default (passing A
  never implies B). A `LAG_RULE_PROXY` value is only produced under the
  optional, explicit `strict_operational_availability=True` sensitivity
  mode, which additionally excludes any hour that would not yet have
  been published under the documented ~5-day ERA5T preliminary-release
  lag (`ERA5T_PRELIMINARY_LAG_DAYS`, official ECMWF/Copernicus
  documentation, never an invented exact publication timestamp).
  `ACTUAL` is never produced anywhere in this pipeline.

Real consequence, not hypothetical: with this checkpoint's smoke-test
`lookback_hours=24`, enabling `strict_operational_availability=True`
for the Sri Lanka smoke AOI eliminates every sample (0 of 24 hours
satisfy the strict rule) — the entire 24h lookback window sits within
the 5-day lag, so under a strict operational-availability
interpretation, none of it would have been usable in real time. This is
reported honestly (`MISSING`, not fabricated) whenever the strict mode
is used; the default primary path does not make this claim at all.

## The frozen primary rule (Checkpoint 5.5, timezone-corrected in 5.6)

**PRIMARY HISTORICAL WEATHER INFORMATION = PRE-T0 RETROSPECTIVE
REANALYSIS HISTORY ONLY** (safety question A only; B stays `UNKNOWN`
unless explicitly opted into). Enforced structurally in
`build_pre_t0_weather_summary`:

- **`t0_precision = DATE_ONLY`** (the common case — this corpus's
  `outbreak_start_date`/`proxy_availability_date` fields are calendar
  dates, not exact trigger timestamps): the cutoff is midnight of the
  t0 date in the AOI's own SOURCE-LOCAL civil timezone (Checkpoint 5.6
  — resolved offline via `timezonefinder`, converted to UTC via
  `zoneinfo` using the historically-correct offset for that date, never
  an unconditional UTC midnight and never a hardcoded per-country
  offset), and eligibility requires `weather_timestamp_utc < cutoff_utc`
  (strict). If no IANA timezone can be defensibly resolved for the
  coordinate, every result is BLOCKED — never silently treated as UTC.
- **`t0_precision = TIMESTAMP`** (only when a real exact instant is
  known): an explicit UTC offset on the input is trusted; a naive
  (offset-less) input is still usable but stamped
  `ASSUMED_UTC_NAIVE_TIMESTAMP_INPUT` — never a silent default.
  Eligibility relaxes to `weather_timestamp_utc <= cutoff_utc`.
- `REALIZED_FUTURE_REANALYSIS` remains excluded from this primary path
  entirely — `build_pre_t0_weather_summary` never requests or considers
  a timestamp at/after its own cutoff, so it cannot leak future
  information even in principle, not merely by a checked flag.
- A historically issued weather **forecast** (as opposed to reanalysis)
  may be used later only through a separate archive/protocol with
  genuine issue-time provenance — no such archive exists in this
  pipeline, and D+1..D+7 forecast weather is never fabricated to fill
  that gap.

## What remains explicitly UNFROZEN

- **`lookback_hours`** — `config.WEATHER_LOOKBACK_HOURS_DEV_DEFAULT = 24`
  is an `UNFROZEN_DEVELOPMENT_PARAMETER`: a documented fixture (the
  previous completed 24 hours before t0) used for Checkpoint 5.5's
  smoke tests only, never claimed epidemiologically optimal. Candidate
  lookback durations are future development-fold work, evaluated
  strictly inside training folds, never against a held-out validation
  signal used to pick the "final" duration.
- **Which formulation of pre-t0 history to summarize** (see candidates
  below) — the freeze above fixes the *cutoff safety rule*, not the
  *aggregation strategy*.

## Candidate primary formulations (not yet chosen)

Any of these would use only pre-t0 `RETROSPECTIVE_REANALYSIS_STATE_PROXY`
data — the distinction between them is *how much history before t0* is
summarized and *how*, not *whether* future data leaks in (that question
is now closed by the frozen rule above):

1. **State-at-t0 only** — the single most recent completed day's mean
   `temperature_2m`, `relative_humidity_2m`, `precipitation`, `u10`,
   `v10`. Simplest, cheapest, most sensitive to a single noisy day.
2. **Short trailing window (e.g. 3-7 day mean/sum)** — smooths daily
   noise, plausible for slower-moving covariates like cumulative
   precipitation or humidity trend. Requires deciding the window length
   and aggregation (mean vs. sum vs. max) per variable — a longer
   `lookback_hours` value in `build_pre_t0_weather_summary`.
3. **Trailing window + trend** — window mean plus a simple slope term
   (e.g. is temperature rising or falling into t0). More expressive,
   more parameters, more ways to overfit with limited outbreak events.

## What this checkpoint does NOT do

- **Does not pick one of the above.** No ST-DBSCAN tuning, no model
  training, and therefore no performance signal exists yet to justify
  preferring one formulation — picking now would be an unjustified,
  unfalsifiable choice dressed up as a decision.
- **Does not build any feature-assembly pipeline** that combines these
  into a single vector; `build_pre_t0_weather_summary` returns one
  `FeatureResult` per raw/derived variable per query, nothing more.
- **Does not freeze `lookback_hours`** — see "What remains explicitly
  UNFROZEN" above.

## When this gate should be revisited

Once ST-DBSCAN/PISTES model development begins (a later checkpoint),
the choice among formulations 1-3 (or a variant) and the specific
`lookback_hours` value should be made **before** looking at any
validation metric, and the reasoning recorded here, updating this
document — not decided by whichever formulation happens to score best
on the walk-forward folds (which would itself be a form of leakage:
tuning feature engineering against the test signal).

## Related temporal-leakage guards (Part 16, preserved)

`services/geospatial/temporal_leakage.py` provides standalone functions
usable once feature assembly exists:

- `landcover_year_mismatches_forecast_year(...)` — flags ESA WorldCover
  land cover used for a target year it does not match (WorldCover only
  ships 2020/2021) — see `services/geospatial/landcover/esa_worldcover.py`'s
  `resolve_landcover_temporal_role` (Checkpoint 5.5 Part 10) for the
  per-extraction version of this same check.
- `host_density_used_as_exact_truth(...)` — flags any host-density
  result not carrying `STATIC_REFERENCE_PROXY` (GLW4's reference year
  is 2015; it must never be presented as an exact/current herd count).
- `weather_leaks_future_information(...)` — flags any weather result
  carrying `REALIZED_FUTURE_REANALYSIS` reaching a primary feature path.
  `build_pre_t0_weather_summary`'s results never carry this role by
  construction (see "The frozen primary rule" above).

## Host-density gate (Checkpoint 5.6 Parts 9-11)

A parallel decision gate, not a weather question, but recorded here
because it follows the same "no arbitrary parameter choice" principle:
`host_density/fao_glw.py`'s `extract_grid_cell_density` (the PRIMARY
host-density feature for the computational risk grid) uses an
overlap-area-weighted mean across whichever real GLW4 source pixels
intersect a grid cell's own bounds — never an arbitrary AOI-window
radius. Checkpoint 5.5 showed a 5km vs. 10km window changing the Sri
Lanka cattle density from 0.0 to ~44.6 animals/km² at the SAME centroid,
with no principled reason to prefer either; that radius parameter has
been removed from the final grid feature entirely, not tuned to a
"better" value. `source_resolution` (GLW4's real ~10km grid) and
`target_grid_resolution` (the computational cell's own size) are always
reported together — a smaller computational grid never implies a finer
livestock measurement than GLW4 actually contains.

## Checkpoint 6A: this protocol now feeds a real assembly layer

`services/features/` (`FEATURE_ASSEMBLY_PROTOCOL.md`) is the first
consumer of every rule above, assembled into a `FeatureSnapshot` — no
risk/direction/speed computation happens there either. Two corrections
to this document's own terminology, both applied for consistency with
that layer:

- **`strict_operational_availability=True` is the
  ERA5T_LAG_FILTER_SENSITIVITY diagnostic mode**, named explicitly as
  such wherever it is documented from here on (Checkpoint 6A Part 8).
  The underlying numerical values it returns are still FINAL ERA5
  values — this mode only FILTERS which valid-times are included
  (by the documented ~5-day ERA5T lag), it does not fetch genuine
  ERA5T-vintage numbers. It must never be described as
  "ACTUAL_OPERATIONAL_ERA5" or a "historically available ERA5T
  reconstruction," and `services/features/assembler.py`'s primary
  assembly path never enables it — every `FeatureSnapshot` built there
  uses `strict_operational_availability=False`,
  `availability_quality=UNKNOWN`,
  `temporal_role=RETROSPECTIVE_REANALYSIS_STATE_PROXY` (verified by
  `WX-ASSEMBLY-02` grepping `assembler.py`'s own source).
- **Weather is sampled once per snapshot, at the AOI center** — see
  `FEATURE_ASSEMBLY_PROTOCOL.md` §4 for the full rationale (ERA5's
  ~25km resolution is coarser than the entire smoke-grid extent, so
  per-cell/per-source sampling would only add redundant API calls, not
  real spatial information).

## Checkpoint 6A.5: declared model can no longer disagree with the actual request

A real reproducibility bug, now fixed: `build_pre_t0_weather_summary`'s
`model=` parameter previously had no effect on the actual HTTP request
sent to Open-Meteo (`era5.py`'s `_hourly_request_params` hardcoded the
`WEATHER_MODEL` constant regardless of what `model` was passed) — so a
caller could report `weather_model="era5_land"` in a `FeatureSnapshot`
while the real request still silently fetched `era5` data. Fixed: the
request now always uses the caller's own `model` argument, and any
`model` other than `WEATHER_MODEL` ("era5" — the only model this
pipeline has investigated) is refused (`BLOCKED`), never silently
substituted. `services/features/feature_policy.FeaturePolicy` also now
restricts `weather_model` to `{"era5"}` at construction time. Full
before/after evidence: `FEATURE_ASSEMBLY_PROTOCOL.md` §2.1.

Also corrected: the ambiguous `environment_temporal_mode` `FeaturePolicy`
field (which could change the feature-protocol hash without changing
any assembled feature, and was easily confused with the unrelated
outbreak/source-availability `RETROSPECTIVE_PROXY` temporal mode) is
removed. The historical assembler's ONE legal weather temporal role is
now a fixed constant, `PRIMARY_WEATHER_TEMPORAL_ROLE =
"RETROSPECTIVE_REANALYSIS_STATE_PROXY"` — never a configurable field.

## Checkpoint 7C — wind reused directly by model development

`services/model_development/wind_readiness_7c.py` calls
`build_pre_t0_weather_summary` exactly as `assembler.py` does (same
`t0_precision`/`strict_operational_availability=False`/AOI-center
convention, `assembler._aoi_center` imported directly rather than
re-derived). `environmental_suitability_factor`/`water_context_factor`
remain `NOT_YET_SCIENTIFICALLY_DEFINED` and are not read by 7C at all —
only the real `mean_u10`/`mean_v10` pair feeds the (separate)
`services/hazard/anisotropy.py` primitive. See
`ENVIRONMENTAL_WIND_MODEL_DEVELOPMENT_PROTOCOL.md`.
