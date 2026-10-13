"""
Recipient Directory Integration Boundary (Phase 3).

Defines the loosely coupled RecipientDirectory abstraction for resolving assigned farms/recipients.
Provides an in-memory test double for standalone operation.

PRODUCTION REPLACEMENT PATH:
In production/shared-system integration, InMemoryRecipientDirectory will be replaced by an adapter
calling the authoritative shared Farm/Farmer microservice API or database.
"""

from typing import List, Optional, Protocol
from pydantic import BaseModel, Field


class Recipient(BaseModel):
    """Minimal recipient metadata required for advisory targeting. Contains NO sensitive PII."""
    recipient_id: str = Field(..., description="Unique recipient or farm identifier.")
    recipient_name: str = Field(..., description="Human-readable farm display name or identifier label.")
    district: str = Field(..., description="District where farm is located.")
    assigned_vet_id: str = Field(..., description="Veterinary Officer user ID assigned to this farm.")


class RecipientDirectory(Protocol):
    """Protocol defining the Recipient Directory contract."""

    def list_assigned_recipients(
        self, vet_id: str, district: Optional[str] = None
    ) -> List[Recipient]:
        """Lists all active farms assigned to the given Vet, optionally filtered by district."""
        ...

    def resolve_recipients(
        self, recipient_ids: List[str], vet_id: str
    ) -> List[Recipient]:
        """Resolves recipient models by IDs, validating that they belong to the requesting Vet."""
        ...


class InMemoryRecipientDirectory:
    """
    In-memory test double implementation of RecipientDirectory.
    Pre-seeded with 20 sample farms assigned to vet_officer_01 across Sri Lankan districts.
    """

    def __init__(self):
        # Pre-seed 20 sample farms for standalone tests
        self._recipients: List[Recipient] = [
            # Anuradhapura (5 farms)
            Recipient(recipient_id="DEMO_FARM_001", recipient_name="Maha Illuppallama Dairy Farm", district="Anuradhapura", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_002", recipient_name="Kekirawa Cattle Station", district="Anuradhapura", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_003", recipient_name="Eppawala Livestock Unit", district="Anuradhapura", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_004", recipient_name="Thambuttegama Dairy Co-op", district="Anuradhapura", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_005", recipient_name="Medawachchiya Cattle Farm", district="Anuradhapura", assigned_vet_id="vet_officer_01"),
            # Colombo (5 farms)
            Recipient(recipient_id="DEMO_FARM_006", recipient_name="Homagama Dairy Station", district="Colombo", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_007", recipient_name="Padukka Cattle Ranch", district="Colombo", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_008", recipient_name="Avissawella Livestock Farm", district="Colombo", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_009", recipient_name="Hanwella Dairy Unit", district="Colombo", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_010", recipient_name="Kaduwela Smallholder Farm", district="Colombo", assigned_vet_id="vet_officer_01"),
            # Jaffna (5 farms)
            Recipient(recipient_id="DEMO_FARM_011", recipient_name="Chavakachcheri Dairy Co-op", district="Jaffna", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_012", recipient_name="Nallur Livestock Unit", district="Jaffna", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_013", recipient_name="Point Pedro Cattle Farm", district="Jaffna", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_014", recipient_name="Karainagar Farm", district="Jaffna", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_015", recipient_name="Valvettithurai Dairy", district="Jaffna", assigned_vet_id="vet_officer_01"),
            # Galle (5 farms)
            Recipient(recipient_id="DEMO_FARM_016", recipient_name="Elpitiya Dairy Estate", district="Galle", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_017", recipient_name="Baddegama Livestock", district="Galle", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_018", recipient_name="Ambalangoda Farm", district="Galle", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_019", recipient_name="Karandeniya Dairy Station", district="Galle", assigned_vet_id="vet_officer_01"),
            Recipient(recipient_id="DEMO_FARM_020", recipient_name="Bentota Cattle Ranch", district="Galle", assigned_vet_id="vet_officer_01"),
        ]

    def add_recipient(self, recipient: Recipient) -> None:
        """Helper to add custom recipients in tests."""
        self._recipients.append(recipient)

    def list_assigned_recipients(
        self, vet_id: str, district: Optional[str] = None
    ) -> List[Recipient]:
        results = [r for r in self._recipients if r.assigned_vet_id == vet_id]
        if district:
            dist_title = district.strip().title()
            if dist_title in ["Moneragala", "Monaragala"]:
                dist_title = "Monaragala"
            elif dist_title in ["Nuwaraeliya", "Nuwara Eliya"]:
                dist_title = "Nuwara Eliya"
            results = [r for r in results if r.district == dist_title]
        return results

    def resolve_recipients(
        self, recipient_ids: List[str], vet_id: str
    ) -> List[Recipient]:
        # Deduplicate recipient_ids preserving order
        seen = set()
        clean_ids = []
        for rid in recipient_ids:
            trimmed = rid.strip()
            if trimmed and trimmed not in seen:
                seen.add(trimmed)
                clean_ids.append(trimmed)

        by_id = {r.recipient_id: r for r in self._recipients}
        resolved = []
        for rid in clean_ids:
            if rid not in by_id:
                raise ValueError(f"Recipient ID '{rid}' not found in directory.")
            r = by_id[rid]
            if r.assigned_vet_id != vet_id:
                raise ValueError(
                    f"Recipient ID '{rid}' is assigned to vet '{r.assigned_vet_id}', "
                    f"not requesting vet '{vet_id}'."
                )
            resolved.append(r)
        return resolved


# Singleton instance for default route injection
recipient_directory = InMemoryRecipientDirectory()
