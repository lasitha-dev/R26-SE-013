# ST-DBSCAN-Style Outbreak Context Clustering Protocol — Checkpoint 6B

This document specifies the deterministic spatiotemporal density-based
clustering layer built in `services/stdbscan/`. It is a **custom,
self-designed deterministic core/border/noise algorithm inspired by the
general ST-DBSCAN family of spatiotemporal density-clustering methods**
(joint spatial+temporal epsilon neighborhoods, core/border/noise
density roles). It is **not** presented as a byte-for-byte
reproduction of any single published ST-DBSCAN paper's exact
algorithm — where this implementation makes its own design choice
(notably the border-point tie-break rule, and the approximate-GPS core
support guard), that is stated explicitly below rather than attributed
to a source that does not specify it.

## 1. Permanent scientific framing

This module performs **"spatiotemporal density-based outbreak context
clustering"**, also written **"ST-DBSCAN-style outbreak context
clustering."** A cluster produced by this module is **never** evidence
that:

- one member outbreak caused another,
- members form a transmission chain,
- every member is epidemiologically linked,
- a cluster's spatial extent is a disease's infection boundary,
- a cluster's start date is a disease's "infection start", or
- a cluster's centroid is a "disease origin."

No field anywhere in `services/stdbscan/` or its outputs is named
`transmission_chain`, `causal_parent`, or `infected_by_cluster` — this
is verified structurally (dataclass field names, not just prose) by
`tests/test_stdbscan.py::test_st_17_no_causal_or_transmission_chain_field`.
An optional convex-hull-style spatial summary, if ever added, must be
labeled a "context envelope," never a "predicted spread boundary."

## 2. Joint neighborhood definition

Two usable sources `a` and `b` are neighbors if and only if **both**:

1. `geodesic_distance_km(a, b) <= eps_space_km` (WGS84 geodesic via
   `services/geospatial/distance.distance_km`, never raw lat/lon
   degrees treated as kilometers), **and**
2. `abs(event_date(a) - event_date(b)) <= eps_time_days`.

Both boundaries are **inclusive** (`<=`, not `<`). A point is always
its own neighbor (self-inclusion) — this is documented and tested
(`ST` tests), and is what makes "self counts as one support" (§4)
well-defined. Implemented in `services/stdbscan/neighborhood.py`.

## 3. Temporal coordinate: `cluster_event_date`

Clustering's temporal axis is **`cluster_event_date`**, resolved via
`services/stdbscan/event_date.resolve_cluster_event_date`, which reuses
`services/historical_event_date.derive_historical_event_date`
unmodified — **no new fallback chain is introduced.**
`cluster_event_date` is a genuinely separate concept from the
`effective_availability_date` that made a source eligible in the first
place (Part 6/7 distinction): availability answers "when could this
system have known about it"; `cluster_event_date` answers "when did
the underlying event occur, insofar as the historical record states
it."

Rule: `cluster_event_date <= t0` is required for a source to be
`ST_USABLE`. If `cluster_event_date` cannot be derived, or derives to a
date strictly after `t0`, the source is marked `ST_TEMPORAL_UNUSABLE`
for clustering — it is **never silently dropped from the active-source
set**, and the pipeline **never substitutes** `report_date`, a final
follow-up date, or a future confirmation date to paper over a missing
event date.

## 4. Core / border / noise / temporal-unusable roles

Each `ST_USABLE` source is assigned exactly one `cluster_role`:

- **CORE**: the number of *distinct* `core_support_id`s (§5) among its
  joint neighbors, including itself, is `>= min_core_supports`.
- **BORDER**: not core, but joint-neighbors at least one core point.
- **NOISE**: neither core nor border. **Noise is retained, never
  deleted** — it keeps its `source_id`, gets `cluster_id=None`,
  `is_noise=True`, `cluster_role="NOISE"`, and remains a fully valid
  member of the active-source set for later PISTES risk logic. This is
  a **permanent rule**: ST-DBSCAN clustering must never gate or delete
  a confirmed outbreak source, no matter how isolated it is spatially
  or temporally.
- **TEMPORAL_UNUSABLE**: not passed into clustering at all (§3); still
  present in the source-level assignment map with this explicit role.

`min_core_supports` counts **support identities**, not a raw headcount
of neighbor rows — see §5.

## 5. Approximate-GPS core-density guard (`core_support.py`)

