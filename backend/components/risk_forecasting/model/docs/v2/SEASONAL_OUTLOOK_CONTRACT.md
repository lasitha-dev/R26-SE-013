# Seasonal Outlook — Product Contract v1.1

Status (2026-10-14): **code written for P1–P4 (backend, CLI, endpoints, Vet and DAPH screens), accelerated for a
2026-10-19 demonstration of the November 2026 outlook.** No collection and no record exists in Atlas yet: reading,
the preview endpoint and `--dry-run` create nothing. P5 (docs) is partly done here; P6 (manual review),
P6.5 (index creation) and P8 (first issuance) each still need your explicit approval. Scoring (P3) is not built yet.

Demo path: until an issuance is approved, the screens show the server-computed **PREVIEW** (clearly labelled
"not yet issued"); after P6.5 and P8 they show the issued, immutable records.

Related: [MODEL_CARD.md](MODEL_CARD.md) (evidence and limits), [OPERATIONS.md](OPERATIONS.md).

## 1. Purpose and scope

Give Veterinary Officers and DAPH officials, **before a month starts**, a climatology-based view of how likely each
district is to have an outbreak month for **the next month only**, and keep it as an immutable record so it can later be
compared with the early-month forecast made with current data.

Out of scope (fixed): outlooks for 2–3 months ahead, ML-based outlooks, risk tiers, severity, any Farmer screen
(the farmer dashboard belongs to the health-anomaly component), rewriting or converting existing October 2026
records, enabling a scheduler, pushing or opening a PR.

## 2. The two products

| | **Seasonal Outlook** (new) | **Early-Month Forecast** (existing `forecast_records`) |
|---|---|---|
| Question | Is the next month an outbreak month, judged from the historical pattern? | Is this month an outbreak month, given last month's climate and surveillance? |
| Issue window | 15–30 days before the target month starts | around day 5 of the target month |
| Inputs | historical district-month frequency only | previous-month climate (rain, weather, soil wetness) and verified app cases/deaths |
| Method | district-month climatology | deployed variant, or the same climatology when inputs are unknown |
| Tier labels | **none** | LOW / MEDIUM / HIGH / BASELINE |
| Replaces the other? | **never** | **never** |

Both are scored separately (section 8). The early-month forecast never supersedes, edits or hides an outlook.

## 3. Record contract (`SeasonalOutlookRecord`)

| Field | Type / rule |
|---|---|
| `outlook_id` | `out_<12 hex>`, primary key |
| `product_type` | constant `SEASONAL_OUTLOOK` |
| `disease`, `district` | FMD or LSD; one of the 25 canonical districts |
| `target_year`, `target_month` | the month **after** the issue month |
| `probability` | float 0–1. **The only stored probability** (no percentage field; `probability_pct` is computed when serving) |
| `interval_type` | constant `BETA_POSTERIOR_CREDIBLE_APPROX` |
| `interval_level` | 0.8 (10th–90th percentile) |
| `probability_low`, `probability_high` | `low <= probability <= high` |
| `years_observed` | training years behind this district-month |
| `positive_years` | years in which this district-month was an outbreak month |
| `method` | constant `DISTRICT_MONTH_CLIMATOLOGY` |
| `method_version` | `district_month_climatology_v1` |
| `source_artifact_version` | e.g. `fmd_v2.1` (provenance only, not a prediction-model label) |
| `source_artifact_hash` | SHA-256 of the canonical JSON of the artifact's `climatology` block (not the whole file) |
| `data_cutoff` | last month of the training data |
| `issue_date`, `generated_at` | real UTC date and time of issuance |
| `lead_days` | days from `issue_date` to the first day of the target month |
| `status` | `ACTIVE` (default), `VOIDED`, `CORRECTED` |
| `replaces_outlook_id` | set only on a corrected record |
| `disclaimer_version` | `seasonal_outlook_v1` (the text lives in the UI and docs, not in every record) |
| `idempotency_key` | `OUTLOOK|disease|district|YYYY-MM` — **one official outlook per target** |

Deliberately absent: `risk_level`, `relative_risk`, `contributions`, `predicted_severity`, any severity or tier
field. Climatology has relative risk 1.0 by construction, so a tier would be meaningless.

## 4. Computation (deterministic, no external API)

