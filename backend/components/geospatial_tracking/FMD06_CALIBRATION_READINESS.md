# FMD-06 Calibration Readiness

Status: **FMD-06 COMPLETE -- GO for FMD-07 review, subject to the workflow
stop at this checkpoint.** (Originally written at FMD-06B; extended in place
through FMD-06C, FMD-06C-R1/R2, FMD-06C-PA, and FMD-06D -- see the
checkpoint-specific sections below for what each stage actually froze.)

Verified software/data conditions:

- `FIT_DEVELOPMENT` only: 3,761 forecast origins and 6,799 unique source-event
  rows across 91 countries.
- Held-out and Sri Lanka case-study origins are rejected by the FMD-06B entry
  firewall and were not used for candidate generation or sensitivity.
- Active-window candidates are the existing deterministic `(7, 14, 21, 28)`
  registry; the selected temporal data parameter is 7 days.
- ST-DBSCAN candidates are country-balanced, deterministic, and generated from
  FMD development geometry/time evidence only.
- Selected software parameters are `eps_space_km=18.58035`,
  `eps_time_days=13.5`, and `min_core_supports=4`.
- Both selected values are development-calibrated software/data parameters,
  not biological constants.
- All groups are descriptive historical geospatial-temporal clusters only.
- Inclusive availability filtering and the `cluster_event_date <= t0` rule
  protect historical predictor snapshots from future rows.
- No predictive ML model, predictive metric, or held-out performance is
  present anywhere in FMD-06. (A `FIT_DEVELOPMENT`-only risk-origin label
  artifact was later materialized at FMD-06D -- see below -- a deterministic
  projection of already-frozen structure, never a model or a metric.)

Required artifacts are under `local_data/processed/fmd/calibration/` and are
deterministic. Rebuilding them produces identical SHA-256 hashes.

## FMD-06C spatial-domain status

The original predeclared 100%-coverage rule was evaluated on real
`FIT_DEVELOPMENT` data and returned **`spatial_domain_status = NO-GO`**
(`spatial_evaluation_radius_km = null`): no candidate in
`(25, 50, 75, 100, 150, 200)` km reached full D1-D7 target-appearance
coverage. This original result is preserved permanently and is never
rewritten.

## FMD-06C-PA amendment status

Status: **`spatial_protocol_amendment_status = POST_FEASIBILITY_PROTOCOL_AMENDMENT`
(explicitly NOT preregistered) -- GO for FMD-06D under the amended local
domain, subject to the workflow stop at this checkpoint.**

- `amended_spatial_domain_status = GO_WITH_TRANSPARENT_AMENDMENT`.
- `amended_spatial_selection_rule = MAXIMUM_PREDECLARED_LOCAL_EVALUATION_DOMAIN`.
- `amended_spatial_evaluation_radius_km = 200.0` -- the maximum radius already
  present in the predeclared candidate registry; no new candidate was
  introduced.
- `held_out_data_used_for_amendment`, `sri_lanka_data_used_for_amendment`, and
  `predictive_metrics_used_for_amendment` are all `false`.
- The amended local-domain audit (`fmd06_pa_local_domain_audit.csv`, one row
  per `FIT_DEVELOPMENT` forecast origin) and its summary
  (`fmd06_pa_amendment_summary.json`) are deterministic; rebuilding them
  produces identical SHA-256 hashes.
- At the FMD-06C-PA checkpoint itself no `fmd06_risk_origin_labels.csv` file
  existed yet -- `run_fmd06c_pa`'s own implementation never writes it (still
  true and tested). It was materialized one checkpoint later, at FMD-06D
  (below).
- Full details: `FMD06_SPATIAL_DOMAIN_PROTOCOL_AMENDMENT.md`.

## FMD-06D development label freeze

Status: **development labels materialized -- `FIT_DEVELOPMENT` only, one row
per forecast origin, deterministic.**

