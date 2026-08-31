# Factor Transformation Protocol — Checkpoint 6D / 6D.5 / 6D.6

This document specifies `services/factors/` — the real-data
feature→factor transformation FOUNDATION built in Checkpoint 6D and
corrected in Checkpoint 6D.5. It proves raw `FeatureSnapshot` inputs
can be turned into auditable, leakage-safe, provenance-preserving
DEVELOPMENT-ONLY candidates. It does **not** implement a final PISTES
predictive model, and it does **not** feed any real value into the
hazard engine.

## 0. Checkpoint 6D.5 corrections (read this first)

Checkpoint 6D's `FactorReferenceProfile` had a real scientific-identity
gap, found and fixed before any production use: `reference_profile_hash()`
covered only summary quantiles (p05/p25/p50/p75/p95/lower/upper), not
the full effective `EMPIRICAL_CDF_REFERENCE` support
(`host_density_total_reference_values`) — two profiles with different
interior reference distributions could alias to the SAME hash if their
percentiles happened to match. Also corrected in the same pass:

- **Raster vs. query identity** (§3 below): static reference-observation
  identity now prefers the real underlying raster pixel(s) a value was
  computed from (`FeatureResult.sample_identity`, new in 6D.5 —
  populated by `host_density/fao_glw.py` from the real, already-computed
  pixel-overlap geometry, never fabricated), falling back to the
  rounded query centroid only when an adapter can't supply one.
- **Host-total identity** (§4): derived from the cattle/buffalo
  observation identities themselves, never independently re-derived.
- **Dataset-compatibility firewall** (§7): incompatible host dataset
  strata can no longer silently pool.
- **Unit safety** (§9): `cattle + buffalo` requires matching canonical
  units (`animals_per_km2`) — never summed across incompatible units.
- **Degenerate reference span** (§9): returns an explicit
  `DEGENERATE_REFERENCE_DISTRIBUTION` status, never a silent `0`.
- **ECDF tie convention** (§9): now explicit
  (`EcdfTieConvention.LOWER_RANK`/`MID_RANK`) and part of
  `transform_config_hash`.
- **Honest global-readiness labeling** (§11): a small diagnostic sample
  is never presented as `GLOBAL_REFERENCE_PROFILE_READY`.

See `DATA_AUDIT.md` §75 for the full before/after correction record and
real re-run results.

## 1. Permanent rule

A scientifically BLOCKED factor is an acceptable result. Fabricating a
factor to make the full hazard equation run is **not** acceptable. This
checkpoint would rather report `environmental_suitability_factor =
NOT_YET_SCIENTIFICALLY_DEFINED` forever than invent a weighted sum to
fill the gap.

## 2. Lineage (permanent diagram)

```
RAW FeatureSnapshot
        |
        v
FIT_DEVELOPMENT-only reference observations
        |
        v
FactorReferenceProfile
        |
        v
candidate real transformations
        |
        +--> Host factor CANDIDATES (LOG1P_ROBUST_REFERENCE_SCALE, EMPIRICAL_CDF_REFERENCE)
        |
        +--> Environmental COMPONENTS (temperature/humidity/precipitation/landcover)
        |       scalar suitability NOT_YET_SCIENTIFICALLY_DEFINED
        |
        +--> Water raw context (distance_to_river preserved)
        |       factor NOT_YET_SCIENTIFICALLY_DEFINED
        |
        +--> Real u10/v10 meteorology (AOI_CENTER_UNIFORM_REAL_PROXY)
        |       speed effect NOT_YET_SELECTED
        |
        +--> Source strength
                NOT_YET_SCIENTIFICALLY_DEFINED
        |
        v
FactorSnapshot   (label: DEVELOPMENT_FACTOR_TRANSFORMATION_DIAGNOSTIC)
```

**NO REAL HAZARD PREDICTION HAPPENS HERE.** `FeatureSnapshot` remains
raw and immutable — this package never overwrites cattle/buffalo
density, land-cover fractions, temperature/dewpoint/precipitation/
humidity, u10/v10, HydroRIVERS distance, elevation, or any source
metadata; every transformation creates a NEW object.

## 3. Architecture and independence

