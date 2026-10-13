"""GEO-INT-01 operational data boundary: scientific/service code depends on
this Protocol, never on Mongo/JWT directly — mirrors `base.py`'s
`OutbreakRepository` split exactly:

    OperationalDataPort (this Protocol)
            |
            +-- (no concrete implementation yet, by design)   NOW
            |
            +-- a host-application-backed adapter               LATER
                (reads the existing `vets`/`farms`/
                `diagnostic_cases` Mongo collections via the
                shared app's own `core.database`/`core.security` —
                verified read-only this checkpoint, never imported
                or duplicated here; see Section 2/6/17)

No concrete adapter is constructed or connected in this checkpoint
(Section 17/18) — building one requires the host application's own
JWT/Mongo wiring, which this branch intentionally does not contain
(Section 6). Tests use an in-memory fake (`tests/_operational_fakes.py`),
never a real database.

GEO-INT-02 update: both methods are declared `async`. The host's real
collections are Motor's `AsyncIOMotorCollection`, which has no synchronous
API at all (`await collection.find_one(...)`, `async for doc in
collection.find(...)`) — see
`repositories/host_operational_adapter.py::MongoOperationalDataPort`, the
first concrete implementation of this Protocol. This is a calling-
convention change only, made because GEO-INT-01 deliberately deferred
building any concrete adapter and so could not have anticipated it; it
changes no filtering/authorization/semantic behavior (Section 18) —
`services/operational/context_service.py::OperationalContextService` is
updated the same way, `await`-ing these calls instead of calling them
synchronously.
"""

from __future__ import annotations

from typing import Protocol

from ..domain.operational_models import AuthenticatedVetContext, HostDiagnosticCase, HostFarmRecord


class OperationalDataPort(Protocol):
    """Storage-agnostic read boundary. Both methods take the already
    host-authenticated vet context and are expected to return data already
    scoped to that vet (mirroring `GET /vet/my-farms`'s own per-vet
    scoping) — but `services/operational/context_service.py` never trusts
    that scoping alone: it re-checks farm assignment itself before any
    case can qualify as a `VerifiedClinicalContext` (Section 11, defense
    in depth against an adapter that scopes cases less strictly than
    `/vet/my-farms` scopes farms — see `GET /vet/cases`'s upstream
    contract, which today applies no vet-scoping at all).

    Filtering here is a plain data fetch — no authorization decision, no
    GPS validation, no disease classification belongs on this Protocol or
    its implementations; that logic lives entirely in
    `services/operational/*` (Section 5/6), which depends on this Protocol
    rather than any concrete backend.
    """

    async def get_assigned_farms(self, vet: AuthenticatedVetContext) -> list[HostFarmRecord]: ...

    async def get_verified_clinical_cases(self, vet: AuthenticatedVetContext) -> list[HostDiagnosticCase]: ...

    # GEO29A Phase 4/6: the registered-district surveillance path --
    # deliberately TWO separate methods (mirroring the pair above) rather
    # than folding district resolution into `get_assigned_farms`, so a
    # vet's personally-assigned farms and their registered-district
    # surveillance scope stay two independently callable, independently
    # testable concepts, never merged into one query.
    async def get_vet_district(self, vet: AuthenticatedVetContext) -> str | None: ...

    async def get_district_surveillance_farms(self, vet: AuthenticatedVetContext, district: str) -> list[HostFarmRecord]: ...

    async def get_verified_clinical_cases_for_farm_ids(self, farm_ids: list[str]) -> list[HostDiagnosticCase]: ...
