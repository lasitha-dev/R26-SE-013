"""FMD-07B minimum executable candidate-set structural layer.

This module composes only the three candidate families frozen as the minimum
executable comparison set by
``FMD07B_PREEXECUTION_FEASIBILITY_PROTOCOL_AMENDMENT.md``:

* FMD-EXP-01 naive/statistical country-history baseline;
* FMD-EXP-02 spatial/distance baseline; and
* FMD-EXP-04 frozen tabular ML candidates.

Importing or constructing these objects does not fit a model, score an origin,
calculate a metric, read a dataset, or inspect held-out/Sri Lanka data.  Real
execution remains a later, separately gated FMD-07B action.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from itertools import product
from typing import Mapping, Sequence

import sklearn
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .fmd_model_development_r1 import (
    build_hybrid_candidate_status,
    build_ml_candidate_registry,
    build_pistes_hazard_candidate_status,
    build_spatial_baseline_kernel_scale_registry,
)
from .fmd_calibration import FMD_MODEL_FITTING_CUTOFF
from .forecast_origin import ForecastOrigin
from .model_fitting_exposure import CalendarYearFold, assert_fit_development_only
from .split_embargo import AT_OR_AFTER_BOUNDARY, BEFORE_BOUNDARY, assess_embargo, assess_validation_block
from .model_development.baseline_registry import BASELINE_CANDIDATES, KERNEL_CANDIDATE_FAMILIES
from .model_development.baseline_scoring import SCORED, score_origin_all_candidates
from .model_development.candidate_registry_7b import BaselineCandidateSpec

CHECKPOINT = "FMD-07B"
RANDOM_SEED = 42
REQUIRED_SKLEARN_VERSION = "1.8.0"
DEPENDENCY_REQUIREMENT = f"scikit-learn=={REQUIRED_SKLEARN_VERSION}"
DEPENDENCY_STATUS = "SCIKIT_LEARN_1_8_0_OBSERVED_COMPATIBLE_AND_DECLARED"

MINIMUM_EXECUTABLE_EXPERIMENT_IDS = ("FMD-EXP-01", "FMD-EXP-02", "FMD-EXP-04")
REGISTERED_EXPERIMENT_IDS = ("FMD-EXP-01", "FMD-EXP-02", "FMD-EXP-03", "FMD-EXP-04", "FMD-EXP-05")

FMD07B_EXECUTABLE_SELECTION_ELIGIBLE = "FMD07B_EXECUTABLE_SELECTION_ELIGIBLE"
FMD07B_BLOCKED = "FMD07B_BLOCKED"
FMD07B_MINIMUM_EXECUTABLE_COMPARISON_SET_READY = "FMD-07B_MINIMUM_EXECUTABLE_COMPARISON_SET_READY"
FMD07B_INTERSECTION_OF_STRUCTURALLY_SCOREABLE_ORIGINS_V1 = (
    "FMD07B_INTERSECTION_OF_STRUCTURALLY_SCOREABLE_ORIGINS_V1"
)
COMMON_SUPPORT_RULE = FMD07B_INTERSECTION_OF_STRUCTURALLY_SCOREABLE_ORIGINS_V1

# Structural-readiness evidence. These values can change only in a real
# execution module, never as a side effect of importing/building this layer.
HELD_OUT_USED = False
SRI_LANKA_USED = False
REAL_TRAINING_RUN = False
DEVELOPMENT_METRICS_GENERATED = False


class CommonSupportFailClosedError(RuntimeError):
    """A frozen-support prediction is absent or structurally unavailable."""


def _sorted_unique_strings(label: str, values: Sequence[str]) -> tuple[str, ...]:
    materialized = tuple(values)
    if any(not isinstance(value, str) or not value for value in materialized):
        raise ValueError(f"{label} must contain only non-empty strings")
    if len(materialized) != len(set(materialized)):
        raise ValueError(f"{label} contains duplicate values")
    return tuple(sorted(materialized))


def compute_common_support_sha256(origin_ids: Sequence[str]) -> str:
    """Hash the canonical JSON array for a set of frozen support IDs."""
    canonical_ids = _sorted_unique_strings("common support origin IDs", origin_ids)
    canonical = json.dumps(list(canonical_ids), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FrozenCommonSupport:
    """Immutable per-fold comparison support frozen before metric calculation."""

    fold_id: str
    validation_origin_ids: tuple[str, ...]
    candidate_keys: tuple[tuple[str, str], ...]
    common_support_origin_ids: tuple[str, ...]
    common_support_sha256: str
    common_support_rule: str = COMMON_SUPPORT_RULE

    def __post_init__(self) -> None:
        if not isinstance(self.fold_id, str) or not self.fold_id:
            raise ValueError("fold_id must be a non-empty string")
        if self.validation_origin_ids != _sorted_unique_strings(
            "validation origin IDs", self.validation_origin_ids
        ):
            raise ValueError("validation_origin_ids must be in deterministic sorted order")
        if self.common_support_origin_ids != _sorted_unique_strings(
            "common support origin IDs", self.common_support_origin_ids
        ):
            raise ValueError("common_support_origin_ids must be in deterministic sorted order")
        if not set(self.common_support_origin_ids).issubset(self.validation_origin_ids):
            raise ValueError("common support must be a subset of validation origins")
        if self.candidate_keys != tuple(sorted(self.candidate_keys)):
            raise ValueError("candidate_keys must be in deterministic sorted order")
        if len(self.candidate_keys) != len(set(self.candidate_keys)):
            raise ValueError("candidate_keys contains duplicate values")
        if {experiment_id for experiment_id, _candidate_id in self.candidate_keys} != set(
            MINIMUM_EXECUTABLE_EXPERIMENT_IDS
        ):
            raise ValueError("candidate_keys must cover exactly FMD-EXP-01, FMD-EXP-02, and FMD-EXP-04")
        if self.common_support_rule != COMMON_SUPPORT_RULE:
            raise ValueError(f"common_support_rule must be {COMMON_SUPPORT_RULE}")
        expected_sha256 = compute_common_support_sha256(self.common_support_origin_ids)
        if self.common_support_sha256 != expected_sha256:
            raise ValueError("common_support_sha256 does not match the frozen origin IDs")

    def as_dict(self) -> dict:
        support = set(self.common_support_origin_ids)
        excluded = [origin_id for origin_id in self.validation_origin_ids if origin_id not in support]
        return {
            "fold_id": self.fold_id,
            "common_support_rule": self.common_support_rule,
            "full_validation_origin_count": len(self.validation_origin_ids),
            "common_support_count": len(self.common_support_origin_ids),
            "excluded_count": len(excluded),
            "common_support_origin_ids": list(self.common_support_origin_ids),
            "common_support_sha256": self.common_support_sha256,
            "candidate_keys": [
                {"experiment_id": experiment_id, "candidate_id": candidate_id}
                for experiment_id, candidate_id in self.candidate_keys
            ],
        }


def build_frozen_common_support(
    *,
    fold_id: str,
    validation_origin_ids: Sequence[str],
    candidate_ids_by_experiment: Mapping[str, Sequence[str]],
    structural_availability_rows: Sequence[Mapping[str, object]],
) -> FrozenCommonSupport:
    """Freeze the intersection of structurally scoreable validation origins.

    Only ``experiment_id``, ``candidate_id``, ``forecast_origin_id``, and the
    boolean ``structurally_scoreable`` field are read from availability rows.
    Labels, outcomes, prediction values, and all other fields are deliberately
    outside the construction rule.
    """
    validation_ids = _sorted_unique_strings("validation origin IDs", validation_origin_ids)
    validation_set = set(validation_ids)

    required_experiments = set(MINIMUM_EXECUTABLE_EXPERIMENT_IDS)
    provided_experiments = set(candidate_ids_by_experiment)
    if provided_experiments != required_experiments:
        missing = sorted(required_experiments - provided_experiments)
        unexpected = sorted(provided_experiments - required_experiments)
        raise ValueError(
            "candidate_ids_by_experiment must contain exactly the minimum executable set; "
            f"missing={missing}, unexpected={unexpected}"
        )

    candidate_keys: list[tuple[str, str]] = []
    for experiment_id in MINIMUM_EXECUTABLE_EXPERIMENT_IDS:
        raw_candidate_ids = candidate_ids_by_experiment[experiment_id]
        if isinstance(raw_candidate_ids, str):
            raise ValueError(f"candidate IDs for {experiment_id} must be a sequence, not a string")
        candidate_ids = _sorted_unique_strings(f"candidate IDs for {experiment_id}", raw_candidate_ids)
        if not candidate_ids:
            raise ValueError(f"candidate IDs for {experiment_id} must not be empty")
        candidate_keys.extend((experiment_id, candidate_id) for candidate_id in candidate_ids)
    frozen_candidate_keys = tuple(sorted(candidate_keys))
    expected_candidate_keys = set(frozen_candidate_keys)

    scoreable_by_candidate = {candidate_key: set() for candidate_key in frozen_candidate_keys}
    observed_rows: set[tuple[str, str, str]] = set()
    for index, row in enumerate(structural_availability_rows):
        try:
            experiment_id = row["experiment_id"]
            candidate_id = row["candidate_id"]
            origin_id = row["forecast_origin_id"]
            structurally_scoreable = row["structurally_scoreable"]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"structural availability row {index} is missing a required field") from exc
        if not all(isinstance(value, str) and value for value in (experiment_id, candidate_id, origin_id)):
            raise ValueError(f"structural availability row {index} has an invalid identity")
        candidate_key = (experiment_id, candidate_id)
        if candidate_key not in expected_candidate_keys:
            raise ValueError(f"structural availability row {index} has an unexpected candidate {candidate_key!r}")
        if origin_id not in validation_set:
            raise ValueError(f"structural availability row {index} has a non-validation origin {origin_id!r}")
        if not isinstance(structurally_scoreable, bool):
            raise ValueError(f"structural availability row {index} must use a boolean structurally_scoreable value")
        row_identity = (experiment_id, candidate_id, origin_id)
        if row_identity in observed_rows:
            raise ValueError(f"duplicate structural availability row for {row_identity!r}")
        observed_rows.add(row_identity)
        if structurally_scoreable:
            scoreable_by_candidate[candidate_key].add(origin_id)

    common_support = set(validation_ids)
    for candidate_key in frozen_candidate_keys:
        common_support.intersection_update(scoreable_by_candidate[candidate_key])
    common_support_origin_ids = tuple(sorted(common_support))
    return FrozenCommonSupport(
        fold_id=fold_id,
        validation_origin_ids=validation_ids,
        candidate_keys=frozen_candidate_keys,
        common_support_origin_ids=common_support_origin_ids,
        common_support_sha256=compute_common_support_sha256(common_support_origin_ids),
    )


def apply_frozen_common_support(
    frozen_support: FrozenCommonSupport,
    *,
    prediction_rows: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Validate prediction availability without changing frozen support.

    Rows outside common support remain auditable but cannot alter the support.
    Every expected candidate must have a ``SCORED`` row for every origin inside
    it; a missing or unavailable row raises before any metric can be calculated.
    """
    expected_candidate_keys = set(frozen_support.candidate_keys)
    validation_ids = set(frozen_support.validation_origin_ids)
    statuses: dict[tuple[str, str, str], object] = {}
    for index, row in enumerate(prediction_rows):
        try:
            experiment_id = row["experiment_id"]
            candidate_id = row["candidate_id"]
            origin_id = row["forecast_origin_id"]
            status = row["status"]
        except (KeyError, TypeError) as exc:
            raise CommonSupportFailClosedError(
                f"prediction row {index} is missing a required availability field"
            ) from exc
        candidate_key = (experiment_id, candidate_id)
        if candidate_key not in expected_candidate_keys:
            raise CommonSupportFailClosedError(f"unexpected prediction candidate {candidate_key!r}")
        if origin_id not in validation_ids:
            raise CommonSupportFailClosedError(f"prediction row has a non-validation origin {origin_id!r}")
        row_identity = (experiment_id, candidate_id, origin_id)
        if row_identity in statuses:
            raise CommonSupportFailClosedError(f"duplicate prediction row for {row_identity!r}")
        statuses[row_identity] = status

    violations: list[str] = []
    for experiment_id, candidate_id in frozen_support.candidate_keys:
        for origin_id in frozen_support.common_support_origin_ids:
            status = statuses.get((experiment_id, candidate_id, origin_id))
            if status != SCORED:
                violations.append(
                    f"{experiment_id}/{candidate_id}/{origin_id}:"
                    f"{status if status is not None else 'MISSING_ROW'}"
                )
    if violations:
        raise CommonSupportFailClosedError(
            "frozen common support cannot shrink; unavailable prediction(s) inside support: "
            + ", ".join(violations)
        )

    applied = {experiment_id: {} for experiment_id in MINIMUM_EXECUTABLE_EXPERIMENT_IDS}
    for experiment_id, candidate_id in frozen_support.candidate_keys:
        applied[experiment_id][candidate_id] = frozen_support.common_support_origin_ids
    return applied


