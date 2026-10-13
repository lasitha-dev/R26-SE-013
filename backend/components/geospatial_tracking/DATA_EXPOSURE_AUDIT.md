# Data Exposure Audit — Checkpoint 4 Part 1

Scientific honesty check: what has already been looked at, by whom, and
what that does and doesn't mean for later validation claims.

## 1. Why this document exists

Checkpoints 1-3.5 involved extensive manual and programmatic inspection of
the entire raw and canonical corpus — parsing verification, duplicate
detection, the Sri Lanka and Thailand matching audits, date-distribution
analysis, and data-quality scoring. That inspection was necessary
engineering work. But it means that **no future partition drawn from this
same corpus can be casually called "completely unseen," "a blind test," or
"an untouched test set"** without that being a specific, checkable claim
about model-fitting exposure — not about whether a human or a data
pipeline has ever looked at the rows.

**The distinction that matters:** seeing records during data engineering
(parsing, deduplication, quality scoring, chronology description) is not
the same as fitting a model's parameters on them. A partition can still be
legitimately "held out from model fitting" even though its rows were
inspected while building the pipeline. What it can *never* honestly be
called, given that inspection, is "blind" in the sense of "no one and
nothing has examined this data's content, structure, or distribution."

## 2. Exactly what has been inspected so far, and how

