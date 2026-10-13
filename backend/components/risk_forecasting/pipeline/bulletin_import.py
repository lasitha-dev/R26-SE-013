"""
DAPH bulletin import: lets officials add district-month outbreak facts transcribed from official
bulletins, so surveillance coverage does not depend only on farms registered in the app.

Rules (nothing is ever inferred):
- Only rows that are explicitly entered are stored. A district-month that is absent from the file
  stays *unknown*; it is never read as "no outbreak".
- Every row names its source document (bulletin and page), so each fact can be traced and audited.
- `outbreak` must be an explicit 1 or 0. `cases` / `deaths` are optional; an outbreak of 0 cannot carry
  positive counts.
- Months already covered by the curated training labels (the verified years) are skipped: the curated
  dataset takes precedence there. Bulletins add value for months outside it (for example the unverified
  FMD 2024 labels, or 2025 onwards).
- Importing is a two-step operation: `plan_import` previews exactly what would be written and
  `apply_import` writes only if the previewed write count is confirmed.

Pure functions plus a thin collection adapter (find / replace_one), so everything is testable offline.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from components.risk_forecasting.pipeline.geography import normalize_district
from components.risk_forecasting.pipeline.labels import LABEL_YEARS, UNVERIFIED_YEARS

COLLECTION = "surveillance_bulletin_reports"
SOURCE = "DAPH_BULLETIN_IMPORT"
DISEASES = ("FMD", "LSD")
YEAR_RANGE = (2017, 2030)
TEMPLATE_COLUMNS = ["disease", "district", "year", "month", "outbreak", "cases", "deaths", "source_document", "entered_by"]
TEMPLATE_EXAMPLE = "FMD,Kandy,2025,3,1,12,2,DAPH Annual Bulletin 2025 p.14,officer@example.lk\n"


@dataclass(frozen=True)
class BulletinRow:
    disease: str
    district: str
    year: int
    month: int
    outbreak: int
    cases: Optional[int]
    deaths: Optional[int]
    source_document: str
    entered_by: Optional[str]
    line: int = 0

    @property
    def key(self) -> str:
        return f"{self.disease}|{self.district}|{self.year:04d}-{self.month:02d}"

    def document(self) -> dict:
        return {"_id": self.key, "disease": self.disease, "district": self.district, "year": self.year,
                "month": self.month, "outbreak": self.outbreak, "cases": self.cases, "deaths": self.deaths,
                "source_document": self.source_document, "entered_by": self.entered_by}


def _count(value: str, name: str) -> Tuple[Optional[int], Optional[str]]:
    value = (value or "").strip()
    if value == "":
        return None, None
    if not value.isdigit():
        return None, f"{name} must be a whole number >= 0 or blank (got '{value}')"
    return int(value), None


def curated_covers(disease: str, year: int) -> bool:
    """True for verified curated-label years (bulletin rows are redundant there)."""
    return year in LABEL_YEARS[disease] and year not in UNVERIFIED_YEARS.get(disease, set())


def parse_bulletin_csv(text: str) -> Tuple[List[BulletinRow], List[dict]]:
    """Parse and validate a bulletin CSV. Returns (valid rows, errors); an invalid row is never imported."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    missing_columns = [c for c in TEMPLATE_COLUMNS[:5] + ["source_document"] if c not in (reader.fieldnames or [])]
    if missing_columns:
        return [], [{"line": 1, "error": f"missing column(s): {', '.join(missing_columns)}"}]

    rows: List[BulletinRow] = []
    errors: List[dict] = []
    seen: Dict[str, int] = {}
    for line, raw in enumerate(reader, start=2):
        problems: List[str] = []
        disease = (raw.get("disease") or "").strip().upper()
        if disease not in DISEASES:
            problems.append(f"disease must be one of {', '.join(DISEASES)}")
        district = normalize_district(raw.get("district"))
        if not district:
            problems.append(f"unknown district '{(raw.get('district') or '').strip()}'")
        try:
            year, month = int((raw.get("year") or "").strip()), int((raw.get("month") or "").strip())
            if not (YEAR_RANGE[0] <= year <= YEAR_RANGE[1] and 1 <= month <= 12):
                problems.append(f"year must be {YEAR_RANGE[0]}-{YEAR_RANGE[1]} and month 1-12")
        except ValueError:
            year = month = 0
            problems.append("year and month must be whole numbers")
        outbreak_text = (raw.get("outbreak") or "").strip()
        if outbreak_text not in ("0", "1"):
            problems.append("outbreak must be exactly 1 or 0 (leave the row out if the bulletin does not say)")
        cases, case_error = _count(raw.get("cases"), "cases")
        deaths, death_error = _count(raw.get("deaths"), "deaths")
        problems += [e for e in (case_error, death_error) if e]
        if outbreak_text == "0" and ((cases or 0) > 0 or (deaths or 0) > 0):
            problems.append("outbreak 0 cannot have cases or deaths above 0")
        source_document = (raw.get("source_document") or "").strip()
        if not source_document:
            problems.append("source_document (bulletin and page) is required")

        if not problems:
            row = BulletinRow(disease, district, year, month, int(outbreak_text), cases, deaths,
                              source_document, (raw.get("entered_by") or "").strip() or None, line)
            if row.key in seen:
                problems.append(f"duplicate of line {seen[row.key]} ({row.key})")
            else:
                seen[row.key] = line
                rows.append(row)
        if problems:
            errors.append({"line": line, "error": "; ".join(problems)})
    return rows, errors


