"""GEO-MONGODB-NATIVE-INTEGRATION-24B: in-memory fake Mongo *database*
(not just a collection) for `scripts/migrate_sqlite_to_mongo.py` tests --
supports exactly what that script calls: `db.list_collection_names()`,
`db[name].find(...)`, `db[name].bulk_write([ReplaceOne(...), ...])`, and a
`.name` attribute (mirrors real `pymongo.database.Database.name`). Accepts
REAL `pymongo.ReplaceOne` operation objects (pymongo is already an
installed dependency of `motor`) rather than reimplementing bulk-write
semantics from scratch -- reads their `_filter`/`_doc`/`_upsert`
attributes, the same ones a real `Collection.bulk_write` reads. No real
Mongo driver connection, no network, never touches the real `adrs_core`
database."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass
class _FakeBulkWriteResult:
    upserted_count: int
    matched_count: int
    modified_count: int


class FakeDestinationCollection:
    def __init__(self) -> None:
        self._documents: dict[Any, dict[str, Any]] = {}

    def seed(self, doc: dict[str, Any]) -> None:
        self._documents[doc["_id"]] = dict(doc)

    def find(self, filter: dict[str, Any] | None = None, projection: dict[str, Any] | None = None):
        filter = filter or {}
        if "_id" in filter and isinstance(filter["_id"], dict) and "$in" in filter["_id"]:
            wanted = set(filter["_id"]["$in"])
            docs = [d for _id, d in self._documents.items() if _id in wanted]
        else:
            docs = list(self._documents.values())
        if projection == {"_id": 1}:
            return [{"_id": d["_id"]} for d in docs]
        return [dict(d) for d in docs]

    def bulk_write(self, operations: Iterable[Any], ordered: bool = True) -> _FakeBulkWriteResult:
        upserted = 0
        matched = 0
        modified = 0
        for op in operations:
            doc_id = op._filter["_id"]
            doc = dict(op._doc)
            if doc_id in self._documents:
                matched += 1
                if self._documents[doc_id] != doc:
                    modified += 1
                self._documents[doc_id] = doc
            else:
                upserted += 1
                self._documents[doc_id] = doc
        return _FakeBulkWriteResult(upserted_count=upserted, matched_count=matched, modified_count=modified)

    def count_documents(self, filter: dict[str, Any] | None = None) -> int:
        return len(self.find(filter))


class FakeDestinationDb:
    """Fake `pymongo.database.Database` -- `db[name]` indexing,
    `.list_collection_names()`, `.name`."""

    def __init__(self, name: str = "adrs_core", *, preexisting_collections: Iterable[str] = ()) -> None:
        self.name = name
        self._collections: dict[str, FakeDestinationCollection] = {c: FakeDestinationCollection() for c in preexisting_collections}

    def __getitem__(self, name: str) -> FakeDestinationCollection:
        return self._collections.setdefault(name, FakeDestinationCollection())

    def list_collection_names(self) -> list[str]:
        return list(self._collections.keys())
