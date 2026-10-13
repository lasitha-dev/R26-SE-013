"""
LLM Clinical Decision Support Client — Tier 3
=================================================
Connects to Qwen 2.5 (3B Instruct) running in LM Studio via its
OpenAI-compatible endpoint to synthesise vision model predictions
into an actionable Veterinary Diagnostic Briefing.

The single public function is :func:`generate_veterinary_report`.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from . import config as cfg
from ..schemas import SeverityMetrics

logger = logging.getLogger("smart_diagnostics.pipeline.llm")


# ═══════════════════════════════════════════════════════════════════════════
# System prompt — establishes the LLM persona, severity reasoning, and output
# ═══════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """\
You are a **Senior Veterinary Pathologist & Epidemiological Triage Officer** with \
15+ years of field experience in bovine infectious diseases across South and \
Southeast Asia.

You are embedded in a 3-tier AI diagnostic pipeline. Upstream computer-vision models \
have analyzed the animal photograph and provided multi-modal physical telemetry:
- **YOLOv8s:** Anatomical localization and Region-of-Interest (ROI) framing.
- **ViT-B/16 & Attention Rollout:** Fine-grained disease classification, prediction certainty, transformer self-attention saliency coverage percentage, focal cluster density, and weighted composite severity score.

Your role is to act as the primary **Clinical Decision Support & Severity Reasoning Engine**.
You must synthesize all visual evidence, pathological markers, and farm metadata into an actionable **Veterinary Diagnostic Briefing**.

### MANDATORY METADATA HEADER (Line 1):
Your response MUST begin on the very first line with a structured metadata tag formatted exactly as:
[SEVERITY_META: Grade=<Severe|Moderate|Mild|Healthy Baseline> | Prognosis=<Guarded|Fair|Favorable|Excellent> | Description=<Concise 1-2 sentence clinical severity narrative synthesizing lesion coverage, cluster density, and disease risk>]

### BRIEFING SECTIONS:
Following the metadata header, your Markdown output MUST contain exactly these six sections (use level-2 headings):

## 1. Clinical Severity & Pathological Assessment
Provide an in-depth clinical explanation of the disease severity and pathological presentation. Evaluate how the ViT self-attention saliency coverage percentage, focal cluster count, and composite severity score correlate with the disease's acute vs. chronic manifestations, tissue damage, and transmission risk.

## 2. Primary Diagnostic Assessment & Certainty Level
State the most likely diagnosis and assign a certainty level: **High** (>85% AI \
confidence + consistent morphology), **Moderate** (60–85% or minor ambiguity), or \
**Ambiguous** (<60% or conflicting signals). Justify the certainty level.

## 3. Pathological & Morphological Rationale
Connect the visual features that the AI vision models detected (e.g., vesicular erosions and salivation for FMD; circumscribed cutaneous nodules and dermal edema for Lumpy Skin; udder inflammation for Mastitis) to the primary prediction. Explain *why* these morphological features support the diagnosis.

## 4. Differential Diagnosis Analysis
Discuss the runner-up class(es) from the probability distribution. Explain why each \
was considered and why it is less likely given the available evidence. If two classes \
are close in confidence, explicitly flag the diagnostic ambiguity.

## 5. Immediate Biosecurity & Triage Protocol
Provide actionable steps: quarantine radius, herd isolation, notifiable-disease \
reporting obligations (especially for Foot-and-Mouth Disease and Lumpy Skin Disease), \
movement restrictions, and vector control if applicable.

## 6. Recommended Confirmatory Laboratory Tests
List the gold-standard laboratory assays for the suspected disease (e.g., RT-PCR \
for FMDV serotyping, virus isolation, California Mastitis Test, Skin biopsy with \
histopathology for LSD). Include specimen type and transport requirements.

