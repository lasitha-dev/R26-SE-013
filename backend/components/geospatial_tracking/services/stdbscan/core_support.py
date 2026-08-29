"""Checkpoint 6B Parts 9-11: support identity and the approximate-GPS
core-density guard.

**Critical problem this module exists to prevent (Part 10)**: real
reports can contain multiple genuinely DISTINCT outbreaks that all share
one placeholder/approximate coordinate (a village-level or district-level
GPS stand-in, not each outbreak's own precise location). Three such
records plus `min_core_supports=3` must NEVER automatically become a
dense CORE cluster merely because the source happened to use the same
approximate point — that would be manufacturing density out of GPS
imprecision, not genuine spatiotemporal clustering. This module NEVER
deletes or merges those records (they remain fully distinct for
provenance, display, cluster membership, and later sensitivity
analysis) — it only controls how many CORE-DENSITY supports they may
jointly contribute.

**This is a density-contribution control, not a statistical-independence
claim** — a shared `core_support_id` says nothing about whether the
underlying outbreaks are epidemiologically related.

Two policies (`config.GpsCorePolicy`):

- `PRIMARY_CORE_SUPPORT` (Part 10): `EXACT` and `UNKNOWN`-precision
  records each get their OWN unique support id (one resolved outbreak =
  one support). `APPROXIMATE`/`COARSE` records sharing the same rounded
  coordinate collapse to AT MOST ONE shared support id for that
  location.
- `EXACT_ONLY_CORE_SUPPORT` (Part 11, stricter sensitivity mode): ONLY
  `EXACT` records ever receive a support id (`core_support_id=None` for
  everything else) — `APPROXIMATE`/`COARSE`/`UNKNOWN` records may still
  be BORDER/NOISE/context records downstream, they simply can never
  themselves make a point CORE.

Neither policy is chosen using held-out prediction performance — both
are reported side-by-side for development sensitivity (`STDBSCAN_PROTOCOL.md`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ...schemas import GpsQuality
from ..source_selector import EligibleSource
from .config import GpsCorePolicy

_EXACT = GpsQuality.EXACT.value
_APPROXIMATE = GpsQuality.APPROXIMATE.value
_COARSE = GpsQuality.COARSE.value
_UNKNOWN = GpsQuality.UNKNOWN.value

# Matches `coordinate_collision.py`'s own rounding convention — the same
# notion of "shares a documented coordinate" used there.
_COORD_ROUND_DECIMALS = 6


def _coordinate_key(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat, _COORD_ROUND_DECIMALS), round(lon, _COORD_ROUND_DECIMALS))


@dataclass
class CoreSupportAssignment:
    source_id: str
    gps_quality: str  # NEVER rewritten from the source's own real value (ST-15)
    core_support_id: str | None  # None => this source can never itself be CORE
    support_group_source_ids: list[str]  # every source sharing this support id (transparency)

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "gps_quality": self.gps_quality,
            "core_support_id": self.core_support_id,
            "support_group_source_ids": self.support_group_source_ids,
        }


def compute_core_support_assignments(
    sources: list[EligibleSource], *, gps_core_policy: str
) -> dict[str, CoreSupportAssignment]:
    """Deterministic — grouping keys off real coordinates/source ids
    only, never input order. See module docstring for the two policies."""
    approx_groups: dict[tuple[float, float], list[EligibleSource]] = {}
    for s in sources:
        if s.gps_quality in (_APPROXIMATE, _COARSE):
            approx_groups.setdefault(_coordinate_key(s.latitude, s.longitude), []).append(s)

    strict = gps_core_policy == GpsCorePolicy.EXACT_ONLY_CORE_SUPPORT.value

    assignments: dict[str, CoreSupportAssignment] = {}
    for s in sorted(sources, key=lambda x: x.source_id):
        if s.gps_quality == _EXACT:
            support_id = f"SUPPORT:EXACT:{s.source_id}"
            group_ids = [s.source_id]
        elif s.gps_quality == _UNKNOWN:
            if strict:
                support_id = None
                group_ids = [s.source_id]
            else:
                support_id = f"SUPPORT:UNKNOWN:{s.source_id}"
                group_ids = [s.source_id]
        else:  # APPROXIMATE / COARSE
            if strict:
                support_id = None
                group_ids = [s.source_id]
            else:
                key = _coordinate_key(s.latitude, s.longitude)
                group = sorted(approx_groups[key], key=lambda x: x.source_id)
                group_ids = [g.source_id for g in group]
                # deterministic shared id derived from the group's own
                # sorted membership -- never from input order, never random
                fingerprint = hashlib.sha256(",".join(group_ids).encode("utf-8")).hexdigest()[:16]
                support_id = f"SUPPORT:APPROXCOLLAPSE:{fingerprint}"

        assignments[s.source_id] = CoreSupportAssignment(
            source_id=s.source_id,
            gps_quality=s.gps_quality,
            core_support_id=support_id,
            support_group_source_ids=group_ids,
        )
    return assignments
