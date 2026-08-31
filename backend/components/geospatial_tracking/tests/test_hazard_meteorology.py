"""Checkpoint 6C.5 Part 24: meteorology index tests — WX-HAZ-01..05."""

from __future__ import annotations

from components.geospatial_tracking.services.hazard.contracts import (
    CELL_HAZARD_INCOMPLETE,
    COMPLETE,
    CellHazardFactors,
    FactorStatus,
    FactorValue,
    HazardMixConfig,
    SourceGeometry,
    SourceHazardFactors,
    WindVector,
)
from components.geospatial_tracking.services.hazard.meteorology import CellMeteorology, expand_uniform_meteorology
from components.geospatial_tracking.services.hazard.protocol import HazardConfig
from components.geospatial_tracking.services.hazard.snapshot import build_hazard_snapshot

_FIXTURE = FactorStatus.SOFTWARE_FIXTURE_ONLY.value


def _fv(v: float) -> FactorValue:
    return FactorValue(v, _FIXTURE)


def _cell_factors(cell_id: str) -> CellHazardFactors:
    return CellHazardFactors(cell_id, host_factor=_fv(0.8), environmental_suitability_factor=_fv(0.6), water_context_factor=_fv(0.5))


def _config(anisotropic_enabled: bool = True) -> HazardConfig:
    return HazardConfig(
        local_kernel_family="EXPONENTIAL", local_kernel_distance_scale_km=10.0,
        anisotropic_pathway_enabled=anisotropic_enabled, anisotropy_mode="MODULATING", anisotropy_kappa=1.0,
        wind_kernel_family="EXPONENTIAL", wind_kernel_distance_scale_km=10.0,
        mix=HazardMixConfig(local_weight=1.0, anisotropic_weight=1.0),
    )


def test_wx_haz_01_wind_is_explicitly_cell_indexed():
    cm = CellMeteorology("CELL1", wind_vector=WindVector(2.0, 0.0), wind_speed_factor=_fv(1.0))
    assert cm.grid_cell_id == "CELL1"


def test_wx_haz_02_uniform_fixture_mode_expands_explicitly():
    wind = WindVector(3.0, 4.0)
    wsf = _fv(1.0)
    wind_by_cell = expand_uniform_meteorology(grid_cell_ids=["CELL1", "CELL2", "CELL3"], wind=wind, wind_speed_factor=wsf)
    assert set(wind_by_cell.keys()) == {"CELL1", "CELL2", "CELL3"}
    for cell_id, cm in wind_by_cell.items():
        assert cm.grid_cell_id == cell_id
        assert cm.wind_vector is wind
        assert cm.wind_speed_factor is wsf


def test_wx_haz_03_different_cells_may_carry_different_wind_vectors():
    wind_by_cell = {
        "CELL1": CellMeteorology("CELL1", wind_vector=WindVector(5.0, 0.0), wind_speed_factor=_fv(1.0)),
        "CELL2": CellMeteorology("CELL2", wind_vector=WindVector(0.0, 5.0), wind_speed_factor=_fv(1.0)),
    }
    assert wind_by_cell["CELL1"].wind_vector != wind_by_cell["CELL2"].wind_vector


def _grid_kwargs(wind_by_cell):
    geometry = SourceGeometry("A", "CELL1", distance_km=5.0, t_hat_east=1.0, t_hat_north=0.0)
    return dict(
        forecast_origin_id="O1", t0="2021-01-01", feature_snapshot_id="SNAPSHOT:abc",
        active_source_ids=["A"], expected_grid_cell_ids=["CELL1"],
        geometry_by_cell={"CELL1": {"A": geometry}},
        cell_factors_by_cell={"CELL1": _cell_factors("CELL1")},
        source_factors_by_source={"A": SourceHazardFactors("A", source_strength_factor=_fv(1.0))},
        wind_by_cell=wind_by_cell,
    )


def test_wx_haz_04_missing_cell_wind_with_enabled_anisotropic_pathway_incomplete():
    snap = build_hazard_snapshot(**_grid_kwargs({}), config=_config(anisotropic_enabled=True))
    cell = snap.grid_cell_results[0]
    assert cell["status"] == CELL_HAZARD_INCOMPLETE
    assert any("wind_vector" in m for m in cell["missing_requirements"])


def test_wx_haz_05_missing_wind_irrelevant_when_pathway_disabled():
    snap = build_hazard_snapshot(**_grid_kwargs({}), config=_config(anisotropic_enabled=False))
    cell = snap.grid_cell_results[0]
    assert cell["status"] == COMPLETE
