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
  createForecastRecord,
} from '../../services/riskForecastingWorkflowApi.js';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

/**
 * Calculates next calendar period (month/year) from reference date.
 */
export function getNextTargetPeriod(referenceDate = new Date()) {
  const currentYear = referenceDate.getFullYear();
  const currentMonth = referenceDate.getMonth() + 1; // 1-indexed (1-12)

  if (currentMonth === 12) {
    return { targetYear: currentYear + 1, targetMonth: 1 };
  }
  return { targetYear: currentYear, targetMonth: currentMonth + 1 };
}

/**
 * Deterministically sorts stored records to select the latest one.
 * Priority: target_year DESC, target_month DESC, generated_at DESC.
 */
export function getLatestRecord(records = []) {
  if (!Array.isArray(records) || records.length === 0) {
    return null;
  }
  const sorted = [...records].sort((a, b) => {
    const yA = a.target_year ?? a.targetYear ?? 0;
    const yB = b.target_year ?? b.targetYear ?? 0;
    if (yB !== yA) return yB - yA;

    const mA = a.target_month ?? a.targetMonth ?? 0;
    const mB = b.target_month ?? b.targetMonth ?? 0;
    if (mB !== mA) return mB - mA;

    const timeA = a.generated_at ? new Date(a.generated_at).getTime() : 0;
    const timeB = b.generated_at ? new Date(b.generated_at).getTime() : 0;
    return timeB - timeA;
  });
  return sorted[0];
}

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

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [genNotice, setGenNotice] = useState(null); // { type: 'success'|'warning'|'error', text: '' }

  // 3. Load latest stored records for assigned district
  const fetchOverviewRecords = useCallback(async () => {
    if (!assignedDistrict) return;
    setLoading(true);
    setApiError(null);

    try {
      const [fmdRes, lsdRes] = await Promise.allSettled([
        listForecastRecords({ disease: 'FMD', district: assignedDistrict, limit: 50 }),
        listForecastRecords({ disease: 'LSD', district: assignedDistrict, limit: 50 }),
      ]);

      if (fmdRes.status === 'fulfilled') {
        const records = fmdRes.value?.records || fmdRes.value || [];
        setFmdRecord(getLatestRecord(records));
      }

      if (lsdRes.status === 'fulfilled') {
        const records = lsdRes.value?.records || lsdRes.value || [];
        setLsdRecord(getLatestRecord(records));
      }

      if (fmdRes.status === 'rejected' && lsdRes.status === 'rejected') {
        setApiError(fmdRes.reason?.message || lsdRes.reason?.message || 'Failed to load official forecast records.');
      }
    } catch (err) {
      setApiError(err.message || 'An unexpected error occurred loading forecast overview.');
    } finally {
      setLoading(false);
    }
  }, [assignedDistrict]);

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

  // Calculate next target period
  const { targetYear, targetMonth } = getNextTargetPeriod(referenceDate);
  const isYearSupported = targetYear <= 2030;

  // 4. Generate next-month official forecast handler
  const handleGenerateNextMonth = async () => {
    if (generating || !isYearSupported) return;
    setGenerating(true);
    setGenNotice(null);

    const fmdKey = `${actorId}_${assignedDistrict}_FMD_${targetYear}_${targetMonth}_overview_gen`;
    const lsdKey = `${actorId}_${assignedDistrict}_LSD_${targetYear}_${targetMonth}_overview_gen`;

    const [fmdResult, lsdResult] = await Promise.allSettled([
      createForecastRecord({
        disease: 'FMD',
        district: assignedDistrict,
        year: targetYear,
        month: targetMonth,
        trigger_type: 'MANUAL',
        generated_by: actorId,
        idempotency_key: fmdKey,
      }),
      createForecastRecord({
        disease: 'LSD',
        district: assignedDistrict,
        year: targetYear,
        month: targetMonth,
        trigger_type: 'MANUAL',
        generated_by: actorId,
        idempotency_key: lsdKey,
      }),
    ]);

    const fmdOk = fmdResult.status === 'fulfilled';
    const lsdOk = lsdResult.status === 'fulfilled';

    if (fmdOk && lsdOk) {
      setFmdRecord(fmdResult.value);
      setLsdRecord(lsdResult.value);
      setGenNotice({
        type: 'success',
        text: `Successfully generated official forecasts for ${MONTH_NAMES[targetMonth - 1]} ${targetYear} (FMD: ${fmdResult.value.forecast_id}, LSD: ${lsdResult.value.forecast_id}).`,
      });
    } else if (fmdOk || lsdOk) {
      if (fmdOk) setFmdRecord(fmdResult.value);
      if (lsdOk) setLsdRecord(lsdResult.value);
      const okRecord = fmdOk ? fmdResult.value : lsdResult.value;
      const failedDisease = fmdOk ? 'LSD' : 'FMD';
      setGenNotice({
        type: 'warning',
        text: `Generated ${okRecord.disease} forecast (${okRecord.forecast_id}). ${failedDisease} generation failed.`,
      });
    } else {
      const errMsg = fmdResult.reason?.message || lsdResult.reason?.message || 'Generation failed.';
      setGenNotice({
        type: 'error',
        text: `Failed to generate official forecasts: ${errMsg}`,
      });
    }

    setGenerating(false);
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
    const hasDataQualityWarning = record.fallback_applied || (record.data_quality && record.data_quality !== 'EXACT');

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

          {/* Fallback Warning Callout */}
          {hasDataQualityWarning && (
            <div
              role="region"
              aria-label="Data Quality Notice"
              className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs text-amber-300 space-y-1"
            >
              <div className="flex items-center gap-1.5 font-bold">
                <span className="material-symbols-outlined text-sm" aria-hidden="true">
                  warning
                </span>
                <span>Proxy / Historical Input Data Applied</span>
              </div>
              <p className="text-[11px] text-amber-300/90 leading-relaxed">
                Data quality: {record.data_quality || 'PROXY'}. Historical or spatial proxy metrics were used due to sparse primary surveillance inputs.
              </p>
            </div>
          )}

          {/* Record Metadata Details */}
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs border-t border-outline-variant/30 pt-3">
            <div>
              <dt className="text-on-surface-variant">Record ID:</dt>
              <dd className="font-mono text-on-surface font-semibold truncate">{record.forecast_id}</dd>
            </div>
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
      <header className="bg-surface-container p-6 rounded-2xl border border-outline-variant/30 shadow-xl space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-primary tracking-tight">
              Veterinary Forecast Overview
            </h1>
            <p className="text-sm text-on-surface-variant">
              Latest Official Forecast Decision Records — {assignedDistrict} District
            </p>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-container-high rounded-full border border-outline-variant/40 text-xs text-on-surface-variant w-fit">
            <span className="material-symbols-outlined text-primary text-sm" aria-hidden="true">
              location_on
            </span>
            <span>
              Assigned District:{' '}
              <span className="font-semibold text-primary uppercase tracking-wide">
                {assignedDistrict}
              </span>
            </span>
          </div>
        </div>
      </header>

      {/* Live Region for Screen Readers */}
      <div role="status" aria-live="polite" className="sr-only">
        {loading && 'Loading official forecast decision records…'}
        {generating && 'Generating next-month official forecast records…'}
        {genNotice && genNotice.text}
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

      {genNotice && (
        <div
          role={genNotice.type === 'error' ? 'alert' : 'status'}
          className={`p-4 rounded-xl text-sm flex items-center gap-3 border ${
            genNotice.type === 'error'
              ? 'bg-error-container/20 border-error/30 text-error'
              : genNotice.type === 'warning'
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
              : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
          }`}
        >
          <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
            {genNotice.type === 'error' ? 'error' : genNotice.type === 'warning' ? 'warning' : 'check_circle'}
          </span>
          <span>{genNotice.text}</span>
        </div>
      )}

      {/* Generation Bar */}
      <section
        aria-labelledby="generate-next-period-heading"
        className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg flex flex-col md:flex-row md:items-center justify-between gap-4"
      >
        <div className="space-y-1">
          <h2 id="generate-next-period-heading" className="text-base font-semibold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-lg" aria-hidden="true">
              auto_awesome
            </span>
            <span>Next-Month Official Forecast Generation</span>
          </h2>
          <p className="text-xs text-on-surface-variant">
            Target Period: <strong className="text-on-surface">{MONTH_NAMES[targetMonth - 1]} {targetYear}</strong> ({assignedDistrict} District)
          </p>
        </div>

        {isYearSupported ? (
          <button
            type="button"
            onClick={handleGenerateNextMonth}
            disabled={generating || loading}
            className="px-5 py-2.5 bg-primary-container text-on-primary hover:brightness-110 disabled:opacity-50 font-semibold text-sm rounded-xl min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400 transition-all shrink-0 flex items-center justify-center gap-2"
          >
            <span className="material-symbols-outlined text-sm" aria-hidden="true">
              {generating ? 'sync' : 'bolt'}
            </span>
            <span>{generating ? 'Generating Official Forecasts…' : 'Generate Next-Month Official Forecasts'}</span>
          </button>
        ) : (
          <div role="status" className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs text-amber-300">
            Target year {targetYear} exceeds supported forecast range (up to 2030).
          </div>
        )}
      </section>

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

      {/* Scientific & Diagnostic Disclaimer */}
      <section
        aria-labelledby="overview-disclaimer-heading"
        className="p-6 rounded-2xl bg-surface-container-low border border-outline-variant/30 text-on-surface space-y-3"
      >
        <div className="flex items-center gap-2 text-on-surface font-semibold text-sm">
          <span className="material-symbols-outlined text-amber-400 text-lg" aria-hidden="true">
            biomedical
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
  referenceDate: PropTypes.instanceOf(Date),
};
