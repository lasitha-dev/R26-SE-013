"""GEO-LIVE-05 Section 5/7: the ONE place a raw `RawCaseChange` is allowed
to become a `VerifiedClinicalEvent`. Reuses `clinical_context.py`'s exact
gate order (Section 11 of GEO-INT-01, unchanged) via
`build_verified_clinical_context` rather than re-implementing a second
verified/farm/GPS/disease/timestamp check -- a case failing any one of
those gates silently yields no event here either (never repaired, never
included with a caveat)."""

from __future__ import annotations

from datetime import datetime, timezone

from ...domain.operational_events import CaseChangeKind, OperationalEventType, RawCaseChange, VerifiedClinicalEvent
from ...domain.operational_models import OperationalFarm
from .clinical_context import build_verified_clinical_context

_EVENT_TYPE_BY_CHANGE_KIND = {
    CaseChangeKind.CREATED: OperationalEventType.VERIFIED_CLINICAL_CONTEXT_CREATED,
    CaseChangeKind.UPDATED: OperationalEventType.VERIFIED_CLINICAL_CONTEXT_UPDATED,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_deep_link_context(case_id: str, farm_id: str, disease: str) -> dict:
    """Section 12: identifies the CLINICAL CASE only -- `target` is a
    Geospatial Cases-context selector, never `selectedOutbreakId`/an
    origin id. The frontend deep-link handler (Section 12) is expected to
    call its own "select operational clinical case" action with this
    `case_id`, exactly the same as `OutbreakMapPage.jsx`'s existing
    `handleSelectOperationalCase`/`operationalPopupCase` path -- never
    `ctx.selectOutbreak`."""
    return {"target": "geospatial_clinical_case", "case_id": case_id, "farm_id": farm_id, "disease": disease}


def normalize_case_event(
    raw_change: RawCaseChange,
    *,
    assigned_farms_by_id: dict[str, OperationalFarm],
) -> VerifiedClinicalEvent | None:
    """Returns a `VerifiedClinicalEvent` for `raw_change`, or `None` if the
    underlying case does not qualify as a `VerifiedClinicalContext`
    (unverified, unassigned/invalid-GPS farm, unsupported disease, or
    missing verification timestamp -- Section 15's required-test list)."""
    clinical_context = build_verified_clinical_context(raw_change.case, assigned_farms_by_id=assigned_farms_by_id)
    if clinical_context is None:
        return None

    event_type = _EVENT_TYPE_BY_CHANGE_KIND[raw_change.change_kind]
    verification_time = clinical_context.verification_time  # gated non-None/non-blank by build_verified_clinical_context

    return VerifiedClinicalEvent(
        event_id=f"vcc:{clinical_context.case_id}:{verification_time}",
        event_type=event_type.value,
        case_id=clinical_context.case_id,
        farm_id=clinical_context.farm_id,
        disease=clinical_context.disease,
        verified_at=verification_time,
        event_generated_at=_now_iso(),
        deep_link_context=build_deep_link_context(clinical_context.case_id, clinical_context.farm_id, clinical_context.disease),
    )