def assert_compatible_sklearn_runtime() -> None:
    """Fail closed if the runtime differs from the observed frozen version."""
    if sklearn.__version__ != REQUIRED_SKLEARN_VERSION:
        raise RuntimeError(
            f"FMD-07B requires {DEPENDENCY_REQUIREMENT}; observed scikit-learn=={sklearn.__version__}"
        )


def _canonical_digest(value: object, *, length: int = 16) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:length]


def _require_unique(label: str, values: Sequence[str]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} contains duplicate forecast_origin_id values")


@dataclass(frozen=True)
class Fmd07bFoldInput:
    """Validated, FIT_DEVELOPMENT-only chronological fold identity."""

    fold_id: str
    training_origin_ids: tuple[str, ...]
    validation_origin_ids: tuple[str, ...]
    purged_origin_ids: tuple[str, ...]
    firewall_status: str = "FIT_DEVELOPMENT_ONLY"


def validate_fmd07b_fold_input(
    origins: Sequence[ForecastOrigin], fold: CalendarYearFold
) -> Fmd07bFoldInput:
    """Validate role, membership, chronology, and the frozen seven-day purge.

    The caller supplies the development origin universe and one already-frozen
    calendar-year fold. Mixed-role input is rejected in full by the existing
    repository firewall before any fold membership is accepted.
    """
    origin_list = list(origins)
    assert_fit_development_only(
        origin_list, cutoff=FMD_MODEL_FITTING_CUTOFF, caller="FMD-07B structural fold validation"
    )

    origin_by_id: dict[str, ForecastOrigin] = {}
    for origin in origin_list:
        if origin.forecast_origin_id in origin_by_id:
            raise ValueError(f"duplicate forecast_origin_id {origin.forecast_origin_id!r}")
        origin_by_id[origin.forecast_origin_id] = origin

    partitions = {
        "training": tuple(fold.training_origin_ids),
        "validation": tuple(fold.validation_origin_ids),
        "purged": tuple(fold.purged_origin_ids),
    }
    for label, ids in partitions.items():
        _require_unique(label, ids)
        if list(ids) != sorted(ids):
            raise ValueError(f"{label} forecast_origin_id values must use deterministic sorted order")
        missing = sorted(set(ids) - set(origin_by_id))
        if missing:
            raise ValueError(f"{label} references unknown forecast origins: {missing}")

    training_ids = set(partitions["training"])
    validation_ids = set(partitions["validation"])
    purged_ids = set(partitions["purged"])
    if training_ids & validation_ids or training_ids & purged_ids or validation_ids & purged_ids:
        raise ValueError("training, validation, and purged fold memberships must be pairwise disjoint")

    training_assessments = assess_embargo(
        [origin_by_id[oid] for oid in partitions["training"]],
        boundary=fold.validation_date_range_start,
    )
    if any(a.partition != BEFORE_BOUNDARY or a.embargoed for a in training_assessments):
        raise ValueError("training fold violates PURGED_7_DAY_HORIZON_POLICY")

    purged_assessments = assess_embargo(
        [origin_by_id[oid] for oid in partitions["purged"]],
        boundary=fold.validation_date_range_start,
    )
    if any(a.partition != BEFORE_BOUNDARY or not a.embargoed for a in purged_assessments):
        raise ValueError("purged fold membership does not match PURGED_7_DAY_HORIZON_POLICY")

    validation_origins = [origin_by_id[oid] for oid in partitions["validation"]]
    validation_assessments = assess_validation_block(
        validation_origins,
        block_start=fold.validation_date_range_start,
        block_end=fold.validation_date_range_end,
    )
    if len(validation_assessments) != len(validation_origins) or any(not a.complete for a in validation_assessments):
        raise ValueError("validation fold does not have complete D1-D7 horizon coverage")
    if any(
        assessment.partition != AT_OR_AFTER_BOUNDARY
        for assessment in assess_embargo(validation_origins, boundary=fold.validation_date_range_start)
    ):
        raise ValueError("validation origin precedes its chronological fold boundary")

    return Fmd07bFoldInput(
        fold_id=fold.fold_id,
        training_origin_ids=partitions["training"],
        validation_origin_ids=partitions["validation"],
        purged_origin_ids=partitions["purged"],
    )


