from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from components.smart_diagnostics.config import settings
from components.smart_diagnostics.implementations.yolo_detector import YOLODetector
from components.smart_diagnostics.implementations.vit_classifier import ViTClassifier
from components.smart_diagnostics.routes import router as sd_router


def create_app() -> FastAPI:
    app = FastAPI(title="Animal Farm Reporting - Smart Diagnostics")
    # Development CORS: allow Vite dev server and localhost
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://localhost:3000", "http://localhost:8000", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(sd_router)

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