| Activity | Checkpoint | What was seen |
|---|---|---|
| Raw file parsing + structural inventory | 1 | Every row/outbreak block's field-level content, all 4 WAHIS PDFs read close to fully (Event_3644.pdf's 670 blocks processed programmatically + spot-checked), full CSV column inventory |
| Duplicate detection thresholds (date/distance tolerances) | 2 | Hand-verified against the actual Sri Lanka 6-episode match table and Thailand's overlap patterns — tolerances were chosen partly by looking at what values made the known-correct matches work |
| Sri Lanka 6-outbreak match table | 2 | Full manual verification: every CSV row's coordinates, dates, and species compared directly against every WAHIS outbreak in Event_3473.pdf |
| Thailand overlap counts (817 CSV rows, 676 WAHIS blocks) | 2 | Aggregate statistics computed and read (counts by confidence tier), not row-by-row, but the distribution shape (heavy LOW-confidence clustering from Event_3644's approximate coordinates) directly informed the approximate-coordinate protection rule design |
| Data-quality component distributions | 2 | Full distribution tables (gps_quality, date_quality, etc.) across all 3089 raw records |
| Model-candidate / dedup-status counts, per-country | 2.5 | Full breakdown inspected, including the exact Thailand LOW/MEDIUM/HIGH split |
| Chronology (date ranges, monthly counts) | 4 | Full per-country date range and monthly-bucket counts for all 37 countries, explicitly including Thailand and Sri Lanka |
| Canonical spatial-independence results | 4 | Full True/False counts and country breakdown, including the specific Sri Lanka Chavakachcheri coordinate collision |
| Target quality tier counts, per country | 4 | Full breakdown — including that Thailand holds effectively all Tier-A eligible targets (see `HISTORICAL_CHRONOLOGY_AUDIT.md`) |

**What has NOT happened:** no model has been fit, tuned, or evaluated
against any of this data. No performance metric (accuracy, distance
error, calibration, or otherwise) has ever been computed. "Inspection"
here means data engineering and descriptive statistics only.

## 3. Accurate terminology going forward

Do not use "unseen"/"blind"/"untouched" for any partition of this corpus.
Instead:

- **DEVELOPMENT** — data used to build, debug, and iterate on the
  pipeline/model itself. Fully inspected, expected to be inspected.
- **TEMPORAL_VALIDATION** — a chronologically later partition, held out
  from model *fitting* (parameter estimation), used to check performance
  under a genuine forecast-origin ordering. Its rows were inspected during
  data engineering (this document); they were not used to fit model
  parameters.
- **HELD_OUT_FROM_MODEL_FITTING** — the general, honest description for
  any partition never used to fit parameters, regardless of whether its
  distribution was described during engineering.
- **TEMPORAL_SENSITIVITY** — an analysis re-run across a different
  chronological cut to check how sensitive results are to the split
  boundary choice, not a claim of independent validation.
- **GEOGRAPHIC_TRANSFER_CASE_STUDY** — evaluating a model fit on one
  geography against a different geography (e.g. Sri Lanka), explicitly
  NOT a random or chronological holdout of the same population. See
  `SPLIT_PROTOCOL_DRAFT.md` Part 12 for why Sri Lanka's small N makes it
  a case study, not a statistically powered external test.

## 4. Rule from this checkpoint onward

**Do not inspect validation/test PARTITION PERFORMANCE to make
development choices.** Chronology, counts, coverage, and data-quality
distributions (as documented in this file and
`HISTORICAL_CHRONOLOGY_AUDIT.md`) may continue to be examined — that is
data engineering, and this document exists precisely so that examination
is never mistaken for blindness. What must not happen from here on is
looking at how well a fitted model performs on a validation/test
partition and then adjusting development choices (features, model
structure, hyperparameters, tier thresholds) in response. No model exists
yet, so this rule is prospective — it binds the *next* checkpoint's
process, not anything already done.

## 5. Consequence for later checkpoints

- Any reported "validation" or "test" result must state explicitly which
  of the terms in §3 applies and why.
- Sri Lanka, in particular, must never be called a "large external
  validation dataset" or "statistically strong external test" — see
  `SPLIT_PROTOCOL_DRAFT.md` Part 12 and `HISTORICAL_CHRONOLOGY_AUDIT.md`
  for its actual N and chronology.
- If a chronological split boundary is chosen and development data
  postdates part of a nominally "held out" country's history (e.g.
  Sri Lanka 2020 vs. other countries' later records), the corresponding
  evaluation must be labeled a retrospective **geographic transfer case
  study**, never "prospective temporal validation" — see
  `SPLIT_PROTOCOL_DRAFT.md` Part 12 for the specific chronology check.

## 6. Locked rule (Checkpoint 4.5) — no performance-driven redesign

Restating §4 with the exact scope, now that `VALIDATION_PROTOCOL.md`
freezes a primary validation strategy: **validation/test-partition
PERFORMANCE must never be used to redesign** dedup rules, GPS rules,
event-date rules, target-tier definitions, or split boundaries — unless
that redesign is explicitly declared as a new DEVELOPMENT decision and is
followed by a new, genuinely independent evaluation protocol (never a
re-check against the same partition that motivated the change). This
governs work from Checkpoint 4.5 forward. It does not retroactively
condemn Checkpoints 4/4.5's own tier/collision/split-boundary design
work — none of it was performance-driven, because no model has existed at
any point so far to produce a performance number to react to. See
`VALIDATION_PROTOCOL.md` §4 for the frozen statement of this rule
alongside the rest of the validation freeze.

## 7. Checkpoint 7D / 7D.1 — held-out exposure disclosure, CORRECTED (never called single-shot/blind/untouched)

`HELD_OUT_FROM_MODEL_FITTING` (229 real origins, `t0 >= 2024-01-01`,
non-Sri-Lanka) was excluded from every parameter/coefficient FITTING
decision (Checkpoint 6B onward), and the Checkpoint 7C model
specification was frozen before the FINAL 229-origin predictive score
was computed (Checkpoint 7D Part 2's hard freeze gate). The 2024+ corpus
had already been inspected/characterized at the DATASET level during
project development — its existence, row counts, and date range were
referenced when `MODEL_FITTING_CUTOFF` and `classify_origin_role` were
designed and tested (Checkpoint 6B).

**Correction (Checkpoint 7D.1)**: the original Checkpoint 7D report
additionally stated "no 7D held-out PREDICTIVE outcome was inspected...
prior to this checkpoint's single-shot run." **This was false.** Before
the formal 7D test suite and before the final 229-origin freeze
manifest/run, a real predictive sanity evaluation was executed on a
40-origin held-out subset (`heldout[:40]`, first 40 origins in
deterministic ledger order — Algeria, Cambodia, China/Hong Kong, France)
using the exact same evaluator. Its pooled metrics (mean percentile
84.763, TOP5 0.25, TOP10 0.383, n=10 contributing origins) and
country-level diagnostics were genuinely inspected. This exposure is
preserved, never hidden, at
`local_data/model_evaluation/7d/pre_final_40_origin_sanity_exposure.json`.
Independent filesystem-mtime audit
(`procedural_exposure_correction_7d1.json`) confirms no numerically
load-bearing scientific code changed between that exposure and the
final run — `NO_POST_EXPOSURE_MODEL_RETUNING_DETECTED` — so the final
229-origin result was not retuned in response, but the exposure itself
did happen and is disclosed.

The accurate label is now
`FROZEN_HELD_OUT_FROM_FITTING_EVALUATION_WITH_PRIOR_DATASET_AND_PRE_FINAL_PREDICTIVE_SUBSET_EXPOSURE_DISCLOSED`
— never `SINGLE_SHOT`, `FIRST_PREDICTIVE_INSPECTION`, `BLIND_TEST`,
`UNTOUCHED_TEST`, `UNSEEN_TEST`, or `EXTERNAL_VALIDATION`. See
`local_data/model_evaluation/7d/heldout_exposure_disclosure.json`
(gitignored, corrected) and `MODEL_DEVELOPMENT_PROTOCOL.md` §61.

## 8. Checkpoint 7E — Sri Lanka geographic-transfer case-study exposure disclosure

`SRI_LANKA_TRANSFER_CASE_STUDY` (5 real forecast origins) was excluded
from every fitting decision from Checkpoint 6B onward, unconditionally
(regardless of t0) per `classify_origin_role`'s Sri-Lanka-first check.
The Checkpoint 7C model specification was frozen (Checkpoint 7C.1.1)
long before this case study ever ran. **This is a
`FROZEN_GEOGRAPHIC_TRANSFER_CASE_STUDY`, never
`EXTERNAL_VALIDATION`/`INDEPENDENT_VALIDATION`/`BLIND_VALIDATION`/
`PROSPECTIVE_VALIDATION`/`SRI_LANKA_MODEL_TUNING`/`PRODUCTION_ACCURACY`/
`CAUSAL_TRANSMISSION_VALIDATION`.** Sri Lanka's raw data had already
been characterized at the dataset level in earlier checkpoints
(`HISTORICAL_CHRONOLOGY_AUDIT.md` §7, `SPLIT_PROTOCOL_DRAFT.md` Part 12
— including the finding that Sri Lanka's 2020 event predates 11 other
countries' data and predates Thailand entirely, ruling out any
"prospective" framing). All 6 model-candidate Sri Lanka records carry
`availability_quality=EVENT_DATE_PROXY` (never `ACTUAL`) — the real
`operational_availability_date`/`operational_availability_quality` are
genuinely `None`/`UNKNOWN` for every record, honestly disclosed, never
manufactured. The result is therefore `RETROSPECTIVE_PROXY`, never
claimed as prospective real-time performance. Only 1 of 2 real D1-D7
targets fell within the frozen 25km scope; with only 1 contributing
origin (far below the n=10 small-sample threshold), the case study is
`SRI_LANKA_TRANSFER_CASE_STUDY_LIMITED_BY_SMALL_SAMPLE` — reported
descriptively only (individual target percentile, no bootstrap CI). See
`local_data/model_evaluation/7e_sri_lanka/` (gitignored),
`CHECKPOINT_7E_EVIDENCE_SUMMARY.json` (not gitignored and intended to be
tracked, though currently untracked pending a checkpoint commit), and
`VALIDATION_PROTOCOL.md` §12.
