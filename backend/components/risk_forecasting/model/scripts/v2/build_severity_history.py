"""Build the district severity-history artifact used to show "severity if an outbreak occurs".

Source: annual DAPH district-year severity labels (data/processed/severity_labels.csv for FMD,
LSD_severity_labels.csv for LSD). For each district the class frequencies of its recorded outbreak years are
combined with the national frequencies (k = 2 pseudo-counts). The "typical" class is the most likely one; when
several classes are within 5 percentage points of the most likely, the most severe of them is shown (a deliberate
cautious rule for an early-warning tool; the full percentages are always displayed next to it). This is a descriptive estimate from past annual records, not a model forecast:
the Stage 2 experiment (docs/v2/STAGE2_EXPERIMENT_PLAN.md) found no model that beats it.

Run from the model directory:  python scripts/v2/build_severity_history.py
Writes only models/v2/severity_history.json.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

MODEL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MODEL_DIR.parents[2]))                       # backend/ (for the district list)
from components.risk_forecasting.pipeline.geography import DISTRICT_NAMES  # noqa: E402

PROCESSED = MODEL_DIR / "data" / "processed"
OUT = MODEL_DIR / "models" / "v2" / "severity_history.json"
CLASSES = ["LOW", "MEDIUM", "HIGH"]
K_SHRINK = 2.0
NEAR_TIE = 0.05
SOURCES = {
    "FMD": {"file": "severity_labels.csv", "rename": {"District": "district", "Year": "year"},
            "score": "cases * outbreak_months / 12 + 10 * deaths (LOW < 50, MEDIUM < 300, HIGH >= 300)"},
    "LSD": {"file": "LSD_severity_labels.csv", "rename": {},
            "score": "cases + 5 * outbreak_months + 10 * deaths (LOW < 63, MEDIUM < 460, HIGH >= 460)"},
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_disease(disease):
    cfg = SOURCES[disease]
    df = pd.read_csv(PROCESSED / cfg["file"]).rename(columns=cfg["rename"])
    unknown = sorted(set(df.district) - set(DISTRICT_NAMES))
    if unknown:
        raise SystemExit(f"{disease}: label districts not in the canonical list: {unknown}")
    national_counts = {c: int((df.severity_class == c).sum()) for c in CLASSES}
    total = sum(national_counts.values())
    national_p = {c: national_counts[c] / total for c in CLASSES}
    districts = {}
    for name, g in df.groupby("district"):
        counts = {c: int((g.severity_class == c).sum()) for c in CLASSES}
        n = sum(counts.values())
        probs = {c: (counts[c] + K_SHRINK * national_p[c]) / (n + K_SHRINK) for c in CLASSES}
        best = max(probs.values())
        typical = [c for c in reversed(CLASSES) if best - probs[c] <= NEAR_TIE + 1e-12][0]   # near-ties -> more severe
        districts[name] = {"outbreak_years": n, "counts": counts, "probabilities": {c: round(probs[c], 4) for c in CLASSES},
                           "typical": typical, "first_year": int(g.year.min()), "last_year": int(g.year.max())}
    return {"label_unit": "annual district-year", "score_definition": cfg["score"], "source_file": cfg["file"],
            "source_sha256": sha256(PROCESSED / cfg["file"]), "years": [int(df.year.min()), int(df.year.max())],
            "n_district_years": int(len(df)), "national": {"counts": national_counts, "probabilities": {c: round(national_p[c], 4) for c in CLASSES}},
            "districts": districts}


def main():
    artifact = {"artifact_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "method": f"district class frequencies shrunk toward the national frequencies (k={K_SHRINK:g}); near-ties within {NEAR_TIE:.0%} show the more severe class; descriptive, not a forecast",
                "diseases": {d: build_disease(d) for d in SOURCES}}
    OUT.write_text(json.dumps(artifact, indent=1), encoding="utf-8")
    for d, block in artifact["diseases"].items():
        print(d, block["n_district_years"], "district-years,", len(block["districts"]), "districts, national", block["national"]["counts"])
    print("written", OUT)


if __name__ == "__main__":
    main()
