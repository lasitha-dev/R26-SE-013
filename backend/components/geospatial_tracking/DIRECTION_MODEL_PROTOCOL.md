# DIRECTION_MODEL_PROTOCOL — Checkpoint 8A / 8A.1

This document freezes SEMANTIC conventions only. **No direction model
is fit, tuned, or scored here.** C0 (`C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8`)
is unchanged and carries no directional parameter.

`direction_readiness_protocol_hash_8a()` (`services/model_development/direction_protocol_8a.py`)
is UNCHANGED and continues to return the exact same value it always
did — now labelled `HISTORICAL_CHECKPOINT_8A_INITIAL_READINESS_HASH`:
`c896048f4bc11264d17385240898ba6566b843a3f5a56f7fc8c21ae802187160`.
Checkpoint 8A.1 (below, sections 16-20) hardened genuinely load-bearing
readiness semantics and freezes a NEW, separately named
`direction_readiness_protocol_hash_8a1()`:
`8aa69a68f27980134caa3cb1c5c96f5b66ab1e41274bc9def38a9aa5a627869e`.
Sections 1-15 below describe the ORIGINAL 8A semantics as historically
frozen; sections 16-20 describe what 8A.1 changed and why.

## 1. Non-negotiable terminology (Part 2)

Never interchangeable:

1. `METEOROLOGICAL_WIND_DIRECTION` — physical air motion only.
2. `SOURCE_TO_CELL_GEOMETRIC_DIRECTION` — `t_hat_east`/`t_hat_north` from `distance.py`.
3. `LOCAL_HAZARD_RESULTANT_DIRECTION` — a weighted-source resultant, if/when a weight is scientifically defined.
4. `OBSERVED_FUTURE_TARGET_DISPLACEMENT_BEARING` — evaluation truth only, never a model input.
5. `SPREAD_RISK_TENDENCY_DIRECTION` — only if mathematically justified; not claimed in 8A.

Raw wind direction is never called "disease spread direction." Wind
speed is never called "disease spread speed."

## 2. Frozen C0 identifiability (Part 4)

**`FROZEN_C0_HAS_NO_INTRINSIC_DIRECTIONAL_TRANSMISSION_PARAMETER`.**

C0 is `STATIC`, `ISOTROPIC`, `DISTANCE_ONLY`, summed over all eligible
sources with no wind/host/environment/water/terrain/source-strength/
ST-cluster/nearest-source-replacement input. The scalar C0 score alone
does not identify an empirically validated direction of spread. A
geometric vector derived from source/cell configuration must be
labelled geometric or relative-risk tendency unless further evidence
supports a stronger interpretation — never manufactured merely so a UI
can show an arrow.

## 3. Source-specific geometry (Part 5)

`geometry_by_source[source_id] = {distance_km, t_hat_east, t_hat_north}`,
unit vector pointing **SOURCE -> CELL**, one entry per eligible source,
never collapsed to a nearest-source vector before or after aggregation.
Verified: `services/geospatial/source_geometry.py`,
`services/geospatial/distance.py::source_to_cell_unit_vector`
(8A-GEO-01/02, 8A-SOURCE-01/02).

## 4. Bearing convention (Part 6)

`BEARING_CONVENTION = CLOCKWISE_FROM_NORTH_DEGREES_0_TO_360_EXCLUSIVE`.
0=North, 90=East, 180=South, 270=West. For components `(east, north)`:
`bearing = atan2(east, north)` in degrees, normalized to `[0, 360)`.
`0.0` degrees is a VALID direction and is never treated as missing;
the only "no direction" sentinel is `None` (8A-BEAR-01..05).

## 5. Meteorological wind FROM/TO semantics (Part 7)

`u10` = eastward component, `v10` = northward component (m/s) —
never swapped, never reconstructed from a compass bearing inside the
hazard contract layer (`hazard/contracts.py::WindVector`).
Meteorological "wind direction" is the FROM-bearing (where the wind
blows FROM). `wind_to_bearing = atan2(u10, v10)` normalized to
`[0, 360)`; `wind_from_bearing = (wind_to_bearing + 180) mod 360`,
applied exactly once (8A-WIND-01..04 prove the round trip; the real
`wind_components_from_speed_direction` implementation — `u = -speed*sin(from)`,
`v = -speed*cos(from)` — is independently confirmed consistent with
this convention, no double conversion).

