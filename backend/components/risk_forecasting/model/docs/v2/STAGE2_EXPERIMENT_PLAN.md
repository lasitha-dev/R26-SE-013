# Stage 2 (annual severity) — target audit and pre-registered experiment plan

Status: **DRAFT for approval. Nothing in this plan has been trained or deployed.** No repository code, Atlas data,
stored forecasts or UI is changed by this document. Written 2026-10-14.

## 1. What is being asked

Can a model estimate, from information available before the event, the **annual severity class of an outbreak
district-year** (LOW < MEDIUM < HIGH) better than baselines that use no weather? This is an *annual,
conditional-on-outbreak* quantity. It is **not** a forecast for a month, and it is **not** multiplied with the
monthly Stage 1 probability (different time units; no valid combined score exists today).

## 2. Target audit (reproduced from the files in `data/processed`, hashes in `data_manifest.json`)

| Item | FMD | LSD |
|---|---|---|
| Rows (district-years) | 115, 23 districts, 2017-2024 | 56, 24 districts, 2020-2024 |
| Classes LOW / MEDIUM / HIGH | 72 / 31 / 12 | 19 / 18 / 19 |
| Score formula (recovered exactly from the data) | `cases * outbreak_months/12 + 10 * deaths` | `cases + 5 * outbreak_months + 10 * deaths` |
| Class thresholds | fixed 50 / 300 | 63 / 460, **equal to the tertiles of the whole data set** |
| Rows with deaths > 0 | 55 | 17 |
| Observations per district (min / median / max) | 1 / 5 / 8 | 1 / 2 / 5 |
| Rows with a previous-year label for the same district | 74 (64%) | **19 (34%)** |
| Rows with any earlier-year label | 92 | 32 |

Findings that change how the experiment must be run:

1. **The two diseases use different score formulas**, so their scores and classes are not comparable. Models are
   disease-specific; scores are never pooled.
2. **The weights (10 per death; 5 per outbreak month in LSD) and the thresholds are design choices**, not
   clinically validated. FMD's score also divides by 12, LSD's does not. Exposure (herd size) is not considered and
   reporting completeness may differ between years.
3. **LSD thresholds were computed on the whole data set** (tertiles including future years), a mild form of
   leakage. FMD tertiles would assign **47%** of rows to a different class than the fixed 50/300 thresholds, so the
   class definition itself is a large researcher degree of freedom. Thresholds are fixed in advance (section 4);
   the alternatives are reported only as sensitivity analyses.
4. **Class mix by year is very uneven.** FMD 2024 is entirely LOW (13/13; FMD 2024 outbreak labels are already
   excluded from Stage 1); FMD 2020 and 2023 have no HIGH. LSD 2023 holds 24 of 56 rows (43%); LSD 2022 and 2024 have
   no MEDIUM or HIGH. Results must be shown per year and with 2024 (FMD) / 2023 (LSD) removed.
5. **`outbreak_months` is part of the target.** It matches the feature-file outbreak-month count in 87.8% of FMD
   rows (all LSD rows). It is therefore never used as a predictor, and neither is Stage 1 output derived from the
   same year's outbreak flags.
6. **Earlier evaluation used the target year's outbreak-month weather as predictors.** That information is not
   available before an outbreak, so it is not allowed in this experiment (section 3).
7. **Lag features are mostly unusable.** A previous-year severity label exists for 64% of FMD rows and only 34% of
   LSD rows. "No earlier label" means *unknown*, never LOW and never zero; it is modelled with an explicit missing
   indicator. For LSD, lag features are dropped (too few rows).
8. **Outbreak labels are a different signal from the monthly app counts** (`cases + 10 * deaths` per month) and are
   not comparable with them.

Missing tools: `statsmodels`, `pymc` and `mord` are not installed. The ordinal models below are implemented with
`scipy`/`numpy` only (no new dependency).

## 3. Pre-specified predictors (fixed before any model is fitted)

Only information that exists before the start of the target year:

- Static district features: `livestock_density`, `buffalo_density` (latitude/longitude are excluded because they
  only identify the district).
- Environmental summary of the **previous** calendar year: mean `rainfall_mm`, `humidity`, `temp_lag1`.
- District history from **earlier years only**: number of earlier labelled years, mean `log1p(score)` of earlier
  years, plus a missing indicator when there is none (FMD only).
