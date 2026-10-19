# Stage 2 monthly severity pipeline (district level)

Purpose: as verified cases and deaths accumulate in the application, check every month whether a severity model can be
evaluated honestly, and whether it beats simple baselines. It is read-only, it does not touch Stage 1, and it never
deploys anything by itself.

## What runs
`python -m components.risk_forecasting.jobs.run_severity_monthly [--months 12] [--report file.json]` (run from `backend/`)

1. Reads verified app records per district and month (`pipeline.surveillance.app_month_observations`: verified cases,
   disease deaths, district from the record or from its farm). Districts the app cannot see are unknown and are left
   out, never counted as zero.
2. Severity of an outbreak district-month = `cases + 10 x deaths`; LOW < 10, MEDIUM < 30, HIGH >= 30. These weights and
   cut-offs are design choices, not clinically validated.
3. Builds pairs "previous month's cases, deaths and outbreak flag -> this month's class" for outbreak district-months
   whose previous month was also observed.
4. Readiness gate (all must hold): at least 100 outbreak district-months, 12 distinct months and 10 district-months of
   each class (`STAGE2_MIN_*` in `forecast_v2_service`, plus the class minimum).
5. Only if ready: forward chaining by month (train on earlier months, test on the month) of a penalised ordinal
   regression against three baselines (national class frequency, persistence of last month's class, district
   history). Metrics: Ranked Probability Score, ordinal MAE, balanced accuracy, reliability. Decision rule: model RPS
   below every baseline, ordinal MAE not above the best baseline, better than the best baseline in most test months,
   no calibration reversal.

States: `INSUFFICIENT_DATA`, `EVALUATED_NOT_BETTER`, `EVALUATED_BETTER`. Even `EVALUATED_BETTER` only reports; issuing
a severity model needs a separate, approved step and a new model version.

## What the application shows meanwhile
"Severity if an outbreak occurs" from the district's past outbreak years (see the model card) and last month's cases
and deaths. Nothing on screen depends on this job.

## State on 2026-10-14 (real data, read-only run, 12 months to 2026-09)
- FMD: INSUFFICIENT_DATA - 8 of 100 outbreak district-months, 5 of 12 months, classes LOW 1 / MEDIUM 7 / HIGH 0.
- LSD: INSUFFICIENT_DATA - 3 of 100 outbreak district-months, 2 of 12 months.

## Tests
`tests/test_severity_monthly.py`: table rules (unknown is not zero, class cut-offs, previous month needed), the gate
(including the per-class minimum), a simulated deployment, a check that independent random counts never yield a
deployable model, and a read-only guarantee (a database stand-in that fails on any write). **All simulated counts are
synthetic, generated in memory inside the tests, and are never stored or used for any real output.**

## Risks
Coverage bias (only reporting districts), small and possibly test-entered counts, design-choice weights, and the gate
is a minimum, not proof that the model will be good. The thesis should describe the counts as app-recorded pilot
observations.
