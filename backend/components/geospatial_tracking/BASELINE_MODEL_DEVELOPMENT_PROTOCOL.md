# Baseline Model Development Protocol — Checkpoint 7B

Defines the nested chronological, `FIT_DEVELOPMENT`-only baseline
spatial-rank model development pipeline built on top of the frozen
Checkpoint 7A.6.2 scientific grid/domain protocol (hash
`603052e0ca2c92c6cfbd06ed35cd5705aa85e8cdd45c8dd1629a926ef0af4eed`).

## 1. Scientific purpose (Part 1)

7B answers one narrow question: *given only information available at t0,
do later D1-D7 local-scope outbreak targets tend to occur in higher-ranked
spatial areas than the rest of the declared local evaluation domain?* It
never estimates infection probability, individual animal risk, causal
transmission probability, final PISTES risk, spread direction, or spread
speed. Every candidate's output is a `RELATIVE_SPATIAL_SCORE` /
`AREA_WEIGHTED_TARGET_PERCENTILE` — never a probability, never a
classification-accuracy metric.

## 2. Firewall (Part 2)

`run_checkpoint_7b_development` (`services/model_development/development_run_7b.py`)
calls `model_fitting_exposure.assert_fit_development_only` at its OWN
entry point, before any repository/raster access — a single
`HELD_OUT_FROM_MODEL_FITTING` or `SRI_LANKA_TRANSFER_CASE_STUDY` origin
mixed into the supplied list raises `ValueError` naming every offending
origin, rejecting the ENTIRE call. `build_fold_safe_reference`
(`fold_reference.py`) applies the same firewall independently, to both its
`training_origins` and `validation_origins` arguments, so a caller cannot
smuggle a non-`FIT_DEVELOPMENT` origin in through the validation side
either (7B-LEAK-01..03).

## 3. Chronological folds (Part 3)

Reuses the frozen `services.model_fitting_exposure.build_calendar_year_folds`
unchanged (`development_run_7b.build_calendar_year_folds is
model_fitting_exposure.build_calendar_year_folds`, asserted structurally
by 7B-LEAK-06) — never a random split, never a bespoke reimplementation.
Calendar-year expanding-window folds; training = all `FIT_DEVELOPMENT`
origins with `t0` before the fold year, purge-filtered by the frozen
`PURGED_7_DAY_HORIZON_POLICY`; validation = `FIT_DEVELOPMENT` origins with
a COMPLETE (non-truncated) D1-D7 window inside that calendar year. A fold
whose training-origin list is empty is reported as
`INSUFFICIENT_PRIOR_TRAINING_HISTORY` and excluded from evaluation/
selection — never given a fabricated training set.

## 4. Fold-safe host reference (Parts 4-6, 29)

Architecture (`services/model_development/fold_reference.py`):

```
RAW SCIENTIFIC-GRID HOST OBSERVATIONS   (build_raw_host_snapshots --
                |                        the ONE real GLW4 extraction
                v                        pass, run once over the whole
TRAIN-FOLD SUBSET                        FIT_DEVELOPMENT universe)
                |
                v
FactorReferenceProfile(training only)   (build_fold_safe_reference)
                |
                v
transform TRAIN + VALIDATION raw host values
```

`build_raw_host_snapshots` calls the SAME `build_scientific_grid_host_only_snapshot`
used by the frozen 7A.6.2 host-reference rebuild, once per origin, for the
WHOLE `FIT_DEVELOPMENT` universe — never repeated per fold. Each fold then
only *subsets* that already-built dict by training-origin id before
calling `build_factor_reference_profile(..., require_effective_sample_identity=True)`.
Raw GLW4 pixel values themselves are never recomputed, never changed,
never faked per fold.

Each fold's `FoldSafeHostReference` carries its own deterministic
`fold_reference_identity_hash` — a SHA256 over: fold id, sorted
training-origin ids, training t0 min/max, transform-config hash, the
training profile's full effective observation-id set,
`reference_observation_digest`, dataset-compatibility stratum, canonical
units, and reference-profile version. `generated_at` never participates.
A validation origin's id, coordinates, or host value can never appear in
this hash — proven behaviorally by FOLDREF-01/02 and 7B-LEAK-04 (changing
a validation-side raw value leaves both the fold reference hash and the
underlying reference-profile hash bit-for-bit unchanged).

## 5. Baseline candidate registry (Parts 7-11)

Three pre-registered `EQUAL_SOURCE_BASELINE` families
(`services/model_development/baseline_registry.py`, unchanged from
Checkpoint 7A):

```
B0_DISTANCE_ONLY:        score_i = sum_j K(d_j_i)
B1_HOST_DISTANCE_LOG1P:  score_i = Host_LOG1P_i * sum_j K(d_j_i)
B2_HOST_DISTANCE_ECDF:   score_i = Host_ECDF_i  * sum_j K(d_j_i)
```

`sum_j` always runs over the COMPLETE eligible-source set at that origin
(BASE7B-05/06) — never nearest-source-only, never gated by computational-
component or ST-cluster membership (BASE7B-07/08; `score_origin_all_candidates`
takes no component/cluster/domain parameter at all). Output is always
labeled `RELATIVE_SPATIAL_SCORE`, never a probability (BASE7B-09).

Kernel families (`services/hazard/kernels.py`, unchanged): `EXPONENTIAL`
and `GAUSSIAN`. Kernel scale candidates, frozen BEFORE any score was
evaluated (`services/model_development/candidate_registry_7b.py`):

