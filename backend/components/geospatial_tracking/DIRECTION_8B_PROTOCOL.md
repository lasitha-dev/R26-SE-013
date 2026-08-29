# DIRECTION_8B_PROTOCOL — Checkpoint 8B / 8B.1 / 8B.2 / 8B.3

Frozen-C0-derived local geometric tendency field. **No direction model
is fit or tuned here.** C0
(`C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8`,
`frozen_7c_spec_hash=ef3511d3527da6d85598846c0d828509ed07f134ac8d987c3d5702b507505a6d`)
is unchanged and carries no directional parameter. The HISTORICAL
8B/8B.1/8B.2 numerical field values are preserved exactly, byte-for-
byte, in every historical artifact — never rewritten. Checkpoint 8B.3
(section 20) introduces a genuinely NEW, numerically DISTINCT
(corrected) active field alongside the unchanged historical one — see
section 20.6 for the honest old-vs-new difference audit; the two are
NOT numerically identical.

`direction_method_protocol_hash_8b()` (`services/model_development/direction_protocol_8b.py`)
is UNCHANGED and continues to return the exact same value it always
did — now labelled `HISTORICAL_CHECKPOINT_8B_PROTOCOL_HASH`:
`9d111741d303d1dcf73c2a624b99c3fa7c3aaa2020d52d3254d5d744e963f32d`.
Checkpoint 8B.2 (section 19) hardened the sign/semantic identity and
froze `direction_method_protocol_hash_8b2()`:
`d8dd12da100f3446f29967dcd221d25112669703ab3d201333a17a07ad89f906`
(now itself relabelled historical — see 19.10/20.1). Checkpoint 8B.3
(section 20) corrects a genuine reference-frame defect and is the
ACTIVE method going forward, with
`direction_method_protocol_hash_8b3() = dc3b245aa8ea6748c8abf8bcf0c56db75aca34a6118b02776b9c5490fa6c0282`.
Sections 1-18 below describe the ORIGINAL 8B/8B.1 record as
historically frozen; section 19 describes what 8B.2 added (and where
it was later found to overstate its identity); section 20 describes
the 8B.3 correction.

## 0. 8A.1 pre-flight identity

`verify_8a1_preflight()` loads the LIVE `direction_readiness_protocol_dict_8a1()`
and asserts every semantic this checkpoint depends on is actually
bound in it (not merely that the hash string matches) — bearing
convention, generic zero-vector semantics, relative-cancellation and
unit-vector and clarity-clamp tolerances, non-finite rejection,
zero-distance semantics, calm-wind epsilon identity, wind FROM/TO,
source->cell orientation, temporal firewall, Method-A status, the two
unresolved statuses, and the `NOT_SPREAD_DIRECTION` classification.
Fails closed (`AssertionError`) if the hash matches but any expected
key is absent — never silently continues on a hash string alone.

## 1. Scientific purpose

Can the already-frozen scalar C0 model be given a mathematically
consistent LOCAL geometric relative-risk tendency vector field without
adding or tuning any new predictive parameter? This is NOT "can we
predict true disease transmission direction." Output semantics are
always `C0_DERIVED_LOCAL_GEOMETRIC_RELATIVE_RISK_TENDENCY` — never
`DISEASE_SPREAD_DIRECTION`, `TRANSMISSION_DIRECTION`,
`VALIDATED_SPREAD_DIRECTION`, or `FUTURE_OUTBREAK_DIRECTION`.

## 2. Directional weight without fitting

`w_j_i = K_C0(d_j_i) = exp(-d_j_i / 25.0 km)` — the EXACT frozen C0
per-source kernel contribution, computed via the same
`services.hazard.kernels.evaluate_kernel` primitive and the same
`FROZEN_KERNEL_FAMILY`/`FROZEN_KERNEL_SCALE_KM` constants C0's real
scoring uses. Status: `DIRECTIONAL_WEIGHT_DERIVED_FROM_FROZEN_C0_NO_NEW_PARAMETER`.
No candidate grid, no bandwidth search, no learned coefficient, no
wind term.

