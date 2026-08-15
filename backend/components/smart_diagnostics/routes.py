import logging

from fastapi import APIRouter, UploadFile, File, Request
from starlette.concurrency import run_in_threadpool

from . import image_service
from .schemas import (
    DetectResponse,
    Detection,
    BestDetection,
    BoundingBoxNormalized,
    Disease,
    ReasoningRequest,
    ReasoningResponse,
)

logger = logging.getLogger("smart_diagnostics.routes")

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


# ---------------------------------------------------------------------------
# Tier 3 — LLM Clinical Reasoning
# ---------------------------------------------------------------------------

@router.post("/api/reason", response_model=ReasoningResponse)
async def reason(body: ReasoningRequest):
    """Generate a Veterinary Diagnostic Briefing via the local LLM.

    Accepts the structured detection/classification results from /api/detect
    and passes them through the pipeline's LLM reasoner (Qwen 2.5 via
    LM Studio).  The call is blocking (~15-20 s) so it runs in a threadpool.
    """
    from .pipeline.llm_reasoner import generate_veterinary_report
    from .pipeline import config as pipeline_cfg

    # Transform the detection result into the shape expected by the reasoner.
    # The reasoner expects a dict with "detections" (list of per-box dicts)
    # and "image_size".
    best = body.best_detection
    disease = body.disease

    # Build a single-detection entry matching the pipeline's vision_engine
    # output format so the LLM prompt is consistent regardless of whether
    # the request came from the CLI pipeline or the web frontend.
    detections_for_llm = []
    if best and disease:
        bbox = best.bbox
        img_w = (body.image_size or {}).get("width", 1)
        img_h = (body.image_size or {}).get("height", 1)
        bbox_w = round(bbox[2] - bbox[0], 1) if len(bbox) == 4 else 0
        bbox_h = round(bbox[3] - bbox[1], 1) if len(bbox) == 4 else 0
        frame_area = img_w * img_h if img_w and img_h else 1
        box_area = bbox_w * bbox_h
        area_pct = round((box_area / frame_area) * 100, 2)

        detections_for_llm.append({
            "bbox": bbox,
            "bbox_width_px": bbox_w,
            "bbox_height_px": bbox_h,
            "bbox_area_pct": area_pct,
            "yolo_class": body.detections[0].class_name if body.detections else "cattle",
            "yolo_confidence": best.confidence,
            "vit_predicted_class": disease.name,
            "vit_predicted_display": disease.name,
            "vit_confidence_pct": disease.confidence,
            "vit_probabilities": disease.all_probabilities,
        })

    vision_results = {
        "status": "PROCESSED",
        "image_size": body.image_size or {},
        "detections": detections_for_llm,
    }

    # Convert optional farm metadata.
    farm_metadata = dict(body.farm_metadata) if body.farm_metadata else None

    try:
        report = await run_in_threadpool(
            generate_veterinary_report, vision_results, farm_metadata
        )

        # Determine if the report is an error message from the reasoner.
        is_error = report.startswith("⚠")

        return ReasoningResponse(
            status="error" if is_error else "ok",
            reasoning_report=report,
            model_name=pipeline_cfg.LLM_MODEL_NAME,
        )

    except Exception as exc:
        logger.exception("LLM reasoning failed.")
        return ReasoningResponse(
            status="error",
            reasoning_report=f"Tier 3 error: {exc}",
            model_name=None,
        )