1. `probability` = artifact `climatology.district_month["<district>|<month>"]` (shrunk rate; prior strength 3
   pseudo-years toward the national month rate). Fallback order if missing: national month rate, then overall rate.
2. Interval = 10th and 90th percentiles of `Beta(rate*(n+3), (1-rate)*(n+3))` with `n = years_observed`.
   It is an **approximate credible interval from shrunk counts**, not a conformal or guaranteed interval. The prior
   parameters are part of `method_version`. The model card already shows such intervals can be too narrow.
3. `years_observed` and `positive_years` come from the artifact. The current artifact does not store the counts, so the
   first implementation step adds them to the exported `climatology` block (a re-export, not a change of rates).
4. No threshold such as "fewer than N years is limited". The UI shows the two numbers; the interpretation (for
   example LSD seasonality reversing between 2022 and 2023) lives in the model card.

## 5. Identity, immutability and corrections

- Issued content (`probability`, interval, provenance) is never edited. Normal flow has no update or delete.
- A wrong record is handled by **status only**: `VOIDED` (withdrawn, no replacement) or `CORRECTED` plus a new
  record whose `replaces_outlook_id` points at it. The original stays for audit. Readers use the active head.
- Re-running the same command returns the existing record (same key) and creates nothing.
- A later retrain of the artifact does **not** create a second official outlook for a target already issued;
  only an explicit correction can.
- Minimal scope: `status` + `replaces_outlook_id` + tests. No correction UI.

## 6. Storage and Atlas safety

- New collection `forecast_outlooks`. **`forecast_records`, advisories and follow-ups are never touched**, so the
  official-record selection, the supersede policy and `/v2/performance` keep their current meaning.
- Repositories used by dry-run, GET endpoints and the UI must **not** create collections or indexes. Index
  creation is a separate `ensure_indexes()` step run only in an approved phase (P6.5).
- Writes happen only in P8, only to the new collection, only after a dry-run preview and your explicit approval.

## 7. Serving and UI (Vet and DAPH only)

- `GET /v2/outlooks?disease&district&target_year&target_month` (read-only).
- Vet and DAPH screens: when a target month has no early-month forecast, show an **Outlook card** instead of
  "No Record" (own colour, "SEASONAL OUTLOOK" label, probability, interval, "N years, X with an outbreak",
  disclaimer). When an early-month forecast exists it is the main figure and the outlook is one small line,
  "Outlook issued earlier: 3.1% (80% range 1–9%)". Outlooks are excluded from the HIGH/MEDIUM/LOW KPI counts.
- No Farmer screen.
- Wording (EN): "A climatology-based seasonal outlook from historical district-month outbreak frequency. It does
  not include current surveillance or recent environmental conditions."
  Wording (SI): "අතීත සෘතුමය රටාව මත පදනම් වූ අවදානම් දර්ශනයකි. වත්මන් රෝග වාර්තා හෝ මෑත කාලගුණ දත්ත ඇතුළත් නැත."

## 8. Outcome and scoring (fixed in advance)

