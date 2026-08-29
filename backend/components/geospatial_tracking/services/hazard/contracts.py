"""Checkpoint 6C: the hazard-engine input/factor contracts.

This package (`services/hazard/`) is deliberately independent of
SQLite, FastAPI, React, and ST-DBSCAN internals (Part 1) — every
function here consumes explicit structured inputs
(`SourceGeometry`/`WindVector`/`HazardFactors`), never a
`FeatureSnapshot`, `GridCellFeatures`, `STClusterSnapshot`, or a repo
object directly. Wiring real feature data into these contracts is a
FUTURE, separate transformer — not built in this checkpoint (Part 3).

**Permanent scientific label (Part 2)**: this engine's output is a
**RELATIVE RISK INDEX**, never "infection probability," "chance an
animal becomes infected," or a percentage framed as calibrated risk.

**Missingness contract (Part 28-29)**: `FactorValue` structurally
prevents a `MISSING`/`BLOCKED`/`DEMO` factor from ever carrying a
usable number — `__post_init__` raises if a non-`REAL`/
`SOFTWARE_FIXTURE_ONLY` status carries a value, so no downstream code
can silently read a missing factor as `0` ("no risk") or `1`
("neutral"). A pathway that is INTENTIONALLY disabled by
`HazardConfig.anisotropic_pathway_enabled=False` is a completely
different, distinguishable outcome (`DISABLED_BY_CONFIG`, contributes
exactly `0.0` by declared design) from a pathway that is enabled but
missing required data (`SOURCE_HAZARD_INCOMPLETE`) — never conflated.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum

SOFTWARE_FIXTURE_ONLY = "SOFTWARE_FIXTURE_ONLY"
UNFROZEN_DEVELOPMENT_CANDIDATE = "UNFROZEN_DEVELOPMENT_CANDIDATE"
FROZEN_REFERENCE = "FROZEN_REFERENCE"
ALLOWED_HAZARD_PARAMETER_STATUSES = {SOFTWARE_FIXTURE_ONLY, UNFROZEN_DEVELOPMENT_CANDIDATE}  # never FROZEN_REFERENCE (Part 18)

WIND_SPEED_EFFECT_NOT_YET_SELECTED = "NOT_YET_SELECTED"
WATER_PATHWAY_NOT_YET_SELECTED = "NOT_YET_SELECTED"
PRIOR_TERM_NOT_SCIENTIFICALLY_DEFINED = "NOT_SCIENTIFICALLY_DEFINED"

COMPLETE = "COMPLETE"
SOURCE_HAZARD_INCOMPLETE = "SOURCE_HAZARD_INCOMPLETE"
CELL_HAZARD_INCOMPLETE = "CELL_HAZARD_INCOMPLETE"
HAZARD_SNAPSHOT_INCOMPLETE = "HAZARD_SNAPSHOT_INCOMPLETE"
DISABLED_BY_CONFIG = "DISABLED_BY_CONFIG"


class KernelFamily(str, Enum):
    """Part 7: candidate radial kernel families — NEVER scientifically
    frozen to one family in this checkpoint."""

    EXPONENTIAL = "EXPONENTIAL"
    GAUSSIAN = "GAUSSIAN"


class AnisotropyMode(str, Enum):
    """Part 13: two explicitly different candidate semantics for how
    anisotropy affects total pathway mass — never mixed, never
    scientifically selected in this checkpoint."""

    MODULATING = "MODULATING"
    ANGULAR_NORMALIZED = "ANGULAR_NORMALIZED"


class FactorStatus(str, Enum):
    """`REAL`/`SOFTWARE_FIXTURE_ONLY` are the only statuses that may
    carry a usable numeric value. `MISSING`/`BLOCKED`/`DEMO` may not —
    see `FactorValue.__post_init__`."""

    REAL = "REAL"
    SOFTWARE_FIXTURE_ONLY = "SOFTWARE_FIXTURE_ONLY"
    MISSING = "MISSING"
    BLOCKED = "BLOCKED"
    DEMO = "DEMO"


_USABLE_FACTOR_STATUSES = {FactorStatus.REAL.value, FactorStatus.SOFTWARE_FIXTURE_ONLY.value}


def reject_non_finite(name: str, value: float) -> None:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {value!r}")
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"{name} must be finite (NaN/infinity rejected), got {value!r}")


@dataclass(frozen=True)
class FactorValue:
    """A single dimensionless-modifier input, carrying its own
    provenance status. `value` is `None` for every non-usable status —
    this is a structural guarantee (Part 22/28), not a convention."""

    value: float | None
    status: str  # FactorStatus value

    def __post_init__(self) -> None:
        if self.status not in {s.value for s in FactorStatus}:
            raise ValueError(f"unknown FactorStatus {self.status!r}")
        if self.status in _USABLE_FACTOR_STATUSES:
            if self.value is None:
                raise ValueError(f"status={self.status} requires a non-None value")
            reject_non_finite("value", self.value)
        elif self.value is not None:
            raise ValueError(
                f"status={self.status} must never carry a numeric value — this would let a MISSING/BLOCKED/DEMO "
                "factor be silently misread as usable (Part 28)"
            )

    @property
    def usable(self) -> bool:
        return self.status in _USABLE_FACTOR_STATUSES


def _validate_unit_factor(fv: FactorValue) -> None:
    if fv.usable and not (0.0 <= fv.value <= 1.0):
        raise ValueError(f"factor must be within [0, 1] when usable, got {fv.value!r}")


def _validate_nonnegative_factor(fv: FactorValue) -> None:
    if fv.usable and fv.value < 0:
        raise ValueError(f"factor must be >= 0 when usable, got {fv.value!r}")


@dataclass(frozen=True)
class SourceGeometry:
    """Mirrors `features.contracts.GridCellFeatures.geometry_by_source[source_id]`
    (`distance_km`, `t_hat_east`, `t_hat_north`) — but this dataclass is
    the hazard package's OWN contract; it never imports the features
    package (Part 1's independence requirement)."""

    source_id: str
    grid_cell_id: str
    distance_km: float
    t_hat_east: float
    t_hat_north: float

    def __post_init__(self) -> None:
        reject_non_finite("distance_km", self.distance_km)
        if self.distance_km < 0:
            raise ValueError(f"distance_km must be >= 0, got {self.distance_km!r}")
        reject_non_finite("t_hat_east", self.t_hat_east)
        reject_non_finite("t_hat_north", self.t_hat_north)


@dataclass(frozen=True)
class WindVector:
    """`u10` = eastward component, `v10` = northward component (m/s) —
    the SAME convention as `geospatial/weather/wind.py`. Never converted
    to/reconstructed from a compass bearing (Part 9)."""

    u10: float
    v10: float

    def __post_init__(self) -> None:
        reject_non_finite("u10", self.u10)
        reject_non_finite("v10", self.v10)


LEGACY_6C_FIXTURE_ONLY = "LEGACY_6C_FIXTURE_ONLY"


@dataclass(frozen=True)
class HazardFactors:
    """**SUPERSEDED_BY_6C5_INDEX_CORRECTION — `LEGACY_6C_FIXTURE_ONLY`.**
    Checkpoint 6C grouped `host_factor`/`environmental_suitability_factor`/
    `water_context_factor` under a single per-SOURCE bag, which
    incorrectly implied these are source-specific quantities. They are
    actually CELL properties (`CellHazardFactors`) — only
    `source_strength_factor` (`SourceHazardFactors`) is genuinely
    source-indexed. This class is kept ONLY so old fixtures/tests that
    still construct it do not need to be deleted outright; the primary
    hazard path (`source_hazard.compute_source_hazard`,
    `snapshot.build_hazard_snapshot`) no longer accepts it at all —
    see `CellHazardFactors`/`SourceHazardFactors` below."""

    host_factor: FactorValue
    environmental_suitability_factor: FactorValue
    water_context_factor: FactorValue
    source_strength_factor: FactorValue

    def __post_init__(self) -> None:
        for name, fv in (
            ("host_factor", self.host_factor),
            ("environmental_suitability_factor", self.environmental_suitability_factor),
            ("water_context_factor", self.water_context_factor),
            ("source_strength_factor", self.source_strength_factor),
        ):
            if not isinstance(fv, FactorValue):
                raise TypeError(f"{name} must be a FactorValue, got {type(fv)!r}")
            if fv.usable and fv.status != SOFTWARE_FIXTURE_ONLY:
                raise ValueError(
                    f"{name} has usable status {fv.status!r} — Checkpoint 6C permits only "
                    f"SOFTWARE_FIXTURE_ONLY usable factors (no real feature->factor transformer exists yet)"
                )
        _validate_unit_factor(self.host_factor)
        _validate_unit_factor(self.environmental_suitability_factor)
        _validate_unit_factor(self.water_context_factor)
        _validate_nonnegative_factor(self.source_strength_factor)


def _require_fixture_only(name: str, fv: FactorValue) -> None:
    if not isinstance(fv, FactorValue):
        raise TypeError(f"{name} must be a FactorValue, got {type(fv)!r}")
    if fv.usable and fv.status != SOFTWARE_FIXTURE_ONLY:
        raise ValueError(
            f"{name} has usable status {fv.status!r} — Checkpoint 6C.5 permits only SOFTWARE_FIXTURE_ONLY "
            "usable factors (no real feature->factor transformer exists yet)"
        )


@dataclass(frozen=True)
class CellHazardFactors:
    """Checkpoint 6C.5 Parts 1-3: CELL-indexed dimensionless factors.
    `host_factor`, `environmental_suitability_factor`, and
    `water_context_factor` are properties of the CELL, not of any one
    source — every source contribution to a given cell reads the exact
    same `CellHazardFactors` object, so they can never disagree
    (INDEX-01/02/03). Every usable value must carry
    `status=SOFTWARE_FIXTURE_ONLY` in this checkpoint."""

    grid_cell_id: str
    host_factor: FactorValue
    environmental_suitability_factor: FactorValue
    water_context_factor: FactorValue

    def __post_init__(self) -> None:
        _require_fixture_only("host_factor", self.host_factor)
        _require_fixture_only("environmental_suitability_factor", self.environmental_suitability_factor)
        _require_fixture_only("water_context_factor", self.water_context_factor)
        _validate_unit_factor(self.host_factor)
        _validate_unit_factor(self.environmental_suitability_factor)
        _validate_unit_factor(self.water_context_factor)


@dataclass(frozen=True)
class SourceHazardFactors:
    """Checkpoint 6C.5 Part 4: SOURCE-indexed dimensionless factors.
    Only `source_strength_factor` belongs to a source in the current
    mathematical design — it is NEVER derived from `affected_animals`,
    DQS, cluster role, GPS quality, or case count (this dataclass
    structurally has no such parameter to derive it from), and every
    usable value must carry `status=SOFTWARE_FIXTURE_ONLY`."""

    source_id: str
    source_strength_factor: FactorValue

    def __post_init__(self) -> None:
        _require_fixture_only("source_strength_factor", self.source_strength_factor)
        _validate_nonnegative_factor(self.source_strength_factor)


@dataclass(frozen=True)
class HazardMixConfig:
    """Part 18: pathway-mixing coefficients `a` (local_weight) and `b`
    (anisotropic_weight) in `H_j_i = a*L_j_i + b*W_j_i`. NEVER
    scientifically chosen in this checkpoint — `parameter_status` may
    only be `SOFTWARE_FIXTURE_ONLY` or `UNFROZEN_DEVELOPMENT_CANDIDATE`,
    never `FROZEN_REFERENCE`."""

    local_weight: float
    anisotropic_weight: float
    parameter_status: str = UNFROZEN_DEVELOPMENT_CANDIDATE

    def __post_init__(self) -> None:
        reject_non_finite("local_weight", self.local_weight)
        reject_non_finite("anisotropic_weight", self.anisotropic_weight)
        if self.local_weight < 0 or self.anisotropic_weight < 0:
            raise ValueError("pathway mixing coefficients must be >= 0 (a mathematical software contract only)")
        if self.parameter_status not in ALLOWED_HAZARD_PARAMETER_STATUSES:
            raise ValueError(
                f"HazardMixConfig.parameter_status must be one of {sorted(ALLOWED_HAZARD_PARAMETER_STATUSES)}, "
                f"got {self.parameter_status!r} — FROZEN_REFERENCE is not permitted in Checkpoint 6C"
            )

    def as_dict(self) -> dict:
        return {
            "local_weight": self.local_weight,
            "anisotropic_weight": self.anisotropic_weight,
            "parameter_status": self.parameter_status,
        }
