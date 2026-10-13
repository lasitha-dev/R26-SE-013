"""Checkpoint 6C Part 33: radial kernel tests — KERNEL-01..06."""

from __future__ import annotations

import math

import pytest

from components.geospatial_tracking.services.hazard.kernels import DISTANCE_SCALE_PARAMETER_STATUS, evaluate_kernel


@pytest.mark.parametrize("family", ["EXPONENTIAL", "GAUSSIAN"])
def test_kernel_01_k_zero_equals_one(family):
    assert evaluate_kernel(0.0, family=family, distance_scale_km=10.0) == pytest.approx(1.0)


@pytest.mark.parametrize("family", ["EXPONENTIAL", "GAUSSIAN"])
def test_kernel_02_decreases_with_distance(family):
    k1 = evaluate_kernel(1.0, family=family, distance_scale_km=10.0)
    k2 = evaluate_kernel(5.0, family=family, distance_scale_km=10.0)
    k3 = evaluate_kernel(20.0, family=family, distance_scale_km=10.0)
    assert k1 > k2 > k3


@pytest.mark.parametrize("family", ["EXPONENTIAL", "GAUSSIAN"])
def test_kernel_03_negative_distance_rejected(family):
    with pytest.raises(ValueError):
        evaluate_kernel(-1.0, family=family, distance_scale_km=10.0)


@pytest.mark.parametrize("family", ["EXPONENTIAL", "GAUSSIAN"])
@pytest.mark.parametrize("bad_scale", [0.0, -5.0])
def test_kernel_04_nonpositive_scale_rejected(family, bad_scale):
    with pytest.raises(ValueError):
        evaluate_kernel(5.0, family=family, distance_scale_km=bad_scale)


@pytest.mark.parametrize("family", ["EXPONENTIAL", "GAUSSIAN"])
@pytest.mark.parametrize("distance", [0.0, 1.0, 100.0, 1_000_000.0])
def test_kernel_05_always_finite_nonnegative(family, distance):
    k = evaluate_kernel(distance, family=family, distance_scale_km=10.0)
    assert math.isfinite(k)
    assert k >= 0.0
    assert k <= 1.0


def test_kernel_06_scale_labeled_unfrozen_not_spread_radius():
    assert DISTANCE_SCALE_PARAMETER_STATUS == "UNFROZEN_DEVELOPMENT_PARAMETER"
    assert "radius" not in DISTANCE_SCALE_PARAMETER_STATUS.lower()
    assert "reach" not in DISTANCE_SCALE_PARAMETER_STATUS.lower()


def test_unknown_family_rejected():
    with pytest.raises(ValueError):
        evaluate_kernel(5.0, family="LINEAR", distance_scale_km=10.0)


def test_nan_and_infinite_distance_rejected():
    with pytest.raises(ValueError):
        evaluate_kernel(float("nan"), family="EXPONENTIAL", distance_scale_km=10.0)
    with pytest.raises(ValueError):
        evaluate_kernel(float("inf"), family="EXPONENTIAL", distance_scale_km=10.0)


def test_no_hard_reach_cutoff_nofit_07():
    # NOFIT-07: a distance many multiples of the kernel scale still
    # returns a small positive value, never a hard-truncated zero (as
    # opposed to an arbitrarily huge distance, where exp() legitimately
    # underflows to 0.0 in float64 -- that is floating-point precision,
    # not a scientifically imposed reach cutoff).
    k = evaluate_kernel(500.0, family="EXPONENTIAL", distance_scale_km=10.0)
    assert k > 0.0
