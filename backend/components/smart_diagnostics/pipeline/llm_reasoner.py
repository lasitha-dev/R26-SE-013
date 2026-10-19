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

from .grounded_reasoning import SYSTEM_PROMPT as _SYSTEM_PROMPT


def _build_user_prompt(
    detections: List[Dict[str, Any]],
    image_size: Dict[str, int],
    farm_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Legacy debug formatter; active requests use the complete JSON evidence record."""

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
        lines.append(f"- **Detector class / tag:** {det.get('yolo_class', 'unknown')}")
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
        attn_cov = det.get("attention_coverage_pct")
        attn_cls = det.get("attention_cluster_count")
        lines.append(
            f"- **ViT Attention Saliency Coverage:** {attn_cov if attn_cov is not None else 'unavailable'} (saliency only, percent of analyzed ROI)"
        )
        lines.append(
            f"- **ViT Attention Connected Regions:** {attn_cls if attn_cls is not None else 'unavailable'}"
        )
        if det.get("composite_score") is not None:
            lines.append(f"- **Composite Severity Score:** {det.get('composite_score'):.2f}")
        if det.get("confidence_level"):
            lines.append(f"- **Severity Confidence Level:** {det.get('confidence_level')}")
        if det.get("top2_margin") is not None:
            lines.append(f"- **Diagnostic Margin (Top 1 vs Top 2):** {det.get('top2_margin'):.1f}%")

        if det.get("spatial_correlation"):
            lines.append(f"- **Spatial Morphology Telemetry:** {det.get('spatial_correlation')}")

        lines.append(f"- **Segmentation status:** {det.get('segmentation_status', 'unavailable')}")
        for field in ('lesion_coverage_pct', 'cluster_count', 'mean_intensity'):
            value = det.get(field)
            lines.append(f"- **{field}:** {value if value is not None else 'unavailable / not measured'}")
        lines.append("- **Mask denominator:** analyzed crop pixels; connected regions are not clinical nodules.")
        lines.append(f"- **Reported body site:** {det.get('body_site') or 'unknown'}")
        lines.append(f"- **Reported symptoms:** {det.get('observed_symptoms') or 'not supplied'}")
        lines.append(f"- **Review required:** {det.get('needs_review', 'unknown')}; reasons: {det.get('review_reasons', [])}")

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
    """Compatibility name: pin the configured model, never pick the first listed."""
    from ..config import settings
    return settings.REASONING_MODEL_NAME


# ═══════════════════════════════════════════════════════════════════════════
# Clinical Fallback Engine (for offline or unparsed LLM responses)
# ═══════════════════════════════════════════════════════════════════════════

def _clinical_checklist_assessment(vision_results: Dict[str, Any]):
    """Keep all FMD/mastitis entry points independent of LLM or image-only grades."""
    from ..implementations.clinical_severity import assess_clinical_severity, clinical_disease_key, clinical_report
    detections = vision_results.get("detections", [])
    primary = detections[0] if detections else {}
    name = (primary.get("vit_predicted_class") if clinical_disease_key(primary.get("vit_predicted_class"))
            else primary.get("vit_predicted_display"))
    if not clinical_disease_key(name):
        return None
    if vision_results.get("clinical_observations") is None:
        from ..implementations.severity_scorer import visual_severity_report
        upstream = vision_results.get("upstream_severity")
        assessment = (SeverityMetrics.model_validate(upstream) if upstream and upstream.get("source") == "visual_thresholds"
                      else create_clinical_fallback_severity(vision_results))
        return visual_severity_report(name, assessment), assessment
    signals = dict(primary, visual_assessment=(vision_results.get("upstream_severity") or {}).get("visual_assessment"))
    assessment = assess_clinical_severity(name, vision_results.get("clinical_observations"), signals)
    return clinical_report(name, assessment), assessment


def create_clinical_fallback_severity(vision_results: Dict[str, Any]) -> SeverityMetrics:
    """Generate a provisional assessment from measured vision telemetry.

    Used when LLM service is offline or in test environments.
    """
    from components.smart_diagnostics.implementations.severity_scorer import compute_composite_severity
    from components.smart_diagnostics.implementations.clinical_recommendations import generate_clinical_recommendation

    detections = vision_results.get("detections", [])
    primary_det = detections[0] if detections else {}

    signals = {
        "clinical_observations": vision_results.get("clinical_observations"),
        "attention_coverage_pct": (primary_det.get("attention_coverage_pct") or 0.0),
        "attention_cluster_count": (primary_det.get("attention_cluster_count") or 0),
        "vit_confidence_pct": primary_det.get("vit_confidence_pct", 0.0),
        "top2_margin": (primary_det.get("top2_margin") or 0.0),
        "yolo_detection_count": len(detections),
        "yolo_confidence": primary_det.get("yolo_confidence"),
        "segmentation_status": primary_det.get("segmentation_status"),
        "segmentation_contract_status": primary_det.get("segmentation_contract_status"),
        "yolo_max_bbox_area_pct": primary_det.get("bbox_area_pct", 0.0),
        "predicted_class": primary_det.get("vit_predicted_class", "cattle"),
        "predicted_display": primary_det.get("vit_predicted_display", primary_det.get("vit_predicted_class", "Condition")),
        "spatial_correlation": primary_det.get("spatial_correlation"),
        "lesion_coverage_pct": primary_det.get("lesion_coverage_pct"),
        "cluster_count": primary_det.get("cluster_count"),
        "mean_intensity": primary_det.get("mean_intensity"),
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
    clinical = _clinical_checklist_assessment(vision_results)
    if clinical is not None:
        return clinical
    detections = vision_results.get("detections", [])
    primary_det = detections[0] if detections else {}
    lsr = float((primary_det.get("lesion_coverage_pct") or 0.0))
    clusters = int((primary_det.get("cluster_count") or 0))
    attn_cov = float((primary_det.get("attention_coverage_pct") or 0.0))
    attn_clusters = int((primary_det.get("attention_cluster_count") or 0))
    top2_margin = float((primary_det.get("top2_margin") or 0.0))
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
        attn_cov = float((primary_det.get("attention_coverage_pct") or 0.0))
        attn_clusters = int((primary_det.get("attention_cluster_count") or 0))
        top2_margin = float((primary_det.get("top2_margin") or 0.0))
        intensity = float((primary_det.get("mean_intensity") or 0.0))

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
        from components.smart_diagnostics.implementations.clinical_recommendations import generate_clinical_recommendation
        primary_name = primary_det.get("vit_predicted_display") or primary_det.get("vit_predicted_class")
        sev_model.recommendation = generate_clinical_recommendation(primary_name, grade, lsr)
        return cleaned_report, sev_model

    if match:
        grade = match.group(1).strip()
        prognosis = match.group(2).strip()
        description = match.group(3).strip()
        attn_cov = float((primary_det.get("attention_coverage_pct") or 0.0))
        attn_clusters = int((primary_det.get("attention_cluster_count") or 0))
        top2_margin = float((primary_det.get("top2_margin") or 0.0))
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
        from components.smart_diagnostics.implementations.clinical_recommendations import generate_clinical_recommendation
        primary_name = primary_det.get("vit_predicted_display") or primary_det.get("vit_predicted_class")
        sev_model.recommendation = generate_clinical_recommendation(primary_name, grade, lsr)
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

def generate_report_result(vision_results: Dict[str, Any], farm_metadata=None):
    """Combine model findings with a grounded, configurable LLM recommendation."""
    from ..schemas import ReasoningResponse
    from ..config import settings
    from .grounded_reasoning import (ExplanationSelection, build_context, default_selection,
        assemble_explanation, selection_prompt, selection_schema, render_report)
    from ..implementations.clinical_recommendations import generate_clinical_recommendation

    clinical = _clinical_checklist_assessment(vision_results) if vision_results.get("clinical_observations") is not None else None
    upstream = vision_results.get("upstream_severity")
    baseline = clinical[1] if clinical else SeverityMetrics.model_validate(upstream) if upstream else None
    if not vision_results.get("detections"):
        return ReasoningResponse(status="unavailable", error_code="no_analysis_evidence", reasoning_report="No analyzed region is available for explanation.", severity_assessment=baseline)
    baseline = baseline or create_clinical_fallback_severity(vision_results)

    primary = (vision_results.get("detections") or [{}])[0]
    primary_name = primary.get("vit_predicted_display") or primary.get("vit_predicted_class") or "Condition"
    grade_for_rec = baseline.grade if baseline else "Unassessable"
    cov_for_rec = baseline.lesion_coverage_pct if baseline else None
    rec = generate_clinical_recommendation(primary_name, grade_for_rec, cov_for_rec)

    context = build_context(vision_results, baseline, farm_metadata)
    model_name = None

    def fallback(code, message, status="fallback"):
        explanation = assemble_explanation(context, default_selection(context), "template")
        return ReasoningResponse(status=status, error_code=code, model_name=model_name,
            reasoning_report=message + "\n\n" + render_report(explanation), severity_assessment=baseline,
            explanation=explanation, recommendations=rec)

    try:
        from openai import OpenAI
    except ImportError:
        return fallback("reasoner_not_installed", "Explanation service is unavailable. A reference summary is shown; the original assessment is retained.", "unavailable")
    try:
        client = OpenAI(base_url=cfg.LM_STUDIO_BASE_URL, api_key=cfg.LM_STUDIO_API_KEY,
                        timeout=settings.REASONING_TIMEOUT_SECONDS, max_retries=settings.REASONING_MAX_RETRIES)
        model_name = _discover_model_name(client)
        response = client.chat.completions.create(model=model_name,
            messages=[{"role": "system", "content": _SYSTEM_PROMPT},
                      {"role": "user", "content": selection_prompt(context)}],
            response_format={"type": "json_schema", "json_schema": {"name": "veterinary_explanation", "strict": True,
                "schema": selection_schema(context)}}, temperature=0.1, max_tokens=800)
        content = response.choices[0].message.content
        reported_model = getattr(response, "model", None)
        if isinstance(reported_model, str) and reported_model:
            model_name = reported_model
        if not content or not content.strip():
            return fallback("empty_explanation", "The explanation service returned no report. A reference summary is shown; the original assessment is retained.")
        try:
            if len(content) > 16000 or response.choices[0].finish_reason in ("length", "content_filter"):
                raise ValueError("Incomplete or oversized explanation")
            selection = ExplanationSelection.model_validate_json(content)
            # Validate all selected IDs before accepting any severity influence.
            explanation = assemble_explanation(context, selection, "llm_selected")
            if selection.severity_grade is not None:
                from ..implementations.severity_scorer import combine_reasoned_severity
                combined = combine_reasoned_severity(baseline, selection.severity_grade,
                    [context["evidence"][id]["text"] for id in selection.severity_evidence_ids], context["severity_policy"])
                combined_rec = generate_clinical_recommendation(primary_name, combined.grade, combined.lesion_coverage_pct)
                combined.recommendation = combined_rec
                updated_context = build_context(vision_results, combined, farm_metadata, policy=context["severity_policy"])
                # The original context has already validated the recommendation;
                # the final context renders the combined grade and its evidence.
                rendered_selection = selection.model_copy(update=dict(severity_grade=None, severity_evidence_ids=[]))
                explanation = assemble_explanation(updated_context, rendered_selection, "llm_selected")
                explanation.recommendation = combined_rec
                baseline = combined
                rec = combined_rec
        except ValueError:
            return fallback("invalid_explanation", "The generated explanation could not be verified. A reference summary is shown; the original assessment is retained.")
        return ReasoningResponse(status="ok", reasoning_report=render_report(explanation), model_name=model_name,
            severity_assessment=baseline, explanation=explanation, recommendations=rec)
    except Exception as exc:
        logger.warning("Explanation unavailable (%s)", type(exc).__name__)
        return fallback("explanation_unavailable", "Explanation unavailable. A reference summary is shown. The original image assessment, measurements and review flags are retained; retry explanation separately.")


def generate_veterinary_report(vision_results: Dict[str, Any], farm_metadata=None):
    """Compatibility API for CLI callers consuming a report/assessment pair."""
    result = generate_report_result(vision_results, farm_metadata)
    return result.reasoning_report, result.severity_assessment
