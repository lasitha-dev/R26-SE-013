# FMD-05 Evaluation Protocol — Frozen

Freezes metrics, baseline comparator categories, the weather-window
selection RULE, the ST-DBSCAN role boundary, the negative/control-sample
decision, and training-only preprocessing rules — all **before** any
FMD-06/07 model development, so no later choice can be justified by a
performance number that does not yet exist.

## 1. Negative / control sample methodology

**Decision: explicit negative/control rows are NOT required for the
primary RISK task, and none are generated in FMD-05.**

Per `FMD_TARGET_PROTOCOL.md` §3, the risk label is a binary property of a
forecast ORIGIN (does >=1 qualifying D1-D7 target exist in-domain?), not
a property of an arbitrarily chosen spatial point. Every one of the 4,322
real forecast origins already has a determinate label under this
definition once the domain radius is fixed (`risk_present ∈ {True,
False}`, `False` for the 1,478 origins with zero targets) — there is no
missing/undefined class requiring synthetic negatives, because the origin
population itself (not a sampled background) IS the modelling
population. This differs from a spatial-grid risk-surface formulation
(which WOULD need explicit negative cells) — FMD-05 does not adopt a grid
formulation (`FMD_STUDY_PROTOCOL.md` §4).

**If a future checkpoint (FMD-07+) proposes a spatial-grid or
cell-classification reformulation that DOES need negatives**, the
control-generation protocol must, at minimum:
- restrict candidate negative locations/times to the SAME
  `FIT_DEVELOPMENT` role and country/temporal coverage as the positives
  they are contrasted against (never sampled from
  `HELD_OUT_FROM_MODEL_FITTING`/`SRI_LANKA_TRANSFER_CASE_STUDY` space);
- require a genuine event-free D1-D7 interval at that location, not
  merely "not exactly a recorded event";
  respect the same forecast-origin `t0` — a negative is a
  (location, `t0`) pair, never a location alone;
- be documented with an explicit sampling ratio and reporting of
  repeated sampling, exactly like the positive pseudo-replication
  disclosure in `FMD_TARGET_PROTOCOL.md` §1;
- never be drawn from arbitrary random coordinates unconstrained by
  livestock presence, surveillance coverage, or historical reporting —
  none of which this repository has a validated global layer for
  (`FMD_FEATURE_ELIGIBILITY.csv`: swine/sheep/goat density and any
  livestock-movement/road proxy are `UNAVAILABLE`).
This is a protocol for a **future** decision, recorded here so it cannot
be improvised post-hoc — no control rows are built in FMD-05.

## 2. Preprocessing / imputation rules (training-only, frozen)

No learned preprocessing parameter may be fit on anything other than
`FIT_DEVELOPMENT` data:
- any future feature scaler mean/std, imputation median/mode, or
  categorical encoding must be fit on `FIT_DEVELOPMENT` origins/events
  only, then applied unchanged to `HELD_OUT_FROM_MODEL_FITTING` and
  `SRI_LANKA_TRANSFER_CASE_STUDY` rows;
- feature selection (e.g. which weather window, which host-density
  species) must use `FIT_DEVELOPMENT` folds only (§3);
- class-balancing/weighting decisions (if the risk task's natural class
  balance motivates one) must be derived from `FIT_DEVELOPMENT` data
  only. **The natural class balance is NOT yet known**: 2,844 of 4,322
  origins have `>= 1` temporally-eligible (D1-D7, same-country) target,
  1,478 have zero — but `risk_present` additionally requires the target
  to fall within the still-unfrozen spatial domain (`FMD_TARGET_PROTOCOL.md`
  §3), so 2,844 is an UPPER BOUND on the positive count, never itself the
  final positive-class count or a frozen ratio. The 1,478 zero-target
  origins ARE already final `risk_present = False` (no spatial condition
  can turn a temporally-absent target into a positive), but the
  remaining 2,844 cannot be labeled until FMD-06 freezes a radius;
