# Disease Risk Forecasting v2 — Model Card

Models: `models/v2/fmd_v2.json`, `models/v2/lsd_v2.json` (plain JSON coefficients — no pickles).
Reproduce: from `backend/`, run `scripts/v2/build_dataset.py` then `scripts/v2/train_evaluate.py`.
Full numbers: `docs/v2/v2_evaluation.json`. Input fingerprints (name, size, SHA-256 of every cached
source file) are in `docs/v2/data_manifest.json`; each model JSON records the dataset hash, seed and settings.

## 1. What the models predict

For each of Sri Lanka's 25 districts and each disease (FMD, LSD), the probability that the
district-month is recorded as an outbreak month in **target month t**.

- **Issue rule:** issued on **day 5 of month t**, using only observations published by then:
  rainfall and weather for t-1 and t-2, Niño 3.4 for t-2 and t-3, outbreak status for t-1 and t-2.
  No observation of month t is used. This is an *early-month operational forecast* (lead time
  is the remaining ~25 days of the month); it is not issued before the month starts.
- **Outputs:** probability, the district-month climatological baseline probability, and the
  relative risk (probability / baseline). "Elevated" means relative risk ≥ 2.

## 2. Labels (ground truth)

The `Outbreak status` field of the curated DAPH-derived district-month datasets.
Its original surveillance definition (declared outbreak vs reported case) is undocumented;
the models predict *that field*, nothing stronger.

| Disease | Years used | Outbreak months | Excluded |
|---|---|---|---|
| FMD | 2017–2023 | 228 / 2,100 | 2024 (see below) |
| LSD | 2020–2024 | 115 / 1,500 | — |

**FMD 2024 excluded as unverified.** All seven original merged files of the dataset author
(April–May 2026, e.g. `merged_final.csv`) have 2024 = 0 outbreaks. The final v1 dataset adds 78
positives forming one identical block — 13 districts × exactly Jan, Feb, Mar, Oct, Nov, Dec — while
no other FMD or LSD year has more than 5 districts sharing a month pattern. Their source is unknown.
Note: v1 reported its headline FMD metrics on this 2024 block.

## 3. Features and provenance (all public, all reproduced)

| Group | Features | Source | Verification |
|---|---|---|---|
| Season | sin/cos month, monsoon phase (target month) | calendar | — |
| Rainfall | rain_t1, rain_t2, r3h_t1, rfq_t1 | CHIRPS, WFP/HDX `lka-rainfall-subnat-full.csv` (adm2). Monthly = Σ dekad `rfh`; `r3h` = mean dekad 3-month rolling rainfall; `rfq` = mean dekad rainfall anomaly % | Reproduces v1 columns for 2,400/2,400 rows |
| Weather | temp_t1, humidity_t1, wind_t1 | NASA POWER (community AG) T2M, RH2M, WS2M at the dataset's district points | 2,400/2,400 rows exact; monthly = mean of daily (exact) |
| Soil | soil_top_t1 | NASA POWER (community AG) GWETTOP, surface soil wetness 0–1, previous month, same district points | Stands in for the proposal's SMAP soil moisture (Earthdata login, different latency); available as early as T2M |
| ENSO | nino34_anom_t2, nino34_anom_t3 | NOAA PSL `nina34.data` (now ERSST v6), anomaly vs 1991–2020 | Rebuilt for all years from the current file |
| Host | buffalo_density, livestock_density | v1 dataset (GLW-derived yearly values; latest year carried forward) | Interpolation method undocumented |
| Surveillance | own_t1, own_t2, neighbour_fraction_t1, neighbour_count_t1, neighbour_fraction_t2 | Outbreak labels (training); verified app cases/deaths (operations) | Neighbours from HDX COD-AB `lka_admin2` touches; reproduces all v1 neighbour features |

Unknown inputs stay unknown — they are never set to 0. The IOD (DMI) index was dropped: the
HadISST DMI file is ~5 months behind real time, so it is not available at issue time.

## 4. Candidates and evaluation protocol

- **Baselines:** always-zero; persistence (= last month's status); climatology (district × calendar
  month outbreak rate, shrunk toward the national month rate with 3 pseudo-years).