@dataclass(frozen=True)
class NaiveStatisticalCandidateSpec:
    candidate_id: str = "FMD07B:FMD-EXP-01:COUNTRY_HISTORICAL_OCCURRENCE_RATE"
    experiment_id: str = "FMD-EXP-01"
    registry_status: str = "FULLY_SPECIFIED"
    output_semantics: str = "COUNTRY_HISTORICAL_OCCURRENCE_RATE"

    def as_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "experiment_id": self.experiment_id,
            "registry_status": self.registry_status,
            "output_semantics": self.output_semantics,
        }


@dataclass(frozen=True)
class FittedNaiveStatisticalModel:
    """Training-fold-only country occurrence rates; no global fallback."""

    candidate_id: str
    country_rates: tuple[tuple[str, float], ...]
    training_origin_ids: tuple[str, ...]

    def rate_for_country(self, country: str) -> float:
        rates = dict(self.country_rates)
        if country not in rates:
            raise ValueError(f"no training-fold country history for {country!r}")
        return rates[country]


@dataclass(frozen=True)
class NaiveStatisticalRunner:
    candidate: NaiveStatisticalCandidateSpec = NaiveStatisticalCandidateSpec()

    def fit_training_fold(
        self,
        fold: Fmd07bFoldInput,
        *,
        countries_by_origin: Mapping[str, str],
        labels_by_origin: Mapping[str, int | bool],
    ) -> FittedNaiveStatisticalModel:
        if fold.firewall_status != "FIT_DEVELOPMENT_ONLY":
            raise ValueError("naive runner requires a validated FIT_DEVELOPMENT-only fold")
        country_labels: dict[str, list[int]] = defaultdict(list)
        for origin_id in fold.training_origin_ids:
            if origin_id not in countries_by_origin or origin_id not in labels_by_origin:
                raise ValueError(f"missing country/label for training origin {origin_id!r}")
            label = labels_by_origin[origin_id]
            if label not in (0, 1, False, True):
                raise ValueError(f"risk label must be binary for {origin_id!r}")
            country_labels[countries_by_origin[origin_id]].append(int(label))
        if not country_labels:
            raise ValueError("naive runner cannot fit an empty training fold")
        rates = tuple(
            (country, sum(values) / len(values))
            for country, values in sorted(country_labels.items())
        )
        return FittedNaiveStatisticalModel(
            candidate_id=self.candidate.candidate_id,
            country_rates=rates,
            training_origin_ids=fold.training_origin_ids,
        )


