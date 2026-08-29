# FMD-07A-R2B3: Offline Origin-Matrix Population Protocol

Status: **`PRE_IMPLEMENTATION_SOFTWARE_DATA_PIPELINE_PROTOCOL_FREEZE`**.

This document defines the missing software/data-pipeline boundary between the
completed FMD-07A-R2B2 source-feature extraction checkpoint and FMD-07B model
development. It is frozen before any R2B3 implementation, model fit, predictive
score, metric, threshold selection, or held-out/case-study outcome access.

This checkpoint introduces no new scientific or biological rule. It applies the
already-frozen FMD-07A-R2A source-to-origin aggregation rule to the already-frozen
FMD-07A-R2B2 local artifacts.

## 1. Checkpoint identity and purpose

```text
checkpoint = FMD-07A-R2B3
checkpoint_status = PRE_IMPLEMENTATION_SOFTWARE_DATA_PIPELINE_PROTOCOL_FREEZE
purpose = OFFLINE_FIT_DEVELOPMENT_SOURCE_TO_ORIGIN_MATRIX_POPULATION
```

R2B3 must:

1. read the completed R2B2 source-feature table and materialized origin-to-source
   map without rebuilding the source universe or making a network request;
2. construct one predictor row per `FIT_DEVELOPMENT` forecast origin by calling
   the frozen R2A aggregation implementation unchanged;
3. keep predictor construction independent of labels and outcome-derived audit
   fields;
4. only after predictor construction, join the predictor row to the existing
   FMD-07A schema-freeze matrix's non-predictor columns by
   `forecast_origin_id`;
5. write deterministic, auditable R2B3 outputs for the later FMD-07B checkpoint.

R2B3 does not perform extraction, retry, calibration, feature selection,
imputation, scaling, model fitting, prediction, or evaluation.

## 2. Repository evidence for this boundary

The operation above is required by the following existing repository contracts:

- `FMD07_ORIGIN_FEATURE_ASSEMBLY_PROTOCOL_AMENDMENT.md` Section 15 permits the
  post-extraction checkpoint to use the frozen active-source set, extracted
  per-source feature values, and
  `build_origin_feature_row_from_source_features` to populate a real
  origin-level development matrix.
- `services/fmd_model_development_r2a.py` already implements the complete,
  label-independent source-deduplication, numeric aggregation, missingness, and
  origin-status rules. R2B3 must orchestrate that implementation; it must not
  redefine it.
- `fmd07_origin_feature_assembly_protocol.json` freezes the 47 eligible
  predictor features, their order, the 14-day active-source rule, and the
  source-to-origin aggregation semantics.
- `fmd07_full_source_features.csv` and
  `fmd07_full_source_extraction_manifest.json` are the completed R2B2
  source-level outputs: 6,799 rows, 6,799 unique `source_id` values, and no
  remaining source-level extraction work.
- `fmd07_origin_source_map.json` materializes the R2B2 source membership for all
  3,761 development origins. It contains 41,684 origin-source appearances whose
  union is exactly the 6,799 R2B2 source ids.
- `fmd07_development_feature_matrix.csv` is the existing 3,761-row FMD-07A
  schema freeze. Its predictor values remain blank with
  `EXTRACTION_NOT_RUN`; its identifier, metadata, label, and audit-only columns
  are already frozen.
- `fmd07_model_input_schema.json` assigns any learned preprocessing or
  imputation to FMD-07B, inside training folds only. R2B3 therefore cannot
  perform either.
- `FMD07_PRE_MODEL_PROTOCOL_AMENDMENT.md` assigns candidate fitting and
  train-fold-only transformations to FMD-07B. R2B3 must stop before that work.

## 3. Allowed input artifacts

### 3.1 Predictor-construction inputs

Only these artifacts may determine R2B3 predictor values and statuses:

1. `local_data/processed/fmd/model_development/fmd07_full_source_features.csv`
2. `local_data/processed/fmd/model_development/fmd07_full_source_extraction_manifest.json`
3. `local_data/processed/fmd/model_development/fmd07_feature_extraction_progress.json`
   and `fmd07_feature_extraction_failure_ledger.json` for terminal-accounting
   validation only
4. `local_data/processed/fmd/model_development/fmd07_origin_source_map.json`
5. `local_data/processed/fmd/model_development/fmd07_unique_source_extraction_index.csv`
   for identity/metadata reconciliation only; it must not replace or extend the
   frozen origin-to-source membership
6. `local_data/processed/fmd/model_development/fmd07_origin_feature_assembly_protocol.json`
7. the unchanged aggregation functions in
   `services/fmd_model_development_r2a.py`

