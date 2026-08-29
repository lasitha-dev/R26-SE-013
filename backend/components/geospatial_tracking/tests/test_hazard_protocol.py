"""Checkpoint 6C Parts 18, 30, 32 / Checkpoint 6C.5 Parts 14-15:
HazardMixConfig / HazardConfig / HazardSnapshot identity contracts.

SUPERSEDED_BY_6C5_INDEX_CORRECTION: `build_hazard_snapshot` now takes
`expected_grid_cell_ids`/`cell_factors_by_cell`/`source_factors_by_source`/
`wind_by_cell` instead of a combined `factors_by_source`/single `wind`
— rewritten below.
"""

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
from components.geospatial_tracking.services.hazard.meteorology import expand_uniform_meteorology
from components.geospatial_tracking.services.hazard.protocol import HazardConfig
from components.geospatial_tracking.services.hazard.snapshot import build_hazard_snapshot, compute_hazard_snapshot_id

_FIXTURE = FactorStatus.SOFTWARE_FIXTURE_ONLY.value


def _fv(v: float) -> FactorValue:
    return FactorValue(v, _FIXTURE)


def _mix(**overrides) -> HazardMixConfig:
    fields = dict(local_weight=1.0, anisotropic_weight=0.0, parameter_status="UNFROZEN_DEVELOPMENT_CANDIDATE")
    fields.update(overrides)
    return HazardMixConfig(**fields)


def _config(**overrides) -> HazardConfig:
    fields = dict(
        local_kernel_family="EXPONENTIAL", local_kernel_distance_scale_km=10.0,
        anisotropic_pathway_enabled=False, anisotropy_mode="MODULATING", anisotropy_kappa=1.0,
        wind_kernel_family="EXPONENTIAL", wind_kernel_distance_scale_km=10.0,
        mix=_mix(),
    )
    fields.update(overrides)
    return HazardConfig(**fields)


def test_mix_config_rejects_frozen_reference():
    with pytest.raises(ValueError):
        _mix(parameter_status="FROZEN_REFERENCE")


def test_mix_config_accepts_software_fixture_and_unfrozen():
    _mix(parameter_status="SOFTWARE_FIXTURE_ONLY")
    _mix(parameter_status="UNFROZEN_DEVELOPMENT_CANDIDATE")


def test_mix_config_rejects_negative_weight():
    with pytest.raises(ValueError):
        _mix(local_weight=-1.0)


def test_hazard_config_rejects_frozen_reference():
    with pytest.raises(ValueError):
        _config(parameter_status="FROZEN_REFERENCE")


def test_hazard_config_hash_deterministic():
    c1 = _config()
    c2 = _config()
    assert c1.config_hash() == c2.config_hash()


def test_hazard_config_hash_changes_with_kappa():
    c1 = _config(anisotropy_kappa=1.0)
    c2 = _config(anisotropy_kappa=2.0)
    assert c1.config_hash() != c2.config_hash()


def test_hazard_config_hash_changes_with_kernel_family():
    c1 = _config(local_kernel_family="EXPONENTIAL")
    c2 = _config(local_kernel_family="GAUSSIAN")
    assert c1.config_hash() != c2.config_hash()


def test_hazard_config_hash_changes_with_anisotropic_enabled():
    c1 = _config(anisotropic_pathway_enabled=True)
    c2 = _config(anisotropic_pathway_enabled=False)
    assert c1.config_hash() != c2.config_hash()


def test_hazard_config_hash_never_includes_generated_at():
    assert "generated_at" not in _config().config_dict()


def test_hazard_config_rejects_nonpositive_kernel_scale():
    with pytest.raises(ValueError):
        _config(local_kernel_distance_scale_km=0.0)


def test_hazard_config_rejects_negative_kappa():
    with pytest.raises(ValueError):
        _config(anisotropy_kappa=-1.0)


def _cell_factors(cell_id="CELL1") -> CellHazardFactors:
    return CellHazardFactors(cell_id, host_factor=_fv(0.8), environmental_suitability_factor=_fv(0.6), water_context_factor=_fv(0.5))


def _source_factors(source_id="A") -> SourceHazardFactors:
    return SourceHazardFactors(source_id, source_strength_factor=_fv(1.0))


def _snapshot_kwargs(**overrides):
    geometry = SourceGeometry("A", "CELL1", distance_km=5.0, t_hat_east=1.0, t_hat_north=0.0)
    fields = dict(
        forecast_origin_id="O1", t0="2021-01-01", feature_snapshot_id="SNAPSHOT:abc",
        active_source_ids=["A"], expected_grid_cell_ids=["CELL1"],
        geometry_by_cell={"CELL1": {"A": geometry}},
        cell_factors_by_cell={"CELL1": _cell_factors()},
        source_factors_by_source={"A": _source_factors()},
        config=_config(),
    )
    fields.update(overrides)
    return fields


def test_snapshot_id_deterministic_same_inputs():
    id1 = compute_hazard_snapshot_id(
        feature_snapshot_id="SNAPSHOT:abc", active_source_ids=["A", "B"], expected_grid_cell_ids=["CELL1"],
        hazard_config_hash="hash1", hazard_input_signature_hash="sig1",
    )
    id2 = compute_hazard_snapshot_id(
        feature_snapshot_id="SNAPSHOT:abc", active_source_ids=["B", "A"], expected_grid_cell_ids=["CELL1"],
        hazard_config_hash="hash1", hazard_input_signature_hash="sig1",
    )
    assert id1 == id2  # order of active_source_ids must not matter


def test_snapshot_id_changes_with_config_hash():
    id1 = compute_hazard_snapshot_id(
        feature_snapshot_id="SNAPSHOT:abc", active_source_ids=["A"], expected_grid_cell_ids=["CELL1"],
        hazard_config_hash="hash1", hazard_input_signature_hash="sig1",
    )
    id2 = compute_hazard_snapshot_id(
        feature_snapshot_id="SNAPSHOT:abc", active_source_ids=["A"], expected_grid_cell_ids=["CELL1"],
        hazard_config_hash="hash2", hazard_input_signature_hash="sig1",
    )
    assert id1 != id2


def test_st_cluster_snapshot_id_has_zero_numeric_influence():
    snap_without = build_hazard_snapshot(**_snapshot_kwargs(st_cluster_snapshot_id=None))
    snap_with = build_hazard_snapshot(**_snapshot_kwargs(st_cluster_snapshot_id="STCLUSTER:xyz"))
    assert snap_without.grid_cell_results == snap_with.grid_cell_results
    assert snap_without.hazard_config_hash == snap_with.hazard_config_hash
    assert snap_without.hazard_input_signature_hash == snap_with.hazard_input_signature_hash
    assert snap_without.hazard_snapshot_id == snap_with.hazard_snapshot_id  # identity excludes ST cluster id
    assert snap_with.st_cluster_snapshot_id == "STCLUSTER:xyz"
