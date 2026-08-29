import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  SCOPE_LEVELS,
  validateViewerContext,
  getAuthorizedDistricts,
} from '../../contracts/viewerContext.js';
import { AccessContextUnavailable } from '../AccessContextUnavailable.jsx';
import { listForecastRecords, listCanonicalDistricts } from '../../services/riskForecastingWorkflowApi.js';

const CANONICAL_DISTRICTS = [
  'Ampara', 'Anuradhapura', 'Badulla', 'Batticaloa', 'Colombo', 'Galle', 'Gampaha',
  'Hambantota', 'Jaffna', 'Kalutara', 'Kandy', 'Kegalle', 'Kilinochchi', 'Kurunegala',
  'Mannar', 'Matale', 'Matara', 'Monaragala', 'Mullaitivu', 'Nuwara Eliya',
  'Polonnaruwa', 'Puttalam', 'Ratnapura', 'Trincomalee', 'Vavuniya'
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
  const [canonicalDistricts, setCanonicalDistricts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [selectedDisease, setSelectedDisease] = useState('ALL');
  const [selectedDistrict, setSelectedDistrict] = useState('ALL');

  const abortControllerRef = useRef(null);

  const TARGET_YEAR = 2025;
  const TARGET_MONTH = 1;

  const fetchData = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const [recordsRes, districtsRes] = await Promise.allSettled([
        listForecastRecords({ limit: 200, target_year: TARGET_YEAR, target_month: TARGET_MONTH }, { signal: controller.signal }),
        listCanonicalDistricts({ signal: controller.signal })
      ]);
      if (controller.signal.aborted) return;

      let fetchedDistricts = CANONICAL_DISTRICTS;
      if (districtsRes.status === 'fulfilled' && districtsRes.value?.districts) {
        fetchedDistricts = districtsRes.value.districts;
      }
      setCanonicalDistricts(fetchedDistricts);

      if (recordsRes.status === 'fulfilled') {
        const fetchedRecords = recordsRes.value?.records || [];
        const filteredRecords = fetchedRecords.filter(r => r.target_year === TARGET_YEAR && r.target_month === TARGET_MONTH);
        const authRecords = isNational
          ? filteredRecords
          : filteredRecords.filter(r => authorizedDistricts.includes(r.district));
        setAllRecords(authRecords);
      } else {
        throw recordsRes.reason;
      }
      setLoading(false);
    } catch (err) {
      if (controller.signal.aborted) return;
      if (err.name !== 'AbortError') {
        setError('District forecast records could not be loaded. Please try again.');
      }
      setLoading(false);
    }
  }, [authorizedDistricts, isNational]);

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
    if (isNational) {
      return canonicalDistricts.length > 0 ? canonicalDistricts : CANONICAL_DISTRICTS;
    }
    return authorizedDistricts;
  }, [canonicalDistricts, isNational, authorizedDistricts]);

  const handleReset = () => {
    setSelectedDisease('ALL');
    setSelectedDistrict('ALL');
  };

  const displayRecords = useMemo(() => {
    return allRecords.filter(r => {
      const matchDisease = selectedDisease === 'ALL' || r.disease === selectedDisease;
      const matchDistrict = selectedDistrict === 'ALL' || r.district === selectedDistrict;
      return matchDisease && matchDistrict;
    }).sort((a, b) => b.probability - a.probability);
  }, [allRecords, selectedDisease, selectedDistrict]);

  const coverageSummary = useMemo(() => {
    if (loading || error) return null;
    const uniqueDistrictsCount = new Set(displayRecords.map(r => r.district)).size;
    const recordCount = displayRecords.length;

    if (selectedDistrict !== 'ALL') {
      if (recordCount > 0) return 'Forecast available for selected district';
      return 'No saved forecast for selected district and period.';
    }
    return `District coverage: ${uniqueDistrictsCount} of ${availableDistricts.length} | Available records: ${recordCount}`;
  }, [displayRecords, selectedDistrict, availableDistricts.length, loading, error]);



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
      <header className="bg-surface-container p-6 rounded-2xl border border-outline-variant/30 shadow-xl space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-primary tracking-tight">
              January 2025 District Disease Risk Outlook
            </h1>
            <p className="text-sm text-on-surface-variant">
              Department of Animal Production &amp; Health (DAPH) — Risk Forecasting Analytics
            </p>
          </div>
          <div className="flex flex-wrap gap-2 mt-3 md:mt-0">
            {authorizedDistricts.map(d => (
              <span key={d} className="px-2 py-1 bg-surface-container-high border border-outline-variant/50 rounded text-xs font-medium text-on-surface-variant">
                {d}
              </span>
            ))}
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
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
      </header >

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
            <option value="ALL">All districts</option>
            {availableDistricts.map((d) => (
              <option key={d} value={d}>
                {d}
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



  {
    loading && !error && (
      <div role="status" className="p-8 rounded-2xl bg-surface-container border border-outline-variant/30 space-y-4 animate-pulse">
        <div className="h-6 w-1/3 bg-surface-container-high rounded"></div>
        <div className="h-24 w-full bg-surface-container-high rounded"></div>
      </div>
    )
  }

  {
    !loading && !error && displayRecords.length === 0 && (
      <div className="p-8 text-center rounded-2xl bg-surface-container border border-outline-variant/30 space-y-3">
        <p className="text-on-surface font-medium">No saved district forecast records are available.</p>
      </div>
    )
  }

  {
    !loading && !error && displayRecords.length > 0 && (
      <div className="grid grid-cols-1 gap-4">
        {displayRecords.map(r => {
          const badge = getRiskBadge(r.risk_level);
          return (
              <div key={r.district+r.disease} className="p-5 rounded-xl bg-surface-container border border-outline-variant/30 shadow flex flex-col md:flex-row gap-6">
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
                    <span className="text-xs font-medium text-on-surface-variant block">Target Period</span>
                    <span className="text-on-surface font-medium">January 2025</span>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-on-surface-variant block">Data Provenance</span>
                    <span className="text-on-surface font-medium">{r.fallback_applied ? 'Proxy Data (Fallback)' : 'Exact Period'}</span>
                  </div>
                </div>
              </div>
    );
  })
}
        </div >
      )}

      {error && (
        <div role="alert" className="p-6 rounded-xl bg-rose-950/30 border border-rose-900/50 text-rose-300">
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined shrink-0 mt-0.5">error</span>
            <div className="space-y-1">
              <h3 className="font-semibold">Error</h3>
              <p className="text-sm">District forecast records could not be loaded.</p>
            </div>
          </div>
        </div>
      )}

      <section aria-labelledby="scientific-guardrails-heading" className="p-6 rounded-2xl bg-surface-container-low border border-outline-variant/30 text-on-surface space-y-3">
        <div className="flex items-center gap-2 text-on-surface font-semibold text-sm">
          <span aria-hidden="true" className="material-symbols-outlined text-amber-400 text-lg">health_and_safety</span>
          <h2 id="scientific-guardrails-heading">Epidemiological & Diagnostic Guardrails</h2>
        </div>
        <p className="text-xs text-on-surface-variant leading-relaxed">
          Forecast decision records are immutable statistical early-warning estimates generated for veterinary surveillance support. They do not constitute clinical diagnosis, laboratory confirmation, or an active quarantine order. All operational disease response decisions must be validated through authorized field inspection.
        </p>
      </section>
    </div >
  );
}

DaphDistrictForecasts.propTypes = {
  viewerContext: PropTypes.object,
};
