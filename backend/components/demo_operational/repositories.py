"""
Asynchronous MongoDB Repositories for synthetic operational demo records.

Provides isolated data access for:
- DemoFarmRepository ('demo_farms')
- DemoSurveillanceRepository ('demo_surveillance_records')
- DemoAlertRepository ('demo_alerts')
- DemoResponseTaskRepository ('demo_response_tasks')

Enforces strict synthetic filtering, input safety, bounded pagination, tie-breaker sorting,
and sanitized error handling.
"""

from typing import List, Optional, Any, Dict, Type, TypeVar
from pydantic import BaseModel

from backend.components.demo_operational.models import (
    DemoFarm,
    DemoSurveillanceRecord,
    DemoAlert,
    DemoResponseTask,
)

T = TypeVar("T", bound=BaseModel)


class DemoOperationalRepositoryError(ValueError):
    """Sanitized exception for demo operational repository failures."""
    pass


class DemoOperationalDuplicateError(DemoOperationalRepositoryError):
    """Sanitized exception when attempting to insert or replace a duplicate operational record."""
    pass


def _validate_prefix_id(val: Any, prefix: str, field_name: str) -> str:
    if not isinstance(val, str) or not val.strip():
        raise DemoOperationalRepositoryError(f"Invalid {field_name}: Must be a non-empty string.")
    trimmed = val.strip()
    if not trimmed.startswith(prefix) or len(trimmed) <= len(prefix):
        raise DemoOperationalRepositoryError(f"Invalid {field_name}: Must start with '{prefix}'.")
    return trimmed


def _validate_non_empty_str(val: Any, field_name: str) -> str:
    if not isinstance(val, str) or not val.strip():
        raise DemoOperationalRepositoryError(f"Invalid {field_name}: Must be a non-empty string.")
    return val.strip()


def _clean_and_dedup_strings(raw: Any, field_name: str) -> List[str]:
    if not isinstance(raw, list):
        raise DemoOperationalRepositoryError(f"Invalid {field_name}: Must be a list.")
    cleaned = []
    seen = set()
    for item in raw:
        clean_str = _validate_non_empty_str(item, f"element in {field_name}")
        if clean_str not in seen:
            seen.add(clean_str)
            cleaned.append(clean_str)
    return cleaned


def _clean_and_dedup_prefix_ids(raw: Any, prefix: str, field_name: str) -> List[str]:
    if not isinstance(raw, list):
        raise DemoOperationalRepositoryError(f"Invalid {field_name}: Must be a list.")
    cleaned = []
    seen = set()
    for item in raw:
        clean_id = _validate_prefix_id(item, prefix, f"element in {field_name}")
        if clean_id not in seen:
            seen.add(clean_id)
            cleaned.append(clean_id)
    return cleaned


def _validate_pagination(skip: int, limit: int) -> tuple[int, int]:
    if not isinstance(skip, int) or isinstance(skip, bool) or skip < 0:
        raise DemoOperationalRepositoryError("Invalid skip: Must be a non-negative integer.")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise DemoOperationalRepositoryError("Invalid limit: Must be a positive integer.")
    if limit > 100:
        raise DemoOperationalRepositoryError("Invalid limit: Maximum allowed limit is 100.")
    return skip, limit


def _to_pydantic_model(doc: Dict[str, Any], model_cls: Type[T]) -> T:
    clean_doc = dict(doc)
    clean_doc.pop("_id", None)
    try:
        return model_cls(**clean_doc)
    except Exception:
        raise DemoOperationalRepositoryError("Database document is corrupt or invalid.") from None


