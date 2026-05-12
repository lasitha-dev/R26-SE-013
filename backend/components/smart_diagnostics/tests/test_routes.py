import io
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.smart_diagnostics.routes import router


class FakeDetector:
    def predict(self, image):
        # Return a single high-confidence detection
        return [{"bbox": [10, 10, 110, 110], "confidence": 0.9, "class_name": "cow"}]


class FakeClassifier:
    def predict(self, image):
        return {"name": "Healthy", "confidence": 95.0, "all_probabilities": {"Healthy": 95.0, "Other": 5.0}}


def create_test_app():
    app = FastAPI()
    app.state.detector = FakeDetector()
    app.state.classifier = FakeClassifier()
    app.include_router(router)
    return app


def test_detect_success(tmp_path):
    app = create_test_app()
    client = TestClient(app)

    # create a tiny test image
    img = Image.new("RGB", (200, 200), (255, 0, 0))
    p = tmp_path / "test.jpg"
    img.save(p)

    with open(p, "rb") as f:
        response = client.post("/api/detect", files={"image": ("test.jpg", f, "image/jpeg")})

    assert response.status_code == 200
    data = response.json()
    assert data["cattle_detected"] is True
    assert data["disease"]["name"] == "Healthy"
