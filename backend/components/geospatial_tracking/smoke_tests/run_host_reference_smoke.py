"""Checkpoint 6D.5 Parts 17-21: real, FULL-FIT_DEVELOPMENT-universe host
reference profile — no weather I/O.

Not a pytest suite (real DB/raster-cache calls over the REAL
`FIT_DEVELOPMENT` universe, runtime-derived at run time — never
hardcoded). Run directly:

    python -m components.geospatial_tracking.smoke_tests.run_host_reference_smoke

Uses `services/factors/host_reference_gathering.py` — the SAME real
`source_selector`/`grid`/GLW4 adapters the full assembler uses, but
skips weather/land-cover/hydrology entirely, since the host-density
reference distribution depends on none of them (Part 17). This lets
the ENTIRE real `FIT_DEVELOPMENT` origin universe be processed in
roughly a minute rather than the ~30s/origin the weather-inclusive path
would need.

Reports honest global-readiness (Part 16, 20): `GLOBAL_REFERENCE_PROFILE_READY`
only if every origin in the real, runtime-derived `FIT_DEVELOPMENT`
universe was actually processed; otherwise
`GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY` — this script never claims
readiness it hasn't earned. Also reports the LOG1P clipping audit over
the whole processed universe (Part 21), grouped by country — never
generalized from one cell.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT, DEFAULT_SQLITE_DB_PATH
from ..repositories.sqlite_repository import SQLiteOutbreakRepository
from ..services.factors.audit import build_development_clipping_audit, build_development_reference_audit
from ..services.factors.host_reference_gathering import build_host_only_snapshot
from ..services.factors.reference_profile import build_factor_reference_profile
from ..services.factors.transform_config import FactorTransformConfig
from ..services.forecast_origin import build_forecast_origin_ledger
from ..services.geospatial.raster import LOCAL_GIS_CACHE_DIR
from ..services.model_fitting_exposure import fit_development_origins

DISEASE = "Lumpy skin disease"
LOCAL_DATA_ROOT = LOCAL_GIS_CACHE_DIR.parent
OUTPUT_DIR = LOCAL_DATA_ROOT / "factor_transforms"
_GRID_HALF_EXTENT_KM = 5.0
_GRID_CELL_SIZE_KM = 2.5


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


if __name__ == "__main__":
    db_path = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
    repo = SQLiteOutbreakRepository(db_path)
    try:
        all_origins = build_forecast_origin_ledger(repo, disease=DISEASE)
        dev_origins = fit_development_origins(all_origins)  # the REAL, runtime-derived FIT_DEVELOPMENT universe -- never hardcoded
        total_universe_ids = [o.forecast_origin_id for o in dev_origins]
        print(f"Real FIT_DEVELOPMENT universe (runtime-derived): {len(dev_origins)} origins across "
              f"{len(sorted({o.country for o in dev_origins}))} countries")

        snapshots_by_origin_id: dict = {}
        n_no_sources = 0
        for i, origin in enumerate(dev_origins):
            snap = build_host_only_snapshot(
                repo, origin=origin, disease=DISEASE, active_window_days=ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT,
                grid_half_extent_km=_GRID_HALF_EXTENT_KM, grid_cell_size_km=_GRID_CELL_SIZE_KM,
            )
            if snap is None:
                n_no_sources += 1
                continue
            snapshots_by_origin_id[origin.forecast_origin_id] = snap
            if (i + 1) % 100 == 0:
                print(f"  ... {i + 1}/{len(dev_origins)} origins processed")

        print(f"\n{len(snapshots_by_origin_id)} host-only snapshots built / {n_no_sources} origins had no eligible sources / {len(dev_origins)} total")

        transform_config = FactorTransformConfig()
        reference_profile = build_factor_reference_profile(
            fit_development_origins=dev_origins, feature_snapshots_by_origin_id=snapshots_by_origin_id, transform_config=transform_config,
        )
        _write_json(OUTPUT_DIR / "factor_reference_profile.json", reference_profile.as_dict())
        print(f"\nfactor_reference_profile.json (FULL FIT_DEVELOPMENT universe) -> {OUTPUT_DIR / 'factor_reference_profile.json'}")
        print(json.dumps(reference_profile.as_dict(), indent=2, default=str))

        audit = build_development_reference_audit(
            fit_development_origins=dev_origins, feature_snapshots_by_origin_id=snapshots_by_origin_id,
            reference_profile=reference_profile, total_fit_development_origin_ids=total_universe_ids,
        )
        _write_json(OUTPUT_DIR / "factor_transform_audit.json", audit)
        print(f"\nfactor_transform_audit.json -> {OUTPUT_DIR / 'factor_transform_audit.json'}")
        print(json.dumps(audit, indent=2, default=str))

        if reference_profile.status == "COMPLETE_DIAGNOSTIC":
            clipping = build_development_clipping_audit(
                feature_snapshots_by_origin_id=snapshots_by_origin_id, reference_profile=reference_profile, transform_config=transform_config,
            )
            _write_json(OUTPUT_DIR / "host_transform_clipping_audit.json", clipping)
            print(f"\nclipping audit (LOG1P_ROBUST_REFERENCE_SCALE, real FIT_DEVELOPMENT universe):")
            print(json.dumps(clipping, indent=2, default=str))
        else:
            print(f"\nreference_profile.status={reference_profile.status!r} -- skipping clipping audit (no usable pooled transform)")

        print(f"\nGLOBAL_REFERENCE_PROFILE STATUS: {audit['global_reference_profile_status']}")
    finally:
        repo.close()
