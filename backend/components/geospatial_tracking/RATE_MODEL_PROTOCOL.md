# RATE_MODEL_PROTOCOL — Checkpoint 9A

Apparent local spread-front rate: **methodology freeze and
FIT_DEVELOPMENT data readiness only.** No S0 aggregate value is
computed or frozen as the system rate here — that is Checkpoint 9B.

`rate_readiness_protocol_hash_9a()` (`services/model_development/rate_protocol_9a.py`)
binds every identity below (never a timestamp), printed BEFORE any
real rate value was summarized. Current value:
`326427b08f5c43b9708409ae112460e8f0804db0c972a007caaae8ffca3b58ac`.

## 0. 8B.3 reporting corrections (no rerun)

**A.** The Checkpoint 8B.3 final report said the maximum 25.4-degree
historical-vs-active bearing delta was "confirmed to occur only in
near-cancellation cells." The retained aggregate audit proves only
that maximum bearing delta was 25.4°, resultant-component differences
stayed small throughout, and the angular-instability mechanism was
reproduced synthetically — it does NOT retain per-cell outlier detail
proving every large-delta real cell was actually near-cancellation.
`DIRECTION_8B_PROTOCOL.md` §20.6/20.9, `DATA_AUDIT.md` §96, and
`MODEL_DEVELOPMENT_PROTOCOL.md` §67 have been corrected to the more
precise wording. No rerun performed.

**B.** The 8B.3 structural audit called `score_origin_candidates_7c`
on real FIT_DEVELOPMENT scientific cells to verify the scalar identity
— a real, deterministic C0 recomputation, not "C0 was never
recomputed." Corrected wording: C0 was NOT refitted, retuned, or
predictively re-evaluated; deterministic FIT_DEVELOPMENT C0 scores
were recomputed only as a structural scalar-identity check.

## 1. Scientific purpose

Can a leakage-safe, deduplicated, interpretable historical dataset be
defined for estimating an **apparent local spread-front rate** from
FIT_DEVELOPMENT data? Output label: **"Estimated apparent local
spread-front rate (km/day)"** — never true disease transmission speed,
viral velocity, wind speed, direction-vector magnitude, exact epidemic
front velocity, or causal farm-to-farm transmission speed. "Apparent"
is scientifically load-bearing throughout.

## 2. Independence from the direction field

No formula anywhere connects 8B.3's `resultant_magnitude`,
`directional_clarity`, or `directional_input_coverage` to
`apparent_local_spread_front_rate_km_day`. Verified structurally
(8A-DIR-01/02, 8A-WIND-01 — an AST import scan of
`rate_readiness_9a.py` confirms no `direction`/`wind`/`weather` module
is even imported). Rate is derived independently from historical
outbreak geometry and elapsed time.

## 3. Frozen observation formula

For forecast origin `o` at `t0` and future target event `k`
(`lead_days(o,k) > 0`): `d_min(o,k) = MIN` over ALL eligible t0
sources of the WGS84 geodesic distance to `k`
(`services.model_development.local_evaluation_scope.classify_target_primary_scope`,
reused directly, never reimplemented). `v_obs(o,k) = d_min(o,k) /
lead_days(o,k)`, units km/day. The nearest source is
`NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE` only — never a
causal parent, confirmed transmission source, or infection origin.

## 4. Primary horizon

D1-D7 only (`services.forecast_target.PRIMARY_HORIZON_DAYS`, reused).
D8-D14 is never introduced to rescue the primary rate dataset after
observing its result.

## 5. Local-scope identity

Reuses the SAME already-frozen 25km `FROZEN_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE`
(`services.model_development.local_evaluation_scope.PRIMARY_LOCAL_EVALUATION_DISTANCE_KM`)
every prior checkpoint (7A.6 onward) already uses — no new distance
threshold was searched or selected by looking at rate values; no
10/20/30/50/100km comparison was run. No pre-existing rate-specific
scope protocol was found in the repository (confirmed by inspection
before any rate derivation), so no conflict exists. 25km remains
`OPERATIONAL_LOCAL_EVALUATION_ENVELOPE` — never a biological LSD
spread radius or maximum transmission distance. Targets outside the
envelope are retained in the audit, labelled
`OUTSIDE_DECLARED_LOCAL_RATE_SCOPE`, and excluded only from the
PRIMARY local-rate estimator — never deleted from provenance.

## 6. Role firewall

`services.model_fitting_exposure.assert_fit_development_only` —
`HELD_OUT_FROM_MODEL_FITTING` and `SRI_LANKA_TRANSFER_CASE_STUDY`
origins are hard-rejected BEFORE any repository access (verified,
9A-ROLE-02/03). The 2024+ held-out corpus and Sri Lanka were never
inspected, not even "quickly."

