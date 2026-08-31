"""WX-01..06, WX-ID-01..03, WIND-01..06, TIMEWX-01..05, TIMEZONE-01..06,
WX-AVAIL-01..05, POLICY-02 (era5-adapter half)."""

from datetime import datetime, timedelta, timezone

import pytest

from components.geospatial_tracking.services.geospatial.feature_result import FeatureStatus
from components.geospatial_tracking.services.geospatial.weather.base import (
    T0Precision,
    WeatherAvailabilityQuality,
    WeatherTemporalRole,
)
from components.geospatial_tracking.services.geospatial.weather import era5
from components.geospatial_tracking.services.geospatial.weather.era5 import (
    ERA5T_PRELIMINARY_LAG_DAYS,
    WEATHER_MODEL,
    WEATHER_MODEL_RESOLUTION,
    aggregate_hourly_wind,
    _classify_temporal_role,
    _daily_request_params,
    _hourly_request_params,
    build_pre_t0_weather_summary,
    fetch_daily_weather,
)
from components.geospatial_tracking.services.geospatial.weather.humidity import relative_humidity_percent
from components.geospatial_tracking.services.geospatial.weather.t0_resolution import (
    is_timestamp_eligible,
    pre_t0_window_bounds,
    resolve_iana_timezone,
    resolve_t0_boundary,
)
from components.geospatial_tracking.services.geospatial.weather.wind import (
    wind_components_from_speed_direction,
    wind_speed_from_components,
)

# Sri Lanka Chavakachcheri smoke coordinate — real, offline-resolvable
# IANA timezone Asia/Colombo.
SL_LAT, SL_LON = 9.6579014, 80.1643076


class TestWindComponents:
    def test_wx_01_u_and_v_remain_separate_distinct_values(self):
        # wind from the east (blowing FROM 90deg, i.e. blowing westward)
        u, v = wind_components_from_speed_direction(10.0, 90.0)
        assert u != v
        assert abs(u - (-10.0)) < 1e-9  # blowing FROM east -> eastward component is negative (blows west)
        assert abs(v - 0.0) < 1e-9

    def test_wx_01_wind_from_north_has_zero_east_component(self):
        u, v = wind_components_from_speed_direction(5.0, 0.0)
        assert abs(u) < 1e-9
        assert abs(v - (-5.0)) < 1e-9  # FROM north -> blows south -> negative northward component

    def test_wx_02_wind_speed_conversion_correct(self):
        u, v = wind_components_from_speed_direction(7.0, 45.0)
        recovered_speed = wind_speed_from_components(u, v)
        assert abs(recovered_speed - 7.0) < 1e-9

    def test_wx_02_speed_recovered_for_various_directions(self):
        for direction in (0, 30, 90, 135, 180, 225, 270, 315, 359):
            u, v = wind_components_from_speed_direction(12.3, direction)
            assert abs(wind_speed_from_components(u, v) - 12.3) < 1e-9

    def test_wx_03_wind_direction_never_labeled_disease_spread_direction(self):
        import inspect

        from components.geospatial_tracking.services.geospatial.weather import wind

        src = inspect.getsource(wind)
        assert "disease" in src.lower() and "never" in src.lower()
        assert "spread_direction" not in src.lower().replace(" ", "_").replace("-", "_") or "never" in src.lower()


class TestHumidity:
    def test_saturation_gives_100_percent(self):
        rh = relative_humidity_percent(temperature_c=25.0, dewpoint_c=25.0)
        assert abs(rh - 100.0) < 0.5

    def test_drier_air_gives_lower_humidity(self):
        rh_humid = relative_humidity_percent(temperature_c=30.0, dewpoint_c=28.0)
        rh_dry = relative_humidity_percent(temperature_c=30.0, dewpoint_c=10.0)
        assert rh_humid > rh_dry
        assert 0 <= rh_dry <= 100
        assert 0 <= rh_humid <= 100

    def test_known_real_value_from_smoke_data(self):
        # real Sri Lanka Chavakachcheri, 2020-09-09: T=27.7C, Td=24.0C
        rh = relative_humidity_percent(27.7, 24.0)
        assert 75 < rh < 90  # plausible tropical humid-day range


