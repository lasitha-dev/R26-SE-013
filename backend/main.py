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

@app.get("/reset-pramod-password")
async def reset_pramod_password():
    from core.security import get_password_hash
    hashed = get_password_hash("123456")
    existing = await farms_collection.find_one({"email": "pramod@gmail.com"})
    if existing:
        await farms_collection.update_one({"email": "pramod@gmail.com"}, {"$set": {"password": hashed}})
        msg = "Password for pramod@gmail.com successfully updated to 123456"
    else:
        doc = {
            "owner_name": "Pramod Wijenayake",
            "email": "pramod@gmail.com",
            "password": hashed,
            "location_district": "Colombo",
            "registration_number": "REG-PR-2026",
            "veterinarian_name": "Dr. Nimal Perera",
            "total_animals": 10
        }
        await farms_collection.insert_one(doc)
        msg = "Created pramod@gmail.com account with password 123456"
    return {"status": "success", "email": "pramod@gmail.com", "password": "123456", "message": msg}

