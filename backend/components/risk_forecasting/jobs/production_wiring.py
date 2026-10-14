"""Production wiring for the monthly job (Atlas repositories).

Kept in its own module and imported lazily by the job's CLI path only, so importing the job
(for example from tests) never loads database code or reads backend/.env.
"""

from components.risk_forecasting.repositories.mongo_advisory_repository import MongoAdvisoryRepository
from components.risk_forecasting.repositories.mongo_follow_up_repository import MongoFollowUpRepository
from components.risk_forecasting.repositories.mongo_forecast_record_repository import MongoForecastRecordRepository
from components.risk_forecasting.routes import get_app_db
from components.risk_forecasting.services.forecast_v2_service import ForecastV2Service


def build_default_service() -> ForecastV2Service:
    repository = MongoForecastRecordRepository()
    advisories, follow_ups = MongoAdvisoryRepository(), MongoFollowUpRepository()

    def dependency_counter(forecast_id):
        return {"advisories": advisories.list(forecast_id=forecast_id, limit=1, offset=0)[1],
                "follow_ups": follow_ups.list(forecast_id=forecast_id, limit=1, offset=0)[1]}

    return ForecastV2Service(repository_getter=lambda: repository, app_db_factory=get_app_db,
                             dependency_counter=dependency_counter)


def build_outlook_service():
    """Outlook service on the Atlas collection. Constructing it performs no I/O (no index, no collection)."""
    from components.risk_forecasting.repositories.outlook_repository import MongoOutlookRepository
    from components.risk_forecasting.services.seasonal_outlook_service import SeasonalOutlookService
    repository = MongoOutlookRepository()
    return SeasonalOutlookService(repository_getter=lambda: repository)
