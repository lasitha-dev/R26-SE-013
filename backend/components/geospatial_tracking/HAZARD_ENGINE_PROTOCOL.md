# Hazard Engine Protocol — Checkpoint 6C

This document specifies `services/hazard/` — the mathematical hazard
engine FOUNDATION built in Checkpoint 6C. It proves the multi-source
accumulation and relative-risk-index mathematics work correctly; it
does **not** implement a real, calibrated PISTES risk model. No
coefficient is frozen, no real feature is transformed into a hazard
factor, and no output may be read as infection probability.

## 0. Checkpoint 6C.5 — critical CELL-vs-SOURCE indexing correction

Checkpoint 6C's `HazardFactors` grouped `host_factor`,
`environmental_suitability_factor`, and `water_context_factor` under a
single per-SOURCE bag — incorrectly implying these are source-specific
quantities. They are actually properties of the CELL: every source
contributing to a given cell must read the exact same host/
environmental/water values, or the model would let two sources
"disagree" about the very cell they're both hazarding into. Only
`source_strength_factor` is genuinely source-indexed. Checkpoint 6C.5
corrected this BEFORE any real feature->factor transformer was built:

```
CELL i:
  Host_i
  Environmental_i
  WaterContext_i
  Meteorology_i

SOURCE j:
  SourceStrength_j

PAIR (j, i):
  distance_j_i
  t_hat_j_i          (t_hat_east_j_i, t_hat_north_j_i)
  anisotropy_j_i
  H_j_i

CELL RESULT:
  H_i = Σ_j H_j_i
```

`contracts.HazardFactors` is retained ONLY as `LEGACY_6C_FIXTURE_ONLY`
— the primary hazard path (`source_hazard.compute_source_hazard`,
`snapshot.build_hazard_snapshot`) no longer accepts it at all. The real
contracts are `CellHazardFactors(grid_cell_id, host_factor,
environmental_suitability_factor, water_context_factor)` and
`SourceHazardFactors(source_id, source_strength_factor)`. This
correction also introduced: explicit cell-indexed meteorology
(`meteorology.py`, §6 below), a complete-grid contract so an entire
missing cell can never silently vanish (§7), strict extra-/duplicate-
input rejection (§8), a `hazard_input_signature_hash` covering every
effective mathematical input (§9), and numerically safe relative-risk
saturation handling (§10). See `DATA_AUDIT.md` §73 for the full
before/after correction record.

## 1. Permanent scientific label

The engine's output is a **RELATIVE RISK INDEX**. It is never
"infection probability," "chance an animal becomes infected,"
"predicted infection percentage," or any other calibrated
epidemiological claim. A value of `0.72` is never presented as "72%
chance of infection." This label survives until a separate,
explicitly-scoped calibration protocol is completed in a future
checkpoint.

## 2. Architecture and independence

```
services/hazard/
    __init__.py
    contracts.py     — FactorValue, CellHazardFactors, SourceHazardFactors,
                        HazardMixConfig, SourceGeometry, WindVector,
                        status constants (+ legacy HazardFactors, 6C.5 §0)
    kernels.py        — EXPONENTIAL/GAUSSIAN radial kernel primitives
    anisotropy.py      — meteorological alignment + anisotropy factor
    meteorology.py      — CellMeteorology, expand_uniform_meteorology (6C.5)
    protocol.py           — HazardConfig + deterministic config_hash()
    source_hazard.py       — local/anisotropic pathway + per-source H_j_i
    accumulator.py           — all-source summation -> CellHazardResult
    relative_risk.py          — the bounded R = 1-exp(-H) link + saturation status
    snapshot.py                — complete-grid orchestrator + identity (6C.5)
```

Every function consumes explicit structured inputs
(`SourceGeometry`/`WindVector`/`HazardFactors`) — this package never
imports SQLite, FastAPI, React, ST-DBSCAN internals, or the
`features.contracts` module (`FeatureSnapshot`/`GridCellFeatures`)
directly (verified structurally by `tests/test_hazard_no_forbidden_modeling.py::test_nofit_08`).
Wiring real `FeatureSnapshot` values into `HazardFactors` is a
**future, separate transformer — not built in this checkpoint.**