**The problem this guards against**: several outbreak records that all
carry the *same imprecise placeholder coordinate* (e.g. a country or
province centroid used because no farm-level GPS was available) must
never be allowed to manufacture an artificially dense "cluster" purely
because they share that placeholder — that would be a GPS-resolution
artifact, not real spatial density.

**The rule**: every `ST_USABLE` source gets a `core_support_id`:

- `EXACT` and `UNKNOWN` GPS quality: each record gets its **own**
  unique `core_support_id` (quality is retained on the record; it is
  never treated as evidence of density collapse).
- `APPROXIMATE` / `COARSE` GPS quality sharing a **documented
  coordinate-collision group** (coordinates rounded to 6 decimal
  places, mirroring the convention already used in
  `services/coordinate_collision.py`): all records in that group
  collapse to **at most one** `core_support_id` for that location —
  they can jointly contribute no more than a single unit of
  core-density support.

Under `EXACT_ONLY_CORE_SUPPORT` policy (§6), only `EXACT` records ever
receive a real `core_support_id`; every other quality gets `None` and
can never be core (though it can still be border or noise).

This guard is explicitly **not** a claim of statistical independence —
it does not assert that the collapsed records are independent
observations in any inferential sense, only that they must not be
double-counted as separate *density* evidence at a location whose
true precision cannot support that claim. No record is ever deleted by
this guard; it only affects the *support-counting* step above.

## 6. Two GPS core policies

`STDBSCANConfig.gps_core_policy` is one of:

- `PRIMARY_CORE_SUPPORT` (default): the collapse rule in §5 applies.
- `EXACT_ONLY_CORE_SUPPORT` (stricter sensitivity mode): only `EXACT`
  records can ever be core; everything else can only be border, noise,
  or (if `ST_TEMPORAL_UNUSABLE`) excluded from clustering entirely.

**Neither mode is chosen using held-out performance in this
checkpoint** (or ever, per Part 11) — both are run and reported
side-by-side in the development-sensitivity output (§10) as descriptive
counts only.

## 7. Determinism

Every step that could otherwise depend on iteration/input order is
made explicit and stable:

- Neighbor-graph construction and the core/border/noise passes always
  iterate over `sorted(source_id)`, never raw input order.
- Connected components among CORE points are found via a
  sorted-seed, sorted-neighbor depth-first traversal — reordering the
  input `usable_points` list can never change which points end up in
  which component.
- **Border tie-break** (a self-designed rule, stated explicitly as
  such — no external paper is cited for this specific mechanism): when
  a border point's joint neighborhood touches core points from more
  than one cluster candidate, it is assigned to the cluster whose core
  member is at the **smallest real geodesic distance**; ties are
  broken by comparing each candidate cluster's **preliminary
  fingerprint** — a SHA-256 hash of that cluster's own sorted
  core-only membership, computed before border assignment — and
  choosing the lexicographically smallest. This is fully deterministic
  and never depends on processing order.

## 8. Deterministic cluster IDs

`cluster_id` is `f"STCLUSTER:{sha256(sorted(member_source_ids) + config_hash + forecast_origin_id)[:24]}"`
(`services/stdbscan/cluster._stable_cluster_id`) — **never** a
positional label like `cluster_0`/`cluster_1`. Reordering the input
source list never changes a cluster's ID, because the ID is derived
purely from its own (sorted) content plus the config and forecast
origin that produced it.

## 9. Configuration and parameter status (`config.py`)

`STDBSCANConfig(eps_space_km, eps_time_days, min_core_supports,
active_window_days, gps_core_policy, parameter_status, config_version)`
carries a content-derived `config_hash()` (SHA-256 of its canonical
JSON) and a `parameter_status` that is one of:

- `SOFTWARE_FIXTURE_ONLY` — synthetic or clearly-labeled smoke-test
  values; never described as "optimal", "best", or "final"; no model
  decision may depend on a smoke test's resulting cluster counts.
- `UNFROZEN_DEVELOPMENT_CANDIDATE` — a real, `FIT_DEVELOPMENT`-derived
  candidate under active sensitivity analysis.
- `FROZEN_REFERENCE` — **structurally forbidden to construct in
  Checkpoint 6B**: `STDBSCANConfig.__post_init__` raises `ValueError`
  if `parameter_status == FROZEN_REFERENCE`. No configuration may be
  declared scientifically final in this checkpoint.

## 10. Development-only parameter candidates (`parameter_candidates.py`, `development_sensitivity.py`)