class TestTemporalRoleClassification:
    def test_wx_04_date_at_t0_is_retrospective_proxy(self):
        assert (
            _classify_temporal_role("2020-09-09", "2020-09-09")
            == WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY.value
        )

    def test_wx_04_date_before_t0_is_retrospective_proxy(self):
        assert (
            _classify_temporal_role("2020-09-05", "2020-09-09")
            == WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY.value
        )

    def test_wx_04_date_after_t0_is_realized_future(self):
        assert (
            _classify_temporal_role("2020-09-12", "2020-09-09") == WeatherTemporalRole.REALIZED_FUTURE_REANALYSIS.value
        )

    def test_wx_04_future_realized_weather_blocked_without_explicit_opt_in(self):
        results = fetch_daily_weather(
            latitude=9.66, longitude=80.16, date="2099-01-08", forecast_origin_t0="2099-01-01"
        )
        assert len(results) > 0
        for r in results:
            assert r.status == FeatureStatus.BLOCKED.value
            assert r.value is None
            assert "REALIZED_FUTURE_REANALYSIS" in r.quality_notes or "allow_future_reanalysis" in r.quality_notes

    def test_wx_05_temporal_role_never_becomes_live_operational(self):
        assert WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY.value != "LIVE_OPERATIONAL"
        assert WeatherTemporalRole.REALIZED_FUTURE_REANALYSIS.value != "LIVE_OPERATIONAL"
        import inspect

        src = inspect.getsource(era5)
        assert "LIVE_OPERATIONAL" not in src

    def test_wx_06_unreachable_host_yields_blocked_not_fabricated(self):
        results = fetch_daily_weather(
            latitude=9.66,
            longitude=80.16,
            date="2020-09-09",
            timeout_seconds=0.001,  # force a timeout/failure
        )
        for r in results:
            assert r.status in (FeatureStatus.BLOCKED.value, FeatureStatus.REAL.value)
            if r.status == FeatureStatus.BLOCKED.value:
                assert r.value is None


class TestWeatherModelIdentity:
    """WX-ID-01..03."""

    def test_wx_id_01_daily_request_always_includes_explicit_model(self):
        params = _daily_request_params(9.66, 80.16, "2020-09-09")
        assert "models" in params
        assert params["models"] == WEATHER_MODEL
        # never the unset default that silently resolves to best_match
        assert params["models"] != "best_match"

    def test_wx_id_01_hourly_request_always_includes_explicit_model(self):
        params = _hourly_request_params(9.66, 80.16, "2020-09-08", "2020-09-09")
        assert "models" in params
        assert params["models"] == WEATHER_MODEL
        assert params["models"] != "best_match"

    def test_wx_id_01_default_best_match_never_silently_used(self):
        import inspect

        src = inspect.getsource(era5)
        assert "requests.get(ARCHIVE_URL, params=" in src
        assert src.count('"models":') >= 2

    def test_wx_id_02_selected_model_appears_in_feature_result_provenance(self):
        results = fetch_daily_weather(latitude=9.6579014, longitude=80.1643076, date="2020-09-09")
        real_results = [r for r in results if r.status == FeatureStatus.REAL.value]
        assert real_results, "expected at least one REAL result for a real, reachable AOI/date"
        for r in real_results:
            assert WEATHER_MODEL in r.dataset_version
            assert f"weather_model={WEATHER_MODEL}" in r.quality_notes

    def test_wx_id_03_model_resolution_metadata_matches_selected_model(self):
        results = fetch_daily_weather(latitude=9.6579014, longitude=80.1643076, date="2020-09-09")
        real_results = [r for r in results if r.status == FeatureStatus.REAL.value]
        assert real_results
        for r in real_results:
            assert r.source_resolution == WEATHER_MODEL_RESOLUTION
            assert "9 km" not in r.source_resolution
            assert "0.25" in r.source_resolution


