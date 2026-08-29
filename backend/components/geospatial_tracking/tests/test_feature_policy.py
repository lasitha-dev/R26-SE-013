"""POLICY-01..06, HYDRO-POLICY-01/02 (hash sensitivity — pure, no network)."""

import pytest

from components.geospatial_tracking.services.features.feature_policy import (
    DEFAULT_HYDRORIVERS_SEARCH_RADIUS_KM,
    ELEVATION_NOT_YET_IMPLEMENTED_MESSAGE,
    FeaturePolicy,
    LandCoverFeaturePolicy,
)


def _policy(**overrides) -> FeaturePolicy:
    fields = dict(
        disease="Lumpy skin disease",
        active_window_days=14,
        grid_half_extent_km=5.0,
        grid_cell_size_km=2.5,
        weather_model="era5",
        weather_lookback_hours=24,
        landcover_policy=LandCoverFeaturePolicy(mode="OMIT"),
    )
    fields.update(overrides)
    return FeaturePolicy(**fields)


class TestWeatherModelValidation:
    def test_policy_01_era5_is_accepted(self):
        assert _policy(weather_model="era5").weather_model == "era5"

    def test_policy_01_era5_land_is_rejected(self):
        with pytest.raises(ValueError, match="unsupported weather_model"):
            _policy(weather_model="era5_land")

    def test_policy_01_best_match_is_rejected(self):
        with pytest.raises(ValueError, match="unsupported weather_model"):
            _policy(weather_model="best_match")

    def test_policy_01_ecmwf_ifs_is_rejected(self):
        with pytest.raises(ValueError):
            _policy(weather_model="ecmwf_ifs")


class TestTemporalRoleIsNotConfigurable:
    def test_policy_03_no_environment_temporal_mode_field_exists(self):
        # Checkpoint 6A.5 Part 3: the ambiguous, hash-only-no-op field
        # is removed entirely -- there is nothing to set that would
        # change the hash without changing assembled behavior.
        p = _policy()
        assert not hasattr(p, "environment_temporal_mode")

    def test_policy_03_config_dict_declares_the_fixed_role(self):
        from components.geospatial_tracking.services.features.feature_policy import PRIMARY_WEATHER_TEMPORAL_ROLE

        cfg = _policy().config_dict()
        assert cfg["weather_temporal_role"] == "RETROSPECTIVE_REANALYSIS_STATE_PROXY"
        assert cfg["weather_temporal_role"] == PRIMARY_WEATHER_TEMPORAL_ROLE


class TestElevationSafety:
    def test_policy_04_elevation_include_true_rejected(self):
        with pytest.raises(ValueError) as exc_info:
            _policy(elevation_include=True)
        assert str(exc_info.value) == ELEVATION_NOT_YET_IMPLEMENTED_MESSAGE

    def test_policy_04_elevation_include_false_accepted(self):
        assert _policy(elevation_include=False).elevation_include is False


class TestGridAndLookbackValidation:
    def test_policy_05_negative_active_window_days_rejected(self):
        with pytest.raises(ValueError):
            _policy(active_window_days=-1)

    def test_policy_05_zero_grid_half_extent_rejected(self):
        with pytest.raises(ValueError):
            _policy(grid_half_extent_km=0)

    def test_policy_05_negative_grid_cell_size_rejected(self):
        with pytest.raises(ValueError):
            _policy(grid_cell_size_km=-2.5)

    def test_policy_05_zero_lookback_hours_rejected(self):
        with pytest.raises(ValueError):
            _policy(weather_lookback_hours=0)

    def test_policy_05_nan_grid_half_extent_rejected(self):
        with pytest.raises(ValueError):
            _policy(grid_half_extent_km=float("nan"))

    def test_policy_05_valid_config_accepted(self):
        p = _policy(active_window_days=0, grid_half_extent_km=0.1, grid_cell_size_km=0.1, weather_lookback_hours=1)
        assert p.active_window_days == 0


class TestFrozenWorldCoverYearValidation:
    def test_policy_06_valid_frozen_years_accepted(self):
        LandCoverFeaturePolicy(mode="FROZEN_STATIC_REFERENCE", frozen_worldcover_year="2020")
        LandCoverFeaturePolicy(mode="FROZEN_STATIC_REFERENCE", frozen_worldcover_year="2021")

    def test_policy_06_invalid_frozen_year_rejected(self):
        with pytest.raises(ValueError):
            LandCoverFeaturePolicy(mode="FROZEN_STATIC_REFERENCE", frozen_worldcover_year="2019")

    def test_policy_06_missing_frozen_year_rejected(self):
        with pytest.raises(ValueError):
            LandCoverFeaturePolicy(mode="FROZEN_STATIC_REFERENCE")


class TestHostDensitySpeciesValidation:
    def test_unsupported_species_rejected(self):
        with pytest.raises(ValueError):
            _policy(host_density_species=("goat",))

    def test_supported_species_accepted(self):
        assert _policy(host_density_species=("cattle",)).host_density_species == ("cattle",)


class TestHydrologyRadiusInPolicy:
    def test_hydro_policy_01_radius_is_a_policy_field(self):
        p = _policy(hydrology_include=True, hydrorivers_search_radius_km=30.0)
        assert p.hydrorivers_search_radius_km == 30.0

    def test_hydro_policy_01_default_radius_exists(self):
        assert DEFAULT_HYDRORIVERS_SEARCH_RADIUS_KM > 0

    def test_hydro_policy_negative_radius_rejected_when_hydrology_enabled(self):
        with pytest.raises(ValueError):
            _policy(hydrology_include=True, hydrorivers_search_radius_km=-1.0)

    def test_hydro_policy_02_changing_radius_changes_protocol_hash(self):
        p1 = _policy(hydrology_include=True, hydrorivers_search_radius_km=25.0)
        p2 = _policy(hydrology_include=True, hydrorivers_search_radius_km=50.0)
        assert p1.protocol_hash() != p2.protocol_hash()

    def test_hydro_policy_radius_excluded_from_hash_when_hydrology_disabled(self):
        # radius is irrelevant (never used) when hydrology_include=False --
        # changing it must not silently change the hash either (it would
        # be exactly the Part 1 hash-only-no-op the checkpoint forbids)
        p1 = _policy(hydrology_include=False, hydrorivers_search_radius_km=25.0)
        p2 = _policy(hydrology_include=False, hydrorivers_search_radius_km=99.0)
        assert p1.protocol_hash() == p2.protocol_hash()
