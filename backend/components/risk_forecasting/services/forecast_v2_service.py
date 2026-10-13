"""
v2 forecast generation: builds availability-aware features from public sources and
coverage-aware surveillance, applies the deployed v2 forecaster, and persists one
immutable ForecastDecisionRecord per district and disease.

Idempotency: key "v2|<disease>|<district>|<YYYY-MM>|<model_version>" (unique index in
Mongo), so re-running a period never duplicates records. Earlier records for the same
disease/district/period (e.g. v1 proxy-based records) are marked SUPERSEDED, not deleted.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional

from components.risk_forecasting.pipeline.features import BASE_FEATURES, build_features, shift
from components.risk_forecasting.pipeline.geography import DISTRICT_NAMES
from components.risk_forecasting.pipeline.labels import load_labels
from components.risk_forecasting.pipeline.live_sources import build_live_sources
from components.risk_forecasting.pipeline.predictor import V2Predictor
from components.risk_forecasting.pipeline.surveillance import SurveillanceProvider
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
    "climatology": "district-month historical baseline",
}


class ForecastV2Service:
    def __init__(
        self,
        repository_getter: Callable[[], object],
        app_db_factory: Optional[Callable[[], object]] = None,
        predictor_loader: Callable[[str], V2Predictor] = V2Predictor.load,
        sources_builder: Callable = build_live_sources,
        clock: Optional[Callable[[], datetime]] = None,
        id_generator: Optional[Callable[[], str]] = None,
    ):
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
        now = self.clock().isoformat()
        prev = shift((year, month), -1)
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
                    issue_date=f"{year:04d}-{month:02d}-05",
                    baseline_probability=round(prediction.baseline_probability, 6),
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
                "scored": 0, "outbreaks": 0, "alerts": 0, "hits": 0, "missed_outbreaks": 0,
                "false_alarms": 0, "brier_sum": 0.0, "unscored_by_status": {}, "scored_by_forecaster": {},
            })
            outcome = observation.outbreak
            if outcome is None:
                stats["unscored_by_status"][observation.status] = stats["unscored_by_status"].get(observation.status, 0) + 1
                continue
            alert = record.risk_level in ("MEDIUM", "HIGH")
            stats["scored"] += 1
            stats["outbreaks"] += outcome
            stats["alerts"] += int(alert)
            stats["hits"] += int(alert and outcome == 1)
            stats["missed_outbreaks"] += int(not alert and outcome == 1)
            stats["false_alarms"] += int(alert and outcome == 0)
            stats["brier_sum"] += (record.probability - outcome) ** 2
            key = record.forecaster or "unknown"
            stats["scored_by_forecaster"][key] = stats["scored_by_forecaster"].get(key, 0) + 1
        for stats in summary["diseases"].values():
            scored = stats["scored"]
            stats["brier_score"] = round(stats.pop("brier_sum") / scored, 4) if scored else None
            stats["recall"] = round(stats["hits"] / stats["outbreaks"], 3) if stats["outbreaks"] else None
            stats["precision"] = round(stats["hits"] / stats["alerts"], 3) if stats["alerts"] else None
        return summary

    def generate_period(self, year: int, month: int, diseases: Iterable[str] = ("FMD", "LSD"),
                        generated_by: Optional[str] = None, trigger_type: str = "MANUAL",
                        dry_run: bool = False) -> dict:
        """Compute and (unless dry_run) persist v2 forecasts; supersede older records for the period."""
        records = self.forecast_period(year, month, diseases, generated_by, trigger_type)
        summary = {
            "target_period": f"{year:04d}-{month:02d}",
            "dry_run": dry_run,
            "records": len(records),
            "by_forecaster": {},
            "by_risk_level": {},
            "superseded": 0,
        }
        for r in records:
            key = f"{r.disease}:{r.forecaster}"
            summary["by_forecaster"][key] = summary["by_forecaster"].get(key, 0) + 1
            summary["by_risk_level"][r.risk_level] = summary["by_risk_level"].get(r.risk_level, 0) + 1
        if dry_run:
            return {"summary": summary, "records": records}

        repository = self.repository_getter()
        saved = [repository.save(r) for r in records]
        saved_ids = {r.forecast_id for r in saved}
        for disease in {r.disease for r in saved}:
            existing, _ = repository.list(disease=disease, target_year=year, target_month=month, limit=200, offset=0)
            for old in existing:
                if old.forecast_id not in saved_ids and old.status != "SUPERSEDED":
                    repository.update_status(old.forecast_id, "SUPERSEDED")
                    summary["superseded"] += 1
        return {"summary": summary, "records": saved}
