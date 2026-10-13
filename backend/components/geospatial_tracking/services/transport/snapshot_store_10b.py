"""Checkpoint 10B/10B.1: bounded, thread-safe, single-flight snapshot
cache with memory-safe auxiliary state.

**Engineering only** -- `SNAPSHOT_CACHE_MAX_ENTRIES_10B`/
`SNAPSHOT_CACHE_TTL_SECONDS_10B` are
`ENGINEERING_TRANSPORT_PARAMETERS_NOT_SCIENTIFIC_PARAMETERS`: never
tuned against outbreak outcomes, risk values, or validation metrics.
This module knows nothing about C0/direction/rate/reach -- it caches
whatever opaque object `compute_fn()` returns, keyed by a caller-
supplied tuple.

**Cache scope is honest**: the current repository abstraction
(`repositories/base.py::OutbreakRepository`) exposes no real data
revision/version token, so none is invented.
`SNAPSHOT_CACHE_SCOPE_10B = "PROCESS_LOCAL_EPHEMERAL_HISTORICAL_REPLAY_ONLY"`
and `REPOSITORY_REVISION_TOKEN_STATUS_10B = "NOT_AVAILABLE"` -- this
cache is permissible only because the active scientific mode is
`HISTORICAL_RETROSPECTIVE_REPLAY`; it is never proof of cross-process
consistency or live-data freshness. Any future `LIVE_OPERATIONAL` mode
must disable this reuse or add a real invalidation mechanism.

**Checkpoint 10B.1 Part 2: reference-counted per-key single-flight
slots.** A `_KeySlot` (one `threading.Lock` + a borrower `refcount`) is
created the first time a key is seen and reclaimed the moment the last
borrower releases it -- in a `finally` block, so this happens whether
`compute_fn()` succeeds, raises, or the caller is cancelled. Two
concurrent callers for the SAME key are handed the SAME slot object
(the increment happens under `self._lock`, so no caller can observe a
slot mid-removal): the second blocks on `slot.lock` until the first's
`compute_fn()` finishes and stores its result, then observes a cache
hit -- `compute_fn()` still runs at most once per key per
miss/expiry/failure window. Because reclamation only removes a slot
once its `refcount` reaches zero, a slot already handed to a waiting
thread is never invalidated out from under it. Thousands of distinct
keys -- successful or failing -- never leave a stale entry in
`_key_slots`: at any instant it holds at most as many entries as there
are keys with an in-flight `get_or_compute` call.

**Bounded eviction diagnostics** (Part 2): `eviction_count` is a plain
int (unbounded as a *number*, but O(1) memory); `recent_evicted_keys`
is a `deque(maxlen=EVICTION_DIAGNOSTIC_HISTORY_MAXLEN_10B1)` -- never
an unbounded historical list.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any, Callable

SNAPSHOT_CACHE_MAX_ENTRIES_10B = 8
SNAPSHOT_CACHE_TTL_SECONDS_10B = 60.0
CACHE_PARAMETER_CLASSIFICATION_10B = "ENGINEERING_TRANSPORT_PARAMETERS_NOT_SCIENTIFIC_PARAMETERS"

SNAPSHOT_CACHE_SCOPE_10B = "PROCESS_LOCAL_EPHEMERAL_HISTORICAL_REPLAY_ONLY"
REPOSITORY_REVISION_TOKEN_STATUS_10B = "NOT_AVAILABLE"

EVICTION_DIAGNOSTIC_HISTORY_MAXLEN_10B1 = 50

CACHE_STATUS_MISS_COMPUTED = "MISS_COMPUTED"
CACHE_STATUS_HIT_REUSED = "HIT_REUSED"
CACHE_STATUS_FORCE_REFRESH_RECOMPUTED = "FORCE_REFRESH_RECOMPUTED"
CACHE_STATUS_EXPIRED_RECOMPUTED = "EXPIRED_RECOMPUTED"
CACHE_STATUS_EVICTED_LRU = "EVICTED_LRU"  # recorded against the evicted key, never returned as a get_or_compute() result


@dataclass
class _CacheEntry:
    value: Any
    created_monotonic: float


@dataclass
class _KeySlot:
    lock: threading.Lock = field(default_factory=threading.Lock)
    refcount: int = 0


class SnapshotStore10B:
    """Generic bounded LRU+TTL cache with per-key single-flight
    compute and memory-safe auxiliary state. Knows nothing about
    scientific content -- `key` is any hashable tuple the caller builds
    (for the geospatial snapshot use case: `forecast_origin_id`,
    `active_api_protocol_hash_10a1`, `runtime_data_mode`,
    `availability_mode`, `record_domain_scope`,
    `active_source_window_days`)."""

    def __init__(
        self, *,
        max_entries: int = SNAPSHOT_CACHE_MAX_ENTRIES_10B,
        ttl_seconds: float = SNAPSHOT_CACHE_TTL_SECONDS_10B,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1:
            raise ValueError(f"max_entries must be >= 1, got {max_entries!r}")
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: OrderedDict[tuple, _CacheEntry] = OrderedDict()
        self._key_slots: dict[tuple, _KeySlot] = {}
        self.eviction_count = 0
        self.recent_evicted_keys: deque[tuple] = deque(maxlen=EVICTION_DIAGNOSTIC_HISTORY_MAXLEN_10B1)

    def _acquire_key_slot(self, key: tuple) -> _KeySlot:
        with self._lock:
            slot = self._key_slots.get(key)
            if slot is None:
                slot = _KeySlot()
                self._key_slots[key] = slot
            slot.refcount += 1
            return slot

    def _release_key_slot(self, key: tuple, slot: _KeySlot) -> None:
        with self._lock:
            slot.refcount -= 1
            if slot.refcount <= 0 and self._key_slots.get(key) is slot:
                del self._key_slots[key]

    def get_or_compute(self, key: tuple, compute_fn: Callable[[], Any], *, force_refresh: bool = False) -> tuple[Any, str]:
        """Returns `(value, cache_status)`. `compute_fn` is called AT
        MOST once per (key, miss-or-expiry) -- never while `self._lock`
        is held, so unrelated keys are never blocked by one key's
        expensive computation. The per-key slot is always reclaimed
        (Part 2) whether `compute_fn` succeeds or raises."""
        slot = self._acquire_key_slot(key)
        try:
            with slot.lock:
                if not force_refresh:
                    with self._lock:
                        entry = self._entries.get(key)
                    if entry is not None:
                        age = self._clock() - entry.created_monotonic
                        if age <= self._ttl_seconds:
                            with self._lock:
                                if key in self._entries:
                                    self._entries.move_to_end(key)
                            return entry.value, CACHE_STATUS_HIT_REUSED
                        status_on_store = CACHE_STATUS_EXPIRED_RECOMPUTED
                    else:
                        status_on_store = CACHE_STATUS_MISS_COMPUTED
                else:
                    status_on_store = CACHE_STATUS_FORCE_REFRESH_RECOMPUTED

                value = compute_fn()  # never cached if this raises -- and the slot is still reclaimed in `finally` below

                with self._lock:
                    self._entries[key] = _CacheEntry(value=value, created_monotonic=self._clock())
                    self._entries.move_to_end(key)
                    while len(self._entries) > self._max_entries:
                        evicted_key, _ = self._entries.popitem(last=False)
                        self.eviction_count += 1
                        self.recent_evicted_keys.append(evicted_key)

                return value, status_on_store
        finally:
            self._release_key_slot(key, slot)

    def invalidate(self, key: tuple) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self.eviction_count = 0
            self.recent_evicted_keys.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def n_active_key_slots(self) -> int:
        """Diagnostic only -- the number of keys with an in-flight
        `get_or_compute` call right now. Never grows with historical
        key count (10B1-MEM-01/02)."""
        with self._lock:
            return len(self._key_slots)