class DemoFarmRepository:
    COLLECTION_NAME = "demo_farms"

    def __init__(self, db: Any):
        if db is None:
            raise DemoOperationalRepositoryError("Database instance is required.")
        self._db = db
        self._collection = db[self.COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        try:
            await self._collection.create_index(
                [("farmId", 1)],
                unique=True,
                name="idx_demo_farms_farm_id_unique",
            )
            await self._collection.create_index(
                [("ownerUserId", 1)],
                name="idx_demo_farms_owner_user_id",
            )
            await self._collection.create_index(
                [("assignedVetUserIds", 1)],
                name="idx_demo_farms_assigned_vet_user_ids",
            )
            await self._collection.create_index(
                [("district", 1)],
                name="idx_demo_farms_district",
            )
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Failed to ensure farm indexes ({exc.__class__.__name__})") from None

    async def find_by_farm_id(self, farm_id: str) -> Optional[DemoFarm]:
        clean_id = _validate_prefix_id(farm_id, "DEMO_FARM_", "farmId")
        query_filter = {
            "farmId": clean_id,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            doc = await self._collection.find_one(query_filter)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None
        if doc is None:
            return None
        return _to_pydantic_model(doc, DemoFarm)

    async def list_by_owner_user_id(self, owner_user_id: str, skip: int = 0, limit: int = 50) -> List[DemoFarm]:
        clean_user_id = _validate_prefix_id(owner_user_id, "DEMO_USER_", "ownerUserId")
        skip_val, limit_val = _validate_pagination(skip, limit)

        query_filter = {
            "ownerUserId": clean_user_id,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            cursor = self._collection.find(query_filter).sort([("farmId", 1)]).skip(skip_val).limit(limit_val)
            docs = await cursor.to_list(length=limit_val)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None

        return [_to_pydantic_model(doc, DemoFarm) for doc in docs]

    async def list_by_assigned_vet_user_id(self, vet_user_id: str, skip: int = 0, limit: int = 50) -> List[DemoFarm]:
        clean_vet_id = _validate_prefix_id(vet_user_id, "DEMO_USER_", "vet_user_id")
        skip_val, limit_val = _validate_pagination(skip, limit)

        query_filter = {
            "assignedVetUserIds": clean_vet_id,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            cursor = self._collection.find(query_filter).sort([("farmId", 1)]).skip(skip_val).limit(limit_val)
            docs = await cursor.to_list(length=limit_val)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None

        return [_to_pydantic_model(doc, DemoFarm) for doc in docs]

    async def list_by_farm_ids(self, farm_ids: List[str], skip: int = 0, limit: int = 50) -> List[DemoFarm]:
        cleaned_ids = _clean_and_dedup_prefix_ids(farm_ids, "DEMO_FARM_", "farm_ids")
        if not cleaned_ids:
            return []
        skip_val, limit_val = _validate_pagination(skip, limit)

        query_filter = {
            "farmId": {"$in": cleaned_ids},
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            cursor = self._collection.find(query_filter).sort([("farmId", 1)]).skip(skip_val).limit(limit_val)
            docs = await cursor.to_list(length=limit_val)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None

        return [_to_pydantic_model(doc, DemoFarm) for doc in docs]

    async def insert_farm(self, farm: DemoFarm) -> DemoFarm:
        if not isinstance(farm, DemoFarm):
            raise DemoOperationalRepositoryError("farm must be a valid DemoFarm instance.")
        doc = farm.model_dump()
        try:
            await self._collection.insert_one(doc)
            return farm
        except Exception as exc:
            if "duplicate" in str(exc).lower() or exc.__class__.__name__ == "DuplicateKeyError":
                raise DemoOperationalDuplicateError("Farm with this farmId already exists.") from None
            raise DemoOperationalRepositoryError(f"Failed to insert farm ({exc.__class__.__name__})") from None

    async def replace_farm(self, farm: DemoFarm, upsert: bool = False) -> DemoFarm:
        if not isinstance(farm, DemoFarm):
            raise DemoOperationalRepositoryError("farm must be a valid DemoFarm instance.")
        query_filter = {
            "farmId": farm.farmId,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        doc = farm.model_dump()
        try:
            res = await self._collection.replace_one(query_filter, doc, upsert=upsert)
            if not upsert and hasattr(res, "matched_count") and res.matched_count == 0:
                raise DemoOperationalRepositoryError("No matching farm found to replace.")
            return farm
        except DemoOperationalRepositoryError:
            raise
        except Exception as exc:
            if "duplicate" in str(exc).lower() or exc.__class__.__name__ == "DuplicateKeyError":
                raise DemoOperationalDuplicateError("Duplicate key constraint violated on farm replace.") from None
            raise DemoOperationalRepositoryError(f"Failed to replace farm ({exc.__class__.__name__})") from None

    def __repr__(self) -> str:
        return f"DemoFarmRepository(collection={self.COLLECTION_NAME!r})"


class DemoSurveillanceRepository:
    COLLECTION_NAME = "demo_surveillance_records"

    def __init__(self, db: Any):
        if db is None:
            raise DemoOperationalRepositoryError("Database instance is required.")
        self._db = db
        self._collection = db[self.COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        try:
            await self._collection.create_index(
                [("surveillanceRecordId", 1)],
                unique=True,
                name="idx_demo_surveillance_record_id_unique",
            )
            await self._collection.create_index(
                [("farmId", 1), ("observedAt", -1)],
                name="idx_demo_surveillance_farm_observed",
            )
            await self._collection.create_index(
                [("district", 1), ("observedAt", -1)],
                name="idx_demo_surveillance_district_observed",
            )
            await self._collection.create_index(
                [("verificationStatus", 1)],
                name="idx_demo_surveillance_status",
            )
        except Exception as exc:
            raise DemoOperationalRepositoryError(
                f"Failed to ensure surveillance indexes ({exc.__class__.__name__})"
            ) from None

    async def find_by_record_id(self, record_id: str) -> Optional[DemoSurveillanceRecord]:
        clean_id = _validate_prefix_id(record_id, "DEMO_SURV_", "surveillanceRecordId")
        query_filter = {
            "surveillanceRecordId": clean_id,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            doc = await self._collection.find_one(query_filter)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None
        if doc is None:
            return None
        return _to_pydantic_model(doc, DemoSurveillanceRecord)

    async def list_by_farm_ids(self, farm_ids: List[str], skip: int = 0, limit: int = 50) -> List[DemoSurveillanceRecord]:
        cleaned_ids = _clean_and_dedup_prefix_ids(farm_ids, "DEMO_FARM_", "farm_ids")
        if not cleaned_ids:
            return []
        skip_val, limit_val = _validate_pagination(skip, limit)

        query_filter = {
            "farmId": {"$in": cleaned_ids},
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            cursor = (
                self._collection.find(query_filter)
                .sort([("observedAt", -1), ("surveillanceRecordId", 1)])
                .skip(skip_val)
                .limit(limit_val)
            )
            docs = await cursor.to_list(length=limit_val)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None

        return [_to_pydantic_model(doc, DemoSurveillanceRecord) for doc in docs]

    async def list_by_districts(self, districts: List[str], skip: int = 0, limit: int = 50) -> List[DemoSurveillanceRecord]:
        cleaned_districts = _clean_and_dedup_strings(districts, "districts")
        if not cleaned_districts:
            return []
        skip_val, limit_val = _validate_pagination(skip, limit)

        query_filter = {
            "district": {"$in": cleaned_districts},
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            cursor = (
                self._collection.find(query_filter)
                .sort([("observedAt", -1), ("surveillanceRecordId", 1)])
                .skip(skip_val)
                .limit(limit_val)
            )
            docs = await cursor.to_list(length=limit_val)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None

        return [_to_pydantic_model(doc, DemoSurveillanceRecord) for doc in docs]

    async def insert_record(self, record: DemoSurveillanceRecord) -> DemoSurveillanceRecord:
        if not isinstance(record, DemoSurveillanceRecord):
            raise DemoOperationalRepositoryError("record must be a valid DemoSurveillanceRecord instance.")
        doc = record.model_dump()
        try:
            await self._collection.insert_one(doc)
            return record
        except Exception as exc:
            if "duplicate" in str(exc).lower() or exc.__class__.__name__ == "DuplicateKeyError":
                raise DemoOperationalDuplicateError("Surveillance record with this ID already exists.") from None
            raise DemoOperationalRepositoryError(f"Failed to insert record ({exc.__class__.__name__})") from None

    async def replace_record(self, record: DemoSurveillanceRecord, upsert: bool = False) -> DemoSurveillanceRecord:
        if not isinstance(record, DemoSurveillanceRecord):
            raise DemoOperationalRepositoryError("record must be a valid DemoSurveillanceRecord instance.")
        query_filter = {
            "surveillanceRecordId": record.surveillanceRecordId,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        doc = record.model_dump()
        try:
            res = await self._collection.replace_one(query_filter, doc, upsert=upsert)
            if not upsert and hasattr(res, "matched_count") and res.matched_count == 0:
                raise DemoOperationalRepositoryError("No matching surveillance record found to replace.")
            return record
        except DemoOperationalRepositoryError:
            raise
        except Exception as exc:
            if "duplicate" in str(exc).lower() or exc.__class__.__name__ == "DuplicateKeyError":
                raise DemoOperationalDuplicateError("Duplicate key constraint violated on record replace.") from None
            raise DemoOperationalRepositoryError(f"Failed to replace record ({exc.__class__.__name__})") from None

    def __repr__(self) -> str:
        return f"DemoSurveillanceRepository(collection={self.COLLECTION_NAME!r})"


class DemoAlertRepository:
    COLLECTION_NAME = "demo_alerts"

    def __init__(self, db: Any):
        if db is None:
            raise DemoOperationalRepositoryError("Database instance is required.")
        self._db = db
        self._collection = db[self.COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        try:
            await self._collection.create_index(
                [("alertId", 1)],
                unique=True,
                name="idx_demo_alerts_alert_id_unique",
            )
            await self._collection.create_index(
                [("affectedFarmIds", 1), ("issuedAt", -1)],
                name="idx_demo_alerts_farm_issued",
            )
            await self._collection.create_index(
                [("district", 1), ("issuedAt", -1)],
                name="idx_demo_alerts_district_issued",
            )
            await self._collection.create_index(
                [("status", 1)],
                name="idx_demo_alerts_status",
            )
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Failed to ensure alert indexes ({exc.__class__.__name__})") from None

    async def find_by_alert_id(self, alert_id: str) -> Optional[DemoAlert]:
        clean_id = _validate_prefix_id(alert_id, "DEMO_ALERT_", "alertId")
        query_filter = {
            "alertId": clean_id,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            doc = await self._collection.find_one(query_filter)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None
        if doc is None:
            return None
        return _to_pydantic_model(doc, DemoAlert)

    async def list_by_farm_ids(self, farm_ids: List[str], skip: int = 0, limit: int = 50) -> List[DemoAlert]:
        cleaned_ids = _clean_and_dedup_prefix_ids(farm_ids, "DEMO_FARM_", "farm_ids")
        if not cleaned_ids:
            return []
        skip_val, limit_val = _validate_pagination(skip, limit)

        query_filter = {
            "affectedFarmIds": {"$in": cleaned_ids},
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            cursor = (
                self._collection.find(query_filter)
                .sort([("issuedAt", -1), ("alertId", 1)])
                .skip(skip_val)
                .limit(limit_val)
            )
            docs = await cursor.to_list(length=limit_val)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None

        return [_to_pydantic_model(doc, DemoAlert) for doc in docs]

    async def list_by_districts(self, districts: List[str], skip: int = 0, limit: int = 50) -> List[DemoAlert]:
        cleaned_districts = _clean_and_dedup_strings(districts, "districts")
        if not cleaned_districts:
            return []
        skip_val, limit_val = _validate_pagination(skip, limit)

        query_filter = {
            "district": {"$in": cleaned_districts},
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            cursor = (
                self._collection.find(query_filter)
                .sort([("issuedAt", -1), ("alertId", 1)])
                .skip(skip_val)
                .limit(limit_val)
            )
            docs = await cursor.to_list(length=limit_val)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None

        return [_to_pydantic_model(doc, DemoAlert) for doc in docs]

    async def insert_alert(self, alert: DemoAlert) -> DemoAlert:
        if not isinstance(alert, DemoAlert):
            raise DemoOperationalRepositoryError("alert must be a valid DemoAlert instance.")
        doc = alert.model_dump()
        try:
            await self._collection.insert_one(doc)
            return alert
        except Exception as exc:
            if "duplicate" in str(exc).lower() or exc.__class__.__name__ == "DuplicateKeyError":
                raise DemoOperationalDuplicateError("Alert with this alertId already exists.") from None
            raise DemoOperationalRepositoryError(f"Failed to insert alert ({exc.__class__.__name__})") from None

    async def replace_alert(self, alert: DemoAlert, upsert: bool = False) -> DemoAlert:
        if not isinstance(alert, DemoAlert):
            raise DemoOperationalRepositoryError("alert must be a valid DemoAlert instance.")
        query_filter = {
            "alertId": alert.alertId,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        doc = alert.model_dump()
        try:
            res = await self._collection.replace_one(query_filter, doc, upsert=upsert)
            if not upsert and hasattr(res, "matched_count") and res.matched_count == 0:
                raise DemoOperationalRepositoryError("No matching alert found to replace.")
            return alert
        except DemoOperationalRepositoryError:
            raise
        except Exception as exc:
            if "duplicate" in str(exc).lower() or exc.__class__.__name__ == "DuplicateKeyError":
                raise DemoOperationalDuplicateError("Duplicate key constraint violated on alert replace.") from None
            raise DemoOperationalRepositoryError(f"Failed to replace alert ({exc.__class__.__name__})") from None

    def __repr__(self) -> str:
        return f"DemoAlertRepository(collection={self.COLLECTION_NAME!r})"


class DemoResponseTaskRepository:
    COLLECTION_NAME = "demo_response_tasks"

    def __init__(self, db: Any):
        if db is None:
            raise DemoOperationalRepositoryError("Database instance is required.")
        self._db = db
        self._collection = db[self.COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        try:
            await self._collection.create_index(
                [("responseTaskId", 1)],
                unique=True,
                name="idx_demo_tasks_task_id_unique",
            )
            await self._collection.create_index(
                [("assignedOfficerUserId", 1), ("status", 1)],
                name="idx_demo_tasks_officer_status",
            )
            await self._collection.create_index(
                [("district", 1), ("dueAt", 1)],
                name="idx_demo_tasks_district_due",
            )
            await self._collection.create_index(
                [("alertId", 1)],
                name="idx_demo_tasks_alert_id",
            )
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Failed to ensure task indexes ({exc.__class__.__name__})") from None

    async def find_by_task_id(self, task_id: str) -> Optional[DemoResponseTask]:
        clean_id = _validate_prefix_id(task_id, "DEMO_TASK_", "responseTaskId")
        query_filter = {
            "responseTaskId": clean_id,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            doc = await self._collection.find_one(query_filter)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None
        if doc is None:
            return None
        return _to_pydantic_model(doc, DemoResponseTask)

    async def list_by_assigned_officer_user_id(
        self, user_id: str, skip: int = 0, limit: int = 50
    ) -> List[DemoResponseTask]:
        clean_user_id = _validate_prefix_id(user_id, "DEMO_USER_", "assignedOfficerUserId")
        skip_val, limit_val = _validate_pagination(skip, limit)

        query_filter = {
            "assignedOfficerUserId": clean_user_id,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            cursor = (
                self._collection.find(query_filter)
                .sort([("dueAt", 1), ("responseTaskId", 1)])
                .skip(skip_val)
                .limit(limit_val)
            )
            docs = await cursor.to_list(length=limit_val)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None

        return [_to_pydantic_model(doc, DemoResponseTask) for doc in docs]

    async def list_by_districts(
        self, districts: List[str], skip: int = 0, limit: int = 50
    ) -> List[DemoResponseTask]:
        cleaned_districts = _clean_and_dedup_strings(districts, "districts")
        if not cleaned_districts:
            return []
        skip_val, limit_val = _validate_pagination(skip, limit)

        query_filter = {
            "district": {"$in": cleaned_districts},
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        try:
            cursor = (
                self._collection.find(query_filter)
                .sort([("dueAt", 1), ("responseTaskId", 1)])
                .skip(skip_val)
                .limit(limit_val)
            )
            docs = await cursor.to_list(length=limit_val)
        except Exception as exc:
            raise DemoOperationalRepositoryError(f"Database query error ({exc.__class__.__name__})") from None

        return [_to_pydantic_model(doc, DemoResponseTask) for doc in docs]

    async def insert_task(self, task: DemoResponseTask) -> DemoResponseTask:
        if not isinstance(task, DemoResponseTask):
            raise DemoOperationalRepositoryError("task must be a valid DemoResponseTask instance.")
        doc = task.model_dump()
        try:
            await self._collection.insert_one(doc)
            return task
        except Exception as exc:
            if "duplicate" in str(exc).lower() or exc.__class__.__name__ == "DuplicateKeyError":
                raise DemoOperationalDuplicateError("Response task with this task ID already exists.") from None
            raise DemoOperationalRepositoryError(f"Failed to insert task ({exc.__class__.__name__})") from None

    async def replace_task(self, task: DemoResponseTask, upsert: bool = False) -> DemoResponseTask:
        if not isinstance(task, DemoResponseTask):
            raise DemoOperationalRepositoryError("task must be a valid DemoResponseTask instance.")
        query_filter = {
            "responseTaskId": task.responseTaskId,
            "isSynthetic": True,
            "dataOrigin": "SYNTHETIC_DEMO",
        }
        doc = task.model_dump()
        try:
            res = await self._collection.replace_one(query_filter, doc, upsert=upsert)
            if not upsert and hasattr(res, "matched_count") and res.matched_count == 0:
                raise DemoOperationalRepositoryError("No matching task found to replace.")
            return task
        except DemoOperationalRepositoryError:
            raise
        except Exception as exc:
            if "duplicate" in str(exc).lower() or exc.__class__.__name__ == "DuplicateKeyError":
                raise DemoOperationalDuplicateError("Duplicate key constraint violated on task replace.") from None
            raise DemoOperationalRepositoryError(f"Failed to replace task ({exc.__class__.__name__})") from None

    def __repr__(self) -> str:
        return f"DemoResponseTaskRepository(collection={self.COLLECTION_NAME!r})"
