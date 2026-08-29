"""GEO-INT-02: concrete `OperationalDataPort` backed by the host
application's existing Mongo collections.

Reads three collections whose shapes were verified READ-ONLY against
`origin/main` (never imported, never materialized into this branch):

  - `origin/main:backend/core/database.py` -- collection wiring pattern
    (`db.farms`, `db.cattle`, `db.vets`; `core.database` itself is never
    imported here -- Section 4).
  - `origin/main:backend/components/health_anomaly/database.py` -- adds
    `diagnostic_cases_collection = db.diagnostic_cases`.
  - `origin/main:backend/components/health_anomaly/router.py` --
    `GET /vet/my-farms` (`list_vet_assigned_farms`, line ~619) is the
    proven assignment-resolution query this adapter's
    `_resolve_assigned_farm_documents` reproduces exactly: a vet is
    matched to `vets_collection` by `email` (JWT `sub`), and a farm is
    "assigned" when ANY of four conditions holds --
    `farm._id in vet.assigned_farm_ids`, `farm.email in
    vet.assigned_farms`, `vet_id_str in farm.assigned_vet_ids`, or
    `vet.email in farm.assigned_vet_emails`. `farm_id` on a
    `diagnostic_cases` document is a plain string -- `str(farm["_id"])`,
    verified from `report_diagnostic_case`/`verify_diagnostic_case`
    (lines ~781, ~799) -- never a `bson.ObjectId`.
  - `origin/main:backend/components/health_anomaly/schemas.py` --
    `DiagnosticCaseResponse` field names (`verified`, `disease_name`,
    `created_at`, `verified_at`, `farm_id`).

Constructor-injected, generic collections only (Section 4/5) -- no
`MongoClient`, no connection string, no `core.database`/`core.security`
import anywhere in this module. `ReadOnlyCollection` below is the minimal
shape actually used (`find_one`, `find`); a real Motor
`AsyncIOMotorCollection` satisfies it structurally, and so does a plain
in-memory fake used by tests (`tests/_operational_fakes.py`) -- no live
Mongo/network required to exercise this adapter.

READ-ONLY (Section 10): every method below only ever calls `find_one`/
`find`. No `insert_one`/`update_one`/`delete_one` (or any mutation) is
called or even importable from a `ReadOnlyCollection`, since that Protocol
does not declare them -- see
`tests/test_host_operational_adapter.py::TestReadOnlyGuarantee` and the
structural scan in `tests/test_operational_structural_ownership.py`.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol

from bson import ObjectId

from ..domain.operational_models import AuthenticatedVetContext, HostDiagnosticCase, HostFarmRecord


class ReadOnlyCollection(Protocol):
    """The minimal Motor-collection surface this adapter needs -- deliberately
    NOT the full `AsyncIOMotorCollection` API, so a lightweight in-memory
    fake can implement it for tests without a real Mongo driver."""

    async def find_one(self, filter: dict[str, Any]) -> dict[str, Any] | None: ...

    def find(self, filter: dict[str, Any]) -> AsyncIterator[dict[str, Any]]: ...


def _valid_object_id(value: Any) -> ObjectId | None:
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


class MongoOperationalDataPort:
    """Host-adapter implementation of
    `repositories.operational_port.OperationalDataPort`. Every method takes
    the trusted `AuthenticatedVetContext` and resolves data scoped to that
    vet's own assignments only (Section 6: never all farms, never another
    vet's farms) -- the vet's `email` is the only identity ever used in a
    query; nothing here trusts a caller-supplied id."""

    def __init__(
        self,
        vets_collection: ReadOnlyCollection,
        farms_collection: ReadOnlyCollection,
        diagnostic_cases_collection: ReadOnlyCollection,
    ) -> None:
        self._vets = vets_collection
        self._farms = farms_collection
        self._diagnostic_cases = diagnostic_cases_collection

    async def _resolve_assigned_farm_documents(self, vet: AuthenticatedVetContext) -> list[dict[str, Any]]:
        """Section 6/8: the ONE place assignment is resolved, reused by
        both port methods so a farm's id normalizes identically in both
        (`HostFarmRecord.farm_id` and `HostDiagnosticCase.farm_id` must
        agree -- Section 8)."""
        vet_doc = await self._vets.find_one({"email": vet.email})
        if vet_doc is None:
            return []  # Section 15 case 3: no vet record -> safe empty outcome, never an error

        vet_id_str = str(vet_doc["_id"])
        assigned_farm_object_ids = [
            oid for oid in (_valid_object_id(f) for f in vet_doc.get("assigned_farm_ids", [])) if oid is not None
        ]
        assigned_farm_emails = vet_doc.get("assigned_farms", [])

        query = {
            "$or": [
                {"_id": {"$in": assigned_farm_object_ids}},
                {"email": {"$in": assigned_farm_emails}},
                {"assigned_vet_ids": vet_id_str},
                {"assigned_vet_emails": vet_doc.get("email")},
            ]
        }

        documents = []
        async for farm_doc in self._farms.find(query):
            documents.append(farm_doc)
        return documents

    async def get_assigned_farms(self, vet: AuthenticatedVetContext) -> list[HostFarmRecord]:
        farm_documents = await self._resolve_assigned_farm_documents(vet)
        return [
            HostFarmRecord(
                farm_id=str(doc["_id"]),
                latitude=doc.get("latitude"),
                longitude=doc.get("longitude"),
                location_district=doc.get("location_district"),
                total_animals=doc.get("total_animals"),
            )
            for doc in farm_documents
        ]

    async def get_verified_clinical_cases(self, vet: AuthenticatedVetContext) -> list[HostDiagnosticCase]:
        farm_documents = await self._resolve_assigned_farm_documents(vet)
        assigned_farm_ids = [str(doc["_id"]) for doc in farm_documents]
        if not assigned_farm_ids:
            return []

        # Section 7: filter as early as safely possible -- both
        # `verified` and the assigned-farm scope are pushed into the
        # Mongo query itself, not applied only after fetching everything.
        query = {"verified": True, "farm_id": {"$in": assigned_farm_ids}}

        cases: list[HostDiagnosticCase] = []
        async for case_doc in self._diagnostic_cases.find(query):
            cases.append(
                HostDiagnosticCase(
                    case_id=str(case_doc["_id"]),
                    farm_id=case_doc.get("farm_id"),
                    disease_name=case_doc.get("disease_name"),
                    verified=bool(case_doc.get("verified", False)),
                    created_at=case_doc.get("created_at"),
                    verified_at=case_doc.get("verified_at"),
                )
            )
        return cases
