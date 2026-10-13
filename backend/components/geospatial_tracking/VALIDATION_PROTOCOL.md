# PISTES Validation Protocol — Frozen as of Checkpoint 4.5

This is the frozen validation-strategy decision for PISTES's historical
replay. It does not train, tune, or freeze any model — no model exists
yet. It freezes *how future model development must be evaluated*, based
only on chronology, target counts, temporal coverage, coordinate-
collision evidence, and data quality (`HISTORICAL_CHRONOLOGY_AUDIT.md`,
real-corpus counts below) — never on any performance number, because none
exists.

## 1. Primary validation strategy — FROZEN

**PRIMARY VALIDATION = EXPANDING-WINDOW / WALK-FORWARD CHRONOLOGICAL
EVALUATION.**

Not chosen because it performs better than alternatives — no model
exists to compare. Chosen because:

- Thailand's chronology is dominated by one concentrated 2021 wave
  (`HISTORICAL_CHRONOLOGY_AUDIT.md` §4); a single fixed train/validation/
  test boundary is fragile to exactly where it lands relative to that
  wave, while walk-forward samples the wave's structure across multiple
  folds instead of putting it entirely on one side of one cut.
- PISTES's own deployment model is outbreak-triggered and inherently
  walk-forward-shaped (a forecast origin is created whenever new sources
  arrive — master-prompt Part 6) — walk-forward evaluation matches how
  the system would actually run.
- Confirmed against the real corpus (§5 below): the global 4-fold
  candidate schedule shows strict Tier-A direction target counts of
  304 / 9 / 0 / 0 across its four folds — almost entirely concentrated in
  the earliest fold. A single fixed boundary drawn anywhere else would
  have left 2-3 of 4 partitions with zero direction-evaluable targets.

**No random shuffling for primary evaluation** —
`train_test_split(random_state=...)` or any row-level shuffle is
explicitly rejected; verified structurally, no module in
`services/{aggregation,forecast_origin,forecast_target,historical_trigger,source_selector,split_embargo,walk_forward}.py`
imports a random-shuffle facility (SPLIT-01).

**Nested chronological validation**, if needed for parameter tuning, must
be nested INSIDE development folds — never substituting for the outer
walk-forward structure, and never used to sneak a look at the final
holdout.

## 2. Frozen 7-day purge/embargo policy

**PURGED_7_DAY_HORIZON_POLICY** (`services/split_embargo.py`), for split
boundary B and horizon H=7:

```
A development/training origin is eligible for the earlier partition
ONLY when:           t0 + H < B

If:  t0 < B  AND  t0 + H >= B
the origin is PURGED from the earlier partition — never clipped and kept
as a normal training origin with a truncated horizon.

For a finite validation block [B, E]:
a validation origin supports a COMPLETE D1-D7 evaluation only when
    t0 >= B  AND  t0 + H <= E
unless the block is intentionally open-ended/final (E = None), in which
case no upper completeness bound applies.
```

Implemented and tested (PURGE-01..04). Applied automatically by
`services/walk_forward.build_candidate_folds` to every candidate fold's
training/validation split.

## 3. Task-specific validation protocols

Checkpoint 4 found that strict Tier-A direction/speed targets are almost
entirely a Thailand phenomenon (see §5). Forcing one identical evaluation
protocol onto risk, direction, and speed would either starve direction/
speed of usable targets (if scoped broadly) or throw away most of the
risk-eligible international data (if scoped to Thailand only). They are
therefore separate protocols.

### A. Risk-surface protocol

May use the broader RISK_TARGET_ELIGIBLE international dataset (1368
targets corpus-wide, all countries). **Primary validation: chronological
expanding-window / walk-forward** (the global 4-fold candidate schedule,
`walk_forward_fold_candidates.csv`). Never random-shuffled. Country and
calendar time remain explicit grouping/reporting variables — never
collapsed into one undifferentiated pool when reporting results.

### B. Direction protocol

