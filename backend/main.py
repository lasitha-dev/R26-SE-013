import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.components.risk_forecasting.routes import router as risk_forecasting_router
from backend.components.demo_auth.routes import router as demo_auth_router
from backend.components.demo_operational.routes import router as demo_operational_router
from backend.components.demo_forecasting.routes import router as demo_forecasting_router
from backend.core.demo_database_config import load_demo_database_config, DemoDatabaseConfigError
from backend.core.demo_database_connection import (
    DemoDatabaseConnectionManager,
    DemoDatabaseConnectionError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes optional demo database connection on startup if enabled and closes it on shutdown.
    Existing forecasting routes operate normally regardless of demo database enablement status.
    """
    manager = None
    try:
        config = load_demo_database_config()
        if config.enabled:
            manager = DemoDatabaseConnectionManager(config)
            await manager.connect()
            await manager.ping()
            app.state.demo_db_manager = manager
        else:
            app.state.demo_db_manager = None
    except (DemoDatabaseConfigError, DemoDatabaseConnectionError) as err:
        sys.stderr.write(f"Demo database startup failure: {err}\n")
        raise RuntimeError(f"Application startup aborted: {err}") from None
    except Exception as exc:
        sys.stderr.write(f"Demo database startup failure: Unexpected error ({exc.__class__.__name__})\n")
        raise RuntimeError("Application startup aborted due to database initialization failure.") from None

    try:
        yield
    finally:
        if manager is not None:
            await manager.close()
        app.state.demo_db_manager = None


app = FastAPI(
    title="Livestock Epidemic Surveillance System API",
    version="1.0.0",
    description="Multi-component epidemic surveillance system for Sri Lanka.",
    lifespan=lifespan,
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "Livestock Epidemic Surveillance System API"}


# Register Risk Forecasting Component Router
app.include_router(risk_forecasting_router, prefix="/api/v1/risk-forecasting", tags=["Risk Forecasting"])

# Register Demo Authentication Component Router
app.include_router(demo_auth_router, prefix="/api/v1/demo-auth", tags=["Demo Authentication"])

# Register Demo Operational Data Component Router
app.include_router(demo_operational_router, prefix="/api/v1/demo-operational", tags=["Demo Operational Data"])

# Register Demo Role-Scoped Forecasting Component Router
app.include_router(demo_forecasting_router, prefix="/api/v1/demo-forecasting", tags=["Demo Role-Scoped Forecasting"])