- `fmd06_risk_origin_labels.csv`: exactly 3,761 rows, one per
  `FIT_DEVELOPMENT` forecast origin (unique `forecast_origin_id`), every
  `model_fitting_role = FIT_DEVELOPMENT`. Built as a pure, deterministic
  projection of the already-frozen `fmd06_pa_local_domain_audit.csv` -- no
  radius, spatial-domain, nearest-source-distance, ST-DBSCAN, or
  active-window parameter is recomputed.
- `risk_target_label = 1` iff `local_domain_positive` (>=1 eligible D1-D7
  target within the fixed 200km local evaluation domain); `= 0` otherwise,
  covering both `no eligible D1-D7 target` and `eligible target(s), all
  outside the domain` -- the latter stays separately visible via the
  preserved `outside_domain_target_present` column, never collapsed.
- Reconciliation (matches the FMD-06C-PA audit exactly):
  `positive = 2,215`, `negative = 1,546` (`no_target = 1,402` +
  `outside_domain_only = 144`), `positive_fraction = 0.588939`.
  `2215 + 1402 + 144 = 3761`.
- `local_evaluation_radius_km = 200.0` on every row; `spatial_reference_source_set
  = ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0` and `spatial_protocol_amendment_status
  = POST_FEASIBILITY_PROTOCOL_AMENDMENT` are carried on every row for
  provenance.
- `HELD_OUT_FROM_MODEL_FITTING` (541 origins) and `SRI_LANKA_TRANSFER_CASE_STUDY`
  (20 origins) outcomes are **not** materialized, inspected, or summarized
  here -- `build_fmd06d_risk_origin_labels` firewalls on
  `assert_fit_development_only` at its own entry point. Their labels,
  positive/negative counts, and prevalence remain unopened until FMD-08.
- `fmd06_calibration_freeze.json.risk_origin_labels_generated` is now `true`
  (it was `false` at every earlier checkpoint, which never wrote the file --
  each earlier checkpoint's own non-generation is independently tested).
- Final manifest: `fmd06_calibration_manifest.json` (`checkpoint = FMD-06`,
  `overall_status = GO`) -- see the file itself for the full frozen-parameter
  snapshot and artifact hashes.
- Repeated-target-appearance semantics remain distinct: 17,965
  target-appearance rows / 4,906 unique target events (`fmd06_pa_amendment_summary.json`)
  never become 17,965 or 4,906 modelling rows -- the modelling unit stays the
  3,761 forecast origins.
- Deterministic: rebuilding `fmd06_risk_origin_labels.csv` and
  `fmd06_calibration_manifest.json` from the same frozen inputs produces
  identical SHA-256 hashes.

## Direction/speed and weather-window status

- **Direction/speed: `NO-GO`, explicitly non-blocking.** Tier A
  (`gps_quality == EXACT`) is structurally unreachable for the FMD corpus (0
  of 31,658 target rows -- `FMD_TARGET_PROTOCOL.md` Section 4), a
  data-quality gap, not a modelling choice. No direction/speed label or
  model exists anywhere in FMD-06. This does not block the primary binary
  D1-D7 risk-model readiness above.
- **Weather-window selection: `DEFERRED_TO_FMD07_DEVELOPMENT_SELECTION`.**
  FMD-04 computed four candidate pre-t0 ERA5 windows
  (`event_day`/`3day`/`7day`/`14day`); FMD-06 selects none of them. Per
  `FMD_EVALUATION_PROTOCOL.md` Section 3, window selection is a
  development-only decision made inside leakage-safe `FIT_DEVELOPMENT`
  cross-validation in FMD-07, never in FMD-06.

## FMD-07 readiness gate

FMD-07 may proceed using `fmd06_risk_origin_labels.csv` as the primary
binary D1-D7 risk-model development target, subject to every rule already
frozen in `FMD_SPLIT_PROTOCOL.md`, `FMD_TARGET_PROTOCOL.md`, and
`FMD_EVALUATION_PROTOCOL.md` -- in particular: `FIT_DEVELOPMENT`-only
parameter/coefficient fitting, no held-out/Sri-Lanka outcome inspection
before FMD-08, and no re-opening of the FMD-06 spatial-domain amendment or
any other frozen FMD-06 parameter based on FMD-07 results.
