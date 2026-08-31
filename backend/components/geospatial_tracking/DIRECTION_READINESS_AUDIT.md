# DIRECTION_READINESS_AUDIT — Checkpoint 8A / 8A.1

Methodology/readiness checkpoint. No direction model fit, no parameter
tuned, no held-out/Sri Lanka direction performance scored. Full code
inventory: `DIRECTION_CODE_READINESS_AUDIT.md`. Frozen semantics:
`DIRECTION_MODEL_PROTOCOL.md`.

## Findings

1. **C0 direction-identifiability**: `FROZEN_C0_HAS_NO_INTRINSIC_DIRECTIONAL_TRANSMISSION_PARAMETER`
   — verified against the live candidate registry (8A-C0-01): the
   `C0_FROZEN_B0_ISOTROPIC` entry (`C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8`)
   carries `anisotropy_mode=None`, `anisotropy_kappa=None`.
2. **Source-specific geometry**: real, tested, unit-vector
   `t_hat_east`/`t_hat_north` (SOURCE -> CELL) exists for every eligible
   source, never collapsed to nearest-source (8A-GEO-01/02,
   8A-SOURCE-01/02).
3. **Anisotropy equation audit**: `wind_scoring_7c.score_origin_candidates_7c`
   applies `alignment`/`anisotropy_factor` per source, inside the
   per-source loop, before summation — **no mathematical defect found**;
   nothing required correction.
4. **Wind FROM/TO semantics**: `wind_components_from_speed_direction`'s
   `u=-speed*sin(from)`/`v=-speed*cos(from)` is consistent with the
   frozen 8A bearing convention with no double conversion (8A-WIND-01..04).
5. **Zero-wind / zero-distance / zero-resultant**: all three produce an
   explicit `None`/`CALM_NEUTRAL`/excluded-term outcome, never a
   fabricated direction (8A-WIND-05, 8A-ZERO-01, and the exclusion logic
   documented in `DIRECTION_MODEL_PROTOCOL.md` section 7).
6. **Multi-source conflict**: two equal opposing contributions cancel to
   `directional_clarity=0`, never an arbitrary bearing (8A-MULTI-01);
   clarity strictly decreases as contributions disagree (8A-MULTI-02).
7. **Resultant-vector math (Part 11)**: no such aggregation previously
   existed anywhere in the codebase. `DIRECTION_WEIGHT_NOT_YET_SCIENTIFICALLY_DEFINED`
   — the new `compute_resultant_vector` readiness primitive accepts a
   caller-supplied weight for testing only; no weight is chosen or
   frozen in 8A.
8. **"Confidence" terminology**: rejected. `directional_clarity` is the
   only allowed agreement measure; the term "confidence" appears in
   source only inside explicit negations (8A-SEM-02).
9. **Temporal-input protocol**: pre-t0-only, re-confirmed against real
   code (`wind_readiness_7c.resolve_origin_wind` calls only
   `build_pre_t0_weather_summary`; no "target" concept anywhere in the
   readiness primitives) (8A-TIME-01/02).
10. **Weather-availability limitation**: historical ERA5 is
    `RETROSPECTIVE_REANALYSIS_STATE_PROXY`; ERA5T lag filtering is a
    sensitivity approximation, never real-time operational weather.
11. **7C wind-coverage implication**: 192/277 (~69.3%) REAL wind,
    85/277 (~30.7%) `WEATHER_INPUT_UNAVAILABLE` in the real 7C.1
    579-origin development run; all 8 CW candidates
    `PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE`. This is
    carried forward as a real, unresolved input-coverage gap for
    `WIND_INFORMED_HAZARD_RESULTANT` — never claimed as "wind was
    validated" or "environmental model was selected."
12. **Candidate direction-method readiness matrix**: see
    `DIRECTION_MODEL_PROTOCOL.md` section 11 —
    A=`ELIGIBLE_FOR_8B_DEVELOPMENT`,
    B=`AUXILIARY_DIRECTION_METHOD_BLOCKED_BY_INPUT_COVERAGE`,
    C=`DIRECTION_METHOD_NOT_YET_SCIENTIFICALLY_IDENTIFIABLE`.
