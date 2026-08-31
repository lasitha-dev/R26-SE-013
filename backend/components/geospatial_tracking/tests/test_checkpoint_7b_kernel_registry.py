"""Checkpoint 7B Part 40: KERNEL7B-01..05 candidate/kernel registry tests."""

from __future__ import annotations

from components.geospatial_tracking.services.model_development.candidate_registry_7b import (
    KERNEL_SCALE_CANDIDATES_KM,
    build_candidate_registry,
    candidate_registry_hash,
)


def test_kernel7b_01_exact_scale_registry():
    assert KERNEL_SCALE_CANDIDATES_KM == (5.0, 10.0, 15.0, 25.0)


def test_kernel7b_02_exact_kernel_families():
    registry = build_candidate_registry()
    families = {c.kernel_family for c in registry}
    assert families == {"EXPONENTIAL", "GAUSSIAN"}


def test_kernel7b_03_registry_has_exactly_24_candidates():
    registry = build_candidate_registry()
    assert len(registry) == 24
    assert len({c.candidate_id for c in registry}) == 24  # every id unique


def test_kernel7b_04_registry_takes_no_held_out_or_performance_arguments():
    import inspect

    params = set(inspect.signature(build_candidate_registry).parameters)
    assert params == set()  # cannot be mutated by any external result


def test_kernel7b_05_candidate_id_deterministic_and_order_invariant():
    r1 = build_candidate_registry()
    r2 = build_candidate_registry()
    assert tuple(c.candidate_id for c in r1) == tuple(c.candidate_id for c in r2)
    assert candidate_registry_hash() == candidate_registry_hash()

    ids_1 = sorted(c.candidate_id for c in r1)
    ids_2 = sorted(reversed([c.candidate_id for c in r2]))
    assert ids_1 == ids_2
