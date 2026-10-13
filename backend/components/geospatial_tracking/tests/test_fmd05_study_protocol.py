"""FMD-05: study-cohort / forecast-origin / target-semantics / split
protocol freeze tests.

Reads the already-generated, already-reproducibility-verified cohort
artifacts (`local_data/processed/fmd/cohort/*`, produced by
`data_processing/build_fmd_cohort.py` — see `FMD_STUDY_PROTOCOL.md` for
the two-independent-run byte-identical hash evidence) rather than
re-running the full pipeline on every test collection: a real full run
against the 9,526-row corpus takes ~79s (SQLite import + per-origin
target queries), which would be an unreasonable cost to pay twice on
every `pytest components -q` invocation. Determinism of the PURE
(no I/O) cohort-row-building logic is instead re-verified directly and
cheaply (`test_fmd05_05_cohort_row_building_is_deterministic`).

All paths are resolved relative to `__file__`, never to the process's
current working directory, so these tests behave identically whether
invoked as `pytest components/geospatial_tracking/tests/...` from
`backend/` or via any other pytest rootdir.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent  # .../geospatial_tracking/tests
_GEOSPATIAL_TRACKING_DIR = _THIS_DIR.parent  # .../geospatial_tracking
_REPO_ROOT = _THIS_DIR.parents[3]  # .../R26-SE-013 (tests -> geospatial_tracking -> components -> backend -> repo root)

CANONICAL_CSV = _REPO_ROOT / "local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
COHORT_DIR = _REPO_ROOT / "local_data/processed/fmd/cohort"
COHORT_MANIFEST = COHORT_DIR / "FMD_COHORT_MANIFEST.json"
COHORT_AUDIT = COHORT_DIR / "FMD_COHORT_AUDIT.csv"
FORECAST_TARGETS_CSV = COHORT_DIR / "fmd_historical_forecast_targets.csv"
ELIGIBILITY_CSV = _GEOSPATIAL_TRACKING_DIR / "FMD_FEATURE_ELIGIBILITY.csv"

CANONICAL_SHA256 = "11b4528d32fcb9f6f26cd537511b0d0fca531890a8af5d7480e94188d3d0114e"
EXPECTED_COHORT_AUDIT_SHA256 = "5e341065477055eb6b663175a02f0fafb4002aebc5f7ab0d9f2e956b41a7c96d"


def _load_manifest() -> dict:
    return json.loads(COHORT_MANIFEST.read_text(encoding="utf-8"))


def _load_audit_rows() -> list[dict]:
    with COHORT_AUDIT.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# -- 1. canonical corpus size ------------------------------------------------


def test_fmd05_01_canonical_corpus_is_9526():
    manifest = _load_manifest()
    assert manifest["canonical_event_count"] == 9526


# -- 2. every canonical row gets exactly one disposition ---------------------


def test_fmd05_02_every_canonical_row_has_disposition():
    rows = _load_audit_rows()
    assert len(rows) == 9526
    for row in rows:
        assert row["cohort_disposition"], f"missing disposition: {row['fmd_canonical_event_id']}"


def test_fmd05_03_included_count_is_9311():
    rows = _load_audit_rows()
    included = sum(1 for r in rows if r["cohort_disposition"] == "INCLUDED")
    assert included == 9311


def test_fmd05_04_excluded_count_is_215():
    rows = _load_audit_rows()
    excluded = sum(1 for r in rows if r["cohort_disposition"] != "INCLUDED")
    assert excluded == 215
    assert all(r["cohort_disposition"] == "EXCLUDED_STATUS_NOT_CONFIRMED" for r in rows if r["cohort_disposition"] != "INCLUDED")


# -- 5. deterministic cohort-row construction (pure-function, no full rerun) -


def test_fmd05_05_cohort_row_building_is_deterministic():
    from components.geospatial_tracking.data_processing.build_fmd_cohort import build_cohort_rows

    canonical_rows = [
        {
            "fmd_canonical_event_id": "FAO_EMPRESI_BIGQUERY_CSV:E1",
            "source_record_id": "FAO_EMPRESI_BIGQUERY_CSV:f.csv:000001",
            "country": "Sri Lanka",
            "onset_date": "2019-11-04",
            "diagnosis_status": "Confirmed",
            "modelling_eligible": "True",
            "eligibility_reason": "ELIGIBLE",
        },
        {
            "fmd_canonical_event_id": "FAO_EMPRESI_BIGQUERY_CSV:E2",
            "source_record_id": "FAO_EMPRESI_BIGQUERY_CSV:f.csv:000002",
            "country": "Sri Lanka",
            "onset_date": "2019-11-05",
            "diagnosis_status": "Suspected",
            "modelling_eligible": "False",
            "eligibility_reason": "STATUS_NOT_CONFIRMED",
        },
    ]
    origin_by_source_id = {"FAO_EMPRESI_BIGQUERY_CSV:f.csv:000001": "ORIGIN:Sri Lanka:2019-11-04"}
    role_by_origin_id = {"ORIGIN:Sri Lanka:2019-11-04": "SRI_LANKA_TRANSFER_CASE_STUDY"}

    run_1 = build_cohort_rows(canonical_rows, origin_by_source_id=origin_by_source_id, role_by_origin_id=role_by_origin_id)
    run_2 = build_cohort_rows(canonical_rows, origin_by_source_id=origin_by_source_id, role_by_origin_id=role_by_origin_id)
    assert run_1 == run_2
    assert run_1[0]["cohort_disposition"] == "INCLUDED"
    assert run_1[0]["containing_origin_model_fitting_role"] == "SRI_LANKA_TRANSFER_CASE_STUDY"
    assert run_1[1]["cohort_disposition"] == "EXCLUDED_STATUS_NOT_CONFIRMED"
    assert run_1[1]["containing_origin_model_fitting_role"] == ""


def test_fmd05_05b_generated_cohort_audit_matches_its_own_recorded_hash():
    """Confirms the on-disk `FMD_COHORT_AUDIT.csv` used by every other test
    in this module is exactly the file `FMD_COHORT_MANIFEST.json` itself
    recorded a hash for — i.e. nobody hand-edited it after generation."""
    manifest = _load_manifest()
    assert manifest["cohort_audit_sha256"] == _sha256_file(COHORT_AUDIT)
    assert manifest["cohort_audit_sha256"] == EXPECTED_COHORT_AUDIT_SHA256


# -- 6/7/8. primary D1-D7 target lead-day boundary ---------------------------


def test_fmd05_06_primary_target_lead_days_only_1_to_7():
    with FORECAST_TARGETS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            lead = int(row["lead_days"])
            assert 1 <= lead <= 7, f"invalid lead_days {lead}"


def test_fmd05_07_lead_days_zero_never_in_targets():
    with FORECAST_TARGETS_CSV.open(encoding="utf-8", newline="") as f:
        leads = [int(row["lead_days"]) for row in csv.DictReader(f)]
    assert 0 not in leads
    assert len(leads) > 0


def test_fmd05_08_no_lead_days_above_7():
    with FORECAST_TARGETS_CSV.open(encoding="utf-8", newline="") as f:
        over_7 = [int(row["lead_days"]) for row in csv.DictReader(f) if int(row["lead_days"]) > 7]
    assert len(over_7) == 0


# -- 9/10. FMD cutoff frozen and independent of LSD's ------------------------


def test_fmd05_09_fmd_cutoff_is_2026_01_01():
    from components.geospatial_tracking.data_processing.build_fmd_cohort import FMD_MODEL_FITTING_CUTOFF

    assert FMD_MODEL_FITTING_CUTOFF == "2026-01-01"


def test_fmd05_10_fmd_cutoff_not_inherited_from_lsd():
    from components.geospatial_tracking.data_processing.build_fmd_cohort import FMD_MODEL_FITTING_CUTOFF
    from components.geospatial_tracking.services.model_fitting_exposure import MODEL_FITTING_CUTOFF as LSD_CUTOFF

    assert FMD_MODEL_FITTING_CUTOFF != LSD_CUTOFF


# -- 11/12/13/14. model-fitting roles are mutually exclusive and correctly counted --


def test_fmd05_11_roles_are_mutually_exclusive():
    rows = _load_audit_rows()
    seen_any_role = False
    for row in rows:
        role = row["containing_origin_model_fitting_role"]
        disposition = row["cohort_disposition"]
        if disposition != "INCLUDED":
            assert role == "", "excluded rows must never carry a model-fitting role"
            continue
        assert role in ("FIT_DEVELOPMENT", "HELD_OUT_FROM_MODEL_FITTING", "SRI_LANKA_TRANSFER_CASE_STUDY")
        seen_any_role = True
        if role == "SRI_LANKA_TRANSFER_CASE_STUDY":
            assert row["country"] == "Sri Lanka"
        if role in ("FIT_DEVELOPMENT", "HELD_OUT_FROM_MODEL_FITTING"):
            assert row["country"] != "Sri Lanka"
    assert seen_any_role


def test_fmd05_12_fit_development_count_is_6799():
    # NOTE: this is an EVENT-level count (one canonical row = one event),
    # not the origin-level count. FMD-05R split the single, mislabeled
    # `model_fitting_role_counts` key into `forecast_origin_role_counts`
    # (origin-level: FIT_DEVELOPMENT=3761) and
    # `included_source_event_role_counts` (event-level: FIT_DEVELOPMENT=6799).
    # This test's name and value (6799) were always about events, so only
    # the manifest key name needed correcting.
    manifest = _load_manifest()
    assert manifest["included_source_event_role_counts"]["FIT_DEVELOPMENT"] == 6799


def test_fmd05_13_held_out_count_is_2492():
    manifest = _load_manifest()
    assert manifest["included_source_event_role_counts"]["HELD_OUT_FROM_MODEL_FITTING"] == 2492


def test_fmd05_14_sri_lanka_count_is_20():
    manifest = _load_manifest()
    assert manifest["included_source_event_role_counts"]["SRI_LANKA_TRANSFER_CASE_STUDY"] == 20


def test_fmd05_14b_roles_sum_to_included_count():
    manifest = _load_manifest()
    roles = manifest["included_source_event_role_counts"]
    assert sum(roles.values()) == manifest["cohort_disposition_counts"]["INCLUDED"]


# -- 15. held-out origins are hard-rejected by the development-only firewall --


def test_fmd05_15_held_out_cannot_enter_fit_development_assertion():
    from components.geospatial_tracking.data_processing.build_fmd_cohort import FMD_MODEL_FITTING_CUTOFF
    from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
    from components.geospatial_tracking.services.model_fitting_exposure import assert_fit_development_only

    held_out_origin = ForecastOrigin(
        forecast_origin_id="ORIGIN:South Africa:2026-02-01",
        country="South Africa",
        t0="2026-02-01",  # after the frozen FMD cutoff
        temporal_mode="RETROSPECTIVE_PROXY",
    )
    with pytest.raises(ValueError):
        assert_fit_development_only([held_out_origin], cutoff=FMD_MODEL_FITTING_CUTOFF)


def test_fmd05_15b_sri_lanka_origin_rejected_by_development_firewall_even_pre_cutoff():
    from components.geospatial_tracking.data_processing.build_fmd_cohort import FMD_MODEL_FITTING_CUTOFF
    from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
    from components.geospatial_tracking.services.model_fitting_exposure import assert_fit_development_only

    sri_lanka_origin = ForecastOrigin(
        forecast_origin_id="ORIGIN:Sri Lanka:2010-01-13",
        country="Sri Lanka",
        t0="2010-01-13",  # long before the cutoff -- must still be rejected
        temporal_mode="RETROSPECTIVE_PROXY",
    )
    with pytest.raises(ValueError):
        assert_fit_development_only([sri_lanka_origin], cutoff=FMD_MODEL_FITTING_CUTOFF)


# -- 16/17/18. feature eligibility freeze ------------------------------------


def test_fmd05_16_feature_eligibility_csv_has_all_required_statuses():
    with ELIGIBILITY_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    statuses = {r["status"] for r in rows}
    assert "ELIGIBLE_CANDIDATE" in statuses
    assert "STATIC_REFERENCE_PROXY" in statuses
    assert "UNAVAILABLE" in statuses


def test_fmd05_17_unavailable_features_stay_unavailable():
    with ELIGIBILITY_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    unavailable = {r["feature_family"] for r in rows if r["status"] == "UNAVAILABLE"}
    assert "road_density_or_livestock_movement_proxy" in unavailable
    assert "swine_pig_density" in unavailable
    assert "sheep_density" in unavailable
    assert "goat_density" in unavailable


def test_fmd05_18_static_proxies_explicitly_labelled():
    with ELIGIBILITY_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    proxies = {r["feature_family"] for r in rows if r["status"] == "STATIC_REFERENCE_PROXY"}
    assert "elevation_m" in proxies
    assert "cattle_density_animals_per_km2" in proxies
    assert "buffalo_density_animals_per_km2" in proxies


# -- 19/20. determinism + non-mutation of the frozen canonical corpus --------


def test_fmd05_19_cohort_generation_is_deterministic():
    manifest = _load_manifest()
    assert manifest["cohort_audit_sha256"] == EXPECTED_COHORT_AUDIT_SHA256


def test_fmd05_20_canonical_corpus_not_mutated():
    assert _sha256_file(CANONICAL_CSV) == CANONICAL_SHA256


# -- 21. FMD and LSD disease identifiers never collide -----------------------


def test_fmd05_21_fmd_disease_normalizes_differently_from_lsd():
    from components.geospatial_tracking.services.disease import normalize_disease

    fmd = normalize_disease("Foot and mouth disease")
    lsd = normalize_disease("Lumpy skin disease")
    assert fmd is not None
    assert lsd is not None
    assert fmd != lsd


# -- extra: direction/speed tier findings must never be silently upgraded ----


def test_fmd05_22_direction_tier_a_is_zero_and_tier_b_covers_all_risk_eligible():
    manifest = _load_manifest()
    assert manifest["direction_tier_a_strict_count"] == 0
    assert manifest["direction_tier_a_resolved_only_count"] == 0
    assert manifest["direction_tier_b_count"] == manifest["risk_target_eligible_count"]


def test_fmd05_23_target_row_count_exceeds_unique_event_count_pseudo_replication():
    manifest = _load_manifest()
    assert manifest["total_target_rows"] > manifest["unique_target_events"]


# -- extra: FMD/LSD isolation via the bridge's dedup remap -------------------


def test_fmd05_24_bridge_remap_never_touches_shared_dedup_status_enum():
    from components.geospatial_tracking.data_processing.fmd_forecast_bridge import (
        DEDUP_STATUS_REMAP_FOR_GENERIC_GATE,
    )
    from components.geospatial_tracking.schemas import DedupStatus

    for remapped_value in DEDUP_STATUS_REMAP_FOR_GENERIC_GATE.values():
        assert remapped_value in {s.value for s in DedupStatus}