## 3. Scalar identity

`SUM_j w_j_i == frozen C0 cell score` by construction (same kernel
calls over the same eligible-source set). Verified both synthetically
(8B-WEIGHT-02) and against the REAL C0 scorer
(`wind_scoring_7c.score_origin_candidates_7c`, `wind=None`) over every
cell of every real, runtime-derived `FIT_DEVELOPMENT` origin in the
structural audit (`n_invariant_failures`, expected `0`).

## 4. Local direction field formula

For eligible source `j`, scientific cell `i`:
`V_east_i = SUM_j w_j_i * t_hat_east_j_i`, `V_north_i = SUM_j w_j_i *
t_hat_north_j_i`, `t_hat` = SOURCE -> CELL (never reversed). Uses the
frozen Checkpoint 8A.1 `DirectionalMassTerm`/`compute_resultant_vector`
directly — no second bearing/cancellation/clarity implementation.

## 5. Cell-local, not global

`compute_cell_direction_tendency` operates on exactly one grid cell
per call. No cross-cell aggregation into a single global or
origin-level bearing exists anywhere in this module — the isotropic C0
model does not scientifically identify one.

## 6. Zero-distance mass coverage

A zero-distance source carries `K(0) = 1` (full scalar C0 mass,
retained in `total_scalar_c0_mass`) but a structurally undefined
direction (excluded from the resultant sum and
`directionally_defined_mass`). `directional_input_coverage =
directionally_defined_mass / total_scalar_c0_mass`.
`directional_mass_coverage_status` is `COMPLETE_DIRECTIONAL_MASS_COVERAGE`
or `PARTIAL_DIRECTIONAL_MASS_COVERAGE_ZERO_DISTANCE`, determined
STRUCTURALLY (any zero-distance source present with positive mass),
never a tuned threshold.

## 7. Clarity vs. coverage vs. confidence

`directional_clarity` (agreement among directionally-defined
contributions) and `directional_input_coverage` (fraction of C0 scalar
mass with a defined direction) are two distinct fields, never merged
or multiplied. Neither is ever called "confidence" — that term is
rejected entirely (8B-SEM-02).

## 8. Source-count semantics

`n_total_eligible_sources`, `n_positive_c0_weight_sources` (for the
EXPONENTIAL kernel, structurally always equal to the total —
documented, never silently reinterpreted), `n_directionally_defined_sources`
(`distance_km > 0`, the same meaning as the 8A.1 primitive's
`n_terms_usable`), `n_zero_distance_undefined_direction_sources`
(complement), `n_positive_weight_directionally_defined_sources`
(intersection).

## 9. Per-source evidence

Every `CellDirectionTendency8B.source_terms` tuple preserves
`source_id`/`distance_km`/`c0_directional_weight`/`t_hat_east`/
`t_hat_north`/`direction_defined`/`exclusion_reason` for every source —
never only the resultant. No largest/nearest source is ever picked to
force an arrow; exact cancellation reports `bearing_deg=None`.

## 10. Static t0 temporal semantics

`temporal_scope = T0_STATIC_NOT_DAY_SPECIFIC`. C0 is static, so this
field is not independently different for D1..D7 — never seven
fabricated bearings from one static input.

## 11. Future-target firewall

`compute_cell_direction_tendency(cell, sources)` — no target/future-
outbreak parameter exists in this or any public function signature in
the module (verified structurally, 8B-TIME-02/8B-CIRCULAR-01).

## 12. Circular-evaluation prohibition

No future-target direction-performance metric (angular error, hit
rate, bearing accuracy) is computed anywhere in Checkpoint 8B —
selecting the field at a future target cell and comparing to the
source->target bearing would be geometrically tautological for a
single source. `DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN`.

## 13. Wind/environment exclusion

Method A is derived from frozen C0 geometry only — no weather/wind/
ERA5/rainfall/humidity/water/terrain/host/source-strength/ST-cluster
input (verified via direct-import AST scan, 8B-WIND-01). Method B
(`WIND_INFORMED_HAZARD_RESULTANT`) remains separately
`AUXILIARY_DIRECTION_METHOD_BLOCKED_BY_INPUT_COVERAGE`, unchanged from
8A/8A.1.