## 7. Source and target selection

Sources: `services.source_selector.get_eligible_sources`
(`temporal_mode=RETROSPECTIVE_PROXY`, `domain_scope=HISTORICAL_ONLY`)
— the EXACT existing selector every prior checkpoint uses; ST-DBSCAN
never gates inclusion; a source is never fabricated when none exists
(`ORIGIN_NO_ELIGIBLE_SOURCE`, honestly reported, 0/579 real origins hit
this in the readiness run). Targets:
`services.forecast_target.build_forecast_targets` +
`ForecastTarget.risk_target_eligible` (Checkpoint 4/4.5, unchanged) —
target identity is outbreak-episode based, never a raw animal report.
Uniqueness: `(forecast_origin_id, target_event_id)`, enforced via
`services.model_development.development_run_7b.dedupe_targets_by_origin_and_event`
(first occurrence kept).

## 8. Pseudo-replication control (frozen, load-bearing)

The same future outbreak `target_event_id` may legitimately appear as
a target for multiple forecast origins — these are NOT independent
outbreak events. `target_level_v(target_event_id) = MEDIAN` of every
valid FIT_DEVELOPMENT `v_obs` associated with that unique
`target_event_id`. **The future Checkpoint 9B S0 estimator MUST be**
`S0 = MEDIAN of target_level_v across UNIQUE target_event_id values`
— never the median of raw origin-target rows, never letting a
repeatedly-forecasted target dominate. Frozen here; computed in 9B.

## 9. Temporal semantics

`lead_days` comes from `historical_event_date`
(`services.historical_event_date`, the SAME recorded historical
event-date / target-occurrence proxy field 7B-8B already use — never
described as exact biological/infection/transmission time; recorded
event date is explicitly distinct from exact infection time, exact
transmission time, and operational availability time) — never silently
mixed with `proxy_availability_date`/`confirmation_date`/`report_date`
across rows. `lead_days > 0` is structurally guaranteed by
`build_forecast_targets` (`1 <= lead_days <= 7`); re-verified
defensively in `rate_readiness_9a.py`, never assumed. Real result: 0
origins hit `EXCLUDED_LEAD_DAYS_NOT_POSITIVE`.

**"Apparent" temporal limitation**: `APPARENT_RATE_FROM_RECORDED_EVENT_CHRONOLOGY_NOT_TRUE_INFECTION_TIME`
— `v_obs` is distance divided by recorded event-time separation, never
direct biological propagation velocity. This limitation must survive
into any later API/UI.

## 10. GPS / spatial quality

Reuses the existing `GpsQuality` enum (`EXACT`/`APPROXIMATE`/`COARSE`/`UNKNOWN`)
verbatim — `EXACT` is never read as implying meter-level precision.
Approximate/coarse coordinates are never silently excluded for
producing inconvenient values; their counts are reported (§13 below).

## 11. Zero-distance observations

A legitimate distinct deduplicated outbreak episode with `d_min=0` and
`lead_days>0` retains `v_obs=0` km/day as a genuine geometric apparent-
rate observation, with coordinate-quality/collision metadata attached
— never converted to missing, never asserted as "no spread," never
epsilon-substituted. If coordinate identity is unresolved under an
existing dedup/collision rule, that frozen rule is applied and
reported, not silently dropped. Real result: **12** legitimate
zero-distance observations retained.

## 12. Geodesic distance only

`services.geospatial.distance.distance_km` (WGS84, `pyproj.Geod`) —
never Euclidean degrees, never grid-cell-center approximation; `d_min`
is computed from actual accepted outbreak coordinate records (verified
9A-GEO-01/02/03).

## 13. No outlier tuning

No winsorization, clipping, high/low-rate removal, log-transform, or
post-hoc scope change after viewing values (verified 9A-OUTLIER-01 —
structural absence of any clip/winsorize/log path in the derivation
module). Extreme observations are reported diagnostically, never
deleted.

## 14. Predeclared Checkpoint 9B bootstrap plan

Primary estimator: median across unique target-level rates. Bootstrap
unit: **unique `target_event_id`** (never origin-target row, never
grid cell). Seed `42`, `n_resamples=1000`, 95% percentile interval.
Interpretation: uncertainty around the historical target-level median,
never a causal transmission-speed confidence interval. Frozen in
`rate_protocol_9a.BOOTSTRAP_PLAN_9B`.

## 15. S1 / nominal reach status