Primary quantitative evaluation uses only DIRECTION_TARGET_TIER_A_STRICT
(or, as an explicit documented sensitivity variant,
DIRECTION_TARGET_TIER_A_RESOLVED_ONLY) targets. Based on the real corpus,
this is overwhelmingly Thailand (§5: 313-334 of ~334 Tier-A targets
corpus-wide are Thailand's). This must be reported and labeled as:

> **within-corpus / Thailand-dominant chronological direction
> evaluation**

**never** as "a global validated direction model" — that claim is not
supported by this corpus's actual coordinate-collision/GPS-precision/
date-quality distribution (see `HISTORICAL_CHRONOLOGY_AUDIT.md` §6),
regardless of what a future fitted model's error looks like. A separate
Thailand-only walk-forward fold schedule
(`walk_forward_fold_candidates_thailand_direction.csv`) is proposed
specifically because the global schedule concentrates almost all Tier-A
depth in one fold — Thailand's own chronology gives a much more balanced
4-fold split (§5).

### C. Speed protocol — PENDING, not yet a validated task

Do **not** assume every Tier-A direction target is valid for speed. The
current speed tiers (`speed_target_tier_a_strict`/
`speed_target_tier_a_resolved_only`/`speed_target_tier_b`) are computed
with the identical candidate criteria as direction (no distinct evidence
exists yet to differentiate them), but every row additionally carries:

```
speed_eligibility_status = "SPEED_ELIGIBILITY_PENDING_GEOMETRY"
```

**Any report of a speed tier count (e.g. "329 candidate speed-eligible
targets") must include this status alongside it and must never be
presented as a validated speed sample count.** Source-to-target geometry
and event-level conditions (minimum inter-source spacing, direction-of-
travel consistency, etc.) have not been built. This status will only
change once that geometry work happens, in a later checkpoint.

### D. Sri Lanka — frozen role

**Frozen label: `GEOGRAPHIC_TRANSFER_CASE_STUDY`.** Never "prospective
validation," "large external validation dataset," or "statistically
strong external test."

- N = 6 defensible episodes, all within a 52-day window
  (`HISTORICAL_CHRONOLOGY_AUDIT.md` §2, §7).
- Concrete chronology finding (unchanged from Checkpoint 4, re-confirmed):
  Thailand — the country carrying essentially all Tier-A direction
  depth — starts 2021-03-10, entirely AFTER Sri Lanka's 2020-09-07 event.
  Any development pool that includes Thailand's data makes a
  Sri-Lanka-2020 evaluation retrospective, never prospective.
- **Sri Lanka data must never be used to tune model parameters.** It may
  be used, after the model-development protocol is frozen and applied,
  for: case-study visualization, transfer assessment, and qualitative/
  limited-quantitative discussion — never folded into the primary
  risk/direction/speed validation metrics.

## 4. Performance-non-exposure rule (locked, Checkpoint 4 → 4.5)

No partition of this corpus may be called "blind," "completely
untouched," or "never seen" — extensive data engineering (parsing,
deduplication, chronology description, coordinate-collision analysis) has
already inspected all of it. Use "**held out from model fitting**" where
accurate (`DATA_EXPOSURE_AUDIT.md`).

**From Checkpoint 4.5 onward: validation/test-partition PERFORMANCE must
never be used to redesign** dedup rules, GPS rules, event-date rules,
target-tier definitions, or split boundaries — unless that redesign is
explicitly declared as a new DEVELOPMENT decision and is followed by a
genuinely new, independent evaluation protocol (not a re-check against
the same partition that motivated the change). This rule is prospective:
it governs work from this checkpoint forward, not anything already done
(all tier/collision/split-boundary work in Checkpoints 4-4.5 was done from
chronology/coverage/quality alone — no model exists yet to have exposed
any performance number to react to).

## 5. Real-corpus counts backing this freeze

From `services/build_historical_replay.py`'s real run (2587 imported
historical records, 1480 model candidates, disease = Lumpy skin disease):

