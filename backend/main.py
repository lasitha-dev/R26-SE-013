from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.components.risk_forecasting.routes import router as risk_forecasting_router

app = FastAPI(
    title="Livestock Epidemic Surveillance System API",
    version="1.0.0",
    description="Multi-component epidemic surveillance system for Sri Lanka."
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