```
KERNEL_SCALE_CANDIDATES_KM = (5.0, 10.0, 15.0, 25.0)
```

`3 baseline families x 2 kernel families x 4 scales = 24` primary
candidates. Each `candidate_id` deterministically encodes baseline
family, kernel family, kernel scale, host-transform candidate, and every
registry version — order-invariant (KERNEL7B-05), never mutable from
held-out/Sri-Lanka results (KERNEL7B-04: `build_candidate_registry` takes
no arguments at all).

## 6. Scoring semantics (Parts 12-16)

The score surface is spatially STATIC across D1-D7 for one t0
(`STATIC_T0_SPATIAL_BASELINE`) — no learned temporal spread mechanism
exists yet. Raw scores are never AOI-normalized. Missing host input is
NEVER converted to zero: a cell whose host transform cannot be produced
(unusable raw value, incompatible/degenerate reference span) is
`MODEL_INPUT_INCOMPLETE`; if that is a target's own assigned cell, the
target's own outcome is `TARGET_SCORE_UNAVAILABLE` — both are preserved
in the per-target audit record, never silently dropped.

## 7. Area-weighted ranking metrics (Parts 17-21)

Primary evaluation domain: `WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE`
targets only (`OUTSIDE` targets remain in the master audit, never
deleted, never treated as biological negatives).

```
AREA_WEIGHTED_TARGET_PERCENTILE =
    100 * (area(score < S_t) + 0.5 * area(score == S_t)) / total_valid_domain_area
```

using `domain_overlap_area_km2` (the real, edge-clipped cell area, never
the full square `area_km2`) as the area weight — explicit
`AREA_WEIGHTED_MIDRANK` tie semantics, grid-iteration-order-independent
(METRIC7B-01..04). `total_valid_domain_area` is the sum over EVERY cell in
the domain, scored or `MODEL_INPUT_INCOMPLETE` — an incomplete cell still
occupies real declared-domain area; it is simply never counted toward the
numerator, so a material missing-area fraction visibly suppresses
percentiles rather than silently shrinking the denominator.
`TOP_5_PERCENT_CAPTURE`/`TOP_10_PERCENT_CAPTURE` are percentile >= 95/90.
Secondary diagnostic `TARGET_CELL_RANK` breaks ties by score descending
then `scientific_cell_id` ascending (METRIC7B-07) — never called
classification accuracy. Never emits `TRUE_NEGATIVE`/`DISEASE_FREE`/
`HEALTHY_CELL` (METRIC7B-08).

## 8. Unique-target / origin-balanced aggregation (Parts 22-27)

One row per (`forecast_origin_id`, `target_event_id`) — a duplicate
ledger row is dropped by `dedupe_targets_by_target_id` before scoring
(UNIT7B-01). Grid cells are never an independent-sample denominator
(UNIT7B-02) — the inferential unit is the forecast task. Primary
candidate comparison uses EQUAL ORIGIN WEIGHT within each fold
(`fold_origin_balanced_metrics`) — an origin with 20 targets cannot
outweigh an origin with 1 (UNIT7B-03/04) — then aggregates fold results
using `EQUAL_VALIDATION_ORIGIN_WEIGHTING_ACROSS_FOLDS`
(`overall_equal_origin_weighted`): every validation origin counts equally
in the overall figure regardless of which fold (or how large that fold
was) it came from.

Clustered bootstrap uncertainty (95% CI, fixed seed 42, 1000 resamples)
is reported for the primary target percentile, TOP10, and TOP5, clustered
by ORIGIN (never grid cells). A secondary sensitivity diagnostic reports
the same three CIs clustered by `target_event_id` instead (the same
future event can appear in forecasts from multiple origins) — this never
changes the primary equal-origin selection rule.

## 9. Selection rule (Parts 24-25, 30)

```
PRIMARY_SELECTION_METRIC = MEAN_ORIGIN_BALANCED_AREA_WEIGHTED_TARGET_PERCENTILE
```

frozen BEFORE any candidate result was computed
(`services/model_development/selection_7b.py`). Highest overall metric
wins; EXACT-numerical-tie tie-breakers only (never an invented
"approximately tied" tolerance): (1) higher origin-balanced TOP10, (2)
higher origin-balanced TOP5, (3) `candidate_id` lexical order
(SELECT7B-03). One candidate configuration is selected for ALL of D1-D7 —
7B never selects a different baseline per lead day (SELECT7B-04); D1-D7
metrics are reported as a post-hoc breakdown of the ONE selected
candidate's own records.

## 10. Frozen baseline specification (Parts 30-33)

`services/model_development/protocol_7b.py::FrozenBaselineModelSpecification`
carries `parameter_status = FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION` —
never "validated," never "final PISTES model," never "infection
probability model" (SELECT7B-06). If B1/B2 was selected, the already-
approved complete 579-origin Checkpoint 7A.6.2 host reference (hash
`5f41f5917bedf61e721e286e5bab031c22bbb687a8157f197dbac751b023e22d`)
becomes the FINAL development reference, provided its transform config
matches the selected host transform — never rebuilt using held-out data.
If B0 was selected, the host reference is not an effective model input
for the frozen spec, but is preserved as research evidence regardless.

## 11. Real Checkpoint 7B development results

See `MODEL_DEVELOPMENT_PROTOCOL.md` sec 58+ and `DATA_AUDIT.md` sec 83 for
the full real, current-code 579-origin chronological development run
results (fold manifest, candidate registry, D1-D7 metrics, bootstrap
uncertainty, selection outcome, frozen specification hash).