## 14. Output contract (draft, non-DB)

`scientific_cell_id`, `direction_status`, `direction_semantics`,
`temporal_scope`, `bearing_deg` (`null` when undefined, never a fake
`0`), `resultant_east`/`resultant_north`/`resultant_magnitude`,
`directional_clarity`, `total_scalar_c0_mass`,
`directionally_defined_mass`, `directional_input_coverage`,
`directional_mass_coverage_status`, five source-count fields,
`method_id`/`method_version`, `source_terms`, `limitations[]`. No
`confidence`/`probability`/`spread_speed`/`infection_probability`/
`validated_spread_direction` field exists.

## 15. No arbitrary clarity threshold

The continuous `directional_clarity` value is always exposed as-is; no
`>= 0.5` / `< 0.3` visualization rule is invented here. Bearing
availability uses only the 8A.1 relative-cancellation rule.

## 17. Real FIT_DEVELOPMENT structural audit result

`smoke_tests/run_direction_structural_audit_8b.py`, run over the real,
runtime-derived `FIT_DEVELOPMENT` universe (never hardcoded). No
target outcomes, no held-out origins, no Sri Lanka origins touched.

- **579/579** real `FIT_DEVELOPMENT` origins processed (0 with no
  eligible sources, 0 with no grid).
- **560,853** real scientific grid cells processed.
- `direction_status_counts`: `DIRECTION_AVAILABLE: 560853` (0
  `DIRECTIONAL_CONTRIBUTIONS_CANCELLED`, 0 `NO_DIRECTIONAL_MASS` in
  this real corpus — never engineered to be so, simply the observed
  real outcome).
- `coverage_status_counts`: `COMPLETE_DIRECTIONAL_MASS_COVERAGE: 560853`
  (0 `PARTIAL_...` — no real source coincided exactly with a grid-cell
  centroid anywhere in the corpus).
- `directional_clarity` distribution: min `0.0014`, p25 `0.469`,
  median `0.709`, p75 `0.902`, p95 `0.999`, max `1.0` — real
  near-total-cancellation cases exist (min near 0) alongside
  perfectly-aligned single/coherent-source cells (max exactly 1.0).
- `directional_input_coverage` distribution: `1.0` at every percentile
  (consistent with 0 zero-distance cases).
- `eligible_source_count` per-origin distribution: min `1`, p25 `2`,
  median `6`, p75 `18`, p95 `54.1`, max `120`.
- `n_exact_zero_distance_cases`: **0**.
- **`n_invariant_failures`: 0** — the Part 3 scalar identity
  (`total_scalar_c0_mass == real C0 cell score`) held EXACTLY across
  all 560,853 real cells, cross-checked directly against
  `wind_scoring_7c.score_origin_candidates_7c` (`wind=None`), not
  merely asserted.
- Runtime: 274.8s (pure geometry/kernel computation, no weather I/O).

Local evidence (gitignored):
`local_data/model_development/8b_direction/{direction_protocol_8b.json,direction_structural_audit_8b.json,direction_example_source_terms_8b.json,direction_origin_summary_8b.csv}`.
Tracked aggregate summary: `CHECKPOINT_8B_EVIDENCE_SUMMARY.json`.

## 18. Overall classification (historical, as of Checkpoint 8B)

**`C0_DERIVED_LOCAL_GEOMETRIC_RISK_TENDENCY_FIELD_READY_NOT_PREDICTIVE_SPREAD_DIRECTION`.**
`n_invariant_failures == 0` on the full real FIT_DEVELOPMENT universe
and all 31 Checkpoint 8B tests pass (30 unit + 1 evidence-summary
consistency).

## 18a. Checkpoint 8B.1 — artifact path and provenance repair

