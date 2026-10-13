"""GEO-INT-01 Section 11-14: the verified-clinical-context filter.

`build_verified_clinical_context` is the ONE place a raw `HostDiagnosticCase`
is allowed to become a `VerifiedClinicalContext`. Every gate in Section 11
is enforced here, in order, and a case failing any one of them is silently
excluded (returns `None`) — never repaired, never included with a caveat
(Section 11: "Do not silently repair malformed records").
"""

from __future__ import annotations

from ...domain.operational_models import HostDiagnosticCase, OperationalFarm, VerifiedClinicalContext
from .disease_normalization import resolve_operational_disease


def build_verified_clinical_context(
    case: HostDiagnosticCase,
    *,
    assigned_farms_by_id: dict[str, OperationalFarm],
) -> VerifiedClinicalContext | None:
    """Returns a `VerifiedClinicalContext` for `case`, or `None` if it does
    not qualify. Gate order follows Section 11's list:

    1. case identity exists
    2. verified == true
    3. farm_id exists AND belongs to the vet's assigned farms
    4. that farm has valid GPS (`LocationStatus.VALID`)
    5. disease is supported (LSD or FMD, never guessed)
    6. required operational timestamp (`verified_at`) is present
    """
    if not case.case_id or not case.case_id.strip():
        return None

    if not case.verified:
        return None

    if not case.farm_id:
        return None
    farm = assigned_farms_by_id.get(case.farm_id)
    if farm is None:
        return None

    if farm.location_status != "VALID":
        return None

    disease = resolve_operational_disease(case.disease_name)
    if disease is None:
        return None

    if not case.verified_at or not case.verified_at.strip():
        return None

    return VerifiedClinicalContext(
        case_id=case.case_id,
        farm_id=case.farm_id,
        disease=disease.value,
        verification_time=case.verified_at,
        case_creation_time=case.created_at,
    )