def build_naive_statistical_runner() -> NaiveStatisticalRunner:
    return NaiveStatisticalRunner()


def _fmd_spatial_candidate_id(
    *, baseline_family: str, kernel_family: str, kernel_scale_km: float, host_factor_candidate: str | None
) -> str:
    payload = {
        "checkpoint": CHECKPOINT,
        "experiment_id": "FMD-EXP-02",
        "baseline_family": baseline_family,
        "kernel_family": kernel_family,
        "kernel_scale_km": kernel_scale_km,
        "host_factor_candidate": host_factor_candidate,
        "registry_status": "FMD07A_R1_FROZEN",
    }
    digest = _canonical_digest(payload)
    return (
        f"FMD07B:SPATIAL:{baseline_family}:{kernel_family}:{kernel_scale_km:g}KM:"
        f"{host_factor_candidate or 'NONE'}:{digest}"
    )


def build_fmd_spatial_candidate_specs() -> tuple[BaselineCandidateSpec, ...]:
    """Compose the frozen FMD grid using generic candidate/scoring types.

    This deliberately does not call the earlier Checkpoint 7B candidate-grid
    builder because its kernel scales belong to the earlier disease context.
    """
    registry = build_spatial_baseline_kernel_scale_registry()
    if registry["status"] != "FMD07A_R1_FROZEN":
        raise RuntimeError("FMD spatial candidate registry is not frozen")

    candidates: list[BaselineCandidateSpec] = []
    for baseline in BASELINE_CANDIDATES:
        for kernel_family in KERNEL_CANDIDATE_FAMILIES:
            for scale_km in registry["candidate_kernel_scale_km"]:
                candidates.append(
                    BaselineCandidateSpec(
                        candidate_id=_fmd_spatial_candidate_id(
                            baseline_family=baseline.family,
                            kernel_family=kernel_family,
                            kernel_scale_km=scale_km,
                            host_factor_candidate=baseline.host_factor_candidate,
                        ),
                        baseline_family=baseline.family,
                        host_factor_candidate=baseline.host_factor_candidate,
                        kernel_family=kernel_family,
                        kernel_scale_km=scale_km,
                        source_weighting=baseline.source_weighting,
                        output_label=baseline.output_label,
                    )
                )
    return tuple(sorted(candidates, key=lambda candidate: candidate.candidate_id))


