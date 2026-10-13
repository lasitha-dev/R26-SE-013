"""PROV-01/02/03."""

import pytest

from components.geospatial_tracking.services.geospatial.feature_result import (
    FeatureResult,
    FeatureStatus,
    assert_not_demo_for_scientific_use,
)


def _real_result(**overrides):
    fields = dict(
        feature_name="landcover_cropland_fraction",
        value=0.42,
        units="fraction",
        status=FeatureStatus.REAL.value,
        dataset_name="ESA WorldCover",
        dataset_version="v200 (2021)",
        reference_time="2021",
        retrieved_at="2026-08-19T00:00:00Z",
        source_resolution="10m",
        source_crs="EPSG:4326",
        analysis_method="area-weighted zonal fraction",
        quality_notes="",
    )
    fields.update(overrides)
    return FeatureResult(**fields)


def test_prov_01_real_feature_carries_full_dataset_provenance():
    r = _real_result()
    assert r.dataset_name == "ESA WorldCover"
    assert r.dataset_version == "v200 (2021)"
    assert r.reference_time == "2021"
    assert r.source_resolution == "10m"
    assert r.source_crs == "EPSG:4326"
    assert r.analysis_method
    assert r.retrieved_at


def test_prov_02_demo_feature_cannot_be_marked_real():
    demo = _real_result(status=FeatureStatus.DEMO.value, value=None)
    with pytest.raises(ValueError, match="DEMO"):
        assert_not_demo_for_scientific_use([demo])


def test_prov_02_real_features_pass_the_demo_gate():
    assert_not_demo_for_scientific_use([_real_result()])  # must not raise


def test_prov_03_static_reference_year_remains_visible():
    r = _real_result(dataset_name="FAO GLW 4", dataset_version="GLW4", reference_time="2015")
    assert r.reference_time == "2015"
    # never silently blank when the reference year differs from the
    # event/analysis year it is being used alongside
    assert r.reference_time is not None


class TestNoFabricatedValues:
    def test_missing_status_cannot_carry_a_value(self):
        with pytest.raises(ValueError, match="only REAL results may carry a value"):
            FeatureResult(
                feature_name="wind_speed_10m",
                value=3.0,  # forbidden fallback like "wind = 3 m/s"
                units="m/s",
                status=FeatureStatus.MISSING.value,
                dataset_name=None,
                dataset_version=None,
                reference_time=None,
                retrieved_at=None,
                source_resolution=None,
                source_crs=None,
                analysis_method=None,
                quality_notes="",
            )

    def test_blocked_status_cannot_carry_a_value(self):
        with pytest.raises(ValueError):
            FeatureResult(
                feature_name="elevation_m",
                value=100.0,  # forbidden fallback like "elevation = 100m"
                units="m",
                status=FeatureStatus.BLOCKED.value,
                dataset_name=None,
                dataset_version=None,
                reference_time=None,
                retrieved_at=None,
                source_resolution=None,
                source_crs=None,
                analysis_method=None,
                quality_notes="source unreachable",
            )

    def test_missing_status_with_none_value_is_valid(self):
        r = FeatureResult(
            feature_name="host_density_cattle",
            value=None,
            units="animals/km2",
            status=FeatureStatus.MISSING.value,
            dataset_name="FAO GLW 4",
            dataset_version="GLW4",
            reference_time="2015",
            retrieved_at="2026-08-19T00:00:00Z",
            source_resolution="5 arcmin",
            source_crs="EPSG:4326",
            analysis_method="area-weighted zonal mean",
            quality_notes="nodata at this location",
        )
        assert r.value is None
        assert r.status == FeatureStatus.MISSING.value
