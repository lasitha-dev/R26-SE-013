"""
v2 forecast generation: builds availability-aware features from public sources and
coverage-aware surveillance, applies the deployed v2 forecaster, and persists one
immutable ForecastDecisionRecord per district and disease.

Idempotency: key "v2|<disease>|<district>|<YYYY-MM>|<model_version>" (unique index in
Mongo), so re-running a period never duplicates records.

Superseding older records (e.g. v1 proxy-based ones) is guarded (see pipeline/supersede_policy.py):
records with advisories, follow-ups or workflow status are protected and never superseded; an
unavailable dependency check protects everything; a real run must confirm the exact number of
records a preview said it would supersede; superseding happens only after every new record is
saved. Records are never deleted.
"""

from __future__ import annotations

import calendar
import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional

from components.risk_forecasting.pipeline.features import BASE_FEATURES, build_features, shift
from components.risk_forecasting.pipeline.geography import DISTRICT_NAMES
from components.risk_forecasting.pipeline.labels import load_labels
from components.risk_forecasting.pipeline.live_sources import build_live_sources
from components.risk_forecasting.pipeline.predictor import V2Predictor
from components.risk_forecasting.pipeline.supersede_policy import SupersedePlan, plan_supersede
from components.risk_forecasting.pipeline.surveillance import SurveillanceProvider, observed_severity
from components.risk_forecasting.config import FMD_DATASET_FILE, LSD_DATASET_FILE
from components.risk_forecasting.schemas import ForecastDecisionRecord

logger = logging.getLogger(__name__)

DATASETS = {"FMD": FMD_DATASET_FILE, "LSD": LSD_DATASET_FILE}
DISCLAIMER = (
    "Statistical early-warning estimate (v2) for decision support only; it is not a diagnosis. "
    "Issued with observations up to the previous month. See the v2 model card for validation "
    "status and limitations. Veterinary/DAPH confirmation is required before intervention."
)
FORECASTER_LABELS = {
    "A": "climate + surveillance model",
    "S": "surveillance-dynamics model",
    "B": "climate model",
    "O": "district-history model",
    "OC": "district-history + climate model",
    "climatology": "district-month historical baseline",
}


class SupersedeConfirmationRequired(Exception):
    """A real run would supersede records but no confirmation count was supplied."""

    def __init__(self, would_supersede: int):
        super().__init__(f"{would_supersede} records would be superseded; preview and confirm the count first.")
        self.would_supersede = would_supersede


class StalePreview(Exception):
    """The confirmed supersede count no longer matches what a run would do."""

    def __init__(self, expected: int, actual: int):
        super().__init__(f"Preview is stale: confirmed {expected} but {actual} records would be superseded. Preview again.")
        self.expected = expected
        self.actual = actual


# Stage 2 (outbreak severity) is not predicted: the training labels are annual district totals, not monthly.
# It becomes worth trying once the app has recorded enough MONTHLY verified counts for outbreak months.
STAGE2_MIN_OUTBREAK_MONTHS = 100
STAGE2_MIN_DISTINCT_MONTHS = 12


