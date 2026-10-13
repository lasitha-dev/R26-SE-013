# v2 Forecasting — Operations Guide

How the v2 system runs day to day. Validation results and limitations: [MODEL_CARD.md](MODEL_CARD.md).

## What happens each month

1. **Day 5 of month t** — the job builds features from data published up to month t-1:
   CHIRPS rainfall (WFP/HDX), NASA POWER weather, NOAA Niño 3.4, and outbreak surveillance
   (curated labels for historical periods, verified app cases/deaths afterwards).
2. It applies the deployed forecaster per disease and district (see "Deployment" in the model card)
   and stores **50 immutable records** (25 districts × FMD/LSD) in `forecast_records`.
3. Older records for the same disease/district/month (e.g. v1 proxy-based ones) can be marked
   `SUPERSEDED` (never deleted), under strict guards: records that have **advisories, follow-ups or
   workflow status (AVAILABLE/REFERENCED) are always protected**, and if the dependency check is
   unavailable nothing is superseded. A real run that would supersede records must pass the count
   from a preview; a mismatch stops the run before any write. UIs show only non-superseded records.
4. After the target month plus one grace month, `GET /v2/performance` scores the forecasts
   against what was observed.

## Running it

From `backend/` (the Atlas connection comes from `backend/.env`; nothing else is configured):

```
python -m components.risk_forecasting.jobs.run_monthly_forecast --dry-run            # preview: nothing written
python -m components.risk_forecasting.jobs.run_monthly_forecast                      # current month, stores records, supersedes nothing
python -m components.risk_forecasting.jobs.run_monthly_forecast --year 2026 --month 11
python -m components.risk_forecasting.jobs.run_monthly_forecast --supersede-count N   # N = "would_supersede" from the preview
```

Re-running is safe: record identity is `v2|DISEASE|district|YYYY-MM|model_version`.
Each run appends a JSON line to `model/data/cache/runs/forecast_runs.jsonl`.
Exit codes: 0 ok, 1 storage unavailable, 2 bad arguments, 3 supersede count missing/stale (nothing written),
4 partial failure (some records failed; nothing superseded; re-running is safe).

**Scheduling (Windows Task Scheduler):** program `python`, arguments
`-m components.risk_forecasting.jobs.run_monthly_forecast --trigger SCHEDULED`, start in `<repo>\backend`,
monthly on day 5 (a daily trigger also works).

DAPH officials can also use **Generate v2 forecasts** on the National Overview page. It first runs a
preview (`dry_run`), shows what will be stored, superseded and protected, and only stores after the
official confirms (`POST /api/v1/risk-forecasting/v2/forecasts/generate`, JWT role DAPH_OFFICIAL only;
a real run sends `expected_supersede_count` from the preview, otherwise HTTP 400/409 and nothing is written).

## Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /v2/forecasts/generate` | Preview (`dry_run`) or store forecasts for a month (DAPH only). Real runs that would supersede records need `expected_supersede_count` (400 if missing, 409 if stale) |
| `GET /v2/model-card` | Deployed forecaster, validation status, evaluation summary |
| `GET /v2/surveillance/active` | Verified cases/deaths per district for a month — observed facts, separate from forecasts |
| `GET /v2/performance` | Hits, missed outbreaks, false alarms, Brier score for past forecasts |

## Reading a forecast record

- `forecaster` / `deployment_status`: which model produced it and its evidence level (`back_tested` = beat the baseline in rolling back-testing but not yet confirmed on future data; `exploratory`; `baseline`).
  `climatology` + `baseline` means surveillance for the district or its neighbours was unknown, so the
  district's historical rate is shown — it is never a disguised model output.
- `issue_date` is the real UTC date the record was generated; `data_cutoff` is the last day of the
  newest month of observations used. The "day 5" in this guide is only the intended schedule.
- `trigger_type: BACKFILL` / `retrospective: true` mean the record was generated after its target
  month had ended. It is kept for completeness but is **not a prospective forecast**; `GET /v2/performance`
  reports such records separately (`retrospective_scored`) and they must not be quoted as live skill.
- A `climatology` record is the district's usual rate for the month, so its `relative_risk` is 1.0 and its
  stored `risk_level` is always LOW by construction. The UI shows it as **BASELINE** ("no elevated signal
  assessed"), never as an assessed LOW RISK, and it is not counted in the LOW tier summary.
- `relative_risk` = probability ÷ `baseline_probability` (usual rate for that district and month).
  LOW < 2×, MEDIUM ≥ 2×, HIGH ≥ 4× (or probability ≥ 50%).
- `previous_month_observation`: verified cases, deaths and observed severity (cases + 10 × deaths;
  heuristic weights) for month t-1. Null counts mean the app has no coverage in that district.
- `input_quality`: `DEGRADED` when climate inputs were unavailable (e.g. data not yet published).
- `feature_snapshot` / `contributions`: exact inputs and top log-odds contributions.
- v2 records do **not** predict severity (`predicted_severity` is null): the v1 severity models were
  not validated and, for FMD, are of uncertain provenance.

## Known operational limits

- Current deployment (model card section 6): **FMD uses the climatology baseline everywhere** because no
  model beat it with a confidence interval above zero; LSD uses variant A (back-tested candidate) where
  surveillance of the district and its neighbours is known, otherwise climatology.
- Surveillance coverage: the app currently has few registered farms, so most districts have
  unknown surveillance and receive the climatology baseline. Forecast skill rises as coverage grows
  or if DAPH monthly reports are imported.
- Preliminary CHIRPS values for the latest months can be revised; records keep the `preliminary` source
  note in `fallback_message`.
- NASA POWER daily data lags ~4 days; running before day 5 may leave weather inputs missing
  (`input_quality: DEGRADED`).
- Re-train with `scripts/v2/build_dataset.py` + `scripts/v2/train_evaluate.py` when enough new labelled
  months exist (yearly). Promote a new model only if it passes the deployment rule in the model card.
