"""Checkpoint 4 Part 2: canonical (post-dedup) spatial independence.

Checkpoint 2's `data_processing.normalize.assign_spatial_independence`
computes `spatial_independence` over RAW, pre-dedup source records. That
means the same real outbreak represented twice (once in the FAO EMPRES-i
CSV, once in a WAHIS PDF) shares a coordinate with itself across sources
and gets flagged non-independent — not because two real, distinct
outbreaks share a location, but because ONE real outbreak has multiple
raw source rows. That raw-level flag must never be used directly for
scientific direction/speed filtering; it stays as-is, unmodified, for
provenance (rule 5 below).

This module recomputes the same "is this coordinate unique?" question,
but over CANONICAL outbreak identities — i.e., over
`canonical_outbreaks_conservative.csv` rows, where an `AUTO_MERGED_HIGH`
group has already collapsed to ONE row with ONE coordinate. Rules:

1. Members of one `AUTO_MERGED_HIGH` duplicate group represent ONE
   canonical outbreak and never count against each other — automatically
   true here, since the conservative CSV already stores one row per
   merged group (not one row per raw member).
2. Two genuinely distinct canonical outbreaks (two different conservative
   rows) sharing a coordinate remain identifiable as spatially
   non-independent — same "is this coordinate unique across the corpus"
   rule as Checkpoint 2, just applied one level up.
3. APPROXIMATE (or COARSE) GPS requires special caution: a row's own
   `gps_quality` is always carried through in the output, and the `reason`
   column calls it out explicitly, so a consumer never has to guess
   whether "independent" was asserted with EXACT-coordinate confidence or
   merely "no other canonical row happens to round to this same
   imprecise point."
4. Same coordinate alone is NEVER used to deduplicate anything here — this
   module only classifies already-resolved canonical rows, it never
   merges or drops one.
5. The raw-level `spatial_independence` column already present on
   conservative rows (Checkpoint 2/2.5, computed pre-dedup) is left
   completely untouched — this module's output is a SEPARATE column
   (`canonical_spatial_independence`), never an overwrite.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..schemas import GpsQuality


@dataclass
class CanonicalSpatialRow:
    source_record_id: str
    latitude: float | None
    longitude: float | None
    gps_quality: str
    dedup_status: str
    canonical_spatial_independence: bool | None
    shared_coordinate_group_id: str | None
    shared_coordinate_count: int
    reason: str

    def as_dict(self) -> dict:
        return {
            "source_record_id": self.source_record_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "gps_quality": self.gps_quality,
            "dedup_status": self.dedup_status,
            "canonical_spatial_independence": self.canonical_spatial_independence,
            "shared_coordinate_group_id": self.shared_coordinate_group_id,
            "shared_coordinate_count": self.shared_coordinate_count,
            "reason": self.reason,
        }


def compute_canonical_spatial_independence(conservative_rows: list[dict]) -> list[CanonicalSpatialRow]:
    """`conservative_rows` are dict rows as produced by
    `data_processing.build_canonical.build_conservative_rows` (or read
    back from `canonical_outbreaks_conservative.csv`) — one row per
    canonical outbreak identity (a merged HIGH group, or an individually
    unresolved/singleton record)."""
    coord_groups: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for row in conservative_rows:
        lat, lon = row.get("latitude"), row.get("longitude")
        if lat in (None, "") or lon in (None, ""):
            continue
        key = (round(float(lat), 6), round(float(lon), 6))
        coord_groups[key].append(row)

    group_id_by_coord: dict[tuple[float, float], str] = {}
    for i, coord in enumerate(sorted(coord_groups.keys()), start=1):
        group_id_by_coord[coord] = f"COORDGRP:{i:05d}"

    results: list[CanonicalSpatialRow] = []
    for row in conservative_rows:
        lat, lon = row.get("latitude"), row.get("longitude")
        gps_quality = row.get("gps_quality") or GpsQuality.UNKNOWN.value
        dedup_status = row.get("dedup_status") or ""

        if lat in (None, "") or lon in (None, ""):
            results.append(
                CanonicalSpatialRow(
                    source_record_id=row["source_record_id"],
                    latitude=None,
                    longitude=None,
                    gps_quality=gps_quality,
                    dedup_status=dedup_status,
                    canonical_spatial_independence=None,
                    shared_coordinate_group_id=None,
                    shared_coordinate_count=0,
                    reason="missing coordinates — independence cannot be assessed",
                )
            )
            continue

        key = (round(float(lat), 6), round(float(lon), 6))
        group_id = group_id_by_coord[key]
        count = len(coord_groups[key])
        independent = count == 1

        if independent:
            reason = "unique coordinate across the canonical (dedup-resolved) corpus"
            if gps_quality in (GpsQuality.APPROXIMATE.value, GpsQuality.COARSE.value):
                reason += (
                    " — CAUTION: coordinate precision is "
                    f"{gps_quality}, so uniqueness here is not the same confidence as an "
                    "EXACT-precision independent point"
                )
        else:
            reason = f"shared with {count - 1} other canonical outbreak(s) at this coordinate"
            if gps_quality in (GpsQuality.APPROXIMATE.value, GpsQuality.COARSE.value):
                reason += (
                    f" — coordinate precision is {gps_quality}; sharing may reflect "
                    "geocoding/snapping imprecision rather than true co-location"
                )

        results.append(
            CanonicalSpatialRow(
                source_record_id=row["source_record_id"],
                latitude=float(lat),
                longitude=float(lon),
                gps_quality=gps_quality,
                dedup_status=dedup_status,
                canonical_spatial_independence=independent,
                shared_coordinate_group_id=group_id,
                shared_coordinate_count=count,
                reason=reason,
            )
        )

    return results


def load_conservative_rows(path: str | Path) -> list[dict]:
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_canonical_spatial_independence_report(conservative_csv_path: str | Path) -> list[dict]:
    rows = load_conservative_rows(conservative_csv_path)
    return [r.as_dict() for r in compute_canonical_spatial_independence(rows)]