```
FeatureSnapshot raw variables (cattle density, humidity, precipitation,
river distance, mean_u10/mean_v10, ...)
        |
        v  <- FUTURE factor transformation (NOT built in 6C)
dimensionless HazardFactors (host_factor, environmental_suitability_factor,
water_context_factor, source_strength_factor — all [0,1] or >=0,
SOFTWARE_FIXTURE_ONLY only in 6C)
        |
        v
source-specific pathways (local L_j_i, anisotropic W_j_i)
        |
        v
H_j_i = a*L_j_i + b*W_j_i    (source-specific pre-link hazard)
        |
        v  Σ over ALL eligible active sources (never gated by ST role)
H_i = Σ_j H_j_i
        |
        v
R_i = 1 - exp(-H_i)          (BOUNDED RELATIVE RISK INDEX — never probability)
```

Raw environmental values are never directly multiplied into one hazard
equation (Part 3) — their scales are incompatible and no
normalization/transformation protocol has been frozen. `HazardFactors`
is the explicit boundary between raw and dimensionless.

## 3. Factor contract (`contracts.py`)

`FactorValue(value, status)` is the atomic input: `status` is one of
`REAL`, `SOFTWARE_FIXTURE_ONLY`, `MISSING`, `BLOCKED`, `DEMO`.
**Structural guarantee**: only `REAL`/`SOFTWARE_FIXTURE_ONLY` may carry
a non-`None` numeric `value` — `__post_init__` raises otherwise, so a
`MISSING`/`BLOCKED`/`DEMO` factor can never be silently read as a
number by downstream code. In Checkpoint 6C, `HazardFactors` further
requires every usable factor to carry `status=SOFTWARE_FIXTURE_ONLY`
specifically — there is no real feature->factor transformer yet, so a
`REAL` value is refused even though the status exists in the contract
for future use.

**CELL-vs-SOURCE split (6C.5 §0)**: `CellHazardFactors(grid_cell_id,
host_factor, environmental_suitability_factor, water_context_factor)`
— one object per cell, read identically by every source's contribution
to that cell (`host_factor`/`environmental_suitability_factor`/
`water_context_factor` must be within `[0, 1]` when usable — a
**mathematical software contract**, not a probability claim).
`SourceHazardFactors(source_id, source_strength_factor)` — one object
per source, `source_strength_factor` must be `>= 0` when usable, and is
**never** derived from `affected_animals`, DQS, cluster membership, GPS
quality, or case count in this checkpoint — the dataclass has no such
parameter to derive it from at all (structurally verified, NOFIT-04/05,
INDEX-07). The legacy combined `HazardFactors` bag is kept only as
`LEGACY_6C_FIXTURE_ONLY` for old fixtures; `compute_source_hazard`
structurally does not accept it (no `factors=` parameter exists at
all).

## 4. Kernel formulas (`kernels.py`)

Two candidate families, neither scientifically frozen:

    EXPONENTIAL:  K(d; s) = exp(-d / s)
    GAUSSIAN:     K(d; s) = exp(-0.5 * (d / s)^2)

Both guarantee, for `d >= 0` and `s > 0`: `K(0) = 1`; `K(d) in (0, 1]`;
monotonically non-increasing; finite and non-negative for any distance
(no hard reach cutoff — an astronomically large distance may underflow
to `0.0` in float64, which is a representation limit, not a
scientifically imposed truncation). `distance_scale_km` is
`UNFROZEN_DEVELOPMENT_PARAMETER` — never called a "disease spread
radius," "maximum transmission distance," "predicted spread boundary,"
"nominal reach," or "spread-front rate."

**Checkpoint 8B.2/8B.3 note**: for the frozen EXPONENTIAL kernel used
by C0 (`s=25km`), `dK/dd = -(1/s)*K(d)` — this exact derivative is the
algebraic basis of the analytical identity `V = -25km*grad(C0)`
between the C0 scalar field and the C0-derived local geometric vector
field. Checkpoint 8B.2 proved this identity against the wrong local
tangent frame (approximate); Checkpoint 8B.3 corrected the frame so
the identity now holds to convergent numerical precision for the
ACTIVE method. See `DIRECTION_8B_PROTOCOL.md` §19-20 for the full
proof and correction; nothing in this file's kernel formula changed.

## 5. Anisotropy formula and modes (`anisotropy.py`)

**Wind vector semantics**: `mean_u10`/`mean_v10` are meteorological
vector components (`u10` eastward, `v10` northward, matching
`geospatial/weather/wind.py`) — never reconstructed as a compass
bearing, never called "disease direction."

**`meteorological_alignment`**: for source `j` -> cell `i`,

    alignment = t_hat_east * wind_unit_east + t_hat_north * wind_unit_north

