"""Checkpoint 6C.5 Part 22: pathway index tests — INDEX-01..06.
(INDEX-07 lives in test_hazard_no_forbidden_modeling.py.)"""

from __future__ import annotations

from components.geospatial_tracking.services.hazard.contracts import (
    CellHazardFactors,
    FactorStatus,
    FactorValue,
    HazardMixConfig,
    SourceGeometry,
    SourceHazardFactors,
)
from components.geospatial_tracking.services.hazard.protocol import HazardConfig
from components.geospatial_tracking.services.hazard.source_hazard import compute_source_hazard

_FIXTURE = FactorStatus.SOFTWARE_FIXTURE_ONLY.value


def _fv(v: float) -> FactorValue:
    return FactorValue(v, _FIXTURE)


def _config() -> HazardConfig:
    return HazardConfig(
        local_kernel_family="EXPONENTIAL", local_kernel_distance_scale_km=10.0,
        anisotropic_pathway_enabled=False, anisotropy_mode="MODULATING", anisotropy_kappa=1.0,
        wind_kernel_family="EXPONENTIAL", wind_kernel_distance_scale_km=10.0,
        mix=HazardMixConfig(local_weight=1.0, anisotropic_weight=0.0),
    )


def _contribution(source_id: str, cell_factors: CellHazardFactors, strength: float, distance_km: float = 5.0):
    geometry = SourceGeometry(source_id, cell_factors.grid_cell_id, distance_km=distance_km, t_hat_east=1.0, t_hat_north=0.0)
    source_factors = SourceHazardFactors(source_id, source_strength_factor=_fv(strength))
    return compute_source_hazard(geometry=geometry, cell_factors=cell_factors, source_factors=source_factors, config=_config())


def test_index_01_same_cell_three_sources_identical_host_factor():
    cell = CellHazardFactors("CELL1", host_factor=_fv(0.77), environmental_suitability_factor=_fv(0.5), water_context_factor=_fv(0.4))
    contribs = [_contribution(sid, cell, strength) for sid, strength in (("A", 1.0), ("B", 0.5), ("C", 2.0))]
    hosts = {c.local_pathway_components["host_factor"] for c in contribs}
    assert hosts == {0.77}


def test_index_02_same_cell_three_sources_identical_environmental_factor():
    cell = CellHazardFactors("CELL1", host_factor=_fv(0.6), environmental_suitability_factor=_fv(0.33), water_context_factor=_fv(0.4))
    contribs = [_contribution(sid, cell, strength) for sid, strength in (("A", 1.0), ("B", 0.5), ("C", 2.0))]
    envs = {c.local_pathway_components["environmental_suitability_factor"] for c in contribs}
    assert envs == {0.33}


def test_index_03_same_cell_three_sources_identical_water_context_factor():
    cell = CellHazardFactors("CELL1", host_factor=_fv(0.6), environmental_suitability_factor=_fv(0.5), water_context_factor=_fv(0.91))
    config = HazardConfig(
        local_kernel_family="EXPONENTIAL", local_kernel_distance_scale_km=10.0,
        anisotropic_pathway_enabled=True, anisotropy_mode="MODULATING", anisotropy_kappa=1.0,
        wind_kernel_family="EXPONENTIAL", wind_kernel_distance_scale_km=10.0,
        mix=HazardMixConfig(local_weight=1.0, anisotropic_weight=1.0),
    )
    from components.geospatial_tracking.services.hazard.contracts import WindVector

    wind = WindVector(u10=2.0, v10=0.0)
    wsf = _fv(1.0)
    waters = set()
    for sid, strength in (("A", 1.0), ("B", 0.5), ("C", 2.0)):
        geometry = SourceGeometry(sid, "CELL1", distance_km=5.0, t_hat_east=1.0, t_hat_north=0.0)
        source_factors = SourceHazardFactors(sid, source_strength_factor=_fv(strength))
        c = compute_source_hazard(geometry=geometry, cell_factors=cell, source_factors=source_factors, config=config, wind=wind, wind_speed_factor=wsf)
        waters.add(c.anisotropic_pathway_components["water_context_factor"])
    assert waters == {0.91}


def test_index_04_different_cells_may_have_different_cell_factors():
    cell_n = CellHazardFactors("CELL_N", host_factor=_fv(0.9), environmental_suitability_factor=_fv(0.7), water_context_factor=_fv(0.6))
    cell_s = CellHazardFactors("CELL_S", host_factor=_fv(0.2), environmental_suitability_factor=_fv(0.3), water_context_factor=_fv(0.1))
    c_n = _contribution("A", cell_n, 1.0)
    c_s = _contribution("A", cell_s, 1.0)
    assert c_n.local_pathway_components["host_factor"] != c_s.local_pathway_components["host_factor"]


def test_index_05_source_strength_may_differ_between_sources():
    cell = CellHazardFactors("CELL1", host_factor=_fv(0.6), environmental_suitability_factor=_fv(0.5), water_context_factor=_fv(0.4))
    c_a = _contribution("A", cell, 1.0)
    c_b = _contribution("B", cell, 0.3)
    assert c_a.local_pathway_components["source_strength_factor"] != c_b.local_pathway_components["source_strength_factor"]
    assert c_a.source_hazard != c_b.source_hazard


def test_index_06_changing_source_a_strength_does_not_alter_source_b():
    cell = CellHazardFactors("CELL1", host_factor=_fv(0.6), environmental_suitability_factor=_fv(0.5), water_context_factor=_fv(0.4))
    c_b_before = _contribution("B", cell, 0.5)
    # constructing a NEW, differently-strengthed A contribution must not
    # mutate B's already-computed, independently-owned SourceHazardFactors
    _ = _contribution("A", cell, 9.99)
    c_b_after = _contribution("B", cell, 0.5)
    assert c_b_before.source_hazard == c_b_after.source_hazard
    assert c_b_before.local_pathway_components["source_strength_factor"] == 0.5
    assert c_b_after.local_pathway_components["source_strength_factor"] == 0.5
