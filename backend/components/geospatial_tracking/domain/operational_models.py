"""GEO-INT-01 domain objects for the Geospatial-owned operational-context
boundary (see `operational_enums.py` module docstring for why this is kept
separate from the Checkpoint 3 live-scientific domain).

Three families of object, deliberately never conflated:

1. Host-supplied RAW records (`HostFarmRecord`, `HostDiagnosticCase`) —
   exactly what `repositories/operational_port.py::OperationalDataPort`
   returns. Not yet validated/authorized against anything; a
   not-yet-trusted shape crossing the boundary from whatever concrete
   adapter a later checkpoint wires up (Section 6/17 — no such adapter is
   built or connected here).
2. Geospatial-NORMALIZED records (`OperationalFarm`,
   `VerifiedClinicalContext`) — the minimal, GPS-validated,
   authorization-checked, semantically-neutral shapes
   `services/operational/*` builds from the raw ones. Only these may
   appear in the final response DTO.
3. `AuthenticatedVetContext` — trusted identity handed IN by the host
   application (Section 6/7). This boundary never constructs one itself:
   no JWT parsing, no password/token logic lives here.

Nothing here invents a value the host/raw record did not provide (mirrors
`domain/models.py`'s rule) — a missing/invalid field always resolves to an
explicit status (`LocationStatus.LOCATION_REQUIRED`,
`OperationalStatus.NO_VERIFIED_CLINICAL_CONTEXT`, etc.), never a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields

from .operational_enums import ClinicalSemanticClass, LocationStatus, OperationalStatus, TimestampBasis


@dataclass(frozen=True)
class AuthenticatedVetContext:
    """Trusted caller identity, supplied by the host application boundary
    (Section 6) — never constructed from a raw JWT/header here. Mirrors the
    upstream contract verified read-only from
    `origin/main:backend/components/health_anomaly/router.py`: token
    `sub` -> `email`, `role == "vet"` only for veterinarian accounts.
    """

    email: str
    role: str

    def is_vet(self) -> bool:
        """Section 7: the ONLY authorization check this boundary performs.
        Never based on a client-supplied vet_id/role — `role` here must
        already come from a verified token payload, not request input."""
        return self.role == "vet"


@dataclass(frozen=True)
class HostFarmRecord:
    """Raw per-farm record as the host application boundary supplies it,
    already scoped to one authenticated vet's assignment (mirrors
    `GET /vet/my-farms`'s own per-vet scoping, verified read-only). The
    host adapter is responsible for never putting farmer PII (owner name,
    email, phone) on this record in the first place — Section 8's minimal
    field list is enforced again downstream by `OperationalFarm`, but is
    not this dataclass's job alone to guarantee."""

    farm_id: str
    latitude: float | None = None
    longitude: float | None = None
    location_district: str | None = None
    total_animals: int | None = None


@dataclass(frozen=True)
class HostDiagnosticCase:
    """Raw per-case record as the host application boundary supplies it —
    field names/semantics verified read-only against
    `origin/main:backend/components/health_anomaly/{router,schemas}.py`
    (`DiagnosticCaseResponse`). Deliberately carries only the fields the
    Section 11 filter needs; it does NOT carry `cattle_id`,
    `animal_identifier`, images, LLM reasoning, or any cattle/health-alert
    field — a farm's or animal's health status alone is never eligible to
    become a `VerifiedClinicalContext` (Section 13), so there is nothing
    here it could be built from even by mistake."""

    case_id: str
    farm_id: str | None
    disease_name: str | None
    verified: bool
    created_at: str | None = None
    verified_at: str | None = None


@dataclass(frozen=True)
class OperationalFarm:
    """Section 8 minimal operational farm DTO. Deliberately excludes
    owner_name/email/phone/registration_number — those exist on the
    upstream `FarmSummaryResponse` (verified read-only) but are never
    needed by, or copied into, this boundary.

    GEO29A: `personally_assigned` distinguishes a farm the vet
    administers directly (any of the four `assigned_*` relationships)
    from one that only qualifies through district-wide surveillance
    (Phase 5's privacy firewall) — `True` for every existing caller
    (the assigned-farm path never set this explicitly before this field
    existed), so no prior behavior changes."""

    farm_id: str
    latitude: float | None
    longitude: float | None
    location_status: str  # LocationStatus value
    location_district: str | None = None
    total_animals: int | None = None
    personally_assigned: bool = True


@dataclass(frozen=True)
class VerifiedClinicalContext:
    """Section 12/13/15 neutral clinical-evidence record. `semantic_class`
    is always `ClinicalSemanticClass.VERIFIED_CLINICAL_CONTEXT` — see that
    enum's docstring for why "outbreak" is never a legal value here.
    """

    case_id: str
    farm_id: str
    disease: str  # OperationalDisease value: "LSD" | "FMD"
    semantic_class: str = ClinicalSemanticClass.VERIFIED_CLINICAL_CONTEXT.value
    verification_time: str | None = None
    timestamp_basis: str = TimestampBasis.VERIFICATION_TIME.value
    case_creation_time: str | None = None
    """TimestampBasis.CASE_CREATION_TIME — never read as onset/observation
    time (Section 14)."""


@dataclass(frozen=True)
class VetContextSummary:
    """The only vet-identifying information exposed on the public response
    DTO (Section 15 "Vet: role, optionally non-PII identifier ... only if
    needed"). This checkpoint keeps it to `role` only — no email, no
    internal vet id — since nothing built here needs more than that."""

    role: str


@dataclass(frozen=True)
class OperationalGeospatialContext:
    """Section 15 top-level response DTO. `status` (not in the section's
    example sketch, but required by Section 19's explicit error/empty
    states) always reflects the least-available data — see
    `services/operational/context_service.py` for exactly which state maps
    to which value.

    GEO29A Phase 6: `vet_district`/`surveillance_farms`/
    `surveillance_contexts` are ADDITIVE fields for the Page-1 registered-
    district surveillance concept (Phase 4) — deliberately separate from
    `farms`/`clinical_contexts`, which keep their original
    personally-assigned-only meaning unchanged so no existing client/test
    is affected by their presence. `surveillance_farms`/
    `surveillance_contexts` are the BROADER set (every farm/case in the
    vet's registered district, which may overlap with `farms`/
    `clinical_contexts` but is never a subset of them).
    """

    status: str  # OperationalStatus value
    vet: VetContextSummary | None
    farms: list[OperationalFarm] = field(default_factory=list)
    clinical_contexts: list[VerifiedClinicalContext] = field(default_factory=list)
    generated_at: str | None = None
    vet_district: str | None = None
    surveillance_farms: list[OperationalFarm] = field(default_factory=list)
    surveillance_contexts: list[VerifiedClinicalContext] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def unauthorized_context(generated_at: str) -> OperationalGeospatialContext:
    return OperationalGeospatialContext(
        status=OperationalStatus.UNAUTHORIZED.value, vet=None, generated_at=generated_at
    )


def non_vet_forbidden_context(vet: AuthenticatedVetContext, generated_at: str) -> OperationalGeospatialContext:
    return OperationalGeospatialContext(
        status=OperationalStatus.NON_VET_FORBIDDEN.value,
        vet=VetContextSummary(role=vet.role),
        generated_at=generated_at,
    )
