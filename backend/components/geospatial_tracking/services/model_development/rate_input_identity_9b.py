"""Checkpoint 9B Part 4: canonical target-level dataset identity.

Reads the ALREADY-PERSISTED Checkpoint 9A
`rate_target_level_readiness_9a.csv` -- never regenerates it, never
calls the outbreak database, never rebuilds `d_min`/`v_obs`. Computes
TWO distinct identities:

A. RAW FILE IDENTITY -- SHA256 of the exact CSV bytes.

B. CANONICAL SCIENTIFIC PAYLOAD IDENTITY -- built from the EXACT
   persisted numeric TEXT (never a Python-float round-trip through
   JSON, which can silently change the last significant digits),
   sorted by `target_event_id`, serialized deterministically. This
   protects the exact scientific (target, rate) pairs independent of
   irrelevant CSV row order, while the raw file hash protects every
   byte of the file including its order/formatting.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

TARGET_EVENT_ID_COLUMN = "target_event_id"
RATE_COLUMN = "target_level_median_v_km_day"


@dataclass(frozen=True)
class TargetLevelRow:
    target_event_id: str
    rate_text: str  # exact persisted text, stripped, never reformatted
    rate_value: float  # parsed only for validation -- never used to rebuild rate_text


@dataclass(frozen=True)
class DatasetIdentity:
    input_csv_path: str
    input_csv_sha256: str
    canonical_payload_hash_from_persisted_text: str
    n_rows: int
    n_unique_target_event_id: int
    canonical_numeric_validation_status: str

    def as_dict(self) -> dict:
        return {
            "input_csv_path": self.input_csv_path,
            "input_csv_sha256": self.input_csv_sha256,
            "canonical_payload_hash_from_persisted_text": self.canonical_payload_hash_from_persisted_text,
            "n_rows": self.n_rows,
            "n_unique_target_event_id": self.n_unique_target_event_id,
            "canonical_numeric_validation_status": self.canonical_numeric_validation_status,
        }


def load_target_level_rows(csv_path: Path) -> list[TargetLevelRow]:
    """Reads the persisted CSV as text, preserving the EXACT stripped
    numeric text for `RATE_COLUMN` -- never rewritten/reformatted.
    Read-only; performs no geometry, no DB access."""
    rows: list[TargetLevelRow] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rate_text = row[RATE_COLUMN].strip()
            rate_value = float(rate_text)
            rows.append(TargetLevelRow(target_event_id=row[TARGET_EVENT_ID_COLUMN], rate_text=rate_text, rate_value=rate_value))
    return rows


def raw_csv_sha256(csv_path: Path) -> str:
    return hashlib.sha256(csv_path.read_bytes()).hexdigest()


def canonical_payload_hash_from_persisted_text(rows: list[TargetLevelRow]) -> str:
    """Sorted `[target_event_id, exact_persisted_rate_text]` pairs,
    serialized as UTF-8 JSON with `ensure_ascii=False`,
    `separators=(",",":")`, the numeric value kept as a JSON STRING
    (never reserialized as a Python float, which can silently alter
    trailing digits)."""
    pairs = sorted(([r.target_event_id, r.rate_text] for r in rows), key=lambda p: p[0])
    canonical = json.dumps(pairs, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_rows(rows: list[TargetLevelRow]) -> str:
    """Fails closed (raises `ValueError`) on any duplicate `target_event_id`
    or any non-finite/negative rate value. Returns a status string on
    success -- never silently repairs invalid data."""
    seen: set[str] = set()
    for r in rows:
        if r.target_event_id in seen:
            raise ValueError(f"duplicate target_event_id in persisted dataset: {r.target_event_id!r}")
        seen.add(r.target_event_id)
        if math.isnan(r.rate_value) or math.isinf(r.rate_value):
            raise ValueError(f"non-finite rate value for target_event_id={r.target_event_id!r}: {r.rate_text!r}")
        if r.rate_value < 0.0:
            raise ValueError(f"negative rate value for target_event_id={r.target_event_id!r}: {r.rate_text!r}")
    return "ALL_ROWS_FINITE_NONNEGATIVE_UNIQUE_TARGET_EVENT_ID"


def compute_dataset_identity(csv_path: Path) -> tuple[DatasetIdentity, list[TargetLevelRow]]:
    rows = load_target_level_rows(csv_path)
    validation_status = validate_rows(rows)
    identity = DatasetIdentity(
        input_csv_path=str(csv_path),
        input_csv_sha256=raw_csv_sha256(csv_path),
        canonical_payload_hash_from_persisted_text=canonical_payload_hash_from_persisted_text(rows),
        n_rows=len(rows),
        n_unique_target_event_id=len({r.target_event_id for r in rows}),
        canonical_numeric_validation_status=validation_status,
    )
    return identity, rows