clamped only for floating-point safety to `[-1, 1]`. `+1` = cell lies
directly down-vector; `0` = perpendicular; `-1` = directly up-vector.
Never called "disease spread direction," "transmission bearing," or
"confidence."

**Calm wind**: if `hypot(u10, v10) < 1e-6` m/s, direction is undefined
— never a division by zero, never a fabricated direction. Returns
`alignment=None`, `status=CALM_NEUTRAL`, and the anisotropy factor is
exactly `1.0` regardless of `kappa`/mode.

**Anisotropy factor**: `A(alignment, kappa) = exp(kappa * alignment)`,
`kappa >= 0` ("anisotropy strength," never "wind transmission
coefficient," and UNFROZEN). Two explicitly different modes
(`AnisotropyMode`), never mixed:

- `MODULATING`: exactly the formula above. Its direction-averaged value
  over a uniform angular distribution is `I0(kappa)` (modified Bessel
  function, order 0), which grows with `kappa` — total angular mass is
  NOT preserved as `kappa` changes.
- `ANGULAR_NORMALIZED`: `A = exp(kappa * alignment) / I0(kappa)` — the
  same numerator, divided by that same `I0(kappa)` so the
  direction-averaged mass stays `1` regardless of `kappa`.
  `I0` is computed via a self-contained convergent power series
  (`anisotropy._bessel_i0`) — no new dependency.

Both modes agree (`A=1` everywhere) at `kappa=0`. Down-vector factor >
perpendicular factor > up-vector factor for any `kappa > 0`, in both
modes.

## 6. Wind speed and water pathway — explicitly not selected

`G(v)` (a real wind-speed effect on spread) and the real
`distance_to_river -> water_context_factor` transformation are **both
explicitly NOT implemented** in Checkpoint 6C
(`wind_speed_effect_status`/`water_pathway_status =
"NOT_YET_SELECTED"` on `HazardConfig`). Synthetic tests/smoke use a
fixture `wind_speed_factor = FactorValue(1.0, SOFTWARE_FIXTURE_ONLY)`
and a fixture `water_context_factor` — never a real derivation.
HydroLAKES remains unavailable/blocked where applicable (unchanged from
earlier checkpoints).

## 7. Local pathway (`source_hazard.py`)

    L_j_i = Host_i * Environmental_i
            * SourceStrength_j * K_local(distance_j_i)

`Host_i`/`Environmental_i` come from the cell's `CellHazardFactors`;
`SourceStrength_j` from the source's `SourceHazardFactors`. Always
computed when all three factors are usable (the local pathway is never
"disabled" — only the anisotropic pathway has that concept). Every
intermediate component is preserved on
`SourceHazardContribution.local_pathway_components`/`local_kernel` —
never only one opaque number. `compute_source_hazard` verifies
`geometry.grid_cell_id == cell_factors.grid_cell_id` and
`geometry.source_id == source_factors.source_id` itself before
computing anything — dictionary placement alone is never trusted
(6C.5 Part 13, GRID-HAZ-09/10).

## 8. Anisotropic pathway (`source_hazard.py`)

    W_j_i = WaterContext_i * Host_i * Environmental_i
            * SourceStrength_j * anisotropy_factor_j_i * wind_speed_factor
            * K_wind(distance_j_i)

**Disabled vs. missing (Part 29 — HAZMISS-05)**: if
`HazardConfig.anisotropic_pathway_enabled=False`, this pathway
contributes exactly `0.0` with `status=DISABLED_BY_CONFIG` — an
intentional, declared-by-design outcome. If enabled but the wind
vector or any required factor is not usable, the pathway (and the
whole source) becomes `SOURCE_HAZARD_INCOMPLETE` with `value=None` and
an explicit list of missing requirement names — never conflated with
"disabled."

## 9. Source-specific pre-link hazard and mixing (Part 18-19)

    H_j_i = a * L_j_i + b * W_j_i

`a`/`b` (`HazardMixConfig.local_weight`/`anisotropic_weight`) are
**never scientifically chosen** in this checkpoint —
`parameter_status` may only be `SOFTWARE_FIXTURE_ONLY` or
`UNFROZEN_DEVELOPMENT_CANDIDATE`, structurally never `FROZEN_REFERENCE`.
`H_j_i` (the `SourceHazardContribution.source_hazard` field) is
retained per-source specifically because a future spread-direction
calculation will need it — **direction is not calculated in this
checkpoint.**

## 10. All-source accumulation (`accumulator.py`)

    H_i = sum_j H_j_i

over **every** eligible active source, sorted by `source_id` and summed
via `math.fsum` for numerically stable, order-independent floating-point
summation (Part 21). A "nearest source" may be stored for display only
— it never replaces the sum (HAZARD-05).

**ST-DBSCAN never gates a hazard source (Part 6 — permanent rule)**:
CORE, BORDER, NOISE, and `ST_TEMPORAL_UNUSABLE` sources all contribute
identically, provided each independently satisfies the normal
eligible-source contract and has valid geometry for the cell. Nothing
in any hazard function's signature accepts a cluster role, `is_noise`,
`is_core`, or any ST-DBSCAN concept at all — this is a structural
impossibility, not a policy choice that could be silently violated
(verified by `tests/test_hazard_no_forbidden_modeling.py::test_nofit_06`
and `tests/test_hazard_multi_source.py`'s HAZARD-06..09).

**Missing geometry blocks, never silently drops (Part 5)**: the
accumulator takes the FULL `eligible_source_ids` list; any id with no
corresponding contribution makes the entire cell
`CELL_HAZARD_INCOMPLETE`, with an explicit
`"geometry missing for source <id>"` entry — the sum is never quietly
computed over fewer sources than were actually eligible.

## 11. Relative-risk-index link (`relative_risk.py`) — numerically safe (6C.5 Part 19-20)

    R_i = 1 - exp(-H_i)          (computed as -expm1(-H_i))

`H=0 -> R=0` EXACTLY, no epsilon floor; `H>=0 -> 0<=R<1` mathematically;
monotonically increasing; large `H` asymptotically approaches 1. This
is a **BOUNDED RELATIVE RISK INDEX LINK**, not epidemiological
probability calibration. `prior_relative_risk` is accepted only as
`None` in this checkpoint — any non-null value is rejected outright
(`PRIOR_TERM_NOT_SCIENTIFICALLY_DEFINED`). The generalized
`R = 1 - (1-P)*exp(-H)` expression may only be activated after a
separate, scientifically defined prior protocol.

`compute_relative_risk_index` returns `RelativeRiskResult(value,
status)`, never a bare float. `-math.expm1(-H)` avoids the
catastrophic-cancellation precision loss that `1 - exp(-H)` suffers for
small `H`. For sufficiently large `H` (roughly `H > 37`), float64
genuinely cannot represent any value between the true (finite, `<1`)
result and `1.0` — rather than silently returning an unlabeled `1.0`
(quietly weakening the declared `R<1` contract) or silently clamping,
the function detects this and returns `status=NUMERIC_SATURATION_ADJUSTED`
with `value` nudged one float64 step below `1.0`
(`math.nextafter(1.0, 0.0)`). The ordinary case is
`status=FINITE_INTERIOR`. **This is a numerical representation
safeguard, not epidemiological calibration** — it says the software
will never emit an unlabeled exact `1.0`, nothing about the real
probability of an outbreak. `CellHazardResult.relative_risk_status`
preserves this status alongside `relative_risk_index` (tested,
RISKNUM-01..07).

## 12. No temporal invention (Parts 25-27)

The base hazard engine is horizon-agnostic — no D1-D7 day multiplier, no
`D7 = 7 * D1` assumption, and no temporal-decay `lambda` are
implemented or enabled in this checkpoint. No hard maximum-reach gate
exists (`distance > speed * day` is never computed to zero a hazard) —
a kernel evaluated at any real distance always returns a small positive
value, never a truncated zero by rule.

## 13. Provenance (`protocol.py`, Part 30)

`HazardConfig.config_hash()` is a deterministic SHA-256 of every
scientific/mathematical choice: local kernel family/scale, whether the
anisotropic pathway is enabled, anisotropy mode/strength, wind kernel
family/scale, pathway mixing coefficients, factor-contract version,
relative-risk-link version. It **never** includes `generated_at`. Same
config -> same hash; any changed scientific parameter -> changed hash
(tested in `tests/test_hazard_protocol.py`).

## 14. Output contract and identity (Parts 31-32, corrected 6C.5 Part 14-15)

`SourceHazardContribution`, `CellHazardResult`, `HazardSnapshot` carry
every intermediate component listed in Checkpoint 6C's Part 31 spec —
no field is ever named `infection_probability`, `spread_direction`,
`speed`, or `confidence` (structurally verified).

**`hazard_input_signature_hash`** (new, 6C.5 Part 14): a deterministic
SHA-256 of every EFFECTIVE mathematical input to a run — the sorted
expected grid-cell set, every `CellHazardFactors` value+status by cell,
every `SourceHazardFactors` value+status by source, every
`SourceGeometry` identity (`distance_km`/`t_hat_east`/`t_hat_north`) by
cell/source, every `CellMeteorology` (wind vector + wind-speed factor)
by cell, and the active source IDs. Every nested mapping is sorted by
key before hashing (`json.dumps(..., sort_keys=True)` on top of that),
so dictionary insertion order never affects the hash (HAZ-ID-09).
Never includes `generated_at`.

**`hazard_snapshot_id`** (corrected 6C.5 Part 15) is now derived from
`feature_snapshot_id` + `hazard_config_hash` + `hazard_input_signature_hash`
+ sorted `active_source_ids` + the sorted expected grid-cell set —
deterministic, never a random UUID, never `generated_at`. Changing ANY
effective input (a cell factor, a source strength, a wind vector, the
grid-cell set itself) changes `hazard_snapshot_id`; `generated_at`
changing never does (HAZ-ID-01..08). An `STClusterSnapshot` id may be
recorded separately as `st_cluster_snapshot_id` contextual metadata; it
has **zero** numeric influence on the hazard values or on either
identity hash (tested).

## 15. No pseudo-replication / no forbidden modeling

`services/hazard/` imports no `sklearn` fitting/optimization API, never
accesses a future-target coordinate or an outcome label, and performs
no fitting/calibration of any kind (NOFIT-01..03 tests). It is a pure
mathematics module: given explicit inputs, it computes a deterministic
number — nothing here trains, tunes, or learns.

## 16. Software-fixture smoke (Part 40, corrected 6C.5 Parts 17-18)

`smoke_tests/run_hazard_smoke.py` runs a fully synthetic, no-network,
no-DB 3-source x 4-cell demonstration (`label="SOFTWARE_FIXTURE_ONLY"`).
Fixture values follow the corrected indexing: one `(host, env, water)`
triple per CELL (`CELL_N`/`CELL_E`/`CELL_S`/`CELL_W`), one
`source_strength` per SOURCE (`SRC_A=1.0`/`SRC_B=0.8`/`SRC_C=0.6`).
Verifies: every cell has exactly 3 source-specific contributions;
within each cell every source contribution reads the identical host/
environmental/water values while `source_strength` differs (6C.5 Part
18); the multi-source sum is exact; a cell directly down-vector from
the wind gets a strictly larger anisotropy-driven hazard than a
perpendicular or up-vector cell; every relative-risk-index is bounded
in `[0, 1]`; and reordering the source list changes neither any result
nor `hazard_input_signature_hash`. Never compared against real outbreak
outcomes.

An OPTIONAL `REAL_GEOMETRY_SYNTHETIC_FACTORS_DIAGNOSTIC` (real
`geometry_by_source` distances/`t_hat` vectors from an actual
`FeatureSnapshot`, synthetic factors only) is described but not run in
this checkpoint — it requires real GIS/weather adapter access and adds
no additional mathematical proof beyond the synthetic smoke.

## 17. Explicit cell-indexed meteorology (`meteorology.py`, 6C.5 Parts 6-7)

Checkpoint 6C's `build_hazard_snapshot` accepted one `wind`/
`wind_speed_factor` pair for the whole snapshot — a convenient
representation of a deliberately uniform field, but an API that didn't
say so. `CellMeteorology(grid_cell_id, wind_vector, wind_speed_factor)`
makes the cell index mandatory; `wind_by_cell: dict[grid_cell_id,
CellMeteorology]` is the primary contract `build_hazard_snapshot` now
takes. `expand_uniform_meteorology(grid_cell_ids, wind, wind_speed_factor,
mode=MeteorologySpatialMode.UNIFORM_FIELD_FIXTURE)` is the ONLY
sanctioned way to turn one shared vector into that mapping — the
repetition across cells is explicit in both the function's name and its
output, never hidden behind an implicit "just pass one wind" path
deeper in the engine. Real ERA5 cell interpolation is NOT built here —
a future checkpoint may add a new `MeteorologySpatialMode` member for
coarse-grid repetition with provenance, without breaking this shape.

## 18. Complete grid contract (6C.5 Parts 8-9)

`build_hazard_snapshot` iterates `expected_grid_cell_ids` — an explicit,
complete grid definition — never merely `geometry_by_cell.keys()`. A
cell entirely absent from `geometry_by_cell`/`cell_factors_by_cell`
still produces exactly one `CellHazardResult`
(`status=CELL_HAZARD_INCOMPLETE`, `missing_requirements=["missing cell
factor for cell <id>"]`) — it is never silently omitted from
`grid_cell_results` (GRID-HAZ-01/02/06). For every expected cell and
every eligible active source, the orchestrator resolves geometry,
source factors, cell factors, and (when the anisotropic pathway is
enabled) cell meteorology independently; any gap produces an explicit
`SOURCE_HAZARD_INCOMPLETE`/`CELL_HAZARD_INCOMPLETE` outcome with a
named missing requirement — never an uncontrolled `KeyError`, never a
silently-dropped source (GRID-HAZ-04/05, Part 10-11). A complete cell
always has `len(source_contributions) == len(active_source_ids)`
(GRID-HAZ-03).

## 19. Extra-input safety (6C.5 Part 12-13)

`build_hazard_snapshot` raises `ValueError` immediately, before any
hazard math runs, if: `active_source_ids` contains a duplicate
(GRID-HAZ-07); `geometry_by_cell`/`source_factors_by_source` contains a
source not present in `active_source_ids` (GRID-HAZ-08) — a future/
non-eligible source can never silently contribute; a `SourceGeometry`'s
own `source_id`/`grid_cell_id` disagrees with its dictionary placement
(GRID-HAZ-09/10); or a `CellHazardFactors.grid_cell_id` disagrees with
its dictionary key. Dictionary placement is never trusted alone —
every index is cross-checked against the object's own declared
identity.

## 20. Checkpoint 6D — real factor transformation stays firewalled out

Checkpoint 6D built `services/factors/` (see `FACTOR_TRANSFORMATION_PROTOCOL.md`)
— the real feature→factor transformation development layer. It
produces `FactorSnapshot`s, never a real `HazardSnapshot`: this
package's hazard contracts (`HazardFactors`/`CellHazardFactors`/
`SourceHazardFactors`/`FactorValue`) still structurally accept only
`SOFTWARE_FIXTURE_ONLY`-status usable values — 6D did not loosen them,
and no code in `services/factors/` imports `build_hazard_snapshot`,
`accumulate_cell_hazard`, `compute_relative_risk_index`, or
`compute_source_hazard` (verified via `ast`). Also hardened in 6D:
`build_hazard_snapshot` now rejects duplicate `expected_grid_cell_ids`
and any extra (non-expected) key in `geometry_by_cell`/
`cell_factors_by_cell`/`wind_by_cell`, and verifies
`SourceHazardFactors.source_id`/`CellMeteorology.grid_cell_id` against
their own dictionary keys at preflight (Part 0 A-D).
`MeteorologySpatialMode` gained `AOI_CENTER_UNIFORM_REAL_PROXY` and
`SPATIALLY_RESOLVED_REAL` (reserved, unused) alongside
`UNIFORM_FIELD_FIXTURE`; `spatial_mode` now participates in
`hazard_input_signature_hash` (Part 0E).

## Checkpoint 7C — anisotropy primitive reused, full pathway formula not used

Checkpoint 7C reuses `hazard/anisotropy.py`'s
`compute_meteorological_alignment`/`compute_anisotropy_factor` and
`hazard/kernels.py`'s `evaluate_kernel` DIRECTLY — no second anisotropy
formula was written. It deliberately does NOT call
`source_hazard.compute_source_hazard`/`accumulator.accumulate_cell_hazard`:
that pathway's `L_j_i`/`W_j_i` formulas structurally require
`host_factor`/`environmental_suitability_factor`/`source_strength_factor`
(and, for the wind pathway, additionally `water_context_factor`/
`wind_speed_factor`) to all be `.usable` — none of these carry real data
today (Checkpoint 6C.5 permits only `SOFTWARE_FIXTURE_ONLY` for them),
so the full pathway would return `SOURCE_HAZARD_INCOMPLETE` for every
real origin. 7C instead composes the frozen distance kernel directly
with the anisotropy factor, per source, before summation. The real ERA5
wind vector 7C uses is one observation per forecast origin, sampled at
the AOI center and held spatially uniform across that origin's local
evaluation domain — `meteorology_spatial_mode=AOI_CENTER_UNIFORM_REAL_PROXY`
(the same status defined above, never `SPATIALLY_RESOLVED_REAL`, never
per-cell ERA5 resolution). Per-source directional modulation still
varies within the domain because each source keeps its own
`t_hat_east`/`t_hat_north` geometry to each cell — only the wind vector
itself is uniform, never the resulting anisotropy factor. See
`ENVIRONMENTAL_WIND_MODEL_DEVELOPMENT_PROTOCOL.md`.
