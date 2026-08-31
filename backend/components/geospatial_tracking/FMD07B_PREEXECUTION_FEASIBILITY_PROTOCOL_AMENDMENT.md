# FMD-07B Pre-Execution Feasibility Protocol Amendment

## 1. Amendment identity, timing, and scope

```text
checkpoint=FMD-07B
amendment_status=PREEXECUTION_FEASIBILITY_FREEZE
amendment_timing=BEFORE_ANY_FMD07B_MODEL_RESULT
development_candidate_metrics_inspected=false
held_out_outcomes_inspected=false
sri_lanka_outcomes_inspected=false
training_performed=false
evaluation_performed=false
dependency_installed=false
```

This amendment resolves one ambiguity in
`FMD07B_MODEL_DEVELOPMENT_PROTOCOL.md`: whether the five registered FMD risk
candidate families must all execute successfully for FMD-07B to complete, even
when a family was formally declared `BLOCKED` before any FMD-07B result existed.

This amendment supersedes only:

- Section 8 of `FMD07B_MODEL_DEVELOPMENT_PROTOCOL.md`; and
- the phrases in Section 12 that require every `FMD-EXP-01..05` family to be
  executable.

All other FMD-07B input, data-role, selection, artifact, testing,
reproducibility, firewall, completion-token, and next-checkpoint requirements
remain unchanged.

## 2. Evidence used

This decision is frozen from repository text and structural software contracts,
not candidate results:

1. `FMD_EVALUATION_PROTOCOL.md` Section 6 says FMD-07 candidate families must
   be compared against, at minimum, the naive/statistical, spatial/distance,
   PISTES, ML, and hybrid families.
2. `FMD_EXPERIMENT_REGISTRY.json` registers `FMD-EXP-01..05` and describes the
   downstream model as the single model selected from that universe using
   FIT_DEVELOPMENT evidence only. It does not define how a later formal
   `BLOCKED` state affects selection eligibility.
3. `FMD07_PRE_MODEL_PROTOCOL_AMENDMENT.md`, written before any FMD predictive
   score or model fit, makes a later and more specific feasibility finding:
   PISTES is `BLOCKED`, hybrid is `BLOCKED_BY_PISTES`, and forcing either family
   would pretend a scientifically undefined pathway computes something it
   cannot.
4. The machine-readable
   `fmd07_pre_model_protocol_amendment.json` and amended
   `fmd07_development_protocol.json` preserve those exact states and their
   reasons.
5. `services/model_development/development_run_7b.py` and
   `services/model_development/evaluation_protocol_7b.py` establish a repository
   distinction between the full registered candidate universe and the
   `PRIMARY_SELECTION_ELIGIBLE` subset. Ineligible candidates remain audited and
   are not silently treated as losing candidates; selection becomes blocked
   when no candidate is eligible.
6. `FMD07B_MODEL_DEVELOPMENT_PROTOCOL.md` statically establishes that the
   naive, spatial, and ML FMD execution paths are not yet implemented and that
   the ML dependency policy remains unresolved.

The phrase “at minimum” predates the formal PISTES/hybrid block and does not
state whether scientifically impossible, pre-result-blocked candidates must
prevent completion forever. The repository therefore contains an ambiguity,
not evidence that either blocked family may be fabricated or silently omitted.
This amendment resolves it conservatively before any result exists.

## 3. Registered candidate universe

The registered candidate universe remains unchanged:

| Experiment | Family | Frozen registry/protocol state |
|---|---|---|
| `FMD-EXP-01` | naive/statistical baseline | `FULLY_SPECIFIED` |
| `FMD-EXP-02` | spatial/distance baseline | `FMD07A_R1_FROZEN` |
| `FMD-EXP-03` | PISTES/hazard | `BLOCKED` |
| `FMD-EXP-04` | ML | `FMD07A_R1_FROZEN_PENDING_DEPENDENCY` |
| `FMD-EXP-05` | hybrid | `BLOCKED_BY_PISTES` |

No family is removed from the experiment registry. Registration, executable
eligibility, selection participation, and winning-model eligibility are
separate fields in every future FMD-07B audit.

## 4. Executable-candidate eligibility rule

A registered candidate family is `FMD07B_EXECUTABLE_SELECTION_ELIGIBLE` only
when all of the following are true before the first candidate fit or metric:

1. its candidate definition and complete finite candidate grid are frozen;
2. it is not marked `BLOCKED`, `BLOCKED_BY_PISTES`, or
   `FROZEN_PENDING_DEPENDENCY` by a governing pre-result protocol;
3. a complete FMD implementation, input adapter, and runner exist;
4. all direct implementation dependencies have a repository-resolved
   compatibility policy and are explicitly declared;
5. the implementation can enforce FIT_DEVELOPMENT-only folds, training-fold-
   only preprocessing, the D1-D7 target semantics, and all three evaluation
   firewalls;
6. its focused pre-execution structural gates pass without fitting a model or
   calculating candidate performance.

A family that fails any condition is not assigned a placeholder score, default
rank, synthetic loss, or proxy implementation. Its registry identity, frozen
state, exact exclusion reason, and absence of candidate metrics must remain in
`fmd07b_candidate_eligibility.json` and `fmd07b_manifest.json`.

## 5. Blocked-candidate handling

