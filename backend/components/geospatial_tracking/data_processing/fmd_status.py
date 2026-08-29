"""FMD-03: diagnosis-status policy for the FAO EMPRES-i FMD export.

The EMPRES-i BigQuery CSV's `diagnosis_status` column (surfaced on
`RawOutbreakRecord.diagnostic_result` by `fmd_source_adapter.py`) takes three
values in the real export: Confirmed, Suspected, Denied. Unlike the existing
single-disease LSD corpus (which has no comparable status column to filter
on), FMD-03 must not treat all 9,526 rows as confirmed positive events:

  CONFIRMED — eligible for the primary positive-event modelling corpus.
  SUSPECTED — retained in every raw/audit output, but never mixed into the
      primary confirmed-positive corpus (a later, clearly-labeled secondary/
      sensitivity dataset could use it — not built by this checkpoint).
  DENIED    — retained for provenance/audit only. DENIED / NON-POSITIVE
      REPORT: the source did not confirm this reported event — it is
      excluded from the confirmed positive corpus, but that is not the same
      claim as a scientifically valid supervised negative/control
      observation. This module never manufactures negative/control samples
      from DENIED rows, and no downstream code may treat a DENIED row as an
      ML negative example without a separate, explicitly justified decision.
  UNKNOWN   — the status string didn't match any recognized value (defensive
      case; the real 2002-2026 export has zero such rows).

This module never mutates `diagnostic_result` (the raw source string is
preserved verbatim on the record) — `classify_diagnosis_status` is a pure
read-side classification, mirroring `species.py`/`disease.py`'s pattern of
normalization-for-decision-making without overwriting the source field.
"""

from __future__ import annotations

from enum import Enum

CONFIRMED = "CONFIRMED"
SUSPECTED = "SUSPECTED"
DENIED = "DENIED"
UNKNOWN = "UNKNOWN"


class FMDDiagnosisStatus(str, Enum):
    CONFIRMED = CONFIRMED
    SUSPECTED = SUSPECTED
    DENIED = DENIED
    UNKNOWN = UNKNOWN


_RAW_TO_STATUS = {
    "confirmed": CONFIRMED,
    "suspected": SUSPECTED,
    "denied": DENIED,
}


def classify_diagnosis_status(raw_diagnosis_status: str | None) -> str:
    """Classify a raw `diagnosis_status` string (as carried on
    `RawOutbreakRecord.diagnostic_result`) into CONFIRMED/SUSPECTED/DENIED/
    UNKNOWN. Case-insensitive, whitespace-tolerant; any unrecognized or
    missing value classifies as UNKNOWN rather than being guessed."""
    if raw_diagnosis_status is None:
        return UNKNOWN
    key = raw_diagnosis_status.strip().lower()
    return _RAW_TO_STATUS.get(key, UNKNOWN)


def is_primary_positive_corpus_eligible(raw_diagnosis_status: str | None) -> bool:
    """True only for CONFIRMED — the sole status admitted into the primary
    conservative positive-event canonical corpus (see module docstring)."""
    return classify_diagnosis_status(raw_diagnosis_status) == CONFIRMED
