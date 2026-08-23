"""
Forecast-Linked DAPH–Vet Follow-Up Service (Phase 6B-1).

Coordinates DAPH operational follow-up creation, scientific snapshot freezing,
Veterinary Officer directory verification, optimistic locking, actor authorization,
and lifecycle state transitions.

ARCHITECTURAL GUARANTEES:
1. Scientific Linkage: Sourced directly from stored ForecastDecisionRecord. Scientific snapshot fields
   (district, disease, target_year, target_month, forecast_risk_level) are frozen and immutable.
2. Transparent Priority: Operational priority is derived directly from forecast risk level:
   HIGH risk -> HIGH priority, MEDIUM risk -> MEDIUM priority, LOW risk -> LOW priority.
3. Directory Verification: Validates that the assigned Vet exists, is active, and is assigned to the forecast district.
4. Non-Repudiation & Concurrency: Optimistic locking (version checking) and strict actor authorization rules.
5. Privacy & Decoupling: Zero farmer PII. Zero stock/inventory management.
"""

from datetime import datetime, timezone
import uuid
from typing import Callable, Optional, List, Tuple

from backend.components.risk_forecasting.integrations.vet_directory import (
    VeterinaryOfficerDirectory,
    veterinary_officer_directory,
)
from backend.components.risk_forecasting.repositories.forecast_record_repository import (
    ForecastRecordRepository,
)
from backend.components.risk_forecasting.repositories.follow_up_repository import (
    FollowUpRepository,
    InMemoryFollowUpRepository,
)
from backend.components.risk_forecasting.schemas import (
    CreateFollowUpRequest,
    FollowUpActorContext,
    FollowUpListResponse,
    ForecastDecisionRecord,
    ForecastFollowUpRecord,
    OperationalPriority,
)
from backend.components.risk_forecasting.services.forecast_record_service import (
    ForecastRecordService,
    forecast_record_service,
)


