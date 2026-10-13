"""Checkpoint 6C.5 Parts 6-7 / Checkpoint 6D Part 0E: explicit
cell-indexed meteorology with explicit spatial provenance.

Checkpoint 6C's `build_hazard_snapshot` accepted a single `wind`/
`wind_speed_factor` pair for the entire snapshot — a convenient
representation of a deliberately UNIFORM meteorological field, but an
API that did not say so explicitly, and would silently keep "working"
even if a future caller expected per-cell resolution. `CellMeteorology`
makes the cell index explicit and mandatory; `expand_uniform_meteorology`
is the ONLY way to populate it from one shared vector, and it must be
called explicitly — the repetition across cells is visible in the
resulting `wind_by_cell` mapping, never implicit.

**Spatial provenance (Checkpoint 6D Part 0E)**: identical `(u10, v10)`
values reached through different spatial-resolution semantics are
SCIENTIFICALLY DIFFERENT inputs — a software fixture, a single real
AOI-center observation stretched across many cells, and genuine
per-cell sampling are not interchangeable claims about what is known.
`CellMeteorology.spatial_mode` records which one applies, and it
participates in `hazard_input_signature_hash` for exactly that reason.
`SPATIALLY_RESOLVED_REAL` must never be used unless real per-cell
sampling actually exists — Checkpoint 6D does not build that sampling,
so no code in this repository may construct a `CellMeteorology` with
that mode yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .contracts import FactorValue, WindVector


class MeteorologySpatialMode(str, Enum):
    """`UNIFORM_FIELD_FIXTURE`: a software-fixture vector explicitly
    expanded to every requested cell (6C.5). `AOI_CENTER_UNIFORM_REAL_PROXY`
    (6D): one REAL weather observation, sampled once at the AOI center,
    expanded across cells — a real value, but NOT independently sampled
    per cell; never claim more spatial resolution than this actually
    has. `SPATIALLY_RESOLVED_REAL` (6D, reserved): genuine per-cell real
    meteorology — must never be used until real per-cell retrieval
    exists and is tested; no code constructs this mode yet."""

    UNIFORM_FIELD_FIXTURE = "UNIFORM_FIELD_FIXTURE"
    AOI_CENTER_UNIFORM_REAL_PROXY = "AOI_CENTER_UNIFORM_REAL_PROXY"
    SPATIALLY_RESOLVED_REAL = "SPATIALLY_RESOLVED_REAL"


_KNOWN_MODES = {m.value for m in MeteorologySpatialMode}


@dataclass(frozen=True)
class CellMeteorology:
    grid_cell_id: str
    wind_vector: WindVector
    wind_speed_factor: FactorValue
    spatial_mode: str = MeteorologySpatialMode.UNIFORM_FIELD_FIXTURE.value

    def __post_init__(self) -> None:
        if not isinstance(self.wind_vector, WindVector):
            raise TypeError(f"wind_vector must be a WindVector, got {type(self.wind_vector)!r}")
        if not isinstance(self.wind_speed_factor, FactorValue):
            raise TypeError(f"wind_speed_factor must be a FactorValue, got {type(self.wind_speed_factor)!r}")
        if self.spatial_mode not in _KNOWN_MODES:
            raise ValueError(f"unknown meteorology spatial mode {self.spatial_mode!r} — must be one of {sorted(_KNOWN_MODES)}")


def expand_uniform_meteorology(
    *,
    grid_cell_ids: list,
    wind: WindVector,
    wind_speed_factor: FactorValue,
    mode: str = MeteorologySpatialMode.UNIFORM_FIELD_FIXTURE.value,
) -> dict:
    """The ONLY function that turns one shared `(wind, wind_speed_factor)`
    pair into a `{grid_cell_id: CellMeteorology}` mapping — the
    repetition is explicit in both the function name and the resulting
    mapping's contents, never hidden behind a "just pass one wind"
    convenience path deeper in the hazard engine.

    `mode` may be `UNIFORM_FIELD_FIXTURE` (software fixture) or
    `AOI_CENTER_UNIFORM_REAL_PROXY` (one real AOI-center observation
    stretched across cells) — never `SPATIALLY_RESOLVED_REAL`, since
    that claims per-cell sampling this function does not perform."""
    if mode == MeteorologySpatialMode.SPATIALLY_RESOLVED_REAL.value:
        raise ValueError(
            "expand_uniform_meteorology must never be called with SPATIALLY_RESOLVED_REAL — that mode claims "
            "genuine per-cell sampling, which this function (expanding ONE shared vector) does not perform"
        )
    if mode not in _KNOWN_MODES:
        raise ValueError(f"unknown meteorology spatial mode {mode!r} — must be one of {sorted(_KNOWN_MODES)}")
    return {
        grid_cell_id: CellMeteorology(grid_cell_id=grid_cell_id, wind_vector=wind, wind_speed_factor=wind_speed_factor, spatial_mode=mode)
        for grid_cell_id in grid_cell_ids
    }
