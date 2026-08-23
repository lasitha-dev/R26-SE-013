"""
Veterinary Officer Directory Integration Boundary (Phase 6B-1).

Defines the VeterinaryOfficerDirectory contract for resolving Veterinary Officers,
verifying active status, and validating district assignment bounds.

Provides an in-memory standalone test double pre-seeded with sample Vet officers.

PRODUCTION REPLACEMENT PATH:
In production integration, InMemoryVeterinaryOfficerDirectory will be replaced by an adapter
querying the central Ministry of Agriculture / DAPH HR and IAM User Directory API.
"""

from typing import List, Optional, Protocol
from pydantic import BaseModel, Field
from backend.components.risk_forecasting.config import SRI_LANKA_DISTRICTS


class VeterinaryOfficerSummary(BaseModel):
    """Minimal Veterinary Officer metadata required for follow-up assignment verification."""
    vet_id: str = Field(..., description="Unique Veterinary Officer identifier.")
    display_name: str = Field(..., description="Human-readable officer display name.")
    assigned_districts: List[str] = Field(default_factory=list, description="Districts assigned to this officer.")
    active: bool = Field(default=True, description="Whether the officer account is active.")


class VeterinaryOfficerDirectory(Protocol):
    """Protocol defining the Veterinary Officer Directory contract."""

    def get_vet(self, vet_id: str) -> Optional[VeterinaryOfficerSummary]:
        """Retrieves officer summary by vet_id."""
        ...

    def list_vets_by_district(self, district: str) -> List[VeterinaryOfficerSummary]:
        """Lists active officers assigned to a specific Sri Lankan district."""
        ...

    def is_vet_assigned_to_district(self, vet_id: str, district: str) -> bool:
        """Validates whether an officer exists, is active, and is assigned to the specified district."""
        ...


class InMemoryVeterinaryOfficerDirectory:
    """
    In-memory test double implementation of VeterinaryOfficerDirectory.
    Pre-seeded with operational demo Veterinary Officers across Sri Lankan districts.
    """

    def __init__(self):
        self._vets: List[VeterinaryOfficerSummary] = [
            VeterinaryOfficerSummary(
                vet_id="vet_officer_01",
                display_name="Dr. Nimal Perera (District Veterinary Officer)",
                assigned_districts=["Anuradhapura", "Colombo", "Jaffna", "Galle", "Kandy", "Polonnaruwa"],
                active=True,
            ),
            VeterinaryOfficerSummary(
                vet_id="vet_officer_02",
                display_name="Dr. Sunethra Silva (Regional Veterinary Specialist)",
                assigned_districts=["Kurunegala", "Puttalam", "Gampaha", "Kegalle"],
                active=True,
            ),
            VeterinaryOfficerSummary(
                vet_id="DEMO_USER_VET_NORTH",
                display_name="Dr. K. Arul (Northern Province Veterinary Officer)",
                assigned_districts=["Jaffna", "Kilinochchi", "Mannar", "Vavuniya", "Mullaitivu", "Anuradhapura"],
                active=True,
            ),
            VeterinaryOfficerSummary(
                vet_id="DEMO_USER_VET_SOUTH",
                display_name="Dr. Priyantha Fernando (Southern Region Veterinary Officer)",
                assigned_districts=["Galle", "Matara", "Hambantota", "Ratnapura", "Monaragala"],
                active=True,
            ),
            VeterinaryOfficerSummary(
                vet_id="vet_inactive_01",
                display_name="Dr. Retired Officer (Inactive Account)",
                assigned_districts=["Anuradhapura", "Colombo"],
                active=False,
            ),
        ]

    def _normalize_district(self, district: str) -> str:
        formatted = district.strip().title()
        if formatted in ["Moneragala", "Monaragala"]:
            return "Monaragala"
        elif formatted in ["Nuwaraeliya", "Nuwara Eliya"]:
            return "Nuwara Eliya"
        return formatted

    def add_vet(self, vet: VeterinaryOfficerSummary) -> None:
        """Helper for adding custom vet officer entries in tests."""
        self._vets.append(vet)

    def get_vet(self, vet_id: str) -> Optional[VeterinaryOfficerSummary]:
        clean_id = vet_id.strip()
        for vet in self._vets:
            if vet.vet_id == clean_id:
                return vet.model_copy(deep=True)
        return None

    def list_vets_by_district(self, district: str) -> List[VeterinaryOfficerSummary]:
        norm_dist = self._normalize_district(district)
        results = []
        for vet in self._vets:
            if vet.active:
                norm_assigned = [self._normalize_district(d) for d in vet.assigned_districts]
                if norm_dist in norm_assigned:
                    results.append(vet.model_copy(deep=True))
        return results

    def is_vet_assigned_to_district(self, vet_id: str, district: str) -> bool:
        vet = self.get_vet(vet_id)
        if not vet or not vet.active:
            return False
        norm_dist = self._normalize_district(district)
        norm_assigned = [self._normalize_district(d) for d in vet.assigned_districts]
        return norm_dist in norm_assigned


# Singleton instance for default injection
veterinary_officer_directory = InMemoryVeterinaryOfficerDirectory()
