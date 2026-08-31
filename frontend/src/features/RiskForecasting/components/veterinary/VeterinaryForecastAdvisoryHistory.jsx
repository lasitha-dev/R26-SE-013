import React, { useState, useEffect, useRef, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  validateViewerContext,
} from '../../contracts/viewerContext';
import { AccessContextUnavailable } from '../AccessContextUnavailable';
import {
  listForecastRecords,
  listAdvisories,
  listNotificationBatches,
  listNotificationDeliveries,
} from '../../services/riskForecastingWorkflowApi';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

/**
 * Sanitizes technical error messages to avoid displaying sensitive internal traces,
 * credentials, file paths, or stack frames.
 */
export function sanitizeErrorMessage(
  err,
  fallbackMessage = 'A system error occurred while retrieving historical records. Please try again later.'
) {
  if (!err) return fallbackMessage;
  const raw = typeof err === 'string' ? err : (err && typeof err.message === 'string') ? err.message : '';
  if (!raw || typeof raw !== 'string') return fallbackMessage;

  const sensitivePattern = /(?:Traceback|File\s+"|\bline\s+\d+|\bKeyError:|\bAttributeError:|\bTypeError|\bReferenceError|\bSyntaxError|\bRangeError|\bURIError|\bError:|[a-zA-Z]:[\\\/]|\/(?:home|var|tmp|usr|etc|root)\/|token=|api_key=|password=|Authorization:|Bearer|postgresql:\/\/|mongodb:\/\/|mysql:\/\/|redis:\/\/|\bat\s+\w+|\bloadHistory|\[object\s+Object\])/i;

  if (sensitivePattern.test(raw)) {
    return fallbackMessage;
  }

  return raw;
}

/**
 * VeterinaryForecastAdvisoryHistory
 * Read-only Veterinary Officer workspace for auditing historical forecast decision records,
 * linked farmer advisory records, enqueued simulated notification batches, and per-recipient delivery statuses.
 */
export function VeterinaryForecastAdvisoryHistory({ viewerContext }) {
  // 1. ViewerContext Authorization & Security Validation
  const validation = validateViewerContext(viewerContext);
  const normalizedContext = validation.valid ? validation.normalizedContext : null;
  const role = normalizedContext?.role;
  const authorizedDistricts = normalizedContext?.authorization?.authorizedDistricts || [];
  const authorizedDistrictsKey = authorizedDistricts.join('|');

  // Fail closed if context is invalid or role is not VETERINARY_OFFICER
  if (!validation.valid || role !== ROLES.VETERINARY_OFFICER || authorizedDistricts.length === 0) {
    return (
      <AccessContextUnavailable
        reason="Veterinary Officer authorization with assigned district scope is required to access Forecast & Advisory History."
      />
    );
  }

  // 2. Filter State Management
  const [selectedDistrict, setSelectedDistrict] = useState(authorizedDistricts[0] || '');
  const [selectedDisease, setSelectedDisease] = useState('ALL');
  const [targetYear, setTargetYear] = useState('');
  const [targetMonth, setTargetMonth] = useState('');
  const [recordStatus, setRecordStatus] = useState('ALL');
  const [advisoryStatusFilter, setAdvisoryStatusFilter] = useState('ALL');

  // Pagination State
  const [limit] = useState(10);
  const [offset, setOffset] = useState(0);

  // Data States
  const [forecastRecords, setForecastRecords] = useState([]);
  const [totalRecordsCount, setTotalRecordsCount] = useState(0);
  const [loadingForecasts, setLoadingForecasts] = useState(false);
  const [forecastError, setForecastError] = useState(null);

  // Selected Forecast & Linked Items State
  const [selectedForecastId, setSelectedForecastId] = useState(null);
  const [linkedAdvisories, setLinkedAdvisories] = useState([]);
  const [loadingAdvisories, setLoadingAdvisories] = useState(false);
  const [advisoryError, setAdvisoryError] = useState(null);

  const [selectedAdvisoryId, setSelectedAdvisoryId] = useState(null);
  const [linkedBatches, setLinkedBatches] = useState([]);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [batchError, setBatchError] = useState(null);

  const [selectedBatchId, setSelectedBatchId] = useState(null);
  const [linkedDeliveries, setLinkedDeliveries] = useState([]);
  const [loadingDeliveries, setLoadingDeliveries] = useState(false);
  const [deliveryError, setDeliveryError] = useState(null);

  // Stale request tracking refs
  const forecastReqIdRef = useRef(0);
  const advisoryReqIdRef = useRef(0);
  const batchReqIdRef = useRef(0);
  const deliveryReqIdRef = useRef(0);

  // 3. Fetch Forecast Records
  const fetchForecasts = useCallback(async () => {
    if (!selectedDistrict || !authorizedDistricts.includes(selectedDistrict)) {
      setForecastError('Selected district is not within your authorized scope.');
      return;
    }

    const currentReqId = ++forecastReqIdRef.current;
    setLoadingForecasts(true);
    setForecastError(null);

    try {
      const filters = {
        district: selectedDistrict,
        disease: selectedDisease !== 'ALL' ? selectedDisease : undefined,
        target_year: targetYear ? parseInt(targetYear, 10) : undefined,
        target_month: targetMonth ? parseInt(targetMonth, 10) : undefined,
        status: recordStatus !== 'ALL' ? recordStatus : undefined,
        limit,
        offset,
      };

      const response = await listForecastRecords(filters);
      if (forecastReqIdRef.current !== currentReqId) return;

      const records = response?.records || [];
      // Deterministic sort: target_year DESC, target_month DESC, generated_at DESC
      records.sort((a, b) => {
        if (b.target_year !== a.target_year) return b.target_year - a.target_year;
        if (b.target_month !== a.target_month) return b.target_month - a.target_month;
        return new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime();
      });

      setForecastRecords(records);
      setTotalRecordsCount(response?.total_count ?? records.length);

      setSelectedForecastId((prevId) => {
        if (records.length > 0) {
          if (!prevId || !records.some((r) => r.forecast_id === prevId)) {
            return records[0].forecast_id;
          }
          return prevId;
        }
        return null;
      });
    } catch (err) {
      if (forecastReqIdRef.current !== currentReqId) return;
      setForecastError(sanitizeErrorMessage(err, 'Failed to retrieve forecast decision records.'));
      setForecastRecords([]);
      setTotalRecordsCount(0);
      setSelectedForecastId(null);
    } finally {
      if (forecastReqIdRef.current === currentReqId) {
        setLoadingForecasts(false);
      }
    }
  }, [selectedDistrict, selectedDisease, targetYear, targetMonth, recordStatus, limit, offset, authorizedDistrictsKey]);

  useEffect(() => {
    fetchForecasts();
  }, [fetchForecasts]);

  // 4. Fetch Linked Advisories when Selected Forecast Changes
  const fetchAdvisories = useCallback(async (forecastId) => {
    if (!forecastId) {
      setLinkedAdvisories([]);
      setSelectedAdvisoryId(null);
      return;
    }

    const currentReqId = ++advisoryReqIdRef.current;
    setLoadingAdvisories(true);
    setAdvisoryError(null);

    try {
      const filters = {
        forecast_id: forecastId,
        status: advisoryStatusFilter !== 'ALL' ? advisoryStatusFilter : undefined,
      };

      const response = await listAdvisories(filters);
      if (advisoryReqIdRef.current !== currentReqId) return;

      const advisories = response?.advisories || [];
      // Defensive authorization check: retain advisories matching forecast_id
      const authorizedAdvisories = advisories.filter((adv) => adv.forecast_id === forecastId);
      setLinkedAdvisories(authorizedAdvisories);

      setSelectedAdvisoryId((prevId) => {
        if (authorizedAdvisories.length > 0) {
          if (!prevId || !authorizedAdvisories.some((a) => a.advisory_id === prevId)) {
            return authorizedAdvisories[0].advisory_id;
          }
          return prevId;
        }
        return null;
      });
    } catch (err) {
      if (advisoryReqIdRef.current !== currentReqId) return;
      setAdvisoryError(sanitizeErrorMessage(err, 'Failed to load linked advisories.'));
      setLinkedAdvisories([]);
      setSelectedAdvisoryId(null);
    } finally {
      if (advisoryReqIdRef.current === currentReqId) {
        setLoadingAdvisories(false);
      }
    }
  }, [advisoryStatusFilter]);

  useEffect(() => {
    fetchAdvisories(selectedForecastId);
  }, [selectedForecastId, fetchAdvisories]);

  // 5. Fetch Linked Notification Batches when Selected Advisory Changes
  const fetchBatches = useCallback(async (advisoryId) => {
    if (!advisoryId) {
      setLinkedBatches([]);
      setSelectedBatchId(null);
      return;
    }

    const currentReqId = ++batchReqIdRef.current;
    setLoadingBatches(true);
    setBatchError(null);

    try {
      const response = await listNotificationBatches({ advisory_id: advisoryId });
      if (batchReqIdRef.current !== currentReqId) return;

      const batches = response?.batches || [];
      // Defensive authorization check: retain batches for this advisory
      const authorizedBatches = batches.filter((b) => b.advisory_id === advisoryId);
      setLinkedBatches(authorizedBatches);

      setSelectedBatchId((prevId) => {
        if (authorizedBatches.length > 0) {
          if (!prevId || !authorizedBatches.some((b) => b.batch_id === prevId)) {
            return authorizedBatches[0].batch_id;
          }
          return prevId;
        }
        return null;
      });
    } catch (err) {
      if (batchReqIdRef.current !== currentReqId) return;
      setBatchError(sanitizeErrorMessage(err, 'Failed to load linked notification batches.'));
      setLinkedBatches([]);
      setSelectedBatchId(null);
    } finally {
      if (batchReqIdRef.current === currentReqId) {
        setLoadingBatches(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchBatches(selectedAdvisoryId);
  }, [selectedAdvisoryId, fetchBatches]);

  // 6. Fetch Per-Recipient Deliveries when Selected Batch Changes
  const fetchDeliveries = useCallback(async (batchId) => {
    if (!batchId) {
      setLinkedDeliveries([]);
      return;
    }

    const currentReqId = ++deliveryReqIdRef.current;
    setLoadingDeliveries(true);
    setDeliveryError(null);

    try {
      const response = await listNotificationDeliveries(batchId);
      if (deliveryReqIdRef.current !== currentReqId) return;

      const deliveries = response?.deliveries || [];
      setLinkedDeliveries(deliveries);
    } catch (err) {
      if (deliveryReqIdRef.current !== currentReqId) return;
      setDeliveryError(sanitizeErrorMessage(err, 'Failed to load recipient simulated delivery items.'));
      setLinkedDeliveries([]);
    } finally {
      if (deliveryReqIdRef.current === currentReqId) {
        setLoadingDeliveries(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchDeliveries(selectedBatchId);
  }, [selectedBatchId, fetchDeliveries]);

  // Handle Reset Filters
  const handleResetFilters = () => {
    setSelectedDistrict(authorizedDistricts[0] || '');
    setSelectedDisease('ALL');
    setTargetYear('');
    setTargetMonth('');
    setRecordStatus('ALL');
    setAdvisoryStatusFilter('ALL');
    setOffset(0);
  };

  const selectedForecastRecord = forecastRecords.find((r) => r.forecast_id === selectedForecastId);

  return (
    <div className="w-full min-w-0 space-y-6 text-slate-100">
      {/* Header & Page Title */}
      <header className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-lg backdrop-blur-md space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
              <span className="material-symbols-outlined text-emerald-400 text-3xl" aria-hidden="true">
                history
              </span>
              Forecast &amp; Advisory History
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Auditable read-only history linking official forecast decision records and veterinary advisory records.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-xs font-medium text-emerald-400">
            <span className="material-symbols-outlined text-base">verified_user</span>
            <span>Veterinary Officer Read-Only Audit</span>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="pt-4 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-3">
          {/* Authorized District */}
          <div>
            <label htmlFor="filter-district" className="block text-xs font-semibold text-slate-400 mb-1">
              Authorized District
            </label>
            <select
              id="filter-district"
              aria-label="Authorized District Filter"
              value={selectedDistrict}
              onChange={(e) => {
                setSelectedDistrict(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              {authorizedDistricts.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          {/* Disease Filter */}
          <div>
            <label htmlFor="filter-disease" className="block text-xs font-semibold text-slate-400 mb-1">
              Disease
            </label>
            <select
              id="filter-disease"
              aria-label="Disease Filter"
              value={selectedDisease}
              onChange={(e) => {
                setSelectedDisease(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="ALL">All Diseases</option>
              <option value="FMD">FMD</option>
              <option value="LSD">LSD</option>
            </select>
          </div>

          {/* Target Year */}
          <div>
            <label htmlFor="filter-target-year" className="block text-xs font-semibold text-slate-400 mb-1">
              Target Year
            </label>
            <select
              id="filter-target-year"
              aria-label="Target Year Filter"
              value={targetYear}
              onChange={(e) => {
                setTargetYear(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All Years</option>
              {Array.from({ length: 14 }, (_, i) => 2017 + i).map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>

          {/* Target Month */}
          <div>
            <label htmlFor="filter-target-month" className="block text-xs font-semibold text-slate-400 mb-1">
              Target Month
            </label>
            <select
              id="filter-target-month"
              aria-label="Target Month Filter"
              value={targetMonth}
              onChange={(e) => {
                setTargetMonth(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All Months</option>
              {MONTH_NAMES.map((m, idx) => (
                <option key={m} value={idx + 1}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          {/* Record Status */}
          <div>
            <label htmlFor="filter-record-status" className="block text-xs font-semibold text-slate-400 mb-1">
              Forecast Status
            </label>
            <select
              id="filter-record-status"
              aria-label="Forecast Status Filter"
              value={recordStatus}
              onChange={(e) => {
                setRecordStatus(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="GENERATED">GENERATED</option>
              <option value="AVAILABLE">AVAILABLE</option>
              <option value="REFERENCED">REFERENCED</option>
              <option value="SUPERSEDED">SUPERSEDED</option>
            </select>
          </div>

          {/* Advisory Status Filter */}
          <div>
            <label htmlFor="filter-advisory-status" className="block text-xs font-semibold text-slate-400 mb-1">
              Advisory Status
            </label>
            <select
              id="filter-advisory-status"
              aria-label="Advisory Status Filter"
              value={advisoryStatusFilter}
              onChange={(e) => {
                setAdvisoryStatusFilter(e.target.value);
              }}
              className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="DRAFT">DRAFT</option>
              <option value="REVIEW_READY">REVIEW_READY</option>
              <option value="APPROVED">APPROVED</option>
              <option value="CANCELLED">CANCELLED</option>
            </select>
          </div>

          {/* Reset Filters */}
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleResetFilters}
              className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 font-medium px-3 py-1.5 rounded-lg text-xs transition-colors flex items-center justify-center gap-1 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <span className="material-symbols-outlined text-sm">restart_alt</span>
              Reset Filters
            </button>
          </div>
        </div>
      </header>

      {/* Main Master-Detail Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Master Column: Forecast History List (5 cols) */}
        <section className="lg:col-span-5 bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-md space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <span className="material-symbols-outlined text-emerald-400 text-base">analytics</span>
              Forecast Records ({totalRecordsCount})
            </h3>
            {loadingForecasts && (
              <span role="status" className="text-xs text-emerald-400 flex items-center gap-1">
                <span className="material-symbols-outlined animate-spin text-sm">sync</span>
                Loading...
              </span>
            )}
          </div>

          {/* Error Alert */}
          {forecastError && (
            <div role="alert" className="p-3 bg-red-950/60 border border-red-800/80 rounded-lg text-xs text-red-200 flex items-start gap-2">
              <span className="material-symbols-outlined text-red-400 text-base flex-shrink-0">error</span>
              <span>{forecastError}</span>
            </div>
          )}

          {/* Empty State */}
          {!loadingForecasts && !forecastError && forecastRecords.length === 0 && (
            <div className="p-6 text-center space-y-3 bg-slate-950/40 rounded-lg border border-slate-800/60">
              <span className="material-symbols-outlined text-4xl text-slate-600">find_in_page</span>
              <p className="text-xs text-slate-400">No forecast decision records match the current filters.</p>
              <button
                type="button"
                onClick={handleResetFilters}
                className="text-xs text-emerald-400 hover:text-emerald-300 underline font-medium"
              >
                Reset Filters
              </button>
            </div>
          )}

          {/* Forecast Record Cards */}
          <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
            {forecastRecords.map((record) => {
              const isSelected = record.forecast_id === selectedForecastId;
              const probVal = record.probability_pct ?? (typeof record.probability === 'number' ? record.probability * 100 : null);

              return (
                <div
                  key={record.forecast_id}
                  onClick={() => setSelectedForecastId(record.forecast_id)}
                  aria-current={isSelected ? 'true' : undefined}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setSelectedForecastId(record.forecast_id);
                    }
                  }}
                  className={`p-3.5 rounded-lg border transition-all cursor-pointer text-left space-y-2 ${
                    isSelected
                      ? 'bg-slate-800 border-emerald-500/80 ring-1 ring-emerald-500/50 shadow-md'
                      : 'bg-slate-950/50 border-slate-800 hover:bg-slate-800/50 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold tracking-wide bg-emerald-950/80 border border-emerald-800/80 text-emerald-300">
                      {record.disease}
                    </span>
                    <span className="text-[11px] font-medium text-slate-400">
                      {record.district}
                    </span>
                  </div>

                  <div className="flex items-baseline justify-between text-xs">
                    <span className="font-semibold text-slate-200">
                      Target: {MONTH_NAMES[record.target_month - 1] || record.target_month} {record.target_year}
                    </span>
                    <span className="font-semibold text-slate-300">
                      {probVal !== null ? `${probVal.toFixed(1)}%` : 'N/A'}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <span>
                      Risk:{' '}
                      <strong
                        className={
                          record.risk_level === 'HIGH'
                            ? 'text-red-400 font-semibold'
                            : record.risk_level === 'MEDIUM'
                            ? 'text-amber-400 font-semibold'
                            : record.risk_level === 'LOW'
                            ? 'text-emerald-400 font-semibold'
                            : 'text-slate-400 font-semibold'
                        }
                      >
                        {record.risk_level || 'N/A'}
                      </strong>
                    </span>
                    <span>Status: <strong className="text-slate-300">{record.status}</strong></span>
                  </div>

                  <div className="pt-1 border-t border-slate-800/60 flex items-center justify-between text-[10px] text-slate-500">
                    <span>Gen: {new Date(record.generated_at).toLocaleString()}</span>
                    <span>Quality: {record.data_quality}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination Controls */}
          {totalRecordsCount > limit && (
            <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
              <button
                type="button"
                disabled={offset === 0 || loadingForecasts}
                onClick={() => setOffset(Math.max(0, offset - limit))}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 rounded text-slate-200 transition-colors"
              >
                Previous
              </button>
              <span>
                Page {Math.floor(offset / limit) + 1} of {Math.ceil(totalRecordsCount / limit)}
              </span>
              <button
                type="button"
                disabled={offset + limit >= totalRecordsCount || loadingForecasts}
                onClick={() => setOffset(offset + limit)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 rounded text-slate-200 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </section>

        {/* Detail Column: Selected Forecast, Advisories & Deliveries (7 cols) */}
        <section className="lg:col-span-7 space-y-6">
          {!selectedForecastRecord ? (
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-8 text-center text-slate-400 space-y-3">
              <span className="material-symbols-outlined text-5xl text-slate-600">info</span>
              <p className="text-sm font-medium">Select a forecast decision record from the list to view its complete audit history.</p>
            </div>
          ) : (
            <>
              {/* 1. Selected Forecast Record Detail Card */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-md space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <span className="material-symbols-outlined text-emerald-400">shield</span>
                      Forecast Decision Record
                    </h3>
                    <span className="text-xs text-slate-400 font-mono">ID: {selectedForecastRecord.forecast_id}</span>
                  </div>
                  <span className="px-2.5 py-1 rounded text-xs font-semibold bg-slate-800 border border-slate-700 text-emerald-400">
                    Status: {selectedForecastRecord.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                  <div className="bg-slate-950/60 p-2.5 rounded border border-slate-800">
                    <span className="text-slate-400 block text-[11px]">Disease</span>
                    <strong className="text-slate-100 font-bold text-sm">{selectedForecastRecord.disease}</strong>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded border border-slate-800">
                    <span className="text-slate-400 block text-[11px]">District</span>
                    <strong className="text-slate-100 font-semibold">{selectedForecastRecord.district}</strong>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded border border-slate-800">
                    <span className="text-slate-400 block text-[11px]">Target Period</span>
                    <strong className="text-slate-100 font-semibold">
                      {MONTH_NAMES[selectedForecastRecord.target_month - 1]} {selectedForecastRecord.target_year}
                    </strong>
                  </div>

                  <div className="bg-slate-950/60 p-2.5 rounded border border-slate-800">
                    <span className="text-slate-400 block text-[11px]">Outbreak Probability</span>
                    <strong className="text-emerald-400 font-bold text-sm">
                      {(selectedForecastRecord.probability_pct ?? (typeof selectedForecastRecord.probability === 'number' ? selectedForecastRecord.probability * 100 : null)) !== null
                        ? `${(selectedForecastRecord.probability_pct ?? (selectedForecastRecord.probability * 100)).toFixed(1)}%`
                        : 'N/A'}
                    </strong>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded border border-slate-800">
                    <span className="text-slate-400 block text-[11px]">Risk Level</span>
                    <strong
                      className={
                        selectedForecastRecord.risk_level === 'HIGH'
                          ? 'text-red-400 font-bold text-sm'
                          : selectedForecastRecord.risk_level === 'MEDIUM'
                          ? 'text-amber-400 font-bold text-sm'
                          : selectedForecastRecord.risk_level === 'LOW'
                          ? 'text-emerald-400 font-bold text-sm'
                          : 'text-slate-400 font-bold text-sm'
                      }
                    >
                      {selectedForecastRecord.risk_level || 'N/A'}
                    </strong>
                  </div>
                  <div className="bg-slate-950/60 p-2.5 rounded border border-slate-800">
                    <span className="text-slate-400 block text-[11px]">Predicted Severity</span>
                    <strong className="text-slate-200 font-semibold">
                      {selectedForecastRecord.predicted_severity || 'N/A'}
                    </strong>
                  </div>
                </div>

                {/* Provenance & Scientific Disclaimer */}
                <div className="space-y-2 text-xs pt-2 border-t border-slate-800">
                  <div className="flex flex-wrap items-center justify-between text-slate-400 gap-2 text-[11px]">
                    <span>Model: <strong className="text-slate-300">{selectedForecastRecord.model_variant}</strong></span>
                    <span>Data Quality: <strong className="text-slate-300">{selectedForecastRecord.data_quality}</strong></span>
                    <span>Fallback: <strong className={selectedForecastRecord.fallback_applied ? 'text-amber-400' : 'text-slate-300'}>{selectedForecastRecord.fallback_applied ? 'Yes' : 'No'}</strong></span>
                  </div>

                  <div className="p-2.5 bg-slate-950/80 rounded border border-slate-800/80 text-[11px] text-slate-400 flex items-start gap-2">
                    <span className="material-symbols-outlined text-amber-400 text-sm flex-shrink-0 mt-0.5">info</span>
                    <span>{selectedForecastRecord.disclaimer || 'Scientific decision-support output. Model forecasts do not constitute confirmed clinical diagnoses.'}</span>
                  </div>
                </div>
              </div>

              {/* 2. Linked Advisories Section */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-md space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    <span className="material-symbols-outlined text-emerald-400">campaign</span>
                    Linked Advisory History ({linkedAdvisories.length})
                  </h4>
                  {loadingAdvisories && (
                    <span role="status" className="text-xs text-emerald-400 flex items-center gap-1">
                      <span className="material-symbols-outlined animate-spin text-sm">sync</span>
                      Loading advisories...
                    </span>
                  )}
                </div>

                {advisoryError && (
                  <div role="alert" className="p-3 bg-red-950/60 border border-red-800/80 rounded-lg text-xs text-red-200">
                    {advisoryError}
                  </div>
                )}

                {!loadingAdvisories && !advisoryError && linkedAdvisories.length === 0 && (
                  <div className="p-4 bg-slate-950/40 border border-slate-800/60 rounded-lg text-center text-xs text-slate-400">
                    No advisory created for this forecast.
                  </div>
                )}

                <div className="space-y-3">
                  {linkedAdvisories.map((adv) => {
                    const isAdvSelected = adv.advisory_id === selectedAdvisoryId;
                    return (
                      <div
                        key={adv.advisory_id}
                        onClick={() => setSelectedAdvisoryId(adv.advisory_id)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setSelectedAdvisoryId(adv.advisory_id);
                          }
                        }}
                        className={`p-4 rounded-lg border transition-all cursor-pointer space-y-3 ${
                          isAdvSelected
                            ? 'bg-slate-800/90 border-emerald-500/80 ring-1 ring-emerald-500/40'
                            : 'bg-slate-950/60 border-slate-800 hover:bg-slate-800/40'
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs font-mono text-slate-300 font-semibold">
                            {adv.advisory_id}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 border border-slate-700 text-slate-300">
                              v{adv.version}
                            </span>
                            <span
                              className={`px-2.5 py-0.5 rounded text-[11px] font-bold border ${
                                adv.status === 'APPROVED'
                                  ? 'bg-emerald-950 border-emerald-700 text-emerald-300'
                                  : adv.status === 'CANCELLED'
                                  ? 'bg-red-950 border-red-800 text-red-300'
                                  : 'bg-amber-950 border-amber-800 text-amber-300'
                              }`}
                            >
                              {adv.status === 'APPROVED' ? 'APPROVED (Frozen)' : adv.status}
                            </span>
                          </div>
                        </div>

                        <div className="text-xs space-y-1.5">
                          <p className="font-semibold text-slate-200">{adv.title}</p>
                          <div className="p-2.5 bg-slate-950 rounded border border-slate-800/80 text-slate-300 whitespace-pre-wrap font-sans text-xs">
                            {adv.standard_message}
                          </div>
                          {adv.vet_custom_note && (
                            <div className="p-2.5 bg-emerald-950/30 rounded border border-emerald-800/40 text-emerald-200 text-xs">
                              <strong className="block text-[10px] text-emerald-400 mb-0.5">Vet Custom Advice Note:</strong>
                              {adv.vet_custom_note}
                            </div>
                          )}
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-slate-400 pt-2 border-t border-slate-800/80">
                          <div>Scope: <strong className="text-slate-200">
                            {adv.recipient_scope === 'ALL_ASSIGNED' ? 'All Assigned Farmers' : 
                             adv.recipient_scope === 'DISTRICT_WIDE' ? 'Entire District' : 
                             adv.recipient_scope}
                          </strong></div>
                          <div>Targeted: <strong className="text-slate-200">{adv.recipient_summary?.selected_count ?? 0}</strong></div>
                          <div>Created By: <strong className="text-slate-200" title={adv.created_by}>{adv.created_by ? 'Veterinary Officer (You)' : 'N/A'}</strong></div>
                          <div>Approved By: <strong className="text-slate-200" title={adv.approved_by}>{adv.approved_by ? 'DAPH Official' : 'Pending'}</strong></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 3. Linked Simulated-Delivery History Section */}
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-md space-y-4">
                <div className="flex flex-wrap items-center justify-between border-b border-slate-800 pb-3 gap-2">
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    <span className="material-symbols-outlined text-emerald-400">mark_email_read</span>
                    Simulated Delivery History
                  </h4>
                  {loadingBatches && (
                    <span role="status" className="text-xs text-emerald-400 flex items-center gap-1">
                      <span className="material-symbols-outlined animate-spin text-sm">sync</span>
                      Loading batches...
                    </span>
                  )}
                </div>

                {/* Mandatory Persistent Disclaimer */}
                <div className="p-3 bg-amber-950/40 border border-amber-800/50 rounded-lg text-xs text-amber-200 flex items-start gap-2">
                  <span className="material-symbols-outlined text-amber-400 text-base flex-shrink-0 mt-0.5">info</span>
                  <span>
                    Standalone simulation history only. A successful result confirms mock provider execution; it does not confirm that a farmer received or read a real notification.
                  </span>
                </div>

                {batchError && (
                  <div role="alert" className="p-3 bg-red-950/60 border border-red-800/80 rounded-lg text-xs text-red-200">
                    {batchError}
                  </div>
                )}

                {!loadingBatches && !batchError && linkedBatches.length === 0 && (
                  <div className="p-4 bg-slate-950/40 border border-slate-800/60 rounded-lg text-center text-xs text-slate-400">
                    No notification batches enqueued for this advisory.
                  </div>
                )}

                <div className="space-y-4">
                  {linkedBatches.map((batch) => {
                    const isBatchSelected = batch.batch_id === selectedBatchId;
                    return (
                      <div
                        key={batch.batch_id}
                        onClick={() => setSelectedBatchId(batch.batch_id)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setSelectedBatchId(batch.batch_id);
                          }
                        }}
                        className={`p-4 rounded-lg border transition-all cursor-pointer space-y-3 ${
                          isBatchSelected
                            ? 'bg-slate-800/90 border-emerald-500/80 ring-1 ring-emerald-500/40'
                            : 'bg-slate-950/60 border-slate-800 hover:bg-slate-800/40'
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs font-mono text-slate-300 font-semibold">
                            Batch ID: {batch.batch_id}
                          </span>
                          <span
                            className={`px-2.5 py-0.5 rounded text-[11px] font-bold border ${
                              batch.status === 'COMPLETED'
                                ? 'bg-emerald-950 border-emerald-700 text-emerald-300'
                                : batch.status === 'FAILED' || batch.status === 'CANCELLED'
                                ? 'bg-red-950 border-red-800 text-red-300'
                                : 'bg-amber-950 border-amber-800 text-amber-300'
                            }`}
                          >
                            Batch Status: {batch.status}
                          </span>
                        </div>

                        {/* Batch Stat Summary Cards */}
                        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-center text-xs">
                          <div className="bg-slate-950 p-2 rounded border border-slate-800">
                            <span className="text-[10px] text-slate-400 block">Total</span>
                            <strong className="text-slate-100 font-bold">{batch.recipient_count}</strong>
                          </div>
                          <div className="bg-slate-950 p-2 rounded border border-slate-800">
                            <span className="text-[10px] text-slate-400 block">Pending</span>
                            <strong className="text-amber-300 font-bold">{batch.pending_count}</strong>
                          </div>
                          <div className="bg-slate-950 p-2 rounded border border-slate-800">
                            <span className="text-[10px] text-slate-400 block">Processing</span>
                            <strong className="text-blue-300 font-bold">{batch.processing_count}</strong>
                          </div>
                          <div className="bg-slate-950 p-2 rounded border border-slate-800">
                            <span className="text-[10px] text-slate-400 block">Simulated Success</span>
                            <strong className="text-emerald-400 font-bold">{batch.succeeded_count}</strong>
                          </div>
                          <div className="bg-slate-950 p-2 rounded border border-slate-800">
                            <span className="text-[10px] text-slate-400 block">Failed</span>
                            <strong className="text-red-400 font-bold">{batch.failed_count}</strong>
                          </div>
                          <div className="bg-slate-950 p-2 rounded border border-slate-800">
                            <span className="text-[10px] text-slate-400 block">Cancelled</span>
                            <strong className="text-slate-400 font-bold">{batch.cancelled_count || 0}</strong>
                          </div>
                        </div>

                        <div className="text-[11px] text-slate-400 flex items-center justify-between pt-1">
                          <span>Created By: {batch.created_by}</span>
                          <span>Provider: {batch.provider_name}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Per-Recipient Deliveries Table */}
                {selectedBatchId && (
                  <div className="pt-4 border-t border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <h5 className="text-xs font-bold text-slate-200">
                        Recipient Deliveries for Selected Batch ({linkedDeliveries.length})
                      </h5>
                      {loadingDeliveries && (
                        <span role="status" className="text-[11px] text-emerald-400 flex items-center gap-1">
                          <span className="material-symbols-outlined animate-spin text-xs">sync</span>
                          Loading deliveries...
                        </span>
                      )}
                    </div>

                    {deliveryError && (
                      <div role="alert" className="p-2.5 bg-red-950/60 border border-red-800/80 rounded text-xs text-red-200">
                        {deliveryError}
                      </div>
                    )}

                    {!loadingDeliveries && !deliveryError && linkedDeliveries.length === 0 && (
                      <p className="text-xs text-slate-400 italic">No recipient delivery records found for this batch.</p>
                    )}

                    {linkedDeliveries.length > 0 && (
                      <div className="overflow-x-auto border border-slate-800 rounded-lg">
                        <table className="w-full text-left text-xs text-slate-300">
                          <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] font-semibold tracking-wider border-b border-slate-800">
                            <tr>
                              <th className="p-2.5">Recipient ID</th>
                              <th className="p-2.5">Delivery Status</th>
                              <th className="p-2.5">Provider Ref</th>
                              <th className="p-2.5">Attempts</th>
                              <th className="p-2.5">Last Error</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60 bg-slate-900/50">
                            {linkedDeliveries.map((del) => {
                              const displayStatus = del.status === 'SUCCEEDED' ? 'Simulated Success' : del.status;
                              return (
                                <tr key={del.delivery_id} className="hover:bg-slate-800/40">
                                  <td className="p-2.5 font-mono text-[11px] text-slate-200">{del.recipient_id}</td>
                                  <td className="p-2.5">
                                    <span
                                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                                        del.status === 'SUCCEEDED'
                                          ? 'bg-emerald-950 border-emerald-700 text-emerald-300'
                                          : del.status === 'FAILED'
                                          ? 'bg-red-950 border-red-800 text-red-300'
                                          : 'bg-slate-800 border-slate-700 text-slate-300'
                                      }`}
                                    >
                                      {displayStatus}
                                    </span>
                                  </td>
                                  <td className="p-2.5 font-mono text-[11px] text-slate-400">
                                    {del.provider_reference || 'N/A'}
                                  </td>
                                  <td className="p-2.5 font-semibold text-slate-200">{del.attempt_count}</td>
                                  <td className="p-2.5 text-red-300/90 text-[11px] max-w-[200px] truncate">
                                    {del.last_error ? sanitizeErrorMessage(del.last_error, 'Provider execution error.') : 'None'}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

VeterinaryForecastAdvisoryHistory.propTypes = {
  viewerContext: PropTypes.object,
};
