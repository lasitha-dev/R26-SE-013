import os
import unittest
from unittest.mock import patch, MagicMock
import httpx
import pandas as pd

from components.risk_forecasting.config import (
    SRI_LANKA_DISTRICT_CENTROIDS,
    SRI_LANKA_DISTRICTS,
)
from components.risk_forecasting.integrations import (
    create_forecast_data_provider,
    CsvForecastDataProvider,
    LiveWeatherForecastDataProvider,
)


class TestLiveWeatherProvider(unittest.TestCase):

    def test_factory_creation(self):
        provider = create_forecast_data_provider(mode="live_weather")
        self.assertIsInstance(provider, LiveWeatherForecastDataProvider)
        self.assertIsInstance(provider.fallback_provider, CsvForecastDataProvider)

    @patch("httpx.get")
    def test_live_weather_aggregation(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "daily": {
                "precipitation_sum": [1.5, 0.5, 2.0, 0.0, 1.0] + [0.0] * 25,
                "temperature_2m_mean": [25.0, 26.0, 24.0, 27.0, 28.0] + [26.0] * 25,
                "wind_speed_10m_max": [10.0, 12.0, 15.0, 8.0, 11.0] + [10.0] * 25
            },
            "hourly": {
                "precipitation": [0.0, 0.0, 1.0, 2.0, 0.5, 0.0] + [0.0] * (24 * 30 - 6),
                "relative_humidity_2m": [80, 85, 90, 75, 70, 80] + [80] * (24 * 30 - 6)
            }
        }
        mock_get.return_value = mock_response

        csv_provider = CsvForecastDataProvider()
        live_provider = LiveWeatherForecastDataProvider(fallback_provider=csv_provider)

        feature_cols = [
            "rainfall_mm", "rain_lag1", "rain_lag2",
            "temp_lag1", "humidity", "humidity_lag1",
            "wind_speed", "wind_lag1", "rfq", "rfq_lag1",
            "r3h"
        ]

        row_df, fallback_applied, fallback_message, source_year, source_month, data_age_months, data_quality = (
            live_provider.get_feature_row(
                disease="FMD",
                district="Colombo",
                month_num=8,
                year=2026,
                feature_cols=feature_cols,
                district_enc_val=0.0
            )
        )

        self.assertFalse(fallback_applied)
        self.assertIn("LIVE_WEATHER_API", fallback_message)
        self.assertEqual(source_year, 2026)
        self.assertEqual(source_month, 8)
        self.assertEqual(data_age_months, 0)
        self.assertEqual(data_quality, "EXACT_REQUESTED_PERIOD")

        self.assertAlmostEqual(row_df["rainfall_mm"].iloc[0], 5.0)
        self.assertAlmostEqual(row_df["rain_lag1"].iloc[0], 5.0)
        self.assertAlmostEqual(row_df["rain_lag2"].iloc[0], 5.0)
        self.assertAlmostEqual(row_df["temp_lag1"].iloc[0], 26.0)
        self.assertAlmostEqual(row_df["humidity"].iloc[0], 80.0)
        self.assertAlmostEqual(row_df["humidity_lag1"].iloc[0], 80.0)
        self.assertAlmostEqual(row_df["wind_speed"].iloc[0], 10.2)
        self.assertAlmostEqual(row_df["wind_lag1"].iloc[0], 10.2)
        self.assertAlmostEqual(row_df["rfq"].iloc[0], 3.0)
        self.assertAlmostEqual(row_df["rfq_lag1"].iloc[0], 3.0)
        self.assertAlmostEqual(row_df["r3h"].iloc[0], 3.5)

    @patch("httpx.get")
    def test_ttl_caching(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "daily": {
                "precipitation_sum": [1.0] * 30,
                "temperature_2m_mean": [25.0] * 30,
                "wind_speed_10m_max": [10.0] * 30
            },
            "hourly": {
                "precipitation": [0.0] * (24 * 30),
                "relative_humidity_2m": [80] * (24 * 30)
            }
        }
        mock_get.return_value = mock_response

        csv_provider = CsvForecastDataProvider()
        live_provider = LiveWeatherForecastDataProvider(fallback_provider=csv_provider)

        feature_cols = ["rainfall_mm"]

        for _ in range(3):
            live_provider.get_feature_row(
                disease="FMD",
                district="Colombo",
                month_num=8,
                year=2026,
                feature_cols=feature_cols,
                district_enc_val=0.0
            )

        self.assertEqual(mock_get.call_count, 3)

    @patch("httpx.get")
    def test_network_error_fallback(self, mock_get):
        mock_get.side_effect = httpx.TimeoutException("Connection timed out")

        csv_provider = CsvForecastDataProvider()
        live_provider = LiveWeatherForecastDataProvider(fallback_provider=csv_provider)

        feature_cols = ["rainfall_mm"]

        row_df, fallback_applied, fallback_message, source_year, source_month, data_age_months, data_quality = (
            live_provider.get_feature_row(
                disease="FMD",
                district="Colombo",
                month_num=8,
                year=2026,
                feature_cols=feature_cols,
                district_enc_val=0.0
            )
        )

        self.assertTrue(fallback_applied)
        self.assertIn("Weather API request failed", fallback_message)

    def test_all_district_centroids(self):
        for district in SRI_LANKA_DISTRICTS:
            self.assertIn(district, SRI_LANKA_DISTRICT_CENTROIDS)
            centroid = SRI_LANKA_DISTRICT_CENTROIDS[district]
            self.assertIn("lat", centroid)
            self.assertIn("lon", centroid)
            self.assertIsInstance(centroid["lat"], float)
            self.assertIsInstance(centroid["lon"], float)