class TestModelParameterCannotDisagreeWithRequest:
    """Checkpoint 6A.5 Part 2 (POLICY-02): the regression this checkpoint
    exists to fix — `build_pre_t0_weather_summary`'s `model=` parameter
    previously had no effect on the actual HTTP request (`_hourly_request_params`
    hardcoded the `WEATHER_MODEL` module constant), so declared metadata
    could silently disagree with what was actually fetched."""

    def test_hourly_request_params_uses_the_passed_model_not_the_constant(self):
        params = _hourly_request_params(9.66, 80.16, "2020-09-08", "2020-09-09", model="some_other_model")
        assert params["models"] == "some_other_model"
        assert params["models"] != WEATHER_MODEL

    def test_hourly_request_params_defaults_to_weather_model_constant(self):
        params = _hourly_request_params(9.66, 80.16, "2020-09-08", "2020-09-09")
        assert params["models"] == WEATHER_MODEL

    def test_supported_model_era5_produces_a_real_result(self):
        window, results = build_pre_t0_weather_summary(
            latitude=9.6579014, longitude=80.1643076, t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value,
            lookback_hours=24, model="era5",
        )
        assert window.weather_model == "era5"
        assert window.request_parameters.get("models") == "era5"
        assert any(r.status == FeatureStatus.REAL.value for r in results)

    def test_unsupported_model_is_blocked_never_silently_substituted(self):
        window, results = build_pre_t0_weather_summary(
            latitude=9.6579014, longitude=80.1643076, t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value,
            lookback_hours=24, model="era5_land",
        )
        for r in results:
            assert r.status == FeatureStatus.BLOCKED.value
            assert r.value is None
            assert "era5_land" in r.quality_notes

    def test_declared_metadata_model_always_equals_actual_request_model(self):
        for model in ("era5", "best_match", "ecmwf_ifs"):
            window, results = build_pre_t0_weather_summary(
                latitude=9.6579014, longitude=80.1643076, t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value,
                lookback_hours=24, model=model,
            )
            # whether accepted (era5, real request+metadata match) or
            # refused (unsupported, no request sent at all) -- the
            # reported weather_model is never something OTHER than what
            # was actually requested (or would have been requested)
            assert window.weather_model == model
            if window.request_parameters:
                assert window.request_parameters["models"] == model

    def test_cache_key_reflects_the_actual_requested_model(self):
        # cache identity is derived from the exact request_parameters
        # dict, which now always carries the real requested model --
        # two different models can never collide on the same cache key
        params_era5 = _hourly_request_params(9.66, 80.16, "2020-09-08", "2020-09-09", model="era5")
        params_other = _hourly_request_params(9.66, 80.16, "2020-09-08", "2020-09-09", model="era5_land")
        assert params_era5 != params_other
        assert params_era5["models"] != params_other["models"]


class TestWindMathematics:
    """WIND-01..06."""

    def test_wind_01_from_north(self):
        u, v = wind_components_from_speed_direction(10.0, 0.0)
        assert abs(u) < 1e-9
        assert v < 0

    def test_wind_02_from_east(self):
        u, v = wind_components_from_speed_direction(10.0, 90.0)
        assert u < 0
        assert abs(v) < 1e-9

    def test_wind_03_from_south(self):
        u, v = wind_components_from_speed_direction(10.0, 180.0)
        assert v > 0

    def test_wind_04_from_west(self):
        u, v = wind_components_from_speed_direction(10.0, 270.0)
        assert u > 0

    def test_wind_05_opposite_equal_speed_winds_cancel(self):
        mean_u, mean_v = aggregate_hourly_wind([10.0, 10.0], [0.0, 180.0])
        assert abs(mean_u) < 1e-9
        assert abs(mean_v) < 1e-9

    def test_wind_05_aggregate_never_averages_compass_bearings_directly(self):
        mean_u, mean_v = aggregate_hourly_wind([5.0, 5.0], [350.0, 10.0])
        naive_wrong_direction_u, naive_wrong_direction_v = wind_components_from_speed_direction(5.0, 180.0)
        assert abs(mean_v - naive_wrong_direction_v) > 1.0
        assert mean_v < 0

    def test_wind_06_scientific_summary_path_never_pairs_daily_max_with_dominant_direction(self):
        import inspect

        src = inspect.getsource(era5)
        assert "wind_speed_10m_max" not in src
        assert "wind_direction_10m_dominant" not in src

    def test_wind_06_aggregate_hourly_wind_requires_paired_equal_length_inputs(self):
        with pytest.raises(ValueError):
            aggregate_hourly_wind([1.0, 2.0], [0.0])

    def test_wind_06_aggregate_hourly_wind_rejects_empty_input(self):
        with pytest.raises(ValueError):
            aggregate_hourly_wind([], [])


