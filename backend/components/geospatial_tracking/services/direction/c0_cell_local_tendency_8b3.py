"""Checkpoint 8B.3: ACTIVE cell-local negative-gradient tendency field.

**This is the ACTIVE, corrected method.** `services.direction.c0_geometric_tendency`
(Checkpoint 8B/8B.1, `compute_cell_direction_tendency`) remains
completely UNCHANGED for provenance -- its historical artifacts and
tests are frozen evidence, never rewritten. This module fixes a real
reference-frame defect Checkpoint 8B.2 discovered but did not
numerically correct: the historical field is expressed in each
SOURCE's own local tangent frame (`source_to_cell_unit_vector`'s
departure-azimuth-at-source convention), not the CELL's -- and the
true gradient of a geodesic distance function at an evaluation point
lives in that POINT's own local tangent frame. On the WGS84 ellipsoid
the two frames differ by the geodesic's meridian-convergence angle
over each source-cell path (confirmed empirically ~0.0012 degrees for
a 3km geodesic) -- small, but not identically zero, and a genuine
frame mismatch, not a numerical noise floor.

`compute_cell_direction_tendency_8b3` uses `services.geospatial.distance.source_to_cell_tangent_at_cell`
instead, so every source's directional contribution to a given cell is
expressed in that SAME cell's local East/North tangent frame before
summation -- the key correction (Checkpoint 8B.3 Part 6). With this
correction, `V_CELL(x) = -25km * grad(C0(x))` holds to genuinely
convergent numerical/geodesic precision (proven in
`tests/test_checkpoint_8b3_cell_local_correction.py`), not merely
approximately.

The directional weight is UNCHANGED: `w_j_i = K_C0(d_j_i) =
exp(-d_j_i/25km)`, the exact frozen C0 per-source kernel contribution
(`services.hazard.kernels.evaluate_kernel`, reused via
`c0_geometric_tendency.c0_directional_weight` -- no second
implementation, no new scientific parameter). Reuses the frozen
Checkpoint 8A.1 `DirectionalMassTerm`/`compute_resultant_vector`
directly for bearing/cancellation/clarity -- no second aggregation
implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..geospatial.distance import CELL_LOCAL_EAST_NORTH_TANGENT_FRAME, source_to_cell_tangent_at_cell
from ..model_development.direction_readiness_8a import DirectionalMassTerm, compute_resultant_vector
from .c0_geometric_tendency import c0_directional_weight

METHOD_ID_8B3 = "C0_CELL_LOCAL_NEGATIVE_GRADIENT_TENDENCY"
METHOD_VERSION_8B3 = "8B.3"
ACTIVE_OUTPUT_SEMANTICS_8B3 = "C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY"
ACTIVE_COORDINATE_FRAME_8B3 = CELL_LOCAL_EAST_NORTH_TANGENT_FRAME
TEMPORAL_SCOPE_8B3 = "T0_STATIC_NOT_DAY_SPECIFIC"
DIRECTION_EVALUATION_TRUTH_STATUS_8B3 = "DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN"
PREDICTIVE_SPREAD_DIRECTION_STATUS_8B3 = "NOT_PREDICTIVE_SPREAD_DIRECTION"

COMPLETE_DIRECTIONAL_MASS_COVERAGE = "COMPLETE_DIRECTIONAL_MASS_COVERAGE"
PARTIAL_DIRECTIONAL_MASS_COVERAGE_ZERO_DISTANCE = "PARTIAL_DIRECTIONAL_MASS_COVERAGE_ZERO_DISTANCE"
NO_SCALAR_MASS_COVERAGE_STATUS = "NO_SCALAR_MASS"
DIRECTION_STATUS_NO_ELIGIBLE_SOURCES = "DIRECTION_UNAVAILABLE_NO_ELIGIBLE_SOURCES"
ZERO_DISTANCE_UNDEFINED_DIRECTION = "ZERO_DISTANCE_UNDEFINED_DIRECTION"

_STANDARD_LIMITATIONS_8B3 = (
    "C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY_NOT_DISEASE_SPREAD_DIRECTION",
    "ISOTROPIC_C0_DOES_NOT_IDENTIFY_A_GLOBAL_OR_ORIGIN_LEVEL_BEARING",
    "T0_STATIC_NOT_DAY_SPECIFIC",
    "DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN",
)


@dataclass(frozen=True)
class SourceCellDirectionTerm8B3:
    source_id: str
    distance_km: float
    c0_directional_weight: float
    t_cell_east: float | None
    t_cell_north: float | None
    direction_defined: bool
    exclusion_reason: str | None
    coordinate_frame: str

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id, "distance_km": self.distance_km,
            "c0_directional_weight": self.c0_directional_weight,
            "t_cell_east": self.t_cell_east, "t_cell_north": self.t_cell_north,
            "direction_defined": self.direction_defined, "exclusion_reason": self.exclusion_reason,
            "coordinate_frame": self.coordinate_frame,
        }


@dataclass(frozen=True)
class CellDirectionTendency8B3:
    scientific_cell_id: str
    direction_status: str

    method_id: str
    method_version: str
    direction_semantics: str
    coordinate_frame: str
    temporal_scope: str
    direction_evaluation_truth_status: str
    predictive_spread_direction_status: str

    bearing_deg: float | None
    resultant_east: float
    resultant_north: float
    resultant_magnitude: float
    directional_clarity: float | None

    total_scalar_c0_mass: float
    directionally_defined_mass: float
    directional_input_coverage: float | None
    directional_mass_coverage_status: str

    n_total_eligible_sources: int
    n_positive_c0_weight_sources: int
    n_directionally_defined_sources: int
    n_zero_distance_undefined_direction_sources: int
    n_positive_weight_directionally_defined_sources: int

    source_terms: tuple
    limitations: tuple

    def as_dict(self) -> dict:
        return {
            "scientific_cell_id": self.scientific_cell_id, "direction_status": self.direction_status,
            "method_id": self.method_id, "method_version": self.method_version,
            "direction_semantics": self.direction_semantics, "coordinate_frame": self.coordinate_frame,
            "temporal_scope": self.temporal_scope,
            "direction_evaluation_truth_status": self.direction_evaluation_truth_status,
            "predictive_spread_direction_status": self.predictive_spread_direction_status,
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
            "source_terms": [t.as_dict() for t in self.source_terms],
            "limitations": list(self.limitations),
        }


def compute_cell_direction_tendency_8b3(cell: dict, sources: list) -> CellDirectionTendency8B3:
    """ACTIVE Checkpoint 8B.3 entry point. `cell`: a dict with
    `centroid_lat`/`centroid_lon` and `scientific_cell_id`/`grid_cell_id`
    (the same shape `compute_cell_direction_tendency` accepts).
    `sources`: `list[EligibleSourcePoint]`. NO target/future-outbreak
    parameter exists in this signature."""
    cell_id = cell.get("scientific_cell_id") or cell["grid_cell_id"]
    cell_lat, cell_lon = cell["centroid_lat"], cell["centroid_lon"]

    n_total = len(sources)
    if n_total == 0:
        return CellDirectionTendency8B3(
            scientific_cell_id=cell_id, direction_status=DIRECTION_STATUS_NO_ELIGIBLE_SOURCES,
            method_id=METHOD_ID_8B3, method_version=METHOD_VERSION_8B3,
            direction_semantics=ACTIVE_OUTPUT_SEMANTICS_8B3, coordinate_frame=ACTIVE_COORDINATE_FRAME_8B3,
            temporal_scope=TEMPORAL_SCOPE_8B3, direction_evaluation_truth_status=DIRECTION_EVALUATION_TRUTH_STATUS_8B3,
            predictive_spread_direction_status=PREDICTIVE_SPREAD_DIRECTION_STATUS_8B3,
            bearing_deg=None, resultant_east=0.0, resultant_north=0.0, resultant_magnitude=0.0,
            directional_clarity=None, total_scalar_c0_mass=0.0, directionally_defined_mass=0.0,
            directional_input_coverage=None, directional_mass_coverage_status=NO_SCALAR_MASS_COVERAGE_STATUS,
            n_total_eligible_sources=0, n_positive_c0_weight_sources=0, n_directionally_defined_sources=0,
            n_zero_distance_undefined_direction_sources=0, n_positive_weight_directionally_defined_sources=0,
            source_terms=(), limitations=_STANDARD_LIMITATIONS_8B3,
        )

    source_terms: list[SourceCellDirectionTerm8B3] = []
    directional_terms: list[DirectionalMassTerm] = []
    total_scalar_c0_mass = 0.0
    directionally_defined_mass = 0.0
    n_positive_weight = 0
    n_directionally_defined = 0
    n_zero_distance = 0
    n_positive_weight_directionally_defined = 0

    for s in sources:
        tangent = source_to_cell_tangent_at_cell(s.latitude, s.longitude, cell_lat, cell_lon)
        weight = c0_directional_weight(tangent.distance_km)
        total_scalar_c0_mass += weight
        if weight > 0:
            n_positive_weight += 1

        direction_defined = tangent.distance_km > 0
        if direction_defined:
            n_directionally_defined += 1
            directionally_defined_mass += weight
            if weight > 0:
                n_positive_weight_directionally_defined += 1
            directional_terms.append(DirectionalMassTerm(
                source_id=s.source_id, weight=weight, t_hat_east=tangent.t_cell_east,
                t_hat_north=tangent.t_cell_north, distance_km=tangent.distance_km,
            ))
            source_terms.append(SourceCellDirectionTerm8B3(
                source_id=s.source_id, distance_km=tangent.distance_km, c0_directional_weight=weight,
                t_cell_east=tangent.t_cell_east, t_cell_north=tangent.t_cell_north,
                direction_defined=True, exclusion_reason=None, coordinate_frame=tangent.coordinate_frame,
            ))
        else:
            n_zero_distance += 1
            source_terms.append(SourceCellDirectionTerm8B3(
                source_id=s.source_id, distance_km=tangent.distance_km, c0_directional_weight=weight,
                t_cell_east=None, t_cell_north=None,
                direction_defined=False, exclusion_reason=ZERO_DISTANCE_UNDEFINED_DIRECTION,
                coordinate_frame=tangent.coordinate_frame,
            ))

    result = compute_resultant_vector(directional_terms)

    coverage = (directionally_defined_mass / total_scalar_c0_mass) if total_scalar_c0_mass > 0 else None
    coverage_status = (
        NO_SCALAR_MASS_COVERAGE_STATUS if total_scalar_c0_mass <= 0
        else (PARTIAL_DIRECTIONAL_MASS_COVERAGE_ZERO_DISTANCE if n_zero_distance > 0 else COMPLETE_DIRECTIONAL_MASS_COVERAGE)
    )

    return CellDirectionTendency8B3(
        scientific_cell_id=cell_id, direction_status=result.cancellation_status,
        method_id=METHOD_ID_8B3, method_version=METHOD_VERSION_8B3,
        direction_semantics=ACTIVE_OUTPUT_SEMANTICS_8B3, coordinate_frame=ACTIVE_COORDINATE_FRAME_8B3,
        temporal_scope=TEMPORAL_SCOPE_8B3, direction_evaluation_truth_status=DIRECTION_EVALUATION_TRUTH_STATUS_8B3,
        predictive_spread_direction_status=PREDICTIVE_SPREAD_DIRECTION_STATUS_8B3,
        bearing_deg=result.bearing_deg, resultant_east=result.resultant_east, resultant_north=result.resultant_north,
        resultant_magnitude=result.magnitude, directional_clarity=result.directional_clarity,
        total_scalar_c0_mass=total_scalar_c0_mass, directionally_defined_mass=directionally_defined_mass,
        directional_input_coverage=coverage, directional_mass_coverage_status=coverage_status,
        n_total_eligible_sources=n_total, n_positive_c0_weight_sources=n_positive_weight,
        n_directionally_defined_sources=n_directionally_defined,
        n_zero_distance_undefined_direction_sources=n_zero_distance,
        n_positive_weight_directionally_defined_sources=n_positive_weight_directionally_defined,
        source_terms=tuple(source_terms), limitations=_STANDARD_LIMITATIONS_8B3,
    )
