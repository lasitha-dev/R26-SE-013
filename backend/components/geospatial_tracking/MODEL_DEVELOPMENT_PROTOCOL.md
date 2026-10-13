# Model Development Protocol — Checkpoint 7A / 7A.5 / 7A.6 / 7A.6.1 / 7A.6.2

Freezes (or honestly blocks) the scientific spatial/evaluation framework
BEFORE any model candidate is fit or compared, per Checkpoint 7A's own
scope. See `SCIENTIFIC_GRID_PROTOCOL.md` for the grid/CRS side.

**Permanent scope boundary**: nothing in `services/model_development/`
computes a predictive score, a target-percentile/capture metric, an AUC, or
any other model-performance number. That begins only in Checkpoint 7B —
verified structurally (no function signature or dataclass field in this
package names a performance/outcome metric, mirroring the established
`services/factors/` leakage-test pattern).

## 1. Development-domain design is allowed to look at FIT_DEVELOPMENT
   targets (Part 7)

`services/model_development/domain_design.py` inspects real
`FIT_DEVELOPMENT` future-target geometry — allowed ONLY because (a)
FIT_DEVELOPMENT is development data, (b) no predictive model score exists
anywhere in this checkpoint, (c) the resulting domain rule is frozen BEFORE
any candidate model is ever fit or compared using it. Labeled
`DEVELOPMENT_DOMAIN_DESIGN`, never model validation.
`assert_fit_development_only` is called at the module's own entry point (a
hard firewall, not caller trust) — verified rejecting both
`HELD_OUT_FROM_MODEL_FITTING` (`DOMAIN-02`) and
`SRI_LANKA_TRANSFER_CASE_STUDY` (`DOMAIN-03`) origins.

## 2. Predeclared domain candidates (Part 8)

`PREDECLARED_DOMAIN_CANDIDATES_KM = (25, 50, 75, 100, 150, 200)` — fixed
BEFORE computing any coverage number. These are COMPUTATIONAL/EVALUATION
DOMAIN EXTENTS only — never a spread radius, transmission boundary, nominal
reach, kernel scale, or speed × time product (verified structurally,
`DOMAIN-05`).

## 3. Coverage test and selection rule (Parts 9-10)

For each candidate distance `D`, a `risk_target_eligible` D1-D7 target is
"covered" iff its geodesic distance to at least one eligible active source
at that origin's t0 is `<= D` — the exact buffer-union-membership test,
computed directly via geodesic distance (mathematically identical to a
real polygon buffer-union containment test, without needing to construct
the polygons for this check).

**Selection rule** (`select_frozen_domain_distance`): the SMALLEST
predeclared candidate achieving 100% coverage of every real FIT_DEVELOPMENT
D1-D7 risk-eligible target. If none does, the function returns
`(None, DOMAIN_RULE_BLOCKED)` — it never silently expands past the
predeclared candidates and never drops outliers to force a result.

## 4. Real result: the domain rule is BLOCKED (Part 10)

Running `build_development_domain_candidate_audit` against the real,
runtime-derived 579-origin `FIT_DEVELOPMENT` universe (3,947 real
risk-eligible D1-D7 targets) produced:

| candidate (km) | targets covered | coverage |
|---:|---:|---:|
| 25 | 1,387 / 3,947 | 35.1% |
| 50 | 2,634 / 3,947 | 66.7% |
| 75 | 3,134 / 3,947 | 79.4% |
| 100 | 3,405 / 3,947 | 86.3% |
| 150 | 3,713 / 3,947 | 94.1% |
| 200 | 3,820 / 3,947 | 96.8% |

No candidate reaches 100% — full detail in
`local_data/model_development/domain_candidate_audit.csv`. Real target
distance-to-nearest-eligible-source distribution: min 0.0km, p50 33.5km,
p95 161.7km, **p99 372.9km, max 3,290.5km**; 127 of 3,947 targets (3.2%)
exceed even the largest predeclared candidate (200km), spread across 13
countries (Thailand 72, Russian Federation 24, Cambodia 10, Nepal 4, and 9
others with 1-3 each). These are real, large countries where a
`risk_target_eligible` target can legitimately be a geographically distant,
independent outbreak within the same country-scoped record set, not a
local-spread candidate from a specific origin's own active-source cluster.

**Result**: `domain_rule_status = DOMAIN_RULE_BLOCKED_NO_CANDIDATE_ACHIEVES_FULL_COVERAGE`.
Per Part 10's own explicit instruction, this is reported as a STOP, not
resolved by expanding candidates or dropping outliers. **A `LOCAL_SCOPE`
rule — explicitly separating "local spatial spread" evaluation targets from
distant, independent same-country events — is very likely the correct
future resolution, but it is NOT invented here**: doing so immediately
after seeing this exact failure would risk looking like (or actually being)
retuning the rule until results look acceptable, which Part 10 explicitly
forbids. This is left as the primary blocker for a future checkpoint to
design and freeze deliberately, on its own terms.

## 5. Out-of-domain targets are retained, never dropped (Part 11)

`services/model_development/target_assignment.py`'s
`assign_target_to_scientific_grid` has no filtering step — every target
gets exactly one `TargetGridAssignment` row, with
`domain_status = TARGET_OUTSIDE_EVALUATION_DOMAIN` when
`min_distance_to_eligible_source_km > domain_distance_km` (`DOMAIN-04`,
tested; also demonstrated on real data — see
`local_data/model_development/target_grid_assignment.csv`).

## 6. Cell-size engineering audit (Part 12) — also blocked, independent of
   the domain-rule blocker

`local_data/model_development/grid_runtime_audit.csv` reports real
(analytic, no raster I/O) cell counts for every FIT_DEVELOPMENT origin ×
each predeclared domain distance × `{2.5km, 5.0km}` cells:

| domain (km) | cell (km) | mean cells/origin | max cells/origin | est. full-universe raster-extraction time* |
|---:|---:|---:|---:|---:|
| 25 | 5.0 | 8,901 | 156,578 | ~7.9 hours |
| 25 | 2.5 | 35,485 | 625,996 | ~31.5 hours |
| 200 | 5.0 | 24,483 | 241,908 | ~21.7 hours |
| 200 | 2.5 | 97,701 | 967,176 | ~86.7 hours |

*extrapolated from the real 6D.6 GLW4 extraction rate (~2.76ms/extraction,
2 species), analytic cell counts only.

Even the CHEAPEST tested combination (25km domain / 5km cells) is
infeasible to run as a full real 579-origin rebuild within this session.
The dominant driver is NOT cell size but domain bounding-box area: a
forecast origin with geographically dispersed active sources produces a
bounding box far larger than any single source's own buffer (e.g. one real
2-source Bangladesh origin: 4,485 cells at 25km/5km, vs. 100 cells for a
single-source origin at the same parameters — see
`local_data/model_development/scientific_grid_audit.json`).

**Result**: no cell size is frozen. Neither 2.5km nor 5km is defensibly
preferable while the domain question itself remains open, and forcing a
choice now (or artificially shrinking the domain definition to make a
rebuild "fit") would be exactly the kind of premature freeze Part 12 itself
warns against. `ScientificGridConfig.parameter_status` stays
`UNFROZEN_DOMAIN_CANDIDATE`.

## 7. Host-reference rebuild — NOT performed (Part 16-17)

`local_data/model_development/host_reference_rebuild_audit.json`:
`status = BLOCKED_PENDING_DOMAIN_RULE_RESOLUTION`. The 6D.6 host reference
(built on `build_smoke_grid`, hash
`e34fc9d8...`, 6,780 unique observations) is **not deleted** — it remains
valid methodological history, labeled
`SUPERSEDED_FOR_MODEL_FITTING_BY_7A_GRID_PROTOCOL` (it must not be used to
fit anything new once a scientific grid protocol is actually frozen), but
it is currently still the only real host reference this project has, since
no scientific-grid replacement could be honestly built without a frozen
domain rule.

## 8. Unique target-event unit / pseudo-replication (Part 20)

One row per `(forecast_origin_id, target_event_id)` pair, matching
`ForecastTarget`'s own within-origin uniqueness guarantee
(`TARGET7A-01`, tested). The SAME real target event legitimately appearing
from several different forecast origins is repeated forecasting of one
biological event, not pseudo-replication — distinguishable via `target_id`
(`TARGET7A-02`, tested).

## 9. D1-D7 only (Part 21)

`services.forecast_target.PRIMARY_HORIZON_DAYS = 7` (unchanged, reused).
D8+ exclusion is already covered by the pre-existing
`test_forecast_target.py::test_target_04_d8_excluded_from_primary_target_set`
— not duplicated here.

## 10. Deterministic target-cell assignment (Part 22)

Real polygon containment (`shapely`, same UTM projection as the grid).
A point on a shared cell boundary is assigned to the lexicographically
SMALLEST `grid_cell_id` among every cell it touches — explicit, documented,
deterministic (`TARGET7A-03`, tested).

## 11. Fold/exposure firewall reused unchanged (Part 23)

`MODEL_FITTING_CUTOFF = 2024-01-01`, `PURGED_7_DAY_HORIZON_POLICY`, and the
three-role split (`FIT_DEVELOPMENT` / `HELD_OUT_FROM_MODEL_FITTING` /
`SRI_LANKA_TRANSFER_CASE_STUDY`) are reused unchanged from Checkpoint 6B/6B.5
— every `services/model_development/` module calls
`assert_fit_development_only` at its own entry point.

## 12. Presence-only target semantics (Parts 18-19)

Historical outbreak data are PRESENCE events. `target_assignment.py` never
creates a `TRUE_NEGATIVE` label (`PB-01`, structurally verified — no such
string anywhere in the module). Every assignment carries
`label = TARGET_EVENT`; a grid cell without an outbreak is `BACKGROUND`
("a sampled spatial comparison location"), never asserted disease-free
(`PB-02`/`PB-03`).

Primary evaluation metrics are FROZEN AS DEFINITIONS ONLY — never computed
in 7A (Part 28): `TARGET_PERCENTILE_RANK`, `TARGET_CELL_RANK`,
`TOP_5_PERCENT_CAPTURE`, `TOP_10_PERCENT_CAPTURE`; optional:
`DISTANCE_TO_HIGH_RISK_REGION`. None of these is "classification accuracy";
AUC may only be used later in a clearly labeled presence-background
analysis.

## 13. Pre-registered baseline candidates (Parts 24-27) — registry only,
    never fit

`services/model_development/baseline_registry.py`:

- `B0_DISTANCE_ONLY`: `score_i = sum_j K(distance_j_i)` — no host/
  environment/water/source-strength factor.
- `B1_HOST_DISTANCE_LOG1P`: `score_i = Host_LOG1P_i * sum_j K(distance_j_i)`.
- `B2_HOST_DISTANCE_ECDF`: `score_i = Host_ECDF_i * sum_j K(distance_j_i)`.

All three are labeled `EQUAL_SOURCE_BASELINE` (every eligible source gets
equal structural contribution) — never `source_strength_factor = 1.0 REAL`;
the real status stays `NOT_YET_SCIENTIFICALLY_DEFINED`
(`services.factors.source_strength`, unchanged). None uses
`environmental_suitability_factor`/`water_context_factor` (both remain
`NOT_YET_SCIENTIFICALLY_DEFINED`) and none emits an infection probability
— every candidate's `output_label = RELATIVE_SPATIAL_SCORE`
(`BASE-01..08`, tested).

Kernel candidates: `EXPONENTIAL`/`GAUSSIAN`
(`services.hazard.contracts.KernelFamily`, reused unchanged);
`distance_scale_km` remains `UNFROZEN_DEVELOPMENT_PARAMETER`
(`services.hazard.kernels`, unchanged) — never called "spread radius."

## 14. `model_development_protocol_hash` (Part 29)

`services/model_development/protocol.py` hashes together: the scientific
grid config, the frozen domain distance (`None` — blocked) and its status,
the predeclared candidate list, the D1-D7 horizon, the target-assignment
rule, the out-of-domain rule, the primary/optional evaluation-metric
definitions, the background-semantics version, the fold/exposure cutoff and
purge-policy version, and both registry hashes/versions. Never includes
`generated_at`. Current real value (with `frozen_domain_distance_km=None`,
`domain_rule_status=DOMAIN_RULE_BLOCKED...`) is recorded in
`local_data/model_development/model_development_protocol.json`.

## 15. Output manifests (Part 30)

Tracked: this file, `SCIENTIFIC_GRID_PROTOCOL.md`. Local (gitignored,
`/local_data/`): `scientific_grid_audit.json`, `domain_candidate_audit.csv`,
`target_grid_assignment.csv`, `grid_runtime_audit.csv`,
`host_reference_rebuild_audit.json`, `baseline_candidate_registry.json`,
`model_development_protocol.json` — all under
`local_data/model_development/`.

---

# Checkpoint 7A.5 — local forecast context, true-domain grid, projection safety

## 16. Part 1: existing ST-DBSCAN freeze status — inspected FIRST, per instruction

