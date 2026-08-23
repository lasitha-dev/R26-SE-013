import React, { useState, useEffect, useMemo, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  validateViewerContext,
} from '../../contracts/viewerContext';
import {
  listFollowUps,
  getFollowUp,
  cancelFollowUp,
  FOLLOW_UP_STATUS,
  OPERATIONAL_PRIORITY,
  RiskForecastingWorkflowApiError,
} from '../../services/riskForecastingWorkflowApi';
import { AccessContextUnavailable } from '../AccessContextUnavailable';

/**
 * Sanitizes technical error messages to prevent leakage of paths, credentials, or internal details.
 */
function sanitizeErrorMessage(error) {
  if (!error) return 'An unexpected error occurred.';
  const msg = typeof error === 'string' ? error : error.message || String(error);

  // Strip file paths, database URLs, auth headers, and stack traces
  const sanitized = msg
    .replace(/(?:[a-zA-Z]:\\|\/)[^\s:]+/g, '[redacted-path]')
    .replace(/mongodb(?:\+srv)?:\/\/[^\s]+/gi, '[redacted-url]')
    .replace(/Bearer\s+[^\s]+/gi, '[redacted-token]')
    .replace(/API Error \d+:\s*/gi, '');

  return sanitized.trim() || 'An unexpected error occurred.';
}

/**
 * Formats ISO timestamp for human-friendly display.
 */