@dataclass
class ImportPlan:
    to_write: List[BulletinRow] = field(default_factory=list)       # new or changed
    new: int = 0
    changed: List[dict] = field(default_factory=list)                # overwrites: before / after
    unchanged: int = 0
    skipped_curated: List[str] = field(default_factory=list)         # keys covered by curated labels
    errors: List[dict] = field(default_factory=list)

    def summary(self) -> dict:
        return {"rows_to_write": len(self.to_write), "new": self.new, "changed": len(self.changed),
                "unchanged": self.unchanged, "skipped_covered_by_curated_labels": len(self.skipped_curated),
                "errors": len(self.errors), "changed_details": self.changed, "error_details": self.errors}


def plan_import(rows: Iterable[BulletinRow], existing: Dict[str, dict], errors: Optional[List[dict]] = None) -> ImportPlan:
    plan = ImportPlan(errors=list(errors or []))
    for row in rows:
        if curated_covers(row.disease, row.year):
            plan.skipped_curated.append(row.key)
            continue
        stored = existing.get(row.key)
        if stored is None:
            plan.new += 1
            plan.to_write.append(row)
            continue
        fields = ("outbreak", "cases", "deaths", "source_document")
        before = {f: stored.get(f) for f in fields}
        after = {f: row.document()[f] for f in fields}
        if before == after:
            plan.unchanged += 1
        else:
            plan.changed.append({"key": row.key, "before": before, "after": after})
            plan.to_write.append(row)
    return plan


class StaleImportPreview(Exception):
    pass


class ImportBlocked(Exception):
    pass


def fetch_existing(collection, rows: Iterable[BulletinRow]) -> Dict[str, dict]:
    keys = sorted({row.key for row in rows})
    if not keys:
        return {}
    return {doc["_id"]: doc for doc in collection.find({"_id": {"$in": keys}})}


def apply_import(collection, rows: List[BulletinRow], errors: List[dict], expected_write_count: Optional[int],
                 now: Optional[datetime] = None) -> dict:
    """Write the planned rows. Refuses to run with validation errors, without a confirmed count,
    or if the number of rows to write differs from what the preview showed (data changed meanwhile)."""
    plan = plan_import(rows, fetch_existing(collection, rows), errors)
    if plan.errors:
        raise ImportBlocked(f"{len(plan.errors)} row(s) failed validation; fix the file and preview again")
    if expected_write_count is None:
        raise ImportBlocked("preview first, then confirm with the number of rows it reported")
    if expected_write_count != len(plan.to_write):
        raise StaleImportPreview(
            f"preview said {expected_write_count} rows but {len(plan.to_write)} would be written now; preview again")
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    for row in plan.to_write:
        document = {**row.document(), "imported_at": stamp, "source": SOURCE}
        collection.replace_one({"_id": row.key}, document, upsert=True)
    return {"status": "OK", "written": len(plan.to_write), **plan.summary()}
