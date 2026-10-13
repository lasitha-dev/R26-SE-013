"""Single shared date parser for Checkpoint 3's domain/service layer.

Historical records (`data_processing/dedup.py`) only ever use
`YYYY/MM/DD` (WAHIS) or `YYYY-MM-DD` (FAO EMPRES-i CSV). Live domain
timestamps (`AnimalReport.submitted_at`/`accepted_at`, a forecast's `t0`)
may additionally be full ISO-8601 datetimes. This module is the one place
that reconciles both conventions, rather than scattering date-parsing
logic across `aggregation.py` and `source_selector.py`.
"""

from __future__ import annotations

from datetime import date, datetime

from ..data_processing.dedup import parse_date as _parse_wahis_style_date


def parse_flexible_date(raw: str | None) -> date | None:
    """Returns only the DATE component — time-of-day is not modeled by
    this checkpoint's domain layer. Returns None (never fabricates a
    date) when `raw` is empty or unparseable in any known format."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        pass
    return _parse_wahis_style_date(raw)