`S1_STATUS_9A = NOT_SELECTED_IN_CHECKPOINT_9A` — no regression/ML
speed model built or considered here. `NOMINAL_REACH_STATUS_9A =
NOT_YET_COMPUTED` — only the later definition is frozen:
`nominal_reach_km(day_h) = frozen_rate_km_day * day_h`, labelled
"Nominal Day-h local reach — not a hard disease boundary," never
truncating C0/risk surface, never changing target scope, never
creating infection probability, never a biological radius; unavailable
if rate is unavailable, never a default substitution.

## 16. Real FIT_DEVELOPMENT readiness audit result

`smoke_tests/run_rate_readiness_9a.py`, run once after protocol freeze
and green tests. Real, runtime-derived universe, never hardcoded:

- **579/579** FIT_DEVELOPMENT origins inspected, all with eligible
  sources (0 without).
- **3,947** raw future D1-D7 target rows; **0** excluded as not
  risk-target-eligible; **3,947** after `(origin, target_event_id)`
  dedup (no duplicates found in this real corpus).
- **1,387** WITHIN primary local scope; **2,560** OUTSIDE; **0**
  unresolved. `1387 + 2560 = 3947` — reconciles exactly.
- **1,387** valid `v_obs` observations (`= n WITHIN`, since 0 excluded
  for `lead_days<=0`).
- **371** unique `target_event_id`. Observations-per-unique-target:
  min `1`, p25 `2`, median `4`, p75 `5`, p95 `7`, max `7`.
- Lead-day counts D1..D7: `228/207/212/186/180/185/189` — sum `1387`,
  reconciles exactly with valid observations.
- **12** zero-distance observations (legitimate, retained).
- Target GPS quality: `EXACT=1854`, `UNKNOWN=1629`, `APPROXIMATE=464`.
  Nearest-source GPS quality: `EXACT=1915`, `UNKNOWN=1626`,
  `APPROXIMATE=406`. All eligible-source GPS quality (all sources at
  all origins): `EXACT=4009`, `UNKNOWN=3673`, `APPROXIMATE=1014`.
  Availability quality (all eligible sources):
  `EVENT_DATE_PROXY=5023`, `OBSERVATION_DATE_PROXY=3673`.
- Sample-size readiness (original 9A status, superseded by §20):
  **`SAMPLE_SIZE_NOMINALLY_SUFFICIENT_FOR_MEDIAN_ESTIMATION`**
  (371 unique targets). See §20 — this status relied on an
  undeclared `n_unique_targets < 10` cutoff and has been corrected to
  an evidence-neutral report.
- Runtime: 5.6s (pure geometry over origin-target pairs, no grid
  iteration, no weather I/O).

## 17. Diagnostic distributions (`DEVELOPMENT_RATE_DATASET_DIAGNOSTIC` — not the system rate)

Episode-target `v_obs` (n=1387): min `0.0`, p25 `2.17`, median `3.68`,
p75 `6.79`, p95 `19.24`, max `24.84` km/day. Target-level median `v`
(n=371): min `0.0`, p25 `2.25`, median `3.95`, p75 `6.09`, p95
`16.91`, max `24.26` km/day. **Neither distribution's median is the
final system rate (S0)** — Checkpoint 9B computes and freezes S0 using
the frozen formula in §8.

## 18. Final classification

**`APPARENT_LOCAL_SPREAD_FRONT_RATE_S0_DEVELOPMENT_DATASET_READY_FOR_9B_ESTIMATION`.**

## 19. Outputs

Tracked: this file, `CHECKPOINT_9A_EVIDENCE_SUMMARY.json`. Gitignored:
`local_data/model_development/9a_rate/{rate_protocol_9a.json,rate_readiness_audit_9a.json,rate_quality_audit_9a.json,rate_diagnostic_distributions_9a.json,rate_origin_target_observations_9a.csv,rate_target_level_readiness_9a.csv}`.
No held-out/Sri Lanka rows anywhere.

## 20. Checkpoint 9A.1 — pre-9B S0 numeric-exposure correction (no rerun, no geometry recomputed)

**Classification: `PRE_9B_S0_NUMERIC_ESTIMATOR_EXPOSURE_IN_9A_DIAGNOSTIC_DISCLOSED`.**
§17's `target_level_median_v_km_day_distribution["median"]` diagnostic
and the frozen §8 `FUTURE_S0_FORMULA_9A` (`S0 = MEDIAN of
target_level_v across UNIQUE target_event_id`) are the same
mathematical estimator — the 9A diagnostic run already computed
`statistics.median()` over the 371 persisted `target_level_v` values,
so the numeric point-estimate value was visible before Checkpoint 9B.
This is a semantic/procedural correction, not a change to the
estimator, the geometry, `d_min`, `v_obs`, or the historical protocol
hash (`326427b08f5c43b9708409ae112460e8f0804db0c972a007caaae8ffca3b58ac`,
unchanged).

