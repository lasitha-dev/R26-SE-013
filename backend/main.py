from fastapi import FastAPI
from backend.components.risk_forecasting.routes import router as risk_forecasting_router

app = FastAPI(
    title="Livestock Epidemic Surveillance System API",
    version="1.0.0",
    description="Multi-component epidemic surveillance system for Sri Lanka."
)

@app.get("/")
def root():
    return {"status": "ok", "service": "Livestock Epidemic Surveillance System API"}

# Register Risk Forecasting Component Router
app.include_router(risk_forecasting_router, prefix="/api/v1/risk-forecasting", tags=["Risk Forecasting"])

