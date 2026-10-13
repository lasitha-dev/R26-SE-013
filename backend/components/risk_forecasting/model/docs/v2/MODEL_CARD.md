# Disease Risk Forecasting v2 — Model Card

Models: `models/v2/fmd_v2.json`, `models/v2/lsd_v2.json` (plain JSON coefficients — no pickles).
Reproduce: from `backend/`, run `scripts/v2/build_dataset.py` then `scripts/v2/train_evaluate.py`.
Full numbers: `docs/v2/v2_evaluation.json`.

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
| ENSO | nino34_anom_t2, nino34_anom_t3 | NOAA PSL `nina34.data` (now ERSST v6), anomaly vs 1991–2020 | Rebuilt for all years from the current file |
| Host | buffalo_density, livestock_density | v1 dataset (GLW-derived yearly values; latest year carried forward) | Interpolation method undocumented |
| Surveillance | own_t1, own_t2, neighbour_fraction_t1, neighbour_count_t1, neighbour_fraction_t2 | Outbreak labels (training); verified app cases/deaths (operations) | Neighbours from HDX COD-AB `lka_admin2` touches; reproduces all v1 neighbour features |

Unknown inputs stay unknown — they are never set to 0. The IOD (DMI) index was dropped: the
HadISST DMI file is ~5 months behind real time, so it is not available at issue time.

## 4. Candidates and evaluation protocol

- **Baselines:** always-zero; persistence (= last month's status); climatology (district × calendar
  month outbreak rate, shrunk toward the national month rate with 3 pseudo-years).
- **Variants (L2 logistic regression, standardised):**
  - **A** — season + climate + host + surveillance + logit(climatology) *(pre-specified primary)*
  - **S** — surveillance features only
  - **B** — season + climate + host + logit(climatology) *(for when surveillance is unknown)*
- **Backtest:** monthly rolling origin, expanding window; each month is predicted by models trained
  only on earlier months. C ∈ {0.01, 0.03, 0.1, 0.3, 1}. Selection is **prequential**: each month uses
  the (variant, C) with the best PR-AUC on all earlier backtest months. First backtest year is
  warm-up; metrics are on the following years (FMD 2022–2023, LSD 2023–2024; 600 district-months each).
- **Metrics:** PR-AUC (primary, outbreaks are rare), ROC-AUC, Brier skill vs climatology,
  recall/precision at relative risk ≥ 2, onset PR-AUC (months with no outbreak in t-1),
  month-block bootstrap 95% CIs (2,000 resamples).
- **Deployment rule:** a forecaster is deployed only if its PR-AUC gain over climatology has a 95%
  CI above 0, its Brier skill is positive, and it is not worse than persistence on average.

## 5. Results (evaluation years)

### FMD (2022–2023, 48 outbreak months)

| Forecaster | PR-AUC | ROC-AUC | Brier skill | Onset PR-AUC |
|---|---|---|---|---|
| Always zero | 0.080 | 0.500 | −0.042 | 0.053 |
| Persistence | 0.180 | 0.663 | −0.455 | — |
| Climatology | 0.196 | 0.671 | 0 | 0.111 |
| **A (deployed)** | **0.309** | **0.731** | **+0.102** | 0.140 |
| S | 0.312 | 0.760 | +0.160 | 0.168 |
| B | 0.204 | 0.677 | +0.008 | 0.112 |

A − climatology: **+0.116 [+0.006, +0.220]**; A − persistence: **+0.128 [+0.021, +0.227]**.
Per year (deployed forecaster): 2022 0.323, 2023 0.253.

### LSD (2023–2024, 70 outbreak months)

| Forecaster | PR-AUC | ROC-AUC | Brier skill | Onset PR-AUC |
|---|---|---|---|---|
| Always zero | 0.117 | 0.500 | +0.022 | 0.079 |
| Persistence | 0.228 | 0.659 | −0.187 | — |
| Climatology | 0.094 | 0.299 | 0 | 0.065 |
| A | 0.210 | 0.550 | +0.130 | 0.066 |
| **S (deployed, exploratory)** | **0.307** | **0.723** | **+0.206** | **0.152** |
| B | 0.108 | 0.378 | −0.042 | 0.074 |

S − climatology: **+0.214 [+0.097, +0.347]**; S − persistence: **+0.091 [+0.036, +0.167]**.
Per year (prequential forecaster): 2023 0.312, **2024 0.021** (only 5 outbreak months).

## 6. Deployment

| Disease | Surveillance status known | Surveillance status unknown |
|---|---|---|
| FMD | Variant **A**, C = 0.01 — **back-tested candidate** | Climatology — baseline |
| LSD | Variant **S**, C = 0.01 — **exploratory** | Climatology — baseline |

"Surveillance known" means the outbreak status of the district **and all its neighbours** for t-1
and t-2 is known. In operations this comes from verified app cases/deaths in districts with
registered farms; elsewhere status is unknown and the climatology forecast is shown, labelled as such.

## 7. Protocol history (all evaluation runs, for transparency)

1. **Run 1:** variants A and B, C chosen on the first backtest year. FMD: A passed. LSD: nothing
   passed; climatology was *anti-informative* (ROC 0.30) because the 2023 LSD wave had no precedent.
2. **Run 2:** added variant **S** (surveillance only) after seeing run 1 — motivated by LSD's
   epidemic dynamics. Single-year selection chose A for LSD from 2022, a year with only 4 outbreaks.
3. **Run 3:** replaced single-year selection with **prequential** selection (each month uses only
   earlier months) to reduce selection noise.
4. **Run 4 (final):** fixed the deployment protocol: the pre-specified primary A is preferred when it
   passes ("back_tested"); otherwise the prequential A/S forecaster may be deployed as "exploratory".
   Because S was introduced after evaluation results were seen, LSD's deployed model is exploratory
   and needs prospective confirmation.

## 8. Limitations

- Small samples (FMD 228, LSD 115 outbreak months); CIs are wide. LSD skill comes almost entirely from
  the 2023 wave; 2024 (5 outbreaks) shows almost no skill.
- Label semantics are undocumented; FMD 2024 labels are excluded.
- Operational surveillance (app verified cases/deaths from registered farms) is a different signal from
  the curated labels used in training and currently covers few districts.
- The relative-risk alert threshold (2×) is a design choice, not tuned on outcomes.
- Coefficients are associations, not causal effects. The largest FMD weights are the climatology prior
  and last month's outbreak status; climate terms contribute little.
- Host density values are GLW-derived yearly interpolations whose method is undocumented.

## 9. What this replaces (v1)

v1 used same-month weather (not available at issue time), forecast 2025–2026 months from 2024 proxy
rows, reported FMD metrics on the unverified 2024 labels, turned unknown surveillance into
"verified 0", and its live weather provider computed `r3h`/`rfq`/wind with different definitions and
units from the training data. v2 removes each of these issues.
