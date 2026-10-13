"""Checkpoint 4 Part 3: historical event/target-occurrence date.

Historical SOURCE AVAILABILITY (`operational_availability_date` /
`proxy_availability_date`, Checkpoint 1-3) and TARGET OCCURRENCE (when the
outbreak itself actually happened, for building future-forecast targets)
are different concepts and must not be conflated. This module derives the
latter, explicitly, per canonical record:

    historical_event_date
    historical_event_date_quality      (HIGH / MEDIUM / UNKNOWN)
    historical_event_date_source_field (the literal field name copied from)

Priority, by source system (recovered from the `source_record_id` prefix,
e.g. "WAHIS_PDF:Event_3473.pdf:000002" — a stable format since Checkpoint
2's `normalize.make_source_record_id`):

    WAHIS_PDF:
        1. outbreak_start_date  -> HIGH   (outbreak-specific occurrence)
        2. event_start_date     -> MEDIUM (broader event-level fallback)
        3. (neither)            -> UNKNOWN

    FAO_EMPRESI_CSV:
        1. onset_date            -> HIGH   (this source's documented
                                             observation/onset field —
                                             see data_processing/csv_parser.py)
        2. (nothing else exists for this source)
        3. (missing)             -> UNKNOWN

    FAO_EMPRESI_BIGQUERY_CSV (FMD-03's source system, see
    data_processing/fmd_source_adapter.py):
        1. onset_date            -> HIGH   (this source's own documented
                                             observation/onset field,
                                             identical role to
                                             FAO_EMPRESI_CSV's onset_date —
                                             see FMD_DATA_AUDIT.md "DATE
                                             VALIDATION", 100% VALID across
                                             the real 9,526-row corpus)
        2. (nothing else exists for this source)
        3. (missing)             -> UNKNOWN

NEVER used, under any circumstance, as historical_event_date:
    - report_date            (source-document filing date — see
                               schemas.py DATE SEMANTICS category B)
    - proxy_availability_date (a distinct RETROSPECTIVE_PROXY-mode
                               *availability* substitute, not a target-
                               occurrence claim — using it here "because
                               it's convenient" would silently blur the
                               source-availability/target-occurrence
                               distinction this module exists to prevent)

All original date fields on the record are left completely untouched —
this is a pure, read-only derivation.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.models import HistoricalOutbreakRecord

HIGH, MEDIUM, UNKNOWN = "HIGH", "MEDIUM", "UNKNOWN"


@dataclass
class HistoricalEventDate:
    historical_event_date: str | None
    historical_event_date_quality: str
    historical_event_date_source_field: str | None


def _source_system_of(record: HistoricalOutbreakRecord) -> str | None:
    if not record.source_record_id or ":" not in record.source_record_id:
        return None
    return record.source_record_id.split(":", 1)[0]


def derive_historical_event_date(record: HistoricalOutbreakRecord) -> HistoricalEventDate:
    source_system = _source_system_of(record)

    if source_system == "WAHIS_PDF":
        if record.outbreak_start_date:
            return HistoricalEventDate(record.outbreak_start_date, HIGH, "outbreak_start_date")
        if record.event_start_date:
            return HistoricalEventDate(record.event_start_date, MEDIUM, "event_start_date")
        return HistoricalEventDate(None, UNKNOWN, None)

    if source_system in ("FAO_EMPRESI_CSV", "FAO_EMPRESI_BIGQUERY_CSV"):
        if record.onset_date:
            return HistoricalEventDate(record.onset_date, HIGH, "onset_date")
        return HistoricalEventDate(None, UNKNOWN, None)

    # Unknown/unrecognized source system: fall back to the same priority
    # WAHIS uses (outbreak_start_date > event_start_date), then CSV's
    # onset_date, before giving up — still never report_date or a proxy
    # field. This keeps the function total or a genuinely new source
    # system, rather than raising, while never inventing higher confidence
    # than the evidence supports.
    if record.outbreak_start_date:
        return HistoricalEventDate(record.outbreak_start_date, MEDIUM, "outbreak_start_date")
    if record.onset_date:
        return HistoricalEventDate(record.onset_date, MEDIUM, "onset_date")
    if record.event_start_date:
        return HistoricalEventDate(record.event_start_date, MEDIUM, "event_start_date")
    return HistoricalEventDate(None, UNKNOWN, None)
