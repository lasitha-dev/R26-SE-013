# FMD-05 Study Protocol — Frozen

This is the frozen FMD study-design decision: what later FMD-06/07/08
modelling work is allowed to predict, which historical events belong to
the modelling study, what information exists at prediction time, and how
train/validation/test separation prevents leakage. **No model is fit, no
ST-DBSCAN parameter is calibrated, no PISTES coefficient is estimated, and
no held-out/Sri-Lanka performance is inspected anywhere in FMD-05.**

Companion documents: `FMD_TARGET_PROTOCOL.md` (target/label semantics),
`FMD_SPLIT_PROTOCOL.md` (train/validation/test freeze),
`FMD_EVALUATION_PROTOCOL.md` (metrics, baselines, weather-window rule,
ST-DBSCAN role, control-sample decision), `FMD_FEATURE_ELIGIBILITY.csv`
(per-feature-family status), `FMD_EXPERIMENT_REGISTRY.json`
(pre-registered comparison matrix).

Machine-readable evidence backing every count in this document:
`local_data/processed/fmd/cohort/FMD_COHORT_MANIFEST.json` (+ the five
CSV/JSON artifacts alongside it), generated deterministically by
`data_processing/build_fmd_cohort.py` from the frozen FMD-03D canonical
corpus (`local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv`,
SHA-256 `11b4528d32fcb9f6f26cd537511b0d0fca531890a8af5d7480e94188d3d0114e`,
unchanged — see "FMD/LSD isolation" below).

## 1. Why this checkpoint exists (roadmap, unchanged from FMD-03D)

`FMD_DATASET_CARD.md`'s "Roadmap correction" section already froze this
order: FMD-04 (feature engineering, DONE) -> **FMD-05 (this checkpoint:
target, cohort, forecast-origin, control methodology if required,
validation-protocol freeze)** -> FMD-06 (FMD-specific calibration,
training data only) -> FMD-07 (candidate model development) -> FMD-08
(locked held-out evaluation). This order exists specifically to prevent
post-hoc split selection, test-set leakage, tuning against held-out data,
and unsupported scientific-parameter reuse from LSD.

## 2. What is reused from the shared/generic engineering, and what is FMD-specific

The repository already has a disease-parameterized forecast-origin /
forecast-target / model-fitting-exposure engine
(`services/forecast_origin.py`, `services/forecast_target.py`,
`services/historical_trigger.py`, `services/source_selector.py`,
`services/split_embargo.py`, `services/model_fitting_exposure.py`) built
for, and previously only exercised against, LSD's corpus. None of these
modules were modified for FMD-05 except one narrow, additive,
disease-agnostic correction (`services/historical_event_date.py` gained a
branch for the `FAO_EMPRESI_BIGQUERY_CSV` source system — previously
absent, so FMD records fell through to a generic MEDIUM-confidence
fallback instead of the HIGH-confidence treatment their own
100%-VALID `onset_date` field actually warrants; see
`FMD_TARGET_PROTOCOL.md` §2). **Reused unchanged (disease-agnostic
mechanics):** one-origin-per-`(country, t0)` outbreak-triggered
construction; the T0/window/dedup/model-candidate eligibility gates; the
`PURGED_7_DAY_HORIZON_POLICY`; the `FIT_DEVELOPMENT` /
`HELD_OUT_FROM_MODEL_FITTING` / `SRI_LANKA_TRANSFER_CASE_STUDY` role
taxonomy and its hard firewalls (`assert_fit_development_only` etc.);
calendar-year expanding-window fold construction. **FMD-specific
(frozen in FMD-05, independently derived from FMD's own data, never
copied from LSD):** the disease identifier (`"Foot and mouth disease"`),
the model-fitting cutoff date (`2026-01-01`, see `FMD_SPLIT_PROTOCOL.md`),
which country plays the `SRI_LANKA_TRANSFER_CASE_STUDY` role and why
(same mechanism, FMD-specific justification), and the study cohort
itself.

A new, narrow **bridge adapter**
(`data_processing/fmd_forecast_bridge.py`) lets the generic engine read
FMD's canonical schema, which differs from LSD's in two ways: FMD has no
`model_candidate` column (it has the stricter `modelling_eligible`
instead) and FMD-03D's `DISTINCT_AUTHORITATIVE_EVENT` dedup status is not
a member of the shared `schemas.DedupStatus` enum. Both gaps are closed
by a documented, one-way mapping applied only to the disposable import
used to exercise the generic pipeline — `schemas.py` and every LSD-facing
module are untouched (see the bridge module's own docstring for the
full justification and `test_fmd05_study_protocol.py` for the isolation
proof).