Exact already-persisted value read (not recomputed) from
`rate_diagnostic_distributions_9a.json` →
`target_level_median_v_km_day_distribution.median` =
**`3.946421443154751` km/day** (n=371 unique `target_event_id`).
Independently verified: `statistics.median()` of the 371
`target_level_median_v_km_day` values in the persisted
`rate_target_level_readiness_9a.csv` equals the same value at machine
precision (non-geometric consistency check only).

Source-file mtime chronology (session evidence, not asserted from
memory): `rate_protocol_9a.py` (04:34:32), `rate_readiness_9a.py`
(04:42:19), and `smoke_tests/run_rate_readiness_9a.py` (04:43:41) were
all last modified BEFORE the artifact-writing run that produced the
diagnostic values (local_data artifacts, 04:44). No numerically
load-bearing edit to any rate-method file occurred after the diagnostic
median became visible in this session →
`NO_POST_EXPOSURE_RATE_METHOD_RETUNING_DETECTED_IN_RECORDED_SESSION`.

**Arbitrary sample-size cutoff removed**: `smoke_tests/run_rate_readiness_9a.py`
previously derived `sample_size_readiness_status` from an undeclared
`n_unique_targets < 10` cutoff. No predeclared/literature justification
for `N=10` exists, and no replacement arbitrary N was substituted.
Corrected to report `n_unique_target_event_id=371` and
`n_episode_target_observations=1387` without a sufficiency verdict
(`SAMPLE_SIZE_REPORTED_WITHOUT_ARBITRARY_SUFFICIENCY_THRESHOLD`) — see
`s0_pre_9b_exposure_audit_9a1.json`. This does NOT claim
representativeness, external validity, biological completeness, or
Sri Lanka applicability; Checkpoint 9B's predeclared bootstrap
(unique `target_event_id`, seed 42, 1000 resamples, 95% percentile
interval — §14, unchanged) quantifies sampling uncertainty instead.

**Revised Checkpoint 9B purpose**: 9B may not be described as
`FIRST_COMPUTATION_OF_S0`/`FIRST_LOOK_AT_S0`/`UNSEEN_S0_ESTIMATION`.
Its role is now
`FORMAL_FREEZE_OF_PREDECLARED_S0_ESTIMATOR_WITH_PRE_9B_NUMERIC_VALUE_EXPOSURE_DISCLOSED_AND_BOOTSTRAP_UNCERTAINTY`:
load the already-persisted 371 target-level values, verify
artifact/dataset identity, formally freeze the exact estimator value,
and execute only the predeclared §14 bootstrap — zero parameter
changes, no re-derivation of geometry.

Full detail, quality-count denominator semantics, and the zero-distance
diagnostic audit: `s0_pre_9b_exposure_audit_9a1.json` and
`CHECKPOINT_9A_EVIDENCE_SUMMARY.json.s0_numeric_exposure_correction_9a1`.

## 21. Checkpoint 9B — formal freeze of the predeclared S0 estimator, with target-event-level percentile bootstrap uncertainty

**Purpose, precisely**: 9A intended Checkpoint 9B to perform the first
FORMAL S0 computation; 9A's own diagnostic accidentally exposed the
identical point estimator first; 9A.1 disclosed and froze that fact.
9B formally re-derives the UNCHANGED estimator from the exact persisted
371-target dataset and executes the predeclared bootstrap. 9B is **never**
`FIRST_COMPUTATION_OF_S0`/`FIRST_LOOK_AT_S0`/`UNSEEN_S0_ESTIMATION` —
its actual purpose is
`FORMAL_FREEZE_OF_PREDECLARED_S0_ESTIMATOR_WITH_PRE_9B_NUMERIC_VALUE_EXPOSURE_DISCLOSED_AND_BOOTSTRAP_UNCERTAINTY`.

**No 9A geometry rerun**: `services/model_development/{rate_s0_bootstrap_9b.py,rate_input_identity_9b.py,rate_protocol_9b.py}`
have zero DB/geospatial/direction/weather dependency (verified
structurally, 9B-FIREWALL-01..03) — they start from the already-
persisted `rate_target_level_readiness_9a.csv` and (for provenance
only) `rate_origin_target_observations_9a.csv`; `SQLiteOutbreakRepository`,
`build_forecast_targets`, `get_eligible_sources`, `classify_target_primary_scope`,
`distance_km`, and `pyproj.Geod` are never called.

