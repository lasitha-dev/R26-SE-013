"""Veterinary AI Diagnostic Pipeline — 3-tier inference (YOLO → ViT → LLM).

Run as a standalone CLI tool:
    python -m components.smart_diagnostics.pipeline.main
"""

__all__ = [
    "config",
    "vision_engine",
    "llm_reasoner",
    "main",
]
