"""Instant and Sri Lanka calendar-date handling for host case timestamps.

Host `diagnostic_cases` timestamps arrive in two shapes:

- BSON dates, written with `datetime.utcnow()` (naive UTC);
- legacy naive strings `"YYYY-MM-DD HH:MM:SS[.ffffff]"`, written by the
  host's earlier `datetime.utcnow().strftime(...)` code path (verified in
  git history of `components/health_anomaly/router.py`) -- also UTC, just
  without a marker.

Both therefore carry a UTC instant. Converting each value to an explicit,
offset-aware instant happens ONCE, at the host boundary
(`host_operational_adapter.host_timestamp_text`); everything downstream
reads offset-aware ISO text and only ever converts an instant to a Sri
Lanka calendar date (Asia/Colombo, UTC+05:30, no DST). An offset that is
already present is never re-interpreted, so no value is converted twice.
A date-only value is a calendar date, not an instant, and is kept as-is.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

SRI_LANKA_TIMEZONE = timezone(timedelta(hours=5, minutes=30))  # Asia/Colombo, no DST
HOST_NAIVE_TIMESTAMP_BASIS = "NAIVE_HOST_TIMESTAMPS_ARE_UTC"

_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_instant(value: str | None) -> datetime | None:
    """Offset-aware UTC instant for an ISO date-time text, or `None` for a
    missing, date-only or unparseable value. Naive text is UTC (module
    docstring); text with an offset keeps that offset."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or _DATE_ONLY.match(text):
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_instant_text(value: str) -> str:
    """Host string -> explicit UTC ISO text (`...+00:00`). Date-only and
    unparseable strings are returned unchanged (never guessed)."""
    instant = parse_instant(value)
    return instant.isoformat() if instant is not None else value


def sri_lanka_date(value: str | None) -> date | None:
    """The Asia/Colombo calendar date of a case timestamp; a date-only
    value is already a calendar date. `None` when absent/unparseable."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if _DATE_ONLY.match(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    instant = parse_instant(text)
    return instant.astimezone(SRI_LANKA_TIMEZONE).date() if instant is not None else None