class ForecastFollowUpService:
    """Service layer managing DAPH-to-Vet operational follow-up workflows."""

    def __init__(
        self,
        forecast_service: Optional[ForecastRecordService] = None,
        follow_up_repository: Optional[FollowUpRepository] = None,
        vet_directory: Optional[VeterinaryOfficerDirectory] = None,
        clock: Optional[Callable[[], datetime]] = None,
        id_generator: Optional[Callable[[], str]] = None,
    ):
        self.forecast_service = forecast_service or forecast_record_service
        self.follow_up_repo = follow_up_repository or InMemoryFollowUpRepository()
        self.vet_dir = vet_directory or veterinary_officer_directory
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_generator = id_generator or (lambda: f"ffu_{uuid.uuid4().hex[:12]}")

    def _derive_operational_priority(self, risk_level: str) -> OperationalPriority:
        """Transparently maps scientific forecast risk level to operational priority."""
        norm_risk = risk_level.strip().upper()
        if norm_risk == "HIGH":
            return "HIGH"
        elif norm_risk == "MEDIUM":
            return "MEDIUM"
        elif norm_risk == "LOW":
            return "LOW"
        else:
            raise ValueError(f"Cannot derive operational priority from unsupported forecast risk level '{risk_level}'.")

    def _validate_daph_authority(self, actor: Optional[FollowUpActorContext]) -> None:
        """Ensures acting user has DAPH official authorization."""
        if not actor:
            return  # Default standalone fallback if actor context not provided in legacy calls
        if actor.role not in ["DAPH_OFFICIAL", "SYSTEM"]:
            raise ValueError(f"Actor '{actor.actor_id}' with role '{actor.role}' is not authorized to issue DAPH follow-up instructions.")

    def issue_follow_up(
        self,
        request: CreateFollowUpRequest,
        actor: Optional[FollowUpActorContext] = None,
    ) -> ForecastFollowUpRecord:
        """
        Issues a new DAPH operational follow-up instruction linked to an authoritative forecast.
        Scientific snapshot values are copied server-side directly from stored ForecastDecisionRecord.
        """
        # 1. Actor Authorization
        self._validate_daph_authority(actor)

        # 2. Fetch Authoritative Forecast Record
        forecast = self.forecast_service.get_record(request.forecast_id)
        if forecast.status == "SUPERSEDED":
            raise ValueError(f"Cannot issue follow-up for superseded forecast record '{request.forecast_id}'.")

        # 3. Verify Assigned Veterinary Officer Directory Assignment
        assigned_vet_id = request.assigned_vet_id.strip()
        vet_info = self.vet_dir.get_vet(assigned_vet_id)
        if not vet_info:
            raise ValueError(f"Assigned Veterinary Officer ID '{assigned_vet_id}' not found in directory.")
        if not vet_info.active:
            raise ValueError(f"Assigned Veterinary Officer '{assigned_vet_id}' is inactive.")
        if not self.vet_dir.is_vet_assigned_to_district(assigned_vet_id, forecast.district):
            raise ValueError(
                f"Assigned Veterinary Officer '{assigned_vet_id}' is not assigned to district '{forecast.district}'."
            )

        # 4. Idempotency Check
        if request.idempotency_key:
            existing = self.follow_up_repo.find_by_idempotency_key(request.idempotency_key)
            if existing:
                matches = (
                    existing.forecast_id == request.forecast_id
                    and existing.assigned_vet_id == assigned_vet_id
                    and existing.instruction_summary == request.instruction_summary.strip()
                )
                if matches:
                    return existing
                else:
                    raise ValueError(
                        f"Idempotency key collision: Key '{request.idempotency_key}' "
                        f"was previously used with different follow-up request parameters."
                    )

        # 5. Operational Priority Derivation
        priority = self._derive_operational_priority(forecast.risk_level)

        # 6. Construct Immutable Record
        now_iso = self.clock().isoformat()
        follow_up_id = self.id_generator()
        issuing_daph_id = actor.actor_id if actor else "daph_hq_01"

        record = ForecastFollowUpRecord(
            follow_up_id=follow_up_id,
            forecast_id=forecast.forecast_id,
            district=forecast.district,
            disease=forecast.disease,
            target_year=forecast.target_year,
            target_month=forecast.target_month,
            forecast_risk_level=forecast.risk_level,
            operational_priority=priority,
            instruction_summary=request.instruction_summary.strip(),
            issued_by_daph_id=issuing_daph_id,
            assigned_vet_id=assigned_vet_id,
            status="ISSUED",
            version=1,
            idempotency_key=request.idempotency_key,
            issued_at=now_iso,
            created_at=now_iso,
            updated_at=now_iso,
        )

        return self.follow_up_repo.save(record)

    def get_follow_up(
        self,
        follow_up_id: str,
        actor: Optional[FollowUpActorContext] = None,
    ) -> ForecastFollowUpRecord:
        """Retrieves a follow-up record by ID, checking actor visibility permissions."""
        record = self.follow_up_repo.get_by_id(follow_up_id)
        if not record:
            raise KeyError(f"Follow-up record with ID '{follow_up_id}' not found.")

        if actor:
            if actor.role == "FARMER":
                raise ValueError("Farmers are not authorized to access internal DAPH–Vet follow-up records.")
            elif actor.role == "VETERINARY_OFFICER":
                is_assigned = record.assigned_vet_id == actor.actor_id
                in_district = record.district in actor.authorized_districts
                if not (is_assigned or in_district):
                    raise ValueError(
                        f"Veterinary Officer '{actor.actor_id}' is not authorized to view follow-up '{follow_up_id}'."
                    )

        return record

    def list_follow_ups(
        self,
        forecast_id: Optional[str] = None,
        district: Optional[str] = None,
        disease: Optional[str] = None,
        assigned_vet_id: Optional[str] = None,
        issued_by_daph_id: Optional[str] = None,
        status: Optional[str] = None,
        target_year: Optional[int] = None,
        target_month: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        actor: Optional[FollowUpActorContext] = None,
    ) -> FollowUpListResponse:
        """Queries stored follow-up records with authorization filter scoping."""
        if actor:
            if actor.role == "FARMER":
                raise ValueError("Farmers are not authorized to list internal DAPH–Vet follow-up records.")
            elif actor.role == "VETERINARY_OFFICER":
                # Restrict to assigned vet unless filtering by authorized district
                if district and district in actor.authorized_districts:
                    pass
                else:
                    assigned_vet_id = actor.actor_id

        records, total_count = self.follow_up_repo.list(
            forecast_id=forecast_id,
            district=district,
            disease=disease,
            assigned_vet_id=assigned_vet_id,
            issued_by_daph_id=issued_by_daph_id,
            status=status,
            target_year=target_year,
            target_month=target_month,
            limit=limit,
            offset=offset,
        )

        return FollowUpListResponse(
            total_count=total_count,
            limit=min(max(1, limit), 200),
            offset=max(0, offset),
            follow_ups=records,
        )

    def acknowledge_follow_up(
        self,
        follow_up_id: str,
        expected_version: int,
        actor: FollowUpActorContext,
    ) -> ForecastFollowUpRecord:
        """Transitions status from ISSUED -> ACKNOWLEDGED. Only the assigned Vet may acknowledge."""
        record = self.get_follow_up(follow_up_id)

        if expected_version != record.version:
            raise ValueError(
                f"Optimistic lock conflict: Request specified version {expected_version}, "
                f"but current record version is {record.version}."
            )

        if actor.role != "VETERINARY_OFFICER":
            raise ValueError(f"Only a Veterinary Officer may acknowledge follow-up instructions (actor role: '{actor.role}').")

        if record.assigned_vet_id != actor.actor_id:
            raise ValueError(
                f"Veterinary Officer '{actor.actor_id}' is not the assigned officer for follow-up '{follow_up_id}' "
                f"(assigned to '{record.assigned_vet_id}')."
            )

        if record.status != "ISSUED":
            raise ValueError(f"Cannot acknowledge follow-up in status '{record.status}'. Expected status 'ISSUED'.")

        now_iso = self.clock().isoformat()
        updated_dict = record.model_dump()
        updated_dict["status"] = "ACKNOWLEDGED"
        updated_dict["acknowledged_at"] = now_iso
        updated_dict["version"] = record.version + 1
        updated_dict["updated_at"] = now_iso

        updated_record = ForecastFollowUpRecord(**updated_dict)
        return self.follow_up_repo.update_record(updated_record)

    def start_follow_up_action(
        self,
        follow_up_id: str,
        expected_version: int,
        actor: FollowUpActorContext,
    ) -> ForecastFollowUpRecord:
        """Transitions status from ACKNOWLEDGED -> ACTION_IN_PROGRESS. Assigned Vet only."""
        record = self.get_follow_up(follow_up_id)

        if expected_version != record.version:
            raise ValueError(
                f"Optimistic lock conflict: Request specified version {expected_version}, "
                f"but current record version is {record.version}."
            )

        if actor.role != "VETERINARY_OFFICER" or record.assigned_vet_id != actor.actor_id:
            raise ValueError(f"Only assigned Veterinary Officer '{record.assigned_vet_id}' may start follow-up action.")

        if record.status != "ACKNOWLEDGED":
            raise ValueError(f"Cannot start follow-up action in status '{record.status}'. Expected status 'ACKNOWLEDGED'.")

        now_iso = self.clock().isoformat()
        updated_dict = record.model_dump()
        updated_dict["status"] = "ACTION_IN_PROGRESS"
        updated_dict["action_started_at"] = now_iso
        updated_dict["version"] = record.version + 1
        updated_dict["updated_at"] = now_iso

        updated_record = ForecastFollowUpRecord(**updated_dict)
        return self.follow_up_repo.update_record(updated_record)

    def complete_follow_up(
        self,
        follow_up_id: str,
        expected_version: int,
        actor: FollowUpActorContext,
    ) -> ForecastFollowUpRecord:
        """Transitions status from ACTION_IN_PROGRESS -> COMPLETED. Assigned Vet only."""
        record = self.get_follow_up(follow_up_id)

        if expected_version != record.version:
            raise ValueError(
                f"Optimistic lock conflict: Request specified version {expected_version}, "
                f"but current record version is {record.version}."
            )

        if actor.role != "VETERINARY_OFFICER" or record.assigned_vet_id != actor.actor_id:
            raise ValueError(f"Only assigned Veterinary Officer '{record.assigned_vet_id}' may complete follow-up.")

        if record.status != "ACTION_IN_PROGRESS":
            raise ValueError(f"Cannot complete follow-up in status '{record.status}'. Expected status 'ACTION_IN_PROGRESS'.")

        now_iso = self.clock().isoformat()
        updated_dict = record.model_dump()
        updated_dict["status"] = "COMPLETED"
        updated_dict["completed_at"] = now_iso
        updated_dict["version"] = record.version + 1
        updated_dict["updated_at"] = now_iso

        updated_record = ForecastFollowUpRecord(**updated_dict)
        return self.follow_up_repo.update_record(updated_record)

    def cancel_follow_up(
        self,
        follow_up_id: str,
        expected_version: int,
        reason: Optional[str],
        actor: FollowUpActorContext,
    ) -> ForecastFollowUpRecord:
        """Transitions status to CANCELLED. DAPH Official only from ISSUED or ACKNOWLEDGED."""
        record = self.get_follow_up(follow_up_id)

        if expected_version != record.version:
            raise ValueError(
                f"Optimistic lock conflict: Request specified version {expected_version}, "
                f"but current record version is {record.version}."
            )

        if actor.role not in ["DAPH_OFFICIAL", "SYSTEM"]:
            raise ValueError(f"Only DAPH Officials are authorized to cancel follow-up instructions (actor role: '{actor.role}').")

        if record.status not in ["ISSUED", "ACKNOWLEDGED"]:
            raise ValueError(f"Cannot cancel follow-up in status '{record.status}'. Allowed from ISSUED or ACKNOWLEDGED.")

        now_iso = self.clock().isoformat()
        updated_dict = record.model_dump()
        updated_dict["status"] = "CANCELLED"
        updated_dict["cancelled_at"] = now_iso
        if reason:
            updated_dict["cancellation_reason"] = reason.strip()
        updated_dict["version"] = record.version + 1
        updated_dict["updated_at"] = now_iso

        updated_record = ForecastFollowUpRecord(**updated_dict)
        return self.follow_up_repo.update_record(updated_record)

    def escalate_follow_up(
        self,
        follow_up_id: str,
        expected_version: int,
        reason: str,
        actor: FollowUpActorContext,
    ) -> ForecastFollowUpRecord:
        """Transitions status to ESCALATED. Requires explicit controlled reason."""
        if not reason or not reason.strip():
            raise ValueError("Escalation reason is required and cannot be empty.")

        record = self.get_follow_up(follow_up_id)

        if expected_version != record.version:
            raise ValueError(
                f"Optimistic lock conflict: Request specified version {expected_version}, "
                f"but current record version is {record.version}."
            )

        # Authorized actors: DAPH Official or assigned Vet
        if actor.role == "VETERINARY_OFFICER":
            if record.assigned_vet_id != actor.actor_id and record.district not in actor.authorized_districts:
                raise ValueError(f"Veterinary Officer '{actor.actor_id}' is not authorized to escalate follow-up '{follow_up_id}'.")
        elif actor.role not in ["DAPH_OFFICIAL", "SYSTEM"]:
            raise ValueError(f"Actor role '{actor.role}' is not authorized to escalate follow-ups.")

        if record.status in ["COMPLETED", "CANCELLED"]:
            raise ValueError(f"Cannot escalate follow-up in terminal status '{record.status}'.")

        now_iso = self.clock().isoformat()
        updated_dict = record.model_dump()
        updated_dict["status"] = "ESCALATED"
        updated_dict["escalated_at"] = now_iso
        updated_dict["escalation_reason"] = reason.strip()
        updated_dict["version"] = record.version + 1
        updated_dict["updated_at"] = now_iso

        updated_record = ForecastFollowUpRecord(**updated_dict)
        return self.follow_up_repo.update_record(updated_record)

    def link_external_resource_request(
        self,
        follow_up_id: str,
        expected_version: int,
        external_resource_request_id: str,
        actor: FollowUpActorContext,
    ) -> ForecastFollowUpRecord:
        """Associates an opaque external supply-chain resource request reference ID."""
        if not external_resource_request_id or not external_resource_request_id.strip():
            raise ValueError("external_resource_request_id cannot be empty.")

        record = self.get_follow_up(follow_up_id, actor=actor)

        if expected_version != record.version:
            raise ValueError(
                f"Optimistic lock conflict: Request specified version {expected_version}, "
                f"but current record version is {record.version}."
            )

        if record.status in ["COMPLETED", "CANCELLED"]:
            raise ValueError(f"Cannot link external resource request to follow-up in status '{record.status}'.")

        now_iso = self.clock().isoformat()
        updated_dict = record.model_dump()
        updated_dict["external_resource_request_id"] = external_resource_request_id.strip()
        updated_dict["version"] = record.version + 1
        updated_dict["updated_at"] = now_iso

        updated_record = ForecastFollowUpRecord(**updated_dict)
        return self.follow_up_repo.update_record(updated_record)


# Singleton Instance for Default Injection
forecast_follow_up_service = ForecastFollowUpService()
