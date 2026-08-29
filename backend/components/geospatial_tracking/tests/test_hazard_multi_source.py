"""Checkpoint 6C Part 35 / Checkpoint 6C.5 Part 1-5: multi-source
accumulation tests — HAZARD-01..10.

SUPERSEDED_BY_6C5_INDEX_CORRECTION: the original 6C version of this
file used the combined `HazardFactors` bag (source-indexed host/
environmental/water factors), which Checkpoint 6C.5 corrected to be
CELL-indexed (`CellHazardFactors`) with only `source_strength_factor`
remaining SOURCE-indexed (`SourceHazardFactors`). Rewritten below to
use the corrected contracts throughout.
"""

from __future__ import annotations

import pytest

from components.geospatial_tracking.services.hazard.accumulator import accumulate_cell_hazard
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
from components.geospatial_tracking.services.hazard.source_hazard import compute_source_hazard

_FIXTURE = FactorStatus.SOFTWARE_FIXTURE_ONLY.value


def _fv(v: float) -> FactorValue:
    return FactorValue(v, _FIXTURE)


def _cell_factors(cell_id: str = "CELL1") -> CellHazardFactors:
    return CellHazardFactors(cell_id, host_factor=_fv(0.8), environmental_suitability_factor=_fv(0.6), water_context_factor=_fv(0.5))


def _source_factors(source_id: str) -> SourceHazardFactors:
    return SourceHazardFactors(source_id, source_strength_factor=_fv(1.0))


def _config(anisotropic_enabled: bool = False) -> HazardConfig:
    return HazardConfig(
        local_kernel_family="EXPONENTIAL", local_kernel_distance_scale_km=10.0,
        anisotropic_pathway_enabled=anisotropic_enabled, anisotropy_mode="MODULATING", anisotropy_kappa=1.0,
        wind_kernel_family="EXPONENTIAL", wind_kernel_distance_scale_km=10.0,
        mix=HazardMixConfig(local_weight=1.0, anisotropic_weight=0.0),
    )


def _contribution(source_id: str, distance_km: float, config: HazardConfig):
    geometry = SourceGeometry(source_id, "CELL1", distance_km=distance_km, t_hat_east=1.0, t_hat_north=0.0)
    return compute_source_hazard(geometry=geometry, cell_factors=_cell_factors(), source_factors=_source_factors(source_id), config=config)


def test_hazard_01_one_source_total_equals_source_hazard():
    config = _config()
    c1 = _contribution("A", 5.0, config)
    result = accumulate_cell_hazard(grid_cell_id="CELL1", eligible_source_ids=["A"], contributions={"A": c1})
    assert result.total_hazard == pytest.approx(c1.source_hazard)


def test_hazard_02_two_source_total_is_exact_sum():
    config = _config()
    c1 = _contribution("A", 5.0, config)
    c2 = _contribution("B", 8.0, config)
    result = accumulate_cell_hazard(grid_cell_id="CELL1", eligible_source_ids=["A", "B"], contributions={"A": c1, "B": c2})
    assert result.total_hazard == pytest.approx(c1.source_hazard + c2.source_hazard)


def test_hazard_03_three_source_total_is_exact_sum():
    config = _config()
    c1 = _contribution("A", 5.0, config)
    c2 = _contribution("B", 8.0, config)
    c3 = _contribution("C", 12.0, config)
    result = accumulate_cell_hazard(
        grid_cell_id="CELL1", eligible_source_ids=["A", "B", "C"], contributions={"A": c1, "B": c2, "C": c3}
    )
    assert result.total_hazard == pytest.approx(c1.source_hazard + c2.source_hazard + c3.source_hazard)


def test_hazard_04_source_order_does_not_change_total():
    config = _config()
    contribs = {sid: _contribution(sid, d, config) for sid, d in (("A", 5.0), ("B", 8.0), ("C", 12.0))}
    forward = accumulate_cell_hazard(grid_cell_id="CELL1", eligible_source_ids=["A", "B", "C"], contributions=contribs)
    reordered = accumulate_cell_hazard(
        grid_cell_id="CELL1", eligible_source_ids=["C", "A", "B"],
        contributions={"C": contribs["C"], "A": contribs["A"], "B": contribs["B"]},
    )
    assert forward.total_hazard == reordered.total_hazard
    assert forward.relative_risk_index == reordered.relative_risk_index


def test_hazard_05_nearest_source_cannot_replace_sum():
    config = _config()
    near = _contribution("NEAR", 1.0, config)
    far = _contribution("FAR", 50.0, config)
    result = accumulate_cell_hazard(grid_cell_id="CELL1", eligible_source_ids=["NEAR", "FAR"], contributions={"NEAR": near, "FAR": far})
    assert result.total_hazard == pytest.approx(near.source_hazard + far.source_hazard)
    assert result.total_hazard != pytest.approx(near.source_hazard)


@pytest.mark.parametrize("role_label", ["NOISE", "BORDER", "CORE", "ST_TEMPORAL_UNUSABLE"])
def test_hazard_06_09_st_role_never_gates_contribution(role_label):
    # HAZARD-06/07/08/09: a source's ST-DBSCAN role (represented here
    # purely as a test label -- the hazard engine has no such parameter
    # at all, see NOFIT-06) never changes whether or how it contributes.
    config = _config()
    tagged = _contribution(f"SRC_{role_label}", 6.0, config)
    baseline = _contribution("SRC_BASELINE", 6.0, config)
    assert tagged.source_hazard == pytest.approx(baseline.source_hazard)
    assert tagged.source_hazard > 0.0
    result = accumulate_cell_hazard(
        grid_cell_id="CELL1", eligible_source_ids=[tagged.source_id], contributions={tagged.source_id: tagged}
    )
    assert result.total_hazard == pytest.approx(tagged.source_hazard)


def test_hazard_10_missing_geometry_blocks_not_silently_dropped():
    config = _config()
    a = _contribution("A", 5.0, config)
    # "B" is eligible but has no geometry/contribution at all
    result = accumulate_cell_hazard(grid_cell_id="CELL1", eligible_source_ids=["A", "B"], contributions={"A": a})
    assert result.status == CELL_HAZARD_INCOMPLETE
    assert result.total_hazard is None
    assert any("B" in m for m in result.missing_requirements)


def test_order_invariance_uses_fsum_for_many_sources():
    config = _config()
    contribs = {f"S{i}": _contribution(f"S{i}", float(i + 1), config) for i in range(10)}
    ids = list(contribs.keys())
    forward = accumulate_cell_hazard(grid_cell_id="CELL1", eligible_source_ids=ids, contributions=contribs)
    reversed_ids = list(reversed(ids))
    backward = accumulate_cell_hazard(grid_cell_id="CELL1", eligible_source_ids=reversed_ids, contributions=contribs)
    assert forward.total_hazard == backward.total_hazard


def test_non_negative_hazard_hard_checked():
    config = _config()
    c = _contribution("A", 5.0, config)
    assert c.source_hazard >= 0.0
    result = accumulate_cell_hazard(grid_cell_id="CELL1", eligible_source_ids=["A"], contributions={"A": c})
    assert result.total_hazard >= 0.0