| Metric | Count |
|---|---|
| RISK_TARGET_ELIGIBLE | 1368 |
| DIRECTION_TARGET_TIER_A_STRICT | 329 |
| DIRECTION_TARGET_TIER_A_RESOLVED_ONLY | 334 |
| DIRECTION_TARGET_TIER_B | 1034 |
| Forecast origins | 813 |
| Origins with >=1 D1-D7 target | 569 |
| Unique target events | 1089 |
| Total target rows (all origins) | 4537 |
| Target events repeated across >1 origin | 910 (max 7 repeats — bounded by the 7-day horizon, as expected) |

Coordinate collision status (`coordinate_collision_report.csv`, 2587
canonical rows):

| Status | Count |
|---|---|
| UNIQUE_AMONG_RESOLVED | 1954 |
| SHARED_WITH_RESOLVED | 42 |
| SHARED_WITH_UNRESOLVED | 555 |
| SHARED_WITH_BOTH | 36 |

Sri Lanka's 6 candidates: 5 `UNIQUE_AMONG_RESOLVED`, 1
`SHARED_WITH_UNRESOLVED` (the Chavakachcheri `REVIEW_LOW` conflict record
— not "non-independent," ambiguous and preserved for review, matching
Checkpoint 2.5's finding independently).

Global candidate folds (`walk_forward_fold_candidates.csv`, 4 folds,
quantile boundaries over all 813 origins):

| Fold | Validation range | Strict Tier-A direction targets |
|---|---|---|
| 1 | 2020-11-15 → 2021-08-24 | 304 |
| 2 | 2021-08-24 → 2023-02-06 | 9 |
| 3 | 2023-02-06 → 2024-11-24 | 0 |
| 4 | 2024-11-24 → (open) | 0 |

Thailand-only direction fold schedule (`walk_forward_fold_candidates_thailand_direction.csv`,
4 folds over Thailand's 187 origins) — proposed specifically because the
table above shows the global schedule cannot support direction evaluation
past fold 1:

| Fold | Validation range | Strict Tier-A direction targets |
|---|---|---|
| 1 | 2021-05-04 → 2021-05-31 | 129 |
| 2 | 2021-05-31 → 2021-07-02 | 95 |
| 3 | 2021-07-02 → 2021-10-26 | 35 |
| 4 | 2021-10-26 → (open) | 9 |

## 6. What this protocol does NOT do

- Does not choose a final split boundary or freeze which candidate fold
  schedule (global vs. Thailand-only vs. a nested variant) is "the" one
  used — `SPLIT_PROTOCOL_DRAFT.md` still frames these as candidates.
- Does not build final train/test files (master-prompt Part 11).
- Does not implement speed geometry, ST-DBSCAN, risk coefficients,
  direction estimation, or any model.
- Does not decide the Part 14 embargo exclusion mechanism beyond "purge
  the whole origin" (documented in `split_embargo.py`; alternative
  per-target clipping was considered and rejected as the frozen policy
  — see §2, "never clipped and kept").

## 7. Checkpoint 6D — factor-transformation development reuses this same firewall

`services/factors/reference_profile.assert_factor_development_only`
(Checkpoint 6D) reuses the same underlying role-classification service
this protocol's split is built on (`model_fitting_exposure.assert_fit_development_only`,
Checkpoint 6B.5) — reference-profile quantiles, host-density
transformation candidates, and reference-observation de-duplication are
all restricted to `FIT_DEVELOPMENT` origins by the identical hard
firewall, not a re-implementation. See `FACTOR_TRANSFORMATION_PROTOCOL.md`.

Checkpoint 6D.5 confirmed this firewall scales to the REAL, full
`FIT_DEVELOPMENT` universe: `services/factors/host_reference_gathering.py`
derives that universe AT RUNTIME from the same exposure-role ledger
(never a hardcoded origin count) and processed all 579 real origins —
0 held-out, 0 Sri-Lanka origins ever reached the reference-profile
builder, by construction.