The four real 8B artifacts (`direction_protocol_8b.json`,
`direction_structural_audit_8b.json`,
`direction_example_source_terms_8b.json`,
`direction_origin_summary_8b.csv`) were originally written under an
accidental component-nested path
(`backend/components/geospatial_tracking/local_data/model_development/8b_direction/`)
due to a `Path(__file__).resolve().parents[1]` bug in the runner
script. `CHECKPOINT_8B1_ROLE = ARTIFACT_PATH_AND_PROVENANCE_REPAIR` —
relocated byte-for-byte (SHA256/size verified identical before and
after) to the canonical `local_data/model_development/8b_direction/`.
No numerical result, hash, or scientific parameter changed. Full
record: `DATA_AUDIT.md` §94.

## 19. Checkpoint 8B.2 — analytical negative-gradient equivalence, sign/semantic hardening, method-identity binding

No real structural-audit rerun; no C0 rescoring; no numerical vector
result changed; no direction parameter fit or tuned.

**19.1 Analytical identity, proven (not merely asserted)**: for kernel
scale `lambda=25km`, `grad_x d_j(x) = t_hat_j(x)` (the source->cell
unit tangent) almost everywhere — a standard result for the gradient
of a distance function from a fixed point — except at `d=0` (not
differentiable) and at the geodesic cut locus (never reached at this
25km kernel scale; Earth's antipodal cut-locus distance is ~20,000km).
By the chain rule, `grad exp(-d_j/lambda) = -(1/lambda) * exp(-d_j/lambda)
* t_hat_j`, matching the frozen EXPONENTIAL kernel's own derivative
`dK/dd = -(1/lambda)*K`. Summed over all eligible sources: `grad
C0(x) = -(1/lambda) * V(x)`, therefore **`V(x) = -lambda * grad
C0(x)`**. Proven synthetically (8B2-GRAD-01..08,
`tests/test_checkpoint_8b2_negative_gradient.py`) against the real
`source_to_cell_unit_vector` orientation, the real frozen kernel
derivative, and the real `compute_cell_direction_tendency` output,
cross-checked by metric (km-scale, not raw-degree) finite differences
on real WGS84 geodesics — never rerun over the 579-origin/560,853-cell
real corpus.

**19.2 A fourth exception, discovered empirically during 8B.2 test
development**: `source_to_cell_unit_vector` uses the geodesic
DEPARTURE azimuth measured AT THE SOURCE (the codebase's existing,
frozen convention since Checkpoint 5, used unchanged throughout
7B-8B), not the true local gradient tangent AT THE CELL (the arrival
azimuth). On the WGS84 ellipsoid these differ by the geodesic's
meridian-convergence angle over the source-cell path — confirmed
empirically at ~0.0012 degrees for a 3km geodesic at the test
latitude. This makes the identity approximate (sub-percent level, not
exact to machine precision) rather than exact for source distances up
to tens of km at the frozen 25km kernel scale — small, real, and
documented, never hidden.

**19.3 Sign semantics (Part 2)**: `V = -lambda*grad(C0)` points DOWN
the C0 gradient — for an isolated source, radially OUTWARD/AWAY from
it, in the direction of DECREASING C0. `POSITIVE_C0_GRADIENT` (the
direction of INCREASING C0, toward sources) is the OPPOSITE direction,
exactly 180 degrees apart whenever the gradient is materially nonzero.
`V` is never described as "direction of increasing risk," "risk-
gradient direction," "direction toward higher relative risk,"
"predicted disease-spread direction," or "transmission direction."

**19.4 Terminology**: the ORIGINAL Checkpoint 8B output-semantics
string (`c0_geometric_tendency.DIRECTION_SEMANTICS_8B`, still the
literal value every `CellDirectionTendency8B.direction_semantics`
field actually returns — UNCHANGED, never retroactively rewritten) is
`HISTORICAL_CHECKPOINT_8B_OUTPUT_TERMINOLOGY = "C0_DERIVED_LOCAL_GEOMETRIC_RELATIVE_RISK_TENDENCY"`.
The new, sign-explicit ACTIVE terminology for describing this exact
same unchanged quantity going forward (docs/UI/reports) is
`ACTIVE_OUTPUT_SEMANTICS_8B2 = "C0_DERIVED_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY"`
— mathematically derived from frozen C0, points down the C0 scalar
gradient, SOURCE->CELL weighted geometry, a static t0 quantity, never
disease-spread direction, never validated future movement direction,
never probability, never confidence. "Outward" is never read as
implying every multi-source vector points away from every source
simultaneously — for multiple sources, `V` is precisely the negative
local gradient of the AGGREGATE C0 field.

**19.5 8A Method-C / 8B Method-A reconciliation (Part 4)**: Checkpoint
8A's `HAZARD_SURFACE_GRADIENT_DIRECTION` (Method C) correctly found no
separately invented/estimated generic gradient method existed in the
codebase at that time (`DIRECTION_METHOD_NOT_YET_SCIENTIFICALLY_IDENTIFIABLE`).
Checkpoint 8B did not fit or invent such a method either — it froze
Method A's directional weight as the exact C0 per-source kernel
contribution for independent geometric reasons. Checkpoint 8B.2
discovered ANALYTICALLY (not by design or fitting) that the resulting
weighted resultant is mathematically equal to the negative gradient of
that specific already-frozen C0 field — a later analytical consequence
discovered after the fact, never a claim that 8A was wrong or that a
gradient method was secretly already implemented.

**19.6 Clarity's analytical relation (Part 6)**: under COMPLETE
directional mass coverage and away from `d=0`,
`directional_clarity = ||V||/C0 = lambda*||grad C0||/C0 = lambda*||grad
log(C0)||` — a normalized local-slope-magnitude agreement quantity,
never confidence/probability/accuracy/certainty. Under PARTIAL
coverage (zero-distance sources present) this same log-gradient
identity does NOT hold with the same denominator (directionally
defined mass excludes the zero-distance term while C0 includes it) —
never claimed in that case.

**19.7 Method-identity gap closed (Parts 7-9, additive only)**: the
historical `direction_method_protocol_dict_8b()` never bound
`method_id`/`method_version` — a real reproducibility gap, left
UNCLOSED in the historical dict/hash (never retroactively "fixed" to
pretend it always bound them). The new
`direction_method_protocol_dict_8b2()`/`direction_method_protocol_hash_8b2()`
binds `method_id="C0_GEOMETRIC_TENDENCY"`, `method_version="8B.2"`,
`historical_method_version_string="8B.1"` (the production code's
`METHOD_VERSION_8B` string, set BEFORE the unrelated later Checkpoint
8B.1 artifact-path repair — a naming coincidence, never implying 8B.1
created that version string), plus every 8B.2 semantic above, the 8A.1
parent hash, and the historical 8A/8B hashes for provenance — never a
timestamp.

**19.8 Tests**: 18 new
(`tests/test_checkpoint_8b2_negative_gradient.py`, 8B2-GRAD-01..08,
8B2-SEM-01..03, 8B2-ID-01..04, 8B2-HIST-01, 8B2-CIRCULAR-01, plus one
evidence-summary consistency check). Full backend regression:
**1333/1333 passed, 0 failed, 0 skipped** (1315 baseline + 18 new).

**19.9 Final classification, re-affirmed:
`C0_DERIVED_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY_FIELD_READY_AS_DESCRIPTIVE_NOT_PREDICTIVE_SPREAD_DIRECTION`.**

**19.10 Checkpoint 8B.2 status correction, made honestly**:
`CHECKPOINT_8B2_ANALYTICAL_IDENTITY_OVERSTATED_DUE_TO_SOURCE_FRAME_VS_CELL_FRAME_MISMATCH`.
8B.2's claimed identity `V=-lambda*grad(C0)` was analytically correct
in structure but was proven against `source_to_cell_unit_vector`'s
SOURCE-frame `t_hat`, not the CELL-frame tangent the true gradient
actually requires — the meridian-convergence discrepancy 8B.2 found
empirically (and initially treated as a numerical-tolerance matter)
was in fact this frame mismatch. The historical 8B/8B.2 numerical
field itself was never wrong on its own terms (a real
`SOURCE_DEPARTURE_FRAME_GEOMETRIC_RESULTANT`) and was never called a
predictive spread direction in either checkpoint — but its identity
with `-lambda*grad(C0)` was only approximate, not exact. See §20 for
the correction.

## 20. Checkpoint 8B.3 — cell-local tangent-frame correction (ACTIVE method)

No real risk-model rerun; no target outcomes used; C0 unchanged. The
real 579-origin/560,853-cell structural audit WAS legitimately rerun
for the new geometry-only method (permitted: no tuning, no target
outcomes, FIT_DEVELOPMENT structural evidence only) — historical 8B
artifacts were never touched and were reverified byte-identical
before and after.

**20.1 The defect**: `source_to_cell_unit_vector` (historical, Checkpoint
5, unchanged) expresses `t_hat` in the SOURCE's local tangent frame
(the geodesic DEPARTURE azimuth, `az12`). The gradient of a distance
function at an evaluation point `x` is a tangent vector AT `x` — it
must be expressed in the CELL's own local frame. New
`services.geospatial.distance.source_to_cell_tangent_at_cell` computes
this correctly: `cell_arrival_forward_azimuth_deg = (az21 + 180) mod
360`, where `az21` is `pyproj.Geod.inv`'s back azimuth (the bearing
measured AT THE CELL, pointing back toward the source) — confirmed
directly against independent `pyproj.Geod.inv` calls (8B3-GEO-01).