- **Prior without leakage:** the climatology prior is a *model input* in variants A and B. For the
  training rows it is computed **leave-one-year-out** (a row's prior never contains its own year's
  labels); for the forecast month it comes from all earlier data, as in operation. (An earlier run used
  the in-sample prior, which let each row's own label leak into its input — see section 7.)
- **Variants (L2 logistic regression, standardised):**
  - **A** — season + climate + host + surveillance + logit(climatology) *(pre-specified primary)*
  - **S** — surveillance features only
  - **B** — season + climate + host + logit(climatology) *(for when surveillance is unknown)*
  - **O** — the district's own last two months + logit(climatology) *(pre-specified primary for the
    "own district known, neighbours unknown" case; added in run 6)*
  - **OC** — O + season/climate/host features
- **Backtest:** monthly rolling origin, expanding window; each month is predicted by models trained
  only on earlier months. C ∈ {0.01, 0.03, 0.1, 0.3, 1}. Selection is **prequential**: each month uses
  the (variant, C) with the best PR-AUC on all earlier backtest months. First backtest year is
  warm-up; metrics are on the following years (FMD 2022–2023, LSD 2023–2024; 600 district-months each).
- **Metrics:** PR-AUC (primary, outbreaks are rare), ROC-AUC, Brier skill vs climatology,
  recall/precision at relative risk ≥ 2, onset PR-AUC (months with no outbreak in t-1),
  bootstrap 95% CIs of PR-AUC differences (2,000 resamples, fixed seed). The decision CI resamples
  **6-month moving blocks** because outbreaks cluster in time; the narrower i.i.d. month bootstrap is
  stored next to it (`iid_month_ci95`) as a sensitivity only.
- **Deployment rule:** a forecaster is deployed only if its PR-AUC gain over climatology has a 95%
  CI above 0, its Brier skill is positive, and it is not worse than persistence on average.

## 5. Results (evaluation years; leave-one-year-out prior, 6-month block CIs, soil wetness included)

### FMD (2022–2023, 48 outbreak months)

| Forecaster | PR-AUC | ROC-AUC | Brier skill | Onset PR-AUC |
|---|---|---|---|---|
| Always zero | 0.080 | 0.500 | -0.042 | 0.053 |
| Persistence | 0.180 | 0.663 | -0.455 | — |
| **Climatology (deployed for known surveillance)** | 0.196 | 0.671 | +0.000 | 0.111 |
| A (primary, not deployed) | 0.295 | 0.745 | +0.131 | 0.146 |
| S | 0.312 | 0.760 | +0.160 | 0.168 |
| B | 0.211 | 0.706 | +0.058 | 0.112 |

A − climatology: +0.052 [-0.022, +0.126] (i.i.d. month bootstrap [-0.024, +0.296]) — the interval includes zero, so A **does not pass**
the deployment rule. A − persistence: +0.094 [+0.006, +0.193]. S − climatology: +0.067 [-0.029, +0.156]. Per year (A/S prequential): 2022 0.308, 2023 0.360.
The models are ahead of climatology on point estimates, but with 48 outbreak months in two years that
advantage cannot be distinguished from chance, so the full-surveillance case deploys the baseline.

### LSD (2023–2024, 70 outbreak months)

| Forecaster | PR-AUC | ROC-AUC | Brier skill | Onset PR-AUC |
|---|---|---|---|---|
| Always zero | 0.117 | 0.500 | +0.022 | 0.079 |
| Persistence | 0.228 | 0.659 | -0.187 | — |
| Climatology | 0.094 | 0.299 | +0.000 | 0.065 |
| **A (deployed)** | 0.246 | 0.647 | +0.166 | 0.093 |
| S | 0.307 | 0.723 | +0.206 | 0.152 |
| B | 0.098 | 0.320 | +0.018 | 0.063 |

A − climatology: +0.148 [+0.004, +0.228] (i.i.d. [+0.042, +0.312]); A − persistence: +0.024 [-0.019, +0.077]. S − climatology: +0.188 [-0.022, +0.257]; S − persistence: +0.064 [+0.014, +0.106].
Per year (prequential A/S): 2023 0.339, 2024 0.021 (2024 has only 5 outbreak months).
A passes the pre-specified rule, but its lower confidence bound is barely above zero and the skill comes almost
entirely from the 2023 wave. Treat it as weak evidence that needs prospective confirmation. (Climatology's ROC
of 0.30 means the LSD seasonal pattern *reversed* between years.)

