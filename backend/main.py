from fastapi import FastAPI
import uvicorn

from components.smart_diagnostics.config import settings
from components.smart_diagnostics.implementations.yolo_detector import YOLODetector
from components.smart_diagnostics.implementations.vit_classifier import ViTClassifier
from components.smart_diagnostics.routes import router as sd_router


def create_app() -> FastAPI:
    app = FastAPI(title="Animal Farm Reporting - Smart Diagnostics")
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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
