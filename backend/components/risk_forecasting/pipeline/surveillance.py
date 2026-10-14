"""
Coverage-aware outbreak surveillance for the v2 forecaster (decision D-5).

Status of a district-month (never defaulted to "no outbreak"):
  CONFIRMED_OUTBREAK        curated label = 1, or >= 1 verified case / disease death in the app
  NO_OUTBREAK_RECORDED      curated label = 0
  NO_REPORTED_CASES         app: the district has registered farms but no verified case/death
  NO_SURVEILLANCE_COVERAGE  app: no registered farm in the district          -> unknown
  UNVERIFIED_LABEL          curated label exists but is excluded (FMD 2024)   -> unknown
  SOURCE_UNAVAILABLE        the database could not be queried                 -> unknown

Periods covered by the curated dataset use its labels; later periods use verified app
records (diagnostic_cases with verified=True, death_logs with a matching cause), which are
written by the Smart Diagnostics / Health Anomaly component.
"""

from __future__ import annotations

import calendar
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Optional

from bson import ObjectId

from components.risk_forecasting.pipeline.geography import DISTRICT_NAMES, normalize_district
from components.risk_forecasting.pipeline.labels import LABEL_YEARS, UNVERIFIED_YEARS

logger = logging.getLogger(__name__)

KNOWN_POSITIVE = {"CONFIRMED_OUTBREAK"}
KNOWN_NEGATIVE = {"NO_OUTBREAK_RECORDED", "NO_REPORTED_CASES"}
DISEASE_PATTERNS = {
    "FMD": r"FMD|Foot[- _]?and[- _]?Mouth",
    "LSD": r"LSD|Lumpy[- _]?Skin|lumpy",
}
CURATED_SOURCE = "CURATED_DAPH_DATASET"
APP_SOURCE = "APP_VERIFIED_CASES_AND_DEATHS"


@dataclass
class DistrictObservation:
    status: str
    source: str
    cases: Optional[int] = None
    deaths: Optional[int] = None

    @property
    def outbreak(self) -> Optional[int]:
        if self.status in KNOWN_POSITIVE:
            return 1
        if self.status in KNOWN_NEGATIVE:
            return 0
        return None

    def as_dict(self) -> dict:
        return {"status": self.status, "source": self.source, "verified_cases": self.cases,
                "deaths": self.deaths, "observed_severity": observed_severity(self.cases, self.deaths)}


def observed_severity(cases: Optional[int], deaths: Optional[int]) -> Optional[str]:
    """Descriptive severity of an observed month: score = cases + 10 x deaths.
    NONE (0), LOW (< 10), MODERATE (< 30), HIGH (>= 30). Heuristic weights, documented as such."""
    if cases is None or deaths is None:
        return None
    score = cases + 10 * deaths
    if score == 0:
        return "NONE"
    if score < 10:
        return "LOW"
    if score < 30:
        return "MODERATE"
    return "HIGH"


def _month_bounds(year: int, month: int):
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    last_day = calendar.monthrange(year, month)[1]
    return start, end, start.strftime("%Y-%m-%d"), f"{year:04d}-{month:02d}-{last_day:02d}~"


def _in_month(field_names, start, end, start_s, end_s):
    clauses = []
    for name in field_names:
        clauses.append({name: {"$gte": start, "$lt": end}})
        clauses.append({name: {"$gte": start_s, "$lt": end_s}})
    return {"$or": clauses}