```
services/factors/
    __init__.py
    contracts.py              — candidate/status vocabulary, TransformedFactorProvenance
    transform_config.py         — FactorTransformConfig (UNFROZEN_DEVELOPMENT_CANDIDATE only)
    reference_profile.py         — FactorReferenceProfile + the FIT_DEVELOPMENT firewall
    reference_observations.py     — ReferenceObservation identity/de-duplication
    host_transform.py              — host_density_total + LOG1P/EMPIRICAL_CDF candidates
    environmental_components.py     — raw component preservation, NO weighted sum
    meteorology_adapter.py           — real u10/v10 -> RealMeteorologyObservation
    water_context.py                  — raw distance preserved, factor undefined
    source_strength.py                 — factor undefined
    factor_snapshot.py                  — FactorSnapshot + deterministic identity
    audit.py                             — distribution/provenance-only reporting
```

Transformation-FITTING logic never lives inside `services/hazard/` —
that package remains a pure mathematical consumer of already-decided
factor values (Checkpoint 6C/6C.5, unchanged). `services/factors/`
freely imports `FeatureSnapshot`-shaped data (unlike `services/hazard/`,
which stays independent of it) because that IS this package's job.

**Contract**: every function in this package consumes/produces
`FeatureSnapshot.as_dict()`-shaped plain dicts, not the dataclass
objects directly — this matches what is actually cached on disk
(`local_data/feature_snapshots/*.json`) and what the real assembler
produces via `.as_dict()`, and avoids a second, parallel dataclass
surface.

## 4. Model-fitting exposure firewall (Part 3)

`reference_profile.assert_factor_development_only` reuses
`model_fitting_exposure.assert_fit_development_only` — the SAME hard
firewall the ST-DBSCAN development layer uses (Checkpoint 6B.5).
`build_factor_reference_profile` calls it at its own entry point,
raising `ValueError` (never silently filtering) the instant any
supplied origin is not `FIT_DEVELOPMENT`. A mixed development+held-out
list rejects the WHOLE call. `HELD_OUT_FROM_MODEL_FITTING` and
`SRI_LANKA_TRANSFER_CASE_STUDY` origins can never influence reference
quantiles, transformation selection, clipping boundaries, feature
inclusion, or missingness thresholds.

No factor-transformation function accepts a future target coordinate,
outcome label, capture metric, direction/speed error, or prediction
accuracy — verified structurally (no such parameter/field exists
anywhere in the package).

## 5. Reference-observation de-duplication (Part 5) — CORRECTED in 6D.5, see §16

`reference_observations.py` prevents pseudo-replication of raw feature
values:

- **STATIC** layers (host density, land cover, HydroRIVERS): identity =
  `(dataset_name, dataset_version, feature_name, real underlying raster
  sample identity when available — §16 — else rounded resolved query
  coordinates)`. The SAME real-world raster observation appearing in
  multiple forecast origins' overlapping AOIs, or reached via two
  different query centroids that resolve to the same pixel(s), is ONE
  reference observation.
- **DYNAMIC** layers (weather): identity = `(weather model, sampling
  location, weather window, feature_name)`. One AOI-center weather
  observation expanded across N hazard grid cells is counted ONCE — the
  loop is over snapshots, never over grid cells, because
  `FeatureSnapshot.weather` is sampled once per snapshot.

Every report includes raw appearances, unique observations, and the
resulting de-duplication ratio — never hidden.

## 6. `FactorReferenceProfile` (Parts 6-8, 26) — hash CORRECTED in 6D.5, see §16

Built ONLY from `FIT_DEVELOPMENT` material. **No AOI/per-origin/
per-cell-neighborhood min/max/mean/quantile is ever used anywhere
downstream** — every candidate scaling reads from this ONE precomputed
profile. `reference_profile_hash()` excludes `generated_at`; same
development corpus + config -> same hash — and (6D.5 correction) now
covers the FULL effective reference support via
`reference_observation_digest`, not only summary quantiles (§16).

