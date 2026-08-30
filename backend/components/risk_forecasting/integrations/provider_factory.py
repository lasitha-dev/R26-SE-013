"""
Factory module for Disease Forecasting Data Provider selection.

Supports configuration-driven selection between standalone CSV data access
and shared-data API client integration via FORECAST_DATA_PROVIDER env variable.
"""

import os
from typing import Optional
from components.risk_forecasting.integrations.forecast_data_provider import (
    ForecastDataProvider,
    CsvForecastDataProvider,
    SharedApiForecastDataProvider,
)
from components.risk_forecasting.integrations.live_weather_provider import (
    LiveWeatherForecastDataProvider,
)
from components.risk_forecasting.integrations.shared_forecast_client import (
    SharedForecastDataClient,
)


def create_forecast_data_provider(
    mode: Optional[str] = None,
    shared_client: Optional[SharedForecastDataClient] = None,
) -> ForecastDataProvider:
    """
    Creates and returns a ForecastDataProvider instance based on requested or configured mode.

    Args:
        mode: Provider mode string ("csv" or "shared_api"). If None, reads FORECAST_DATA_PROVIDER env var.
        shared_client: SharedForecastDataClient instance required if mode is "shared_api".

    Returns:
        ForecastDataProvider implementation (CsvForecastDataProvider or SharedApiForecastDataProvider).

    Raises:
        ValueError: If mode is unsupported.
        RuntimeError: If mode is 'shared_api' but shared_client is not injected.
    """
    if mode is None:
        mode = os.getenv("FORECAST_DATA_PROVIDER", "csv")

    normalized_mode = mode.strip().lower() if mode and isinstance(mode, str) else "csv"
    if not normalized_mode:
        normalized_mode = "csv"

    if normalized_mode == "csv":
        return CsvForecastDataProvider()

    if normalized_mode == "shared_api":
        if shared_client is None:
            raise RuntimeError(
                "FORECAST_DATA_PROVIDER is configured as 'shared_api' but no "
                "SharedForecastDataClient instance was supplied."
            )
        return SharedApiForecastDataProvider(client=shared_client)

    if normalized_mode == "live_weather":
        fallback = (
            SharedApiForecastDataProvider(client=shared_client)
            if shared_client
            else CsvForecastDataProvider()
        )
        return LiveWeatherForecastDataProvider(fallback_provider=fallback)

    raise ValueError(
        f"Invalid FORECAST_DATA_PROVIDER mode '{mode}'. Supported modes are 'csv', 'shared_api', or 'live_weather'."
    )
