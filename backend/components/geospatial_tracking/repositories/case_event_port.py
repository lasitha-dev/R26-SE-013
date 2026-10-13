"""GEO-LIVE-05 Section 4/7: storage-agnostic boundary for a live upstream
case-change source. Mirrors `operational_port.py`'s Protocol split exactly
-- `services/operational/event_stream_service.py` depends on this Protocol
only, never on a concrete Mongo change-stream/polling implementation.

Two concrete adapters exist (`mongo_case_event_source.py`):
`MongoChangeStreamCaseEventSource` (preferred, true push, requires a
replica-set-backed Mongo deployment) and `DeltaPollingCaseEventSource` (the
explicit, honestly-labeled near-real-time fallback -- Section 4:
`describe_transport()` never claims `"push"` when it is not). Tests use
`tests/_event_fakes.py::FakeCaseEventSource`, never a real Mongo/Atlas
connection.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol

from ..domain.operational_events import RawCaseChange


class CaseEventSource(Protocol):
    """A long-lived, shareable source of raw case changes. `watch()` may be
    called concurrently by multiple subscribers (one per live vet
    connection) -- an implementation is expected to fan out the same
    underlying change to every active subscriber, not create a second
    independent upstream watch per call (Section 7: efficient, and avoids
    duplicate load on the host's Mongo deployment)."""

    def describe_transport(self) -> str:
        """`"push"` for a true change-stream source, `"delta_refresh"` for
        a polling fallback. Never a third, ambiguous value -- callers
        (Section 4/9) use this exact string to decide whether "LIVE"
        wording is honest to show."""
        ...

    def watch(self) -> AsyncIterator[RawCaseChange]:
        """Yields a `RawCaseChange` each time the source observes a case
        creation/update, until the caller stops iterating (cancels/closes
        the async generator) -- Section 7/8: disconnect-aware, reconnect-
        tolerant. Never raises for "no new change yet"; it simply does not
        yield."""
        ...
