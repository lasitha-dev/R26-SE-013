import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  enqueueNotificationBatch,
  getNotificationBatch,
  listNotificationBatches,
  listNotificationDeliveries,
  dispatchNotificationBatch,
  retryFailedNotificationDeliveries,
  cancelNotificationBatch,
  WORKFLOW_DELIVERY_STATUS,
  WORKFLOW_PROVIDER_STATUS,
} from '../../services/riskForecastingWorkflowApi';
import { validateViewerContext } from '../../contracts/viewerContext';

function sanitizeErrorMessage(err, defaultMsg) {
  if (!err) return defaultMsg;
  const msg = err.message || String(err);
  if (
    msg.includes('TypeError') ||
    msg.includes('ReferenceError') ||
    msg.includes('SyntaxError') ||
    msg.includes('at ') ||
    msg.includes('\\') ||
    msg.includes('://')
  ) {
    return defaultMsg;
  }
  return msg;
}

/**
 * SimulatedDeliveryPanel — Embedded panel for managing notification batch enqueuing,
 * explicit mock dispatch simulation, delivery item monitoring, and retry operations.
 *
 * Mandatory Domain Invariant:
 * Standalone mock simulation only. A successful result confirms mock provider execution;
 * it does not confirm that a farmer received or read a real notification.
 */