**Dataset-compatibility firewall (Part 26, ENFORCED not just reported
as of 6D.5 §17)**: `dataset_version_composition`,
`landcover_comparability_composition`, and `weather_model_composition`
still record everything that was pooled for visibility; additionally,
`dataset_compatibility_stratum` now HARD-BLOCKS pooling of an
incompatible host-dataset mix under `STRICT_COMPATIBLE` mode — see §17.

**No country-specific normalization by default (Part 8)**: the primary
reference profile pools all FIT_DEVELOPMENT countries together. A
country-specific SENSITIVITY mode would need its own explicit config/
hash and is not built or selected in this checkpoint. Country is NEVER
automatically a compatibility stratum (§17) — only real dataset-lineage
facts are.

## 7. Host-density combination and candidates (Parts 9-12) — safety CORRECTED in 6D.5, see §18

`host_density_total = cattle_density + buffalo_density` **only** when
BOTH are `REAL`, both carry the SAME canonical unit
(`animals_per_km2`, §18), and both are finite/non-negative — never
substituted with zero when unusable, never summed across incompatible
units. GLW density remains a host-density **PROXY** — never "farm
count," "actual farm inventory," or "exact animal population." A real
raster value of `0` is preserved as a genuine observation, distinct
from `MISSING` — it is **not** proof that no susceptible livestock
exists in reality.

Two explicit candidates (`HostTransformFamily`), neither scientifically
selected:

- `LOG1P_ROBUST_REFERENCE_SCALE`: `z = clip((log1p(x) - ref_lower) /
  (ref_upper - ref_lower), 0, 1)` using FIT_DEVELOPMENT reference
  quantiles (`log1p_reference_lower_quantile`/`_upper_quantile`,
  default 0.05/0.95, `UNFROZEN_DEVELOPMENT_CANDIDATE`). `reference_upper`
  is never called "maximum biological density." A degenerate reference
  span (`upper <= lower`) now returns an explicit
  `DEGENERATE_REFERENCE_DISTRIBUTION` status, never a silent `0` (§18).
- `EMPIRICAL_CDF_REFERENCE`: deterministic percentile rank within the
  FIT_DEVELOPMENT reference sample using an EXPLICIT, documented tie
  convention (`EcdfTieConvention.LOWER_RANK`/`MID_RANK`, part of
  `transform_config_hash` — §18) — `0..1` is a relative/reference
  scale, **not** probability.

Every clipping event (`ClippingAudit`) records `was_clipped_low`/
`was_clipped_high`/the reference bounds used — bounds are never
silently adjusted to reduce clipping. See §20 for the real clipping
audit over the FULL `FIT_DEVELOPMENT` universe (never generalized from
one diagnostic cell, as Checkpoint 6D's original 8-origin finding
risked being read).

## 8. Environmental components — no invented weighted sum (Parts 13-16)

**Critical, permanent rule**: this package never constructs anything
like `0.3*humidity + 0.3*precipitation + 0.2*temperature +
0.2*landcover`, and never copies a feature-importance/percentage-
contribution/odds-ratio number from published literature and uses it as
a PISTES weight. Literature may justify variable CANDIDACY; it never
supplies fitted coefficients.

`EnvironmentalComponentVector` preserves temperature/humidity/
precipitation as independent `RAW_REAL_COMPONENT` values (no assumed
monotonic risk direction — higher temperature/humidity/rain is NOT
assumed to mean higher risk) and preserves every WorldCover land-cover
class fraction individually (never hand-combined; WorldCover version/
temporal role/comparability group travel alongside). In Checkpoint 6D,
`environmental_suitability_factor_status` is **always**
`NOT_YET_SCIENTIFICALLY_DEFINED` — no separate aggregation protocol has
been approved.

## 9. Water context (Part 17)

`distance_to_nearest_river_km` is preserved as raw provenance;
`water_context_factor` remains `NOT_YET_SCIENTIFICALLY_DEFINED`. No
"closer to river = greater LSD transmission" assumption and no invented
exponential-decay transform — Checkpoint 6C already left this
undefined, and 6D keeps it that way pending a defensible, pre-registered
transformation protocol.

## 10. Source strength (Part 18)

