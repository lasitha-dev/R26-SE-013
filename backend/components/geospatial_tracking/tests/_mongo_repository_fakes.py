"""GEO-MONGODB-NATIVE-INTEGRATION-24B: in-memory `SyncCollection` fake for
`MongoOutbreakRepository` tests (mirrors `_operational_fakes.py::FakeCollection`'s
same "no real Mongo driver / no network" discipline, but synchronous --
`repositories/mongo_repository.py::SyncCollection` is a plain, non-async
Protocol). Not a `test_*` module -- pytest will not collect it directly.
"""

from __future__ import annotations

from typing import Any, Iterator


class FakeSyncCollection:
    """In-memory stand-in for `repositories.mongo_repository.SyncCollection`.
    Supports exactly what `MongoOutbreakRepository` calls: `find_one`,
    `find` (plain equality filters only -- every filter
    `MongoOutbreakRepository` builds is a plain equality `dict`, never a
    Mongo operator), `replace_one(..., upsert=True)`, and a no-op
    `create_index` (schema/index calls need no real backing store to be
    exercised as idempotent no-ops in a test)."""

    def __init__(self) -> None:
        self._documents: dict[Any, dict[str, Any]] = {}
        self.write_calls: list[str] = []
        self.read_calls: list[str] = []

    def find_one(self, filter: dict[str, Any]) -> dict[str, Any] | None:
        self.read_calls.append("find_one")
        for doc in self._documents.values():
            if _matches(doc, filter):
                return dict(doc)
        return None

    def find(self, filter: dict[str, Any]) -> Iterator[dict[str, Any]]:
        self.read_calls.append("find")
        return iter([dict(doc) for doc in self._documents.values() if _matches(doc, filter)])

    def replace_one(self, filter: dict[str, Any], replacement: dict[str, Any], upsert: bool = False) -> None:
        self.write_calls.append("replace_one")
        self._documents[replacement["_id"]] = dict(replacement)

    def create_index(self, keys: Any, **kwargs: Any) -> None:
        # Idempotent no-op -- mirrors real Mongo's own idempotent
        # create_index behavior; nothing to track for a fake.
        return None

    # -- test helpers, never called by MongoOutbreakRepository itself --
    def seed(self, doc: dict[str, Any]) -> None:
        self._documents[doc["_id"]] = dict(doc)

    def all_ids(self) -> list[Any]:
        return list(self._documents.keys())


def _matches(doc: dict[str, Any], filter: dict[str, Any]) -> bool:
    return all(doc.get(k) == v for k, v in filter.items())
