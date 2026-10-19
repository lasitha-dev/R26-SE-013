"""Runtime ST-DBSCAN over real eligible case records (EXPLORATORY).

Reuses the existing, tested clustering code unchanged:
`services.stdbscan.cluster.run_st_clustering` (joint space-time neighbour
graph, CORE/BORDER/NOISE, connected components) and
`services.stdbscan.core_support.compute_core_support_assignments`.

Parameters: the documented development candidate in STDBSCAN_PROTOCOL.md
section 11 -- eps_space_km=12.37, eps_time_days=3, min_core_supports=2,
active_window_days=14, PRIMARY_CORE_SUPPORT -- built as
`STDBSCANConfig(parameter_status=UNFROZEN_DEVELOPMENT_CANDIDATE)`. The
protocol forbids freezing these (no held-out evidence), so every output is
labelled EXPLORATORY: a descriptive space-time grouping of reports, never a
validated outbreak chain or transmission evidence.

Points:
- OPERATIONAL: one point per vet-verified case record of the selected disease
  (Asia/Colombo verification date in [as_of - 14, as_of], valid on-island farm
  GPS). Every case on the same farm shares ONE core-support id, so repeat
  reports from a single farm can never form a cluster by themselves -- a
  cluster needs >= 2 distinct farms within 12.37 km and 3 days.
- HISTORICAL: eligible research records (same frozen eligibility as the
  spatial timeline), core support from their own GPS-quality policy.
Identities are privacy-reduced: case points use `/national-cases` record keys.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import pyproj
from shapely.geometry import MultiPoint, mapping

from ..operational.disease_normalization import resolve_operational_disease
from ..operational.farm_normalization import _has_valid_coordinates
from ..operational.national_cases import record_key
from ..source_selector import EligibleSource
from ..sri_lanka_time import sri_lanka_date
from ..stdbscan.cluster import run_st_clustering
from ..stdbscan.config import UNFROZEN_DEVELOPMENT_CANDIDATE, GpsCorePolicy, STDBSCANConfig
from ..stdbscan.core_support import CoreSupportAssignment, compute_core_support_assignments
from .sources import _inside_study_area, active_window, operational_farm_key

EXPLORATORY_CONFIG = STDBSCANConfig(
    eps_space_km=12.37,
    eps_time_days=3,
    min_core_supports=2,
    active_window_days=14,
    gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value,
    parameter_status=UNFROZEN_DEVELOPMENT_CANDIDATE,
)
PARAMETER_SOURCE = "STDBSCAN_PROTOCOL.md section 11 development candidate (UNFROZEN_DEVELOPMENT_CANDIDATE)"
SEMANTICS = "EXPLORATORY_SPACE_TIME_GROUPING_OF_REPORTS_NOT_A_VALIDATED_OUTBREAK_CHAIN"
LIMITATIONS = (
    "PARAMETERS_UNFROZEN_DEVELOPMENT_CANDIDATE_NO_HELD_OUT_VALIDATION",
    "A_CLUSTER_IS_DESCRIPTIVE_PROXIMITY_IN_SPACE_AND_TIME_NOT_TRANSMISSION_EVIDENCE",
    "OPERATIONAL_POINTS_ARE_VET_VERIFIED_DIAGNOSES_NOT_OFFICIAL_OUTBREAK_CONFIRMATIONS",
    "REPORTS_FROM_ONE_FARM_SHARE_ONE_CORE_SUPPORT_AND_CANNOT_CLUSTER_ALONE",
    "POSITION_IS_FARM_GPS_NOT_ANIMAL_LOCATION",
)


_GEOD = pyproj.Geod(ellps="WGS84")
DRIFT_SEMANTICS = "DESCRIPTIVE_SHIFT_OF_THE_MEMBER_CENTROID_FROM_THE_EARLY_TO_THE_LATE_HALF_OF_THE_CLUSTER_PERIOD_NOT_A_SPREAD_DIRECTION"


def _mean_point(points):
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def cluster_geometry(members: list[tuple[float, float, str]], centroid_lat: float, centroid_lon: float) -> dict:
    """Descriptive extent and drift of one cluster from its members
    `(lat, lon, iso_date)`: radius = farthest member from the centroid; drift
    = from the centroid of the members in the first half of the cluster's
    date span to the centroid of those in the second half (unsupported when
    the cluster spans a single day or one half is empty)."""
    radius = max((_GEOD.inv(centroid_lon, centroid_lat, lon, lat)[2] / 1000.0 for lat, lon, _ in members), default=0.0)
    dates = sorted(date.fromisoformat(d[:10]) for _, _, d in members)
    drift = {"supported": False, "km": None, "bearing_deg": None, "early_member_count": 0, "late_member_count": 0, "semantics": DRIFT_SEMANTICS}
    if dates and dates[-1] > dates[0]:
        middle = dates[0] + timedelta(days=(dates[-1] - dates[0]).days / 2.0)
        early = [(lat, lon) for lat, lon, d in members if date.fromisoformat(d[:10]) <= middle]
        late = [(lat, lon) for lat, lon, d in members if date.fromisoformat(d[:10]) > middle]
        if early and late:
            (lat0, lon0), (lat1, lon1) = _mean_point(early), _mean_point(late)
            azimuth, _, metres = _GEOD.inv(lon0, lat0, lon1, lat1)
            drift.update({"supported": True, "km": round(metres / 1000.0, 3), "bearing_deg": round(azimuth % 360.0, 1),
                          "early_member_count": len(early), "late_member_count": len(late)})
    return {"radius_km": round(radius, 3), "drift": drift}


def operational_case_points(case_documents, farm_documents_by_id, *, disease_code: str, as_of: date, window_days: int):
    """Eligible per-case points `(point_id, lat, lon, iso_date, farm_key)` plus exclusion counts."""
    from ...repositories.host_operational_adapter import host_timestamp_text

    start, end = active_window(as_of, window_days)
    points, excluded = [], Counter()
    for doc in case_documents:
        if doc.get("_id") is None:
            continue
        disease = resolve_operational_disease(doc.get("disease_name"))
        if disease is None or disease.value != disease_code:
            excluded["WRONG_DISEASE"] += 1
            continue
        if doc.get("verified") is not True:
            excluded["NOT_VET_VERIFIED"] += 1
            continue
        verified_on = sri_lanka_date(host_timestamp_text(doc.get("verified_at")))
        if verified_on is None:
            excluded["MISSING_VERIFICATION_DATE"] += 1
            continue
        if not start <= verified_on <= end:
            excluded["OUTSIDE_ACTIVE_WINDOW"] += 1
            continue
        farm = farm_documents_by_id.get(str(doc.get("farm_id"))) if doc.get("farm_id") else None
        lat, lon = (farm or {}).get("latitude"), (farm or {}).get("longitude")
        if farm is None or not _has_valid_coordinates(lat, lon) or not _inside_study_area(lat, lon):
            excluded["NO_USABLE_FARM_GPS"] += 1
            continue
        points.append((record_key(str(doc["_id"])), float(lat), float(lon), verified_on.isoformat(), operational_farm_key(str(doc["farm_id"]))))
    return points, excluded


def run_runtime_st_clustering(*, operational_points, historical_sources: list[EligibleSource], as_of: date, disease_display: str,
                              config: STDBSCANConfig = EXPLORATORY_CONFIG) -> dict:
    core_support: dict[str, CoreSupportAssignment] = {}
    farm_members: dict[str, list[str]] = {}
    for point_id, _lat, _lon, _d, farm_key in operational_points:
        farm_members.setdefault(farm_key, []).append(point_id)
    for point_id, _lat, _lon, _d, farm_key in operational_points:
        core_support[point_id] = CoreSupportAssignment(
            source_id=point_id, gps_quality="FARM_GPS", core_support_id=f"SUPPORT:FARM:{farm_key}",
            support_group_source_ids=sorted(farm_members[farm_key]))
    historical_points = []
    for s in historical_sources:
        if s.latitude is None or s.longitude is None or not s.effective_availability_date:
            continue
        historical_points.append((f"HIST:{s.source_id}", float(s.latitude), float(s.longitude), str(s.effective_availability_date)[:10]))
    for sid, csa in compute_core_support_assignments(historical_sources, gps_core_policy=config.gps_core_policy).items():
        core_support[f"HIST:{sid}"] = CoreSupportAssignment(source_id=f"HIST:{sid}", gps_quality=csa.gps_quality,
                                                            core_support_id=csa.core_support_id,
                                                            support_group_source_ids=[f"HIST:{x}" for x in csa.support_group_source_ids])

    usable = [(p[0], p[1], p[2], p[3]) for p in operational_points] + historical_points
    assignments, summaries = run_st_clustering(
        usable_points=usable, core_support_by_id=core_support, eps_space_km=config.eps_space_km,
        eps_time_days=config.eps_time_days, min_core_supports=config.min_core_supports,
        config_hash=config.config_hash(), forecast_origin_id=f"RUNTIME:{disease_display}:{as_of.isoformat()}")

    location = {p[0]: (p[1], p[2], p[3]) for p in usable}
    clusters = []
    for summary in summaries:
        coords = sorted({(round(location[m][1], 5), round(location[m][0], 5)) for m in summary.member_source_ids})
        hull = MultiPoint(coords).convex_hull
        farms = {core_support[m].core_support_id for m in summary.member_source_ids if m in core_support}
        clusters.append({
            "cluster_id": summary.cluster_id,
            "member_count": summary.member_count,
            "distinct_location_count": len(coords),
            "core_support_count": summary.core_support_count,
            "distinct_farm_or_support_count": len(farms),
            "core_member_count": len(summary.core_source_ids),
            "border_member_count": len(summary.border_source_ids),
            "start_date": summary.cluster_start_date,
            "end_date": summary.cluster_end_date,
            "centroid": {"latitude": summary.centroid_lat, "longitude": summary.centroid_lon},
            "member_locations": [{"longitude": lon, "latitude": lat} for lon, lat in coords],
            "hull_geometry": mapping(hull),
            "member_record_keys": sorted(summary.member_source_ids),
            **cluster_geometry([location[m] for m in summary.member_source_ids], summary.centroid_lat, summary.centroid_lon),
            "semantics": SEMANTICS,
        })
    noise = [a.source_id for a in assignments.values() if a.is_noise]
    roles = Counter(a.cluster_role for a in assignments.values())
    return {
        "status": "OK" if usable else "NO_ELIGIBLE_POINTS",
        "method": "ST-DBSCAN (existing services.stdbscan.run_st_clustering)",
        "evidence_status": "EXPLORATORY",
        "semantics": SEMANTICS,
        "disease": disease_display,
        "as_of": as_of.isoformat(),
        "parameters": {**config.config_dict(), "config_hash": config.config_hash(), "parameter_source": PARAMETER_SOURCE},
        "input": {"operational_case_points": len(operational_points), "historical_points": len(historical_points),
                  "distinct_operational_farms": len(farm_members)},
        "role_counts": dict(roles),
        "cluster_count": len(clusters),
        "noise_count": len(noise),
        "noise_locations": sorted({(round(location[n][0], 5), round(location[n][1], 5)) for n in noise}),
        "clusters": clusters,
        "limitations": list(LIMITATIONS),
    }