- **unavailable features are never imputed into existence** — a
  `UNAVAILABLE` feature family (`FMD_FEATURE_ELIGIBILITY.csv`) stays
  absent from the feature matrix; it is not filled with a population
  mean, a proxy species, or a placeholder zero.
- the frozen FMD canonical corpus and cohort artifacts are never
  overwritten by any of the above — they remain the single upstream
  source of truth (`test_fmd05_study_protocol.py` re-hashes it).

## 3. Weather-window selection rule (frozen; no winner selected)

FMD-04 computed the same weather covariates for **4 candidate pre-t0
windows**: `event_day` (24h), `3day` (72h), `7day` (168h), `14day`
(336h) — all ERA5 reanalysis, always `models=era5` explicit
(`fmd_feature_registry.py`). **No window is selected as primary in
FMD-05.** The frozen selection rule for FMD-06+:

- Window selection is a **development-only** decision: it must be made
  using `FIT_DEVELOPMENT` folds only (cross-validated inside those
  folds, e.g. nested chronological validation per
  `VALIDATION_PROTOCOL.md` §1's already-frozen convention for LSD, reused
  unmodified), never against `HELD_OUT_FROM_MODEL_FITTING` or
  `SRI_LANKA_TRANSFER_CASE_STUDY` performance.
- Once selected in FMD-06, the winning window is **locked** before FMD-07
  model development and **never re-opened** based on FMD-08's locked
  test result.
- **Retrospective-reanalysis limitation (must be stated wherever ERA5
  features are used):** ERA5 is a historical reanalysis product, not a
  real-time operational forecast or an as-of-`t0` observation network.
  Its `availability_quality` is `UNKNOWN` by default in this repository's
  own convention — using it is valid for retrospective research (it
  correctly respects the pre-`t0` VALID-TIME boundary: `build_pre_t0_weather_summary`
  never requests a post-cutoff timestamp), but it must **never** be
  described as information that was operationally available in real time
  at the historical `t0`. Label ERA5-derived predictors precisely as
  **retrospective epidemiological covariates**, never as a live
  forecasting input or a claimed real-time surveillance signal.

## 4. ST-DBSCAN role (frozen boundary; nothing calibrated here)

`STDBSCAN_PROTOCOL.md`'s existing design (disease-agnostic joint
spatial+temporal epsilon clustering, structurally forbidden from ever
being marked `FROZEN_REFERENCE` — `STDBSCANConfig.__post_init__` raises
if attempted) applies to FMD exactly as it does to LSD, with FMD's own
data producing FMD's own candidate parameter statistics in FMD-06 — never
LSD's `eps_space_km≈12.37`/`eps_time_days=3` values, which are LSD-corpus
quantiles, not universal constants.

- ST-DBSCAN's role for FMD is **descriptive spatiotemporal outbreak
  context only** — it clusters DISTINCT, already-deduplicated FMD events
  into candidate outbreak chains for exploratory/contextual use. It is
  **never** a model-development gate and **never** a substitute for the
  target/eligibility logic this document freezes (same decoupling
  already enforced for LSD after its own Checkpoint 7A.6 bug).
- **Legal at `t0`**: only cluster structure built from FMD sources with
  effective availability `<= t0` (the same T0 invariant as every other
  predictor, §2 of `FMD_TARGET_PROTOCOL.md`) may ever feed a future
  historical predictor. A cluster label computed using a FUTURE event
  (available only after `t0`) can never be used as a predictor for that
  `t0` — this is a structural consequence of reusing the same
  `get_eligible_sources`/T0-gated source enumeration ST-DBSCAN candidate
  statistics must be built from, not a new mechanism.
- **What FMD-06 MAY calibrate**: `eps_space_km`, `eps_time_days`,
  `min_core_supports`, `active_window_days` — as
  `UNFROZEN_DEVELOPMENT_CANDIDATE`s, derived from `FIT_DEVELOPMENT`-only
  FMD sources (mirroring `build_fit_development_source_universe`'s
  already-hard-gated approach), never from held-out/Sri-Lanka data, never
  chosen by outcome performance (no risk/direction/speed model exists to
  produce one).
