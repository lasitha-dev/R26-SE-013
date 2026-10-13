# PISTES Repository & Domain Design — Checkpoint 3

Domain model, storage abstraction, report→outbreak aggregation, and
temporal-mode source selection, built on top of Checkpoint 1-2.5's raw
parsing / deduplication / conservative model-candidate pipeline. No
SQLite-specific assumption leaks into scientific code; no GIS, ST-DBSCAN,
risk modeling, training, or FastAPI routes were touched.

## 1. Architecture extended (inspection findings)

Before writing anything, the actual repo was inspected:

- `backend/core/` and `backend/shared/` are empty scaffolding (`.gitkeep`
  only) — no existing convention to follow or break. This checkpoint does
  **not** populate them: doing so now would mean inventing cross-component
  conventions for `health_anomaly`/`risk_forecasting`/`smart_diagnostics`,
  none of which exist yet — premature abstraction. Everything here lives
  inside `components/geospatial_tracking/`, exactly like Checkpoint 1-2.5.
  If a second component needs its own repository later, promoting the
  `OutbreakRepository`-style Protocol pattern into `backend/core/` at that
  point is a natural, low-risk move — deferred, not forgotten.
- `backend/main.py` is a two-line FastAPI stub (`GET /` → `{"status":
  "ok"}`). Not touched — no routes were added this checkpoint.
- `backend/requirements.txt` already lists `motor` (async MongoDB driver)
  from the original scaffold, unused until now and still unused — nothing
  here constructs a Mongo client or connection.
- Checkpoint 1-2.5's `schemas.py`, `data_processing/*`, `DATA_AUDIT.md`,
  `DATA_PROVENANCE.md`, and all existing tests are extended, not replaced.
  The only change to that existing code is additive: a `disease` field was
  added to `RawOutbreakRecord`/`NormalizedOutbreakRecord` (populated from
  the CSV's `Disease` column and the WAHIS title line's middle segment,
  e.g. `"Sri Lanka - Lumpy skin disease virus (Inf. with) - Follow-up
  report 1"` → disease = `"Lumpy skin disease virus (Inf. with)"`) because
  `get_eligible_sources` genuinely needs a disease filter and no such
  field existed. Verified against all 4 real WAHIS PDFs before
  implementing; all 90+ pre-existing tests still pass unmodified.

New packages added under `components/geospatial_tracking/`:

```
config.py                    # UNFROZEN_DEVELOPMENT_PARAMETER constants, DB path
domain/
    enums.py                 # ReportStatus, RecordDomain
    models.py                 # AnimalReport, OutbreakEpisode, HistoricalOutbreakRecord, PredictionRun
repositories/
    base.py                   # OutbreakRepository Protocol
    sqlite_repository.py      # SQLiteOutbreakRepository (dev persistence)
services/
    dates.py                   # shared flexible date parser (ISO + WAHIS "/" style)
    disease.py                 # normalize_disease (mirrors data_processing/species.py)
    aggregation.py             # report -> outbreak episode aggregation
    historical_import.py       # conservative CSV -> HistoricalOutbreakRecord rows
    source_selector.py         # get_eligible_sources — the eligibility engine
    seed_dev_db.py              # reproducible local dev-DB seeding entry point
data/local/                   # gitignored — pistes_dev.db lives here
```

## 2. Two data domains, explicit and never mixed

`domain/enums.RecordDomain`:

- `LIVE_OPERATIONAL_RECORD` — `AnimalReport` and `OutbreakEpisode`. A
  future centralized system's actual workflow timestamps
  (`submitted_at`, `notification_date`, `confirmation_date`,
  `accepted_at`). `operational_availability_date`/`_quality` on an
  `OutbreakEpisode` CAN legitimately reach `ACTUAL` — derived only from
  `accepted_at` (see §4).
- `HISTORICAL_RESEARCH_RECORD` — `HistoricalOutbreakRecord`, imported from
  Checkpoint 2.5's conservative canonical CSV. Every record's
  `operational_availability_quality` is `UNKNOWN` in the current corpus,
  because neither WAHIS nor FAO EMPRES-i records a real "system knew by"
  timestamp (unchanged fact from Checkpoint 1). `proxy_availability_date`
  carries the RETROSPECTIVE_PROXY-mode substitute already built in
  Checkpoint 1-2, never upgradeable to `ACTUAL` (`__post_init__` guard on
  both `RawOutbreakRecord` and `HistoricalOutbreakRecord`).

Every record carries its own `record_domain` field, set explicitly at
construction — never inferred, never defaulted from context. A
retrospective WAHIS/EMPRES record can never silently present itself as a
live report.

## 3. Repository abstraction

`repositories/base.py` defines `OutbreakRepository` as a `typing.Protocol`
— structural typing, not inheritance. Storage-only: disease/country
filters are plain data filters, never a scientific policy (see §7).
Eligibility/temporal-mode/model-candidate logic lives entirely in
`services/source_selector.py`, which depends on this Protocol, never on
`sqlite3` directly.

```
OutbreakRepository (Protocol)
        |
        +-- SQLiteOutbreakRepository      NOW   (repositories/sqlite_repository.py)
        |
        +-- MongoOutbreakRepository       LATER (not implemented, not connected)
```

`SQLiteOutbreakRepository` is development persistence only. Local file:
`components/geospatial_tracking/data/local/pistes_dev.db`, gitignored
(`.gitignore`: both the specific directory and a general `*.db`/
`*.db-journal` pattern). `init_schema()` is a single idempotent
`CREATE TABLE IF NOT EXISTS` script, safe to call on every process start —
proven deterministic in `test_sqlite_repository.py` (REPO-01).

## 4. Report → outbreak aggregation (`services/aggregation.py`)

Conservative, fully documented, NOT epidemiologically-tuned:

1. Group reports **only** by `(farm_id, disease)`. Same GPS coordinate
   alone never merges reports (mirrors `data_processing/dedup.py`'s
   equivalent historical-domain rule).
2. A report with no `farm_id` becomes its own singleton episode — a
   fuzzy, farm-less matching path is deliberately not implemented (that
   would reopen exactly the "GPS alone merges everything" risk this rule
   exists to close).
3. Within one `(farm_id, disease)` group, reports split into separate
   episodes wherever the gap between consecutive biological dates exceeds
   `episode_gap_days` — a required, explicit parameter (no default in the
   function signature), labeled `UNFROZEN_DEVELOPMENT_PARAMETER` in
   `config.py`. Never presented as a biological incubation/recovery
   constant.
4. `affected_animals` = distinct `animal_id` count among reports that have
   one, **plus** one for each report with no `animal_id` (can't be
   deduplicated, so it must count on its own rather than silently
   vanishing). Repeated submissions of the same `animal_id` never
   increase the count (REPORT-01/02).
5. Episode `status` rolls up to the most-progressed member status
   (`REJECTED < SUBMITTED < ACCEPTED < CONFIRMED`).
6. `operational_availability_date`/`_quality` is derived **only** from the
   earliest `accepted_at` among ACCEPTED/CONFIRMED member reports — never
   from `onset_date` (biological) or `created_at` (storage) — see §6.
   With no such timestamp, it stays `UNKNOWN`, exactly like every
   historical record today.

## 5. Temporal mode

Reuses `schemas.ValidationMode` (already defined in Checkpoint 1 —
`STRICT_OPERATIONAL` / `RETROSPECTIVE_PROXY`) rather than inventing a
parallel enum.

- **STRICT_OPERATIONAL**: a source is eligible only when its
  `operational_availability_quality == ACTUAL` and a non-null date exists.
  For every historical record in the current corpus this is `(None,
  UNKNOWN)` by construction (`HistoricalOutbreakRecord.effective_availability`)
  — they never silently pass. A live `OutbreakEpisode` CAN satisfy this
  once it has a real `accepted_at`-derived date.
- **RETROSPECTIVE_PROXY**: research-only. May use `proxy_availability_date`
  when its `proxy_availability_quality` is a real, non-UNKNOWN label
  (`EVENT_DATE_PROXY`/`OBSERVATION_DATE_PROXY`/etc.). Every
  `EligibleSource` explicitly carries `availability_quality`, and every
  `EligibleSourceResult` carries `temporal_mode` — a caller can never
  mistake a proxy result for real-time operational forecasting (DATE-03).

## 6. Biological vs. operational vs. storage time — kept separate end to end

- Biological: `AnimalReport.onset_date`, `HistoricalOutbreakRecord.
  {event_start_date, outbreak_start_date, onset_date}`.
- Operational: `AnimalReport.{submitted_at, notification_date,
  confirmation_date, accepted_at}`, `OutbreakEpisode.
  operational_availability_date`, `HistoricalOutbreakRecord.
  operational_availability_date`/`proxy_availability_date`.
- Storage: `AnimalReport.created_at`, `OutbreakEpisode.created_at`,
  `HistoricalOutbreakRecord.imported_at`. **Never** read as either of the
  above by any service in this checkpoint (DATE-01).

## 7. Eligible active-source selector (`services/source_selector.py`)

`get_eligible_sources(repo, *, disease, t0, active_window_days,
temporal_mode, country_scope=None) -> EligibleSourceResult`.

Deliberately called the **eligible active-source set**, never "currently
infectious animals/farms" — infection duration is not established by this
selector (§12 of the master prompt).

Rules, applied uniformly to both domains via the same repository queries:

1. **Model-candidate hard gate** (historical only): `model_candidate`
   must be `True`, checked directly and unconditionally — never through a
   quality proxy. `dedup_status` must additionally be one of
   `SINGLETON`/`AUTO_MERGED_HIGH`/`MANUALLY_ACCEPTED` (a second, explicit
   gate — `REVIEW_MEDIUM`/`REVIEW_LOW` are excluded even if some future
   bug ever let `model_candidate` drift out of sync). DQS is never read
   anywhere in this module — structurally proven in
   `test_source_11_high_dqs_never_consulted`.
2. **Disease match**: normalized comparison (`services/disease.py`, same
   pattern as `data_processing/species.py`) so `"Lumpy skin disease"` and
   `"Lumpy skin disease virus (Inf. with)"` are recognized as the same
   disease without literally rewriting either source field.
3. **Valid coordinates**: missing latitude/longitude excludes a record
   from being an active spatial source, full stop. An `UNKNOWN` **GPS
   precision label** with otherwise-valid coordinates does **not**
   exclude a record — precision and validity are different questions
   (§17; `test_source_17_...`).
4. **Live workflow-status gate** (live only): `status` must be
   `ACCEPTED`/`CONFIRMED` — `SUBMITTED`/`REJECTED` never qualify. (No
   equivalent workflow-status field exists on historical records; they
   are treated as already-confirmed by virtue of being sourced from
   WAHIS/EMPRES confirmed-diagnosis reports — see Checkpoint 1
   `DATA_AUDIT.md` §2, "all rows `Diagnosis Status = Confirmed`".)