Per Part 17, `active_window_days` candidates are **fixed, not
data-derived**: `(7, 14, 21, 28)`. `eps_space_km` / `eps_time_days`
candidates are transparent descriptive quantiles computed **only** from
`FIT_DEVELOPMENT` records (Sri Lanka and 2024+ records structurally
excluded before any quantile is computed): nearest-neighbor geodesic
spatial-distance quantiles, and *positive* inter-event temporal-gap
quantiles (same-day pairs, i.e. zero-gap, are excluded from the
temporal quantile so they cannot silently collapse it to zero).
Pathological inputs (e.g. a single record with no possible neighbor)
are reported via `pathological_note`, never silently capped or hidden.

The development-sensitivity report aggregates real `STClusterSnapshot`s
across a bounded, real `FIT_DEVELOPMENT` origin sample for a given
candidate config: origins evaluated, usable/temporal-unusable counts,
cluster count, noise count and fraction, cluster-size distribution,
largest-cluster fraction, GPS-quality composition, and
approximate-coordinate support-collapse count. It reports
`PRIMARY_CORE_SUPPORT` vs `EXACT_ONLY_CORE_SUPPORT` side-by-side. It
has **no access to any target/outcome field at all** — there is no
prediction-accuracy, risk-capture, direction-error, or speed-error
field anywhere in its output (structurally verified by
`tests/test_stdbscan_development_sensitivity.py`).

**Observed real result** (Thailand `FIT_DEVELOPMENT` sample, 136
origins): at the tightest data-derived candidates (`eps_space_km≈4.44`
= corpus-wide p50 nearest-neighbor distance, `eps_time_days=3` =
corpus-wide p75 positive gap), **zero clusters formed** across all
active-window-day candidates and both GPS policies — essentially all
usable sources landed as noise. A direct check across a single real
origin confirmed the mechanism itself is not broken: the same origin
produces real 2-member clusters once `eps_space_km` is widened to
50-100km. This is reported honestly as a real sensitivity finding, not
adjusted or hidden: Thailand's real recorded outbreak-point spacing is
evidently wider than the corpus-wide median nearest-neighbor distance
at these tight thresholds. No config was chosen or preferred based on
this — it is descriptive-only.

## 11. Development/held-out firewall — CORRECTED in Checkpoint 6B.5

**Checkpoint 6B's original design was too soft.** `parameter_candidates.build_parameter_candidate_report`
filtered to `FIT_DEVELOPMENT` internally, but computed candidate
geometry directly from raw `HistoricalOutbreakRecord`s — "model_candidate/
dedup filtering is the caller's own responsibility" — and admitted a
record via `historical_event_date < cutoff` alone, which confuses
availability (WHETHER a source may be used) with occurrence (WHERE it
lies on the temporal axis): a record with a pre-cutoff biological event
but availability evidence dated at/after the cutoff was wrongly
admitted. Separately, `development_sensitivity.build_config_sensitivity_report`
only documented the precondition that its `fit_development_origins`
argument must already be pre-filtered — it never checked.

**Checkpoint 6B.5 replaced both with hard gates, never caller
discipline:**

- `services/stdbscan/development_source_universe.build_fit_development_source_universe`
  is now the ONLY safe path to real parameter-candidate geometry. It
  reuses `source_selector.get_eligible_sources` (which already enforces
  `model_candidate=True`, resolved dedup, valid coordinates, and the
  `t0`-window bound) across every real `FIT_DEVELOPMENT` origin's
  28-day superset window, then classifies every real historical record
  for the disease into "validated" or "excluded with one specific,
  reported reason" — see §15 below. `parameter_candidates.build_parameter_candidate_report`
  (the old raw-record path) is kept ONLY as a pure, lower-level function
  for tests — it is `SUPERSEDED_BY_6B5` and never called from the real
  pipeline.
- `model_fitting_exposure.assert_fit_development_only` is a new hard
  firewall: `development_sensitivity.build_config_sensitivity_report`
  and `international_sensitivity.build_international_development_sensitivity_report`
  both call it at their OWN entry point, and it **raises** `ValueError`
  — never silently filters — the instant any supplied origin is not
  `FIT_DEVELOPMENT`. A single `HELD_OUT_FROM_MODEL_FITTING` or
  `SRI_LANKA_TRANSFER_CASE_STUDY` origin mixed into an otherwise-valid
  list rejects the entire call, not just that one origin.

## 12. Inputs and eligible active-source set

