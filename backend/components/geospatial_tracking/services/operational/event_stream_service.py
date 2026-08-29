"""GEO-LIVE-05 Section 6/7: the single orchestrator turning
(`AuthenticatedVetContext`, `OperationalDataPort`, `CaseEventSource`) into
one authorized, deduplicated `VerifiedClinicalEvent` stream for exactly one
vet connection. Mirrors `context_service.py`'s "one orchestrator, gates
delegated to smaller modules" shape.

Authorization (Section 6): a raw change is only ever considered for a vet
if its `farm_id` is in that vet's OWN assigned-farm set, resolved the exact
same way `OperationalContextService`/`MongoOperationalDataPort` already
resolve it (via the injected `OperationalDataPort`) -- never a client-
supplied vet_id/farm_id, never another vet's farms. This is the one place
that guarantees "Vet A cannot receive Vet B's farm event."
"""

from __future__ import annotations

import time
from typing import AsyncIterator

from ...domain.operational_events import CaseChangeKind, RawCaseChange, VerifiedClinicalEvent
from ...domain.operational_models import AuthenticatedVetContext, HostDiagnosticCase, OperationalFarm
from ...repositories.case_event_port import CaseEventSource
from ...repositories.operational_port import OperationalDataPort
from .event_dedup import SeenEventTracker
from .event_normalization import normalize_case_event
from .farm_normalization import normalize_assigned_farm

_ASSIGNED_FARM_CACHE_TTL_SECONDS = 30.0
"""Section 6: how long a resolved assigned-farm set is trusted before
re-checking with the host port. A live connection re-resolves periodically
rather than once at connect time, so a farm assignment revoked mid-
connection stops being authorized within one TTL window, not only on the
next reconnect."""


class OperationalEventStreamService:
    """One instance may be shared across many vets/connections (it holds no
    per-vet state itself beyond the small in-memory reconciliation map
    below) -- depends on `OperationalDataPort`/`CaseEventSource` (Protocols)
    only, never a concrete Mongo/JWT implementation (Section 6/7)."""

    def __init__(self, port: OperationalDataPort, source: CaseEventSource, *, clock=time.monotonic) -> None:
        self._port = port
        self._source = source
        self._clock = clock
        # Section 15 "reconnect/missed-event reconciliation": what this
        # service has already delivered to each vet (by email), in THIS
        # PROCESS's lifetime only -- in-memory, resets on restart. Never
        # written to scientific/persistent storage (Section 14).
        self._delivered_by_vet: dict[str, dict[str, str]] = {}

    def transport_mode(self) -> str:
        return self._source.describe_transport()

    async def _resolve_assigned_farms(self, vet: AuthenticatedVetContext) -> dict[str, OperationalFarm]:
        raw_farms = await self._port.get_assigned_farms(vet)
        return {farm.farm_id: normalize_assigned_farm(farm) for farm in raw_farms}

    def _reconciliation_changes(self, vet_email: str, assigned_farm_ids: set[str]) -> list[RawCaseChange]:
        """Section 15: diff this vet's own last-delivered map against the
        source's current authoritative snapshot (delta-polling sources
        only -- `current_snapshot()` is optional on the `CaseEventSource`
        Protocol; a true-push change-stream source has no equivalent
        catch-up concept and is skipped here, a known limitation noted in
        `mongo_case_event_source.py`'s module docstring)."""
        snapshot_getter = getattr(self._source, "current_snapshot", None)
        if snapshot_getter is None:
            return []
        snapshot: dict[str, HostDiagnosticCase] = snapshot_getter()
        delivered = self._delivered_by_vet.setdefault(vet_email, {})
        changes: list[RawCaseChange] = []
        for case_id, case in snapshot.items():
            if case.farm_id not in assigned_farm_ids:
                continue
            prior_verified_at = delivered.get(case_id)
            if prior_verified_at is None:
                changes.append(RawCaseChange(case=case, change_kind=CaseChangeKind.CREATED))
            elif prior_verified_at != case.verified_at:
                changes.append(RawCaseChange(case=case, change_kind=CaseChangeKind.UPDATED))
        return changes

    async def stream_events(self, vet: AuthenticatedVetContext) -> AsyncIterator[VerifiedClinicalEvent]:
        if vet is None or not vet.is_vet():
            return  # Section 6: router already gates 401/403 before calling this; defensive no-op here too.

        assigned_farms_by_id = await self._resolve_assigned_farms(vet)
        farms_resolved_at = self._clock()
        dedup = SeenEventTracker()
        delivered = self._delivered_by_vet.setdefault(vet.email, {})

        async def _emit(raw_change: RawCaseChange) -> VerifiedClinicalEvent | None:
            if raw_change.case.farm_id not in assigned_farms_by_id:
                return None  # Section 6: not this vet's farm -- silently excluded, never an error
            event = normalize_case_event(raw_change, assigned_farms_by_id=assigned_farms_by_id)
            if event is None:
                return None
            if dedup.seen(event.event_id):
                return None
            dedup.remember(event.event_id)
            delivered[raw_change.case.case_id] = raw_change.case.verified_at
            return event

        for raw_change in self._reconciliation_changes(vet.email, set(assigned_farms_by_id)):
            event = await _emit(raw_change)
            if event is not None:
                yield event

        async for raw_change in self._source.watch():
            if self._clock() - farms_resolved_at >= _ASSIGNED_FARM_CACHE_TTL_SECONDS:
                assigned_farms_by_id = await self._resolve_assigned_farms(vet)
                farms_resolved_at = self._clock()
            event = await _emit(raw_change)
            if event is not None:
                yield event