5. **T0 invariants**, both bounds inclusive (a documented, consistent
   convention, not a scientific claim):
   `t0 - active_window_days <= effective_availability_date <= t0`.
   A source strictly after `t0` can never appear (SOURCE-03); a source
   exactly at `t0` or exactly at the window's start boundary is included
   (SOURCE-04/06).

`active_window_days` has **no default** in the function signature — every
caller must pass it explicitly. `config.ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT`
exists only as a development/smoke-test convenience value, explicitly
labeled `UNFROZEN_DEVELOPMENT_PARAMETER`, and is never read implicitly by
the selector itself.

## 8. Historical import — where the model-candidate gate actually lives

`services/historical_import.import_conservative_csv` imports the **full**
conservative corpus — including `REVIEW_MEDIUM`/`REVIEW_LOW`/
`model_candidate=False` rows — into `historical_outbreak_records`.
Nothing is filtered or dropped at import time, and the source CSV is
never modified.

This is intentional, not an oversight: the model-candidate/dedup-status
hard gate is enforced entirely at **query time** by
`get_eligible_sources` (§7.1). Importing only the eligible subset would
make that gate untestable (SOURCE-09/10/11 need ineligible rows to
actually exist in storage to prove the selector excludes them) and would
throw away exactly the audit trail Checkpoint 2.5 was built to preserve.
"Only model_candidate=True records may enter the scientific historical
candidate pool" (master-prompt §7) is satisfied at the pool's actual
boundary — the selector's output — not by pre-filtering storage.

## 9. No country assumption (§8)

`OutbreakRepository.list_historical_records`/`list_outbreak_episodes`
accept an optional `country` filter — a plain string comparison. Neither
the repository nor `source_selector.py` contains a single literal
reference to `"Thailand"` or `"Sri Lanka"` anywhere in the eligibility
logic (`test_source_12_country_filter_works_but_is_not_hardcoded` asserts
this by inspecting the module source directly). Country/development/
evaluation partitioning is explicitly deferred to the next
historical-episode/split phase.

## 10. PredictionRun (§15)

`PredictionRun` is storage-only scaffolding: `prediction_id`,
`forecast_origin_t0`, `temporal_mode`, `primary_source_id`,
`active_source_ids`, `model_version`, `config_hash`, `created_at`.
`model_version`/`config_hash` are nullable and are never fabricated —
no model exists to version yet. No prediction/risk logic reads or writes
this table beyond the round-trip persistence test (PRED-01).

## 11. Known limitations / open items

- Live ingestion has no HTTP surface yet (no FastAPI routes were added,
  by design this checkpoint) — `AnimalReport`/`OutbreakEpisode` rows are
  only ever inserted directly through the repository in tests/smoke runs,
  simulating what a future ingestion endpoint would do.
- The farm-less report matching path is unimplemented on purpose (§4.2) —
  a real live pipeline should require a farm/herd identifier; revisit only
  if that assumption turns out to be false operationally.
- Live episodes have no dedup/model_candidate concept at all — by
  construction there is no cross-source ambiguity for a single centralized
  live system. If a live system ever ingests from multiple upstream
  sources, this assumption needs revisiting before it stays valid.
- `disease` on `HistoricalOutbreakRecord` still carries the two sources'
  raw, un-harmonized spelling (`normalize_disease` only affects matching,
  never the stored/displayed value) — deliberate, consistent with how
  `species` is handled.
- `EligibleSource.status` currently reuses `dedup_status` for historical
  records and `ReportStatus` for live ones — two different vocabularies
  in the same field. Acceptable for a checkpoint that only reports IDs and
  dates back to the caller; would need a cleaner status projection before
  any UI consumes this directly.
- No historical episode construction, GIS/environment features,
  ST-DBSCAN, risk modeling, model training, direction/speed estimation,
  FastAPI production routes, or frontend work — none of it started, per
  the Checkpoint 3 scope boundary.

---

## 12. Checkpoint 3.5 — date-purity and animal-count-uncertainty correction

Checkpoint 3's aggregation architecture (§4 above) is preserved
unchanged in structure — same grouping-by-`(farm_id, disease)` rule, same
"same GPS alone never merges" rule, same repository/service boundary.
Two real bugs in `services/aggregation.py`'s date/count handling were
found and fixed; nothing else in Checkpoint 3 was rewritten.

### The bug

`_best_report_date` (Checkpoint 3) tried each of `onset_date`,
`submitted_at`, `notification_date`, `confirmation_date`, `accepted_at`
in order and returned whichever parsed first, then that ONE value was
used for two unrelated purposes at once: (a) deciding which reports
cluster into an episode, and (b) becoming `OutbreakEpisode.onset_date`.
Purpose (a) is a legitimate operational need; purpose (b) is a
scientific-integrity bug — a workflow timestamp is not evidence of when
an animal actually showed symptoms, and Checkpoint 3's own tests never
caught it only because every test that checked `onset_date` happened to
also supply a real `onset_date` on every report (so the bug's fallback
path was never exercised by an assertion, even though the code path
existed and was reachable — e.g. any live report submitted without a
documented symptom-onset date, which is entirely plausible operationally,
would have silently gotten its `submitted_at` timestamp mislabeled as
biological onset).

### The fix — four separated concepts

`OutbreakEpisode` now carries four independent groups of fields (see the
class docstring in `domain/models.py` for the authoritative version):

1. **Biological onset** — `onset_date`. Populated ONLY from
   `AnimalReport.onset_date` values actually present in the episode's
   reports (earliest one, if any). `None` otherwise. Nothing else ever
   writes to this field.
2. **Episode grouping date** — `episode_grouping_date` /
   `episode_grouping_date_quality` (`domain.enums.GroupingDateQuality`:
   `BIOLOGICAL_DATE` / `OPERATIONAL_PROXY` / `UNKNOWN`). The value
   actually used to decide clustering, with an explicit, documented
   fallback hierarchy per report: `onset_date` (BIOLOGICAL_DATE) →
   `submitted_at` → `notification_date` → `confirmation_date` →
   `accepted_at` (all four OPERATIONAL_PROXY) → none (UNKNOWN). An
   OPERATIONAL_PROXY date is real evidence for *clustering* purposes but
   is never presented as biological time and never copied into
   `onset_date`.
3. **Operational availability** — unchanged in spirit from Checkpoint 3,
   tightened to an explicit two-step hierarchy (never a bare
   `submitted_at`, `onset_date`, or `created_at`):
   a. earliest `accepted_at` among ACCEPTED/CONFIRMED reports → `ACTUAL`;
   b. only if (a) found nothing, earliest `confirmation_date` among
      CONFIRMED reports → `ACTUAL`;
   c. neither exists → `None` / `UNKNOWN`.
