# FMD-06B Calibration Protocol

This checkpoint defines deterministic software/data calibration for historical
timestamped geospatial records. It does not interpret disease biology.

## Development universe

The input ledger is first passed through the existing `FIT_DEVELOPMENT` role
selection and then through `assert_fit_development_only` at every calibration
entry point. `HELD_OUT_FROM_MODEL_FITTING` and
`SRI_LANKA_TRANSFER_CASE_STUDY` rows are rejected before repository access.
The validated source universe is built by the existing
`build_fit_development_source_universe` helper, which reuses the existing
historical source selector and country scope.

The run contains 3,761 forecast origins, 6,799 unique development source-event
rows, and 91 countries. Source availability and historical event dates remain
separate fields. Predictor-facing source construction uses availability dates
in the inclusive interval `[t0 - active_window_days, t0]`; a source after `t0`
cannot enter. Historical event dates after `t0` remain temporally unusable for
clustering and are not substituted with a later field.

## Active-window candidates and selection

The existing generic registry supplies the fixed candidates `(7, 14, 21, 28)`
days. The active window is a temporal data window only. For each candidate the
run reports origin counts, active-source distribution quantiles, zero/single
source counts, a p95-based very-large snapshot diagnostic, and country/year
distributions.

The predeclared selection rule is:

1. reject the candidate set if every candidate leaves every development origin
   empty;
2. retain candidates with the minimum zero-source-origin fraction; and
3. select the smallest retained window.

This minimizes the temporal data window subject to the best available origin
coverage. The FMD run selects 7 days, classified as
`DEVELOPMENT_CALIBRATED_TEMPORAL_DATA_PARAMETER`, not a biological constant.

## ST-DBSCAN candidates and selection

The existing country-scoped candidate registry is reused. Each country
contributes one median within-country nearest-neighbour distance and one median
positive temporal gap. The p25/p50/p75 values of those country medians form the
candidate axes, with six-decimal deterministic rounding. The existing fixed
`min_core_supports` registry `(2, 3, 4)` is reused. The FMD candidate grid is
therefore 3 × 3 × 3 = 27 configurations; no LSD fitted value is copied.

Each configuration uses the existing WGS84 geodesic neighbourhood, core-support
policy, and deterministic clustering implementation. Structural diagnostics
include cluster/noise counts, noise fraction, cluster-size and temporal-span
distributions, spatial compactness, country/year coverage, and one-step
neighbour stability. A configuration is rejected as degenerate when it is
all-noise, has noise fraction at least 0.90, or has largest-cluster fraction at
least 0.90. Among the remaining configurations, the highest mean neighbour
agreement is selected, with deterministic parameter-value tie-breaks.

The selected FMD configuration is `eps_space_km=18.58035`,
`eps_time_days=13.5`, and `min_core_supports=4`, classified as
`DEVELOPMENT_CALIBRATED_SOFTWARE_PARAMETERS`. Resulting groups are described
only as descriptive historical geospatial-temporal clusters.

No target rows, risk labels, predictive metrics, held-out rows, Sri Lanka
case-study rows, or ML model are used.

## FMD-06C spatial-domain calibration (original predeclared rule)

FMD-06C reuses, verbatim, the pre-existing Checkpoint 7A domain-design
candidate registry `PREDECLARED_DOMAIN_CANDIDATES_KM = (25, 50, 75, 100, 150,
200)` km and selection rule
`services.model_development.domain_design.select_frozen_domain_distance`: the
smallest predeclared candidate whose `FIT_DEVELOPMENT` D1-D7
`risk_target_eligible` target-appearance coverage (geodesic distance from the
target to the nearest `ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0` source `<=`
candidate km) reaches exactly 100%. This rule is fixed before any candidate
outcome is generated and never chosen using predictive accuracy, held-out
data, or Sri Lanka case-study data.

