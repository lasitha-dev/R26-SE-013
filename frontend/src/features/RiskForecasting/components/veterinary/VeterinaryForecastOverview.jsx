import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  SCOPE_LEVELS,
  validateViewerContext,
  getAuthorizedDistricts,
} from '../../contracts/viewerContext.js';
import { AccessContextUnavailable } from '../AccessContextUnavailable.jsx';
import { getDefaultTargetPeriod } from '../../config/forecastPeriod';
import { OutlookCard, OUTLOOK_NOTE } from '../OutlookCard';
import { ForecastDetails } from '../ForecastDetails';
import { RiskReasonBulb } from '../GuideCards';
import { loadOutlooks, outlookFor, NO_OUTLOOK } from '../../services/outlookLoader';
import { loadSeverityHistory, severityFor, NO_SEVERITY_HISTORY } from '../../services/severityHistoryLoader';
import { SeverityPanel } from '../SeverityPanel';
import { loadObservations, monthHasStarted } from '../../services/liveObservationLoader';
import {
  describeRiskPlain,
  formatChance,
  formatLikelyRange,
  isV2Record,
  monthName,
  nextPeriod,
  periodLabel,
  selectOfficialRecords,
  storedExplanation,
} from '../forecastPresentation';
import { listForecastRecords } from '../../services/riskForecastingWorkflowApi.js';

const FEATURE_LABELS = {
  'Iod Dmi': 'Indian Ocean Dipole (Sea Temp Anomaly)',
  'Rfq': 'Rainfall Frequency (Days with Rain)',
  'Humidity Lag1': 'Relative Humidity (Previous Month)',
  'Humidity Lag2': 'Relative Humidity (2 Months Ago)',
  'Humidity Lag3': 'Relative Humidity (3 Months Ago)',
  'Cos Month': 'Seasonal Cycle (Time of Year)',
  'Sin Month': 'Seasonal Cycle (Time of Year)',
  'Nino34 Lag3': 'El Niño Indicator (3 Months Ago)',
  'Nino34 Lag2': 'El Niño Indicator (2 Months Ago)',
  'Nino34 Lag1': 'El Niño Indicator (Previous Month)',
  'Nino34': 'El Niño Indicator (Current)',
  'Rain Lag3': 'Total Rainfall (3 Months Ago)',
  'Rain Lag2': 'Total Rainfall (2 Months Ago)',
  'Rain Lag1': 'Total Rainfall (Previous Month)',
  'Rain': 'Total Rainfall (Current Month)',
  'Own Outbreak Lag1': 'Local Outbreak History (Previous Month)',
  'Own Outbreak Lag2': 'Local Outbreak History (2 Months Ago)',
  'Own Outbreak Lag3': 'Local Outbreak History (3 Months Ago)',
  'Monsoon Phase First Inter Monsoon': 'First Inter-Monsoon Phase',
  'Monsoon Phase Second Inter Monsoon': 'Second Inter-Monsoon Phase',
  'Monsoon Phase South West Monsoon': 'South-West Monsoon Phase',
  'Monsoon Phase North East Monsoon': 'North-East Monsoon Phase',
  'Tmax': 'Maximum Temperature',
  'Tmin': 'Minimum Temperature',
  'Tmax Lag1': 'Max Temperature (Previous Month)',
  'Tmax Lag2': 'Max Temperature (2 Months Ago)',
  'Tmin Lag1': 'Min Temperature (Previous Month)',
  'Tmin Lag2': 'Min Temperature (2 Months Ago)',
  'Ndvi': 'Vegetation Index (NDVI)',
  'Ndvi Lag1': 'Vegetation Index (Previous Month)',
  'Ndvi Lag2': 'Vegetation Index (2 Months Ago)',
  'Elevation': 'District Elevation (Topography)',
  'Cattle Density': 'District Cattle Density'
};

function formatProbability(val) {
  if (typeof val === 'number') {
    return `${val.toFixed(1)}%`;
  }
  if (typeof val === 'string' && val.trim() !== '') {
    const parsed = parseFloat(val);
    return isNaN(parsed) ? val : `${parsed.toFixed(1)}%`;
  }
  return 'Not available';
}

const periodKey = (p) => p.year * 12 + p.month;