Checkpoint 6D.6 re-ran the same firewall unchanged after correcting the
identity/conflict/compatibility logic around it (effective weighted
raster-sample identity, a value-conflict firewall, and full
`ReferenceStratumKey` compatibility — see `FACTOR_TRANSFORMATION_PROTOCOL.md`
§21). `GLOBAL_REFERENCE_PROFILE_READY` now means ONLY that the global
`FIT_DEVELOPMENT` HOST REFERENCE DISTRIBUTION was fully, honestly
constructed under the frozen data/reference protocol — it is explicitly
NOT a validated PISTES model, NOT calibrated infection probability, NOT
final host-transform selection, and NOT Sri-Lanka/held-out validation
(`reference_scope=GLOBAL_FIT_DEVELOPMENT_HOST_REFERENCE`,
`selection_status=UNFROZEN_DEVELOPMENT_CANDIDATE` are reported
explicitly alongside the label to prevent that over-reading). Held-out
and Sri-Lanka outcomes were not inspected at any point in this
checkpoint — the identity/conflict corrections were verified using
FIT_DEVELOPMENT data and direct floating-point measurement only.

## 8. Checkpoint 7B — nested chronological development folds reuse this same firewall

`services/model_development/development_run_7b.run_checkpoint_7b_development`
and `services/model_development/fold_reference.build_fold_safe_reference`
both call `assert_fit_development_only` at their OWN entry point (never
trusting a pre-filtered caller) — a `HELD_OUT_FROM_MODEL_FITTING` or
`SRI_LANKA_TRANSFER_CASE_STUDY` origin mixed into either function's
arguments rejects the WHOLE call before any repository/raster access
(7B-LEAK-01..03). Chronological folds reuse
`model_fitting_exposure.build_calendar_year_folds` unchanged — Checkpoint
7B introduces no new split logic, only a fold-local, training-only host
reference (`FoldSafeHostReference`) built on top of it, to prevent
validation-fold covariate distributions leaking backward into training
transform statistics (see `BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md` §4).
No `HELD_OUT_FROM_MODEL_FITTING`/`SRI_LANKA_TRANSFER_CASE_STUDY`
predictive performance is computed anywhere in Checkpoint 7B — baseline
candidate selection uses `FIT_DEVELOPMENT` validation folds exclusively.

## 9. Checkpoint 7C — wind-anisotropic development reuses this same firewall

`services/model_development/development_run_7c.run_checkpoint_7c_development`
calls `assert_fit_development_only` at its own entry point, identically
to 7B, and reuses `build_calendar_year_folds` unchanged (same folds,
same 7-day purge). The real, network-fetched ERA5 wind acquisition
(`wind_readiness_7c.resolve_origin_wind`) is itself t0-safe by
construction — `build_pre_t0_weather_summary` never requests a
post-cutoff timestamp at all, so no explicit "reject held-out" check is
needed at the weather layer; the origin-level firewall alone is
sufficient (7C-LEAK-01..02), and 7C-LEAK-04/05 directly prove a
realized-future weather value cannot change a primary wind score while a
genuinely pre-t0 value can. No `HELD_OUT_FROM_MODEL_FITTING`/
`SRI_LANKA_TRANSFER_CASE_STUDY` predictive performance is computed
anywhere in Checkpoint 7C.

## 10. Checkpoint 7D — the held-out-from-fitting firewall inverted

`services/model_development/heldout_run_7d.run_checkpoint_7d_heldout_evaluation`
calls a new, exactly symmetric firewall,
`model_fitting_exposure.assert_held_out_only` — the inverse of
`assert_fit_development_only`: it hard-rejects any `FIT_DEVELOPMENT` or
`SRI_LANKA_TRANSFER_CASE_STUDY` origin, accepting only
`HELD_OUT_FROM_MODEL_FITTING` (7D-FREEZE-03/04). Before this firewall is
even reached, `heldout_protocol_7d.assert_frozen_c0_model` verifies the
on-disk Checkpoint 7C frozen specification matches the expected selected
candidate id/hash/kernel/factor-exclusion set exactly — scoring never
proceeds on a mismatch (Part 2). There is no candidate registry in 7D:
exactly one frozen `Candidate7CSpec` is passed in by the caller, and
nothing in `heldout_run_7d.py` can select a different one
(7D-FREEZE-05/06).

