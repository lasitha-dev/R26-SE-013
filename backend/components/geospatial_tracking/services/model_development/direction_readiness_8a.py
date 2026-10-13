"""Checkpoint 8A / 8A.1: frozen READINESS-ONLY direction primitives.

**Not wired into any predictive pipeline.** `wind_scoring_7c.py` (C0/CW
candidate scoring, Checkpoints 7B-7E) does not import this module and
this module does not import `wind_scoring_7c.py`. Nothing here computes
disease-spread direction, fits a direction model, or scores held-out/Sri
Lanka data. These are pure, self-contained mathematical primitives that
exist ONLY so Checkpoint 8A's bearing-convention/resultant-vector/
directional-clarity semantics can be frozen and unit-tested before any
8B development work is attempted.

**Terminology discipline (Part 2)**: never call a value in this module
"disease spread direction," "spread-front rate," or "confidence."
`directional_clarity` is an agreement measure between 0 and 1, never a
probability or accuracy statement (Part 12).

**Bearing convention (Part 6)**: 0=North, 90=East, 180=South, 270=West,
clockwise from north, range [0, 360). For east/north unit components,
`bearing = atan2(east, north)` normalized to [0, 360). `0.0` degrees is
a VALID North bearing and is never conflated with "missing" (Part 6,
14) -- absence of a defined bearing is represented structurally as
`None`, never as the float `0.0`.

**Checkpoint 8A.1 hardening -- three DISTINCT, separately named
numerical tolerances, never conflated (Part 8)**:

A. `GENERIC_BEARING_ZERO_SEMANTICS` -- `bearing_deg_from_components`
   returns `None` ONLY for an EXACT `(0, 0)` input (`magnitude == 0.0`).
   No absolute epsilon is applied here: a finite, arbitrarily tiny,
   nonzero generic vector still has a well-defined geometric bearing
   (8A1-BEAR-02) and must never be silently suppressed by a
   weighted-resultant tolerance that has nothing to do with generic
   geometry.

B. `RESULTANT_RELATIVE_CANCELLATION_EPSILON` -- a DIMENSIONLESS
   engineering tolerance (never a fitted scientific parameter) applied
   ONLY inside `compute_resultant_vector`, to the SCALE-INVARIANT ratio
   `magnitude / total_mass`, never to raw magnitude. Multiplying every
   positive weight by a common positive scalar `c` leaves this ratio
   exactly unchanged (both numerator and denominator scale by `c`), so
   bearing availability and `directional_clarity` are provably
   scale-invariant (8A1-SCALE-01/02).

C. Meteorological calm-wind threshold -- `wind_to_bearing_from_components`
   reuses `services.hazard.anisotropy.CALM_WIND_EPSILON_M_S` (`1e-6
   m/s`, absolute, the SAME already-audited constant and `<` comparison
   `compute_meteorological_alignment` uses) rather than duplicating a
   second magic `1e-6` literal or applying either of the two tolerances
   above, which have different units and different meanings
   (8A1-WIND-01..03).

**Non-finite values fail closed (Part 4)**: every numerical input to
every function/dataclass in this module is rejected (`ValueError`) if
it is `NaN`, `+-inf`, or not a real number -- reusing
`services.hazard.contracts.reject_non_finite` rather than a second
implementation. A `NaN` is never silently reinterpreted as `0` or as
"missing/North."

**Unit-vector invariant (Part 5)**: a USABLE term (`distance_km > 0`)
must carry `t_hat_east**2 + t_hat_north**2 ~= 1` within
`UNIT_VECTOR_NORM_TOLERANCE`, checked at construction and never
silently renormalized -- a malformed unit vector indicates an upstream
geometry defect and must fail closed, not be hidden. A zero-distance
term (`distance_km == 0`) must carry EXACTLY `(0.0, 0.0)` -- the
existing `source_to_cell_unit_vector` degenerate-case convention -- and
is excluded from both the resultant sum and the clarity denominator
rather than silently contributing a fabricated direction or deflating
`directional_clarity` for a source that never had a definable direction
(Parts 13-14).

**Directional-clarity range guarantee (Part 6)**: with weights `>= 0`
and every usable `t_hat` a genuine unit vector, `directional_clarity in
[0, 1]` follows from the triangle inequality. Floating-point rounding
can still produce a microscopic overshoot (e.g. `1.0000000000000002`);
such overshoot is clamped ONLY within `CLARITY_RANGE_CLAMP_TOLERANCE`,
never silently for a materially out-of-range value, which instead
raises `ValueError` as a genuine scientific-invariant violation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..hazard.anisotropy import CALM_WIND_EPSILON_M_S
from ..hazard.contracts import reject_non_finite

BEARING_CONVENTION = "CLOCKWISE_FROM_NORTH_DEGREES_0_TO_360_EXCLUSIVE"
GENERIC_BEARING_ZERO_SEMANTICS = "EXACT_ZERO_MAGNITUDE_ONLY_RETURNS_NONE_NO_ABSOLUTE_EPSILON"

# Checkpoint 8A.1 Part 2: dimensionless, applied only to magnitude/total_mass.
RESULTANT_RELATIVE_CANCELLATION_EPSILON = 1e-9

# Checkpoint 8A.1 Part 5.
UNIT_VECTOR_NORM_TOLERANCE = 1e-6

# Checkpoint 8A.1 Part 6.
CLARITY_RANGE_CLAMP_TOLERANCE = 1e-9

NO_DIRECTIONAL_MASS = "NO_DIRECTIONAL_MASS"
DIRECTIONAL_CONTRIBUTIONS_CANCELLED = "DIRECTIONAL_CONTRIBUTIONS_CANCELLED"
DIRECTION_AVAILABLE = "DIRECTION_AVAILABLE"


def _wrap_bearing_deg(raw_degrees: float) -> float:
    bearing = raw_degrees % 360.0
    # a near-360 float can round UP to exactly 360.0 (the ULP near 360 is
    # larger than a sub-picodegree residual from atan2) -- re-wrap so the
    # contract's own [0, 360) range is never violated by its edge case.
    if bearing >= 360.0:
        bearing = 0.0
    return bearing


def bearing_deg_from_components(east: float, north: float) -> float | None:
    """`None` (UNDEFINED) ONLY for an EXACT `(0, 0)` vector -- no
    absolute epsilon (`GENERIC_BEARING_ZERO_SEMANTICS`). Otherwise
    `atan2(east, north)` in degrees, normalized to `[0, 360)`. Rejects
    non-finite input."""
    reject_non_finite("east", east)
    reject_non_finite("north", north)
    if east == 0.0 and north == 0.0:
        return None
    return _wrap_bearing_deg(math.degrees(math.atan2(east, north)))


def wind_to_bearing_from_components(u10: float, v10: float) -> float | None:
    """Motion-TO bearing (the compass direction the wind is blowing
    TOWARD) from eastward/northward wind components. Kept as a distinct
    named entry point (Part 7) so a caller can never mistake a
    wind-motion bearing for a generic geometric bearing by accident of a
    shared function name. Uses the SAME calm-wind threshold/comparison
    as `services.hazard.anisotropy.compute_meteorological_alignment`
    (`magnitude < CALM_WIND_EPSILON_M_S`) -- never the generic-bearing
    exact-zero rule and never a duplicated literal (Checkpoint 8A.1 Part
    7). Rejects non-finite input."""
    reject_non_finite("u10", u10)
    reject_non_finite("v10", v10)
    magnitude = math.hypot(u10, v10)
    if magnitude < CALM_WIND_EPSILON_M_S:
        return None
    return _wrap_bearing_deg(math.degrees(math.atan2(u10, v10)))


def wind_from_bearing_deg(wind_to_bearing_deg: float) -> float:
    """Meteorological FROM-bearing (the traditional "wind direction")
    from a motion-TO bearing: `(to + 180) mod 360` (Part 7). Applies the
    180-degree conversion EXACTLY once; callers must not pass an
    already-FROM bearing back through this function. Rejects non-finite
    input."""
    reject_non_finite("wind_to_bearing_deg", wind_to_bearing_deg)
    return _wrap_bearing_deg(wind_to_bearing_deg + 180.0)


@dataclass(frozen=True)
class DirectionalMassTerm:
    """One SOURCE-SPECIFIC directional contribution. `weight` (`w_j_i`)
    is a caller-supplied scientifically defined directional/hazard
    weight -- Checkpoint 8A/8A.1 does not choose or freeze any such
    weight (Part 11); this dataclass only carries whatever weight the
    caller passes in for readiness-testing purposes. `distance_km` is
    required so zero-distance (undefined-direction) terms can be
    identified and excluded rather than silently contributing a
    fabricated `(0, 0)` vector to a clarity denominator.

    Fails closed (Checkpoint 8A.1 Parts 4-5): every field must be a
    finite real number; a USABLE term (`distance_km > 0`) must carry a
    genuine unit vector within `UNIT_VECTOR_NORM_TOLERANCE`, never
    silently renormalized; a zero-distance term must carry EXACTLY
    `(0.0, 0.0)`, never a fabricated nonzero direction."""

    source_id: str
    weight: float
    t_hat_east: float
    t_hat_north: float
    distance_km: float

    def __post_init__(self) -> None:
        reject_non_finite("weight", self.weight)
        reject_non_finite("distance_km", self.distance_km)
        reject_non_finite("t_hat_east", self.t_hat_east)
        reject_non_finite("t_hat_north", self.t_hat_north)
        if self.weight < 0:
            raise ValueError(f"directional weight must be >= 0, got {self.weight!r}")
        if self.distance_km < 0:
            raise ValueError(f"distance_km must be >= 0, got {self.distance_km!r}")

        if self.distance_km > 0:
            norm = math.hypot(self.t_hat_east, self.t_hat_north)
            if abs(norm - 1.0) > UNIT_VECTOR_NORM_TOLERANCE:
                raise ValueError(
                    f"source {self.source_id!r}: t_hat unit-vector norm {norm!r} deviates from 1.0 by more "
                    f"than UNIT_VECTOR_NORM_TOLERANCE={UNIT_VECTOR_NORM_TOLERANCE!r} at distance_km="
                    f"{self.distance_km!r} -- this indicates an upstream geometry defect and is never "
                    "silently renormalized"
                )
        else:
            if self.t_hat_east != 0.0 or self.t_hat_north != 0.0:
                raise ValueError(
                    f"source {self.source_id!r}: zero-distance term must carry exactly (0.0, 0.0) -- got "
                    f"({self.t_hat_east!r}, {self.t_hat_north!r}); a nonzero direction at zero distance is "
                    "never permitted"
                )


@dataclass(frozen=True)
class ResultantVectorResult:
    resultant_east: float
    resultant_north: float
    bearing_deg: float | None
    magnitude: float
    directional_clarity: float | None  # None only when total usable directional mass is 0
    cancellation_status: str  # NO_DIRECTIONAL_MASS | DIRECTIONAL_CONTRIBUTIONS_CANCELLED | DIRECTION_AVAILABLE
    n_terms_total: int
    n_terms_usable: int
    n_terms_excluded_zero_distance: int


def compute_resultant_vector(terms: list[DirectionalMassTerm]) -> ResultantVectorResult:
    """Part 11/12 readiness primitive, hardened scale-invariant in
    Checkpoint 8A.1. `resultant = SUM_j weight_j * t_hat_j` over USABLE
    (non-zero-distance) terms only; `directional_clarity =
    ||resultant|| / SUM_j weight_j` over the same usable set. Both
    bearing availability and `directional_clarity` depend ONLY on the
    dimensionless ratio `magnitude / total_mass`, which is invariant
    under multiplying every weight by a common positive scalar
    (8A1-SCALE-01/02) -- no absolute magnitude cutoff is used. This
    function performs no source aggregation shortcut: it sums exactly
    the per-source terms it is given, with no nearest-source collapse."""
    usable = [t for t in terms if t.distance_km > 0]
    n_excluded = len(terms) - len(usable)
    total_mass = sum(t.weight for t in usable)

    if total_mass <= 0.0:
        return ResultantVectorResult(
            resultant_east=0.0, resultant_north=0.0, bearing_deg=None, magnitude=0.0,
            directional_clarity=None, cancellation_status=NO_DIRECTIONAL_MASS,
            n_terms_total=len(terms), n_terms_usable=len(usable), n_terms_excluded_zero_distance=n_excluded,
        )

    r_east = sum(t.weight * t.t_hat_east for t in usable)
    r_north = sum(t.weight * t.t_hat_north for t in usable)
    magnitude = math.hypot(r_east, r_north)
    relative_magnitude = magnitude / total_mass

    clarity = relative_magnitude
    if clarity > 1.0:
        overshoot = clarity - 1.0
        if overshoot > CLARITY_RANGE_CLAMP_TOLERANCE:
            raise ValueError(
                f"directional_clarity {clarity!r} exceeds 1.0 by more than CLARITY_RANGE_CLAMP_TOLERANCE="
                f"{CLARITY_RANGE_CLAMP_TOLERANCE!r} -- scientific invariant violated (weights/unit-vectors "
                "malformed upstream), never silently clamped"
            )
        clarity = 1.0
    elif clarity < 0.0:
        undershoot = -clarity
        if undershoot > CLARITY_RANGE_CLAMP_TOLERANCE:
            raise ValueError(
                f"directional_clarity {clarity!r} is below 0.0 by more than CLARITY_RANGE_CLAMP_TOLERANCE="
                f"{CLARITY_RANGE_CLAMP_TOLERANCE!r} -- scientific invariant violated, never silently clamped"
            )
        clarity = 0.0

    if relative_magnitude <= RESULTANT_RELATIVE_CANCELLATION_EPSILON:
        return ResultantVectorResult(
            resultant_east=r_east, resultant_north=r_north, bearing_deg=None, magnitude=magnitude,
            directional_clarity=clarity, cancellation_status=DIRECTIONAL_CONTRIBUTIONS_CANCELLED,
            n_terms_total=len(terms), n_terms_usable=len(usable), n_terms_excluded_zero_distance=n_excluded,
        )

    bearing = bearing_deg_from_components(r_east, r_north)
    return ResultantVectorResult(
        resultant_east=r_east, resultant_north=r_north, bearing_deg=bearing, magnitude=magnitude,
        directional_clarity=clarity, cancellation_status=DIRECTION_AVAILABLE,
        n_terms_total=len(terms), n_terms_usable=len(usable), n_terms_excluded_zero_distance=n_excluded,
    )