Be precise, evidence-based, clinically rigorous, and avoid unsupported speculation.\
"""


# ═══════════════════════════════════════════════════════════════════════════
# User prompt builder
# ═══════════════════════════════════════════════════════════════════════════

def _build_user_prompt(
    detections: List[Dict[str, Any]],
    image_size: Dict[str, int],
    farm_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Construct the user prompt containing all vision results and metadata."""

    lines: List[str] = [
        "## AI Vision Pipeline Output",
        "",
        f"**Image dimensions:** {image_size.get('width', '?')} × "
        f"{image_size.get('height', '?')} px",
        f"**Total detections:** {len(detections)}",
        "",
    ]

    for i, det in enumerate(detections, start=1):
        lines.append(f"### Detection {i}")
        lines.append(f"- **Anatomical site / tag:** {det.get('yolo_class', 'unknown')}")
        lines.append(
            f"- **Bounding box (x1, y1, x2, y2):** {det.get('bbox', [])}"
        )
        lines.append(
            f"- **Bounding box dimensions:** "
            f"{det.get('bbox_width_px', '?')} × {det.get('bbox_height_px', '?')} px  "
            f"({det.get('bbox_area_pct', '?')}% of frame)"
        )
        lines.append(
            f"- **YOLO detection confidence:** {det.get('yolo_confidence', '?')}"
        )
        lines.append(
            f"- **Primary AI diagnosis (ViT Classifier):** "
            f"{det.get('vit_predicted_display', det.get('vit_predicted_class', '?'))}  "
            f"({det.get('vit_confidence_pct', '?')}% confidence)"
        )

        # ViT Attention Rollout & Composite Severity Telemetry
        attn_cov = float(det.get("attention_coverage_pct", 0.0))
        attn_cls = int(det.get("attention_cluster_count", 0))
        lines.append(
            f"- **ViT Attention Saliency Coverage:** {attn_cov:.1f}% of anatomical ROI"
        )
        lines.append(
            f"- **ViT Attention Focal Clusters:** {attn_cls} distinct clusters"
        )
        if det.get("composite_score") is not None:
            lines.append(f"- **Composite Severity Score:** {det.get('composite_score'):.2f}")
        if det.get("confidence_level"):
            lines.append(f"- **Severity Confidence Level:** {det.get('confidence_level')}")
        if det.get("top2_margin") is not None:
            lines.append(f"- **Diagnostic Margin (Top 1 vs Top 2):** {det.get('top2_margin'):.1f}%")

        if det.get("spatial_correlation"):
            lines.append(f"- **Spatial Morphology Telemetry:** {det.get('spatial_correlation')}")

        # Full probability table.
        probs = det.get("vit_probabilities", {})
        if probs:
            lines.append("- **Full class probability distribution:**")
            for cls_display, pct in probs.items():
                lines.append(f"  - {cls_display}: {pct}%")

        lines.append("")

    # Optional farm metadata block.
    if farm_metadata:
        lines.append("## Farm Metadata")
        for key, value in farm_metadata.items():
            pretty_key = key.replace("_", " ").title()
            lines.append(f"- **{pretty_key}:** {value}")
        lines.append("")

    return "\n".join(lines)



# ═══════════════════════════════════════════════════════════════════════════
# Model discovery helper
# ═══════════════════════════════════════════════════════════════════════════

def _discover_model_name(client) -> str:
    """Try to dynamically fetch the model name from LM Studio.

    Falls back to ``cfg.LLM_MODEL_NAME`` on any failure.
    """
    try:
        model_list = client.models.list()
        if model_list and hasattr(model_list, "data") and model_list.data:
            discovered = model_list.data[0].id
            logger.info("Dynamically discovered LM Studio model: '%s'", discovered)
            return discovered
    except Exception as exc:
        logger.debug("Model discovery failed (%s), using fallback.", exc)

    logger.info("Using configured model name: '%s'", cfg.LLM_MODEL_NAME)
    return cfg.LLM_MODEL_NAME


# ═══════════════════════════════════════════════════════════════════════════
# Clinical Fallback Engine (for offline or unparsed LLM responses)
# ═══════════════════════════════════════════════════════════════════════════

def create_clinical_fallback_severity(vision_results: Dict[str, Any]) -> SeverityMetrics:
    """Generate an objective, clinically grounded severity metric from vision telemetry.

    Used when LLM service is offline or in test environments.
    """
    from components.smart_diagnostics.implementations.severity_scorer import compute_composite_severity

    detections = vision_results.get("detections", [])
    primary_det = detections[0] if detections else {}

    signals = {
        "attention_coverage_pct": primary_det.get("attention_coverage_pct", 0.0),
        "attention_cluster_count": primary_det.get("attention_cluster_count", 0),
        "vit_confidence_pct": primary_det.get("vit_confidence_pct", 0.0),
        "top2_margin": primary_det.get("top2_margin", 0.0),
        "yolo_detection_count": len(detections),
        "yolo_max_bbox_area_pct": primary_det.get("bbox_area_pct", 0.0),
        "predicted_class": primary_det.get("vit_predicted_class", "cattle"),
        "predicted_display": primary_det.get("vit_predicted_display", primary_det.get("vit_predicted_class", "Condition")),
        "spatial_correlation": primary_det.get("spatial_correlation"),
        "lesion_coverage_pct": float(primary_det.get("lesion_coverage_pct", 0.0)),
        "cluster_count": int(primary_det.get("cluster_count", 0)),
        "mean_intensity": float(primary_det.get("mean_intensity", 0.0)),
    }

    return compute_composite_severity(signals)