### Own district known, neighbours unknown (same rows and rule)

| Forecaster | FMD PR-AUC | FMD gain vs climatology (95% CI) | LSD PR-AUC | LSD gain vs climatology (95% CI) |
|---|---|---|---|---|
| Climatology | 0.196 | — | 0.094 | — |
| **O** | **0.302** | **+0.069 [+0.004, +0.123]** | 0.256 | +0.140 [-0.025, +0.219] |
| OC | 0.338 | +0.059 [+0.002, +0.172] | 0.215 | +0.118 [+0.018, +0.171] |

FMD O passes the rule, but its lower bound is almost zero and O/OC were added after the earlier runs on the same
data, so treat it as weak evidence. LSD O fails (CI includes zero; also not better than persistence), so LSD stays
on the baseline for this case.

### Alert-rule metrics (alert = probability ≥ 2× the climatological baseline)

| Forecaster | FMD recall | FMD precision | FMD F1 | LSD recall | LSD precision | LSD F1 |
|---|---|---|---|---|---|---|
| Persistence (last month) | 0.33 | 0.30 | 0.32 | 0.40 | 0.39 | 0.40 |
| Climatology | 0.00 | n/a | 0.00 | 0.00 | n/a | 0.00 |
| A (known surveillance) | 0.40 | 0.09 | 0.15 | 0.81 | 0.19 | 0.31 |
| S | 0.42 | 0.08 | 0.13 | 0.81 | 0.19 | 0.31 |
| O (own district only) | 0.35 | 0.08 | 0.13 | 0.77 | 0.19 | 0.30 |

Climatology never raises an alert by construction (its relative risk is exactly 1). At this alert rule the models
find more outbreaks than persistence (higher recall, especially LSD) but with much lower precision, so
**persistence has the better F1**. The models' advantage is in ranking and calibration (PR-AUC, Brier skill), not
in a hard yes/no alert.

### Effect of adding soil wetness (run 7)

`soil_top_t1` (NASA POWER surface soil wetness, previous month) was added to the climate features as the
proposal's soil-moisture variable. Evaluated with the unchanged rule it made **no measurable difference**:

| Forecaster | FMD PR-AUC before → after | LSD PR-AUC before → after |
|---|---|---|
| A | 0.294 → 0.295 | 0.249 → 0.246 |
| B | 0.208 → 0.211 | 0.113 → 0.098 |
| OC | 0.337 → 0.338 | 0.214 → 0.215 |

Changes are within ±0.015 PR-AUC and no deployment decision changed. The feature is kept because it is part of
the proposal's design and is harmless, not because it improved the forecasts.

## 6. Deployment

| Disease | District **and** neighbours known | District known, neighbours unknown | Nothing known |
|---|---|---|---|
| FMD | Climatology — **baseline** (no model passed) | Variant **O**, C = 1.0 — **back-tested candidate** (weak) | Climatology — baseline |
| LSD | Variant **A**, C = 0.01 — **back-tested candidate** (weak) | Climatology — baseline | Climatology — baseline |

"Back-tested candidate" means the forecaster beat climatology in rolling back-testing; it has **not**
been confirmed on future data. "Surveillance known" means the outbreak status of the district **and all
its neighbours** for t-1 and t-2 is known. In operations this comes from verified app cases/deaths in
districts with registered farms; elsewhere status is unknown and the climatology forecast is shown,
labelled as such. A climatology record's relative risk is 1.0 by construction, so it is displayed as a
seasonal baseline, never as an assessed LOW risk.

## 6b. Forecast uncertainty (probability intervals)

Every stored forecast carries an **80% interval** (`probability_low`, `probability_high`, `interval_level`)
shown in the UI as e.g. "80% range 18–47%".

- **Models:** 200 coefficient sets are stored per deployed model, each fitted on training months resampled in
  6-month blocks. The interval is the 10th–90th percentile of the probabilities those sets give for the
  forecast's inputs. It captures **uncertainty in the estimated probability from limited training data
  only** — not outcome randomness and not drift between years.
- **Baseline:** 10th–90th percentile of a Beta distribution built from the district-month's outbreak counts
  (wide, because each district-month has only 5–7 yearly observations).
