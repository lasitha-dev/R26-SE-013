"""
Main CLI Entry Point — Veterinary AI Diagnostic Pipeline
===========================================================
Interactive CLI that chains:

    Tier 1 (YOLO) → Tier 2 (ViT) → Tier 3 (LLM via LM Studio)

Run with::

    python -m components.smart_diagnostics.pipeline.main

The user is prompted to select an image via a Tkinter file dialog.
If Tkinter is unavailable (headless / SSH), falls back to ``sys.argv[1]``
or an interactive ``input()`` prompt.
"""

from __future__ import annotations

import logging
import os
import sys
import time

# ═══════════════════════════════════════════════════════════════════════════
# Logging setup — configure root logger for the pipeline
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("smart_diagnostics.pipeline.main")


# ═══════════════════════════════════════════════════════════════════════════
# Image selection — Tkinter dialog with CLI fallbacks
# ═══════════════════════════════════════════════════════════════════════════

def _select_image_path() -> str | None:
    """Prompt the user to select a cattle image file.

    Tries (in order):
        1. ``sys.argv[1]`` if provided.
        2. Tkinter ``filedialog.askopenfilename``.
        3. Interactive ``input()`` prompt.

    Returns ``None`` if the user cancels or provides an empty path.
    """
    # 1. CLI argument.
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if os.path.isfile(path):
            return path
        print(f"✖  File not found: {path}")
        return None

    # 2. Tkinter file dialog.
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()  # Hide the empty Tk window.
        root.attributes("-topmost", True)  # Bring dialog to front.

        path = filedialog.askopenfilename(
            title="Select a Cattle Image for Diagnosis",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"),
                ("JPEG", "*.jpg *.jpeg"),
                ("PNG", "*.png"),
                ("All files", "*.*"),
            ],
        )
        root.destroy()

        if path and os.path.isfile(path):
            return path
        if path:
            print(f"✖  Selected file not found: {path}")
        else:
            print("✖  No file selected.")
        return None

    except Exception:
        # Tkinter unavailable (headless, WSL, etc.).
        pass

    # 3. Interactive prompt.
    path = input("Enter the path to a cattle image: ").strip().strip('"').strip("'")
    if path and os.path.isfile(path):
        return path
    if path:
        print(f"✖  File not found: {path}")
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Pretty-print helpers
# ═══════════════════════════════════════════════════════════════════════════

_DIVIDER = "═" * 72
_THIN_DIVIDER = "─" * 72


def _print_header(title: str) -> None:
    print()
    print(_DIVIDER)
    print(f"  {title}")
    print(_DIVIDER)


def _print_vision_results(results: dict) -> None:
    """Print Tier 1 + 2 vision results in a readable format."""
    status = results.get("status", "UNKNOWN")
    img_size = results.get("image_size", {})

    print(f"\n  Status     : {status}")
    print(f"  Image      : {results.get('image_path', '?')}")
    print(f"  Dimensions : {img_size.get('width', '?')} × {img_size.get('height', '?')} px")

    if status == "REJECTED":
        print(f"\n  ⚠  Reason: {results.get('reason', 'Unknown')}")
        return

    detections = results.get("detections", [])
    print(f"  Detections : {len(detections)}")

    for i, det in enumerate(detections, start=1):
        print(f"\n  {_THIN_DIVIDER}")
        print(f"  Detection {i}:")
        print(f"    YOLO class      : {det.get('yolo_class', '?')}")
        print(f"    YOLO confidence  : {det.get('yolo_confidence', '?')}")
        print(
            f"    Bounding box     : {det.get('bbox', [])}  "
            f"({det.get('bbox_width_px', '?')}×{det.get('bbox_height_px', '?')} px, "
            f"{det.get('bbox_area_pct', '?')}% of frame)"
        )
        print(
            f"    ViT prediction   : {det.get('vit_predicted_display', '?')}  "
            f"({det.get('vit_confidence_pct', '?')}%)"
        )

        probs = det.get("vit_probabilities", {})
        if probs:
            print("    Probability distribution:")
            for cls_name, pct in probs.items():
                bar = "█" * int(pct / 2.5)  # Simple bar chart.
                print(f"      {cls_name:<30s} {pct:6.2f}%  {bar}")


# ═══════════════════════════════════════════════════════════════════════════
# Main pipeline orchestrator
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Run the full 3-tier Veterinary AI Diagnostic Pipeline."""

    _print_header("🐄  Veterinary AI Diagnostic Pipeline  🐄")
    print("  Tier 1: YOLOv8s — Input Gate & Localizer")
    print("  Tier 2: ViT-B/16 — Fine-Grained Disease Classifier")
    print("  Tier 3: Qwen 2.5 — Clinical Reasoning Engine (LM Studio)")
    print(_DIVIDER)

    # ------------------------------------------------------------------
    # Step 1 — Image selection
    # ------------------------------------------------------------------
    image_path = _select_image_path()
    if not image_path:
        print("\n✖  No valid image provided. Exiting.")
        sys.exit(1)

    print(f"\n✔  Selected image: {image_path}")

    # ------------------------------------------------------------------
    # Step 2 — Tier 1 + 2: Vision Pipeline
    # ------------------------------------------------------------------
    _print_header("Tier 1 + 2 — Vision Pipeline Results")

    try:
        from .vision_engine import run_vision_pipeline

        t0 = time.perf_counter()
        vision_results = run_vision_pipeline(image_path)
        elapsed = time.perf_counter() - t0

        _print_vision_results(vision_results)
        print(f"\n  ⏱  Vision pipeline completed in {elapsed:.2f}s")

    except FileNotFoundError as exc:
        print(f"\n✖  {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.exception("Vision pipeline failed.")
        print(f"\n✖  Vision pipeline error: {exc}")
        sys.exit(1)

    # If rejected, no point calling the LLM.
    if vision_results.get("status") == "REJECTED":
        print("\n  Image rejected — Tier 3 (LLM) skipped.")
        print(_DIVIDER)
        sys.exit(0)

    # ------------------------------------------------------------------
    # Step 3 — Tier 3: LLM Clinical Reasoning
    # ------------------------------------------------------------------
    _print_header("Tier 3 — Clinical Diagnostic Briefing (LLM)")

    # Optional: farm metadata can be extended by the user or read from a file.
    farm_metadata = None  # Placeholder — add metadata here if desired.
    # Example:
    # farm_metadata = {
    #     "herd_size": 45,
    #     "symptom_duration": "3 days",
    #     "observed_symptoms": "Excessive salivation, reluctance to eat",
    #     "location": "Western Province, Sri Lanka",
    # }

    try:
        from .llm_reasoner import generate_veterinary_report

        t0 = time.perf_counter()
        report = generate_veterinary_report(vision_results, farm_metadata)
        elapsed = time.perf_counter() - t0

        print()
        print(report)
        print(f"\n  ⏱  LLM reasoning completed in {elapsed:.2f}s")

    except Exception as exc:
        logger.exception("LLM reasoning failed.")
        print(f"\n⚠  Tier 3 error: {exc}")
        print("   Tier 1 and Tier 2 results above remain valid.")

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    _print_header("Pipeline Complete")
    print("  All tiers executed. Review the briefing above.")
    print(_DIVIDER)


# ═══════════════════════════════════════════════════════════════════════════
# Module entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
