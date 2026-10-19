import pytest

# Every (module, service attribute) that setup_production_services() or a test can rebind.
# All are restored after each test so one test cannot leak a Mongo adapter into another.
_RESTORED_ATTRIBUTES = (
    ("components.risk_forecasting.routes", "forecast_record_service", "repository"),
    ("components.risk_forecasting.routes", "forecast_follow_up_service", "vet_dir"),
    ("components.risk_forecasting.routes", "forecast_follow_up_service", "follow_up_repo"),
    ("components.risk_forecasting.routes", "recipient_query_service", "recipient_dir"),
    ("components.risk_forecasting.routes", "advisory_service", "advisory_repo"),
    ("components.risk_forecasting.routes", "advisory_service", "recipient_dir"),
    ("components.risk_forecasting.services.notification_service", "notification_service", "recipient_dir"),
    ("components.risk_forecasting.routes", "fmd_service", "data_provider"),
    ("components.risk_forecasting.routes", "lsd_service", "data_provider"),
)


def _inject_in_memory_services_generator():
    """Inner generator for explicit testing without pytest fixture interception."""
    import importlib

    from components.risk_forecasting.routes import (
        forecast_follow_up_service,
        recipient_query_service,
        forecast_record_service,
        advisory_service,
        fmd_service,
        lsd_service,
    )
    from components.risk_forecasting.services.notification_service import notification_service
    from components.risk_forecasting.integrations.forecast_data_provider import CsvForecastDataProvider
    from components.risk_forecasting.integrations.vet_directory import InMemoryVeterinaryOfficerDirectory
    from components.risk_forecasting.integrations.recipient_directory import InMemoryRecipientDirectory
    from components.risk_forecasting.repositories.forecast_record_repository import InMemoryForecastRecordRepository
    from components.risk_forecasting.repositories.advisory_repository import InMemoryAdvisoryRepository
    from components.risk_forecasting.repositories.follow_up_repository import InMemoryFollowUpRepository

    # Save prior state of every attribute a test could rebind
    missing = object()
    saved = []
    for module_name, service_name, attribute in _RESTORED_ATTRIBUTES:
        service = getattr(importlib.import_module(module_name), service_name)
        saved.append((service, attribute, getattr(service, attribute, missing)))

    forecast_record_service.repository = InMemoryForecastRecordRepository()
    forecast_follow_up_service.vet_dir = InMemoryVeterinaryOfficerDirectory()
    forecast_follow_up_service.follow_up_repo = InMemoryFollowUpRepository()
    advisory_service.advisory_repo = InMemoryAdvisoryRepository()
    recipient_query_service.recipient_dir = InMemoryRecipientDirectory()
    advisory_service.recipient_dir = recipient_query_service.recipient_dir
    notification_service.recipient_dir = recipient_query_service.recipient_dir
    # Importing main during collection installs production adapters. Replace the data
    # providers as well, so legacy inference tests cannot query MongoDB or live weather.
    provider = CsvForecastDataProvider()
    fmd_service.data_provider = provider
    lsd_service.data_provider = provider

    try:
        yield
    finally:
        # Exact restoration of prior values
        for service, attribute, value in reversed(saved):
            if value is missing:
                delattr(service, attribute)
            else:
                setattr(service, attribute, value)

@pytest.fixture(autouse=True, scope="function")
def inject_in_memory_services():
    """
    Explicitly injects in-memory fake implementations for all risk forecasting tests.
    Since some tests import `main.app`, which explicitly injects Mongo for production,
    we override them back to InMemory for these unit tests.
    """
    yield from _inject_in_memory_services_generator()
