"""Checkpoint 8B: frozen-C0-derived local geometric relative-risk
tendency field.

**Scientific purpose**: can the already-frozen scalar C0 model be given
a mathematically consistent LOCAL geometric relative-risk tendency
vector field without adding or tuning any new predictive parameter?
This module does NOT predict disease-spread direction. Output
semantics are always `C0_DERIVED_LOCAL_GEOMETRIC_RELATIVE_RISK_TENDENCY`
-- never `DISEASE_SPREAD_DIRECTION`, `TRANSMISSION_DIRECTION`,
`VALIDATED_SPREAD_DIRECTION`, or `FUTURE_OUTBREAK_DIRECTION`.

**Directional weight (Part 2)**: `w_j_i` is EXACTLY the frozen C0
per-source kernel contribution, `K_C0(d_j_i) = exp(-d_j_i / 25.0 km)`
-- computed via the SAME `services.hazard.kernels.evaluate_kernel`
primitive and the SAME `FROZEN_KERNEL_FAMILY`/`FROZEN_KERNEL_SCALE_KM`
constants `wind_scoring_7c.py`'s real C0 scoring uses (imported
directly from `candidate_registry_7c.py`, never re-declared). This is
`DIRECTIONAL_WEIGHT_DERIVED_FROM_FROZEN_C0_NO_NEW_PARAMETER` -- not a
newly fitted direction parameter.

**Scalar identity (Part 3)**: `SUM_j w_j_i == frozen C0 cell score`
by construction, since both sum the exact same per-source kernel
values over the exact same eligible-source set. This module computes
`total_scalar_c0_mass` directly as that sum -- it never imports or
reimplements a second exponential kernel.

**Cell-local, not global (Part 5)**: `compute_cell_direction_tendency`
operates on ONE grid cell at a time. There is no cross-cell
aggregation into a single global/origin-level bearing anywhere in this
module -- the isotropic C0 model does not scientifically identify one.

**Zero-distance mass coverage (Part 6)**: a source at `distance_km ==
0` carries full scalar C0 mass (`K(0) == 1`) but has a structurally
undefined SOURCE->CELL direction. That mass is INCLUDED in
`total_scalar_c0_mass` (never deleted from the C0-identity sum) but
EXCLUDED from `directionally_defined_mass` and the resultant-vector
computation (never a fabricated direction). `directional_input_coverage
= directionally_defined_mass / total_scalar_c0_mass` when
`total_scalar_c0_mass > 0`; `directional_mass_coverage_status` is
`COMPLETE_DIRECTIONAL_MASS_COVERAGE` or
`PARTIAL_DIRECTIONAL_MASS_COVERAGE_ZERO_DISTANCE`, determined
STRUCTURALLY (any positive-mass zero-distance source present), never by
a tuned threshold.

**Clarity vs. coverage vs. confidence (Part 7)**: `directional_clarity`
(agreement among directionally-defined contributions, from
`compute_resultant_vector`) and `directional_input_coverage` (fraction
of C0 scalar mass that has a defined direction) are kept as two
DISTINCT fields, never merged/multiplied into a new score. Neither is
ever called "confidence."

**Source-count semantics (Part 8)** -- five distinct counts, never
conflated:

- `n_total_eligible_sources`: every source passed in.
- `n_positive_c0_weight_sources`: sources with `K_C0(d) > 0`. For the
  frozen EXPONENTIAL kernel this is structurally ALWAYS equal to
  `n_total_eligible_sources` (`exp(x) > 0` for every finite `x`) --
  documented explicitly, never silently reinterpreted, and kept as a
  separate field only because a future kernel family need not share
  this property.
- `n_directionally_defined_sources`: sources with `distance_km > 0`
  (the SAME meaning as the 8A.1 primitive's `n_terms_usable`).
- `n_zero_distance_undefined_direction_sources`: the complement.
- `n_positive_weight_directionally_defined_sources`: the intersection
  (for this kernel, identical to `n_directionally_defined_sources`).

**Per-source evidence preserved (Part 9)**: every cell's result
carries a full `source_terms` tuple (never only the resultant), so
disagreement/cancellation among sources remains auditable and no
largest/nearest source is ever picked to force an arrow.

**Static t0 temporal scope (Part 10)**: C0 is static, so this field is
`T0_STATIC_NOT_DAY_SPECIFIC` -- never seven independently fabricated
D1-D7 bearings.

**Future-target firewall (Part 11)**: `compute_cell_direction_tendency`
takes only a cell and a list of eligible sources -- there is no
`target`/future-outbreak parameter anywhere in this module's public
signatures (verified structurally by 8B-TIME-02/8B-CIRCULAR-01).

**No circular evaluation, no wind (Parts 12-13)**: this module computes
no angular-performance metric of any kind and imports no
weather/wind/environmental module -- Method A is derived from frozen
C0 geometry only.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..geospatial.distance import source_to_cell_unit_vector
from ..hazard.kernels import evaluate_kernel
from ..model_development.candidate_registry_7c import FROZEN_KERNEL_FAMILY, FROZEN_KERNEL_SCALE_KM
from ..model_development.direction_readiness_8a import (
    DIRECTION_AVAILABLE,
    DIRECTIONAL_CONTRIBUTIONS_CANCELLED,
    NO_DIRECTIONAL_MASS,
    DirectionalMassTerm,
    compute_resultant_vector,
)

DIRECTION_SEMANTICS_8B = "C0_DERIVED_LOCAL_GEOMETRIC_RELATIVE_RISK_TENDENCY"
TEMPORAL_SCOPE_8B = "T0_STATIC_NOT_DAY_SPECIFIC"
METHOD_ID_8B = "C0_GEOMETRIC_TENDENCY"
METHOD_VERSION_8B = "8B.1"
DIRECTIONAL_WEIGHT_IDENTITY_8B = "FROZEN_C0_PER_SOURCE_SCALAR_CONTRIBUTION"

COMPLETE_DIRECTIONAL_MASS_COVERAGE = "COMPLETE_DIRECTIONAL_MASS_COVERAGE"
PARTIAL_DIRECTIONAL_MASS_COVERAGE_ZERO_DISTANCE = "PARTIAL_DIRECTIONAL_MASS_COVERAGE_ZERO_DISTANCE"
NO_SCALAR_MASS_COVERAGE_STATUS = "NO_SCALAR_MASS"

DIRECTION_STATUS_NO_ELIGIBLE_SOURCES = "DIRECTION_UNAVAILABLE_NO_ELIGIBLE_SOURCES"

ZERO_DISTANCE_UNDEFINED_DIRECTION = "ZERO_DISTANCE_UNDEFINED_DIRECTION"

_STANDARD_LIMITATIONS = (
    "C0_DERIVED_LOCAL_GEOMETRIC_RELATIVE_RISK_TENDENCY_NOT_DISEASE_SPREAD_DIRECTION",
    "ISOTROPIC_C0_DOES_NOT_IDENTIFY_A_GLOBAL_OR_ORIGIN_LEVEL_BEARING",
    "T0_STATIC_NOT_DAY_SPECIFIC",
    "DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN",
)


def c0_directional_weight(distance_km: float) -> float:
    """`w_j_i = K_C0(d_j_i)` -- the exact frozen C0 per-source kernel
    contribution, no second implementation."""
    return evaluate_kernel(distance_km, family=FROZEN_KERNEL_FAMILY, distance_scale_km=FROZEN_KERNEL_SCALE_KM)


@dataclass(frozen=True)
class SourceCellDirectionTerm:
    source_id: str
    distance_km: float
    c0_directional_weight: float
    t_hat_east: float | None  # None exactly when direction_defined is False
    t_hat_north: float | None
    direction_defined: bool
    exclusion_reason: str | None  # None exactly when direction_defined is True

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id, "distance_km": self.distance_km,
            "c0_directional_weight": self.c0_directional_weight,
            "t_hat_east": self.t_hat_east, "t_hat_north": self.t_hat_north,
            "direction_defined": self.direction_defined, "exclusion_reason": self.exclusion_reason,
        }


@dataclass(frozen=True)
class CellDirectionTendency8B:
    scientific_cell_id: str
    direction_status: str  # DIRECTION_AVAILABLE | DIRECTIONAL_CONTRIBUTIONS_CANCELLED | NO_DIRECTIONAL_MASS | DIRECTION_UNAVAILABLE_NO_ELIGIBLE_SOURCES
    direction_semantics: str
    temporal_scope: str

    bearing_deg: float | None
    resultant_east: float
    resultant_north: float
    resultant_magnitude: float
    directional_clarity: float | None

    total_scalar_c0_mass: float
    directionally_defined_mass: float
    directional_input_coverage: float | None  # None only when total_scalar_c0_mass == 0
    directional_mass_coverage_status: str

    n_total_eligible_sources: int
    n_positive_c0_weight_sources: int
    n_directionally_defined_sources: int
    n_zero_distance_undefined_direction_sources: int
    n_positive_weight_directionally_defined_sources: int

    method_id: str
    method_version: str

    source_terms: tuple
    limitations: tuple

    def as_dict(self) -> dict:
        return {
            "scientific_cell_id": self.scientific_cell_id, "direction_status": self.direction_status,
            "direction_semantics": self.direction_semantics, "temporal_scope": self.temporal_scope,
            "bearing_deg": self.bearing_deg, "resultant_east": self.resultant_east,
            "resultant_north": self.resultant_north, "resultant_magnitude": self.resultant_magnitude,
            "directional_clarity": self.directional_clarity,
            "total_scalar_c0_mass": self.total_scalar_c0_mass,
            "directionally_defined_mass": self.directionally_defined_mass,
            "directional_input_coverage": self.directional_input_coverage,
            "directional_mass_coverage_status": self.directional_mass_coverage_status,
            "n_total_eligible_sources": self.n_total_eligible_sources,
            "n_positive_c0_weight_sources": self.n_positive_c0_weight_sources,
            "n_directionally_defined_sources": self.n_directionally_defined_sources,
            "n_zero_distance_undefined_direction_sources": self.n_zero_distance_undefined_direction_sources,
            "n_positive_weight_directionally_defined_sources": self.n_positive_weight_directionally_defined_sources,
            "method_id": self.method_id, "method_version": self.method_version,
            "source_terms": [t.as_dict() for t in self.source_terms],
            "limitations": list(self.limitations),
        }


def compute_cell_direction_tendency(cell: dict, sources: list) -> CellDirectionTendency8B:
    """`cell`: a dict with `centroid_lat`/`centroid_lon` and
    `scientific_cell_id`/`grid_cell_id` (the SAME shape
    `development_run_7c._grid_cell_dicts` already produces). `sources`:
    `list[EligibleSourcePoint]`. NO target/future-outbreak parameter
    exists in this signature (Part 11 firewall) -- there is structurally
    nothing a caller could pass to make this function circular."""
    cell_id = cell.get("scientific_cell_id") or cell["grid_cell_id"]
    cell_lat, cell_lon = cell["centroid_lat"], cell["centroid_lon"]

    n_total = len(sources)
    if n_total == 0:
        return CellDirectionTendency8B(
            scientific_cell_id=cell_id, direction_status=DIRECTION_STATUS_NO_ELIGIBLE_SOURCES,
            direction_semantics=DIRECTION_SEMANTICS_8B, temporal_scope=TEMPORAL_SCOPE_8B,
            bearing_deg=None, resultant_east=0.0, resultant_north=0.0, resultant_magnitude=0.0,
            directional_clarity=None, total_scalar_c0_mass=0.0, directionally_defined_mass=0.0,
            directional_input_coverage=None, directional_mass_coverage_status=NO_SCALAR_MASS_COVERAGE_STATUS,
            n_total_eligible_sources=0, n_positive_c0_weight_sources=0, n_directionally_defined_sources=0,
            n_zero_distance_undefined_direction_sources=0, n_positive_weight_directionally_defined_sources=0,
            method_id=METHOD_ID_8B, method_version=METHOD_VERSION_8B, source_terms=(), limitations=_STANDARD_LIMITATIONS,
        )

    source_terms: list[SourceCellDirectionTerm] = []
    directional_terms: list[DirectionalMassTerm] = []
    total_scalar_c0_mass = 0.0
    directionally_defined_mass = 0.0
    n_positive_weight = 0
    n_directionally_defined = 0
    n_zero_distance = 0
    n_positive_weight_directionally_defined = 0

    for s in sources:
        vec = source_to_cell_unit_vector(s.latitude, s.longitude, cell_lat, cell_lon)
        weight = c0_directional_weight(vec.distance_km)
        total_scalar_c0_mass += weight
        if weight > 0:
            n_positive_weight += 1

        direction_defined = vec.distance_km > 0
        if direction_defined:
            n_directionally_defined += 1
            directionally_defined_mass += weight
            if weight > 0:
                n_positive_weight_directionally_defined += 1
            directional_terms.append(DirectionalMassTerm(
                source_id=s.source_id, weight=weight, t_hat_east=vec.t_hat_east,
                t_hat_north=vec.t_hat_north, distance_km=vec.distance_km,
            ))
            source_terms.append(SourceCellDirectionTerm(
                source_id=s.source_id, distance_km=vec.distance_km, c0_directional_weight=weight,
                t_hat_east=vec.t_hat_east, t_hat_north=vec.t_hat_north,
                direction_defined=True, exclusion_reason=None,
            ))
        else:
            n_zero_distance += 1
            source_terms.append(SourceCellDirectionTerm(
                source_id=s.source_id, distance_km=vec.distance_km, c0_directional_weight=weight,
                t_hat_east=None, t_hat_north=None,
                direction_defined=False, exclusion_reason=ZERO_DISTANCE_UNDEFINED_DIRECTION,
            ))

    result = compute_resultant_vector(directional_terms)

    coverage = (directionally_defined_mass / total_scalar_c0_mass) if total_scalar_c0_mass > 0 else None
    coverage_status = (
        NO_SCALAR_MASS_COVERAGE_STATUS if total_scalar_c0_mass <= 0
        else (PARTIAL_DIRECTIONAL_MASS_COVERAGE_ZERO_DISTANCE if n_zero_distance > 0 else COMPLETE_DIRECTIONAL_MASS_COVERAGE)
    )

    return CellDirectionTendency8B(
        scientific_cell_id=cell_id, direction_status=result.cancellation_status,
        direction_semantics=DIRECTION_SEMANTICS_8B, temporal_scope=TEMPORAL_SCOPE_8B,
        bearing_deg=result.bearing_deg, resultant_east=result.resultant_east, resultant_north=result.resultant_north,
        resultant_magnitude=result.magnitude, directional_clarity=result.directional_clarity,
        total_scalar_c0_mass=total_scalar_c0_mass, directionally_defined_mass=directionally_defined_mass,
        directional_input_coverage=coverage, directional_mass_coverage_status=coverage_status,
        n_total_eligible_sources=n_total, n_positive_c0_weight_sources=n_positive_weight,
        n_directionally_defined_sources=n_directionally_defined,
        n_zero_distance_undefined_direction_sources=n_zero_distance,
        n_positive_weight_directionally_defined_sources=n_positive_weight_directionally_defined,
        method_id=METHOD_ID_8B, method_version=METHOD_VERSION_8B,
        source_terms=tuple(source_terms), limitations=_STANDARD_LIMITATIONS,
    )
