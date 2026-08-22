"""
Recipient Query Service (Phase 5B-1).

Provides a narrow, read-only query service over RecipientDirectory for listing
non-sensitive farm recipients assigned to a Veterinary Officer.

SECURITY AND ARCHITECTURAL BOUNDARIES:
1. Non-Sensitive Metadata Only: Returns strictly recipient_id, recipient_name, and district.
   Never exposes phone numbers, emails, home addresses, owner names, or sensitive PII.
2. Read-Only: Contains no write operations, state mutations, or external notification triggers.
3. Unauthenticated Standalone Placeholder: The supplied vet_id is an unauthenticated actor ID.
   In production/shared-system integration, Vet identity MUST be derived from verified OAuth/JWT claims.
4. Replaceable Boundary: Wraps RecipientDirectory. In production, InMemoryRecipientDirectory
   will be replaced by an HTTP/gRPC adapter querying the authoritative shared Farm/Farmer service.
5. No Advisory Preview Misuse: Provides dedicated query capability so the frontend does not misuse
   advisory preview calls for recipient discovery.
"""

from typing import List, Optional

from backend.components.risk_forecasting.config import SRI_LANKA_DISTRICTS
from backend.components.risk_forecasting.integrations.recipient_directory import (
    RecipientDirectory,
    recipient_directory,
)
from backend.components.risk_forecasting.schemas import (
    AssignedRecipientListResponse,
    RecipientSummaryItem,
)


class RecipientQueryService:
    """Read-only query service managing assigned farm recipient lookups for Veterinary Officers."""

    def __init__(self, recipient_dir: Optional[RecipientDirectory] = None):
        self.recipient_dir = recipient_dir or recipient_directory

    def list_assigned_recipients(
        self, vet_id: str, district: Optional[str] = None
    ) -> AssignedRecipientListResponse:
        """
        Lists active farm recipients assigned to the requesting Vet, optionally filtered by district.

        :param vet_id: Veterinary Officer actor reference ID (required, non-blank).
        :param district: Optional Sri Lankan district name to filter recipients.
        :return: AssignedRecipientListResponse containing non-sensitive recipient summaries.
        :raises ValueError: If vet_id is blank/whitespace or district is not a valid Sri Lankan district.
        """
        if not vet_id or not vet_id.strip():
            raise ValueError("vet_id parameter cannot be empty or whitespace-only.")

        clean_vet_id = vet_id.strip()

        # Validate district if provided
        clean_district: Optional[str] = None
        if district is not None:
            raw_district = district.strip()
            if not raw_district:
                raise ValueError("district query parameter cannot be whitespace-only.")

            formatted = raw_district.title()
            if formatted in ["Moneragala", "Monaragala"]:
                formatted = "Monaragala"
            elif formatted in ["Nuwaraeliya", "Nuwara Eliya"]:
                formatted = "Nuwara Eliya"

            if formatted not in SRI_LANKA_DISTRICTS:
                raise ValueError(
                    f"Invalid district '{district}'. Must be one of {list(SRI_LANKA_DISTRICTS)}"
                )
            clean_district = formatted

        # 1. Total assigned farms for this vet across ALL districts
        all_vet_farms = self.recipient_dir.list_assigned_recipients(
            vet_id=clean_vet_id, district=None
        )
        total_assigned = len(all_vet_farms)

        # 2. Filter by district if requested
        if clean_district:
            filtered_farms = [
                r for r in all_vet_farms if r.district == clean_district
            ]
        else:
            filtered_farms = list(all_vet_farms)

        # 3. Deduplicate defensively by recipient_id while preserving order
        seen = set()
        unique_farms = []
        for r in filtered_farms:
            if r.recipient_id not in seen:
                seen.add(r.recipient_id)
                unique_farms.append(r)

        # 4. Deterministic sorting by recipient_id
        unique_farms.sort(key=lambda r: r.recipient_id)

        # 5. Convert to non-sensitive RecipientSummaryItem objects (deep copy)
        summary_items = [
            RecipientSummaryItem(
                recipient_id=r.recipient_id,
                recipient_name=r.recipient_name,
                district=r.district,
            )
            for r in unique_farms
        ]

        return AssignedRecipientListResponse(
            vet_id=clean_vet_id,
            district_filter=clean_district,
            total_assigned=total_assigned,
            eligible_count=len(summary_items),
            recipients=summary_items,
            source="InMemoryRecipientDirectory (Standalone Test Double)",
            integration_note=(
                "Standalone read-only recipient bridge. Exposes non-sensitive metadata only for UI targeting; "
                "no PII transmitted. Production deployment replaces this adapter with authenticated shared system calls."
            ),
        )


# Default singleton instance bound to shared recipient_directory instance
recipient_query_service = RecipientQueryService()