@dataclass(frozen=True)
class SpatialDistanceRunner:
    candidates: tuple[BaselineCandidateSpec, ...]
    experiment_id: str = "FMD-EXP-02"
    registry_status: str = "FMD07A_R1_FROZEN"

    def score_validation_origin(
        self,
        fold: Fmd07bFoldInput,
        *,
        forecast_origin_id: str,
        grid_cells: list[dict],
        sources: list,
        reference_profile,
        transform_config=None,
        unsafe_component_count: int = 0,
    ) -> dict:
        """Delegate unchanged spatial math for one validated development origin.

        The fold-safe reference and spatial fixture/input remain explicit caller
        inputs. This method performs no selection or metric calculation.
        """
        if fold.firewall_status != "FIT_DEVELOPMENT_ONLY":
            raise ValueError("spatial runner requires a validated FIT_DEVELOPMENT-only fold")
        if forecast_origin_id not in fold.validation_origin_ids:
            raise ValueError("spatial scoring is restricted to this fold's validation origins")
        if (
            unsafe_component_count == 0
            and reference_profile is None
            and any(c.host_factor_candidate is not None for c in self.candidates)
        ):
            raise ValueError("complete FMD spatial grid requires a training-fold-safe host reference profile")
        return score_origin_all_candidates(
            grid_cells=grid_cells,
            sources=sources,
            candidates=self.candidates,
            reference_profile=reference_profile,
            transform_config=transform_config,
            unsafe_component_count=unsafe_component_count,
        )


