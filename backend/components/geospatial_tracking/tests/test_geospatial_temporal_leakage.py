"""LEAK-01/02/03 (master-prompt Part 16)."""

from components.geospatial_tracking.services.geospatial.host_density.fao_glw import (
    TEMPORAL_ROLE as GLW_TEMPORAL_ROLE,
)
from components.geospatial_tracking.services.geospatial.temporal_leakage import (
    host_density_used_as_exact_truth,
    landcover_year_mismatches_forecast_year,
    weather_leaks_future_information,
)
from components.geospatial_tracking.services.geospatial.weather.base import WeatherTemporalRole


def test_leak_01_worldcover_2021_for_2020_forecast_is_flagged():
    assert landcover_year_mismatches_forecast_year("v200 (2021)", "2020") is True


def test_leak_01_worldcover_matching_year_is_not_flagged():
    assert landcover_year_mismatches_forecast_year("v200 (2021)", "2021") is False
    assert landcover_year_mismatches_forecast_year("v100 (2020)", "2020") is False


def test_leak_02_glw_real_adapter_declares_static_reference_proxy():
    # the adapter's own constant, not a re-typed literal — catches drift
    # if fao_glw.py's TEMPORAL_ROLE is ever changed without updating this
    assert GLW_TEMPORAL_ROLE == "STATIC_REFERENCE_PROXY"
    assert host_density_used_as_exact_truth(GLW_TEMPORAL_ROLE) is False


def test_leak_02_host_density_treated_as_live_truth_is_flagged():
    assert host_density_used_as_exact_truth("LIVE_OPERATIONAL") is True
    assert host_density_used_as_exact_truth("EXACT_CENSUS") is True


def test_leak_03_future_reanalysis_is_flagged_as_leakage():
    assert weather_leaks_future_information(WeatherTemporalRole.REALIZED_FUTURE_REANALYSIS.value) is True


def test_leak_03_retrospective_reanalysis_proxy_is_not_flagged():
    assert weather_leaks_future_information(WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY.value) is False