`STDBSCAN_PROTOCOL.md` §8-9 and `services/stdbscan/config.py`:
`STDBSCANConfig.__post_init__` **structurally forbids**
`parameter_status=FROZEN_REFERENCE` — raises `ValueError` unconditionally
("no held-out prediction performance exists yet to justify freezing any
ST-DBSCAN parameter"). `SPLIT_USAGE_FREEZE.md` §7 confirms explicitly:
"This freeze governs exposure only. It does not select an ST-DBSCAN
[parameter/constant]." No `eps_space_km`, `eps_time_days`, or
`min_core_supports` value has ever been selected — only quantile-derived
CANDIDATES exist (`candidate_constants.py`), and the one real
Thailand-only sensitivity result on record found essentially 100% noise
(zero clusters) at the tightest data-derived candidates.

**Conclusion**: no defensible FROZEN ST-DBSCAN context rule exists, and
none can exist within this checkpoint's own rules — this is a
STRUCTURAL fact of the codebase (a `ValueError`, not a judgment call),
not something that could be resolved by choosing different numbers. Per
Part 1's own explicit instruction, this is reported as the PRIMARY
blocker for `LOCAL_FORECAST_CONTEXT_PROTOCOL`/`LOCAL_TARGET_SCOPE_PROTOCOL`
finalization — no new local-distance number was invented in response to
7A's coverage failure. Consistent with the codebase's own established
practice (every ST-DBSCAN sensitivity report runs REAL descriptive
statistics under multiple explicitly-labeled unfrozen candidates, never
selecting one), this checkpoint still builds and exercises the real
`LocalForecastContext`/local-target-scope MACHINERY under one
explicitly-named unfrozen candidate — descriptive, real, honest, never
presented as a finalized scientific decision (`context_status` is always
`LOCAL_CONTEXT_UNFROZEN_ST_DBSCAN_CANDIDATE_BASIS`).

**Real audit candidate used** (chosen because it already existed in the
codebase BEFORE this checkpoint — `STDBSCAN_PROTOCOL.md` §16's real,
corrected, pooled within-country quantiles — never invented now):
`eps_space_km=12.37` (pooled within-country p50 nearest-neighbor
distance), `eps_time_days=3.0` (pooled within-country p50 positive
temporal gap), `min_core_supports=2` (MID of the 2/3/4 candidates),
`active_window_days=14` (MID of the 7/14/21/28 candidates),
`gps_core_policy=PRIMARY_CORE_SUPPORT` — labeled
`MID_TIER_POOLED_WITHIN_COUNTRY_CANDIDATE_7A5_AUDIT`.

## 17. `LocalForecastContext` design (Parts 2-5)

`services/model_development/local_context.py`: for each forecast-origin
TRIGGER source, finds the ST-DBSCAN connected component (CORE+BORDER
cluster, or a NOISE/TEMPORAL_UNUSABLE singleton — never discarded for
being noise) containing it, under the supplied `STDBSCANConfig`. Two
triggers in the SAME component collapse into ONE context; triggers in
disconnected components become SEPARATE contexts sharing only
`forecast_origin_id` (`LOCAL-SRC-01`). Every country-eligible source at
t0 is preserved in `country_eligible_source_ids`; sources not in any
trigger's context are retained in `excluded_country_source_ids` with an
explicit reason (`OUTSIDE_TRIGGER_LOCAL_CONTEXT` or
`TEMPORAL_UNUSABLE_NOT_CLUSTERED`) — never silently dropped
(`LOCAL-SRC-04`). T0-safe by construction (`LOCAL-SRC-07`); deterministic
`local_context_id` (`LOCAL-SRC-08`);
`build_local_forecast_context_development_report` is the sole real
multi-origin entry point and calls `assert_fit_development_only` at its
own boundary (`LOCAL-SRC-05/06`).

## 18. Real local-context counts (Part 37.A)

Real, full 579-origin `FIT_DEVELOPMENT` universe, MID-tier candidate
above: **1,045 local contexts** across **579 origins** (mean 1.80
contexts/origin), of which **981 (94%) are SINGLETON** contexts (a
single, isolated trigger source — consistent with `STDBSCAN_PROTOCOL.md`
§10's own finding that tight-ish candidates produce mostly noise). Across
all origins: **8,696** total country-eligible source appearances, of
which only **1,121** ended up inside SOME local context and **7,575**
(87%) were excluded as belonging to another/no local situation — a
substantial, real correction from 7A's country-wide source scoping.

## 19. Local target-scope association (Parts 6-9, 21-22) — real result

`services/model_development/local_target_scope.py` uses ONLY
`services.stdbscan.neighborhood.joint_neighbors` (unchanged, pre-existing
rule) to decide whether a real future D1-D7 target is a joint
spatiotemporal neighbor of ANY member of its origin's local context(s) —
no model score, kernel scale, or domain-distance parameter exists on its
signature at all (`LOCAL-TGT-05/06/07`).

**Real result** (same MID-tier candidate, all 3,947 real risk-eligible
D1-D7 targets): **33 `LOCAL_SCOPE_TARGET` (0.84%)**, **3,914
`NONLOCAL_FUTURE_EVENT` (99.16%)**, **0 `LOCAL_SCOPE_UNRESOLVED`**.
Reported honestly by country/lead-day in
`local_data/model_development/local_context_audit.json`. This is a real,
reproducible consequence of the MID-tier candidate's tight `eps_space_km`
(12.37km) — most real future D1-D7 events are simply not within 12.37km
AND 3 days of the SAME trigger-anchored context's own members. This
result is NOT interpreted as "the model doesn't work" — it is a direct,
honest report of what a real but UNFROZEN candidate produces; a different
(also unfrozen) candidate would produce a different split, which is
exactly why nothing here is claimed frozen.

## 20. Old >200km outlier re-audit (Part 9) — applied, not assumed

All **127** of 7A's real targets that were >200km from ANY
country-eligible source were re-run through the real local-scope rule
above (never assumed to be nonlocal). **Result: all 127 are
`NONLOCAL_FUTURE_EVENT`** under the real rule — e.g. the Bangladesh
target at 402.3km and the Bhutan target at 266.1km both resolve to
`NONLOCAL_FUTURE_EVENT` by actually applying `joint_neighbors`, not by
assumption. Full list in
`local_data/model_development/local_context_audit.json`'s
`old_200km_outlier_reclassification`.

## 21. Local-domain candidate rerun (Part 20) — real result, and why it is
    NOT a freeze

Rerunning the SAME predeclared 25-200km candidates against the 33 real
`LOCAL_SCOPE_TARGET` rows (each measured against its OWN local context's
member coordinates, never all country-eligible sources) produced **100%
coverage at every candidate, including the smallest (25km)** — trivially
expected, since a `LOCAL_SCOPE_TARGET` is by definition within
`eps_space_km=12.37km` of a context member, and 12.37 < 25.

**This numeric result does NOT mean `EVALUATION_DOMAIN_DISTANCE` is
frozen.** Per Part 26/38: a clean coverage number cannot retroactively
freeze the protocol it depends on — `LOCAL_FORECAST_CONTEXT_PROTOCOL`
and `LOCAL_TARGET_SCOPE_PROTOCOL` themselves rest on the MID-tier
`STDBSCANConfig`, which is structurally forbidden from ever being
`FROZEN_REFERENCE` (§16). A different, equally-defensible unfrozen
candidate (e.g. the p75 tier) would very likely produce a different
local-scope split and a different domain-coverage result. Freezing
`EVALUATION_DOMAIN_DISTANCE` now, on the strength of one arbitrary
candidate's clean-looking number, would be exactly the kind of premature
freeze this checkpoint exists to prevent.

## 22. Domain/grid/projection results (Part 37.D-F) — real

**D. True-domain grid vs. old bounding box** (`grid_runtime_audit_7a5.csv`).
REAL full grid construction at 25km/50km domain × {2.5, 5.0}km cells,
across all 1,045 real local contexts:

| domain (km) | cell (km) | mean true-domain cells | mean old-bbox cells | reduction |
|---:|---:|---:|---:|---:|
| 25 | 2.5 | 349.6 | 406.8 | 14.1% |
| 25 | 5.0 | 89.8 | 101.7 | 11.7% |
| 50 | 2.5 | 1,334.6 | 1,613.2 | 17.3% |
| 50 | 5.0 | 347.0 | 403.3 | 14.0% |

The true-domain masking correction removes a real, consistent **~11-17%**
of cells that the old bounding-box tiling would have wastefully created —
smaller than 7A's own dramatic finding (because REAL local contexts, being
tight and mostly single-source, don't have 7A's huge disconnected-source
bounding boxes any more; a single circular buffer's own bounding-square
"corner gaps" are the main remaining waste). At 75/100/150/200km, full
real re-tiling across all 1,045 contexts was judged too expensive to
repeat in full (the 25/50km real runs already took ~215s combined; the
same measured **0.8575** true/bbox cell-count ratio was applied to the
(real, not extrapolated) analytic bounding-box cell counts at those
distances — reported in the CSV explicitly labeled
`ANALYTIC_BBOX_WITH_EXTRAPOLATED_TRUE_DOMAIN_RATIO`, never presented as
independently re-measured).

Real, **already dramatically smaller than 7A's own numbers**: even the
largest analytic-extrapolated combination (200km/2.5km) averages ~22,021
true-domain cells/context, vs. 7A's real 97,701 mean cells/ORIGIN at the
same domain/cell parameters — because local contexts (mostly 1 source) are
far smaller than 7A's country-wide "every eligible active source" sets.

**E. Projection safety** (`true_domain_grid_and_projection_audit.json`):
real assessment across all 1,045 local contexts (25km domain): **1,045/1,045
`PROJECTION_CONTEXT_SAFE`, 0 unsafe**. Maximum relative distance distortion
observed: **0.094%** — 10x below the 1% predeclared tolerance. 21 distinct
UTM zones were touched ACROSS all contexts (expected — contexts span 29
countries), but every INDIVIDUAL context stayed safely within its own local
projection. No context was blocked by the projection-safety gate in this
real run; the synthetic ~4,000km-wide artificial case (`CRS7A5-03`) remains
the only demonstrated `PROJECTION_CONTEXT_UNSAFE` example, confirming the
gate is exercised and correct without ever firing spuriously on real,
genuinely local data.

**F. Cell-size engineering audit** (25km domain, real): 2.5km → max 590
cells/context (well within the predeclared 2,000-cell budget), all
polygons valid, all sources represented; 5.0km → max 161 cells/context,
same. Both candidates pass every engineering constraint at 25km, so
`select_frozen_cell_size` mechanically picks the COARSEST — **5.0km** —
labeled `FROZEN_ENGINEERING_RESOLUTION`. **This mechanical result is
reported honestly but is NOT actually applied as a freeze** — see §23:
Part 26 requires the domain distance to ALSO be frozen before a cell size
may be declared frozen ("Never partially claim freeze"), and the domain
distance cannot be honestly frozen while it depends on the unfrozen
ST-DBSCAN protocol.

## 23. Freeze decision (Part 26/38)

**NOT FROZEN.** `LOCAL_FORECAST_CONTEXT_PROTOCOL`,
`LOCAL_TARGET_SCOPE_PROTOCOL`, and `EVALUATION_DOMAIN_DISTANCE` all
remain blocked on the same root cause: no ST-DBSCAN configuration can be
`FROZEN_REFERENCE` in this codebase today (§16). `SCIENTIFIC_GRID_CELL_SIZE`
freeze is evaluated independently via engineering-only criteria (§22) but
is likewise not claimed frozen while the local-context protocol it would
serve remains unfrozen. Per Part 39: the host-reference rebuild is **NOT
performed** — 7B model fitting stays blocked. The 6D.6 (smoke-grid) host
reference remains the only real host reference this project has, still
labeled `SUPERSEDED_FOR_MODEL_FITTING_BY_7A_GRID_PROTOCOL`.

## 24. `model_development_protocol_hash` (Part 30) — extended

`services/model_development/protocol.py` now also covers:
`local_context_protocol_version`/`local_context_protocol_hash` (`None`
while unfrozen), `st_dbscan_config_hash_if_used`, `local_context_status`,
`target_scope_rule_version`, `nonlocal_target_policy`,
`out_of_domain_local_target_policy`, `projection_strategy`, and
`projection_tolerance_version` — changing local-scope semantics changes
this hash. Current real value recorded in
`local_data/model_development/model_development_protocol_7a5.json`.

---

# Checkpoint 7A.6 — decouple ST-DBSCAN from evaluation truth, freeze a literature-anchored local evaluation envelope

## 25. The critical semantic bug in 7A.5 (Parts 1-2)

7A.5's real target-scope classifier reused
`STDBSCANConfig.eps_time_days` (a SOURCE-SOURCE clustering temporal
neighborhood parameter — 3 days in the real audit candidate) as the
temporal gate on `joint_neighbors(source_event_date, target_event_date,
...)` when evaluating whether a REAL FUTURE D1-D7 target fell within a
forecast origin's local evaluation scope. This conflated two unrelated
concepts: forecast target temporal eligibility is ALREADY fully and
correctly defined by `1 <= lead_days <= 7`
(`services.forecast_target.build_forecast_targets`) — re-applying a
3-day ST clustering epsilon on top of that meant a spatially close D4-D7
outcome could be, and in the real 7A.5 run WAS, rejected purely because
the source-target event-date gap exceeded 3 days. This produced 7A.5's
real result of only 33/3,947 (0.84%) targets labeled `LOCAL_SCOPE_TARGET`
— confirmed by the real by-lead-day breakdown below to have been an
ARTIFACT of the bug, not a genuine finding about local spread.

## 26. Permanent distinction (Parts 5-6) — ST-DBSCAN is contextual, never gating

`services/model_development/local_evaluation_scope.py` is the new
PRIMARY evaluation contract — it has NO `STDBSCANConfig` parameter
anywhere (`ST-DECOUPLE-01`, structurally verified). ST cluster
membership, noise/temporal-unusable role, `eps_time_days`, `MinPts`,
`active_window_days`, `gps_core_policy`, and config hash all have ZERO
effect on: whether an eligible source contributes to the domain/hazard-
source set (`ST-DECOUPLE-03/04`), whether a grid cell exists, D1-D7
target temporal eligibility, or the primary evaluation denominator
(`ST-DECOUPLE-02/05`). `services/model_development/{local_context.py,local_target_scope.py}`
are NOT deleted — they remain valid for descriptive/diagnostic purposes
only (map display, sensitivity analysis, future scientific discussion).
ST parameters remain genuinely `UNFROZEN_DEVELOPMENT_CANDIDATE` — this
correction does not retroactively freeze them merely to unblock the
pipeline (§16's structural `FROZEN_REFERENCE` prohibition is unchanged
and no longer relevant to primary model development at all).

## 27. Superseded 7A.5 result (Part 3)

Preserved, never deleted, never reused for domain freeze/model
fitting/evaluation/host-reference rebuild: `TARGET_SCOPE_RULE_VERSION =
"7A.5.1_SUPERSEDED_ST_TEMPORAL_EPS_TARGET_SCOPE_DIAGNOSTIC"`
(`services/model_development/protocol.py`) — 33 `LOCAL_SCOPE_TARGET` /
3,914 `NONLOCAL_FUTURE_EVENT`, recorded in
`local_data/model_development/local_context_audit.json`.

## 28. Corrected terminology (Part 4)

Distance/domain membership alone can never prove biological
independence. `local_evaluation_scope.py` never emits
`NONLOCAL_FUTURE_EVENT` (`SCOPE-SEM-01`, verified structurally and
behaviorally). Its three labels:

- `WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE`
- `OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE` — "outside the declared
  modeling claim," never "proven unrelated" (`SCOPE-SEM-02/04`)
- `LOCAL_SCOPE_UNRESOLVED` — no eligible sources existed to test against

A target exactly on the 25km domain boundary counts as WITHIN
(`shapely` `covers()`, boundary-inclusive, never the exclusive
`contains()` — verified with a real geodesically-exact 25.000km boundary
point, `SCOPE-SEM-03`).

## 29. Frozen primary local evaluation envelope (Parts 7-9)

`PRIMARY_LOCAL_EVALUATION_DISTANCE_KM = 25.0`, status
`FROZEN_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE`. An OPERATIONAL LOCAL
ANALYSIS ENVELOPE — never an LSD transmission radius, maximum vector
flight distance, infection boundary, kernel scale, spread-front reach,
or speed × time product. Full rationale, literature characterization
(with an explicit citation-verification caveat — no bibliographic
details fabricated), and the required
`DEVELOPMENT_TARGET_DISTANCE_DISTRIBUTION_ALREADY_EXPOSED = True`
disclosure: `LOCAL_EVALUATION_SCOPE_RATIONALE.md` (new). 25km was
already part of the Checkpoint 7A predeclared candidate registry — no
new number was introduced. `SENSITIVITY_LOCAL_EVALUATION_DISTANCE_KM =
50.0` is pre-registered as a future robustness check ONLY
(`PREREGISTERED_SENSITIVITY_ENVELOPE_NOT_PRIMARY`) — no function in this
codebase ever substitutes it for the primary envelope
(`GRIDFREEZE-04`), and no predictive score was computed under it in this
checkpoint.

## 30. Primary evaluation domain construction (Parts 10-12)

Per forecast origin: obtain ALL eligible active sources via
`source_selector.get_eligible_sources` (the frozen, unmodified selector
rules — no ST-DBSCAN involvement anywhere), construct 25km
`PROJECTED_METRIC_BUFFER_UNION` buffers around every one, take the TRUE
union (`build_source_buffer_union_domain`, unchanged from 7A.5), and grid
only cells intersecting it (`build_scientific_grid`, unchanged from
7A.5). T0-safe by construction — no function here accepts a future
target coordinate (`SCOPE-SEM-05`). Disconnected `MultiPolygon`
components are COMPUTATIONAL DOMAIN COMPONENTS, never transmission
chains — they share one forecast origin and are tiled independently for
efficiency (unchanged from 7A.5), but **partitioning the grid into
disconnected components never filters the hazard-source set**
(`ALLSRC-7A6-01..03`, verified): every scientific cell, regardless of
which component it belongs to, still gets real
`source_geometry.build_geometry_for_grid` entries for EVERY eligible
source at that origin's t0, including sources whose own buffer created a
completely different, distant component. The domain partition is
computational only; a distance kernel may later make a far source's
numeric contribution small, but that is a LATER, separate mathematical
step, never a structural exclusion here.

## 31. Primary target-scope rule (Parts 13-20)

For each `risk_target_eligible` `ForecastTarget` (already
`1 <= lead_days <= 7`-filtered by `build_forecast_targets`):
`classify_target_primary_scope` tests ONLY spatial membership in the
frozen 25km true domain — no source event-date difference, ST
`eps_time_days`, `MinPts`, cluster role, model score, or kernel value is
ever inspected (`SCOPE-TIME-01..05`, verified — including a real D7
target that stays WITHIN scope, and a structural check that no such
parameter exists on the function at all). `TEMPORAL_UNUSABLE`/`NOISE`-
labeled sources (a concept this module cannot even see —
`EligibleSourcePoint` carries no ST field) still contribute a buffer if
otherwise eligible (`ST-DECOUPLE-03/04`). A WITHIN-scope target is then
assigned to a real scientific grid cell via the SAME deterministic
polygon-containment / lexicographically-smallest-`grid_cell_id`
tie-break already established in `target_assignment.py` — target scope
and target assignment remain two distinct steps (Part 16), never
conflated; the old ST-based classifier's first-match iteration-order
behavior is not preserved in this primary path (Part 18) — there is no
per-component "first match" step here at all, since scope is a single
whole-union geometric test. Nearest-source/nearest-component fields are
always reported as explicitly DESCRIPTIVE ONLY, never as an implied
biological membership field like `local_context_id` (Part 19).

## 32. Real corrected FIT_DEVELOPMENT audit (Parts 22-23, 36.B-D)

`local_data/model_development/primary_target_scope_audit_7a6.json`, full
579-origin real `FIT_DEVELOPMENT` universe, primary (25km) rule:

- **Master D1-D7 risk-eligible targets: 3,947** (unchanged from 7A/7A.5
  — same underlying real corpus).
- **`WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE`: 1,387 (35.1%)**.
- **`OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE`: 2,560 (64.9%)**.
- **`LOCAL_SCOPE_UNRESOLVED`: 0**.

**Consistency check, not coincidence**: 1,387/3,947 = 35.14% is EXACTLY
Checkpoint 7A's own original 25km country-wide coverage figure
(`domain_candidate_audit.csv`) — expected, because the primary spatial
membership test ("is this point within 25km of any eligible source") is
mathematically identical whether or not the true-domain grid-masking
correction is applied (masking only changes which GRID CELLS are
returned for tiling, never the underlying point-in-buffer-union test).
This is real, independent confirmation the implementation is correct.

**By lead day** (`by_lead_day` in the JSON) — the bug-fix signature: a
roughly FLAT ~34-39% WITHIN rate across D1 through D7 (D1: 228/587=38.8%,
D4: 186/535=34.8%, D7: 189/564=33.5%) — no collapse at higher lead days,
confirming the 7A.5 ST-`eps_time_days` bug (which would have
disproportionately suppressed D4-D7 matches) is genuinely fixed, not
just relabeled.

**Real vs. superseded comparison**: 7A.5's buggy diagnostic found 33
(0.84%) local; the corrected primary rule finds 1,387 (35.1%) — a ~42x
difference, entirely attributable to removing the erroneous ST temporal
gate (§25).

## 33. Real true-union grid + projection-safety audit (Part 36.C-D)

Same real run, 25km domain / 5km cells, ALL eligible sources per origin
(matching Part 10's primary-domain definition exactly): **979 of 579
origins had >= 1 eligible source** (9 origins' domains were
`PROJECTION_CONTEXT_UNSAFE` and were skipped for grid TILING only —
their spatial scope classification remained valid, since that uses real
geodesic distance directly, not the projected grid). Real cell counts
across the remaining 570 origins: **mean 980.7, p50 440, p95 3,998, max
7,006 cells/origin, 558,982 cells total**.

This is dramatically smaller than Checkpoint 7A's original bounding-box
figure at the same parameters (mean 8,901 cells/origin) — the true-
domain PER-COMPONENT tiling correction (7A.5 Part 10) turns out to be far
more impactful for a country-wide "all eligible sources" domain than it
was for 7A.5's already-tight local contexts: when an origin's eligible
sources are widely dispersed (further apart than 2 x 25km = 50km, so
their buffers never touch), each now tiles its OWN small local bounding
box independently, instead of the old approach tiling ONE bounding
rectangle spanning the entire dispersed set. This finding is what made
the real full-universe host-reference rebuild (§34) genuinely feasible
within this session, where Checkpoint 7A had found it infeasible.

## 34. Scientific-grid host-reference rebuild (Parts 26-27, 36.E)

[Filled in once the real full-universe rebuild — launched in the
background, ~50 minute estimated real runtime based on the measured
558,982-cell/2-species real extraction volume — completes; see
`local_data/model_development/scientific_grid_host_reference_profile_7a6.json`.]

## 35. Freeze decisions (Part 24, 26)

**`PRIMARY_LOCAL_EVALUATION_DISTANCE_KM = 25.0`**, status
`FROZEN_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE` — **FROZEN** (§29).

**`SCIENTIFIC_GRID_CELL_SIZE_KM = 5.0`**, status
`FROZEN_ENGINEERING_RESOLUTION` — **FROZEN** (Part 24): both 2.5km and
5.0km passed every engineering constraint in 7A.5's real 25km audit (max
590 vs. 161 cells/context there); the predeclared coarsest-qualifying
rule selects 5.0km. Unlike 7A.5 (where this freeze was correctly withheld
because the DOMAIN distance was itself unfrozen), the domain distance is
now genuinely frozen (§29), so Part 26's "never partially claim freeze"
condition is satisfied and both freezes are declared together. 5km is
never described as prediction/biological accuracy — GLW4 (~10km), ERA5
(~25km), GPS quality, and WorldCover/hydrology resolution all remain
independently preserved provenance facts, unaffected by this engineering
choice (Part 25).

## 36. `model_development_protocol_hash` (Part 28) — extended again

`services/model_development/protocol.py` now also covers:
`primary_local_evaluation_distance_km`/`_status`,
`sensitivity_local_evaluation_distance_km`/`_status`,
`scientific_grid_cell_size_km`/`_status`, `primary_scope_rule_version`,
`scope_rationale_document_version`,
`development_target_distance_distribution_already_exposed`,
`all_source_contribution_rule`, and `st_dbscan_gating_policy_version` —
changing any of these changes this hash. Current real value recorded in
`local_data/model_development/model_development_protocol_7a6.json`.

---

# Checkpoint 7A.6.1 — geodesic primary-scope truth, projection-safe multi-component domain, full host-reference rebuild

## 37. Root cause (Parts 1-2): the single-global-CRS assumption itself was unsafe

7A.6's PRIMARY scope decision (`classify_target_primary_scope`) depended
on `DomainGeometry.union_geometry` — a SINGLE AOI-local UTM CRS chosen
from the mean of an ENTIRE origin's eligible-source set, then checked via
`covers(point)`. The real 7A.6 audit found 9 of 579 real origins where
that single-CRS assumption was itself `PROJECTION_CONTEXT_UNSAFE` — the
scope decision for those origins' targets was resting on distorted
geometry. This is now labeled
`SUPERSEDED_SINGLE_ANALYSIS_CRS_ALL_SOURCE_DOMAIN_7A6`
(`services/model_development/host_reference_rebuild.py`) — never
resolved by dropping the 9 origins, excluding distant sources,
loosening the 1% tolerance, using ST-DBSCAN to split sources, or
changing the 25km envelope.

## 38. Primary scope truth is now pure WGS84 geodesic distance (Parts 3-6)

`services/model_development/local_evaluation_scope.classify_target_primary_scope`
no longer accepts (or needs) ANY projected geometry — its scope decision
is computed directly: `min_d_km = min(WGS84 geodesic distance(source,
target) for every eligible active source)`; WITHIN iff
`min_d_km <= 25.0 + GEODESIC_BOUNDARY_TOLERANCE_KM` (`1e-6`, a named
SOFTWARE numerical tolerance — never biological uncertainty, versioned
as `GEODESIC_BOUNDARY_TOLERANCE_VERSION`, included in
`model_development_protocol_hash`). An optional
`ScientificEvaluationDomain` may be supplied for the SEPARATE grid-cell-
assignment step, but it never participates in, and can never override,
scope truth (`GEO-SCOPE-07`, verified with a fabricated always-unsafe
component that still leaves a WITHIN target WITHIN). `GRID_REPRESENTATION_BOUNDARY_MISMATCH`
is a distinct status from scope, never silently converted to OUTSIDE.

## 39. Real row-level regression (Part 5) — clean

`local_data/model_development/primary_scope_row_level_regression_7a61.csv`:
every one of the 3,947 real `(forecast_origin_id, target_event_id)`
D1-D7 risk-eligible rows compared — 7A's original inline geodesic
25km check vs. 7A.6.1's `classify_target_primary_scope` —
**0 row-level disagreements**. Expected: both reduce to the identical
real computation (min geodesic distance to any eligible source vs.
25km), so this is a correctness confirmation, not a coincidence.

## 40. Geodesic source componentization (Parts 7-9) — new `services/geospatial/scientific_domain.py`

Sources are grouped into `SCIENTIFIC_DOMAIN_COMPONENTS` via a PURELY
GEOMETRIC connectivity graph over real geodesic distance — an edge
exists between two sources iff their distance is
`<= 2 * PRIMARY_LOCAL_EVALUATION_DISTANCE_KM = 50km` (two 25km buffers
can only touch/overlap within that separation), using the same
`GEODESIC_BOUNDARY_TOLERANCE_KM` for the edge-threshold comparison.
NEVER ST-DBSCAN — zero `STDBSCANConfig` involvement anywhere
(`COMP-06`), and explicitly never a "transmission cluster," "infection
chain," or "causal outbreak group" (`COMP-07`). Deterministic regardless
of source ordering (`COMP-04`); `component_id` changes iff source
membership changes (`COMP-05`). EACH component gets its OWN local CRS
from ONLY its own sources' coordinates
(`services.geospatial.crs.analysis_crs_for`, reused unchanged) — the
parent `ScientificEvaluationDomain` never claims one global
`analysis_crs`/`bounds_utm`/projected geometry of its own
(`MULTICRS-02`).

## 41. Buffer-radial distortion audit (Part 12) — new diagnostic

Source-source distance distortion alone does not prove a component's
own 25km BUFFER is well-represented. For every source, 8 real geodesic
test points exactly 25km away (bearings 0/45/90/135/180/225/270/315)
are compared against their projected planar distance from that source;
the largest relative error is checked against the SAME predeclared 1%
tolerance (`PROJECTION_DISTORTION_REL_TOL`) — never a separately tuned
number. A component is `is_safe` only if BOTH source-source AND
buffer-radial distortion pass.

## 42. Real 579-origin projection/componentization audit (Part 21) — CLEAN

`local_data/model_development/projection_component_audit_7a61.json`,
full real `FIT_DEVELOPMENT` universe:

- **579/579 origins had eligible sources** (0 with none).
- **3,147 total computational components**: 1,739 singleton, 1,408
  multi-source (mean 5.44 components/origin, p50 3, p95 21, max 25).
- **3,147/3,147 components `is_safe` — 0 UNSAFE components, 0 origins
  with any unsafe component.** The componentized architecture fully
  resolves 7A.6's 9-unsafe-origin problem.
- Max real source-source projection distortion: **0.151%**. Max real
  buffer-radial projection distortion: **0.165%**. Both far below the 1%
  tolerance.
- 21 distinct UTM zones touched ACROSS all components (expected — the
  universe spans 29 countries); every INDIVIDUAL component stayed
  safely within its own local projection.

Per Part 21's own gate ("Required before host rebuild: UNSAFE
components = 0, UNSAFE origins = 0"), this clean result is what unblocks
§45's real full host-reference rebuild.

## 43. Real corrected primary target-scope audit (Parts 22-24) — with correct denominators

`local_data/model_development/primary_target_scope_audit_7a61.json`:

- **`n_intended_origins = 579`, `n_grid_built_origins = 579`,
  `n_grid_blocked_origins = 0`** — the FULL, correctly-labeled
  denominator (7A.6's own report conflated "579 origins with sources"
  with the true 579-origin intended universe; both happen to be 579
  here, but 7A.6.1 reports both explicitly and separately per Part 22 so
  they are never silently assumed equal again).
- Master 3,947 D1-D7 risk-eligible targets → **1,387 (35.1%) WITHIN**,
  **2,560 (64.9%) OUTSIDE**, **0 UNRESOLVED** — identical to 7A.6's
  total (expected: Part 6's scope truth is mathematically unchanged by
  the componentization/grid-representation correction; only the GRID
  geometry changed).
- **`n_within_scope_targets_without_grid_cell = 0`** — every single
  real WITHIN-scope target received a real scientific grid cell (Part
  17's pass gate, satisfied with real data, not merely tested
  synthetically).
- Real cell counts (denominator = 579 `n_grid_built_origins`, Part 22):
  mean **968.7**, p50 434, p95 4,000, max 7,001 cells/origin, **560,853
  cells total**.

## 44. Terminology and status separation (Parts 14, 24)

A component's own projected 25km buffer union is a
`PROJECTION_SAFE_PROJECTED_APPROXIMATION_OF_25KM_GEODESIC_ENVELOPE` —
never called an "exact geodesic buffer." `scope_status` and
`grid_representation_status` are two structurally distinct fields on
`PrimaryTargetScopeResult`; nothing in this codebase ever converts a
`PROJECTION_CONTEXT_UNSAFE`/missing-grid condition into
`OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE` (`GEO-SCOPE-07`,
`TARGETGRID-03`, verified).

## 45. Full scientific-grid host-reference rebuild (Parts 26-28)

`services/model_development/host_reference_rebuild.py`'s
`build_scientific_grid_host_only_snapshot` now builds a
`ScientificEvaluationDomain` per origin (componentized, per-component
local CRS) and pools cells from EVERY safe component
(`evaluation_domain.all_cells()`) — an origin with any unsafe component
is tracked explicitly (`n_unsafe_components`) rather than silently
truncated. `build_scientific_grid_host_reference_development_report`
reports `completeness` (`intended_origin_count`,
`successful_snapshot_origin_count`, `blocked_origin_count`,
`n_origins_with_unsafe_components`, `is_complete`) alongside the pooled
`FactorReferenceProfile` (built with
`require_effective_sample_identity=True` — verified by intercepting the
real call, `HOSTREF7A61-05`, never by source-text search).

[Real results filled in once the background rebuild — launched given
§42's clean 0-unsafe-component gate — completes; see
`local_data/model_development/{scientific_grid_host_reference_profile_7a61.json,host_reference_rebuild_audit_7a61.json}`.]

## 46. `model_development_protocol_hash` (Part 35) — extended again

`services/model_development/protocol.py` now also covers:
`primary_scope_truth_method` (`WGS84_GEODESIC_DISTANCE`),
`geodesic_boundary_tolerance_km`/`_version`,
`scientific_domain_protocol_version`,
`component_edge_distance_km_multiple` (`2.0`),
`grid_truth_separation_policy_version`, `zero_origin_drop_policy`,
`target_grid_completeness_policy`,
`host_reference_sampling_protocol_version`, and
`buffer_radial_audit_version` — changing any of these changes this
hash. Current real value recorded in
`local_data/model_development/model_development_protocol_7a61.json`.

## 47. Bibliography-verification status (Part 36)

`LOCAL_EVALUATION_SCOPE_RATIONALE.md` now explicitly frames 25km as a
**LITERATURE-INFORMED, PRE-MODEL OPERATIONAL LOCAL EVALUATION ENVELOPE**
— never "literature-validated" or "proven." Exact bibliographic
verification (author names, venue, year, DOI) remains an explicitly
open, formal documentation task for before final thesis submission —
never fabricated in this codebase.

---

# Checkpoint 7A.6.2 — identity hardening, D1-D7 surfacing, final host-reference completion

## 48. D1-D7 breakdown (Part 9) — read from the real 7A.6.1 manifest, not guessed

| Day | WITHIN | OUTSIDE | UNRESOLVED | TOTAL |
|---:|---:|---:|---:|---:|
| D1 | 228 | 359 | 0 | 587 |
| D2 | 207 | 367 | 0 | 574 |
| D3 | 212 | 374 | 0 | 586 |
| D4 | 186 | 349 | 0 | 535 |
| D5 | 180 | 368 | 0 | 548 |
| D6 | 185 | 368 | 0 | 553 |
| D7 | 189 | 375 | 0 | 564 |
| **Total** | **1,387** | **2,560** | **0** | **3,947** |

WITHIN rate stays roughly flat (33.5%-38.8%) across every lead day —
consistent with 7A.6's own finding that fixing the ST-`eps_time_days`
bug removed the artificial D4-D7 collapse.

## 49. Scientific identity hardening (Parts 3-6)

`services/geospatial/scientific_domain.py` now separates three distinct
identities (full design: `SCIENTIFIC_GRID_PROTOCOL.md` §13):
`scientific_domain_protocol_hash` (RULES only — no origin/t0/source/
`generated_at`), `ScientificEvaluationDomain.scientific_evaluation_domain_id`
(one concrete instance), and `ScientificGridCell.scientific_cell_id` (one
concrete cell — new optional field, `None` outside the componentized
pipeline). All required invariants verified real-code (`DOMAINID-01..10`,
`CELLID-01..03`): identical settings/ordering → identical identity;
`t0`/coordinates/domain-distance/cell-size/CRS-strategy/projection-
tolerance-version/component-geometry changes → different identity;
`generated_at` never participates (no such parameter exists on any
identity function at all).

**Cache-identity audit (Part 5)**: no scientifically under-specified
persistent cache exists — see `SCIENTIFIC_GRID_PROTOCOL.md` §13's
detail. Zero cache keys required changing.

**No numerical result changed (Part 7)**: this checkpoint is identity/
provenance-only. The 25km envelope, 50km sensitivity registration, 5km
grid, 1% projection tolerance, 50km component-connectivity rule, 8
radial bearings, geodesic scope truth, and all-source hazard eligibility
are all unchanged from 7A.6.1 — verified by rerunning the real audits
(§50) and confirming identical 1,387/2,560/3,947 counts.

## 50. Re-run core real audits after identity hardening (Part 8) — unchanged, as expected, RE-VERIFIED with current code

Rerun for real, using the fully identity-hardened current code (domain-
distance invariant, `scientific_cell_id` propagation, and all): **579
intended origins, 579 with sources, 579 grids built, 0 blocked; 3,147
components, 0 unsafe; 3,947 master targets → 1,387 WITHIN / 2,560
OUTSIDE / 0 unresolved; 0 row-level disagreements; 0 WITHIN targets
without a grid cell.** Exact match to 7A.6.1's numbers and to the
predeclared regression checksum — zero drift from identity hardening,
confirmed by REAL execution, not just code-inspection argument.

## 51. Is the 7A.6.1 host-reference build still valid? (Part 10) — proof of independence

**Proof**: `services/model_development/host_reference_rebuild.build_scientific_grid_host_only_snapshot`'s
exported snapshot dict includes exactly `grid_cell_id`, `centroid_lat`,
`centroid_lon`, `host_density`, `landcover`, `hydrology` per cell — it
NEVER reads or exports `scientific_cell_id`/`scientific_domain_protocol_hash`/
`scientific_evaluation_domain_id` at all (grep-verified: these three
identity fields/attributes do not appear anywhere in
`host_reference_rebuild.py`). `services.factors.reference_profile`'s
pooling/hashing logic keys observations by `sample_support_digest`/
`resolve_static_observation_identity` (tied to real GLW4 raster pixel
support) and by `host_density_total_observation_id` — never by any of
the three hardened identity fields either. Cell CENTROIDS, BOUNDS, and
raster query windows (the only things that actually drive
`extract_grid_cell_density`'s real numerical output) are computed
identically before and after the identity hardening — nothing about how
a cell's `centroid_lat`/`centroid_lon`/`bounds_utm` is computed changed
in this checkpoint.

**Conclusion**: the identity-hardening changes are PROVABLY independent
of the host-reference pooling/hashing computation. The already-launched
7A.6.1 background rebuild (`b6t0md2j5`) — built on the correct,
already-approved componentized geometry — remains valid and is NOT
marked `SUPERSEDED_BY_7A62_IDENTITY_HARDENING`; its real results are
reported directly in §52 once it completes, never re-run merely to
regenerate identical numbers.

## 52. Final scientific-grid host-reference rebuild (Part 11-12) — COMPLETE, real

`b6t0md2j5` completed successfully (61.3 minutes real runtime — longer
than the ~51 minute analytic estimate, consistent with real disk/CPU
contention over a genuinely large 579-origin sweep). **Completeness:
`intended_origin_count=579`, `successful_snapshot_origin_count=579`,
`blocked_origin_count=0`, `unexpected_origin_count=0`, `is_complete=True`.**
`require_effective_sample_identity=True`; **0 legacy pixel-set
identities, 0 query-centroid fallbacks, 0 strict-identity exclusions**
admitted into the primary pool.

- **Status**: `COMPLETE_DIAGNOSTIC`.
- **`reference_profile_hash`**: `5f41f5917bedf61e721e286e5bab031c22bbb687a8157f197dbac751b023e22d`.
- Raw host-total appearances: **509,813**. Unique effective observations:
  **124,520**. Real GLW4 species observations via
  `RASTER_EFFECTIVE_SAMPLE_IDENTITY`: **1,046,426** (0 legacy, 0
  fallback).
- Reference conflicts: **0**. Incompatible strata: **0**.
- Host-density quantiles: `{p05: 1.38, p25: 3.84, p50: 7.63, p75: 20.83,
  p95: 50.32}` animals/km². Log1p quantiles: `{p05: 0.867, p95: 3.938}`.
- **LOG1P clipping** (all 509,813 real transformed observations): 5.21%
  clipped low, 3.07% clipped high overall — country variation remains
  real and un-smoothed (e.g. Thailand 331,797 obs, 6.20% low/0.85% high;
  Nepal 4,328 obs, 0.49% low/89.8% high; Bhutan 4,261 obs, 9.55%
  low/14.95% high — reported honestly, never retuned).

This result is preserved unchanged from `b6t0md2j5` per §51's proven
numerical-independence argument — **not re-run**.
`local_data/model_development/{scientific_grid_host_reference_profile_7a61.json,host_reference_rebuild_audit_7a61.json,clipping_audit_7a61.json}`.

## 53. `model_development_protocol_hash` (Part 13) — extended again, final value

`services/model_development/protocol.py` now also covers
`scientific_cell_identity_version` (new) alongside every 7A.6.1 field.

- **Old 7A.6.1 hash**: `7e91cd22837425007ed20e707081d9b1491a22efe3bbb87615e1137e10b54b13`.
- **Interim (mid-checkpoint) sanity hash**: `7dd78b67537ad5a3fe3f5eb3b691227ba3e886142791bfa79714ceac4becc243`
  — computed after `SCIENTIFIC_DOMAIN_PROTOCOL_VERSION` was bumped
  `7A.6.1`→`7A.6.2`, but BEFORE `scientific_cell_identity_version` was
  added as its own explicit field.
- **Final 7A.6.2 hash**: `603052e0ca2c92c6cfbd06ed35cd5705aa85e8cdd45c8dd1629a926ef0af4eed`.

**Exact reason for the final difference from the interim hash**: adding
the explicit `scientific_cell_identity_version` field to
`ModelDevelopmentProtocol.protocol_dict()` (Part 13's own requirement) —
the domain-distance invariant check (§54) and the `scientific_cell_id`
snapshot-propagation change (§55) are both RUNTIME behaviors, not
protocol-hash payload fields, so neither affected this hash further.
Current real value recorded in
`local_data/model_development/model_development_protocol_7a62.json`.

## 54. Domain-distance duplicate-source-of-truth invariant (Part 3)

`build_scientific_evaluation_domain` now raises `ValueError` if
`abs(primary_local_evaluation_distance_km - grid_config.domain_distance_km)`
exceeds `GEODESIC_BOUNDARY_TOLERANCE_KM` — the two parameters must
describe the identical real distance; a caller can never silently pass
a 25km config alongside a 50km primary distance (or vice versa) and
have `scientific_domain_protocol_hash` describe a different distance
than the actual component/grid geometry (`DOMAINID-11/12/13`, tested).
Every real call site already passed matching values by construction,
so this is a pure safety net — verified to have zero effect on the real
579-origin rerun (§50).

## 55. `scientific_cell_id` propagation and identity-strength audit (Part 7)

`services/model_development/host_reference_rebuild.build_scientific_grid_host_only_snapshot`
now exports `scientific_cell_id` alongside `grid_cell_id` in every
host-only snapshot cell dict (`IDPROP-01`, verified) — purely additive
provenance, never touching any numerical `host_density` value. Proven
structurally (`IDPROP-02`) that `services.factors.{host_transform,reference_profile}`'s
pooling/hashing already depends on a STRONGER, raster-tied identity
(`sample_support_digest`/`resolve_static_observation_identity`) —
`scientific_cell_id` is additive traceability, never load-bearing for
pooling correctness, and never "purely decorative" either (since it now
does propagate for audit purposes).

## 56. Behavioral cache-identity audit (Part 6)

`FileWeatherCache.cache_key_for_request` verified BEHAVIORALLY (not
just by signature inspection): identical request → identical key;
changing latitude, longitude, the temporal window, or the weather model
→ different key; dict key ORDERING alone → same key (`CACHEID-01a..f`).
`services.geospatial.raster.download_and_cache`'s cache identity is
proven, by inspecting every real caller
(`services/geospatial/{host_density/fao_glw.py,hydrology/hydrosheds.py}`),
to be derived exclusively from the DATASET-SPECIFIC source-asset
filename — never any grid/cell/domain parameter — and
`extract_grid_cell_density` re-reads that cached file fresh on every
call using real query bounds, so no separate per-query result cache
exists anywhere in this path that a grid-size/domain-distance change
could go stale against (`CACHEID-02`).

## 57. Old and superseded host-reference attempts, final classification

- **`baqfeoxed`** (7A.6's original single-global-CRS attempt): I
  terminated it mid-computation once its architecture was recognized as
  superseded, before it wrote any output file at all —
  `local_data/model_development/scientific_grid_host_reference_profile_7a6.json`
  was verified never created. Classification: **`OUTPUT_UNAVAILABLE`**
  — nothing exists to preserve/label; it was correctly never used as a
  scientific reference.
- **`b6t0md2j5`** (7A.6.1's componentized attempt, launched before the
  7A.6.2 identity hardening): **`COMPLETED_SUCCESSFULLY`** — see §52.
  Proven numerically independent of the identity hardening (§51) and
  reused directly: **`REUSED_AFTER_PROVEN_NUMERICAL_INDEPENDENCE`**.

## 58. Checkpoint 7B — baseline spatial-rank model development

Full design: `BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md`. Summary:
nested chronological (`build_calendar_year_folds`, reused unchanged),
`FIT_DEVELOPMENT`-only baseline development comparing 24 pre-registered
`B0/B1/B2 x EXPONENTIAL/GAUSSIAN x {5,10,15,25}km` candidates via
`AREA_WEIGHTED_TARGET_PERCENTILE` (domain-overlap-area-weighted,
explicit MIDRANK ties), equal-origin-weighted primary selection metric,
clustered (by-origin) bootstrap uncertainty. Fold-safe host reference
(`FoldSafeHostReference`) prevents validation-fold covariate leakage
into training transform statistics.

**Finalization hardening** (second 7B pass, applied before the real
579-origin run's results were accepted):

1. Fixed a false always-true host-reference config-compatibility gate —
   the real persisted 7A.6.2 `transform_config_hash`
   (`ba43c03780ed7d1fb05f2fce810065cc80753b4013131c7204ef8d1120fbfcb3`,
   loaded from `scientific_grid_host_reference_profile_7a61.json`) is
   now compared against the CURRENT run's own transform-config hash —
   never the same variable assigned to both sides of the comparison.
2. Per-(origin, fold, candidate) domain-coverage records
   (`declared_domain_area_km2`/`scored_domain_area_km2`/
   `missing_domain_area_km2`/`n_incomplete_cells`) are now persisted,
   never computed-and-discarded.
3. Frozen `PRIMARY_SELECTION_ELIGIBLE` coverage-eligibility rule: a
   candidate with ANY `TARGET_SCORE_UNAVAILABLE` row or ANY real missing
   domain area beyond a tiny software floating-point-zero tolerance
   (`SOFTWARE_ZERO_AREA_TOLERANCE_KM2 = 1e-6`, never an invented
   biological/statistical percentage) is
   `PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE` — excluded
   from the selection comparison, reported as
   `INCOMPLETE_DOMAIN_DIAGNOSTIC`, never silently treated as having
   "lost" to a fully-covered candidate.
   `HOST_DEPENDENT_BASELINES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_DOMAIN_SUPPORT`
   is the required wording whenever this applies.
4. Unique WITHIN-scope target counts
   (`n_unique_validation_targets_within_scope`,
   `n_unique_evaluable_origin_target_events`) are now reported
   separately from the 24x-multiplied candidate-target row counts
   (`n_candidate_target_evaluation_rows`).
5. Every validation origin's outcome is now tracked explicitly
   (`VALIDATION_ORIGIN_READY`/`_RAW_SNAPSHOT_MISSING`/
   `_NO_ELIGIBLE_SOURCE`/`_GRID_UNAVAILABLE`) with an asserted
   denominator invariant (intended = ready + blocked) — no intended
   validation origin can silently vanish.
6. Candidate scientific identity now binds
   `BASELINE_EVALUATION_PROTOCOL_HASH` (percentile definition, MIDRANK
   tie semantics, TOP5/TOP10 thresholds, equal-origin aggregation rule,
   D1-D7 horizon, primary 25km scope protocol, coverage-eligibility rule
   version) — not merely the candidate's own baseline/kernel/scale/
   host-transform parameters. A legacy (7B.1)-to-current (7B.2)
   `IDENTITY_ONLY_RESULT_REMAP` was proven bijective over the same 24
   underlying candidates (never requiring a numerical rerun for a
   metadata-only identity change).
7. Target dedup now keys directly on
   (`forecast_origin_id`, `target_event_id`) rather than trusting the
   joined `target_id` display string as a proven collision-free
   encoding.
8. `FrozenBaselineModelSpecification` now names
   `scientific_grid_config_hash` (config only) distinctly from
   `scientific_domain_protocol_hash`/`_version` (the full 7A.6.2
   scientific-domain protocol) and `model_development_protocol_hash_7a62`
   — the original field name conflated a config hash with the entire
   protocol identity.
9. A disk-persisted, gitignored raw host-snapshot cache
   (`local_data/model_development/7b/raw_host_snapshot_cache/`), keyed
   by `ScientificEvaluationDomain.scientific_evaluation_domain_id` (an
   identity that already encodes the scientific-domain protocol hash,
   grid config hash, origin/t0, and every eligible source), means the
   ~hour-long raw GLW extraction pass is never repeated once a scientific
   identity is already cached — automatically invalidated by construction
   whenever grid/domain/source protocol changes the key.

Real 579-origin final results: see §59 / `DATA_AUDIT.md` §83.

## 59. Checkpoint 7B — real 579-origin final results (PASS)

Selected: `CAND:B0_DISTANCE_ONLY:EXPONENTIAL:25KM:NONE:a48d9efcbb587cf1`
(B0, EXPONENTIAL, 25km, no host transform),
`frozen_spec_hash=6bb8f67a7bc1188be324bf0a58e2399ed87df619b96c5a0db0ba5a3191794950`.
5/6 folds usable (`FOLD:2018` insufficient prior history); 0 blocked
validation origins across 532 ready origins. 1,302 unique WITHIN-scope
validation origin-target events (reconciled exactly against the
3,947-target/1,387-WITHIN master audit — see §84.1). All 8 B0 candidates
`PRIMARY_SELECTION_ELIGIBLE` (0 missing coverage); all 16 B1/B2
candidates `PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE`
(real GLW support gaps, 121/1181 targets each) — selection note
`HOST_DEPENDENT_BASELINES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_DOMAIN_SUPPORT`,
never interpreted as B0 predictively defeating B1/B2. Pooled D1-D7:
mean origin-balanced area-weighted target percentile 62.034, TOP10
0.2024, TOP5 0.1145, n=277 origins. Origin-clustered 95% bootstrap CI
for the mean percentile: [59.77, 64.39].

## 60. Checkpoint 7C — wind-anisotropic augmentation of the frozen 7B baseline

Full design: `ENVIRONMENTAL_WIND_MODEL_DEVELOPMENT_PROTOCOL.md`. Summary:
`FIT_DEVELOPMENT`-only, host-free development comparing the frozen 7B B0
anchor (`C0_FROZEN_B0_ISOTROPIC`) against 8 wind-anisotropic candidates
(`CW_WIND_ANISOTROPIC`: `{MODULATING, ANGULAR_NORMALIZED} x {0.25, 0.5,
1.0, 2.0}` anisotropy strength), reusing the EXISTING
`services/hazard/anisotropy.py` primitive and real, t0-safe ERA5 wind
(`services/geospatial/weather/era5.py`) — never a new anisotropy
formula, never real-time/future weather. Host,
`environmental_suitability_factor`, `water_context_factor`, and
`source_strength_factor` all remain excluded from every 7C primary
candidate (still `NOT_PRIMARY_ELIGIBLE`/`NOT_YET_SCIENTIFICALLY_DEFINED`/
`NOT_SELECTED` — see the protocol doc's factor readiness table). Reuses
7B's entire evaluation/selection stack unchanged (same percentile
metric, MIDRANK ties, TOP5/TOP10, equal-origin aggregation, coverage
eligibility rule) plus a new paired-delta-vs-anchor comparison
(origin-matched, origin-clustered bootstrap). Real results: see
`DATA_AUDIT.md` §84.

## 61. Checkpoint 7D / 7D.1 — frozen held-out-from-fitting evaluation of C0, WITH pre-final predictive subset exposure disclosed

The ONLY frozen candidate,
`C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8`
(`frozen_checkpoint_7c_spec_hash=ef3511d3527da6d85598846c0d828509ed07f134ac8d987c3d5702b507505a6d`),
evaluated against the real 229-origin `HELD_OUT_FROM_MODEL_FITTING`
universe — no candidate registry, no tuning, no weather/host input (C0
needs neither). `heldout_protocol_7d.assert_frozen_c0_model` verified
the on-disk 7C spec matched before any repository access;
`pre_evaluation_freeze_manifest.json` and `heldout_exposure_disclosure.json`
were persisted before the FINAL 229-origin run's held-out metrics were
computed (Parts 2/4/18).

**Correction (Checkpoint 7D.1)**: this evaluation is NOT single-shot. A
40-origin predictive sanity subset (`heldout[:40]`) was scored and its
metrics inspected BEFORE the formal test suite and the final freeze
manifest existed — disclosed in full at
`local_data/model_evaluation/7d/pre_final_40_origin_sanity_exposure.json`,
never hidden. An independent filesystem-mtime audit
(`procedural_exposure_correction_7d1.json`) proved no numerically
load-bearing scientific code (scoring, target-scope, domain, source
selection, metric/threshold definitions) changed between that exposure
and the final run — `NO_POST_EXPOSURE_MODEL_RETUNING_DETECTED`. The
final 229-origin numbers below are therefore unretuned but were NOT the
first predictive look at held-out data.

**Real result** (label:
`FROZEN_HELD_OUT_FROM_FITTING_EVALUATION_WITH_PRIOR_DATASET_AND_PRE_FINAL_PREDICTIVE_SUBSET_EXPOSURE_DISCLOSED`
— never "single-shot," "external validation," or "blind"): 229/229
origins `VALIDATION_ORIGIN_READY`, 0 blocked. 588 real D1-D7 target
rows; 323 `WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE` (0 unresolved, 0
without a grid cell) = 126 origins with >=1 primary target + 103 with
zero (proven exactly, `heldout_origin_participation_audit_7d1.json`).
C0 coverage verified complete for all 126 contributing origins (0
missing domain area, 0 `TARGET_SCORE_UNAVAILABLE`); the 103 zero-target
origins carry `NOT_APPLICABLE_NO_PRIMARY_TARGET`, never claimed as
"coverage verified" since C0 was never scored there. Pooled D1-D7: mean
origin-balanced area-weighted target percentile **73.847** (development:
62.034), TOP10 **0.2919** (development: 0.2024), TOP5 **0.1739**
(development: 0.1145), n=126 origins, 323 unique targets.
Origin-clustered 95% bootstrap CI: mean [70.51, 77.11], TOP5 [0.127,
0.223], TOP10 [0.235, 0.352]. Target-event-clustered sensitivity CI
(n=122): mean [66.91, 75.79], TOP5 [0.102, 0.218], TOP10 [0.200, 0.345].
Held-out performance was numerically higher than development on every
primary metric — reported descriptively only, under disclosed pre-final
exposure (never tuned on, never overclaimed as proof of superior
generalization; no pre-specified significance test was run).
Country-level breakdown (8 countries, `descriptive_only=true`, several
with very small n) never used to modify the model. Runtime: 15.6s. Full
design/results: `heldout_protocol_7d.py`, `heldout_run_7d.py`,
`DATA_AUDIT.md` §85-88.

**Scope-conditional interpretation (Checkpoint 7D.1.2)**: only 323 of
588 real D1-D7 target events (55.3%) fell inside the frozen 25km
declared local evaluation scope, and only 126 of 229 held-out origins
(55.0%) contributed a primary evaluable target. **The pooled 73.847
percentile is therefore conditional on WITHIN-scope inclusion — never
an unconditional "overall outbreak-prediction accuracy," and the 25km
envelope is an operational evaluation envelope, never a biological
transmission radius.** See `scope_and_participation_summary_7d12.json`.
Additionally, `availability_protocol_identity = RETROSPECTIVE_PROXY_T0_INVARIANT`
— the result is retrospective held-out-from-fitting spatial-ranking
evidence, never prospective operational validation or real-time
production accuracy (`VALIDATION_PROTOCOL.md` §11).

## 62. Checkpoint 7E / 7E.1 — frozen Sri Lanka geographic-transfer case study of C0, with non-predictive semantic and evidence-seal hardening

The SAME frozen candidate as 7D
(`C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8`,
`frozen_checkpoint_7c_spec_hash=ef3511d3527da6d85598846c0d828509ed07f134ac8d987c3d5702b507505a6d`),
replayed on the real `SRI_LANKA_TRANSFER_CASE_STUDY` origin universe --
never re-selected, never re-tuned. `sri_lanka_protocol_7e.assert_frozen_c0_model_7e`
reuses Checkpoint 7D's own freeze assertion directly.

**Real reconciliation** (`sri_lanka_origin_universe_audit.json`): 7 raw
historical Sri Lanka records -> 6 model-candidate dedup-resolved
episodes (1 excluded: `FAO_EMPRESI_CSV:...:002066`, `REVIEW_LOW`
dedup status, unresolved 8-day date discrepancy with
`WAHIS_PDF:Event_3473.pdf:002408`, already documented in
`HISTORICAL_CHRONOLOGY_AUDIT.md`) -> 5 forecast origins (two
same-day 2020-09-28 episodes collapse into one origin) -> 5
`SRI_LANKA_TRANSFER_CASE_STUDY` origins, all 5 `VALIDATION_ORIGIN_READY`,
0 blocked.

**Temporal/availability quality** (`sri_lanka_temporal_availability_audit.json`):
all 6 model-candidate records carry `availability_quality=EVENT_DATE_PROXY`
(the recorded outbreak/event start date, used as `EVENT_DATE_PROXY`
under the already-frozen `RETROSPECTIVE_PROXY` temporal protocol --
never `ACTUAL`, and never claimed as guaranteed exact biological onset
truth). Real `operational_availability_date`/`operational_availability_quality`
are genuinely `None`/`UNKNOWN` for every record -- disclosed honestly,
never manufactured. All 6 records share `confirmation_date=2020-12-18`
(a single batch confirmation ~2-3 months after the individual recorded
event-start dates) and `report_date=2023/07/28` (the WAHIS PDF
publication date, ~3 years after the events); as a descriptive
consequence (not the protocol-selection justification, which is the
already-frozen retrospective-proxy protocol itself), using the shared
confirmation date would collapse the recorded temporal structure of
these six records onto a single date.

**GPS quality** (`sri_lanka_geolocation_quality_audit.json`): all 6
model-candidate records `EXACT`. One (`002408`) carries
`coordinate_collision_status=SHARED_WITH_UNRESOLVED` (shares
coordinates with the excluded, unresolved `002066`) -- never treated as
proof of duplication; `002408` remains its own distinct episode.

**Real target-scope result**: of 2 real D1-D7 risk-eligible targets, only
**1** fell inside the frozen 25km declared local evaluation scope
(`WAHIS_PDF:Event_3473.pdf:002408`, 12.43km from its origin's sole
eligible source, D2); the other (`002411`, ~87-95km from its origin's
two eligible sources) was correctly `OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE`
-- never used to justify widening the envelope. C0 fully
`PRIMARY_SELECTION_ELIGIBLE` (0 missing coverage) for the 1 evaluable
origin.

**Result**: `n_contributing_origins=1 < 10` -- **`SMALL_SAMPLE_DESCRIPTIVE_ONLY`**,
never a bootstrap CI presented as robust evidence. Single real target
percentile: **61.104** (vs. development 62.034, held-out-from-fitting
73.847 -- descriptive context only, no significance claimed, no model
selection performed). **Final classification:
`SRI_LANKA_TRANSFER_CASE_STUDY_LIMITED_BY_SMALL_SAMPLE`.** D8-D14 exists
in the broader PISTES product/research roadmap as an exploratory output
horizon, but no frozen Checkpoint 7E D8-D14 case-study evaluation
protocol and target-scoring implementation had been preregistered
before the Sri Lanka D1-D7 result -- the evaluation horizon was
therefore never extended post hoc after observing sparse D1-D7 support
(Checkpoint 7E.1 correction of an earlier overly broad "no D8-D14
protocol exists anywhere" claim). Runtime: 0.29s. Full design/results:
`sri_lanka_protocol_7e.py`, `sri_lanka_run_7e.py`,
`CHECKPOINT_7E_EVIDENCE_SUMMARY.json`, `DATA_AUDIT.md` §89-90.

## 63. Checkpoint 8A — spread-risk direction identifiability, mathematical semantics, and readiness audit

Methodology/readiness only -- no direction model fit, no parameter
tuned, no held-out/Sri Lanka direction performance scored, 7B-7E not
reopened, C0 unchanged. Confirmed
`FROZEN_C0_HAS_NO_INTRINSIC_DIRECTIONAL_TRANSMISSION_PARAMETER` against
the live registry (`anisotropy_mode=None`, `anisotropy_kappa=None` on
`C0_FROZEN_B0_ISOTROPIC`). Audited the existing anisotropy equation
(`services.hazard.anisotropy`) and confirmed
`wind_scoring_7c.score_origin_candidates_7c` already applies alignment/
anisotropy per source, inside the per-source loop, before summation --
no mathematical defect found, nothing corrected. Froze a bearing
convention (0=N/90=E/180=S/270=W, clockwise, `[0,360)`, `0.0` a valid
direction, `None` the only "undefined" sentinel), the wind FROM/TO
conversion, zero-distance/zero-resultant exclusion semantics, and a
`directional_clarity` agreement measure (never confidence/probability)
in two new, isolated, non-predictive modules:
`services/model_development/{direction_readiness_8a.py,direction_protocol_8a.py}`
-- neither imports nor is imported by any C0/CW scoring path. Audited
(never selected) three candidate direction methods: geometric
source-resultant tendency (`ELIGIBLE_FOR_8B_DEVELOPMENT` -- real,
tested, no data dependency, but `DIRECTION_WEIGHT_NOT_YET_SCIENTIFICALLY_DEFINED`,
so it may only be called a geometric/relative-risk tendency, never
spread direction), wind-informed hazard resultant
(`AUXILIARY_DIRECTION_METHOD_BLOCKED_BY_INPUT_COVERAGE` -- real 7C.1
coverage was 192/277 REAL wind, 85/277 (~30.7%)
`WEATHER_INPUT_UNAVAILABLE`, all 8 CW candidates
`PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE`), and a
hazard-surface gradient direction (`DIRECTION_METHOD_NOT_YET_SCIENTIFICALLY_IDENTIFIABLE`
-- no existing implementation anywhere). Direction evaluation-truth
definition explicitly `DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN`.
`direction_readiness_protocol_hash_8a() = c896048f4bc11264d17385240898ba6566b843a3f5a56f7fc8c21ae802187160`
(never binds a timestamp). 26 new tests
(`tests/test_checkpoint_8a_direction_readiness.py`), full backend
regression 1230/1230 passed, 0 failed, 0 skipped. **Final
classification: `GEOMETRIC_DIRECTION_ONLY_READY_NOT_SPREAD_DIRECTION`.**
Full design/results: `DIRECTION_MODEL_PROTOCOL.md`,
`DIRECTION_READINESS_AUDIT.md`, `DIRECTION_CODE_READINESS_AUDIT.md`.

## 64. Checkpoint 8A.1 — resultant scale-invariance, non-finite/unit-vector validation, calm-wind consistency, method-readiness correction (`CHECKPOINT_8A1_MATHEMATICAL_HARDENING`)

No predictive result changed; C0 unchanged; 7B-7E not reopened; no
direction model fit; no directional weight selected. Fixed a genuine
mathematical defect: the original absolute `RESULTANT_MAGNITUDE_EPSILON`
made bearing/clarity availability depend on the arbitrary scale of
`w_j_i`; replaced with the scale-invariant ratio `magnitude /
total_mass` (proven under `c in {1e-12,1,1e12}`). Kept three
numerical tolerances explicitly separate and never conflated: generic
bearing zero semantics (exact `(0,0)` only), `RESULTANT_RELATIVE_CANCELLATION_EPSILON`
(`1e-9`, dimensionless, resultant-only), and the meteorological calm-
wind threshold -- `wind_to_bearing_from_components` now reuses
`hazard.anisotropy.CALM_WIND_EPSILON_M_S` directly (no duplicated
literal), verified to agree with `compute_meteorological_alignment` at
the exact boundary. Every numerical input now fails closed on
`NaN`/`+-inf` (`reject_non_finite`, reused not reimplemented). Usable
`t_hat` vectors are validated as genuine unit vectors
(`UNIT_VECTOR_NORM_TOLERANCE=1e-6`, never silently renormalized);
zero-distance terms must carry exactly `(0.0, 0.0)`.
`directional_clarity in [0,1]` is guaranteed, with only sub-`1e-9`
float overshoot clamped. Corrected a genuine semantic contradiction in
the Method-A readiness matrix (`scientifically_defined=True` alongside
an undefined weight) into four explicit, non-contradictory statuses
(`geometry_definition_status`, `aggregation_framework_status`,
`directional_weight_status`, `complete_method_specification_status` --
`INCOMPLETE_PENDING_WEIGHT_DEFINITION`); Method A remains eligible only
for `FIT_DEVELOPMENT`-only 8B methodology development, never presented
as evidence a spread-direction method already exists. Old
`direction_readiness_protocol_hash_8a()` verified unchanged
(`c896048f4bc11264d17385240898ba6566b843a3f5a56f7fc8c21ae802187160`,
`HISTORICAL_CHECKPOINT_8A_INITIAL_READINESS_HASH`); new hardened
`direction_readiness_protocol_hash_8a1() = 8aa69a68f27980134caa3cb1c5c96f5b66ab1e41274bc9def38a9aa5a627869e`
(never binds a timestamp). 44 new tests
(`tests/test_checkpoint_8a1_direction_hardening.py`), all 26 original
8A tests still pass unmodified. Full backend regression: 1274/1274
passed, 0 failed, 0 skipped. **Final classification (re-affirmed):
`GEOMETRIC_DIRECTION_ONLY_READY_NOT_SPREAD_DIRECTION`.**

## 65. Checkpoint 8B — frozen-C0-derived local geometric relative-risk tendency field

No direction model fit; no directional weight tuned; no direction
candidate selection run; no future-target angular error calculated; no
held-out/Sri Lanka direction scoring; C0 unchanged; 7B-7E/8A/8A.1 not
reopened. Part 0 pre-flight (`verify_8a1_preflight`) loaded the LIVE
`direction_readiness_protocol_dict_8a1()` and confirmed every depended-
on semantic is actually bound in it, not merely that the hash string
matches.

Directional weight `w_j_i = K_C0(d_j_i) = exp(-d_j_i/25km)` is the
EXACT frozen C0 per-source kernel contribution
(`services.hazard.kernels.evaluate_kernel`, the same
`FROZEN_KERNEL_FAMILY`/`FROZEN_KERNEL_SCALE_KM` constants C0's real
scorer uses) — `DIRECTIONAL_WEIGHT_DERIVED_FROM_FROZEN_C0_NO_NEW_PARAMETER`,
never a fitted parameter. New reusable, DB-independent service
`services/direction/c0_geometric_tendency.py::compute_cell_direction_tendency(cell,
sources)` — no target/future-outbreak parameter anywhere in its public
surface (verified structurally). Reuses the frozen Checkpoint 8A.1
`DirectionalMassTerm`/`compute_resultant_vector` primitives directly
for bearing/cancellation/clarity — no second implementation. A
zero-distance source retains its full `K(0)=1` scalar C0 mass in
`total_scalar_c0_mass` (never deleted) but is excluded from the
directional resultant sum (never a fabricated direction);
`directional_mass_coverage_status` is determined structurally, never a
tuned threshold. Five source-count fields kept explicitly distinct
(`n_total_eligible_sources`, `n_positive_c0_weight_sources`,
`n_directionally_defined_sources`,
`n_zero_distance_undefined_direction_sources`,
`n_positive_weight_directionally_defined_sources`). No angular-
performance metric of any kind is computed anywhere in 8B (circular-
evaluation prohibition); `DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN`
remains unresolved.

New `services/model_development/direction_protocol_8b.py` freezes
`direction_method_protocol_hash_8b() = 9d111741d303d1dcf73c2a624b99c3fa7c3aaa2020d52d3254d5d744e963f32d`
(binding the 8A.1 parent hash, the frozen C0 identity, the directional-
weight identity, and every 8B semantic; never a timestamp), and reuses
7D/7E's own `assert_frozen_c0_model` hard-freeze gate directly.

**Real FIT_DEVELOPMENT-only structural audit** (`smoke_tests/run_direction_structural_audit_8b.py`,
never held-out/Sri Lanka, no target outcomes): 579/579 real
`FIT_DEVELOPMENT` origins processed, 560,853 real grid cells. **The
Part-3 scalar identity (`total_scalar_c0_mass == real C0 cell score`)
held exactly on all 560,853 cells — `n_invariant_failures=0`** —
cross-checked directly against `wind_scoring_7c.score_origin_candidates_7c`,
not merely asserted. `direction_status_counts`:
`DIRECTION_AVAILABLE: 560853` (0 cancelled, 0 no-mass in this real
corpus). `coverage_status_counts`: `COMPLETE_DIRECTIONAL_MASS_COVERAGE: 560853`
(`n_exact_zero_distance_cases=0`). `directional_clarity`: min
`0.0014`, median `0.709`, max `1.0`. Runtime 274.8s (pure geometry, no
weather I/O).

31 new tests (`tests/test_checkpoint_8b_direction_field.py`). Full
backend regression: 1305/1305 passed, 0 failed, 0 skipped. **Final
classification: `C0_DERIVED_LOCAL_GEOMETRIC_RISK_TENDENCY_FIELD_READY_NOT_PREDICTIVE_SPREAD_DIRECTION`.**
Full design: `DIRECTION_8B_PROTOCOL.md`.

Checkpoint 8B.1 (`CHECKPOINT_8B_ARTIFACT_PATH_AND_PROVENANCE_REPAIRED`)
relocated the four real 8B artifacts byte-for-byte from an accidental
component-nested `local_data` path to the canonical repository-root
`local_data/model_development/8b_direction/` — no scientific value
changed. 10 new tests, full regression 1315/1315. Full record:
`DATA_AUDIT.md` §94.

## 66. Checkpoint 8B.2 — analytical negative-gradient equivalence, sign/semantic hardening, method-identity binding

No real structural-audit rerun; no C0 rescoring; no numerical vector
result changed; no direction parameter fit/tuned. Proved analytically
(never merely asserted) that Checkpoint 8B's vector field equals
`V(x) = -25km * grad(C0(x))` — `grad_x d_j(x) = t_hat_j(x)` almost
everywhere (standard result for the gradient of a distance function
from a fixed point) except at `d=0` and the geodesic cut locus (never
reached at this kernel scale), and matches the frozen EXPONENTIAL
kernel's own derivative `dK/dd = -(1/25)*K` by the chain rule. A
fourth, real exception was discovered empirically during test
development: `source_to_cell_unit_vector`'s departure-azimuth-at-
source convention (unchanged since Checkpoint 5) differs from the true
local gradient tangent at the cell by the geodesic's meridian-
convergence angle (~0.0012 degrees for a 3km geodesic) — small,
sub-percent, real, documented, never hidden. `V` points DOWN the C0
gradient (away from sources, decreasing C0); positive `grad(C0)`
points toward sources (increasing C0) — exactly 180 degrees apart when
nonzero; `V` is never described as direction of increasing risk or
predicted/validated spread direction.

Historical output terminology
(`HISTORICAL_CHECKPOINT_8B_OUTPUT_TERMINOLOGY = C0_DERIVED_LOCAL_GEOMETRIC_RELATIVE_RISK_TENDENCY`)
preserved unchanged — the actual `direction_semantics` field value
never changed. New active, sign-explicit terminology:
`ACTIVE_OUTPUT_SEMANTICS_8B2 = C0_DERIVED_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY`.
Reconciled 8A's Method C (`HAZARD_SURFACE_GRADIENT_DIRECTION`,
correctly `NOT_YET_SCIENTIFICALLY_IDENTIFIABLE` at the time) as a
later-discovered analytical consequence of 8B's independently-chosen
weight, never a claim 8A was wrong. Documented clarity's analytical
relation (`directional_clarity = 25*||grad log(C0)||` under complete
coverage away from `d=0` only — never claimed under partial coverage).
Closed a real method-identity gap (`method_id`/`method_version` never
bound in the historical 8B protocol hash, left unclosed there;
`method_version="8B.2"` vs. the coincidentally-named production
`METHOD_VERSION_8B="8B.1"` string, unrelated to the Checkpoint 8B.1
artifact-path repair) in a NEW, additive
`direction_method_protocol_hash_8b2() = d8dd12da100f3446f29967dcd221d25112669703ab3d201333a17a07ad89f906`
— the historical
`direction_method_protocol_hash_8b() = 9d111741d303d1dcf73c2a624b99c3fa7c3aaa2020d52d3254d5d744e963f32d`
left completely untouched and reverified unchanged.

18 new tests (`tests/test_checkpoint_8b2_negative_gradient.py`). Two
genuine test-authoring bugs caught and fixed during development, not
hidden: an unrealistically tight finite-difference tolerance that
didn't account for the real meridian-convergence effect above, and an
inverted expected value in the 180-degree bearing-opposition check.
Full backend regression: **1333/1333 passed, 0 failed, 0 skipped**
(1315 baseline + 18 new). **Final classification:
`C0_DERIVED_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY_FIELD_READY_AS_DESCRIPTIVE_NOT_PREDICTIVE_SPREAD_DIRECTION`.**
Full design: `DIRECTION_8B_PROTOCOL.md` §19.

## 67. Checkpoint 8B.3 — cell-local geodesic tangent-frame correction, exact C0 negative-gradient consistency, active method/version identity

No C0 change; no risk-model rerun; no target outcomes used; 7B-7E not
reopened. **Corrected a real geodesy defect** Checkpoint 8B.2 found but
did not numerically fix: `source_to_cell_unit_vector` (historical,
unchanged since Checkpoint 5) expresses `t_hat` in the SOURCE's local
tangent frame (departure azimuth `az12`); the gradient of a distance
function at cell `x` is a tangent vector AT `x` and must use the
CELL's own frame. New `services.geospatial.distance.source_to_cell_tangent_at_cell`
computes the correct cell-arrival bearing `(az21 + 180) mod 360`
(`az21` = `pyproj.Geod.inv`'s back azimuth), verified directly against
independent `pyproj.Geod.inv` calls. New ACTIVE service
`services.direction.c0_cell_local_tendency_8b3.compute_cell_direction_tendency_8b3`
aggregates all source terms for a cell in that SAME cell's frame
before summation (the key correction) — historical
`c0_geometric_tendency.compute_cell_direction_tendency` untouched for
provenance. Directional weight unchanged
(`w_j_i=exp(-d_j_i/25km)`, same kernel evaluator, no new parameter).

**Corrected identity holds to convergent numerical precision**: a real
finite-difference convergence table (step=0.1km/0.01km/0.001km) shows
relative error shrinking ~100x per 10x step reduction (textbook
`O(step^2)` central-difference convergence to zero bias) — down to
<1e-5 — unlike the historical field's persistent ~2e-4 to 7e-4
relative plateau that never shrank with step size (a real frame bias,
not truncation error).

**8B.2 honestly reclassified** (not deleted, not called fraudulent):
`CHECKPOINT_8B2_ANALYTICAL_IDENTITY_OVERSTATED_DUE_TO_SOURCE_FRAME_VS_CELL_FRAME_MISMATCH`
— the historical numerical field is re-described precisely as
`SOURCE_DEPARTURE_FRAME_GEOMETRIC_RESULTANT`, only approximately
aligned with the true cell-local gradient, never exactly, and never
called predictive spread direction in either checkpoint. Historical
`direction_method_protocol_hash_8b()` and
`direction_method_protocol_hash_8b2()` both reverified byte-for-byte
unchanged; all four historical 8B local artifacts reverified byte-
identical before and after this checkpoint's real rerun.

**Real FIT_DEVELOPMENT structural audit legitimately rerun** for the
NEW method only (geometry-only, no target outcomes, no tuning, C0
unchanged — explicitly permitted): 579/579 real origins, **560,853**
real cells, `DIRECTION_AVAILABLE`/`COMPLETE_DIRECTIONAL_MASS_COVERAGE`
for all 560,853, `n_invariant_failures=0`, clarity median
`0.709082530806226`. Honest historical-vs-active diff over all
560,853 cells: bearing delta median `0.045°`/max `25.4°` (consistent
with angular instability near vector cancellation, where bearing is
inherently ill-conditioned — the mechanism was reproduced
synthetically; **correction, Checkpoint 9A Part 0.A**: the aggregate
audit did not retain per-cell outlier detail to prove every large-delta
cell was actually near-cancellation, only that the mechanism is
consistent with it), resultant-component delta small throughout
(median `0.00075`, max `0.018`). C0 was NOT refitted/retuned/
predictively re-evaluated — deterministic FIT_DEVELOPMENT C0 scores
were recomputed only as a structural scalar-identity check
(**correction, Checkpoint 9A Part 0.B**, replacing an earlier "C0 was
never recomputed" overclaim).

New, ACTIVE, self-identifying output: `method_id=C0_CELL_LOCAL_NEGATIVE_GRADIENT_TENDENCY`,
`method_version=8B.3`,
`direction_semantics=C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY`,
`coordinate_frame=CELL_LOCAL_EAST_NORTH_TANGENT_FRAME` — never
silently returning the historical 8B.1 identity. New
`direction_method_protocol_hash_8b3() = dc3b245aa8ea6748c8abf8bcf0c56db75aca34a6118b02776b9c5490fa6c0282`
(binds the 8A.1 parent hash, historical 8B/8B.2 hashes/correction
provenance, method id/version, active semantics, coordinate frame,
geodesic convention, arrival-bearing formula, and every other 8B.3
semantic; never a timestamp).

26 new tests (`tests/test_checkpoint_8b3_cell_local_correction.py`).
Full backend regression: **1359/1359 passed, 0 failed, 0 skipped**
(1333 baseline + 26 new). **Final classification:
`C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY_FIELD_READY_AS_DESCRIPTIVE_NOT_PREDICTIVE_SPREAD_DIRECTION`.**
Full design: `DIRECTION_8B_PROTOCOL.md` §20.

## 68. Checkpoint 9A — apparent local spread-front rate methodology freeze, FIT_DEVELOPMENT readiness, target-level de-pseudoreplication

No S0 aggregate computed/frozen as the system rate (Checkpoint 9B
only); no S1; no nominal reach numeric; no held-out/Sri Lanka rate
data; C0/8B.3 unchanged; no direction/wind input in the rate formula
(verified structurally). Two 8B.3 reporting corrections applied first
(wording only, no rerun) — see `RATE_MODEL_PROTOCOL.md` §0.

Frozen formula: `v_obs(o,k) = d_min(o,k) / lead_days(o,k)` km/day,
`d_min` = geodesic minimum over ALL eligible t0 sources
(`local_evaluation_scope.classify_target_primary_scope`, reused
directly). Nearest source =
`NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE` only, never
causal. Reuses the SAME frozen 25km `FROZEN_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE`
every prior checkpoint uses (no new threshold searched); D1-D7 only,
never rescued by D8-D14. FIT_DEVELOPMENT-only firewall
(`assert_fit_development_only`) verified to hard-reject held-out/Sri
Lanka before any repository access. De-pseudoreplication frozen:
`target_level_v(target_event_id) = MEDIAN` of that target's valid
`v_obs` rows; future `S0 = MEDIAN of target_level_v across UNIQUE
target_event_id` — never the median of raw origin-target rows.
Zero-distance observations retained honestly (never epsilon-
substituted); GPS/availability quality reused verbatim and reported,
never used to silently exclude inconvenient values; no clipping/
winsorization. Predeclared Checkpoint 9B bootstrap plan: unique
`target_event_id` as the resample unit, seed 42, n=1000, 95%
percentile interval.

New `services/model_development/{rate_protocol_9a.py,rate_readiness_9a.py}`
— `rate_readiness_protocol_hash_9a() = 326427b08f5c43b9708409ae112460e8f0804db0c972a007caaae8ffca3b58ac`
(printed BEFORE any real value was summarized; never a timestamp).

Real FIT_DEVELOPMENT readiness run (`smoke_tests/run_rate_readiness_9a.py`,
5.6s): 579/579 origins, all with eligible sources; 3947 raw D1-D7
target rows, 0 not-risk-eligible, 3947 after dedup (no duplicates
found); 1387 WITHIN / 2560 OUTSIDE / 0 unresolved (reconciles exactly);
1387 valid v_obs; 371 unique target_event_id (observations-per-target
median 4, max 7); lead-day counts D1-D7 sum to 1387 exactly; 12
zero-distance observations. Sample-size status:
`SAMPLE_SIZE_NOMINALLY_SUFFICIENT_FOR_MEDIAN_ESTIMATION`. Diagnostic-
only distributions (`DEVELOPMENT_RATE_DATASET_DIAGNOSTIC`, never
called the system rate): episode-target v_obs median 3.68 km/day
(n=1387), target-level median v median 3.95 km/day (n=371).

25 new tests (`tests/test_checkpoint_9a_rate_readiness.py` — 23
methodology/freeze tests plus 2 evidence-summary consistency/SHA256
checks). Full backend regression: **1384/1384 passed, 0 failed, 0
skipped** (1359 baseline + 25 new). **Final classification:
`APPARENT_LOCAL_SPREAD_FRONT_RATE_S0_DEVELOPMENT_DATASET_READY_FOR_9B_ESTIMATION`.**
Full design: `RATE_MODEL_PROTOCOL.md`.

## 69. Checkpoint 9A.1 — pre-9B S0 numeric-exposure disclosure, arbitrary sample-threshold removal, temporal-semantic hardening

No 9A geometry rerun. Disclosed
`PRE_9B_S0_NUMERIC_ESTIMATOR_EXPOSURE_IN_9A_DIAGNOSTIC_DISCLOSED`: 9A's
own `target_level_median_v_km_day_distribution["median"]` diagnostic
was mathematically the same estimator the frozen `FUTURE_S0_FORMULA_9A`
defines as S0 — exposed value `3.946421443154751` km/day (n=371),
verified to exact machine precision against the persisted CSV. File-
mtime audit confirmed `NO_POST_EXPOSURE_RATE_METHOD_RETUNING_DETECTED_IN_RECORDED_SESSION`
(the numerically load-bearing modules were untouched after exposure;
only the run script's interpretive status label and documentation
wording were corrected). Removed the arbitrary
`n_unique_targets < 10` sufficiency cutoff with no replacement
threshold. Corrected temporal wording to avoid implying exact
biological/infection/transmission time. Documented quality-count
denominators explicitly and audited the 12-vs-4 zero-distance
distinction (origin-target vs. target-level). Revised Checkpoint 9B's
purpose to a formal freeze, never a first look. 10 new tests. Full
design: `DATA_AUDIT.md` §98, `RATE_MODEL_PROTOCOL.md` §20.

## 70. Checkpoint 9B — formal freeze of the predeclared S0 estimator, target-event-level percentile bootstrap uncertainty

No 9A geometry rerun; no `d_min`/`v_obs` rebuild; no DB query for rate
estimation; formula/scope/horizon/aggregation/bootstrap unit/seed/
n_resamples all unchanged. New dependency-minimal modules
`services/model_development/{rate_s0_bootstrap_9b.py,rate_input_identity_9b.py,rate_protocol_9b.py}`
(zero DB/geospatial/direction/weather dependency, verified
structurally). Canonical input-dataset identity frozen from the
already-persisted 371-row `rate_target_level_readiness_9a.csv`: raw
`input_csv_sha256=71e7d82f974d1dd01911c45fbbfd7121ef07e915212c3f7004fef6120399b183`
and text-preserving canonical payload hash
`ebbd08e30c14f91e17110dfe42a20b7239812a4f307f3edc2137cde98ca6202f`
(sorted `[target_event_id, exact-persisted-numeric-text]` pairs, never
a Python-float round-trip). Zero counts kept distinct: 12 origin-target
vs. 4 target-level. Bootstrap: Python stdlib `random.Random(42)`,
`randrange` with replacement, `n=371` per replicate, `statistics.median`,
1000 replicates, explicit linear-interpolation 95% percentile interval
— `s0_bootstrap_protocol_hash_9b()=969161e318508edfa2465d2f4598dbca17fcf29ef01bba2df42bec8093835d28`.
Manifest written and independently re-verified from disk BEFORE the
real bootstrap ran (`pre_bootstrap_manifest_file_sha256=622562e544b3d92541321239251efaf08edcb624ceb763cc530ed96f2431569b`);
a second run of the runner was confirmed to refuse (exclusive-create
guard). Real result: point estimate **3.946421443154751 km/day**
(exactly reproduces the already-exposed 9A.1 value), 95% target-event
percentile bootstrap interval **[3.549, 4.343] km/day**, seed 42, 1000
resamples. Nine required scientific limitations persisted verbatim
(A-I, `RATE_MODEL_PROTOCOL.md` §21). No S1; no nominal reach; no held-
out/Sri Lanka rate inspected. 43 new tests. Full backend regression:
**1437/1437 passed, 0 failed, 0 skipped** (1394 baseline + 43 new).
**Final classification:
`FROZEN_DEVELOPMENT_DERIVED_S0_ESTIMATED_APPARENT_LOCAL_SPREAD_FRONT_RATE_WITH_PRE_9B_NUMERIC_EXPOSURE_DISCLOSED_AND_TARGET_EVENT_BOOTSTRAP_UNCERTAINTY`.**
Full design: `RATE_MODEL_PROTOCOL.md` §21.

## 71. Checkpoint 9C — deterministic nominal-reach derivation and frozen scientific component integration contract

New `services/integration/{nominal_reach_9c.py,geospatial_intelligence_contract_9c.py,geospatial_intelligence_protocol_9c.py}`
package — zero model fitting, zero predictive evaluation. Freezes
`nominal_reach_km(day_h) = frozen_S0_rate_km_day * day_h` for D1-D7
only (`3.946`, `7.893`, `11.839`, `15.786`, `19.732`, `23.679`,
`27.625` km), a pure deterministic transform of the already-frozen 9B
point estimate — never a new bootstrap, never a rebuilt `d_min`/`v_obs`.
The frozen 25km operational local evaluation envelope and the D7
nominal reach (`27.625` km, > 25km) are kept as two explicitly separate
fields, never reconciled (min/max/clip). Assembles
`FrozenGeospatialIntelligenceContract9C` (risk/direction/apparent_rate/
nominal_reach_by_day/provenance/limitations) as a plain
DB/framework-independent dataclass DTO — no FastAPI route yet; the DTO
never computes scientific values itself, only assembles
already-computed inputs plus frozen constants. Risk stays
`STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT` — nominal reach never
modifies the C0 cell score. `integration_protocol_hash_9c()=cec826a26c860c752d1fa32d94edcdfba2e0186950cdccfc96067fef2ce51a90`
binds every frozen parent hash (7C, 8B.3, 9A, 9B) plus every semantic
separation rule, excluding timestamps/paths/UI/URLs. 28 new tests. Full
backend regression: **1465/1465 passed, 0 failed, 0 skipped** (1437
baseline + 28 new). **Final classification:
`FROZEN_GEOSPATIAL_RISK_DIRECTION_APPARENT_RATE_AND_NOMINAL_REACH_INTEGRATION_CONTRACT_READY_FOR_API`.**
Full design: `RATE_MODEL_PROTOCOL.md` §22, `GEOSPATIAL_INTELLIGENCE_INTEGRATION_PROTOCOL.md`.

## 72. Checkpoint 9C.1 — rate-scope conditioning, lead-time truncation, target-inclusion, and GPS-quality diagnostic audit

Read-only diagnostic
(`services/model_development/{rate_scope_conditioning_9c1.py,rate_scope_conditioning_protocol_9c1.py}`)
over the already-persisted 9A `rate_origin_target_observations_9a.csv`
(SHA256-verified before use) — no DB query, no geodesic
recomputation, no 9B bootstrap rerun. Establishes that the frozen
`d_min <= 25km` inclusion rule mathematically forces
`v_obs <= 25/lead_days`, with the D7 ceiling (`3.571` km/day) strictly
below the frozen S0 (`3.946` km/day) — characterized as
`RATE_SCOPE_CONDITIONING`/`LEAD_DEPENDENT_TRUNCATION_MECHANISM`, never
a bug/leakage/p-hacking claim. Pooled reconciliation confirmed
unchanged (`3947 = 1387 WITHIN + 2560 OUTSIDE + 0 unresolved`);
target-event inclusion set (371 with >= 1 WITHIN) confirmed to exactly
match `rate_target_level_readiness_9a.csv`; zero-distance diagnostic
(12 rows / 4 targets / all UNKNOWN GPS) reconfirmed. No alternate S0
computed anywhere (`NO_ALTERNATE_POOLED_S0_CALCULATED_IN_9C1`,
structurally verified — no `statistics.median`/`statistics.mean` call
in either module). S0, the 9B interval, the 25km envelope, and all
9C nominal-reach numbers remain byte/numerically unchanged; only the
interpretation is hardened. `rate_scope_conditioning_protocol_hash_9c1()=26168ca784b5f8cb5393db872baa1e7e7f1d74f782b16df17c97354b9bf52b8f`.
24 new tests. Full backend regression: **1489/1489 passed, 0 failed, 0
skipped** (1465 baseline + 24 new). **Final classification:
`RATE_SCOPE_CONDITIONING_AUDIT_COMPLETE_PRIMARY_S0_RETAINED_WITH_EXPLICIT_CONDITIONAL_INTERPRETATION`.**
Full design: `RATE_MODEL_PROTOCOL.md` §23,
`GEOSPATIAL_INTELLIGENCE_INTEGRATION_PROTOCOL.md` §6.
