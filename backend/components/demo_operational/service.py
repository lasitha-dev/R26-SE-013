"""
Server-side authorization service for synthetic operational demo data.

Applies strict role, permission, district, and farm scope authorization rules.
Injects repositories; never creates database clients or reads environment secrets.
Includes defence-in-depth post-filtering and sanitized error handling.
"""

from typing import List, Optional
from backend.components.demo_auth.models import (
    Role,
    ScopeLevel,
    DemoUserDocument,
    ROLE_ALLOWED_SCOPES,
)
from backend.components.demo_operational.models import (
    DemoFarm,
    DemoSurveillanceRecord,
    DemoAlert,
    DemoResponseTask,
)
from backend.components.demo_operational.repositories import (
    DemoFarmRepository,
    DemoSurveillanceRepository,
    DemoAlertRepository,
    DemoResponseTaskRepository,
    DemoOperationalRepositoryError,
)


class DemoOperationalForbiddenError(Exception):
    """Sanitized exception raised when user identity or role is not authorized for requested data."""
    def __init__(self, message: str = "Access to requested operational data is forbidden."):
        super().__init__(message)


class DemoOperationalUnavailableError(Exception):
    """Sanitized exception raised when operational repository operations fail."""
    def __init__(self, message: str = "Operational data service is currently unavailable."):
        super().__init__(message)