**20.2 Corrected identity**: `V_CELL(x) = SUM_j K(d_j(x)) *
t_hat_CELL_j(x) = -lambda * grad(C0(x))`, now holding to CONVERGENT
numerical precision — proven with a real finite-difference convergence
table: relative error shrinks ~100x per 10x reduction in step size
(step=0.1km -> 0.01km -> 0.001km), from ~2e-3 down to <1e-5, the
textbook signature of genuine O(step^2) central-difference convergence
to a true zero-bias limit — unlike the historical field's persistent
~2e-4 to 7e-4 relative plateau that never shrank regardless of step
size (a real frame bias, not truncation error).

**20.3 New active service**: `services.direction.c0_cell_local_tendency_8b3.compute_cell_direction_tendency_8b3` —
same frozen weight (`w_j_i = exp(-d_j_i/25km)`, same
`c0_directional_weight`/kernel evaluator, no new parameter), same
frozen 8A.1 `DirectionalMassTerm`/`compute_resultant_vector`, all
source terms for a given cell built in that SAME cell's local frame
before aggregation (the key correction). Active output identity:
`method_id=C0_CELL_LOCAL_NEGATIVE_GRADIENT_TENDENCY`,
`method_version=8B.3`,
`direction_semantics=C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY`,
`coordinate_frame=CELL_LOCAL_EAST_NORTH_TANGENT_FRAME`,
`direction_evaluation_truth_status=DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN`,
`predictive_spread_direction_status=NOT_PREDICTIVE_SPREAD_DIRECTION` —
self-identifying, never silently returning the historical 8B.1
identity. `services.direction.c0_geometric_tendency` (historical) is
completely unchanged and remains available for provenance.

