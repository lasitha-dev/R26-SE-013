"""SIGNATURE-01..04, COMPAT-01..03 (pure, no network)."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field

from components.geospatial_tracking.services.features.resolved_data_signature import (
    LANDCOVER_GROUP_NOT_SELECTED,
    LANDCOVER_GROUP_UNRECOGNIZED,
    LANDCOVER_GROUP_V100,
    LANDCOVER_GROUP_V200,
    MISMATCH_HOST_DATASET,
    MISMATCH_HYDROLOGY_DATASET,
    MISMATCH_LANDCOVER_UNRECOGNIZED,
    MISMATCH_LANDCOVER_VERSION,
    MISMATCH_POLICY,
    MISMATCH_WEATHER_MODEL,
    compare_feature_compatibility,
    compute_resolved_data_signature,
    landcover_comparability_group,
)


def _base_kwargs(**overrides) -> dict:
    fields = dict(
        feature_policy_hash="POLICY_HASH_1",
        landcover_dataset_version="v100 (2020)",
        host_density_dataset_version="GLW4 reference_year=2015",
        weather_provider="Open-Meteo Historical Weather API",
        weather_model="era5",
        weather_model_resolution="0.25 degrees",
        weather_temporal_role="RETROSPECTIVE_REANALYSIS_STATE_PROXY",
        weather_sampling_strategy="AOI_CENTER",
        hydrology_dataset_version="v1.0",
        resolved_t0_cutoff_utc="2020-09-08T18:30:00+00:00",
        source_timezone="Asia/Colombo",
    )
    fields.update(overrides)
    return fields


class TestLandcoverComparabilityGroup:
    def test_v100_recognized(self):
        assert landcover_comparability_group("v100 (2020)") == LANDCOVER_GROUP_V100

    def test_v200_recognized(self):
        assert landcover_comparability_group("v200 (2021)") == LANDCOVER_GROUP_V200

    def test_none_is_not_selected(self):
        assert landcover_comparability_group(None) == LANDCOVER_GROUP_NOT_SELECTED

    def test_not_selected_string_is_not_selected(self):
        assert landcover_comparability_group("NOT_SELECTED") == LANDCOVER_GROUP_NOT_SELECTED

    def test_lc_compat_unknown_01_unrecognized_string_is_unrecognized_not_omitted(self):
        # Checkpoint 6B Part 0 fix: a real, non-empty, unknown product
        # must never be folded into NOT_SELECTED (which would hide it as
        # if land cover had been deliberately omitted).
        assert landcover_comparability_group("some_future_product") == LANDCOVER_GROUP_UNRECOGNIZED
        assert landcover_comparability_group("v300 (2025)") == LANDCOVER_GROUP_UNRECOGNIZED


class TestResolvedDataSignature:
    def test_signature_01_identical_resolved_config_same_hash(self):
        h1 = compute_resolved_data_signature(**_base_kwargs())
        h2 = compute_resolved_data_signature(**_base_kwargs())
        assert h1 == h2

    def test_signature_02_v100_vs_v200_different_hash(self):
        h_v100 = compute_resolved_data_signature(**_base_kwargs(landcover_dataset_version="v100 (2020)"))
        h_v200 = compute_resolved_data_signature(**_base_kwargs(landcover_dataset_version="v200 (2021)"))
        assert h_v100 != h_v200

    def test_signature_03_no_generated_at_or_retrieved_at_parameter_exists(self):
        sig = inspect.signature(compute_resolved_data_signature)
        assert "generated_at" not in sig.parameters
        assert "retrieved_at" not in sig.parameters

    def test_signature_03_identical_inputs_always_same_hash_regardless_of_call_time(self):
        # the function has no time-based input at all, so repeated calls
        # with identical arguments are byte-identical regardless of when
        # each call actually happens
        import time

        h1 = compute_resolved_data_signature(**_base_kwargs())
        time.sleep(0.01)
        h2 = compute_resolved_data_signature(**_base_kwargs())
        assert h1 == h2

    def test_signature_04_host_density_dataset_version_affects_hash(self):
        h1 = compute_resolved_data_signature(**_base_kwargs(host_density_dataset_version="GLW4 reference_year=2015"))
        h2 = compute_resolved_data_signature(**_base_kwargs(host_density_dataset_version="GLW5 reference_year=2030"))
        assert h1 != h2

    def test_signature_04_hydrology_dataset_version_affects_hash(self):
        h1 = compute_resolved_data_signature(**_base_kwargs(hydrology_dataset_version="v1.0"))
        h2 = compute_resolved_data_signature(**_base_kwargs(hydrology_dataset_version="NOT_SELECTED"))
        assert h1 != h2

    def test_signature_04_weather_model_affects_hash(self):
        h1 = compute_resolved_data_signature(**_base_kwargs(weather_model="era5"))
        h2 = compute_resolved_data_signature(**_base_kwargs(weather_model="era5_land"))
        assert h1 != h2

    def test_resolved_t0_cutoff_affects_hash(self):
        h1 = compute_resolved_data_signature(**_base_kwargs(resolved_t0_cutoff_utc="2020-09-08T18:30:00+00:00"))
        h2 = compute_resolved_data_signature(**_base_kwargs(resolved_t0_cutoff_utc="2020-09-09T00:00:00+00:00"))
        assert h1 != h2


@dataclass
class _FakeSnapshot:
    """Minimal stand-in exposing only what `compare_feature_compatibility`
    reads — avoids a real, slow `assemble_feature_snapshot` call for
    pure compatibility-logic tests."""

    feature_protocol_hash: str = "POLICY_HASH_1"
    source_dataset_versions: dict = field(default_factory=lambda: {
        "landcover": "v100 (2020)",
        "host_density": "GLW4 reference_year=2015",
        "hydrology": "v1.0",
    })
    weather: dict = field(default_factory=lambda: {"window": {"weather_model": "era5"}})
    grid_meta: dict = field(default_factory=lambda: {"cell_size_km": 2.5, "half_extent_km": 5.0})


class TestCompareFeatureCompatibility:
    def test_compat_02_identical_snapshots_report_no_mismatches(self):
        a = _FakeSnapshot()
        b = _FakeSnapshot()
        assert compare_feature_compatibility(a, b) == []

    def test_compat_01_v100_vs_v200_reports_landcover_version_mismatch(self):
        a = _FakeSnapshot()
        b = _FakeSnapshot(source_dataset_versions={**a.source_dataset_versions, "landcover": "v200 (2021)"})
        mismatches = compare_feature_compatibility(a, b)
        assert MISMATCH_LANDCOVER_VERSION in mismatches

    def test_compat_03_weather_model_mismatch_detectable(self):
        a = _FakeSnapshot()
        b = _FakeSnapshot(weather={"window": {"weather_model": "era5_land"}})
        mismatches = compare_feature_compatibility(a, b)
        assert MISMATCH_WEATHER_MODEL in mismatches

    def test_lc_compat_unknown_01_unrecognized_product_flagged_even_if_both_sides_match(self):
        a = _FakeSnapshot(source_dataset_versions={**_FakeSnapshot().source_dataset_versions, "landcover": "v300 (2025)"})
        b = _FakeSnapshot(source_dataset_versions={**_FakeSnapshot().source_dataset_versions, "landcover": "v300 (2025)"})
        mismatches = compare_feature_compatibility(a, b)
        assert MISMATCH_LANDCOVER_UNRECOGNIZED in mismatches
        # both sides resolve to the SAME unrecognized group -> no version
        # mismatch between them, but the unrecognized-product warning
        # still fires
        assert MISMATCH_LANDCOVER_VERSION not in mismatches

    def test_unrecognized_vs_known_product_flags_both_warnings(self):
        a = _FakeSnapshot()  # v100 (2020)
        b = _FakeSnapshot(source_dataset_versions={**a.source_dataset_versions, "landcover": "v300 (2025)"})
        mismatches = compare_feature_compatibility(a, b)
        assert MISMATCH_LANDCOVER_VERSION in mismatches
        assert MISMATCH_LANDCOVER_UNRECOGNIZED in mismatches

    def test_policy_mismatch_detectable(self):
        a = _FakeSnapshot()
        b = _FakeSnapshot(feature_protocol_hash="POLICY_HASH_2")
        assert MISMATCH_POLICY in compare_feature_compatibility(a, b)

    def test_host_dataset_mismatch_detectable(self):
        a = _FakeSnapshot()
        b = _FakeSnapshot(source_dataset_versions={**a.source_dataset_versions, "host_density": "GLW3 reference_year=2010"})
        assert MISMATCH_HOST_DATASET in compare_feature_compatibility(a, b)

    def test_hydrology_dataset_mismatch_detectable(self):
        a = _FakeSnapshot()
        b = _FakeSnapshot(source_dataset_versions={**a.source_dataset_versions, "hydrology": "NOT_SELECTED"})
        assert MISMATCH_HYDROLOGY_DATASET in compare_feature_compatibility(a, b)

    def test_grid_protocol_mismatch_detectable(self):
        a = _FakeSnapshot()
        b = _FakeSnapshot(grid_meta={"cell_size_km": 5.0, "half_extent_km": 5.0})
        assert "GRID_PROTOCOL_MISMATCH" in compare_feature_compatibility(a, b)

    def test_mismatch_is_not_automatically_called_invalid(self):
        # the function returns a plain list of warning labels -- no
        # exception, no "is_valid" boolean, no automatic rejection
        a = _FakeSnapshot()
        b = _FakeSnapshot(source_dataset_versions={**a.source_dataset_versions, "landcover": "v200 (2021)"})
        result = compare_feature_compatibility(a, b)
        assert isinstance(result, list)
