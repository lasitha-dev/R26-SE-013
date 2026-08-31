"""Checkpoint 6C Parts 9-13: meteorological alignment and the
anisotropy primitive.

**Wind vector semantics (Part 9)**: `mean_u10`/`mean_v10` are
meteorological vector components — `u10` eastward, `v10` northward
(matching `geospatial/weather/wind.py`'s convention). They are NEVER
"disease direction." This module never reconstructs or averages compass
bearings — it works with `(u, v)` components directly throughout.

**`meteorological_alignment` (Part 10)**: for source `j` -> cell `i`,

    alignment = t_hat_east * wind_unit_east + t_hat_north * wind_unit_north

clamped only for floating-point safety to `[-1, 1]`. `+1` means the
cell lies directly down-vector (in the direction the wind blows
toward); `0` perpendicular; `-1` directly up-vector. This value is
called `meteorological_alignment` — NEVER "disease spread direction,"
"transmission bearing," or "confidence."

**Calm wind (Part 11)**: if the wind vector's magnitude is effectively
zero, direction is undefined — this module never divides by zero and
never invents a direction. It returns `alignment=None`,
`status=CALM_NEUTRAL`, and the anisotropy factor is exactly `1.0`.

**Anisotropy modes (Part 12-13)**: `A(alignment, kappa) = exp(kappa *
alignment)` is `MODULATING` — it changes total angular mass as `kappa`
changes (its average over a uniform angular distribution is
`I0(kappa)`, the modified Bessel function of the first kind, order 0,
which grows with `kappa`). `ANGULAR_NORMALIZED` divides by that same
`I0(kappa)` so the direction-averaged mass stays 1 regardless of
`kappa` — a genuinely different candidate semantic, never silently
mixed with `MODULATING`. Both agree (`A=1` everywhere) at `kappa=0`.
`kappa` (`anisotropy_strength`) is UNFROZEN — never called "wind
transmission coefficient."
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .contracts import AnisotropyMode, WindVector, reject_non_finite

CALM_WIND_EPSILON_M_S = 1e-6
CALM_NEUTRAL = "CALM_NEUTRAL"
DIRECTIONAL = "DIRECTIONAL"

_KNOWN_MODES = {m.value for m in AnisotropyMode}


@dataclass(frozen=True)
class AlignmentResult:
    alignment: float | None  # None exactly when status == CALM_NEUTRAL
    status: str  # DIRECTIONAL | CALM_NEUTRAL

    def as_dict(self) -> dict:
        return {"meteorological_alignment": self.alignment, "status": self.status}


@dataclass(frozen=True)
class AnisotropyResult:
    anisotropy_factor: float
    status: str  # DIRECTIONAL | CALM_NEUTRAL
    mode: str
    kappa: float

    def as_dict(self) -> dict:
        return {
            "anisotropy_factor": self.anisotropy_factor,
            "status": self.status,
            "mode": self.mode,
            "anisotropy_strength": self.kappa,
        }


def compute_meteorological_alignment(*, t_hat_east: float, t_hat_north: float, wind: WindVector) -> AlignmentResult:
    """Pure. Part 11's calm-wind guard — never a `ZeroDivisionError`,
    never a fabricated direction."""
    reject_non_finite("t_hat_east", t_hat_east)
    reject_non_finite("t_hat_north", t_hat_north)
    magnitude = math.hypot(wind.u10, wind.v10)
    if magnitude < CALM_WIND_EPSILON_M_S:
        return AlignmentResult(alignment=None, status=CALM_NEUTRAL)
    wind_unit_east = wind.u10 / magnitude
    wind_unit_north = wind.v10 / magnitude
    raw = t_hat_east * wind_unit_east + t_hat_north * wind_unit_north
    clamped = max(-1.0, min(1.0, raw))
    return AlignmentResult(alignment=clamped, status=DIRECTIONAL)


def _bessel_i0(x: float) -> float:
    """Modified Bessel function of the first kind, order 0, via its
    convergent power series — a self-contained implementation (no new
    dependency) used only by `ANGULAR_NORMALIZED` mode's mass
    normalization. Accurate to double-precision for the moderate
    `kappa` ranges relevant to a development-only anisotropy strength
    parameter."""
    if x == 0.0:
        return 1.0
    half_x_sq = (x / 2.0) ** 2
    term = 1.0
    total = 1.0
    k = 1
    while k <= 200:
        term *= half_x_sq / (k * k)
        total += term
        if term < 1e-16 * total:
            break
        k += 1
    return total


def compute_anisotropy_factor(alignment_result: AlignmentResult, *, kappa: float, mode: str) -> AnisotropyResult:
    """Pure. `kappa >= 0` required (Part 12). Calm wind always yields
    the neutral factor `1.0` regardless of `kappa`/`mode` (Part 11)."""
    reject_non_finite("kappa", kappa)
    if kappa < 0:
        raise ValueError(f"kappa (anisotropy strength) must be >= 0, got {kappa!r}")
    if mode not in _KNOWN_MODES:
        raise ValueError(f"unknown anisotropy mode {mode!r} — must be one of {sorted(_KNOWN_MODES)}")

    if alignment_result.status == CALM_NEUTRAL:
        return AnisotropyResult(anisotropy_factor=1.0, status=CALM_NEUTRAL, mode=mode, kappa=kappa)

    alignment = alignment_result.alignment
    if mode == AnisotropyMode.MODULATING.value:
        factor = math.exp(kappa * alignment)
    else:  # ANGULAR_NORMALIZED
        factor = math.exp(kappa * alignment) / _bessel_i0(kappa)

    if math.isnan(factor) or math.isinf(factor) or factor < 0:
        raise ValueError(f"anisotropy factor evaluated to a non-finite/negative value ({factor!r}) — never silently repaired")
    return AnisotropyResult(anisotropy_factor=factor, status=DIRECTIONAL, mode=mode, kappa=kappa)
