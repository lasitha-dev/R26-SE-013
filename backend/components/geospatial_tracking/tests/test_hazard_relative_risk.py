"""Checkpoint 6C Part 36 (RISKLINK-01..07) / Checkpoint 6C.5 Part 19-20
(RISKNUM-01..07): the relative-risk-index link, now returning an
explicit `RelativeRiskResult(value, status)`.

SUPERSEDED_BY_6C5_INDEX_CORRECTION: `compute_relative_risk_index` used
to return a bare float; Checkpoint 6C.5 Part 19 requires an explicit
numerical-saturation status, so it now returns `RelativeRiskResult`.
"""

from __future__ import annotations

import pytest

from components.geospatial_tracking.services.hazard.relative_risk import (
    FINITE_INTERIOR,
    NUMERIC_SATURATION_ADJUSTED,
    RelativeRiskResult,
    compute_relative_risk_index,
)


def test_risklink_01_risknum_01_zero_hazard_zero_risk_exact():
    result = compute_relative_risk_index(0.0)
    assert result.value == 0.0
    assert result.status == FINITE_INTERIOR


def test_risklink_02_monotonically_increasing():
    values = [compute_relative_risk_index(h).value for h in (0.0, 0.5, 1.0, 5.0, 20.0)]
    assert values == sorted(values)
    assert len(set(values)) == len(values)


def test_risklink_03_within_bounds():
    for h in (0.0, 0.1, 1.0, 10.0, 30.0):
        r = compute_relative_risk_index(h)
        assert 0.0 <= r.value < 1.0
    # very large H: still bounded, but may report saturation explicitly
    saturated = compute_relative_risk_index(1000.0)
    assert 0.0 <= saturated.value <= 1.0


def test_risklink_04_negative_hazard_rejected():
    with pytest.raises(ValueError):
        compute_relative_risk_index(-0.1)


def test_risklink_05_output_label_is_relative_risk_index():
    from components.geospatial_tracking.services.hazard.accumulator import CellHazardResult

    assert "relative_risk_index" in CellHazardResult.__dataclass_fields__
    assert "relative_risk_status" in CellHazardResult.__dataclass_fields__


def test_risklink_06_no_infection_probability_field():
    from components.geospatial_tracking.services.hazard.accumulator import CellHazardResult
    from components.geospatial_tracking.services.hazard.snapshot import HazardSnapshot
    from components.geospatial_tracking.services.hazard.source_hazard import SourceHazardContribution

    forbidden = {"infection_probability", "probability", "spread_direction", "speed", "confidence"}
    for cls in (CellHazardResult, HazardSnapshot, SourceHazardContribution, RelativeRiskResult):
        field_names = {name.lower() for name in cls.__dataclass_fields__}
        assert not (field_names & forbidden), f"{cls.__name__} leaked forbidden field {field_names & forbidden}"


def test_risklink_07_nonzero_prior_rejected():
    with pytest.raises(ValueError):
        compute_relative_risk_index(1.0, prior_relative_risk=0.2)


def test_risknum_02_ordinary_finite_h_is_finite_interior():
    result = compute_relative_risk_index(2.5)
    assert result.status == FINITE_INTERIOR
    assert result.value < 1.0


def test_risknum_03_very_large_h_never_unlabeled_exact_one():
    # H large enough that naive 1-exp(-H) saturates to exactly 1.0 --
    # must never be returned as an unlabeled 1.0.
    result = compute_relative_risk_index(1000.0)
    if result.value == 1.0:
        assert result.status == NUMERIC_SATURATION_ADJUSTED
    else:
        assert result.value < 1.0


def test_risknum_04_saturation_status_explicit_and_value_adjusted():
    result = compute_relative_risk_index(1000.0)
    assert result.status in (FINITE_INTERIOR, NUMERIC_SATURATION_ADJUSTED)
    if result.status == NUMERIC_SATURATION_ADJUSTED:
        assert result.value < 1.0  # nudged below 1.0, never exactly 1.0


def test_risknum_05_monotonic_non_decreasing_across_saturation_boundary():
    hs = [0.0, 1.0, 10.0, 30.0, 50.0, 100.0, 1000.0, 10000.0]
    values = [compute_relative_risk_index(h).value for h in hs]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def test_risknum_06_negative_and_nonfinite_h_rejected():
    with pytest.raises(ValueError):
        compute_relative_risk_index(-1.0)
    with pytest.raises(ValueError):
        compute_relative_risk_index(float("nan"))
    with pytest.raises(ValueError):
        compute_relative_risk_index(float("inf"))


def test_risknum_07_still_no_probability_field():
    field_names = {name.lower() for name in RelativeRiskResult.__dataclass_fields__}
    assert "probability" not in field_names
    assert "infection_probability" not in field_names


def test_large_hazard_asymptotically_approaches_one():
    r = compute_relative_risk_index(20.0)
    assert r.value > 0.999999
    assert r.value < 1.0
    assert r.status == FINITE_INTERIOR
