"""Checkpoint 6C Part 7-8: radial distance-kernel primitives.

Two candidate kernel families — neither scientifically frozen:

    EXPONENTIAL:  K(d; s) = exp(-d / s)
    GAUSSIAN:     K(d; s) = exp(-0.5 * (d / s)^2)

Both satisfy, by construction, for `d >= 0` and `s > 0`:

    K(0) = 1
    K(d) in (0, 1]
    monotonically non-increasing with distance
    finite and non-negative everywhere (NOFIT-07: no hard reach cutoff
    — a kernel evaluated at an arbitrarily large distance returns a
    small positive number, never a hard zero from a truncation rule)

`distance_scale_km` is a `UNFROZEN_DEVELOPMENT_PARAMETER` — this module
never calls it a "disease spread radius," "maximum transmission
distance," "predicted spread boundary," "nominal reach," or
"spread-front rate" (Part 8). It is purely the kernel's own
mathematical decay-length parameter.
"""

from __future__ import annotations

import math

from .contracts import KernelFamily, reject_non_finite

DISTANCE_SCALE_PARAMETER_STATUS = "UNFROZEN_DEVELOPMENT_PARAMETER"

_KNOWN_FAMILIES = {f.value for f in KernelFamily}


def evaluate_kernel(distance_km: float, *, family: str, distance_scale_km: float) -> float:
    """Pure. Raises `ValueError` on a negative distance, a non-positive
    scale, a non-finite input, or an unrecognized family — never
    silently coerces or clamps an invalid input (KERNEL-03/04)."""
    reject_non_finite("distance_km", distance_km)
    if distance_km < 0:
        raise ValueError(f"distance_km must be >= 0, got {distance_km!r}")
    reject_non_finite("distance_scale_km", distance_scale_km)
    if distance_scale_km <= 0:
        raise ValueError(f"distance_scale_km must be > 0, got {distance_scale_km!r}")
    if family not in _KNOWN_FAMILIES:
        raise ValueError(f"unknown kernel family {family!r} — must be one of {sorted(_KNOWN_FAMILIES)}")

    if family == KernelFamily.EXPONENTIAL.value:
        value = math.exp(-distance_km / distance_scale_km)
    else:  # GAUSSIAN
        value = math.exp(-0.5 * (distance_km / distance_scale_km) ** 2)

    # KERNEL-05: always finite and non-negative by construction (exp of
    # a real, non-positive argument) -- asserted defensively, never
    # silently repaired if it were ever violated.
    if math.isnan(value) or math.isinf(value) or value < 0:
        raise ValueError(f"kernel evaluated to a non-finite/negative value ({value!r}) — this indicates a bug, "
                          "never silently repaired")
    return value
