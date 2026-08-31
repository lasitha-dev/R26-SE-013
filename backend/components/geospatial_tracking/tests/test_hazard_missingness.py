"""Checkpoint 6C Part 37 / Checkpoint 6C.5: missingness tests —
HAZMISS-01..07.

SUPERSEDED_BY_6C5_INDEX_CORRECTION: rewritten to use the corrected
`CellHazardFactors`/`SourceHazardFactors` split instead of the legacy
combined `HazardFactors` bag.
"""

from __future__ import annotations

import pytest

from components.geospatial_tracking.services.hazard.contracts import (
    DISABLED_BY_CONFIG,
    SOURCE_HAZARD_INCOMPLETE,
    CellHazardFactors,
    FactorStatus,
    FactorValue,
    HazardMixConfig,
    SourceGeometry,
    SourceHazardFactors,
)
from components.geospatial_tracking.services.hazard.protocol import HazardConfig
from components.geospatial_tracking.services.hazard.source_hazard import compute_source_hazard

_REAL = FactorStatus.SOFTWARE_FIXTURE_ONLY.value


def _real(value: float) -> FactorValue:
    return FactorValue(value, _REAL)


def _geometry() -> SourceGeometry:
    return SourceGeometry("A", "CELL1", distance_km=5.0, t_hat_east=1.0, t_hat_north=0.0)


def _source_factors(strength: float = 1.0) -> SourceHazardFactors:
    return SourceHazardFactors("A", source_strength_factor=_real(strength))


def _local_only_config() -> HazardConfig:
    return HazardConfig(
        local_kernel_family="EXPONENTIAL", local_kernel_distance_scale_km=10.0,
        anisotropic_pathway_enabled=False, anisotropy_mode="MODULATING", anisotropy_kappa=1.0,
        wind_kernel_family="EXPONENTIAL", wind_kernel_distance_scale_km=10.0,
        mix=HazardMixConfig(local_weight=1.0, anisotropic_weight=0.0),
    )


def _aniso_config() -> HazardConfig:
    return HazardConfig(
        local_kernel_family="EXPONENTIAL", local_kernel_distance_scale_km=10.0,
        anisotropic_pathway_enabled=True, anisotropy_mode="MODULATING", anisotropy_kappa=1.0,
        wind_kernel_family="EXPONENTIAL", wind_kernel_distance_scale_km=10.0,
        mix=HazardMixConfig(local_weight=1.0, anisotropic_weight=1.0),
    )


@pytest.mark.parametrize("status", [FactorStatus.MISSING.value, FactorStatus.BLOCKED.value, FactorStatus.DEMO.value])
def test_hazmiss_01_02_03_04_missing_cell_factor_never_becomes_0_or_1(status):
    cell_factors = CellHazardFactors(
        "CELL1", host_factor=FactorValue(None, status),
        environmental_suitability_factor=_real(0.6), water_context_factor=_real(0.5),
    )
    result = compute_source_hazard(geometry=_geometry(), cell_factors=cell_factors, source_factors=_source_factors(), config=_local_only_config())
    assert result.status == SOURCE_HAZARD_INCOMPLETE
    assert result.source_hazard is None
    assert result.local_pathway_value is None
    assert any("host_factor" in m for m in result.missing_requirements)
    assert not isinstance(result.local_pathway_value, float)


def test_hazmiss_05_disabled_vs_missing_enabled_distinguishable():
    cell_factors = CellHazardFactors("CELL1", host_factor=_real(0.8), environmental_suitability_factor=_real(0.6), water_context_factor=_real(0.5))
    disabled = compute_source_hazard(geometry=_geometry(), cell_factors=cell_factors, source_factors=_source_factors(), config=_local_only_config())
    assert disabled.anisotropic_pathway_value == 0.0
    assert DISABLED_BY_CONFIG in disabled.notes
    assert disabled.status == "COMPLETE"

    missing_enabled = compute_source_hazard(
        geometry=_geometry(), cell_factors=cell_factors, source_factors=_source_factors(), config=_aniso_config(),
        wind=None, wind_speed_factor=None,
    )
    assert missing_enabled.status == SOURCE_HAZARD_INCOMPLETE
    assert missing_enabled.anisotropic_pathway_value is None
    assert DISABLED_BY_CONFIG not in missing_enabled.notes


def test_hazmiss_06_nan_rejected():
    with pytest.raises(ValueError):
        FactorValue(float("nan"), _REAL)


def test_hazmiss_07_infinity_rejected():
    with pytest.raises(ValueError):
        FactorValue(float("inf"), _REAL)


def test_missing_status_cannot_carry_a_value():
    with pytest.raises(ValueError):
        FactorValue(0.5, FactorStatus.MISSING.value)


def test_blocked_status_cannot_carry_a_value():
    with pytest.raises(ValueError):
        FactorValue(0.5, FactorStatus.BLOCKED.value)


def test_demo_status_cannot_be_used_in_scientific_hazard():
    cell_factors = CellHazardFactors(
        "CELL1", host_factor=FactorValue(None, FactorStatus.DEMO.value),
        environmental_suitability_factor=_real(0.6), water_context_factor=_real(0.5),
    )
    result = compute_source_hazard(geometry=_geometry(), cell_factors=cell_factors, source_factors=_source_factors(), config=_local_only_config())
    assert result.source_hazard is None
    assert result.status == SOURCE_HAZARD_INCOMPLETE


def test_anisotropic_missing_wind_vector_incomplete():
    cell_factors = CellHazardFactors("CELL1", host_factor=_real(0.8), environmental_suitability_factor=_real(0.6), water_context_factor=_real(0.5))
    result = compute_source_hazard(
        geometry=_geometry(), cell_factors=cell_factors, source_factors=_source_factors(), config=_aniso_config(),
        wind=None, wind_speed_factor=_real(1.0),
    )
    assert result.status == SOURCE_HAZARD_INCOMPLETE
    assert any("wind_vector" in m for m in result.missing_requirements)


def test_missing_source_strength_factor_incomplete():
    cell_factors = CellHazardFactors("CELL1", host_factor=_real(0.8), environmental_suitability_factor=_real(0.6), water_context_factor=_real(0.5))
    missing_source_factors = SourceHazardFactors("A", source_strength_factor=FactorValue(None, FactorStatus.MISSING.value))
    result = compute_source_hazard(geometry=_geometry(), cell_factors=cell_factors, source_factors=missing_source_factors, config=_local_only_config())
    assert result.status == SOURCE_HAZARD_INCOMPLETE
    assert any("source_strength_factor" in m for m in result.missing_requirements)
