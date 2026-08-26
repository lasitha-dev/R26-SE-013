import React, { useState, useEffect, useContext } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  SCOPE_LEVELS,
  validateViewerContext,
  getAuthorizedDistricts,
} from '../../contracts/viewerContext.js';
import { AccessContextUnavailable } from '../AccessContextUnavailable.jsx';
import { DemoForecastingAuthContext } from '../../context/DemoForecastingAuthContext.jsx';
import { useAuthorizedDemoForecast } from '../../hooks/useAuthorizedDemoForecast.js';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const VALID_YEARS = Array.from({ length: 14 }, (_, i) => 2017 + i); // 2017-2030

const WORKSPACE_CARDS = [
  {
    id: 'daph-period-heading',
    title: 'Forecast Period',
    icon: 'calendar_clock',
    status: 'Integration blocked',
    description:
      'Year and month target period selection will be enabled after secure DAPH server-side authorization integration.',
  },
  {
    id: 'daph-fmd-heading',
    title: 'Foot-and-Mouth Disease (FMD)',
    icon: 'coronavirus',
    status: 'Forecast loading blocked',
    description:
      'District-level FMD risk predictions cannot be loaded safely until DAPH backend scope validation is connected.',
  },
  {
    id: 'daph-lsd-heading',
    title: 'Lumpy Skin Disease (LSD)',
    icon: 'vaccines',
    status: 'Forecast loading blocked',
    description:
      'District-level LSD risk predictions cannot be loaded safely until DAPH backend scope validation is connected.',
  },
  {
    id: 'daph-regional-comparison-heading',
    title: 'Regional Comparison',
    icon: 'stacked_bar_chart',
    status: 'Not connected',
    description:
      'Multi-district and provincial risk comparisons will remain strictly restricted to server-authorized jurisdictions.',
  },
];

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
 * Supports both standalone isolated presentation (when demo auth is inactive)
 * and connected protected demo forecasting (when demo auth is active).
 */