def build_spatial_distance_runner() -> SpatialDistanceRunner:
    return SpatialDistanceRunner(candidates=build_fmd_spatial_candidate_specs())


@dataclass(frozen=True)
class MlCandidateSpec:
    candidate_id: str
    algorithm_family: str
    hyperparameters: tuple[tuple[str, object], ...]
    preprocessing: tuple[str, ...]
    random_seed: int = RANDOM_SEED

    def hyperparameter_dict(self) -> dict:
        return dict(self.hyperparameters)

    def as_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "algorithm_family": self.algorithm_family,
            "hyperparameters": self.hyperparameter_dict(),
            "preprocessing": list(self.preprocessing),
            "random_seed": self.random_seed,
        }


_ML_PREPROCESSING = {
    "LOGISTIC_REGRESSION": ("MEDIAN_IMPUTATION", "STANDARDIZATION"),
    "RANDOM_FOREST": ("MEDIAN_IMPUTATION",),
    "GRADIENT_BOOSTED_TREES": ("NATIVE_MISSING_VALUES",),
}


def _expand_hyperparameters(values: Mapping[str, object]) -> list[dict]:
    varying_keys = [key for key, value in values.items() if isinstance(value, list)]
    fixed = {key: value for key, value in values.items() if key not in varying_keys}
    if not varying_keys:
        return [fixed]
    return [
        {**fixed, **dict(zip(varying_keys, combination, strict=True))}
        for combination in product(*(values[key] for key in varying_keys))
    ]