class DemoOperationalAuthorizationService:
    """
    Authorization service for synthetic operational data access.
    Enforces RBAC and scope filtering on top of operational repositories.
    """

    def __init__(
        self,
        farm_repo: DemoFarmRepository,
        surv_repo: DemoSurveillanceRepository,
        alert_repo: DemoAlertRepository,
        task_repo: DemoResponseTaskRepository,
    ):
        self._farm_repo = farm_repo
        self._surv_repo = surv_repo
        self._alert_repo = alert_repo
        self._task_repo = task_repo

    def _validate_user(self, current_user: DemoUserDocument) -> None:
        """Validates that current_user is an enabled DemoUserDocument with valid role/scope combination."""
        if not isinstance(current_user, DemoUserDocument):
            raise DemoOperationalForbiddenError("Invalid user identity document.")

        if not current_user.enabled:
            raise DemoOperationalForbiddenError("User account is disabled.")

        allowed_scopes = ROLE_ALLOWED_SCOPES.get(current_user.role, set())
        if current_user.authorization.scopeLevel not in allowed_scopes:
            raise DemoOperationalForbiddenError("Incompatible user role and scope combination.")

    async def get_accessible_farms(
        self,
        current_user: DemoUserDocument,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DemoFarm]:
        """
        Retrieves farms accessible to current_user.
        - FARMER: owned farms in registeredFarmDistrict.
        - VETERINARY_OFFICER: assigned farms in authorizedDistricts containing Vet in assignedVetUserIds.
        - DAPH_OFFICIAL: Forbidden.
        """
        self._validate_user(current_user)

        try:
            if current_user.role == Role.FARMER:
                reg_district = current_user.authorization.registeredFarmDistrict
                if not reg_district:
                    return []
                raw_farms = await self._farm_repo.list_by_owner_user_id(
                    current_user.userId, skip=skip, limit=limit
                )
                # Post-filter
                return [
                    f
                    for f in raw_farms
                    if f.ownerUserId == current_user.userId and f.district == reg_district
                ]

            elif current_user.role == Role.VETERINARY_OFFICER:
                assigned_farm_ids = current_user.authorization.assignedFarmIds
                authorized_districts = set(current_user.authorization.authorizedDistricts)
                if not assigned_farm_ids or not authorized_districts:
                    return []
                raw_farms = await self._farm_repo.list_by_farm_ids(
                    assigned_farm_ids, skip=skip, limit=limit
                )
                # Post-filter
                return [
                    f
                    for f in raw_farms
                    if f.farmId in assigned_farm_ids
                    and f.district in authorized_districts
                    and current_user.userId in f.assignedVetUserIds
                ]

            elif current_user.role == Role.DAPH_OFFICIAL:
                raise DemoOperationalForbiddenError(
                    "Farm listing is not accessible for DAPH official context."
                )

            else:
                raise DemoOperationalForbiddenError()

        except (DemoOperationalForbiddenError, DemoOperationalUnavailableError):
            raise
        except DemoOperationalRepositoryError:
            raise DemoOperationalUnavailableError()
        except Exception:
            raise DemoOperationalUnavailableError()

    async def get_accessible_surveillance_records(
        self,
        current_user: DemoUserDocument,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DemoSurveillanceRecord]:
        """
        Retrieves surveillance records accessible to current_user.
        - FARMER: Forbidden.
        - VETERINARY_OFFICER: surveillance records for accessible farms in authorizedDistricts.
        - DAPH_OFFICIAL: surveillance records in authorizedDistricts.
        """
        self._validate_user(current_user)

        try:
            if current_user.role == Role.FARMER:
                raise DemoOperationalForbiddenError(
                    "Clinical surveillance records are forbidden for farmer role."
                )

            elif current_user.role == Role.VETERINARY_OFFICER:
                accessible_farms = await self.get_accessible_farms(
                    current_user, skip=0, limit=100
                )
                farm_ids = [f.farmId for f in accessible_farms]
                authorized_districts = set(current_user.authorization.authorizedDistricts)
                if not farm_ids or not authorized_districts:
                    return []
                raw_records = await self._surv_repo.list_by_farm_ids(
                    farm_ids, skip=skip, limit=limit
                )
                # Post-filter
                return [
                    r
                    for r in raw_records
                    if r.farmId in farm_ids and r.district in authorized_districts
                ]

            elif current_user.role == Role.DAPH_OFFICIAL:
                authorized_districts = current_user.authorization.authorizedDistricts
                if not authorized_districts:
                    return []
                dist_set = set(authorized_districts)
                raw_records = await self._surv_repo.list_by_districts(
                    authorized_districts, skip=skip, limit=limit
                )
                # Post-filter
                return [r for r in raw_records if r.district in dist_set]

            else:
                raise DemoOperationalForbiddenError()

        except (DemoOperationalForbiddenError, DemoOperationalUnavailableError):
            raise
        except DemoOperationalRepositoryError:
            raise DemoOperationalUnavailableError()
        except Exception:
            raise DemoOperationalUnavailableError()

    async def get_accessible_alerts(
        self,
        current_user: DemoUserDocument,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DemoAlert]:
        """
        Retrieves operational alerts accessible to current_user.
        - FARMER: alerts for owned farm in registeredFarmDistrict.
        - VETERINARY_OFFICER: alerts for assigned farms in authorizedDistricts.
        - DAPH_OFFICIAL: alerts in authorizedDistricts.
        """
        self._validate_user(current_user)

        try:
            if current_user.role == Role.FARMER:
                accessible_farms = await self.get_accessible_farms(
                    current_user, skip=0, limit=100
                )
                farm_ids = [f.farmId for f in accessible_farms]
                reg_district = current_user.authorization.registeredFarmDistrict
                if not farm_ids or not reg_district:
                    return []
                raw_alerts = await self._alert_repo.list_by_farm_ids(
                    farm_ids, skip=skip, limit=limit
                )
                farm_set = set(farm_ids)
                # Post-filter
                return [
                    a
                    for a in raw_alerts
                    if a.district == reg_district
                    and any(fid in farm_set for fid in a.affectedFarmIds)
                ]

            elif current_user.role == Role.VETERINARY_OFFICER:
                accessible_farms = await self.get_accessible_farms(
                    current_user, skip=0, limit=100
                )
                farm_ids = [f.farmId for f in accessible_farms]
                authorized_districts = set(current_user.authorization.authorizedDistricts)
                if not farm_ids or not authorized_districts:
                    return []
                raw_alerts = await self._alert_repo.list_by_farm_ids(
                    farm_ids, skip=skip, limit=limit
                )
                farm_set = set(farm_ids)
                # Post-filter
                return [
                    a
                    for a in raw_alerts
                    if a.district in authorized_districts
                    and any(fid in farm_set for fid in a.affectedFarmIds)
                ]

            elif current_user.role == Role.DAPH_OFFICIAL:
                authorized_districts = current_user.authorization.authorizedDistricts
                if not authorized_districts:
                    return []
                dist_set = set(authorized_districts)
                raw_alerts = await self._alert_repo.list_by_districts(
                    authorized_districts, skip=skip, limit=limit
                )
                # Post-filter
                return [a for a in raw_alerts if a.district in dist_set]

            else:
                raise DemoOperationalForbiddenError()

        except (DemoOperationalForbiddenError, DemoOperationalUnavailableError):
            raise
        except DemoOperationalRepositoryError:
            raise DemoOperationalUnavailableError()
        except Exception:
            raise DemoOperationalUnavailableError()

    async def get_accessible_response_tasks(
        self,
        current_user: DemoUserDocument,
        skip: int = 0,
        limit: int = 50,
    ) -> List[DemoResponseTask]:
        """
        Retrieves response tasks accessible to current_user.
        - FARMER: Forbidden.
        - VETERINARY_OFFICER: tasks assigned to user in authorizedDistricts (requires recordResponse permission).
        - DAPH_OFFICIAL: tasks in authorizedDistricts (requires recordResponse permission).
        """
        self._validate_user(current_user)

        if not current_user.permissions.recordResponse:
            raise DemoOperationalForbiddenError(
                "Permission 'recordResponse' is required to access response tasks."
            )

        try:
            if current_user.role == Role.FARMER:
                raise DemoOperationalForbiddenError(
                    "Response tasks are forbidden for farmer role."
                )

            elif current_user.role == Role.VETERINARY_OFFICER:
                authorized_districts = current_user.authorization.authorizedDistricts
                if not authorized_districts:
                    return []
                dist_set = set(authorized_districts)
                raw_tasks = await self._task_repo.list_by_assigned_officer_user_id(
                    current_user.userId, skip=skip, limit=limit
                )
                # Post-filter
                return [
                    t
                    for t in raw_tasks
                    if t.assignedOfficerUserId == current_user.userId
                    and t.district in dist_set
                ]

            elif current_user.role == Role.DAPH_OFFICIAL:
                authorized_districts = current_user.authorization.authorizedDistricts
                if not authorized_districts:
                    return []
                dist_set = set(authorized_districts)
                raw_tasks = await self._task_repo.list_by_districts(
                    authorized_districts, skip=skip, limit=limit
                )
                # Post-filter
                return [t for t in raw_tasks if t.district in dist_set]

            else:
                raise DemoOperationalForbiddenError()

        except (DemoOperationalForbiddenError, DemoOperationalUnavailableError):
            raise
        except DemoOperationalRepositoryError:
            raise DemoOperationalUnavailableError()
        except Exception:
            raise DemoOperationalUnavailableError()

    def __repr__(self) -> str:
        return "DemoOperationalAuthorizationService()"
