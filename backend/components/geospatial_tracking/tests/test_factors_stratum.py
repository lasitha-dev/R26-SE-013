"""Checkpoint 6D.6 Part 18: full-field ReferenceStratumKey identity
tests — STRATUM-01..06."""

from __future__ import annotations

from components.geospatial_tracking.services.factors.contracts import ReferenceStratumKey

_BASE = dict(
    factor_family="HOST_DENSITY", dataset_family="GLW4",
    dataset_comparability_group="GLW4:2015", canonical_units="animals_per_km2",
    sampling_protocol_version="GLW4_OVERLAP_AREA_WEIGHTED_V1",
)


def _key(**overrides) -> ReferenceStratumKey:
    kwargs = dict(_BASE)
    kwargs.update(overrides)
    return ReferenceStratumKey(**kwargs)


def test_stratum_01_canonical_key_contains_every_field():
    key = _key()
    canonical = key.canonical_key()
    for field_name, value in _BASE.items():
        assert value in canonical, f"{field_name}={value!r} missing from canonical_key()"


def test_stratum_02_field_order_does_not_affect_identity():
    # ReferenceStratumKey is a dataclass -- construct via keyword args in
    # two different orders; canonical_key()/digest() must not depend on
    # construction order (json.dumps(sort_keys=True) makes this true by
    # construction, but this test proves it rather than assuming it).
    key_a = ReferenceStratumKey(
        factor_family="HOST_DENSITY", dataset_family="GLW4",
        dataset_comparability_group="GLW4:2015", canonical_units="animals_per_km2",
        sampling_protocol_version="GLW4_OVERLAP_AREA_WEIGHTED_V1",
    )
    key_b = ReferenceStratumKey(
        sampling_protocol_version="GLW4_OVERLAP_AREA_WEIGHTED_V1", canonical_units="animals_per_km2",
        dataset_comparability_group="GLW4:2015", dataset_family="GLW4",
        factor_family="HOST_DENSITY",
    )
    assert key_a.canonical_key() == key_b.canonical_key()
    assert key_a.digest() == key_b.digest()


def test_stratum_03_sampling_protocol_version_difference_is_distinct_stratum():
    key_a = _key(sampling_protocol_version="GLW4_OVERLAP_AREA_WEIGHTED_V1")
    key_b = _key(sampling_protocol_version="GLW4_OVERLAP_AREA_WEIGHTED_V2")
    assert key_a.canonical_key() != key_b.canonical_key()
    assert key_a.digest() != key_b.digest()


def test_stratum_04_dataset_family_difference_is_distinct_stratum():
    key_a = _key(dataset_family="GLW4")
    key_b = _key(dataset_family="Some Other Livestock Density Product")
    assert key_a.canonical_key() != key_b.canonical_key()
    assert key_a.digest() != key_b.digest()


def test_stratum_05_canonical_units_difference_is_distinct_stratum():
    key_a = _key(canonical_units="animals_per_km2")
    key_b = _key(canonical_units="animals_per_hectare")
    assert key_a.canonical_key() != key_b.canonical_key()
    assert key_a.digest() != key_b.digest()


def test_stratum_06_dataset_comparability_group_difference_is_distinct_stratum():
    key_a = _key(dataset_comparability_group="GLW4:2015")
    key_b = _key(dataset_comparability_group="GLW4:2020")
    assert key_a.canonical_key() != key_b.canonical_key()
    assert key_a.digest() != key_b.digest()


def test_stratum_identical_fields_produce_identical_identity():
    key_a = _key()
    key_b = _key()
    assert key_a.canonical_key() == key_b.canonical_key()
    assert key_a.digest() == key_b.digest()