- **Outcome source:** `APP_VERIFIED_CASES_AND_DEATHS` (veterinary-verified records in the platform, which is the
  system's own ground truth); curated DAPH data where it exists for the period. A DAPH bulletin arriving years
  later is additional confirmation, not a precondition for scoring.
- **Outcome statuses** (existing): `CONFIRMED_OUTBREAK`, `NO_REPORTED_CASES`, `NO_SURVEILLANCE_COVERAGE`,
  `UNVERIFIED_LABEL`, `SOURCE_UNAVAILABLE`. Only the first two are scored; the others are counted and reported as
  excluded, never treated as 0.
- **Timing:** scored once the target month plus one grace month has passed.
- **Metrics:** Brier score of the outlook; paired comparison on the same disease + district + month:
  `delta_brier = Brier_early_update - Brier_outlook` (negative = the update is better, positive = the outlook is
  better, 0 = equal). Report `n_paired`, the excluded counts, and a month-block bootstrap 95% interval; with
  few pairs say "too few to conclude".
- Report separately by `lead_days` band and keep late or backfilled records apart.

## 9. Phases and gates

| Phase | Content | Gate |
|---|---|---|
| P0 | Approve this contract | your approval |
| P1 | Schema, service, artifact `climatology` counts, tests | **done** (91 allowlisted tests pass) |
| P2 | CLI job (dry-run), repository, GET endpoint | **done**; dry-run output: 50 planned, 0 saved |
| P3 | Scoring | not built (after the demo) |
| P4 | UI (Vet, DAPH) | **done**; frontend suite has no new failures, build passes |
| P5 | Docs (model card "Products", operations) | — |
| P6 | Read-only audit and your manual UI review | your sign-off |
| P6.5 | `ensure_indexes()` on the new collection | **explicit approval** |
| P7 | Dry-run preview of the first issuance | you review it |
| P8 | First issuance: **December 2026** outlook (FMD 25 + LSD 25), after Nov 5 | **explicit approval** |
| P9 | Read-back verification and prospective-scoring registration | — |

P1 starts only after the current v2 UI review and the first prospective run (early November) are finished.

## 10. Definition of done

1. 50 records for the first target month (FMD 25, LSD 25), duplicates 0.
2. No `probability_pct`, `risk_level`, `relative_risk` or severity stored; every record carries `method_version`,
   `source_artifact_hash`, `data_cutoff`, interval metadata, `years_observed`, `positive_years`.
3. Re-running changes nothing and returns the existing ids.
4. `forecast_records`, advisories and follow-ups are byte-for-byte unchanged by the release.
5. Read paths never create collections or indexes (tested).
6. A VOID and a CORRECT case are tested.
7. Scoring excludes unknown outcomes and reports the paired delta with its direction and counts.
8. UI: only Vet and DAPH; an outlook never shows LOW/MEDIUM/HIGH; the early-month forecast is the main figure when both exist.
9. Allowlisted backend tests pass; frontend suite has no new failures against the pre-existing set; build passes.

## 11. Changes from v1.0 (traceable)

| Change | Reason |
|---|---|
| Farmer UI removed | Farmer dashboard belongs to another component |
| `model_version` → `method_version` + `source_artifact_*` | an outlook is not a model prediction |
| `probability_pct` not stored | avoid two values drifting apart |
| Interval renamed, prior versioned | accurate statistical meaning |
| Key without version; corrections via `status` / `replaces_outlook_id` | one official outlook per target |
| Index creation moved to an approved phase (P6.5) | even constructing a repository can create indexes |
| Outcome source and statuses written down | scoring must be unambiguous |
| Delta direction and `n_paired` specified | avoid misreading the comparison |
| "years < 10 = Limited" removed | arbitrary threshold; numbers are shown instead |
| Issue windows defined | outlook 15–30 days before, update at day ~5 |
| `disclaimer_version` instead of repeated text | smaller records |

Not adopted from review: requiring DAPH-confirmed outcomes as the only ground truth. The platform's own
vet-verified records are the intended replacement for bulletins that arrive years late; the source is named
explicitly instead.

## 12. Open items for your decision
1. Approve this contract (P0).
2. First real issuance: changed to the **November 2026** outlook for the 2026-10-19 demonstration (approval still needed
   for P6.5 and P8). `lead_days` records the true lead time (about 17 days if issued on Oct 15); the 15–30 day issue
   window is a target, not a validity rule, and an issuance on Oct 19 would be 13 days ahead and recorded as such.
3. `years_observed` and `positive_years` were added to the exported climatology block (re-export done; rates and
   every other field are unchanged).
4. **Month lists as time passes (Vet, DAPH).** The lists follow the date: "recent" months and the outlook month move with
   the forecast reference month (pinned to 2026-09 for the demo through `VITE_FORECAST_REFERENCE_PERIOD`; unset it
   afterwards). Nothing is issued automatically, because there is no scheduler yet:
   - about Nov 5: the DAPH official issues the November early-month forecast (preview, then confirm); the
     "(outlook)" tag on November goes away and the earlier outlook stays under "More details" ("Outlook given earlier");
   - during November: the December outlook is issued by the outlook job (explicit approval); only then does
     "December 2026 (outlook)" appear on the Vet list (the DAPH list always offers the month after the forecast month);
   - the same pattern repeats for January 2027 and later.
   A scheduler stays deferred until the manual routine has run for a few months.
5. **Old-method records in `forecast_records`** (70 v1 records, none with a `model_version`): removal or hiding is waiting
   for your decision; some are referenced by advisories and follow-ups (see the owner's message of 2026-10-14).
