# HTTP workflow: uploaded photo -> detector crop -> disease classification ->
# lesion measurements -> severity policy. /api/reason then explains the evidence.
import logging

from fastapi import APIRouter, UploadFile, File, Request, HTTPException, Form
from starlette.concurrency import run_in_threadpool

from . import image_service
from .schemas import (
    DetectResponse,
    Detection,
    BestDetection,
    BoundingBoxNormalized,
    Disease,
    SeverityMetrics,
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
    device = str(getattr(classifier, "_device", None) or "unknown")

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
                "load_state": getattr(classifier, "load_state", "loaded" if classifier_loaded else "not_loaded"),
                "device": str(getattr(classifier, "_device", None) or "unknown"),
                "registered": classifier is not None,
                "loaded": classifier_loaded,
            },
            "lesion_segmenter": {
                "architecture": "ResNet50 U-Net",
                "device": str(getattr(segmenter, "_device", None) or "unknown"),
                "load_state": getattr(segmenter, "load_state", "loaded" if segmenter_loaded else "not_loaded"),
                "registered": segmenter is not None,
                "loaded": segmenter_loaded,
            },
        },
        "device": str(device),
    }


@router.post("/api/detect", response_model=DetectResponse)
async def detect(request: Request, image: UploadFile = File(...),
                 body_site: str | None = Form(None), observed_symptoms: str | None = Form(None)):
    from .model_errors import ModelUnavailable
    from .implementations.severity_scorer import compute_composite_severity, load_severity_policy
    from .config import settings
    from .schemas import SegmentationAssessment, ReviewAssessment
    import numpy as np

    if (body_site and len(body_site) > 120) or (observed_symptoms and len(observed_symptoms) > 1000):
        raise HTTPException(422, "Observation text is too long.")
    # Decode and orient the photo before any model produces pixel coordinates.
    pil = image_service.open_image_from_bytes(await image.read())
    detector = getattr(request.app.state, "detector", None)
    classifier = getattr(request.app.state, "classifier", None)
    segmenter = getattr(request.app.state, "segmenter", None)
    if detector is None or classifier is None:
        raise HTTPException(503, detail={"code": "required_model_unavailable", "message": "Detection/classification models are not configured."})
    try:
        # Model inference is blocking work; a worker thread keeps the async API responsive.
        detections = await run_in_threadpool(detector.predict, pil)
    except Exception as exc:
        logger.exception("Detector failed")
        raise HTTPException(503 if isinstance(exc, ModelUnavailable) else 502,
            detail={"code": "detector_unavailable", "message": "Cattle detection could not be completed."}) from exc
    if not detections:
        return DetectResponse(cattle_detected=False, detections=[], best_detection=None, disease=None,
            cropped_image=None, image_size={"width": pil.width, "height": pil.height}, device="unknown",
            segmentation=SegmentationAssessment(status="skipped"),
            review=ReviewAssessment(required=True, reasons=["no_supported_region_detected"]))

    # Preserve the highest-confidence single-ROI policy.
    # A region of interest (ROI) is the part of the photo passed to later models.
    best = max(detections, key=lambda item: item["confidence"])
    coords = np.asarray(best["bbox"], dtype=float)
    if coords.shape != (4,) or not np.isfinite(coords).all():
        raise HTTPException(502, "Detector returned an invalid bounding box.")
    # Clamp the selected box to the actual photo, then reject an empty crop.
    x1, y1 = max(0, int(coords[0])), max(0, int(coords[1]))
    x2, y2 = min(pil.width, int(coords[2])), min(pil.height, int(coords[3]))
    if x2 <= x1 or y2 <= y1:
        raise HTTPException(502, "Detector returned an empty bounding box.")
    crop_box = [x1, y1, x2, y2]
    cropped = image_service.crop_image(pil, crop_box)
    try:
        # ViT labels the same crop used for segmentation; attention is an optional
        # view of model focus, while the mask supplies lesion-area measurements.
        predict = getattr(classifier, "predict_with_attention", classifier.predict)
        prediction = await run_in_threadpool(predict, cropped)
        disease = Disease(name=prediction["name"], confidence=prediction["confidence"],
                          all_probabilities=prediction.get("all_probabilities", {}))
        values = [disease.confidence, *disease.all_probabilities.values()]
        if not all(np.isfinite(value) and 0 <= value <= 100 for value in values):
            raise ValueError("Invalid class probabilities.")
    except Exception as exc:
        logger.exception("Classifier failed")
        raise HTTPException(503 if isinstance(exc, ModelUnavailable) else 502,
            detail={"code": "classifier_unavailable", "message": "Trained disease classification could not be completed."}) from exc
    # A healthy-class prediction skips lesion segmentation. A missing/failed
    # segmenter has its own status and must not be reported as zero lesion area.
    healthy = disease.name.lower() in ("cattle", "cattle (healthy)", "healthy")
    metrics = {"status": "skipped" if healthy else "unavailable"}
    symptoms = None
    if not healthy and segmenter is not None:
        try:
            symptoms, metrics = await run_in_threadpool(segmenter.predict_with_metrics, cropped)
            # Compatibility for existing metric adapters; production adapter reports explicit status.
            metrics.setdefault("status", "completed_with_regions" if metrics.get("cluster_count", 0) else "completed_no_regions")
        except Exception:
            logger.exception("Segmenter failed")
            metrics = {"status": "failed", "error_code": "segmentation_failed"}
            symptoms = None
    segmentation = SegmentationAssessment(**metrics)
    completed = segmentation.status.startswith("completed_")
    if not completed:
        symptoms = None
        for field in ("lesion_coverage_pct", "cluster_count", "lesion_pixels", "mean_intensity"):
            setattr(segmentation, field, None)

    attn_cov = float(prediction.get("attention_coverage_pct") or 0)
    attn_clusters = int(prediction.get("attention_cluster_count") or 0)
    margin = float(prediction.get("top2_margin") or 0)
    spatial = f"Analyzed crop: ({x1}, {y1}) to ({x2}, {y2}) pixels in the original image. "
    spatial += f"Body site reported by user: {body_site}." if body_site else "Body site is unknown; frame position does not identify anatomy."
    signals = dict(attention_coverage_pct=attn_cov, attention_cluster_count=attn_clusters,
        vit_confidence_pct=disease.confidence, top2_margin=margin, yolo_detection_count=len(detections),
        yolo_confidence=best["confidence"], segmentation_status=segmentation.status,
        segmentation_contract_status=segmentation.contract_status,
        yolo_max_bbox_area_pct=round(float((coords[2]-coords[0])*(coords[3]-coords[1]))/(pil.width*pil.height)*100, 2),
        predicted_class="cattle" if healthy else disease.name, predicted_display=disease.name,
        lesion_coverage_pct=segmentation.lesion_coverage_pct, cluster_count=segmentation.cluster_count,
        mean_intensity=segmentation.mean_intensity, spatial_correlation=spatial)
    # Thresholds come from a versioned policy so the basis for the grade is traceable.
    policy = load_severity_policy(settings.SEVERITY_POLICY_PATH)
    severity = compute_composite_severity(signals, policy)
    severity.spatial_correlation = spatial
    severity.lesion_coverage_pct = segmentation.lesion_coverage_pct
    severity.cluster_count = segmentation.cluster_count
    severity.mean_intensity = segmentation.mean_intensity
    if prediction.get("attention_status") == "failed" or "attention_coverage_pct" not in prediction:
        severity.attention_coverage_pct = None
        severity.attention_cluster_count = None

    # Image quality and model limitations can request human review even when
    # classification succeeds; these flags travel alongside the prediction.
    reasons = list(severity.visual_assessment.review_reasons) if severity.visual_assessment else []
    if min(cropped.size) < policy.review.minimum_crop_side_px:
        reasons.append("small_analyzed_region")
    gray = np.asarray(cropped.convert("L"), dtype=float)
    if gray.std() < policy.review.minimum_image_stddev:
        reasons.append("low_image_detail")
    if gray.mean() < policy.review.minimum_image_brightness or gray.mean() > policy.review.maximum_image_brightness:
        reasons.append("extreme_image_brightness")
    if not healthy:
        if not completed:
            reasons.append("segmentation_" + segmentation.status)
        if policy.review.require_unverified_segmentation_review and segmentation.contract_status != "verified":
            reasons.append("segmentation_training_contract_unverified")
    if prediction.get("attention_status") == "failed":
        reasons.append("attention_unavailable")
    reasons = list(dict.fromkeys(reasons))
    if reasons:
        severity.needs_review = True
    attention = prediction.get("attention_overlay_image")
    model_metadata = dict(classifier_device=str(getattr(classifier, "_device", None) or "unknown"),
        segmenter_architecture="ResNet50 U-Net", segmenter_device=str(getattr(segmenter, "_device", None) or "unknown"), segmentation_policy=segmentation.policy_version,
        training_contract=segmentation.contract_status)
    # Include both crop and original-image coordinates so overlays can be aligned.
    return DetectResponse(cattle_detected=True, detections=[Detection(**item) for item in detections],
        best_detection=BestDetection(bbox=crop_box, confidence=best["confidence"],
            bbox_normalized=BoundingBoxNormalized(x1=x1/pil.width, y1=y1/pil.height, x2=x2/pil.width, y2=y2/pil.height)),
        disease=disease, severity=severity, segmentation=segmentation,
        review=ReviewAssessment(required=bool(reasons) or severity.needs_review, reasons=reasons),
        spatial_correlation=spatial, body_site=body_site, observed_symptoms=observed_symptoms,
        crop_transform=dict(original_size=[pil.width, pil.height], crop_box=crop_box,
                            crop_size=list(cropped.size), model_size=[224,224], padding=False),
        cropped_image="data:image/jpeg;base64,"+image_service.encode_image_base64(cropped),
        symptoms_image="data:image/jpeg;base64,"+image_service.encode_image_base64(symptoms) if symptoms else None,
        attention_image="data:image/jpeg;base64,"+image_service.encode_image_base64(attention) if attention else None,
        image_size={"width": pil.width, "height": pil.height}, device=model_metadata["classifier_device"], model_metadata=model_metadata)


