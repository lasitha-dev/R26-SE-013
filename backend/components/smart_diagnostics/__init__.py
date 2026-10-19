"""Smart Diagnostics package (detector + classifier + API router)."""

# Code walkthrough:
# 1. schemas.py defines the evidence and response contracts.
# 2. routes.py coordinates photo preparation and model calls.
# 3. implementations/ contains detection, classification, masks and grading rules.
# 4. pipeline/llm_reasoner.py validates evidence-based explanation selections.

__all__ = [
    "config",
    "logger",
    "image_service",
    "interfaces",
    "implementations",
    "schemas",
    "routes",
]