13. **Direction evaluation-truth readiness**: `DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN`
    — no truth definition chosen; causality from multiple eligible
    sources remains genuinely unresolved.
14. **Day/horizon semantics**: no day-specific predictive mechanism
    exists; any output must be labelled `T0_LOCAL_SPREAD_RISK_TENDENCY`
    or `PRE_T0_STATE_DERIVED_DIRECTIONAL_TENDENCY`, never "D7 predicted
    direction."
15. **Draft output contract**: drafted, not integrated (`DIRECTION_MODEL_PROTOCOL.md`
    section 14) — no `confidence` field, `bearing_deg` uses `null` not a
    fake `0`.

## Protocol hash

`direction_readiness_protocol_hash_8a() = c896048f4bc11264d17385240898ba6566b843a3f5a56f7fc8c21ae802187160`
(`services/model_development/direction_protocol_8a.py`). Binds bearing
convention, source->cell orientation, wind FROM/TO semantics,
zero-resultant/zero-distance semantics, clarity semantics, temporal
firewall, candidate direction-method definitions (audited, not
selected), and evaluation-truth status. Never binds a timestamp
(8A protocol-hash-determinism test).

## Tests

`tests/test_checkpoint_8a_direction_readiness.py` — 26 tests (8A-BEAR-01..05,
8A-ZERO-01, 8A-GEO-01/02, 8A-MULTI-01/02, 8A-WIND-01..05 (WIND-04
parametrized x4), 8A-SOURCE-01/02, 8A-SEM-01/02, 8A-TIME-01/02,
8A-C0-01, plus a protocol-hash-determinism test), all passing. No
predictive scoring anywhere in the file. Full backend regression:
1230/1230 passed, 0 failed, 0 skipped (1204 baseline + 26 new).

Two genuine bugs were caught and fixed by these tests during
development, not hidden: (1) a floating-point edge case in
`bearing_deg_from_components` where a near-180-degree FROM/TO
round-trip could round UP to exactly `360.0` instead of wrapping to
`0.0` (the ULP near 360 exceeds the sub-picodegree residual from
`atan2`) — fixed with an explicit re-wrap guard; (2) the test file's
own negation-aware terminology check initially used too narrow a
detection window/keyword set and false-positived on a legitimately
negated docstring sentence — fixed by widening the window, mirroring
the same class of self-correction already established in Checkpoint
7E.1.

## Repository status

Branch `component/geospatial-pistes`. Nothing staged, no commit, no
push (confirmed in the final STOP AND REPORT below).

## Final classification (Part 23/29)

**`GEOMETRIC_DIRECTION_ONLY_READY_NOT_SPREAD_DIRECTION`.**

A defensible, real, tested geometric source-resultant tendency is
available for 8B development. It must never be presented as validated
disease-spread direction: no directional weight is scientifically
defined, C0 itself has no directional parameter, and the wind-informed
alternative remains blocked by a real input-coverage gap.

## Checkpoint 8A.1 — mathematical hardening (CHECKPOINT_8A1_MATHEMATICAL_HARDENING)

No predictive result changed; C0 unchanged; 7B-7E not reopened; no
directional weight selected; no FIT_DEVELOPMENT/held-out/Sri Lanka
direction performance scored.

16. **Resultant scale-invariance fixed**: the original absolute
    `RESULTANT_MAGNITUDE_EPSILON` was replaced with a purely relative
    rule (`magnitude / total_mass`), proven scale-invariant under
    `c in {1e-12, 1, 1e12}` (8A1-SCALE-01/02).
17. **Generic bearing made scale-independent**: `bearing_deg_from_components`
    now returns `None` only for an EXACT `(0,0)` input; a finite tiny
    nonzero vector (`1e-15`) resolves to a real bearing, not suppressed
    by the weighted-resultant tolerance (8A1-BEAR-02).
