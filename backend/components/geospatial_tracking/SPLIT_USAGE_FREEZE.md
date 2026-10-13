# Split Usage Freeze — Checkpoint 6B

This document freezes how the historical corpus's forecast origins are
partitioned for model-fitting purposes, **before** any parameter or
model development begins, and states the rules that govern each
partition's use for the rest of the project. It is tracked in git (not
`local_data/`) because it is a project-governance decision, not raw
data output.

## 1. Roles

Every `ForecastOrigin` is classified into exactly one of three
mutually-exclusive roles by
`services/model_fitting_exposure.classify_origin_role`:

| Role | Rule | Meaning |
|---|---|---|
| `FIT_DEVELOPMENT` | `country != "Sri Lanka"` and `t0 < 2024-01-01` | May be used for ST-DBSCAN parameter selection, feature selection, active-window selection, weather-lookback selection, risk-coefficient fitting (future checkpoints), normalization fitting (future checkpoints). |
| `HELD_OUT_FROM_MODEL_FITTING` | `country != "Sri Lanka"` and `t0 >= 2024-01-01` | Excluded from every fitting/selection/tuning decision. Administrative counting only. Its risk-capture/direction/speed/accuracy performance is **never inspected** in Checkpoint 6B (or before a future, explicitly-authorized evaluation checkpoint). |
| `SRI_LANKA_TRANSFER_CASE_STUDY` | `country == "Sri Lanka"` (unconditionally — even pre-2024 records) | Never used to select or tune anything. May only be *run through* an already-frozen pipeline later as a geographic-transfer demonstration. |

`MODEL_FITTING_CUTOFF = "2024-01-01"` is frozen. It must never be moved
later merely because held-out or transfer-case results look poor —
doing so would be outcome-driven leakage.

## 2. Why Sri Lanka is unconditional

Sri Lanka is the project's real target geography. Even its pre-2024
records are excluded from every development computation (not just
future ones) so that no development decision — a distance threshold, a
temporal window, a feature choice — is ever implicitly shaped by the
one country the system is ultimately meant to generalize to. This is a
geographic-transfer validity concern, independent of the temporal
cutoff.

## 3. What "held out" does and does not mean

`HELD_OUT_FROM_MODEL_FITTING` is **not** "blind", "untouched", or
"unseen" data. The corpus underlying it has already been through the
same audited ingestion, deduplication, and eligibility pipeline as
`FIT_DEVELOPMENT` records. The only thing that changes is that its
origins are excluded from any function that selects, fits, or tunes a
parameter, coefficient, or normalization constant. This distinction
matters because a later evaluation checkpoint may legitimately compute
descriptive counts over it (e.g. corpus size, coverage) without that
constituting leakage — only decisions driven by its *prediction
performance* would.

## 4. Purging at fold boundaries

Within `FIT_DEVELOPMENT`, the calendar-year expanding-window folds
(`services/model_fitting_exposure.build_calendar_year_folds`) reuse the
already-frozen `PURGED_7_DAY_HORIZON_POLICY`
(`services/split_embargo.py`, unchanged since its own freeze): a
training-eligible origin is purged from a fold's training set if
`t0 + 7 days >= validation_block_start`, because its outcome window
would otherwise overlap the validation period. Purging is never
silent — every purged origin is recorded with `purged_by_7_day_rule =
True` in the exposure manifest.

## 5. Where the real counts live

The frozen split is not just a rule — it has been run against the real
corpus and recorded:

- `local_data/manifests/model_fitting_exposure_manifest.csv` (gitignored,
  regenerate via `python -m components.geospatial_tracking.smoke_tests.run_stdbscan_smoke`):
  one row per forecast origin, every role, every reason, nothing hidden.
- Real totals as of this checkpoint (813 total forecast origins):
  **579 FIT_DEVELOPMENT / 229 HELD_OUT_FROM_MODEL_FITTING / 5
  SRI_LANKA_TRANSFER_CASE_STUDY.**
- Calendar-year folds (`FIT_DEVELOPMENT` only) as verified against the
  real corpus — `(train, validation, purged)` counts:
  2018 (0, 41, 0); 2019 (41, 55, 0); 2020 (96, 44, 0); 2021 (140, 303, 0);
  2022 (443, 54, 4); 2023 (501, 76, 1). Early years are honestly sparse
  (2018 has zero training origins because it is the first observed
  year) — this is reported, not smoothed over or discarded.

## 6. Checkpoint 6B.5 correction — availability, not raw records, controls development permission

Checkpoint 6B's own real-data ST-DBSCAN parameter statistics initially
computed candidate geometry directly from
`repo.list_historical_records(...)`, gated only by "non-Sri-Lanka +
`historical_event_date` before the cutoff." That is a weaker rule than
this freeze's own definition of `FIT_DEVELOPMENT` and let unresolved
duplicates / non-model-candidate rows shape parameter evidence, and let
a record with a pre-cutoff biological event but POST-cutoff-only
availability slip in. Checkpoint 6B.5 replaced it with
`services/stdbscan/development_source_universe.build_fit_development_source_universe`,
which reuses the already hard-gated `source_selector.get_eligible_sources`
across every real `FIT_DEVELOPMENT` origin's window — so a source is
admitted to development statistics only because information-availability
rules actually placed it inside a real `FIT_DEVELOPMENT` origin's
eligible window, never because its own event date alone looked early
enough. See `STDBSCAN_PROTOCOL.md` §11 for the full rule and real
before/after counts (old unsafe path: 1278 "usable" records; corrected,
hard-gated, de-duplicated universe: 657 validated sources — the gap is
dominated by `model_candidate=False` records the old path never
excluded).

This correction does not change anything in §1-5 above — the
`FIT_DEVELOPMENT`/`HELD_OUT_FROM_MODEL_FITTING`/
`SRI_LANKA_TRANSFER_CASE_STUDY` forecast-origin roles, the cutoff, and
the 7-day purge rule are exactly as frozen, confirmed unchanged against
the real corpus after this fix (579/229/5 of 813, identical to before).

## 7. What this freeze does not do

This freeze governs *exposure* only. It does not select an ST-DBSCAN
parameter, a feature set, a risk coefficient, or a normalization
constant — see `STDBSCAN_PROTOCOL.md` for the parameter-development
rules that build on top of this freeze, and the Checkpoint 6B
instructions' explicit DO-NOT list for what remains out of scope until
a future checkpoint.