def _ml_candidate_id(algorithm_family: str, hyperparameters: Mapping[str, object]) -> str:
    payload = {
        "checkpoint": CHECKPOINT,
        "experiment_id": "FMD-EXP-04",
        "algorithm_family": algorithm_family,
        "hyperparameters": dict(hyperparameters),
        "preprocessing": list(_ML_PREPROCESSING[algorithm_family]),
        "random_seed": RANDOM_SEED,
    }
    return f"FMD07B:ML:{algorithm_family}:{_canonical_digest(payload)}"


def build_ml_candidate_specs() -> tuple[MlCandidateSpec, ...]:
    assert_compatible_sklearn_runtime()
    registry = build_ml_candidate_registry()
    if registry["status"] != "FMD07A_R1_FROZEN_PENDING_DEPENDENCY":
        raise RuntimeError("unexpected FMD ML registry status")

    candidates: list[MlCandidateSpec] = []
    for family_entry in registry["candidates"]:
        algorithm_family = family_entry["algorithm_family"]
        for hyperparameters in _expand_hyperparameters(family_entry["hyperparameter_candidates"]):
            candidates.append(
                MlCandidateSpec(
                    candidate_id=_ml_candidate_id(algorithm_family, hyperparameters),
                    algorithm_family=algorithm_family,
                    hyperparameters=tuple(sorted(hyperparameters.items())),
                    preprocessing=_ML_PREPROCESSING[algorithm_family],
                )
            )
    if len(candidates) != registry["total_hyperparameter_candidate_count"]:
        raise RuntimeError("expanded ML candidate count differs from frozen registry")
    return tuple(sorted(candidates, key=lambda candidate: candidate.candidate_id))


def build_ml_pipeline(candidate: MlCandidateSpec) -> Pipeline:
    """Construct a new unfitted, training-fold-local sklearn pipeline."""
    assert_compatible_sklearn_runtime()
    parameters = candidate.hyperparameter_dict()
    if candidate.algorithm_family == "LOGISTIC_REGRESSION":
        estimator = LogisticRegression(random_state=RANDOM_SEED, **parameters)
        steps = [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("estimator", estimator),
        ]
    elif candidate.algorithm_family == "RANDOM_FOREST":
        estimator = RandomForestClassifier(random_state=RANDOM_SEED, **parameters)
        steps = [
            ("imputer", SimpleImputer(strategy="median")),
            ("estimator", estimator),
        ]
    elif candidate.algorithm_family == "GRADIENT_BOOSTED_TREES":
        estimator = HistGradientBoostingClassifier(random_state=RANDOM_SEED, **parameters)
        steps = [("estimator", estimator)]
    else:
        raise ValueError(f"unknown frozen ML algorithm family {candidate.algorithm_family!r}")
    return Pipeline(steps=steps)


