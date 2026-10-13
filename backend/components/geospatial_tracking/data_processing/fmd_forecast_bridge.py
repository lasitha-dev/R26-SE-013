"""FMD-05: bridge adapter that lets the generic, disease-parameterized
forecast-origin / forecast-target / model-fitting-exposure infrastructure
(`services/forecast_origin.py`, `services/forecast_target.py`,
`services/model_fitting_exposure.py`, `services/historical_trigger.py`,
`services/source_selector.py` — all built for and previously exercised
only against LSD's canonical schema) run against FMD's own canonical
corpus (`fmd_canonical_outbreaks_conservative.csv`), without modifying any
of that shared/LSD-facing code.

Two narrow, documented schema gaps this bridge closes:

1. `HistoricalOutbreakRecord.model_candidate` — LSD's canonical schema
   carries a `model_candidate` boolean column
   (`data_processing/model_candidate.py`) that
   `services/historical_import.parse_conservative_row` reads directly.
   FMD's canonical CSV has no such column: FMD-03's own, stricter,
   confirmed-status-aware gate is `modelling_eligible`
   (`data_processing/fmd_eligibility.py`) — already a superset check
   (dedup-resolved identity AND Confirmed diagnosis status AND a usable
   event date AND a valid coordinate). This bridge maps
   `model_candidate = (modelling_eligible == "True")`: a faithful,
   documented substitution of an equivalent-or-stricter gate, never an
   invented value.

2. `dedup_status` vocabulary — FMD-03D's same-source authoritative-
   identity guard introduces `DISTINCT_AUTHORITATIVE_EVENT`
   (`fmd_eligibility.DISTINCT_AUTHORITATIVE_EVENT`), a resolved status for
   FMD eligibility purposes but NOT a member of the shared
   `schemas.DedupStatus` enum that the generic `source_selector`/
   `historical_trigger` gates check against
   (`schemas.DEDUP_RESOLVED_STATUSES`). This bridge remaps that one value
   to `SINGLETON` — a real, resolved, non-ambiguous status, exactly what
   `DISTINCT_AUTHORITATIVE_EVENT` means — for the record handed to the
   generic pipeline only. `schemas.py`'s shared enum is never modified,
   and no LSD row is ever touched by this remap. Every other dedup_status
   value the real FMD corpus contains (`SINGLETON` — the only other value
   present, see `FMD_DATA_AUDIT.md`) passes through unchanged. The FMD
   canonical CSV's own `dedup_status` column is never rewritten on disk by
   this module; the remap exists only inside the disposable, throwaway
   repository used to exercise the generic pipeline.

This module only READS the frozen canonical CSV. It never writes to it.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..domain.models import HistoricalOutbreakRecord
from ..repositories.base import OutbreakRepository
from ..schemas import AvailabilityQuality, DedupStatus, GpsQuality
from .fmd_eligibility import DISTINCT_AUTHORITATIVE_EVENT

DEDUP_STATUS_REMAP_FOR_GENERIC_GATE: dict[str, str] = {
    DISTINCT_AUTHORITATIVE_EVENT: DedupStatus.SINGLETON.value,
}


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


def parse_fmd_canonical_row(row: dict) -> HistoricalOutbreakRecord:
    """Pure: one FMD canonical CSV row -> one `HistoricalOutbreakRecord`,
    with the two documented gap-closing remaps above applied (module
    docstring). Every other field is carried through literally, exactly as
    `services/historical_import.parse_conservative_row` does for LSD."""
    raw_dedup_status = _none_if_blank(row.get("dedup_status")) or DedupStatus.SINGLETON.value
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
        dedup_status=DEDUP_STATUS_REMAP_FOR_GENERIC_GATE.get(raw_dedup_status, raw_dedup_status),
        dedup_confidence=_none_if_blank(row.get("dedup_confidence")),
        model_candidate=row.get("modelling_eligible") == "True",
        duplicate_group_id=_none_if_blank(row.get("duplicate_group_id")),
        member_record_ids=_none_if_blank(row.get("member_record_ids")),
    )


def load_fmd_canonical_csv(path: str | Path) -> list[HistoricalOutbreakRecord]:
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [parse_fmd_canonical_row(row) for row in reader]


def import_fmd_canonical_csv(repo: OutbreakRepository, path: str | Path) -> int:
    """Returns the number of records imported (== number of rows read; the
    FULL corpus is imported, every diagnosis status, exactly like
    `historical_import.import_conservative_csv` does for LSD — the
    scientific gate is enforced at query time via `model_candidate`, not
    by dropping rows here)."""
    records = load_fmd_canonical_csv(path)
    for record in records:
        repo.add_historical_record(record)
    return len(records)
