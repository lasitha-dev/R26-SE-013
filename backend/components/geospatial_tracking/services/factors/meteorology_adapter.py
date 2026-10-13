"""Checkpoint 6D Part 19: real meteorology adapter.

Preserves the real, paired `u10`/`v10` components exactly as retrieved
— never converted into a compass bearing or "disease spread direction."
`wind_speed_effect` remains `NOT_YET_SELECTED` (no real `G(v)` is
invented here). If `FeatureSnapshot.weather` represents one AOI-center
observation (the current architecture, Checkpoint 5.5/5.6), this
adapter labels it explicitly `AOI_CENTER_UNIFORM_REAL_PROXY` — never
`SPATIALLY_RESOLVED_REAL`, since no independent per-cell sampling
exists. This module produces the factors package's OWN
`RealMeteorologyObservation` — it does NOT construct
`services.hazard.meteorology.CellMeteorology` (which would require a
`SOFTWARE_FIXTURE_ONLY` wind-speed factor and structurally cannot carry
a real status), keeping the hazard-engine firewall (Part 22) intact.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..hazard.meteorology import MeteorologySpatialMode
from .contracts import MISSING

WIND_SPEED_EFFECT_NOT_YET_SELECTED = "NOT_YET_SELECTED"


@dataclass(frozen=True)
class RealMeteorologyObservation:
    grid_cell_id: str
    u10: float | None
    u10_status: str
    v10: float | None
    v10_status: str
    spatial_mode: str
    dataset_name: str | None
    weather_model: str | None
    wind_speed_effect_status: str = WIND_SPEED_EFFECT_NOT_YET_SELECTED

    def as_dict(self) -> dict:
        return {
            "grid_cell_id": self.grid_cell_id, "u10": self.u10, "u10_status": self.u10_status,
            "v10": self.v10, "v10_status": self.v10_status, "spatial_mode": self.spatial_mode,
            "dataset_name": self.dataset_name, "weather_model": self.weather_model,
            "wind_speed_effect_status": self.wind_speed_effect_status,
        }


def build_meteorology_by_cell(snapshot: dict, *, expected_grid_cell_ids: list) -> dict:
    """One REAL AOI-center weather observation, explicitly expanded
    across `expected_grid_cell_ids` — the repetition is visible in the
    resulting mapping, and every entry carries
    `spatial_mode=AOI_CENTER_UNIFORM_REAL_PROXY` (never
    `SPATIALLY_RESOLVED_REAL`)."""
    weather = snapshot.get("weather") or {}
    results = weather.get("results") or {}
    window = weather.get("window") or {}
    u10_fr = results.get("mean_u10") or {}
    v10_fr = results.get("mean_v10") or {}
    u10_status = u10_fr.get("status", MISSING)
    v10_status = v10_fr.get("status", MISSING)

    out = {}
    for cell_id in expected_grid_cell_ids:
        out[cell_id] = RealMeteorologyObservation(
            grid_cell_id=cell_id,
            u10=u10_fr.get("value") if u10_status == "REAL" else None, u10_status=u10_status,
            v10=v10_fr.get("value") if v10_status == "REAL" else None, v10_status=v10_status,
            spatial_mode=MeteorologySpatialMode.AOI_CENTER_UNIFORM_REAL_PROXY.value,
            dataset_name=u10_fr.get("dataset_name") or v10_fr.get("dataset_name"),
            weather_model=window.get("weather_model"),
        )
    return out