@dataclass(frozen=True)
class MlEstimatorRunner:
    candidates: tuple[MlCandidateSpec, ...]
    experiment_id: str = "FMD-EXP-04"
    registry_status: str = "FMD07A_R1_FROZEN_PENDING_DEPENDENCY"
    dependency_status: str = DEPENDENCY_STATUS

    def build_unfitted_pipeline(self, candidate_id: str) -> Pipeline:
        matches = [candidate for candidate in self.candidates if candidate.candidate_id == candidate_id]
        if len(matches) != 1:
            raise ValueError(f"unknown ML candidate_id {candidate_id!r}")
        return build_ml_pipeline(matches[0])

    def fit_training_fold(
        self,
        candidate_id: str,
        fold: Fmd07bFoldInput,
        *,
        features_by_origin: Mapping[str, Sequence[float | None]],
        labels_by_origin: Mapping[str, int | bool],
    ) -> Pipeline:
        """Fit only explicitly validated training-fold rows; calculate no metric."""
        if fold.firewall_status != "FIT_DEVELOPMENT_ONLY":
            raise ValueError("ML runner requires a validated FIT_DEVELOPMENT-only fold")
        missing = [
            origin_id
            for origin_id in fold.training_origin_ids
            if origin_id not in features_by_origin or origin_id not in labels_by_origin
        ]
        if missing:
            raise ValueError(f"missing ML training-fold inputs for {missing}")
        labels = [labels_by_origin[origin_id] for origin_id in fold.training_origin_ids]
        if any(label not in (0, 1, False, True) for label in labels):
            raise ValueError("ML risk labels must be binary")
        pipeline = clone(self.build_unfitted_pipeline(candidate_id))
        pipeline.fit(
            [features_by_origin[origin_id] for origin_id in fold.training_origin_ids],
            [int(label) for label in labels],
        )
        return pipeline


def build_ml_estimator_runner() -> MlEstimatorRunner:
    return MlEstimatorRunner(candidates=build_ml_candidate_specs())


def registered_candidate_eligibility() -> dict[str, dict]:
    pistes = build_pistes_hazard_candidate_status()
    hybrid = build_hybrid_candidate_status(pistes)
    return {
        "FMD-EXP-01": {
            "registry_status": "FULLY_SPECIFIED",
            "eligibility": FMD07B_EXECUTABLE_SELECTION_ELIGIBLE,
        },
        "FMD-EXP-02": {
            "registry_status": "FMD07A_R1_FROZEN",
            "eligibility": FMD07B_EXECUTABLE_SELECTION_ELIGIBLE,
        },
        "FMD-EXP-03": {
            "registry_status": pistes["status"],
            "eligibility": FMD07B_BLOCKED,
            "runner": None,
        },
        "FMD-EXP-04": {
            "registry_status": "FMD07A_R1_FROZEN_PENDING_DEPENDENCY",
            "dependency_status": DEPENDENCY_STATUS,
            "eligibility": FMD07B_EXECUTABLE_SELECTION_ELIGIBLE,
        },
        "FMD-EXP-05": {
            "registry_status": hybrid["status"],
            "eligibility": FMD07B_BLOCKED,
            "runner": None,
        },
    }


def build_minimum_candidate_runners() -> dict[str, object]:
    assert_compatible_sklearn_runtime()
    return {
        "FMD-EXP-01": build_naive_statistical_runner(),
        "FMD-EXP-02": build_spatial_distance_runner(),
        "FMD-EXP-04": build_ml_estimator_runner(),
    }


def build_runner(experiment_id: str):
    if experiment_id in ("FMD-EXP-03", "FMD-EXP-05"):
        status = registered_candidate_eligibility()[experiment_id]["registry_status"]
        raise RuntimeError(f"{experiment_id} is {status} and has no FMD-07B executable runner")
    runners = build_minimum_candidate_runners()
    if experiment_id not in runners:
        raise ValueError(f"unknown registered experiment_id {experiment_id!r}")
    return runners[experiment_id]


def structural_readiness_audit() -> dict:
    runners = build_minimum_candidate_runners()
    ready = tuple(sorted(runners)) == tuple(sorted(MINIMUM_EXECUTABLE_EXPERIMENT_IDS))
    return {
        "checkpoint": CHECKPOINT,
        "python_runtime_dependency": DEPENDENCY_REQUIREMENT,
        "naive_ready": "FMD-EXP-01" in runners,
        "spatial_ready": "FMD-EXP-02" in runners,
        "ml_ready": "FMD-EXP-04" in runners,
        "dependency_declared": True,
        "minimum_candidate_set_ready": ready,
        "held_out_used": HELD_OUT_USED,
        "sri_lanka_used": SRI_LANKA_USED,
        "real_training_run": REAL_TRAINING_RUN,
        "development_metrics_generated": DEVELOPMENT_METRICS_GENERATED,
        "readiness_token": FMD07B_MINIMUM_EXECUTABLE_COMPARISON_SET_READY if ready else None,
    }
