"""Checkpoint 6C.5 Part 23: grid completeness tests — GRID-HAZ-01..10."""

from __future__ import annotations

import pytest

from components.geospatial_tracking.services.hazard.contracts import (
    CELL_HAZARD_INCOMPLETE,
    COMPLETE,
    CellHazardFactors,
    FactorStatus,
    FactorValue,
    HazardMixConfig,
    SourceGeometry,
    SourceHazardFactors,
)
from components.geospatial_tracking.services.hazard.protocol import HazardConfig
from components.geospatial_tracking.services.hazard.snapshot import build_hazard_snapshot

_FIXTURE = FactorStatus.SOFTWARE_FIXTURE_ONLY.value


def _fv(v: float) -> FactorValue:
    return FactorValue(v, _FIXTURE)


def _cell_factors(cell_id: str) -> CellHazardFactors:
    return CellHazardFactors(cell_id, host_factor=_fv(0.8), environmental_suitability_factor=_fv(0.6), water_context_factor=_fv(0.5))


def _source_factors(source_id: str) -> SourceHazardFactors:
    return SourceHazardFactors(source_id, source_strength_factor=_fv(1.0))


def _geometry(source_id: str, cell_id: str) -> SourceGeometry:
    return SourceGeometry(source_id, cell_id, distance_km=5.0, t_hat_east=1.0, t_hat_north=0.0)


def _config() -> HazardConfig:
    return HazardConfig(
        local_kernel_family="EXPONENTIAL", local_kernel_distance_scale_km=10.0,
        anisotropic_pathway_enabled=False, anisotropy_mode="MODULATING", anisotropy_kappa=1.0,
        wind_kernel_family="EXPONENTIAL", wind_kernel_distance_scale_km=10.0,
        mix=HazardMixConfig(local_weight=1.0, anisotropic_weight=0.0),
    )


def _base_kwargs(**overrides):
    fields = dict(
        forecast_origin_id="O1", t0="2021-01-01", feature_snapshot_id="SNAPSHOT:abc",
        active_source_ids=["A", "B"], expected_grid_cell_ids=["CELL1", "CELL2"],
        geometry_by_cell={
            "CELL1": {"A": _geometry("A", "CELL1"), "B": _geometry("B", "CELL1")},
            "CELL2": {"A": _geometry("A", "CELL2"), "B": _geometry("B", "CELL2")},
        },
        cell_factors_by_cell={"CELL1": _cell_factors("CELL1"), "CELL2": _cell_factors("CELL2")},
        source_factors_by_source={"A": _source_factors("A"), "B": _source_factors("B")},
        config=_config(),
    )
    fields.update(overrides)
    return fields


def test_grid_haz_01_expected_cell_absent_from_geometry_still_incomplete():
    kwargs = _base_kwargs(expected_grid_cell_ids=["CELL1", "CELL2", "CELL3"])
    # CELL3 has no geometry, no cell factors at all
    snap = build_hazard_snapshot(**kwargs)
    cell3 = next(c for c in snap.grid_cell_results if c["grid_cell_id"] == "CELL3")
    assert cell3["status"] == CELL_HAZARD_INCOMPLETE
    assert any("CELL3" in m for m in cell3["missing_requirements"])


def test_grid_haz_02_all_expected_cells_appear_exactly_once():
    kwargs = _base_kwargs(expected_grid_cell_ids=["CELL1", "CELL2", "CELL3"])
    snap = build_hazard_snapshot(**kwargs)
    ids = [c["grid_cell_id"] for c in snap.grid_cell_results]
    assert sorted(ids) == ["CELL1", "CELL2", "CELL3"]
    assert len(ids) == len(set(ids))


def test_grid_haz_03_complete_cell_has_one_contribution_per_active_source():
    snap = build_hazard_snapshot(**_base_kwargs())
    for cell in snap.grid_cell_results:
        assert cell["status"] == COMPLETE
        assert len(cell["source_contributions"]) == 2


def test_grid_haz_04_missing_source_geometry_marks_incomplete_not_dropped():
    kwargs = _base_kwargs()
    kwargs["geometry_by_cell"] = {"CELL1": {"A": _geometry("A", "CELL1")}, "CELL2": {"A": _geometry("A", "CELL2"), "B": _geometry("B", "CELL2")}}
    snap = build_hazard_snapshot(**kwargs)
    cell1 = next(c for c in snap.grid_cell_results if c["grid_cell_id"] == "CELL1")
    assert cell1["status"] == CELL_HAZARD_INCOMPLETE
    assert any("B" in m for m in cell1["missing_requirements"])


def test_grid_haz_05_missing_source_factor_marks_incomplete_not_keyerror():
    kwargs = _base_kwargs()
    kwargs["source_factors_by_source"] = {"A": _source_factors("A")}  # B missing entirely
    snap = build_hazard_snapshot(**kwargs)  # must not raise KeyError
    for cell in snap.grid_cell_results:
        assert cell["status"] == CELL_HAZARD_INCOMPLETE
        assert any("missing source factor for B" in m for m in cell["missing_requirements"])


def test_grid_haz_06_missing_cell_factor_marks_incomplete_not_keyerror():
    kwargs = _base_kwargs()
    kwargs["cell_factors_by_cell"] = {"CELL1": _cell_factors("CELL1")}  # CELL2 missing
    snap = build_hazard_snapshot(**kwargs)  # must not raise KeyError
    cell2 = next(c for c in snap.grid_cell_results if c["grid_cell_id"] == "CELL2")
    assert cell2["status"] == CELL_HAZARD_INCOMPLETE
    assert any("CELL2" in m for m in cell2["missing_requirements"])
    assert cell2["source_contributions"] == []


def test_grid_haz_07_duplicate_active_source_ids_rejected():
    kwargs = _base_kwargs(active_source_ids=["A", "A", "B"])
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)


def test_grid_haz_08_extra_non_active_geometry_source_rejected():
    kwargs = _base_kwargs()
    kwargs["geometry_by_cell"]["CELL1"]["ROGUE"] = _geometry("ROGUE", "CELL1")
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)


def test_grid_haz_09_source_id_mismatch_inside_source_geometry_rejected():
    kwargs = _base_kwargs()
    # placed under key "A" but geometry itself claims to be "B"
    kwargs["geometry_by_cell"]["CELL1"]["A"] = _geometry("B", "CELL1")
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)


def test_grid_haz_10_grid_cell_id_mismatch_inside_geometry_rejected():
    kwargs = _base_kwargs()
    # placed under CELL1 but geometry itself claims CELL2
    kwargs["geometry_by_cell"]["CELL1"]["A"] = _geometry("A", "CELL2")
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)


def test_grid_cell_id_mismatch_inside_cell_factors_rejected():
    kwargs = _base_kwargs()
    kwargs["cell_factors_by_cell"]["CELL1"] = _cell_factors("WRONG_ID")
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)


def test_extra_non_active_source_factor_rejected():
    kwargs = _base_kwargs()
    kwargs["source_factors_by_source"]["ROGUE"] = _source_factors("ROGUE")
    with pytest.raises(ValueError):
        build_hazard_snapshot(**kwargs)
