"""In-memory `CaseEventSource`/`WatchableCollection` fakes for GEO-LIVE-05
tests (Section 7/21: "Use an abstraction/port so tests do NOT require Mongo
Atlas", "Use fake in-memory event sources for tests"). Not a `test_*`
module -- pytest will not collect it directly.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from components.geospatial_tracking.domain.operational_events import RawCaseChange
from components.geospatial_tracking.domain.operational_models import HostDiagnosticCase


class FakeCaseEventSource:
    """Directly implements `repositories.case_event_port.CaseEventSource`.
    `push()` lets a test inject a raw change on demand (no real polling/
    change-stream timing involved); `current_snapshot()` optionally
    supports the same reconciliation contract
    `DeltaPollingCaseEventSource` provides, for
    `event_stream_service.py`'s reconnect-catch-up tests."""

    def __init__(self, *, transport: str = "push") -> None:
        self._transport = transport
        self._subscribers: list[asyncio.Queue] = []
        self._snapshot: dict[str, HostDiagnosticCase] = {}

    def describe_transport(self) -> str:
        return self._transport

    def current_snapshot(self) -> dict[str, HostDiagnosticCase]:
        return dict(self._snapshot)

    def seed_snapshot(self, case: HostDiagnosticCase) -> None:
        """Simulates a case the source already knew about BEFORE this
        vet's connection started (e.g. verified while they were
        disconnected) -- used for reconciliation tests."""
        self._snapshot[case.case_id] = case

    def push(self, raw_change: RawCaseChange) -> None:
        self._snapshot[raw_change.case.case_id] = raw_change.case
        for queue in list(self._subscribers):
            queue.put_nowait(raw_change)

    async def watch(self) -> AsyncIterator[RawCaseChange]:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)


class FakeWatchableCollection:
    """Fake for `repositories.mongo_case_event_source.WatchableCollection`
    -- `push()` injects one raw Mongo change-stream document (the same
    shape a real `AsyncIOMotorChangeStream` would yield: `operationType`,
    `fullDocument`)."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []
        self.watch_calls: list[list[dict[str, Any]]] = []

    def watch(self, pipeline: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
        self.watch_calls.append(pipeline)
        return self._iter()

    async def _iter(self) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    def push(self, change_document: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            queue.put_nowait(change_document)


class FakeDiagnosticCasesCollection:
    """Minimal fake for `DeltaPollingCaseEventSource`'s
    `ReadOnlyCollection` dependency -- a plain, test-controlled document
    list, `find()` filtered to `{"verified": True}` only (the one query
    shape that source ever issues)."""

    def __init__(self, documents: list[dict[str, Any]] | None = None) -> None:
        self.documents = documents or []

    async def find_one(self, filter: dict[str, Any]) -> dict[str, Any] | None:
        for doc in self.documents:
            if all(doc.get(k) == v for k, v in filter.items()):
                return doc
        return None

    def find(self, filter: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        matching = [doc for doc in self.documents if doc.get("verified") is True] if filter.get("verified") else list(self.documents)
        return self._iter(matching)

    async def _iter(self, documents: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
        for doc in documents:
            yield doc