Clustering's spatial candidate pool is the existing
`services.source_selector.get_eligible_sources` result, called with
`domain_scope=HISTORICAL_ONLY`, `temporal_mode=RETROSPECTIVE_PROXY`,
already-resolved dedup, `effective_availability <= t0`, valid
coordinates, and the config's `active_window_days`. It is called the
**"eligible active-source set,"** never the "infectious source set" —
this module makes no claim about infectiousness. Future forecast
targets never enter this set (the same T0 invariant already enforced
by `get_eligible_sources` in earlier checkpoints).

## 13. Snapshot contract (`snapshot.py`)

`STClusterSnapshot` carries: `forecast_origin_id`, `t0`,
`active_source_ids`, `cluster_usable_source_ids`,
`temporal_unusable_source_ids`, per-source `assignments`, `clusters`,
`noise_source_ids`, `config`, `config_hash`, `gps_core_policy`,
`generated_at` (plus `source_gps_quality`/`source_core_support_id`,
added to support the sensitivity report in §10 without a redundant
second query layer). It contains **no** future target ID, risk value,
probability, direction, speed, or prediction-accuracy field —
`build_st_cluster_snapshot`'s signature structurally accepts no such
parameter at all.

## 14. No pseudo-replication claim

A cluster with N members is **not** N independent experiments. This
module preserves each member's stable source/event identity precisely
so that any later statistical evaluation can group or bootstrap at the
unique-target-event level, never by treating cluster members (or grid
cells) as independent samples.

## 15. Validated development source universe (`development_source_universe.py`, Checkpoint 6B.5)

`build_fit_development_source_universe(repo, forecast_origins, *,
disease)` is the ONLY safe input to real parameter-candidate statistics
(§10/§16). It filters `forecast_origins` to `FIT_DEVELOPMENT` itself
(never trusts the caller), unions `source_selector.get_eligible_sources`
across every such origin's 28-day superset window
(`candidate_constants.MAX_ACTIVE_WINDOW_DAYS`), then classifies EVERY
real historical record for the disease into exactly one outcome:

- **validated** (`DevelopmentSource`, one row per unique `source_id` —
  a source repeated across many origins' windows is never
  pseudo-replicated into multiple rows, §14), or
- **excluded with one specific, reported reason** (`SourceExclusion`):
  `MODEL_CANDIDATE_FALSE`, `UNRESOLVED_DEDUP`, `SRI_LANKA`,
  `INVALID_COORDINATE`, `HELD_OUT_ONLY_AVAILABILITY` (never available
  inside any real `FIT_DEVELOPMENT` origin's window — covers a
  post-cutoff-only proxy date and a source seen only in
  held-out/Sri-Lanka origins alike), or `MISSING_EVENT_DATE` (valid
  coordinates/availability, but no defensible `cluster_event_date` —
  such a source could never be `ST_USABLE` for real clustering
  regardless of parameter choice).

Real corpus result: of 1910 historical records, **657 validated**,
**1253 excluded** (863 `MODEL_CANDIDATE_FALSE`, 390
`HELD_OUT_ONLY_AVAILABILITY`, 0 in the remaining reason categories for
this corpus) — a substantial correction from Checkpoint 6B's unsafe
1278-record count, dominated by records the old path never checked
`model_candidate` on at all. Nothing is hidden: `n_records_considered ==
n_validated_sources + len(exclusions)` always (tested).

## 16. Country-scoped parameter candidates (`parameter_candidates.build_country_scoped_parameter_candidates`, Checkpoint 6B.5)

Operates on a validated `DevelopmentSource` list (§15) — adds no
further eligibility filtering, only country-scoped descriptive
geometry/time statistics:

- **Within-country nearest-neighbor distance**: for each country
  independently, every source's NN distance is computed only against
  OTHER sources in the SAME country — a source in another country can
  never be used as anyone's nearest neighbor here, no matter how close
  it happens to sit. A single-source country is reported with
  `n_unique_sources=1` and `null` quantiles, never merged into another
  country or hidden.
- **Within-country positive temporal gap**: for each country
  independently, sources with a resolvable `cluster_event_date` are
  sorted and consecutive positive gaps computed — a gap can never
  bridge two countries' date sequences.
- **Pooled distributions**: `pooled_within_country_nn_distance_km_quantiles`/
  `pooled_within_country_temporal_gap_days_quantiles` concatenate ONLY
  the within-country values computed above — never a raw global
  cross-country pool.
- **`TEMPORALLY_LOCAL_NN_DISTANCE_AUDIT`**: a separate, explicitly
  descriptive audit (never a replacement for the ordinary within-country
  NN distribution above) — for each dated source, the nearest
  same-country source whose `cluster_event_date` gap is within
  `MAX_ACTIVE_WINDOW_DAYS` (28) days, where one exists. Reveals whether
  spatial scale changes when only temporally-nearby outbreaks are
  considered.