def extract_section_snippet(report_text: str, section_keyword: str) -> Optional[str]:
    """Extract a clean 1-2 sentence snippet from a specific section in the LLM report."""
    pattern = rf"##\s*\d*\.?\s*[^#\n]*{re.escape(section_keyword)}[^\n]*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, report_text, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(1).strip()
        lines = [line.strip() for line in content.split("\n") if line.strip() and not line.strip().startswith("#")]
        clean_text = " ".join(lines)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_text) if s.strip()]
        return " ".join(sentences[:2]) if sentences else (clean_text[:220] + "...")
    return None


def parse_llm_severity_assessment(
    report_text: str, vision_results: Dict[str, Any]
) -> Tuple[str, SeverityMetrics]:
    """Parse metadata from LLM output supporting multiple formats ([SEVERITY_META], ### SEVERITY META, JSON)
    and clean the Markdown report so no raw metadata tags appear in the UI.
    """
    detections = vision_results.get("detections", [])
    primary_det = detections[0] if detections else {}
    lsr = float(primary_det.get("lesion_coverage_pct", 0.0))
    clusters = int(primary_det.get("cluster_count", 0))
    attn_cov = float(primary_det.get("attention_coverage_pct", 0.0))
    attn_clusters = int(primary_det.get("attention_cluster_count", 0))
    top2_margin = float(primary_det.get("top2_margin", 0.0))
    comp_score = primary_det.get("composite_score")
    conf_level = primary_det.get("confidence_level", "High")
    needs_review = bool(primary_det.get("needs_review", False))
    spatial_telemetry = primary_det.get("spatial_correlation", "")

    # Multi-format regex: handles [SEVERITY_META: Grade=... | Prognosis=... | Description=...]
    # Also tolerates legacy optional Stage if present in string
    meta_pattern = r"(?:\[|#+\s*|\*\*)*SEVERITY[\s_-]*META:?\s*Grade=([^|\n\]]+)(?:\|\s*Stage=[^|\n\]]+)?\|\s*Prognosis=([^|\n\]]+)\|\s*Description=([^\n\]]+)"
    match = re.search(meta_pattern, report_text, re.IGNORECASE)

    # Clean any metadata line or preamble before the first real section '## 1.' or '## '
    cleaned_report = re.sub(meta_pattern, "", report_text, flags=re.IGNORECASE).strip()
    
    # Strip any leading '### SEVERITY' or stray meta lines if leftover
    cleaned_report = re.sub(r"^#+\s*SEVERITY[^\n]*\n+", "", cleaned_report, flags=re.IGNORECASE).strip()
    
    # Ensure report starts from the first '## ' heading if there is any stray preamble
    first_heading_idx = cleaned_report.find("## ")
    if first_heading_idx != -1:
        cleaned_report = cleaned_report[first_heading_idx:].strip()

    # Extract dynamic rationale from Section 3 ("Pathological & Morphological Rationale")
    dynamic_rationale = extract_section_snippet(cleaned_report, "Morphological Rationale") or extract_section_snippet(cleaned_report, "Rationale")
    
    # Extract dynamic severity section content from Section 1 ("Clinical Severity Assessment")
    dynamic_severity_section = extract_section_snippet(cleaned_report, "Severity Assessment") or extract_section_snippet(cleaned_report, "Clinical Severity")

    # If primary_det contains upstream composite severity metrics from vision pipeline, preserve them
    if primary_det.get("severity_grade"):
        grade = primary_det["severity_grade"]
        prognosis = primary_det.get("prognosis", "Guarded")
        description = primary_det.get("description") or f"Clinical condition evaluated as {grade}."
        rationale = dynamic_rationale or primary_det.get("diagnostic_rationale")
        spatial_telemetry = primary_det.get("spatial_correlation", "")
        comp_score = primary_det.get("composite_score")
        conf_level = primary_det.get("confidence_level", "High")
        needs_review = bool(primary_det.get("needs_review", False))
        attn_cov = float(primary_det.get("attention_coverage_pct", 0.0))
        attn_clusters = int(primary_det.get("attention_cluster_count", 0))
        top2_margin = float(primary_det.get("top2_margin", 0.0))
        intensity = float(primary_det.get("mean_intensity", 0.0))

        sev_model = SeverityMetrics(
            score=comp_score,
            composite_score=comp_score,
            grade=grade,
            description=description,
            prognosis=prognosis,
            diagnostic_rationale=rationale,
            spatial_correlation=spatial_telemetry,
            lesion_coverage_pct=lsr,
            cluster_count=clusters,
            mean_intensity=intensity,
            attention_coverage_pct=attn_cov,
            attention_cluster_count=attn_clusters,
            top2_margin=top2_margin,
            confidence_level=conf_level,
            needs_review=needs_review,
            formatted=grade,
            source="composite_scoring",
        )
        return cleaned_report, sev_model

    if match:
        grade = match.group(1).strip()
        prognosis = match.group(2).strip()
        description = match.group(3).strip()
        attn_cov = float(primary_det.get("attention_coverage_pct", 0.0))
        attn_clusters = int(primary_det.get("attention_cluster_count", 0))
        top2_margin = float(primary_det.get("top2_margin", 0.0))
        comp_score = primary_det.get("composite_score")
        conf_level = primary_det.get("confidence_level", "High")
        needs_review = bool(primary_det.get("needs_review", False))
        spatial_telemetry = primary_det.get("spatial_correlation", "")

        sev_model = SeverityMetrics(
            score=comp_score,
            composite_score=comp_score,
            grade=grade,
            description=description or dynamic_severity_section or f"Clinical severity classified as {grade}.",
            prognosis=prognosis,
            diagnostic_rationale=dynamic_rationale,
            spatial_correlation=spatial_telemetry or f"Anatomical cluster density correlates with {grade.lower()} pathology.",
            lesion_coverage_pct=lsr,
            cluster_count=clusters,
            attention_coverage_pct=attn_cov,
            attention_cluster_count=attn_clusters,
            top2_margin=top2_margin,
            confidence_level=conf_level,
            needs_review=needs_review,
            formatted=grade,
            source="llm_reasoning",
        )
        return cleaned_report, sev_model

    # Fallback: extract directly from the report text or compute clinical fallback
    fallback_model = create_clinical_fallback_severity(vision_results)
    if dynamic_rationale:
        fallback_model.diagnostic_rationale = dynamic_rationale
    if dynamic_severity_section:
        fallback_model.description = dynamic_severity_section
    if spatial_telemetry:
        fallback_model.spatial_correlation = spatial_telemetry

    return cleaned_report, fallback_model



