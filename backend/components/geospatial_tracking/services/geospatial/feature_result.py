"""Checkpoint 5 Part 15: the common feature-result contract.

Every geospatial/environmental adapter in this package returns
`FeatureResult` objects — downstream (future) model code never receives a
naked number with no provenance. `status` is the permanent-rule
enforcement point (master-prompt "Never fabricate GIS/environmental
values"):

    REAL    — a genuine value was retrieved/computed from a real,
              verified source and is usable as such.
    MISSING — the source was reachable but had no data for this
              location/time (e.g. nodata pixel, no station coverage).
    BLOCKED — the source could not be retrieved at all (network/auth/
              file-availability failure) — never silently swapped for a
              plausible-looking default.
    DEMO    — a placeholder/synthetic value for interface demonstration
              only. **`assert_not_demo_for_scientific_use` (PROV-02) must
              be called, or an equivalent check performed, before any
              DEMO-status result is allowed anywhere near scientific
              validation.**

`value` is `None` whenever `status` is not `REAL` — never a fabricated
number "just in case," per the permanent rule (no `land_cover =
grassland`, `wind = 3 m/s`, etc. fallback defaults).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FeatureStatus(str, Enum):
    REAL = "REAL"
    MISSING = "MISSING"
    BLOCKED = "BLOCKED"
    DEMO = "DEMO"


@dataclass
class FeatureResult:
    feature_name: str
    value: Any
    units: str | None
    status: str  # FeatureStatus value
    dataset_name: str | None
    dataset_version: str | None
    reference_time: str | None  # reference year/timestamp the data represents
    retrieved_at: str | None  # ISO timestamp this extraction actually ran
    source_resolution: str | None
    source_crs: str | None
    analysis_method: str | None
    quality_notes: str
    # Checkpoint 6D.5: an OPTIONAL, adapter-supplied stable identifier for
    # the specific underlying real sample(s) (e.g. raster pixel(s)) this
    # value was actually derived from — distinct from the query location
    # that TRIGGERED the extraction. `None` when an adapter cannot derive
    # one (never fabricated); populated only from real, already-computed
    # sampling geometry (see `host_density/fao_glw.py`). Every existing
    # caller is unaffected — this field defaults to `None`.
    sample_identity: str | None = None
    # Checkpoint 6D.6: the CORRECTED effective-extraction identity — a
    # digest of the full weighted contribution support (which real
    # samples contributed AND their normalized effective weights), not
    # merely which samples were touched. `sample_identity` alone cannot
    # distinguish two extractions that share a sample set but combined
    # it with different weights; `sample_support_digest` can. `None`
    # when an adapter cannot derive one (never fabricated).
    sample_support_digest: str | None = None
    sampling_protocol_version: str | None = None
    n_contributing_pixels: int | None = None

    def __post_init__(self) -> None:
        if self.status != FeatureStatus.REAL.value and self.value is not None:
            raise ValueError(
                f"FeatureResult({self.feature_name!r}) has status={self.status!r} but a non-None "
                "value — only REAL results may carry a value; MISSING/BLOCKED/DEMO must be None "
                "(never a fabricated fallback)."
            )

    def as_dict(self) -> dict:
        return {
            "feature_name": self.feature_name,
            "value": self.value,
            "units": self.units,
            "status": self.status,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "reference_time": self.reference_time,
            "retrieved_at": self.retrieved_at,
            "source_resolution": self.source_resolution,
            "source_crs": self.source_crs,
            "analysis_method": self.analysis_method,
            "quality_notes": self.quality_notes,
            "sample_identity": self.sample_identity,
            "sample_support_digest": self.sample_support_digest,
            "sampling_protocol_version": self.sampling_protocol_version,
            "n_contributing_pixels": self.n_contributing_pixels,
        }


def assert_not_demo_for_scientific_use(results: list[FeatureResult]) -> None:
    """PROV-02: raises if any result is DEMO-status — call this as a gate
    before any feature set is used for scientific validation. DEMO data
    must never silently enter that path."""
    demo = [r.feature_name for r in results if r.status == FeatureStatus.DEMO.value]
    if demo:
        raise ValueError(f"DEMO-status features cannot enter scientific validation: {demo}")
