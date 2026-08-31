# FMD-06C-PA: Spatial-Domain Protocol Amendment

Status: **`POST_FEASIBILITY_PROTOCOL_AMENDMENT`**. This document is written
BEFORE predictive model development (FMD-07), held-out evaluation, or Sri
Lanka transfer evaluation. It amends only the FMD-06C spatial-domain
(evaluation-radius) rule. It does not touch active-window or ST-DBSCAN
calibration (FMD-06B-R), and it does not generate final risk-origin labels.

## 1. Original preregistered/predeclared rule

Predeclared candidate registry (Checkpoint 7A, `domain_design.py`, reused
verbatim by FMD-06C, never appended/reordered):

```
PREDECLARED_DOMAIN_CANDIDATES_KM = (25.0, 50.0, 75.0, 100.0, 150.0, 200.0)
```

Predeclared selection rule
(`domain_design.select_frozen_domain_distance`, fixed before any FMD-06C
candidate outcome was generated):

> Select the smallest candidate in `PREDECLARED_DOMAIN_CANDIDATES_KM` whose
> `FIT_DEVELOPMENT` D1-D7 `risk_target_eligible` target-appearance coverage
> -- geodesic distance from the target to the nearest
> `ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0` source `<=` candidate km -- reaches
> exactly 100% of evaluated target appearances. Never chosen using predictive
> accuracy/capture, held-out data, or Sri Lanka case-study data. Returns
> `DOMAIN_RULE_BLOCKED` (NO-GO) rather than silently expanding past the
> predeclared candidates or dropping outliers if no candidate achieves full
> coverage.

## 2. Original NO-GO result

Evaluated on the real FMD `FIT_DEVELOPMENT` corpus (3,761 forecast origins;
2,359 with at least one eligible D1-D7 target; 17,965 target-appearance rows;
4,906 unique target events):

| candidate (km) | appearances within / total | coverage |
|---|---|---|
| 25 | 12,148 / 17,965 | 67.6% |
| 50 | 14,144 / 17,965 | 78.7% |
| 75 | 15,269 / 17,965 | 85.0% |
| 100 | 15,991 / 17,965 | 89.0% |
| 150 | 16,715 / 17,965 | 93.0% |
| 200 | 17,106 / 17,965 | 95.2% |

No candidate reached 100%. The original rule therefore correctly returns:

```
original_spatial_domain_status      = "NO-GO"
original_selected_radius_km         = null
original_candidate_registry_km      = [25, 50, 75, 100, 150, 200]
original_selection_rule             = "smallest predeclared candidate reaching
                                        100% FIT_DEVELOPMENT target-appearance
                                        coverage"
```

**This original result is permanent history.** It is preserved unchanged
under `spatial_domain_status` / `spatial_evaluation_radius_km` in
`fmd06_calibration_freeze.json` and is never rewritten, deleted, or
retroactively reinterpreted as a success by this amendment.

## 3. Reason an amendment is necessary

A 100%-coverage evaluation-domain rule cannot be met within the predeclared
candidate universe on this real corpus. Continuing to FMD-06D/FMD-07 requires
*some* fixed geospatial evaluation domain for the "is there an eligible D1-D7
target nearby" question. Four options were rejected as scientifically unsound:

1. Invent a new radius after seeing the development coverage table.
2. Extend the candidate search past the predeclared maximum (200 km).
3. Use `HELD_OUT_FROM_MODEL_FITTING` or `SRI_LANKA_TRANSFER_CASE_STUDY`
   outcomes to pick a radius.
4. Select a radius using predictive-model performance (no predictive model
   exists at this stage; none was fit or scored to make this choice).

Instead, the amendment reuses a value that already existed in the
pre-registered candidate registry before any outcome was seen: its maximum,
200 km.

## 4. Explicit statement: POST-FEASIBILITY, NOT preregistered

```
spatial_protocol_amendment_status = "POST_FEASIBILITY_PROTOCOL_AMENDMENT"
```

This amendment was written and applied **only after** the original
100%-coverage rule was evaluated on real `FIT_DEVELOPMENT` data and returned
NO-GO (Section 2). It is explicitly **not** a preregistered rule, not decided
before development-data inspection, and must never be described or reported
as preregistered. Every downstream artifact and freeze-metadata key that
refers to it uses the `POST_FEASIBILITY_PROTOCOL_AMENDMENT` label, distinct
from `FROZEN_EVALUATION_DOMAIN_RULE` (the original rule's success label,
which was never reached here).

