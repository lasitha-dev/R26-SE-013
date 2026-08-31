"""Checkpoint 4.5 Parts 1-3: coordinate-collision status.

**Coordinate uniqueness is a DATA-QUALITY / CO-LOCATION indicator. It is
NOT proof that outbreak events are epidemiologically or statistically
independent.** Checkpoint 4's `services/canonical_spatial.py` computed a
boolean `canonical_spatial_independence` from exactly this same
"is the rounded coordinate unique?" question, and calling that "spatial
independence" overstated what it actually establishes — two outbreaks a
few hundred meters apart with distinct (non-colliding) rounded
coordinates are not thereby proven statistically independent events, and
this module makes no such claim either. It only classifies coordinate
CO-LOCATION among conservative outbreak identities. `services/canonical_spatial.py`
is left unmodified and its output (`canonical_spatial_independence.csv`)
is kept on disk for provenance/comparison — see DATA_PROVENANCE.md — but
is superseded by this module going forward.

**Resolved vs. unresolved collisions are different evidence (Part 2).** A
resolved candidate (`SINGLETON`/`AUTO_MERGED_HIGH`/`MANUALLY_ACCEPTED` —
`schemas.DEDUP_RESOLVED_STATUSES`) sharing a coordinate with another
RESOLVED outbreak is much stronger co-location evidence than sharing a
coordinate only with an UNRESOLVED (`REVIEW_MEDIUM`/`REVIEW_LOW`)
candidate that hasn't even been confirmed as its own real, distinct
outbreak yet. This module keeps those two situations in separate labels
(`SHARED_WITH_RESOLVED` vs. `SHARED_WITH_UNRESOLVED`) rather than
collapsing them — the Sri Lanka Chavakachcheri case is the concrete
example: the `AUTO_MERGED_HIGH` WAHIS canonical outbreak shares its
coordinate only with the excluded `REVIEW_LOW` CSV conflict record, so it
is labeled `SHARED_WITH_UNRESOLVED`, never definitively "non-independent"
— the ambiguity is preserved for manual review, not force-merged and not
silently ignored (see COORD-03).

**Never upgrades GPS quality (Part 4).** A unique APPROXIMATE/COARSE
coordinate means only "no other retained row shares this exact stored
coordinate" — it is never read as "precisely located independent
outbreak." `gps_quality` is always carried through unmodified.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..domain.enums import CoordinateCollisionStatus
from ..schemas import DEDUP_RESOLVED_STATUSES, GpsQuality


@dataclass
class CoordinateCollisionRow:
    source_record_id: str
    latitude: float | None
    longitude: float | None
    gps_quality: str
    dedup_status: str
    coordinate_collision_status: str
    shared_coordinate_group_id: str | None
    resolved_shared_count: int
    unresolved_shared_count: int
    reason: str

    def as_dict(self) -> dict:
        return {
            "source_record_id": self.source_record_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "gps_quality": self.gps_quality,
            "dedup_status": self.dedup_status,
            "coordinate_collision_status": self.coordinate_collision_status,
            "shared_coordinate_group_id": self.shared_coordinate_group_id,
            "resolved_shared_count": self.resolved_shared_count,
            "unresolved_shared_count": self.unresolved_shared_count,
            "reason": self.reason,
        }


def _is_resolved(dedup_status: str) -> bool:
    return dedup_status in DEDUP_RESOLVED_STATUSES


def compute_coordinate_collision_status(conservative_rows: list[dict]) -> list[CoordinateCollisionRow]:
    """`conservative_rows` are dict rows as produced by
    `data_processing.build_canonical.build_conservative_rows` (or read
    back from `canonical_outbreaks_conservative.csv`) — one row per
    canonical outbreak identity. An `AUTO_MERGED_HIGH` group is already
    represented by exactly ONE row here (Checkpoint 2.5), so its own raw
    pre-dedup members never count against it (COORD-01) — there is
    structurally nothing left to compare it against itself.
    """
    coord_groups: dict[tuple[float, float], list[int]] = defaultdict(list)
    for idx, row in enumerate(conservative_rows):
        lat, lon = row.get("latitude"), row.get("longitude")
        if lat in (None, "") or lon in (None, ""):
            continue
        key = (round(float(lat), 6), round(float(lon), 6))
        coord_groups[key].append(idx)

    group_id_by_coord: dict[tuple[float, float], str] = {
        coord: f"COORDGRP:{i:05d}" for i, coord in enumerate(sorted(coord_groups.keys()), start=1)
    }

    results: list[CoordinateCollisionRow] = []
    for idx, row in enumerate(conservative_rows):
        lat, lon = row.get("latitude"), row.get("longitude")
        gps_quality = row.get("gps_quality") or GpsQuality.UNKNOWN.value
        dedup_status = row.get("dedup_status") or ""

        if lat in (None, "") or lon in (None, ""):
            results.append(
                CoordinateCollisionRow(
                    source_record_id=row["source_record_id"],
                    latitude=None,
                    longitude=None,
                    gps_quality=gps_quality,
                    dedup_status=dedup_status,
                    coordinate_collision_status=CoordinateCollisionStatus.MISSING_COORDINATE.value,
                    shared_coordinate_group_id=None,
                    resolved_shared_count=0,
                    unresolved_shared_count=0,
                    reason="missing coordinates — collision status cannot be assessed",
                )
            )
            continue

        key = (round(float(lat), 6), round(float(lon), 6))
        group_id = group_id_by_coord[key]
        other_indices = [i for i in coord_groups[key] if i != idx]

        resolved_others = sum(1 for i in other_indices if _is_resolved(conservative_rows[i].get("dedup_status") or ""))
        unresolved_others = len(other_indices) - resolved_others

        if resolved_others > 0 and unresolved_others > 0:
            status = CoordinateCollisionStatus.SHARED_WITH_BOTH.value
            reason = (
                f"coordinate shared with {resolved_others} resolved and {unresolved_others} "
                "unresolved other canonical row(s)"
            )
        elif resolved_others > 0:
            status = CoordinateCollisionStatus.SHARED_WITH_RESOLVED.value
            reason = f"coordinate shared with {resolved_others} other RESOLVED canonical outbreak(s)"
        elif unresolved_others > 0:
            status = CoordinateCollisionStatus.SHARED_WITH_UNRESOLVED.value
            reason = (
                f"coordinate shared only with {unresolved_others} UNRESOLVED (REVIEW_MEDIUM/LOW) "
                "candidate(s) — ambiguous, not treated as definitive non-independence"
            )
        else:
            status = CoordinateCollisionStatus.UNIQUE_AMONG_RESOLVED.value
            reason = "unique coordinate — no other resolved or unresolved canonical row shares it"

        if gps_quality in (GpsQuality.APPROXIMATE.value, GpsQuality.COARSE.value):
            reason += (
                f" — CAUTION: coordinate precision is {gps_quality}; this reflects stored-coordinate "
                "co-location only, never upgraded to a precise/exact independent-location claim"
            )

        results.append(
            CoordinateCollisionRow(
                source_record_id=row["source_record_id"],
                latitude=float(lat),
                longitude=float(lon),
                gps_quality=gps_quality,
                dedup_status=dedup_status,
                coordinate_collision_status=status,
                shared_coordinate_group_id=group_id,
                resolved_shared_count=resolved_others,
                unresolved_shared_count=unresolved_others,
                reason=reason,
            )
        )

    return results


def load_conservative_rows(path: str | Path) -> list[dict]:
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_coordinate_collision_report(conservative_csv_path: str | Path) -> list[dict]:
    rows = load_conservative_rows(conservative_csv_path)
    return [r.as_dict() for r in compute_coordinate_collision_status(rows)]