- **Reliability check (backtest):** forecasts are grouped into five probability bins; for each bin the
  observed outbreak rate is compared with the bin's mean interval. "± sampling noise" additionally allows
  ±1.28 standard errors on the observed rate, because a bin of ~120 rows has noisy outcomes. This check
  was refined after a first run showed the raw check ignores that noise; both versions are reported.

| Disease | Case | Forecaster | Bins inside (raw) | Bins inside (± sampling noise) | Mean width |
|---|---|---|---|---|---|
| FMD | District known, neighbours unknown | O | 2/5 | 3/5 | 0.045 |
| FMD | Nothing known | climatology | 4/5 | 5/5 | 0.198 |
| LSD | District and neighbours known | A | 4/5 | 4/5 | 0.097 |
| LSD | Nothing known | climatology | 2/5 | 3/5 | 0.144 |

Reading: intervals that are too narrow understate the real uncertainty (observed rate outside the interval in
several bins) — treat every interval as a lower bound on the true uncertainty. Intervals were not tuned to
improve this result.

## 6c. Artifact versions

| Version | What it is | Records made with it |
|---|---|---|
| `v2.0` | Artifact before the own-district tier, probability intervals, soil wetness and the Patch C evaluation fixes were in the shipped models | The 50 forecasts issued on 2026-10-14 for October 2026 (no interval or soil fields; issued on day 14, not the nominal day 5) |
| `v2.1` | Current artifact (coefficients re-derived deterministically; only the version label and timestamp differ from the artifact those intermediate runs produced) | Every forecast issued from now on |

A record's `model_version` and idempotency key therefore identify the artifact that produced it. October 2026
records are kept as issued and are not re-written; they are late-issued (day 14) and use the older schema, so
they should not be counted as prospective validation evidence. The first prospective run is the next month,
issued on or after day 5 with `v2.1`.

## 7. Protocol history (all evaluation runs, for transparency)

1. **Run 1:** variants A and B, C chosen on the first backtest year. FMD: A passed. LSD: nothing
   passed; climatology was *anti-informative* (ROC 0.30) because the 2023 LSD wave had no precedent.
2. **Run 2:** added variant **S** (surveillance only) after seeing run 1 — motivated by LSD's
   epidemic dynamics. Single-year selection chose A for LSD from 2022, a year with only 4 outbreaks.
3. **Run 3:** replaced single-year selection with **prequential** selection (each month uses only
   earlier months) to reduce selection noise.
4. **Run 4 (final):** fixed the deployment protocol: the pre-specified primary A is preferred when it
   passes ("back_tested"); otherwise the prequential A/S forecaster may be deployed as "exploratory".
   Because S was introduced after evaluation results were seen, LSD's deployed model was exploratory.
5. **Run 5 (current, "Patch C"):** removed a leak and made the intervals more honest.
   (a) Training rows now use a leave-one-year-out climatology prior instead of one that contained their
   own label. (b) The decision CI uses 6-month moving blocks instead of independent months.
   (c) Fixed seed per comparison, dataset hashes and a data manifest were added.
   Effect: FMD variant A's PR-AUC gain over climatology shrank from +0.116 [+0.006, +0.220] to
   +0.051 [−0.022, +0.123], so FMD no longer qualifies and falls back to the baseline. For LSD the
   pre-specified primary A now passes (A − climatology +0.151 [+0.010, +0.227]) and is deployed as a
   back-tested candidate in place of the exploratory S. No decision rule or threshold was changed after
   seeing these results; the earlier runs' numbers are superseded by this run.
6. **Run 6 (own-district tier):** because the app covers few districts, "district and all neighbours
   known" almost never holds. Added the pre-specified variants O and OC for "district known, neighbours
   unknown" and a new `own_known` deployment tier. Rule unchanged. FMD O passes narrowly; LSD does not.
   No other numbers changed.
7. **Run 7 (soil wetness):** added `soil_top_t1` (NASA POWER surface soil wetness). All variants were
   re-evaluated with the unchanged rule: PR-AUC changed by at most 0.015, no deployment decision changed.
   NDVI (MODIS) was not added: it needs an Earthdata login and was not part of the training data.

## 8. Limitations

- Small samples (FMD 228, LSD 115 outbreak months); CIs are wide. LSD skill comes almost entirely from
  the 2023 wave; 2024 (5 outbreaks) shows almost no skill. FMD has too few outbreak months in two
  evaluation years to show a significant gain over the seasonal baseline.