4. **Animal-count uncertainty** — `affected_animals` (now nullable) /
   `affected_animals_quality` (`domain.enums.AnimalCountQuality`: `EXACT`
   / `LOWER_BOUND` / `UNKNOWN`) / `unidentified_report_count`. Checkpoint
   3's rule ("distinct animal_id count, plus one per unidentified report")
   could overstate the true count — two unidentified reports might
   describe the same physical animal, and there was no way to tell.
   Replaced with:
   - **CASE A** (every report has `animal_id`): `affected_animals` =
     distinct `animal_id` count, quality `EXACT`.
   - **CASE B** (some have, some don't): `affected_animals` = distinct
     KNOWN `animal_id` count (a genuine lower bound — never assumed to be
     the true count), quality `LOWER_BOUND`, `unidentified_report_count`
     = the rest.
   - **CASE C** (none have `animal_id`): `affected_animals = None`,
     quality `UNKNOWN`, `unidentified_report_count` = all of them.
   **A `LOWER_BOUND`/`UNKNOWN` count must never be treated as an exact
   source-pressure/case-count value by any later modeling work without an
   explicitly developed rule for doing so** — this is a structural
   property (the field is genuinely nullable and carries its own quality
   label) as well as a documented policy.

### Reports with no reliable grouping date (master-prompt §4)

Chosen behavior: **option B** (explicit review flag), layered with a
narrow identity-based exception. Same-`(farm_id, disease)` reports are
never silently merged by adjacency alone when no date exists for one of
them:

- A dateless report is attached to an already date-clustered episode
  **only** when it shares a known `animal_id` with a report already in
  that cluster — the same physical animal is about as strong an identity
  signal as exists, regardless of missing dates. This attachment does
  **not** set the review flag (the identity evidence is strong enough).
- Anything left over (no date, no identity link to a dated cluster) is
  grouped only by shared `animal_id` among itself, or stands alone if it
  has no `animal_id` either. **Every episode assembled this way sets
  `aggregation_review_required = True`** — its placement in the farm's
  outbreak timeline relative to other episodes is unconfirmed and needs a
  human's eyes. See `services/aggregation._cluster_group`.
- Farm-less reports (no `farm_id` at all) are unaffected by this rule —
  they are a distinct, already-documented Checkpoint 3 policy (never
  group without a farm/herd identifier) and are never review-flagged for
  that reason alone.

### Duplicate report_id safety

`aggregate_reports_into_episodes` now dedupes its input by `report_id`
before any grouping/counting happens (`_dedupe_by_report_id`, keeps the
first occurrence). Combined with the repository's pre-existing `INSERT OR
REPLACE` upsert semantics on `report_id` (Checkpoint 3), the same report
can never contribute twice to an animal count, a grouping decision, or an
outbreak episode — at either the service layer or the storage layer.

### Parameter validation

Both `episode_gap_days` (`services/aggregation.py`) and
`active_window_days` (`services/source_selector.py`) now reject negative
values with a `ValueError`. `0` is accepted and is deterministic in both:
`episode_gap_days=0` means reports must share the exact grouping date to
cluster (any 1+ day gap starts a new episode); `active_window_days=0`
means only a source whose effective availability date is exactly `t0` is
eligible ("same-day-only").

### SQLite schema changes

`outbreak_episodes` gained: `affected_animals` (now nullable),
`affected_animals_quality` (`TEXT NOT NULL`), `unidentified_report_count`
(`INTEGER NOT NULL DEFAULT 0`), `episode_grouping_date` (`TEXT`),
`episode_grouping_date_quality` (`TEXT NOT NULL`),
`aggregation_review_required` (`INTEGER NOT NULL DEFAULT 0`, bool). No
other table changed. Since `CREATE TABLE IF NOT EXISTS` cannot alter an
existing table's columns, the (gitignored, development-only) dev DB file
was deleted and recreated from scratch — no raw source file was touched,
and the historical corpus was re-imported unchanged from
`canonical_outbreaks_conservative.csv` (still 2587 rows).

### Regression confirmation

The exact Checkpoint 3 smoke query (Thailand, `t0=2021-05-20`,
`active_window_days=14`) was re-run after this correction:
**RETROSPECTIVE_PROXY still returns 109 sources; STRICT_OPERATIONAL still
returns 0.** Unsurprising but confirmed rather than assumed — this
checkpoint only touched the live-domain aggregation logic and the
`outbreak_episodes` table; the historical import path and
`historical_outbreak_records` table were not modified at all.

---

## 13. Checkpoint 4 — historical replay layer (chronology, forecast origins, D1-D7 targets)

Builds the FOUNDATION for historical replay and future train/validation
logic on top of §1-12 unchanged. No model, GIS, ST-DBSCAN, or frozen split
was built — see `SPLIT_PROTOCOL_DRAFT.md`, `HISTORICAL_CHRONOLOGY_AUDIT.md`,
`DATA_EXPOSURE_AUDIT.md`, and `DATA_AUDIT.md` §42-55 for the full
analysis and real-corpus counts; this section is the architecture
reference only.

### Two pre-flight fixes (Part 0)

- **`services/disease.py`** gained a small abbreviation-expansion table
  (`"lsd" -> "lumpy skin disease"`, `"fmd" -> "foot and mouth disease"`,
  checked only against the WHOLE normalized string so it can't
  accidentally expand part of an unrelated name). `services/aggregation.py`'s
  report-grouping KEY now uses `normalize_disease(r.disease)` instead of
  the raw string, while `OutbreakEpisode.disease` still stores one
  cluster's own real raw text (never the normalized key) — see that
  module's updated docstring.
- **`domain.enums.RecordDomainScope`** (`HISTORICAL_ONLY` / `LIVE_ONLY` /
  `BOTH`) is a new required-by-convention parameter on
  `get_eligible_sources` (`domain_scope`, defaulting to `BOTH` for
  Checkpoint 3/3.5 backward compatibility). Every call inside
  `services/forecast_origin.py` (historical replay) passes
  `HISTORICAL_ONLY` explicitly — checked structurally by a test that
  inspects that module's source for the literal string, not just by
  convention.

### Shared constant consolidation

`schemas.DEDUP_RESOLVED_STATUSES` (`{SINGLETON, AUTO_MERGED_HIGH,
MANUALLY_ACCEPTED}`) replaces three previously-duplicated local copies of
the same set in `source_selector.py`, `target_quality.py`, and (via
import) `forecast_target.py` — one definition, used everywhere a
"is this historical record's dedup status resolved enough to use
scientifically" question is asked.

### Canonical spatial independence (`services/canonical_spatial.py`)

Recomputes "is this coordinate unique?" over CANONICAL (post-dedup)
outbreak identities — i.e. over `canonical_outbreaks_conservative.csv`
rows, where an `AUTO_MERGED_HIGH` group has already collapsed to one row
with one coordinate — rather than Checkpoint 2's raw pre-dedup records,
where the same real outbreak's multiple source rows (CSV + WAHIS) could
make it look spatially non-independent against itself. The Checkpoint 2
raw-level `spatial_independence` column is left completely untouched;
this is a new, separate column
(`canonical_spatial_independence`/`shared_coordinate_group_id`/
`shared_coordinate_count`/`reason`), written to
`local_data/manifests/canonical_spatial_independence.csv`.

### Historical event date vs. source availability (`services/historical_event_date.py`)

A THIRD date concept, distinct from both the biological-onset/operational-
availability split already established for the live domain (Checkpoint
3.5) and from `proxy_availability_date` (a source-availability
substitute, not a target-occurrence claim): `historical_event_date`
answers "when did the outbreak actually happen, for building a future
target," derived per source system (WAHIS: `outbreak_start_date` then
`event_start_date`; CSV: `onset_date`), recovering the source system from
the stable `source_record_id` prefix rather than a stored field. Never
`report_date`, never `proxy_availability_date` "because it's convenient"
— even though in this corpus those often hold the same literal value as
the correct source field, using the wrong *concept* would blur exactly
the distinction this module exists to keep clear.

### Target quality tiers (`services/target_quality.py`)

`RISK_TARGET_ELIGIBLE` / `DIRECTION_TARGET_TIER_A`/`_B` /
`SPEED_TARGET_TIER_A`/`_B` — not one blanket flag. Tier A requires EXACT
GPS + canonical spatial independence + HIGH-quality event date, on top of
the risk-eligibility gate (model_candidate, dedup resolved, valid
coordinates, usable event date). Speed tiers are currently defined
identically to direction tiers — documented as provisional, not
fabricated as a distinct criterion without evidence to support one yet.

### Forecast-origin ledger and source snapshot (`services/forecast_origin.py`)

One origin per unique `(country, t0)` where `t0` is a date at least one
eligible historical record's own RETROSPECTIVE_PROXY availability date
lands on (never an arbitrary random t0 — PISTES is outbreak-triggered,
master-prompt Part 6). Discovery reuses the exact same, already-tested
`get_eligible_sources` function with a deliberately far-future `t0` and a
deliberately enormous window (chosen to comfortably reach back past any
real historical date — an earlier, too-small attempt at this window
undercounted and was caught before the real-data run, see
`DATA_AUDIT.md` §49-adjacent finding in `build_historical_replay.py`'s
history) rather than duplicating eligibility logic. The real per-origin
source snapshot always uses the real origin `t0` and the real, explicit
`active_window_days` — never the wide discovery window — so the T0
invariants are enforced by the same code path already proven in
Checkpoint 3.

### D1-D7 target construction + pseudo-replication safety (`services/forecast_target.py`)

A target is a distinct historical record with `1 <= lead_days <= 7`
relative to an origin's `t0` (`lead_days = historical_event_date - t0`),
passing the same model-candidate/dedup-resolved gate as a source, and
never a record already in that origin's own source snapshot.
`target_event_id` is always the record's own `source_record_id` — stable
across every origin that legitimately includes it as a target, so later
statistics can aggregate at the unique-target-event level rather than
over-counting a single real future outbreak that was "seen coming" from
several earlier origins (repeated forecasting of one event, not several
independent biological events — master-prompt Part 9). No
`true_parent_source_id`/causal-parent inference exists anywhere in this
checkpoint (master-prompt Part 10, deliberately not built).

### Split-boundary embargo rule (`services/split_embargo.py`)

The one piece of split-safety logic built this checkpoint (no actual
train/test assignment yet — that requires a frozen split decision, not
made here). Classifies each origin as `BEFORE_BOUNDARY` /
`AT_OR_AFTER_BOUNDARY` relative to a candidate split boundary, and flags
`BEFORE_BOUNDARY` origins whose D1-D7 target window reaches or crosses the
boundary (a horizon-boundary leak). Identifies leaking origins only —
does not choose which of three documented exclusion strategies
(`SPLIT_PROTOCOL_DRAFT.md` Part 14) to apply.

### Dataset freeze manifest (`services/dataset_freeze.py`)

Reproducibility metadata: raw input file hashes, conservative-dataset
hash, model-candidate-manifest hash, parser/dedup-policy/episode-builder
version strings, generation timestamp, and a git commit marker that
**never fabricates a clean hash for an uncommitted or dirty tree** — an
untracked repo returns `"NO_COMMIT_AVAILABLE"`, a dirty tree appends
`"-DIRTY_WORKING_TREE"` to the real commit hash rather than presenting it
as if the working tree matched that commit exactly.

### Orchestrator (`services/build_historical_replay.py`)

Ties the above together against the real local corpus, mirroring
`data_processing/build_canonical.py`'s `run()`/`main()` shape — never run
in CI (same convention as every prior local-data script in this
component). Real-corpus counts from the actual run are in `DATA_AUDIT.md`
§42-51 and `HISTORICAL_CHRONOLOGY_AUDIT.md`, not repeated here.

### Known limitations added this checkpoint

- Speed and direction tiers are currently identical — see
  `services/target_quality.py`.
- Tier-A direction/speed depth is almost entirely Thailand-only (GPS
  precision, not tier-definition bias — `HISTORICAL_CHRONOLOGY_AUDIT.md`
  §6). Any cross-country Tier-A claim needs this addressed first.
- The horizon-boundary embargo rule identifies leaks but does not
  implement an exclusion strategy.
- No split boundary or walk-forward fold scheme is frozen.
- `active_window_days=14` used for the real-data run remains an
  `UNFROZEN_DEVELOPMENT_PARAMETER`.

---

## 14. Checkpoint 4.5 — coordinate-evidence correction, replay hardening, validation freeze

Corrects three Checkpoint 4 items and freezes the validation strategy
those corrections made possible to freeze responsibly. Full rationale and
real-corpus counts: `VALIDATION_PROTOCOL.md` (new, primary deliverable),
`DATA_AUDIT.md` §56-64.

### Coordinate-collision status replaces "spatial independence" (`services/coordinate_collision.py`)

Checkpoint 4's `canonical_spatial_independence` boolean conflated
"coordinate is unique" with "outbreak is epidemiologically independent" —
never actually established, and it collapsed two different evidentiary
situations (a resolved candidate colliding with another RESOLVED outbreak
vs. colliding only with an UNRESOLVED `REVIEW_LOW`/`REVIEW_MEDIUM`
candidate) into one bucket. `coordinate_collision_status` is now a
five-way categorical (`UNIQUE_AMONG_RESOLVED` / `SHARED_WITH_RESOLVED` /
`SHARED_WITH_UNRESOLVED` / `SHARED_WITH_BOTH` / `MISSING_COORDINATE`),
computed by comparing each canonical row against every OTHER row split by
whether that other row is itself dedup-resolved. `services/canonical_spatial.py`
is unmodified and still runs (its output stays on disk for provenance —
master-prompt Part 15, "do not silently overwrite methodological
history") but is superseded for scientific use.

### Target tiers report two sensitivity variants, never one blended choice (`services/target_quality.py`)

`direction_target_tier_a_strict` (excludes ANY coordinate collision, even
an unresolved one) and `direction_target_tier_a_resolved_only` (excludes
only collisions with resolved candidates) are both always computed and
reported — the choice between them is never made in code, and never will
be based on model performance (`VALIDATION_PROTOCOL.md` §4). Speed tiers
share the direction tiers' criteria (still no distinct evidence to
justify a different rule) but every row carries
`speed_eligibility_status = "SPEED_ELIGIBILITY_PENDING_GEOMETRY"` so a
speed count is never presentable as a validated sample without that label.

### Far-future discovery hack removed (`services/historical_trigger.py`)

Checkpoint 4 discovered forecast-origin trigger candidates by calling
`get_eligible_sources` with a synthetic `t0="2999-12-31"` and an
initially-too-small "huge window" (a real bug, caught before the
Checkpoint 4 real-data run but still a sign the trick was fragile).
`list_historical_trigger_candidates` replaces it: a direct enumeration of
eligible historical records (model_candidate, dedup-resolved, disease
match, valid coordinates — mirroring but not importing
`source_selector._historical_eligible`'s non-temporal gates) with their
own real RETROSPECTIVE_PROXY effective-availability dates. No synthetic
date or window exists anywhere in this module or in
`forecast_origin.py` anymore. Confirmed byte-identical forecast-origin
and target counts against the real corpus after the swap (813 origins,
569 with targets, 1089 unique target events — all unchanged).

### Domain scope is now required, not defaulted (`services/source_selector.py`)

`get_eligible_sources`'s `domain_scope` parameter lost its `BOTH`
default entirely — every caller (all of `services/`, all tests) must
state `HISTORICAL_ONLY`/`LIVE_ONLY`/`BOTH` explicitly; omission raises
`TypeError`. Prevents a future caller from accidentally mixing historical
and live domains through a simple parameter omission, which the
Checkpoint 4 default structurally permitted.

### `country_scope` is documented as a replay boundary, not a biological one

Added directly to `get_eligible_sources`'s docstring: `country_scope`
restricts which stored records are queried because that is how this
corpus happens to be organized administratively — it is never a claim
that disease transmission stops at a national border, and no cross-border
epidemiological modeling exists anywhere in this component.

### Frozen validation strategy (`services/split_embargo.py`, `services/walk_forward.py`)

`PURGED_7_DAY_HORIZON_POLICY` is now the frozen name for the Checkpoint 4
embargo rule (logic unchanged — `t0 < B and t0+H >= B` purges an
origin from the earlier partition entirely, never clipped-and-kept).
`assess_validation_block` adds the finite-block completeness check (a
validation origin needs `t0 >= B and t0+H <= E` for a complete D1-D7
evaluation inside a finite block `[B, E]`, unless `E` is `None` for an
intentionally open-ended final block). `services/walk_forward.py`
(new) proposes chronology-only, quantile-based candidate fold boundaries
and builds per-fold training/validation counts (applying the purge policy
automatically), plus a Thailand-only variant specifically because the
global schedule concentrates almost all direction Tier-A depth in one
fold (`VALIDATION_PROTOCOL.md` §5 has the real numbers). **Primary
validation strategy (walk-forward) and the purge policy are now frozen**
— see `VALIDATION_PROTOCOL.md` §1-2. The exact split boundary date(s) and
which candidate fold schedule to actually use remain open.

### Known limitations added this checkpoint

- Which candidate fold schedule (global, Thailand-only, or a future
  nested variant) is "the" one used is not decided.
- Speed remains `SPEED_ELIGIBILITY_PENDING_GEOMETRY` throughout — no
  geometry work has started.
- `services/canonical_spatial.py` and `target_quality_report.csv`'s old
  schema are kept for provenance but are stale — a future checkpoint
  should decide when (if ever) to stop generating them.

## 15. Checkpoint 5 — real GIS/environmental data foundation (`services/geospatial/`)

A new, independent package alongside the outbreak-replay services above
— it does not read from or write to `historical_outbreak_records`,
`canonical_spatial.py`, or any forecast-origin/target service. Full
per-source provenance lives in `GIS_DATA_SOURCES.md`; this section
covers architecture and interfaces only.

```
services/geospatial/
  crs.py               AOI-aware analysis CRS (UTM zone/hemisphere from centroid — never one hardcoded EPSG per country)
  distance.py           Geodesic distance/bearing (pyproj.Geod, WGS84) — never raw lat/lon degrees treated as km
  grid.py                Smoke-test computational grid generator (resolution != prediction accuracy, GRID-03)
  raster.py               Shared AOI bbox + download/cache helpers (all real downloads under local_data/gis/, gitignored)
  source_geometry.py       geometry_by_source[source_id] = {distance_km, t_hat_east, t_hat_north} for EVERY eligible source per grid cell, not just nearest
  source_registry.py        Machine-readable registry, mirrored to local_data/manifests/gis_source_registry.json
  feature_result.py          FeatureResult contract: REAL/MISSING/BLOCKED/DEMO, structurally enforced (non-REAL cannot carry a value)
  temporal_leakage.py         Standalone leakage guards (WorldCover year mismatch, GLW-as-exact-truth, future-reanalysis leak)
  landcover/esa_worldcover.py  Real ESA WorldCover adapter (windowed vsicurl reads, v100/2020 vs v200/2021 never mixed)
  host_density/fao_glw.py       Real FAO GLW4 adapter (cattle/buffalo, reference year 2015 — corrected from an initial 2020 assumption)
  weather/era5.py                 Real ERA5 adapter via Open-Meteo (explicit models=era5; OBSERVED_REANALYSIS_AT_T0 vs REALIZED_FUTURE_REANALYSIS, hard-gated — see §16 for the Checkpoint 5.5 model-identity/wind-vector/t0-precision corrections)
  hydrology/hydrosheds.py         Real HydroRIVERS adapter (Asia region only); HydroLAKES deliberately deferred (BLOCKED)
  elevation/terrain_tiles.py       Real AWS Terrain Tiles adapter (explicitly NOT NASADEM, which is BLOCKED on an Earthdata auth wall)
```

Every adapter follows the same two-layer pattern established by
`esa_worldcover.py`: a pure, network-free core function (e.g.
`compute_class_fractions`, `compute_zonal_density`,
`nearest_feature_distance_km`, `decode_terrarium_elevation`) that unit
tests exercise with synthetic arrays/geometries, wired into a real I/O
function that downloads/reads real data and turns any failure into a
`BLOCKED` `FeatureResult` — never a fabricated value.

**`geometry_by_source` is a distinct concept from the "speed" geometry**
referenced in Checkpoint 4.5's known limitations above
(`SPEED_ELIGIBILITY_PENDING_GEOMETRY`, i.e. outbreak-to-outbreak
spread-front direction/speed for the eventual PISTES risk model).
Checkpoint 5's geometry is source-to-grid-cell (e.g. a weather
station/observation point to a computational grid cell), used for
`services/geospatial`'s own real-data smoke tests
(`smoke_tests/run_smoke_test.py`). It does not resolve, and was not
intended to resolve, the outbreak-spread-geometry limitation — that
remains open, unstarted PISTES model work.

### Known limitations added this checkpoint

- Only the Asia ("as") HydroRIVERS continental region is integrated;
  any AOI outside it returns BLOCKED, not a wrong-continent distance.
- HydroLAKES, NASADEM, and DEM-derived slope are not implemented
  (deferred/BLOCKED with documented reasons — see `GIS_DATA_SOURCES.md`).
- No primary weather-feature formulation has been chosen — see
  `ENVIRONMENTAL_FEATURE_PROTOCOL.md`'s decision gate.
- No PISTES feature-assembly pipeline exists yet that combines these
  adapters' outputs into a single model-ready vector; each adapter
  returns independent `FeatureResult`s only.

## 16. Checkpoint 5.5 — weather source identity, wind-vector, and t0 temporal-purity corrections

Four scientific-semantics fixes to §15's weather adapter, none of which
touch land-cover/host-density/hydrology/elevation/grid/CRS/geometry
architecture (all preserved unmodified per this checkpoint's explicit
instruction). `weather/era5_land.py` is renamed `weather/era5.py` (the
old name was itself part of the mislabeling problem being fixed — kept
would have implied a dataset identity the code no longer even attempts).

1. **Explicit model selection.** Every Open-Meteo request now passes
   `models=era5` via `_daily_request_params`/`_hourly_request_params` —
   never the unset `best_match` default. Selection evidence (live
   probing, not memory): `era5_land` cannot supply
   wind/precipitation through this API; `era5_seamless`/`best_match`
   silently blend ERA5-Land+ERA5; `ecmwf_ifs` is a temporally-
   inconsistent operational archive per Open-Meteo's own docs; `cerra`
   doesn't cover either smoke AOI. `era5` is the only model with every
   required variable, single fixed version, full corpus coverage.
2. **Hourly-paired wind.** `aggregate_hourly_wind` converts each hour's
   own `(wind_speed_10m, wind_direction_10m)` pair to `(u, v)`
   independently, then averages the COMPONENTS — the Checkpoint 5 path
   that paired `wind_speed_10m_max` with `wind_direction_10m_dominant`
   (two independent daily statistics) is removed from
   `fetch_daily_weather` entirely, not just supplemented.
3. **t0 temporal-purity.** `T0Precision` (`weather/base.py`) distinguishes
   `DATE_ONLY` (this corpus's normal case — cutoff at midnight UTC,
   `timestamp < cutoff`) from `TIMESTAMP` (`timestamp <= cutoff`).
   `build_pre_t0_weather_summary` (`era5.py`) is the new PRIMARY weather
   feature builder — structurally incapable of including a post-cutoff
   hour, since it never requests or considers one.
4. **Land-cover year safety + area-statistic terminology** (adjacent
   fixes bundled into the same checkpoint, `landcover/esa_worldcover.py`):
   `resolve_landcover_temporal_role` reports `YEAR_MATCHED_REFERENCE`
   only when `worldcover_year == target_year`, never a silent "nearest
   available year" substitution; the land-cover fraction statistic is
   now documented and named as a pixel-count zonal fraction (not
   "area-weighted," which the implementation never actually was).

Full model-selection evidence, wind-math proofs, and t0-cutoff rule:
`ENVIRONMENTAL_FEATURE_PROTOCOL.md`, `GIS_DATA_SOURCES.md` §3,
`era5.py`/`esa_worldcover.py` module docstrings.

### Known limitations added this checkpoint

- `lookback_hours` remains an `UNFROZEN_DEVELOPMENT_PARAMETER`
  (`config.WEATHER_LOOKBACK_HOURS_DEV_DEFAULT = 24`) — which duration is
  epidemiologically appropriate is undecided.
- Which pre-t0 aggregation formulation (state-at-t0, trailing window,
  trailing window + trend) is primary remains undecided
  (`ENVIRONMENTAL_FEATURE_PROTOCOL.md`).
- ERA5's 0.25° (~25km) resolution is coarser than ERA5-Land/IFS/CERRA —
  accepted as the tradeoff for variable coherence and temporal
  consistency, not revisited by this checkpoint.
- Land-cover pixel-count zonal fractions remain an approximation of true
  area weighting, accepted only at this checkpoint's small-AOI scale.

## 17. Checkpoint 5.6 — weather valid-time/availability-time split, timezone-safe t0, grid-cell host density

Three further corrections, all preserving §15/§16's architecture and the
GLW4 count/area fix unmodified:

1. **New module `weather/t0_resolution.py`** — supersedes §16's
   `era5.py`-local `t0_cutoff`/`is_timestamp_eligible`/`pre_t0_window_bounds`.
   `resolve_iana_timezone` (offline, via `timezonefinder`'s
   `timezone_at_land` — deliberately not `timezone_at`, which falls back
   to conventional ocean/pole zones and would make "timezone cannot be
   resolved" untestable) + `resolve_t0_boundary` (`zoneinfo`-based,
   historically-correct UTC offset per date) replace Checkpoint 5.5's
   unconditional UTC-midnight cutoff. `T0Boundary.resolved=False` when
   no land timezone exists for a coordinate — callers treat this as
   BLOCKED, never a silent UTC fallback.
2. **`weather/base.py`**: `WeatherTemporalRole.OBSERVED_REANALYSIS_AT_T0`
   renamed `RETROSPECTIVE_REANALYSIS_STATE_PROXY` (the old name was
   itself the overclaim being corrected — see `ENVIRONMENTAL_FEATURE_PROTOCOL.md`'s
   PERMANENT RULE). New `WeatherAvailabilityQuality` enum
   (`ACTUAL`/`LAG_RULE_PROXY`/`UNKNOWN`) answers the separate
   operational-availability question, never `ACTUAL` anywhere in this
   pipeline. `era5.py`'s `build_pre_t0_weather_summary` gained an
   optional `strict_operational_availability` parameter (citation-backed
   ERA5T ~5-day lag, `ERA5T_PRELIMINARY_LAG_DAYS`) and a
   `PreT0WeatherWindow` carrying the full timezone/availability
   provenance trail (`source_timezone`, `t0_start_local`,
   `availability_quality`, etc.) — the shared `FeatureResult` contract
   itself is untouched.
3. **`host_density/fao_glw.py`**: new `extract_grid_cell_density` (pure
   core: `overlap_fraction`, `compute_cell_density_from_pixel_overlaps`)
   is now the PRIMARY host-density feature for the computational grid,
   replacing Checkpoint 5.5's `extract_density` AOI-window radius for
   that purpose (`extract_density` itself is unmodified and still
   exists). Overlap-area-weighted mean across real GLW4 source pixels
   intersecting a `grid.GridCell`'s own bounds; a cell fully inside one
   source pixel algebraically inherits exactly that pixel's density
   (the overlap-fraction factor cancels) — no arbitrary-radius averaging
   survives into the final grid feature.

### Known limitations added this checkpoint

- `strict_operational_availability`'s ERA5T ~5-day lag is a documented,
  citation-backed CONSERVATIVE PROXY, not a per-record exact historical
  publication timestamp (none exists/is fabricated).
- Neighboring computational grid cells sharing one coarse GLW4 source
  pixel legitimately get identical density values — expected, not a bug,
  but not yet decided how (or whether) PISTES feature assembly should
  treat that degenerate-resolution case specially.
- `timezone_at_land` returns `None` for non-land coordinates (by
  design) — a genuinely bad/corrupted outbreak coordinate that lands in
  open water would BLOCK its own weather features; this is treated as a
  safety feature (catches bad data) rather than a limitation, but is
  worth noting for future debugging.

## 18. Checkpoint 6A — feature-assembly layer (`services/features/`)

New package, full design in `FEATURE_ASSEMBLY_PROTOCOL.md`. Summary for
this document's own architecture record:

```
services/features/
    contracts.py       FeatureSnapshot, GridCellFeatures, SnapshotReadiness, compute_snapshot_id
    feature_policy.py  FeaturePolicy, LandCoverFeaturePolicy, protocol_hash()
    cache.py           FileWeatherCache (duck-typed; era5.py never imports it)
    assembler.py        assemble_feature_snapshot(...) -- the only entry point
```

`assemble_feature_snapshot(repo, *, forecast_origin, policy, ...)`
consumes `services/forecast_origin.ForecastOrigin` and
`services/source_selector.get_eligible_sources` directly (no new
source-eligibility logic is introduced) and every `services/geospatial/*`
adapter's existing `FeatureResult` contract unmodified. It produces a
`FeatureSnapshot` — raw, provenance-preserving, unnormalized,
un-risk-scored — that a later PISTES engine will consume instead of
calling any geospatial adapter directly.

One additive change to a Checkpoint 5.6 module: `era5.build_pre_t0_weather_summary`
gained an optional `cache=` parameter (`services/features/cache.FileWeatherCache`,
duck-typed, no import in `era5.py`) — everything else in
`services/geospatial/` is unmodified.

### Known limitations added this checkpoint

- No development/evaluation fold-usage freeze exists yet (Part 24,
  deferred to before any ST-DBSCAN/model-parameter tuning).
- `FeaturePolicy` values used for the two real smoke snapshots
  (`weather_lookback_hours=24`, `active_window_days=14`, 2.5km grid)
  remain `UNFROZEN_DEVELOPMENT_PARAMETER`s — no scientific selection has
  been made.
- Land cover is only ever computed per-cell using the existing
  Checkpoint 5.5/5.6 pixel-count zonal-fraction method (windowed on the
  cell's own extent) — it does not yet have a GLW4-style overlap-area-
  weighted grid-cell method; only host density received that treatment
  in Checkpoint 5.6/6A.
- Hydrology is computed per grid-cell centroid (`distance_to_nearest_river_km`),
  not overlap-weighted — a single real geodesic distance per cell, which
  is already the correct unit for a point-to-nearest-feature query
  (unlike GLW4's raster-overlap case).

## 19. Checkpoint 6A.5 — feature-policy truthfulness, resolved-data signature, snapshot identity

Full design: `FEATURE_ASSEMBLY_PROTOCOL.md` §2-3, §12. Summary for this
document's architecture record: `services/features/feature_policy.py`
gained `__post_init__` validation (rejects unsupported `weather_model`,
`elevation_include=True`, invalid grid/lookback parameters, unsupported
host-density species, invalid `hydrorivers_search_radius_km`, invalid
`FROZEN_STATIC_REFERENCE` years); the ambiguous `environment_temporal_mode`
field is removed. New module `services/features/resolved_data_signature.py`
(`compute_resolved_data_signature`, `landcover_comparability_group`,
`compare_feature_compatibility`). `FeatureSnapshot` (`contracts.py`)
gained `feature_policy_hash`/`resolved_data_signature_hash` (replacing
the single `feature_protocol_hash`, kept as a backward-compatible
read-only property), `landcover_comparability_group`, and top-level
`source_timezone`/`t0_timezone_quality`/`resolved_t0_cutoff_utc` fields.
`compute_snapshot_id` now additionally takes `t0_precision`,
`temporal_mode`, `country_scope`, `disease`, and
`resolved_data_signature_hash`.

One real bug fixed in `services/geospatial/weather/era5.py`
(Checkpoint 5.5/5.6 code, not previously caught): `_hourly_request_params`
hardcoded the `WEATHER_MODEL` module constant into the actual HTTP
request regardless of what `model` argument `build_pre_t0_weather_summary`
received — declared metadata could silently disagree with the real
request. Fixed by threading the caller's own `model` through
consistently, plus a hard refusal (`BLOCKED`) for any model other than
`WEATHER_MODEL` (only `"era5"` has verified provenance constants).

### Known limitations added this checkpoint

- No version-harmonization protocol exists for combining
  `WORLDCOVER_V100`/`WORLDCOVER_V200` snapshots into one model matrix —
  `compare_feature_compatibility` only detects and flags the mismatch,
  it does not resolve it.
- `resolved_data_signature_hash` does not yet cover every conceivable
  resolved-configuration detail (e.g. individual per-cell host-density
  MISSING/BLOCKED patterns) — it covers dataset/method identity, not a
  full content hash of every assembled value.

### Checkpoint 6B — model-fitting exposure freeze + ST-DBSCAN context layer

Two new independent service groups, both governed by tracked design
docs rather than repeating their rules here:

- `services/model_fitting_exposure.py` — classifies every forecast
  origin into `FIT_DEVELOPMENT` / `HELD_OUT_FROM_MODEL_FITTING` /
  `SRI_LANKA_TRANSFER_CASE_STUDY` and builds calendar-year expanding
  folds reusing the frozen `split_embargo` purge policy unmodified. See
  `SPLIT_USAGE_FREEZE.md` for the full rules and real corpus counts.
- `services/stdbscan/` — deterministic joint space+time density
  clustering (`config.py`, `event_date.py`, `core_support.py`,
  `neighborhood.py`, `cluster.py`, `snapshot.py`), plus
  development-only parameter infrastructure
  (`parameter_candidates.py`, `development_sensitivity.py`) that never
  reads held-out or Sri Lanka data and never reports outcome/accuracy
  fields. See `STDBSCAN_PROTOCOL.md` for the full joint-neighborhood
  definition, the approximate-GPS core-support guard, and the
  deterministic border/cluster-ID design.

No ST-DBSCAN parameter is frozen this checkpoint —
`STDBSCANConfig.parameter_status` structurally forbids constructing a
`FROZEN_REFERENCE` config until a future checkpoint explicitly
authorizes one.

### Checkpoint 6B.5 — hard development firewall correction

Checkpoint 6B's real parameter-candidate path computed geometry
directly from raw historical records (caller-trusted filtering,
cross-country NN/temporal comparisons). Two new modules close that gap:
`services/stdbscan/development_source_universe.py` (reuses the already
hard-gated `source_selector.get_eligible_sources` to build a validated,
de-duplicated, exclusion-reported source universe) and
`services/stdbscan/international_sensitivity.py` (real, all-country,
MICRO+MACRO development sensitivity, replacing an under-labeled
Thailand-only run). `model_fitting_exposure.assert_fit_development_only`
is now the single hard-firewall implementation both sensitivity report
builders call at their own entry point — never relying on the caller to
have pre-filtered. See `STDBSCAN_PROTOCOL.md` §11/§15-19 for the full
design and `DATA_AUDIT.md` §71 for the real before/after corpus
correction.

### Checkpoint 6C — hazard-engine foundation (`services/hazard/`)

A new, deliberately independent package proving the multi-source
hazard mathematics: `contracts.py` (`FactorValue`/`HazardFactors`/
`HazardMixConfig`/`SourceGeometry`/`WindVector`), `kernels.py`
(EXPONENTIAL/GAUSSIAN radial kernels), `anisotropy.py` (meteorological
alignment + `MODULATING`/`ANGULAR_NORMALIZED` anisotropy), `protocol.py`
(`HazardConfig` + deterministic hash), `source_hazard.py` (local/
anisotropic pathway -> per-source pre-link hazard), `accumulator.py`
(all-source summation), `relative_risk.py` (bounded `1-exp(-H)` link),
`snapshot.py` (`HazardSnapshot` orchestrator + identity). Deliberately
imports neither SQLite/FastAPI/React nor `features.contracts`/
ST-DBSCAN internals — consumes only its own explicit contracts. Every
usable factor in this checkpoint carries `status=SOFTWARE_FIXTURE_ONLY`
— no real feature->factor transformer exists yet. Full design:
`HAZARD_ENGINE_PROTOCOL.md`.

Also renamed the Checkpoint 6B legacy unsafe parameter path
(`parameter_candidates.build_parameter_candidate_report` ->
`build_legacy_parameter_candidate_report`) so it can never be reached
by accident under its old, plausible-sounding public name — it remains
a pure, `SUPERSEDED_BY_6B5` function for tests/methodological-history
comparison only; the real pipeline uses
`build_country_scoped_parameter_candidates` exclusively.

### Checkpoint 6C.5 — cell-vs-source factor index correction

Found and fixed before any real feature->factor transformer was built:
`HazardFactors` (6C) incorrectly grouped cell-level environmental
factors under a per-SOURCE bag. Split into `CellHazardFactors`
(grid_cell_id-indexed: host/environmental-suitability/water-context —
shared identically by every source's contribution to that cell) and
`SourceHazardFactors` (source_id-indexed: source_strength_factor
only); the legacy combined class survives only as
`LEGACY_6C_FIXTURE_ONLY`, no longer accepted by
`compute_source_hazard`. New `meteorology.py` makes wind explicitly
cell-indexed (`CellMeteorology`/`wind_by_cell`,
`expand_uniform_meteorology` for the current uniform-fixture case).
`snapshot.build_hazard_snapshot` now iterates an explicit
`expected_grid_cell_ids` (a cell can never silently vanish), validates
every geometry/factor object's own declared identity against its
dictionary placement, and rejects duplicate/non-eligible source IDs
outright. `relative_risk.compute_relative_risk_index` now returns
`RelativeRiskResult(value, status)` — `status=NUMERIC_SATURATION_ADJUSTED`
makes float64 saturation at large `H` explicit rather than silently
returning an unlabeled `1.0`. Full design: `HAZARD_ENGINE_PROTOCOL.md`
§0, §17-19; before/after record: `DATA_AUDIT.md` §73.

### Checkpoint 6D — real feature→factor transformation development layer

New `services/factors/` package (10 modules — see
`FACTOR_TRANSFORMATION_PROTOCOL.md` for the full list) sits BETWEEN raw
`FeatureSnapshot`s and the hazard engine's dimensionless factor
contracts, deliberately never putting transformation-fitting logic
inside `services/hazard/` (which stays a pure mathematical consumer).
Produces `FactorSnapshot`s only — never a real `HazardSnapshot`; the
hazard package's `SOFTWARE_FIXTURE_ONLY`-only contracts were not
loosened. Also hardened `services/hazard/snapshot.py`/`meteorology.py`
with the Part 0 preflight guards (duplicate/extra grid-cell rejection,
source/meteorology identity cross-checks, explicit meteorology spatial
provenance participating in `hazard_input_signature_hash`) before any
real-data work began.

### Checkpoint 6D.5 — reference-identity correction + new module

Fixed a real scientific-identity gap in `FactorReferenceProfile` before
any production use: `reference_profile_hash()` now includes a
`reference_observation_digest` covering the FULL effective
`EMPIRICAL_CDF_REFERENCE` support, not just summary quantiles. New
`services/factors/host_reference_gathering.py` reuses the real
assembler's own `source_selector`/`grid`/GLW4 adapters to build
host-only reference material without weather I/O (real 579-origin
universe in ~80s vs. the weather-inclusive path's ~30s/origin). New
`ReferenceStratumKey`/`ReferenceCompatibilityMode.STRICT_COMPATIBLE`
dataset-compatibility firewall added to `reference_profile.py`. New
`sample_identity` field on `services/geospatial/feature_result.py`'s
`FeatureResult` (optional, backward-compatible) populated by
`services/geospatial/host_density/fao_glw.py`'s new
`contributing_pixel_sample_identity` from real pixel-overlap geometry.
Full design: `FACTOR_TRANSFORMATION_PROTOCOL.md` §16-20.

### Checkpoint 6D.6 — effective weighted raster identity, conflict firewall, honest readiness

Corrected 6D.5's `sample_identity` (pixel-SET only) with
`contributing_pixel_sample_support`/`FeatureResult.sample_support_digest`
— a weight-aware digest mirroring the real density computation's own
filter/weighting, so two cells sharing a pixel set but different
overlap splits no longer alias. Added a reference-observation
value-conflict firewall (`REFERENCE_OBSERVATION_VALUE_CONFLICT`) that
blocks pooling on a same-identity/different-value collision rather than
silently keeping first/last/average. Rerunning this over the real
579-origin universe with an initial exact float comparison produced
1,690 false positives, all measured at ~3.5e-18 to ~5.7e-14 absolute —
resolved with a tiny, documented software tolerance
(`reference_observations.values_conflict`,
`math.isclose(rel_tol=1e-9, abs_tol=1e-9)`), adopted only after direct
measurement of the real diffs, never assumed upfront. Extended
`ReferenceStratumKey` with a full-field, order-independent
`canonical_key()`/`digest()`. Corrected `build_development_reference_audit`'s
readiness rule to require actually-available (not merely
listed) intended-universe coverage plus zero conflicts/incompatible
strata before reporting `GLOBAL_REFERENCE_PROFILE_READY`. Full design:
`FACTOR_TRANSFORMATION_PROTOCOL.md` §21.

### Checkpoint 7A — production scientific grid + evaluation-domain freeze attempt (honestly blocked)

New `services/geospatial/scientific_grid.py`: real `shapely` polygon
grid cells in an AOI-local UTM projection, replacing `build_smoke_grid`
for all model-development work (`build_smoke_grid` remains a smoke/test
fixture only). New `services/model_development/` package:
`domain_design.py` (predeclared 25-200km domain candidates evaluated
against real FIT_DEVELOPMENT D1-D7 target coverage — real result:
`DOMAIN_RULE_BLOCKED_NO_CANDIDATE_ACHIEVES_FULL_COVERAGE`, honestly
reported, not forced), `target_assignment.py` (presence/background
labeling, deterministic polygon-containment cell assignment,
out-of-domain targets retained never dropped), `baseline_registry.py`
(`B0`/`B1`/`B2` pre-registered, never fit), `protocol.py`
(`model_development_protocol_hash`), `host_reference_rebuild.py`
(scientific-grid host-only snapshot builder — rebuild itself blocked
pending the domain-rule resolution above). Full design:
`SCIENTIFIC_GRID_PROTOCOL.md`, `MODEL_DEVELOPMENT_PROTOCOL.md`.

### Checkpoint 7A.5 — local forecast context, true-domain grid masking, projection-safety hardening

Inspected the existing ST-DBSCAN freeze status FIRST (`STDBSCAN_PROTOCOL.md`,
`SPLIT_USAGE_FREEZE.md`): `STDBSCANConfig.__post_init__` structurally
forbids `parameter_status=FROZEN_REFERENCE` — no `eps_space_km`/
`eps_time_days`/`min_core_supports` value has ever been, or can yet be,
scientifically frozen. New `services/model_development/local_context.py`
builds `LocalForecastContext` (trigger-anchored ST-spatial components,
never merging geographically disconnected trigger situations into one
country-wide domain) from an explicitly-labeled UNFROZEN ST-DBSCAN
candidate config — `context_status` always reports
`LOCAL_CONTEXT_UNFROZEN_ST_DBSCAN_CANDIDATE_BASIS`, never a finalized
scientific decision. New `local_target_scope.py` classifies future D1-D7
targets `LOCAL_SCOPE_TARGET`/`NONLOCAL_FUTURE_EVENT`/`LOCAL_SCOPE_UNRESOLVED`
using ST-DBSCAN's own pre-existing joint-neighborhood rule — never a new
distance invented in response to 7A's coverage failure. New
`local_domain_design.py` reruns the SAME predeclared 25-200km candidates
against `LOCAL_SCOPE_TARGET`-only rows. Corrected
`services/geospatial/scientific_grid.py`'s domain/grid construction to mask
to the TRUE source-buffer union (never the old rectangular bounding box —
`DomainGeometry.union_geometry`/`union_geometry_digest`,
`ScientificGridCell.domain_overlap_area_km2`/`domain_overlap_fraction`) and
added real projection-safety diagnostics/gating
(`assess_projection_safety`, `PROJECTION_CONTEXT_SAFE`/`_UNSAFE`, a
predeclared 1% distortion tolerance). New `cell_size_selection.py`
(engineering-only coarsest-qualifying-candidate rule). Added a
`functools.lru_cache` to `services/geospatial/crs.build_transformer` —
real-data audits at this checkpoint's scale (thousands of per-context UTM
transforms) made repeated `pyproj.Transformer.from_crs` construction a
genuine bottleneck; caching is pure/stateless and changes no computed
result. Full design: `SCIENTIFIC_GRID_PROTOCOL.md` §10-11,
`MODEL_DEVELOPMENT_PROTOCOL.md`.

### Checkpoint 7A.6 — decouple ST-DBSCAN from evaluation truth, freeze the local evaluation envelope

Fixed a real semantic bug: 7A.5 reused an ST-DBSCAN source-clustering
temporal epsilon (`eps_time_days`) to gate FUTURE D1-D7 target
evaluation, producing an artificially tiny (0.84%) "local" result. New
`services/model_development/local_evaluation_scope.py` is the corrected
PRIMARY evaluation contract — structurally decoupled from ST-DBSCAN (no
`STDBSCANConfig` parameter anywhere); `local_context.py`/
`local_target_scope.py` are kept unmodified for descriptive/diagnostic
use only. Freezes `PRIMARY_LOCAL_EVALUATION_DISTANCE_KM = 25.0`
(`FROZEN_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE`, literature-anchored
rationale in new `LOCAL_EVALUATION_SCOPE_RATIONALE.md`) and
`SCIENTIFIC_GRID_CELL_SIZE_KM = 5.0` (`FROZEN_ENGINEERING_RESOLUTION`).
Real corrected audit: 1,387/3,947 (35.1%) targets
`WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE` — exactly reproducing
Checkpoint 7A's own original 25km coverage figure, confirming
correctness. `services/geospatial/scientific_grid.py`'s
`ScientificGridConfig` gained separate `domain_distance_status`/
`cell_size_status` fields. Full design: `STDBSCAN_PROTOCOL.md` §21,
`MODEL_DEVELOPMENT_PROTOCOL.md` §25-36.

### Checkpoint 7A.6.1 — geodesic primary-scope truth + projection-safe multi-component domain

Fixed a real projection bug: 7A.6 still projected one ENTIRE origin's
eligible-source set into a single AOI-local UTM CRS for its primary
scope decision — the real audit found 9 real origins where that was
itself unsafe. New `services/geospatial/scientific_domain.py`: sources
are grouped into geodesically-connected `SCIENTIFIC_DOMAIN_COMPONENTS`
(edge iff real distance `<= 50km`, never ST-DBSCAN), each with its own
local CRS and a new buffer-radial distortion check. Primary scope truth
(`services/model_development/local_evaluation_scope.classify_target_primary_scope`)
is now computed directly from real WGS84 geodesic distance and no
longer accepts any projected-geometry parameter at all — grid-cell
assignment is a separate, non-authoritative step. Real result: 0 of
3,147 real components unsafe (vs. 7A.6's 9 unsafe origins); 0 row-level
disagreements between the old and new geodesic classification; 579/579
real origins built complete scientific grids; every real WITHIN-scope
target received a grid cell.
`services/model_development/host_reference_rebuild.py` rebuilt on this
componentized architecture. Full design: `SCIENTIFIC_GRID_PROTOCOL.md`
§12, `MODEL_DEVELOPMENT_PROTOCOL.md` §37-47.

### Checkpoint 7A.6.2 — scientific identity hardening

Split 7A.6.1's single weak `domain_protocol_hash` into three explicit
identities in `services/geospatial/scientific_domain.py`:
`scientific_domain_protocol_hash` (rules only), `ScientificEvaluationDomain.scientific_evaluation_domain_id`
(one concrete prediction-time instance), and a new
`ScientificGridCell.scientific_cell_id` field (one concrete
configuration/projection-sensitive cell). Audited every real persistent
cache in the codebase for scientific under-specification — found none.
Proved (grep + logic) that the identity hardening is independent of the
already-running host-reference rebuild's numerical/hash output, so it
did not need to be re-run. Full design: `SCIENTIFIC_GRID_PROTOCOL.md`
§13, `MODEL_DEVELOPMENT_PROTOCOL.md` §48-53.

### Checkpoint 7B — baseline spatial-rank model development

New `services/model_development/` modules, all `FIT_DEVELOPMENT`-only
and firewalled at their own entry point: `candidate_registry_7b.py`
(kernel-scale registry + the frozen 24-member baseline x kernel x scale
candidate grid), `fold_reference.py` (raw host-observation caching +
fold-local training-only `FactorReferenceProfile` construction, never
leaking validation-fold covariates backward into training statistics),
`baseline_scoring.py` (B0/B1/B2 x EXPONENTIAL/GAUSSIAN scoring, area-
weighted percentile/rank computation), `selection_7b.py` (origin-balanced
aggregation, the frozen primary selection rule, clustered bootstrap
uncertainty), `development_run_7b.py` (top-level chronological-fold
orchestration), `protocol_7b.py` (`FrozenBaselineModelSpecification`).
Reuses `model_fitting_exposure.build_calendar_year_folds` unchanged for
fold construction — no new split logic. Full design:
`BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md`, `MODEL_DEVELOPMENT_PROTOCOL.md`
§58+.

## Checkpoint 7C

`services/model_development/{candidate_registry_7c.py,evaluation_protocol_7c.py,wind_scoring_7c.py,wind_readiness_7c.py,paired_comparison_7c.py,development_run_7c.py,protocol_7c.py}`.
Host-free (no raw host snapshot cache). Reuses 7B's entire
scoring-support/selection/bootstrap stack
(`baseline_scoring.{CellScore,compute_area_weighted_percentiles,compute_target_cell_ranks,compute_coverage_record}`,
`selection_7b.*`) plus `services/hazard/{anisotropy.py,kernels.py,contracts.py}`
(reused, not duplicated) and
`services/geospatial/{distance.py,source_geometry.py,weather/era5.py}`.
Full design: `ENVIRONMENTAL_WIND_MODEL_DEVELOPMENT_PROTOCOL.md`,
`MODEL_DEVELOPMENT_PROTOCOL.md` §60.

## Checkpoint 7D / 7E

`services/model_development/{heldout_protocol_7d.py,heldout_run_7d.py,sri_lanka_protocol_7e.py,sri_lanka_run_7e.py}`.
7E reuses 7D's freeze assertion and constants directly
(`sri_lanka_protocol_7e` imports from `heldout_protocol_7d` rather than
redefining them) and reuses the same C0 scorer
(`wind_scoring_7c.score_origin_candidates_7c`, `wind=None`), target-scope
machinery (`local_evaluation_scope.py`), and coverage/percentile
functions (`baseline_scoring.py`) as every prior checkpoint. Both add a
symmetric role firewall in `model_fitting_exposure.py`
(`held_out_from_model_fitting_origins`/`assert_held_out_only` for 7D,
`sri_lanka_transfer_case_study_origins`/`assert_sri_lanka_transfer_case_study_only`
for 7E) alongside the original `fit_development_origins`/
`assert_fit_development_only`. Tracked aggregate evidence summaries:
`CHECKPOINT_7D_EVIDENCE_SUMMARY.json`, `CHECKPOINT_7E_EVIDENCE_SUMMARY.json`.
Full design: `MODEL_DEVELOPMENT_PROTOCOL.md` §61-62.

## Checkpoint 8A

`services/model_development/{direction_readiness_8a.py,direction_protocol_8a.py}`
-- pure, self-contained direction-semantics primitives (bearing
conversion, wind FROM/TO, resultant-vector/clarity math) frozen for
readiness testing only. Deliberately isolated: neither module imports
`wind_scoring_7c.py`, `candidate_registry_7c.py`, or any evaluation/
development-run module, and neither is imported by them -- C0/CW
scoring is completely unaffected. `direction_readiness_protocol_hash_8a()`
binds the frozen semantics (never a timestamp). Full design:
`DIRECTION_MODEL_PROTOCOL.md`, `DIRECTION_READINESS_AUDIT.md`,
`DIRECTION_CODE_READINESS_AUDIT.md`, `MODEL_DEVELOPMENT_PROTOCOL.md` §63-64.

## Checkpoint 8B

`services/direction/c0_geometric_tendency.py` -- the first REUSABLE,
DB-independent direction-field service (cell-in, sources-in,
`CellDirectionTendency8B`-out; no target/future-outbreak parameter
anywhere). Directional weight is the exact frozen C0 per-source kernel
contribution (`services.hazard.kernels.evaluate_kernel`,
`FROZEN_KERNEL_FAMILY`/`FROZEN_KERNEL_SCALE_KM` from
`candidate_registry_7c.py`, no new implementation), aggregated via the
frozen Checkpoint 8A.1 `DirectionalMassTerm`/`compute_resultant_vector`
primitives directly. `services/model_development/direction_protocol_8b.py`
freezes the protocol identity (`direction_method_protocol_hash_8b()`,
binding the 8A.1 parent hash, the frozen C0 identity, and every 8B
semantic, never a timestamp) and reuses 7D/7E's own
`assert_frozen_c0_model` hard-freeze gate. Real FIT_DEVELOPMENT-only
structural audit:
`smoke_tests/run_direction_structural_audit_8b.py`. Full design:
`DIRECTION_8B_PROTOCOL.md`, `MODEL_DEVELOPMENT_PROTOCOL.md` §65.

## Checkpoint 8B.3

`services/direction/c0_cell_local_tendency_8b3.py` -- the ACTIVE
corrected direction-field service (`compute_cell_direction_tendency_8b3`,
`CellDirectionTendency8B3`-out, same target-free signature shape as
8B). Uses the new `services/geospatial/distance.py::source_to_cell_tangent_at_cell`
(the SOURCE->CELL direction expressed in the CELL's own local East/
North tangent frame, `CELL_LOCAL_EAST_NORTH_TANGENT_FRAME`) instead of
the historical `source_to_cell_unit_vector` (SOURCE-frame, unchanged
for provenance) -- the fix for a real geodesic reference-frame defect
8B.2 found but did not correct. Same frozen directional weight, same
8A.1 resultant primitives, no new parameter. New protocol hash
`direction_method_protocol_hash_8b3()`
(`services/model_development/direction_protocol_8b.py`, additive
symbols only) binds the corrected identity; historical
`direction_method_protocol_hash_8b()`/`_8b2()` untouched. Real
FIT_DEVELOPMENT-only structural audit + historical-vs-active diff:
`smoke_tests/run_direction_structural_audit_8b3.py`, writing to a
separate `local_data/model_development/8b3_direction/` (historical
`8b_direction/` never touched). Full design: `DIRECTION_8B_PROTOCOL.md`
§20, `MODEL_DEVELOPMENT_PROTOCOL.md` §67.

## Checkpoint 9A

`services/model_development/{rate_protocol_9a.py,rate_readiness_9a.py}`
-- apparent local spread-front rate methodology freeze and
FIT_DEVELOPMENT-only readiness dataset (`v_obs = d_min/lead_days`
km/day, target-level de-pseudoreplication). Reuses existing frozen
primitives directly with no new distance/eligibility/dedup logic:
`source_selector.get_eligible_sources`, `forecast_target.build_forecast_targets`,
`development_run_7b.dedupe_targets_by_origin_and_event`,
`local_evaluation_scope.classify_target_primary_scope` (for the real
`d_min`/nearest-source-reference computation). `rate_readiness_protocol_hash_9a()`
binds the frozen formula/firewalls/bootstrap-plan identity (never a
timestamp), printed before any real rate value was summarized. No S0
value computed here -- Checkpoint 9B only. Real readiness run:
`smoke_tests/run_rate_readiness_9a.py`. Full design:
`RATE_MODEL_PROTOCOL.md`, `MODEL_DEVELOPMENT_PROTOCOL.md` §68.

## Checkpoint 9B

`services/model_development/{rate_s0_bootstrap_9b.py,rate_input_identity_9b.py,rate_protocol_9b.py}`
-- formal freeze of the predeclared S0 estimated apparent local
spread-front rate, with the pre-9B numeric exposure (9A.1) disclosed
rather than re-derived. Zero DB/geospatial/direction/weather
dependency: reads only the already-persisted 9A
`rate_target_level_readiness_9a.csv` (371 target-level rows). Canonical
dataset identity uses two distinct hashes -- raw file SHA256 and a
text-preserving canonical scientific-payload hash (sorted
`[target_event_id, exact-persisted-numeric-text]` pairs, numeric value
never round-tripped through a Python float) -- so drift in either the
bytes or the scientific content is independently detectable.
`rate_s0_bootstrap_9b.py` implements a target-event-level percentile
bootstrap using only Python stdlib (`random.Random(42)`,
`Random.randrange`, `statistics.median`, explicit linear-interpolation
quantile), never NumPy/SciPy, bound to its own frozen implementation
source SHA256 so the estimator cannot silently change between runs.
One-time runner `smoke_tests/run_s0_bootstrap_9b.py`: writes a
pre-bootstrap freeze manifest, closes and re-reads it from disk to
compute and persist its SHA256 sidecar, reloads and verifies both
before executing the real (never re-executed after) bootstrap;
exclusive-create guarded against 6 result filenames, empirically
confirmed to refuse a second run. Real result: point estimate
`3.946421443154751` km/day (reproducing the 9A.1-exposed value
exactly), 95% bootstrap interval `[3.5491046170907765,
4.343077329563724]` km/day, n=371, seed 42, 1000 resamples. No S1
selection, no nominal-reach computation -- later checkpoint. Full
design: `RATE_MODEL_PROTOCOL.md` §21, `MODEL_DEVELOPMENT_PROTOCOL.md`
§70, `VALIDATION_PROTOCOL.md` §15.

## Checkpoint 9C

`services/integration/{nominal_reach_9c.py,geospatial_intelligence_contract_9c.py,geospatial_intelligence_protocol_9c.py}`
-- deterministic nominal-reach derivation
(`nominal_reach_km(day_h) = frozen_S0_rate_km_day * day_h`, D1-D7 only,
`3.946..27.625` km) plus a DB/framework-independent internal
presentation contract (`FrozenGeospatialIntelligenceContract9C`) that
assembles the already-frozen risk (7C), direction (8B.3), and
apparent-rate (9B) components without conflating their scientific
meanings. No model fitting, no predictive evaluation, no rerun of
anything upstream -- structurally verified via AST import scans (no
DB/repository, no 8B.3/7C scoring recomputation, no 9B bootstrap
implementation module, no held-out/Sri Lanka rate-run module). The
frozen 25km operational local evaluation envelope and nominal reach are
always two separate fields, never reconciled -- Day 7 nominal reach
(`27.625` km) exceeds 25km by design. Risk stays
`STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT`; direction and rate remain
independent (direction never scaled into km/day, rate never derived
from bearing/clarity). No FastAPI route yet.
`integration_protocol_hash_9c()=cec826a26c860c752d1fa32d94edcdfba2e0186950cdccfc96067fef2ce51a90`
binds every frozen parent hash and semantic separation rule, excluding
timestamps/paths/UI/URLs. Full design: `RATE_MODEL_PROTOCOL.md` §22,
`MODEL_DEVELOPMENT_PROTOCOL.md` §71, `VALIDATION_PROTOCOL.md` §16,
`GEOSPATIAL_INTELLIGENCE_INTEGRATION_PROTOCOL.md`.

## Checkpoint 9C.1

`services/model_development/{rate_scope_conditioning_9c1.py,rate_scope_conditioning_protocol_9c1.py}`
-- read-only post-freeze diagnostic over the already-persisted 9A
`rate_origin_target_observations_9a.csv`: the frozen 25km inclusion
rule mathematically forces `v_obs <= 25/lead_days`, and the D7
theoretical ceiling (`3.571` km/day) is strictly below the frozen S0
(`3.946` km/day). No DB query, no geodesic recomputation, no 9B
bootstrap rerun -- structurally verified (AST import + real-call
scans). S0, the 9B interval, the 25km envelope, and every Checkpoint
9C nominal-reach value are byte/numerically unchanged; only the
interpretation is hardened
(`RATE_ESTIMAND_CONDITIONING_9C1`). No alternate pooled S0 estimator
exists anywhere (no `statistics.median`/`statistics.mean` call in
either module). `rate_scope_conditioning_protocol_hash_9c1()=26168ca784b5f8cb5393db872baa1e7e7f1d74f782b16df17c97354b9bf52b8f`
reads (never redefines) the historical 9A/9B/9C hashes. Full design:
`RATE_MODEL_PROTOCOL.md` §23, `GEOSPATIAL_INTELLIGENCE_INTEGRATION_PROTOCOL.md`
§6, `MODEL_DEVELOPMENT_PROTOCOL.md` §72, `VALIDATION_PROTOCOL.md` §17.

## Checkpoint 10A

`services/application/frozen_geospatial_analysis_10a.py` -- the first
runtime (as opposed to research-batch) orchestrator: given an
`OutbreakRepository` and a `forecast_origin_id`, resolves the real
origin, calls `get_eligible_sources`, `build_scientific_evaluation_domain`,
`score_origin_candidates_7c` (frozen C0), and
`compute_cell_direction_tendency_8b3` (frozen 8B.3 direction) exactly
as already frozen -- no formula reimplemented, no new research metric.
Attaches the frozen 9C rate/nominal-reach context and 9C.1 conditioning
disclosure. Raises `RuntimeAnalysisError10A` with an explicit status
(`ORIGIN_NOT_FOUND`/`ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE`/
`ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN`/`ANALYSIS_UNAVAILABLE_GRID`)
instead of ever fabricating a score/bearing/source. New
`api/{schemas.py,router.py}` -- a read-only FastAPI `APIRouter` (prefix
`/api/geospatial`, 5 routes: `/protocol`, `/origins`,
`/analysis/{id}/summary`, `/analysis/{id}/cells`,
`/analysis/{id}/sources`) containing zero scientific computation and no
direct SQLite query, integrated into `backend/main.py` alongside the
pre-existing root route (no other team component had any code to
preserve -- `health_anomaly`/`risk_forecasting`/`smart_diagnostics`
were all empty `.gitkeep` placeholders at integration time). GeoJSON
cell/source features use `[longitude, latitude]` EPSG:4326 (RFC 7946);
the internal AOI-local UTM CRS is exposed separately as
`scientific_crs`, never conflated. New
`services/integration/geospatial_api_protocol_10a.py`:
`geospatial_api_protocol_hash_10a()=8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716`,
binding the parent 9C/9C.1 hashes and every response-semantic rule,
excluding timestamps/ports/paths/UI. Full design:
`GEOSPATIAL_API_PROTOCOL.md`.

## Checkpoint 10A.1

No science changed -- `services/application/frozen_geospatial_analysis_10a.py`
and `api/{schemas.py,router.py}` gain ADDITIVE fields/constants only
(historical 10A behavior for every existing field is unchanged). Makes
explicit what was always true: the runtime analysis is a
`HISTORICAL_RETROSPECTIVE_REPLAY` over `ValidationMode.RETROSPECTIVE_PROXY`/
`RecordDomainScope.HISTORICAL_ONLY` (the SAME enum objects structurally
verified to feed both the real source-selection call and the new
metadata fields), never live operational forecasting. The 14-day active
source window (`ACTIVE_SOURCE_WINDOW_DAYS_10A1`, reused verbatim from
the historical constant) is labeled
`FIXED_HISTORICAL_DEVELOPMENT_PROTOCOL_VALUE_NOT_SCIENTIFICALLY_VALIDATED`,
tracing its `UNFROZEN_DEVELOPMENT_PARAMETER` provenance back through
`ACTIVE_SOURCE_WINDOW_DAYS_7C`/`_7D`/`_7E`/`rate_protocol_9a` to the
single canonical `config.ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT` (a
code/protocol-identity audit, never a model rerun). New
`services/integration/geospatial_api_protocol_10a1.py` --
`geospatial_api_protocol_hash_10a1()=e44761319870e9196768599ad88fde237d709c2b17b03f17662ab144bd5634b8`
-- binds the historical, UNCHANGED
`geospatial_api_protocol_hash_10a()=8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716`
plus every mode/window semantic above; the historical dict is
structurally proven to have lacked these fields (classified
`HISTORICAL_API_IDENTITY_WITH_RUNTIME_INPUT_SEMANTICS_NOT_YET_BOUND`,
never "invalid"). Corrected the prior checkpoint's own stale evidence
test count (1531, not 1530) and recorded the pre-existing
`StarletteDeprecationWarning` (httpx/TestClient) honestly rather than
silently installing `httpx2`. Full design: `GEOSPATIAL_API_PROTOCOL.md`
§15.

## Checkpoint 10B

`services/transport/{geospatial_snapshot_10b.py,snapshot_store_10b.py,chunking_10b.py}`
-- real-time TRANSPORT engineering over the frozen historical-
retrospective scientific snapshot, never live science. One scientific
computation (`run_frozen_geospatial_runtime_analysis_10a`, unchanged)
produces one immutable `GeospatialSnapshot10B`, identified by a
deterministic `snapshot_id` (SHA256 of canonical scientific content
only -- excludes `generated_at`, cache status, chunk metadata). A
bounded (8 entries), TTL'd (60s), thread-safe, single-flight
`SnapshotStore10B` (generic, zero scientific knowledge) backs both HTTP
(`/summary`,`/cells`,`/sources` now resolve ONE shared snapshot instead
of three independent computations) and a new `/api/geospatial/ws`
WebSocket endpoint (`transport_ready` ->
`snapshot_request`/`snapshot_refresh`/`ping` ->
`snapshot_begin`/`summary`/`sources`/`cells_chunk`*/`snapshot_end`/
`pong`/`error`, chunked at 500 cells via `chunking_10b.py`, both
engineering-only `ENGINEERING_TRANSPORT_PARAMETERS_NOT_SCIENTIFIC_PARAMETERS`).
Verified exactly: HTTP payload == WebSocket payload for the same
`snapshot_id`, byte/numerically. New
`services/integration/geospatial_transport_protocol_10b.py::geospatial_transport_protocol_hash_10b()=071dbd1baebfa18d30626a39b218287bb25269a0ec1e61b809a955b31191f657`.
**Historical `geospatial_api_protocol_hash_10a()` and active
`geospatial_api_protocol_hash_10a1()` are unchanged.** No 7B-9C.1
rerun, no held-out/Sri Lanka evaluation, no rate/bootstrap rerun, no
automatic DB polling anywhere. Full design:
`GEOSPATIAL_REALTIME_TRANSPORT_PROTOCOL.md`.

