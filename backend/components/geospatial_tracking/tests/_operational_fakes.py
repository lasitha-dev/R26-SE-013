"""In-memory `OperationalDataPort` fake for GEO-INT-01/02 tests (Section
6/21: "Tests should use fake/in-memory implementations", "NO Mongo Atlas/
network dependency"). Not a `test_*` module — pytest will not collect it
directly.

Also provides `FakeCollection` — a minimal in-memory stand-in for
`repositories.host_operational_adapter.ReadOnlyCollection` (`find_one`/
`find`, with just enough Mongo query semantics — `$or`, `$in`, and
array-contains-or-equals plain-field matching — to exercise
`MongoOperationalDataPort` against realistic vet/farm/case documents
without a real Mongo driver), plus builders for documents whose FIELD
SHAPES match `origin/main`'s real `vets`/`farms`/`diagnostic_cases`
collections (Section 14) — synthetic values, real shapes.
"""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from components.geospatial_tracking.domain.operational_models import (
    AuthenticatedVetContext,
    HostDiagnosticCase,
    HostFarmRecord,
)


class FakeOperationalDataPort:
    def __init__(
        self,
        farms: list[HostFarmRecord] | None = None,
        cases: list[HostDiagnosticCase] | None = None,
        raise_on_farms: bool = False,
        raise_on_cases: bool = False,
    ) -> None:
        self._farms = farms or []
        self._cases = cases or []
        self._raise_on_farms = raise_on_farms
        self._raise_on_cases = raise_on_cases
        self.farms_calls: list[AuthenticatedVetContext] = []
        self.cases_calls: list[AuthenticatedVetContext] = []

    async def get_assigned_farms(self, vet: AuthenticatedVetContext) -> list[HostFarmRecord]:
        self.farms_calls.append(vet)
        if self._raise_on_farms:
            raise RuntimeError("simulated host data source outage")
        return list(self._farms)

    async def get_verified_clinical_cases(self, vet: AuthenticatedVetContext) -> list[HostDiagnosticCase]:
        self.cases_calls.append(vet)
        if self._raise_on_cases:
            raise RuntimeError("simulated host data source outage")
        return list(self._cases)


def _field_matches(doc_value: Any, condition: Any) -> bool:
    if isinstance(condition, dict) and "$in" in condition:
        target = condition["$in"]
        if isinstance(doc_value, list):
            return any(v in target for v in doc_value)
        return doc_value in target
    # Plain-value condition: real Mongo matches a scalar condition against
    # an array field if the array CONTAINS that value (not only equality) —
    # `MongoOperationalDataPort`'s `assigned_vet_ids`/`assigned_vet_emails`
    # conditions rely on exactly this.
    if isinstance(doc_value, list):
        return condition in doc_value
    return doc_value == condition


def _matches_query(doc: dict[str, Any], query: dict[str, Any]) -> bool:
    if "$or" in query:
        return any(_matches_query(doc, sub_query) for sub_query in query["$or"])
    return all(_field_matches(doc.get(field), condition) for field, condition in query.items())


class _FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents
        self._index = 0

    def __aiter__(self) -> "_FakeCursor":
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._index >= len(self._documents):
            raise StopAsyncIteration
        document = self._documents[self._index]
        self._index += 1
        return document


class FakeCollection:
    """In-memory `ReadOnlyCollection`. `find_one`/`find` only — adding an
    insert/update/delete method here would be a step backward for the
    read-only guarantee this fake exists to help test."""

    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    async def find_one(self, filter: dict[str, Any]) -> dict[str, Any] | None:
        for document in self._documents:
            if _matches_query(document, filter):
                return document
        return None

    def find(self, filter: dict[str, Any]) -> _FakeCursor:
        return _FakeCursor([document for document in self._documents if _matches_query(document, filter)])


def make_vet_document(**overrides: Any) -> dict[str, Any]:
    """Shape verified against `origin/main:backend/components/health_anomaly/
    router.py::register_vet`/`login_vet`/`list_vet_assigned_farms`."""
    document: dict[str, Any] = {
        "_id": ObjectId(),
        "full_name": "Dr. Test Vet",
        "email": "vet@example.com",
        "password": "hashed",
        "license_number": "VET-0001",
        "phone": "0770000000",
        "district": "Colombo",
        "role": "vet",
        "assigned_farms": [],
        "assigned_farm_ids": [],
    }
    document.update(overrides)
    return document


def make_farm_document(**overrides: Any) -> dict[str, Any]:
    """Shape verified against `origin/main:backend/components/health_anomaly/
    schemas.py::FarmRegister`/`FarmSummaryResponse` and
    `router.py::list_vet_assigned_farms`'s `assigned_vet_ids`/
    `assigned_vet_emails` query fields."""
    document: dict[str, Any] = {
        "_id": ObjectId(),
        "owner_name": "Test Farm Owner",
        "email": "farm@example.com",
        "password": "hashed",
        "location_district": "Colombo",
        "registration_number": "REG-TEST-0001",
        "veterinarian_name": "Dr. Test Vet",
        "total_animals": 12,
        "latitude": 6.9271,
        "longitude": 79.8612,
        "assigned_vet_ids": [],
        "assigned_vet_emails": [],
    }
    document.update(overrides)
    return document


def make_diagnostic_case_document(**overrides: Any) -> dict[str, Any]:
    """Shape verified against `origin/main:backend/components/health_anomaly/
    schemas.py::DiagnosticCaseResponse` and
    `router.py::report_diagnostic_case`/`verify_diagnostic_case` — `farm_id`
    is a plain string (`str(farm["_id"])`), never an `ObjectId`."""
    document: dict[str, Any] = {
        "_id": ObjectId(),
        "case_number": "REC-2026-0001",
        "cattle_id": None,
        "farm_id": None,
        "farm_name": "Test Farm",
        "animal_identifier": "COW-001",
        "breed": "Dairy Breed",
        "disease_name": "Lumpy Skin Disease",
        "confidence": 0.92,
        "verified": True,
        "status": "Verified",
        "created_at": "2026-01-01 09:00:00",
        "verified_at": "2026-01-02 10:00:00",
        "vet_id": None,
        "vet_name": "Dr. Test Vet",
        "vet_license": "VET-0001",
    }
    document.update(overrides)
    return document
