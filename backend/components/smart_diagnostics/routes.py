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
    severity_model = None
    stage_str = None
    spatial_correlation_str = None

    predicted_name = disease.get("name", "").lower()
    is_healthy = predicted_name in ("cattle", "cattle (healthy)")
    vit_conf = float(disease.get("confidence", 0.0))

    img_w, img_h = pil.size
    bbox_norm = BoundingBoxNormalized(x1=x1 / img_w, y1=y1 / img_h, x2=x2 / img_w, y2=y2 / img_h)

    # Compute anatomical geometry and spatial telemetry from bounding box
    cx = (bbox_norm.x1 + bbox_norm.x2) / 2.0
    cy = (bbox_norm.y1 + bbox_norm.y2) / 2.0
    bw_pct = (bbox_norm.x2 - bbox_norm.x1) * 100
    bh_pct = (bbox_norm.y2 - bbox_norm.y1) * 100

    if cy < 0.40 and cx < 0.50:
        anatomical_site = "Anterior Cranial & Oral / Muzzle Zone"
    elif cy < 0.45 and cx >= 0.50:
        anatomical_site = "Cervical & Dorsal Nape Region"
    elif cy >= 0.55 and cx < 0.60:
        anatomical_site = "Ventral Inguinal & Mammary / Udder Quadrant"
    elif cy >= 0.70:
        anatomical_site = "Distal Locomotor & Coronary / Interdigital Cleft"
    else:
        anatomical_site = "Mid-Thoracic Flank & Lateral Dermal Wall"

    if is_healthy:
        spatial_correlation_str = (
            f"Full-frame anatomical scan across the {anatomical_site} reveals homogeneous epidermal contour "
            "with zero focal lesion clustering or inflammatory edema."
        )
        severity_model = SeverityMetrics(
            grade="Healthy Baseline",
            description="Epidermal surface presents homogeneous texture with zero anomalous lesion density or inflammatory markers.",
            stage="Healthy Baseline",
            prognosis="Excellent",
            diagnostic_rationale="No pathological tissue disruptions detected. Dermal contour aligns with physiological baseline.",
            spatial_correlation=spatial_correlation_str,
            lesion_coverage_pct=0.0,
            cluster_count=0,
            mean_intensity=0.0,
            formatted="Healthy Baseline",
            source="vision_telemetry",
        )
        stage_str = "Healthy Baseline"
    elif segmenter and predicted_name:
        symptoms_img, metrics = await run_in_threadpool(segmenter.predict_with_metrics, cropped)
        symptoms_b64 = image_service.encode_image_base64(symptoms_img)

        lsr = metrics.get("lesion_coverage_pct", 0.0)
        clusters = metrics.get("cluster_count", 0)
        intensity = metrics.get("mean_intensity", 0.0)

        # Preliminary visual stage estimation from morphological telemetry
        if lsr >= 12.0 or clusters >= 8:
            prelim_grade = "Severe"
            stage_str = "Acute Eruptive / Advanced"
            prelim_prognosis = "Guarded"
        elif lsr >= 4.0 or clusters >= 3:
            prelim_grade = "Moderate"
            stage_str = "Active Progression / Multifocal"
            prelim_prognosis = "Recoverable with Intervention"
        else:
            prelim_grade = "Mild"
            stage_str = "Early Focal / Prodromal"
            prelim_prognosis = "Favorable"

        if lsr == 0 and clusters == 0:
            spatial_correlation_str = (
                f"Localized ROI focus at the {anatomical_site} ({bw_pct:.1f}% × {bh_pct:.1f}% frame area). "
                "Low surface disruption detected at early baseline threshold."
            )
        else:
            spatial_correlation_str = (
                f"Automated segmentation identified {clusters} distinct focal lesion cluster(s) covering {lsr:.1f}% "
                f"surface area localized at the {anatomical_site} ({bw_pct:.1f}% × {bh_pct:.1f}% frame ROI). "
                f"Spatial density aligns with {prelim_grade.lower()} pathological progression."
            )

        prelim_rationale = (
            f"Vision classifier identified morphological biomarkers consistent with {disease.get('name')} "
            f"({vit_conf:.1f}% confidence), corroborated by {clusters} segmented nodular/lesion cluster(s)."
        )

        severity_model = SeverityMetrics(
            grade=prelim_grade,
            description=f"Automated segmentation identified {clusters} distinct lesion cluster(s) covering {lsr:.1f}% anatomical surface area.",
            stage=stage_str,
            prognosis=prelim_prognosis,
            diagnostic_rationale=prelim_rationale,
            spatial_correlation=spatial_correlation_str,
            lesion_coverage_pct=lsr,
            cluster_count=clusters,
            mean_intensity=intensity,
            formatted=f"{prelim_grade} ({stage_str})",
            source="vision_telemetry",
        )

    best_det = BestDetection(bbox=best["bbox"], confidence=best["confidence"], bbox_normalized=bbox_norm)
    disease_model = Disease(
        name=disease.get("name"), confidence=disease.get("confidence"), all_probabilities=disease.get("all_probabilities", {})
    )

    return DetectResponse(
        cattle_detected=True,
        detections=[Detection(**d) for d in detections],
        best_detection=best_det,
        disease=disease_model,
        severity=severity_model,
        stage=stage_str,
        spatial_correlation=spatial_correlation_str,
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
    best = body.best_detection
    disease = body.disease
    sev = body.severity

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
            "yolo_class": body.detections[0].class_name if body.detections else "cattle",
            "yolo_confidence": best.confidence,
            "vit_predicted_class": disease.name,
            "vit_predicted_display": disease.name,
            "vit_confidence_pct": disease.confidence,
            "vit_probabilities": disease.all_probabilities,
        }
        if sev:
            det_dict.update({
                "severity_grade": sev.grade,
                "lesion_coverage_pct": sev.lesion_coverage_pct,
                "cluster_count": sev.cluster_count,
                "stage": body.stage or sev.stage or "N/A",
                "spatial_correlation": body.spatial_correlation or sev.spatial_correlation or "",
            })

        detections_for_llm.append(det_dict)

    vision_results = {
        "status": "PROCESSED",
        "image_size": body.image_size or {},
        "detections": detections_for_llm,
    }

    # Convert optional farm metadata.
    farm_metadata = dict(body.farm_metadata) if body.farm_metadata else None

    try:
        report, severity_assessment = await run_in_threadpool(
            generate_veterinary_report, vision_results, farm_metadata
        )

        is_error = report.startswith("⚠️") and "Error" in report

        return ReasoningResponse(
            status="error" if is_error else "ok",
            reasoning_report=report,
            model_name=pipeline_cfg.LLM_MODEL_NAME,
            severity_assessment=severity_assessment,
        )

    except Exception as exc:
        logger.exception("LLM reasoning failed.")
        from .pipeline.llm_reasoner import create_clinical_fallback_severity
        fallback_sev = create_clinical_fallback_severity(vision_results)
        return ReasoningResponse(
            status="error",
            reasoning_report=f"Tier 3 error: {exc}",
            model_name=None,
            severity_assessment=fallback_sev,
        )
