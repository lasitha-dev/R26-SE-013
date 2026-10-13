"""Checkpoint 9C Parts 2-5: deterministic nominal-reach derivation.

`nominal_reach_km(day_h) = frozen_S0_rate_km_day * day_h` -- a pure
positive linear transform of the already-frozen Checkpoint 9B apparent
local spread-front rate point estimate
(`services.model_development.rate_protocol_9b.EXPOSED_ESTIMATOR_VALUE_9B`).
This module reads no database, recomputes no geometry, and reruns no
bootstrap -- every function here is pure arithmetic over frozen
constants.

**NOMINAL is scientifically load-bearing** (Part 2). The label is
always `"Nominal Day-h local reach -- not a hard disease boundary"`.
This quantity is ONLY a deterministic visualization/context quantity.
It is NEVER: maximum LSD transmission distance, infection radius,
quarantine boundary, risk-surface boundary, probability contour,
guaranteed travel distance, or biological epidemic-front location.

**Hard separation from the frozen 25km operational local evaluation
envelope** (Part 3) --
`services.model_development.local_evaluation_scope.PRIMARY_LOCAL_EVALUATION_DISTANCE_KM`,
frozen since Checkpoint 7A.6: these are two DIFFERENT quantities that
must coexist. This module never imports that constant and never
clips/truncates/reconciles its own output against it -- Day 7 nominal
reach is EXPECTED to exceed 25km, and that is not an error.

**D1-D7 only** (Part 4): `PRIMARY_HORIZON_DAYS_9C = (1,2,3,4,5,6,7)`.
D8-D14 exploratory horizons are explicitly out of scope for this
checkpoint's primary contract -- `build_nominal_reach_by_day_9c` never
generates them.

**Interval is a pure multiplication of already-frozen 9B endpoints**
(Part 5) -- `derived_nominal_reach_interval` never calls
`run_bootstrap`/`compute_bootstrap_uncertainty` and accepts no raw
target-level data. The two endpoint constants below are copied from
the real, already-persisted
`local_data/model_development/9b_rate/s0_bootstrap_uncertainty_9b.json`
(`ci_lower_km_day`/`ci_upper_km_day`) -- never recomputed here.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..model_development.rate_protocol_9b import EXPOSED_ESTIMATOR_VALUE_9B

FROZEN_S0_RATE_KM_DAY_9C = EXPOSED_ESTIMATOR_VALUE_9B
FROZEN_BOOTSTRAP_LOWER_RATE_KM_DAY_9C = 3.5491046170907765
FROZEN_BOOTSTRAP_UPPER_RATE_KM_DAY_9C = 4.343077329563724

PRIMARY_HORIZON_DAYS_9C = (1, 2, 3, 4, 5, 6, 7)

NOMINAL_REACH_LABEL_9C = "Nominal Day-h local reach -- not a hard disease boundary"
NOMINAL_REACH_SEMANTICS_9C = "VISUALIZATION_ONLY_NOT_HARD_DISEASE_BOUNDARY"
NOMINAL_REACH_FORMULA_9C = "nominal_reach_km(day_h) = frozen_S0_rate_km_day * day_h"
DERIVED_INTERVAL_LABEL_9C = "Derived nominal-reach interval under the frozen 9B target-event bootstrap assumption"
DERIVED_INTERVAL_FORMULA_9C = (
    "nominal_reach_lower(day_h) = 9B_bootstrap_lower_rate*day_h; "
    "nominal_reach_upper(day_h) = 9B_bootstrap_upper_rate*day_h"
)


@dataclass(frozen=True)
class NominalReachDay9C:
    day: int
    nominal_reach_km: float
    derived_interval_lower_km: float | None
    derived_interval_upper_km: float | None

    def as_dict(self) -> dict:
        return {
            "day": self.day, "nominal_reach_km": self.nominal_reach_km,
            "derived_interval_lower_km": self.derived_interval_lower_km,
            "derived_interval_upper_km": self.derived_interval_upper_km,
        }


def nominal_reach_km(day_h: int, *, rate_km_day: float = FROZEN_S0_RATE_KM_DAY_9C) -> float:
    """Part 2. Never clipped/reconciled against the 25km envelope --
    callers must not min()/max() this against anything."""
    if day_h < 1:
        raise ValueError(f"nominal_reach_km: day_h must be >= 1, got {day_h}")
    return rate_km_day * day_h


def derived_nominal_reach_interval(
    day_h: int, *,
    lower_rate_km_day: float = FROZEN_BOOTSTRAP_LOWER_RATE_KM_DAY_9C,
    upper_rate_km_day: float = FROZEN_BOOTSTRAP_UPPER_RATE_KM_DAY_9C,
) -> tuple[float, float]:
    """Part 5. Pure multiplication of the two already-frozen 9B
    bootstrap endpoints -- never a new resample."""
    if day_h < 1:
        raise ValueError(f"derived_nominal_reach_interval: day_h must be >= 1, got {day_h}")
    return lower_rate_km_day * day_h, upper_rate_km_day * day_h


def build_nominal_reach_by_day_9c(*, include_derived_interval: bool = True) -> tuple[NominalReachDay9C, ...]:
    """D1-D7 ONLY (Part 4) -- never D8-D14 in this primary contract."""
    days: list[NominalReachDay9C] = []
    for day_h in PRIMARY_HORIZON_DAYS_9C:
        reach = nominal_reach_km(day_h)
        lower = upper = None
        if include_derived_interval:
            lower, upper = derived_nominal_reach_interval(day_h)
        days.append(NominalReachDay9C(
            day=day_h, nominal_reach_km=reach,
            derived_interval_lower_km=lower, derived_interval_upper_km=upper,
        ))
    return tuple(days)
