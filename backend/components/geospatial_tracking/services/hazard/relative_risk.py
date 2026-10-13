"""Checkpoint 6C Parts 23-24 / Checkpoint 6C.5 Part 19-20: the bounded
relative-risk-index link, with explicit numerical-saturation status.

Because no calibrated prior `P_i_d` exists yet, this checkpoint
implements ONLY the baseline link:

    R_i = 1 - exp(-H_i)      (computed as -expm1(-H_i) for precision)

as a **BOUNDED RELATIVE RISK INDEX LINK** — never "infection
probability" or a calibrated epidemiological quantity. Properties:
`H=0 -> R=0` EXACTLY (no epsilon floor, Part 20); `H>=0 -> 0<=R<1`
mathematically; monotonically increasing; large `H` asymptotically
approaches (never reaches) 1.

**Numerical safety (Checkpoint 6C.5 Part 19)**: `-math.expm1(-H)` is
used instead of `1 - math.exp(-H)` — `expm1` avoids the catastrophic
cancellation that `1 - exp(-H)` suffers for small `H` (where `exp(-H)`
is close to 1). For sufficiently large `H` (roughly `H > 37`), even
`expm1` cannot avoid the fact that float64 has no representable value
between `1.0` and its next-lower neighbor at that magnitude — the
mathematically-correct-but-unrepresentable result rounds to exactly
`1.0`. Rather than silently returning that `1.0` (weakening the
declared `R<1` contract without saying so) or silently clamping,
`compute_relative_risk_index` returns a `RelativeRiskResult(value,
status)`: `status=FINITE_INTERIOR` for the ordinary case, and
`status=NUMERIC_SATURATION_ADJUSTED` when saturation is detected, in
which case `value` is nudged one float64 step below `1.0`
(`math.nextafter(1.0, 0.0)`) specifically so it never returns an
unlabeled exact `1.0`. This is a **numerical representation safeguard,
not epidemiological calibration** — it says nothing about the real
probability of an outbreak, only that this software will never emit an
unlabeled `1.0` for a genuinely finite hazard.

The later generalized expression `R = 1 - (1-P) * exp(-H)` may only be
activated after a separate, scientifically defined prior protocol —
`prior_relative_risk` is accepted only as `None` in this checkpoint; any
non-null value is rejected outright (Part 24:
`PRIOR_TERM_NOT_SCIENTIFICALLY_DEFINED`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .contracts import PRIOR_TERM_NOT_SCIENTIFICALLY_DEFINED, reject_non_finite

FINITE_INTERIOR = "FINITE_INTERIOR"
NUMERIC_SATURATION_ADJUSTED = "NUMERIC_SATURATION_ADJUSTED"


@dataclass(frozen=True)
class RelativeRiskResult:
    value: float
    status: str  # FINITE_INTERIOR | NUMERIC_SATURATION_ADJUSTED

    def as_dict(self) -> dict:
        return {"value": self.value, "status": self.status}


def compute_relative_risk_index(total_hazard: float, *, prior_relative_risk: float | None = None) -> RelativeRiskResult:
    """Pure. Raises `ValueError` on negative/non-finite `total_hazard`
    or any non-`None` `prior_relative_risk` (Part 24). Never silently
    clamps — saturation is always reported via `status`."""
    if prior_relative_risk is not None:
        raise ValueError(
            f"prior_relative_risk is {PRIOR_TERM_NOT_SCIENTIFICALLY_DEFINED} in Checkpoint 6C — must be None; "
            "the generalized 1-(1-P)*exp(-H) link may only be activated after a separate, scientifically "
            "defined prior protocol"
        )
    reject_non_finite("total_hazard", total_hazard)
    if total_hazard < 0:
        raise ValueError(f"total_hazard must be >= 0, got {total_hazard!r}")

    if total_hazard == 0.0:
        return RelativeRiskResult(0.0, FINITE_INTERIOR)  # Part 20: exact zero, no epsilon floor

    r = -math.expm1(-total_hazard)
    if math.isnan(r) or r < 0.0 or r > 1.0:
        raise ValueError(f"relative_risk_index evaluated outside [0, 1] ({r!r}) — never silently clamped")

    if r < 1.0:
        return RelativeRiskResult(r, FINITE_INTERIOR)

    # r == 1.0 exactly: float64 cannot represent the true (finite, <1)
    # mathematical value at this magnitude of H -- explicit saturation,
    # never an unlabeled exact 1.0.
    adjusted = math.nextafter(1.0, 0.0)
    return RelativeRiskResult(adjusted, NUMERIC_SATURATION_ADJUSTED)
