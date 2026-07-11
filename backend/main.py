from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.database import farms_collection
from components.health_anomaly.router import router as health_anomaly_router

app = FastAPI(title="ADRS Core Backend", version="1.0.0")

# Setup CORS middleware to allow requests from any frontend port/origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the Health Anomaly component router
app.include_router(health_anomaly_router, prefix="/api")

@app.get("/")
async def root():
    try:
        # Simple database ping check
        count = await farms_collection.count_documents({})
        return {"status": "ok", "database_connected": True, "registered_farms_count": count}
    except Exception as e:
        return {"status": "error", "database_connected": False, "error_details": str(e)}
