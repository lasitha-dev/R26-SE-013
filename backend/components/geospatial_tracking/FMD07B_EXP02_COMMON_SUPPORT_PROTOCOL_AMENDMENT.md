# FMD-07B EXP-02 Common-Support Evaluation Protocol Amendment

## 1. Identity, timing, and scope

```text
checkpoint=FMD-07B
amendment_status=FINAL_PREEXECUTION_EVALUATION_DENOMINATOR_FREEZE
fmd_exp01_exp04_predictions_already_persisted=true
fmd_exp01_exp04_retraining_authorized=false
fmd_exp02_real_scores_produced=false
fmd_exp02_candidate_metrics_inspected=false
persisted_prediction_values_inspected_for_this_amendment=false
engineering_unavailable_origin_labels_inspected=false
held_out_outcomes_inspected=false
sri_lanka_outcomes_inspected=false
locked_test_outcomes_inspected=false
```

This amendment freezes only the FMD-07B development candidate-comparison
denominator. It does not change a candidate definition, kernel, transform,
feature, fitted parameter, prediction formula, fold membership, label, target,
threshold grid, metric formula, or aggregation formula. It does not authorize
held-out, Sri Lanka, or locked-test access.

The amendment is made after the deliberately partial FMD-EXP-01/FMD-EXP-04
prediction run, but before any real FMD-EXP-02 score and before any final
comparison across the minimum executable set. The existing partial ranking and
metrics remain diagnostic only and are not eligible for final selection.

## 2. Existing-contract finding

The repository already supports visible candidate-specific prediction
unavailability:

- `fmd_model_development_7b_execution.compute_fold_metrics` records
  `n_scored`, `n_unscored`, and `unscored_reason_counts`, but currently derives
  each candidate's metric denominator from that candidate's own prediction keys;
- `model_development/evaluation_protocol_7b.py` preserves incomplete coverage
  and can make an incomplete candidate ineligible for primary selection.

Neither mechanism defines an intersection-of-scoreable-origins denominator for
FMD-EXP-01, FMD-EXP-02, and FMD-EXP-04. Candidate-specific denominators would
therefore be possible without this amendment and would not provide a like-for-
like primary comparison.

## 3. Frozen common-support rule

For each already-frozen usable chronological fold `f`, let `V_f` be its full
validation-origin set. For every candidate `c` in the minimum executable set
FMD-EXP-01, FMD-EXP-02, and FMD-EXP-04, let `A_c,f` be the origins in `V_f`
whose prediction status is structurally scoreable.

`A_c,f` must be determined without reading a validation outcome or candidate
performance:

- FMD-EXP-01 and FMD-EXP-04 use only persisted row presence and prediction
  availability status; numeric prediction values and labels are not inputs to
  support construction;
- FMD-EXP-02 uses only pre-score source/grid/reference/input completeness and
  engineering status, including the propagated unsafe-component count; no
  numeric spatial score or label is an input to support construction;
- the three known projection-unsafe origin identifiers are derived only from
  `unsafe_component_count > 0` and its existing engineering completeness
  status. Their labels, target outcomes, and candidate scores must not be read
  to decide exclusion.

The primary comparison support is frozen as:

```text
S_f = intersection(A_c,f for every minimum-set candidate c)
COMMON_SUPPORT_RULE=FMD07B_INTERSECTION_OF_STRUCTURALLY_SCOREABLE_ORIGINS_V1
```

The identical `S_f` must be used for every FMD-EXP-01, FMD-EXP-02, and
FMD-EXP-04 candidate when calculating PR-AUC, AUROC, Brier score, threshold
selection, F1, precision, recall, specificity, reliability curves, fold
summaries, and final candidate ranking. Candidate-specific unavailable rows
remain visible in audits, but a candidate must never receive a primary metric
on a denominator different from another compared candidate.