**20.4 New protocol hash**:
`direction_method_protocol_hash_8b3() = dc3b245aa8ea6748c8abf8bcf0c56db75aca34a6118b02776b9c5490fa6c0282`
(binds the 8A.1 parent hash, historical 8B/8B.2 hashes and correction
provenance, frozen C0 identity, method id/version, active semantics,
`CELL_LOCAL_EAST_NORTH_TANGENT_FRAME`, the pyproj/WGS84 geodesic
convention identity, the arrival-bearing formula, zero-distance/unit-
vector/cancellation tolerances, the clarity-gradient identity,
temporal/firewall/evaluation-truth status; never a timestamp).
Historical `direction_method_protocol_hash_8b()` and
`direction_method_protocol_hash_8b2()` both reverified byte-for-byte
unchanged.

**20.5 Real structural audit (8B.3)**: same real, runtime-derived
FIT_DEVELOPMENT universe as historical 8B — **579/579 origins,
560,853 cells**, `direction_status_counts={DIRECTION_AVAILABLE:560853}`,
`coverage_status_counts={COMPLETE_DIRECTIONAL_MASS_COVERAGE:560853}`,
`n_exact_zero_distance_cases=0`, **`n_invariant_failures=0`** (the
scalar identity holds exactly against the real C0 scorer, cell-frame
geometry included), clarity median `0.709082530806226`. Runtime
420.8s (roughly double the historical 8B run — two geodesic
computations per source-cell pair instead of one, for the honest
old-vs-new diff below).