**Correction (Checkpoint 7D.1)**: Checkpoint 7D's original report
additionally claimed the evaluation was genuinely "single-shot" with no
prior predictive inspection. This was false — a 40-origin predictive
sanity subset was inspected before the final run (disclosed, never
hidden, in `DATA_EXPOSURE_AUDIT.md` §7). An independent mtime audit
confirmed no numerically load-bearing code changed afterward
(`NO_POST_EXPOSURE_MODEL_RETUNING_DETECTED`). **Checkpoint 7D's held-out
result is now labeled
`FROZEN_HELD_OUT_FROM_FITTING_EVALUATION_WITH_PRIOR_DATASET_AND_PRE_FINAL_PREDICTIVE_SUBSET_EXPOSURE_DISCLOSED`
— never single-shot/blind/untouched/external validation** (see
`DATA_EXPOSURE_AUDIT.md` §7).

## 12. Checkpoint 7E — Sri Lanka GEOGRAPHIC_TRANSFER_CASE_STUDY firewall (never "validation")

`services/model_development/sri_lanka_run_7e.run_checkpoint_7e_sri_lanka_case_study`
calls a third symmetric firewall,
`model_fitting_exposure.assert_sri_lanka_transfer_case_study_only` --
hard-rejects `FIT_DEVELOPMENT`/`HELD_OUT_FROM_MODEL_FITTING`, accepting
only `SRI_LANKA_TRANSFER_CASE_STUDY`. `sri_lanka_protocol_7e.assert_frozen_c0_model_7e`
reuses Checkpoint 7D's own freeze assertion directly (never
re-implemented) before any repository access. Real universe: 5 Sri Lanka
origins (from 7 raw historical records -> 6 model-candidate
dedup-resolved episodes -> 5 forecast origins, one excluded record with
an unresolved 8-day date discrepancy already documented in
`HISTORICAL_CHRONOLOGY_AUDIT.md`), 0 blocked. Only **1** real D1-D7
target fell inside the frozen 25km scope (a second real target existed
but at ~87km, correctly excluded, never used to justify widening the
envelope). This is a `GEOGRAPHIC_TRANSFER_CASE_STUDY` — never
`EXTERNAL_VALIDATION`/`INDEPENDENT_VALIDATION`/`BLIND_VALIDATION`/
`PROSPECTIVE_VALIDATION` — and, with `n_contributing_origins=1 < 10`,
is reported under the small-sample descriptive-only rule (§`SMALL_SAMPLE_DESCRIPTIVE_ONLY`,
never a bootstrap CI presented as robust inferential evidence). See
`DATA_EXPOSURE_AUDIT.md` §8.

## 11. Checkpoint 7D.1.2 — retrospective availability limitation

7D's `availability_protocol_identity = RETROSPECTIVE_PROXY_T0_INVARIANT`
(the same `ValidationMode.RETROSPECTIVE_PROXY` temporal mode every
eligible-source query in this repository already uses). The 7D held-out
result is therefore **RETROSPECTIVE held-out-from-fitting spatial-
ranking evidence** — it is **NOT** prospective operational validation,
real-time production accuracy, or a strict operational-availability
reconstruction (no claim is made that the exact same information would
have been operationally available to a live system at each historical
t0 with zero latency; C0 needs no weather so this limitation is milder
for 7D than it was for 7C's ERA5 acquisition, but the retrospective
framing still applies to source/target data availability itself). Also
see `MODEL_DEVELOPMENT_PROTOCOL.md` §61 and `DATA_AUDIT.md` §85/§88.

## 13. Checkpoint 8B/8B.2/8B.3 — no direction-performance evaluation, circular-evaluation prohibition

