from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from core.database import farms_collection
from fastapi.middleware.cors import CORSMiddleware
from components.health_anomaly.router import router as health_anomaly_router
import uvicorn

from components.smart_diagnostics.config import settings
from components.smart_diagnostics.implementations.yolo_detector import YOLODetector
from components.smart_diagnostics.implementations.vit_classifier import ViTClassifier
from components.smart_diagnostics.implementations.mask_rcnn_segmenter import MaskRCNNSegmenter
from components.smart_diagnostics.routes import router as sd_router


from components.risk_forecasting.routes import router as risk_forecasting_router

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





