import React, { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  validateViewerContext,
  getAuthorizedDistricts,
} from '../../contracts/viewerContext.js';
import { AccessContextUnavailable } from '../AccessContextUnavailable.jsx';
import {
  FOLLOW_UP_STATUS,
  OPERATIONAL_PRIORITY,
  listFollowUps,
  getFollowUp,
  acknowledgeFollowUp,
  startFollowUpAction,
  completeFollowUp,
  escalateFollowUp,
} from '../../services/riskForecastingWorkflowApi.js';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

/**
 * Sanitizes API error messages by redacting system paths, stack traces, database URLs, and bearer tokens.
 */
export function sanitizeErrorMessage(err) {
  if (!err) return 'An unexpected error occurred.';
  let raw = typeof err === 'string' ? err : err.message || err.detail || String(err);
  if (typeof raw !== 'string' || raw === '[object Object]') {
    raw = err.message || err.detail || 'An unexpected error occurred.';
  }

  raw = raw
    .replace(/(?:[a-zA-Z]:\\[^\s:]+|\/[^\s:]+\/[^\s:]+)/g, '<redacted_path>')
    .replace(/(?:mongodb|postgres|mysql|sqlite):\/\/[^\s]+/gi, '<redacted_db_url>')
    .replace(/(?:Bearer\s+[A-Za-z0-9._~+/-]+=*|Authorization:\s*[^\s]+)/gi, '<redacted_credentials>')
    .replace(/Traceback \(most recent call last\):[\s\S]*/gi, '')
    .replace(/at\s+[\w.<>]+\s+\([^)]+\)/g, '')
    .replace(/\[object Object\]/g, 'An unexpected error occurred.');

  return raw.trim() || 'An operational error occurred. Please retry.';
}