18. **Non-finite values fail closed**: `NaN`/`+-inf` rejected with
    `ValueError` for every numerical field/function in the readiness
    module, via the existing `reject_non_finite` helper — never
    reinterpreted as `0`/missing-North (8A1-FINITE-01..04).
19. **Unit-vector invariant enforced**: usable terms must carry a
    genuine unit `t_hat` within `UNIT_VECTOR_NORM_TOLERANCE`, never
    silently renormalized; zero-distance terms must carry exactly
    `(0.0, 0.0)` (8A1-UNIT-01..03).
20. **Directional-clarity range guaranteed**: `[0,1]` proven by
    construction (unit weights, unit vectors), with only microscopic
    float overshoot clamped, material overshoot raising `ValueError`
    (8A1-CLARITY-01).
21. **Calm-wind threshold made consistent**: `wind_to_bearing_from_components`
    now reuses `hazard.anisotropy.CALM_WIND_EPSILON_M_S` and its exact
    `<` comparison — verified to agree with
    `compute_meteorological_alignment` at, above, and below the
    boundary (8A1-WIND-01..03).
22. **Three tolerances kept explicitly separate**: generic zero-vector
    (exact), resultant relative-cancellation (`1e-9`, dimensionless),
    and meteorological calm-wind (`1e-6` m/s, absolute, reused not
    duplicated) — see `DIRECTION_MODEL_PROTOCOL.md` section 17.
23. **Method-A readiness matrix corrected**: the semantic contradiction
    (`scientifically_defined=True` alongside an undefined weight) is
    resolved into four explicit, non-contradictory statuses (see
    `DIRECTION_MODEL_PROTOCOL.md` section 20). Methods B/C carried
    forward unchanged.
24. **Terminology tests hardened**: added direct positive assertions
    (dataclass field names, live C0 registry values, module public
    namespace) alongside the existing text-scan checks, rather than
    relying on text scans alone (8A1-SEM-01/02).

**Protocol hash versioning**: `direction_readiness_protocol_hash_8a()`
is UNCHANGED (`c896048f4bc11264d17385240898ba6566b843a3f5a56f7fc8c21ae802187160`,
now labelled `HISTORICAL_CHECKPOINT_8A_INITIAL_READINESS_HASH`, verified
identical by test). New hardened
`direction_readiness_protocol_hash_8a1() = 8aa69a68f27980134caa3cb1c5c96f5b66ab1e41274bc9def38a9aa5a627869e`.

**Tests**: 44 new (`tests/test_checkpoint_8a1_direction_hardening.py`).
Full backend regression: **1274/1274 passed, 0 failed, 0 skipped**
(1230 baseline + 44 new). All previous 8A tests (26) still pass
unmodified against the hardened primitives.

**Final classification, re-affirmed with evidence unchanged:
`GEOMETRIC_DIRECTION_ONLY_READY_NOT_SPREAD_DIRECTION`.**

## Checkpoint 8B / 8B.1 / 8B.2 / 8B.3 pointer

Method A was developed into a real service
(`services/direction/c0_geometric_tendency.py`) and structurally
audited over the real FIT_DEVELOPMENT origin universe. No direction
performance was scored; `DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN`
remains unresolved. 8B.1 repaired an accidental local_data path (no
scientific change). 8B.2 proved the vector field approximately equals
`-25km*grad(C0)` and hardened sign-aware terminology, with no
numerical result changed. 8B.3 found 8B.2's identity was proven
against the wrong local tangent frame, corrected it in a new ACTIVE
service (`services/direction/c0_cell_local_tendency_8b3.py`), and
reran the real structural audit (permitted — geometry-only, no target
outcomes) confirming the corrected identity now holds to convergent
numerical precision; historical 8B/8B.2 artifacts remain byte-
identical. Full record: `DIRECTION_8B_PROTOCOL.md`.
