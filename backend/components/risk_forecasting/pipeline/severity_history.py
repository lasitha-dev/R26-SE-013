"""Read-only access to the district severity-history artifact (models/v2/severity_history.json).

"Severity if an outbreak occurs" is the class mix of a district's recorded outbreak years (annual DAPH labels),
shrunk toward the national mix. It is a descriptive estimate from past records, not a model forecast.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

ARTIFACT_PATH = Path(__file__).resolve().parents[1] / "model" / "models" / "v2" / "severity_history.json"
DISEASES = ("FMD", "LSD")


@lru_cache(maxsize=1)
def load_severity_history(path: Path = ARTIFACT_PATH) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lookup(disease: str, district: str, artifact: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """History for one district, or None when the district has no recorded outbreak year (not "LOW")."""
    artifact = artifact or load_severity_history()
    block = artifact["diseases"].get(str(disease).upper())
    if not block:
        return None
    entry = block["districts"].get(district)
    if entry is None:
        return None
    return {"disease": str(disease).upper(), "district": district, **entry, "years": block["years"], "label_unit": block["label_unit"]}


def summary(artifact: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Whole artifact (about 50 small entries) for the UI to cache."""
    return artifact or load_severity_history()
