"""
Advisory Service (Phase 3).

Coordinates farmer advisory draft creation, personalization, preview generation,
recipient directory resolution, optimistic locking, and review/approval lifecycle transitions.

ARCHITECTURAL RULES:
1. Forecast Provenance: Reads authoritative disease, district, target period, risk level, severity,
   and disclaimer directly from stored ForecastDecisionRecord. Never mutates the forecast record.
2. Recipient Targeting: Resolves recipients via RecipientDirectory boundary. Rejects unassigned recipients
   and district-incompatible recipients.
3. Message Resolution: Standard message applies to recipients without overrides. Personalized overrides
   supplement standard content for targeted recipients.
4. Notification Deferral: Does NOT send notifications, emails, SMS, or outbox messages.
5. Durability: Uses injectable AdvisoryRepository (in-memory for standalone, replaced in production).
"""

from datetime import datetime, timezone
import uuid
from typing import Callable, List, Optional, Tuple

from backend.components.risk_forecasting.integrations.recipient_directory import (
    InMemoryRecipientDirectory,
    Recipient,
    RecipientDirectory,
    recipient_directory,
)
from backend.components.risk_forecasting.repositories.advisory_repository import (
    AdvisoryRepository,
    InMemoryAdvisoryRepository,
)
from backend.components.risk_forecasting.repositories.forecast_record_repository import (
    ForecastRecordRepository,
    InMemoryForecastRecordRepository,
)
from backend.components.risk_forecasting.schemas import (
    AdvisoryListResponse,
    AdvisoryPreviewResponse,
    CreateAdvisoryDraftRequest,
    FarmerAdvisoryRecord,
    ForecastDecisionRecord,
    PersonalizedOverride,
    RecipientResolvedPreview,
    RecipientSummary,
    UpdateAdvisoryDraftRequest,
)
from backend.components.risk_forecasting.services.advisory_template_service import (
    AdvisoryTemplateService,
    advisory_template_service,
)
from backend.components.risk_forecasting.services.forecast_record_service import (
    ForecastRecordService,
    forecast_record_service,
)