Neither `compute_cell_direction_tendency` (historical,
`services/direction/c0_geometric_tendency.py`) nor
`compute_cell_direction_tendency_8b3` (active,
`services/direction/c0_cell_local_tendency_8b3.py`) takes a target/
future-outbreak parameter — evaluating the field at a future target
cell and comparing to the source->target bearing would be
geometrically tautological (especially for a single source) and is
never performed, in either method. `DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN`
remains unresolved through 8B.3. See `DIRECTION_8B_PROTOCOL.md` §12,
§19, §20.

## 14. Checkpoint 9A — apparent local spread-front rate role/temporal firewalls

`services.model_development.rate_readiness_9a.derive_fit_development_rate_observations`
calls `assert_fit_development_only` at its own entry point (never
trusting a pre-filtered caller) — `HELD_OUT_FROM_MODEL_FITTING` and
`SRI_LANKA_TRANSFER_CASE_STUDY` origins are hard-rejected before any
repository access; the 2024+ held-out corpus and Sri Lanka were never
inspected, not even diagnostically. `v_obs` is `APPARENT_RATE_FROM_RECORDED_EVENT_CHRONOLOGY_NOT_TRUE_INFECTION_TIME`
— derived from recorded event chronology, never true biological
infection timing, and never called validated/production rate in
Checkpoint 9A (`DEVELOPMENT_RATE_DATASET_DIAGNOSTIC` only). See
`RATE_MODEL_PROTOCOL.md`.

## 15. Checkpoint 9B — formal S0 freeze firewall (no held-out/Sri Lanka rate evaluation)

`services/model_development/{rate_s0_bootstrap_9b.py,rate_input_identity_9b.py,rate_protocol_9b.py}`
have no DB/repository dependency at all (verified structurally,
9B-FIREWALL-01) — they cannot query held-out or Sri Lanka data even in
principle, since they never call `SQLiteOutbreakRepository` or any
eligible-source/target-construction function. `heldout_rate_validation_status`
and `sri_lanka_rate_status` are both frozen as `NOT_EVALUATED_IN_9B` in
`frozen_s0_apparent_rate_spec_9b.json`. The formal S0 result remains
`DEVELOPMENT_HISTORICAL_APPARENT_RATE_ESTIMATION` — never prospective
operational validation, held-out rate validation, or a Sri Lanka-
specific estimate. See `RATE_MODEL_PROTOCOL.md` §21.

## 16. Checkpoint 9C — integration-contract firewall (no held-out/Sri Lanka rate input, no rerun of anything upstream)

`services/integration/{nominal_reach_9c.py,geospatial_intelligence_contract_9c.py,geospatial_intelligence_protocol_9c.py}`
import no held-out/Sri Lanka RATE run module
(`heldout_run_7d`/`sri_lanka_run_7e`/`sri_lanka_protocol_7e`
structurally absent, 9C-FIREWALL-01), no repository/database module
(9C-FIREWALL-02), and no 9B bootstrap implementation module
(`rate_s0_bootstrap_9b` structurally absent, 9C-FIREWALL-03) — the real
1000-replicate bootstrap cannot be re-invoked from this checkpoint even
in principle. `nominal_reach_9c.py` additionally never imports the
frozen 25km envelope module or any C0-scoring module
(`local_evaluation_scope`/`baseline_scoring`/`wind_scoring_7c`/
`candidate_registry_7c`/`hazard` all structurally absent), proving by
construction that nominal reach cannot modify the evaluation envelope
or the C0 score (9C-REACH-04/05). `rate_status`/`sri_lanka_rate_status`
in the presentation contract remain `FROZEN_DEVELOPMENT_HISTORICAL_APPARENT_RATE`/
`NOT_EVALUATED`, matching the frozen 9B firewall values exactly — no
new evidence classification is introduced. The one import of
`heldout_protocol_7d` (for the frozen `SELECTED_CANDIDATE_ID`/
`FROZEN_7C_SPEC_HASH` risk-model identity constants only, per the
provenance requirement) is explicitly distinguished from, and never
confused with, the forbidden `heldout_run_7d` held-out RATE evaluation
module. See `RATE_MODEL_PROTOCOL.md` §22.