`source_strength_factor` remains `NOT_YET_SCIENTIFICALLY_DEFINED`.
`build_source_strength_status` takes only a `source_id` — structurally
nothing to derive a value from `affected_animals`, case count, deaths,
DQS, GPS quality, ST cluster role, cluster size, or report frequency.

## 11. Meteorology real-data adapter (Part 19)

`meteorology_adapter.build_meteorology_by_cell` preserves the real,
paired `u10`/`v10` components exactly as retrieved — never converted
into a compass bearing or "disease spread direction." `wind_speed_effect`
remains `NOT_YET_SELECTED` (no `G(v)` invented). Because
`FeatureSnapshot.weather` represents ONE AOI-center observation
(Checkpoint 5.5/5.6 architecture, unchanged), every `RealMeteorologyObservation`
is explicitly labeled `spatial_mode=AOI_CENTER_UNIFORM_REAL_PROXY` —
**never** `SPATIALLY_RESOLVED_REAL`, which is reserved for a future
checkpoint that actually retrieves independent per-cell meteorology.
This module produces the factors package's OWN
`RealMeteorologyObservation` (not `services.hazard.meteorology.CellMeteorology`)
— it never constructs a hazard-engine object with a `REAL`-status usable
value, which the hazard contracts structurally refuse anyway (Part 22).

## 12. `FactorSnapshot` and its identity (Parts 22-24)

`FactorSnapshot` carries `factor_snapshot_id`, `feature_snapshot_id`,
`forecast_origin_id`, `t0`, `expected_grid_cell_ids`,
`cell_factor_candidates`, `environmental_component_vectors`,
`source_factor_status`, `meteorology_by_cell`, `water_context_status`,
`factor_transform_config_hash`, `reference_profile_hash`,
`input_feature_signature`, `status`, `blockers`,
`label="DEVELOPMENT_FACTOR_TRANSFORMATION_DIAGNOSTIC"`, `generated_at`.
No field is ever `infection_probability`, `relative_risk_prediction`,
`direction`, `speed`, or `confidence`.

`compute_factor_snapshot_id` deterministically hashes
`feature_snapshot_id` + `transform_config_hash` + `reference_profile_hash`
+ every effective transformed component value/status (cell factor
candidates, environmental component vectors, source factor statuses,
meteorology-by-cell INCLUDING spatial provenance, water-context status)
+ the expected grid-cell set + active-source identity — never
`generated_at`, never sensitive to dict ordering (every nested mapping
is sorted before hashing). Changing any raw feature value, the
reference profile, the transform config, or the meteorology spatial
provenance changes the ID (tested, FACTOR-ID-01..07).

## 13. Architectural firewall — no real HazardSnapshot (Part 22, NO-REAL-HAZARD)

Checkpoint 6C.5's hazard contracts (`HazardFactors`/`CellHazardFactors`/
`SourceHazardFactors`/`FactorValue`) structurally accept only
`SOFTWARE_FIXTURE_ONLY`-status usable values — Checkpoint 6D does not
loosen this. No function in `services/factors/` imports
`build_hazard_snapshot`, `accumulate_cell_hazard`,
`compute_relative_risk_index`, or `compute_source_hazard` (verified via
`ast`, not text search — the docstrings here legitimately name these
symbols while explaining they are never imported). A future adapter may
connect a frozen, validated transformation to the hazard engine only
after a separate selection/freeze checkpoint explicitly authorizes it.

## 14. Real development audit (Part 27, real results)

`smoke_tests/run_factor_transformation_smoke.py` ran against 8 real
`FIT_DEVELOPMENT` Thailand forecast origins (of 136 available) —
**8 available, 0 blocked/missing.** Real reference-profile results:
200 raw host-density appearances, 200 unique observations (no dedup
collapse — 8 distinct AOIs, no overlapping real-world locations at the
6-decimal rounding used); host-density quantiles `{p05: 2.80, p50:
25.91, p95: 45.46}` animals/km²; log1p quantiles `{p05: 1.34, p95:
3.84}`; weather reference observations 8/8 unique (dedup ratio 1.0 —
expected, since each origin has a distinct `t0`/window); dataset/version
composition entirely consistent (GLW4 2015, WorldCover v200 2021,
ERA5) — no incompatibility stratification was triggered.

