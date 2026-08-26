"""
Forecast Record Repository Package.
Provides storage abstractions and concrete implementations for immutable forecast decision records.
"""

from backend.components.risk_forecasting.repositories.forecast_record_repository import (
    ForecastRecordRepository,
    InMemoryForecastRecordRepository,
)

__all__ = [
    "ForecastRecordRepository",
    "InMemoryForecastRecordRepository",
]