On the real FMD `FIT_DEVELOPMENT` corpus, no candidate reached 100% coverage
(maximum coverage at 200 km was 17,106/17,965 = 95.2%), so the rule correctly
returns `DOMAIN_RULE_BLOCKED` and the original result is
**`spatial_domain_status = NO-GO`**, `spatial_evaluation_radius_km = null`.
This original NO-GO result is preserved permanently in
`fmd06_calibration_freeze.json` under `spatial_domain_status`/
`spatial_evaluation_radius_km` and is never rewritten.

## FMD-06C-PA spatial-domain protocol amendment

See `FMD06_SPATIAL_DOMAIN_PROTOCOL_AMENDMENT.md` for the full amendment
record. In short: because the original predeclared 100%-coverage rule was
infeasible, a `POST_FEASIBILITY_PROTOCOL_AMENDMENT` (explicitly NOT
preregistered) fixes the LOCAL geospatial prediction domain at
`FMD_SPATIAL_EVALUATION_RADIUS_KM = 200.0` km -- the maximum radius already
present in the predeclared candidate registry, chosen by the rule
`MAXIMUM_PREDECLARED_LOCAL_EVALUATION_DOMAIN`, never a newly invented value,
and never chosen using held-out data, Sri Lanka data, or predictive-model
performance. This is recorded in `fmd06_calibration_freeze.json` under the
`amended_*` keys, alongside the untouched original `spatial_domain_status`/
`spatial_evaluation_radius_km` NO-GO/null record.

## FMD-06D deterministic development label freeze (final FMD-06 checkpoint)

FMD-06D materializes the `FIT_DEVELOPMENT` risk-origin label artifact FMD-07
will train against: `fmd06_risk_origin_labels.csv`, one row per forecast
origin (never per target appearance), built by
`build_fmd06d_risk_origin_labels`/`run_fmd06d`
(`services/fmd_calibration.py`). It performs no new geospatial computation --
`fmd06_pa_local_domain_audit.csv` (FMD-06C-PA's already-frozen output) is the
sole source of each origin's coverage decision, and
`assert_fit_development_only` firewalls the origin list at the function's own
entry point before any row is emitted.

Label rule: `risk_target_label = 1` iff `local_domain_positive` is true for
that origin in the frozen audit (>=1 eligible D1-D7 target within the fixed
200 km local evaluation domain); `= 0` otherwise. The negative class
deliberately keeps two distinguishable subtypes visible via the preserved
`outside_domain_target_present` and `has_eligible_d1_d7_target` columns:
"no eligible D1-D7 target at all" and "eligible target(s), all outside the
domain" are never collapsed into one undifferentiated negative.

`run_fmd06d` asserts the resulting counts match the frozen FMD-06C-PA
reconciliation exactly (3,761 rows; 2,215 positive; 1,546 negative = 1,402
no-target + 144 outside-domain-only; positive fraction 0.588939) and raises
(BLOCKED, never silently adjusted) if they do not.

`HELD_OUT_FROM_MODEL_FITTING` and `SRI_LANKA_TRANSFER_CASE_STUDY` outcomes
are never materialized, inspected, or summarized by FMD-06D -- their labels
and prevalence remain unopened until FMD-08's locked evaluation.

FMD-06D also writes the final `fmd06_calibration_manifest.json`, recording
every frozen FMD-06 parameter (active-window, ST-DBSCAN, original NO-GO,
amendment provenance), the label reconciliation, `direction_speed_status =
NO-GO` (non-blocking; see `FMD_TARGET_PROTOCOL.md` Section 4),
`weather_window_selection_status = DEFERRED_TO_FMD07_DEVELOPMENT_SELECTION`
(see `FMD_EVALUATION_PROTOCOL.md` Section 3), and
`predictive_model_trained = false`, so FMD-07 can consume one deterministic
snapshot of everything FMD-06 froze.

No target rows beyond the D1-D7 window, no held-out/Sri-Lanka labels, no
predictive metric, and no ML model are used or created anywhere in FMD-06D.