function getPriorityBadge(priority) {
  const norm = (priority || '').toUpperCase();
  switch (norm) {
    case OPERATIONAL_PRIORITY.HIGH:
      return { label: 'HIGH', class: 'bg-rose-500/20 text-rose-300 border-rose-500/40' };
    case OPERATIONAL_PRIORITY.MEDIUM:
      return { label: 'MEDIUM', class: 'bg-amber-500/20 text-amber-300 border-amber-500/40' };
    case OPERATIONAL_PRIORITY.LOW:
      return { label: 'LOW', class: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' };
    default:
      return { label: norm || 'N/A', class: 'bg-surface-container-high text-on-surface-variant border-outline-variant/40' };
  }
}

function getStatusBadge(status) {
  const norm = (status || '').toUpperCase();
  switch (norm) {
    case FOLLOW_UP_STATUS.ISSUED:
      return { label: 'ISSUED', class: 'bg-sky-500/20 text-sky-300 border-sky-500/40' };
    case FOLLOW_UP_STATUS.ACKNOWLEDGED:
      return { label: 'ACKNOWLEDGED', class: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40' };
    case FOLLOW_UP_STATUS.ACTION_IN_PROGRESS:
      return { label: 'IN PROGRESS', class: 'bg-amber-500/20 text-amber-300 border-amber-500/40' };
    case FOLLOW_UP_STATUS.COMPLETED:
      return { label: 'COMPLETED', class: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' };
    case FOLLOW_UP_STATUS.CANCELLED:
      return { label: 'CANCELLED', class: 'bg-slate-500/20 text-slate-400 border-slate-500/40' };
    case FOLLOW_UP_STATUS.ESCALATED:
      return { label: 'ESCALATED', class: 'bg-rose-500/20 text-rose-300 border-rose-500/40' };
    default:
      return { label: norm || 'UNKNOWN', class: 'bg-surface-container-high text-on-surface-variant border-outline-variant/40' };
  }
}

function formatProbability(val) {
  if (val === undefined || val === null || val === '') return 'N/A';
  if (typeof val === 'number') {
    return `${val.toFixed(1)}%`;
  }
  if (typeof val === 'string' && val.trim() !== '') {
    const parsed = parseFloat(val);
    return isNaN(parsed) ? val : `${parsed.toFixed(1)}%`;
  }
  return 'N/A';
}

function formatTimestamp(isoStr) {
  if (!isoStr) return 'N/A';
  try {
    const dt = new Date(isoStr);
    return isNaN(dt.getTime()) ? isoStr : dt.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
  } catch (_) {
    return isoStr;
  }
}

/**
 * Veterinary Officer Assigned Follow-Ups Workspace.
 * Allows Veterinary Officers to query, view, and transition DAPH-issued follow-up tasks.
 */
export function VeterinaryAssignedFollowUps({ viewerContext }) {
  // 1. Fail-Closed Context Validation
  const validation = React.useMemo(() => validateViewerContext(viewerContext), [viewerContext]);
  const isValidVet =
    validation.valid &&
    validation.normalizedContext &&
    validation.normalizedContext.role === ROLES.VETERINARY_OFFICER &&
    Boolean(validation.normalizedContext.userId);

  const actorId = isValidVet ? validation.normalizedContext.userId : null;
  const actorContext = isValidVet ? validation.normalizedContext : null;
  const authorizedDistricts = isValidVet ? getAuthorizedDistricts(viewerContext) : [];

  // 2. Component State
  const [followUps, setFollowUps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [diseaseFilter, setDiseaseFilter] = useState('ALL');
  const [districtFilter, setDistrictFilter] = useState('ALL');

  // Selected Detail Record
  const [selectedRecord, setSelectedRecord] = useState(null);

  // Dialog State
  const [activeActionModal, setActiveActionModal] = useState(null); // 'ACKNOWLEDGE' | 'START' | 'COMPLETE' | 'ESCALATE' | null
  const [escalationReason, setEscalationReason] = useState('');
  const [escalationReasonError, setEscalationReasonError] = useState(null);

  // Submission State
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [concurrencyConflict, setConcurrencyConflict] = useState(false);
  const [actionSuccessNotice, setActionSuccessNotice] = useState(null);

  // 3. Fetch Follow-Ups Scoped to Authenticated Vet
  const activeRequestRef = useRef(null);

  const fetchFollowUps = useCallback(async () => {
    if (!isValidVet || !actorId || !actorContext) return;

    if (activeRequestRef.current) {
      activeRequestRef.current.isActive = false;
      activeRequestRef.current.controller.abort();
    }

    const controller = new AbortController();
    const currentRequest = { controller, isActive: true };
    activeRequestRef.current = currentRequest;

    setLoading(true);
    setApiError(null);

    try {
      const filters = {
        assigned_vet_id: actorId,
      };
      if (statusFilter !== 'ALL') filters.status = statusFilter;
      if (diseaseFilter !== 'ALL') filters.disease = diseaseFilter;
      if (districtFilter !== 'ALL') filters.district = districtFilter;

      const res = await listFollowUps(filters, {
        actorContext,
        signal: controller.signal,
      });

      if (!currentRequest.isActive || controller.signal.aborted) return;

      const records = res?.follow_ups || res?.records || (Array.isArray(res) ? res : []);
      setFollowUps(records);
      setApiError(null);
    } catch (err) {
      if (!currentRequest.isActive || controller.signal.aborted) return;
      if (err.name === 'AbortError' || (err.message && err.message.includes('aborted without reason'))) return;

      setApiError(sanitizeErrorMessage(err));
    } finally {
      if (currentRequest.isActive && !controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [isValidVet, actorId, actorContext, statusFilter, diseaseFilter, districtFilter]);

  useEffect(() => {
    if (isValidVet) {
      fetchFollowUps();
    }
    return () => {
      if (activeRequestRef.current) {
        activeRequestRef.current.isActive = false;
        activeRequestRef.current.controller.abort();
        activeRequestRef.current = null;
      }
    };
  }, [isValidVet, fetchFollowUps]);

  // Keep selected record updated when followUps list re-fetches
  useEffect(() => {
    if (selectedRecord && followUps.length > 0) {
      const updated = followUps.find((item) => item.follow_up_id === selectedRecord.follow_up_id);
      if (updated) {
        setSelectedRecord(updated);
      }
    }
  }, [followUps, selectedRecord]);

  if (!isValidVet) {
    return (
      <AccessContextUnavailable
        reason={
          validation.reason ||
          'VETERINARY_OFFICER role with a valid authenticated identity (userId) is required.'
        }
      />
    );
  }

  // Calculate Summary Counts
  const totalAssigned = followUps.length;
  const awaitingAck = followUps.filter((item) => item.status === FOLLOW_UP_STATUS.ISSUED).length;
  const inProgress = followUps.filter(
    (item) => item.status === FOLLOW_UP_STATUS.ACKNOWLEDGED || item.status === FOLLOW_UP_STATUS.ACTION_IN_PROGRESS
  ).length;
  const completedCount = followUps.filter((item) => item.status === FOLLOW_UP_STATUS.COMPLETED).length;
  const escalatedCount = followUps.filter((item) => item.status === FOLLOW_UP_STATUS.ESCALATED).length;

  const handleResetFilters = () => {
    setStatusFilter('ALL');
    setDiseaseFilter('ALL');
    setDistrictFilter('ALL');
  };

  const handleOpenActionModal = (modalType) => {
    setActionError(null);
    setConcurrencyConflict(false);
    setActionSuccessNotice(null);
    if (modalType === 'ESCALATE') {
      setEscalationReason('');
      setEscalationReasonError(null);
    }
    setActiveActionModal(modalType);
  };

  const handleCloseModal = () => {
    if (submitting) return;
    setActiveActionModal(null);
    setEscalationReasonError(null);
  };

  // Single Refresh for Concurrency Conflict
  const handleRefreshSingleRecord = async () => {
    if (!selectedRecord) return;
    setLoading(true);
    setActionError(null);
    try {
      const fresh = await getFollowUp(selectedRecord.follow_up_id, {
        actorContext: validation.normalizedContext,
      });
      if (fresh) {
        setSelectedRecord(fresh);
        setConcurrencyConflict(false);
        setActionSuccessNotice('Refreshed authoritative follow-up record.');
        fetchFollowUps();
      }
    } catch (err) {
      setActionError(sanitizeErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  // Transition Action Handlers
  const handleExecuteTransition = async (actionType) => {
    if (submitting || !selectedRecord) return;

    if (actionType === 'ESCALATE') {
      const trimmed = escalationReason.trim();
      if (trimmed.length < 5) {
        setEscalationReasonError('Escalation reason must be at least 5 characters long.');
        return;
      }
      setEscalationReasonError(null);
    }

    setSubmitting(true);
    setActionError(null);
    setConcurrencyConflict(false);
    setActionSuccessNotice(null);

    const followUpId = selectedRecord.follow_up_id;
    const version = selectedRecord.version;

    try {
      let updated = null;
      if (actionType === 'ACKNOWLEDGE') {
        updated = await acknowledgeFollowUp(followUpId, {
          version,
          actorContext: validation.normalizedContext,
        });
      } else if (actionType === 'START') {
        updated = await startFollowUpAction(followUpId, {
          version,
          actorContext: validation.normalizedContext,
        });
      } else if (actionType === 'COMPLETE') {
        updated = await completeFollowUp(followUpId, {
          version,
          actorContext: validation.normalizedContext,
        });
      } else if (actionType === 'ESCALATE') {
        updated = await escalateFollowUp(followUpId, {
          version,
          reason: escalationReason.trim(),
          actorContext: validation.normalizedContext,
        });
      }

      if (updated) {
        setSelectedRecord(updated);
        setActiveActionModal(null);
        setActionSuccessNotice(`Follow-up successfully updated to status ${updated.status}.`);
        fetchFollowUps();
      }
    } catch (err) {
      const is409 = err.status === 409 || (err.message && err.message.includes('409'));
      if (is409) {
        setConcurrencyConflict(true);
        setActionError('Conflict Detected (409): This follow-up record was updated by another transaction.');
      } else {
        setActionError(sanitizeErrorMessage(err));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const renderScientificSnapshot = (record) => {
    const probabilityVal = record.probability_pct ?? (record.probability != null ? record.probability * 100 : undefined);
    const priorityBadge = getPriorityBadge(record.operational_priority);
    const statusBadge = getStatusBadge(record.status);

    return (
      <div className="p-4 rounded-xl bg-surface-container-high/70 border border-outline-variant/40 space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold text-primary uppercase tracking-wider flex items-center gap-1.5">
            <span className="material-symbols-outlined text-sm" aria-hidden="true">
              analytics
            </span>
            <span>Immutable Scientific Forecast Snapshot</span>
          </h4>
          <span className="text-[11px] font-semibold text-on-surface-variant">Read-Only</span>
        </div>

        <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
          <div>
            <dt className="text-on-surface-variant">Disease:</dt>
            <dd className="font-bold text-on-surface">{record.disease || 'N/A'}</dd>
          </div>
          <div>
            <dt className="text-on-surface-variant">District:</dt>
            <dd className="font-bold text-on-surface">{record.district || 'N/A'}</dd>
          </div>
          <div>
            <dt className="text-on-surface-variant">Target Period:</dt>
            <dd className="font-bold text-on-surface">
              {record.target_month ? MONTH_NAMES[record.target_month - 1] : ''} {record.target_year || 'N/A'}
            </dd>
          </div>
          <div>
            <dt className="text-on-surface-variant">Risk Level:</dt>
            <dd className="font-bold text-on-surface">{record.forecast_risk_level || record.risk_level || 'N/A'}</dd>
          </div>
          <div>
            <dt className="text-on-surface-variant">Risk Probability:</dt>
            <dd className="font-extrabold text-primary">{formatProbability(probabilityVal)}</dd>
          </div>
          <div>
            <dt className="text-on-surface-variant">Predicted Severity:</dt>
            <dd className="font-semibold text-on-surface">{record.predicted_severity || 'N/A'}</dd>
          </div>
        </dl>

        {record.fallback_applied && (
          <div className="text-xs text-on-surface-variant italic mt-2">
            Historical proxy data used
          </div>
        )}
      </div>
    );
  };

  const renderActionControls = (record) => {
    const status = (record.status || '').toUpperCase();

    if (status === FOLLOW_UP_STATUS.COMPLETED) {
      return (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs text-emerald-300 flex items-center gap-2 font-medium">
          <span className="material-symbols-outlined text-sm" aria-hidden="true">
            check_circle
          </span>
          <span>Task marked complete. No further state transitions available.</span>
        </div>
      );
    }

    if (status === FOLLOW_UP_STATUS.CANCELLED) {
      return (
        <div className="p-3 bg-slate-500/10 border border-slate-500/30 rounded-xl text-xs text-slate-300 flex items-center gap-2 font-medium">
          <span className="material-symbols-outlined text-sm" aria-hidden="true">
            cancel
          </span>
          <span>Task cancelled by DAPH. No further state transitions available.</span>
        </div>
      );
    }

    if (status === FOLLOW_UP_STATUS.ESCALATED) {
      return (
        <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300 flex items-center gap-2 font-medium">
          <span className="material-symbols-outlined text-sm" aria-hidden="true">
            error
          </span>
          <span>Task escalated for higher-level departmental attention. No further state transitions available.</span>
        </div>
      );
    }

    return (
      <div className="flex flex-wrap items-center gap-3">
        {status === FOLLOW_UP_STATUS.ISSUED && (
          <button
            type="button"
            onClick={() => handleOpenActionModal('ACKNOWLEDGE')}
            disabled={submitting}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl min-h-[40px] focus:outline-none focus:ring-2 focus:ring-indigo-400 transition-all flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-sm" aria-hidden="true">
              mark_email_read
            </span>
            <span>Acknowledge</span>
          </button>
        )}

        {status === FOLLOW_UP_STATUS.ACKNOWLEDGED && (
          <button
            type="button"
            onClick={() => handleOpenActionModal('START')}
            disabled={submitting}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded-xl min-h-[40px] focus:outline-none focus:ring-2 focus:ring-amber-400 transition-all flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-sm" aria-hidden="true">
              play_arrow
            </span>
            <span>Start Action</span>
          </button>
        )}

        {status === FOLLOW_UP_STATUS.ACTION_IN_PROGRESS && (
          <button
            type="button"
            onClick={() => handleOpenActionModal('COMPLETE')}
            disabled={submitting}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl min-h-[40px] focus:outline-none focus:ring-2 focus:ring-emerald-400 transition-all flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-sm" aria-hidden="true">
              task_alt
            </span>
            <span>Complete</span>
          </button>
        )}

        <button
          type="button"
          onClick={() => handleOpenActionModal('ESCALATE')}
          disabled={submitting}
          className="px-4 py-2 bg-rose-600/20 border border-rose-500/40 hover:bg-rose-600/30 text-rose-300 text-xs font-semibold rounded-xl min-h-[40px] focus:outline-none focus:ring-2 focus:ring-rose-400 transition-all flex items-center gap-1.5"
        >
          <span className="material-symbols-outlined text-sm" aria-hidden="true">
            priority_high
          </span>
          <span>Escalate</span>
        </button>
      </div>
    );
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-on-surface">
      {/* Page Header */}
      <header className="bg-surface-container p-6 rounded-2xl border border-outline-variant/30 shadow-xl space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-primary tracking-tight flex items-center gap-2">
              <span className="material-symbols-outlined text-2xl" aria-hidden="true">
                assignment_turned_in
              </span>
              <span>Assigned Follow-Ups</span>
            </h1>
            <p className="text-sm text-on-surface-variant">
              DAPH-Issued Operational Follow-Up Tasks — Assigned to Veterinary Officer
              {actorContext?.name ? ` ${actorContext.name}` : ''}
              {authorizedDistricts.length > 0 ? ` (${authorizedDistricts[0]})` : ''}
            </p>
          </div>
        </div>
      </header>

      {/* Live Region for Screen Readers */}
      <div role="status" aria-live="polite" className="sr-only">
        {loading && 'Loading assigned follow-ups…'}
        {submitting && 'Submitting follow-up state transition…'}
        {actionSuccessNotice && actionSuccessNotice}
      </div>

      {/* API Error Notification */}
      {apiError && (
        <div role="alert" className="p-4 bg-error-container/20 border border-error/30 rounded-xl text-error text-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
              error
            </span>
            <span>{apiError}</span>
          </div>
          <button
            type="button"
            onClick={() => fetchFollowUps()}
            className="px-3 py-1 bg-error/20 hover:bg-error/30 border border-error/40 text-error text-xs font-semibold rounded-lg shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* Action Success Notification */}
      {actionSuccessNotice && (
        <div role="status" className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-300 text-sm flex items-center gap-3">
          <span className="material-symbols-outlined text-xl shrink-0" aria-hidden="true">
            check_circle
          </span>
          <span>{actionSuccessNotice}</span>
        </div>
      )}

      {/* Summary Cards Grid */}
      <section aria-label="Follow-Up Summary Statistics" className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
        <div className="p-4 rounded-xl bg-surface-container border border-outline-variant/30 shadow-md space-y-1">
          <span className="text-xs text-on-surface-variant font-medium block">Total Assigned</span>
          <span className="text-2xl font-extrabold text-on-surface">{totalAssigned}</span>
        </div>
        <div className="p-4 rounded-xl bg-surface-container border border-outline-variant/30 shadow-md space-y-1">
          <span className="text-xs text-sky-400 font-medium block">Awaiting Ack (ISSUED)</span>
          <span className="text-2xl font-extrabold text-sky-300">{awaitingAck}</span>
        </div>
        <div className="p-4 rounded-xl bg-surface-container border border-outline-variant/30 shadow-md space-y-1">
          <span className="text-xs text-amber-400 font-medium block">In Progress</span>
          <span className="text-2xl font-extrabold text-amber-300">{inProgress}</span>
        </div>
        <div className="p-4 rounded-xl bg-surface-container border border-outline-variant/30 shadow-md space-y-1">
          <span className="text-xs text-emerald-400 font-medium block">Completed</span>
          <span className="text-2xl font-extrabold text-emerald-300">{completedCount}</span>
        </div>
        <div className="p-4 rounded-xl bg-surface-container border border-outline-variant/30 shadow-md space-y-1 col-span-2 sm:col-span-1">
          <span className="text-xs text-rose-400 font-medium block">Escalated</span>
          <span className="text-2xl font-extrabold text-rose-300">{escalatedCount}</span>
        </div>
      </section>

      {/* Filter Bar */}
      <section aria-label="Follow-Up Filters" className="p-4 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            {/* Status Filter */}
            <div className="space-y-1">
              <label htmlFor="filter-status" className="text-xs font-semibold text-on-surface-variant block">
                Status
              </label>
              <select
                id="filter-status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-1.5 rounded-xl bg-surface-container-high border border-outline-variant/40 text-xs text-on-surface focus:outline-none focus:ring-2 focus:ring-emerald-400 min-h-[36px]"
              >
                <option value="ALL">All Statuses</option>
                <option value={FOLLOW_UP_STATUS.ISSUED}>ISSUED</option>
                <option value={FOLLOW_UP_STATUS.ACKNOWLEDGED}>ACKNOWLEDGED</option>
                <option value={FOLLOW_UP_STATUS.ACTION_IN_PROGRESS}>ACTION_IN_PROGRESS</option>
                <option value={FOLLOW_UP_STATUS.COMPLETED}>COMPLETED</option>
                <option value={FOLLOW_UP_STATUS.CANCELLED}>CANCELLED</option>
                <option value={FOLLOW_UP_STATUS.ESCALATED}>ESCALATED</option>
              </select>
            </div>

            {/* Disease Filter */}
            <div className="space-y-1">
              <label htmlFor="filter-disease" className="text-xs font-semibold text-on-surface-variant block">
                Disease
              </label>
              <select
                id="filter-disease"
                value={diseaseFilter}
                onChange={(e) => setDiseaseFilter(e.target.value)}
                className="px-3 py-1.5 rounded-xl bg-surface-container-high border border-outline-variant/40 text-xs text-on-surface focus:outline-none focus:ring-2 focus:ring-emerald-400 min-h-[36px]"
              >
                <option value="ALL">All Diseases</option>
                <option value="FMD">FMD</option>
                <option value="LSD">LSD</option>
              </select>
            </div>

            {/* District Filter (Rendered if Vet has > 1 Authorized District) */}
            {authorizedDistricts.length > 1 && (
              <div className="space-y-1">
                <label htmlFor="filter-district" className="text-xs font-semibold text-on-surface-variant block">
                  District
                </label>
                <select
                  id="filter-district"
                  value={districtFilter}
                  onChange={(e) => setDistrictFilter(e.target.value)}
                  className="px-3 py-1.5 rounded-xl bg-surface-container-high border border-outline-variant/40 text-xs text-on-surface focus:outline-none focus:ring-2 focus:ring-emerald-400 min-h-[36px]"
                >
                  <option value="ALL">All Authorized Districts</option>
                  {authorizedDistricts.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 pt-4 sm:pt-0">
            <button
              type="button"
              onClick={handleResetFilters}
              className="px-3 py-1.5 bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant/40 text-xs font-semibold text-on-surface-variant rounded-xl min-h-[36px]"
            >
              Reset Filters
            </button>
            <button
              type="button"
              onClick={() => fetchFollowUps()}
              disabled={loading}
              className="px-3 py-1.5 bg-primary-container text-on-primary hover:brightness-110 border border-outline-variant/40 text-xs font-semibold rounded-xl min-h-[36px] flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-sm" aria-hidden="true">
                refresh
              </span>
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </section>

      {/* Main Content Layout (Table & Detail Modal) */}
      <div className="space-y-6">
        {/* Follow-Up List Table */}
        <section
          aria-label="Follow-Up Tasks List"
          className="bg-surface-container rounded-2xl border border-outline-variant/30 shadow-xl overflow-hidden"
        >
          {loading ? (
            <div className="p-8 text-center text-sm text-on-surface-variant space-y-3">
              <span className="material-symbols-outlined text-3xl animate-spin text-primary" aria-hidden="true">
                sync
              </span>
              <p>Loading assigned follow-ups…</p>
            </div>
          ) : followUps.length === 0 ? (
            <div className="p-12 text-center text-sm text-on-surface-variant space-y-3">
              <span className="material-symbols-outlined text-4xl text-on-surface-variant/50" aria-hidden="true">
                assignment_turned_in
              </span>
              <h3 className="text-base font-semibold text-on-surface">No Assigned Follow-Ups Found</h3>
              <p className="max-w-md mx-auto text-xs text-on-surface-variant/80">
                No DAPH operational follow-up tasks match the selected filter criteria for officer {actorId}.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-surface-container-high border-b border-outline-variant/30 text-on-surface-variant font-semibold">
                    <th className="p-3">Disease / District</th>
                    <th className="p-3">Target Period</th>
                    <th className="p-3">Priority</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Instruction Summary</th>
                    <th className="p-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant/20">
                  {followUps.map((item) => {
                    const priorityBadge = getPriorityBadge(item.operational_priority);
                    const statusBadge = getStatusBadge(item.status);
                    const isSelected = selectedRecord && selectedRecord.follow_up_id === item.follow_up_id;

                    return (
                      <tr
                        key={item.follow_up_id}
                        className={`hover:bg-surface-container-high/40 transition-colors ${
                          isSelected ? 'bg-primary-container/10 font-medium' : ''
                        }`}
                      >
                        <td className="p-3">
                          <div className="font-bold text-on-surface">{item.disease}</div>
                          <div className="text-[11px] text-on-surface-variant flex items-center gap-1.5">
                            <span>{item.district}</span>
                          </div>
                        </td>
                        <td className="p-3 text-on-surface">
                          {item.target_month ? MONTH_NAMES[item.target_month - 1] : ''} {item.target_year}
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded-md border text-[10px] font-bold ${priorityBadge.class}`}>
                            {priorityBadge.label}
                          </span>
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded-md border text-[10px] font-bold ${statusBadge.class}`}>
                            {statusBadge.label}
                          </span>
                        </td>
                        <td className="p-3 max-w-xs truncate text-on-surface-variant">
                          {item.instruction_summary}
                        </td>
                        <td className="p-3 text-right">
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedRecord(item);
                              setActionError(null);
                              setConcurrencyConflict(false);
                              setActionSuccessNotice(null);
                            }}
                            className="px-3 py-1 bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant/40 text-on-surface font-semibold text-xs rounded-lg transition-all"
                          >
                            View Details
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Detail Modal */}
        {selectedRecord && (
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="follow-up-detail-heading"
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <div className="bg-surface-container rounded-2xl border border-outline-variant/40 shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden text-on-surface">
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-outline-variant/30 shrink-0">
                <h3 id="follow-up-detail-heading" className="text-lg font-bold flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">
                    assignment
                  </span>
                  <span>Follow-Up Details</span>
                </h3>
                <button
                  type="button"
                  onClick={() => setSelectedRecord(null)}
                  className="p-1.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-on-surface-variant transition-colors"
                  aria-label="Close detail modal"
                >
                  <span className="material-symbols-outlined text-sm" aria-hidden="true">
                    close
                  </span>
                </button>
              </div>

              {/* Scrollable Content */}
              <div className="p-6 overflow-y-auto space-y-5">
                {/* Status & Priority Badges */}
                <div className="flex items-center gap-3">
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase block font-semibold">Status</span>
                    <span className={`px-2.5 py-1 rounded-lg border text-xs font-extrabold ${getStatusBadge(selectedRecord.status).class}`}>
                    {getStatusBadge(selectedRecord.status).label}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-on-surface-variant uppercase block font-semibold">Priority</span>
                  <span className={`px-2.5 py-1 rounded-lg border text-xs font-extrabold ${getPriorityBadge(selectedRecord.operational_priority).class}`}>
                    {getPriorityBadge(selectedRecord.operational_priority).label}
                  </span>
                </div>
              </div>

              {/* DAPH Instruction */}
              <div className="space-y-1">
                <span className="text-xs font-bold text-on-surface block">DAPH Instruction:</span>
                <div className="p-3 bg-surface-container-high/60 border border-outline-variant/30 rounded-xl text-xs text-on-surface leading-relaxed">
                  {selectedRecord.instruction_summary}
                </div>
              </div>

              {/* Scientific Snapshot */}
              {renderScientificSnapshot(selectedRecord)}

              {/* Operational & Identity Metadata */}
              <dl className="grid grid-cols-2 gap-2 text-xs border-t border-outline-variant/30 pt-3">
                <div>
                  <dt className="text-on-surface-variant">Assigned Vet:</dt>
                  <dd className="text-on-surface font-semibold">
                    {actorContext?.name || 'Veterinary Officer'}
                    {authorizedDistricts.length > 0 ? ` — ${authorizedDistricts[0]}` : ''}
                  </dd>
                </div>
              </dl>

              {/* Status Timeline */}
              <div className="space-y-2 border-t border-outline-variant/30 pt-3 text-xs">
                <span className="font-bold text-on-surface block">Lifecycle Timeline:</span>
                <ul className="space-y-1 text-on-surface-variant text-[11px]">
                  <li>Created: <strong className="text-on-surface">{formatTimestamp(selectedRecord.created_at)}</strong></li>
                  {selectedRecord.acknowledged_at && (
                    <li>Acknowledged: <strong className="text-on-surface">{formatTimestamp(selectedRecord.acknowledged_at)}</strong></li>
                  )}
                  {selectedRecord.action_started_at && (
                    <li>Action Started: <strong className="text-on-surface">{formatTimestamp(selectedRecord.action_started_at)}</strong></li>
                  )}
                  {selectedRecord.completed_at && (
                    <li>Completed: <strong className="text-on-surface">{formatTimestamp(selectedRecord.completed_at)}</strong></li>
                  )}
                  {selectedRecord.escalated_at && (
                    <li>Escalated: <strong className="text-on-surface">{formatTimestamp(selectedRecord.escalated_at)}</strong></li>
                  )}
                </ul>
                {selectedRecord.escalation_reason && (
                  <div className="p-2.5 bg-rose-500/10 border border-rose-500/30 rounded-lg text-[11px] text-rose-300 space-y-0.5">
                    <span className="font-bold block">Escalation Reason:</span>
                    <p>{selectedRecord.escalation_reason}</p>
                  </div>
                )}
              </div>

              {/* Concurrency Error Banner */}
              {concurrencyConflict && (
                <div role="alert" className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-300 text-xs space-y-2">
                  <p className="font-bold">Conflict Detected (409)</p>
                  <p>This follow-up record was updated by another transaction. Please refresh to view latest state.</p>
                  <button
                    type="button"
                    onClick={handleRefreshSingleRecord}
                    className="px-3 py-1 bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 font-bold text-xs rounded-lg"
                  >
                    Refresh Follow-Up
                  </button>
                </div>
              )}

              {/* Action Error Banner */}
              {actionError && !concurrencyConflict && (
                <div role="alert" className="p-3 bg-error-container/20 border border-error/30 rounded-xl text-error text-xs">
                  {actionError}
                </div>
              )}
              </div>

              {/* Footer / Action Buttons */}
              <div className="p-6 border-t border-outline-variant/30 shrink-0 bg-surface-container-low">
                {renderActionControls(selectedRecord)}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Confirmation & Escalation Modals */}
      {activeActionModal && selectedRecord && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
        >
          <div className="bg-surface-container p-6 rounded-2xl border border-outline-variant/40 shadow-2xl max-w-md w-full space-y-4 text-on-surface">
            <h3 id="modal-title" className="text-lg font-bold text-on-surface flex items-center gap-2">
              <span className="material-symbols-outlined text-primary" aria-hidden="true">
                {activeActionModal === 'ESCALATE' ? 'priority_high' : 'task_alt'}
              </span>
              <span>
                {activeActionModal === 'ACKNOWLEDGE' && 'Confirm Acknowledgement'}
                {activeActionModal === 'START' && 'Confirm Start Action'}
                {activeActionModal === 'COMPLETE' && 'Confirm Complete Action'}
                {activeActionModal === 'ESCALATE' && 'Escalate Follow-Up Task'}
              </span>
            </h3>

            {activeActionModal === 'ACKNOWLEDGE' && (
              <p className="text-xs text-on-surface-variant leading-relaxed">
                Recording acknowledgement registers that officer <strong className="text-on-surface">{actorId}</strong> has received this DAPH operational follow-up instruction in the standalone workflow.
              </p>
            )}

            {activeActionModal === 'START' && (
              <p className="text-xs text-on-surface-variant leading-relaxed">
                Marking action as started transitions follow-up status to <strong className="text-amber-300">ACTION_IN_PROGRESS</strong>.
              </p>
            )}

            {activeActionModal === 'COMPLETE' && (
              <div className="space-y-2">
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  Marking assigned follow-up task as complete records digital operational task completion in the Risk Forecasting subsystem.
                </p>
                <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-[11px] text-emerald-300">
                  <strong>Notice:</strong> Completing this task records workflow completion. It does not claim disease eradication or farmer notification.
                </div>
              </div>
            )}

            {activeActionModal === 'ESCALATE' && (
              <div className="space-y-3">
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  Escalating this follow-up transitions status to <strong className="text-rose-300">ESCALATED</strong> for higher-level departmental attention. This is a terminal transition.
                </p>

                <div className="space-y-1">
                  <label htmlFor="escalation-reason-input" className="text-xs font-bold text-on-surface block">
                    Reason for Escalation (Minimum 5 characters):
                  </label>
                  <textarea
                    id="escalation-reason-input"
                    rows={3}
                    value={escalationReason}
                    onChange={(e) => setEscalationReason(e.target.value)}
                    placeholder="Enter explicit operational reason for escalation..."
                    className="w-full p-2.5 rounded-xl bg-surface-container-high border border-outline-variant/40 text-xs text-on-surface focus:outline-none focus:ring-2 focus:ring-rose-400"
                  />
                  {escalationReasonError && (
                    <p className="text-[11px] text-error font-semibold">{escalationReasonError}</p>
                  )}
                </div>
              </div>
            )}

            <div className="flex items-center justify-end gap-3 border-t border-outline-variant/30 pt-4">
              <button
                type="button"
                onClick={handleCloseModal}
                disabled={submitting}
                className="px-4 py-2 bg-surface-container-high hover:bg-surface-container-highest text-on-surface text-xs font-semibold rounded-xl min-h-[40px]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleExecuteTransition(activeActionModal)}
                disabled={submitting}
                className={`px-4 py-2 text-white text-xs font-semibold rounded-xl min-h-[40px] flex items-center gap-1.5 ${
                  activeActionModal === 'ESCALATE'
                    ? 'bg-rose-600 hover:bg-rose-500'
                    : activeActionModal === 'COMPLETE'
                    ? 'bg-emerald-600 hover:bg-emerald-500'
                    : 'bg-primary hover:bg-primary-container'
                }`}
              >
                {submitting ? 'Submitting…' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

VeterinaryAssignedFollowUps.propTypes = {
  viewerContext: PropTypes.object,
};
