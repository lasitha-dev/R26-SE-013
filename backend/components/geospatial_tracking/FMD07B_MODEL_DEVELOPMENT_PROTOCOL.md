# FMD-07B Model Development Protocol — Software Contract Freeze

## 1. Checkpoint identity and current state

- Checkpoint: `FMD-07B`
- Name: FIT_DEVELOPMENT-only model development and training
- Protocol status: `SOFTWARE_CHECKPOINT_CONTRACT_FROZEN_NO_EXECUTION`
- Verified entry gate:
  `FMD-07A-R2B3_COMPLETE_READY_FOR_FMD-07B`
- Current checkpoint state:
  `FMD-07B_BLOCKED_REQUIRED_CANDIDATE_SET_NOT_EXECUTABLE`
- Next checkpoint after a valid FMD-07B completion: `FMD-08`

This document freezes the software contract only. It does not authorize or
perform model fitting, prediction, metric calculation, dependency installation,
or evaluation-data access.

## 2. Purpose and governing repository contracts

FMD-07B is responsible for development-only fitting, chronological validation,
candidate comparison, model selection, final FIT_DEVELOPMENT refitting, and the
freeze of the single model that FMD-08 may evaluate.

The following existing rules govern this checkpoint and are not weakened here:

1. `FMD_EVALUATION_PROTOCOL.md` Section 6 says future FMD-07 candidates must be
   compared, at minimum, with the naive/statistical, spatial/distance, PISTES,
   ML, and hybrid families.
2. `FMD_EXPERIMENT_REGISTRY.json` defines FMD-08's model as the single model
   selected from `FMD-EXP-01..05` using FIT_DEVELOPMENT evidence only.
3. `FMD07_PRE_MODEL_PROTOCOL_AMENDMENT.md` freezes the available candidate
   definitions and preserves the PISTES, hybrid, and dependency blockers.
4. `FMD_EVALUATION_PROTOCOL.md`, `FMD_SPLIT_PROTOCOL.md`, and
   `VALIDATION_PROTOCOL.md` freeze the training-only preprocessing,
   chronological-fold, purge/embargo, selection, and evaluation firewalls.
5. FMD-07B's modelling unit remains the forecast origin and its target remains
   the already-frozen D1-D7 risk target. Labels are outcomes only and must never
   enter the predictor set.

## 3. Exact input artifacts

The following are the only checkpoint data/configuration inputs:

1. `local_data/processed/fmd/model_development/fmd07_r2b3_development_feature_matrix.csv`
2. `local_data/processed/fmd/model_development/fmd07_r2b3_origin_feature_aggregation_audit.csv`
3. `local_data/processed/fmd/model_development/fmd07_r2b3_manifest.json`
4. `local_data/processed/fmd/model_development/fmd07_model_input_schema.json`
5. `local_data/processed/fmd/model_development/fmd07_origin_feature_assembly_protocol.json`
6. `local_data/processed/fmd/model_development/fmd07_development_protocol.json`
7. `local_data/processed/fmd/model_development/fmd07_pre_model_protocol_amendment.json`
8. `local_data/processed/fmd/cohort/fmd_calendar_year_folds.json`
9. `local_data/processed/fmd/calibration/fmd06_risk_origin_labels.csv`
10. `backend/components/geospatial_tracking/FMD_EXPERIMENT_REGISTRY.json`
11. `backend/components/geospatial_tracking/FMD_FEATURE_ELIGIBILITY.csv`
12. The governing protocol documents named in Section 2.

Before any future FMD-07B execution, the implementation must verify the entry
token and every upstream hash recorded by `fmd07_r2b3_manifest.json`. Hash drift,
role drift, schema drift, ordering drift, or replacement of an upstream artifact
is a hard stop. FMD-07B must never rewrite an input artifact.

## 4. Allowed and forbidden data

Allowed:

- `FIT_DEVELOPMENT` forecast origins and their frozen D1-D7 risk labels;
- the frozen calendar-year expanding-window folds;
- fold-training rows for fitting preprocessing, imputation, scaling,
  calibration, class handling, or model parameters;
- each fold's validation rows only for the already-frozen development selection
  and reporting rules;
- all FIT_DEVELOPMENT rows for the final refit only after the winning candidate,
  preprocessing, threshold, and calibration choices have been frozen from the
  development procedure.

Forbidden:

- all `HELD_OUT_FROM_MODEL_FITTING` rows, outcomes, features, predictions, and
  metrics;
- all `SRI_LANKA_TRANSFER_CASE_STUDY` rows, outcomes, features, predictions, and
  metrics;
- any FMD-08 locked-test artifact or result;
- post-`t0` predictor information;
- global preprocessing fitted before a fold split;
- unavailable predictors imputed into existence;
- direction or speed execution while their experiment-registry entries remain
  `BLOCKED`;
- network retrieval, data processing, or mutation of canonical, cohort,
  calibration, feature, or R2B3 artifacts.

Every FMD-07B manifest must carry these exact firewall values:

```text
held_out_used=false
sri_lanka_used=false
locked_test_used=false
```

## 5. Candidate eligibility states

