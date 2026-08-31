"""GEO-INT-01 Section 17: the operational-context service — the single
orchestrator that turns (`AuthenticatedVetContext`, `OperationalDataPort`)
into one `OperationalGeospatialContext`. This is the ONLY place Section
7/11's gates are assembled end-to-end; each individual gate's logic lives
in `farm_normalization.py` / `clinical_context.py` / `disease_normalization.py`.

No Mongo/JWT/HTTP concern belongs here (Section 6/17) — `OperationalDataPort`
is injected, never constructed. No exception from the port ever reaches a
caller of this service (Section 19: "No raw upstream/database exceptions
in public DTOs") — it is caught and mapped to
`OperationalStatus.OPERATIONAL_DATA_UNAVAILABLE`.

GEO-INT-02 update: `get_operational_context` is now `async` and `await`s
the port's (now-`async`) methods — see
`repositories/operational_port.py`'s module docstring for why. No gate,
filter, or status mapping below changed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ...domain.operational_enums import OperationalStatus
from ...domain.operational_models import (
    AuthenticatedVetContext,
    OperationalGeospatialContext,
    VetContextSummary,
    non_vet_forbidden_context,
    unauthorized_context,
)
from ...repositories.operational_port import OperationalDataPort
from .clinical_context import build_verified_clinical_context
from .farm_normalization import normalize_assigned_farm


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationalContextService:
    """Depends on `OperationalDataPort` (Protocol) only — never a concrete
    Mongo/JWT implementation (Section 6/17)."""

    def __init__(self, port: OperationalDataPort) -> None:
        self._port = port

    async def get_operational_context(
        self, vet: AuthenticatedVetContext | None
    ) -> OperationalGeospatialContext:
        generated_at = _now_iso()

        if vet is None:
            return unauthorized_context(generated_at)
        if not vet.is_vet():
            return non_vet_forbidden_context(vet, generated_at)

        vet_summary = VetContextSummary(role=vet.role)

        try:
            raw_farms = await self._port.get_assigned_farms(vet)
        except Exception:
            return OperationalGeospatialContext(
                status=OperationalStatus.OPERATIONAL_DATA_UNAVAILABLE.value,
                vet=vet_summary,
                generated_at=generated_at,
            )

        # Deterministic ordering (Section 20) — stable key, never insertion/host order.
        farms = sorted((normalize_assigned_farm(raw) for raw in raw_farms), key=lambda f: f.farm_id)
        assigned_farm_ids = {farm.farm_id for farm in farms}

        # GEO29A Phase 4/6: registered-district surveillance is resolved
        # ADDITIVELY and independently of the assigned-farm scope above —
        # a vet with ZERO assigned farms may still have a real registered
        # district worth surveilling (Phase 4's whole point). Any failure
        # here degrades to an empty surveillance scope, never disturbing
        # the assigned-farm `status`/`farms`/`clinical_contexts` fields
        # this method already computes exactly as before.
        vet_district, surveillance_farms, surveillance_contexts = await self._resolve_surveillance(
            vet, assigned_farm_ids
        )

        if not farms:
            return OperationalGeospatialContext(
                status=OperationalStatus.NO_ASSIGNED_FARMS.value,
                vet=vet_summary,
                generated_at=generated_at,
                vet_district=vet_district,
                surveillance_farms=surveillance_farms,
                surveillance_contexts=surveillance_contexts,
            )

        farms_by_id = {farm.farm_id: farm for farm in farms}

        try:
            raw_cases = await self._port.get_verified_clinical_cases(vet)
        except Exception:
            return OperationalGeospatialContext(
                status=OperationalStatus.OPERATIONAL_DATA_UNAVAILABLE.value,
                vet=vet_summary,
                farms=farms,
                generated_at=generated_at,
                vet_district=vet_district,
                surveillance_farms=surveillance_farms,
                surveillance_contexts=surveillance_contexts,
            )

        clinical_contexts = [
            ctx
            for ctx in (
                build_verified_clinical_context(case, assigned_farms_by_id=farms_by_id) for case in raw_cases
            )
            if ctx is not None
        ]
        clinical_contexts.sort(key=lambda ctx: ctx.case_id)  # Section 20 determinism

        status = (
            OperationalStatus.OK.value
            if clinical_contexts
            else OperationalStatus.NO_VERIFIED_CLINICAL_CONTEXT.value
        )

        return OperationalGeospatialContext(
            status=status,
            vet=vet_summary,
            farms=farms,
            clinical_contexts=clinical_contexts,
            generated_at=generated_at,
            vet_district=vet_district,
            surveillance_farms=surveillance_farms,
            surveillance_contexts=surveillance_contexts,
        )

    async def _resolve_surveillance(
        self, vet: AuthenticatedVetContext, assigned_farm_ids: set[str]
    ) -> tuple[str | None, list, list]:
        """GEO29A Phase 4/6: builds the registered-district surveillance
        scope. Returns `(vet_district, surveillance_farms,
        surveillance_contexts)` -- all three default to
        `(None, [], [])` on ANY failure (no district on file, port
        exception, etc.), since surveillance is a strictly additive
        enhancement that must never turn a working assigned-farm response
        into an error."""
        try:
            vet_district = await self._port.get_vet_district(vet)
            if not vet_district:
                return None, [], []

            raw_district_farms = await self._port.get_district_surveillance_farms(vet, vet_district)
            surveillance_farms = sorted(
                (
                    normalize_assigned_farm(raw, personally_assigned=raw.farm_id in assigned_farm_ids)
                    for raw in raw_district_farms
                ),
                key=lambda f: f.farm_id,
            )
            if not surveillance_farms:
                return vet_district, [], []

            surveillance_farms_by_id = {farm.farm_id: farm for farm in surveillance_farms}
            district_farm_ids = list(surveillance_farms_by_id.keys())
            raw_district_cases = await self._port.get_verified_clinical_cases_for_farm_ids(district_farm_ids)
            surveillance_contexts = [
                ctx
                for ctx in (
                    build_verified_clinical_context(case, assigned_farms_by_id=surveillance_farms_by_id)
                    for case in raw_district_cases
                )
                if ctx is not None
            ]
            surveillance_contexts.sort(key=lambda ctx: ctx.case_id)
            return vet_district, surveillance_farms, surveillance_contexts
        except Exception:
            return None, [], []
