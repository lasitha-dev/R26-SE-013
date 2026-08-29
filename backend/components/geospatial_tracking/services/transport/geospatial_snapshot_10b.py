"""Checkpoint 10B Part 3-4: framework-independent immutable runtime
snapshot.

**One scientific computation, reused by every transport.** The sole
scientific producer is `run_frozen_geospatial_runtime_analysis_10a`
(Checkpoint 10A, unchanged) -- this module never recomputes C0,
direction, rate, or reach. It only (a) calls that function exactly
once, (b) canonicalizes the result into a deterministic
`snapshot_id`, and (c) attaches the API protocol-identity fields the
scientific dataclass itself does not know about (Part 1: avoiding an
`application` <-> `integration/protocol` import cycle -- the core 10A
application result stays decoupled from HTTP protocol identity; this
module, one layer above both, does the attaching).

**Snapshot identity excludes** (Part 4): `generated_at`, cache hit/
miss, connection/request id, WebSocket chunk index/size, localhost
URL, port, machine path. Changing transport chunk size or re-running
the identical scientific computation at a later wall-clock time NEVER
changes `snapshot_id`.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from ...repositories.base import OutbreakRepository
from ...repositories.provider import create_outbreak_repository
from ..application.frozen_geospatial_analysis_10a import (
    FrozenGeospatialRuntimeAnalysis10A,
    run_frozen_geospatial_runtime_analysis_10a,
)
from ..integration.geospatial_api_protocol_10a import geospatial_api_protocol_hash_10a
from ..integration.geospatial_api_protocol_10a1 import geospatial_api_protocol_hash_10a1

SNAPSHOT_SCIENTIFIC_CONTENT_HASH_RULE_10B = (
    "SHA256 of the canonical JSON payload {forecast_origin_id, t0, runtime_data_mode, "
    "active_api_protocol_hash_10a1, eligible_sources (sorted by source_id), cells (sorted by "
    "scientific_cell_id), apparent_rate_context, nominal_reach_by_day, provenance, limitations} -- "
    "excludes generated_at, cache status, connection/request id, and any transport chunking metadata"
)


@contextmanager
def managed_repository_10b() -> Iterator[OutbreakRepository]:
    """Checkpoint 10B.1 Part 8: obtains its repository from the shared
    `repositories.provider.create_outbreak_repository()` boundary --
    never constructs `SQLiteOutbreakRepository` directly. Opened only
    for the duration of a cache-miss computation, closed immediately
    after -- never held open for an entire WebSocket connection or
    across a cache hit."""
    repo = create_outbreak_repository()
    try:
        yield repo
    finally:
        repo.close()


def canonical_scientific_payload_10b(analysis: FrozenGeospatialRuntimeAnalysis10A) -> dict:
    """Part 4. Deterministic ordering throughout -- `eligible_sources`/
    `cells` are already sorted by `source_id`/`scientific_cell_id` at
    the Checkpoint 10A application layer; this function performs no
    re-sort and no scientific transformation."""
    return {
        "forecast_origin_id": analysis.analysis_metadata.forecast_origin_id,
        "t0": analysis.analysis_metadata.t0,
        "runtime_data_mode": analysis.analysis_metadata.runtime_data_mode,
        "active_api_protocol_hash_10a1": geospatial_api_protocol_hash_10a1(),
        "eligible_sources": [s.as_dict() for s in analysis.eligible_sources],
        "cells": [c.as_dict() for c in analysis.cells],
        "apparent_rate_context": analysis.apparent_rate_context,
        "nominal_reach_by_day": [d.as_dict() for d in analysis.nominal_reach_by_day],
        "provenance": analysis.provenance,
        "limitations": list(analysis.limitations),
    }


def compute_snapshot_id_10b(analysis: FrozenGeospatialRuntimeAnalysis10A) -> str:
    canonical = json.dumps(canonical_scientific_payload_10b(analysis), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_snapshot_integrity_10b(snapshot: "GeospatialSnapshot10B") -> bool:
    """Checkpoint 10B.1 Part 6: recomputes `compute_snapshot_id_10b`
    (the SAME canonical hash function -- never a second formula) over
    `snapshot.analysis` and compares it against `snapshot.snapshot_id`.
    This verifies in-memory transport consistency only -- it is NOT
    cryptographic authenticity, database freshness, or external data
    provenance certification."""
    return compute_snapshot_id_10b(snapshot.analysis) == snapshot.snapshot_id


def transport_analysis_metadata_10b(analysis: FrozenGeospatialRuntimeAnalysis10A) -> dict:
    """Part 1 pre-flight fix: the serialized metadata additively carries
    BOTH the unchanged historical 10A hash and the active 10A.1 hash --
    attached here at the transport/serialization boundary, never inside
    the frozen `RuntimeAnalysisMetadata10A` dataclass itself."""
    metadata = dict(analysis.analysis_metadata.as_dict())
    metadata["historical_api_protocol_hash_10a"] = geospatial_api_protocol_hash_10a()
    metadata["active_api_protocol_hash_10a1"] = geospatial_api_protocol_hash_10a1()
    return metadata


@dataclass(frozen=True)
class GeospatialSnapshot10B:
    snapshot_id: str
    forecast_origin_id: str
    analysis: FrozenGeospatialRuntimeAnalysis10A
    transport_metadata: dict
    # Transport-only field (Part 3) -- when THIS immutable snapshot
    # object was instantiated. Deliberately NEVER an input to
    # `compute_snapshot_id_10b` (Part 4) -- recomputing the identical
    # scientific content later produces a different `generated_at_utc`
    # but the SAME `snapshot_id`.
    generated_at_utc: str

    def summary_payload(self) -> dict:
        return {
            "analysis_metadata": self.transport_metadata,
            "n_eligible_sources": len(self.analysis.eligible_sources),
            "apparent_rate_context": self.analysis.apparent_rate_context,
            "nominal_reach_by_day": [d.as_dict() for d in self.analysis.nominal_reach_by_day],
            "provenance": self.analysis.provenance,
            "limitations": list(self.analysis.limitations),
        }

    def sources_features(self) -> list[dict]:
        return [s.as_dict() for s in self.analysis.eligible_sources]

    def cells_features(self) -> list[dict]:
        return [c.as_dict() for c in self.analysis.cells]


def build_geospatial_snapshot_10b(
    repo: OutbreakRepository, forecast_origin_id: str, *, disease: str | None = None,
) -> GeospatialSnapshot10B:
    """The single scientific-computation call site for this checkpoint
    (Part 3) -- may raise `RuntimeAnalysisError10A`, propagated
    unchanged, never swallowed or converted into a fabricated result.

    FMD-02: `disease` is optional and threaded straight through to
    `run_frozen_geospatial_runtime_analysis_10a` unchanged -- this module
    performs no disease resolution/validation of its own (that already
    happens once, at the router boundary and again, defensively, inside
    the application layer); `disease=None` reproduces pre-FMD-02
    LSD-only behavior exactly."""
    analysis = run_frozen_geospatial_runtime_analysis_10a(repo, forecast_origin_id, disease=disease)
    snapshot_id = compute_snapshot_id_10b(analysis)
    return GeospatialSnapshot10B(
        snapshot_id=snapshot_id, forecast_origin_id=forecast_origin_id,
        analysis=analysis, transport_metadata=transport_analysis_metadata_10b(analysis),
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def compute_snapshot_with_managed_repository_10b(forecast_origin_id: str, *, disease: str | None = None) -> GeospatialSnapshot10B:
    with managed_repository_10b() as repo:
        return build_geospatial_snapshot_10b(repo, forecast_origin_id, disease=disease)
