# FMD-05 Target Protocol — Frozen

Defines exactly what a "target" is for FMD, what quantity is predicted,
and which candidate secondary tasks are and are not currently supported
by the evidence. See `FMD_STUDY_PROTOCOL.md` for the forecast-origin unit
of analysis this document's targets attach to.

## 1. Target row semantics (shared mechanism, FMD-applied)

For forecast origin `t0` (country, date), a **target row** is built by
`services/forecast_target.build_forecast_targets` (unmodified, generic)
for every distinct historical FMD event whose `historical_event_date`
(never source availability, never report date — see §2) falls
**strictly after** `t0` and within the primary horizon:

```
1 <= lead_days <= 7        lead_days = historical_event_date - t0
```

- `lead_days = 0` (same day as `t0`) is a possible SOURCE, **never** a
  target (a record already in the origin's own source snapshot is
  excluded from that origin's target set by construction).
- `lead_days > 7` is out of scope for the primary target set (no D8-D14
  target is built anywhere in FMD-05 — see `FMD_STUDY_PROTOCOL.md` §3).
- A target must independently pass the same model-candidate/dedup-
  resolved gate as a source (via the `fmd_forecast_bridge.py` mapping,
  `FMD_STUDY_PROTOCOL.md` §2) — a `STATUS_NOT_CONFIRMED`-excluded record
  can never become a target any more than it can become a source.

Every target row preserves, unmodified: `forecast_origin_id`,
`target_id` (`"{forecast_origin_id}::{target_event_id}"`, unique per
origin), `target_event_id` (the record's own stable
`source_record_id` — stable across every origin that includes it),
`lead_days`, `latitude`/`longitude`, `gps_quality`,
`coordinate_collision_status`, and the eligibility-tier flags (§4).

**Pseudo-replication (frozen rule, unchanged from the generic
mechanism):** the same real FMD event can legitimately appear as a target
of several earlier forecast origins in the same country within the
7-day lookback window — this is repeated *forecasting* of one biological
event, not several independent events. Measured on the real FMD corpus:
**31,658 total target rows, but only 7,271 unique `target_event_id`
values** (`FMD_COHORT_MANIFEST.json`). Any later evaluation that computes
a rate, an AUROC, or a capture statistic over target rows **must
aggregate/report at the unique-`target_event_id` level, or explicitly
disclose the row-level pseudo-replication factor** (here, ~4.4x) — never
silently treat 31,658 as 31,658 independent biological outbreaks.

## 2. Forecast-origin `t0` semantics (leakage boundary)

`t0` = the origin's own `effective_availability_date` under
`ValidationMode.RETROSPECTIVE_PROXY` — for every FMD record this is
`proxy_availability_date`, which FMD-03's adapter always populates from
`observation_date` (`proxy_availability_quality = OBSERVATION_DATE_PROXY`,
100% of the corpus — never `ACTUAL`, never upgraded). **Formal rule: no
predictor may use information dated after `t0`.**

- **Information known at `t0`**: every other eligible FMD record in the
  same country whose own effective availability date is `<= t0` (subject
  to whatever `active_window_days` a later checkpoint freezes for
  feature/source-snapshot construction — deliberately NOT selected in
  FMD-05, see `FMD_EVALUATION_PROTOCOL.md` §3).
- **Information forbidden**: any record whose `historical_event_date` or
  effective availability date is `> t0` — structurally enforced by
  `source_selector.get_eligible_sources`' T0 invariant
  (`avail_date <= t0`), never re-implemented ad hoc.
- **Multiple report/onset dates**: FMD's biological occurrence date
  (`historical_event_date`) is always `onset_date`
  (`services/historical_event_date.py`, now with an explicit
  `FAO_EMPRESI_BIGQUERY_CSV` branch — see below); `report_date` and
  `proxy_availability_date`/`confirmation_date` are separate, non-
  biological chronologies and are structurally prevented from ever
  becoming a target's occurrence date (`derive_historical_event_date`
  never reads `report_date` or a proxy field for this purpose; see
  `test_historical_event_date.py`'s `test_date_06_*` /
  `test_proxy_availability_date_never_used_even_when_convenient`, both
  reused unmodified and still passing for FMD's own source system).
- **Event/onset vs. report-date semantics**: `onset_date` is FMD-03's own
  documented biological field (verified 100% VALID, no
  MISSING/MALFORMED/impossible dates across all 9,526 rows —
  `FMD_DATA_AUDIT.md` "DATE VALIDATION"). `report_date` is never read for
  target-occurrence purposes.
- **Environmental feature cutoff**: any future feature build must use
  only pre-`t0` weather/host/land-cover state — already enforced upstream
  by FMD-04's `build_pre_t0_weather_summary`-style construction
  (`ENVIRONMENTAL_FEATURE_PROTOCOL.md`); FMD-05 adds no new feature
  computation.
- **Cluster/history cutoff**: any future ST-DBSCAN-derived predictor may
  only use clusters built from sources with effective availability
  `<= t0` — see `FMD_EVALUATION_PROTOCOL.md` §5.
- **Target observation window**: `(t0, t0+7]`, inclusive of day 7,
  exclusive of day 0 (§1).

**FMD-05 correction to shared code (disease-agnostic, additive):**
`services/historical_event_date.py` had branches for `WAHIS_PDF` and
`FAO_EMPRESI_CSV` source-record-id prefixes but none for FMD's own
`FAO_EMPRESI_BIGQUERY_CSV` prefix, so FMD records fell through to a
generic MEDIUM-confidence fallback despite `onset_date` being exactly as
authoritative for this source as it is for `FAO_EMPRESI_CSV`. A new
branch (`FAO_EMPRESI_BIGQUERY_CSV` -> `onset_date` -> `HIGH`, mirroring
the existing `FAO_EMPRESI_CSV` branch exactly) was added; no existing
WAHIS/`FAO_EMPRESI_CSV`/LSD branch was touched (`test_historical_event_date.py::
test_fmd05_bigquery_csv_onset_date_preserved_with_provenance`). This does
not change any Tier-A count (see §4 — Tier A is unreachable for FMD for
an unrelated, GPS-quality reason), only the honesty of the
`historical_event_date_quality` label for any future consumer.

### Worked examples

| Case | t0 | Record date | lead_days | Outcome |
|---|---|---|---|---|
| Valid historical feature | 2020-06-10 | 2020-06-08 (same country) | n/a (source) | usable as a SOURCE at this origin (date <= t0) |
| Future leakage attempt | 2020-06-10 | 2020-06-15 | 5 | usable ONLY as a TARGET of the 2020-06-10 origin, never as a source/predictor for it |
| Boundary at exactly t0 | 2020-06-10 | 2020-06-10 | 0 | excluded from BOTH source-snapshot-derived leakage and the target set (TARGET-01) |
| D1-D7 window edge (valid) | 2020-06-10 | 2020-06-17 | 7 | included (upper bound inclusive) |
| D1-D7 window edge (excluded) | 2020-06-10 | 2020-06-18 | 8 | excluded — D8-D14 not built |

## 3. What the RISK label will be (frozen definition, NOT yet computed)

The **risk label** for a forecast origin is: does at least one D1-D7
target event fall within a to-be-frozen spatial domain, measured from
the target to the nearest **eligible, active-at-`t0` source** (§3a) —
never the origin's own newly-arriving trigger source(s) alone? This
document freezes the DEFINITION, not the domain radius:

### 3a. `SPATIAL_TARGET_REFERENCE_SOURCE_SET` — FROZEN (FMD-05R)

```
SPATIAL_TARGET_REFERENCE_SOURCE_SET = ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0
```

(`data_processing/build_fmd_cohort.py`). FMD-05 left this implicit and
its own prose (an earlier revision of this section) inconsistently said
"origin's own trigger source(s)" — ambiguous between two real,
non-identical candidates:

- `TRIGGER_SOURCES_ONLY`: only the NEW event(s) that caused this origin
  to exist (`origin.trigger_source_ids_at_t0` — same-day arrivals only).
- `ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0` (**FROZEN**): every source that is
  eligible AND active at `t0` under whatever `active_window_days` FMD-06
  later freezes (`services.source_selector.get_eligible_sources` /
  `services.forecast_origin.build_source_snapshot`'s output) — a
  superset of the trigger-only set that also includes still-active
  earlier-arriving sources.

**Resolved using the only spatial-scope classifier already implemented
in this repository**: `services/model_development/local_evaluation_scope.py`'s
`classify_target_primary_scope` (disease-agnostic, built for and
currently only exercised by LSD, reused unmodified rather than
re-implemented for FMD) defines PRIMARY SCOPE TRUTH as `min(WGS84
geodesic distance(source, target) for every eligible active source)` —
its `sources` parameter is typed `list[EligibleSourcePoint]`, the
eligible-and-active set, not a trigger-only subset. Adopting the SAME
reference-set concept for FMD reuses existing, tested, disease-agnostic
architecture rather than inventing a second, FMD-only mechanism. This
freezes WHICH source set a distance will eventually be measured against
— it does **not** select `active_window_days` (still
`UNFROZEN_DEVELOPMENT_PARAMETER`) or any radius (§3b). No source
snapshot or spatial-scope classification is actually computed anywhere
in FMD-05/FMD-05R.

- Start of target interval: `t0 + 1 day`. End: `t0 + 7 days` (inclusive).
- Qualifying event: any `risk_target_eligible` target row (§4) within the
  spatial domain (measured per §3a once a radius is frozen).

### 3b. Candidate spatial-domain radii (unchanged from FMD-05, no selection made)

- Spatial relationship: **REQUIRED but NOT fixed in FMD-05.** LSD froze
  25km from vector-transmission literature that does not apply to FMD
  (FMD spreads by direct contact/aerosol/fomite, not arthropod vectors —
  `fmd_feature_registry.py`'s own note: "FMD is NOT vector-transmission").
  FMD-05 predeclares CANDIDATE domain radii only, borrowing the existing
  generic candidate set already used for LSD's own local-evaluation-scope
  sensitivity work (`PREDECLARED_DOMAIN_CANDIDATES_KM = (25, 50, 75, 100,
  150, 200)`, `MODEL_DEVELOPMENT_PROTOCOL.md`) as a starting menu, plus
  the two commonly cited FMD control-zone radii from veterinary
  contingency-planning practice (a 3km protection zone / 10km surveillance
  zone convention) as additional candidates. **No candidate is selected as
  primary in FMD-05** — selection is deferred to FMD-06 and must use
  `FIT_DEVELOPMENT` chronology/coverage evidence only, never held-out or
  Sri Lanka performance (same non-negotiable rule already governing every
  other frozen threshold in this repository).
- Multiple future events within the window/domain: the risk label is
  **binary presence/absence**, not a count — one or many qualifying
  future events both yield `risk_present = True`. A future secondary
  formulation (count/rate) is NOT precluded but is not frozen here.
- Censoring: an origin whose own country has zero eligible events at all
  within its 7-day window is `risk_present = False` by construction (not
  "missing" — a genuine, measured absence within the available corpus,
  not a claim about surveillance completeness outside it).
- Missing-target handling: an origin can never have a "missing" risk
  label under this definition (absence of a qualifying event IS the
  negative class) — there is therefore **no explicit negative/control
  sampling requirement** for the risk task; see §5 below and
  `FMD_EVALUATION_PROTOCOL.md` §4 for the full reasoning.

Target definition is explicitly **separate from** the future model's
prediction algorithm — nothing here specifies a kernel, a coefficient, or
a distance-decay function; that is FMD-06/07 territory.

## 4. Target-quality tiers and the direction/speed readiness finding

`services/target_quality.compute_target_quality_tiers` (unmodified,
generic) computes, per target row:

- `risk_target_eligible`: model-candidate + dedup-resolved + valid
  coordinates + usable event date. **31,658 of 31,658 FMD target rows
  qualify (100%)** — FMD's target-row population and its
  risk-eligible population are identical, because every target row is
  already built from a `modelling_eligible` record with a valid date and
  coordinate.
- `direction_target_tier_a_strict` / `_resolved_only`: additionally
  requires `gps_quality == EXACT` and
  `historical_event_date_quality == HIGH` and a specific
  coordinate-collision status.
- `direction_target_tier_b`: `risk_target_eligible` but not Tier A.

**Measured result: Tier A strict = 0, Tier A resolved-only = 0, Tier B =
31,658 (100% of risk-eligible targets).**

**Root cause (verified, not assumed):** `FMD_DATA_AUDIT.md` "QUALITY"
already recorded `gps_quality = UNKNOWN` for **all 9,526** raw FMD rows —
the EMPRES-i BigQuery export never marks any coordinate `EXACT`. Since
Tier A requires `gps_quality == EXACT` unconditionally, **Tier A is
structurally unreachable for the current FMD corpus regardless of date
quality or coordinate-collision status** — confirmed by direct
measurement (0 of 31,658), not inferred. This is independent of, and
would not have been fixed by, the `historical_event_date` correction in
§2 (that only affects date-quality labeling, and Tier A already fails on
the GPS-quality clause first).

**This finding must never be worked around by loosening the Tier A
definition, and Tier B must never be silently promoted to Tier A** — both
prohibited explicitly by this freeze. The consequence is scoped narrowly:

- **Risk modelling: unaffected.** `risk_target_eligible` does not require
  `gps_quality == EXACT`; the entire 31,658-row / 7,271-unique-event
  target population remains usable for the primary RISK task.
- **Direction modelling: NOT currently viable** on this corpus under the
  existing Tier-A definition. `DIRECTION_TARGET_TIER_A_STRICT`/
  `_RESOLVED_ONLY` readiness = **NO-GO** (0 usable Tier-A targets).
  Tier B rows exist but per `VALIDATION_PROTOCOL.md`'s already-frozen
  convention (reused, disease-agnostic), Tier B is "usable but with
  weaker location/date evidence, retained for sensitivity analysis only"
  — never a substitute for a validated primary direction evaluation.
- **Speed modelling: NOT currently viable**, for the identical reason
  (speed tiers are computed identically to direction tiers today) —
  additionally, every speed-tier row already carries
  `speed_eligibility_status = "SPEED_ELIGIBILITY_PENDING_GEOMETRY"`
  (source-to-target geometry has never been built for either disease) —
  **NO-GO**, for two independent reasons.
- **This does NOT block FMD-06 risk-target spatial-domain calibration or
  FMD-07 risk-model development** — the risk pipeline's readiness is
  evaluated on its own evidence, not tied to direction/speed's.

Direction/speed become reachable only if a future checkpoint (a) obtains
a materially GPS-precision-labeled FMD source (not available today) or
(b) proposes and freezes a revised, evidence-justified Tier-A definition
for FMD specifically — never by quietly relaxing the shared definition to
manufacture a positive count.

## 5. Readiness (target semantics only — see `FMD_STUDY_PROTOCOL.md` for
the full per-gate table)

- Primary D1-D7 risk target definition: **GO** — fully specified except
  the intentionally-deferred spatial-domain radius.
- Direction target: **NO-GO** (Tier A = 0, structural GPS-quality gap).
- Speed target: **NO-GO** (same GPS gap, plus geometry never built).