function formatTimestamp(isoString) {
  if (!isoString) return 'N/A';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return 'N/A';
    return d.toLocaleString('en-GB', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch (_) {
    return 'N/A';
  }
}

/**
 * Status badge styling mapper.
 */
function getStatusBadgeStyle(status) {
  switch (status) {
    case FOLLOW_UP_STATUS.ISSUED:
      return 'bg-blue-100 text-blue-800 border-blue-300';
    case FOLLOW_UP_STATUS.ACKNOWLEDGED:
      return 'bg-purple-100 text-purple-800 border-purple-300';
    case FOLLOW_UP_STATUS.ACTION_IN_PROGRESS:
      return 'bg-amber-100 text-amber-800 border-amber-300';
    case FOLLOW_UP_STATUS.COMPLETED:
      return 'bg-emerald-100 text-emerald-800 border-emerald-300';
    case FOLLOW_UP_STATUS.CANCELLED:
      return 'bg-slate-100 text-slate-700 border-slate-300';
    case FOLLOW_UP_STATUS.ESCALATED:
      return 'bg-red-100 text-red-800 border-red-300';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-300';
  }
}

/**
 * DaphFollowUpMonitoring — DAPH-only workspace for monitoring forecast follow-ups
 * and cancelling active follow-ups when operationally necessary.
 */
export function DaphFollowUpMonitoring({ viewerContext }) {
  // 1. Fail-closed ViewerContext Authorization
  const validation = useMemo(() => validateViewerContext(viewerContext), [viewerContext]);
  const normalizedContext = validation.valid ? validation.normalizedContext : null;
  const userId = normalizedContext?.userId ? String(normalizedContext.userId).trim() : '';
  const isAuthorized = Boolean(
    validation.valid &&
      normalizedContext &&
      normalizedContext.role === ROLES.DAPH_OFFICIAL &&
      userId !== ''
  );

  // Memoize DAPH actor context for backend request headers
  const actorContext = useMemo(() => {
    if (!isAuthorized || !userId) return null;
    return Object.freeze({
      actor_id: userId,
      role: ROLES.DAPH_OFFICIAL,
    });
  }, [isAuthorized, userId]);

  // Filter state
  const [filters, setFilters] = useState({
    status: '',
    disease: '',
    district: '',
    operational_priority: '',
    assigned_vet_id: '',
    target_year: '',
    target_month: '',
  });

  // Query & Record State
  const [followUps, setFollowUps] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [conflictError, setConflictError] = useState(null);

  // Selected Detail Drawer Record
  const [selectedRecord, setSelectedRecord] = useState(null);

  // Cancellation Dialog State
  const [cancelModalRecord, setCancelModalRecord] = useState(null);
  const [isSubmittingCancel, setIsSubmittingCancel] = useState(false);

  // Query list runner
  const fetchFollowUps = useCallback(
    async (signal) => {
      if (!isAuthorized || !actorContext) return;
      setIsLoading(true);
      setError(null);

      try {
        const queryFilters = {};
        if (filters.status) queryFilters.status = filters.status;
        if (filters.disease) queryFilters.disease = filters.disease;
        if (filters.district) queryFilters.district = filters.district;
        if (filters.operational_priority) queryFilters.operational_priority = filters.operational_priority;
        if (filters.assigned_vet_id) queryFilters.assigned_vet_id = filters.assigned_vet_id.trim();
        if (filters.target_year) queryFilters.target_year = Number(filters.target_year);
        if (filters.target_month) queryFilters.target_month = Number(filters.target_month);

        const res = await listFollowUps(queryFilters, { actorContext, signal });
        const records = res?.follow_ups || res?.records || (Array.isArray(res) ? res : []);

        // Deterministic Newest-First Sorting
        const sorted = [...records].sort((a, b) => {
          const timeA = new Date(a.updated_at || a.created_at || 0).getTime();
          const timeB = new Date(b.updated_at || b.created_at || 0).getTime();
          if (timeB !== timeA) return timeB - timeA;
          const createA = new Date(a.created_at || 0).getTime();
          const createB = new Date(b.created_at || 0).getTime();
          if (createB !== createA) return createB - createA;
          return String(b.follow_up_id || '').localeCompare(String(a.follow_up_id || ''));
        });

        setFollowUps(sorted);
      } catch (err) {
        if (err.name === 'AbortError') return;
        setError(sanitizeErrorMessage(err));
      } finally {
        setIsLoading(false);
      }
    },
    [isAuthorized, actorContext, filters]
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchFollowUps(controller.signal);
    return () => controller.abort();
  }, [fetchFollowUps]);

  // Keep selected record synced with latest followUps list
  useEffect(() => {
    if (selectedRecord && followUps.length > 0) {
      const updatedSelected = followUps.find((r) => r.follow_up_id === selectedRecord.follow_up_id);
      if (updatedSelected && updatedSelected !== selectedRecord) {
        setSelectedRecord(updatedSelected);
      }
    }
  }, [followUps]);

  // Derived Summary Card Statistics
  const summary = useMemo(() => {
    const total = followUps.length;
    const issued = followUps.filter((r) => r.status === FOLLOW_UP_STATUS.ISSUED).length;
    const actionUnderway = followUps.filter(
      (r) => r.status === FOLLOW_UP_STATUS.ACKNOWLEDGED || r.status === FOLLOW_UP_STATUS.ACTION_IN_PROGRESS
    ).length;
    const completed = followUps.filter((r) => r.status === FOLLOW_UP_STATUS.COMPLETED).length;
    const escalated = followUps.filter((r) => r.status === FOLLOW_UP_STATUS.ESCALATED).length;
    const cancelled = followUps.filter((r) => r.status === FOLLOW_UP_STATUS.CANCELLED).length;

    return { total, issued, actionUnderway, completed, escalated, cancelled };
  }, [followUps]);

  // Fail-closed authorization guard
  if (!isAuthorized) {
    return (
      <AccessContextUnavailable reason="Follow-Up Monitoring is available only to authorized DAPH Officials with national scope." />
    );
  }

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  const handleResetFilters = () => {
    setFilters({
      status: '',
      disease: '',
      district: '',
      operational_priority: '',
      assigned_vet_id: '',
      target_year: '',
      target_month: '',
    });
  };

  // Perform Cancellation
  const handleExecuteCancel = async () => {
    if (!cancelModalRecord || !actorContext || isSubmittingCancel) return;

    setIsSubmittingCancel(true);
    setConflictError(null);
    setError(null);

    try {
      const updated = await cancelFollowUp(
        cancelModalRecord.follow_up_id,
        cancelModalRecord.version,
        { actorContext }
      );

      // Update local state cleanly
      setFollowUps((prev) =>
        prev.map((r) => (r.follow_up_id === updated.follow_up_id ? updated : r))
      );
      if (selectedRecord && selectedRecord.follow_up_id === updated.follow_up_id) {
        setSelectedRecord(updated);
      }
      setCancelModalRecord(null);
    } catch (err) {
      if (err?.status === 409 || (err instanceof RiskForecastingWorkflowApiError && err.status === 409)) {
        setConflictError(
          'Optimistic lock conflict: This follow-up was updated elsewhere. Please refresh to view the latest state.'
        );
      } else {
        setError(sanitizeErrorMessage(err));
      }
    } finally {
      setIsSubmittingCancel(false);
    }
  };

  // Explicit Refresh for 409 Conflict recovery
  const handleRefreshRecord = async (followUpId) => {
    if (!followUpId || !actorContext) return;
    setConflictError(null);
    try {
      const fresh = await getFollowUp(followUpId, { actorContext });
      setFollowUps((prev) =>
        prev.map((r) => (r.follow_up_id === fresh.follow_up_id ? fresh : r))
      );
      if (selectedRecord && selectedRecord.follow_up_id === fresh.follow_up_id) {
        setSelectedRecord(fresh);
      }
      if (cancelModalRecord && cancelModalRecord.follow_up_id === fresh.follow_up_id) {
        setCancelModalRecord(fresh);
      }
    } catch (err) {
      setError(`Refresh failed: ${sanitizeErrorMessage(err)}`);
    }
  };

  return (
    <div className="w-full min-w-0 space-y-6">
      {/* Workspace Header & Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Follow-Up Monitoring
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            National overview of forecast-linked operational follow-up instructions issued to Sri Lankan Veterinary Officers.
          </p>
        </div>
        <button
          type="button"
          onClick={() => fetchFollowUps()}
          disabled={isLoading}
          className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
        >
          <span className="material-icons-outlined text-base mr-2">refresh</span>
          Refresh List
        </button>
      </div>

      {/* Operational Disclaimer */}
      <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600 leading-relaxed space-y-1">
        <p className="font-semibold text-slate-800">
          Operational Boundary & Scientific Transparency Notice:
        </p>
        <p>
          This workspace displays operational status metrics for issued follow-ups. Completion or cancellation of a follow-up represents standalone task management within DAPH operations and does not guarantee physical field action reversal, farmer notification receipt, or disease elimination.
        </p>
      </div>

      {/* Error & Conflict Banners */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-start justify-between text-sm text-red-800">
          <div className="flex items-center space-x-2">
            <span className="material-icons-outlined text-red-600">error_outline</span>
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-red-600 hover:text-red-800 text-xs font-semibold"
          >
            Dismiss
          </button>
        </div>
      )}

      {conflictError && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between text-sm text-amber-900">
          <div className="flex items-center space-x-2">
            <span className="material-icons-outlined text-amber-600">warning</span>
            <span>{conflictError}</span>
          </div>
          {selectedRecord && (
            <button
              type="button"
              onClick={() => handleRefreshRecord(selectedRecord.follow_up_id)}
              className="px-3 py-1 bg-amber-600 text-white rounded-md text-xs font-medium hover:bg-amber-700"
            >
              Refresh Record
            </button>
          )}
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Items</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{summary.total}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-blue-600 uppercase tracking-wider">Issued</p>
          <p className="text-2xl font-bold text-blue-900 mt-1">{summary.issued}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-amber-600 uppercase tracking-wider">Underway</p>
          <p className="text-2xl font-bold text-amber-900 mt-1">{summary.actionUnderway}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-emerald-600 uppercase tracking-wider">Completed</p>
          <p className="text-2xl font-bold text-emerald-900 mt-1">{summary.completed}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-red-600 uppercase tracking-wider">Escalated</p>
          <p className="text-2xl font-bold text-red-900 mt-1">{summary.escalated}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Cancelled</p>
          <p className="text-2xl font-bold text-slate-700 mt-1">{summary.cancelled}</p>
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-800 flex items-center">
            <span className="material-icons-outlined text-base mr-1 text-slate-500">filter_list</span>
            Query Filters
          </h2>
          <button
            type="button"
            onClick={handleResetFilters}
            className="text-xs font-medium text-slate-600 hover:text-slate-900 underline"
          >
            Reset Filters
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Status</label>
            <select
              name="status"
              value={filters.status}
              onChange={handleFilterChange}
              className="w-full text-xs border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All Statuses</option>
              <option value={FOLLOW_UP_STATUS.ISSUED}>ISSUED</option>
              <option value={FOLLOW_UP_STATUS.ACKNOWLEDGED}>ACKNOWLEDGED</option>
              <option value={FOLLOW_UP_STATUS.ACTION_IN_PROGRESS}>ACTION_IN_PROGRESS</option>
              <option value={FOLLOW_UP_STATUS.COMPLETED}>COMPLETED</option>
              <option value={FOLLOW_UP_STATUS.ESCALATED}>ESCALATED</option>
              <option value={FOLLOW_UP_STATUS.CANCELLED}>CANCELLED</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Disease</label>
            <select
              name="disease"
              value={filters.disease}
              onChange={handleFilterChange}
              className="w-full text-xs border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All Diseases</option>
              <option value="FMD">FMD</option>
              <option value="LSD">LSD</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">District</label>
            <input
              type="text"
              name="district"
              value={filters.district}
              onChange={handleFilterChange}
              placeholder="e.g. Anuradhapura"
              className="w-full text-xs border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Priority</label>
            <select
              name="operational_priority"
              value={filters.operational_priority}
              onChange={handleFilterChange}
              className="w-full text-xs border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All Priorities</option>
              <option value={OPERATIONAL_PRIORITY.HIGH}>HIGH</option>
              <option value={OPERATIONAL_PRIORITY.MEDIUM}>MEDIUM</option>
              <option value={OPERATIONAL_PRIORITY.LOW}>LOW</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Table & Master-Detail Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Table Column (Span 2 on lg) */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-800">
              National Follow-Up Records ({followUps.length})
            </h2>
            {isLoading && (
              <span className="text-xs text-slate-500 animate-pulse" aria-live="polite">
                Loading follow-ups...
              </span>
            )}
          </div>

          {isLoading && followUps.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-sm">
              Loading follow-up records...
            </div>
          ) : followUps.length === 0 ? (
            <div className="p-12 text-center space-y-2">
              <span className="material-icons-outlined text-4xl text-slate-300">inbox</span>
              <p className="text-sm font-medium text-slate-700">No Follow-Up Records Found</p>
              <p className="text-xs text-slate-500">
                No operational follow-ups match the selected query criteria.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 border-b border-slate-200 font-semibold text-slate-600 uppercase tracking-wider">
                  <tr>
                    <th className="p-3">Follow-Up ID</th>
                    <th className="p-3">Disease / District</th>
                    <th className="p-3">Assigned Vet</th>
                    <th className="p-3">Priority</th>
                    <th className="p-3">Status</th>
                    <th className="p-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {followUps.map((record) => {
                    const isSelected = selectedRecord?.follow_up_id === record.follow_up_id;
                    return (
                      <tr
                        key={record.follow_up_id}
                        className={`hover:bg-slate-50 transition-colors ${
                          isSelected ? 'bg-emerald-50/60' : ''
                        }`}
                      >
                        <td className="p-3 font-mono font-medium text-slate-900">
                          {record.follow_up_id}
                        </td>
                        <td className="p-3">
                          <span className="font-semibold text-slate-800">{record.disease}</span>
                          <span className="text-slate-500 block">{record.district}</span>
                        </td>
                        <td className="p-3 font-mono text-slate-600">
                          {record.assigned_vet_id || 'N/A'}
                        </td>
                        <td className="p-3 font-semibold">
                          {record.operational_priority || 'N/A'}
                        </td>
                        <td className="p-3">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-semibold ${getStatusBadgeStyle(
                              record.status
                            )}`}
                          >
                            {record.status}
                          </span>
                        </td>
                        <td className="p-3 text-right">
                          <button
                            type="button"
                            onClick={() => setSelectedRecord(record)}
                            className="px-2.5 py-1 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded border border-emerald-200"
                          >
                            Details
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Detail Panel Column (Span 1 on lg) */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-6">
          <h2 className="text-base font-bold text-slate-900 border-b border-slate-200 pb-3 flex items-center justify-between">
            <span>Record Details</span>
            {selectedRecord && (
              <span className="text-xs font-mono font-normal text-slate-500">
                {selectedRecord.follow_up_id}
              </span>
            )}
          </h2>

          {!selectedRecord ? (
            <div className="py-12 text-center text-slate-500 text-xs">
              Select a follow-up record from the table to view details, timeline, and actions.
            </div>
          ) : (
            <div className="space-y-6 text-xs">
              {/* Header Status & Version */}
              <div className="flex items-center justify-between bg-slate-50 p-3 rounded-lg border border-slate-200">
                <div>
                  <p className="text-slate-500 text-[10px] uppercase font-medium">Status / Version</p>
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded border font-semibold mt-1 ${getStatusBadgeStyle(
                      selectedRecord.status
                    )}`}
                  >
                    {selectedRecord.status}
                  </span>
                </div>
                <div className="text-right">
                  <p className="text-slate-500 text-[10px] uppercase font-medium">Record Version</p>
                  <p className="font-mono font-bold text-slate-800 text-sm mt-0.5">v{selectedRecord.version}</p>
                </div>
              </div>

              {/* Scientific Forecast Snapshot (Read-Only) */}
              <div className="space-y-2">
                <h3 className="font-bold text-slate-800 uppercase tracking-wider text-[11px] border-b border-slate-100 pb-1">
                  Scientific Forecast Snapshot (Read-Only)
                </h3>
                <div className="grid grid-cols-2 gap-2 text-slate-700">
                  <div>
                    <span className="text-slate-500 block">Forecast ID:</span>
                    <span className="font-mono font-medium">{selectedRecord.forecast_id || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Disease / District:</span>
                    <span className="font-semibold">{selectedRecord.disease} ({selectedRecord.district})</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Target Period:</span>
                    <span>{selectedRecord.target_year} - Month {selectedRecord.target_month}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Risk Level:</span>
                    <span className="font-bold text-slate-900">{selectedRecord.forecast_risk_level || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Probability:</span>
                    <span>{selectedRecord.forecast_probability_pct !== undefined ? `${selectedRecord.forecast_probability_pct}%` : 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Priority:</span>
                    <span className="font-semibold">{selectedRecord.operational_priority || 'N/A'}</span>
                  </div>
                </div>
              </div>

              {/* DAPH Instruction Summary */}
              <div className="space-y-1">
                <h3 className="font-bold text-slate-800 uppercase tracking-wider text-[11px] border-b border-slate-100 pb-1">
                  Operational Instruction
                </h3>
                <p className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 font-medium leading-relaxed">
                  {selectedRecord.instruction_summary || 'N/A'}
                </p>
              </div>

              {/* Personnel Assignment */}
              <div className="grid grid-cols-2 gap-2 text-slate-700">
                <div>
                  <span className="text-slate-500 block">Assigned Vet ID:</span>
                  <span className="font-mono font-semibold text-slate-900">{selectedRecord.assigned_vet_id || 'N/A'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Issued By DAPH:</span>
                  <span className="font-mono font-semibold text-slate-900">{selectedRecord.issued_by_daph_id || 'N/A'}</span>
                </div>
              </div>

              {/* External Resource Request Reference */}
              <div className="space-y-1">
                <span className="text-slate-500 block">External Resource Request ID:</span>
                <span className="font-mono text-slate-800 bg-slate-100 px-2 py-1 rounded inline-block">
                  {selectedRecord.external_resource_request_id || 'Not linked'}
                </span>
              </div>

              {/* Escalation Reason (If Present) */}
              {selectedRecord.escalation_reason && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg space-y-1 text-red-900">
                  <p className="font-bold uppercase text-[10px] text-red-700">Escalation Reason:</p>
                  <p className="leading-relaxed">{selectedRecord.escalation_reason}</p>
                </div>
              )}

              {/* Lifecycle Timeline */}
              <div className="space-y-2">
                <h3 className="font-bold text-slate-800 uppercase tracking-wider text-[11px] border-b border-slate-100 pb-1">
                  Lifecycle Timeline
                </h3>
                <ul className="space-y-1.5 text-[11px] text-slate-600">
                  <li className="flex justify-between border-b border-slate-50 pb-1">
                    <span>Issued:</span>
                    <span className="font-mono">{formatTimestamp(selectedRecord.created_at)}</span>
                  </li>
                  {selectedRecord.acknowledged_at && (
                    <li className="flex justify-between border-b border-slate-50 pb-1">
                      <span>Acknowledged:</span>
                      <span className="font-mono">{formatTimestamp(selectedRecord.acknowledged_at)}</span>
                    </li>
                  )}
                  {selectedRecord.action_started_at && (
                    <li className="flex justify-between border-b border-slate-50 pb-1">
                      <span>Action Started:</span>
                      <span className="font-mono">{formatTimestamp(selectedRecord.action_started_at)}</span>
                    </li>
                  )}
                  {selectedRecord.completed_at && (
                    <li className="flex justify-between border-b border-slate-50 pb-1">
                      <span>Completed:</span>
                      <span className="font-mono">{formatTimestamp(selectedRecord.completed_at)}</span>
                    </li>
                  )}
                  {selectedRecord.cancelled_at && (
                    <li className="flex justify-between border-b border-slate-50 pb-1 text-slate-700 font-semibold">
                      <span>Cancelled:</span>
                      <span className="font-mono">{formatTimestamp(selectedRecord.cancelled_at)}</span>
                    </li>
                  )}
                  {selectedRecord.escalated_at && (
                    <li className="flex justify-between border-b border-slate-50 pb-1 text-red-700 font-semibold">
                      <span>Escalated:</span>
                      <span className="font-mono">{formatTimestamp(selectedRecord.escalated_at)}</span>
                    </li>
                  )}
                </ul>
              </div>

              {/* Allowed DAPH Action Controls */}
              <div className="pt-2 border-t border-slate-200">
                {selectedRecord.status === FOLLOW_UP_STATUS.ISSUED ||
                selectedRecord.status === FOLLOW_UP_STATUS.ACKNOWLEDGED ||
                selectedRecord.status === FOLLOW_UP_STATUS.ACTION_IN_PROGRESS ? (
                  <button
                    type="button"
                    onClick={() => setCancelModalRecord(selectedRecord)}
                    className="w-full py-2.5 px-4 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 focus:ring-2 focus:ring-red-500 focus:outline-none shadow-sm transition-colors flex items-center justify-center space-x-1.5"
                  >
                    <span className="material-icons-outlined text-base">cancel</span>
                    <span>Cancel Follow-Up</span>
                  </button>
                ) : (
                  <p className="text-center text-slate-500 italic py-2">
                    No DAPH mutation controls available for terminal status '{selectedRecord.status}'.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Cancellation Confirmation Modal */}
      {cancelModalRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center space-x-2 text-red-600 border-b border-slate-100 pb-3">
              <span className="material-icons-outlined text-2xl">warning</span>
              <h3 className="text-lg font-bold text-slate-900">Confirm Cancellation</h3>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to cancel operational follow-up instruction{' '}
              <strong className="font-mono text-slate-900">{cancelModalRecord.follow_up_id}</strong>?
            </p>

            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-1 text-xs text-slate-700">
              <p><strong>Disease / District:</strong> {cancelModalRecord.disease} ({cancelModalRecord.district})</p>
              <p><strong>Assigned Vet:</strong> {cancelModalRecord.assigned_vet_id || 'N/A'}</p>
              <p><strong>Current Status:</strong> {cancelModalRecord.status} (v{cancelModalRecord.version})</p>
            </div>

            <p className="text-[11px] text-slate-500 italic">
              Notice: Cancellation updates the standalone operational record status to CANCELLED. It does not guarantee physical field action reversal or recall of issued instructions.
            </p>

            <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setCancelModalRecord(null)}
                disabled={isSubmittingCancel}
                className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
              >
                Keep Follow-Up
              </button>
              <button
                type="button"
                onClick={handleExecuteCancel}
                disabled={isSubmittingCancel}
                className="px-4 py-2 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50 flex items-center space-x-1"
              >
                {isSubmittingCancel ? (
                  <span>Cancelling...</span>
                ) : (
                  <span>Confirm Cancel</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

DaphFollowUpMonitoring.propTypes = {
  viewerContext: PropTypes.object,
};
