"""Checkpoint 6B Part 21/23 + Checkpoint 6B.5 Parts 19/21: real-data
ST-DBSCAN smoke, hard-gated development-source universe, country-scoped
parameter candidates, and international/country-specific sensitivity.

Not a pytest suite (real network/DB calls over the real corpus). Run
directly:

    python -m components.geospatial_tracking.smoke_tests.run_stdbscan_smoke

Writes (local, gitignored under `local_data/`):

    manifests/model_fitting_exposure_manifest.csv          (6B Part 21 — unchanged, full 813-origin corpus)
    manifests/stdbscan_development_candidates.csv           (6B Part 21 — SUPERSEDED_BY_6B5, kept for methodological history)
    manifests/stdbscan_development_sensitivity.csv           (6B Part 21 — SUPERSEDED_BY_6B5, kept for methodological history)
    manifests/stdbscan_development_source_universe.csv       (6B.5 Part 19 — validated, hard-gated, de-duplicated sources)
    manifests/stdbscan_development_source_exclusions.csv     (6B.5 Part 19 — every excluded record, with reason)
    manifests/stdbscan_country_parameter_candidates.csv      (6B.5 Part 19 — country-scoped NN/temporal quantiles + audit)
    manifests/stdbscan_parameter_candidate_registry.csv      (6B.5 Part 19 — declarative candidate registry, all dimensions)
    manifests/stdbscan_international_development_sensitivity.csv  (6B.5 Part 19 — real, multi-country, MICRO+MACRO)
    manifests/stdbscan_thailand_development_sensitivity.csv  (6B.5 Part 19 — explicitly country-specific, not global evidence)
    st_cluster_snapshots/thailand_fit_development_smoke.json (6B Part 23.A)
    st_cluster_snapshots/sri_lanka_case_study_demo.json       (6B Part 23.B — case-study demo only)

Sri Lanka is run ONLY as a `GEOGRAPHIC_TRANSFER_CASE_STUDY` software
demonstration — never fed into any candidate-registry or
sensitivity-report computation in this script.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from ..config import DEFAULT_SQLITE_DB_PATH
from ..repositories.sqlite_repository import SQLiteOutbreakRepository
from ..services.forecast_origin import ForecastOrigin, build_forecast_origin_ledger
from ..services.geospatial.raster import LOCAL_GIS_CACHE_DIR
from ..services.model_fitting_exposure import build_model_fitting_exposure_manifest, fit_development_origins
from ..services.stdbscan.candidate_constants import ACTIVE_WINDOW_DAY_CANDIDATES, MIN_CORE_SUPPORT_CANDIDATES
from ..services.stdbscan.config import GpsCorePolicy, STDBSCANConfig, SOFTWARE_FIXTURE_ONLY, UNFROZEN_DEVELOPMENT_CANDIDATE
from ..services.stdbscan.development_sensitivity import build_config_sensitivity_report
from ..services.stdbscan.development_source_universe import build_fit_development_source_universe
from ..services.stdbscan.international_sensitivity import build_international_development_sensitivity_report
from ..services.stdbscan.parameter_candidates import build_country_scoped_parameter_candidates, build_legacy_parameter_candidate_report
from ..services.stdbscan.snapshot import build_st_cluster_snapshot

DISEASE = "Lumpy skin disease"
LOCAL_DATA_ROOT = LOCAL_GIS_CACHE_DIR.parent
MANIFEST_DIR = LOCAL_DATA_ROOT / "manifests"
SNAPSHOT_DIR = LOCAL_DATA_ROOT / "st_cluster_snapshots"

# Part 16's deterministic reduction rule, declared BEFORE any grid is
# executed: the primary grid crosses {LOW, MID, HIGH} paired
# spatial/temporal tiers x {2,3,4} min_core_supports x {2 GPS policies}
# at a fixed MID active_window_days; a small active-window-only
# sub-sweep separately covers the other 3 active_window_days candidates
# at the MID spatiotemporal tier / min_core_supports=2 / PRIMARY policy.
_GRID_MID_ACTIVE_WINDOW_DAYS = 14


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_model_fitting_exposure_manifest(repo):
    origins = build_forecast_origin_ledger(repo, disease=DISEASE)
    rows = [r.as_dict() for r in build_model_fitting_exposure_manifest(origins)]
    path = MANIFEST_DIR / "model_fitting_exposure_manifest.csv"
    _write_csv(path, rows, fieldnames=["forecast_origin_id", "t0", "country", "role", "purged_by_7_day_rule", "reason"])
    return path, origins


def write_legacy_superseded_candidates_manifest(repo):
    """6B Part 21 output, unmodified computation — kept ONLY for
    methodological history/comparison (Part 21's "do not overwrite old
    6B manifests without preserving methodological history"). Never read
    by the real pipeline as of 6B.5 (see `parameter_candidates.py`)."""
    records = repo.list_historical_records(disease=DISEASE)
    report = build_legacy_parameter_candidate_report(records)
    rows = [
        {"metric": "STATUS", "quantile": "n/a", "value": "SUPERSEDED_BY_6B5 — see stdbscan_country_parameter_candidates.csv "
         "for the hard-gated, country-scoped replacement (global, cross-country NN/temporal comparisons below are UNSAFE evidence)"},
        {"metric": "nearest_neighbor_distance_km", "quantile": "p25", "value": report.nearest_neighbor_distance_km_quantiles["p25"]},
        {"metric": "nearest_neighbor_distance_km", "quantile": "p50", "value": report.nearest_neighbor_distance_km_quantiles["p50"]},
        {"metric": "nearest_neighbor_distance_km", "quantile": "p75", "value": report.nearest_neighbor_distance_km_quantiles["p75"]},
        {"metric": "positive_temporal_gap_days", "quantile": "p25", "value": report.positive_temporal_gap_days_quantiles["p25"]},
        {"metric": "positive_temporal_gap_days", "quantile": "p50", "value": report.positive_temporal_gap_days_quantiles["p50"]},
        {"metric": "positive_temporal_gap_days", "quantile": "p75", "value": report.positive_temporal_gap_days_quantiles["p75"]},
        {"metric": "n_records_considered", "quantile": "n/a", "value": report.n_records_considered},
        {"metric": "n_fit_development_usable_records", "quantile": "n/a", "value": report.n_fit_development_usable_records},
        {"metric": "pathological_note", "quantile": "n/a", "value": report.pathological_note or ""},
    ]
    path = MANIFEST_DIR / "stdbscan_development_candidates.csv"
    _write_csv(path, rows, fieldnames=["metric", "quantile", "value"])
    return path, report


def write_legacy_superseded_sensitivity_manifest(repo, *, dev_origins, eps_space_km, eps_time_days):
    thailand_sample = sorted((o for o in dev_origins if o.country == "Thailand"), key=lambda o: o.forecast_origin_id)
    rows = []
    for active_window_days in ACTIVE_WINDOW_DAY_CANDIDATES:
        for policy in (GpsCorePolicy.PRIMARY_CORE_SUPPORT, GpsCorePolicy.EXACT_ONLY_CORE_SUPPORT):
            config = STDBSCANConfig(
                eps_space_km=eps_space_km, eps_time_days=eps_time_days, min_core_supports=2,
                active_window_days=active_window_days, gps_core_policy=policy.value,
                parameter_status=UNFROZEN_DEVELOPMENT_CANDIDATE,
            )
            report = build_config_sensitivity_report(
                repo, fit_development_origins=thailand_sample, disease=DISEASE, config=config,
                scope_label="SUPERSEDED_BY_6B5_GLOBAL_EPS_THAILAND_ORIGINS",
            )
            row = report.as_dict()
            row["config"] = json.dumps(row["config"])
            row["cluster_size_distribution"] = ";".join(str(v) for v in row["cluster_size_distribution"])
            row["gps_quality_composition"] = json.dumps(row["gps_quality_composition"])
            rows.append(row)
    path = MANIFEST_DIR / "stdbscan_development_sensitivity.csv"
    _write_csv(path, rows, fieldnames=list(rows[0].keys()))
    return path, rows


def write_source_universe_manifests(repo, *, all_origins):
    result = build_fit_development_source_universe(repo, all_origins, disease=DISEASE)
    universe_path = MANIFEST_DIR / "stdbscan_development_source_universe.csv"
    _write_csv(
        universe_path, [s.as_dict() for s in result.sources],
        fieldnames=["source_id", "country", "first_fit_origin_t0_seen", "last_fit_origin_t0_seen",
                    "effective_availability_date", "availability_quality", "cluster_event_date",
                    "cluster_event_date_quality", "cluster_event_date_source_field", "latitude", "longitude",
                    "gps_quality", "dedup_status", "model_candidate"],
    )
    exclusions_path = MANIFEST_DIR / "stdbscan_development_source_exclusions.csv"
    _write_csv(exclusions_path, [e.as_dict() for e in result.exclusions], fieldnames=["source_id", "country", "reason_code", "reason"])
    return universe_path, exclusions_path, result


def write_country_parameter_candidates_manifest(sources):
    report = build_country_scoped_parameter_candidates(sources)
    rows = []
    for row in report.per_country_nn_distance:
        rows.append({"section": "PER_COUNTRY_NN", **row, "n_unique_sources_with_event_date": "", "max_window_days": ""})
    for row in report.per_country_temporal_gap:
        rows.append({"section": "PER_COUNTRY_TEMPORAL_GAP", "country": row["country"], "n_unique_sources": "",
                      "p25": row["p25"], "p50": row["p50"], "p75": row["p75"],
                      "n_unique_sources_with_event_date": row["n_unique_sources_with_event_date"], "max_window_days": ""})
    pooled_nn = report.pooled_within_country_nn_distance_km_quantiles
    rows.append({"section": "POOLED_WITHIN_COUNTRY_NN", "country": "ALL", "n_unique_sources": report.n_sources_considered,
                 "p25": pooled_nn["p25"], "p50": pooled_nn["p50"], "p75": pooled_nn["p75"],
                 "n_unique_sources_with_event_date": "", "max_window_days": ""})
    pooled_gap = report.pooled_within_country_temporal_gap_days_quantiles
    rows.append({"section": "POOLED_WITHIN_COUNTRY_TEMPORAL_GAP", "country": "ALL", "n_unique_sources": "",
                 "p25": pooled_gap["p25"], "p50": pooled_gap["p50"], "p75": pooled_gap["p75"],
                 "n_unique_sources_with_event_date": "", "max_window_days": ""})
    audit = report.temporally_local_nn_distance_audit_km_quantiles
    rows.append({"section": "TEMPORALLY_LOCAL_NN_DISTANCE_AUDIT", "country": "ALL", "n_unique_sources": "",
                 "p25": audit["p25"], "p50": audit["p50"], "p75": audit["p75"],
                 "n_unique_sources_with_event_date": "", "max_window_days": report.temporally_local_nn_audit_max_window_days})
    path = MANIFEST_DIR / "stdbscan_country_parameter_candidates.csv"
    _write_csv(path, rows, fieldnames=["section", "country", "n_unique_sources", "p25", "p50", "p75",
                                        "n_unique_sources_with_event_date", "max_window_days"])
    return path, report


def write_parameter_candidate_registry_manifest(country_report):
    rows = []
    for tier_label, key in (("LOW", "p25"), ("MID", "p50"), ("HIGH", "p75")):
        rows.append({"dimension": "eps_space_km", "label": tier_label,
                     "value": country_report.pooled_within_country_nn_distance_km_quantiles[key],
                     "provenance": f"pooled within-country NN distance {key} (Part 7)"})
        rows.append({"dimension": "eps_time_days", "label": tier_label,
                     "value": country_report.pooled_within_country_temporal_gap_days_quantiles[key],
                     "provenance": f"pooled within-country positive temporal gap {key} (Part 8)"})
    for v in MIN_CORE_SUPPORT_CANDIDATES:
        rows.append({"dimension": "min_core_supports", "label": "CANDIDATE", "value": v, "provenance": "fixed development candidate, unfrozen (Part 10)"})
    for v in ACTIVE_WINDOW_DAY_CANDIDATES:
        rows.append({"dimension": "active_window_days", "label": "CANDIDATE", "value": v, "provenance": "fixed, not data-derived (6B Part 17)"})
    for p in (GpsCorePolicy.PRIMARY_CORE_SUPPORT, GpsCorePolicy.EXACT_ONLY_CORE_SUPPORT):
        rows.append({"dimension": "gps_core_policy", "label": "CANDIDATE", "value": p.value, "provenance": "fixed, both reported side-by-side (6B Part 10-11)"})
    rows.append({"dimension": "note", "label": "n/a", "value": "duplicate numeric values across tiers are not pre-deduplicated in this "
                 "declarative registry (each row keeps its own label/provenance per Part 11); the executed sensitivity grid may skip a "
                 "tier if its quantile is None (pathological)", "provenance": "Part 11"})
    path = MANIFEST_DIR / "stdbscan_parameter_candidate_registry.csv"
    _write_csv(path, rows, fieldnames=["dimension", "label", "value", "provenance"])
    return path


def _build_reduced_grid(*, nn_quantiles: dict, gap_quantiles: dict) -> list[tuple[str, STDBSCANConfig]]:
    """Part 16's deterministic, predeclared reduced grid (see module
    docstring) — declared BEFORE any config is executed, never adjusted
    based on resulting cluster counts."""
    configs: list[tuple[str, STDBSCANConfig]] = []
    for tier_label, q_key in (("LOW", "p25"), ("MID", "p50"), ("HIGH", "p75")):
        eps_space = nn_quantiles[q_key]
        eps_time = gap_quantiles[q_key]
        if eps_space is None or eps_time is None or eps_space <= 0:
            continue
        for min_core in MIN_CORE_SUPPORT_CANDIDATES:
            for policy in (GpsCorePolicy.PRIMARY_CORE_SUPPORT, GpsCorePolicy.EXACT_ONLY_CORE_SUPPORT):
                label = f"{tier_label}_minpts{min_core}_{policy.value}_win{_GRID_MID_ACTIVE_WINDOW_DAYS}"
                cfg = STDBSCANConfig(
                    eps_space_km=eps_space, eps_time_days=eps_time, min_core_supports=min_core,
                    active_window_days=_GRID_MID_ACTIVE_WINDOW_DAYS, gps_core_policy=policy.value,
                    parameter_status=UNFROZEN_DEVELOPMENT_CANDIDATE,
                )
                configs.append((label, cfg))

    mid_space, mid_time = nn_quantiles["p50"], gap_quantiles["p50"]
    if mid_space is not None and mid_time is not None and mid_space > 0:
        for window in ACTIVE_WINDOW_DAY_CANDIDATES:
            if window == _GRID_MID_ACTIVE_WINDOW_DAYS:
                continue
            label = f"MID_minpts2_PRIMARY_CORE_SUPPORT_win{window}"
            cfg = STDBSCANConfig(
                eps_space_km=mid_space, eps_time_days=mid_time, min_core_supports=2, active_window_days=window,
                gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value, parameter_status=UNFROZEN_DEVELOPMENT_CANDIDATE,
            )
            configs.append((label, cfg))
    return configs


def write_international_sensitivity_manifest(repo, *, dev_origins, country_report):
    grid = _build_reduced_grid(
        nn_quantiles=country_report.pooled_within_country_nn_distance_km_quantiles,
        gap_quantiles=country_report.pooled_within_country_temporal_gap_days_quantiles,
    )
    rows = []
    start = time.time()
    for label, cfg in grid:
        report = build_international_development_sensitivity_report(
            repo, fit_development_origins=dev_origins, disease=DISEASE, config=cfg
        )
        rows.append({
            "grid_label": label,
            "config_hash": report.config_hash,
            "config": json.dumps(report.config),
            "n_origins_evaluated": report.n_origins_evaluated,
            "n_countries": report.n_countries,
            "micro_summary": json.dumps(report.micro_summary),
            "macro_country_summary": json.dumps(report.macro_country_summary),
        })
    elapsed = time.time() - start
    path = MANIFEST_DIR / "stdbscan_international_development_sensitivity.csv"
    _write_csv(path, rows, fieldnames=list(rows[0].keys()) if rows else ["grid_label"])
    return path, rows, elapsed


def write_thailand_sensitivity_manifest(repo, *, dev_origins, country_report):
    thailand_nn = next((c for c in country_report.per_country_nn_distance if c["country"] == "Thailand"), None)
    thailand_gap = next((c for c in country_report.per_country_temporal_gap if c["country"] == "Thailand"), None)
    if thailand_nn is None or thailand_gap is None:
        raise RuntimeError("Thailand has no country-scoped parameter candidates in the real corpus")
    nn_q = {"p25": thailand_nn["p25"], "p50": thailand_nn["p50"], "p75": thailand_nn["p75"]}
    gap_q = {"p25": thailand_gap["p25"], "p50": thailand_gap["p50"], "p75": thailand_gap["p75"]}
    grid = _build_reduced_grid(nn_quantiles=nn_q, gap_quantiles=gap_q)

    thailand_sample = sorted((o for o in dev_origins if o.country == "Thailand"), key=lambda o: o.forecast_origin_id)
    rows = []
    for label, cfg in grid:
        report = build_config_sensitivity_report(
            repo, fit_development_origins=thailand_sample, disease=DISEASE, config=cfg,
            scope_label="THAILAND_DEVELOPMENT_SENSITIVITY",
        )
        row = report.as_dict()
        row["grid_label"] = label
        row["config"] = json.dumps(row["config"])
        row["cluster_size_distribution"] = ";".join(str(v) for v in row["cluster_size_distribution"])
        row["gps_quality_composition"] = json.dumps(row["gps_quality_composition"])
        rows.append(row)
    path = MANIFEST_DIR / "stdbscan_thailand_development_sensitivity.csv"
    _write_csv(path, rows, fieldnames=["grid_label"] + [k for k in rows[0].keys() if k != "grid_label"] if rows else ["grid_label"])
    return path, rows


def _summarize_snapshot(snap) -> dict:
    return {
        "forecast_origin_id": snap.forecast_origin_id,
        "t0": snap.t0,
        "country_scope": snap.country_scope,
        "active_source_count": len(snap.active_source_ids),
        "cluster_usable_count": len(snap.cluster_usable_source_ids),
        "temporal_unusable_count": len(snap.temporal_unusable_source_ids),
        "cluster_count": len(snap.clusters),
        "noise_count": len(snap.noise_source_ids),
        "cluster_sizes": [c["member_count"] for c in snap.clusters],
        "gps_quality_composition": {q: list(snap.source_gps_quality.values()).count(q) for q in set(snap.source_gps_quality.values())},
        "config_status": snap.config.get("parameter_status"),
    }


def _save(snapshot_dict: dict, filename: str) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot_dict, f, indent=2, ensure_ascii=False, default=str)
    return path


if __name__ == "__main__":
    db_path = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
    repo = SQLiteOutbreakRepository(db_path)
    try:
        exposure_path, all_origins = write_model_fitting_exposure_manifest(repo)
        print(f"model_fitting_exposure_manifest.csv -> {exposure_path}")

        legacy_candidates_path, legacy_report = write_legacy_superseded_candidates_manifest(repo)
        print(f"stdbscan_development_candidates.csv (SUPERSEDED_BY_6B5) -> {legacy_candidates_path}")

        dev_origins = fit_development_origins(all_origins)

        legacy_eps_space = legacy_report.nearest_neighbor_distance_km_quantiles["p50"] or 25.0
        legacy_eps_time = legacy_report.positive_temporal_gap_days_quantiles["p75"] or 7.0
        legacy_sens_path, _ = write_legacy_superseded_sensitivity_manifest(
            repo, dev_origins=dev_origins, eps_space_km=legacy_eps_space, eps_time_days=legacy_eps_time
        )
        print(f"stdbscan_development_sensitivity.csv (SUPERSEDED_BY_6B5) -> {legacy_sens_path}")

        # ---- Checkpoint 6B.5: the real, safe path ----------------------
        universe_path, exclusions_path, universe_result = write_source_universe_manifests(repo, all_origins=all_origins)
        print(f"\nstdbscan_development_source_universe.csv -> {universe_path} ({universe_result.n_validated_sources} validated sources)")
        print(f"stdbscan_development_source_exclusions.csv -> {exclusions_path} ({len(universe_result.exclusions)} exclusions)")
        print(f"exclusion counts by reason: {universe_result.exclusion_counts_by_reason()}")
        print(f"n_records_considered (real corpus): {universe_result.n_records_considered}")

        country_candidates_path, country_report = write_country_parameter_candidates_manifest(universe_result.sources)
        print(f"\nstdbscan_country_parameter_candidates.csv -> {country_candidates_path}")
        print(json.dumps(country_report.as_dict(), indent=2, default=str))

        registry_path = write_parameter_candidate_registry_manifest(country_report)
        print(f"\nstdbscan_parameter_candidate_registry.csv -> {registry_path}")

        intl_path, intl_rows, intl_elapsed = write_international_sensitivity_manifest(
            repo, dev_origins=dev_origins, country_report=country_report
        )
        print(f"\nstdbscan_international_development_sensitivity.csv -> {intl_path} "
              f"({len(intl_rows)} grid configs, {intl_elapsed:.1f}s for {len(dev_origins)} real FIT_DEVELOPMENT origins per config)")

        thailand_path, thailand_rows = write_thailand_sensitivity_manifest(repo, dev_origins=dev_origins, country_report=country_report)
        print(f"stdbscan_thailand_development_sensitivity.csv (THAILAND_DEVELOPMENT_SENSITIVITY, country-specific only) -> {thailand_path} ({len(thailand_rows)} grid configs)")

        # ---- Part 23: Thailand FIT_DEVELOPMENT + Sri Lanka case-study --
        thailand_origin = ForecastOrigin(
            forecast_origin_id="ORIGIN:Thailand:2021-04-07", country="Thailand", t0="2021-04-07",
            temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["WAHIS_PDF:Event_3644.pdf:002425"],
            trigger_source_count=1,
        )
        smoke_config = STDBSCANConfig(
            eps_space_km=50.0, eps_time_days=14, min_core_supports=2, active_window_days=30,
            gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value, parameter_status=SOFTWARE_FIXTURE_ONLY,
        )
        th_snap = build_st_cluster_snapshot(
            repo, forecast_origin_id=thailand_origin.forecast_origin_id, t0=thailand_origin.t0,
            country_scope=thailand_origin.country, disease=DISEASE, config=smoke_config,
        )
        th_path = _save(th_snap.as_dict(), "thailand_fit_development_smoke.json")
        print(f"\nThailand FIT_DEVELOPMENT smoke -> {th_path}")
        print(json.dumps(_summarize_snapshot(th_snap), indent=2, default=str))

        sl_origin = ForecastOrigin(
            forecast_origin_id="ORIGIN:Sri Lanka:2020-09-09", country="Sri Lanka", t0="2020-09-09",
            temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["WAHIS_PDF:Event_3473.pdf:002408"],
            trigger_source_count=1,
        )
        sl_snap = build_st_cluster_snapshot(
            repo, forecast_origin_id=sl_origin.forecast_origin_id, t0=sl_origin.t0,
            country_scope=sl_origin.country, disease=DISEASE, config=smoke_config,
        )
        sl_path = _save(sl_snap.as_dict(), "sri_lanka_case_study_demo.json")
        print(f"\nSri Lanka GEOGRAPHIC_TRANSFER_CASE_STUDY demo (software demonstration only) -> {sl_path}")
        print(json.dumps(_summarize_snapshot(sl_snap), indent=2, default=str))
    finally:
        repo.close()
