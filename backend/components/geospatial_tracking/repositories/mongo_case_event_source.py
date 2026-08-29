"""GEO-LIVE-05 Section 4: two concrete `CaseEventSource` implementations,
constructor-injected with generic collection objects only (mirrors
`host_operational_adapter.py`'s discipline -- no `MongoClient`, no
connection string, no `core.database` import anywhere in this module).

CHANGE-STREAM CAPABILITY (Section 4 of this checkpoint's own audit):
this repository has no existing `.watch(` usage anywhere, and no live
Atlas network test was run (none is safe to run from this checkpoint --
no `.env`/connection string is present in this branch's tree). The only
structural evidence available is that `origin/main:backend/core/database.py`
uses an `mongodb+srv://` Atlas connection string, and Atlas clusters are
always deployed as replica sets, which is the one deployment requirement
`.watch()` needs. That evidence is suggestive, not a proof -- this
checkpoint's report classifies change-stream support INCONCLUSIVE rather
than VALID, and treats `DeltaPollingCaseEventSource` as the safe default
until a live capability check is actually run against the real deployment.

`MongoChangeStreamCaseEventSource` is still implemented and fully unit-
tested against a fake watchable collection (Section 4: "If change streams
are supported, use them as the preferred operational event source") so a
later checkpoint can wire it in the moment that live check passes, without
writing this adapter from scratch under time pressure then.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Awaitable, Callable, Protocol

from ..domain.operational_events import CaseChangeKind, RawCaseChange
from ..domain.operational_models import HostDiagnosticCase
from .host_operational_adapter import ReadOnlyCollection

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
        created_at=doc.get("created_at"),
        verified_at=doc.get("verified_at"),
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

    def describe_transport(self) -> str:
        return "delta_refresh"

    def current_snapshot(self) -> dict[str, HostDiagnosticCase]:
        """Section 15: a shallow copy of this source's own authoritative
        `case_id -> last-seen HostDiagnosticCase` view, used by
        `event_stream_service.py` to compute a per-vet reconciliation diff
        on (re)connect. Never mutated by the caller."""
        return dict(self._last_seen)

    async def _poll_once(self) -> list[RawCaseChange]:
        changes: list[RawCaseChange] = []
        async for doc in self._collection.find({"verified": True}):
            case = _case_from_document(doc)
            prior = self._last_seen.get(case.case_id, _UNSEEN)
            if prior is _UNSEEN:
                changes.append(RawCaseChange(case=case, change_kind=CaseChangeKind.CREATED))
            elif prior.verified_at != case.verified_at:
                changes.append(RawCaseChange(case=case, change_kind=CaseChangeKind.UPDATED))
            self._last_seen[case.case_id] = case
        return changes

    async def _run(self) -> None:
        await self._poll_once()  # priming pass -- seeds the snapshot, never broadcast
        self._primed.set()
        while True:
            await self._sleep(self._poll_interval)
            changes = await self._poll_once()
            for change in changes:
                for queue in list(self._subscribers):
                    queue.put_nowait(change)

    def _ensure_started(self) -> None:
        if self._run_task is None:
            self._run_task = asyncio.ensure_future(self._run())

    async def watch(self) -> AsyncIterator[RawCaseChange]:
        self._ensure_started()
        await self._primed.wait()
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
