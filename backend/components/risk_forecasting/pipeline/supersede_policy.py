"""
Which existing forecast records may be marked SUPERSEDED when a new forecast run is stored.

Pure policy (no database access) so it can be reviewed and tested in isolation. Rules, in
order of precedence for each existing record in the target period:

1. Records reused by the new run (same idempotency key) are kept as they are.
2. Already SUPERSEDED records are left alone.
3. Records that people have already worked with are PROTECTED and never superseded:
   status AVAILABLE or REFERENCED, or any linked advisory or follow-up (any status).
4. If the dependency check failed or is unavailable, the record is PROTECTED
   (fail closed): nothing is superseded on a guess.
5. Everything else may be superseded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

WORKFLOW_STATUSES = {"AVAILABLE", "REFERENCED"}

REASON_WORKFLOW_STATUS = "WORKFLOW_STATUS"
REASON_HAS_ADVISORY = "HAS_ADVISORY"
REASON_HAS_FOLLOW_UP = "HAS_FOLLOW_UP"
REASON_DEPENDENCY_UNKNOWN = "DEPENDENCY_CHECK_UNAVAILABLE"


@dataclass
class SupersedePlan:
    to_supersede: List[str] = field(default_factory=list)
    protected: List[Dict[str, object]] = field(default_factory=list)
    kept: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, object]:
        reasons: Dict[str, int] = {}
        for item in self.protected:
            for reason in item["reasons"]:
                reasons[reason] = reasons.get(reason, 0) + 1
        return {
            "would_supersede": len(self.to_supersede),
            "protected": len(self.protected),
            "protected_reasons": reasons,
            "reused": len(self.kept),
        }


def plan_supersede(
    existing: Iterable[object],
    new_idempotency_keys: Iterable[str],
    dependents: Mapping[str, Optional[Mapping[str, int]]],
) -> SupersedePlan:
    """`existing`: records with forecast_id, status, idempotency_key.
    `dependents`: forecast_id -> {"advisories": n, "follow_ups": n}, or None when unknown."""
    new_keys = set(new_idempotency_keys)
    plan = SupersedePlan()
    for record in existing:
        fid = record.forecast_id
        if getattr(record, "idempotency_key", None) in new_keys:
            plan.kept.append(fid)
            continue
        if record.status == "SUPERSEDED":
            continue
        reasons: List[str] = []
        if record.status in WORKFLOW_STATUSES:
            reasons.append(REASON_WORKFLOW_STATUS)
        counts = dependents.get(fid)
        if counts is None:
            reasons.append(REASON_DEPENDENCY_UNKNOWN)
        else:
            if counts.get("advisories", 0) > 0:
                reasons.append(REASON_HAS_ADVISORY)
            if counts.get("follow_ups", 0) > 0:
                reasons.append(REASON_HAS_FOLLOW_UP)
        if reasons:
            plan.protected.append({"forecast_id": fid, "reasons": reasons})
        else:
            plan.to_supersede.append(fid)
    return plan