An FMD-07B candidate has exactly one software eligibility state:

- `EXECUTABLE`: a complete FMD implementation and input adapter exist; all
  required direct dependencies are explicitly declared under a resolved
  repository compatibility policy; the candidate can participate in the frozen
  fold procedure without accessing forbidden data.
- `PENDING_DEPENDENCY`: the candidate definition is frozen, but a required
  dependency or its compatibility/version decision is unresolved. It must not
  be imported, instantiated, fitted, or scored.
- `BLOCKED`: a repository-defined scientific/software prerequisite or a complete
  FMD implementation is absent. It must not participate or be replaced by an
  improvised substitute.

Registry status and software eligibility are separate fields. In particular,
`FULLY_SPECIFIED` and `FMD07A_R1_FROZEN` do not mean executable.

## 6. Static implementation and dependency audit

### A. FMD-EXP-01 — naive/statistical baseline

```text
registry_status=FULLY_SPECIFIED
implementation_exists=false
required_dependencies=NOT_DEFINED_FOR_AN_ABSENT_FMD_IMPLEMENTATION
all_dependencies_declared=NOT_DEFINED
currently_executable_without_new_dependency=false
protocol_allows_checkpoint_completion_without_it=false
software_eligibility=BLOCKED
```

Repository evidence defines the country-history/persistence comparator in the
protocol and registry builder, but no FMD candidate class, fitting function,
prediction function, or FMD-07B runner implements it.

### B. FMD-EXP-02 — spatial/distance baseline

```text
registry_status=FMD07A_R1_FROZEN
implementation_exists=PARTIAL_DISEASE_INDEPENDENT_COMPONENTS_ONLY
required_dependencies=PYTHON_STANDARD_LIBRARY, REPOSITORY_INTERNAL_MODULES, pyproj, shapely, rasterio, requests
all_dependencies_declared=TRUE_FOR_THE_EXISTING_GENERIC_COMPONENTS; NOT_DEFINED_FOR_THE_MISSING_FMD07B_COMPOSITION
currently_executable_without_new_dependency=false
protocol_allows_checkpoint_completion_without_it=false
software_eligibility=BLOCKED
```

`services/model_development/baseline_registry.py` and
`services/model_development/baseline_scoring.py` provide reusable
disease-independent candidate/scoring components. Their observed external
import chain is declared in `backend/requirements.txt`. FMD-07A-R1 provides a
frozen FMD kernel-scale registry. No FMD-07B implementation composes those
pieces into the FMD candidate grid, adapts the frozen FMD inputs, performs the
FMD chronological development procedure, or emits an FMD model artifact.

The existing `candidate_registry_7b.py` candidate grid belongs to the earlier
disease-independent/LSD Checkpoint 7B configuration and must not be treated as
an FMD candidate grid or copied with its fitted settings.

### C. FMD-EXP-04 — ML candidates

```text
registry_status=FMD07A_R1_FROZEN_PENDING_DEPENDENCY
implementation_exists=false
required_dependencies=scikit-learn; OTHER_IMPLEMENTATION_DEPENDENCIES_NOT_DEFINED
all_dependencies_declared=false
currently_executable_without_new_dependency=false
protocol_allows_checkpoint_completion_without_it=false
software_eligibility=PENDING_DEPENDENCY
```

The repository contains a declarative registry for `LOGISTIC_REGRESSION`,
`RANDOM_FOREST`, and `GRADIENT_BOOSTED_TREES`. Existing structural tests require
the FMD-07A registry module not to import or instantiate `sklearn`; no estimator,
pipeline, fitting, prediction, or FMD-07B ML runner exists.

### D. Other frozen experiment states

- `FMD-EXP-03` PISTES: registry status `BLOCKED`; software eligibility
  `BLOCKED`. Its real FMD feature-to-factor transformer is not defined.
- `FMD-EXP-05` hybrid: registry status `BLOCKED_BY_PISTES`; software eligibility
  `BLOCKED`. It must not be redefined as an ML-only ensemble.
- `FMD-EXP-08` direction: `BLOCKED` and outside FMD-07B risk-model execution.
- `FMD-EXP-09` speed: `BLOCKED` and outside FMD-07B risk-model execution.

## 7. scikit-learn dependency policy

Current repository evidence provides:

- no `scikit-learn` declaration in a current dependency manifest;
- no repository-defined `scikit-learn` version;
- no CI/runtime compatibility requirement for `scikit-learn`;
- no repository-local installed-environment version identified as the version
  used by project tests or documentation;
- current FMD tests that deliberately verify no `sklearn` import in pre-model
  and data-pipeline modules;
- historical `scikit-learn` dependency declarations, but all are unpinned and
  therefore provide no compatible-version decision. This includes the
  unpinned additions visible in commits `ef4127a`, `9d5672f`, and `31fe1e0`;
  commit `cf6230a` removes one of those unrelated component manifests.

The exact dependency-resolution state is:

```text
SCIKIT_LEARN_VERSION_UNRESOLVED
```

