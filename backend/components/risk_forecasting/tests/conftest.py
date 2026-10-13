import pytest

def _inject_in_memory_services_generator():
    """Inner generator for explicit testing without pytest fixture interception."""
    from components.risk_forecasting.routes import (
        forecast_follow_up_service,
        recipient_query_service,
        forecast_record_service,
        advisory_service
    )
    from components.risk_forecasting.integrations.vet_directory import InMemoryVeterinaryOfficerDirectory
    from components.risk_forecasting.integrations.recipient_directory import InMemoryRecipientDirectory
    from components.risk_forecasting.repositories.forecast_record_repository import InMemoryForecastRecordRepository
    
    # Save prior state
    old_forecast_repo = forecast_record_service.repository
    old_vet_dir = forecast_follow_up_service.vet_dir
    old_rec_dir = recipient_query_service.recipient_dir
    old_adv_rec_dir = advisory_service.recipient_dir
    
    forecast_record_service.repository = InMemoryForecastRecordRepository()
    forecast_follow_up_service.vet_dir = InMemoryVeterinaryOfficerDirectory()
    recipient_query_service.recipient_dir = InMemoryRecipientDirectory()
    advisory_service.recipient_dir = recipient_query_service.recipient_dir

    try:
        yield
    finally:
        # Exact restoration of prior values
        forecast_record_service.repository = old_forecast_repo
        forecast_follow_up_service.vet_dir = old_vet_dir
        recipient_query_service.recipient_dir = old_rec_dir
        advisory_service.recipient_dir = old_adv_rec_dir

@pytest.fixture(autouse=True, scope="function")
def inject_in_memory_services():
    """
    Explicitly injects in-memory fake implementations for all risk forecasting tests.
    Since some tests import `main.app`, which explicitly injects Mongo for production,
    we override them back to InMemory for these unit tests.
    """
    yield from _inject_in_memory_services_generator()
