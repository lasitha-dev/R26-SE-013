import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  validateViewerContext,
} from '../../contracts/viewerContext';
import { AccessContextUnavailable } from '../AccessContextUnavailable';
import {
  listEligibleFollowUpVets,
  issueFollowUp,
  listFollowUps,
} from '../../services/riskForecastingWorkflowApi';

/**
 * Sanitizes technical error messages for presentation.
 * Strips filesystem paths, stack traces, and internal trace details.
 */
function sanitizeErrorMessage(rawMessage, statusCode) {
  if (!rawMessage || typeof rawMessage !== 'string') {
    return 'An unexpected error occurred while processing the follow-up request.';
  }

  const msg = rawMessage.trim();

  // Strip file paths, stack traces, line numbers, bearer tokens, headers, DB URLs, raw object strings
  if (
    msg.includes('Traceback') ||
    msg.includes('File "') ||
    msg.includes('C:\\') ||
    msg.includes('/Users/') ||
    msg.includes('/home/') ||
    msg.includes('Bearer ') ||
    msg.includes('Authorization:') ||
    msg.includes('mongodb://') ||
    msg.includes('postgresql://') ||
    msg.includes('[object Object]')
  ) {
    return 'A technical error occurred during follow-up processing. Please retry or contact system administration.';
  }

  if (statusCode === 409 || msg.toLowerCase().includes('conflict') || msg.toLowerCase().includes('already exists')) {
    return 'Operation conflict: A follow-up matching this operation key or assignment may already exist. Please refresh and review existing follow-ups.';
  }

  if (statusCode === 403 || msg.toLowerCase().includes('not authorized') || msg.toLowerCase().includes('forbidden')) {
    return 'Access Denied: You are not authorized as a DAPH Official to issue follow-up instructions for this district.';
  }

  if (statusCode === 404 || msg.toLowerCase().includes('not found')) {
    return 'Resource Not Found: The specified forecast record or Veterinary Officer was not found.';
  }

  if (statusCode === 400 || statusCode === 422) {
    return `Validation Error: ${msg}`;
  }

  return msg;
}

/**
 * Month number to name helper.
 */
function getMonthName(monthNum) {
  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];
  return months[(Number(monthNum) - 1) % 12] || `Month ${monthNum}`;
}

/**
 * DaphFollowUpComposer Component.
 *
 * Operational DAPH Official follow-up issuing workflow component.
 * Allows DAPH officials to query active, eligible district Veterinary Officers,
 * review immutable scientific forecast snapshots, and issue official follow-up assignments.
 */
