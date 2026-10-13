"""GEO-LIVE-05 event domain: the Geospatial-owned "a verified clinical case
changed" event contract, separate from `operational_models.py`'s snapshot
DTOs (`OperationalGeospatialContext`, `VerifiedClinicalContext`).

An event here represents a CHANGE notification only -- it exists to tell an
authorized vet's browser "go refetch the authoritative operational-context
snapshot", never to carry enough state to replace that refetch (Section 9:
"invalidate/refetch the authoritative operational contracts", never mutate
scientific frontend state directly from the event body alone).

`ClinicalSemanticClass.VERIFIED_CLINICAL_CONTEXT` (operational_enums.py) is
reused as the only semantic class an event may carry -- there is
deliberately no "CONFIRMED_OUTBREAK" event type, matching the same firewall
`clinical_context.py`/`operational_router_factory.py` already enforce for
the snapshot DTO.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum

from .operational_models import HostDiagnosticCase


class OperationalEventType(str, Enum):
    """The only two event types this boundary emits. Never
    "CONFIRMED_OUTBREAK_CREATED" or any scientific/model event type -- a
    future scientific model rerun is a structurally different concept
    (`MODEL_RUN_AVAILABLE`, Section 14), not implemented by this module."""

    VERIFIED_CLINICAL_CONTEXT_CREATED = "VERIFIED_CLINICAL_CONTEXT_CREATED"
    VERIFIED_CLINICAL_CONTEXT_UPDATED = "VERIFIED_CLINICAL_CONTEXT_UPDATED"


class CaseChangeKind(str, Enum):
    """What a raw upstream case-change source (Mongo change stream op type,
    or a delta-poll diff) observed. Mapped 1:1 to `OperationalEventType` by
    `services/operational/event_normalization.py` -- kept as a separate
    enum because a raw change is not yet authorized/validated (mirrors the
    `HostDiagnosticCase` vs `VerifiedClinicalContext` split)."""

    CREATED = "CREATED"
    UPDATED = "UPDATED"


@dataclass(frozen=True)
class RawCaseChange:
    """One raw, not-yet-authorized case change as a `CaseEventSource`
    observed it. `case` is a plain `HostDiagnosticCase` (Section 2's
    existing raw record) -- this module never invents a richer raw shape."""

    case: HostDiagnosticCase
    change_kind: CaseChangeKind


@dataclass(frozen=True)
class VerifiedClinicalEvent:
    """Section 5's minimum event information. Deliberately excludes farmer
    PII, images, and LLM reasoning (Section 5 explicit prohibition) -- it
    carries exactly the same neutral fields as `VerifiedClinicalContext`
    plus event-envelope metadata. `semantic_class` is always
    `"VERIFIED_CLINICAL_CONTEXT"` -- never `"CONFIRMED_OUTBREAK"` (Section 5).
    """

    event_id: str
    """Deterministic dedup key: `f"vcc:{case_id}:{verification_time}"` --
    the SAME case re-observed with the SAME verification timestamp always
    produces the SAME event_id, so a source re-broadcasting an unchanged
    case (e.g. an unrelated field touched by an Mongo update) naturally
    collapses to one logical event on both delivery attempts."""

    event_type: str  # OperationalEventType value
    case_id: str
    farm_id: str
    disease: str  # OperationalDisease value: "LSD" | "FMD"
    verified_at: str
    event_generated_at: str
    semantic_class: str = "VERIFIED_CLINICAL_CONTEXT"
    sequence: int | None = None
    deep_link_context: dict = field(default_factory=dict)
    """Section 12: identifies the relevant Geospatial clinical CASE, never
    an `outbreak`/historical-origin id -- see
    `services/operational/event_normalization.py::build_deep_link_context`.
    """

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}
