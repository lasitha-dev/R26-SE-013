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
from typing import Any, Dict, List, Optional

from . import config as cfg

logger = logging.getLogger("smart_diagnostics.pipeline.llm")


# ═══════════════════════════════════════════════════════════════════════════
# System prompt — establishes the LLM persona and output structure
# ═══════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """\
You are a **Senior Veterinary Pathologist & Epidemiological Triage Officer** with \
15+ years of field experience in bovine infectious diseases across South and \
Southeast Asia.

You are embedded in an AI-assisted diagnostic pipeline. The upstream computer-vision \
models (YOLOv8s object detector → ViT-B/16 fine-grained classifier) have already \
analysed a cattle photograph and produced structured predictions. Your task is to \
interpret those predictions — together with any farm metadata — and produce a \
**Veterinary Diagnostic Briefing** in Markdown format.

Your output MUST contain exactly these five sections (use level-2 headings):

## 1. Primary Diagnostic Assessment & Certainty Level
State the most likely diagnosis and assign a certainty level: **High** (>85% AI \
confidence + consistent morphology), **Moderate** (60–85% or minor ambiguity), or \
**Ambiguous** (<60% or conflicting signals). Justify the certainty level.

## 2. Pathological & Morphological Rationale
Connect the visual features that the AI model likely detected (e.g., vesicles, \
salivation, mucosal erosions for FMD; firm cutaneous nodules for Lumpy Skin; teat \
hyperkeratosis, oedema, or abnormal milk for Mastitis) to the primary prediction. \
Explain *why* these features support the diagnosis.

## 3. Differential Diagnosis Analysis
Discuss the runner-up class(es) from the probability distribution. Explain why each \
was considered and why it is less likely given the available evidence. If two classes \
are close in confidence, explicitly flag the diagnostic ambiguity.

## 4. Immediate Biosecurity & Triage Protocol
Provide actionable steps: quarantine radius, herd isolation, notifiable-disease \
reporting obligations (especially for Foot-and-Mouth Disease and Lumpy Skin Disease), \
movement restrictions, and vector control if applicable.

## 5. Recommended Confirmatory Laboratory Tests
List the gold-standard laboratory assays for the suspected disease (e.g., RT-PCR \
for FMDV serotyping, virus isolation, California Mastitis Test, Skin biopsy with \
histopathology for LSD). Include specimen type and transport requirements.

Be precise, evidence-based, and avoid speculation beyond what the data supports.\
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
            f"- **Primary AI diagnosis:** "
            f"{det.get('vit_predicted_display', det.get('vit_predicted_class', '?'))}  "
            f"({det.get('vit_confidence_pct', '?')}% confidence)"
        )

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
            # Human-readable key.
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
# Public API — generate_veterinary_report
# ═══════════════════════════════════════════════════════════════════════════

def generate_veterinary_report(
    vision_results: Dict[str, Any],
    farm_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a structured Veterinary Diagnostic Briefing via LM Studio.

    Parameters
    ----------
    vision_results : dict
        The output of :func:`vision_engine.run_vision_pipeline`.
        Must contain ``"detections"`` and ``"image_size"`` keys.
    farm_metadata : dict, optional
        Optional context such as ``herd_size``, ``symptom_duration``,
        ``observed_symptoms``, ``location``, etc.

    Returns
    -------
    str
        A Markdown-formatted clinical briefing, or an error message string
        if the LLM is unreachable.
    """
    # ------------------------------------------------------------------
    # Import openai here so the rest of the pipeline works without it
    # ------------------------------------------------------------------
    try:
        from openai import OpenAI
    except ImportError as exc:
        return (
            "⚠️  **Tier 3 Unavailable:** The `openai` Python package is not "
            "installed.  Install it with `pip install openai>=1.0` and retry.\n\n"
            f"Error: {exc}"
        )

    # ------------------------------------------------------------------
    # Build the client
    # ------------------------------------------------------------------
    client = OpenAI(
        base_url=cfg.LM_STUDIO_BASE_URL,
        api_key=cfg.LM_STUDIO_API_KEY,
    )

    # ------------------------------------------------------------------
    # Discover model
    # ------------------------------------------------------------------
    model_name = _discover_model_name(client)

    # ------------------------------------------------------------------
    # Assemble prompts
    # ------------------------------------------------------------------
    detections = vision_results.get("detections", [])
    image_size = vision_results.get("image_size", {})
    user_prompt = _build_user_prompt(detections, image_size, farm_metadata)

    logger.info(
        "Sending request to LM Studio  (model=%s, detections=%d) ...",
        model_name, len(detections),
    )

    # ------------------------------------------------------------------
    # Call the LLM
    # ------------------------------------------------------------------
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,          # Deterministic-ish for clinical use
            max_tokens=2048,
            top_p=0.9,
        )

        # Extract the assistant message content.
        content = response.choices[0].message.content
        if not content:
            return "⚠️  LLM returned an empty response."

        logger.info("Received LLM response (%d chars).", len(content))
        return content

    except Exception as exc:
        error_type = type(exc).__name__
        logger.error("LLM request failed (%s): %s", error_type, exc)

        return (
            f"⚠️  **Tier 3 Error — LLM Unreachable**\n\n"
            f"Could not connect to LM Studio at `{cfg.LM_STUDIO_BASE_URL}`.\n\n"
            f"**Error:** `{error_type}: {exc}`\n\n"
            f"**Troubleshooting:**\n"
            f"1. Verify LM Studio is running and the server is started.\n"
            f"2. Confirm the model `{model_name}` is loaded.\n"
            f"3. Check that the endpoint URL is correct.\n\n"
            f"*Tier 1 and Tier 2 vision results above remain valid.*"
        )