## 5. Amendment rule: MAXIMUM_PREDECLARED_LOCAL_EVALUATION_DOMAIN

```
amended_spatial_selection_rule = "MAXIMUM_PREDECLARED_LOCAL_EVALUATION_DOMAIN"
```

Definition: fix the local geospatial evaluation domain at the **largest**
value in `PREDECLARED_DOMAIN_CANDIDATES_KM`. The choice is based solely on
preserving the pre-existing candidate boundary that was declared before any
FMD-06C coverage outcome existed -- it is **not** an optimization over the
observed coverage table, not the candidate with the best coverage-per-radius
ratio, and not a value chosen because it "looked close enough." It happens to
also be the candidate with the highest observed coverage (95.2%) only because
coverage is monotonically non-decreasing in radius over these candidates --
that monotonic relationship, not the coverage figure itself, is why the
maximum predeclared value is the only defensible fallback that avoids
candidate-search inflation.

## 6. Fixed radius = 200 km

```
FMD_SPATIAL_EVALUATION_RADIUS_KM   = 200.0
amended_spatial_evaluation_radius_km = 200.0
amended_spatial_parameter_classification = "FIXED_LOCAL_COMPUTATIONAL_EVALUATION_DOMAIN"
```

200 km was already the sixth (and largest) entry of
`PREDECLARED_DOMAIN_CANDIDATES_KM` before FMD-06C ran. No new candidate value
was introduced by this amendment; `run_fmd06c_pa` raises `ValueError` if ever
called with a `radius_km` that is not both a member of
`PREDECLARED_DOMAIN_CANDIDATES_KM` and equal to its maximum.

200 km must be described **only** as a fixed computational LOCAL EVALUATION
DOMAIN. It is explicitly **not**:

- a universal biological distance;
- an inferred transmission distance;
- an ST-DBSCAN distance (`stdbscan_eps_space_km = 0.236038` remains a wholly
  separate, much smaller, clustering-neighbourhood parameter -- the two are
  never conflated);
- a quarantine/protection distance;
- an intervention recommendation.

## 7. Local prediction-question semantics

The predictive question after this amendment, to be used starting at
FMD-06D, is:

> For a forecast origin `t0`, is there at least one eligible historical D1-D7
> target event within the fixed 200 km local evaluation domain of
> `ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0`?

This is frozen as the local-domain interpretation before FMD-06D begins. The
primary modelling unit remains the **forecast origin**, not the canonical
event and not the target-appearance row:

- `FORECAST_ORIGIN_COUNT` -- the modelling denominator (3,761 for
  `FIT_DEVELOPMENT`).
- `UNIQUE_TARGET_EVENT_COUNT` -- distinct real-world target events referenced
  anywhere in the audit (4,906).
- `TARGET_EVENT_APPEARANCE_COUNT` -- one row per (origin, target) pair; the
  same real event may legitimately appear from multiple forecast origins
  (17,965). This remains an audit unit only, never a modelling unit.

## 8. Out-of-domain semantics

An eligible D1-D7 target beyond 200 km is labelled:

```
OUTSIDE_LOCAL_EVALUATION_DOMAIN
```

It is never silently deleted from the audit. For the LOCAL binary forecast
question:

- **positive** = at least one eligible D1-D7 target within 200 km.
- **negative** = no eligible D1-D7 target within 200 km (this covers both
  "zero eligible D1-D7 targets at all" and "eligible target(s) exist but all
  are beyond 200 km" -- two negatives with different underlying causes).

`fmd06_pa_local_domain_audit.csv` carries one row per `FIT_DEVELOPMENT`
forecast origin with an explicit `outside_domain_target_present` flag, so an
origin with a farther historical target (`outside_domain_target_present =
True`, `local_domain_positive = False`) stays distinguishable from an origin
with no eligible target at all (`has_eligible_d1_d7_target = False`,
`outside_domain_target_present = False`). This distinction is preserved and
must be carried into FMD-06D.

## 9. Held-out/Sri Lanka firewall

The amendment rule (Section 5) is a pure constant-selection rule -- it reads
no data at all, development or otherwise. The amended-domain **audit**
(Section 5 of the task spec / the local-domain audit CSV) uses
`FIT_DEVELOPMENT` only:

- `build_fmd06c_pa_local_domain_audit` calls
  `assert_fit_development_only` at its own entry point (the same
  Checkpoint 6B.5 Part 12 hard firewall used throughout FMD-06), rejecting
  any `HELD_OUT_FROM_MODEL_FITTING` or `SRI_LANKA_TRANSFER_CASE_STUDY` origin
  before any repository access.
- `run_fmd06c_pa` builds its origin list via `fit_development_origins(...,
  cutoff=FMD_MODEL_FITTING_CUTOFF)` before calling that function, so held-out
  and Sri Lanka rows never reach the audit or the coverage computation.
- `coverage_rows` are the unchanged return value of
  `domain_design.build_development_domain_candidate_audit`, which applies its
  own independent `assert_fit_development_only` firewall.

`held_out_data_used_for_amendment = false` and
`sri_lanka_data_used_for_amendment = false` are recorded explicitly in the
freeze metadata and the amendment summary JSON. Tests in
`test_fmd06_calibration.py` (`test_fmd06c_pa_*_firewall_*`) prove both
firewalls raise before any repository access.

## 10. Limitations

- The amended 200 km domain does not achieve 100% D1-D7 target-appearance
  coverage (95.2% at the target-appearance level); 859 target appearances
  and 509 unique target events remain `OUTSIDE_LOCAL_EVALUATION_DOMAIN`
  within `FIT_DEVELOPMENT`. FMD-06D and later stages must treat these as
  explicit negatives under the local-domain question, not as missing data.
- 144 forecast origins have at least one eligible D1-D7 target, but every
  such target sits beyond 200 km (`outside_domain_target_present = True`,
  `local_domain_positive = False`).
- This amendment describes a computational evaluation domain for the local
  binary question only. It carries no biological, epidemiological, or
  policy claim, and must not be cited as evidence of an actual disease
  spread radius.
- Because this is a post-feasibility amendment rather than a preregistered
  choice, any future comparison against a truly preregistered study should
  disclose this amendment explicitly (which this document, and the
  `POST_FEASIBILITY_PROTOCOL_AMENDMENT` label carried into every downstream
  artifact, is intended to make unambiguous).

## 11. FMD-06D label semantics to be used next

FMD-06D is expected to define, for each `FIT_DEVELOPMENT` forecast origin,
a LOCAL binary label using exactly the Section 7/8 semantics:

```
label = 1  if local_domain_positive        (>= 1 eligible D1-D7 target within 200 km)
label = 0  if NOT local_domain_positive     (no eligible D1-D7 target within 200 km,
                                              whether none exists at all, or all exist
                                              only OUTSIDE_LOCAL_EVALUATION_DOMAIN)
```

`outside_domain_target_present` must be carried forward as an explicit
auxiliary column, not collapsed into the binary label, so FMD-06D and later
analyses can always distinguish the two negative sub-populations. **This
document does not itself generate `fmd06_risk_origin_labels.csv`** -- that
file remains FMD-06D's responsibility, performed after this amendment is
frozen.

## 12. Audit trail / provenance

- Amendment rule and rationale: this document, plus
  `AMENDED_SPATIAL_SELECTION_RATIONALE`,
  `AMENDED_SPATIAL_SELECTION_RULE`, and `FMD_SPATIAL_EVALUATION_RADIUS_KM`
  constants in
  `backend/components/geospatial_tracking/services/fmd_calibration.py`.
- Amended-domain audit implementation:
  `build_fmd06c_pa_local_domain_audit` /
  `summarize_fmd06c_pa_local_domain_audit` /
  `run_fmd06c_pa` in the same module. Coverage-at-200km decisions are never
  recomputed independently -- they come unchanged from
  `domain_design.build_development_domain_candidate_audit`
  (`covered_by_candidate_km[200.0]`), the same single source of truth used by
  the original FMD-06C rule (FMD-06C-R1/R2).
- Machine-readable artifacts (all under
  `local_data/processed/fmd/calibration/`):
  - `fmd06_pa_local_domain_audit.csv` -- one row per `FIT_DEVELOPMENT`
    forecast origin.
  - `fmd06_pa_amendment_summary.json` -- the Section 5 aggregate report plus
    amendment metadata.
  - `fmd06_calibration_freeze.json` -- extended with `original_*`,
    `spatial_protocol_amendment_*`, and `amended_*` keys; original
    `spatial_domain_status` / `spatial_evaluation_radius_km` untouched.
- Tests: `backend/components/geospatial_tracking/tests/test_fmd06_calibration.py`
  (`test_fmd06c_pa_*`).
- Determinism: both the per-origin audit CSV and the summary JSON are
  reproducible byte-for-byte across repeated builds (verified via SHA-256
  hash comparison across two independent build runs).