class AdvisoryService:
    """Service layer managing farmer advisory lifecycle and recipient resolution."""

    def __init__(
        self,
        forecast_service: Optional[ForecastRecordService] = None,
        advisory_repository: Optional[AdvisoryRepository] = None,
        recipient_dir: Optional[RecipientDirectory] = None,
        template_svc: Optional[AdvisoryTemplateService] = None,
        clock: Optional[Callable[[], datetime]] = None,
        id_generator: Optional[Callable[[], str]] = None,
    ):
        self.forecast_service = forecast_service or forecast_record_service
        self.advisory_repo = advisory_repository or InMemoryAdvisoryRepository()
        self.recipient_dir = recipient_dir or recipient_directory
        self.template_svc = template_svc or advisory_template_service
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_generator = id_generator or (lambda: f"adv_{uuid.uuid4().hex[:12]}")

    def _resolve_and_validate_recipients(
        self,
        forecast: ForecastDecisionRecord,
        recipient_scope: str,
        selected_ids: Optional[List[str]],
        vet_id: str,
        overrides: Optional[List[PersonalizedOverride]],
    ) -> Tuple[List[Recipient], RecipientSummary, List[PersonalizedOverride]]:
        """Resolves recipient scope, validates district compatibility and overrides."""
        # 1. Total assigned farms for this vet across ALL districts
        all_vet_farms = self.recipient_dir.list_assigned_recipients(
            vet_id=vet_id, district=None
        )
        total_assigned = len(all_vet_farms)

        # 2. Eligible farms assigned to this vet in the forecast district
        forecast_dist_clean = forecast.district.strip().title()
        if forecast_dist_clean in ["Moneragala", "Monaragala"]:
            forecast_dist_clean = "Monaragala"
        elif forecast_dist_clean in ["Nuwaraeliya", "Nuwara Eliya"]:
            forecast_dist_clean = "Nuwara Eliya"

        eligible_in_district = [
            r for r in all_vet_farms
            if r.district.strip().title() in [forecast_dist_clean, forecast.district.strip().title()]
        ]
        eligible_count = len(eligible_in_district)

        # 3. Resolve targeted recipients based on scope
        if recipient_scope == "ALL_ASSIGNED":
            if eligible_count == 0:
                raise ValueError(
                    f"No assigned farms found in district '{forecast.district}' for vet '{vet_id}'."
                )
            resolved_targets = eligible_in_district
        elif recipient_scope == "SELECTED":
            if not selected_ids:
                raise ValueError("selected_recipient_ids cannot be empty when recipient_scope is 'SELECTED'.")
            resolved_targets = self.recipient_dir.resolve_recipients(
                recipient_ids=selected_ids, vet_id=vet_id
            )
            # Validate district compatibility
            for r in resolved_targets:
                r_dist_clean = r.district.strip().title()
                if r_dist_clean in ["Moneragala", "Monaragala"]:
                    r_dist_clean = "Monaragala"
                elif r_dist_clean in ["Nuwaraeliya", "Nuwara Eliya"]:
                    r_dist_clean = "Nuwara Eliya"
                if r_dist_clean != forecast_dist_clean:
                    raise ValueError(
                        f"Recipient '{r.recipient_id}' is located in district '{r.district}', "
                        f"which is incompatible with forecast district '{forecast.district}'."
                    )
        else:
            raise ValueError(f"Invalid recipient_scope '{recipient_scope}'. Allowed: ALL_ASSIGNED, SELECTED.")

        target_ids = {r.recipient_id for r in resolved_targets}

        # 4. Validate and clean personalized overrides
        clean_overrides: List[PersonalizedOverride] = []
        if overrides:
            seen_override_ids = set()
            for ov in overrides:
                if ov.recipient_id not in target_ids:
                    raise ValueError(
                        f"Personalized override specifies recipient ID '{ov.recipient_id}', "
                        f"which is not in the targeted recipient list."
                    )
                if ov.recipient_id in seen_override_ids:
                    raise ValueError(f"Duplicate personalized override for recipient ID '{ov.recipient_id}'.")
                seen_override_ids.add(ov.recipient_id)
                clean_overrides.append(ov)

        # 5. Construct RecipientSummary
        selected_count = len(resolved_targets)
        personalized_count = len(clean_overrides)
        standard_count = selected_count - personalized_count
        excluded_count = max(0, total_assigned - selected_count)

        summary = RecipientSummary(
            total_assigned=total_assigned,
            eligible_count=eligible_count,
            selected_count=selected_count,
            standard_message_count=standard_count,
            personalized_count=personalized_count,
            excluded_count=excluded_count,
        )

        return resolved_targets, summary, clean_overrides

    def create_draft(self, request: CreateAdvisoryDraftRequest) -> FarmerAdvisoryRecord:
        """Creates a new DRAFT advisory record linked to an authoritative forecast."""
        # 1. Advisory Type Authorization Safeguard
        if request.advisory_type == "OFFICIAL_DAPH_NOTICE":
            raise ValueError(
                "Advisory type 'OFFICIAL_DAPH_NOTICE' is not supported for individual Veterinary Officer advisory creation; "
                "DAPH notice workflows require shared DAPH authority integration in Phase 4+."
            )

        # 2. Fetch Authoritative Forecast
        forecast = self.forecast_service.get_record(request.forecast_id)

        # 3. Idempotency Check
        if request.idempotency_key:
            existing = self.advisory_repo.find_by_idempotency_key(request.idempotency_key)
            if existing:
                matches = (
                    existing.forecast_id == request.forecast_id
                    and existing.recipient_scope == request.recipient_scope
                )
                if matches:
                    return existing
                else:
                    raise ValueError(
                        f"Idempotency key collision: Key '{request.idempotency_key}' "
                        f"was previously used with different advisory request parameters."
                    )

        # TODO (Phase 4 / Shared Auth Integration): In production, actor identity (created_by, approved_by)
        # must be extracted from verified JWT claims/OAuth2 tokens via shared auth dependencies, rather than relying on request body trust.
        creator_id = request.created_by or "vet_officer_01"

        # 4. Resolve & Validate Recipients
        resolved_recipients, summary, clean_overrides = self._resolve_and_validate_recipients(
            forecast=forecast,
            recipient_scope=request.recipient_scope,
            selected_ids=request.selected_recipient_ids,
            vet_id=creator_id,
            overrides=request.personalized_overrides,
        )

        # 5. Generate Standard Content via Template Service
        (
            title,
            std_msg,
            prev_actions,
            symptoms,
            contact_inst,
            disclaimer,
            priority,
        ) = self.template_svc.generate_standard_content(
            disease=forecast.disease,
            district=forecast.district,
            target_year=forecast.target_year,
            target_month=forecast.target_month,
            risk_level=forecast.risk_level,
            predicted_severity=forecast.predicted_severity,
            disclaimer=forecast.disclaimer,
        )

        # 6. Construct Record
        now_dt = self.clock()
        now_iso = now_dt.isoformat()
        advisory_id = self.id_generator()

        selected_ids_list = [r.recipient_id for r in resolved_recipients]

        record = FarmerAdvisoryRecord(
            advisory_id=advisory_id,
            forecast_id=forecast.forecast_id,
            advisory_type=request.advisory_type,
            disease=forecast.disease,
            district=forecast.district,
            target_year=forecast.target_year,
            target_month=forecast.target_month,
            risk_level=forecast.risk_level,
            priority=priority,
            title=title,
            standard_message=std_msg,
            preventive_actions=prev_actions,
            symptoms_to_watch=symptoms,
            contact_instruction=contact_inst,
            vet_custom_note=request.vet_custom_note,
            disclaimer=disclaimer,
            recipient_scope=request.recipient_scope,
            selected_recipient_ids=selected_ids_list,
            personalized_overrides=clean_overrides,
            recipient_summary=summary,
            status="DRAFT",
            created_by=creator_id,
            created_at=now_iso,
            updated_at=now_iso,
            idempotency_key=request.idempotency_key,
            version=1,
        )

        return self.advisory_repo.save(record)

    def preview_advisory(
        self,
        advisory_id: Optional[str] = None,
        draft_req: Optional[CreateAdvisoryDraftRequest] = None,
    ) -> AdvisoryPreviewResponse:
        """
        Generates recipient-resolved previews without persisting or sending any notifications.
        """
        if advisory_id:
            record = self.advisory_repo.get_by_id(advisory_id)
            if not record:
                raise KeyError(f"Advisory record with ID '{advisory_id}' not found.")
            forecast = self.forecast_service.get_record(record.forecast_id)
            vet_id = record.created_by
            scope = record.recipient_scope
            selected_ids = record.selected_recipient_ids or []
            vet_note = record.vet_custom_note
            overrides = record.personalized_overrides or []
            status_label = record.status
            rec_priority = record.priority
            title = record.title
            std_msg = record.standard_message
            disclaimer = record.disclaimer
            forecast_summary = f"{record.disease} risk in {record.district} for {record.target_year}-{record.target_month:02d} is {record.risk_level}."
            summary = record.recipient_summary

            # Use frozen selected_recipient_ids snapshot directly
            dir_map = {}
            try:
                dir_recipients = self.recipient_dir.resolve_recipients(
                    recipient_ids=selected_ids, vet_id=vet_id
                )
                dir_map = {r.recipient_id: r for r in dir_recipients}
            except Exception:
                pass

            resolved_recipients: List[Recipient] = []
            for rid in selected_ids:
                if rid in dir_map:
                    resolved_recipients.append(dir_map[rid])
                else:
                    resolved_recipients.append(
                        Recipient(
                            recipient_id=rid,
                            recipient_name=f"Farm {rid}",
                            district=forecast.district,
                            assigned_vet_id=vet_id,
                        )
                    )
            clean_overrides = overrides
        elif draft_req:
            forecast = self.forecast_service.get_record(draft_req.forecast_id)
            vet_id = draft_req.created_by or "vet_officer_01"
            scope = draft_req.recipient_scope
            selected_ids = draft_req.selected_recipient_ids
            vet_note = draft_req.vet_custom_note
            overrides = draft_req.personalized_overrides or []
            status_label = "DRAFT"
            (
                title,
                std_msg,
                _,
                _,
                _,
                disclaimer,
                rec_priority,
            ) = self.template_svc.generate_standard_content(
                disease=forecast.disease,
                district=forecast.district,
                target_year=forecast.target_year,
                target_month=forecast.target_month,
                risk_level=forecast.risk_level,
                predicted_severity=forecast.predicted_severity,
                disclaimer=forecast.disclaimer,
            )
            forecast_summary = f"{forecast.disease} risk in {forecast.district} for {forecast.target_year}-{forecast.target_month:02d} is {forecast.risk_level}."

            resolved_recipients, summary, clean_overrides = self._resolve_and_validate_recipients(
                forecast=forecast,
                recipient_scope=scope,
                selected_ids=selected_ids,
                vet_id=vet_id,
                overrides=overrides,
            )
        else:
            raise ValueError("Either advisory_id or draft_req must be provided for preview.")

        override_map = {ov.recipient_id: ov.custom_note for ov in clean_overrides}

        previews: List[RecipientResolvedPreview] = []
        for r in resolved_recipients:
            is_personalized = r.recipient_id in override_map
            final_msg_parts = [std_msg]
            if vet_note:
                final_msg_parts.append(f"\n\nVet Note: {vet_note}")
            if is_personalized:
                final_msg_parts.append(f"\n\nPersonalized Advice: {override_map[r.recipient_id]}")

            final_msg = "".join(final_msg_parts)
            previews.append(
                RecipientResolvedPreview(
                    recipient_id=r.recipient_id,
                    recipient_name=r.recipient_name,
                    district=r.district,
                    is_personalized=is_personalized,
                    final_message=final_msg,
                )
            )

        return AdvisoryPreviewResponse(
            advisory_id=advisory_id,
            forecast_id=forecast.forecast_id,
            disease=forecast.disease,
            district=forecast.district,
            target_year=forecast.target_year,
            target_month=forecast.target_month,
            risk_level=forecast.risk_level,
            recommended_priority=rec_priority,
            status=status_label,
            recipient_summary=summary,
            previews=previews,
            forecast_summary=forecast_summary,
            disclaimer=disclaimer,
        )

    def update_draft(
        self, advisory_id: str, request: UpdateAdvisoryDraftRequest
    ) -> FarmerAdvisoryRecord:
        """Updates editable advisory draft fields with optimistic version checking."""
        record = self.advisory_repo.get_by_id(advisory_id)
        if not record:
            raise KeyError(f"Advisory record with ID '{advisory_id}' not found.")

        forecast = self.forecast_service.get_record(record.forecast_id)
        new_scope = request.recipient_scope or record.recipient_scope
        new_selected_ids = (
            request.selected_recipient_ids
            if request.selected_recipient_ids is not None
            else record.selected_recipient_ids
        )
        new_overrides = (
            request.personalized_overrides
            if request.personalized_overrides is not None
            else record.personalized_overrides
        )
        new_vet_note = (
            request.vet_custom_note if request.vet_custom_note is not None else record.vet_custom_note
        )

        resolved_recipients, summary, clean_overrides = self._resolve_and_validate_recipients(
            forecast=forecast,
            recipient_scope=new_scope,
            selected_ids=new_selected_ids,
            vet_id=record.created_by,
            overrides=new_overrides,
        )

        selected_ids_list = [r.recipient_id for r in resolved_recipients]
        now_iso = self.clock().isoformat()

        return self.advisory_repo.update_draft(
            advisory_id=advisory_id,
            expected_version=request.version,
            recipient_scope=new_scope,
            selected_recipient_ids=selected_ids_list,
            vet_custom_note=new_vet_note,
            personalized_overrides=clean_overrides,
            recipient_summary=summary,
            updated_at=now_iso,
        )

    def mark_ready_for_review(
        self, advisory_id: str, expected_version: int
    ) -> FarmerAdvisoryRecord:
        """Transitions advisory status from DRAFT -> REVIEW_READY."""
        now_iso = self.clock().isoformat()
        return self.advisory_repo.update_status(
            advisory_id=advisory_id,
            expected_version=expected_version,
            new_status="REVIEW_READY",
            updated_at=now_iso,
        )

    def approve_advisory(
        self, advisory_id: str, expected_version: int, approved_by: str
    ) -> FarmerAdvisoryRecord:
        """
        Transitions advisory status to APPROVED and records approver metadata.
        Approved content becomes immutable.
        """
        now_dt = self.clock()
        now_iso = now_dt.isoformat()

        approved_record = self.advisory_repo.update_status(
            advisory_id=advisory_id,
            expected_version=expected_version,
            new_status="APPROVED",
            approved_by=approved_by,
            approved_at=now_iso,
            updated_at=now_iso,
        )
        return approved_record

    def cancel_advisory(
        self, advisory_id: str, expected_version: int
    ) -> FarmerAdvisoryRecord:
        """Transitions advisory status to CANCELLED."""
        now_iso = self.clock().isoformat()
        return self.advisory_repo.update_status(
            advisory_id=advisory_id,
            expected_version=expected_version,
            new_status="CANCELLED",
            updated_at=now_iso,
        )

    def get_advisory(self, advisory_id: str) -> FarmerAdvisoryRecord:
        """Retrieves advisory record by ID."""
        record = self.advisory_repo.get_by_id(advisory_id)
        if not record:
            raise KeyError(f"Advisory record with ID '{advisory_id}' not found.")
        return record

    def list_advisories(
        self,
        forecast_id: Optional[str] = None,
        disease: Optional[str] = None,
        district: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AdvisoryListResponse:
        """Queries stored advisories with bounded filters."""
        bounded_limit = min(max(1, limit), 200)
        bounded_offset = max(0, offset)

        advisories, total_count = self.advisory_repo.list(
            forecast_id=forecast_id,
            disease=disease,
            district=district,
            status=status,
            limit=bounded_limit,
            offset=bounded_offset,
        )

        return AdvisoryListResponse(
            total_count=total_count,
            limit=bounded_limit,
            offset=bounded_offset,
            advisories=advisories,
        )


# Singleton Instance for Default Route Injection
advisory_service = AdvisoryService()
