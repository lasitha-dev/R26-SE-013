"""FMD-03: deterministic modelling-candidate eligibility for FMD canonical
events, layered on top of `model_candidate.py`'s dedup-resolution policy
(reused unmodified) plus the FMD-specific confirmed/suspected/denied status
policy (`fmd_status.py`).

Does NOT train a model and does NOT require case counts, lab metadata,
report-after-event information, or future-known control actions — only the
minimum a later geospatial model protocol genuinely needs: confirmed
status, a resolved (non-duplicate-ambiguous) event, a usable event date, and
a valid coordinate pair.

Reason codes are the single source of truth for WHY a record is excluded —
checked in a fixed, documented priority order so every excluded record gets
exactly one reason (the first one that applies), never a silent drop.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import DEDUP_RESOLVED_STATUSES, NormalizedOutbreakRecord
from .dedup import best_match_date
from .fmd_status import CONFIRMED, classify_diagnosis_status

DISTINCT_AUTHORITATIVE_EVENT = "DISTINCT_AUTHORITATIVE_EVENT"
"""FMD-03D dedup_status value: this record shares source_system with one or
more spatiotemporally-similar records, but each has its own distinct,
non-empty authoritative `global_id` — per the same-source event-identity
rule, these are DISTINCT real EMPRES-i events, not an unresolved duplicate
candidate. Not a member of `schemas.DedupStatus` (that shared enum is not
modified — LSD has no such concept and never produces this value); treated
as a resolved status here, alongside the shared `DEDUP_RESOLVED_STATUSES`,
purely for FMD eligibility purposes. See `build_fmd_canonical.py`'s
same-source authoritative-identity guard for where this value is assigned."""

FMD_DEDUP_RESOLVED_STATUSES = DEDUP_RESOLVED_STATUSES | {DISTINCT_AUTHORITATIVE_EVENT}

STATUS_NOT_CONFIRMED = "STATUS_NOT_CONFIRMED"
MISSING_EVENT_DATE = "MISSING_EVENT_DATE"
INVALID_COORDINATE = "INVALID_COORDINATE"
EVENT_IDENTITY_UNRESOLVED = "EVENT_IDENTITY_UNRESOLVED"
DUPLICATE_UNRESOLVED = "DUPLICATE_UNRESOLVED"
SOURCE_PROVENANCE_INCOMPLETE = "SOURCE_PROVENANCE_INCOMPLETE"
ELIGIBLE = "ELIGIBLE"

_REASON_TEXT = {
    STATUS_NOT_CONFIRMED: "diagnosis_status is not Confirmed (Suspected/Denied/Unknown reports never enter the primary positive corpus)",
    MISSING_EVENT_DATE: "no usable epidemiological event date (onset_date) on this record",
    INVALID_COORDINATE: "latitude/longitude missing or outside the valid WGS84 range",
    EVENT_IDENTITY_UNRESOLVED: "no authoritative event identifier (global_id) on this record",
    DUPLICATE_UNRESOLVED: "unresolved TRUE duplicate candidate (a cross-source or same-authoritative-ID REVIEW_MEDIUM/REVIEW_LOW group) — requires manual adjudication before model use",
    SOURCE_PROVENANCE_INCOMPLETE: "source_system/source_file provenance is missing on this record",
}


def _valid_coordinate(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


@dataclass(frozen=True)
class EligibilityResult:
    modelling_eligible: bool
    eligibility_reason: str  # one of the reason-code constants above


def evaluate_fmd_eligibility(
    record: NormalizedOutbreakRecord,
    *,
    raw_diagnosis_status: str | None,
    dedup_status: str,
) -> EligibilityResult:
    """Fixed-priority-order eligibility check. `dedup_status` is either the
    Checkpoint-2.5-style per-record status already computed by
    `model_candidate.build_conservative_rows` (SINGLETON / AUTO_MERGED_HIGH
    / REVIEW_MEDIUM / REVIEW_LOW) — reused, not re-derived — or the
    FMD-03D `DISTINCT_AUTHORITATIVE_EVENT` value assigned by
    `build_fmd_canonical.py`'s same-source authoritative-identity guard."""
    if not record.source_system or not record.source_file:
        return EligibilityResult(False, SOURCE_PROVENANCE_INCOMPLETE)

    if classify_diagnosis_status(raw_diagnosis_status) != CONFIRMED:
        return EligibilityResult(False, STATUS_NOT_CONFIRMED)

    if not record.event_id:
        return EligibilityResult(False, EVENT_IDENTITY_UNRESOLVED)

    if best_match_date(record) is None:
        return EligibilityResult(False, MISSING_EVENT_DATE)

    if not _valid_coordinate(record.latitude, record.longitude):
        return EligibilityResult(False, INVALID_COORDINATE)

    if dedup_status not in FMD_DEDUP_RESOLVED_STATUSES:
        return EligibilityResult(False, DUPLICATE_UNRESOLVED)

    return EligibilityResult(True, ELIGIBLE)


def reason_text(reason_code: str) -> str:
    return _REASON_TEXT.get(reason_code, reason_code)