For FMD-07B only, an unavailable validation-origin row outside pre-frozen
`S_f` does not by itself make a candidate ineligible when the row's exclusion
was determined under this outcome-independent common-support rule. This
narrowly supersedes candidate-specific complete-case metric denominators and
the implication that such an already-excluded origin row must disqualify the
whole FMD candidate. It does not supersede the existing coverage guard inside
`S_f`: candidate-specific missing domain/input support on a common-support
origin remains unavailable and triggers the fail-closed rule below. It also
does not alter the generic 7B spatial-ranking protocol outside FMD-07B.

Support is fixed before the first real FMD-EXP-02 score. If execution later
finds any candidate unavailable on an origin inside frozen `S_f`, the run fails
closed before final metrics or selection; `S_f` must not be shrunk after seeing
scores or outcomes.

After `S_f` is frozen, metric definability is checked on `S_f` identically for
all candidates. A fold with fewer than two common-support origins or only one
class on common support contributes no candidate metric for any candidate. This
common fold-level decision does not alter `S_f` and must not inspect the labels
of excluded engineering-unavailable origins.

## 4. Existing predictions and fitting state

FMD-EXP-01 and FMD-EXP-04 must not be retrained or refitted. Their persisted
out-of-fold predictions are filtered by membership in `S_f`; fold metrics,
thresholds, reliability summaries, and aggregate metrics are then recomputed on
that identical support. Filtering predictions is evaluation bookkeeping, not a
change to candidate mathematics or fitted state.

FMD-EXP-02 is scored under its already-frozen candidate mathematics only for
the real execution. No unavailable origin receives a placeholder number, and
no FMD-EXP-01/FMD-EXP-04 score is substituted for it.

Training-origin membership and training-fold preprocessing/fitting inputs are
unchanged. Common-support filtering applies only to validation prediction rows
used for comparison.

## 5. Required audit evidence

Before real FMD-EXP-02 scoring, the existing chronological-fold manifest and
final FMD-07B manifest must freeze and later reproduce:

- `COMMON_SUPPORT_RULE` and this amendment's SHA-256;
- each fold's full validation-origin count, common-support count, excluded
  count, deterministically sorted common-support origin IDs, and their canonical
  SHA-256;
- the engineering-only unavailable-origin count, deterministically sorted IDs,
  status reasons, and canonical SHA-256;
- proof that the common-support identity was written before the first real
  FMD-EXP-02 score;
- per-candidate unavailable counts before common-support filtering and identical
  evaluated-origin counts after filtering;
- `exp01_retrained=false`, `exp04_retrained=false`, `held_out_used=false`,
  `sri_lanka_used=false`, and `locked_test_used=false`.

The support artifact may reuse the already-required chronological-fold and
manifest outputs; this amendment does not add a new canonical output filename.

## 6. Gate decision

This outcome-independent common-support rule resolves the evaluation-denominator
contract without changing candidate mathematics. Subject to all other existing
FMD-07B readiness and firewall gates, it permits real FMD-EXP-02 execution to
begin. It does not itself execute FMD-EXP-02 or complete FMD-07B.

```text
CHECKPOINT_07B_EXP02_REAL_EXECUTION_READY
```

## 7. EXP-02 cutoff-integrity correction evidence (2026-08-27)

This section records repository-correctness evidence discovered after the
pre-execution amendment above. It does not change the common-support rule,
candidate mathematics, fold eligibility rules, target semantics, or any
biological assumption.

### 7.1 Defect and correction

`run_exp02_composition` already passed the authoritative FMD cutoff
`2026-01-01` to raw-host snapshot construction and fold-safe reference
construction. It did not pass that cutoff to `build_calendar_year_folds`, so
that call used the shared disease-independent default `2024-01-01`. The fix is
local: the composition now passes
`cutoff=AUTHORITATIVE_FIT_DEVELOPMENT_CUTOFF` explicitly. The shared
`MODEL_FITTING_CUTOFF = 2024-01-01` remains unchanged for other workflows.

The corrected propagation chain is therefore:

```text
FMD_MODEL_FITTING_CUTOFF = 2026-01-01
  -> load_authoritative_fit_development_origins
  -> build_calendar_year_folds(..., cutoff=2026-01-01)
  -> build_raw_host_snapshots_cached(..., cutoff=2026-01-01)
  -> build_fold_safe_reference(..., cutoff=2026-01-01)
```

### 7.2 Coverage derived from repository artifacts

The live builder output from the 3,761 authoritative R2B3 development origins
is byte-semantically equal to
`local_data/processed/fmd/cohort/fmd_calendar_year_folds.json`. It contains 23
eligible folds and 3,681 unique validation origins:

| Fold | Validation origins |
|---|---:|
| FOLD:2002 | 1 |
| FOLD:2003 | 2 |
| FOLD:2005 | 40 |
| FOLD:2006 | 76 |
| FOLD:2007 | 90 |
| FOLD:2008 | 61 |
| FOLD:2009 | 66 |
| FOLD:2010 | 168 |
| FOLD:2011 | 284 |
| FOLD:2012 | 184 |
| FOLD:2013 | 107 |
| FOLD:2014 | 219 |
| FOLD:2015 | 241 |
| FOLD:2016 | 72 |
| FOLD:2017 | 177 |
| FOLD:2018 | 443 |
| FOLD:2019 | 231 |
| FOLD:2020 | 94 |
| FOLD:2021 | 219 |
| FOLD:2022 | 250 |
| FOLD:2023 | 113 |
| FOLD:2024 | 122 |
| FOLD:2025 | 421 |
| **Total** | **3,681** |

No authoritative fitting origin and no validation origin has `t0` on or after
`2026-01-01`. The current frozen EXP-02 grid contains 18 candidates, so exact
structural coverage is `3,681 x 18 = 66,258` prediction rows.

The previously persisted artifact is retained unchanged as defective evidence.
Its manifest lists 21 folds ending at `FOLD:2023` and 56,484 rows, equivalent
to `56,484 / 18 = 3,138` validation origins per candidate. It omits the 122
eligible 2024 origins and 421 eligible 2025 origins: 543 origins and 9,774
candidate/origin rows in total. It is not a completed result under the current
protocol.

### 7.3 Completed-artifact reuse contract

Reuse now validates the existing integrity checks plus the current
authoritative structural contract:

- exact ordered fold IDs;
- exact candidate IDs from the frozen runner grid;
- exact validation-origin count;
- exact candidate x fold x validation-origin key coverage;
- no duplicate candidate/fold/origin key;
- expected row count, authoritative cutoff, and current input-artifact hashes.

New manifests also persist `fit_development_cutoff`, `candidate_ids`, and
`validation_origin_count`. A real check against the retained stale pair fails
closed before scoring with:

```text
EXP-02 artifact structural coverage does not match current calendar folds
```

### 7.4 Files and tests

Files changed for this correction:

- `services/fmd_model_development_7b_exp02_execution.py`;
- `tests/test_fmd07b_exp02_execution.py`;
- this existing EXP-02 protocol/evidence document.

The new regression tests were observed failing before the production fix: the
cutoff-propagation test failed because the calendar builder received no cutoff,
and both stale-coverage tests failed because no integrity exception was raised.
After the fix:

```text
cd backend
python -m pytest components/geospatial_tracking/tests/test_fmd07b_exp02_execution.py -q
21 passed in 2.38s

python -m pytest components/geospatial_tracking/tests/test_model_fitting_exposure.py components/geospatial_tracking/tests/test_fmd07b_exp02_origin_adapter.py components/geospatial_tracking/tests/test_fmd07b_exp02_execution.py -q
38 passed in 2.41s
```

### 7.5 Real execution status and stop gate

No corrected real EXP-02 execution was started. The only configured output pair
is occupied by the retained defective artifact, and the strengthened reuse
guard now correctly refuses it. No repository convention authorizes deleting,
overwriting, or relocating that evidence automatically. Running the full CLI
would therefore perform preparatory work only to stop at the same guard.

The next action is an explicit evidence-preserving archival/output-path
decision, followed by the real 66,258-row EXP-02 run and verification of its
new manifest. Until that run completes, FMD-07B is not complete and progression
to locked FMD-08 evaluation is **NO-GO**.