## 3. Research prediction task

**Primary question (FMD-05 freeze):** given an FMD forecast origin — a
country and a date `t0` at which one or more new, eligible, confirmed FMD
events became retrospectively known — what is the probability that at
least one further, distinct, eligible FMD event will be recorded in that
same country within `lead_days` in `[1, 7]` of `t0` (the D1-D7 primary
horizon)?

This is a **RISK** (occurrence) task. Direction (where) and speed (how
fast) are candidate secondary tasks the generic architecture already
supports at the target-row level, but FMD's own target-quality evidence
(§13 below, `FMD_TARGET_PROTOCOL.md` §4) shows they are **not currently
reachable** for this corpus — see readiness gates.

D+7 is PRIMARY. **D8-D14 is NOT frozen, NOT implemented, and remains an
exploratory roadmap concept only** (matching how LSD's own
`sri_lanka_case_study_interpretation.json` already describes D8-D14 for
that disease) — no FMD-05 artifact builds a D8-D14 target set, and none
of the counts in this document set include one. A future checkpoint may
propose a D8-D14 secondary target, but only as a new, explicitly
pre-registered decision, never silently inferred from this prompt
mentioning it.

## 4. Unit of analysis

**ONE MODEL ROW (primary risk task) = one forecast origin**, uniquely
identified by `forecast_origin_id = "ORIGIN:{country}:{t0}"`. This is the
existing generic architecture's own unit (already used, unmodified, for
LSD) — not a new invention for FMD. **An origin is a unique
`(country, t0)` bucket, not a unique event**: a single origin may be
triggered by more than one same-country/same-day canonical event (up to
48 in the real corpus, see `FMD_SPLIT_PROTOCOL.md` §7) and still counts
as exactly ONE model row. FMD-05R found and fixed a defect where
event-level tallies (9,311 INCLUDED events) had been mislabeled and
reported as if they were forecast-origin counts (the corpus has only
**4,322** unique origins) — see `FMD_SPLIT_PROTOCOL.md` §0 for the full
repair and `FMD_COHORT_MANIFEST.json`'s separate
`forecast_origin_role_counts` (origin-level) vs.
`included_source_event_role_counts` (event-level) fields.

The origin's label is derived from its associated `ForecastTarget` rows
(one row per `(origin, candidate-future-event)` pair, `target_id =
"{forecast_origin_id}::{target_event_id}"`) — see `FMD_TARGET_PROTOCOL.md`
§1/§3 for exactly how a binary risk label would be derived from those
rows (spatial-domain threshold intentionally deferred, never fit in
FMD-05/FMD-05R) and §3 for the frozen `SPATIAL_TARGET_REFERENCE_SOURCE_SET
= ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0` definition (FMD-05R) — i.e. once a
radius is eventually chosen (FMD-06+), distance is measured from a
target to every source ELIGIBLE AND ACTIVE at `t0` (the
`classify_target_primary_scope`/`EligibleSourcePoint` architecture
already frozen and reused unmodified from LSD), never from the origin's
own newly-arriving trigger source(s) alone.

This is **not** a spatial-grid-cell unit (no `SCIENTIFIC_GRID_PROTOCOL`
freeze exists for FMD; LSD's own grid work is a separate, later-stage
concept not reused here) and **not** an individual-outbreak-event unit
(an event contributes to an origin as a source, and separately may
contribute to zero or more OTHER origins' target sets — see pseudo-
replication note in `FMD_TARGET_PROTOCOL.md` §1). Different candidate
model families (risk vs. a future direction/speed task, if ever
unblocked) will need their OWN derived learning table built from the SAME
underlying `ForecastTarget` rows with a different filter — they are never
assumed to share one outcome column.

## 5. Study cohort

Source: the frozen FMD-03D canonical corpus, unmutated
(`fmd_canonical_outbreaks_conservative.csv`, 9,526 rows, SHA-256 above).