## 6. Existing anisotropy equation (Part 9)

`alignment_j_i = t_hat_east_j_i * wind_unit_east + t_hat_north_j_i * wind_unit_north`,
clamped to `[-1, 1]`. `A(alignment, kappa; MODULATING) = exp(kappa*alignment)`;
`A(alignment, kappa; ANGULAR_NORMALIZED) = exp(kappa*alignment) / I0(kappa)`.
Calm wind (`|wind| < 1e-6`) -> `alignment=None`, factor exactly `1.0`,
never a fabricated direction. **Confirmed source-specific before
summation**: `wind_scoring_7c.score_origin_candidates_7c` computes
`alignment`/`anisotropy_factor` inside its per-source loop and
accumulates `total += k * aniso.anisotropy_factor` before moving to the
next cell — no aggregate-then-apply defect found; no correction
required.

## 7. Zero-distance / zero-resultant semantics (Parts 13-14)

A source at zero distance from a cell has a structurally undefined
`t_hat` (`(0.0, 0.0)`, per `source_to_cell_unit_vector`). Readiness
primitive `compute_resultant_vector` (`direction_readiness_8a.py`)
**excludes** such terms from both the resultant sum and the clarity
denominator — their weight is never silently folded in, which would
otherwise deflate `directional_clarity` for a source with no definable
direction. If the total usable resultant magnitude is at/below
`1e-9`, `bearing_deg = None` (UNDEFINED/UNAVAILABLE) — never `0.0`,
which would falsely mean North (8A-ZERO-01).

## 8. Directional clarity (Part 12)

`directional_clarity = ||resultant|| / SUM_j(usable weight_j)`, range
`[0, 1]`. High clarity means directional contributions align; low
clarity means they conflict/cancel. It is an agreement measure, never a
probability, accuracy, or confidence statement (8A-MULTI-01/02,
8A-SEM-02). No prior project code defined this formula — it is
introduced here as the 8A reference definition for readiness-testing
purposes only; it is not scientifically selected as a production
formula for 8B.

## 9. Direction weight status (Part 11)

**`DIRECTION_WEIGHT_NOT_YET_SCIENTIFICALLY_DEFINED`.** No `w_j_i` is
chosen in 8A. `compute_resultant_vector` accepts any caller-supplied
weight for readiness testing only.

## 10. Temporal firewall (Part 16)

```
PRIMARY_DIRECTION_INPUT_MAY_USE_ONLY_PRE_T0_WEATHER_STATE_HISTORY;
FUTURE_TARGET_POSITION_FORBIDDEN_AS_INPUT;
REALIZED_D1_D7_WEATHER_FORBIDDEN_AS_PRIMARY_INPUT_ORACLE_SENSITIVITY_ONLY;
FUTURE_OUTBREAKS_MAY_ONLY_BE_EVALUATION_TRUTH_IN_A_LATER_CHECKPOINT
```

Re-confirmed against real code: `wind_readiness_7c.resolve_origin_wind`
calls only `build_pre_t0_weather_summary`; neither it nor
`direction_readiness_8a.py` reference a "target" concept anywhere
(8A-TIME-01/02).

## 11. Candidate direction-method readiness matrix (Part 10)

| Method | Sci. defined | Implemented | Tested | Data ready | Temporally safe | Eligible for 8B |
|---|---|---|---|---|---|---|
| A. `GEOMETRIC_SOURCE_RESULTANT_TENDENCY` | Yes | No (only the 8A readiness primitive exists) | Yes | Yes | Yes | **Yes** |
| B. `WIND_INFORMED_HAZARD_RESULTANT` | Yes | No | Yes | **No** (30.7% wind-coverage gap, 7C) | Yes | **No** |
| C. `HAZARD_SURFACE_GRADIENT_DIRECTION` | **No** | No | No | No | No | No |

Full reasoning per method: `services/model_development/direction_protocol_8a.py::DIRECTION_METHOD_CANDIDATES`.

Reused from 7C only as CODE/MATH (anisotropy primitive, geometry) —
never as proof of directional predictive validity (Part 18). 7C's wind
candidates were never primary-comparable due to incomplete domain
coverage and are not reopened here.

## 12. Direction evaluation-truth readiness (Part 20)