- **What remains forbidden in FMD-05 and FMD-06 alike**: freezing any
  ST-DBSCAN parameter as a claimed scientific/biological constant, and
  treating a cluster as validated "outbreak-chain truth" (the FMD
  canonical corpus's own `possible_related_event_group_id` is explicitly
  documented as "a raw signal... not a substitute" for this analysis —
  `FMD_DATASET_CARD.md`).

## 5. Evaluation metrics (frozen; primary/secondary by task)

**Primary task: RISK (binary, per forecast origin).**

| Tier | Metrics |
|---|---|
| Primary | PR-AUC (appropriate given the risk-eligible target rate is domain-radius-dependent and likely far from 50/50 at small radii), AUROC |
| Secondary | sensitivity/recall, specificity, precision, F1 (all at a threshold selected on `FIT_DEVELOPMENT`/validation folds only) |
| Calibration | Brier score, a reliability/calibration curve — required before any risk score is described as a "probability" |
| Spatial-ranking (if a later checkpoint frames risk as a ranking rather than binary-per-origin problem) | capture-rate-at-top-k / area-weighted target percentile, reusing `BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md`'s already-frozen `RELATIVE_SPATIAL_SCORE`/`AREA_WEIGHTED_TARGET_PERCENTILE` convention rather than inventing a second one |

Every metric above must be reported **per role** (`FIT_DEVELOPMENT`
validation folds vs. the FMD-08 locked `HELD_OUT_FROM_MODEL_FITTING`
evaluation vs. the Sri Lanka case study) — never pooled across roles, and
never computed on held-out/Sri-Lanka data before FMD-08.

**Direction / speed tasks: metrics are NOT frozen** — per
`FMD_TARGET_PROTOCOL.md` §4, both are currently NO-GO (0 Tier-A targets;
speed additionally blocked on ungeometrized `SPEED_ELIGIBILITY_PENDING_GEOMETRY`).
No MAE/bearing-error/speed-error evaluation is promised on a target
population this corpus cannot currently support. If a future checkpoint
unblocks either task, its metrics (e.g. circular MAE for bearing, a
grouped speed error) must be frozen at that time, under the same
before-any-model-exists discipline as this document.

## 6. Baseline comparator categories (frozen; nothing trained)

Future FMD-07 candidate model families must be compared against, at
minimum:

1. **Naive/statistical baseline** — historical FMD occurrence
   rate/prevalence per country (`FIT_DEVELOPMENT` only), a
   persistence-style baseline ("risk today ~ risk in the immediately
   preceding period at this origin's country").
2. **Spatial/distance-based baseline** — reuse `BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md`'s
   already-frozen C0-style relative spatial-rank scoring mechanism
   (`RELATIVE_SPATIAL_SCORE`), refit from FMD `FIT_DEVELOPMENT` data,
   never LSD's fitted C0 candidate.
3. **Mathematical/PISTES-style risk model** — the disease-agnostic
   hazard-engine mathematics (`HAZARD_ENGINE_PROTOCOL.md`) with FMD-06-
   calibrated (never LSD-copied) parameters.
4. **ML candidate** (e.g. gradient-boosted/logistic model over the
   FMD-04 feature set, once full extraction is run) — architecture
   unspecified here, deliberately.
5. **Hybrid candidate** — combining (3) and (4); architecture
   unspecified.

No comparator is trained, ranked, or selected as a winner in FMD-05.

## 7. What this protocol does NOT do

- Does not compute any of the above metrics against real predictions —
  no risk/direction/speed model exists.
- Does not select a weather window, ST-DBSCAN parameter, or spatial
  domain radius.
- Does not generate any negative/control row.
- Does not decide a winning model family.
