"""GEO-LIVE-05 Section 4: two concrete `CaseEventSource` implementations,
constructor-injected with generic collection objects only (mirrors
`host_operational_adapter.py`'s discipline -- no `MongoClient`, no
connection string, no `core.database` import anywhere in this module).

CHANGE-STREAM CAPABILITY (updated by GEO-HOST-READINESS-07's later, bounded
read-only capability probe -- supersedes this module's original GEO-LIVE-05
INCONCLUSIVE finding, which had no live Atlas network test to draw on at
the time): GEO-HOST-READINESS-07 opened `collection.watch(...)` against the
host's actually-configured `diagnostic_cases` collection, confirmed the
server accepted the change-stream aggregation, and closed it immediately --
no document was read, inserted, updated, deleted, or otherwise mutated.
Change-stream capability in that audited environment is therefore VERIFIED/
SUPPORTED, not merely suggestive structural evidence. This result describes
the environment that was probed; it is not a universal guarantee for every
future deployment, and it says nothing about whether a host router is
mounted or push transport is already active in the running application --
capability being SUPPORTED is a separate fact from host composition being
complete (neither is done by this module).

`MongoChangeStreamCaseEventSource` is accordingly the PREFERRED push-capable
source once a later host-composition checkpoint supplies this module with
the host's real, already-configured collection object -- fully implemented
and unit-tested against a fake watchable collection now, so that wiring
step needs no adapter work under time pressure then. `DeltaPollingCaseEventSource`
remains a supported fallback -- for initial deployment, reconnect/degraded
operation, or any environment where change streams turn out to be
unavailable -- never removed just because push is preferred where proven.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Awaitable, Callable, Protocol

import hashlib
import json
from datetime import datetime, timezone

from ..domain.operational_events import CaseChangeKind, GeospatialDataChangedEvent, GeospatialDataChangeKind, RawCaseChange
from ..domain.operational_models import HostDiagnosticCase
from .host_operational_adapter import ReadOnlyCollection, host_timestamp_text

_UNSEEN = object()


def _case_from_document(doc: dict[str, Any]) -> HostDiagnosticCase:
    """Shared raw-document -> `HostDiagnosticCase` mapping, matching
    `host_operational_adapter.MongoOperationalDataPort`'s field reads
    exactly (Section 2: `verified`, `disease_name`, `created_at`,
    `verified_at`, `farm_id` -- `farm_id` already a plain string on the
    document, never an ObjectId)."""
    case_id = doc.get("case_id")
    if case_id is None:
        case_id = str(doc.get("_id"))
    return HostDiagnosticCase(
        case_id=str(case_id),
        farm_id=doc.get("farm_id"),
        disease_name=doc.get("disease_name"),
        verified=bool(doc.get("verified", False)),
        created_at=host_timestamp_text(doc.get("created_at")),
        verified_at=host_timestamp_text(doc.get("verified_at")),
    )


class WatchableCollection(Protocol):
    """The minimal Motor change-stream surface this adapter needs --
    deliberately not the full `AsyncIOMotorCollection` API (mirrors
    `ReadOnlyCollection`'s same minimalism), so a lightweight in-memory
    fake can implement it for tests without a real Mongo driver."""

    def watch(self, pipeline: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]: ...


_CHANGE_STREAM_PIPELINE = [{"$match": {"operationType": {"$in": ["insert", "update", "replace"]}}}]


class MongoChangeStreamCaseEventSource:
    """True-push adapter over `diagnostic_cases_collection.watch(...)`.
    Section 7: fans a single underlying `.watch()` cursor out to every
    concurrent subscriber rather than opening one change stream per vet
    connection -- opening N independent change streams for N concurrently
    connected vets would put unnecessary, unbounded load on the host's
    Mongo deployment for data every subscriber needs filtered from the
    same underlying feed anyway."""

    def __init__(self, collection: WatchableCollection) -> None:
        self._collection = collection
        self._subscribers: list[asyncio.Queue] = []
        self._pump_task: asyncio.Task | None = None

    def describe_transport(self) -> str:
        return "push"

    def _ensure_pump_started(self) -> None:
        if self._pump_task is None:
            self._pump_task = asyncio.ensure_future(self._pump())

    async def _pump(self) -> None:
        async for change in self._collection.watch(_CHANGE_STREAM_PIPELINE):
            full_document = change.get("fullDocument")
            if not full_document:
                # Section 7: a delete/other op with no document body is
                # never a clinical event.
                #
                # GEO-OWNED-FINAL-08 Section 2 (deletion limitation, made
                # explicit): a hard `delete_one` on `diagnostic_cases`
                # (`health_anomaly/router.py::delete_diagnostic_case`) is
                # excluded from `_CHANGE_STREAM_PIPELINE` entirely (it only
                # matches insert/update/replace), and even if it were
                # included, a default Mongo change stream carries no
                # `fullDocument` on a delete op (no
                # `fullDocumentBeforeChange`/pre-image configuration exists
                # anywhere in this branch's Mongo setup -- verified
                # read-only, `core/database.py`). This adapter therefore
                # has NO reliable way to push "case C1 was deleted" as an
                # event, by design -- it never fabricates one. The safety
                # net is the frontend's own periodic authoritative
                # refetch: `useOperationalContext.js`'s 60s controlled poll
                # (and any event-triggered refetch in between) always
                # re-fetches the CURRENT authoritative case list from
                # `OperationalContextService`, which is stateless and
                # simply omits a case no longer returned by the host's
                # `diagnostic_cases` collection (see
                # `test_operational_context_service.py::
                # TestCaseReconciliation::test_case_deleted_upstream_disappears_on_next_call`).
                # A deleted case is guaranteed to disappear from the map
                # within one refresh cycle, never instantly and never via
                # an invented tombstone event.
                continue
            case = _case_from_document(full_document)
            change_kind = CaseChangeKind.CREATED if change.get("operationType") == "insert" else CaseChangeKind.UPDATED
            raw_change = RawCaseChange(case=case, change_kind=change_kind)
            for queue in list(self._subscribers):
                queue.put_nowait(raw_change)

    async def watch(self) -> AsyncIterator[RawCaseChange]:
        self._ensure_pump_started()
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            # Section 8: disconnect cleanup -- a closed subscriber's queue
            # is removed so the pump never grows an unbounded fan-out list.
            if queue in self._subscribers:
                self._subscribers.remove(queue)


class DeltaPollingCaseEventSource:
    """Section 4's explicit near-real-time fallback --
    `describe_transport()` honestly reports `"delta_refresh"`, never
    `"push"`. Polls `diagnostic_cases_collection.find({"verified": True})`
    on a fixed interval and diffs against its own in-memory
    `case_id -> verified_at` snapshot to detect creations/updates.

    The FIRST poll (Section 8 "tolerate reconnect") is a silent priming
    pass -- it seeds the snapshot without broadcasting, so a brand-new
    deployment's first connection is never flooded with a synthetic
    "created" event for every pre-existing verified case. Only genuinely
    NEW or re-verified (changed `verified_at`) cases are broadcast from the
    second poll onward.

    The snapshot lives on this SOURCE instance, not per-subscriber -- so as
    long as the process keeps running, a case change observed while a
    particular vet's browser was briefly disconnected is still captured at
    the next poll tick and delivered to whichever subscribers are attached
    when it fires (Section 15 "reconnect/missed-event reconciliation" is
    handled one layer up, in `event_stream_service.py`, which asks this
    source for `current_snapshot()` to compute a per-vet catch-up diff on
    (re)connect -- see that module)."""

    def __init__(
        self,
        diagnostic_cases_collection: ReadOnlyCollection,
        *,
        poll_interval_seconds: float = 15.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._collection = diagnostic_cases_collection
        self._poll_interval = poll_interval_seconds
        self._sleep = sleep
        self._last_seen: dict[str, HostDiagnosticCase] = {}
        self._subscribers: list[asyncio.Queue] = []
        self._run_task: asyncio.Task | None = None
        self._primed = asyncio.Event()
        self._data_version: str | None = None

    def describe_transport(self) -> str:
        return "delta_refresh"

    def current_snapshot(self) -> dict[str, HostDiagnosticCase]:
        """Section 15: a shallow copy of this source's own authoritative
        `case_id -> last-seen HostDiagnosticCase` view (ALL cases, pending
        included), used by `event_stream_service.py` to compute a per-vet
        reconciliation diff on (re)connect. Never mutated by the caller."""
        return dict(self._last_seen)

    async def ensure_primed(self) -> None:
        """Starts polling (if needed) and waits for the first authoritative snapshot."""
        self._ensure_started()
        await self._primed.wait()

    def current_data_version(self) -> str | None:
        """Deterministic version of the whole case dataset as last polled --
        sent in the SSE `ready` frame so a reconnecting client can tell
        whether it missed any change and must refetch."""
        return self._data_version

    async def _poll_once(self) -> tuple[list[RawCaseChange], list[GeospatialDataChangedEvent]]:
        """One read-only poll of EVERY case (small projection, never images).
        Detects creation (pending or verified), verification, withdrawal of
        verification, disease reclassification, correction and deletion."""
        current: dict[str, HostDiagnosticCase] = {}
        async for doc in self._collection.find({}, _CASE_PROJECTION):
            case = _case_from_document(doc)
            current[case.case_id] = case
        raw_changes: list[RawCaseChange] = []
        data_changes: list[tuple] = []
        for case_id, case in sorted(current.items()):
            prior = self._last_seen.get(case_id)
            if prior is None:
                data_changes.append((GeospatialDataChangeKind.CREATED, case, None))
                raw_changes.append(RawCaseChange(case=case, change_kind=CaseChangeKind.CREATED))
                continue
            if _fingerprint(prior) == _fingerprint(case):
                continue
            if not prior.verified and case.verified:
                data_changes.append((GeospatialDataChangeKind.VERIFIED, case, prior))
                # Newly verified = a NEW verified clinical context (unchanged semantics).
                raw_changes.append(RawCaseChange(case=case, change_kind=CaseChangeKind.CREATED))
            elif prior.verified and not case.verified:
                data_changes.append((GeospatialDataChangeKind.UNVERIFIED, case, prior))
            elif prior.disease_name != case.disease_name:
                data_changes.append((GeospatialDataChangeKind.RECLASSIFIED, case, prior))
                raw_changes.append(RawCaseChange(case=case, change_kind=CaseChangeKind.UPDATED))
            else:
                data_changes.append((GeospatialDataChangeKind.CORRECTED, case, prior))
                if prior.verified_at != case.verified_at or prior.farm_id != case.farm_id:
                    raw_changes.append(RawCaseChange(case=case, change_kind=CaseChangeKind.UPDATED))
        for case_id in sorted(set(self._last_seen) - set(current)):
            data_changes.append((GeospatialDataChangeKind.DELETED, None, self._last_seen[case_id]))
        self._last_seen = current
        self._data_version = _dataset_version(current)
        events = [_data_change_event(kind, case, prior, self._data_version) for kind, case, prior in data_changes]
        return raw_changes, events

    async def _run(self) -> None:
        await self._poll_once()  # priming pass -- seeds the snapshot, never broadcast
        self._primed.set()
        while True:
            await self._sleep(self._poll_interval)
            raw_changes, data_events = await self._poll_once()
            for item in [*raw_changes, *data_events]:
                for queue in list(self._subscribers):
                    queue.put_nowait(item)

    def _ensure_started(self) -> None:
        if self._run_task is None:
            self._run_task = asyncio.ensure_future(self._run())

    def watch(self) -> AsyncIterator:
        """Registers the subscriber EAGERLY (before the first `__anext__`), so a
        change polled between `watch()` and the first read is never lost.
        Yields `RawCaseChange` and `GeospatialDataChangedEvent` items."""
        self._ensure_started()
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        return self._drain(queue)

    async def _drain(self, queue: asyncio.Queue):
        try:
            await self._primed.wait()
            while True:
                yield await queue.get()
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)


_CASE_PROJECTION = {"farm_id": 1, "disease_name": 1, "verified": 1, "created_at": 1, "verified_at": 1, "case_id": 1}


def _fingerprint(case: HostDiagnosticCase) -> tuple:
    return (case.farm_id, case.disease_name, case.verified, case.created_at, case.verified_at)


def _dataset_version(cases: dict[str, HostDiagnosticCase]) -> str:
    canonical = json.dumps(sorted([cid, *map(str, _fingerprint(c))] for cid, c in cases.items()), separators=(",", ":"))
    return "ds_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _disease_code(disease_name: str | None) -> str | None:
    from ..services.operational.disease_normalization import resolve_operational_disease

    resolved = resolve_operational_disease(disease_name)
    return resolved.value if resolved else None


def _data_change_event(kind, case, prior, data_version: str) -> GeospatialDataChangedEvent:
    from ..services.operational.national_cases import record_key

    subject = case or prior
    return GeospatialDataChangedEvent(
        change=kind.value,
        record_key=record_key(subject.case_id),
        disease=_disease_code(subject.disease_name) if case is not None else None,
        previous_disease=_disease_code(prior.disease_name) if prior is not None else None,
        verified=bool(case.verified) if case is not None else None,
        data_version=data_version,
        event_generated_at=datetime.now(timezone.utc).isoformat(),
    )