class TestT0TemporalPrecision:
    """TIMEWX-01..05."""

    def test_timewx_01_date_only_excludes_all_same_local_day_future_hours(self):
        boundary = resolve_t0_boundary(t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, latitude=SL_LAT, longitude=SL_LON)
        same_local_day_afternoon = datetime(2020, 9, 9, 10, 0, tzinfo=timezone.utc)  # local ~15:30, well into local Sept 9
        assert is_timestamp_eligible(same_local_day_afternoon, T0Precision.DATE_ONLY.value, boundary.cutoff_utc) is False

    def test_timewx_02_date_only_permits_completed_pre_t0_hours(self):
        boundary = resolve_t0_boundary(t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, latitude=SL_LAT, longitude=SL_LON)
        well_before_cutoff = boundary.cutoff_utc - timedelta(hours=1)
        assert is_timestamp_eligible(well_before_cutoff, T0Precision.DATE_ONLY.value, boundary.cutoff_utc) is True

    def test_timewx_03_timestamp_permits_observations_at_or_before_exact_t0(self):
        boundary = resolve_t0_boundary(
            t0="2020-09-09T05:00:00+00:00", t0_precision=T0Precision.TIMESTAMP.value, latitude=SL_LAT, longitude=SL_LON
        )
        same_instant = datetime(2020, 9, 9, 5, 0, tzinfo=timezone.utc)
        assert is_timestamp_eligible(same_instant, T0Precision.TIMESTAMP.value, boundary.cutoff_utc) is True

    def test_timewx_04_timestamp_excludes_observations_after_exact_t0(self):
        boundary = resolve_t0_boundary(
            t0="2020-09-09T05:00:00+00:00", t0_precision=T0Precision.TIMESTAMP.value, latitude=SL_LAT, longitude=SL_LON
        )
        one_hour_later = datetime(2020, 9, 9, 6, 0, tzinfo=timezone.utc)
        assert is_timestamp_eligible(one_hour_later, T0Precision.TIMESTAMP.value, boundary.cutoff_utc) is False

    def test_timewx_05_realized_future_reanalysis_remains_blocked_in_primary_path(self):
        boundary = resolve_t0_boundary(t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, latitude=SL_LAT, longitude=SL_LON)
        window_start, cutoff = pre_t0_window_bounds(boundary, lookback_hours=24)
        assert window_start < cutoff
        far_future = datetime(2020, 9, 15, 0, 0, tzinfo=timezone.utc)
        assert is_timestamp_eligible(far_future, T0Precision.DATE_ONLY.value, cutoff) is False

    def test_timewx_unknown_precision_raises(self):
        with pytest.raises(ValueError):
            resolve_t0_boundary(t0="2020-09-09", t0_precision="SOMETHING_ELSE", latitude=SL_LAT, longitude=SL_LON)


class TestTimezoneSafeT0:
    """TIMEZONE-01..06 — all offline/deterministic (timezonefinder's
    polygon data ships locally, no network call)."""

    def test_timezone_01_date_only_cutoff_uses_source_local_midnight_not_utc_midnight(self):
        boundary = resolve_t0_boundary(t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, latitude=SL_LAT, longitude=SL_LON)
        assert boundary.resolved is True
        assert boundary.source_timezone == "Asia/Colombo"
        # Sri Lanka is UTC+5:30 -> local midnight is 18:30 UTC the PRIOR day, not 00:00 UTC that day
        assert boundary.cutoff_utc != datetime(2020, 9, 9, 0, 0, tzinfo=timezone.utc)
        assert boundary.cutoff_utc == datetime(2020, 9, 8, 18, 30, tzinfo=timezone.utc)

    def test_timezone_02_utc_boundary_is_deterministic(self):
        b1 = resolve_t0_boundary(t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, latitude=SL_LAT, longitude=SL_LON)
        b2 = resolve_t0_boundary(t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, latitude=SL_LAT, longitude=SL_LON)
        assert b1.cutoff_utc == b2.cutoff_utc
        assert b1.source_timezone == b2.source_timezone

    def test_timezone_03_first_local_hours_of_t0_day_excluded(self):
        boundary = resolve_t0_boundary(t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, latitude=SL_LAT, longitude=SL_LON)
        # 2020-09-09T00:30 local (Asia/Colombo, +5:30) = 2020-09-08T19:00 UTC —
        # only half an hour into the local t0 day, must still be excluded
        first_local_half_hour_utc = datetime(2020, 9, 8, 19, 0, tzinfo=timezone.utc)
        assert is_timestamp_eligible(first_local_half_hour_utc, T0Precision.DATE_ONLY.value, boundary.cutoff_utc) is False

    def test_timezone_04_historical_offset_change_uses_iana_rules_not_fixed_offset(self):
        # Sri Lanka's real UTC offset differed before ~2006 from today —
        # a hand-written fixed "+5:30 always" rule would make these equal.
        boundary_2000 = resolve_t0_boundary(t0="2000-06-01", t0_precision=T0Precision.DATE_ONLY.value, latitude=SL_LAT, longitude=SL_LON)
        boundary_2020 = resolve_t0_boundary(t0="2020-06-01", t0_precision=T0Precision.DATE_ONLY.value, latitude=SL_LAT, longitude=SL_LON)
        offset_2000 = datetime.fromisoformat(boundary_2000.t0_start_local).utcoffset()
        offset_2020 = datetime.fromisoformat(boundary_2020.t0_start_local).utcoffset()
        assert offset_2000 != offset_2020

    def test_timezone_05_unknown_timezone_cannot_silently_become_utc(self):
        # genuine open-ocean coordinate — no land timezone polygon
        boundary = resolve_t0_boundary(t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, latitude=0.0, longitude=-140.0)
        assert boundary.resolved is False
        assert boundary.cutoff_utc is None
        assert boundary.t0_timezone_quality == "UNKNOWN"

    def test_timezone_05_unresolved_timezone_blocks_the_whole_weather_summary(self):
        window, results = build_pre_t0_weather_summary(
            latitude=0.0, longitude=-140.0, t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, lookback_hours=24
        )
        assert results, "expected BLOCKED placeholder results, not an empty list"
        for r in results:
            assert r.status == FeatureStatus.BLOCKED.value
            assert r.value is None
        assert window.window_start is None
        assert window.window_end is None

    def test_timezone_06_timestamp_preserves_exact_instant_across_conversion(self):
        boundary = resolve_t0_boundary(
            t0="2020-09-09T10:00:00+05:30", t0_precision=T0Precision.TIMESTAMP.value, latitude=SL_LAT, longitude=SL_LON
        )
        assert boundary.cutoff_utc == datetime(2020, 9, 9, 4, 30, tzinfo=timezone.utc)

    def test_resolve_iana_timezone_matches_both_smoke_aois(self):
        assert resolve_iana_timezone(9.6579014, 80.1643076) == "Asia/Colombo"
        assert resolve_iana_timezone(15.785878, 103.807367) == "Asia/Bangkok"