class ForecastV2Service:
    def __init__(
        self,
        repository_getter: Callable[[], object],
        app_db_factory: Optional[Callable[[], object]] = None,
        predictor_loader: Callable[[str], V2Predictor] = V2Predictor.load,
        sources_builder: Callable = build_live_sources,
        clock: Optional[Callable[[], datetime]] = None,
        id_generator: Optional[Callable[[], str]] = None,
        dependency_counter: Optional[Callable[[str], Dict[str, int]]] = None,
    ):
        # dependency_counter(forecast_id) -> {"advisories": n, "follow_ups": n}. Without it nothing
        # can be superseded (fail closed).
        self.dependency_counter = dependency_counter
        self.repository_getter = repository_getter
        self.app_db_factory = app_db_factory
        self.predictor_loader = predictor_loader
        self.sources_builder = sources_builder
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_generator = id_generator or (lambda: f"fdr_{uuid.uuid4().hex[:12]}")
        self._labels: Dict[str, dict] = {}

    def _surveillance(self, disease: str) -> SurveillanceProvider:
        if disease not in self._labels:
            self._labels[disease] = load_labels(disease, DATASETS[disease])
        return SurveillanceProvider(disease, self._labels[disease], self.app_db_factory)

    def forecast_period(self, year: int, month: int, diseases: Iterable[str] = ("FMD", "LSD"),
                        generated_by: Optional[str] = None, trigger_type: str = "MANUAL") -> List[ForecastDecisionRecord]:
        """Compute (not persist) v2 forecasts for every district for the target month."""
        issued_at = self.clock()
        now = issued_at.isoformat()
        # The target period and evidence period are deliberately separate:
        # a forecast for month t uses completed observations from t-1 or earlier.
        prev = shift((year, month), -1)
        # A forecast issued after its target month has ended is retrospective: it is labelled
        # BACKFILL and never presented (or scored) as a prospective forecast.
        retrospective = (issued_at.year, issued_at.month) > (year, month)
        if retrospective:
            trigger_type = "BACKFILL"
        data_cutoff = f"{prev[0]:04d}-{prev[1]:02d}-{calendar.monthrange(prev[0], prev[1])[1]:02d}"
        records: List[ForecastDecisionRecord] = []
        for disease in diseases:
            disease = disease.upper()
            predictor = self.predictor_loader(disease)
            surveillance = self._surveillance(disease)
            sources, notes = self.sources_builder([(year, month)], surveillance)
            previous = surveillance.month(*prev)
            for district in DISTRICT_NAMES:
                features, missing = build_features(district, year, month, sources)
                prediction = predictor.predict(district, month, features)
                climate_missing = [m for m in missing if m in BASE_FEATURES]
                observation = previous[district]
                # Save the estimate together with model version, exact features,
                # missing inputs and source status so a decision can be reviewed.
                records.append(ForecastDecisionRecord(
                    forecast_id=self.id_generator(),
                    disease=disease,
                    district=district,
                    target_year=year,
                    target_month=month,
                    generated_at=now,
                    probability=round(prediction.probability, 6),
                    probability_pct=round(prediction.probability * 100, 1),
                    risk_level=prediction.risk_level,
                    predicted_severity=None,
                    model_variant=f"{prediction.model_version}:{prediction.forecaster}",
                    fallback_applied=prediction.forecaster == "climatology",
                    source_year=prev[0],
                    source_month=prev[1],
                    data_age_months=1,
                    data_quality="V2_BASELINE" if prediction.forecaster == "climatology" else "V2_MODEL",
                    fallback_message=(
                        f"Forecaster: {FORECASTER_LABELS[prediction.forecaster]} ({prediction.deployment_status}). "
                        f"Previous-month surveillance: {observation.status} ({observation.source}). "
                        f"Sources: {', '.join(f'{k}={v}' for k, v in notes.items())}."
                    ),
                    status="GENERATED",
                    trigger_type=trigger_type,
                    generated_by=generated_by,
                    disclaimer=DISCLAIMER,
                    idempotency_key=f"v2|{disease}|{district}|{year:04d}-{month:02d}|{prediction.model_version}",
                    created_at=now,
                    updated_at=now,
                    model_version=prediction.model_version,
                    forecaster=prediction.forecaster,
                    deployment_status=prediction.deployment_status,
                    issue_date=issued_at.date().isoformat(),
                    data_cutoff=data_cutoff,
                    retrospective=retrospective,
                    baseline_probability=round(prediction.baseline_probability, 6),
                    probability_low=None if prediction.probability_low is None else round(prediction.probability_low, 6),
                    probability_high=None if prediction.probability_high is None else round(prediction.probability_high, 6),
                    interval_level=prediction.interval_level,
                    relative_risk=round(prediction.relative_risk, 3),
                    input_quality="DEGRADED" if climate_missing else "COMPLETE",
                    missing_inputs=missing,
                    surveillance_status=observation.status,
                    surveillance_source=observation.source,
                    feature_snapshot={k: (round(v, 6) if isinstance(v, float) else v) for k, v in features.items()},
                    contributions=prediction.contributions,
                    previous_month_observation={"period": f"{prev[0]:04d}-{prev[1]:02d}", **observation.as_dict()},
                ))
        return records

    def _all_v2_records(self) -> List[ForecastDecisionRecord]:
        repository = self.repository_getter()
        records, offset = [], 0
        while True:
            page, total = repository.list(limit=200, offset=offset)
            records.extend(r for r in page if r.model_version and r.status != "SUPERSEDED")
            offset += len(page)
            if not page or offset >= total:
                return records

    def performance(self, as_of: Optional[datetime] = None, grace_months: int = 1) -> dict:
        """Score stored v2 forecasts against observed outcomes, computed on read (records stay
        immutable). A target month is scored once `grace_months` full months have passed.
        Outcomes with unknown surveillance are reported separately and never counted as 0."""
        today = (as_of or self.clock())
        latest = shift((today.year, today.month), -(grace_months + 1))
        providers: Dict[str, SurveillanceProvider] = {}
        summary = {"scored_through": f"{latest[0]:04d}-{latest[1]:02d}", "diseases": {}}
        for record in self._all_v2_records():
            if (record.target_year, record.target_month) > latest:
                continue
            provider = providers.setdefault(record.disease, self._surveillance(record.disease))
            observation = provider.month(record.target_year, record.target_month)[record.district]
            stats = summary["diseases"].setdefault(record.disease, {
                "scored": 0, "retrospective_scored": 0, "outbreaks": 0, "alerts": 0, "hits": 0, "missed_outbreaks": 0,
                "false_alarms": 0, "brier_sum": 0.0, "severity_bands": {}, "severity_periods": set(), "unscored_by_status": {}, "scored_by_forecaster": {},
            })
            outcome = observation.outbreak
            if outcome is None:
                stats["unscored_by_status"][observation.status] = stats["unscored_by_status"].get(observation.status, 0) + 1
                continue
            alert = record.risk_level in ("MEDIUM", "HIGH")
            stats["scored"] += 1
            stats["retrospective_scored"] += int(bool(record.retrospective))  # backfilled: not a prospective test
            stats["outbreaks"] += outcome
            stats["alerts"] += int(alert)
            stats["hits"] += int(alert and outcome == 1)
            stats["missed_outbreaks"] += int(not alert and outcome == 1)
            stats["false_alarms"] += int(alert and outcome == 0)
            # Brier score is the mean squared probability error against 0/1
            # outcomes; smaller values indicate better probabilistic predictions.
            stats["brier_sum"] += (record.probability - outcome) ** 2
            if outcome == 1 and observation.cases is not None and observation.deaths is not None:
                band = observed_severity(observation.cases, observation.deaths)
                stats["severity_bands"][band] = stats["severity_bands"].get(band, 0) + 1
                stats["severity_periods"].add((record.target_year, record.target_month))
            key = record.forecaster or "unknown"
            stats["scored_by_forecaster"][key] = stats["scored_by_forecaster"].get(key, 0) + 1
        for stats in summary["diseases"].values():
            scored = stats["scored"]
            outbreak_months = sum(stats["severity_bands"].values())
            distinct = len(stats.pop("severity_periods"))
            stats["stage2_readiness"] = {
                "observed_outbreak_months_with_monthly_counts": outbreak_months,
                "distinct_months": distinct,
                "observed_severity_bands": stats.pop("severity_bands"),
                "required_outbreak_months": STAGE2_MIN_OUTBREAK_MONTHS,
                "required_distinct_months": STAGE2_MIN_DISTINCT_MONTHS,
                "ready_to_evaluate": outbreak_months >= STAGE2_MIN_OUTBREAK_MONTHS and distinct >= STAGE2_MIN_DISTINCT_MONTHS,
            }
            stats["brier_score"] = round(stats.pop("brier_sum") / scored, 4) if scored else None
            stats["recall"] = round(stats["hits"] / stats["outbreaks"], 3) if stats["outbreaks"] else None
            stats["precision"] = round(stats["hits"] / stats["alerts"], 3) if stats["alerts"] else None
        return summary

    def _existing_records(self, repository, disease: str, year: int, month: int) -> List[ForecastDecisionRecord]:
        """All stored records for a disease and target month, read page by page."""
        records, offset = [], 0
        while True:
            page, total = repository.list(disease=disease, target_year=year, target_month=month, limit=200, offset=offset)
            records.extend(page)
            offset += len(page)
            if not page or offset >= total:
                return records

    def _dependents(self, forecast_id: str) -> Optional[Dict[str, int]]:
        if self.dependency_counter is None:
            return None
        try:
            return self.dependency_counter(forecast_id)
        except Exception as exc:  # unknown dependencies protect the record
            logger.error("Dependency check failed for %s: %s", forecast_id, type(exc).__name__)
            return None

    def plan_period(self, records: List[ForecastDecisionRecord], year: int, month: int) -> SupersedePlan:
        repository = self.repository_getter()
        plan = SupersedePlan()
        for disease in sorted({r.disease for r in records}):
            existing = self._existing_records(repository, disease, year, month)
            keys = [r.idempotency_key for r in records if r.disease == disease]
            dependents = {r.forecast_id: self._dependents(r.forecast_id)
                          for r in existing if r.status != "SUPERSEDED" and r.idempotency_key not in keys}
            part = plan_supersede(existing, keys, dependents)
            plan.to_supersede += part.to_supersede
            plan.protected += part.protected
            plan.kept += part.kept
        return plan

    def generate_period(self, year: int, month: int, diseases: Iterable[str] = ("FMD", "LSD"),
                        generated_by: Optional[str] = None, trigger_type: str = "MANUAL",
                        dry_run: bool = False, supersede: bool = True,
                        expected_supersede_count: Optional[int] = None) -> dict:
        """Compute forecasts and (unless dry_run) store them.

        dry_run=True is a read-only preview that also reports what a real run would supersede
        or protect. A real run with supersede=True and records to supersede must pass the
        previewed count as `expected_supersede_count`; otherwise nothing is written.
        """
        records = self.forecast_period(year, month, diseases, generated_by, trigger_type)
        plan = self.plan_period(records, year, month)
        summary = {
            "target_period": f"{year:04d}-{month:02d}",
            "dry_run": dry_run,
            "status": "PREVIEW" if dry_run else "OK",
            "records": len(records),
            "by_forecaster": {},
            "by_risk_level": {},
            "supersede_enabled": supersede,
            **plan.summary(),
            "protected_details": plan.protected,
            "saved": 0,
            "failed": [],
            "superseded": 0,
            "supersede_failed": [],
        }
        for r in records:
            key = f"{r.disease}:{r.forecaster}"
            summary["by_forecaster"][key] = summary["by_forecaster"].get(key, 0) + 1
            summary["by_risk_level"][r.risk_level] = summary["by_risk_level"].get(r.risk_level, 0) + 1
        # Preview returns computed records and the replacement plan before writes.
        if dry_run:
            return {"summary": summary, "records": records}

        if supersede and plan.to_supersede:
            if expected_supersede_count is None:
                raise SupersedeConfirmationRequired(len(plan.to_supersede))
            if expected_supersede_count != len(plan.to_supersede):
                raise StalePreview(expected_supersede_count, len(plan.to_supersede))

        repository = self.repository_getter()
        # Persist the new set first. If any save fails, return before superseding
        # older records; retries reuse the same per-period idempotency keys.
        saved: List[ForecastDecisionRecord] = []
        for record in records:
            try:
                saved.append(repository.save(record))
            except RuntimeError as exc:
                if not saved and not summary["failed"]:
                    raise  # storage unavailable from the very first write: nothing was stored
                summary["failed"].append({"forecast_id": record.forecast_id, "error": type(exc).__name__})
        summary["saved"] = len(saved)
        if summary["failed"]:
            summary["status"] = "PARTIAL"  # re-running is safe (idempotent); nothing was superseded
            return {"summary": summary, "records": saved}

        if supersede:
            for forecast_id in plan.to_supersede:
                try:
                    repository.update_status(forecast_id, "SUPERSEDED")
                    summary["superseded"] += 1
                except RuntimeError as exc:
                    summary["supersede_failed"].append({"forecast_id": forecast_id, "error": type(exc).__name__})
            if summary["supersede_failed"]:
                summary["status"] = "PARTIAL"
        return {"summary": summary, "records": saved}