**`DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN`.** A future-target bearing
from an eligible t0 source reference is a plausible geometric
definition, but with multiple eligible sources, causality is unknown —
"nearest geometric source" must never be called "causal source," and no
truth rule may be chosen because it improves a future metric. No truth
definition is frozen in 8A.

## 13. Day/horizon semantics (Part 21)

A method using only one pre-t0 static weather summary cannot honestly
produce seven distinct D1-D7 directions without a genuine
time-evolution mechanism. Until/unless such a mechanism exists, any
resulting quantity must be labelled `T0_LOCAL_SPREAD_RISK_TENDENCY` or
`PRE_T0_STATE_DERIVED_DIRECTIONAL_TENDENCY` — never "D7 predicted
direction."

## 14. Draft direction output contract (Part 22 — draft only, not integrated)

```
direction_status
direction_semantics
bearing_deg            # null when undefined, never a fake 0
east_component
north_component
directional_clarity
n_directional_sources
n_total_eligible_sources
directional_input_coverage
temporal_input_protocol
method_id
method_version
limitations[]
```

No `confidence` field. No API/DB wiring in 8A.

## 15. Overall readiness classification (Part 23)

**`GEOMETRIC_DIRECTION_ONLY_READY_NOT_SPREAD_DIRECTION`.**

Real, tested, source->cell geometry is available for every eligible
source at every already-frozen forecast origin with no additional data
dependency, and a resultant-vector/bearing/clarity readiness primitive
now exists and is frozen (this document + `direction_readiness_8a.py`).
It must not be called disease spread direction, because no
scientifically defined directional weight (`w_j_i`) exists yet and C0
itself carries no directional transmission parameter. Wind-informed
direction remains blocked by a real, unresolved 30.7% input-coverage
gap; gradient-direction is not yet scientifically identifiable at all.

## 16. Checkpoint 8A.1 — resultant scale-invariance (hardening)

The original `RESULTANT_MAGNITUDE_EPSILON` (an absolute `1e-9`) made
bearing/clarity availability depend on the arbitrary absolute scale of
`w_j_i` — mathematically unacceptable, since multiplying every positive
weight by a common scalar must not change directional geometry.
Replaced with a purely relative rule: `total_mass = SUM_usable w_j`;
if `total_mass <= 0` -> `NO_DIRECTIONAL_MASS` (bearing/clarity `None`);
else `relative_magnitude = ||resultant|| / total_mass`, and if that
ratio is `<= RESULTANT_RELATIVE_CANCELLATION_EPSILON` (`1e-9`,
dimensionless, an ENGINEERING tolerance, never a fitted scientific
parameter) -> `DIRECTIONAL_CONTRIBUTIONS_CANCELLED` (bearing `None`,
clarity still reported); otherwise `DIRECTION_AVAILABLE`. Proven
scale-invariant by construction (both numerator and denominator scale
by the same `c`) and by test across `c in {1e-12, 1, 1e12}`
(8A1-SCALE-01/02).

## 17. Three distinct numerical tolerances — never conflated

| Tolerance | Value | Units/meaning | Used by |
|---|---|---|---|
| Generic bearing zero semantics | none (exact `magnitude == 0.0` only) | geometric | `bearing_deg_from_components` |
| `RESULTANT_RELATIVE_CANCELLATION_EPSILON` | `1e-9` | dimensionless ratio | `compute_resultant_vector` only |
| `CALM_WIND_EPSILON_M_S` (reused, not duplicated) | `1e-6` | m/s, absolute | `wind_to_bearing_from_components`, matching `compute_meteorological_alignment` exactly (`<` comparison) |

A finite, arbitrarily tiny, nonzero generic vector (e.g. `(1e-15, 0)`)
still resolves to a real bearing — it is never suppressed by the
resultant-cancellation tolerance, which applies only inside
`compute_resultant_vector` (8A1-BEAR-02).

## 18. Non-finite rejection and unit-vector validation (hardening)

Every numerical field of `DirectionalMassTerm` and every bearing
function now rejects `NaN`/`+-inf` via the existing
`services.hazard.contracts.reject_non_finite` (no second
implementation) — never silently reinterpreted as `0` or "missing
North" (8A1-FINITE-01..04). A USABLE term (`distance_km > 0`) must
carry `sqrt(t_hat_east**2 + t_hat_north**2)` within
`UNIT_VECTOR_NORM_TOLERANCE` (`1e-6`) of `1.0`, checked at construction
and never silently renormalized — a malformed unit vector fails closed
as an upstream geometry defect (8A1-UNIT-01/02). A zero-distance term
must carry EXACTLY `(0.0, 0.0)`; any other value at `distance_km == 0`
is rejected (8A1-UNIT-03), preserving the existing
`source_to_cell_unit_vector` degenerate-case convention.

