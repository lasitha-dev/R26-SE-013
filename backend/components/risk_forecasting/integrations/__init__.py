"""
Integrations Package for Disease Forecasting Component.

Exposes data provider abstractions, client contracts, and factory initializers.
"""

from backend.components.risk_forecasting.integrations.forecast_data_provider import (
    ForecastDataProvider,
    CsvForecastDataProvider,
    SharedApiForecastDataProvider,
)
from backend.components.risk_forecasting.integrations.shared_forecast_client import (
    SharedForecastRecord,
    SharedForecastDataClient,
)
from backend.components.risk_forecasting.integrations.provider_factory import (
    create_forecast_data_provider,
)

__all__ = [
    "ForecastDataProvider",
    "CsvForecastDataProvider",
    "SharedApiForecastDataProvider",
    "SharedForecastRecord",
    "SharedForecastDataClient",
    "create_forecast_data_provider",
]