# ---------------------------------------------------------------------------
# Tier 3 — LLM Clinical Reasoning
# ---------------------------------------------------------------------------

@router.post("/api/reason", response_model=ReasoningResponse)
async def reason(body: ReasoningRequest):
    """Rebuild model severity, then combine grounded LLM reasoning using policy."""
    from .implementations.clinical_severity import assess_clinical_severity, clinical_disease_key
    sev = body.severity
    if body.cattle_detected and body.disease:
        if body.clinical_observations is None or not clinical_disease_key(body.disease.name):
            from .implementations.severity_scorer import compute_composite_severity
            # Rebuild from the supplied model measurements, rather than accepting a
            # client-provided grade or retaining the former mandatory checklist.
            probabilities = sorted(body.disease.all_probabilities.values(), reverse=True)
            margin = (probabilities[0] - probabilities[1] if len(probabilities) >= 2
                      else body.severity.top2_margin if body.severity else None)
            sev = compute_composite_severity(dict(predicted_class=body.disease.name,
                vit_confidence_pct=body.disease.confidence, top2_margin=margin,
                yolo_confidence=body.best_detection.confidence if body.best_detection else None,
                segmentation_status=body.segmentation.status if body.segmentation else None,
                segmentation_contract_status=body.segmentation.contract_status if body.segmentation else None,
                lesion_coverage_pct=body.segmentation.lesion_coverage_pct if body.segmentation else None,
                cluster_count=body.segmentation.cluster_count if body.segmentation else None,
                mean_intensity=body.segmentation.mean_intensity if body.segmentation else None,
                spatial_correlation=body.spatial_correlation))
        else:
            # Optional reported clinical findings use a separate disease checklist.
            try:
                sev = assess_clinical_severity(body.disease.name, body.clinical_observations,
                    body.severity.model_dump() if body.severity else None)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

    from .pipeline.llm_reasoner import generate_report_result

    # Transform the detection result into the shape expected by the reasoner.
    best = body.best_detection
    disease = body.disease

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

        det_dict = {
            "bbox": bbox,
            "bbox_width_px": bbox_w,
            "bbox_height_px": bbox_h,
            "bbox_area_pct": area_pct,
            "yolo_class": max(body.detections, key=lambda item: item.confidence).class_name if body.detections else "unknown",
            "yolo_confidence": best.confidence,
            "vit_predicted_class": disease.name,
            "vit_predicted_display": disease.name,
            "vit_confidence_pct": disease.confidence,
            "vit_probabilities": disease.all_probabilities,
        }
        if sev:
            det_dict.update({
                "severity_grade": sev.grade,
                "score": sev.score,
                "composite_score": sev.composite_score,
                "confidence_level": sev.confidence_level,
                "needs_review": sev.needs_review,
                "attention_coverage_pct": sev.attention_coverage_pct,
                "attention_cluster_count": sev.attention_cluster_count,
                "top2_margin": sev.top2_margin,
                "lesion_coverage_pct": sev.lesion_coverage_pct,
                "cluster_count": sev.cluster_count,
                "mean_intensity": sev.mean_intensity,
                "prognosis": sev.prognosis,
                "description": sev.description or "",
                "diagnostic_rationale": sev.diagnostic_rationale or "",
                "spatial_correlation": body.spatial_correlation or sev.spatial_correlation or "",
                "source": sev.source or "composite_scoring",
            })

        det_dict.update(segmentation_status=body.segmentation.status if body.segmentation else "unavailable",
                        body_site=body.body_site, observed_symptoms=body.observed_symptoms,
                        review_reasons=body.review.reasons if body.review else [])
        detections_for_llm.append(det_dict)


    vision_results = {
        "status": "PROCESSED",
        "upstream_severity": sev.model_dump() if sev else None,
        "image_size": body.image_size or {},
        "detections": detections_for_llm,
        "clinical_observations": body.clinical_observations.model_dump() if body.clinical_observations else None,
        "segmentation": body.segmentation.model_dump() if body.segmentation else None,
        "review": body.review.model_dump() if body.review else None,
        "model_metadata": body.model_metadata,
        "crop_transform": body.crop_transform,
    }

    # Convert optional farm metadata.
    farm_metadata = dict(body.farm_metadata) if body.farm_metadata else None

    import asyncio
    from .config import settings
    # Bound the reasoning wait. If generation fails, the fallback below renders
    # a reference summary while retaining the assessment already computed here.
    try:
        return await asyncio.wait_for(run_in_threadpool(generate_report_result, vision_results, farm_metadata),
                                      timeout=settings.REASONING_TIMEOUT_SECONDS + 1)
    except Exception:
        logger.exception("Explanation failed or timed out")
        if sev and detections_for_llm:
            from .pipeline.grounded_reasoning import build_context, default_selection, assemble_explanation, render_report
            context = build_context(vision_results, sev, farm_metadata)
            explanation = assemble_explanation(context, default_selection(context), "template")
            return ReasoningResponse(status="fallback", error_code="reasoning_failed_or_timed_out",
                reasoning_report="Explanation unavailable. A reference summary is shown; the original assessment is retained.\n\n" + render_report(explanation),
                severity_assessment=sev, explanation=explanation,
                recommendations=explanation.recommendation if explanation else None)
        return ReasoningResponse(status="fallback", error_code="reasoning_failed_or_timed_out",
            reasoning_report="Explanation unavailable. The original image assessment is retained.",
            severity_assessment=sev)