This amendment freezes option B, under a narrow pre-result exception:

> A candidate already marked `BLOCKED` or `BLOCKED_BY_PISTES` by the frozen
> pre-model protocol may remain formally blocked and be excluded from the
> executable comparison and winner-selection set, provided the registered
> candidate remains visible and its exact blocker and non-participation are
> reported transparently.

This exception applies now only to:

- `FMD-EXP-03` PISTES; and
- `FMD-EXP-05` hybrid.

Their exclusion is based on protocol/scientific infeasibility recorded before
any FMD-07B result, not speed or observed performance. Neither is required for
FMD-07B completion while its exact frozen blocker remains active. Neither may
be declared inferior, because neither produces a candidate metric.

If a separately scoped, pre-result protocol later resolves the PISTES blocker
before FMD-07B execution begins, PISTES and any consequently resolved hybrid
become subject to the same executable-eligibility gate and must be added to the
comparison set through another explicit pre-execution amendment. The selection
set must never be expanded or reduced after any candidate result is generated.

## 6. Missing implementation is not an exclusion rule

Missing implementation alone is not an acceptable candidate-exclusion reason.
It is a software readiness blocker that must be resolved for every otherwise
required family.

Accordingly:

- the missing FMD naive/statistical runner does not excuse `FMD-EXP-01`;
- the missing FMD spatial composition/runner does not excuse `FMD-EXP-02`;
- the missing FMD ML estimator runner does not excuse `FMD-EXP-04`; and
- an unresolved dependency does not convert an otherwise frozen candidate into
  a scientifically blocked candidate.

This rule prevents implementation effort, convenience, or package availability
from changing the registered comparison after the fact.

## 7. Required minimum executable comparison set

The minimum executable comparison set is exactly:

```text
FMD-EXP-01
FMD-EXP-02
FMD-EXP-04
```

Participation means:

- the fully specified naive/statistical comparator is implemented and included;
- the complete frozen FMD spatial/distance candidate grid is implemented and
  included, never the fitted LSD configuration; and
- all three frozen ML algorithm families and their complete frozen
  hyperparameter grids are implemented and included, without selecting a
  convenient subset before comparison.

FMD-07B cannot execute or complete if any member of this minimum set is absent,
dependency-blocked, runner-blocked, silently dropped, or represented by a
different family's implementation.

The minimum set expands to include PISTES and/or hybrid only if their current
formal blockers are resolved under a separate amendment before any FMD-07B
candidate result exists.

## 8. Dependency policy

The ML family is required in the minimum executable comparison set. Its current
dependency state remains:

```text
SCIKIT_LEARN_VERSION_UNRESOLVED
```

FMD-EXP-04 may not be excluded because `scikit-learn` is undeclared. Before
FMD-07B becomes executable, a separately authorized packaging decision must:

1. establish repository compatibility evidence;
2. select an explicit `scikit-learn` version without using candidate
   performance;
3. declare that version in the applicable dependency manifest; and
4. make the focused dependency/readiness gates pass.

This amendment does not choose a version, install a dependency, or implement an
estimator.

## 9. Completion and no-go rule

PISTES and hybrid do not block FMD-07B completion while their pre-existing exact
blockers remain active and are transparently recorded. The checkpoint may
become executable only when `FMD-EXP-01`, `FMD-EXP-02`, and `FMD-EXP-04` all
satisfy `FMD07B_EXECUTABLE_SELECTION_ELIGIBLE`.

The exact current blocker token is:

```text
FMD-07B_BLOCKED_MINIMUM_EXECUTABLE_COMPARISON_SET_NOT_READY
```

This token supersedes
`FMD-07B_BLOCKED_REQUIRED_CANDIDATE_SET_NOT_EXECUTABLE` as the active
feasibility token. The earlier token remains part of the audit trail; this
amendment narrows “required candidate set” to the pre-result executable set
defined in Section 7.

If the minimum set is not ready, the decision is `NO-GO` and no candidate may
be trained or scored. If the minimum set becomes ready, the pre-execution gate
may emit:

```text
FMD-07B_MINIMUM_EXECUTABLE_COMPARISON_SET_READY
```

That readiness token permits the separately implemented FMD-07B workflow to
begin; it is not the checkpoint completion token. The unchanged completion
token remains:

```text
FMD-07B_COMPLETE_READY_FOR_FMD-08
```

It may be emitted only after the existing FMD-07B execution, artifact,
reproducibility, focused-test, affected-regression, full-backend-suite, and
firewall gates pass.

## 10. Next action

Without training or evaluating a model:

1. resolve and declare the `scikit-learn` compatibility/version policy;
2. implement the FMD-EXP-01 naive/statistical runner;
3. implement the FMD-EXP-02 FMD-specific spatial composition/runner using the
   frozen FMD registry and reusable disease-independent pieces;
4. implement the FMD-EXP-04 estimator/preprocessing runner for the complete
   frozen ML grid;
5. create the already-frozen focused test
   `test_fmd07b_model_development.py`; and
6. perform a structural pre-execution readiness audit and stop before training
   unless `FMD-07B_MINIMUM_EXECUTABLE_COMPARISON_SET_READY` is valid.

FMD-08 remains the next scientific checkpoint after a valid FMD-07B completion.
