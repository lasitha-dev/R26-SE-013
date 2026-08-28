import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  SCOPE_LEVELS,
  validateViewerContext,
  getAuthorizedDistricts,
} from '../../contracts/viewerContext.js';
import { AccessContextUnavailable } from '../AccessContextUnavailable.jsx';
import { listForecastRecords } from '../../services/riskForecastingWorkflowApi.js';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function getMonthNameFallback(monthNum) {
  if (monthNum >= 1 && monthNum <= 12) {
    return MONTH_NAMES[monthNum - 1];
  }
  return 'N/A';
}

function getRiskBadge(riskLevel) {
  const norm = (riskLevel || '').toUpperCase();
  switch (norm) {
    case 'HIGH':
      return { label: 'HIGH RISK', class: 'bg-rose-500/20 text-rose-300 border-rose-500/40' };
    case 'MEDIUM':
      return { label: 'MEDIUM RISK', class: 'bg-amber-500/20 text-amber-300 border-amber-500/40' };
    case 'LOW':
      return { label: 'LOW RISK', class: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' };
    default:
      return { label: norm || 'UNKNOWN', class: 'bg-surface-container-high text-on-surface-variant border-outline-variant/40' };
  }
}

/**
 * DAPH Official District Forecasts Component
 *
 * Read-only consumer of genuine persisted Forecast Decision Records.
 */
export function DaphDistrictForecasts({ viewerContext }) {
  const validation = validateViewerContext(viewerContext);
  const isDaphRole =
    validation.valid && validation.normalizedContext.role === ROLES.DAPH_OFFICIAL;

  const scopeLevel = isDaphRole ? validation.normalizedContext.authorization.scopeLevel : null;
  const isAllowedScope =
    scopeLevel === SCOPE_LEVELS.DISTRICT ||
    scopeLevel === SCOPE_LEVELS.PROVINCE ||
    scopeLevel === SCOPE_LEVELS.NATIONAL;

  const authorizedDistricts = useMemo(() => isDaphRole ? getAuthorizedDistricts(viewerContext) : [], [isDaphRole, viewerContext]);
  const hasAuthorizedDistricts = authorizedDistricts.length > 0;
  const isAccessAllowed = Boolean(isDaphRole && isAllowedScope && hasAuthorizedDistricts);

  const isNational =
    scopeLevel === SCOPE_LEVELS.NATIONAL ||
    authorizedDistricts.includes('ALL_DISTRICTS');

  const [allRecords, setAllRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [selectedDisease, setSelectedDisease] = useState('ALL');
  const [selectedDistrict, setSelectedDistrict] = useState('ALL');
  const [selectedYear, setSelectedYear] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState(null);

  const abortControllerRef = useRef(null);

  const fetchData = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const recordsRes = await listForecastRecords({ limit: 200 }, { signal: controller.signal });
      if (controller.signal.aborted) return;

      const fetchedRecords = recordsRes?.records || [];
      // If national scope, retain all records; otherwise filter by explicit authorized districts
      const authRecords = isNational
        ? fetchedRecords
        : fetchedRecords.filter(r => authorizedDistricts.includes(r.district));

      setAllRecords(authRecords);
      setLoading(false);
    } catch (err) {
      if (controller.signal.aborted) return;
      if (err.name !== 'AbortError') {
        setError('District forecast records could not be loaded. Please try again.');
      }
      setLoading(false);
    }
  }, [authorizedDistricts]);

  useEffect(() => {
    if (isAccessAllowed) {
      fetchData();
    }
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [isAccessAllowed, fetchData]);

  const availableDistricts = useMemo(() => {
    if (isNational && allRecords.length > 0) {
      const dists = new Set(allRecords.map(r => r.district));
      return Array.from(dists).sort();
    }
    return authorizedDistricts;
  }, [allRecords, isNational, authorizedDistricts]);

  const availableYears = useMemo(() => {
    const years = new Set(allRecords.map(r => r.target_year));
    return Array.from(years).sort((a, b) => b - a);
  }, [allRecords]);

  const availableMonths = useMemo(() => {
    if (selectedYear === null) return [];
    const months = new Set(allRecords.filter(r => r.target_year === selectedYear).map(r => r.target_month));
    return Array.from(months).sort((a, b) => a - b);
  }, [allRecords, selectedYear]);

  // Initial Filter State setting (find latest period on load if unselected)
  useEffect(() => {
    if (allRecords.length > 0 && selectedYear === null && selectedMonth === null) {
      let latest = allRecords[0];
      for (let i = 1; i < allRecords.length; i++) {
        const r = allRecords[i];
        if (r.target_year > latest.target_year) {
          latest = r;
        } else if (r.target_year === latest.target_year && r.target_month > latest.target_month) {
          latest = r;
        }
      }
      setSelectedYear(latest.target_year);
      setSelectedMonth(latest.target_month);
    }
  }, [allRecords, selectedYear, selectedMonth]);

  const handleReset = () => {
    setSelectedDisease('ALL');
    setSelectedDistrict('ALL');
    if (allRecords.length > 0) {
      let latest = allRecords[0];
      for (let i = 1; i < allRecords.length; i++) {
        const r = allRecords[i];
        if (r.target_year > latest.target_year) {
          latest = r;
        } else if (r.target_year === latest.target_year && r.target_month > latest.target_month) {
          latest = r;
        }
      }
      setSelectedYear(latest.target_year);
      setSelectedMonth(latest.target_month);
    } else {
      setSelectedYear(null);
      setSelectedMonth(null);
    }
  };

  const handleYearChange = (year) => {
    const y = year === '' ? null : Number(year);
    setSelectedYear(y);
    if (y !== null) {
      const monthsForNewYear = new Set(allRecords.filter(r => r.target_year === y).map(r => r.target_month));
      if (selectedMonth !== null && !monthsForNewYear.has(selectedMonth)) {
        setSelectedMonth(null);
      }
    } else {
      setSelectedMonth(null);
    }
  };

  const displayRecords = useMemo(() => {
    return allRecords.filter(r => {
      const matchDisease = selectedDisease === 'ALL' || r.disease === selectedDisease;
      const matchDistrict = selectedDistrict === 'ALL' || r.district === selectedDistrict;
      const matchYear = selectedYear === null || r.target_year === selectedYear;
      const matchMonth = selectedMonth === null || r.target_month === selectedMonth;
      return matchDisease && matchDistrict && matchYear && matchMonth;
    }).sort((a, b) => b.probability - a.probability);
  }, [allRecords, selectedDisease, selectedDistrict, selectedYear, selectedMonth]);

  if (!isAccessAllowed) {
    return (
      <AccessContextUnavailable
        reason={
          validation.reason ||
          'DAPH_OFFICIAL role with valid scopeLevel and explicit authorized districts required.'
        }
      />
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-on-surface">
      {/* Header */}
      <header className="bg-surface-container p-6 rounded-2xl border border-outline-variant/30 shadow-xl space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-primary tracking-tight">
              Departmental District Forecasts
            </h1>
            <p className="text-sm text-on-surface-variant">
              Department of Animal Production &amp; Health (DAPH) — Risk Forecasting Analytics
            </p>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-container-high rounded-full border border-outline-variant/40 text-xs text-on-surface-variant w-fit">
              <span className="material-symbols-outlined text-primary text-sm" aria-hidden="true">
                query_stats
              </span>
              <span>
                Scope:{' '}
                <span className="font-semibold text-primary uppercase tracking-wide">
                  {scopeLevel}
                </span>
              </span>
            </div>
            <button
              type="button"
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-on-surface text-xs font-medium border border-outline-variant/40 transition disabled:opacity-50"
            >
              <span className={`material-symbols-outlined text-sm ${loading ? 'animate-spin' : ''}`} aria-hidden="true">refresh</span>
              Refresh
            </button>
          </div>
        </div>

        <p className="text-xs text-on-surface-variant leading-relaxed max-w-4xl">
          Epidemiological decision-support risk predictions for authorized Sri Lankan administrative areas.
        </p>
      </header>

      {/* Authorized Forecast Scope Section */}
      <section aria-labelledby="daph-forecast-scope-heading" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-3">
        <div className="flex items-center justify-between">
          <h2 id="daph-forecast-scope-heading" className="text-base font-semibold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-lg" aria-hidden="true">
              travel_explore
            </span>
            <span>Authorized forecast scope</span>
          </h2>
          <span className="text-xs text-on-surface-variant">
            {isNational ? 'All districts \u2014 National scope' : `${authorizedDistricts.length} ${authorizedDistricts.length === 1 ? 'district' : 'districts'} authorized`}
          </span>
        </div>

        <div className="flex flex-wrap gap-2 pt-1">
          {isNational ? (
            <span
              className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface border border-outline-variant/40 text-xs font-medium tracking-wide flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-xs text-primary" aria-hidden="true">
                public
              </span>
              <span>All districts \u2014 National scope</span>
            </span>
          ) : (
            authorizedDistricts.map((dst) => (
              <span
                key={dst}
                className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface border border-outline-variant/40 text-xs font-medium tracking-wide flex items-center gap-1.5"
              >
                <span className="material-symbols-outlined text-xs text-primary" aria-hidden="true">
                  location_on
                </span>
                <span>{dst} District</span>
              </span>
            ))
          )}
        </div>
      </section>

      {/* Controls Form */}
      <section className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-xl flex flex-col gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="flex flex-col space-y-1">
            <label htmlFor="daph-disease-select" className="text-xs font-medium text-on-surface-variant">
              Disease
            </label>
            <select
              id="daph-disease-select"
              value={selectedDisease}
              onChange={(e) => setSelectedDisease(e.target.value)}
              disabled={loading}
              className="bg-surface-container-high text-on-surface border border-outline-variant/40 text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400"
            >
              <option value="ALL">All Diseases</option>
              <option value="FMD">FMD</option>
              <option value="LSD">LSD</option>
            </select>
          </div>

          <div className="flex flex-col space-y-1">
            <label htmlFor="daph-district-select" className="text-xs font-medium text-on-surface-variant">
              Target district
            </label>
            <select
              id="daph-district-select"
              value={selectedDistrict}
              onChange={(e) => setSelectedDistrict(e.target.value)}
              disabled={loading}
              className="bg-surface-container-high text-on-surface border border-outline-variant/40 text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400"
            >
              <option value="ALL">All authorized districts</option>
              {availableDistricts.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col space-y-1">
            <label htmlFor="daph-year-select" className="text-xs font-medium text-on-surface-variant">
              Forecast year
            </label>
            <select
              id="daph-year-select"
              value={selectedYear ?? ''}
              onChange={(e) => handleYearChange(e.target.value)}
              disabled={loading}
              className="bg-surface-container-high text-on-surface border border-outline-variant/40 text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400"
            >
              <option value="">Any Year</option>
              {availableYears.map((yr) => (
                <option key={yr} value={yr}>
                  {yr}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col space-y-1">
            <label htmlFor="daph-month-select" className="text-xs font-medium text-on-surface-variant">
              Forecast month
            </label>
            <select
              id="daph-month-select"
              value={selectedMonth ?? ''}
              onChange={(e) => setSelectedMonth(e.target.value === '' ? null : Number(e.target.value))}
              disabled={loading || selectedYear === null}
              className="bg-surface-container-high text-on-surface border border-outline-variant/40 text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:opacity-50"
            >
              <option value="">Any Month</option>
              {availableMonths.map((m) => (
                <option key={m} value={m}>
                  {getMonthNameFallback(m)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={handleReset}
            disabled={loading}
            className="px-4 py-2 bg-surface-container-highest text-on-surface hover:brightness-110 disabled:opacity-50 font-medium text-xs rounded-lg min-h-[36px] focus:outline-none transition-all"
          >
            Reset Filters
          </button>
        </div>
      </section>

      {/* Accessible Status Messages */}
      {error && (
        <div role="alert" className="p-4 bg-error-container/20 border border-error/30 rounded-xl text-error text-sm flex items-center gap-3">
          <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
            error
          </span>
          <span>{error}</span>
        </div>
      )}

      {/* Loading State */}
      {loading && !error && (
        <div role="status" className="p-8 rounded-2xl bg-surface-container border border-outline-variant/30 space-y-4 animate-pulse motion-reduce:animate-none">
          <div className="h-6 w-1/3 bg-surface-container-high rounded"></div>
          <div className="h-24 w-full bg-surface-container-high rounded"></div>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && displayRecords.length === 0 && (
        <div className="p-8 text-center rounded-2xl bg-surface-container border border-outline-variant/30 space-y-3">
          <span className="material-symbols-outlined text-4xl text-on-surface-variant opacity-50" aria-hidden="true">
            inbox
          </span>
          <p className="text-on-surface font-medium">No saved district forecast records are available for the selected criteria.</p>
          <p className="text-sm text-on-surface-variant">A Veterinary Officer must generate and save an official forecast before it appears here.</p>
        </div>
      )}

      {/* Results Display */}
      {!loading && !error && displayRecords.length > 0 && (
        <div className="grid grid-cols-1 gap-4">
          {displayRecords.map(r => {
            const badge = getRiskBadge(r.risk_level);
            return (
              <div key={r.forecast_id} className="p-5 rounded-xl bg-surface-container border border-outline-variant/30 shadow flex flex-col md:flex-row gap-6">
                <div className="flex-1 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-lg text-on-surface">{r.district} District &middot; {r.disease}</h3>
                    <span className={`px-2.5 py-1 rounded-lg border text-xs font-bold ${badge.class}`}>
                      {badge.label}
                    </span>
                  </div>
                  <div className="flex gap-4 items-baseline">
                    <div className="text-3xl font-extrabold text-on-surface">
                      {typeof r.probability_pct === 'number' ? r.probability_pct.toFixed(1) : (r.probability_pct ?? 'N/A')}{r.probability_pct !== null && r.probability_pct !== undefined ? '%' : ''}
                    </div>
                    <div className="text-sm text-on-surface-variant">
                      Target: {getMonthNameFallback(r.target_month)} {r.target_year ?? 'N/A'}
                    </div>
                  </div>
                </div>

                <div className="flex-1 grid grid-cols-2 gap-4 text-sm">
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-on-surface-variant block">Predicted Severity</span>
                    <span className="text-on-surface font-medium">{r.predicted_severity ?? 'N/A'}</span>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-on-surface-variant block">Record Status</span>
                    <span className="text-on-surface font-medium">{r.status ?? 'N/A'}</span>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-on-surface-variant block">Fallback Applied</span>
                    <span className="text-on-surface font-medium">{r.fallback_applied ? 'Yes' : 'No'}</span>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-on-surface-variant block">Generated</span>
                    <span className="text-on-surface font-medium">{r.generated_at ? new Date(r.generated_at).toLocaleString() : 'N/A'}</span>
                  </div>
                  <div className="space-y-1 col-span-2">
                    <span className="text-xs font-medium text-on-surface-variant block">Data Provenance</span>
                    <span className="text-on-surface font-medium">
                      {r.fallback_applied ? 'YES (Fallback Proxy)' : 'NO (Exact Period)'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Scientific & Operational Boundaries Notice */}
      <section
        aria-labelledby="daph-scientific-boundaries-heading"
        className="p-6 rounded-2xl bg-surface-container-low border border-outline-variant/30 text-on-surface space-y-3"
      >
        <div className="flex items-center gap-2 text-on-surface font-semibold text-sm">
          <span className="material-symbols-outlined text-amber-400 text-lg" aria-hidden="true">
            health_and_safety
          </span>
          <h2 id="daph-scientific-boundaries-heading">Scientific &amp; Epidemiological Boundaries</h2>
        </div>
        <p className="text-xs text-on-surface-variant leading-relaxed">
          These results are epidemiological risk forecasts and are not diagnoses or laboratory confirmation of disease. Disease risk forecasts are district-level early-warning estimates. They do not confirm disease on an individual farm, nor do they constitute an official outbreak alert. Clinical diagnosis requires authorized veterinary field investigation or laboratory confirmation.
        </p>
      </section>

      {/* Footer */}
      <footer className="p-4 bg-surface-container-low/60 rounded-xl border border-outline-variant/30 text-center text-xs text-on-surface-variant">
        <p>
          Departmental Decision Support — Department of Animal Production &amp; Health (DAPH), Sri Lanka.
        </p>
      </footer>
    </div>
  );
}

DaphDistrictForecasts.propTypes = {
  viewerContext: PropTypes.object,
};
