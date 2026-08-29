import React, { useState, useEffect, useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  validateViewerContext,
} from '../../contracts/viewerContext';
import { AccessContextUnavailable } from '../AccessContextUnavailable';
import {
  listForecastRecords,
  listAssignedRecipients,
  createAdvisoryDraft,
  updateAdvisoryDraft,
  previewAdvisory,
  markAdvisoryReadyForReview,
  approveAdvisory,
  cancelAdvisory,
  getAdvisory,
  forwardToAssignedFarmers,
} from '../../services/riskForecastingWorkflowApi';
import { SimulatedDeliveryPanel } from './SimulatedDeliveryPanel';

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
 * VeterinaryAdvisoryCentre — Step-based Veterinary Officer Advisory Centre.
 *
 * Workflow Steps:
 * Step 1 — Select Official Forecast Record
 * Step 2 — Select Recipients (ALL_ASSIGNED or SELECTED)
 * Step 3 — Prepare Advice (Standard Advice + Optional Vet Custom Note + Personalized Overrides)
 * Step 4 — Preview, Review, & Approve Advisory
 * Step 5 — Embedded Simulated Delivery Panel
 */
export function VeterinaryAdvisoryCentre({ viewerContext }) {
  // 1. Fail-closed ViewerContext validation
  const validation = validateViewerContext(viewerContext);
  const normalizedContext = validation.valid ? validation.normalizedContext : null;
  const isVet = normalizedContext?.role === ROLES.VETERINARY_OFFICER;
  const vetId = normalizedContext?.userId || 'vet_officer_01';
  const authorizedDistricts = normalizedContext?.authorization?.authorizedDistricts || [];
  const districtKey = authorizedDistricts.join(',');

  // Active step state (1 to 5)
  const [currentStep, setCurrentStep] = useState(1);

  // Step 1 State: Forecast Selection
  const [forecastRecords, setForecastRecords] = useState([]);
  const [selectedForecast, setSelectedForecast] = useState(null);
  const [loadingForecasts, setLoadingForecasts] = useState(false);

  // Step 2 State: Recipient Selection
  const [recipientList, setRecipientList] = useState([]);
  const [loadingRecipients, setLoadingRecipients] = useState(false);
  const [recipientScope, setRecipientScope] = useState('ALL_ASSIGNED');
  const [selectedRecipientIds, setSelectedRecipientIds] = useState([]);

  // Step 3 State: Advisory Draft & Custom Notes
  const [vetCustomNote, setVetCustomNote] = useState('');
  const [personalizedNotesMap, setPersonalizedNotesMap] = useState({}); // { recipientId: noteText }
  const [currentAdvisory, setCurrentAdvisory] = useState(null);
  const [savingDraft, setSavingDraft] = useState(false);

  // Step 4 State: Preview & Lifecycle
  const [previewData, setPreviewData] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [lifecyclePending, setLifecyclePending] = useState(false);

  // Shared Error / Notification State
  const [error, setError] = useState(null);
  const [infoMessage, setInfoMessage] = useState(null);

  // Farmer Notification State
  const [notifyingFarmers, setNotifyingFarmers] = useState(false);
  const [notifyResult, setNotifyResult] = useState(null);

  // ── 1. Fetch Official Forecast Records for Authorized Districts ────────────────────────
  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    if (!isVet || authorizedDistricts.length === 0) return;

    async function loadForecasts() {
      try {
        setLoadingForecasts(true);
        setError(null);

        // Fetch records for authorized district(s) across all available timeframes
        const fetchPromises = authorizedDistricts.map((district) =>
          listForecastRecords({ district, limit: 100 }, { signal: controller.signal })
            .then((res) => res?.records || [])
            .catch(() => [])
        );

        const recordSets = await Promise.all(fetchPromises);
        const allRecords = recordSets.flat();

        // Deterministic newest-first ordering: target_year desc, target_month desc, generated_at desc
        const sorted = allRecords.sort((a, b) => {
          if (b.target_year !== a.target_year) return b.target_year - a.target_year;
          if (b.target_month !== a.target_month) return b.target_month - a.target_month;
          return new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime();
        });

        if (isMounted) {
          setForecastRecords(sorted);
        }
      } catch (err) {
        if (isMounted && err.name !== 'AbortError') {
          setError(err.message || 'Failed to load official forecast records.');
        }
      } finally {
        if (isMounted) {
          setLoadingForecasts(false);
        }
      }
    }

    loadForecasts();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [isVet, districtKey]);

  // ── 2. Fetch Assigned Recipients when Forecast is Selected ─────────────────────────────
  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    if (!selectedForecast || !vetId) return;

    async function loadRecipients() {
      try {
        setLoadingRecipients(true);
        setError(null);

        const resp = await listAssignedRecipients({
          vetId,
          district: selectedForecast.district,
          signal: controller.signal,
        });

        if (isMounted) {
          setRecipientList(resp?.recipients || []);
        }
      } catch (err) {
        if (isMounted && err.name !== 'AbortError') {
          setError(err.message || 'Failed to load assigned recipients for district.');
        }
      } finally {
        if (isMounted) {
          setLoadingRecipients(false);
        }
      }
    }

    loadRecipients();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [selectedForecast?.forecast_id, vetId]);

  // Fail-closed early return for invalid context
  if (!validation.valid || !isVet) {
    return (
      <AccessContextUnavailable reason="Advisory Centre is restricted to authorized Veterinary Officers." />
    );
  }

  // Handle Forecast Selection
  const handleSelectForecast = (record) => {
    setSelectedForecast(record);
    setRecipientScope('ALL_ASSIGNED');
    setCurrentAdvisory(null);
    setPreviewData(null);
    setSelectedRecipientIds([]);
    setPersonalizedNotesMap({});
    setError(null);
    setInfoMessage(null);
    setCurrentStep(2);
  };

  // Recipient Toggle
  const handleToggleRecipient = (recipientId) => {
    setPreviewData(null);
    setSelectedRecipientIds((prev) =>
      prev.includes(recipientId) ? prev.filter((id) => id !== recipientId) : [...prev, recipientId]
    );
  };

  const handleSelectAllRecipients = () => {
    setPreviewData(null);
    setSelectedRecipientIds(recipientList.map((r) => r.recipient_id));
  };

  const handleClearRecipientSelection = () => {
    setPreviewData(null);
    setSelectedRecipientIds([]);
  };

  // Personalized Note Update
  const handlePersonalizedNoteChange = (recipientId, text) => {
    setPreviewData(null);
    setPersonalizedNotesMap((prev) => ({
      ...prev,
      [recipientId]: text,
    }));
  };

  // ── Step 3 Action: Create or Update Advisory Draft ─────────────────────────────────────
  const handleSaveDraft = async () => {
    if (!selectedForecast) {
      setError('Please select an official forecast record first.');
      return;
    }

    if (recipientScope === 'SELECTED' && selectedRecipientIds.length === 0) {
      setError('Please select at least one recipient farm when using Selected Farms scope.');
      return;
    }

    try {
      setSavingDraft(true);
      setError(null);
      setInfoMessage(null);

      // Build personalized_overrides list from map
      const overrides = Object.entries(personalizedNotesMap)
        .filter(([, note]) => note && note.trim().length > 0)
        .map(([recipient_id, custom_note]) => ({ recipient_id, custom_note: custom_note.trim() }));

      if (!currentAdvisory) {
        // Create initial draft
        const draft = await createAdvisoryDraft({
          forecast_id: selectedForecast.forecast_id,
          advisory_type: 'VETERINARY_CUSTOM_ADVICE',
          recipient_scope: recipientScope,
          selected_recipient_ids: recipientScope === 'SELECTED' ? selectedRecipientIds : undefined,
          vet_custom_note: vetCustomNote.trim() || undefined,
          personalized_overrides: overrides.length > 0 ? overrides : undefined,
          created_by: vetId,
        });

        setCurrentAdvisory(draft);
        setInfoMessage(`Advisory draft created successfully.`);
      } else {
        // Update existing draft with optimistic versioning
        const updated = await updateAdvisoryDraft(currentAdvisory.advisory_id, {
          version: currentAdvisory.version,
          recipient_scope: recipientScope,
          selected_recipient_ids: recipientScope === 'SELECTED' ? selectedRecipientIds : undefined,
          vet_custom_note: vetCustomNote.trim() || undefined,
          personalized_overrides: overrides.length > 0 ? overrides : undefined,
        });

        setCurrentAdvisory(updated);
        setInfoMessage(`Advisory draft updated (Version: ${updated.version}).`);
      }

      setCurrentStep(4);
    } catch (err) {
      setError(sanitizeErrorMessage(err, 'Failed to save advisory draft.'));
    } finally {
      setSavingDraft(false);
    }
  };

  // ── Step 4 Action: Generate Preview ────────────────────────────────────────────────────
  const handleGeneratePreview = async () => {
    if (!currentAdvisory?.advisory_id) {
      setError('No saved advisory draft available to preview.');
      return;
    }

    try {
      setLoadingPreview(true);
      setError(null);

      const preview = await previewAdvisory({ advisoryId: currentAdvisory.advisory_id });
      setPreviewData(preview);
    } catch (err) {
      setError(sanitizeErrorMessage(err, 'Failed to generate advisory preview.'));
    } finally {
      setLoadingPreview(false);
    }
  };

  // ── Step 4 Action: Lifecycle Transitions ───────────────────────────────────────────────

  const handleNotifyFarmers = async () => {
    if (!currentAdvisory?.advisory_id) return;
    setNotifyingFarmers(true);
    setError(null);
    setNotifyResult(null);
    try {
      const result = await forwardToAssignedFarmers(currentAdvisory.advisory_id, { actorContext: normalizedContext });
      setNotifyResult(`Success: ${result.notified_count} notified (${result.already_notified_count} skipped)`);
    } catch (err) {
      setError(sanitizeErrorMessage(err, 'Failed to notify assigned farmers.'));
    } finally {
      setNotifyingFarmers(false);
    }
  };

  const handleMarkReadyForReview = async () => {
    if (!currentAdvisory || lifecyclePending) return;

    try {
      setLifecyclePending(true);
      setError(null);

      const updated = await markAdvisoryReadyForReview(currentAdvisory.advisory_id, currentAdvisory.version);
      setCurrentAdvisory(updated);
      setInfoMessage('Advisory marked as READY FOR REVIEW.');
    } catch (err) {
      setError(sanitizeErrorMessage(err, 'Failed to transition advisory to ready for review.'));
    } finally {
      setLifecyclePending(false);
    }
  };

  const handleApproveAdvisory = async () => {
    if (!currentAdvisory || lifecyclePending) return;

    try {
      setLifecyclePending(true);
      setError(null);

      const updated = await approveAdvisory(currentAdvisory.advisory_id, {
        version: currentAdvisory.version,
        approvedBy: vetId,
      });
      setCurrentAdvisory(updated);
      setInfoMessage('Advisory APPROVED. Recipient snapshot and advisory text are now frozen.');
    } catch (err) {
      setError(sanitizeErrorMessage(err, 'Failed to approve advisory.'));
    } finally {
      setLifecyclePending(false);
    }
  };

  const handleCancelAdvisory = async () => {
    if (!currentAdvisory || lifecyclePending) return;

    try {
      setLifecyclePending(true);
      setError(null);

      const updated = await cancelAdvisory(currentAdvisory.advisory_id, currentAdvisory.version);
      setCurrentAdvisory(updated);
      setInfoMessage('Advisory CANCELLED.');
    } catch (err) {
      setError(sanitizeErrorMessage(err, 'Failed to cancel advisory.'));
    } finally {
      setLifecyclePending(false);
    }
  };

  return (
    <div className="w-full min-w-0 max-w-6xl mx-auto space-y-6 text-slate-100 font-sans">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-800 shadow-xl">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 uppercase tracking-widest mb-1">
              <span className="material-symbols-outlined text-sm" aria-hidden="true">campaign</span>
              <span>Veterinary Decision Support</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              Veterinary Officer Advisory Centre
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-2xl">
              Draft, review, and approve official biosecurity advisories linked to authoritative forecast records.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
              Scope: {authorizedDistricts.join(', ') || 'None'}
            </span>
          </div>
        </div>

        {/* Step Progress Bar */}
        <div className="mt-6 pt-4 border-t border-slate-800/80 grid grid-cols-4 gap-2 text-center text-xs font-medium">
          {[
            { step: 1, label: '1. Select Forecast' },
            { step: 2, label: '2. Recipients' },
            { step: 3, label: '3. Advice Draft' },
            { step: 4, label: '4. Preview & Approve' },
          ].map(({ step, label }) => {
            const isActive = currentStep === step;
            const isPassed = currentStep > step;
            return (
              <button
                key={step}
                type="button"
                onClick={() => {
                  if (step <= currentStep || (step === 2 && selectedForecast) || (step === 3 && selectedForecast) || (step === 4 && currentAdvisory)) {
                    setCurrentStep(step);
                  }
                }}
                className={`py-2 px-1 rounded-lg transition-all ${
                  isActive
                    ? 'bg-emerald-600 text-white font-semibold shadow-md'
                    : isPassed
                    ? 'bg-slate-800 text-emerald-300 hover:bg-slate-700'
                    : 'bg-slate-950 text-slate-500 cursor-not-allowed'
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Global Alerts */}
      {error && (
        <div role="alert" className="p-4 rounded-xl bg-red-950/60 border border-red-800/80 text-red-200 text-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="material-symbols-outlined text-red-400 shrink-0" aria-hidden="true">error</span>
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-xs text-red-400 hover:text-red-200"
          >
            Dismiss
          </button>
        </div>
      )}

      {infoMessage && (
        <div role="status" className="p-4 rounded-xl bg-emerald-950/60 border border-emerald-800/80 text-emerald-200 text-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="material-symbols-outlined text-emerald-400 shrink-0" aria-hidden="true">check_circle</span>
            <span>{infoMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setInfoMessage(null)}
            className="text-xs text-emerald-400 hover:text-emerald-200"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* STEP 1 — SELECT OFFICIAL FORECAST RECORD */}
      {currentStep === 1 && (
        <div className="space-y-4 p-6 rounded-2xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h3 className="text-lg font-semibold text-white">Step 1 — Select Official Forecast Record</h3>
              <p className="text-xs text-slate-400">
                Advisories must reference an authoritative forecast record saved in your authorized district.
              </p>
            </div>
          </div>

          {loadingForecasts ? (
            <div className="py-12 text-center text-slate-400 text-sm space-y-2">
              <span className="material-symbols-outlined text-2xl animate-spin text-emerald-400" aria-hidden="true">progress_activity</span>
              <p>Loading official forecast decision records...</p>
            </div>
          ) : forecastRecords.length === 0 ? (
            <div className="p-8 rounded-xl bg-slate-950 border border-slate-800 text-center space-y-3">
              <span className="material-symbols-outlined text-3xl text-amber-400" aria-hidden="true">assignment_late</span>
              <h4 className="text-base font-semibold text-slate-200">No Stored Forecast Available</h4>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                No forecast decision record is currently available for your assigned district.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {forecastRecords.map((rec) => {
                const isSelected = selectedForecast?.forecast_id === rec.forecast_id;
                const isHigh = rec.risk_level === 'HIGH';
                const isMed = rec.risk_level === 'MEDIUM';

                let riskBadgeClass = 'bg-slate-800 text-slate-300 border-slate-700';
                if (isHigh) riskBadgeClass = 'bg-red-950/70 text-red-300 border-red-800';
                else if (isMed) riskBadgeClass = 'bg-amber-950/70 text-amber-300 border-amber-800';
                else riskBadgeClass = 'bg-emerald-950/70 text-emerald-300 border-emerald-800';

                return (
                  <div
                    key={rec.forecast_id}
                    onClick={() => handleSelectForecast(rec)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-slate-800/90 border-emerald-500 ring-2 ring-emerald-500/30'
                        : 'bg-slate-950 border-slate-800 hover:border-slate-700 hover:bg-slate-800/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-200 border border-slate-700">
                        {rec.disease} — {rec.district}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded border font-semibold ${riskBadgeClass}`}>
                        {rec.risk_level} RISK ({rec.probability_pct}%)
                      </span>
                    </div>

                    <div className="text-sm font-semibold text-white">
                      Target: {rec.target_year}-{String(rec.target_month).padStart(2, '0')}
                    </div>

                    <div className="text-xs text-slate-400 mt-1 flex items-center justify-between gap-2">
                      <span>Severity: {rec.predicted_severity || 'N/A'}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* STEP 2 — SELECT RECIPIENTS */}
      {currentStep === 2 && selectedForecast && (
        <div className="space-y-4 p-6 rounded-2xl bg-slate-900 border border-slate-800">
          <div>
            <h3 className="text-lg font-semibold text-white">Step 2 — Select Recipients</h3>
            <p className="text-xs text-slate-400">
              Target assigned farms in <strong>{selectedForecast.district}</strong> for advisory distribution.
            </p>
          </div>

          <div className="space-y-4 p-4 rounded-xl bg-slate-950 border border-slate-800">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">
              Recipient Scope
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label
                className={`p-3 rounded-lg border cursor-pointer flex items-center gap-3 transition-colors ${
                  recipientScope === 'ALL_ASSIGNED'
                    ? 'bg-slate-800 border-emerald-500 text-white'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                <input
                  type="radio"
                  name="recipientScope"
                  value="ALL_ASSIGNED"
                  checked={recipientScope === 'ALL_ASSIGNED'}
                  onChange={() => {
                    setRecipientScope('ALL_ASSIGNED');
                    setPreviewData(null);
                  }}
                  className="accent-emerald-500"
                />
                <div>
                  <div className="text-sm font-semibold">All Assigned Farms</div>
                  <div className="text-xs text-slate-400">Automatic system resolution for district</div>
                </div>
              </label>

              <label
                className={`p-3 rounded-lg border cursor-pointer flex items-center gap-3 transition-colors ${
                  recipientScope === 'SELECTED'
                    ? 'bg-slate-800 border-emerald-500 text-white'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                <input
                  type="radio"
                  name="recipientScope"
                  value="SELECTED"
                  checked={recipientScope === 'SELECTED'}
                  onChange={() => {
                    setRecipientScope('SELECTED');
                    setPreviewData(null);
                  }}
                  className="accent-emerald-500"
                />
                <div>
                  <div className="text-sm font-semibold">Selected Farms</div>
                  <div className="text-xs text-slate-400">Target specific assigned farm recipients</div>
                </div>
              </label>
            </div>
          </div>

          {recipientScope === 'SELECTED' && (
            <div className="space-y-3 p-4 rounded-xl bg-slate-950 border border-slate-800">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Assigned Farm Directory ({recipientList.length})
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleSelectAllRecipients}
                    className="text-xs text-emerald-400 hover:underline"
                  >
                    Select All Visible
                  </button>
                  <span className="text-slate-600">|</span>
                  <button
                    type="button"
                    onClick={handleClearRecipientSelection}
                    className="text-xs text-slate-400 hover:underline"
                  >
                    Clear Selection
                  </button>
                </div>
              </div>

              {loadingRecipients ? (
                <div className="py-6 text-center text-xs text-slate-400">Loading assigned recipient list...</div>
              ) : recipientList.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-400">No active assigned recipients found for district.</div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-60 overflow-y-auto pr-1">
                  {recipientList.map((rec) => {
                    const isChecked = selectedRecipientIds.includes(rec.recipient_id);
                    return (
                      <label
                        key={rec.recipient_id}
                        className={`p-2.5 rounded-lg border text-xs cursor-pointer flex items-center justify-between gap-2 transition-colors ${
                          isChecked
                            ? 'bg-slate-800 border-emerald-500/80 text-white'
                            : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handleToggleRecipient(rec.recipient_id)}
                            className="accent-emerald-500 rounded"
                          />
                          <div className="truncate">
                            <div className="font-semibold truncate">{rec.recipient_name}</div>
                          </div>
                        </div>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 shrink-0">
                          {rec.district}
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end pt-2">
            <button
              type="button"
              onClick={() => setCurrentStep(3)}
              disabled={recipientScope === 'SELECTED' && selectedRecipientIds.length === 0}
              className="px-5 py-2 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 transition-colors inline-flex items-center gap-2"
            >
              <span>Continue to Prepare Advice</span>
              <span className="material-symbols-outlined text-base" aria-hidden="true">arrow_forward</span>
            </button>
          </div>
        </div>
      )}

      {/* STEP 3 — PREPARE ADVICE */}
      {currentStep === 3 && selectedForecast && (
        <div className="space-y-4 p-6 rounded-2xl bg-slate-900 border border-slate-800">
          <div>
            <h3 className="text-lg font-semibold text-white">Step 3 — Prepare Advice</h3>
            <p className="text-xs text-slate-400">
              Review standard model-explained advisory message and append optional Vet notes.
            </p>
          </div>

          {/* Standard Advice Display */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
              <span className="uppercase tracking-wider font-semibold text-emerald-400">
                Authoritative Standard Advisory Body
              </span>
              <span>{selectedForecast.disease} — {selectedForecast.district}</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-900 text-slate-200 text-xs font-mono leading-relaxed border border-slate-800">
              Standard disease risk forecast advisory for {selectedForecast.disease} in {selectedForecast.district} ({selectedForecast.risk_level} risk, {selectedForecast.probability_pct}% predicted probability).
            </div>
          </div>

          {/* Optional Common Vet Note */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">
              Optional Common Veterinary Note (Appended to all target recipients)
            </label>
            <textarea
              rows={3}
              value={vetCustomNote}
              onChange={(e) => {
                setVetCustomNote(e.target.value);
                setPreviewData(null);
              }}
              placeholder="e.g. Please ensure ring vaccination protocols are verified prior to monsoon entry..."
              className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 text-xs focus:outline-none focus:border-emerald-500 transition-colors resize-y"
            />
          </div>

          {/* Optional Personalized Overrides */}
          {recipientScope === 'SELECTED' && selectedRecipientIds.length > 0 && (
            <div className="space-y-3 p-4 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">
                Optional Personalized Overrides for Selected Farms
              </span>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {selectedRecipientIds.map((recId) => {
                  const rec = recipientList.find((r) => r.recipient_id === recId);
                  return (
                    <div key={recId} className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-white">{rec?.recipient_name || 'Recipient'}</span>
                      </div>
                      <input
                        type="text"
                        value={personalizedNotesMap[recId] || ''}
                        onChange={(e) => handlePersonalizedNoteChange(recId, e.target.value)}
                        placeholder="Specific note for this recipient only..."
                        className="w-full p-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-emerald-500"
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="flex justify-between items-center pt-2">
            <button
              type="button"
              onClick={() => setCurrentStep(2)}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white bg-slate-950 border border-slate-800"
            >
              Back
            </button>
            <button
              type="button"
              onClick={handleSaveDraft}
              disabled={savingDraft}
              className="px-5 py-2 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 transition-colors inline-flex items-center gap-2"
            >
              {savingDraft ? 'Saving Draft...' : currentAdvisory ? 'Update Advisory Draft' : 'Save Advisory Draft'}
            </button>
          </div>
        </div>
      )}

      {/* STEP 4 — PREVIEW, REVIEW, & APPROVE */}
      {currentStep === 4 && currentAdvisory && (
        <div className="space-y-4 p-6 rounded-2xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h3 className="text-lg font-semibold text-white">Step 4 — Preview, Review, & Approval</h3>
              <p className="text-xs text-slate-400">
                Preview fully resolved per-recipient messages and execute authoritative lifecycle transitions.
              </p>
            </div>
            <div className="flex items-center gap-2 font-mono text-xs">
              <span className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
                Status: <strong className="text-emerald-400">{currentAdvisory.status}</strong>
              </span>
              <span className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
                Version: {currentAdvisory.version}
              </span>
            </div>
          </div>

          {currentAdvisory.status === 'APPROVED' && (
            <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-800/80 text-emerald-200 text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-emerald-400 shrink-0 text-base" aria-hidden="true">lock</span>
              <span>Approved advisory snapshot is frozen. Further editing is locked.</span>
            </div>
          )}

          {/* Preview Trigger & Display */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Recipient Message Resolution Preview
              </span>
              <button
                type="button"
                onClick={handleGeneratePreview}
                disabled={loadingPreview}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-emerald-300 border border-slate-700 inline-flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-sm" aria-hidden="true">visibility</span>
                <span>{loadingPreview ? 'Generating Preview...' : 'Generate Preview'}</span>
              </button>
            </div>

            {previewData && (
              <div className="space-y-3">
                <div className="text-xs text-slate-400 flex items-center justify-between">
                  <span>Targeted Recipients: {previewData.recipient_summary?.selected_count ?? 0}</span>
                  <span>Personalized: {previewData.recipient_summary?.personalized_count ?? 0}</span>
                </div>
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {previewData.previews?.map((p) => (
                    <div key={p.recipient_id} className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-white">{p.recipient_name}</span>
                        {p.is_personalized && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
                            Personalized Override
                          </span>
                        )}
                      </div>
                      <p className="text-slate-300 font-mono text-[11px] leading-relaxed">
                        {p.final_message}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Lifecycle Action Toolbar */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              {currentAdvisory.status === 'DRAFT' && (
                <button
                  type="button"
                  onClick={handleMarkReadyForReview}
                  disabled={lifecyclePending}
                  className="px-4 py-2 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 transition-colors"
                >
                  Mark Ready for Review
                </button>
              )}

              {(currentAdvisory.status === 'DRAFT' || currentAdvisory.status === 'REVIEW_READY') && (
                <button
                  type="button"
                  onClick={handleApproveAdvisory}
                  disabled={lifecyclePending}
                  className="px-4 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 transition-colors"
                >
                  Approve Advisory
                </button>
              )}

              {currentAdvisory.status !== 'CANCELLED' && currentAdvisory.status !== 'APPROVED' && (
                <button
                  type="button"
                  onClick={handleCancelAdvisory}
                  disabled={lifecyclePending}
                  className="px-3.5 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-white bg-slate-900 border border-slate-800"
                >
                  Cancel Advisory
                </button>
              )}
            </div>

            {currentAdvisory.status === 'APPROVED' && (
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleNotifyFarmers}
                  disabled={notifyingFarmers}
                  className="px-5 py-2 rounded-xl text-sm font-semibold bg-amber-600 hover:bg-amber-500 text-white transition-colors"
                >
                  {notifyingFarmers ? 'Notifying...' : 'Notify Assigned Farmers'}
                </button>
                {notifyResult && <span className="text-sm font-bold text-emerald-400 whitespace-nowrap">{notifyResult}</span>}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

VeterinaryAdvisoryCentre.propTypes = {
  viewerContext: PropTypes.object,
};
