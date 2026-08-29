"""Checkpoint 6D Parts 27, 29, 40: real DEVELOPMENT-only factor
transformation audit + diagnostic smoke.

Not a pytest suite (real network/DB calls over a real, bounded FIT_DEVELOPMENT
sample). Run directly:

    python -m components.geospatial_tracking.smoke_tests.run_factor_transformation_smoke

Uses ONLY real `FIT_DEVELOPMENT` forecast origins (Thailand) — NEVER
`HELD_OUT_FROM_MODEL_FITTING` or `SRI_LANKA_TRANSFER_CASE_STUDY` — to
assemble real `FeatureSnapshot`s (reusing the existing real GIS/weather
adapters and cache; a genuinely unavailable real source becomes
MISSING/BLOCKED, never a fabricated value or a switched provider),
build a real `FactorReferenceProfile`, and run one real
`FactorSnapshot` diagnostic.

Labels its output `DEVELOPMENT_FACTOR_TRANSFORMATION_DIAGNOSTIC` — never
"prediction." Computes NO `H_j_i`, NO `H_i`, NO relative-risk index, and
inspects NO future-target/outcome metric of any kind.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT, DEFAULT_SQLITE_DB_PATH, WEATHER_LOOKBACK_HOURS_DEV_DEFAULT
from ..repositories.sqlite_repository import SQLiteOutbreakRepository
from ..services.factors.audit import build_development_reference_audit
from ..services.factors.factor_snapshot import build_factor_snapshot
from ..services.factors.reference_profile import build_factor_reference_profile
from ..services.factors.transform_config import FactorTransformConfig
from ..services.features.assembler import assemble_feature_snapshot
from ..services.features.feature_policy import DEFAULT_HYDRORIVERS_SEARCH_RADIUS_KM, FeaturePolicy, LandCoverFeaturePolicy
from ..services.forecast_origin import build_forecast_origin_ledger
from ..services.geospatial.raster import LOCAL_GIS_CACHE_DIR
from ..services.model_fitting_exposure import fit_development_origins

DISEASE = "Lumpy skin disease"
LOCAL_DATA_ROOT = LOCAL_GIS_CACHE_DIR.parent
OUTPUT_DIR = LOCAL_DATA_ROOT / "factor_transforms"
FEATURE_SNAPSHOT_CACHE_DIR = LOCAL_DATA_ROOT / "feature_snapshots"

# Bounded real sample -- kept small deliberately (real weather API calls
# dominate runtime, ~30s/origin uncached). Thailand only: a real,
# already-verified FIT_DEVELOPMENT country from earlier checkpoints.
_SAMPLE_SIZE = 8
_GRID_HALF_EXTENT_KM = 5.0
_GRID_CELL_SIZE_KM = 2.5


def _build_policy() -> FeaturePolicy:
    return FeaturePolicy(
        disease=DISEASE, active_window_days=ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT,
        grid_half_extent_km=_GRID_HALF_EXTENT_KM, grid_cell_size_km=_GRID_CELL_SIZE_KM, weather_model="era5",
        weather_lookback_hours=WEATHER_LOOKBACK_HOURS_DEV_DEFAULT,
        landcover_policy=LandCoverFeaturePolicy(mode="YEAR_MATCHED_REFERENCE"),
        host_density_species=("cattle", "buffalo"), hydrology_include=True,
        hydrorivers_search_radius_km=DEFAULT_HYDRORIVERS_SEARCH_RADIUS_KM, elevation_include=False,
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


if __name__ == "__main__":
    db_path = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
    repo = SQLiteOutbreakRepository(db_path)
    try:
        all_origins = build_forecast_origin_ledger(repo, disease=DISEASE)
        dev_origins = fit_development_origins(all_origins)
        thailand_dev = sorted((o for o in dev_origins if o.country == "Thailand"), key=lambda o: o.forecast_origin_id)
        sample = thailand_dev[:_SAMPLE_SIZE]
        print(f"Real FIT_DEVELOPMENT sample: {len(sample)} Thailand origins (of {len(thailand_dev)} available)")

        policy = _build_policy()
        snapshots_by_origin_id: dict = {}
        n_blocked = 0
        for origin in sample:
            try:
                snap = assemble_feature_snapshot(repo, forecast_origin=origin, policy=policy)
            except Exception as exc:  # real adapter failure -- never fabricate a substitute
                print(f"  {origin.forecast_origin_id}: EXCEPTION during assembly -> BLOCKED ({exc})")
                n_blocked += 1
                continue
            if snap.readiness != "COMPLETE_FOR_ASSEMBLY":
                print(f"  {origin.forecast_origin_id}: readiness={snap.readiness} -> excluded from reference profile")
                n_blocked += 1
                continue
            snapshots_by_origin_id[origin.forecast_origin_id] = snap.as_dict()
            print(f"  {origin.forecast_origin_id}: COMPLETE_FOR_ASSEMBLY ({len(snap.grid_cells)} cells)")

        print(f"\n{len(snapshots_by_origin_id)} available / {n_blocked} blocked-or-missing of {len(sample)} sampled")

        transform_config = FactorTransformConfig()
        reference_profile = build_factor_reference_profile(
            fit_development_origins=sample, feature_snapshots_by_origin_id=snapshots_by_origin_id, transform_config=transform_config,
        )
        _write_json(OUTPUT_DIR / "factor_reference_profile.json", reference_profile.as_dict())
        print(f"\nfactor_reference_profile.json -> {OUTPUT_DIR / 'factor_reference_profile.json'}")
        print(json.dumps(reference_profile.as_dict(), indent=2, default=str))

        audit = build_development_reference_audit(
            fit_development_origins=sample, feature_snapshots_by_origin_id=snapshots_by_origin_id, reference_profile=reference_profile,
        )
        _write_json(OUTPUT_DIR / "factor_transform_audit.json", audit)
        print(f"\nfactor_transform_audit.json -> {OUTPUT_DIR / 'factor_transform_audit.json'}")

        if snapshots_by_origin_id:
            diagnostic_origin_id, diagnostic_snapshot = next(iter(snapshots_by_origin_id.items()))
            diagnostic_origin = next(o for o in sample if o.forecast_origin_id == diagnostic_origin_id)
            expected_cells = [c["grid_cell_id"] for c in diagnostic_snapshot["grid_cells"]]
            factor_snap = build_factor_snapshot(
                feature_snapshot=diagnostic_snapshot, forecast_origin_id=diagnostic_origin.forecast_origin_id, t0=diagnostic_origin.t0,
                expected_grid_cell_ids=expected_cells, active_source_ids=diagnostic_snapshot["active_source_ids"],
                reference_profile=reference_profile, transform_config=transform_config,
            )
            _write_json(OUTPUT_DIR / "factor_snapshot_smoke.json", factor_snap.as_dict())
            print(f"\nfactor_snapshot_smoke.json -> {OUTPUT_DIR / 'factor_snapshot_smoke.json'} "
                  f"({factor_snap.label}, status={factor_snap.status})")
            one_cell = expected_cells[0]
            print(json.dumps({
                "forecast_origin_id": factor_snap.forecast_origin_id,
                "factor_snapshot_id": factor_snap.factor_snapshot_id,
                "reference_profile_hash": factor_snap.reference_profile_hash,
                "factor_transform_config_hash": factor_snap.factor_transform_config_hash,
                "sample_cell": one_cell,
                "host_density_total_candidate": factor_snap.cell_factor_candidates[one_cell]["host_density_total"],
                "log1p_candidate": factor_snap.cell_factor_candidates[one_cell].get("LOG1P_ROBUST_REFERENCE_SCALE"),
                "empirical_cdf_candidate": factor_snap.cell_factor_candidates[one_cell].get("EMPIRICAL_CDF_REFERENCE"),
                "environmental_suitability_factor_status": factor_snap.environmental_component_vectors[one_cell]["environmental_suitability_factor_status"],
                "water_context_status": factor_snap.water_context_status[one_cell]["candidate_status"],
                "meteorology_spatial_mode": factor_snap.meteorology_by_cell[one_cell]["spatial_mode"],
                "source_strength_status": list(factor_snap.source_factor_status.values())[0]["candidate_status"] if factor_snap.source_factor_status else None,
                "blockers": factor_snap.blockers,
            }, indent=2, default=str))
        else:
            print("\nNo FeatureSnapshot was available -- no FactorSnapshot diagnostic could be run (honestly reported, not bypassed).")
    finally:
        repo.close()
