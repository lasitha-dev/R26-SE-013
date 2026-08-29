import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  SCOPE_LEVELS,
  validateViewerContext,
  getAuthorizedDistricts,
} from '../../contracts/viewerContext.js';
import { AccessContextUnavailable } from '../AccessContextUnavailable.jsx';

const API_BASE = import.meta.env?.VITE_API_URL || '';

const SRI_LANKA_DISTRICTS = [
  'Ampara', 'Anuradhapura', 'Badulla', 'Batticaloa', 'Colombo',
  'Galle', 'Gampaha', 'Hambantota', 'Jaffna', 'Kalutara',
  'Kandy', 'Kegalle', 'Kilinochchi', 'Kurunegala', 'Mannar',
  'Matale', 'Matara', 'Monaragala', 'Mullaitivu', 'Nuwara Eliya',
  'Polonnaruwa', 'Puttalam', 'Ratnapura', 'Trincomalee', 'Vavuniya'
];

const DISEASES = ['FMD', 'LSD'];

function getYearMonth(date = new Date()) {
  return { year: date.getFullYear(), month: date.getMonth() + 1 };
}

export function DaphOutbreakMonitor({ viewerContext }) {
  const validation = validateViewerContext(viewerContext);
  const isDaphRole = validation.valid && validation.normalizedContext.role === ROLES.DAPH_OFFICIAL;

  const scopeLevel = isDaphRole ? validation.normalizedContext.authorization.scopeLevel : null;
  const isAllowedScope =
    scopeLevel === SCOPE_LEVELS.DISTRICT ||
    scopeLevel === SCOPE_LEVELS.PROVINCE ||
    scopeLevel === SCOPE_LEVELS.NATIONAL;

  const authorizedDistricts = isDaphRole ? getAuthorizedDistricts(viewerContext) : [];
  const hasAuthorizedDistricts = authorizedDistricts.length > 0;

  const isAccessAllowed = Boolean(isDaphRole && isAllowedScope && hasAuthorizedDistricts);

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

  const { year, month } = getYearMonth();
  const [selectedDisease, setSelectedDisease] = useState('FMD');
  const [selectedYear, setSelectedYear] = useState(year);
  const [selectedMonth, setSelectedMonth] = useState(month);
  const [districtStatuses, setDistrictStatuses] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchOutbreakStatuses = useCallback(async () => {
    setLoading(true);
    setError(null);
    const token = localStorage.getItem('token');
    const statuses = {};
    const districtsToQuery = scopeLevel === SCOPE_LEVELS.NATIONAL
      ? SRI_LANKA_DISTRICTS
      : authorizedDistricts;

    try {
      await Promise.all(
        districtsToQuery.map(async (district) => {
          try {
            const res = await fetch(
              `${API_BASE}/api/v1/risk-forecasting/outbreak-status/${selectedDisease}/${encodeURIComponent(district)}/${selectedYear}/${selectedMonth}`,
              {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
              }
            );
            if (res.ok) {
              const data = await res.json();
              statuses[district] = data;
            } else {
              statuses[district] = {
                district,
                disease: selectedDisease,
                year: selectedYear,
                month: selectedMonth,
                outbreak_status: 0.0,
                cases_count: 0,
                deaths_count: 0,
                error: true,
              };
            }
          } catch {
            statuses[district] = {
              district,
              disease: selectedDisease,
              year: selectedYear,
              month: selectedMonth,
              outbreak_status: 0.0,
              cases_count: 0,
              deaths_count: 0,
              error: true,
            };
          }
        })
      );
      setDistrictStatuses(statuses);
    } catch (err) {
      setError('Failed to load outbreak status data.');
    } finally {
      setLoading(false);
    }
  }, [selectedDisease, selectedYear, selectedMonth, authorizedDistricts, scopeLevel]);

  useEffect(() => {
    fetchOutbreakStatuses();
  }, [fetchOutbreakStatuses]);

  const activeDistricts = Object.values(districtStatuses).filter(
    (d) => d.outbreak_status === 1.0
  );
  const quietDistricts = Object.values(districtStatuses).filter(
    (d) => d.outbreak_status === 0.0
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-on-surface">District Outbreak Monitor</h1>
          <p className="text-sm text-on-surface-variant mt-1">
            Real-time district-wise outbreak status for {selectedDisease} — {selectedMonth}/{selectedYear}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={selectedDisease}
            onChange={(e) => setSelectedDisease(e.target.value)}
            className="px-3 py-2 rounded-lg bg-surface-container-high text-on-surface border border-outline-variant"
          >
            {DISEASES.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(Number(e.target.value))}
            className="px-3 py-2 rounded-lg bg-surface-container-high text-on-surface border border-outline-variant"
          >
            {Array.from({ length: 5 }, (_, i) => year - i).map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(Number(e.target.value))}
            className="px-3 py-2 rounded-lg bg-surface-container-high text-on-surface border border-outline-variant"
          >
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>
                {new Date(2000, m - 1, 1).toLocaleString('en-US', { month: 'long' })}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center p-8" role="status">
          <div className="w-8 h-8 rounded-full border-4 border-dashed border-primary/50 animate-spin-slow"></div>
          <span className="sr-only">Loading outbreak status...</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-error-container text-on-error-container">
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          {activeDistricts.length > 0 && (
            <div className="p-4 rounded-xl bg-error-container text-on-error-container flex items-center gap-3">
              <span className="material-symbols-outlined">warning</span>
              <div>
                <p className="font-semibold">{activeDistricts.length} Active Outbreak District(s)</p>
                <p className="text-sm opacity-90">
                  {activeDistricts.map((d) => d.district).join(', ')}
                </p>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.values(districtStatuses).map((status) => (
              <div
                key={status.district}
                className={`p-4 rounded-xl border ${
                  status.outbreak_status === 1.0
                    ? 'bg-error-container border-error text-on-error-container'
                    : 'bg-surface-container border-outline-variant text-on-surface'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold">{status.district}</h3>
                  <span
                    className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                      status.outbreak_status === 1.0
                        ? 'bg-error text-on-error'
                        : 'bg-primary-container text-on-primary-container'
                    }`}
                  >
                    {status.outbreak_status === 1.0 ? 'Active' : 'Quiet'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <p className="text-on-surface-variant">Verified Cases</p>
                    <p className="font-bold text-lg">{status.cases_count}</p>
                  </div>
                  <div>
                    <p className="text-on-surface-variant">{selectedDisease} Deaths</p>
                    <p className="font-bold text-lg">{status.deaths_count}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

DaphOutbreakMonitor.propTypes = {
  viewerContext: PropTypes.object.isRequired,
};