Real corpus result (657 validated sources, 29 countries): pooled
within-country NN distance {p25: 6.05, p50: 12.37, p75: 30.07} km —
substantially wider than Checkpoint 6B's unsafe global figure (p50:
4.44 km), because the old figure was dominated by cross-country
near-coincidences and unresolved-duplicate noise that never should have
counted. Pooled within-country temporal gap {p25: 1.0, p50: 3.0, p75:
10.0} days. Temporally-local NN audit {p25: 6.71, p50: 14.87, p75:
39.05} km. Changes from Checkpoint 6B's figures are expected and
correct, not an error — see `SPLIT_USAGE_FREEZE.md` §6.

Also carries `min_core_support_candidates` (§17) and
`active_window_day_candidates` (§10) so the full candidate registry's
provenance travels with one report.

## 17. `min_core_supports` is also unfrozen (Checkpoint 6B.5 Part 10)

Checkpoint 6B silently held `min_core_supports = 2` constant across its
whole sensitivity sweep — acceptable as a software-fixture default, but
never a scientifically selected value. `candidate_constants.MIN_CORE_SUPPORT_CANDIDATES
= (2, 3, 4)` makes this an explicit, unfrozen parameter-candidate
dimension like the others — never chosen using held-out/Sri-Lanka
outcomes, always reported side-by-side.

## 18. International vs country-specific development sensitivity (Checkpoint 6B.5 Parts 13-15)

Checkpoint 6B's only real development-sensitivity run used Thailand's
136 `FIT_DEVELOPMENT` origins exclusively and did not clearly label the
result as country-specific — risking it being read as global evidence.
Checkpoint 6B.5 draws an explicit line:

- `development_sensitivity.build_config_sensitivity_report` now takes
  an explicit `scope_label` (default `"COUNTRY_SPECIFIC_DEVELOPMENT_SENSITIVITY"`)
  — any country-specific run (e.g. Thailand) must pass
  `scope_label="THAILAND_DEVELOPMENT_SENSITIVITY"` explicitly.
- `services/stdbscan/international_sensitivity.build_international_development_sensitivity_report`
  is new: it runs the REAL, full `FIT_DEVELOPMENT` origin set (579
  origins, all countries) and reports both a MICRO summary (every
  origin pooled, one number) and a MACRO country summary
  (`CountrySensitivitySlice` per country — origin count, usable-source
  *appearances* [explicitly not "sources," since the same real source
  can appear in many origins' windows — never claimed as independent
  evidence, §14], unique source-ID count, cluster/noise counts, GPS
  composition, support-collapse count) — the country dimension is never
  aggregated away, so no single high-origin-count country (Thailand)
  can dominate or hide what other countries look like.

Both share the same hard firewall (§11) and neither has access to any
target/outcome/performance field (structurally verified by
`tests/test_international_sensitivity.py`/`tests/test_stdbscan_development_sensitivity.py`).

## 19. Deterministic reduced sensitivity grid (Checkpoint 6B.5 Part 16)

Executing the full Cartesian product of every candidate dimension
(spatial x temporal x `min_core_supports` x `active_window_days` x
`gps_core_policy`) would be computationally wasteful without adding
real information. `smoke_tests/run_stdbscan_smoke.py`'s
`_build_reduced_grid` declares a **fixed, predeclared reduction rule
BEFORE any config is executed** (never adjusted afterward based on
resulting cluster counts):

1. Pair same-tier spatial/temporal candidates — `LOW` (pooled p25/p25),
   `MID` (p50/p50), `HIGH` (p75/p75) — rather than a full 3x3 cross.
2. Cross those 3 tiers with all 3 `min_core_supports` candidates and
   both `gps_core_policy` values, at a fixed `active_window_days=14`
   (the middle `ACTIVE_WINDOW_DAY_CANDIDATES` value) — 18 configs.
3. Separately sweep the remaining `active_window_days` candidates (7,
   21, 28) at the `MID` tier / `min_core_supports=2` / `PRIMARY_CORE_SUPPORT`
   — 3 more configs.