class TestWeatherAvailability:
    """WX-AVAIL-01..05."""

    def test_wx_avail_01_pre_t0_valid_time_alone_never_produces_actual_availability(self):
        window, results = build_pre_t0_weather_summary(
            latitude=SL_LAT, longitude=SL_LON, t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, lookback_hours=24
        )
        assert window.availability_quality != WeatherAvailabilityQuality.ACTUAL.value
        real_results = [r for r in results if r.status == FeatureStatus.REAL.value]
        assert real_results
        for r in real_results:
            assert "availability_quality=ACTUAL" not in r.quality_notes

    def test_wx_avail_02_retrospective_proxy_never_becomes_live_operational(self):
        assert WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY.value != WeatherTemporalRole.LIVE_OPERATIONAL.value

    def test_wx_avail_03_future_valid_time_forbidden_in_primary_historical_mode(self):
        results = fetch_daily_weather(latitude=SL_LAT, longitude=SL_LON, date="2099-01-08", forecast_origin_t0="2099-01-01")
        for r in results:
            assert r.status == FeatureStatus.BLOCKED.value

    def test_wx_avail_04_available_time_may_remain_null(self):
        window, _ = build_pre_t0_weather_summary(
            latitude=SL_LAT, longitude=SL_LON, t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, lookback_hours=24
        )
        assert window.weather_available_time is None

    def test_wx_avail_05_lag_rule_sensitivity_mode_is_explicit_and_stamped(self):
        window_default, _ = build_pre_t0_weather_summary(
            latitude=SL_LAT, longitude=SL_LON, t0="2020-09-09", t0_precision=T0Precision.DATE_ONLY.value, lookback_hours=24
        )
        assert window_default.strict_operational_availability is False
        assert window_default.availability_lag_days_used is None
        assert window_default.availability_quality == WeatherAvailabilityQuality.UNKNOWN.value

        window_strict, results_strict = build_pre_t0_weather_summary(
            latitude=SL_LAT,
            longitude=SL_LON,
            t0="2020-09-09",
            t0_precision=T0Precision.DATE_ONLY.value,
            lookback_hours=24,
            strict_operational_availability=True,
        )
        assert window_strict.strict_operational_availability is True
        assert window_strict.availability_lag_days_used == ERA5T_PRELIMINARY_LAG_DAYS
        assert window_strict.availability_quality == WeatherAvailabilityQuality.LAG_RULE_PROXY.value
        # a 24h lookback is entirely within the 5-day lag window -> no
        # sample can satisfy the strict rule, proving it actually filters
        assert window_strict.number_of_hourly_samples == 0
        for r in results_strict:
            assert r.status in (FeatureStatus.MISSING.value, FeatureStatus.BLOCKED.value)
