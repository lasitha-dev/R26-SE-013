"""
Outbreak label policy for the v2 pipeline.

Labels come from the curated district-month datasets in model/data/processed.
Their surveillance definition is only documented as "outbreak status in the
curated DAPH-derived dataset"; nothing stronger is claimed.

FMD 2024 is excluded (treated as unknown): every original merged file of the
dataset author has 2024 = 0 outbreaks, and the 78 positives later added follow
an identical rule-like block (13 districts x Jan-Mar & Oct-Dec) not seen in any
other year. Verified 2026-10-13; see the v2 model card.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import pandas as pd

LabelKey = Tuple[str, int, int]  # (district, year, month)

LABEL_YEARS = {
    "FMD": range(2017, 2024),  # 2017-2023 verified; 2024 unverified
    "LSD": range(2020, 2025),  # 2020-2024
}
UNVERIFIED_YEARS = {"FMD": {2024}, "LSD": set()}


def load_labels(disease: str, dataset_csv_path) -> Dict[LabelKey, int]:
    """Return {(district, year, month): 0/1} for the verified label years of a disease."""
    disease = disease.upper()
    df = pd.read_csv(dataset_csv_path, usecols=["district", "year", "month_num", "Outbreak status"])
    df = df.rename(columns={"Outbreak status": "status"})
    df = df[df["year"].isin(list(LABEL_YEARS[disease]))]
    return {
        (r.district, int(r.year), int(r.month_num)): int(r.status)
        for r in df.itertuples(index=False)
    }


def label_lookup(labels: Dict[LabelKey, int], district: str, year: int, month: int) -> Optional[int]:
    """Outbreak status for a district-month, or None when unknown (never defaulted to 0)."""
    return labels.get((district, year, month))
