"""
Seasonal Outlook: a climatology-based view of the NEXT month, issued before that month starts.

Contract: model/docs/v2/SEASONAL_OUTLOOK_CONTRACT.md. Everything here is deterministic and offline: it reads the
deployed artifact's climatology block (rate, interval, raw counts) and never calls an external API.

Rules enforced in code:
- only the month after the issue month can be issued (next month only);
- no tier, relative risk, contributions or severity (the schema has no such fields);
- one active outlook per disease + district + target (idempotent re-runs);
- a missing district-month fails closed instead of silently falling back to a national rate;
- nothing is written when `dry_run=True`, and planning/reading never creates collections or indexes.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional

from components.risk_forecasting.pipeline.features import shift
from components.risk_forecasting.pipeline.geography import DISTRICT_NAMES
from components.risk_forecasting.pipeline.predictor import V2Predictor
from components.risk_forecasting.schemas import SeasonalOutlookRecord

METHOD_VERSION = "district_month_climatology_v1"


class OutlookTargetError(ValueError):
    """The requested target is not the month after the issue month."""


class OutlookDataError(RuntimeError):
    """The artifact has no evidence for a district-month (fail closed)."""


def climatology_hash(artifact: dict) -> str:
    canonical = json.dumps(artifact["climatology"], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def next_month(today: date) -> tuple:
    return shift((today.year, today.month), 1)


class SeasonalOutlookService:
    def __init__(
        self,
        repository_getter: Callable[[], object],
        predictor_loader: Callable[[str], V2Predictor] = V2Predictor.load,
        clock: Optional[Callable[[], datetime]] = None,
        id_generator: Optional[Callable[[], str]] = None,
    ):
        self.repository_getter = repository_getter
        self.predictor_loader = predictor_loader
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_generator = id_generator or (lambda: f"out_{uuid.uuid4().hex[:12]}")

    @staticmethod
    def key(disease: str, district: str, year: int, month: int) -> str:
        return f"OUTLOOK|{disease}|{district}|{year:04d}-{month:02d}"

    def plan(self, year: int, month: int, diseases: Iterable[str] = ("FMD", "LSD")) -> List[SeasonalOutlookRecord]:
        """Build (not store) the outlooks for the target month."""
        issued = self.clock()
        if (year, month) != next_month(issued.date()):
            expected = next_month(issued.date())
            raise OutlookTargetError(
                f"An outlook can only be issued for the next month ({expected[0]:04d}-{expected[1]:02d}); "
                f"requested {year:04d}-{month:02d}.")
        lead_days = (date(year, month, 1) - issued.date()).days
        records: List[SeasonalOutlookRecord] = []
        for disease in (d.upper() for d in diseases):
            predictor = self.predictor_loader(disease)
            artifact = predictor.artifact
            climatology = artifact["climatology"]
            counts = (climatology.get("counts") or {}).get("district_month") or {}
            intervals = (climatology.get("intervals") or {}).get("district_month") or {}
            source_hash = climatology_hash(artifact)
            for district in DISTRICT_NAMES:
                slot = f"{district}|{month}"
                rate = climatology["district_month"].get(slot)
                evidence = counts.get(slot)
                interval = intervals.get(slot)
                if rate is None or evidence is None or interval is None:
                    raise OutlookDataError(
                        f"{disease} artifact has no climatology evidence for {district} month {month}; "
                        "re-export the artifact before issuing an outlook.")
                positive_years, years_observed = evidence
                records.append(SeasonalOutlookRecord(
                    outlook_id=self.id_generator(),
                    disease=disease,
                    district=district,
                    target_year=year,
                    target_month=month,
                    probability=round(float(rate), 6),
                    interval_level=float(climatology["intervals"]["level"]),
                    probability_low=round(float(min(interval[0], rate)), 6),
                    probability_high=round(float(max(interval[1], rate)), 6),
                    years_observed=int(years_observed),
                    positive_years=int(positive_years),
                    method_version=METHOD_VERSION,
                    source_artifact_version=predictor.model_version,
                    source_artifact_hash=source_hash,
                    data_cutoff=artifact["training_period"][1],
                    issue_date=issued.date().isoformat(),
                    generated_at=issued.isoformat(),
                    lead_days=lead_days,
                    idempotency_key=self.key(disease, district, year, month),
                ))
        return records

    def generate(self, year: int, month: int, diseases: Iterable[str] = ("FMD", "LSD"), dry_run: bool = True) -> dict:
        """Preview (dry_run) or store the outlooks. Existing active outlooks are reused, never rewritten."""
        planned = self.plan(year, month, diseases)
        repository = self.repository_getter()
        existing_keys = {r.idempotency_key for r in planned if repository.get_by_key(r.idempotency_key)}
        to_create = [r for r in planned if r.idempotency_key not in existing_keys]
        summary = {
            "target_period": f"{year:04d}-{month:02d}",
            "dry_run": dry_run,
            "status": "PREVIEW" if dry_run else "OK",
            "planned": len(planned),
            "already_issued": len(existing_keys),
            "would_create": len(to_create),
            "lead_days": planned[0].lead_days if planned else None,
            "by_disease": {d: sum(1 for r in to_create if r.disease == d) for d in sorted({r.disease for r in planned})},
            "saved": 0,
            "failed": [],
        }
        if dry_run:
            return summary
        for record in to_create:
            try:
                repository.save(record)
                summary["saved"] += 1
            except RuntimeError:
                raise
            except Exception as exc:  # one bad record must not hide the others; re-running completes the rest
                summary["failed"].append({"key": record.idempotency_key, "error": type(exc).__name__})
        if summary["failed"]:
            summary["status"] = "PARTIAL"
        return summary

    def void(self, outlook_id: str) -> SeasonalOutlookRecord:
        """Withdraw a wrongly issued outlook (content is kept for audit)."""
        return self.repository_getter().set_status(outlook_id, "VOIDED")

    def correct(self, outlook_id: str, replacement: SeasonalOutlookRecord) -> SeasonalOutlookRecord:
        """Mark an outlook CORRECTED and store its replacement (same key, `replaces_outlook_id` set)."""
        repository = self.repository_getter()
        repository.set_status(outlook_id, "CORRECTED")
        return repository.save(replacement.model_copy(update={"replaces_outlook_id": outlook_id}))
