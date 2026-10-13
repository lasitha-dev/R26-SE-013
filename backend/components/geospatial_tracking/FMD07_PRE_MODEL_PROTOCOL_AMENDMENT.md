# FMD-07A-R1: Pre-Model Development Protocol Amendment

Status: **`PRE_MODEL_DEVELOPMENT_PROTOCOL_AMENDMENT`** — explicitly NOT
preregistered. This document is written after the FMD-07A protocol audit
and BEFORE any FMD-07 predictive score, PR-AUC calculation, model fit,
hyperparameter comparison, or weather-window winner selection.

## 1. FMD-07A blocker

FMD-07A completed a leakage-safe schema-only development feature matrix
(3,761 `FIT_DEVELOPMENT` rows, real metadata/labels, 47 eligible predictor
columns all honestly `EXTRACTION_NOT_RUN`) and audited the pre-existing
model-development protocol. It found two independent blockers:

1. **Predictor value population**: every eligible feature requires the
   FMD-04 remote-adapter pipeline, run so far only on a 29-event validation
   sample — never the real 3,761-origin cohort. This blocker is **not
   resolved by this amendment** (see Section 15/`fmd07a-r1`'s own scope).
2. **Four candidate-model protocol gaps**:
   `FMD07_PROTOCOL_GAP_SPATIAL_BASELINE_KERNEL_SCALE_CANDIDATES`,
   `FMD07_PROTOCOL_GAP_PISTES_HAZARD_COEFFICIENT_CANDIDATES`,
   `FMD07_PROTOCOL_GAP_ML_CANDIDATE_HYPERPARAMETER_SPACE`,
   `FMD07_PROTOCOL_GAP_HYBRID_CANDIDATE_HYPERPARAMETER_SPACE`.

**This amendment addresses only the second blocker.** The FMD-07A finding
that no eligible predictor has a real value yet is preserved unchanged in
`fmd07a_provenance.json` and is never rewritten or reinterpreted as
resolved.

## 2. Why an amendment is required

The current repository did not predeclare every FMD-07 candidate-model
hyperparameter space before FMD-07A's audit ran. Two of the four gaps
(spatial-baseline kernel-scale candidates, ML candidate hyperparameters)
can be defensibly frozen now, using only pre-existing repository
architecture and standard, well-known algorithm definitions — never
inventing a new scientific mechanism, never choosing a value because it
performs well. The other two (PISTES coefficients, the hybrid family that
depends on PISTES) genuinely cannot be defensibly frozen yet, for reasons
specific to each (Sections 5 and 7 below) — they remain honestly BLOCKED
rather than forced.

## 3. Explicit non-preregistered classification

```
amendment_status = "PRE_MODEL_DEVELOPMENT_PROTOCOL_AMENDMENT"
```

This is explicitly **not** a preregistered protocol. It was:

- introduced **after** the FMD-07A protocol audit identified the four gaps;
- introduced **before** any FMD-07 predictive model was trained;
- introduced **before** any validation PR-AUC, AUROC, or other predictive
  metric was calculated;
- introduced **without** using `HELD_OUT_FROM_MODEL_FITTING` outcomes;
- introduced **without** using `SRI_LANKA_TRANSFER_CASE_STUDY` outcomes;
- introduced **without** inspecting any comparative model performance.

## 4. Evidence that no predictive metrics existed before this amendment

- No `fmd07_development_feature_matrix.csv` predictor column has ever
  carried a real numeric value (`FMD07_FEATURE_VALUE_STATUS =
  FULL_CORPUS_EXTRACTION_NOT_RUN`, preserved unchanged by this amendment)
  — there is nothing to have computed a score, let alone a metric, from.
- `services/hazard/`, `services/model_development/baseline_registry.py`,
  and `services/model_development/candidate_registry_7b.py` contain no
  function whose signature accepts a target, label, or outcome parameter
  (verified structurally, unchanged from Checkpoint 7A/7B's own
  `NOFIT`/leakage tests).
- This module (`fmd_model_development_r1.py`) never imports the held-out
  or Sri Lanka origin selectors, and every registry-building function
  records `predictive_metrics_used_to_define: false`.

## 5. Candidate-model registries

### 5a. Spatial/distance baseline — `FMD07A_R1_FROZEN`

Mechanism (unchanged, pre-existing, disease-agnostic):
`services/model_development/baseline_registry.py`'s
`B0_DISTANCE_ONLY`/`B1_HOST_DISTANCE_LOG1P`/`B2_HOST_DISTANCE_ECDF` ×
`services/hazard/contracts.KernelFamily`'s `EXPONENTIAL`/`GAUSSIAN`.

The missing piece — an FMD-specific kernel-scale candidate registry — is
now frozen as a **small, deterministic subset of the pre-existing,
disease-agnostic** `services/model_development/domain_design.
PREDECLARED_DOMAIN_CANDIDATES_KM = (25, 50, 75, 100, 150, 200)` registry:

```
kernel_scale_candidates_km = (25.0, 50.0, 100.0)
```

No new number is invented. Deliberately excluded:

- `200.0` km — the FMD-06C-PA label-definition radius, excluded so this
  registry can never be read as automatically reusing it;
- `0.236038` km — the FMD-06B-R ST-DBSCAN `eps_space_km` value, never a
  member of this list;
- `150.0` km — dropped only to keep the candidate set small and
  panel-defensible while still spanning short/medium/broad scales via the
  retained 25/50/100 km values.

Total grid: `3 baseline families × 2 kernel families × 3 kernel scales =
18` candidates. Classified as a **computational model hyperparameter
only** — never a spread radius, transmission boundary, or biological
claim of any kind.

### 5b. PISTES / hazard model — **BLOCKED**

`services/hazard/` (`HAZARD_ENGINE_PROTOCOL.md` sec 3, Checkpoint 6C.5)
structurally refuses any `CellHazardFactors`/`SourceHazardFactors` value
whose status is not `SOFTWARE_FIXTURE_ONLY` — a `REAL` value is rejected
outright by the contract itself. The real feature→factor transformer
needed to populate `host_factor`/`environmental_suitability_factor`/
`water_context_factor`/`source_strength_factor` from FMD's own extracted
features does not exist: `FEATURE_ASSEMBLY_PROTOCOL.md` Checkpoint 6D
records all three (plus `source_strength_factor`) as
`NOT_YET_SCIENTIFICALLY_DEFINED`, and even `host_density_total`'s own
candidate transforms are not scientifically selected.
`HazardMixConfig.local_weight`/`anisotropic_weight`, the anisotropy
`kappa`, and `distance_scale_km` are all structurally forbidden from
`FROZEN_REFERENCE` status by the engine's own code.

Freezing a coefficient/kernel-scale candidate grid for an equation that
structurally cannot receive real inputs today would not be a defensible
finite candidate space — it would pretend the equation currently computes
something it cannot. The existing equation (`H_j_i = a·L_j_i + b·W_j_i`,
`H_i = Σ_j H_j_i`, `R_i = 1-exp(-H_i)`) is read and preserved unchanged —
no sign, feature, or scientific semantic is reinterpreted. This family
stays **BLOCKED** until a future, separately-scoped checkpoint builds and
freezes the real feature→factor transformer.

### 5c. ML candidate — `FMD07A_R1_FROZEN_PENDING_DEPENDENCY`

A modest, deterministic, 3-algorithm-family registry (11 total
hyperparameter candidates), built from standard, well-known tabular
binary-classification algorithms:

| Algorithm | Hyperparameter candidates | Preprocessing | Missing values | Probability output |
|---|---|---:|---|---|
| `LOGISTIC_REGRESSION` | `C ∈ {0.1, 1.0, 10.0}` (3) | scaling required | requires imputation | native |
| `RANDOM_FOREST` | `n_estimators ∈ {100,300}`, `max_depth ∈ {5,10}` (4) | none | requires imputation | native |
| `GRADIENT_BOOSTED_TREES` | `learning_rate ∈ {0.05,0.1}`, `max_depth ∈ {3,5}` (4) | none | handles natively | native |

Random seed policy: **fixed seed 42** for every candidate (reuses this
repository's own established convention,
`BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md` sec 8's bootstrap-CI seed) — never
re-seeded to chase a result. Class-weight/imbalance handling is available
per-algorithm but **not applied by default** (natural balance 58.9%/41.1%
is not severely imbalanced).

**Dependency note**: `scikit-learn` is **not currently a
`backend/requirements.txt` dependency**. This amendment does not add it —
that remains a separate, non-scientific packaging decision for whenever
FMD-07B actually needs to instantiate these candidates. No candidate was
chosen for observed FMD performance; none was evaluated in this checkpoint.

### 5d. Hybrid candidate — **`BLOCKED_BY_PISTES`**

`FMD_EVALUATION_PROTOCOL.md` sec 6 item 5 defines the hybrid family as
"combining (3) and (4)" — the PISTES/hazard family and the ML family,
architecture otherwise unspecified. Since PISTES remains BLOCKED (5b), the
hybrid family structurally inherits that block. It is never redefined as
an ML-only ensemble or any other architecture not described by the
repository's own definition.
`FMD07_PROTOCOL_GAP_HYBRID_CANDIDATE_HYPERPARAMETER_SPACE` is preserved,
now specifically annotated `BLOCKED_BY_PISTES`.

## 6. Threshold policy

Existing rule (unchanged): the decision threshold is selected on
`FIT_DEVELOPMENT`/validation folds only (`FMD_EVALUATION_PROTOCOL.md` sec
5). No development SELECTION PROCEDURE existed before this amendment. Now
frozen: for any candidate requiring a single operating threshold
(sensitivity/specificity/precision/F1 reporting only — PR-AUC/AUROC/Brier/
reliability remain threshold-free), the threshold is selected via nested
chronological validation strictly inside `FIT_DEVELOPMENT` development
folds (`VALIDATION_PROTOCOL.md` sec 1): for each usable outer fold,
evaluate a fixed candidate threshold grid (0.05 to 0.95, step 0.05)
against that fold's own validation predictions, select the threshold
maximizing F1 within that fold, then report the equal-fold-weighted median
selected threshold across all usable outer folds. Never selected using
held-out/Sri-Lanka data, never using accuracy, never tuned after FMD-08's
locked result.

```
threshold_value_status = "THRESHOLD_VALUE_NOT_SELECTED_PRE_MODEL"
```

No numeric threshold is chosen in this checkpoint.

## 7. Probability calibration policy

Existing requirement (unchanged): Brier score + reliability/calibration
curve required before any risk score is described as a "probability"
(`FMD_EVALUATION_PROTOCOL.md` sec 5). Now frozen: if calibration is
applied, it is fit using only `FIT_DEVELOPMENT` training-fold data, nested
inside the same walk-forward structure — never on validation, held-out, or
Sri Lanka rows. Allowed methods are restricted to standard, well-
established, monotonic techniques (Platt/sigmoid scaling, isotonic
regression); the choice between them, if made, is based on the
`FIT_DEVELOPMENT` reliability-curve shape observed within development
folds only, never on downstream PR-AUC/AUROC improvement. No calibration
is fit in this checkpoint.

## 8. Preprocessing / imbalance policy

Any imputation, scaling, encoding, feature selection, dimensionality
reduction, class weighting, or resampling parameter is fit on the relevant
training fold only, inside nested `FIT_DEVELOPMENT` chronological
validation — never globally across all 3,761 origins, never on
validation/held-out/Sri-Lanka rows. No imbalance correction is applied by
default. Per-algorithm requirements (scaling/class-weight/missing-value
handling) are recorded in Section 5c above and in
`fmd07_pre_model_protocol_amendment.json`.

## 9. CV / fold-validity rule

Reuses the pre-existing repository convention **verbatim**
(`BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md` sec 3: "A fold whose
training-origin list is empty is reported as
`INSUFFICIENT_PRIOR_TRAINING_HISTORY` and excluded from evaluation/
selection"), extended with an equally structural (never performance-based)
single-class-validation criterion: a development fold is excluded from
evaluation/selection iff its training-origin list is empty, OR its
validation set has zero positive-class or zero negative-class origins
(PR-AUC/AUROC are undefined for a single-class validation set). Both
criteria are computed from `fmd_calendar_year_folds.json` +
`fmd06_risk_origin_labels.csv` structure alone, before any model is fit or
scored.

**Real result** (FMD-07A's `verify_fmd07a_cv_folds`, unchanged): of 23
folds, `FOLD:2002` (empty training set, 0 positives in its 1-origin
validation set) and `FOLD:2003` (1 training origin, 0 positives in its
2-origin validation set) are excluded — **21 usable folds** for FMD-07B.
Never silently dropped; both remain fully visible in
`fmd07_development_protocol.json`'s `cv_scheme.verification`.

## 10. Weather-window candidate freeze

Unchanged from FMD-07A: `event_day`, `window_3day`, `window_7day`,
`window_14day` (`FMD_FEATURE_ELIGIBILITY.csv`). No winner is selected —
`weather_winner_status = "NOT_SELECTED"`.

## 11. Held-out / Sri Lanka firewall

`held_out_outcomes_used = false`, `sri_lanka_outcomes_used = false` in
every registry this module builds. No function in
`fmd_model_development_r1.py` imports
`held_out_from_model_fitting_origins`/`sri_lanka_transfer_case_study_origins`
(verified structurally). No candidate value in Sections 5-9 above was
derived from, or could have been influenced by, either group's outcomes —
none has ever been computed for any real FMD score.

## 12. Unresolved families

After this amendment, `unresolved_protocol_gap_count = 2`:

- `FMD07_PROTOCOL_GAP_PISTES_HAZARD_COEFFICIENT_CANDIDATES` — BLOCKED,
  pending a future feature→factor transformer checkpoint.
- `FMD07_PROTOCOL_GAP_HYBRID_CANDIDATE_HYPERPARAMETER_SPACE` — BLOCKED_BY_PISTES,
  inherits the above.

Down from the original 4 (`original_protocol_gap_count`, preserved
unchanged in `fmd07_development_protocol.json`).

## 13. Limitations

- This amendment resolves candidate-model PROTOCOL gaps only. It does
  **not** resolve the predictor-value population blocker — every eligible
  feature remains `EXTRACTION_NOT_RUN` for the real 3,761-origin cohort.
- The ML candidate registry cannot be instantiated until `scikit-learn` is
  added as a repository dependency — a deliberately deferred, non-
  scientific packaging decision.
- The spatial-baseline kernel-scale registry is a software hyperparameter
  choice, not a validated distance derived from FMD spread biology (FMD is
  explicitly documented elsewhere in this repository as non-vector-borne;
  no biological transmission-distance claim is made anywhere in this
  document).
- PISTES/hybrid remain genuinely blocked; no amount of protocol amendment
  can substitute for the missing feature→factor transformer.

## 14. Audit trail

- Amendment implementation: `services/fmd_model_development_r1.py`.
- Machine-readable amendment:
  `local_data/processed/fmd/model_development/fmd07_pre_model_protocol_amendment.json`.
- Updated protocol freeze (original gap audit preserved, amendment fields
  added): `local_data/processed/fmd/model_development/fmd07_development_protocol.json`.
- FMD-07A findings preserved unchanged:
  `local_data/processed/fmd/model_development/fmd07a_provenance.json`,
  `fmd07_development_feature_matrix.csv`, `fmd07_feature_matrix_audit.json`,
  `fmd07_model_input_schema.json` (all three byte-identical to their
  FMD-07A hashes).
- Tests: `backend/components/geospatial_tracking/tests/test_fmd07a_r1_pre_model_amendment.py`.
- Sources consulted: `FMD_EVALUATION_PROTOCOL.md`,
  `FMD_EXPERIMENT_REGISTRY.json`, `MODEL_DEVELOPMENT_PROTOCOL.md`,
  `BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md`, `FEATURE_ASSEMBLY_PROTOCOL.md`,
  `HAZARD_ENGINE_PROTOCOL.md`, `VALIDATION_PROTOCOL.md`,
  `services/model_development/baseline_registry.py`,
  `services/model_development/candidate_registry_7b.py`,
  `services/hazard/kernels.py`, `services/hazard/contracts.py`.
