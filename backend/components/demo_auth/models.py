"""
Data contracts for Disease Forecasting demo authentication and frontend ViewerContext integration.

Includes strict Pydantic v2 models for:
- DemoAuthorization
- DemoPermissions
- DemoUserDocument
- ViewerContextResponse

Enforces role/scope compatibility, strict boolean validation, string trimming/deduplication,
and secret redaction for password hashes and internal fields.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Any
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


class Role(str, Enum):
    FARMER = "FARMER"
    VETERINARY_OFFICER = "VETERINARY_OFFICER"
    DAPH_OFFICIAL = "DAPH_OFFICIAL"


class ScopeLevel(str, Enum):
    FARM = "FARM"
    DISTRICT = "DISTRICT"
    PROVINCE = "PROVINCE"
    NATIONAL = "NATIONAL"


class PermissionName(str, Enum):
    viewDataQuality = "viewDataQuality"
    viewModelTransparency = "viewModelTransparency"
    manageAlerts = "manageAlerts"
    recordResponse = "recordResponse"
    viewReports = "viewReports"


ROLE_ALLOWED_SCOPES = {
    Role.FARMER: {ScopeLevel.FARM},
    Role.VETERINARY_OFFICER: {ScopeLevel.DISTRICT, ScopeLevel.PROVINCE},
    Role.DAPH_OFFICIAL: {ScopeLevel.DISTRICT, ScopeLevel.PROVINCE, ScopeLevel.NATIONAL},
}


def _clean_string_array(raw: Any) -> List[str]:
    """Helper to trim strings, remove empty strings, and deduplicate preserving order."""
    if not isinstance(raw, list):
        raise ValueError("Must be a list")
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


class DemoAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scopeLevel: ScopeLevel
    registeredFarmDistrict: Optional[str] = None
    authorizedDistricts: List[str] = Field(default_factory=list)
    assignedFarmIds: List[str] = Field(default_factory=list)

    @field_validator("registeredFarmDistrict", mode="before")
    @classmethod
    def _validate_registered_farm_district(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("registeredFarmDistrict must be a string")
        trimmed = v.strip()
        return trimmed if trimmed else None

    @field_validator("authorizedDistricts", "assignedFarmIds", mode="before")
    @classmethod
    def _validate_string_arrays(cls, v: Any) -> List[str]:
        if not isinstance(v, list):
            raise ValueError("Must be a list of strings")
        return _clean_string_array(v)


class DemoPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    viewDataQuality: StrictBool
    viewModelTransparency: StrictBool
    manageAlerts: StrictBool
    recordResponse: StrictBool
    viewReports: StrictBool


class ViewerContextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    userId: StrictStr
    role: Role
    authorization: DemoAuthorization
    permissions: DemoPermissions


class DemoUserDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: str = Field(default="1.0")
    userId: StrictStr
    loginName: StrictStr
    passwordHash: StrictStr
    role: Role
    authorization: DemoAuthorization
    permissions: DemoPermissions
    enabled: StrictBool
    tokenVersion: StrictInt = Field(default=1)
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

    @field_validator("userId")
    @classmethod
    def _validate_user_id(cls, v: str) -> str:
        if not v.startswith("DEMO_USER_") or len(v) <= 10 or not v.strip():
            raise ValueError("userId must be a non-empty string starting with 'DEMO_USER_'")
        return v.strip()

    @field_validator("loginName")
    @classmethod
    def _validate_login_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("loginName cannot be empty")
        return trimmed.lower()

    @field_validator("passwordHash")
    @classmethod
    def _validate_password_hash(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("passwordHash cannot be empty")
        return trimmed

    @field_validator("tokenVersion")
    @classmethod
    def _validate_token_version(cls, v: int) -> int:
        if v < 1:
            raise ValueError("tokenVersion must be a positive integer >= 1")
        return v

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

    @model_validator(mode="after")
    def _validate_role_and_authorization_compatibility(self) -> "DemoUserDocument":
        role = self.role
        auth = self.authorization

        # 1. Role / scope compatibility
        allowed_scopes = ROLE_ALLOWED_SCOPES.get(role, set())
        if auth.scopeLevel not in allowed_scopes:
            raise ValueError(f"Incompatible scopeLevel '{auth.scopeLevel}' for role '{role}'")

        # 2. Role-specific authorization adjustments and validations
        if role == Role.FARMER:
            if not auth.registeredFarmDistrict:
                raise ValueError("FARMER role requires a valid non-empty registeredFarmDistrict")
            auth.authorizedDistricts = [auth.registeredFarmDistrict]
            auth.assignedFarmIds = []

        elif role == Role.VETERINARY_OFFICER:
            auth.registeredFarmDistrict = None
            if not auth.authorizedDistricts:
                raise ValueError("VETERINARY_OFFICER role requires at least one authorized district")

        elif role == Role.DAPH_OFFICIAL:
            auth.registeredFarmDistrict = None
            auth.assignedFarmIds = []
            if not auth.authorizedDistricts:
                raise ValueError("DAPH_OFFICIAL role requires explicit authorized districts")

        return self

    def __repr__(self) -> str:
        return (
            f"DemoUserDocument(userId={self.userId!r}, "
            f"loginName={self.loginName!r}, "
            f"role={self.role.value!r}, "
            f"passwordHash='[REDACTED]')"
        )

    def __str__(self) -> str:
        return self.__repr__()

    def to_viewer_context(self) -> ViewerContextResponse:
        return demo_user_to_viewer_context(self)


def demo_user_to_viewer_context(user: DemoUserDocument) -> ViewerContextResponse:
    """
    Converts a DemoUserDocument into the exact ViewerContext response required by the frontend.
    Excludes passwordHash, loginName, tokenVersion, internal metadata.
    """
    if not isinstance(user, DemoUserDocument):
        raise ValueError("user must be a DemoUserDocument instance")

    return ViewerContextResponse(
        userId=user.userId,
        role=user.role,
        authorization=user.authorization,
        permissions=user.permissions,
    )