**20.6 Historical (8B) vs active (8B.3) difference audit** — reported
honestly, not dismissed: over all 560,853 real cells,
resultant-component delta median `0.00075`, p95 `0.0037`, max `0.018`
(small and well-behaved throughout); bearing delta median `0.045
degrees`, p95 `0.272 degrees`, max `25.4 degrees`. The bearing-delta
maximum is consistent with angular instability near vector
cancellation — that mechanism (bearing being inherently ill-
conditioned near zero magnitude, so any small perturbation produces a
large angular swing) was independently reproduced synthetically (a
~0.0006-magnitude perturbation applied to a ~0.0011-magnitude
near-cancellation vector reproduces an ~19-degree swing, consistent
with the real maximum). **Correction (Checkpoint 9A Part 0.A)**: the
aggregate audit did not retain per-cell outlier detail (clarity/
resultant values for the specific high-delta cells), so this evidence
shows the mechanism is *consistent with* near-cancellation cells, not
proof that every large-delta real cell *was* one — the original
report's "occurs exclusively in near-cancellation cells" wording
overstated what the retained aggregate evidence supports. Clarity
absolute delta: median `0.00022`, max `0.0073` — small throughout.
Full detail: `local_data/model_development/8b3_direction/historical_8b_vs_active_8b3_diff_audit.json`.

**20.9 C0 recomputation wording correction (Checkpoint 9A Part 0.B)**:
the 8B.3 structural audit called `score_origin_candidates_7c` on the
real FIT_DEVELOPMENT scientific cells to verify `SUM_j` directional
scalar weights `== frozen C0 cell score` — this is a real,
deterministic recomputation of C0 scores, not something to describe as
"C0 was never recomputed." Accurate wording: C0 was NOT refitted,
retuned, or predictively re-evaluated; deterministic FIT_DEVELOPMENT
C0 scores were recomputed only as a structural scalar-identity check
(`n_invariant_failures=0`), never to select, tune, or re-select a
model, and never against held-out/Sri Lanka data.

**20.7 Tests**: 26 new
(`tests/test_checkpoint_8b3_cell_local_correction.py`, 8B3-GEO-01..06,
8B3-GRAD-01..05, 8B3-C0-01/02, 8B3-HIST-01, 8B3-ID-01..04,
8B3-TIME-01, 8B3-CIRCULAR-01/02, 8B3-WIND-01, 8B3-SEM-01/02, plus two
evidence-summary consistency/SHA256 checks). Full backend regression:
**1359/1359 passed, 0 failed, 0 skipped** (1333 baseline + 26 new).

**20.8 Final classification:
`C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY_FIELD_READY_AS_DESCRIPTIVE_NOT_PREDICTIVE_SPREAD_DIRECTION`.**

**20.10 Checkpoint 9C cross-reference**: the presentation-layer
integration contract in
`services/integration/geospatial_intelligence_contract_9c.py` consumes
`method_id`/`method_version`/`bearing_deg`/`directional_clarity`/
`directional_input_coverage`/`direction_status`/`direction_semantics`
from an already-computed `CellDirectionTendency8B3` instance
unchanged — it never recomputes direction and never scales bearing or
clarity into a rate/distance quantity. `direction_method_protocol_hash_8b3()`
is bound directly (not duplicated) into `integration_protocol_hash_9c()`.
See `RATE_MODEL_PROTOCOL.md` §22.