export function DaphFollowUpComposer({ forecastRecord, viewerContext, onClose, onFollowUpCreated }) {
  // 1. Authorization Access Gating (Fail-closed)
  const validation = validateViewerContext(viewerContext);
  const normalizedContext = validation.valid ? validation.normalizedContext : null;
  const isDaphOfficial = normalizedContext?.role === ROLES.DAPH_OFFICIAL;

  // 2. Component State
  const [vets, setVets] = useState([]);
  const [vetsLoading, setVetsLoading] = useState(false);
  const [vetsError, setVetsError] = useState(null);

  const [existingFollowUps, setExistingFollowUps] = useState([]);
  const [existingLoading, setExistingLoading] = useState(false);
  const [existingError, setExistingError] = useState(null);

  const [selectedVetId, setSelectedVetId] = useState('');
  const [instruction, setInstruction] = useState('');
  const [instructionTouched, setInstructionTouched] = useState(false);

  const [stage, setStage] = useState('PREPARE'); // 'PREPARE' | 'REVIEW' | 'SUCCESS'
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [issuedFollowUp, setIssuedFollowUp] = useState(null);

  // AbortController ref for race condition safeguarding
  const abortControllerRef = useRef(null);

  // 3. Extract Canonical Forecast Snapshot Properties
  const rawForecastId = forecastRecord?.forecast_id || forecastRecord?.id || '';
  const forecastId = String(rawForecastId).trim();
  const hasValidForecastRecord = Boolean(forecastRecord) && forecastRecord.isMissingRecord !== true && forecastId !== '';
  const district = forecastRecord?.district || '';
  const disease = forecastRecord?.disease || '';
  const targetYear = forecastRecord?.target_year ?? null;
  const targetMonth = forecastRecord?.target_month ?? null;
  const riskLevel = forecastRecord?.risk_level || 'LOW';
  const probability = forecastRecord?.probability ?? null;
  const predictedSeverity = forecastRecord?.predicted_severity || 'N/A';
  const dataQuality = forecastRecord?.data_quality || 'N/A';
  const fallbackApplied = forecastRecord?.fallback_applied === true;
  const forecastStatus = forecastRecord?.status || 'OFFICIAL';

  // Derivation of operational priority from forecast risk level
  const operationalPriority = useMemo(() => {
    if (riskLevel === 'HIGH') return 'HIGH';
    if (riskLevel === 'MEDIUM') return 'MEDIUM';
    return 'LOW';
  }, [riskLevel]);

  // 4. Load Eligible Vets & Existing Follow-ups on Mount / District Change
  const loadData = useCallback(async () => {
    if (!district || !isDaphOfficial || !hasValidForecastRecord) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setVetsLoading(true);
    setVetsError(null);
    setExistingLoading(true);
    setExistingError(null);

    // Fetch Eligible Vets
    try {
      const vetRes = await listEligibleFollowUpVets(
        { district },
        { actorContext: viewerContext, signal: controller.signal }
      );
      if (controller.signal.aborted) return;
      const loadedVets = vetRes?.veterinary_officers || [];
      setVets(loadedVets);
      if (loadedVets.length > 0) {
        setSelectedVetId((prev) => (prev ? prev : loadedVets[0].vet_id));
      }
      setVetsLoading(false);
    } catch (err) {
      if (controller.signal.aborted) return;
      setVetsError(sanitizeErrorMessage(err.message || 'Failed to load eligible Veterinary Officers.', err.statusCode));
      setVetsLoading(false);
    }

    // Fetch Existing Follow-Ups for Context
    if (forecastId) {
      try {
        const followUpRes = await listFollowUps(
          { forecast_id: forecastId },
          { actorContext: viewerContext, signal: controller.signal }
        );
        if (controller.signal.aborted) return;
        setExistingFollowUps(followUpRes?.follow_ups || []);
        setExistingLoading(false);
      } catch (err) {
        if (controller.signal.aborted) return;
        setExistingError(sanitizeErrorMessage(err.message || 'Unable to verify existing follow-up history.', err.statusCode));
        setExistingFollowUps([]);
        setExistingLoading(false);
      }
    } else {
      setExistingLoading(false);
    }
  }, [district, forecastId, isDaphOfficial, hasValidForecastRecord, viewerContext]);

  useEffect(() => {
    loadData();
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [loadData]);

  // 5. Instruction Validation
  const trimmedInstruction = instruction.trim();
  const instructionLength = instruction.length;
  const isInstructionValid =
    trimmedInstruction.length >= 1 && instructionLength <= 500;

  const instructionValidationError = useMemo(() => {
    if (!instructionTouched && instructionLength === 0) return null;
    if (instructionLength === 0 || trimmedInstruction.length === 0) {
      return 'Operational instruction is required.';
    }
    if (instructionLength > 500) {
      return 'Instruction cannot exceed 500 characters.';
    }
    return null;
  }, [instructionLength, trimmedInstruction, instructionTouched]);

  // Selected Vet Object
  const selectedVet = useMemo(() => {
    return vets.find((v) => v.vet_id === selectedVetId) || null;
  }, [vets, selectedVetId]);

  // Check Active Existing Follow-ups
  const activeExistingFollowUps = useMemo(() => {
    return existingFollowUps.filter((f) =>
      ['ISSUED', 'ACKNOWLEDGED', 'ACTION_IN_PROGRESS'].includes(f.status)
    );
  }, [existingFollowUps]);

  // 6. Deterministic Idempotency Key Derivation
  const idempotencyKey = useMemo(() => {
    const actorId = normalizedContext?.userId || 'daph_official';
    if (!forecastId || !selectedVetId) return null;
    return `daph-follow-up:${actorId}:${forecastId}:${selectedVetId}`;
  }, [normalizedContext, forecastId, selectedVetId]);

  // Form Handlers
  const handleProceedToReview = (e) => {
    e.preventDefault();
    setInstructionTouched(true);
    if (!selectedVetId || !isInstructionValid) {
      return;
    }
    setSubmitError(null);
    setStage('REVIEW');
  };

  const handleBackToEdit = () => {
    setSubmitError(null);
    setStage('PREPARE');
  };

  const handleConfirmAndIssue = async () => {
    if (!hasValidForecastRecord || !selectedVetId || !isInstructionValid || submitting || stage === 'SUCCESS') {
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    const payload = {
      forecast_id: forecastId,
      assigned_vet_id: selectedVetId,
      instruction_summary: trimmedInstruction,
    };

    if (idempotencyKey) {
      payload.idempotency_key = idempotencyKey;
    }

    try {
      const res = await issueFollowUp(payload, { actorContext: viewerContext });
      setSubmitting(false);
      setIssuedFollowUp(res);
      setStage('SUCCESS');
      if (typeof onFollowUpCreated === 'function') {
        onFollowUpCreated(res);
      }
    } catch (err) {
      setSubmitting(false);
      const sanitized = sanitizeErrorMessage(err.message, err.statusCode);
      setSubmitError(sanitized);
    }
  };

  // 7. Fail-Closed Early Return if Unauthorized or Missing Valid Forecast Record
  if (!validation.valid || !isDaphOfficial) {
    return (
      <AccessContextUnavailable
        reason={
          validation.reason ||
          'Issuing follow-up instructions requires authenticated DAPH_OFFICIAL role.'
        }
      />
    );
  }

  if (!hasValidForecastRecord) {
    return (
      <AccessContextUnavailable
        reason="Follow-up issuing requires a valid, persisted ForecastDecisionRecord."
      />
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      <div className="w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden flex flex-col my-auto text-slate-100">
        {/* Header */}
        <div className="px-6 py-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-amber-400 text-2xl">assignment_add</span>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">Issue Operational Follow-Up</h2>
              <p className="text-xs text-slate-400">
                Forecast-linked Veterinary Officer operational assignment (DAPH Official)
              </p>
            </div>
          </div>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700 transition"
              aria-label="Close Composer"
            >
              <span className="material-symbols-outlined text-lg">close</span>
            </button>
          )}
        </div>

        <div className="p-6 space-y-6 max-h-[80vh] overflow-y-auto">
          {/* Stage Progress Indicator */}
          <div className="flex items-center justify-between text-xs font-semibold text-slate-400 bg-slate-800/40 p-2.5 rounded-xl border border-slate-800">
            <div className={`flex items-center gap-2 ${stage === 'PREPARE' ? 'text-amber-400' : 'text-slate-500'}`}>
              <span className="w-5 h-5 rounded-full bg-slate-800 border border-current flex items-center justify-center text-[10px]">1</span>
              <span>Prepare Instruction</span>
            </div>
            <span className="text-slate-700">➔</span>
            <div className={`flex items-center gap-2 ${stage === 'REVIEW' ? 'text-amber-400' : 'text-slate-500'}`}>
              <span className="w-5 h-5 rounded-full bg-slate-800 border border-current flex items-center justify-center text-[10px]">2</span>
              <span>Review Assignment</span>
            </div>
            <span className="text-slate-700">➔</span>
            <div className={`flex items-center gap-2 ${stage === 'SUCCESS' ? 'text-emerald-400' : 'text-slate-500'}`}>
              <span className="w-5 h-5 rounded-full bg-slate-800 border border-current flex items-center justify-center text-[10px]">3</span>
              <span>Confirmation</span>
            </div>
          </div>

          {/* 1. IMMUTABLE OFFICIAL FORECAST SNAPSHOT */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                <span className="material-symbols-outlined text-sm">lock</span>
                Authoritative Forecast Snapshot (Read-Only)
              </h3>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs bg-slate-800/50 p-4 rounded-xl border border-slate-800">
              <div>
                <span className="text-slate-500 block">District</span>
                <span className="font-semibold text-white">{district || 'N/A'}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Disease</span>
                <span className="font-mono font-medium text-slate-200">{disease || 'N/A'}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Target Period</span>
                <span className="font-medium text-slate-200">
                  {targetMonth ? getMonthName(targetMonth) : 'N/A'} {targetYear || ''}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Risk Tier</span>
                <span className={`font-bold ${riskLevel === 'HIGH' ? 'text-rose-400' : riskLevel === 'MEDIUM' ? 'text-amber-400' : 'text-emerald-400'}`}>
                  {riskLevel}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Outbreak Probability</span>
                <span className="font-mono font-bold text-emerald-400">
                  {probability !== null && probability !== undefined ? `${(probability * 100).toFixed(1)}%` : 'N/A'}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Predicted Severity</span>
                <span className="font-medium text-slate-200">{predictedSeverity}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Operational Priority</span>
                <span className="font-bold text-amber-300">{operationalPriority}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Data Quality</span>
                <span className="font-mono text-slate-300">{dataQuality}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Provenance</span>
                <span className="font-medium text-slate-300">
                  {fallbackApplied ? 'Fallback Proxy Applied' : 'Exact Period'}
                </span>
              </div>
            </div>

            {fallbackApplied && (
              <div className="text-xs text-slate-400 italic mt-2">
                Historical proxy data used
              </div>
            )}
          </div>

          {/* 2. EXISTING FOLLOW-UP AWARENESS WARNING */}
          {activeExistingFollowUps.length > 0 && (
            <div className="bg-amber-950/50 border border-amber-500/50 rounded-xl p-4 space-y-2 text-xs text-amber-200" aria-live="polite">
              <div className="flex items-center gap-2 text-amber-400 font-bold">
                <span className="material-symbols-outlined text-base">warning</span>
                <span>Active Follow-Up Warning ({activeExistingFollowUps.length} Active)</span>
              </div>
              <p>
                An active follow-up instruction is already registered for this forecast record. Please review existing operational activity before issuing an additional follow-up.
              </p>
              <div className="space-y-1.5 pt-1">
                {activeExistingFollowUps.map((f) => (
                  <div key={f.follow_up_id} className="bg-slate-900/80 p-2.5 rounded-lg border border-amber-500/30 flex items-center justify-between text-[11px]">
                    <div>
                      <span className="font-mono text-slate-300 block">ID: {f.follow_up_id}</span>
                      <span className="text-slate-400">Assigned Vet: {f.assigned_vet_id}</span>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                      {f.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Existing Follow-Up Query Failure Warning */}
          {existingError && !existingLoading && (
            <div className="bg-amber-950/40 border border-amber-500/40 rounded-xl p-3 text-xs text-amber-300 flex items-center gap-2" role="alert">
              <span className="material-symbols-outlined text-sm text-amber-400">warning</span>
              <span>Notice: Unable to verify existing follow-up history ({existingError}). Please proceed with caution.</span>
            </div>
          )}

          {/* STAGE 1: PREPARE FORM */}
          {stage === 'PREPARE' && (
            <form onSubmit={handleProceedToReview} className="space-y-5">
              {/* Eligible Vet Selector */}
              <div className="space-y-1.5">
                <label htmlFor="vet-select" className="block text-xs font-semibold text-slate-200">
                  Assign Active Veterinary Officer <span className="text-rose-400">*</span>
                </label>
                {vetsLoading ? (
                  <div className="p-3 bg-slate-800/50 rounded-lg text-xs text-slate-400 flex items-center gap-2 border border-slate-700">
                    <span className="material-symbols-outlined text-sm animate-spin text-emerald-400">sync</span>
                    <span>Querying active Veterinary Officers for district {district}...</span>
                  </div>
                ) : vetsError ? (
                  <div className="p-3 bg-rose-950/40 border border-rose-500/40 rounded-lg text-xs text-rose-300 flex items-center justify-between">
                    <span>{vetsError}</span>
                    <button
                      type="button"
                      onClick={loadData}
                      className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[11px] transition"
                    >
                      Retry
                    </button>
                  </div>
                ) : vets.length === 0 ? (
                  <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700 text-center space-y-1">
                    <p className="text-xs text-amber-300 font-medium">
                      No active Veterinary Officers currently assigned to {district} district.
                    </p>
                    <p className="text-[11px] text-slate-400">
                      Operational follow-up cannot be issued until an active Veterinary Officer is registered in the directory protocol for this district.
                    </p>
                  </div>
                ) : (
                  <select
                    id="vet-select"
                    value={selectedVetId}
                    onChange={(e) => setSelectedVetId(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 text-slate-100 text-xs rounded-xl px-3 py-2.5 focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
                  >
                    {vets.map((v) => (
                      <option key={v.vet_id} value={v.vet_id}>
                        {v.display_name} — {Array.isArray(v.assigned_districts) ? v.assigned_districts.join(', ') : district}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Operational Instruction Input */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label htmlFor="instruction-input" className="block text-xs font-semibold text-slate-200">
                    Operational instruction for the assigned Veterinary Officer <span className="text-rose-400">*</span>
                  </label>
                  <span className={`text-[11px] font-mono ${instructionLength > 500 ? 'text-rose-400 font-bold' : 'text-slate-400'}`}>
                    {500 - instructionLength} characters remaining
                  </span>
                </div>
                <textarea
                  id="instruction-input"
                  rows={4}
                  value={instruction}
                  onChange={(e) => {
                    setInstruction(e.target.value);
                    if (!instructionTouched) setInstructionTouched(true);
                  }}
                  onBlur={() => setInstructionTouched(true)}
                  placeholder="Provide specific operational guidance, field surveillance tasks, or district advisory instructions for the officer..."
                  className={`w-full bg-slate-900 border text-slate-100 text-xs rounded-xl p-3 focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 ${
                    instructionValidationError ? 'border-rose-500 focus:border-rose-500' : 'border-slate-700'
                  }`}
                />
                {instructionValidationError && (
                  <p className="text-[11px] text-rose-400 flex items-center gap-1 mt-1" role="alert">
                    <span className="material-symbols-outlined text-xs">error</span>
                    <span>{instructionValidationError}</span>
                  </p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-3">
                {onClose && (
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition"
                  >
                    Cancel
                  </button>
                )}
                <button
                  type="submit"
                  disabled={vets.length === 0 || !selectedVetId || !isInstructionValid || vetsLoading}
                  className="px-5 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold shadow-lg transition flex items-center gap-1.5"
                >
                  <span>Review & Prepare Issue</span>
                  <span className="material-symbols-outlined text-sm">arrow_forward</span>
                </button>
              </div>
            </form>
          )}

          {/* STAGE 2: REVIEW STAGE */}
          {stage === 'REVIEW' && (
            <div className="space-y-5">
              <div className="bg-slate-800/40 border border-slate-800 rounded-xl p-4 space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400">
                  Review Follow-Up Summary Before Issuance
                </h4>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-500 block">Target District & Disease</span>
                    <span className="font-semibold text-white">{district} — {disease}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Target Period</span>
                    <span className="font-medium text-slate-200">
                      {targetMonth ? getMonthName(targetMonth) : ''} {targetYear}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Assigned Officer</span>
                    <span className="font-semibold text-emerald-300">
                      {selectedVet?.display_name || 'Nimal — Colombo'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Derived Priority</span>
                    <span className="font-bold text-amber-400">{operationalPriority}</span>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800/60">
                  <span className="text-slate-500 text-xs block mb-1">Instruction Summary:</span>
                  <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 text-xs font-mono text-slate-200 whitespace-pre-wrap">
                    {trimmedInstruction}
                  </div>
                </div>
              </div>



              {/* Submit Error Presentation */}
              {submitError && (
                <div className="p-4 bg-rose-950/50 border border-rose-500/50 rounded-xl text-xs text-rose-300 flex items-start gap-2" role="alert">
                  <span className="material-symbols-outlined text-base text-rose-400 shrink-0">error</span>
                  <div>
                    <strong className="block mb-0.5">Issuance Failed</strong>
                    <span>{submitError}</span>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
                <button
                  type="button"
                  onClick={handleBackToEdit}
                  disabled={submitting}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition flex items-center gap-1"
                >
                  <span className="material-symbols-outlined text-sm">arrow_back</span>
                  <span>Back to Edit</span>
                </button>
                <button
                  type="button"
                  onClick={handleConfirmAndIssue}
                  disabled={submitting}
                  className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-lg transition flex items-center gap-2"
                >
                  {submitting ? (
                    <>
                      <span className="material-symbols-outlined text-sm animate-spin">sync</span>
                      <span>Issuing Follow-Up...</span>
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined text-sm">check_circle</span>
                      <span>Confirm & Issue Follow-Up</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* STAGE 3: SUCCESS STATE */}
          {stage === 'SUCCESS' && issuedFollowUp && (
            <div className="space-y-5">
              <div className="bg-emerald-950/40 border border-emerald-500/40 rounded-xl p-5 text-center space-y-3">
                <span className="material-symbols-outlined text-4xl text-emerald-400">check_circle</span>
                <h3 className="text-base font-bold text-white">Operational Follow-Up Successfully Issued</h3>
                <p className="text-xs text-emerald-200">
                  Follow-up record has been registered in status <strong className="px-2 py-0.5 bg-emerald-900 text-emerald-300 rounded font-mono">ISSUED</strong>.
                </p>
              </div>

              <div className="bg-slate-800/40 border border-slate-800 rounded-xl p-4 space-y-2 text-xs">
                <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-400">Issued Assignment Details</h4>
                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div>
                    <span className="text-slate-500 block">Assigned Officer</span>
                    <span className="font-semibold text-white">{selectedVet?.display_name || issuedFollowUp.assigned_vet_id}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">District & Disease</span>
                    <span className="font-semibold text-white">{district} — {disease}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Target Period</span>
                    <span className="font-medium text-slate-300">{targetMonth}/{targetYear}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Priority</span>
                    <span className="font-bold text-amber-300">{issuedFollowUp.operational_priority || operationalPriority}</span>
                  </div>
                </div>
                <div className="pt-2 border-t border-slate-800/60">
                  <span className="text-slate-500 text-xs block mb-1">Instruction:</span>
                  <p className="font-mono text-slate-300 bg-slate-900 p-2.5 rounded border border-slate-800">{issuedFollowUp.instruction_summary}</p>
                </div>
              </div>

              <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 text-[11px] text-slate-400 space-y-1">
                <span className="font-bold text-slate-300 block">System Delivery Notice:</span>
                <p>
                  The follow-up instruction has been created in the operational workflow. This confirmation does not guarantee physical receipt by the officer or farmer contact.
                </p>
              </div>

              <div className="pt-3 border-t border-slate-800 flex items-center justify-end">
                {onClose ? (
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition"
                  >
                    Close
                  </button>
                ) : (
                  <span className="text-xs text-emerald-400 font-medium">Issuance Complete</span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

DaphFollowUpComposer.propTypes = {
  forecastRecord: PropTypes.shape({
    forecast_id: PropTypes.string,
    id: PropTypes.string,
    district: PropTypes.string,
    disease: PropTypes.string,
    target_year: PropTypes.number,
    target_month: PropTypes.number,
    risk_level: PropTypes.string,
    probability: PropTypes.number,
    predicted_severity: PropTypes.string,
    data_quality: PropTypes.string,
    fallback_applied: PropTypes.bool,
    status: PropTypes.string,
  }),
  viewerContext: PropTypes.object,
  onClose: PropTypes.func,
  onFollowUpCreated: PropTypes.func,
};