## 17. Checkpoint 9C.1 — rate-scope conditioning diagnostic firewall (read-only, no rerun, no alternate estimator)

`services/model_development/{rate_scope_conditioning_9c1.py,rate_scope_conditioning_protocol_9c1.py}`
import no DB/repository module, no `heldout_run_7d`/`sri_lanka_run_7e`/
`sri_lanka_protocol_7e`, and no `rate_s0_bootstrap_9b` (verified via
AST import scan, 9C1-FIREWALL-01..04). AST `Call`-node inspection
(excluding docstrings/comments, so the modules' own negated disclaimer
text never false-positives the check) confirms no real call to
`SQLiteOutbreakRepository`, `build_forecast_origin_ledger`,
`build_forecast_targets`, `get_eligible_sources`,
`derive_fit_development_rate_observations`, `distance_km`, `Geod`, or
`classify_target_primary_scope` anywhere in either module. No
`statistics.median`/`statistics.mean` call exists in either module --
structural proof that no alternate pooled S0 estimator is computed
(9C1-NOALT-01). The input observation CSV SHA256 is verified against
the already-evidenced Checkpoint 9A artifact identity before any
diagnostic computation runs; the module raises (STOPs) rather than
proceeding on a mismatch, on a theoretical-ceiling violation, or on a
target-event-set mismatch against `rate_target_level_readiness_9a.csv`.
S0, the 9B interval, the 25km envelope, and the Checkpoint 9C
nominal-reach values are read but never reassigned anywhere in this
checkpoint. See `RATE_MODEL_PROTOCOL.md` §23.

## 18. Checkpoint 10A.1 — historical-replay firewall (no live-operational claim, no source-window tuning, historical 10A identity preserved)

`services/application/frozen_geospatial_analysis_10a.py` calls
`get_eligible_sources` with `ValidationMode.RETROSPECTIVE_PROXY`/
`RecordDomainScope.HISTORICAL_ONLY` -- structurally verified (AST) to
be the exact same two enum objects that also populate the new
`availability_mode`/`record_domain_scope` metadata fields
(10A1-MODE-05), so the exposed labels cannot silently drift from the
real source-selection call. `RecordDomainScope.LIVE_ONLY` is never
imported or used anywhere in this checkpoint --
`live_operational_analysis_status` is hardcoded to
`NOT_IMPLEMENTED_NO_ACTUAL_OPERATIONAL_AVAILABILITY_PIPELINE`, never
silently flipped by any code path. The 14-day active source window
(`ACTIVE_SOURCE_WINDOW_DAYS_10A1`) is imported/aliased from the
historical `ACTIVE_SOURCE_WINDOW_DAYS_10A` constant -- never a second
literal, never varied in any test (10A1-WINDOW-01/05 mutate only a
disposable copied dict, never the real module constant). The historical
`geospatial_api_protocol_hash_10a()` is re-verified equal to its frozen
literal on every test run (10A1-HIST-01); the new
`geospatial_api_protocol_hash_10a1()` module imports it read-only and
defines no function that could reassign it. No held-out/Sri Lanka rate
data is inspected, no 9B bootstrap invoked, no 7B-9C.1 artifact
modified. See `GEOSPATIAL_API_PROTOCOL.md` §15.

## 19. Checkpoint 10B — real-time transport firewall (no science in transport, no live-only path, no automatic polling)