const prevPeriod = (p) => (p.month === 1 ? { year: p.year - 1, month: 12 } : { year: p.year, month: p.month - 1 });

const samePeriod = (a, b) => Boolean(a && b) && a.year === b.year && a.month === b.month;

/**
 * The month shown first: the latest one with a forecast that is not later than the forecast target month
 * (the month after the reference month), so stray records for far-future months never become the default.
 */
function pickDefaultPeriod(available) {
  if (available.length === 0) return null;
  const target = getDefaultTargetPeriod();
  const withForecast = available.filter((p) => !p.outlook);
  return withForecast.find((p) => periodKey(p) <= periodKey(target)) || withForecast[withForecast.length - 1] || available[0];   // newest first
}

/**
 * Veterinary Forecast Overview.
 *
 * Shows, in plain words, the stored forecast for the assigned district (only months that have one can be chosen,
 * so there are no empty cards) and the outlook for the month after it. Technical details sit behind "More details".
 */
export function VeterinaryForecastOverview({ viewerContext, referenceDate = new Date() }) {
  // 1. Fail-closed Context & Access Validation
  const validation = validateViewerContext(viewerContext);
  const isVetRole =
    validation.valid && validation.normalizedContext.role === ROLES.VETERINARY_OFFICER;

  const scopeLevel = isVetRole ? validation.normalizedContext.authorization.scopeLevel : null;
  const isAllowedScope =
    scopeLevel === SCOPE_LEVELS.DISTRICT || scopeLevel === SCOPE_LEVELS.PROVINCE;

  const authorizedDistricts = isVetRole ? getAuthorizedDistricts(viewerContext) : [];
  const assignedDistrict = authorizedDistricts.length > 0 ? authorizedDistricts[0] : null;

  const isAccessAllowed = Boolean(isVetRole && isAllowedScope && assignedDistrict);

  // 2. Component State
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(null);
  const [records, setRecords] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [selected, setSelected] = useState(null);
  const [outlooks, setOutlooks] = useState(NO_OUTLOOK);
  const [outlookPeriod, setOutlookPeriod] = useState(null);
  const [earlierOutlooks, setEarlierOutlooks] = useState(NO_OUTLOOK);   // outlook issued earlier for the month on screen
  const [severityHistory, setSeverityHistory] = useState(NO_SEVERITY_HISTORY);
  const [liveObservations, setLiveObservations] = useState({});   // disease -> district -> recorded counts for the month on screen
  const [outlookRecent, setOutlookRecent] = useState({});          // disease -> recorded counts behind the severity of an outlook month

  const [explanationData, setExplanationData] = useState(null);
  const [explanationError, setExplanationError] = useState(null);

  // 3. Load the stored forecasts of the assigned district (all months) and pick the latest month that has one
  const fetchOverviewRecords = useCallback(async () => {
    if (!assignedDistrict) return;
    setLoading(true);
    setApiError(null);
    try {
      const response = await listForecastRecords({ district: assignedDistrict, limit: 200 });
      const official = selectOfficialRecords(response?.records || response || []);
      const available = [...new Map(official.map((r) => {
        const period = { year: r.target_year ?? r.targetYear, month: r.target_month ?? r.targetMonth };
        return [`${period.year}-${period.month}`, period];
      })).values()].sort((a, b) => (b.year - a.year) || (b.month - a.month));
      // The month after the forecast month is offered too, when its seasonal outlook exists.
      const target = getDefaultTargetPeriod();
      const outlookMonth = nextPeriod(target.year, target.month);
      if (!available.some((p) => samePeriod(p, outlookMonth))) {
        const outlookResult = await loadOutlooks({ year: outlookMonth.year, month: outlookMonth.month, district: assignedDistrict });
        if (['FMD', 'LSD'].some((d) => outlookFor(outlookResult, assignedDistrict, d))) {
          available.unshift({ ...outlookMonth, outlook: true });
        }
      }
      setRecords(official);
      setPeriods(available);
      setSelected((current) => (current && available.some((p) => samePeriod(p, current)) ? current : pickDefaultPeriod(available)));
      setExplanationData(null);
      setExplanationError(null);
    } catch (err) {
      setApiError(err.message || 'Forecasts could not be loaded. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [assignedDistrict]);

  useEffect(() => {
    if (isAccessAllowed) {
      fetchOverviewRecords();
    }
  }, [isAccessAllowed, fetchOverviewRecords]);

  useEffect(() => {
    if (!isAccessAllowed || !selected || !monthHasStarted(selected.year, selected.month)) {
      setLiveObservations({});
      return undefined;
    }
    let active = true;
    Promise.all(['FMD', 'LSD'].map((disease) => loadObservations({ disease, year: selected.year, month: selected.month })
      .then((districts) => [disease, districts]))).then((pairs) => {
      if (active) setLiveObservations(Object.fromEntries(pairs));
    });
    return () => { active = false; };
  }, [isAccessAllowed, selected]);

  // An outlook month has no counts of its own; its severity follows the two months before it, like the forecast cards.
  useEffect(() => {
    if (!isAccessAllowed || !selected?.outlook) {
      setOutlookRecent({});
      return undefined;
    }
    const first = prevPeriod(selected);
    const second = prevPeriod(first);
    const now = new Date();
    const months = [first, second].filter((m) => monthHasStarted(m.year, m.month, now));
    let active = true;
    Promise.all(['FMD', 'LSD'].map(async (disease) => {
      const lists = await Promise.all(months.map(async (m) => {
        const districts = await loadObservations({ disease, year: m.year, month: m.month });
        const isCurrent = m.year === now.getFullYear() && m.month === now.getMonth() + 1;
        return { label: `${periodLabel(m.year, m.month)}${isCurrent ? ' so far' : ''}`, observation: districts[assignedDistrict] };
      }));
      return [disease, lists];
    })).then((pairs) => { if (active) setOutlookRecent(Object.fromEntries(pairs)); });
    return () => { active = false; };
  }, [isAccessAllowed, selected, assignedDistrict]);

  useEffect(() => {
    let active = true;
    loadSeverityHistory().then((history) => { if (active) setSeverityHistory(history); });
    return () => { active = false; };
  }, []);

  // 4. The outlook is for the month after the one on screen (or the default next month when nothing is issued yet)
  useEffect(() => {
    if (!isAccessAllowed || loading) return undefined;
    const target = selected ? (selected.outlook ? selected : null) : getDefaultTargetPeriod();
    let active = true;
    if (target) {
      loadOutlooks({ year: target.year, month: target.month, district: assignedDistrict }).then((result) => {
        if (active) {
          setOutlooks(result);
          setOutlookPeriod(target);
        }
      });
    } else {
      setOutlooks(NO_OUTLOOK);
      setOutlookPeriod(null);
    }
    if (selected) {
      loadOutlooks({ year: selected.year, month: selected.month, district: assignedDistrict }).then((result) => {
        if (active) setEarlierOutlooks(result.source === 'stored' ? result : NO_OUTLOOK);
      });
    } else {
      setEarlierOutlooks(NO_OUTLOOK);
    }
    return () => { active = false; };
  }, [isAccessAllowed, loading, selected, assignedDistrict]);

  if (!isAccessAllowed) {
    return (
      <AccessContextUnavailable
        reason={
          validation.reason ||
          'VETERINARY_OFFICER role with valid DISTRICT or PROVINCE scopeLevel and an assigned district is required.'
        }
      />
    );
  }

  const handleExplainForecast = async (diseaseCode, record) => {
    if (!record) return;
    if (isV2Record(record)) {
      // v2 records store the exact contributions used; no live recomputation needed.
      setExplanationError(null);
      setExplanationData(storedExplanation(record));
      return;
    }
    // Records from the earlier (v1) forecasting version carry no stored explanation, and recomputing one
    // with the old model would show a number that differs from the official record. Say so instead.
    setExplanationData(null);
    setExplanationError(
      'This forecast was issued by an earlier version of the forecasting system and has no stored explanation. ' +
      'Newer forecasts include a full feature breakdown.'
    );
  };

  const recordFor = (disease) => (selected
    ? records.find((r) => r.disease === disease
      && (r.target_year ?? r.targetYear) === selected.year
      && (r.target_month ?? r.targetMonth) === selected.month) || null
    : null);

  // Recent months first (up to three months before the forecast month, plus the outlook month); older or stray months are grouped apart.
  const renderPeriodOptions = () => {
    const target = getDefaultTargetPeriod();
    const isRecent = (p) => p.outlook || (periodKey(p) <= periodKey(target) && periodKey(p) >= periodKey(target) - 3);
    const option = (p) => (
      <option key={`${p.year}-${p.month}`} value={`${p.year}-${p.month}`} className="bg-surface-container text-on-surface">
        {periodLabel(p.year, p.month)}{p.outlook ? ' (outlook)' : ''}
      </option>
    );
    const recent = periods.filter(isRecent);
    const other = periods.filter((p) => !isRecent(p));
    return (
      <>
        {recent.map(option)}
        {other.length > 0 && <optgroup label="Other months">{other.map(option)}</optgroup>}
      </>
    );
  };

  const diseaseTitle = { FMD: 'Foot-and-Mouth Disease (FMD)', LSD: 'Lumpy Skin Disease (LSD)' };

  const renderDiseaseCard = (diseaseCode, record) => {
    if (!record) return null;           // no empty "No forecast" cards
    const plain = describeRiskPlain(record, assignedDistrict, record.target_month);
    const chance = formatChance(record.probability ?? (record.probability_pct != null ? record.probability_pct / 100 : undefined));
    const range = formatLikelyRange(record);
    const previous = isV2Record(record) ? record.previous_month_observation : null;
    const [prevYear, prevMonthNumber] = String(previous?.period || '').split('-').map(Number);
    const now = new Date();
    const isCurrentMonth = record.target_year === now.getFullYear() && record.target_month === now.getMonth() + 1;
    const recent = [
      ...(monthHasStarted(record.target_year, record.target_month)
        ? [{ label: `${periodLabel(record.target_year, record.target_month)}${isCurrentMonth ? ' so far' : ''}`, observation: liveObservations[diseaseCode]?.[assignedDistrict] }]
        : []),
      ...(previous && prevYear && prevMonthNumber ? [{ label: periodLabel(prevYear, prevMonthNumber), observation: previous }] : []),
    ];

    return (
      <article
        key={diseaseCode}
        aria-labelledby={`card-${diseaseCode.toLowerCase()}-heading`}
        className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-xl space-y-4"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">
                {diseaseCode === 'FMD' ? 'coronavirus' : 'vaccines'}
              </span>
              <h3 id={`card-${diseaseCode.toLowerCase()}-heading`} className="text-lg font-bold text-on-surface">
                {diseaseTitle[diseaseCode]}
              </h3>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <RiskReasonBulb record={record} district={assignedDistrict} />
            <span
              className={`px-3 py-1.5 rounded-xl border text-xs font-extrabold tracking-wide ${plain.class}`}
              aria-label={`Risk level: ${plain.label}`}
            >
              {plain.label}
            </span>
          </div>
        </div>

        <div>
          <span className="text-xs text-on-surface-variant block">Chance of an outbreak in {monthName(record.target_month)}</span>
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-3xl font-extrabold text-on-surface">{chance}</span>
            {range && <span className="text-sm text-on-surface-variant">{range}</span>}
          </div>
        </div>

        {plain.sentence && <p className="text-sm text-on-surface leading-relaxed">{plain.sentence}</p>}
        <SeverityPanel recent={recent} entry={severityFor(severityHistory, diseaseCode, assignedDistrict)} />

        <ForecastDetails
          record={record}
          district={assignedDistrict}
          chance={formatProbability(record.probability_pct ?? record.predicted_probability)}
          earlierOutlook={earlierOutlooks.source === 'stored' ? outlookFor(earlierOutlooks, assignedDistrict, diseaseCode) : null}
          onExplain={() => handleExplainForecast(diseaseCode, record)}
        />
      </article>
    );
  };

  const fmdRecord = recordFor('FMD');
  const lsdRecord = recordFor('LSD');
  const hasForecast = Boolean(fmdRecord || lsdRecord);
  const outlookDiseases = ['FMD', 'LSD'].filter((d) => outlookFor(outlooks, assignedDistrict, d));
  const outlookMonthName = outlookPeriod ? periodLabel(outlookPeriod.year, outlookPeriod.month) : '';

  const outlookSection = !hasForecast && outlookDiseases.length > 0 && (
    <section aria-labelledby="next-month-outlook-heading" className="space-y-3">
      <div>
        <h2 id="next-month-outlook-heading" className="text-lg font-bold text-on-surface">
          {`Outlook for ${outlookMonthName}`}
        </h2>
        <p className="text-xs text-on-surface-variant">{OUTLOOK_NOTE}</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {outlookDiseases.map((disease) => (
          <OutlookCard
            key={disease}
            title={diseaseTitle[disease]}
            outlook={outlookFor(outlooks, assignedDistrict, disease)}
            preview={outlooks.source === 'preview'}
            severityEntry={severityFor(severityHistory, disease, assignedDistrict)}
            recent={outlookRecent[disease] || []}
          />
        ))}
      </div>
    </section>
  );

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-on-surface">
      {/* Page Header */}
      <header className="bg-surface-container p-6 rounded-2xl border border-outline-variant/30 shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-primary tracking-tight">
              Disease Risk Forecast
            </h1>
            <p className="text-sm text-on-surface-variant">
              {assignedDistrict} District{selected ? ` · ${periodLabel(selected.year, selected.month)}` : ''}
            </p>
          </div>

          {periods.length > 0 && (
            <div className="flex items-center gap-1.5 bg-surface-container-high px-3 py-1.5 rounded-xl border border-outline-variant/40 w-fit">
              <label htmlFor="vet-month-select" className="text-xs text-on-surface-variant font-medium">Month:</label>
              <select
                id="vet-month-select"
                value={selected ? `${selected.year}-${selected.month}` : ''}
                onChange={(e) => {
                  const [year, month] = e.target.value.split('-').map(Number);
                  setSelected(periods.find((p) => p.year === year && p.month === month) || { year, month });
                  setExplanationData(null);
                  setExplanationError(null);
                }}
                className="bg-transparent text-xs text-on-surface font-semibold focus:outline-none"
              >
                {renderPeriodOptions()}
              </select>
            </div>
          )}
        </div>
      </header>

      <div role="status" aria-live="polite" className="sr-only">
        {loading && 'Loading forecasts…'}
      </div>

      {apiError && (
        <div role="alert" className="p-4 bg-error-container/20 border border-error/30 rounded-xl text-error text-sm flex items-center gap-3">
          <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
            error
          </span>
          <span>{apiError}</span>
        </div>
      )}

      {loading ? (
        <div role="status" className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-pulse motion-reduce:animate-none">
          <div className="h-64 rounded-2xl bg-surface-container border border-outline-variant/30"></div>
          <div className="h-64 rounded-2xl bg-surface-container border border-outline-variant/30"></div>
        </div>
      ) : (
        <>
          {hasForecast && (
            <section aria-labelledby="latest-forecast-cards-heading" className="space-y-4">
              <h2 id="latest-forecast-cards-heading" className="sr-only">Forecast for {periodLabel(selected.year, selected.month)}</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {renderDiseaseCard('FMD', fmdRecord)}
                {renderDiseaseCard('LSD', lsdRecord)}
              </div>
            </section>
          )}
          {outlookSection}
          {!hasForecast && outlookDiseases.length === 0 && !apiError && (
            <p className="text-sm text-on-surface-variant">
              Forecasts for {assignedDistrict} District will appear here as soon as they are issued.
            </p>
          )}
        </>
      )}

      {/* Feature Contribution Explanation Block */}
      {explanationError && (
        <div role="alert" className="p-4 bg-error-container/20 border border-error/30 rounded-xl text-error text-sm flex items-center gap-3">
          <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
            error
          </span>
          <span>{explanationError}</span>
        </div>
      )}

      {explanationData && explanationData.explanation_info && (
        <section className="p-6 rounded-2xl bg-surface-container-high border border-outline-variant/40 shadow-xl space-y-5 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="flex items-center gap-3">
             <span className="material-symbols-outlined text-primary text-3xl" aria-hidden="true">psychology</span>
             <div>
               <h3 className="text-lg font-bold text-on-surface">Feature Contribution Breakdown — {explanationData.disease}</h3>
               <p className="text-xs text-on-surface-variant font-medium">
                 Linear log-odds contributions ({explanationData.explanation_info.method || 'Log-Odds Decomposition'}). Not SHAP values.
                 {!String(explanationData.explanation_info.method || '').includes('stored') &&
                   ' Recomputed by the live model, so values may differ from the stored record if inputs have changed.'}
               </p>
             </div>
          </div>
          <p className="text-xs text-on-surface-variant max-w-3xl">
             {explanationData.explanation_info.notes || explanationData.explanation_info.baseline_description}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Risk Increasing */}
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 space-y-3">
              <h4 className="text-sm font-semibold text-rose-300 flex items-center gap-2">
                <span className="material-symbols-outlined text-base">trending_up</span>
                Top Risk Increasing Drivers
              </h4>
              <ul className="space-y-3">
                {explanationData.explanation_info.top_risk_increasing?.map((f, i) => (
                  <li key={i} className="flex flex-col gap-1 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="text-on-surface font-semibold">{FEATURE_LABELS[f.display_label] || f.display_label}</span>
                      <span className="font-mono text-rose-300 font-bold">+{f.contribution_log_odds.toFixed(2)}</span>
                    </div>
                    <div className="w-full bg-rose-950 rounded-full h-1.5 overflow-hidden">
                      <div className="bg-rose-500 h-1.5 rounded-full" style={{ width: `${Math.min((f.contribution_log_odds / 2) * 100, 100)}%` }}></div>
                    </div>
                  </li>
                ))}
                {(!explanationData.explanation_info.top_risk_increasing || explanationData.explanation_info.top_risk_increasing.length === 0) && (
                   <li className="text-xs text-on-surface-variant">No significant increasing drivers identified.</li>
                )}
              </ul>
            </div>

            {/* Risk Decreasing */}
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 space-y-3">
              <h4 className="text-sm font-semibold text-emerald-300 flex items-center gap-2">
                <span className="material-symbols-outlined text-base">trending_down</span>
                Top Risk Decreasing Drivers
              </h4>
              <ul className="space-y-3">
                {explanationData.explanation_info.top_risk_decreasing?.map((f, i) => (
                  <li key={i} className="flex flex-col gap-1 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="text-on-surface font-semibold">{FEATURE_LABELS[f.display_label] || f.display_label}</span>
                      <span className="font-mono text-emerald-300 font-bold">{f.contribution_log_odds.toFixed(2)}</span>
                    </div>
                    <div className="w-full bg-emerald-950 rounded-full h-1.5 overflow-hidden flex justify-end">
                      <div className="bg-emerald-500 h-1.5 rounded-full" style={{ width: `${Math.min((Math.abs(f.contribution_log_odds) / 2) * 100, 100)}%` }}></div>
                    </div>
                  </li>
                ))}
                {(!explanationData.explanation_info.top_risk_decreasing || explanationData.explanation_info.top_risk_decreasing.length === 0) && (
                   <li className="text-xs text-on-surface-variant">No significant decreasing drivers identified.</li>
                )}
              </ul>
            </div>
          </div>
        </section>
      )}

      {explanationData && !explanationData.explanation_info && explanationData.disease === 'LSD' && (
         <section className="p-6 rounded-2xl bg-surface-container-high border border-outline-variant/40 shadow-xl space-y-5 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="flex items-center gap-3">
             <span className="material-symbols-outlined text-primary text-3xl" aria-hidden="true">psychology</span>
             <div>
               <h3 className="text-lg font-bold text-on-surface">Model Diagnostics — LSD</h3>
               <p className="text-xs text-on-surface-variant font-medium">Verified Operational Status</p>
             </div>
          </div>
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
             <p className="text-sm text-amber-300">{explanationData.disclaimer || 'LSD Explainability is strictly constrained. Model does not validate active outbreak severity.'}</p>
          </div>
         </section>
      )}

      <p className="text-xs text-on-surface-variant text-center">
        Early-warning estimates from past records and recent data. They are not a diagnosis; confirm suspected cases in the field.
      </p>
    </div>
  );
}

VeterinaryForecastOverview.propTypes = {
  viewerContext: PropTypes.object,
  referenceDate: PropTypes.instanceOf(Date),
};
