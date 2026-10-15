import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  validateViewerContext,
} from '../../contracts/viewerContext';
import {
  listFollowUps,
  getFollowUp,
  cancelFollowUp,
  listEligibleFollowUpVets,
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
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

const STATUS_LABEL = {
  ISSUED: 'Issued',
  ACKNOWLEDGED: 'Acknowledged',
  ACTION_IN_PROGRESS: 'In progress',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
  ESCALATED: 'Escalated',
};

// The steps a follow-up goes through; the ones not reached yet are shown greyed out while the follow-up is still open.
function buildTimeline(record) {
  const steps = [
    { key: 'issued', label: 'Issued', at: record.created_at, tone: 'done' },
    { key: 'ack', label: 'Acknowledged by the officer', at: record.acknowledged_at, tone: 'done' },
    { key: 'action', label: 'Field action started', at: record.action_started_at, tone: 'done' },
  ];
  const ending = [
    { key: 'completed', label: 'Completed', at: record.completed_at, tone: 'done' },
    { key: 'cancelled', label: 'Cancelled', at: record.cancelled_at, tone: 'cancel' },
    { key: 'escalated', label: 'Escalated', at: record.escalated_at, tone: 'alert' },
  ];
  const reachedEnd = ending.filter((e) => e.at);
  const closed = reachedEnd.length > 0;
  const all = [...steps.filter((x) => x.at || !closed), ...reachedEnd];
  if (!closed) all.push({ key: 'completed', label: 'Completed', at: null, tone: 'done' });
  return all;
}

function getStatusBadgeStyle(status) {
  switch (status) {
    case FOLLOW_UP_STATUS.ISSUED:
      return 'bg-blue-500/20 text-blue-300 border-blue-500/40';
    case FOLLOW_UP_STATUS.ACKNOWLEDGED:
      return 'bg-purple-500/20 text-purple-300 border-purple-500/40';
    case FOLLOW_UP_STATUS.ACTION_IN_PROGRESS:
      return 'bg-amber-950/300/20 text-amber-300 border-amber-500/40';
    case FOLLOW_UP_STATUS.COMPLETED:
      return 'bg-slate-8000/20 text-emerald-300 border-emerald-500/40';
    case FOLLOW_UP_STATUS.CANCELLED:
      return 'bg-slate-800 text-slate-400 border-slate-700';
    case FOLLOW_UP_STATUS.ESCALATED:
      return 'bg-red-950/300/20 text-red-300 border-red-500/40';
    default:
      return 'bg-slate-800 text-slate-400 border-slate-700';
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
  const activeRequestRef = useRef(null);

  const fetchFollowUps = useCallback(
    async () => {
      if (!isAuthorized || !actorContext) return;

      if (activeRequestRef.current) {
        activeRequestRef.current.isActive = false;
        activeRequestRef.current.controller.abort();
      }

      const currentRequest = {
        isActive: true,
        controller: new AbortController(),
      };
      activeRequestRef.current = currentRequest;

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

        const res = await listFollowUps(queryFilters, { actorContext, signal: currentRequest.controller.signal });
        const records = res?.follow_ups || res?.records || (Array.isArray(res) ? res : []);

        if (currentRequest.isActive) {
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
          setError(null);
          setIsLoading(false);
        }
      } catch (err) {
        if (!currentRequest.isActive || err.name === 'AbortError') return;
        setError('Follow-up information could not be loaded. Please try again.');
        setIsLoading(false);
      }
    },
    [isAuthorized, actorContext, filters]
  );

  // Officer names for the ids on the records (the directory is queried once per district)
  const [vetNames, setVetNames] = useState({});
  useEffect(() => {
    if (!actorContext || followUps.length === 0) return undefined;
    let active = true;
    const districts = [...new Set(followUps.map((f) => f.district).filter(Boolean))];
    Promise.all(districts.map((district) => listEligibleFollowUpVets({ district }, { actorContext }).catch(() => null)))
      .then((results) => {
        if (!active) return;
        const names = {};
        results.forEach((res) => (res?.veterinary_officers || []).forEach((v) => { names[v.vet_id] = v.display_name; }));
        setVetNames((prev) => ({ ...prev, ...names }));
      });
    return () => { active = false; };
  }, [followUps, actorContext]);
  const officerName = (id) => (id ? vetNames[id] || 'Veterinary officer' : 'N/A');

  useEffect(() => {
    fetchFollowUps();
    return () => {
      if (activeRequestRef.current) {
        activeRequestRef.current.isActive = false;
        activeRequestRef.current.controller.abort();
      }
    };
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            Follow-Up Monitoring
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            National overview of forecast-linked operational follow-up instructions issued to Sri Lankan Veterinary Officers.
          </p>
        </div>
        <button
          type="button"
          onClick={() => fetchFollowUps()}
          disabled={isLoading}
          className="inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-slate-300 bg-slate-800/40 border border-slate-700 rounded-lg hover:bg-slate-900/50 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
        >
          <span className="material-symbols-outlined text-base mr-2" aria-hidden="true">refresh</span>
          Refresh List
        </button>
      </div>

      {/* Operational Disclaimer */}
      <div className="p-4 bg-slate-900/50 border border-slate-800 rounded-xl text-xs text-slate-400 leading-relaxed space-y-1">
        <p className="font-semibold text-slate-200">
          Operational Boundary & Scientific Transparency Notice:
        </p>
        <p>
          This workspace displays operational status metrics for issued follow-ups. Completion or cancellation of a follow-up represents standalone task management within DAPH operations and does not guarantee physical field action reversal, farmer notification receipt, or disease elimination.
        </p>
      </div>

      {/* Error & Conflict Banners */}
      {error && (
        <div className="p-4 bg-red-950/30 border border-red-500/30 rounded-xl flex items-start justify-between text-sm text-red-300">
          <div className="flex items-center space-x-2">
            <span className="material-symbols-outlined text-red-400" aria-hidden="true">error_outline</span>
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-red-400 hover:text-red-300 text-xs font-semibold"
          >
            Dismiss
          </button>
        </div>
      )}

      {conflictError && (
        <div className="p-4 bg-amber-950/30 border border-amber-500/30 rounded-xl flex items-center justify-between text-sm text-amber-300">
          <div className="flex items-center space-x-2">
            <span className="material-symbols-outlined text-amber-400" aria-hidden="true">warning</span>
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
        <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-800 shadow-sm">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Items</p>
          <p className="text-2xl font-bold text-white mt-1">{summary.total}</p>
        </div>
        <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-800 shadow-sm">
          <p className="text-xs font-medium text-blue-400 uppercase tracking-wider">Issued</p>
          <p className="text-2xl font-bold text-blue-300 mt-1">{summary.issued}</p>
        </div>
        <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-800 shadow-sm">
          <p className="text-xs font-medium text-amber-400 uppercase tracking-wider">Underway</p>
          <p className="text-2xl font-bold text-amber-300 mt-1">{summary.actionUnderway}</p>
        </div>
        <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-800 shadow-sm">
          <p className="text-xs font-medium text-emerald-400 uppercase tracking-wider">Completed</p>
          <p className="text-2xl font-bold text-emerald-300 mt-1">{summary.completed}</p>
        </div>
        <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-800 shadow-sm">
          <p className="text-xs font-medium text-red-400 uppercase tracking-wider">Escalated</p>
          <p className="text-2xl font-bold text-red-300 mt-1">{summary.escalated}</p>
        </div>
        <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-800 shadow-sm">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Cancelled</p>
          <p className="text-2xl font-bold text-slate-300 mt-1">{summary.cancelled}</p>
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-800 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center">
            <span className="material-symbols-outlined text-base mr-1 text-slate-500" aria-hidden="true">filter_list</span>
            Query Filters
          </h2>
          <button
            type="button"
            onClick={handleResetFilters}
            className="text-xs font-medium text-slate-400 hover:text-white underline"
          >
            Reset Filters
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Status</label>
            <select
              name="status"
              value={filters.status}
              onChange={handleFilterChange}
              className="w-full text-xs bg-slate-900 text-slate-200 border border-slate-700 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
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
            <label className="block text-xs font-medium text-slate-300 mb-1">Disease</label>
            <select
              name="disease"
              value={filters.disease}
              onChange={handleFilterChange}
              className="w-full text-xs bg-slate-900 text-slate-200 border border-slate-700 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All Diseases</option>
              <option value="FMD">FMD</option>
              <option value="LSD">LSD</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">District</label>
            <input
              type="text"
              name="district"
              value={filters.district}
              onChange={handleFilterChange}
              placeholder="e.g. Anuradhapura"
              className="w-full text-xs bg-slate-900 text-slate-200 border border-slate-700 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Priority</label>
            <select
              name="operational_priority"
              value={filters.operational_priority}
              onChange={handleFilterChange}
              className="w-full text-xs bg-slate-900 text-slate-200 border border-slate-700 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
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
        <div className="lg:col-span-2 bg-slate-800/40 rounded-xl border border-slate-800 shadow-sm overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-200">
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
              <span className="material-symbols-outlined text-4xl text-slate-300" aria-hidden="true">inbox</span>
              <p className="text-sm font-medium text-slate-300">No Follow-Up Records Found</p>
              <p className="text-xs text-slate-500">
                No operational follow-ups match the selected query criteria.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/50 border-b border-slate-800 font-semibold text-slate-400 uppercase tracking-wider">
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
                        className={`hover:bg-slate-900/50 transition-colors ${
                          isSelected ? 'bg-emerald-900/30' : ''
                        }`}
                      >
                        <td className="p-3 font-mono font-medium text-white">
                          {record.follow_up_id}
                        </td>
                        <td className="p-3">
                          <span className="font-semibold text-slate-200">{record.disease}</span>
                          <span className="text-slate-500 block">{record.district}</span>
                        </td>
                        <td className="p-3 text-slate-200" title={record.assigned_vet_id || ''}>
                          {officerName(record.assigned_vet_id)}
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
                            className="px-2.5 py-1 text-xs font-medium text-emerald-400 bg-slate-800 hover:bg-slate-700 rounded border border-slate-700"
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
        <div className="bg-slate-800/40 rounded-2xl border border-slate-800 shadow-sm p-5 space-y-5">
          <h2 className="flex items-center justify-between gap-3 border-b border-slate-800 pb-3 text-base font-bold text-white">
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined text-xl text-emerald-400" aria-hidden="true">assignment</span>
              Follow-up details
            </span>
            {selectedRecord && (
              <span className="rounded-full border border-slate-700 bg-slate-900/70 px-2.5 py-0.5 font-mono text-[11px] font-normal text-slate-400" title={selectedRecord.follow_up_id}>
                Ref {String(selectedRecord.follow_up_id || '').replace(/^ffu_|^fu_/i, '').slice(0, 8).toUpperCase()}
              </span>
            )}
          </h2>

          {!selectedRecord ? (
            <div className="py-12 text-center text-slate-500 text-xs">
              Select a follow-up record from the table to view details, timeline, and actions.
            </div>
          ) : (
            <div className="space-y-5 text-xs">
              {/* Who, what, where */}
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-lg font-bold leading-tight text-white">{selectedRecord.disease} <span className="font-medium text-slate-400">in {selectedRecord.district}</span></p>
                  <p className="mt-1 text-slate-400">
                    For {MONTH_NAMES[Number(selectedRecord.target_month) - 1] || `month ${selectedRecord.target_month}`} {selectedRecord.target_year}
                  </p>
                </div>
                <span className={`inline-flex shrink-0 items-center rounded-full border px-3 py-1 text-[11px] font-semibold ${getStatusBadgeStyle(selectedRecord.status)}`}>
                  {STATUS_LABEL[selectedRecord.status] || selectedRecord.status}
                </span>
              </div>

              {/* The instruction */}
              <div className="rounded-xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 to-transparent p-4">
                <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-emerald-300">
                  <span className="material-symbols-outlined text-sm" aria-hidden="true">campaign</span>Instruction
                </p>
                <p className="text-sm leading-relaxed text-slate-100">{selectedRecord.instruction_summary || 'N/A'}</p>
              </div>

              {/* People */}
              <div className="grid grid-cols-2 gap-2.5">
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2.5">
                  <span className="flex items-center gap-1.5 text-slate-500"><span className="material-symbols-outlined text-sm" aria-hidden="true">person</span>Assigned to</span>
                  <span className="mt-0.5 block font-semibold text-white" title={selectedRecord.assigned_vet_id || ''}>{officerName(selectedRecord.assigned_vet_id)}</span>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2.5">
                  <span className="flex items-center gap-1.5 text-slate-500"><span className="material-symbols-outlined text-sm" aria-hidden="true">badge</span>Issued by</span>
                  <span className="mt-0.5 block font-semibold text-white" title={selectedRecord.issued_by_daph_id || ''}>
                    {selectedRecord.issued_by_daph_id ? (selectedRecord.issued_by_daph_id === userId ? 'DAPH Official (You)' : 'DAPH Official') : 'N/A'}
                  </span>
                </div>
              </div>

              {/* The forecast it is based on */}
              <div className="space-y-2">
                <h3 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  <span className="material-symbols-outlined text-sm" aria-hidden="true">fact_check</span>Based on the forecast
                  <span className="ml-auto flex items-center gap-1 rounded-full border border-slate-700 px-2 py-0.5 text-[10px] font-medium normal-case tracking-normal text-slate-500">
                    <span className="material-symbols-outlined text-xs" aria-hidden="true">lock</span>Read-only
                  </span>
                </h3>
                <div className="grid grid-cols-3 gap-2.5">
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2.5">
                    <span className="text-slate-500">Risk</span>
                    <span className={`mt-0.5 block font-bold ${selectedRecord.forecast_risk_level === 'HIGH' ? 'text-rose-400' : selectedRecord.forecast_risk_level === 'MEDIUM' ? 'text-amber-400' : 'text-emerald-400'}`}>
                      {selectedRecord.forecast_risk_level || 'N/A'}
                    </span>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2.5">
                    <span className="text-slate-500">Chance</span>
                    <span className="mt-0.5 block font-bold text-white">{typeof selectedRecord.probability === 'number' ? `${(selectedRecord.probability * 100).toFixed(1)}%` : 'N/A'}</span>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2.5">
                    <span className="text-slate-500">Priority</span>
                    <span className="mt-0.5 block font-bold text-amber-300">{selectedRecord.operational_priority || 'N/A'}</span>
                  </div>
                </div>
              </div>

              {/* Linked resource request, only when there is one */}
              {selectedRecord.external_resource_request_id && (
                <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2.5">
                  <span className="flex items-center gap-1.5 text-slate-500"><span className="material-symbols-outlined text-sm" aria-hidden="true">inventory_2</span>Resource request</span>
                  <span className="font-mono text-slate-200">{selectedRecord.external_resource_request_id}</span>
                </div>
              )}

              {/* Escalation Reason (If Present) */}
              {selectedRecord.escalation_reason && (
                <div className="p-3 bg-red-950/30 border border-red-500/30 rounded-xl space-y-1 text-red-300">
                  <p className="font-bold uppercase text-[10px] text-red-400">Escalation reason</p>
                  <p className="leading-relaxed">{selectedRecord.escalation_reason}</p>
                </div>
              )}

              {/* Progress */}
              <div className="space-y-2.5">
                <h3 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  <span className="material-symbols-outlined text-sm" aria-hidden="true">timeline</span>Progress
                </h3>
                <ol className="space-y-0">
                  {buildTimeline(selectedRecord).map((step, index, list) => {
                    const reached = Boolean(step.at);
                    const dot = !reached ? 'border-slate-600 bg-transparent' : step.tone === 'cancel' ? 'border-slate-400 bg-slate-400' : step.tone === 'alert' ? 'border-red-400 bg-red-400' : 'border-emerald-400 bg-emerald-400';
                    return (
                      <li key={step.key} className="relative flex gap-3 pb-3 last:pb-0">
                        {index < list.length - 1 && <span className="absolute left-[5px] top-3 h-full w-px bg-slate-700" aria-hidden="true" />}
                        <span className={`relative mt-1 h-[11px] w-[11px] shrink-0 rounded-full border-2 ${dot}`} aria-hidden="true" />
                        <div className="flex flex-1 items-baseline justify-between gap-3">
                          <span className={reached ? 'font-medium text-slate-100' : 'text-slate-500'}>{step.label}</span>
                          <span className={reached ? 'text-[11px] text-slate-400' : 'text-[11px] text-slate-600'}>{reached ? formatTimestamp(step.at) : 'Pending'}</span>
                        </div>
                      </li>
                    );
                  })}
                </ol>
              </div>

              {/* Allowed DAPH Action Controls */}
              <div className="pt-2 border-t border-slate-800">
                {selectedRecord.status === FOLLOW_UP_STATUS.ISSUED ||
                selectedRecord.status === FOLLOW_UP_STATUS.ACKNOWLEDGED ||
                selectedRecord.status === FOLLOW_UP_STATUS.ACTION_IN_PROGRESS ? (
                  <button
                    type="button"
                    onClick={() => setCancelModalRecord(selectedRecord)}
                    className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-2.5 font-semibold text-red-300 transition hover:bg-red-500/20 hover:text-red-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                  >
                    <span className="material-symbols-outlined text-base" aria-hidden="true">cancel</span>
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
          <div className="bg-slate-800/40 rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-800 space-y-4">
            <div className="flex items-center space-x-2 text-red-400 border-b border-slate-800 pb-3">
              <span className="material-symbols-outlined text-2xl" aria-hidden="true">warning</span>
              <h3 className="text-lg font-bold text-white">Confirm Cancellation</h3>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Are you sure you want to cancel operational follow-up instruction{' '}
              <strong className="font-mono text-white">{cancelModalRecord.follow_up_id}</strong>?
            </p>

            <div className="bg-slate-900/50 p-3 rounded-lg border border-slate-800 space-y-1 text-xs text-slate-300">
              <p><strong>Disease / District:</strong> {cancelModalRecord.disease} ({cancelModalRecord.district})</p>
              <p><strong>Assigned Vet:</strong> {officerName(cancelModalRecord.assigned_vet_id)}</p>
              <p><strong>Current Status:</strong> {cancelModalRecord.status} (v{cancelModalRecord.version})</p>
            </div>

            <p className="text-[11px] text-slate-500 italic">
              Notice: Cancellation updates the standalone operational record status to CANCELLED. It does not guarantee physical field action reversal or recall of issued instructions.
            </p>

            <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setCancelModalRecord(null)}
                disabled={isSubmittingCancel}
                className="px-4 py-2 text-xs font-medium text-slate-300 bg-slate-800/40 border border-slate-700 rounded-lg hover:bg-slate-900/50"
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