export function DaphDistrictForecasts({ viewerContext }) {
  // 1. Access & Fail-Closed Validation
  const validation = validateViewerContext(viewerContext);
  const isDaphRole =
    validation.valid && validation.normalizedContext.role === ROLES.DAPH_OFFICIAL;

  const scopeLevel = isDaphRole ? validation.normalizedContext.authorization.scopeLevel : null;
  const isAllowedScope =
    scopeLevel === SCOPE_LEVELS.DISTRICT ||
    scopeLevel === SCOPE_LEVELS.PROVINCE ||
    scopeLevel === SCOPE_LEVELS.NATIONAL;

  const authorizedDistricts = isDaphRole ? getAuthorizedDistricts(viewerContext) : [];
  const hasAuthorizedDistricts = authorizedDistricts.length > 0;

  const isAccessAllowed = Boolean(isDaphRole && isAllowedScope && hasAuthorizedDistricts);

  // 2. Demo Auth Context & Protected Forecast Hook
  const authContext = useContext(DemoForecastingAuthContext);
  const isDemoActive = Boolean(
    (authContext?.isDemoEnabled || authContext?.demoEnabled) &&
    (authContext?.isDemoAuthenticated || authContext?.status === 'authenticated')
  );

  const {
    status,
    fmdForecast,
    lsdForecast,
    error,
    requestForecast,
  } = useAuthorizedDemoForecast();

  // Form selections
  const [selectedMonth, setSelectedMonth] = useState(1);
  const [selectedYear, setSelectedYear] = useState(2024);
  const [selectedDistrictChoice, setSelectedDistrictChoice] = useState('ALL'); // 'ALL' or specific district string

  // Automatically request initial forecast for all explicit authorized districts on mount in demo mode
  useEffect(() => {
    if (isAccessAllowed && isDemoActive) {
      requestForecast({
        year: 2024,
        targetMonth: 1,
        districts: authorizedDistricts,
      });
    }
  }, [isAccessAllowed, isDemoActive]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // Handle form submission
  const handleSubmit = (e) => {
    e.preventDefault();
    if (status === 'loading') return;

    if (selectedDistrictChoice === 'ALL') {
      requestForecast({
        year: selectedYear,
        targetMonth: selectedMonth,
        districts: authorizedDistricts,
      });
    } else {
      requestForecast({
        year: selectedYear,
        targetMonth: selectedMonth,
        district: selectedDistrictChoice,
      });
    }
  };

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
            {authorizedDistricts.length} {authorizedDistricts.length === 1 ? 'district' : 'districts'} authorized
          </span>
        </div>

        <div className="flex flex-wrap gap-2 pt-1">
          {authorizedDistricts.map((dst) => (
            <span
              key={dst}
              className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface border border-outline-variant/40 text-xs font-medium tracking-wide flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-xs text-primary" aria-hidden="true">
                location_on
              </span>
              <span>{dst} District</span>
            </span>
          ))}
        </div>
      </section>

      {/* UNCONNECTED PRESENTATION (When demo mode is inactive) */}
      {!isDemoActive && (
        <>
          <section
            role="status"
            aria-live="polite"
            aria-labelledby="daph-forecast-integration-heading"
            className="p-6 rounded-2xl bg-surface-container border border-amber-500/30 shadow-xl space-y-2"
          >
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
                <span className="material-symbols-outlined text-2xl" aria-hidden="true">
                  lock_reset
                </span>
              </div>
              <div className="space-y-1.5">
                <h2 id="daph-forecast-integration-heading" className="text-lg font-semibold text-amber-300 tracking-wide">
                  District forecasts are awaiting secure DAPH access integration
                </h2>
                <p className="text-sm text-on-surface-variant leading-relaxed">
                  The forecasting service is available, but DAPH regional authorization is not yet enforced by the backend. Forecast data cannot be loaded safely until server-side scope validation is connected.
                </p>
                <p className="text-xs text-amber-400/90 font-medium">
                  Frontend filtering is presentation-only and must not be treated as operational authorization.
                </p>
              </div>
            </div>
          </section>

          <section aria-labelledby="daph-workspace-heading" className="space-y-4">
            <h2 id="daph-workspace-heading" className="text-xl font-bold text-on-surface tracking-tight">
              Departmental Forecast Workspace
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {WORKSPACE_CARDS.map((card) => (
                <article
                  key={card.id}
                  className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg flex flex-col justify-between space-y-4"
                  aria-labelledby={card.id}
                >
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-lg bg-surface-container-high text-on-surface-variant border border-outline-variant/40">
                          <span className="material-symbols-outlined text-xl" aria-hidden="true">
                            {card.icon}
                          </span>
                        </div>
                        <h3 id={card.id} className="text-base font-semibold text-on-surface">
                          {card.title}
                        </h3>
                      </div>

                      <span className="px-2.5 py-1 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/30 text-xs font-semibold">
                        {card.status}
                      </span>
                    </div>

                    <p className="text-xs text-on-surface-variant leading-relaxed">
                      {card.description}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </>
      )}

      {/* CONNECTED PROTECTED DEMO PRESENTATION */}
      {isDemoActive && (
        <>
          {/* Controls Form */}
          <form onSubmit={handleSubmit} className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-xl flex flex-wrap items-end gap-4">
            <div className="flex flex-col space-y-1">
              <label htmlFor="daph-month-select" className="text-xs font-medium text-on-surface-variant">
                Forecast month
              </label>
              <select
                id="daph-month-select"
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(Number(e.target.value))}
                disabled={status === 'loading'}
                className="bg-surface-container-high text-on-surface border border-outline-variant/40 text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400"
              >
                {MONTH_NAMES.map((name, idx) => (
                  <option key={name} value={idx + 1}>
                    {name}
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
                value={selectedYear}
                onChange={(e) => setSelectedYear(Number(e.target.value))}
                disabled={status === 'loading'}
                className="bg-surface-container-high text-on-surface border border-outline-variant/40 text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400"
              >
                {VALID_YEARS.map((yr) => (
                  <option key={yr} value={yr}>
                    {yr}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col space-y-1">
              <label htmlFor="daph-district-select" className="text-xs font-medium text-on-surface-variant">
                Target district
              </label>
              <select
                id="daph-district-select"
                value={selectedDistrictChoice}
                onChange={(e) => setSelectedDistrictChoice(e.target.value)}
                disabled={status === 'loading'}
                className="bg-surface-container-high text-on-surface border border-outline-variant/40 text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400"
              >
                <option value="ALL">All authorized districts</option>
                {authorizedDistricts.map((d) => (
                  <option key={d} value={d}>
                    {d} District
                  </option>
                ))}
              </select>
            </div>

            <button
              type="submit"
              disabled={status === 'loading'}
              className="px-5 py-2.5 bg-primary-container text-on-primary hover:brightness-110 disabled:opacity-50 font-semibold text-sm rounded-xl min-h-[44px] focus:outline-none focus:ring-2 focus:ring-emerald-400 transition-all"
            >
              {status === 'loading' ? 'Updating forecast…' : 'Update forecast'}
            </button>
          </form>

          {/* Status Live Region */}
          <div role="status" aria-live="polite" className="sr-only">
            {status === 'loading' && 'Fetching DAPH departmental forecasting estimates…'}
            {status === 'forbidden' && 'Access to the requested district is forbidden.'}
            {status === 'error' && error}
            {status === 'success' && 'Departmental forecasts updated successfully.'}
          </div>

          {/* Accessible Status Messages */}
          {status === 'forbidden' && (
            <div role="alert" className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-300 text-sm flex items-center gap-3">
              <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
                lock
              </span>
              <span>{error || 'Forecast access to the requested district is forbidden.'}</span>
            </div>
          )}

          {status === 'error' && (
            <div role="alert" className="p-4 bg-error-container/20 border border-error/30 rounded-xl text-error text-sm flex items-center gap-3">
              <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
                error
              </span>
              <span>{error || 'Forecast service is currently unavailable.'}</span>
            </div>
          )}

          {/* Forecast Output Comparative Tables/Cards */}
          {status === 'loading' && (
            <div role="status" className="p-8 rounded-2xl bg-surface-container border border-outline-variant/30 space-y-4 animate-pulse motion-reduce:animate-none">
              <div className="h-6 w-1/3 bg-surface-container-high rounded"></div>
              <div className="h-24 w-full bg-surface-container-high rounded"></div>
            </div>
          )}

          {status === 'success' && (
            <div className="space-y-8">
              {/* FMD Departmental Comparative Section */}
              <section aria-labelledby="daph-fmd-section-heading" className="space-y-4">
                <h2 id="daph-fmd-section-heading" className="text-lg font-bold text-on-surface flex items-center gap-2">
                  <span className="material-symbols-outlined text-rose-400" aria-hidden="true">coronavirus</span>
                  <span>FMD Departmental Risk Comparisons</span>
                </h2>

                {fmdForecast?.districts && fmdForecast.districts.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {fmdForecast.districts.map((item) => {
                      const badge = getRiskBadge(item.risk_level);
                      return (
                        <div key={item.district} className="p-5 rounded-xl bg-surface-container border border-outline-variant/30 shadow space-y-3">
                          <div className="flex items-center justify-between">
                            <h3 className="font-semibold text-on-surface">{item.district} District</h3>
                            <span className={`px-2.5 py-1 rounded-lg border text-xs font-bold ${badge.class}`}>
                              {badge.label}
                            </span>
                          </div>
                          <div className="text-2xl font-extrabold text-on-surface">
                            {typeof item.probability_pct === 'number' ? item.probability_pct.toFixed(1) : item.probability_pct}%
                          </div>
                          <p className="text-xs text-on-surface-variant">
                            Target: {MONTH_NAMES[selectedMonth - 1]} {selectedYear}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-on-surface-variant italic">No FMD forecast data returned for authorized districts.</p>
                )}
              </section>

              {/* LSD Departmental Comparative Section */}
              <section aria-labelledby="daph-lsd-section-heading" className="space-y-4">
                <h2 id="daph-lsd-section-heading" className="text-lg font-bold text-on-surface flex items-center gap-2">
                  <span className="material-symbols-outlined text-purple-400" aria-hidden="true">vaccines</span>
                  <span>LSD Departmental Risk Comparisons</span>
                </h2>

                {lsdForecast?.districts && lsdForecast.districts.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {lsdForecast.districts.map((item) => {
                      const badge = getRiskBadge(item.risk_level);
                      return (
                        <div key={item.district} className="p-5 rounded-xl bg-surface-container border border-outline-variant/30 shadow space-y-3">
                          <div className="flex items-center justify-between">
                            <h3 className="font-semibold text-on-surface">{item.district} District</h3>
                            <span className={`px-2.5 py-1 rounded-lg border text-xs font-bold ${badge.class}`}>
                              {badge.label}
                            </span>
                          </div>
                          <div className="text-2xl font-extrabold text-on-surface">
                            {typeof item.probability_pct === 'number' ? item.probability_pct.toFixed(1) : item.probability_pct}%
                          </div>
                          <p className="text-xs text-on-surface-variant">
                            Target: {MONTH_NAMES[selectedMonth - 1]} {selectedYear}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-on-surface-variant italic">No LSD forecast data returned for authorized districts.</p>
                )}
              </section>
            </div>
          )}
        </>
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
        <p className="text-xs text-on-surface-variant/80 leading-relaxed">
          Forecast results are generated from existing trained forecasting models and climatological data. Synthetic operational records are strictly isolated and not used as model inputs.
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
