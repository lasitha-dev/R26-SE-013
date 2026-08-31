import dns.resolver
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8']

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from core.database import db, farms_collection
from core.security import JWT_SECRET, JWT_ALGORITHM
from fastapi.middleware.cors import CORSMiddleware
from components.health_anomaly.router import router as health_anomaly_router
import jwt
import uvicorn

from components.smart_diagnostics.config import settings
from components.smart_diagnostics.implementations.yolo_detector import YOLODetector
from components.smart_diagnostics.implementations.vit_classifier import ViTClassifier
from components.smart_diagnostics.implementations.mask_rcnn_segmenter import MaskRCNNSegmenter
from components.smart_diagnostics.routes import router as sd_router

from components.risk_forecasting.routes import router as risk_forecasting_router, setup_production_services

from components.geospatial_tracking.api.router import router as geospatial_router
from components.geospatial_tracking.api.operational_router_factory import create_operational_context_router
from components.geospatial_tracking.api.operational_events_router_factory import create_operational_events_router
from components.geospatial_tracking.api.my_area_router_factory import create_my_area_router
from components.geospatial_tracking.api.analysis_trends_router_factory import create_analysis_trends_router

from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext
from components.geospatial_tracking.repositories.provider import set_repository_factory_override
from components.geospatial_tracking.repositories.mongo_repository import MongoOutbreakRepository
from components.geospatial_tracking.repositories.host_operational_adapter import MongoOperationalDataPort
from components.geospatial_tracking.repositories.mongo_case_event_source import DeltaPollingCaseEventSource
from components.geospatial_tracking.repositories.scientific_read_port import RepositoryScientificReadPort
from components.geospatial_tracking.services.operational.event_stream_service import OperationalEventStreamService

def create_app() -> FastAPI:
    app = FastAPI(title="ADRS Core Backend", version="1.0.0")
    # Development CORS: allow Vite dev server and localhost
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://localhost:3000", "http://localhost:8000", "*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(sd_router)
    app.include_router(health_anomaly_router, prefix="/api")
    app.include_router(risk_forecasting_router, prefix="/api/v1/risk-forecasting", tags=["Risk Forecasting"])
    setup_production_services()

    # Mount base Geospatial API and WebSocket
    app.include_router(geospatial_router)

    # Initialize Geospatial Mongo Outbreak Repository
    sync_db = db.delegate
    def _create_mongo_repo():
        return MongoOutbreakRepository(
            animal_reports_collection=sync_db["geospatial_animal_reports"],
            outbreak_episodes_collection=sync_db["geospatial_outbreak_episodes"],
            historical_outbreak_records_collection=sync_db["geospatial_historical_outbreak_records"],
            prediction_runs_collection=sync_db["geospatial_prediction_runs"],
        )

    set_repository_factory_override(_create_mongo_repo)
    try:
        init_repo = _create_mongo_repo()
        init_repo.init_schema()
    except Exception as e:
        print(f"[GEOSPATIAL SCHEMA INIT NOTICE]: {e}")

    # Geospatial Authenticated Vet dependency
    async def get_authenticated_vet_context(authorization: str | None = Header(None)) -> AuthenticatedVetContext | None:
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            email = payload.get("sub")
            role = payload.get("role", "")
            if not email:
                return None
            return AuthenticatedVetContext(email=email, role=role)
        except Exception:
            return None

    # Wire Geospatial Operational & Analytics Port Services
    operational_data_port = MongoOperationalDataPort(
        vets_collection=db.vets,
        farms_collection=db.farms,
        diagnostic_cases_collection=db.diagnostic_cases,
    )
    delta_event_source = DeltaPollingCaseEventSource(
        diagnostic_cases_collection=db.diagnostic_cases,
        poll_interval_seconds=15.0,
    )
    event_stream_service = OperationalEventStreamService(
        port=operational_data_port,
        source=delta_event_source,
    )
    scientific_read_port = RepositoryScientificReadPort()

    # Create & Mount Geospatial Factory Routers
    operational_context_router = create_operational_context_router(
        get_authenticated_vet_context=get_authenticated_vet_context,
        get_operational_data_port=lambda: operational_data_port,
    )
    operational_events_router = create_operational_events_router(
        get_authenticated_vet_context=get_authenticated_vet_context,
        get_event_stream_service=lambda: event_stream_service,
    )
    my_area_router = create_my_area_router(
        get_authenticated_vet_context=get_authenticated_vet_context,
        get_operational_data_port=lambda: operational_data_port,
        get_scientific_read_port=lambda: scientific_read_port,
    )
    analysis_trends_router = create_analysis_trends_router(
        get_authenticated_vet_context=get_authenticated_vet_context,
        get_scientific_read_port=lambda: scientific_read_port,
    )

    app.include_router(operational_context_router)
    app.include_router(operational_events_router)
    app.include_router(my_area_router)
    app.include_router(analysis_trends_router)


    # Attach configuration and lazy model wrappers to app state.
    app.state.settings = settings
    app.state.device = "cpu"

    # Instantiate detector/classifier wrappers (do not force-load heavy models here).
    app.state.detector = YOLODetector(settings.YOLO_MODEL_PATH, settings.YOLO_CONF_THRESHOLD)
    app.state.classifier = ViTClassifier(
        settings.VIT_MODEL_PATH,
        image_size=settings.VIT_IMAGE_SIZE,
        class_names=settings.CLASS_NAMES,
        display_names=settings.CLASS_DISPLAY_NAMES,
    )
    app.state.segmenter = MaskRCNNSegmenter(
        settings.MASK_RCNN_MODEL_PATH,
        image_size=224
    )

    @app.get("/")
    async def root():
        try:
            # Simple database ping check
            count = await farms_collection.count_documents({})
            return {"status": "ok", "database_connected": True, "registered_farms_count": count}
        except Exception as e:
            return {"status": "error", "database_connected": False, "error_details": str(e)}

    return app


app = create_app()


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log to console for now — uvicorn will also show traceback in the server logs
    try:
        import traceback
        traceback.print_exc()
    except Exception:
        pass
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "error": str(exc)})


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)





