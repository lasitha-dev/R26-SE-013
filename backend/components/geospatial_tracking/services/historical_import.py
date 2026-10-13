"""Import Checkpoint 2.5's conservative canonical dataset into an
`OutbreakRepository` as `HistoricalOutbreakRecord` rows.

Imports the FULL corpus — including `REVIEW_MEDIUM`/`REVIEW_LOW`/
`model_candidate=False` rows — nothing is dropped or altered at import
time, and the source CSV is never modified (read-only). The scientific
model_candidate/dedup-status hard gate is enforced at QUERY time by
`services/source_selector.py`, not here — see REPOSITORY_DESIGN.md
"Where the model-candidate gate lives" for why: SOURCE-09/10/11-style
tests need ineligible records to actually exist in storage to prove the
selector excludes them; silently filtering at import time would make that
gate untestable and would also throw away the audit trail Checkpoint 2.5
was built to preserve.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..domain.models import HistoricalOutbreakRecord
from ..repositories.base import OutbreakRepository
from ..schemas import AvailabilityQuality, DedupStatus, GpsQuality


def _none_if_blank(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _to_float(value: str | None) -> float | None:
    value = _none_if_blank(value)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in ("true", "1", "yes")


def parse_conservative_row(row: dict) -> HistoricalOutbreakRecord:
    return HistoricalOutbreakRecord(
        source_record_id=row["source_record_id"],
        country=_none_if_blank(row.get("country")),
        disease=_none_if_blank(row.get("disease")),
        event_id=_none_if_blank(row.get("event_id")),
        outbreak_id=_none_if_blank(row.get("outbreak_id")),
        event_start_date=_none_if_blank(row.get("event_start_date")),
        outbreak_start_date=_none_if_blank(row.get("outbreak_start_date")),
        onset_date=_none_if_blank(row.get("onset_date")),
        confirmation_date=_none_if_blank(row.get("confirmation_date")),
        report_date=_none_if_blank(row.get("report_date")),
        operational_availability_date=_none_if_blank(row.get("operational_availability_date")),
        operational_availability_quality=_none_if_blank(row.get("operational_availability_quality"))
        or AvailabilityQuality.UNKNOWN.value,
        proxy_availability_date=_none_if_blank(row.get("proxy_availability_date")),
        proxy_availability_quality=_none_if_blank(row.get("proxy_availability_quality"))
        or AvailabilityQuality.UNKNOWN.value,
        proxy_availability_source_field=_none_if_blank(row.get("proxy_availability_source_field")),
        latitude=_to_float(row.get("latitude")),
        longitude=_to_float(row.get("longitude")),
        gps_quality=_none_if_blank(row.get("gps_quality")) or GpsQuality.UNKNOWN.value,
        species=_none_if_blank(row.get("species")),
        dedup_status=_none_if_blank(row.get("dedup_status")) or DedupStatus.SINGLETON.value,
        dedup_confidence=_none_if_blank(row.get("dedup_confidence")),
        model_candidate=_to_bool(
            row.get("model_candidate")
            if row.get("model_candidate") not in (None, "")
            else row.get("modelling_eligible")
        ),
        duplicate_group_id=_none_if_blank(row.get("duplicate_group_id")),
        member_record_ids=_none_if_blank(row.get("member_record_ids")),
    )


def load_conservative_csv(path: str | Path) -> list[HistoricalOutbreakRecord]:
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [parse_conservative_row(row) for row in reader]


def import_conservative_csv(repo: OutbreakRepository, path: str | Path) -> int:
    """Returns the number of records imported (== number of rows read,
    since nothing is filtered at import time)."""
    records = load_conservative_csv(path)
    for record in records:
        repo.add_historical_record(record)
    return len(records)