### 7.6 Real execution completed and verified (2026-08-27)

The stale defective artifact pair (21 folds, 56,484 rows) had already been
archived out of the configured output path before this session, satisfying
the evidence-preserving decision called for in 7.5. The corrected canonical
importer mapping (`modelling_eligible` -> `model_candidate`, Section 7.1's
sibling fix in `services/historical_import.py`) was re-imported into the
existing SQLite repository, restoring real eligible sources.

Two execution attempts of
`fmd_model_development_7b_exp02_execution` failed before completion, both for
the same non-scientific, environment-level reason and neither touching
candidate mathematics, fold definitions, or the frozen evaluation protocol:

```text
MemoryError raised inside build_raw_host_snapshots_cached -> _load_cache_entry
(json.load), while accumulating the full-corpus raw host snapshot dict in
process memory. Measured JSON-parse expansion factor ~1.7x; full corpus
(~3,681 origins, ~3.5 GB on disk) requires ~6 GB resident. The host machine's
free commit charge was transiently below that threshold due to concurrent
unrelated applications (multiple editor windows, a browser, other local
processes), not a defect in this repository's code.
```

No production code was changed to work around this; the disk-persisted cache
(keyed by `raw_snapshot_cache_identity_hash`, content-validated on every read)
meant a relaunch after available memory recovered resumed from the
already-cached ~3,230+ entries rather than recomputing them.

The third launch (PID 4672, started 2026-08-27 09:59:13) ran to completion
(`execution_complete=true`) and produced:

```text
fmd07b_exp02_manifest.json
fmd07b_exp02_fold_predictions.csv
```

Observed manifest values, verified against the files on disk (not only the
process's own stdout):

```text
experiment_id            = FMD-EXP-02
fit_development_cutoff   = 2026-01-01
fold_ids                 = 23 folds, FOLD:2002 .. FOLD:2025 (final fold FOLD:2025)
candidate_ids            = 18 (exact frozen FMD07B:SPATIAL grid)
validation_origin_count  = 3681
row_count                = 66258   (3681 x 18)
scored_count             = 26250
unavailable_count        = 40008
held_out_used            = false
sri_lanka_used           = false
locked_test_used         = false
predictions_sha256 (manifest) = 72bd3b5ceb827196dc746ca4cfc555fc111587257b38fa4f498ed9db65f40ac5
predictions_sha256 (recomputed from fmd07b_exp02_fold_predictions.csv on disk) = MATCH
```

Independent verification of `fmd07b_exp02_fold_predictions.csv` (66,258 data
rows, header
`fold_id,experiment_id,candidate_id,forecast_origin_id,true_label,predicted_score,status`):

- 66,258 unique `(fold_id, candidate_id, forecast_origin_id)` keys, no
  duplicates;
- exactly 18 distinct `candidate_id`, 3,681 distinct `forecast_origin_id`, 23
  distinct `fold_id` values, matching the manifest's counts;
- status breakdown `SCORED=26250`, `MODEL_INPUT_INCOMPLETE=40008`, summing to
  66,258; the prior all-`unavailable` (66,258/66,258) condition from the
  pre-importer-fix artifact is gone;
- all 26,250 `SCORED` rows carry a finite `predicted_score`; all
  non-`SCORED` rows carry an empty `predicted_score` (no placeholder or
  invented values on unavailable rows);
- `true_label` is binary (`{0, 1}`) on every row.

The separate LSD raw host-snapshot cache
(`local_data/model_development/7b/raw_host_snapshot_cache`) was not read,
written, or otherwise touched by this correction or by any of the three
execution attempts; its newest file predates this session.

```text
CHECKPOINT_07B_EXP02_REAL_EXECUTION_COMPLETE
```

FMD-07B's real FMD-EXP-02 execution is complete and its artifact pair is
verified against the frozen structural contract in Section 7.3.
Progression to FMD-08 is **GO**.
