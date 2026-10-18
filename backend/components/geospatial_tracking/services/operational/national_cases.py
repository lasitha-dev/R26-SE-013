"""National case-surveillance records for the Outbreak Map (read-only).

Turns raw host `diagnostic_cases` + `farms` documents into privacy-reduced
map records for ANY authenticated veterinarian:

- only LSD/FMD (via the existing `resolve_operational_disease` gate, never
  guessed); other diagnoses are counted as excluded, not shown;
- the case's own verification state is kept: `VERIFIED` (vet-verified) and
  `PENDING_VERIFICATION` are separate and must never be drawn alike;
- coordinates are the farm's own GPS, used only when the existing
  `_has_valid_coordinates` rule accepts them; otherwise the record is kept
  with `location_status = LOCATION_REQUIRED` and no point;
- identity is reduced to a stable one-way `record_key`. No farm/owner/vet
  name, email, animal id, free-text clinical notes or raw database id is
  returned. The clinical summary is limited to non-identifying fields
  (severity, stage, diagnostic-model confidence).

Nothing is written, inferred or repaired here.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Iterable

from .disease_normalization import resolve_operational_disease
from .farm_normalization import _has_valid_coordinates


def _timestamp_text(value: Any) -> str | None:
    from ...repositories.host_operational_adapter import host_timestamp_text

    text = host_timestamp_text(value)
    return text if isinstance(text, str) and text.strip() else None


def record_key(case_id: str) -> str:
    return "CASE:" + hashlib.sha256(f"adrs-geo-national::{case_id}".encode("utf-8")).hexdigest()[:20]


def _clean_text(value: Any, limit: int = 40) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:limit]


def build_national_case_records(case_docs: Iterable[dict], farm_docs_by_id: dict[str, dict]) -> dict:
    records: list[dict] = []
    excluded: Counter = Counter()
    for doc in case_docs:
        case_id = str(doc.get("_id")) if doc.get("_id") is not None else None
        if not case_id:
            excluded["missing_case_id"] += 1
            continue
        disease = resolve_operational_disease(doc.get("disease_name"))
        if disease is None:
            excluded["disease_not_lsd_or_fmd"] += 1
            continue
        verified = doc.get("verified") is True
        farm = farm_docs_by_id.get(str(doc.get("farm_id"))) if doc.get("farm_id") else None
        lat = farm.get("latitude") if farm else None
        lon = farm.get("longitude") if farm else None
        has_gps = farm is not None and _has_valid_coordinates(lat, lon)
        if not has_gps:
            excluded["no_usable_farm_gps"] += 1
        confidence = doc.get("confidence")
        records.append(
            {
                "record_key": record_key(case_id),
                "disease": disease.value,
                "verification_status": "VERIFIED" if verified else "PENDING_VERIFICATION",
                "status_label": _clean_text(doc.get("status")),
                "reported_at": _timestamp_text(doc.get("created_at")),
                "verified_at": _timestamp_text(doc.get("verified_at")) if verified else None,
                "district": _clean_text(farm.get("location_district"), 80) if farm else None,
                "latitude": float(lat) if has_gps else None,
                "longitude": float(lon) if has_gps else None,
                "location_status": "VALID" if has_gps else "LOCATION_REQUIRED",
                "location_quality": "FARM_GPS" if has_gps else "MISSING",
                "clinical_summary": {
                    "severity": _clean_text(doc.get("severity")),
                    "stage": _clean_text(doc.get("stage")),
                    "model_confidence": float(confidence) if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) else None,
                },
                "source": "ADRS_DIAGNOSTIC_CASE",
            }
        )
    by_status = Counter(r["verification_status"] for r in records)
    by_disease = Counter(r["disease"] for r in records)
    return {
        "records": records,
        "summary": {
            "returned": len(records),
            "mappable": sum(1 for r in records if r["location_status"] == "VALID"),
            "by_verification_status": dict(by_status),
            "by_disease": dict(by_disease),
            "excluded": dict(excluded),
        },
    }