## 15. Scientific decision-gate answers (Part 42, updated with real 6D.5 results — see §20)

- **A. Enough FIT_DEVELOPMENT coverage for a defensible global reference
  profile?** **Yes, and now actually achieved**: the corrected,
  weather-free host-only path (§19) processed the REAL, full,
  runtime-derived `FIT_DEVELOPMENT` universe — 579/579 origins, 29
  countries, 0 blocked — in ~80 seconds. `GLOBAL_REFERENCE_PROFILE_READY`
  is honestly reported (§20).
- **B. Host-density candidates numerically usable without severe
  clipping?** Yes, over the FULL universe: 4.69% clipped low, 5.04%
  clipped high (12,591 real transformed observations) — real, moderate,
  never generalized from one cell, and varies meaningfully by country
  (§20).
- **C. Dataset-version differences blocking pooling?** No — the real
  universe's host data resolved to a single compatible stratum (GLW4
  2015, `animals_per_km2`) throughout; `n_incompatible_strata_detected=0`.
- **D. `environmental_suitability_factor` still undefined?** **Yes** —
  as expected/required.
- **E. `water_context_factor` still undefined?** **Yes** — as
  expected/required.
- **F. real `source_strength_factor` still undefined?** **Yes** — as
  expected/required.
- **G. real wind-speed magnitude effect still undefined?** **Yes** — as
  expected/required.
- **H. Can a REAL complete PISTES hazard currently be computed without
  inventing assumptions?** **No** — three of the four hazard factors
  (`environmental_suitability_factor`, `water_context_factor`,
  `source_strength_factor`) and the wind-speed effect remain
  scientifically undefined. This is the CORRECT, acceptable state at
  the end of Checkpoint 6D.5 — the blocker is not bypassed.

## 16. Corrected reference-observation identity (6D.5 Parts 1, 3-6)

**The gap**: `reference_profile_hash()` covered only summary quantiles
(p05/p25/p50/p75/p95/lower/upper) — two profiles with different
INTERIOR reference distributions could alias to the same hash if those
seven numbers happened to match, even though `EMPIRICAL_CDF_REFERENCE`
consumes the FULL sorted distribution, not just its quantiles.

**The fix**: `reference_observation_digest` — a SHA256 over every
contributing host-total observation's `(observation_id, value)` pair,
sorted deterministically — now participates in `reference_profile_hash()`.
Verified: two synthetic distributions with IDENTICAL p50 but different
interior values now produce different `reference_observation_digest`s
and different `reference_profile_hash()`es (`REFHASH-05`, passing).

**Raster vs. query identity**: `host_density/fao_glw.py.extract_grid_cell_density`
now computes and returns a real, deterministic `sample_identity` on
every REAL result — a hash of the actual contributing GLW4 pixel
center(s) (derived from the raster's own affine transform via the
SAME overlap/nodata filter the density computation itself uses, so the
identity always matches what the value was actually computed from —
`contributing_pixel_sample_identity`). `reference_observations.resolve_static_observation_identity`
uses this identity as PRIMARY, falling back to the rounded query
centroid ONLY when an adapter cannot supply one, and labels which path
was used (`identity_source: RASTER_SAMPLE | QUERY_CENTROID_FALLBACK`)
— never silently ambiguous. `FeatureResult` gained an optional
`sample_identity` field (default `None`) to carry this — fully
backward-compatible; every other adapter is unaffected.

**Real effect**: over the full 579-origin universe, this identity
correction produced genuine de-duplication — 12,591 raw appearances
collapsed to 4,974 unique underlying raster observations (a ~40%
dedup ratio), because GLW4's real ~10km pixels are shared across many
overlapping fine-grid cells from nearby forecast origins. The OLD
rounded-query-centroid identity would have under-counted this
sharing.

## 17. Dataset-compatibility firewall (6D.5 Parts 7-10)

