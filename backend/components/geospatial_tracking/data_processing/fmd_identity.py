"""FMD-03: stable canonical event identity for FAO EMPRES-i FMD records.

Deliberately NOT a row-number-based id (those are unstable across re-runs
that add/reorder input, and unstable if the raw CSV is ever re-exported
with rows in a different order). `global_id` is EMPRES-i's own authoritative
per-event identifier for this source (verified unique across all 9,526 raw
rows — 0 duplicates, see FMD_DATA_AUDIT.md), so the canonical id is a
deterministic, source-namespaced wrapper around it: stable across repeated
builds of identical input, and self-describing about which source/namespace
it came from (never to be compared byte-for-byte against a WAHIS `OB_`
id or the "Latest Reported Events" export's `Event ID`, which are different
namespaces — see dedup.py's Level 1 same-source-system gate).
"""

from __future__ import annotations

FMD_EMPRESI_BIGQUERY_ID_PREFIX = "FAO_EMPRESI_BIGQUERY_CSV"


def fmd_canonical_event_id(global_id: str | None) -> str | None:
    if not global_id:
        return None
    return f"{FMD_EMPRESI_BIGQUERY_ID_PREFIX}:{global_id}"