**Canonical input-dataset identity** (Part 4): raw file
`input_csv_sha256 = 71e7d82f974d1dd01911c45fbbfd7121ef07e915212c3f7004fef6120399b183`
(identical to the hash already recorded for this file in Checkpoint
9A's evidence summary — confirming the file was never touched).
Canonical scientific payload — sorted `[target_event_id,
exact-persisted-numeric-text]` pairs, numeric value kept as a JSON
string (never round-tripped through a Python float) —
`canonical_payload_hash_from_persisted_text = ebbd08e30c14f91e17110dfe42a20b7239812a4f307f3edc2137cde98ca6202f`.
`n_rows=371`, `n_unique_target_event_id=371`, validation status
`ALL_ROWS_FINITE_NONNEGATIVE_UNIQUE_TARGET_EVENT_ID`.

**Zero counts kept distinct** (Part 5): `n_zero_distance_origin_target_observations=12`
(origin-target diagnostic, cross-checked against the real CSV) vs.
`n_zero_target_level_median_rates=4` (target-level, from the same 9A.1
finding) — never conflated.

**Bootstrap implementation identity frozen** (Parts 6-7): Python
stdlib `random.Random(42)`, sampling primitive `Random.randrange(n)`,
`n=371` draws WITH replacement per replicate, `statistics.median` per
replicate — no NumPy, no weighted/Bayesian/BCa/cluster/hierarchical
bootstrap. `bootstrap_implementation_source_sha256 = c218b891351fa96a379495c3658c6cab782556bf37e7c424fe40ad25f5b73b55`
(SHA256 of `rate_s0_bootstrap_9b.py`'s exact source).

**Quantile endpoint method frozen explicitly** (Part 8): standard
linear-interpolation empirical quantile,
`Q(q)=b[floor(pos)]+frac*(b[ceil(pos)]-b[floor(pos)])`, `pos=(B-1)*q`,
`q_lower=0.025`, `q_upper=0.975` — verified against hand-computed toy
values (9B-QUANT-01), never an unspecified library default.

**9B protocol hash**:
`s0_bootstrap_protocol_hash_9b() = 969161e318508edfa2465d2f4598dbca17fcf29ef01bba2df42bec8093835d28`
(binds the parent 9A hash, 9A.1 exposure classification, dataset
identity, bootstrap/RNG/quantile identity, zero counts, D1-D7/25km/
retrospective-limitation identity, firewalls, and every scientific
limitation below; never a timestamp).

**Pre-bootstrap manifest, written and verified BEFORE execution**
(Parts 12-16): `pre_bootstrap_freeze_manifest_9b.json` written first;
closed and re-read from disk to compute
`pre_bootstrap_manifest_file_sha256 = 622562e544b3d92541321239251efaf08edcb624ceb763cc530ed96f2431569b`,
persisted in a separate sidecar; the runner then RE-LOADS both files
from disk and verifies the sidecar hash, the protocol hash, and the
371/371 counts — only after every check passes does the real bootstrap
execute. Refuses to run if any 9B result artifact already exists
(verified: a second invocation of the runner was rejected with an
explicit "REFUSING TO RUN" error).

**Real, one-time bootstrap result**: point estimate
**`3.946421443154751` km/day** (n=371 target events) — exactly
reproduces the already-exposed 9A.1 value, as required; the runner
would have STOPPED had it not matched. 95% target-event-level
percentile bootstrap interval: **`[3.549, 4.343]` km/day**
(`3.5491046170907765` to `4.343077329563724`), seed `42`, 1000
resamples. Bootstrap-draw diagnostics (audit only, never used to
change method): min `3.400`, median `3.946`, max `4.563`.

**Result immutability**: every result artifact's SHA256 computed and
persisted in `checkpoint_9b_audit.json` after the run; post-run tests
(9B-POST-01..08) verify the persisted 1000 draws, recompute the CI
from those persisted draws only (never regenerating real bootstrap
replicates), and confirm no test in the suite calls the bootstrap
functions on the real 371-value dataset (only on synthetic toy
vectors).

**Required scientific limitations, persisted verbatim** (Part 23,
`frozen_s0_apparent_rate_spec_9b.json.result_interpretation_limitations`):
apparent geometric historical rate, not biological transmission speed;
recorded event dates are occurrence-time proxies, not exact infection/
transmission times; nearest known eligible source is a geometric
reference, not a confirmed causal parent; conditional on the frozen
D1-D7/25km protocol; GPS/reporting uncertainty remains; the target-
event bootstrap does not model country/outbreak/reporting-system/
spatial-cluster/calendar-period dependence; the interval is empirical
sampling uncertainty under the declared resampling assumption, not
complete epidemiological uncertainty; the 1000-replicate percentile
endpoints carry unquantified finite Monte-Carlo error; this is
development historical evidence, not a held-out or Sri Lanka-specific
result.

**Nominal reach**: `NOT_COMPUTED_IN_9B` — no `S0 * day_h` computed
here; a separate later integration checkpoint.

**Tests**: 43 new (`tests/test_checkpoint_9b_rate_bootstrap.py` — 33
pre-execution + 8 post-execution artifact + 2 evidence-summary
consistency). Full backend regression: **1437/1437 passed, 0 failed, 0
skipped** (1394 baseline + 43 new).

**Final Checkpoint 9B classification:
`FROZEN_DEVELOPMENT_DERIVED_S0_ESTIMATED_APPARENT_LOCAL_SPREAD_FRONT_RATE_WITH_PRE_9B_NUMERIC_EXPOSURE_DISCLOSED_AND_TARGET_EVENT_BOOTSTRAP_UNCERTAINTY`.**

## 22. Checkpoint 9C — deterministic nominal-reach derivation and frozen scientific component integration contract

Checkpoint 9C performs **no model development and no predictive
evaluation**. It asks only how the already-frozen risk score (7C),
descriptive direction field (8B.3), and apparent historical rate (9B)
should be represented together, plus one new deterministic derived
quantity, without conflating any of their scientific meanings
(`FROZEN_COMPONENT_INTEGRATION_SEMANTICS`).

**Nominal reach, frozen** (`services/integration/nominal_reach_9c.py`):

```
nominal_reach_km(day_h) = frozen_S0_rate_km_day * day_h
```

using `frozen_S0_rate_km_day = 3.946421443154751` (the already-frozen
9B point estimate, imported directly — never recomputed), for
`day_h ∈ {1,...,7}` only. Label: **"Nominal Day-h local reach — not a
hard disease boundary"** — the word NOMINAL is scientifically
load-bearing. This is ONLY a deterministic visualization/context
quantity; it is never a maximum transmission distance, infection
radius, quarantine boundary, risk-surface boundary, probability
contour, guaranteed travel distance, or biological epidemic-front
location. An optional derived interval is a pure multiplication of the
two already-frozen 9B bootstrap endpoints
(`3.5491046170907765`/`4.343077329563724` km/day) — no new bootstrap is
run; `services.model_development.rate_s0_bootstrap_9b` is never
imported by the 9C integration modules (verified, 9C-UNC-01,
9C-FIREWALL-03).

**Real D1-D7 result** (deterministic arithmetic, not a "run" in the
sampling sense):

| day | nominal_reach_km | derived interval (km) |
|---|---|---|
| 1 | 3.946421443154751 | [3.549, 4.343] |
| 2 | 7.892842886309502 | [7.098, 8.686] |
| 3 | 11.839264329464253 | [10.647, 13.029] |
| 4 | 15.785685772619004 | [14.196, 17.372] |
| 5 | 19.732107215773755 | [17.746, 21.715] |
| 6 | 23.678528658928506 | [21.295, 26.058] |
| 7 | 27.624950102083258 | [24.844, 30.402] |

**Day 7 nominal reach (`27.62` km) exceeds the frozen 25km operational
local evaluation envelope — this is expected, not an error, and the
two quantities are never reconciled** (min/max/clip) against each
other (9C-REACH-02..04). D8-D14 exploratory horizons are explicitly
out of scope for this checkpoint's primary contract
(9C-REACH-06).

**Risk stays static under the frozen C0 model**: the presentation
contract states `risk_surface_temporal_semantics =
STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT` explicitly — nominal reach
never modifies the C0 cell score, and no day-varying risk surface is
fabricated (9C-RISK-02/03, `NO_C0_MODIFICATION_RULE_9C`,
`NO_FAKE_DAILY_RISK_RULE_9C`).

**Direction/rate independence preserved**: rate is never derived from
bearing/clarity/wind speed/C0 score, and direction is never scaled
into km/day (9C-DIR-01, `DIRECTION_RATE_INDEPENDENCE_RULE_9C`).
`directional_clarity` is never called confidence (9C-DIR-02, checked
by dataclass field-name inspection, not a text scan). Bearing `0.0` is
retained as valid NORTH; unavailable direction stays `None`, never
fabricated to `0.0` — every check uses `is not None` (9C-DIR-03/04).

**Internal DTO, no HTTP yet**
(`services/integration/geospatial_intelligence_contract_9c.py`):
`FrozenGeospatialIntelligenceContract9C` — `risk`, `direction`,
`apparent_rate`, `nominal_reach_by_day`, `operational_evaluation_envelope_km`
(frozen `25.0`, always a field separate from `nominal_reach_by_day`),
`provenance`, `limitations`. The DTO performs no scientific
computation itself — `risk_score` and the direction tendency are
supplied by the caller from the already-frozen 7C/8B.3 services;
`apparent_rate`/`nominal_reach_by_day` are pure frozen-constant
transforms (`default_apparent_rate_component_9c` takes zero
arguments — 9C-DIR-01 structural proof).

**Versioned protocol identity**
(`services/integration/geospatial_intelligence_protocol_9c.py`): binds
every frozen parent hash (7C candidate/spec, 8B.3 direction method,
historical 9A, 9B bootstrap protocol, 9B input/canonical dataset
SHA256s), the nominal-reach formula/D1-D7 range, the frozen rate
point/CI, the 25km-vs-reach separation rule, and every semantic rule
above into one deterministic hash, excluding any timestamp/absolute
path/UI styling/URL —
`integration_protocol_hash_9c()=cec826a26c860c752d1fa32d94edcdfba2e0186950cdccfc96067fef2ce51a90`.
The 9B protocol hash and both rate-dataset SHA256s are copied literally
from the already-frozen Checkpoint 9B result (never re-read from the
gitignored `local_data` tree here) — verified byte-identical against
the real disk-computed value in this environment.

**Tests**: 28 new
(`tests/test_checkpoint_9c_integration.py` — 9C-PARENT-01..05,
9C-RATE-01/02, 9C-REACH-01..06, 9C-UNC-01, 9C-RISK-01..03,
9C-DIR-01..04, 9C-SOURCE-01, 9C-PROV-01, 9C-HASH-01,
9C-FIREWALL-01..03, plus a never-skipping evidence-summary consistency
check). Full backend regression: **1465/1465 passed, 0 failed, 0
skipped** (1437 baseline + 28 new).

**Final Checkpoint 9C classification:
`FROZEN_GEOSPATIAL_RISK_DIRECTION_APPARENT_RATE_AND_NOMINAL_REACH_INTEGRATION_CONTRACT_READY_FOR_API`.**
Full design: `GEOSPATIAL_INTELLIGENCE_INTEGRATION_PROTOCOL.md`.

## 23. Checkpoint 9C.1 — rate-scope conditioning diagnostic (S0 retained, interpretation made explicitly conditional)

**Purpose** (`POST_FREEZE_RATE_SCOPE_CONDITIONING_DIAGNOSTIC`): the
frozen 9A/9B inclusion rule is `d_min <= 25 km` with `v_obs = d_min /
lead_days`. This means every INCLUDED origin-target observation at
lead `h` has a mathematically forced upper bound
`v_obs <= 25/h` km/day — a consequence of the frozen envelope, not
something derived from observed rate values. This checkpoint diagnoses
that structural conditioning; it does **not** retune the rate, select
an alternate S0, fit S1, optimize scope, try an alternate radius, or
inspect held-out/Sri Lanka rate data. **The historical 9B result is
unchanged: S0 remains `3.946421443154751`, CI remains
`[3.5491046170907765, 4.343077329563724]`.**

**Theoretical ceiling table** (`services/model_development/rate_scope_conditioning_9c1.py::theoretical_ceiling_km_day`,
`= PRIMARY_LOCAL_EVALUATION_DISTANCE_KM / lead_days`, the frozen 25km
constant imported directly, never a second literal):

| lead | theoretical ceiling (km/day) |
|---|---|
| D1 | 25.0 |
| D2 | 12.5 |
| D3 | 8.333333333333334 |
| D4 | 6.25 |
| D5 | 5.0 |
| D6 | 4.166666666666667 |
| D7 | 3.5714285714285716 |

**D7 theoretical ceiling (`3.571`) is strictly less than the frozen S0
(`3.946`)** — explicitly acknowledged (9C1-MATH-02). A pre-frozen
threshold is not automatically a neutral sampling rule for a pooled
km/day rate: applying the same fixed distance threshold across
different lead times induces a lead-dependent upper bound on included
`v_obs`. This is characterized as `RATE_SCOPE_CONDITIONING` /
`LEAD_DEPENDENT_TRUNCATION_MECHANISM` — never called a software bug,
data leakage, or p-hacking, since none of those were established by
this diagnostic.

**Real diagnostic run** (read-only over the already-persisted 9A CSVs,
`smoke_tests/run_rate_scope_conditioning_9c1.py`, input
`rate_origin_target_observations_9a.csv` SHA256
`d67f02709a2ddac8b5f02cb4ebacafe42242229deafea153c600fb2bbd714a2d`
verified against the already-evidenced Checkpoint 9A artifact identity
before anything else ran):

- Pooled per-lead reconciliation: `3947 = 1387 WITHIN + 2560 OUTSIDE +
  0 unresolved`, exactly matching the frozen 9A/9A.1 population.
- Every WITHIN v_obs satisfies `v_obs == d_min_km / lead_days` and
  `v_obs <= 25/lead_days` within numerical tolerance — no invariant
  violation, no STOP triggered.
- Target-event inclusion: 879 unique `target_event_id` across all
  3947 rows; 371 have >= 1 WITHIN observation (exactly matching
  `rate_target_level_readiness_9a.csv`); 508 only-OUTSIDE; 124
  mixed; 247 only-WITHIN.
- Zero-distance diagnostic re-verified unchanged: 12 zero-distance
  rows, 4 unique target events, all 12 with `target_gps_quality =
  UNKNOWN` and `target_coordinate_collision_status = UNKNOWN`.
- GPS-quality composition by lead (primary VALID/WITHIN rows only,
  descriptive, no exclusion): `target_gps_quality`/
  `nearest_source_gps_quality` counts persisted per lead in
  `gps_quality_by_lead_rate_audit.json`.

**Current S0 interpretation, made explicit**
(`RATE_ESTIMAND_CONDITIONING_9C1 = D1_D7_TARGET_EVENT_APPARENT_RATE_CONDITIONAL_ON_AT_LEAST_ONE_VALID_25KM_LOCAL_SCOPE_OBSERVATION_UNDER_RETROSPECTIVE_PROXY`):
"The frozen S0 is a development-derived apparent historical local-rate
summary conditional on the predeclared 25-km operational local-scope
inclusion mechanism. Because d_min <= 25 km is applied across D1-D7,
the included origin-target apparent rates have lead-dependent upper
bounds of 25/h km/day." Never described as unbiased spread speed,
population-wide LSD rate, general transmission velocity, Sri Lanka
disease speed, or biological front velocity.

**Nominal reach interpretation hardened, numbers unchanged**: the
Checkpoint 9C D1-D7 nominal reach values (`3.946`...`27.625` km) and
the 25km operational envelope are byte/numerically unchanged
(9C1-REACH-01). Added interpretation: "D7 nominal reach is a
deterministic visualization extrapolation from the pooled frozen S0.
It exceeds the 25-km operational envelope even though the empirical
rate dataset was conditioned by that 25-km inclusion rule. It is
therefore not evidence that a D7 epidemic front was empirically
validated beyond 25 km."

**Bootstrap interpretation, unchanged and now scoped explicitly**: the
frozen 9B interval quantifies empirical target-event resampling
uncertainty CONDITIONAL ON the frozen selected 371-target dataset — it
does not account for 25-km scope-selection uncertainty, the
lead-dependent truncation mechanism, GPS/reporting measurement error,
or country/spatial/temporal higher-level dependence. The existing 9B
higher-level-dependence and finite-Monte-Carlo limitations (A-I) remain
unchanged.

**No alternate S0 anywhere in this checkpoint**
(`NO_ALTERNATE_POOLED_S0_CALCULATED_IN_9C1`): no competing pooled
estimator was computed using all 3947 rows, OUTSIDE rows, an alternate
radius, EXACT-only GPS, zero-excluded rows, or a per-lead replacement
estimator (9C1-NOALT-01, structurally verified — no
`statistics.median`/`statistics.mean` call anywhere in the 9C.1
modules).

**Non-destructive protocol identity**
(`services/model_development/rate_scope_conditioning_protocol_9c1.py`):
`rate_scope_conditioning_protocol_hash_9c1()=26168ca784b5f8cb5393db872baa1e7e7f1d74f782b16df17c97354b9bf52b8f`,
binding the historical 9A/9B/9C hashes (read, never modified), the
verified input CSV SHA256, the frozen S0/CI, the D1-D7 horizon, the
25km envelope, the v_obs/theoretical-ceiling formulas, and every
audit-only/no-alternate-S0/no-held-out/no-Sri-Lanka/GPS-quality-audit
semantic, excluding any timestamp/absolute path/API/UI field.

**Tests**: 24 new
(`tests/test_checkpoint_9c1_rate_scope_conditioning.py` —
9C1-PARENT-01..03, 9C1-MATH-01/02, 9C1-COUNT-01/02, 9C1-RATE-01/02,
9C1-TARGET-01, 9C1-GPS-01, 9C1-ZERO-01, 9C1-NOALT-01,
9C1-FIREWALL-01..04, 9C1-REACH-01, 9C1-SEM-01/02, plus protocol-hash
determinism and two tracked evidence-summary consistency/SHA256
checks). Full backend regression: **1489/1489 passed, 0 failed, 0
skipped** (1465 baseline + 24 new).

**Final Checkpoint 9C.1 classification:
`RATE_SCOPE_CONDITIONING_AUDIT_COMPLETE_PRIMARY_S0_RETAINED_WITH_EXPLICIT_CONDITIONAL_INTERPRETATION`.**