`ReferenceCompatibilityMode.STRICT_COMPATIBLE` (the only mode in
6D.5) inspects a `ReferenceStratumKey` (`factor_family`,
`dataset_family`, `dataset_comparability_group`, `canonical_units`,
`sampling_protocol_version`) for every host observation BEFORE pooling.
If more than one distinct HOST stratum is detected among observations
that would otherwise be pooled, `FactorReferenceProfile.status` becomes
`INCOMPATIBLE_REFERENCE_STRATA` and NO pooled quantiles/reference
values are computed — never silently pooled with a warning appended
after the fact. Country is NEVER automatically a stratum. Compatibility
is factor-specific — an unrelated environmental dataset difference
(e.g. a different `weather_model`) never invalidates the HOST
reference (`COMPAT-05`, tested). The compatibility decision itself
participates in `reference_profile_hash()` (`COMPAT-06`, `REFHASH-06`).

## 18. Host-value and transform safety (6D.5 Parts 11-14)

Before summing, `host_transform.compute_host_density_total` verifies
`cattle`/`buffalo` share the SAME canonical unit (`animals_per_km2`,
read from the real GLW4 adapter's own `UNITS` constant, never
hardcoded independently) — a mismatch yields `UNIT_MISMATCH`, never a
silent sum of incompatible quantities. NaN/infinite/negative REAL
values are rejected outright (`BLOCKED`) — current real GLW4 output
should never produce them, but this is never trusted implicitly. A
degenerate `LOG1P_ROBUST_REFERENCE_SCALE` reference span
(`upper <= lower`) returns `DEGENERATE_REFERENCE_DISTRIBUTION` with
`transformed_value=None` — never a silently chosen `0`/`0.5`. The
`EMPIRICAL_CDF_REFERENCE` tie convention is now explicit
(`EcdfTieConvention.LOWER_RANK` — `bisect_left` semantics — is the
default; `MID_RANK` is the documented alternative) and lives in
`FactorTransformConfig`/`transform_config_hash`, so changing it changes
scientific identity. `host_density_total_observation_id` (the ECDF/
log1p input's own identity) is now derived from the underlying
`cattle_observation_id`/`buffalo_observation_id` themselves
(`SHA256(cattle_id + buffalo_id + canonical_units)`) — never
independently re-derived from dataset versions and rounded query
coordinates, so repeated sampling of the same real underlying
observations can never pseudo-replicate the reference distribution
(`RASTER-REF-05`, tested).

## 19. Host-only real gathering, no weather I/O (6D.5 Part 17)

`services/factors/host_reference_gathering.build_host_only_snapshot`
reuses the exact same real infrastructure the full assembler uses
(`source_selector.get_eligible_sources`, `geospatial.grid.build_smoke_grid`,
`geospatial.host_density.fao_glw.extract_grid_cell_density`) but skips
weather/land-cover/hydrology entirely — no new GIS extraction logic is
duplicated, only orchestration glue. Real timing: 10 real
`FIT_DEVELOPMENT` origins in 1.4 seconds (vs. ~29s/origin for the
weather-inclusive path) — the full 579-origin universe completed in
~80 seconds.

## 20. Real full-universe results (6D.5 Parts 18-21, real, honest)

`smoke_tests/run_host_reference_smoke.py` derived the `FIT_DEVELOPMENT`
universe AT RUNTIME from the real exposure-role ledger (never a
hardcoded count) and processed ALL of it:

- **579/579 real `FIT_DEVELOPMENT` origins** across **29 countries** —
  0 blocked, 0 missing.
- **12,591 raw host-density-total appearances -> 4,974 unique
  underlying raster observations** (real ~40% de-duplication, §16).
- Real pooled quantiles: `{p05: 1.33, p50: 6.56, p95: 105.20}`
  animals/km²; log1p quantiles `{p05: 0.85, p95: 4.67}`.
- Single compatible dataset stratum throughout — `n_incompatible_strata_detected=0`.
- **`global_reference_universe_coverage_fraction = 1.0` ->
  `GLOBAL_REFERENCE_PROFILE_READY`** — honestly earned, not asserted.
- **Real clipping audit** (`LOG1P_ROBUST_REFERENCE_SCALE`, all 12,591
  real transformed observations): **4.69% clipped low, 5.04% clipped
  high** overall — moderate, not pathological. Country-level variation
  is real and substantial and was NOT smoothed away: e.g. Bangladesh
  76.8% clipped-high (96/125), Nepal 61.1% clipped-high (275/450),
  Bhutan 13.7% clipped-low/0% clipped-high, China/Israel/Indonesia
  near-zero clipping. This reveals genuine host-density distributional
  differences across countries relative to the pooled global reference
  — reported honestly, never used to retune the frozen 0.05/0.95
  quantile boundaries, and never inspected for/against held-out or
  Sri-Lanka outcomes.

## 21. Checkpoint 6D.6 — effective weighted raster identity, value-conflict firewall, full-stratum compatibility, honest readiness

**The gap in 6D.5's `sample_identity`**: it identified only the SET of
contributing GLW4 pixels, not their normalized overlap weights. Two
grid cells can share the exact same pixel set but blend it with
different weights (e.g. one cell 90%/10% across pixels A/B, another
20%/80%) and therefore produce genuinely different effective density
values — collapsing them to one reference observation would have been
wrong. **CONTRIBUTING PIXEL SET != EFFECTIVE AREA-WEIGHTED RASTER
OBSERVATION unless the contribution weights are also equivalent.**

**The fix**: `host_density/fao_glw.contributing_pixel_sample_support`
mirrors the SAME filter (nodata excluded, positive-overlap-only) and
weighting (`frac * area_km2`, matching `compute_cell_density_from_pixel_overlaps`'s
own denominator term) used to compute the value itself, then hashes
`dataset_name + dataset_version + source_asset_id + species +
sampling_protocol_version + sorted(pixel_center, normalized_weight)`
into `sample_support_digest` — never dict-order-dependent, never
including `generated_at`. Two cells with an identical pixel set but
different normalized weights now get DIFFERENT digests; one cell fully
inside a single pixel and a second cell elsewhere fully inside the SAME
pixel still correctly share one digest (`WEIGHTED-REF-01..07`, tested;
also confirmed against the live GLW4 cache, not just synthetic data).
`FeatureResult` gained `sample_support_digest`/`sampling_protocol_version`/
`n_contributing_pixels` (all optional, backward-compatible).
`reference_observations.resolve_static_observation_identity` now
prefers this digest, falling back to the older pixel-set-only
`sample_identity`, and only then to the rounded query centroid,
labeling which path was used (`RASTER_EFFECTIVE_SAMPLE_IDENTITY` |
`QUERY_CENTROID_FALLBACK`).

**Value-conflict firewall**: the SAME observation identity producing
TWO DIFFERENT effective raw values is a DATA/IDENTITY CONFLICT, never a
duplicate — it is never resolved by keeping the first value, the last
value, or an average. `reference_profile.py`'s pooling loop now detects
this and sets `status=REFERENCE_OBSERVATION_VALUE_CONFLICT`, blocking
the ENTIRE pool (never a partially-cleaned subset), and preserves each
`ObservationConflict` (identity, first value, conflicting value)
(`REFCONFLICT-01..05`, tested).

**Comparison tolerance — a real, empirical correction**: an initial
EXACT (`==`) comparison was tried first. Rerunning the corrected
pooling logic over the real, full 579-origin `FIT_DEVELOPMENT` universe
disproved the "same computation reproduces bit-for-bit" assumption:
1,690 same-identity pairs differed under exact comparison, every one of
them by between ~3.5e-18 and ~5.7e-14 absolute — floating-point
summation-order noise in the pixel-contribution sum (not literally
re-executed in the same term order for two different query cells that
happen to share the same effective pixel support), never a genuine
differing scientific observation. `reference_observations.values_conflict`
now applies a tiny, explicitly-labeled SOFTWARE numerical tolerance
(`math.isclose(rel_tol=1e-9, abs_tol=1e-9)`) — ~5 orders of magnitude
looser than the largest real noise observed, and ~5 orders of magnitude
tighter than would be needed to call two truly different observations
"the same." This is a numerical-precision allowance for reproducing one
deterministic computation, never a scientific-similarity judgement.
After this correction, the real full-universe run produced **zero**
reference-observation conflicts.

**Full `ReferenceStratumKey` compatibility**: distinct-stratum
detection now uses `ReferenceStratumKey.canonical_key()`/`digest()` —
deterministic, field-order-independent, over ALL five fields
(`factor_family`, `dataset_family`, `dataset_comparability_group`,
`canonical_units`, `sampling_protocol_version`) — never only
`dataset_comparability_group + canonical_units`. A `sampling_protocol_version`
or `dataset_family` difference alone now correctly makes two strata
distinct even when the version/units strings happen to match
(`STRATUM-01..06`, tested).

**Corrected honest readiness rule**: `GLOBAL_REFERENCE_PROFILE_READY`
now requires ALL of: (1) every origin in the real, runtime-derived
`total_fit_development_origin_ids` universe has an ACTUALLY,
SUCCESSFULLY constructed usable snapshot (a `None`/blocked snapshot
never counts, regardless of whether the origin ID appears in a
supplied list); (2) no unexpected extra snapshot IDs; (3)
`reference_profile.status == COMPLETE_DIAGNOSTIC`; (4) zero reference
observation conflicts; (5) zero incompatible strata. `build_development_reference_audit`
reports an honest `global_reference_universe_coverage_fraction` in every
case (`READY-01..07`, tested — including the 100-intended/99-available/
1-blocked regression, which must produce `coverage_fraction=0.99` and
never `READY`). `reference_scope=GLOBAL_FIT_DEVELOPMENT_HOST_REFERENCE`
and `selection_status=UNFROZEN_DEVELOPMENT_CANDIDATE` are always
reported alongside the label so it is never misread as final transform
selection, validated predictive performance, calibrated probability,
Sri-Lanka validation, or deployment readiness.

**Real corrected full-universe results** (rerun after both corrections
above):

- **579/579 real `FIT_DEVELOPMENT` origins** across **29 countries** —
  0 blocked, 0 missing, 0 unexpected extra IDs.
- **12,591 raw host-density-total appearances -> 6,780 unique
  underlying effective raster observations** (up from 6D.5's 4,974 —
  expected and correct: the weight-aware digest is strictly stricter
  than the old pixel-set-only identity, so cells that used to
  over-merge on shared pixel sets with different weights now correctly
  split into separate observations).
- **26,786 real GLW4 species observations identified via
  `RASTER_EFFECTIVE_SAMPLE_IDENTITY`, 0 via `QUERY_CENTROID_FALLBACK`**
  — the preferred effective-support digest was available for every
  single real GLW4 extraction in the universe; no investigation of a
  nonzero fallback count was needed.
- **0 reference-observation value conflicts** (after the tolerance
  correction above).
- Single compatible dataset stratum throughout —
  `n_incompatible_strata_detected=0`.
- Real pooled quantiles: `{p05: 1.41, p50: 6.51, p95: 105.18}`
  animals/km²; log1p quantiles `{p05: 0.88, p95: 4.67}`.
- **`global_reference_universe_coverage_fraction = 1.0` ->
  `GLOBAL_REFERENCE_PROFILE_READY`** — re-earned honestly under the
  corrected, stricter identity/conflict/compatibility protocol, not
  carried over from 6D.5.
- `reference_profile_hash = e34fc9d8da9f594b5638479d5f91436d57d74564a0095355e6a44946c61ed257`
  (changed from 6D.5's, as expected — the identity/pooling logic
  itself changed).
- **Real clipping audit** (`LOG1P_ROBUST_REFERENCE_SCALE`, all 12,591
  real transformed observations): **4.92% clipped low, 5.04% clipped
  high** overall — consistent with 6D.5's finding; country-level
  variation remains real and was NOT smoothed away (e.g. Bangladesh
  76.8% clipped-high, Nepal 61.1% clipped-high) — reported honestly,
  never retuned, never inspected against held-out or Sri-Lanka
  outcomes. `environmental_suitability_factor`, `water_context_factor`,
  `source_strength_factor` (`NOT_YET_SCIENTIFICALLY_DEFINED`) and the
  wind-speed effect (`NOT_YET_SELECTED`) remain unchanged blockers.
  Both `LOG1P_ROBUST_REFERENCE_SCALE` and `EMPIRICAL_CDF_REFERENCE`
  remain `UNFROZEN_DEVELOPMENT_CANDIDATE`.
