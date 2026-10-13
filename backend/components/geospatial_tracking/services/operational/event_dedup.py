"""GEO-LIVE-05 Section 7: a small bounded-size "already delivered"
event_id tracker. Deliberately not a persistence layer -- purely an
in-memory guard against re-emitting the SAME logical event twice within
one stream/connection lifetime (Section 7 "deduplicate repeated
Mongo/update events"), never written to scientific storage."""

from __future__ import annotations

from collections import OrderedDict


class SeenEventTracker:
    def __init__(self, max_size: int = 2048) -> None:
        self._max_size = max_size
        self._seen: "OrderedDict[str, None]" = OrderedDict()

    def seen(self, event_id: str) -> bool:
        return event_id in self._seen

    def remember(self, event_id: str) -> None:
        if event_id in self._seen:
            self._seen.move_to_end(event_id)
            return
        self._seen[event_id] = None
        if len(self._seen) > self._max_size:
            self._seen.popitem(last=False)