`services/transport/{geospatial_snapshot_10b.py,snapshot_store_10b.py,chunking_10b.py}`
and `api/router.py` import no C0/direction/rate-bootstrap/held-out/
Sri-Lanka/weather/host/environment/water/source-strength module, and
no real call to `evaluate_kernel`/`compute_cell_direction_tendency_8b3`/
`run_bootstrap` exists in any transport module (structurally verified,
AST call-node inspection, 10B-FIREWALL-01..05). `snapshot_store_10b.py`
is fully generic -- it caches whatever opaque object a caller-supplied
`compute_fn()` returns and holds zero import of any scientific module
at all. The only scientific entry point anywhere in the transport layer
is a single call to `run_frozen_geospatial_runtime_analysis_10a` inside
`geospatial_snapshot_10b.build_geospatial_snapshot_10b`. `RecordDomainScope.LIVE_ONLY`
is never imported or referenced anywhere in `services/transport/` or
`api/router.py` -- the literal string `"LIVE_ONLY"` does not appear in
either (10B-FIREWALL-08). The WebSocket handler contains exactly one
`while True` loop (the event-driven `receive_text` loop, blocked on
client input) and zero `asyncio.sleep`/`time.sleep` calls -- no
timer-driven scientific refresh, no background outbreak polling, no
file watching exists anywhere in Checkpoint 10B
(`AUTOMATIC_SCIENTIFIC_UPDATE_STATUS_10B = "NOT_IMPLEMENTED"`,
10B-FIREWALL-06). No `local_data` path reference or real
file-read call exists in any transport module (10B-FIREWALL-07). See
`GEOSPATIAL_REALTIME_TRANSPORT_PROTOCOL.md`.

## 20. Checkpoint 10B.1 — transport hardening firewall (no science touched, integrity check uses the canonical hash only, repository construction centralized)

`services/integration/geospatial_transport_protocol_10b1.py` and the
hardened `services/transport/snapshot_store_10b.py` import no C0/
direction/rate-bootstrap/held-out/Sri-Lanka/weather/host/environment/
water/source-strength module -- structurally identical firewall
posture to Checkpoint 10B, re-verified. `verify_snapshot_integrity_10b`
(`services/transport/geospatial_snapshot_10b.py`) calls the SAME
`compute_snapshot_id_10b` function `snapshot_id` was originally built
from -- no second hash formula exists anywhere in this checkpoint.
Repository construction is centralized: `repositories/provider.py::create_outbreak_repository()`
is the only call site that names `SQLiteOutbreakRepository`; both
`api/router.py::get_repository` and
`services/transport/geospatial_snapshot_10b.py::managed_repository_10b`
call the provider function, never the concrete class, and neither
imports `repositories.sqlite_repository` directly (10B1-PROVIDER-01).
`run_frozen_geospatial_runtime_analysis_10a` remains typed against
`OutbreakRepository` (10B1-PROVIDER-02) -- Mongo is not implemented.
The historical `geospatial_transport_protocol_hash_10b()` and both
parent API hashes are re-verified byte-identical to their frozen
literals on every test run (10B1-PARENT-01/02). See
`GEOSPATIAL_REALTIME_TRANSPORT_PROTOCOL.md` §18.

## 21. Checkpoint 10B.1a — HTTP snapshot-identity firewall (envelope is transport metadata only, integrity check unchanged in method)

`snapshot_id`/`generated_at_utc` added to `/summary`/`/cells`/`/sources`
are read directly from the already-computed `GeospatialSnapshot10B`
(`snapshot.snapshot_id`/`snapshot.generated_at_utc`) -- no new
scientific computation, no second hash formula, and `snapshot_id` is
never written back into `canonical_scientific_payload_10b` as an input
(structurally impossible: the envelope fields are added only at the
Pydantic response-model construction call sites in `api/router.py`,
never inside `services/transport/geospatial_snapshot_10b.py`'s
canonical-payload function). The pre-send integrity check still calls
only `verify_snapshot_integrity_10b`, itself still built on the SAME
`compute_snapshot_id_10b` used since Checkpoint 10B -- moving it
earlier in the WebSocket handler changed WHEN it runs, never WHAT it
computes. All 10A/10A.1/10B/10B.1 firewall guarantees (§16-20) are
re-verified unchanged by this correction. See
`GEOSPATIAL_REALTIME_TRANSPORT_PROTOCOL.md` §19.