- Five evaluation runs were made on the same data (section 7). The fixes in run 5 correct a method
  flaw, but model selection across runs is still a source of optimism; only prospective results
  (`GET /v2/performance` on non-backfilled records) can confirm skill.
- **No severity (Stage 2) forecast is issued.** Annual DAPH severity labels do exist (FMD: 115 district-years,
  2017-2024; LSD: 56 district-years, 2020-2024; `data/processed/severity_labels.csv`, `LSD_severity_labels.csv`;
  an earlier statement that FMD had no case/death labels was wrong for these files and is corrected here). They
  are annual totals (cases, deaths, outbreak months), not monthly, so each label is one correlated annual value.
  `scripts/v2/evaluate_severity.py` evaluates the old Stage 2 idea against baselines that use no weather
  (leave-one-year-out and forward-chaining, 95% intervals from resampling whole years; full numbers in
  `docs/v2/severity_evaluation.json`):
  - FMD (LOW 72 / MEDIUM 31 / HIGH 12): "always LOW" reaches 62.6% accuracy (macro-F1 0.26); the old-style random
    forest 56.5% (macro-F1 0.35); the district's own past severity (mode) 62.6% (macro-F1 0.37). Models are not
    better than district history (random forest minus district history, macro-F1: -0.08 to +0.06 leave-one-year-out;
    -0.06 to +0.24 forward); logistic regression is worse.
  - LSD (classes balanced, 19/18/19; chance is about 33%): district history 35.7% accuracy, no model clearly above it
    (all intervals against district history include 0, or are below it).
  - A second, pre-registered experiment (`STAGE2_EXPERIMENT_PLAN.md`, `scripts/v2/stage2_experiment.py`, results in
    `stage2_experiment_results.json`) used only information available before the target year and probabilistic
    scoring (Ranked Probability Score). It tested a penalised ordinal logistic model and a hierarchical model against
    district history and the national class frequency with forward chaining. No candidate met the pre-set decision
    rule for FMD or LSD (for FMD even the national class frequency had a lower RPS than both models). The bootstrap
    intervals quoted above rest on 5-8 years and are descriptive only.
  - Conclusion: with annual labels, weather and density features add no demonstrated skill over a district's own
    history, so no severity forecast is deployed (the same deployment rule as Stage 1: not better than the
    baseline means the baseline is shown). The severity score formula (`cases * months/12 + 10 * deaths`) and its
    thresholds are design choices, not clinically validated. Monthly app counts are a different quantity and are
    not comparable with these labels. `GET /v2/performance` reports `stage2_readiness`; Stage 2 should be
    re-evaluated with the same rules once enough monthly counts exist. Until then the application shows the
    previous month's observed cases and deaths as an observation, not as a severity prediction.
- **Severity shown in the application.** Each forecast card shows "Severity if an outbreak occurs": the most likely
  class of the district's recorded outbreak years (annual DAPH labels), with the three class shares and the number of
  years behind it (`models/v2/severity_history.json`, built by `scripts/v2/build_severity_history.py`, served by
  `GET /v2/severity-history`). District shares are shrunk toward the national shares (k = 2) and classes within five
  percentage points of the most likely one show the more severe class. This is a descriptive estimate from past annual
  records, not a model forecast and not a monthly figure; a district with no recorded outbreak year shows nothing.
  The previous month's verified cases and deaths are shown separately, without the derived severity label.
- Label semantics are undocumented; FMD 2024 labels are excluded.
- Operational surveillance (app verified cases/deaths from registered farms) is a different signal from
  the curated labels used in training and currently covers few districts.
- The relative-risk alert threshold (2×) is a design choice, not tuned on outcomes.
- Intervals reflect parameter uncertainty (and counts for the baseline) only; see section 6b.
- Coefficients are associations, not causal effects; climate terms contribute little compared with the
  climatology prior and last month's outbreak status.
- Host density values are GLW-derived yearly interpolations whose method is undocumented.

## 9. What this replaces (v1)

v1 used same-month weather (not available at issue time), forecast 2025–2026 months from 2024 proxy
rows, reported FMD metrics on the unverified 2024 labels, turned unknown surveillance into
"verified 0", and its live weather provider computed `r3h`/`rfq`/wind with different definitions and
units from the training data. v2 removes each of these issues.