## Checkpoint 10B.1

Transport/architecture hardening only -- no science touched.
`SnapshotStore10B`'s per-key single-flight state is now
reference-counted (`_KeySlot(lock, refcount)`), reclaimed the instant
the last borrower releases it (in a `finally`, covering both success
and `compute_fn` failure) -- thousands of distinct keys, successful or
failing, never leave a stale entry. Eviction diagnostics are now
`eviction_count: int` + `recent_evicted_keys: deque(maxlen=50)`, never
an unbounded list. New `repositories/provider.py::create_outbreak_repository()`
is the ONE place that constructs `SQLiteOutbreakRepository` -- both
`api/router.py` and `services/transport/geospatial_snapshot_10b.py`
now call it instead of constructing the concrete class directly (Mongo
still NOT implemented). New
`services/integration/geospatial_transport_protocol_10b1.py::geospatial_transport_protocol_hash_10b1()=476a7593aafd4011eec840a7ca60cb339302c037f4e00dd7ba11a239ff153a25`
binds the exact inbound/outbound WebSocket message field contract
(cross-checked against the real Pydantic schemas and real WS frames),
the 16 KiB inbound message byte limit, and the `generated_at_utc`/
`scientific_content_hash_verified` field semantics -- on top of the
UNCHANGED historical `geospatial_transport_protocol_hash_10b()=071dbd1baebfa18d30626a39b218287bb25269a0ec1e61b809a955b31191f657`.
`snapshot_end`'s `scientific_content_hash_verified` is now a real
in-memory recomputation via the existing `compute_snapshot_id_10b`
(never a second formula) -- a mismatch produces a
`SNAPSHOT_CONTENT_INTEGRITY_MISMATCH` error frame instead of a false
success claim. `snapshot_id` for `ORIGIN:Afghanistan:2022-05-29`
re-verified unchanged
(`cc92c6f716b7c2d04a2f4c18a893e87757876611e1068d9b0c526ae8853e8598`).
Full design: `GEOSPATIAL_REALTIME_TRANSPORT_PROTOCOL.md` §18.

## Checkpoint 10B.1a

Small transport-contract correction only -- no science touched. HTTP
`/summary`/`/cells`/`/sources` now serialize `snapshot_id`/
`generated_at_utc` (previously WebSocket-only), closing the gap where
a prior test could only compare `forecast_origin_id` across HTTP
routes rather than the real snapshot identity. True equality now
proven both across the three HTTP routes and between HTTP and every
WebSocket frame for one reused snapshot. Integrity verification
(`verify_snapshot_integrity_10b`) moved to run BEFORE any scientific
WS frame is sent, not just before `snapshot_end`. New
`services/integration/geospatial_transport_protocol_10b1a.py::geospatial_transport_protocol_hash_10b1a()=0549339d2d79659048e2d265403507b756b464d454419c28c295d005d8450f0e`
binds the now-historical 10B.1 hash plus the HTTP envelope/equality/
timing facts above -- neither `071dbd1b...` (10B) nor `476a7593...`
(10B.1) was rewritten. Controlled `ORIGIN:Afghanistan:2022-05-29`
snapshot ID re-verified unchanged across HTTP and WS. Full design:
`GEOSPATIAL_REALTIME_TRANSPORT_PROTOCOL.md` §19.