21 total configs, run against the full real 579-origin `FIT_DEVELOPMENT`
set in ~77 seconds. **A 100%-noise or near-100%-noise result at a tight
tier is retained and reported exactly as computed** — eps is never
widened merely because clusters are visually desirable (Part 17). Any
wide-eps (50-100 km) diagnostic config used elsewhere in this codebase
remains `SOFTWARE_FIXTURE_ONLY`/`SOFTWARE_DIAGNOSTIC_ONLY` and is never
read as a development-candidate-protocol-endorsed scale.

## 20. Checkpoint 6C — ST context has zero numeric hazard influence

Checkpoint 6C's hazard engine (`services/hazard/`, see
`HAZARD_ENGINE_PROTOCOL.md`) consumes ALL eligible active sources —
CORE, BORDER, NOISE, and `ST_TEMPORAL_UNUSABLE` alike — with no numeric
gating or weighting by cluster role. An `STClusterSnapshot` id may be
carried as optional contextual metadata on a `HazardSnapshot`
(`st_cluster_snapshot_id`), but it has zero influence on any hazard
value or on the hazard snapshot's own scientific identity
(`hazard_snapshot_id`). This is a permanent rule, not specific to 6C:
ST-DBSCAN clustering must never be read as gating or gate-like for
hazard/risk purposes in any future checkpoint either.

## 21. Checkpoint 7A.6 — ST-DBSCAN is DESCRIPTIVE SPATIOTEMPORAL OUTBREAK CONTEXT, never a model-development gate

**The mistake this corrects**: Checkpoint 7A.5's real target-scope
classifier reused `STDBSCANConfig.eps_time_days` (a SOURCE-SOURCE
clustering temporal neighborhood parameter, e.g. 3 days in the real
audit candidate) as the temporal gate for evaluating whether a REAL
FUTURE D1-D7 outcome fell within a forecast origin's local evaluation
scope. That conflated two unrelated concepts: a spatially close D4-D7
outcome could be — and in the real 7A.5 audit, was — rejected from local
evaluation purely because the source-target event-date gap exceeded the
3-day clustering epsilon, which has nothing to do with the D1-D7
forecast horizon (already fully and correctly defined by `1 <= lead_days
<= 7`, `services.forecast_target.build_forecast_targets`). This produced
7A.5's real result of only 33/3,947 (0.84%) targets classified
`LOCAL_SCOPE_TARGET` — an artifact of the bug, not a real finding about
local spread. That 7A.5 result is preserved as methodological history
(`SUPERSEDED_ST_TEMPORAL_EPS_TARGET_SCOPE_DIAGNOSTIC`,
`services/model_development/protocol.py`) — never deleted, never reused
for domain freeze, model fitting, model evaluation, or the host-reference
rebuild.

**Permanent distinction, made explicit from this checkpoint onward**:
`eps_space_km`/`eps_time_days`/`min_core_supports`/`active_window_days`/
`gps_core_policy` describe SPATIOTEMPORAL SOURCE CONTEXT — whether
several historical SOURCE records are density-clustered together. They
do NOT, and must never again be used to, define whether a FUTURE D1-D7
TARGET is biologically or evaluatively local. The two concepts live in
completely separate modules from 7A.6 onward:
`services/model_development/local_evaluation_scope.py` (the PRIMARY,
ST-DBSCAN-decoupled evaluation contract — see `MODEL_DEVELOPMENT_PROTOCOL.md`)
vs. `services/model_development/{local_context.py,local_target_scope.py}`
(kept, unmodified, for descriptive/diagnostic purposes only — map cluster
display, source-context summaries, sensitivity analysis, later scientific
discussion).

**ST-DBSCAN membership has ZERO effect (verified structurally,
`ST-DECOUPLE-01..05`) on**: whether an eligible source contributes to the
primary evaluation domain or the later multi-source hazard sum; whether a
scientific grid cell exists; D1-D7 target temporal eligibility; or the
primary evaluation denominator. Primary model development/evaluation
NEVER requires `STDBSCANConfig.parameter_status == FROZEN_REFERENCE` —
which remains, and will remain until real held-out predictive evidence
justifies otherwise, structurally impossible to construct (§8-9). This
is no longer a blocker for baseline model development (Checkpoint 7B).

**ST parameters remain genuinely unfrozen** — this correction does NOT
retroactively freeze `eps_space_km=12.37`/`eps_time_days=3`/
`min_core_supports=2`/`active_window_days=14` as scientific truth merely
to unblock the pipeline; they remain `UNFROZEN_DEVELOPMENT_CANDIDATE`. A
later, separate descriptive-clustering protocol may select a reference
DISPLAY configuration if needed — that selection must never affect model
truth or evaluation.