def app_month_observations(db, disease: str, year: int, month: int) -> Dict[str, DistrictObservation]:
    """Count verified cases and disease deaths per district for one month from the app database."""
    start, end, start_s, end_s = _month_bounds(year, month)
    pattern = re.compile(DISEASE_PATTERNS[disease], re.IGNORECASE)

    farm_district, email_district = {}, {}
    for farm in db["farms"].find({}, {"location_district": 1, "district": 1, "email": 1}):
        district = normalize_district(farm.get("location_district") or farm.get("district"))
        if district:
            farm_district[str(farm["_id"])] = district
            if farm.get("email"):
                email_district[farm["email"]] = district
    covered = set(farm_district.values())

    def district_of(record) -> Optional[str]:
        direct = normalize_district(record.get("district"))
        if direct:
            return direct
        farm_id = record.get("farm_id")
        if farm_id and str(farm_id) in farm_district:
            return farm_district[str(farm_id)]
        cattle_id = record.get("cattle_id")
        if cattle_id and ObjectId.is_valid(str(cattle_id)):
            cattle = db["cattle"].find_one({"_id": ObjectId(str(cattle_id))}, {"owner_email": 1})
            if cattle and cattle.get("owner_email") in email_district:
                return email_district[cattle["owner_email"]]
        return None

    cases = {d: 0 for d in DISTRICT_NAMES}
    deaths = {d: 0 for d in DISTRICT_NAMES}
    case_query = {"verified": True, "disease_name": {"$regex": pattern.pattern, "$options": "i"},
                  **_in_month(["verified_at", "created_at"], start, end, start_s, end_s)}
    for case in db["diagnostic_cases"].find(case_query):
        district = district_of(case)
        if district:
            cases[district] += 1
    death_query = {"cause": {"$regex": pattern.pattern, "$options": "i"},
                   **_in_month(["date_of_death", "created_at"], start, end, start_s, end_s)}
    for death in db["death_logs"].find(death_query):
        district = district_of(death)
        if district:
            deaths[district] += 1

    result = {}
    for district in DISTRICT_NAMES:
        if cases[district] or deaths[district]:
            status = "CONFIRMED_OUTBREAK"
        elif district in covered:
            status = "NO_REPORTED_CASES"
        else:
            status = "NO_SURVEILLANCE_COVERAGE"
        # Counts are only meaningful where the app can see the district; elsewhere they are unknown.
        observed = status != "NO_SURVEILLANCE_COVERAGE"
        result[district] = DistrictObservation(
            status, APP_SOURCE,
            cases[district] if observed else None,
            deaths[district] if observed else None,
        )
    return result


@dataclass
class SurveillanceProvider:
    """Answers 'outbreak status of district d in month m' for one disease, with provenance."""
    disease: str
    curated_labels: Dict[tuple, int]
    app_db_factory: Optional[Callable[[], object]] = None
    _cache: Dict[tuple, Dict[str, DistrictObservation]] = field(default_factory=dict)

    def month(self, year: int, month: int) -> Dict[str, DistrictObservation]:
        key = (year, month)
        if key in self._cache:
            return self._cache[key]
        if year in UNVERIFIED_YEARS.get(self.disease, set()):
            result = {d: DistrictObservation("UNVERIFIED_LABEL", CURATED_SOURCE) for d in DISTRICT_NAMES}
        elif year in LABEL_YEARS[self.disease]:
            result = {}
            for d in DISTRICT_NAMES:
                label = self.curated_labels.get((d, year, month))
                status = "CONFIRMED_OUTBREAK" if label == 1 else "NO_OUTBREAK_RECORDED" if label == 0 else "SOURCE_UNAVAILABLE"
                result[d] = DistrictObservation(status, CURATED_SOURCE)
        elif year < min(LABEL_YEARS[self.disease]) or self.app_db_factory is None:
            result = {d: DistrictObservation("SOURCE_UNAVAILABLE", "NONE") for d in DISTRICT_NAMES}
        else:
            try:
                result = app_month_observations(self.app_db_factory(), self.disease, year, month)
            except Exception as exc:  # database unreachable -> unknown, never "no outbreak"
                logger.error("Surveillance query failed for %s %d-%02d: %s", self.disease, year, month, exc)
                result = {d: DistrictObservation("SOURCE_UNAVAILABLE", APP_SOURCE) for d in DISTRICT_NAMES}
        self._cache[key] = result
        return result

    def status(self, district: str, year: int, month: int) -> Optional[int]:
        return self.month(year, month)[district].outbreak
