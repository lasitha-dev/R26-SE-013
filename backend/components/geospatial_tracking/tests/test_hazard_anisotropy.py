"""Checkpoint 6C Part 34: anisotropy tests — ANISO-01..08."""

from __future__ import annotations

import math

import pytest

from components.geospatial_tracking.services.hazard.anisotropy import (
    CALM_NEUTRAL,
    DIRECTIONAL,
    compute_anisotropy_factor,
    compute_meteorological_alignment,
)
from components.geospatial_tracking.services.hazard.contracts import AnisotropyMode, WindVector


def test_aniso_01_eastward_wind_eastward_direction_alignment_plus_one():
    result = compute_meteorological_alignment(t_hat_east=1.0, t_hat_north=0.0, wind=WindVector(u10=5.0, v10=0.0))
    assert result.status == DIRECTIONAL
    assert result.alignment == pytest.approx(1.0)


def test_aniso_02_eastward_wind_westward_direction_alignment_minus_one():
    result = compute_meteorological_alignment(t_hat_east=-1.0, t_hat_north=0.0, wind=WindVector(u10=5.0, v10=0.0))
    assert result.alignment == pytest.approx(-1.0)


def test_aniso_03_perpendicular_alignment_zero():
    result = compute_meteorological_alignment(t_hat_east=0.0, t_hat_north=1.0, wind=WindVector(u10=5.0, v10=0.0))
    assert result.alignment == pytest.approx(0.0, abs=1e-9)


def test_aniso_04_calm_wind_neutral_no_fake_direction():
    result = compute_meteorological_alignment(t_hat_east=1.0, t_hat_north=0.0, wind=WindVector(u10=0.0, v10=0.0))
    assert result.status == CALM_NEUTRAL
    assert result.alignment is None

    aniso = compute_anisotropy_factor(result, kappa=3.0, mode=AnisotropyMode.MODULATING.value)
    assert aniso.anisotropy_factor == pytest.approx(1.0)
    assert aniso.status == CALM_NEUTRAL


@pytest.mark.parametrize("mode", [AnisotropyMode.MODULATING.value, AnisotropyMode.ANGULAR_NORMALIZED.value])
def test_aniso_05_kappa_zero_anisotropy_one(mode):
    alignment = compute_meteorological_alignment(t_hat_east=1.0, t_hat_north=0.0, wind=WindVector(u10=3.0, v10=4.0))
    aniso = compute_anisotropy_factor(alignment, kappa=0.0, mode=mode)
    assert aniso.anisotropy_factor == pytest.approx(1.0)


@pytest.mark.parametrize("mode", [AnisotropyMode.MODULATING.value, AnisotropyMode.ANGULAR_NORMALIZED.value])
def test_aniso_06_down_greater_than_perpendicular_greater_than_up(mode):
    wind = WindVector(u10=5.0, v10=0.0)
    down = compute_meteorological_alignment(t_hat_east=1.0, t_hat_north=0.0, wind=wind)
    perp = compute_meteorological_alignment(t_hat_east=0.0, t_hat_north=1.0, wind=wind)
    up = compute_meteorological_alignment(t_hat_east=-1.0, t_hat_north=0.0, wind=wind)

    kappa = 2.0
    down_factor = compute_anisotropy_factor(down, kappa=kappa, mode=mode).anisotropy_factor
    perp_factor = compute_anisotropy_factor(perp, kappa=kappa, mode=mode).anisotropy_factor
    up_factor = compute_anisotropy_factor(up, kappa=kappa, mode=mode).anisotropy_factor

    assert down_factor > perp_factor > up_factor


def test_aniso_07_wind_never_labeled_disease_direction():
    # structural: no field/parameter name anywhere in the anisotropy
    # output contracts uses "disease_direction"/"transmission_bearing"
    from components.geospatial_tracking.services.hazard.anisotropy import AlignmentResult, AnisotropyResult

    forbidden = {"disease_direction", "transmission_bearing", "spread_direction", "confidence"}
    for cls in (AlignmentResult, AnisotropyResult):
        field_names = {name.lower() for name in cls.__dataclass_fields__}
        assert not (field_names & forbidden), f"{cls.__name__} leaked forbidden field {field_names & forbidden}"


def test_aniso_08_uv_pairing_intact():
    # a wind vector with equal-magnitude u/v components must align at
    # 45 degrees, not be silently converted through a compass bearing
    # that would round differently.
    wind = WindVector(u10=1.0, v10=1.0)
    magnitude = math.hypot(wind.u10, wind.v10)
    result = compute_meteorological_alignment(t_hat_east=1.0, t_hat_north=0.0, wind=wind)
    assert result.alignment == pytest.approx(wind.u10 / magnitude)


def test_angular_normalized_differs_from_modulating_for_kappa_greater_than_zero():
    alignment = compute_meteorological_alignment(t_hat_east=1.0, t_hat_north=0.0, wind=WindVector(u10=5.0, v10=0.0))
    modulating = compute_anisotropy_factor(alignment, kappa=2.0, mode=AnisotropyMode.MODULATING.value)
    normalized = compute_anisotropy_factor(alignment, kappa=2.0, mode=AnisotropyMode.ANGULAR_NORMALIZED.value)
    assert modulating.anisotropy_factor != pytest.approx(normalized.anisotropy_factor)


def test_negative_kappa_rejected():
    alignment = compute_meteorological_alignment(t_hat_east=1.0, t_hat_north=0.0, wind=WindVector(u10=5.0, v10=0.0))
    with pytest.raises(ValueError):
        compute_anisotropy_factor(alignment, kappa=-1.0, mode=AnisotropyMode.MODULATING.value)
