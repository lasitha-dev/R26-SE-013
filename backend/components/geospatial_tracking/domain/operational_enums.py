"""GEO-INT-01 enums for the Geospatial-owned operational-context boundary.

Deliberately separate from `domain/enums.py` (the Checkpoint 3 LIVE
scientific domain — `AnimalReport`/`OutbreakEpisode`/`ReportStatus`/
`RecordDomain`). Nothing in this module, or anywhere under
`services/operational/`, feeds a `RecordDomain.LIVE_OPERATIONAL_RECORD`
or is written to `OutbreakRepository` — see `GEOSPATIAL_INTELLIGENCE...`
this checkpoint's own report (Section L/O). This boundary exists to hand a
host-authenticated veterinarian a read-only operational snapshot for
Page 1/Page 2 overlays; it is not, and must never silently become, an
input to the scientific outbreak/forecast pipeline.
"""

from __future__ import annotations

from enum import Enum


class OperationalStatus(str, Enum):
    """Top-level result state of one `OperationalGeospatialContext` request.
    See `services/operational/context_service.py` for exactly which gate
    produces each value. Never combined/collapsed — a caller must be able
    to tell "no farms assigned" apart from "host data source unavailable"
    apart from "not a veterinarian"."""

    OK = "OK"
    UNAUTHORIZED = "UNAUTHORIZED"
    NON_VET_FORBIDDEN = "NON_VET_FORBIDDEN"
    NO_ASSIGNED_FARMS = "NO_ASSIGNED_FARMS"
    NO_VERIFIED_CLINICAL_CONTEXT = "NO_VERIFIED_CLINICAL_CONTEXT"
    OPERATIONAL_DATA_UNAVAILABLE = "OPERATIONAL_DATA_UNAVAILABLE"


class LocationStatus(str, Enum):
    """GPS usability of one operational farm record. `VALID` is the only
    status a `VerifiedClinicalContext` may be built on top of (Section 11's
    "farm has valid GPS" gate) — never inferred, never backfilled from a
    district name or any other guess (Section 9)."""

    VALID = "VALID"
    LOCATION_REQUIRED = "LOCATION_REQUIRED"


class OperationalDisease(str, Enum):
    """The only two diseases this boundary recognizes as clinically
    supported, matching the Checkpoint 4 scientific registry
    (`services/disease.py::SUPPORTED_DISEASES`). Anything else — including
    a missing/blank disease name — resolves to `None`
    (`disease_normalization.UNSUPPORTED_DISEASE`), never to one of these
    two by default."""

    LSD = "LSD"
    FMD = "FMD"


class ClinicalSemanticClass(str, Enum):
    """Semantic firewall (Section 12/13): a veterinarian-verified diagnostic
    case is neutral clinical evidence, never an epidemiological outbreak
    classification. `VERIFIED_CLINICAL_CONTEXT` is the ONLY value a
    `VerifiedClinicalContext` may carry. There is deliberately no
    "CONFIRMED_OUTBREAK" member here — that concept belongs solely to the
    scientific historical/live-outbreak domain (`domain.enums.RecordDomain`,
    `domain.models.OutbreakEpisode`) and must never be assigned by this
    boundary."""

    VERIFIED_CLINICAL_CONTEXT = "VERIFIED_CLINICAL_CONTEXT"


class TimestampBasis(str, Enum):
    """Section 14: what a `VerifiedClinicalContext` timestamp actually
    proves. Neither value may ever be read as biological disease onset or
    clinical observation time — the current diagnostic-case contract
    (`origin/main:backend/components/health_anomaly/router.py`) does not
    capture either of those."""

    VERIFICATION_TIME = "VERIFICATION_TIME"
    """When the veterinarian verified the case (host `verified_at`)."""

    CASE_CREATION_TIME = "CASE_CREATION_TIME"
    """When the case record was first created (host `created_at`) —
    a pure storage/workflow timestamp, not an onset or observation date."""
