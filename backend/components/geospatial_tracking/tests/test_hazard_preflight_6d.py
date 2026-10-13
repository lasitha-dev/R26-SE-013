"""Checkpoint 6D Part 0/31: 6C.5 input-contract hardening — PRE6D-01..07."""

from __future__ import annotations

import pytest

from components.geospatial_tracking.services.hazard.contracts import (
    CellHazardFactors,
    FactorStatus,
    FactorValue,
    HazardMixConfig,
    SourceGeometry,
    SourceHazardFactors,
    WindVector,
)
from components.geospatial_tracking.services.hazard.meteorology import CellMeteorology, MeteorologySpatialMode, expand_uniform_meteorology
from components.geospatial_tracking.services.hazard.protocol import HazardConfig
from components.geospatial_tracking.services.hazard.snapshot import build_hazard_snapshot, compute_hazard_input_signature_hash

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


def _base_kwargs(**overrides):
    geometry = SourceGeometry("A", "CELL1", distance_km=5.0, t_hat_east=1.0, t_hat_north=0.0)
    wind_by_cell = expand_uniform_meteorology(grid_cell_ids=["CELL1"], wind=WindVector(2.0, 0.0), wind_speed_factor=_fv(1.0))
    fields = dict(
        forecast_origin_id="O1", t0="2021-01-01", feature_snapshot_id="SNAPSHOT:abc",
        active_source_ids=["A"], expected_grid_cell_ids=["CELL1"],
        geometry_by_cell={"CELL1": {"A": geometry}},
        cell_factors_by_cell={"CELL1": _cell_factors("CELL1")},
        source_factors_by_source={"A": SourceHazardFactors("A", source_strength_factor=_fv(1.0))},
        config=_config(), wind_by_cell=wind_by_cell,
    )
    fields.update(overrides)
    return fields


def test_pre6d_01_duplicate_expected_grid_cell_ids_rejected():
    kwargs = _base_kwargs(expected_grid_cell_ids=["CELL1", "CELL1"])
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)


def test_pre6d_02_geometry_map_with_non_expected_cell_rejected():
    kwargs = _base_kwargs()
    kwargs["geometry_by_cell"]["CELL_EXTRA"] = {"A": SourceGeometry("A", "CELL_EXTRA", distance_km=5.0, t_hat_east=1.0, t_hat_north=0.0)}
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)


def test_pre6d_03_cell_factor_map_with_non_expected_cell_rejected():
    kwargs = _base_kwargs()
    kwargs["cell_factors_by_cell"]["CELL_EXTRA"] = _cell_factors("CELL_EXTRA")
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)


def test_pre6d_04_meteorology_map_with_non_expected_cell_rejected():
    kwargs = _base_kwargs()
    kwargs["wind_by_cell"]["CELL_EXTRA"] = CellMeteorology("CELL_EXTRA", wind_vector=WindVector(1.0, 1.0), wind_speed_factor=_fv(1.0))
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)


def test_pre6d_05_source_hazard_factors_id_must_match_mapping_key():
    kwargs = _base_kwargs()
    kwargs["source_factors_by_source"] = {"A": SourceHazardFactors("WRONG_ID", source_strength_factor=_fv(1.0))}
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)


def test_pre6d_06_cell_meteorology_id_must_match_mapping_key():
    kwargs = _base_kwargs()
    kwargs["wind_by_cell"] = {"CELL1": CellMeteorology("WRONG_ID", wind_vector=WindVector(2.0, 0.0), wind_speed_factor=_fv(1.0))}
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)


def test_pre6d_07_meteorology_spatial_mode_changes_hazard_input_signature():
    geometry_by_cell = {"CELL1": {"A": SourceGeometry("A", "CELL1", distance_km=5.0, t_hat_east=1.0, t_hat_north=0.0)}}
    cell_factors_by_cell = {"CELL1": _cell_factors("CELL1")}
    source_factors_by_source = {"A": SourceHazardFactors("A", source_strength_factor=_fv(1.0))}
    wind = WindVector(2.0, 0.0)
    wsf = _fv(1.0)

    fixture_wind = expand_uniform_meteorology(grid_cell_ids=["CELL1"], wind=wind, wind_speed_factor=wsf, mode=MeteorologySpatialMode.UNIFORM_FIELD_FIXTURE.value)
    proxy_wind = expand_uniform_meteorology(grid_cell_ids=["CELL1"], wind=wind, wind_speed_factor=wsf, mode=MeteorologySpatialMode.AOI_CENTER_UNIFORM_REAL_PROXY.value)

    sig_fixture = compute_hazard_input_signature_hash(
        expected_grid_cell_ids=["CELL1"], active_source_ids=["A"], cell_factors_by_cell=cell_factors_by_cell,
        source_factors_by_source=source_factors_by_source, geometry_by_cell=geometry_by_cell, wind_by_cell=fixture_wind,
    )
    sig_proxy = compute_hazard_input_signature_hash(
        expected_grid_cell_ids=["CELL1"], active_source_ids=["A"], cell_factors_by_cell=cell_factors_by_cell,
        source_factors_by_source=source_factors_by_source, geometry_by_cell=geometry_by_cell, wind_by_cell=proxy_wind,
    )
    assert sig_fixture != sig_proxy


def test_expand_uniform_meteorology_rejects_spatially_resolved_real():
    with pytest.raises(ValueError):
        expand_uniform_meteorology(
            grid_cell_ids=["CELL1"], wind=WindVector(1.0, 1.0), wind_speed_factor=_fv(1.0),
            mode=MeteorologySpatialMode.SPATIALLY_RESOLVED_REAL.value,
        )


def test_valid_complete_snapshot_still_works_after_hardening():
    snap = build_hazard_snapshot(**_base_kwargs())
    assert snap.status == "COMPLETE"
