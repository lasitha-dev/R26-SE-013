# FMD-05 Split Protocol — Frozen

Freezes how FMD's forecast origins are partitioned for model-fitting
purposes, before any FMD-06 parameter/coefficient development begins.
Reuses the generic, disease-agnostic role/fold machinery already frozen
for LSD (`services/model_fitting_exposure.py`, `services/split_embargo.py`)
**unmodified**, with FMD's own, independently-derived cutoff date and
FMD-specific justification. No model exists yet for either disease; this
freeze is based on chronology, coverage, and target counts only — never
on any performance number.

## 0. FMD-05R correction — event counts vs. forecast-origin counts

**A real defect was found and repaired after FMD-05's initial freeze.**
`data_processing/build_fmd_cohort.py` built `FMD_COHORT_AUDIT.csv` as one
row per CANONICAL EVENT (9,311 INCLUDED rows), each carrying its
containing forecast origin's role for traceability — correct for an
audit trail. The bug was that `FMD_COHORT_MANIFEST.json`'s
`model_fitting_role_counts` field was computed by counting THOSE EVENT
ROWS (yielding 6,799 / 2,492 / 20, summing to 9,311), while every FMD-05
document (including earlier revisions of this one) then labeled and
reported those numbers as **forecast-origin counts** — but
`FMD_STUDY_PROTOCOL.md` §4 already freezes the forecast origin, not the
canonical event, as the primary modelling unit, and the corpus has only
**4,322** unique forecast origins, not 9,311.

**Fixed.** The manifest now reports two explicitly separate, correctly-
labeled fields, computed from two different one-row-per-unit sources:

- `included_source_event_role_counts` (EVENT-level; one tally per
  INCLUDED canonical event; computed from `FMD_COHORT_AUDIT.csv`; sums to
  the INCLUDED event count, 9,311): `{FIT_DEVELOPMENT: 6799,
  HELD_OUT_FROM_MODEL_FITTING: 2492, SRI_LANKA_TRANSFER_CASE_STUDY: 20}`.
- `forecast_origin_role_counts` (ORIGIN-level — the TRUE, primary-unit
  counts; one tally per row of `fmd_model_fitting_exposure_manifest.csv`,
  which has exactly one row per forecast origin by construction of
  `build_model_fitting_exposure_manifest`; sums to `forecast_origin_count`,
  4,322): **`{FIT_DEVELOPMENT: 3761, HELD_OUT_FROM_MODEL_FITTING: 541,
  SRI_LANKA_TRANSFER_CASE_STUDY: 20}`.**

Both invariants (`sum(forecast_origin_role_counts) ==
forecast_origin_count` and `sum(included_source_event_role_counts) ==
included_event_count`) are now asserted directly inside `run()` — a
future reintroduction of this conflation would raise, not silently
regenerate a wrong manifest. §2-§3 below are corrected to use the
ORIGIN-level counts, since the origin is the frozen primary unit.

## 1. Why chronological (never random) splitting

