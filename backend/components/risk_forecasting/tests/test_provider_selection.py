"""
Unit tests for Disease Forecasting Data Provider Selection & Factory.

Verifies configuration-driven instantiation of ForecastDataProvider implementations,
case-insensitive string handling, safe failure modes, and environment isolation.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

from components.risk_forecasting.integrations import (
    create_forecast_data_provider,
    CsvForecastDataProvider,
    SharedApiForecastDataProvider,
    SharedForecastDataClient,
)


class TestProviderSelection(unittest.TestCase):
    """Test suite for provider factory and environment variable configuration."""

    def setUp(self):
        """Preserve original environment variable state."""
        self._orig_env = os.environ.get("FORECAST_DATA_PROVIDER")

    def tearDown(self):
        """Restore original environment variable state."""
        if self._orig_env is not None:
            os.environ["FORECAST_DATA_PROVIDER"] = self._orig_env
        else:
            os.environ.pop("FORECAST_DATA_PROVIDER", None)

    def test_1_missing_mode_returns_csv_provider(self):
        """Missing mode argument and unset env var defaults to CsvForecastDataProvider."""
        os.environ.pop("FORECAST_DATA_PROVIDER", None)
        provider = create_forecast_data_provider()
        self.assertIsInstance(provider, CsvForecastDataProvider)

    def test_2_blank_mode_returns_csv_provider(self):
        """Blank or whitespace mode string defaults to CsvForecastDataProvider."""
        provider = create_forecast_data_provider(mode="  ")
        self.assertIsInstance(provider, CsvForecastDataProvider)

        os.environ["FORECAST_DATA_PROVIDER"] = "   "
        provider_env = create_forecast_data_provider()
        self.assertIsInstance(provider_env, CsvForecastDataProvider)

    def test_3_explicit_csv_returns_csv_provider(self):
        """Explicit 'csv' mode returns CsvForecastDataProvider."""
        provider = create_forecast_data_provider(mode="csv")
        self.assertIsInstance(provider, CsvForecastDataProvider)

    def test_4_case_normalized_csv_value(self):
        """Case-insensitive string ('CSV', ' Csv ') correctly resolves to CsvForecastDataProvider."""
        provider_upper = create_forecast_data_provider(mode="CSV")
        self.assertIsInstance(provider_upper, CsvForecastDataProvider)

        provider_padded = create_forecast_data_provider(mode="  cSV  ")
        self.assertIsInstance(provider_padded, CsvForecastDataProvider)

    def test_5_invalid_value_fails_closed(self):
        """Unsupported provider mode fails closed by raising ValueError."""
        with self.assertRaises(ValueError) as ctx:
            create_forecast_data_provider(mode="invalid_database_mode")
        self.assertIn("Invalid FORECAST_DATA_PROVIDER mode", str(ctx.exception))

        os.environ["FORECAST_DATA_PROVIDER"] = "mongodb_unsupported"
        with self.assertRaises(ValueError):
            create_forecast_data_provider()

    def test_6_shared_api_without_client_fails(self):
        """Mode 'shared_api' without an injected client raises RuntimeError."""
        with self.assertRaises(RuntimeError) as ctx:
            create_forecast_data_provider(mode="shared_api", shared_client=None)
        self.assertIn("no SharedForecastDataClient instance was supplied", str(ctx.exception))

    def test_7_shared_api_with_client_returns_shared_provider(self):
        """Mode 'shared_api' with injected mock client returns SharedApiForecastDataProvider."""
        mock_client = MagicMock(spec=SharedForecastDataClient)
        provider = create_forecast_data_provider(mode="shared_api", shared_client=mock_client)
        self.assertIsInstance(provider, SharedApiForecastDataProvider)
        self.assertEqual(provider.client, mock_client)

    def test_8_environment_selection_isolation(self):
        """Environment variable changes are isolated per test invocation."""
        os.environ["FORECAST_DATA_PROVIDER"] = "csv"
        p1 = create_forecast_data_provider()
        self.assertIsInstance(p1, CsvForecastDataProvider)

        mock_client = MagicMock(spec=SharedForecastDataClient)
        os.environ["FORECAST_DATA_PROVIDER"] = "shared_api"
        p2 = create_forecast_data_provider(shared_client=mock_client)
        self.assertIsInstance(p2, SharedApiForecastDataProvider)

    def test_9_environment_restoration(self):
        """TearDown reliably restores initial environment state."""
        self.assertEqual(os.environ.get("FORECAST_DATA_PROVIDER"), self._orig_env)


if __name__ == "__main__":
    unittest.main()