## 19. Directional-clarity range guarantee (hardening)

With weights `>= 0` and validated unit vectors, `directional_clarity in
[0, 1]` follows from the triangle inequality. A microscopic
floating-point overshoot is clamped only within
`CLARITY_RANGE_CLAMP_TOLERANCE` (`1e-9`); a materially out-of-range
value instead raises `ValueError` as a genuine invariant violation,
never silently clamped (8A1-CLARITY-01).

## 20. Corrected method-readiness matrix (Part 9)

`GEOMETRIC_SOURCE_RESULTANT_TENDENCY`'s original flat
`"scientifically_defined": True` alongside
`DIRECTION_WEIGHT_NOT_YET_SCIENTIFICALLY_DEFINED` was a genuine
semantic contradiction — a complete weighted-resultant METHOD is not
fully specified until `w_j_i` is frozen. Replaced with explicit,
non-contradictory statuses in `DIRECTION_METHOD_CANDIDATES_8A1`:

| Status | Value |
|---|---|
| `geometry_definition_status` | `SCIENTIFICALLY_DEFINED` |
| `aggregation_framework_status` | `MATHEMATICALLY_DEFINED` |
| `directional_weight_status` | `NOT_YET_SCIENTIFICALLY_DEFINED` |
| `complete_method_specification_status` | `INCOMPLETE_PENDING_WEIGHT_DEFINITION` |
| `data_ready` / `temporally_safe` / `eligible_for_8b_development` | `true` |

Meaning: 8B may develop/predeclare a scientifically defensible
weighting rule on `FIT_DEVELOPMENT` only — this eligibility is NOT
evidence that a spread-direction method already exists. Methods B
(`WIND_INFORMED_HAZARD_RESULTANT`) and C
(`HAZARD_SURFACE_GRADIENT_DIRECTION`) are carried forward UNCHANGED —
no new evidence exists to justify changing their `AUXILIARY_DIRECTION_METHOD_BLOCKED_BY_INPUT_COVERAGE`
/ `DIRECTION_METHOD_NOT_YET_SCIENTIFICALLY_IDENTIFIABLE` classifications.
8B's output must never be called validated spread direction, predicted
transmission direction, or disease movement direction.

**Overall classification, re-affirmed with evidence unchanged:
`GEOMETRIC_DIRECTION_ONLY_READY_NOT_SPREAD_DIRECTION`.**

## 21. Checkpoint 8B / 8B.1 / 8B.2 / 8B.3

Method A (`GEOMETRIC_SOURCE_RESULTANT_TENDENCY`) was developed into a
real, reusable, FIT_DEVELOPMENT-structurally-audited service using the
exact frozen C0 per-source kernel contribution as its directional
weight (`DIRECTIONAL_WEIGHT_DERIVED_FROM_FROZEN_C0_NO_NEW_PARAMETER`)
— resolving the `INCOMPLETE_PENDING_WEIGHT_DEFINITION` status from
section 20 for THIS ONE weight choice, never a general claim that the
directional-weight question is closed for every possible method.
Checkpoint 8B.2 proved analytically that this resulting vector is
approximately `-25km * grad(C0)` — reconciling 8A's Method C
(`HAZARD_SURFACE_GRADIENT_DIRECTION`, `NOT_YET_SCIENTIFICALLY_IDENTIFIABLE`
at the time) as a later-discovered consequence, never a claim that a
gradient method secretly existed in 8A. Checkpoint 8B.3 then found
that 8B.2's identity was proven against the wrong local tangent frame
(source-departure, not cell-arrival) and corrected it — the identity
now holds to convergent numerical precision for the NEW active
cell-local field, while the historical field is honestly re-described
as a `SOURCE_DEPARTURE_FRAME_GEOMETRIC_RESULTANT` (only approximately
aligned with the true gradient, never exactly). Full design, protocol
hashes, and the real structural-audit/diff results:
`DIRECTION_8B_PROTOCOL.md`.
