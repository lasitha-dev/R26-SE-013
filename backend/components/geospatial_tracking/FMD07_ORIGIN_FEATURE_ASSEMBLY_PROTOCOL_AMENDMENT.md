# FMD-07A-R2A: Origin Feature-Assembly Protocol Amendment

Status: **`PRE_EXTRACTION_ORIGIN_FEATURE_ASSEMBLY_PROTOCOL_AMENDMENT`** —
explicitly NOT preregistered.

**THIS RULE WAS INTRODUCED AFTER FMD-07A-R2 IDENTIFIED THE MISSING
SEMANTICS AND BEFORE FULL-CORPUS FEATURE EXTRACTION OR MODEL
DEVELOPMENT.**

## 1. R2 blocker and why it occurred

FMD-07A-R2 (`fmd07a_r2_origin_feature_assembly_audit.json`, preserved
unchanged, never rewritten) found `overall_rule_status = "UNDEFINED"`: the
repository contained no rule mapping event/source-level feature values
into one forecast-origin predictor row. FMD-04's feature pipeline is
explicitly event/point-level (its own docstring: FMD-04 "is explicitly
forbidden from building forecast origins, grids, or anything tied to a
future forecasting/clustering checkpoint"); the one origin-level
convention that exists (`services/features/assembler.py`'s `AOI_CENTER`)
is LSD-specific grid/hazard-model machinery FMD-04 was told to avoid, and
even it never defines a multi-source aggregation rule for anything but
weather.

## 2. Amendment classification

```
amendment_status = "PRE_EXTRACTION_ORIGIN_FEATURE_ASSEMBLY_PROTOCOL_AMENDMENT"
introduced_after_r2_preflight = true
introduced_before_full_feature_extraction = true
introduced_before_any_predictive_model = true
predictive_metrics_used_to_define_rule = false
held_out_outcomes_used = false
sri_lanka_outcomes_used = false
weather_winner_used = false
```

Not preregistered: it was written after R2's audit found the gap, and
before any full-corpus extraction, model fit, PR-AUC calculation, or
weather-window selection.

## 3. Source-set definition

```
source_set = "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"
active_window_days = 14   (FMD-06B-R calibrated value, read from
                            fmd06_calibration_manifest.json, never
                            redeclared as a second source of truth)
```

For forecast origin `t0`, reuses `services.source_selector.
get_eligible_sources` **unchanged** — the same call signature FMD-06's
own `build_fmd06c_spatial_target_distance_audit` and
`services/model_development/domain_design.py` already use. Inclusive
`t0 - 14 <= effective_availability_date <= t0` boundary enforcement is
entirely that existing, frozen implementation's responsibility — never
re-implemented here. No source with an availability timestamp `> t0` can
enter (verified: `get_eligible_active_sources_for_origin` is a thin
pass-through, no new filtering logic exists in this module at all).

## 4. Event/source spatial reference

```
source_spatial_reference = "SOURCE_EVENT_OWN_COORDINATE"
centroid_used = false
trigger_only_used = false
```

Every eligible active source's **own** validated `(latitude, longitude)`
is the feature-extraction point for that source — never replaced by a
centroid, a trigger-only point, an ST-DBSCAN cluster centroid, or a
nearest-source selection. This applies identically to elevation, cattle
density, buffalo density, every land-cover fraction, hydrology, and
source-level weather.

## 5. Event-level weather semantics

Each eligible active source retains its own FMD-04 event-level
retrospective windows — `event_day`, `window_3day`, `window_7day`,
`window_14day` (`data_processing/build_fmd_features.py`
`WEATHER_WINDOWS_HOURS`, unchanged) — strictly backward-looking from that
source's own `effective_availability_date`, which is itself already
`<= t0` by construction of the frozen source set. No new future date is
ever queried; **no weather-window winner is selected in this
checkpoint.**

## 6. Deduplication

Before aggregation, source records are deduplicated by the canonical
source identity field `source_id`
(`services.source_selector.EligibleSource.source_id`, == the repository's
own `source_record_id`, the same field FMD-05/FMD-06 use throughout) —
the same real event/source can never receive multiple weight merely
because it appears more than once in an input list. No new identifier is
invented.

## 7. Equal-weight arithmetic-mean rule

```
numeric_aggregation_rule = "UNWEIGHTED_ARITHMETIC_MEAN_OF_VALID_ACTIVE_SOURCE_VALUES"
```

```
x_o,f = mean(x_s,f for every unique eligible active source s at t0
             having a valid numeric value for feature f)
```

Every valid source contributes exactly `1/N_valid` weight. No label-,
target-, trigger-, distance-, DQS-, source-strength-, livestock-,
recency-, cluster-size-, or learned weighting of any kind is applied — no
minimum, maximum, median, nearest-source-only, or centroid extraction is
used instead. Reason: no scientifically frozen source-level weighting
system currently exists in this repository; an unweighted arithmetic mean
is a deterministic, unit-preserving, non-outcome-dependent summary of the
environmental context across the already-frozen active-source set.

## 8. Per-feature-family application

The **same** generic rule (Section 7) is applied identically to every one
of the 47 eligible predictor features — none is special-cased:

- **Weather** (32: 8 variables × 4 windows) — mean of valid source-level values per variable/window.
- **Elevation** (1) — mean of valid source-level elevation values.
- **Host density** (2: cattle, buffalo) — mean of valid source-level density values per species.
- **Land cover** (11 fractions) — each fraction averaged independently; never renormalized using label/outcome information.
- **Hydrology** (1) — mean of valid source-level nearest-river distances; **never** switched to minimum distance.

## 9. Missing / status aggregation

For one origin-feature pair, with `N_total` = deduplicated eligible active
sources and `N_valid` = those carrying a valid numeric value:

| Condition | Origin value | Origin status |
|---|---|---|
| `N_valid == N_total > 0` | arithmetic mean | `ORIGIN_AGGREGATE_ALL_VALID` |
| `0 < N_valid < N_total` | mean of valid values only | `ORIGIN_AGGREGATE_PARTIAL_VALID` |
| `N_valid == 0 < N_total` | blank/null | `ORIGIN_AGGREGATE_NO_VALID_VALUE` |
| `N_total == 0` | blank/null | `NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0` |

Never: zero-insertion, global-mean imputation, forward-fill, or a
fabricated adapter value. Train-fold-only imputation remains FMD-07B's
responsibility. Underlying per-source statuses
(`SOURCE_VALUE_AVAILABLE`/`SOURCE_VALUE_MISSING`/`SOURCE_FILE_MISSING`/
`OUTSIDE_SOURCE_COVERAGE`/`TEMPORAL_COVERAGE_MISSING`/
`EXTRACTION_FAILED`/`FEATURE_NOT_AVAILABLE` —
`data_processing/fmd_feature_status.py`, unchanged) are preserved as
audit counts (`total_source_count`, `valid_source_count`,
`invalid_source_count`, `valid_source_fraction`,
`underlying_status_counts`) — these are AUDIT information, **not**
predictor columns, unless a future explicit pre-model protocol amendment
separately authorizes that.

## 10. Zero-source behavior

An origin with zero eligible active sources retains its row — every
remote-derived predictor is blank with status
`NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0`. No centroid, fallback event, or
substitute value is ever fabricated.

## 11. Multiple-trigger behavior

Trigger status confers no extra weight. A source that is also a trigger
enters exactly once (post-deduplication, on equal footing with every
other eligible active source); multiple triggers at one origin still each
contribute their own single, equal-weight observation, never a
trigger-only subset. `aggregate_source_feature_values_for_origin` has no
trigger-related parameter at all — structurally incapable of
trigger-weighting.

## 12. Leakage firewall

Aggregation functions read only a source record's canonical id and its
`{feature}_value`/`{feature}_status` columns. They never read
`risk_target_label`, `local_domain_positive`, `has_eligible_d1_d7_target`,
`outside_domain_target_present`, any future target row, candidate-domain
coverage, target distance, or any held-out/Sri-Lanka outcome. Labels are
joined only **after** predictor construction, by `forecast_origin_id`,
exactly as the existing FMD-07A feature-matrix contract already requires.

## 13. Why the rule is computational, not biological

The arithmetic mean is a **pre-model deterministic summarization rule**
required to map a variable-size historical active-source set into a
fixed-width tabular forecast-origin representation. It is explicitly
**not**: a biological transmission equation, an assumption that all
sources transmit equally, a quarantine radius, a source-strength model,
or a movement/contact model. Any biologically weighted source
contribution would require separate scientific evidence and a future,
explicitly frozen protocol.

## 14. Limitations

- Resolves ASSEMBLY SEMANTICS only. All 47 eligible predictor features
  remain `FULL_CORPUS_EXTRACTION_NOT_RUN` — no remote extraction occurred.
- Land-cover fractions are averaged independently per class; the averaged
  vector may not sum to exactly 1.0 bit-for-bit (ordinary float64
  tolerance), never renormalized using label/outcome information.
- No scientifically justified differential source weighting exists yet —
  the unweighted mean is a software default, not a claim that every
  source event is epidemiologically equivalent.

## 15. Downstream extraction contract

A future extraction checkpoint (FMD-07A-R2B or equivalent) may now
legitimately: (a) call `get_eligible_active_sources_for_origin` per
`FIT_DEVELOPMENT` forecast origin to obtain its frozen source set, (b)
extract each unique source's own per-point feature values via the
existing, already-validated FMD-04 adapters (reusing the same cache), and
(c) apply `build_origin_feature_row_from_source_features` unchanged to
populate `fmd07_development_feature_matrix.csv`'s real predictor values.
Nothing about this amendment requires re-deriving the rule at that time.

## 16. Audit trail

- Preserved unchanged: `fmd07a_r2_origin_feature_assembly_audit.json`
  (`overall_rule_status = "UNDEFINED"`,
  `block_name = "FORECAST_ORIGIN_FEATURE_ASSEMBLY_RULE_UNDEFINED"`).
- Implementation: `services/fmd_model_development_r2a.py`.
- Machine-readable protocol:
  `local_data/processed/fmd/model_development/fmd07_origin_feature_assembly_protocol.json`.
- Tests:
  `backend/components/geospatial_tracking/tests/test_fmd07a_r2a_origin_feature_assembly.py`.
- Sources consulted: `FMD_FEATURE_ELIGIBILITY.csv`,
  `FEATURE_ASSEMBLY_PROTOCOL.md`, `FMD_EVALUATION_PROTOCOL.md`,
  `FMD07_PRE_MODEL_PROTOCOL_AMENDMENT.md`,
  `data_processing/build_fmd_features.py`,
  `data_processing/fmd_feature_status.py`, `services/source_selector.py`,
  `services/fmd_model_development.py`, `services/fmd_model_development_r1.py`.
