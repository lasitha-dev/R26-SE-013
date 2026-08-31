import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  SCOPE_LEVELS,
  validateViewerContext,
  getAuthorizedDistricts,
} from '../../contracts/viewerContext.js';
import { AccessContextUnavailable } from '../AccessContextUnavailable.jsx';
import {
  listForecastRecords,
} from '../../services/riskForecastingWorkflowApi.js';
import { fetchAuthorizedDiseaseForecasts } from '../../services/demoForecastingApi.js';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

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

function getRiskBadge(riskLevel) {
  const norm = (riskLevel || '').toUpperCase();
  switch (norm) {
    case 'HIGH':
      return { label: 'HIGH', class: 'bg-rose-500/20 text-rose-300 border-rose-500/40' };
    case 'MEDIUM':
      return { label: 'MEDIUM', class: 'bg-amber-500/20 text-amber-300 border-amber-500/40' };
    case 'LOW':
      return { label: 'LOW', class: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' };
    default:
      return { label: norm || 'UNKNOWN', class: 'bg-surface-container-high text-on-surface-variant border-outline-variant/40' };
  }
}

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

function formatIsoDate(isoStr) {
  if (!isoStr) return 'Not available';
  try {
    const dt = new Date(isoStr);
    return isNaN(dt.getTime()) ? isoStr : dt.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
  } catch (_) {
    return isoStr;
  }
}

/**
 * Veterinary Forecast Overview Component.
 *
 * Displays latest official stored FMD & LSD ForecastDecisionRecords for the assigned district,
 * and provides next-month generation capabilities.
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
  const actorId = validation.valid ? validation.normalizedContext.userId : 'vet_officer_01';

  // 2. Component State
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(null);
  const [fmdRecord, setFmdRecord] = useState(null);
  const [lsdRecord, setLsdRecord] = useState(null);

  const [selectedYear, setSelectedYear] = useState(2025);
  const [selectedMonth, setSelectedMonth] = useState(1);

  const [explanationData, setExplanationData] = useState(null);
  const [explainingDisease, setExplainingDisease] = useState(null);
  const [explanationError, setExplanationError] = useState(null);

  // 3. Load latest stored records for assigned district
  const fetchOverviewRecords = useCallback(async () => {
    if (!assignedDistrict) return;
    setLoading(true);
    setApiError(null);

    try {
      const [fmdRes, lsdRes] = await Promise.allSettled([
        listForecastRecords({ disease: 'FMD', district: assignedDistrict, target_year: selectedYear, target_month: selectedMonth, limit: 50 }),
        listForecastRecords({ disease: 'LSD', district: assignedDistrict, target_year: selectedYear, target_month: selectedMonth, limit: 50 }),
      ]);

      let foundFmd = null;
      let foundLsd = null;

      if (fmdRes.status === 'fulfilled') {
        const records = fmdRes.value?.records || fmdRes.value || [];
        foundFmd = records.find(r => (r.target_year ?? r.targetYear) === Number(selectedYear) && (r.target_month ?? r.targetMonth) === Number(selectedMonth)) || null;
      }

      if (lsdRes.status === 'fulfilled') {
        const records = lsdRes.value?.records || lsdRes.value || [];
        foundLsd = records.find(r => (r.target_year ?? r.targetYear) === Number(selectedYear) && (r.target_month ?? r.targetMonth) === Number(selectedMonth)) || null;
      }

      setFmdRecord(foundFmd);
      setLsdRecord(foundLsd);

      if (fmdRes.status === 'rejected' && lsdRes.status === 'rejected') {
        setApiError(fmdRes.reason?.message || lsdRes.reason?.message || 'Failed to load official forecast records.');
      }
      
      // Clear previous explanation data when the selected period changes
      setExplanationData(null);
      setExplanationError(null);
    } catch (err) {
      setApiError(err.message || 'An unexpected error occurred loading forecast overview.');
    } finally {
      setLoading(false);
    }
  }, [assignedDistrict, selectedYear, selectedMonth]);

  useEffect(() => {
    if (isAccessAllowed) {
      fetchOverviewRecords();
    }
  }, [isAccessAllowed, fetchOverviewRecords]);

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
    setExplainingDisease(diseaseCode);
    setExplanationError(null);
    setExplanationData(null);

    try {
      // Live API call to the actual prediction endpoint for SHAP explainability
      const API_BASE = import.meta.env?.VITE_API_URL || 'http://localhost:8000';
      const endpoint = `${API_BASE}/api/v1/risk-forecasting/predict/${diseaseCode.toLowerCase()}`;
      
      const payload = {
        district: assignedDistrict,
        year: record.target_year || record.targetYear || selectedYear,
        month: record.target_month || record.targetMonth || selectedMonth
      };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error(`Failed to calculate live explainability (Status: ${res.status})`);
      }

      const data = await res.json();
      setExplanationData(data);
    } catch (err) {
      setExplanationError(err.message || 'Unable to generate SHAP breakdown at this moment.');
    } finally {
      setExplainingDisease(null);
    }
  };

  const renderDiseaseCard = (diseaseName, diseaseCode, record) => {
    if (!record) {
      return (
        <article
          aria-labelledby={`empty-${diseaseCode.toLowerCase()}-heading`}
          className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">
                {diseaseCode === 'FMD' ? 'coronavirus' : 'vaccines'}
              </span>
              <h3 id={`empty-${diseaseCode.toLowerCase()}-heading`} className="text-base font-semibold text-on-surface">
                {diseaseName}
              </h3>
            </div>
            <span className="px-2.5 py-1 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/30 text-xs font-semibold">
              No Forecast
            </span>
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed">
            No official stored forecast decision record exists for {diseaseCode} in {assignedDistrict} District.
          </p>
        </article>
      );
    }

    const badge = getRiskBadge(record.risk_level);
    const targetMonthName = record.target_month ? MONTH_NAMES[record.target_month - 1] : 'Unknown';


    return (
      <article
        aria-labelledby={`card-${diseaseCode.toLowerCase()}-heading`}
        className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-xl space-y-5 flex flex-col justify-between"
      >
        <div className="space-y-4">
          {/* Header & Risk Badge */}
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">
                  {diseaseCode === 'FMD' ? 'coronavirus' : 'vaccines'}
                </span>
                <h3 id={`card-${diseaseCode.toLowerCase()}-heading`} className="text-lg font-bold text-on-surface">
                  {diseaseName}
                </h3>
              </div>
              <p className="text-xs text-on-surface-variant font-medium">
                {assignedDistrict} District — Target: {targetMonthName} {record.target_year}
              </p>
            </div>

            <span
              className={`px-3 py-1.5 rounded-xl border text-xs font-extrabold tracking-wide shrink-0 ${badge.class}`}
              aria-label={`Risk Level: ${badge.label}`}
            >
              {badge.label} RISK
            </span>
          </div>

          {/* Probability & Severity Grid */}
          <div className="grid grid-cols-2 gap-4 p-4 rounded-xl bg-surface-container-high/60 border border-outline-variant/40">
            <div>
              <span className="text-[11px] font-medium text-on-surface-variant block uppercase tracking-wider">
                Risk Probability
              </span>
              <span className="text-2xl font-extrabold text-on-surface">
                {formatProbability(record.probability_pct ?? record.predicted_probability)}
              </span>
            </div>
            <div>
              <span className="text-[11px] font-medium text-on-surface-variant block uppercase tracking-wider">
                Predicted Severity
              </span>
              <span className="text-sm font-semibold text-on-surface mt-1 block">
                {record.predicted_severity || 'Not available'}
              </span>
            </div>
          </div>

          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs border-t border-outline-variant/30 pt-3">
            <div>
              <dt className="text-on-surface-variant">Status:</dt>
              <dd className="font-semibold text-primary">{record.status || 'GENERATED'}</dd>
            </div>
            <div>
              <dt className="text-on-surface-variant">Model Variant:</dt>
              <dd className="text-on-surface">{record.model_variant || 'Standard'}</dd>
            </div>
            <div>
              <dt className="text-on-surface-variant">Generated At:</dt>
              <dd className="text-on-surface">{formatIsoDate(record.generated_at)}</dd>
            </div>
            <div>
              <dt className="text-on-surface-variant">Data Period:</dt>
              <dd className="text-on-surface">
                {record.source_year && record.source_month
                  ? `${MONTH_NAMES[record.source_month - 1]} ${record.source_year}`
                  : 'Not available'}
              </dd>
            </div>
            <div>
              <dt className="text-on-surface-variant">Proxy Data Age:</dt>
              <dd className="text-on-surface">
                {record.proxy_data_age_days !== undefined && record.proxy_data_age_days !== null
                  ? `${record.proxy_data_age_days} days`
                  : 'Not available'}
              </dd>
            </div>
          </dl>

          {/* Explainability Button */}
          <div className="pt-4 border-t border-outline-variant/30 flex justify-end">
            <button
              onClick={() => handleExplainForecast(diseaseCode, record)}
              disabled={explainingDisease === diseaseCode || explainingDisease !== null}
              className="flex items-center gap-2 px-4 py-2 bg-primary/10 hover:bg-primary/20 text-primary rounded-xl text-xs font-bold tracking-wide transition-colors disabled:opacity-50"
            >
              <span className={`material-symbols-outlined text-sm ${explainingDisease === diseaseCode ? 'animate-spin' : ''}`}>
                {explainingDisease === diseaseCode ? 'sync' : 'psychology'}
              </span>
              {explainingDisease === diseaseCode ? 'CALCULATING...' : 'EXPLAIN FORECAST'}
            </button>
          </div>
        </div>

        <p className="text-[11px] text-on-surface-variant/70 italic border-t border-outline-variant/20 pt-2">
          Statistical epidemiological early-warning decision record. Does not constitute laboratory confirmation.
        </p>
      </article>
    );
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-on-surface">
      {/* Page Header */}
      <header className="bg-surface-container p-6 rounded-2xl border border-outline-variant/30 shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-primary tracking-tight">
              Veterinary Forecast Overview
            </h1>
            <p className="text-sm text-on-surface-variant">
              Official Risk Forecast Decision Records — {assignedDistrict} District ({MONTH_NAMES[selectedMonth - 1]} {selectedYear})
            </p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1.5 bg-surface-container-high px-3 py-1.5 rounded-xl border border-outline-variant/40">
              <label htmlFor="vet-year-input" className="text-xs text-on-surface-variant font-medium">Year:</label>
              <input
                id="vet-year-input"
                type="number"
                min={2017}
                max={2030}
                value={selectedYear}
                onChange={(e) => setSelectedYear(Number(e.target.value))}
                className="bg-transparent text-xs text-on-surface font-semibold w-16 focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-1.5 bg-surface-container-high px-3 py-1.5 rounded-xl border border-outline-variant/40">
              <label htmlFor="vet-month-select" className="text-xs text-on-surface-variant font-medium">Month:</label>
              <select
                id="vet-month-select"
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(Number(e.target.value))}
                className="bg-transparent text-xs text-on-surface font-semibold focus:outline-none"
              >
                {MONTH_NAMES.map((mName, idx) => (
                  <option key={mName} value={idx + 1} className="bg-surface-container text-on-surface">
                    {idx + 1} — {mName}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-container-high rounded-full border border-outline-variant/40 text-xs text-on-surface-variant w-fit">
              <span className="material-symbols-outlined text-primary text-sm" aria-hidden="true">
                location_on
              </span>
              <span>
                District:{' '}
                <span className="font-semibold text-primary uppercase tracking-wide">
                  {assignedDistrict}
                </span>
              </span>
            </div>
          </div>
        </div>
      </header>

      <div role="status" aria-live="polite" className="sr-only">
        {loading && 'Loading official forecast decision records…'}
      </div>

      {/* Notifications / Alerts */}
      {apiError && (
        <div role="alert" className="p-4 bg-error-container/20 border border-error/30 rounded-xl text-error text-sm flex items-center gap-3">
          <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
            error
          </span>
          <span>{apiError}</span>
        </div>
      )}



      {/* Loading Skeleton */}
      {loading ? (
        <div role="status" className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-pulse motion-reduce:animate-none">
          <div className="h-64 rounded-2xl bg-surface-container border border-outline-variant/30"></div>
          <div className="h-64 rounded-2xl bg-surface-container border border-outline-variant/30"></div>
        </div>
      ) : (
        /* Overview Cards Grid */
        <section aria-labelledby="latest-forecast-cards-heading" className="space-y-4">
          <h2 id="latest-forecast-cards-heading" className="sr-only">
            Latest Official Forecast Cards
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {renderDiseaseCard('Foot-and-Mouth Disease (FMD)', 'FMD', fmdRecord)}
            {renderDiseaseCard('Lumpy Skin Disease (LSD)', 'LSD', lsdRecord)}
          </div>
        </section>
      )}

      {/* SHAP Explanation Block */}
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
               <h3 className="text-lg font-bold text-on-surface">SHAP Explainability Breakdown — {explanationData.disease}</h3>
               <p className="text-xs text-on-surface-variant font-medium">Live model feature contributions ({explanationData.explanation_info.method || 'Log-Odds Decomposition'})</p>
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

      {/* Scientific & Diagnostic Disclaimer */}
      <section
        aria-labelledby="overview-disclaimer-heading"
        className="p-6 rounded-2xl bg-surface-container-low border border-outline-variant/30 text-on-surface space-y-3"
      >
        <div className="flex items-center gap-2 text-on-surface font-semibold text-sm">
          <span className="material-symbols-outlined text-amber-400 text-lg" aria-hidden="true">
            health_and_safety
          </span>
          <h2 id="overview-disclaimer-heading">Epidemiological &amp; Diagnostic Guardrails</h2>
        </div>
        <p className="text-xs text-on-surface-variant leading-relaxed">
          Forecast decision records are immutable statistical early-warning estimates generated for veterinary surveillance support. They do not constitute clinical diagnosis, laboratory confirmation, or an active quarantine order. All operational disease response decisions must be validated through authorized field inspection.
        </p>
      </section>
    </div>
  );
}

VeterinaryForecastOverview.propTypes = {
  viewerContext: PropTypes.object,
};
