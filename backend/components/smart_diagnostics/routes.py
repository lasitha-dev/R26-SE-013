from fastapi import APIRouter, UploadFile, File, Request
from starlette.concurrency import run_in_threadpool

from . import image_service
from .schemas import (
    DetectResponse,
    Detection,
    BestDetection,
    BoundingBoxNormalized,
    Disease,
)

router = APIRouter(prefix="")


@router.get("/api/health")
async def health(request: Request):
    """Report model loading status and device info."""
    detector = getattr(request.app.state, "detector", None)
    classifier = getattr(request.app.state, "classifier", None)
    segmenter = getattr(request.app.state, "segmenter", None)
    device = getattr(request.app.state, "device", "unknown")

    detector_loaded = getattr(detector, "is_loaded", False) if detector else False
    classifier_loaded = getattr(classifier, "is_loaded", False) if classifier else False
    segmenter_loaded = getattr(segmenter, "is_loaded", False) if segmenter else False

    all_loaded = detector_loaded and classifier_loaded and segmenter_loaded

    return {
        "status": "ok" if all_loaded else "degraded",
        "models": {
            "yolo_detector": {
                "registered": detector is not None,
                "loaded": detector_loaded,
            },
            "vit_classifier": {
                "registered": classifier is not None,
                "loaded": classifier_loaded,
            },
            "mask_rcnn_segmenter": {
                "registered": segmenter is not None,
                "loaded": segmenter_loaded,
            },
        },
        "device": str(device),
    }


@router.post("/api/detect", response_model=DetectResponse)
async def detect(request: Request, image: UploadFile = File(...)):
    contents = await image.read()
    pil = image_service.open_image_from_bytes(contents)

    detector = getattr(request.app.state, "detector", None)
    classifier = getattr(request.app.state, "classifier", None)
    segmenter = getattr(request.app.state, "segmenter", None)
    device = getattr(request.app.state, "device", "cpu")

    if detector is None or classifier is None:
        # App not configured with model instances
        return DetectResponse(
            cattle_detected=False,
            detections=[],
            best_detection=None,
            disease=None,
            cropped_image=None,
            symptoms_image=None,
            image_size={"width": pil.width, "height": pil.height},
            device=str(device),
        )

    detections = await run_in_threadpool(detector.predict, pil)

    if not detections:
        return DetectResponse(
            cattle_detected=False,
            detections=[],
            best_detection=None,
            disease=None,
            cropped_image=None,
            symptoms_image=None,
            image_size={"width": pil.width, "height": pil.height},
            device=str(device),
        )

    # Choose highest confidence detection
    best = max(detections, key=lambda d: d["confidence"])
    x1, y1, x2, y2 = best["bbox"]

    cropped = image_service.crop_image(pil, best["bbox"])
    disease = await run_in_threadpool(classifier.predict, cropped)

    crop_b64 = image_service.encode_image_base64(cropped)
    
    # Run segmentation only if the animal is diseased (not "cattle" / healthy)
    symptoms_b64 = None
    predicted_name = disease.get("name", "").lower()
    is_healthy = predicted_name in ("cattle", "cattle (healthy)")
    if segmenter and predicted_name and not is_healthy:
        symptoms_img = await run_in_threadpool(segmenter.predict, cropped)
        symptoms_b64 = image_service.encode_image_base64(symptoms_img)

    img_w, img_h = pil.size
    bbox_norm = BoundingBoxNormalized(x1=x1 / img_w, y1=y1 / img_h, x2=x2 / img_w, y2=y2 / img_h)

    best_det = BestDetection(bbox=best["bbox"], confidence=best["confidence"], bbox_normalized=bbox_norm)
    disease_model = Disease(
        name=disease.get("name"), confidence=disease.get("confidence"), all_probabilities=disease.get("all_probabilities", {})
    )

    return DetectResponse(
        cattle_detected=True,
        detections=[Detection(**d) for d in detections],
        best_detection=best_det,
        disease=disease_model,
        cropped_image=f"data:image/jpeg;base64,{crop_b64}",
        symptoms_image=f"data:image/jpeg;base64,{symptoms_b64}" if symptoms_b64 else None,
        image_size={"width": img_w, "height": img_h},
        device=str(device),
    )

