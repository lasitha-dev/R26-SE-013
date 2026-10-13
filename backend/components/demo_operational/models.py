"""
Strict Pydantic v2 data contracts for synthetic operational demo data.

Includes models for:
- DemoFarm
- DemoSurveillanceRecord
- DemoAlert
- DemoResponseTask

Enforces strict synthetic markers, ID prefixes, enum constraints, cross-field rules,
and UTC-aware datetimes. Strictly forbids extra fields and scientific ML forecasting outputs.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Any
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)


def _clean_string_array(raw: Any) -> List[str]:
    """Helper to trim strings, remove empty strings, and deduplicate preserving order."""
    if not isinstance(raw, list):
        raise ValueError("Must be a list of strings")
    seen = set()
    cleaned = []
    for item in raw:
        if not isinstance(item, str):
            raise ValueError("Array elements must be strings")
        trimmed = item.strip()
        if trimmed and trimmed not in seen:
            seen.add(trimmed)
            cleaned.append(trimmed)
    return cleaned


def _validate_prefix_id(val: str, prefix: str, field_name: str) -> str:
    """Helper to validate string ID prefixes and non-emptiness."""
    if not isinstance(val, str):
        raise ValueError(f"{field_name} must be a string")
    trimmed = val.strip()
    if not trimmed.startswith(prefix) or len(trimmed) <= len(prefix):
        raise ValueError(f"{field_name} must be a non-empty string starting with '{prefix}'")
    return trimmed


class LivestockType(str, Enum):
    CATTLE = "CATTLE"
    BUFFALO = "BUFFALO"
    GOAT = "GOAT"
    SHEEP = "SHEEP"


class DiseaseCode(str, Enum):
    FMD = "FMD"
    LSD = "LSD"


class EvidenceType(str, Enum):
    FARMER_REPORT = "FARMER_REPORT"
    AI_IMAGE_SCREENING = "AI_IMAGE_SCREENING"
    VET_FIELD_OBSERVATION = "VET_FIELD_OBSERVATION"
    LAB_RESULT = "LAB_RESULT"
    WELLNESS_MONITORING = "WELLNESS_MONITORING"


class VerificationStatus(str, Enum):
    REPORTED = "REPORTED"
    AI_SCREENED = "AI_SCREENED"
    VET_REVIEWED = "VET_REVIEWED"
    LAB_CONFIRMED = "LAB_CONFIRMED"
    REJECTED = "REJECTED"


class SourceModule(str, Enum):
    SYNTHETIC_FARM_REPORTING = "SYNTHETIC_FARM_REPORTING"
    SYNTHETIC_AI_DIAGNOSIS = "SYNTHETIC_AI_DIAGNOSIS"
    SYNTHETIC_WELLNESS_MANAGEMENT = "SYNTHETIC_WELLNESS_MANAGEMENT"
    SYNTHETIC_VETERINARY_SERVICE = "SYNTHETIC_VETERINARY_SERVICE"
    SYNTHETIC_LAB_SERVICE = "SYNTHETIC_LAB_SERVICE"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CLOSED = "CLOSED"


class AlertPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TaskType(str, Enum):
    FIELD_REVIEW = "FIELD_REVIEW"
    SAMPLE_COLLECTION = "SAMPLE_COLLECTION"
    BIOSECURITY_GUIDANCE = "BIOSECURITY_GUIDANCE"
    FOLLOW_UP = "FOLLOW_UP"


class TaskStatus(str, Enum):
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DemoFarm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: str = Field(default="1.0")
    farmId: str
    displayName: str
    district: str
    ownerUserId: str
    assignedVetUserIds: List[str] = Field(default_factory=list)
    livestockTypes: List[LivestockType] = Field(default_factory=list)
    active: StrictBool
    isSynthetic: bool = Field(default=True)
    dataOrigin: str = Field(default="SYNTHETIC_DEMO")
    scientificUseAllowed: bool = Field(default=False)
    createdAt: datetime
    updatedAt: datetime

    @field_validator("schemaVersion")
    @classmethod
    def _validate_schema_version(cls, v: str) -> str:
        if v != "1.0":
            raise ValueError("schemaVersion must be exactly '1.0'")
        return v

    @field_validator("farmId")
    @classmethod
    def _validate_farm_id(cls, v: str) -> str:
        return _validate_prefix_id(v, "DEMO_FARM_", "farmId")

    @field_validator("displayName", "district")
    @classmethod
    def _validate_non_empty_str(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("String field cannot be empty")
        return v.strip()

    @field_validator("ownerUserId")
    @classmethod
    def _validate_owner_user_id(cls, v: str) -> str:
        return _validate_prefix_id(v, "DEMO_USER_", "ownerUserId")

    @field_validator("assignedVetUserIds", mode="before")
    @classmethod
    def _validate_assigned_vets(cls, v: Any) -> List[str]:
        cleaned = _clean_string_array(v)
        for item in cleaned:
            _validate_prefix_id(item, "DEMO_USER_", "assignedVetUserId")
        return cleaned

    @field_validator("livestockTypes", mode="before")
    @classmethod
    def _validate_livestock_types(cls, v: Any) -> List[LivestockType]:
        if not isinstance(v, list):
            raise ValueError("livestockTypes must be a list")
        seen = set()
        cleaned = []
        for item in v:
            enum_val = LivestockType(item) if isinstance(item, str) else item
            if enum_val not in seen:
                seen.add(enum_val)
                cleaned.append(enum_val)
        return cleaned

    @field_validator("isSynthetic")
    @classmethod
    def _validate_is_synthetic(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("isSynthetic must be exactly True")
        return v

    @field_validator("dataOrigin")
    @classmethod
    def _validate_data_origin(cls, v: str) -> str:
        if v != "SYNTHETIC_DEMO":
            raise ValueError("dataOrigin must be exactly 'SYNTHETIC_DEMO'")
        return v

    @field_validator("scientificUseAllowed")
    @classmethod
    def _validate_scientific_use(cls, v: bool) -> bool:
        if v is not False:
            raise ValueError("scientificUseAllowed must be exactly False")
        return v

    @field_validator("createdAt", "updatedAt")
    @classmethod
    def _validate_utc_datetime(cls, v: datetime) -> datetime:
        if not isinstance(v, datetime) or v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("Timestamps must be UTC-aware datetime objects")
        return v


class DemoSurveillanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: str = Field(default="1.0")
    surveillanceRecordId: str
    farmId: str
    district: str
    diseaseCode: DiseaseCode
    observedAt: datetime
    evidenceType: EvidenceType
    verificationStatus: VerificationStatus
    sourceModule: SourceModule
    sourceRecordId: str
    sourceProvidedSeverityLabel: Optional[str] = None
    summary: str
    isSynthetic: bool = Field(default=True)
    dataOrigin: str = Field(default="SYNTHETIC_DEMO")
    scientificUseAllowed: bool = Field(default=False)
    createdAt: datetime
    updatedAt: datetime

    @field_validator("schemaVersion")
    @classmethod
    def _validate_schema_version(cls, v: str) -> str:
        if v != "1.0":
            raise ValueError("schemaVersion must be exactly '1.0'")
        return v

    @field_validator("surveillanceRecordId")
    @classmethod
    def _validate_surv_id(cls, v: str) -> str:
        return _validate_prefix_id(v, "DEMO_SURV_", "surveillanceRecordId")

    @field_validator("farmId")
    @classmethod
    def _validate_farm_id(cls, v: str) -> str:
        return _validate_prefix_id(v, "DEMO_FARM_", "farmId")

    @field_validator("sourceRecordId")
    @classmethod
    def _validate_source_record_id(cls, v: str) -> str:
        return _validate_prefix_id(v, "DEMO_SOURCE_", "sourceRecordId")

    @field_validator("district", "summary")
    @classmethod
    def _validate_non_empty_str(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("String field cannot be empty")
        return v.strip()

    @field_validator("sourceProvidedSeverityLabel", mode="before")
    @classmethod
    def _validate_severity_label(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str) or not v.strip():
            raise ValueError("sourceProvidedSeverityLabel must be a non-empty string if provided")
        return v.strip()

    @field_validator("isSynthetic")
    @classmethod
    def _validate_is_synthetic(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("isSynthetic must be exactly True")
        return v

    @field_validator("dataOrigin")
    @classmethod
    def _validate_data_origin(cls, v: str) -> str:
        if v != "SYNTHETIC_DEMO":
            raise ValueError("dataOrigin must be exactly 'SYNTHETIC_DEMO'")
        return v

    @field_validator("scientificUseAllowed")
    @classmethod
    def _validate_scientific_use(cls, v: bool) -> bool:
        if v is not False:
            raise ValueError("scientificUseAllowed must be exactly False")
        return v

    @field_validator("observedAt", "createdAt", "updatedAt")
    @classmethod
    def _validate_utc_datetime(cls, v: datetime) -> datetime:
        if not isinstance(v, datetime) or v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("Timestamps must be UTC-aware datetime objects")
        return v

    @model_validator(mode="after")
    def _validate_cross_field_rules(self) -> "DemoSurveillanceRecord":
        # Rule 1 & 4: AI_IMAGE_SCREENING may produce AI_SCREENED, never LAB_CONFIRMED
        if self.evidenceType == EvidenceType.AI_IMAGE_SCREENING and self.verificationStatus == VerificationStatus.LAB_CONFIRMED:
            raise ValueError("AI_IMAGE_SCREENING evidence type can never produce LAB_CONFIRMED status")

        # Rule 2: LAB_CONFIRMED requires evidenceType=LAB_RESULT
        if self.verificationStatus == VerificationStatus.LAB_CONFIRMED and self.evidenceType != EvidenceType.LAB_RESULT:
            raise ValueError("LAB_CONFIRMED status requires LAB_RESULT evidenceType")

        # Rule 3: REJECTED may be produced only by VET_FIELD_OBSERVATION or LAB_RESULT
        if self.verificationStatus == VerificationStatus.REJECTED and self.evidenceType not in {
            EvidenceType.VET_FIELD_OBSERVATION,
            EvidenceType.LAB_RESULT,
        }:
            raise ValueError("REJECTED status may only be produced by VET_FIELD_OBSERVATION or LAB_RESULT evidenceType")

        return self


class DemoAlert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: str = Field(default="1.0")
    alertId: str
    district: str
    diseaseCode: DiseaseCode
    status: AlertStatus
    priority: AlertPriority
    issuedAt: datetime
    closedAt: Optional[datetime] = None
    sourceSurveillanceRecordIds: List[str]
    affectedFarmIds: List[str] = Field(default_factory=list)
    title: str
    message: str
    isSynthetic: bool = Field(default=True)
    dataOrigin: str = Field(default="SYNTHETIC_DEMO")
    scientificUseAllowed: bool = Field(default=False)
    createdAt: datetime
    updatedAt: datetime

    @field_validator("schemaVersion")
    @classmethod
    def _validate_schema_version(cls, v: str) -> str:
        if v != "1.0":
            raise ValueError("schemaVersion must be exactly '1.0'")
        return v

    @field_validator("alertId")
    @classmethod
    def _validate_alert_id(cls, v: str) -> str:
        return _validate_prefix_id(v, "DEMO_ALERT_", "alertId")

    @field_validator("district", "title", "message")
    @classmethod
    def _validate_non_empty_str(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("String field cannot be empty")
        return v.strip()

    @field_validator("sourceSurveillanceRecordIds", mode="before")
    @classmethod
    def _validate_source_surv_ids(cls, v: Any) -> List[str]:
        cleaned = _clean_string_array(v)
        if not cleaned:
            raise ValueError("sourceSurveillanceRecordIds cannot be empty")
        for item in cleaned:
            _validate_prefix_id(item, "DEMO_SURV_", "sourceSurveillanceRecordId")
        return cleaned

    @field_validator("affectedFarmIds", mode="before")
    @classmethod
    def _validate_affected_farm_ids(cls, v: Any) -> List[str]:
        cleaned = _clean_string_array(v)
        for item in cleaned:
            _validate_prefix_id(item, "DEMO_FARM_", "affectedFarmId")
        return cleaned

    @field_validator("isSynthetic")
    @classmethod
    def _validate_is_synthetic(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("isSynthetic must be exactly True")
        return v

    @field_validator("dataOrigin")
    @classmethod
    def _validate_data_origin(cls, v: str) -> str:
        if v != "SYNTHETIC_DEMO":
            raise ValueError("dataOrigin must be exactly 'SYNTHETIC_DEMO'")
        return v

    @field_validator("scientificUseAllowed")
    @classmethod
    def _validate_scientific_use(cls, v: bool) -> bool:
        if v is not False:
            raise ValueError("scientificUseAllowed must be exactly False")
        return v

    @field_validator("issuedAt", "createdAt", "updatedAt")
    @classmethod
    def _validate_utc_datetime(cls, v: datetime) -> datetime:
        if not isinstance(v, datetime) or v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("Timestamps must be UTC-aware datetime objects")
        return v

    @field_validator("closedAt", mode="before")
    @classmethod
    def _validate_optional_closed_at(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if not isinstance(v, datetime) or v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("closedAt timestamp must be a UTC-aware datetime object")
        return v

    @model_validator(mode="after")
    def _validate_alert_lifecycle(self) -> "DemoAlert":
        if self.status == AlertStatus.CLOSED and self.closedAt is None:
            raise ValueError("CLOSED alert requires a non-null closedAt timestamp")
        if self.status in {AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED} and self.closedAt is not None:
            raise ValueError("OPEN or ACKNOWLEDGED alert must not have a closedAt timestamp")
        return self


class DemoResponseTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: str = Field(default="1.0")
    responseTaskId: str
    alertId: str
    assignedOfficerUserId: str
    district: str
    farmId: Optional[str] = None
    taskType: TaskType
    status: TaskStatus
    dueAt: datetime
    completedAt: Optional[datetime] = None
    notes: str
    isSynthetic: bool = Field(default=True)
    dataOrigin: str = Field(default="SYNTHETIC_DEMO")
    scientificUseAllowed: bool = Field(default=False)
    createdAt: datetime
    updatedAt: datetime

    @field_validator("schemaVersion")
    @classmethod
    def _validate_schema_version(cls, v: str) -> str:
        if v != "1.0":
            raise ValueError("schemaVersion must be exactly '1.0'")
        return v

    @field_validator("responseTaskId")
    @classmethod
    def _validate_task_id(cls, v: str) -> str:
        return _validate_prefix_id(v, "DEMO_TASK_", "responseTaskId")

    @field_validator("alertId")
    @classmethod
    def _validate_alert_id(cls, v: str) -> str:
        return _validate_prefix_id(v, "DEMO_ALERT_", "alertId")

    @field_validator("assignedOfficerUserId")
    @classmethod
    def _validate_officer_id(cls, v: str) -> str:
        return _validate_prefix_id(v, "DEMO_USER_", "assignedOfficerUserId")

    @field_validator("farmId", mode="before")
    @classmethod
    def _validate_optional_farm_id(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return _validate_prefix_id(v, "DEMO_FARM_", "farmId")

    @field_validator("district", "notes")
    @classmethod
    def _validate_non_empty_str(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("String field cannot be empty")
        return v.strip()

    @field_validator("isSynthetic")
    @classmethod
    def _validate_is_synthetic(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("isSynthetic must be exactly True")
        return v

    @field_validator("dataOrigin")
    @classmethod
    def _validate_data_origin(cls, v: str) -> str:
        if v != "SYNTHETIC_DEMO":
            raise ValueError("dataOrigin must be exactly 'SYNTHETIC_DEMO'")
        return v

    @field_validator("scientificUseAllowed")
    @classmethod
    def _validate_scientific_use(cls, v: bool) -> bool:
        if v is not False:
            raise ValueError("scientificUseAllowed must be exactly False")
        return v

    @field_validator("dueAt", "createdAt", "updatedAt")
    @classmethod
    def _validate_utc_datetime(cls, v: datetime) -> datetime:
        if not isinstance(v, datetime) or v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("Timestamps must be UTC-aware datetime objects")
        return v

    @field_validator("completedAt", mode="before")
    @classmethod
    def _validate_optional_completed_at(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if not isinstance(v, datetime) or v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("completedAt timestamp must be a UTC-aware datetime object")
        return v

    @model_validator(mode="after")
    def _validate_task_lifecycle(self) -> "DemoResponseTask":
        if self.status == TaskStatus.COMPLETED and self.completedAt is None:
            raise ValueError("COMPLETED response task requires a non-null completedAt timestamp")
        if self.status in {TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS} and self.completedAt is not None:
            raise ValueError("ASSIGNED or IN_PROGRESS task must not have a completedAt timestamp")
        return self