The R2B2 source cache, raw/canonical source files, and remote providers are not
inputs to R2B3. R2B3 must consume the final source table, not reconstruct it.

### 3.2 Join-only and schema/provenance inputs

These artifacts may be read only after predictor construction is complete:

1. `local_data/processed/fmd/model_development/fmd07_development_feature_matrix.csv`
2. `local_data/processed/fmd/model_development/fmd07_model_input_schema.json`
3. `local_data/processed/fmd/model_development/fmd07a_provenance.json`

The existing matrix supplies only the frozen identifier, metadata, target, and
audit-only columns for an exact `forecast_origin_id` join. Its
`risk_target_label` and `audit_only_*` fields must not be passed to, inspected
by, or used to branch predictor construction. The existing predictor columns
must be replaced in the new R2B3 output by the R2A aggregation result, never
used as source values.

## 4. Forbidden inputs and operations

R2B3 must hard-reject or remain structurally incapable of using:

- any `HELD_OUT_FROM_MODEL_FITTING` outcome, label, feature row, origin, target,
  prediction, or metric;
- any `SRI_LANKA_TRANSFER_CASE_STUDY` outcome, label, feature row, origin,
  target, prediction, or metric;
- any source or feature unavailable after its origin's `t0`;
- any target/future-event column during predictor construction, including
  `risk_target_label`, `local_domain_positive`,
  `has_eligible_d1_d7_target`, and `outside_domain_target_present`;
- model predictions, fitted parameters, comparative performance, or downstream
  model artifacts;
- remote feature providers, network extraction, cache retry, or source-universe
  rebuilding;
- global or per-origin imputation, zero filling, forward filling, normalization,
  feature selection, weather-window selection, or learned transformation;
- cache-private keys such as `_r2b2_retry_attempted` as output columns or
  scientific inputs.

## 5. Row and unit semantics

The R2B3 development matrix unit is **one forecast origin**, identified by
`forecast_origin_id`. Source rows are construction inputs only and never become
model rows.

The real frozen input invariants are:

```text
FIT_DEVELOPMENT forecast origins = 3,761
unique R2B2 source rows = 6,799
unique R2B2 source_id values = 6,799
origin-source appearances = 41,684
eligible predictor features = 47
predictor value/status columns = 94
final development-matrix columns = 105
origin-feature audit rows = 3,761 * 47 = 176,767
```

The output origin-id set must exactly equal both the 3,761 keys of
`fmd07_origin_source_map.json.origin_to_source_ids` and the 3,761
`forecast_origin_id` values in the schema-freeze matrix. Missing, extra, or
duplicate origin ids are a hard failure.

The union of mapped `source_id` values must exactly equal the source-id set in
the final R2B2 source table. A mapped id without a source row, or an unused
source-table id, is a hard failure. No substitute row may be fabricated.

## 6. Inherited aggregation semantics

R2B3 inherits and must call the R2A implementation unchanged:

```text
source set = ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0
source identity = source_id
source spatial reference = SOURCE_EVENT_OWN_COORDINATE
numeric rule = UNWEIGHTED_ARITHMETIC_MEAN_OF_VALID_ACTIVE_SOURCE_VALUES
```

For every origin and each of the 47 eligible predictor features:

1. take exactly the source ids listed for that origin in the materialized R2B2
   origin-source map;
2. deduplicate by canonical `source_id`;
3. sort by `source_id` before summation;
4. treat a value as valid only when its source status is
   `SOURCE_VALUE_AVAILABLE` and it carries a real numeric value;
5. compute the unweighted arithmetic mean of the valid source values;
6. apply `aggregate_origin_feature_status(total_source_count,
   valid_source_count)` unchanged.

The same rule applies to all feature families. Hydrology remains a mean, not a
minimum. Land-cover fractions are averaged independently and are not
renormalized. All four frozen weather windows remain present; R2B3 does not
select a winner. Trigger sources receive no additional weight.

## 7. Timestamp and data-availability constraints

R2B3 must reuse the R2B2 materialized mapping and must not re-run source
selection. That mapping was built from the frozen inclusive constraint:

```text
t0 - 14 days <= source effective_availability_date <= t0
```

Each source's static features remain values extracted at that source's own
coordinate. Each source's weather values retain the source's own retrospective
window ending at its own effective availability date, which is already `<= t0`
for every origin using that source.

R2B3 may validate these recorded identities and dates where present, but it may
not replace the mapping, move a feature to an origin coordinate or centroid,
query a later timestamp, or introduce any post-`t0` value.

## 8. Missing-value and status handling

The R2A status rules are inherited exactly:

| Condition | Origin value | Origin status |
|---|---|---|
| `N_valid == N_total > 0` | mean of all valid values | `ORIGIN_AGGREGATE_ALL_VALID` |
| `0 < N_valid < N_total` | mean of valid values only | `ORIGIN_AGGREGATE_PARTIAL_VALID` |
| `N_valid == 0 < N_total` | blank/null | `ORIGIN_AGGREGATE_NO_VALID_VALUE` |
| `N_total == 0` | blank/null; origin retained | `NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0` |

Every non-available source status remains invalid for numeric aggregation and is
counted under its original status in the audit output. A
`SOURCE_VALUE_AVAILABLE` row with a blank, null, non-numeric, NaN, or infinite
value is a hard failure, not a missing-value conversion.

No zero insertion, imputation, forward fill, global mean, fallback source,
centroid value, or fabricated status is permitted. Any later imputation remains
FMD-07B train-fold-only work.

## 9. Deterministic ordering and serialization

R2B3 must be reproducible offline:

- origins sorted lexically by `forecast_origin_id`;
- sources sorted lexically by `source_id` before aggregation;
- features in the exact order frozen by
  `fmd07_origin_feature_assembly_protocol.json` and
  `fmd07_model_input_schema.json`;
- final matrix fields in the exact existing 105-column schema order;
- audit rows ordered by `forecast_origin_id`, then frozen feature order;
- status-count mappings serialized with sorted keys;
- CSV written as UTF-8 with a fixed line terminator and deterministic float
  serialization, without changing or rounding the computed float value;
- JSON written as UTF-8 with sorted keys and no wall-clock timestamp in the
  deterministic content;
- every output written via a same-directory temporary file followed by atomic
  replacement;
- two independent offline builds from the same inputs must produce identical
  bytes and identical SHA-256 values.

Input rows and input artifacts must not be mutated.

## 10. Expected R2B3 artifacts

R2B3 implementation must create exactly these new artifacts under
`local_data/processed/fmd/model_development/`:

1. `fmd07_r2b3_development_feature_matrix.csv`
   - canonical populated development matrix for FMD-07B;
   - 3,761 rows and 105 columns;
   - non-predictor columns copied byte-for-value from the schema-freeze matrix;
   - 47 predictor value/status pairs populated only by R2A aggregation.
2. `fmd07_r2b3_origin_feature_aggregation_audit.csv`
   - 176,767 rows, one per `(forecast_origin_id, feature_name)`;
   - fields: `forecast_origin_id`, `feature_name`, `total_source_count`,
     `valid_source_count`, `invalid_source_count`, `valid_source_fraction`,
     and deterministic `underlying_status_counts_json`;
   - audit columns are not model predictors.
3. `fmd07_r2b3_manifest.json`
   - checkpoint identity and contract status;
   - input and output SHA-256 values;
   - all row, column, id-set, and ordering checks;
   - per-feature output status counts and missing-value counts;
   - independent-build SHA-256 comparison;
   - explicit `network_used = false`, `held_out_used = false`,
     `sri_lanka_used = false`, `labels_used_for_predictor_construction = false`,
     `imputation_applied = false`, `model_trained = false`, and
     `predictive_metrics_computed = false` flags.

The original `fmd07_development_feature_matrix.csv`,
`fmd07_feature_matrix_audit.json`, `fmd07_model_input_schema.json`, and
`fmd07a_provenance.json` are historical FMD-07A schema-freeze evidence and must
remain byte-identical. R2B3 writes a new populated matrix rather than making the
hashes recorded by `fmd07a_provenance.json` point at overwritten content.

## 11. Provenance and hash gate

Before building, R2B3 must verify and record SHA-256 for:

- the final R2B2 source table;
- the R2B2 manifest;
- the R2B2 progress artifact and failure ledger;
- the R2B2 origin-source map;
- the R2B2 unique-source index;
- the R2A machine-readable aggregation protocol;
- the FMD-07A schema-freeze matrix;
- the FMD-07A model-input schema;
- the FMD-07A provenance artifact.

The source-table hash and row count must equal the values recorded by the R2B2
manifest. The schema-freeze matrix hash must equal the value recorded by
`fmd07a_provenance.json`. Any mismatch is a hard stop; R2B3 must not silently
regenerate an upstream artifact.

The R2B3 manifest must record SHA-256 for both output CSVs and the two
independent-build hashes. Run 1 and Run 2 must match before canonical outputs
are accepted.

## 12. Row-count and invariant gate

R2B3 is incomplete unless all checks pass:

1. R2B2 manifest checkpoint is `FMD-07A-R2B2` and reports 6,799 total,
   complete, and unique sources with zero remaining; the R2B2 progress artifact
   independently reports 6,799 terminal-accounted sources, zero terminal
   remaining, and the failure ledger contains no retryable source.
2. Source table has exactly 6,799 rows and 6,799 unique `source_id` values.
3. Origin-source map has exactly 3,761 origin keys, 41,684 appearances, no
   duplicate id inside an origin list, and a 6,799-id union exactly equal to
   the source-table id set.
4. R2A protocol has exactly 47 eligible predictor features.
5. Schema-freeze matrix has exactly 3,761 rows, 3,761 unique origin ids, and
   105 fields in the frozen order; every row is `FIT_DEVELOPMENT`.
6. Populated R2B3 matrix has exactly 3,761 rows, 3,761 unique origin ids, and
   the same 105 fields in the same order.
7. Every non-predictor cell in the R2B3 matrix is unchanged from the matching
   schema-freeze row.
8. The aggregation audit has exactly 176,767 unique origin-feature rows.
9. For every audit row,
   `valid_source_count + invalid_source_count == total_source_count`; its
   counts and status agree with the populated matrix cell.
10. No `EXTRACTION_NOT_RUN` status remains in the R2B3 predictor columns.
    Blank values are permitted only under the inherited no-valid/zero-source
    statuses.
11. No prohibited outcome-derived field is a predictor and no cache-private
    field is written.
12. Run 1 and Run 2 output SHA-256 values match.
13. All firewall flags in the R2B3 manifest are false as specified in Section
    10.

## 13. Focused software test gate

The future implementation must add:

```text
backend/components/geospatial_tracking/tests/test_fmd07a_r2b3_origin_matrix_population.py
```

The focused gate is:

```powershell
python -m pytest components/geospatial_tracking/tests/test_fmd07a_r2b3_origin_matrix_population.py -q
```

That test module must prove, offline:

- exact input hash/count/set reconciliation and rejection of drift;
- one origin row per id and exact frozen column order;
- source-id deduplication and deterministic source/origin order;
- unchanged R2A mean/status behavior, including all-valid, partial-valid,
  no-valid, and zero-source cases;
- rejection of available-status rows without finite numeric values;
- unchanged non-predictor join values and label-independent predictor output;
- no network, retry, universe rebuild, imputation, model, prediction, or metric
  path;
- exact real row counts (3,761 matrix; 176,767 audit);
- two independent offline builds are byte-identical and SHA-identical;
- held-out and Sri Lanka rows are rejected before output construction.

## 14. Directly affected Phase-7 regression gate

After the focused gate passes, run only:

```powershell
python -m pytest `
  components/geospatial_tracking/tests/test_fmd07a_feature_matrix.py `
  components/geospatial_tracking/tests/test_fmd07a_r2a_origin_feature_assembly.py `
  components/geospatial_tracking/tests/test_fmd07a_r2b2_full_extraction.py `
  -q
```

These cover the schema/role firewall, inherited aggregation semantics, and the
R2B2 input artifact respectively. The full backend/component suite is not an
R2B3 completion requirement unless implementation changes an existing
cross-cutting module outside the isolated R2B3 orchestrator/test surface or a
focused/regression failure demonstrates wider impact.

## 15. Firewalls

### 15.1 Held-out firewall

`HELD_OUT_FROM_MODEL_FITTING` origins, labels, targets, features, predictions,
and metrics are forbidden. A mixed-role input must be rejected as a whole.
FMD-08 remains the only checkpoint permitted to perform locked held-out
evaluation.

### 15.2 Sri Lanka firewall

`SRI_LANKA_TRANSFER_CASE_STUDY` origins, labels, targets, features,
predictions, and metrics are forbidden. Sri Lanka rows must not enter source
membership, predictor construction, the join scaffold, or any output.

### 15.3 Model-training firewall

R2B3 must not import or call estimators, fit preprocessing, select a feature or
weather window, fit calibration, choose a threshold, generate predictions, or
compute a predictive metric. The output is a deterministic data artifact, not
a trained model.

## 16. Completion gate and next checkpoint

R2B3 is complete only when all three artifacts in Section 10 exist, all focused
and affected-regression tests pass, every invariant and firewall flag passes,
and the two independent offline builds have matching SHA-256 values.

The exact completion/readiness token is:

```text
FMD-07A-R2B3_COMPLETE_READY_FOR_FMD-07B
```

The next checkpoint is **FMD-07B: FIT_DEVELOPMENT-only model development and
training under the already-frozen pre-model/evaluation protocols**. R2B3 must
stop before FMD-07B begins.