`VALIDATION_PROTOCOL.md` §1 already established, for the shared
walk-forward machinery, that `train_test_split(random_state=...)` or any
row-level shuffle is structurally absent from this repository's split
code (verified for LSD; the same modules, unmodified, are reused for
FMD, so the same structural guarantee applies — see
`test_fmd05_study_protocol.py`). FMD's own chronology independently
confirms chronological splitting is the right choice: eligible-event
counts per onset-date calendar year show several distinct multi-year
waves (not one concentrated wave, unlike LSD's Thailand 2021 case), so an
expanding-window / walk-forward design — never a single fixed cut — is
appropriate.

**Real per-year eligible FMD EVENT counts** (`onset_date` year, 9,311
eligible events, from the frozen canonical CSV — used here only to show
the corpus has several distinct multi-year waves, motivating
chronological splitting in general; §2 uses ORIGIN-level counts for the
actual cutoff justification):

| Year range | Eligible events |
|---|---:|
| 2002-2009 | 521 |
| 2010-2019 | 3,984 |
| 2020-2024 | 1,224 |
| 2025 | 1,090 |
| 2026 (through 2026-08-09) | 2,492 |

Event-level cumulative through 2025: 6,819 of 9,311 (73.2%). 2026 alone:
2,492 (26.8%). **These are EVENT counts, not forecast-origin counts —
see §0 and §2.**

## 2. FMD_MODEL_FITTING_CUTOFF — FROZEN (origin-level re-derivation, FMD-05R)

```
FMD_MODEL_FITTING_CUTOFF = "2026-01-01"
```

Frozen in `data_processing/build_fmd_cohort.py`, with a structural test
(`test_fmd05_study_protocol.py`) asserting it is **not equal to**
`services.model_fitting_exposure.MODEL_FITTING_CUTOFF` (LSD's
`"2024-01-01"`) — the two are independently derived values, not a copy.

**The primary modelling unit is the forecast origin, so the cutoff must
be justified at the origin level (FMD-05R), not the event level (as
FMD-05 originally, incorrectly, did — see §0).** Real ORIGIN-level
chronology (`fmd_model_fitting_exposure_manifest.csv`, non-Sri-Lanka
origins, 4,302 of 4,322):

| Partition | Origins | % of non-Sri-Lanka origins |
|---|---:|---:|
| `FIT_DEVELOPMENT` (`t0 < 2026-01-01`) | 3,761 | 87.4% |
| `HELD_OUT_FROM_MODEL_FITTING` (`t0 >= 2026-01-01`) | 541 | 12.6% |

**This is a materially different, and materially smaller, held-out
fraction than the event-level 26.8% figure suggested** — because 2026's
held-out countries (South Africa above all) have unusually HIGH
same-country/same-day trigger multiplicity (§3), so a large number of
2026 events collapse into comparatively few origins. 12.6% is below the
conventional ~20-30% held-out convention, but **541 origins spanning 19
countries** (§3) remains a materially sized, purely-future,
multi-country block — large enough to support the frozen primary metrics
(PR-AUC/AUROC, `FMD_EVALUATION_PROTOCOL.md` §5) without collapsing to a
handful of origins. **The cutoff is RECONFIRMED, not moved**: shifting it
now, after seeing this smaller-than-expected origin-level percentage,
would itself be exactly the outcome/percentage-driven leakage this
freeze exists to prevent (§1's ban applies to origin-level evidence
exactly as it did to event-level evidence). No calendar-year boundary in
this 24-year corpus avoids some such trade-off; 2026-01-01 remains the
boundary that isolates a single, purely-future, non-fragmented block.

## 3. Model-fitting-exposure roles (identical mechanism, TRUE origin-level FMD counts)

Computed by `services.model_fitting_exposure.classify_origin_role`
(unmodified) over the 4,322 real FMD forecast origins, with
`cutoff="2026-01-01"` passed explicitly (never relying on that function's
own LSD-oriented default). Authoritative source: `fmd_model_fitting_exposure_manifest.csv`
(exactly one row per forecast origin) — **not** `FMD_COHORT_AUDIT.csv`
(one row per canonical event, §0):

| Role | Rule | Origin count |
|---|---|---:|
| `FIT_DEVELOPMENT` | `country != "Sri Lanka"` and `t0 < 2026-01-01` | 3,761 |
| `HELD_OUT_FROM_MODEL_FITTING` | `country != "Sri Lanka"` and `t0 >= 2026-01-01` | 541 |
| `SRI_LANKA_TRANSFER_CASE_STUDY` | `country == "Sri Lanka"` (unconditional, even pre-cutoff) | 20 |

Sum: 3,761 + 541 + 20 = **4,322**, matching `forecast_origin_count`
exactly (`FMD_COHORT_MANIFEST.json.forecast_origin_role_counts`,
asserted in code). The corresponding EVENT-level tally (how many
INCLUDED canonical events sit inside an origin of each role — a
DIFFERENT, non-interchangeable quantity, useful only for understanding
raw reporting volume, never for stating sample size) is
`included_source_event_role_counts`: `{FIT_DEVELOPMENT: 6799,
HELD_OUT_FROM_MODEL_FITTING: 2492, SRI_LANKA_TRANSFER_CASE_STUDY: 20}`,
summing to 9,311.

`HELD_OUT_FROM_MODEL_FITTING` is **not** "blind," "untouched," or
"unseen" — every FMD record has already been through the same audited
ingestion/dedup/eligibility pipeline (FMD-01 through FMD-04) as
`FIT_DEVELOPMENT` records. The only thing that changes is exclusion from
any function that selects, fits, or tunes a parameter/coefficient/
normalization constant. A future evaluation checkpoint may compute
descriptive counts over it (as this document does) without that
constituting leakage — only decisions driven by its *prediction
performance* would.

**Held-out country footprint (19 countries, 541 ORIGINS — not 2,492;
that figure is the EVENT-level count, §0):** computed at the origin
level from `fmd_model_fitting_exposure_manifest.csv`. This remains a
genuine, multi-country, multi-continent recent block — not an artifact
confined to one reporting country — and the fact that 2,492 EVENTS
collapse into only 541 ORIGINS is itself informative: it shows the
2025-2026 South-Africa-dominated wave is characterized by many same-
country/same-day confirmations (high trigger multiplicity, §3 in
`FMD_STUDY_PROTOCOL.md`/`fmd_historical_forecast_origins.csv`) rather
than by broad daily geographic dispersion.

## 4. Sri Lanka — frozen role and limitations

**Frozen label: `SRI_LANKA_TRANSFER_CASE_STUDY`.** Never "prospective
validation," "large external validation dataset," or "statistically
strong external test." All 20 Sri Lanka events (2009-09-09 through
2019-12-17, see `FMD_COHORT_AUDIT.csv`) are unconditionally excluded from
`FIT_DEVELOPMENT` — even the 2009-2019 ones that would otherwise fall
before the 2026-01-01 cutoff — for the same reason
`SPLIT_USAGE_FREEZE.md` §2 gives for LSD (never let the country the
system is meant to serve implicitly shape a development decision), plus
an FMD-specific reason: **20 events is far too small a sample to
independently fit or validate a complex spatial-temporal model**
(`FMD_DATA_AUDIT.md` panel-defence note 12 — unlike LSD's justification,
this is a sample-size argument, not a vector-biology argument, and must
never be conflated with LSD's). All 20 Sri Lanka events yield 20 distinct
forecast origins (no two share a country+day bucket). Sri Lanka data may
be used, after FMD-06/07 protocols are frozen and applied using
`FIT_DEVELOPMENT` data only, for case-study visualization and
transfer/limited-quantitative discussion — **never** folded into primary
risk-model validation metrics, and never used to tune anything.

## 5. Horizon-safe purge/embargo (identical mechanism, FMD-applied)

**`PURGED_7_DAY_HORIZON_POLICY`** (`services/split_embargo.py`,
unmodified): for split boundary `B` and horizon `H=7`, a development
origin is eligible for the earlier partition only when `t0 + 7 < B`; an
origin with `t0 < B` and `t0 + 7 >= B` is purged from that partition
entirely (never clipped-and-kept with a truncated horizon). A validation
origin supports a COMPLETE D1-D7 evaluation only when
`t0 >= block_start` and (`block_end is None` or `t0 + 7 <= block_end`).

**Calendar-year expanding-window folds** (`build_calendar_year_folds`,
`FIT_DEVELOPMENT` origins only, `cutoff=2026-01-01`) — real FMD counts,
23 folds (years 2002-2025, 2004 has zero eligible events so contributes
no fold):

| Validation year | Training origins | Validation origins | Purged |
|---:|---:|---:|---:|
| 2002 | 0 | 1 | 0 |
| 2006 | 43 | 76 | 0 |
| 2010 | 339 | 168 | 2 |
| 2015 | 1,326 | 241 | 8 |
| 2019 | 2,272 | 231 | 14 |
| 2022 | 2,836 | 250 | 3 |
| 2025 | 3,328 | 421 | 5 |

(Full 23-row table: `local_data/processed/fmd/cohort/fmd_calendar_year_folds.json`.)
Every year has a non-trivial validation count (unlike LSD's own schedule,
where folds 3-4 had near-zero Tier-A depth) — because FMD's primary
target is RISK, which 100% of target rows qualify for (`FMD_TARGET_PROTOCOL.md`
§4), not the sparse Tier-A direction population LSD's schedule was
built around. This independently supports expanding-window/walk-forward
as the primary FMD validation strategy, consistent with §1.

## 6. Locked test-set usage policy (frozen, non-negotiable)

Once `HELD_OUT_FROM_MODEL_FITTING` (541 origins — see §0/§3 for why this
is not 2,492, which is the corresponding EVENT count — `t0 >= 2026-01-01`)
is frozen, it must **never** be used for: feature/window selection,
ST-DBSCAN parameter tuning, spatial-domain threshold selection,
hyperparameter tuning, coefficient fitting, model-family selection,
imputation-parameter tuning, class-balancing decisions, or calibration
fitting. The same firewall functions LSD already relies on
(`assert_fit_development_only`, `assert_held_out_only`,
`assert_sri_lanka_transfer_case_study_only` —
`services/model_fitting_exposure.py`, unmodified) apply verbatim to FMD
origins, since role classification (not disease identity) is what they
gate on; `test_fmd05_study_protocol.py` proves a mixed-role list is
rejected in full for FMD data specifically. **Only FMD-08 may perform the
final locked evaluation.**

## 7. Trigger-source multiplicity (why event count != origin count)

Real distribution, `fmd_historical_forecast_origins.csv.trigger_source_count`
(4,322 origins, sum = 9,311 INCLUDED events):

| | Count |
|---|---:|
| Origins with exactly 1 trigger source | 2,769 |
| Origins with >1 trigger source | 1,553 |
| Maximum trigger-source count at one origin | 48 |

An origin's `trigger_source_count` is how many INCLUDED canonical events
share that exact `(country, t0)` bucket — i.e. were all confirmed FMD
events in the same country with the identical retrospective-proxy
availability date. A single origin with 48 trigger sources counts as
**ONE** row in every origin-level statistic in this document (fold
membership, role counts, target-support counts) — never 48. This is the
same, unmodified, one-origin-per-`(country, t0)` collapsing rule
`services/forecast_origin.py`'s own module docstring already documents
for LSD ("multiple sources becoming available on the same country-day
collapse into ONE origin... rather than creating statistically identical
duplicate country-level snapshots").

## 8. What this freeze does NOT do

- Does not select a spatial-domain radius, weather window, ST-DBSCAN
  parameter, feature set, or model-family winner — that is FMD-06/07,
  `FIT_DEVELOPMENT`-only.
- Does not compute or inspect any `HELD_OUT_FROM_MODEL_FITTING` or
  `SRI_LANKA_TRANSFER_CASE_STUDY` predictive performance — none exists.
- Does not build a final train/test feature matrix (that is downstream of
  the still-deferred full feature extraction, `FMD_STUDY_PROTOCOL.md`
  §7).