No version may be inferred from an installed machine, selected as "latest", or
copied from an unrelated component. FMD-EXP-04 remains non-executable until a
separately authorized packaging decision establishes compatibility evidence,
chooses an explicit version, declares it in the repository dependency manifest,
and updates the focused dependency assertions. This protocol does not make that
decision.

## 8. Completion with a candidate subset

FMD-07B is not allowed to complete with only a currently executable subset.

`FMD_EVALUATION_PROTOCOL.md` Section 6 requires the five FMD-07 comparator
families at minimum, and `FMD_EXPERIMENT_REGISTRY.json` defines downstream
selection across `FMD-EXP-01..05`. Omitting ML, naive, spatial, PISTES, or hybrid
would change that frozen selection contract. An ineligible candidate must remain
visible and blocked; it must not be silently dropped, replaced, or scored using
another family's implementation.

At this freeze, no complete FMD-07B candidate path is `EXECUTABLE`. Dependency
resolution alone is not sufficient: the missing FMD implementations and the
PISTES/hybrid prerequisites must also be resolved under separately frozen,
repository-supported contracts before FMD-07B can run to completion.

## 9. Exact output artifacts

After all blockers are resolved, a valid FMD-07B execution must create exactly
these new artifacts under `local_data/processed/fmd/model_development/`:

1. `fmd07b_candidate_eligibility.json`
2. `fmd07b_candidate_registry.json`
3. `fmd07b_chronological_fold_manifest.json`
4. `fmd07b_fold_predictions.csv`
5. `fmd07b_fold_candidate_metrics.csv`
6. `fmd07b_fold_summary_metrics.csv`
7. `fmd07b_preprocessing_calibration_audit.json`
8. `fmd07b_candidate_selection_summary.json`
9. `fmd07b_frozen_model_spec.json`
10. `fmd07b_manifest.json`

`fmd07b_frozen_model_spec.json` must contain the complete selected model,
preprocessing, calibration, threshold, fitted-state, implementation-identity,
and resolved dependency metadata required for FMD-08 to use the already-fitted
model without tuning or refitting. No unlisted model-state sidecar is permitted.

No artifact in this list may be emitted as valid completion evidence while the
checkpoint blocker token is active. Partial/debug outputs must not use these
canonical names.

## 10. Focused and regression tests

The exact focused test filename is:

```text
backend/components/geospatial_tracking/tests/test_fmd07b_model_development.py
```

The focused test must cover candidate-state classification, dependency refusal,
the complete minimum candidate set, chronological and purge/embargo invariants,
training-fold-only preprocessing, label exclusion from predictors, deterministic
candidate identity, output schema/hashes, final-fit freeze, and all three
firewall flags.

Required affected regressions are:

- `test_fmd07a_r1_pre_model_amendment.py`
- `test_fmd07a_r2b3_origin_matrix_population.py`
- `test_fmd07a_feature_matrix.py`
- `test_fmd05_study_protocol.py`
- `test_fmd05r_unit_semantics.py`
- `test_fmd06_calibration.py`
- `test_model_fitting_exposure.py`
- `test_split_embargo.py`
- `test_walk_forward.py`
- `test_baseline_registry.py`
- `test_checkpoint_7b_kernel_registry.py`
- `test_checkpoint_7b_baseline_math.py`
- `test_hazard_no_forbidden_modeling.py`

The full backend suite is required before a future FMD-07B completion may be
declared. It is not run during this software-contract freeze.

## 11. Determinism and reproducibility

A future implementation must:

1. use only the frozen candidate values and the fixed seed `42` already defined
   by the FMD-07A-R1 amendment;
2. derive candidate identifiers from complete canonical candidate definitions,
   never list order or observed performance;
3. preserve the frozen fold membership and purge/embargo policy exactly;
4. fit every learned preprocessing, imputation, scaling, calibration, class
   handling, and model parameter inside the applicable training fold only;
5. use stable row ordering and field ordering for CSV outputs;
6. write JSON with sorted keys, finite values only, and no wall-clock field in
   deterministic content;
7. write outputs atomically and record SHA-256 for every input and output;
8. record the Python and resolved direct dependency versions in the manifest,
   without using those environment values to choose a winner;
9. produce byte-identical canonical artifacts in two independent offline runs
   from identical inputs and the same resolved environment;
10. fail closed on input/hash/schema/role drift, single-role contamination,
    dependency mismatch, non-finite output, or nondeterminism.

## 12. Completion and blocker tokens

The exact blocker token for the current repository state is:

```text
FMD-07B_BLOCKED_REQUIRED_CANDIDATE_SET_NOT_EXECUTABLE
```

That token remains active while any required `FMD-EXP-01..05` family is not
`EXECUTABLE`, including while `SCIKIT_LEARN_VERSION_UNRESOLVED` is active.

Only after all required candidate families participate, all frozen selection and
firewall rules pass, all ten artifacts exist and hash correctly, the focused and
affected-regression tests pass, the full backend suite passes, and independent
offline runs are reproducible may the checkpoint emit:

```text
FMD-07B_COMPLETE_READY_FOR_FMD-08
```

FMD-08 is the next checkpoint. FMD-07B must stop after freezing its selected
model and must not inspect or evaluate the locked test or Sri Lanka case study.