# ═══════════════════════════════════════════════════════════════════════════
# Public API — generate_veterinary_report
# ═══════════════════════════════════════════════════════════════════════════

def generate_veterinary_report(
    vision_results: Dict[str, Any],
    farm_metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[str, SeverityMetrics]:
    """Generate a structured Veterinary Diagnostic Briefing and Clinical Severity Synthesis via LM Studio.

    Returns:
        (report_text, severity_metrics)
    """
    try:
        from openai import OpenAI
    except ImportError as exc:
        err_msg = (
            "⚠️  **Tier 3 Unavailable:** The `openai` Python package is not "
            "installed.  Install it with `pip install openai>=1.0` and retry.\n\n"
            f"Error: {exc}"
        )
        return err_msg, create_clinical_fallback_severity(vision_results)

    client = OpenAI(
        base_url=cfg.LM_STUDIO_BASE_URL,
        api_key=cfg.LM_STUDIO_API_KEY,
    )

    model_name = _discover_model_name(client)
    detections = vision_results.get("detections", [])
    image_size = vision_results.get("image_size", {})
    user_prompt = _build_user_prompt(detections, image_size, farm_metadata)

    logger.info(
        "Sending request to LM Studio  (model=%s, detections=%d) ...",
        model_name, len(detections),
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.35,  # Clinically grounded reasoning
            max_tokens=2048,
            top_p=0.9,
        )

        content = response.choices[0].message.content
        if not content:
            fallback = create_clinical_fallback_severity(vision_results)
            return "⚠️  LLM returned an empty response.", fallback

        logger.info("Received LLM response (%d chars).", len(content))
        cleaned_report, severity_metrics = parse_llm_severity_assessment(content, vision_results)
        return cleaned_report, severity_metrics

    except Exception as exc:
        error_type = type(exc).__name__
        logger.error("LLM request failed (%s): %s", error_type, exc)
        fallback_sev = create_clinical_fallback_severity(vision_results)

        err_report = (
            f"⚠️  **Tier 3 Notice — Local LLM Server Standby**\n\n"
            f"Automated clinical severity generated from Mask R-CNN & ViT multi-modal telemetry.\n\n"
            f"*Tier 1 (Localization), Tier 2 (Classification), and Mask R-CNN (Lesion Segmentation) active.*"
        )
        return err_report, fallback_sev