| Disposition | Count | Reason |
|---|---:|---|
| `INCLUDED` | 9,311 | `modelling_eligible = True` (Confirmed status, resolved identity, valid event date, valid coordinate) |
| `EXCLUDED_STATUS_NOT_CONFIRMED` | 215 | Suspected/Denied — never confirmed positive; `Denied` is explicitly NOT a supervised negative (see FMD-03's own `FMD_DATA_AUDIT.md` panel-defence note 9) |

Every one of the 9,526 rows receives exactly one disposition — nothing is
silently dropped (`FMD_COHORT_AUDIT.csv`, one row per canonical event;
`FMD_COHORT_MANIFEST.json.cohort_disposition_counts` sums to 9,526). No
other exclusion reason (`MISSING_EVENT_DATE`, `INVALID_COORDINATE`,
`EVENT_IDENTITY_UNRESOLVED`, `DUPLICATE_UNRESOLVED`,
`SOURCE_PROVENANCE_INCOMPLETE`) is observed in the real 2026-08 export —
the cohort-building code handles all of them (so a future re-export that
does trigger one of these is still correctly classified), but reports
what is actually measured, not what is theoretically possible.

**All 9,311 `INCLUDED` events become forecast-origin trigger sources** —
every eligible event's own `(country, effective_availability_date)`
bucket becomes (or joins) exactly one forecast origin, by construction of
`build_forecast_origin_ledger`. This yields **4,322 forecast origins
across 96 countries** (`FMD_COHORT_MANIFEST.json`). No `country_scope`
restriction was applied — every country in the corpus is IN the study
population (see §6); `country_scope`/per-country grouping remains a
surveillance/data-replay bookkeeping boundary, never a claim that FMD
transmission stops at a border (same documented limitation the generic
`get_eligible_sources` docstring already states for LSD).

Not every included event becomes a **target**: `2,844` origins have
`>= 1` D1-D7 target, `1,478` have zero (a record with no other eligible
event in the same country within the next 7 days). This is expected and
reported, not smoothed over.

## 6. Geographic study design

FMD is not scoped to Sri Lanka, unlike this repository's LSD track. The
FMD-04 dataset card already established the reason: Sri Lanka contributes
only 20 of 9,311 confirmed-eligible events globally — "far too small a
sample to independently fit and validate a complex spatial-temporal
model" (`FMD_DATA_AUDIT.md` panel-defence note 12). The frozen design is
therefore:

- **Model-development population**: all non-Sri-Lanka countries with
  `t0 < 2026-01-01` (`FIT_DEVELOPMENT`, **3,761 forecast origins** —
  91 countries contribute across the years each was active; see
  `FMD_SPLIT_PROTOCOL.md` §0/§3 for why this is 3,761 origins, not the
  6,799 INCLUDED events that trigger them).
- **Locked temporal test population**: all non-Sri-Lanka countries with
  `t0 >= 2026-01-01` (`HELD_OUT_FROM_MODEL_FITTING`, **541 forecast
  origins**, 19 countries — South Africa dominates; see
  `FMD_SPLIT_PROTOCOL.md` §2-§3 for the full origin-level breakdown and
  why this is 541 origins, not the 2,492 events that trigger them).
- **Sri Lanka role**: `SRI_LANKA_TRANSFER_CASE_STUDY` (20 origins, every
  Sri Lanka event, unconditionally, regardless of its own `t0` — same
  mechanism LSD already uses, FMD-specific justification: see
  `FMD_SPLIT_PROTOCOL.md` §3).
- **No claim of geographic transfer VALIDITY is made in FMD-05** — that
  is an empirical question for FMD-07/08 once a model exists. This
  checkpoint only freezes which role each origin gets and why, before any
  performance number exists to bias that choice.

This is a **global-development-with-Sri-Lanka-transfer-case-study**
design, structurally identical in shape to LSD's own frozen design
(`SPLIT_USAGE_FREEZE.md`) but independently justified from FMD's own
20-event Sri Lanka sample size and FMD's own (non-vector-borne)
transmission biology — never a copy of LSD's vector-borne/Thailand-
chronology justification.

## 7. What this protocol explicitly does NOT do

- Does not fit, tune, or calibrate any model, coefficient, or ST-DBSCAN
  parameter (`FMD_EVALUATION_PROTOCOL.md` §5 — that is FMD-06/07).
- Does not select a final local spatial-domain radius for the risk label
  (`FMD_TARGET_PROTOCOL.md` §3) — candidates only, deferred.
- Does not select a final weather-lookback window
  (`FMD_EVALUATION_PROTOCOL.md` §3) — rule frozen, winner deferred.
- Does not run full-corpus environmental/host feature extraction (still
  deferred from FMD-04, unblocked now that the cohort is frozen — a
  separate, future engineering task, not performed here).
- Does not inspect `HELD_OUT_FROM_MODEL_FITTING` or
  `SRI_LANKA_TRANSFER_CASE_STUDY` predictive performance — no
  risk/direction/speed model exists yet to have any.

See `FMD_SPLIT_PROTOCOL.md` §6 and `FMD_TARGET_PROTOCOL.md` §5 for the
full per-gate GO/NO-GO assessment.
