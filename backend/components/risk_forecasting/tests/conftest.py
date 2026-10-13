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
        advisory_service
    )
    from components.risk_forecasting.integrations.vet_directory import InMemoryVeterinaryOfficerDirectory
    from components.risk_forecasting.integrations.recipient_directory import InMemoryRecipientDirectory
    from components.risk_forecasting.repositories.forecast_record_repository import InMemoryForecastRecordRepository

    # Save prior state of every attribute a test could rebind
    saved = []
    for module_name, service_name, attribute in _RESTORED_ATTRIBUTES:
        service = getattr(importlib.import_module(module_name), service_name)
        saved.append((service, attribute, getattr(service, attribute)))

    forecast_record_service.repository = InMemoryForecastRecordRepository()
    forecast_follow_up_service.vet_dir = InMemoryVeterinaryOfficerDirectory()
    recipient_query_service.recipient_dir = InMemoryRecipientDirectory()
    advisory_service.recipient_dir = recipient_query_service.recipient_dir

    try:
        yield
    finally:
        # Exact restoration of prior values
        for service, attribute, value in reversed(saved):
            setattr(service, attribute, value)

@pytest.fixture(autouse=True, scope="function")
def inject_in_memory_services():
    """
    Explicitly injects in-memory fake implementations for all risk forecasting tests.
    Since some tests import `main.app`, which explicitly injects Mongo for production,
    we override them back to InMemory for these unit tests.
    """
    yield from _inject_in_memory_services_generator()