export function SimulatedDeliveryPanel({ advisory, viewerContext }) {
  const validation = validateViewerContext(viewerContext);
  const normalizedContext = validation.valid ? validation.normalizedContext : null;
  const vetId = normalizedContext?.userId || 'vet_officer_01';

  const [activeBatch, setActiveBatch] = useState(null);
  const [deliveries, setDeliveries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionPending, setActionPending] = useState(false);
  const [error, setError] = useState(null);
  const [infoMessage, setInfoMessage] = useState(null);

  const advisoryId = advisory?.advisory_id;
  const isApproved = advisory?.status === 'APPROVED';

  // Fetch active batch and deliveries for this advisory if approved
  const refreshBatchData = useCallback(async (batchId = null, signal = null) => {
    if (!advisoryId || !isApproved) return;

    try {
      setLoading(true);
      setError(null);

      let targetBatchId = batchId || activeBatch?.batch_id;

      if (!targetBatchId) {
        // Query existing batches for this advisory
        const response = await listNotificationBatches({ advisory_id: advisoryId }, { signal }).catch(() => null);
        const existingBatch = response?.batches?.[0];
        if (existingBatch && existingBatch.batch_id) {
          targetBatchId = existingBatch.batch_id;
          const fullBatch = await getNotificationBatch(targetBatchId, { signal }).catch(() => existingBatch);
          setActiveBatch(fullBatch);
        }
      } else {
        const updatedBatch = await getNotificationBatch(targetBatchId, { signal });
        setActiveBatch(updatedBatch);
      }

      if (targetBatchId) {
        const deliveryResp = await listNotificationDeliveries(targetBatchId, {}, { signal });
        setDeliveries(deliveryResp?.deliveries || []);
      }
    } catch (err) {
      setError(sanitizeErrorMessage(err, 'Failed to load simulated delivery data.'));
    } finally {
      setLoading(false);
    }
  }, [advisoryId, isApproved, activeBatch?.batch_id]);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    if (isApproved && advisoryId) {
      refreshBatchData(null, controller.signal).catch(() => {});
    }

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [advisoryId, isApproved]);

  // Action: Create/Enqueue Batch
  const handleEnqueueBatch = async () => {
    if (!advisoryId || !isApproved || actionPending) return;

    try {
      setActionPending(true);
      setError(null);
      setInfoMessage(null);

      const batch = await enqueueNotificationBatch(advisoryId, { created_by: vetId });
      setActiveBatch(batch);
      setInfoMessage(`Simulated notification batch enqueued (Batch ID: ${batch.batch_id}).`);

      const deliveryResp = await listNotificationDeliveries(batch.batch_id).catch(() => null);
      setDeliveries(deliveryResp?.deliveries || []);
    } catch (err) {
      setError(sanitizeErrorMessage(err, 'Failed to enqueue notification batch.'));
    } finally {
      setActionPending(false);
    }
  };

  // Action: Explicit Simulated Dispatch
  const handleDispatchBatch = async () => {
    if (!activeBatch?.batch_id || actionPending) return;

    try {
      setActionPending(true);
      setError(null);
      setInfoMessage(null);

      await dispatchNotificationBatch(activeBatch.batch_id);
      setInfoMessage('Simulation completed. Mock provider dispatch executed.');
      await refreshBatchData(activeBatch.batch_id);
    } catch (err) {
      setError(sanitizeErrorMessage(err, 'Failed to execute simulated notification dispatch.'));
    } finally {
      setActionPending(false);
    }
  };

  // Action: Retry Failed Deliveries
  const handleRetryFailed = async () => {
    if (!activeBatch?.batch_id || actionPending) return;

    try {
      setActionPending(true);
      setError(null);
      setInfoMessage(null);

      await retryFailedNotificationDeliveries(activeBatch.batch_id);
      setInfoMessage('Retry command sent for failed simulated deliveries.');
      await refreshBatchData(activeBatch.batch_id);
    } catch (err) {
      setError(sanitizeErrorMessage(err, 'Failed to retry notification deliveries.'));
    } finally {
      setActionPending(false);
    }
  };

  // Action: Cancel Pending Batch
  const handleCancelBatch = async () => {
    if (!activeBatch?.batch_id || actionPending) return;

    try {
      setActionPending(true);
      setError(null);
      setInfoMessage(null);

      const cancelled = await cancelNotificationBatch(activeBatch.batch_id);
      setActiveBatch(cancelled);
      setInfoMessage('Simulated notification batch cancelled.');
      await refreshBatchData(activeBatch.batch_id);
    } catch (err) {
      setError(sanitizeErrorMessage(err, 'Failed to cancel notification batch.'));
    } finally {
      setActionPending(false);
    }
  };

  if (!isApproved) {
    return (
      <div className="p-4 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 text-sm">
        <div className="flex items-center gap-2 mb-2 font-medium text-slate-300">
          <span className="material-symbols-outlined text-amber-400" aria-hidden="true">lock</span>
          <span>Simulated Delivery Enqueue Locked</span>
        </div>
        <p>
          Notification batches can only be enqueued and simulated for advisories in <strong className="text-emerald-400">APPROVED</strong> status. Please review and approve the advisory draft above first.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-5 rounded-xl bg-slate-900 border border-slate-800 text-slate-100">
      {/* Header & Mandatory Disclaimer */}
      <div>
        <div className="flex items-center justify-between gap-4 flex-wrap mb-2">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-emerald-400" aria-hidden="true">outbox</span>
            <h4 className="text-base font-semibold text-white">Embedded Simulated Delivery Panel</h4>
          </div>
          {activeBatch && (
            <span className="text-xs px-2.5 py-1 rounded font-mono bg-slate-800 text-emerald-300 border border-slate-700">
              Batch: {activeBatch.batch_id}
            </span>
          )}
        </div>

        {/* Mandatory Simulation Clarification Banner */}
        <div role="status" className="p-3 rounded-lg bg-amber-950/40 border border-amber-800/50 text-amber-200 text-xs flex items-start gap-2.5">
          <span className="material-symbols-outlined text-amber-400 shrink-0 text-base" aria-hidden="true">info</span>
          <div>
            <strong>Standalone simulation only.</strong> A successful result confirms mock provider execution; it does not confirm that a farmer received or read a real notification.
          </div>
        </div>
      </div>

      {/* Notifications / Alerts */}
      {error && (
        <div role="alert" className="p-3 rounded-lg bg-red-950/50 border border-red-800/60 text-red-200 text-sm flex items-center gap-2">
          <span className="material-symbols-outlined text-red-400 shrink-0" aria-hidden="true">error</span>
          <span>{error}</span>
        </div>
      )}

      {infoMessage && (
        <div role="status" className="p-3 rounded-lg bg-emerald-950/50 border border-emerald-800/60 text-emerald-200 text-sm flex items-center gap-2">
          <span className="material-symbols-outlined text-emerald-400 shrink-0" aria-hidden="true">check_circle</span>
          <span>{infoMessage}</span>
        </div>
      )}

      {/* Batch Controls */}
      {!activeBatch ? (
        <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 text-center space-y-3">
          <p className="text-sm text-slate-300">
            This advisory is approved and ready for simulated notification batch processing.
          </p>
          <button
            type="button"
            onClick={handleEnqueueBatch}
            disabled={actionPending || loading}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 transition-colors inline-flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-base" aria-hidden="true">queue_play_next</span>
            <span>Create Simulated Delivery Batch</span>
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Summary Stat Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center">
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
              <div className="text-xs text-slate-400">Total</div>
              <div className="text-lg font-semibold text-white">{activeBatch.recipient_count}</div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
              <div className="text-xs text-amber-400">Pending</div>
              <div className="text-lg font-semibold text-amber-300">{activeBatch.pending_count}</div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
              <div className="text-xs text-blue-400">Processing</div>
              <div className="text-lg font-semibold text-blue-300">{activeBatch.processing_count}</div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
              <div className="text-xs text-emerald-400">Simulated Success</div>
              <div className="text-lg font-semibold text-emerald-300">{activeBatch.succeeded_count}</div>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
              <div className="text-xs text-red-400">Failed</div>
              <div className="text-lg font-semibold text-red-300">{activeBatch.failed_count}</div>
            </div>
            {activeBatch.cancelled_count > 0 && (
              <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                <div className="text-xs text-slate-400">Cancelled</div>
                <div className="text-lg font-semibold text-slate-300">{activeBatch.cancelled_count}</div>
              </div>
            )}
          </div>

          {/* Action Buttons Toolbar */}
          <div className="flex items-center gap-3 flex-wrap pt-1">
            <button
              type="button"
              onClick={handleDispatchBatch}
              disabled={actionPending || loading || (activeBatch.pending_count === 0 && activeBatch.processing_count === 0)}
              className="px-3.5 py-1.5 rounded-lg text-sm font-medium bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 transition-colors inline-flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-base" aria-hidden="true">send</span>
              <span>Simulate Farmer Notification</span>
            </button>

            {activeBatch.failed_count > 0 && (
              <button
                type="button"
                onClick={handleRetryFailed}
                disabled={actionPending || loading}
                className="px-3.5 py-1.5 rounded-lg text-sm font-medium bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-50 transition-colors inline-flex items-center gap-1.5"
              >
                <span className="material-symbols-outlined text-base" aria-hidden="true">replay</span>
                <span>Retry Failed Simulated Deliveries</span>
              </button>
            )}

            {(activeBatch.status === 'QUEUED' || activeBatch.pending_count > 0) && (
              <button
                type="button"
                onClick={handleCancelBatch}
                disabled={actionPending || loading}
                className="px-3.5 py-1.5 rounded-lg text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 disabled:opacity-50 transition-colors inline-flex items-center gap-1.5"
              >
                <span className="material-symbols-outlined text-base" aria-hidden="true">cancel</span>
                <span>Cancel Pending Batch</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => refreshBatchData(activeBatch.batch_id)}
              disabled={loading || actionPending}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white bg-slate-950 border border-slate-800 hover:border-slate-700 transition-colors inline-flex items-center gap-1 ml-auto"
            >
              <span className="material-symbols-outlined text-sm" aria-hidden="true">refresh</span>
              <span>Refresh Status</span>
            </button>
          </div>

          {/* Delivery Items List */}
          {deliveries.length > 0 && (
            <div className="mt-3 space-y-2">
              <h5 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Simulated Delivery Recipients ({deliveries.length})
              </h5>
              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {deliveries.map((del) => {
                  const isSuccess = del.status === WORKFLOW_DELIVERY_STATUS.SUCCEEDED;
                  const isFailed = del.status === WORKFLOW_DELIVERY_STATUS.FAILED;
                  const isCancelled = del.status === WORKFLOW_DELIVERY_STATUS.CANCELLED;

                  let badgeStyle = 'bg-amber-950/60 text-amber-300 border-amber-800';
                  if (isSuccess) {
                    badgeStyle = 'bg-emerald-950/60 text-emerald-300 border-emerald-800';
                  } else if (isFailed) {
                    badgeStyle = 'bg-red-950/60 text-red-300 border-red-800';
                  } else if (isCancelled) {
                    badgeStyle = 'bg-slate-900 text-slate-400 border-slate-700';
                  }

                  return (
                    <div
                      key={del.delivery_id}
                      className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                    >
                      <div className="space-y-1">
                        <div className="font-mono text-slate-200 font-medium">{del.recipient_id}</div>
                        <div className="text-slate-400 truncate max-w-md">{del.resolved_message}</div>
                        {isFailed && del.last_error && (
                          <div className="text-red-400 font-mono text-[11px]">
                            Last Error: {del.last_error}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`px-2 py-0.5 rounded border text-[11px] font-mono ${badgeStyle}`}>
                          {isSuccess ? 'SIMULATED SUCCESS' : del.status}
                        </span>
                        {del.provider_reference && (
                          <span className="text-[11px] text-slate-500 font-mono">
                            Ref: {del.provider_reference}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

SimulatedDeliveryPanel.propTypes = {
  advisory: PropTypes.shape({
    advisory_id: PropTypes.string,
    status: PropTypes.string,
  }),
  viewerContext: PropTypes.object,
};
