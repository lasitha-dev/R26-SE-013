# Final presentation guide (Disease Risk Forecasting: FMD and LSD)

For the presenter. Everything below was checked in the running application on 2026-10-14. Sign-in accounts:
`review.vet@adrs-review.lk` (Veterinary Officer, Colombo) and `review.daph@adrs-review.lk` (DAPH official), password `Review@2026`.

## 1. Before you start (10 minutes, same morning)
1. Backend, from `backend/`: `python -B -m uvicorn main:app --host 127.0.0.1 --port 8000`; wait for `/api/v1/risk-forecasting/health` to answer 200.
2. Frontend, from `frontend/`: `set VITE_FORECAST_REFERENCE_PERIOD=2026-09` then `npm run dev` (page: `http://127.0.0.1:5174`).
   With this setting the forecast month stays **October 2026** and the outlook month **November 2026**.
3. Open both accounts in two browser windows (or one normal and one private window). Icons and fonts are local, so no internet is needed.
4. Open the Vet page `/vet/forecasting` and the DAPH page `/vet/forecasting`; press refresh once; confirm the Colombo FMD card shows HIGH RISK.
5. Keep a screen recording of the full run as a backup (section 5).

## 2. Eight-minute run (what to click, what to say)
**Vet window (1: forecast).** Disease Risk Forecast, Colombo, October 2026.
- FMD card: "HIGH RISK, about 30% chance of an outbreak this month, higher than usual for Colombo."
- "Severity if an outbreak occurs: HIGH" with the three shares: "from this district's past outbreak years, 2017 to 2024."
- "Severity watch": "this follows the cases and deaths recorded in the app: September, 1 case and 2 deaths, so MEDIUM; October so far, none."
- Open "More details": exact figure, reason, "Explain forecast".

**Vet window (2: looking ahead).** Scroll to "Looking ahead: November 2026": "a seasonal outlook for next month: about 3%, likely between 0% and 10%, with the severity level of the district." Then open the Month list: "October, and November as an outlook."

**Live input (the key moment).** In the application used for case recording, record one verified case or a disease death for a Colombo farm, then refresh the Vet page: "October 2026 so far" now shows the new count and the severity watch changes (for example 12 cases and 2 deaths gives HIGH). "Nothing was typed into the forecasting screen; it reads the records."
(If you do not want to add a record on stage, show the September line, which comes from records entered earlier.)

**DAPH window (national).** District Priority Assessment Matrix: 25 districts x 2 diseases, Colombo FMD first; the new column "Severity if outbreak". Month list: October and "November (outlook)". Open "Generate forecasts" and show the **preview** dialog ("Nothing has been written yet"), then Cancel. Say: "the monthly forecast is issued by the DAPH official after a preview; in deployment this is a scheduled job."

**DAPH window (action).** Follow-Up Monitoring: the Colombo FMD follow-up that was issued to the Colombo veterinary officer. **Vet window:** Assigned Follow-Ups, status ACKNOWLEDGED; Advisory Centre: the approved advisory. "Forecast, follow-up and advisory are linked to the same stored forecast record."

## 3. What to say about the science (short and true)
- "The forecast is for the next month, per district, from last month's recorded outbreak status, seasonal patterns and weather. Candidate models were compared with a seasonal-average baseline using time-aware validation, and a model is used only where it beats the baseline. Otherwise the seasonal level is shown, which is why many districts read USUAL LEVEL."
- "Severity: the level shown is the usual severity of this district's past outbreak years. The monthly severity model is built: each month it reads the recorded cases and deaths, checks whether there is enough data, retrains and compares with baselines, and only then would it be issued. Today it reports that there is not enough monthly data yet (FMD: 8 of 100 outbreak district-months)."
- "The cases and deaths in the application are pilot entries from the veterinary workflow. The system is shown here as a working pipeline, not as field outbreak performance."

## 4. Likely questions
| Question | Answer |
|---|---|
| Is the severity machine learning? | The shown level comes from past outbreak records. A monthly learning pipeline exists and runs automatically as data accumulates; it will only replace the shown level if it beats simple baselines. I tested learning models on the old annual data and they did not beat the baseline, so I did not present them as predictions. |
| What is the accuracy? | Early warning is judged by alerts and probability quality rather than a single accuracy figure; the numbers and the comparison with the baseline are in the model card (section 5). |
| Why is Colombo HIGH? | The district recorded an outbreak last month and the data-driven variant for districts with recorded history raised its chance; the reason is shown in "Explain forecast". |
| Why do most districts say USUAL LEVEL? | No stronger warning sign than the seasonal pattern; an honest "usual level" is better than an invented low risk. |
| Is the data real? | Cases and deaths are what the veterinary workflow recorded in the application (pilot). The weather and climate inputs come from public sources (CHIRPS, NASA POWER, NOAA). |
| Why only a few districts have counts? | Only districts with registered farms report; others show "No app reports" and are never treated as zero. |
| What updates automatically? | The recorded counts, the severity watch and the next monthly forecast once the DAPH official issues it. A scheduler for the monthly run is the next deployment step. |
| What about farmers? | The farmer dashboard belongs to the health-anomaly component; this component serves veterinary officers and DAPH. |

## 5. If something fails
- A page shows no data: refresh; check `http://127.0.0.1:8000/api/v1/risk-forecasting/health`; restart the backend command in section 1.
- Atlas unreachable: play the screen recording.
- Do not click "Notify Assigned Farmers" or "Confirm and store" during the demonstration (they write data; October 2026 was already regenerated with ranges on 2026-10-15).

## 6. Facts you can quote (verified 2026-10-14)
50 current forecasts for October 2026 (25 districts x FMD and LSD; the earlier versions are kept as replaced records); Colombo FMD about 30% (HIGH); 50 issued November outlooks (Colombo FMD about 3%, likely 0% to 10%); severity history from 115 FMD and 56 LSD annual district-year records; monthly severity pipeline read-only, state INSUFFICIENT_DATA (FMD 8 of 100 outbreak district-months, 5 of 12 months).