- Neighbour severity is **not** used (unreported is not LOW, and the reporting is too incomplete).

No feature selection on the full data; any selection happens inside the training folds.

## 4. Candidates (three, fixed)

| ID | Model | Role |
|---|---|---|
| B | District history baseline: most frequent class of the district's earlier years, national mode otherwise (the always-majority class is reported for reference) | mandatory benchmark |
| M1 | Penalised cumulative-logit ordinal regression (L2, penalty from the fixed grid {0.03, 0.1, 0.3, 1} chosen by an inner year-block validation) | primary ML candidate |
| M2 | Empirical-Bayes hierarchical model: `log1p(score)` with a district random intercept and the same covariates; class probabilities from the predictive normal at the thresholds | sparse-data candidate |

Gradient boosting is **not** a candidate (56 / 115 rows). If run at all, it is reported as a clearly labelled
sensitivity analysis and can never be the deployed model.

Class thresholds: FMD fixed 50 / 300; LSD fixed 63 / 460 (as in the labels). Sensitivity: tertiles recomputed
inside each training fold.

## 5. Evaluation protocol

- **Disease-specific.** No random splits.
- **Primary:** forward chaining (train on years before Y, test on Y). FMD test years 2019-2024 (6), LSD test years
  2021-2024 (4).
- **Secondary:** leave-one-year-out, descriptive only (it uses future years to predict the past).
- **Nested tuning:** the penalty and the random-effect variance are tuned only inside the training years.
- **Metrics:** balanced accuracy, macro-F1, ordinal mean absolute class error, **Ranked Probability Score**
  (lower is better), and calibration (reliability of P(HIGH) and the cumulative probabilities, with the number of
  rows per bin). Regression target M2 additionally: MAE, median absolute error, RMSE and Spearman correlation of
  `log1p(score)`.
- **Uncertainty:** year-block bootstrap, but with 6 (FMD) and 4 (LSD) test years the intervals are **descriptive
  and unreliable** (this also applies to the intervals in `severity_evaluation.json`). They are not used as the
  deciding evidence.
- **Reported:** every run, every candidate, every year, plus the earlier attempts that touch the same data (old
  Stage 2 RF / XGBoost / LightGBM / CatBoost and SMOTE / ADASYN / SMOTE-Tomek, and the five-model baseline
  comparison in `severity_evaluation.json`), so the amount of searching is visible.

## 6. Decision rule (fixed before running)

A model is *considered for use* only if, in the forward-chaining evaluation of its disease, **all** hold:

1. its mean Ranked Probability Score is lower than baseline B and also lower than the national class-frequency
   forecast;
2. its ordinal mean absolute class error is not higher than B;
3. it has a lower RPS than B in more than half of the test years;
4. it is not worse than B after removing FMD 2024 / LSD 2023 (sensitivity);
5. calibration shows no systematic reversal (a predicted HIGH-probability bin is not observed less often than a
   LOW-probability bin).

- **If met:** the application may show an *indicative annual severity estimate, conditional on an outbreak*:
  `P(LOW) / P(MEDIUM) / P(HIGH)`, with a note that it is based on a few years of annual records.
- **If not met:** no model is deployed. The application shows the **district's historical severity pattern**
  ("not a forecast for the selected month") and the previous month's observed cases and deaths as an observation.
  A negative result is reported as such in the thesis.

## 7. Display rules whatever the outcome

- Never described as a monthly or "next-month" severity forecast.
- No combined "expected burden" score (monthly probability x annual severity is not valid).
- `predicted_severity` stays empty for v2 records unless the rule in section 6 is met and a new, approved model
  version is issued.
- Cases and deaths are shown separately; the score formula is not presented as a clinical severity.

## 8. Steps and gates

| Step | Content | Gate |
|---|---|---|
| 1 | This audit and plan | **your approval** |
| 2 | Offline experiment (scratch only; no repository, Atlas or UI change) and report | you review the report |
| 3 | If the rule is met: a separate plan for a model artifact and UI; if not: the "historical pattern" display | your approval |
| 4 | Model card and thesis wording | — |

## 9. What this plan does not promise

It does not promise that a model will beat the baseline. With 115 / 56 annual, correlated, partly design-defined
labels the most likely honest outcome is that no model clearly does. The value is in testing that properly and
saying so.
