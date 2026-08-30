import React, { useEffect, useState } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import UploadDropzone from '../../SmartDiagnostics/components/UploadDropzone';
import ReasoningBriefing from '../../SmartDiagnostics/components/ReasoningBriefing';
import useDetection from '../../SmartDiagnostics/hooks/useDetection';
import { getDiseaseProfile } from '../../SmartDiagnostics/diseaseProfiles';
import { reportDiagnosticCase } from '../../SmartDiagnostics/services/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

/**
 * FarmerSmartDiagnostics — Farmer portal view for AI-Powered Smart Diagnosis.
 *
 * Full feature parity with the clinical diagnostics pipeline:
 * - 01 Image Intake (upload dropzone)
 * - 02 Symptom Analysis (Mask R-CNN lesion segmentation & bounding box)
 * - 03 AI Logic Trace (step reveal + inference results)
 * - Model Reasoning & Evidence (rationale, telemetry, LLM reasoning briefing)
 * - Disease Reporting (creates a "Pending Verification" case routed to assigned vet)
 * - Mortality Declaration (confirm cattle death directly if applicable)
 */
const FarmerSmartDiagnostics = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const cattleId = searchParams.get('cattle_id');

  const [cattleInfo, setCattleInfo] = useState(null);
  const [loadingContext, setLoadingContext] = useState(false);

  // Case reporting states
  const [caseReport, setCaseReport] = useState(null);
  const [isReporting, setIsReporting] = useState(false);
  const [reportError, setReportError] = useState(null);

  // Mortality declaration states
  const [showMortalityModal, setShowMortalityModal] = useState(false);
  const [deathCause, setDeathCause] = useState('FMD');
  const [deathDate, setDeathDate] = useState(new Date().toISOString().split('T')[0]);
  const [deathNotes, setDeathNotes] = useState('');
  const [submittingDeath, setSubmittingDeath] = useState(false);
  const [deathError, setDeathError] = useState('');
  const [deathSuccess, setDeathSuccess] = useState('');

  const {
    status, result, error, imagePreview, detect, reset,
    reasoning, reasoningStatus, reasoningError, severityAssessment,
  } = useDetection();
  const [visibleSteps, setVisibleSteps] = useState(0);
  const [showSymptomMask, setShowSymptomMask] = useState(true);
  const [activeView, setActiveView] = useState('full'); // 'full' | 'lesion'

  // Fetch cattle metadata if cattleId is passed in URL
  useEffect(() => {
    const fetchCattleContext = async () => {
      if (!cattleId) {
        setCattleInfo(null);
        return;
      }
      setLoadingContext(true);
      try {
        const token = localStorage.getItem('token');
        const res = await fetch(`${API_BASE}/api/cattle/${cattleId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
        if (res.ok) {
          const data = await res.json();
          setCattleInfo(data);
        }
      } catch (err) {
        console.error('Error fetching cattle context:', err);
      } finally {
        setLoadingContext(false);
      }
    };
    fetchCattleContext();
  }, [cattleId]);

  // Determine effective status for UI rendering
  const isIdle = status === 'idle';
  const isLoading = status === 'processing';
  const isSuccess = status === 'done' && result?.cattle_detected;
  const isFailure = status === 'error' || (status === 'done' && !result?.cattle_detected);

  // Animate logic trace steps on success
  useEffect(() => {
    if (!isSuccess) {
      setVisibleSteps(0);
      return;
    }

    const timers = [];
    for (let i = 1; i <= 6; i++) {
      const timer = setTimeout(() => setVisibleSteps(i), i * 400);
      timers.push(timer);
    }

    return () => timers.forEach(clearTimeout);
  }, [isSuccess]);

  // Dynamic clinical severity & profile resolution
  const disease = result?.disease;
  const staticProfile = getDiseaseProfile(disease?.name);

  const effectiveSeverity = severityAssessment || result?.severity;
  const dynamicSeverity = effectiveSeverity;
  const dynamicStage = severityAssessment?.stage || result?.stage;
  const dynamicSpatialCorrelation = severityAssessment?.spatial_correlation || result?.spatial_correlation;

  const severityGrade = effectiveSeverity?.grade || (staticProfile.severity.split('/')[1] || '').trim() || 'Moderate';
  const severityDescription = effectiveSeverity?.description || staticProfile.rationale;

  const gradeLower = (severityGrade || '').toLowerCase();
  const severityColor = gradeLower.includes('severe') || gradeLower.includes('high')
    ? 'text-error'
    : gradeLower.includes('moderate')
    ? 'text-[#f59e0b]'
    : gradeLower.includes('mild') || gradeLower.includes('low')
    ? 'text-teal-400'
    : 'text-primary';

  const stage = dynamicStage || staticProfile.stage;
  const spatialCorrelation = dynamicSpatialCorrelation || staticProfile.spatialCorrelation;
  const rationale = severityAssessment?.diagnostic_rationale || effectiveSeverity?.diagnostic_rationale || staticProfile.rationale;
  
  const rawPrognosis = effectiveSeverity?.prognosis || staticProfile.prognosis;
  const prognosis = rawPrognosis;
  const progLower = (rawPrognosis || '').toLowerCase();
  const prognosisColor = progLower.includes('guarded') || progLower.includes('poor')
    ? 'text-error'
    : progLower.includes('fair') || progLower.includes('recoverable')
    ? 'text-[#f59e0b]'
    : 'text-primary';

  const evidenceItems = staticProfile.evidenceItems;

  const confidence = disease?.confidence
    ? disease.confidence.toFixed(1)
    : '0.0';

  const bestBbox = result?.best_detection?.bbox_normalized;
  const symptomsImage = result?.symptoms_image;
  const croppedImage = result?.cropped_image;

  const handleFile = (file) => {
    setCaseReport(null);
    setReportError(null);
    detect(file);
  };

  const handleResetAnalysis = () => {
    setActiveView('full');
    setShowSymptomMask(true);
    setCaseReport(null);
    setReportError(null);
    reset();
  };

  const handleReportCase = async () => {
    if (!result) return;
    setIsReporting(true);
    setReportError(null);
    try {
      const ownerName = localStorage.getItem('owner_name') || 'Farm Owner';
      const payload = {
        cattle_id: cattleId || null,
        farm_name: `${ownerName}'s Farm`,
        animal_identifier: cattleInfo?.identifier || 'COW-UNASSIGNED',
        breed: cattleInfo?.breed || 'Dairy Breed',
        disease_name: disease?.name || 'Cattle (Healthy)',
        confidence: parseFloat(confidence) || 0,
        severity: severityGrade,
        stage: stage,
        prognosis: prognosis,
        rationale: rationale,
        spatial_correlation: spatialCorrelation,
        symptoms_image: symptomsImage,
        cropped_image: croppedImage,
        clinical_notes: `Farmer-submitted AI diagnostic report. Pathology: ${disease?.name || 'Healthy'}. Severity: ${severityGrade} (${stage}). Awaiting veterinary verification.`,
        llm_reasoning: reasoning,
        verified: false, // Farmers create pending verification reports
      };

      const resData = await reportDiagnosticCase(payload);
      setCaseReport(resData);
    } catch (err) {
      console.error('Case reporting error:', err);
      setReportError(err.message || 'Failed to submit diagnostic report.');
    } finally {
      setIsReporting(false);
    }
  };

  const handleDeclareDeceasedSubmit = async (e) => {
    e.preventDefault();
    if (!cattleInfo) return;
    setSubmittingDeath(true);
    setDeathError('');
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE}/api/vet/cattle/${cattleInfo.id || cattleId}/declare-deceased`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          cause: deathCause,
          date_of_death: deathDate,
          notes: deathNotes
        })
      });

      if (response.ok) {
        const updated = await response.json();
        setCattleInfo(updated);
        setShowMortalityModal(false);
        setDeathSuccess(`Successfully updated ${cattleInfo.identifier} as deceased.`);
        setTimeout(() => setDeathSuccess(''), 5000);
      } else {
        const data = await response.json();
        setDeathError(data.detail || 'Failed to record mortality.');
      }
    } catch (err) {
      setDeathError('Network error. Unable to declare cattle deceased.');
    } finally {
      setSubmittingDeath(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Page Header */}
      <div className="mb-6 md:mb-8 flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4 pb-4 border-b border-outline-variant/10">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="px-2.5 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-3xs font-mono font-bold uppercase tracking-wider">
              Farmer AI Diagnostics
            </span>
            <span className="text-outline text-3xs">•</span>
            <span className="text-tertiary text-3xs font-mono">Vision Transformer &amp; Mask R-CNN</span>
          </div>
          <h2 className="text-2xl md:text-3xl lg:text-4xl font-extrabold text-on-surface tracking-tight">
            Smart Livestock Disease Diagnostics
          </h2>
          <p className="text-on-surface-variant text-xs md:text-sm max-w-2xl mt-1.5 leading-relaxed">
            Scan your cattle for early disease detection. Reports are securely transmitted to your assigned veterinarian for verification.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 shrink-0">
          <Link
            to="/health/case-history"
            className="text-slate-200 hover:text-white hover:bg-surface-container-highest font-bold text-xs flex items-center gap-2 border border-white/10 px-4 py-2.5 rounded-xl bg-surface-container-high transition-all shadow-sm shrink-0 active:scale-95"
            id="view-case-history-btn"
          >
            <span className="material-symbols-outlined text-base text-emerald-400">folder_open</span>
            My Case History
          </Link>
          {!isIdle && !isLoading && (
            <button
              onClick={handleResetAnalysis}
              className="text-primary hover:text-on-primary hover:bg-primary font-bold text-xs flex items-center gap-2 border border-primary/30 px-4 py-2.5 rounded-xl bg-primary/10 transition-all shadow-sm hover:shadow-glow-sm shrink-0 active:scale-95"
              id="new-analysis-btn"
            >
              <span className="material-symbols-outlined text-base">refresh</span>
              New Scan
            </button>
          )}
        </div>
      </div>

      {/* Success Notification for Mortality */}
      {deathSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2 animate-fadeIn">
          <span className="material-symbols-outlined text-base">check_circle</span>
          <span>{deathSuccess}</span>
        </div>
      )}

      {/* Subject Animal Clinical Context Card */}
      {cattleInfo && (
        <div className="p-4 md:p-5 rounded-2xl bg-gradient-to-r from-[#131b2e] via-[#0f172a] to-[#0b1326] border border-emerald-500/30 shadow-card-subtle flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-xl bg-surface-container-highest overflow-hidden border border-white/10 flex items-center justify-center flex-shrink-0">
              {cattleInfo.profile_photo ? (
                <img src={cattleInfo.profile_photo} alt={cattleInfo.identifier} className="w-full h-full object-cover" />
              ) : (
                <span className="material-symbols-outlined text-2xl text-emerald-400">pets</span>
              )}
            </div>
            <div>
              <div className="flex items-center gap-2 mb-0.5">
                <span className="px-2.5 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 text-3xs font-mono font-bold uppercase border border-emerald-500/20">
                  Selected Animal
                </span>
                <span className="text-slate-500">•</span>
                <span className="text-slate-400 text-3xs font-mono">{cattleInfo.breed || 'Dairy Breed'}</span>
              </div>
              <h3 className="text-lg font-bold text-white font-mono flex items-center gap-2">
                {cattleInfo.identifier}
                <span className="text-xs font-normal text-slate-300">({cattleInfo.gender || 'Bovine'})</span>
              </h3>
              <p className="text-2xs text-slate-400 mt-0.5">
                Current Health Status:{' '}
                <span className={`font-bold ${cattleInfo.status === 'Deceased' ? 'text-red-500' : cattleInfo.health_status === 'Alert' ? 'text-amber-400' : 'text-emerald-400'}`}>
                  {cattleInfo.status === 'Deceased' ? 'Deceased' : (cattleInfo.health_status || 'Healthy')}
                </span>
                {cattleInfo.bcs_score !== null && cattleInfo.bcs_score !== undefined && (
                  <span> • BCS: <strong className="text-emerald-400 font-mono">{Number(cattleInfo.bcs_score).toFixed(1)}</strong></span>
                )}
                {cattleInfo.weight && <span> • Weight: <strong className="text-slate-200 font-mono">{cattleInfo.weight} kg</strong></span>}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end md:self-auto">
            {cattleInfo.status !== 'Deceased' && (
              <button
                type="button"
                onClick={() => setShowMortalityModal(true)}
                className="px-3.5 py-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-300 text-xs font-mono font-bold flex items-center gap-1.5 transition-all"
              >
                <span className="material-symbols-outlined text-sm">skull</span>
                <span>Confirm Mortality</span>
              </button>
            )}
            <Link
              to="/health/herd-registry"
              className="px-3.5 py-2 rounded-lg bg-surface-container-highest/60 hover:bg-surface-container-highest border border-white/10 text-slate-300 hover:text-white text-xs font-mono flex items-center gap-1.5 transition-all"
            >
              <span className="material-symbols-outlined text-sm">arrow_back</span>
              <span>Change Animal</span>
            </Link>
          </div>
        </div>
      )}

      {/* Unassigned Animal Guidance Banner */}
      {!cattleInfo && !loadingContext && (
        <div className="p-4 rounded-xl bg-surface-container-low border border-outline-variant/15 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-card-subtle">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 text-primary flex items-center justify-center flex-shrink-0">
              <span className="material-symbols-outlined text-lg">info</span>
            </div>
            <div>
              <p className="text-xs font-bold text-on-surface">General Diagnostic Scan</p>
              <p className="text-2xs text-on-surface-variant">
                You can run a scan directly, or select a specific cattle from your Herd Registry to link this report to its permanent profile.
              </p>
            </div>
          </div>
          <Link
            to="/health/herd-registry"
            className="px-3.5 py-1.5 rounded-lg bg-primary/15 hover:bg-primary/25 border border-primary/30 text-primary text-xs font-bold font-mono uppercase tracking-wider flex items-center gap-1.5 shrink-0 transition-all"
          >
            <span className="material-symbols-outlined text-sm">pets</span>
            <span>Select Cattle</span>
          </Link>
        </div>
      )}

      {/* Failure Alert Banner */}
      {isFailure && (
        <div className="mb-8" id="alert-container">
          <div className="flex-1 p-4 md:p-5 rounded-xl bg-surface-container-low border-l-4 border-error border border-outline-variant/10 flex items-start sm:items-center gap-3.5 shadow-card-subtle">
            <div className="p-2 bg-error/10 rounded-lg shrink-0">
              <span className="material-symbols-outlined text-error text-xl">error</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs md:text-sm font-bold text-on-surface">Analysis Inconclusive</p>
              <p className="text-2xs md:text-xs text-on-surface-variant mt-0.5">
                {error || 'No bovine features detected or image clarity is insufficient. Please provide a clear, well-lit photo of the cattle.'}
              </p>
            </div>
            <button
              onClick={reset}
              className="p-1 text-on-surface-variant hover:text-on-surface rounded-md hover:bg-surface-container-high transition-colors shrink-0"
              aria-label="Dismiss alert"
            >
              <span className="material-symbols-outlined text-base">close</span>
            </button>
          </div>
        </div>
      )}

      <div className="min-h-[400px] md:min-h-[500px]">
        {/* ========= DECEASED LOCK VIEW ========= */}
        {cattleInfo && (cattleInfo.status === 'Deceased' || cattleInfo.health_status === 'Deceased') ? (
          <div className="p-6 bg-error-container text-on-error-container border border-error rounded-2xl space-y-4 max-w-xl mx-auto text-center" data-testid="diagnostics-locked-banner">
            <div className="flex items-center justify-center gap-2 font-bold text-lg">
              <span className="material-symbols-outlined text-2xl">block</span>
              <span>Diagnostics Locked</span>
            </div>
            <p className="text-sm">Diagnostics are locked for deceased cattle. Disease reporting is disabled for this animal.</p>
            <Link
              to="/health/herd-registry"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-error text-on-error hover:brightness-110 rounded-xl text-xs font-bold uppercase tracking-wider transition-all select-none cursor-pointer"
            >
              <span className="material-symbols-outlined text-sm">arrow_back</span>
              <span>Return to Herd Registry</span>
            </Link>
          </div>
        ) : (
          <>
            {/* ========= IDLE / LOADING VIEW ========= */}
            {(isIdle || isLoading) && (
              <UploadDropzone isLoading={isLoading} onFile={handleFile} />
            )}
          </>
        )}

        {/* ========= SUCCESS VIEW ========= */}
        {isSuccess && (
          <div className="space-y-6" data-testid="success-view">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

              {/* Column 1: Symptom Analysis (7/12) */}
              <div className="lg:col-span-7">
                <div className="bg-surface-container-low rounded-2xl p-4 md:p-6 h-full flex flex-col overflow-hidden relative border border-outline-variant/15 shadow-card-subtle">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-3 md:mb-4 pb-3 border-b border-outline-variant/10">
                    <div className="flex items-center gap-2.5">
                      <div className="p-1.5 bg-primary/10 rounded-lg border border-primary/20">
                        <span className="material-symbols-outlined text-primary text-base">visibility</span>
                      </div>
                      <span className="text-xs font-bold text-primary tracking-widest uppercase font-mono">
                        02 Symptom Analysis
                      </span>
                      {symptomsImage ? (
                        <span className="px-2 py-0.5 bg-rose-500/15 text-rose-400 text-3xs rounded-md font-mono font-bold uppercase tracking-wider border border-rose-500/30 flex items-center gap-1.5 shadow-sm">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-ping" />
                          Mask R-CNN Active
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 bg-primary/15 text-primary text-3xs rounded-md font-mono font-bold uppercase tracking-wider border border-primary/30 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-primary animate-ping" />
                          Live Scan
                        </span>
                      )}
                    </div>
                    <div className="text-3xs font-mono text-outline">
                      {symptomsImage ? 'MASK_RCNN_LAYER_03' : 'YOLO_LAYER_01'}
                    </div>
                  </div>

                  {/* View Switcher Toolbar */}
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                    <div className="flex items-center p-0.5 bg-surface-container rounded-lg border border-outline-variant/20">
                      <button
                        type="button"
                        onClick={() => setActiveView('full')}
                        className={`px-2.5 py-1 rounded-md text-3xs font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all ${
                          activeView === 'full'
                            ? 'bg-primary text-on-primary shadow-sm'
                            : 'text-on-surface-variant hover:text-on-surface'
                        }`}
                      >
                        <span className="material-symbols-outlined text-xs">aspect_ratio</span>
                        Full Scan
                      </button>
                      <button
                        type="button"
                        onClick={() => setActiveView('lesion')}
                        className={`px-2.5 py-1 rounded-md text-3xs font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all ${
                          activeView === 'lesion'
                            ? 'bg-primary text-on-primary shadow-sm'
                            : 'text-on-surface-variant hover:text-on-surface'
                        }`}
                      >
                        <span className="material-symbols-outlined text-xs">zoom_in</span>
                        Lesion ROI
                      </button>
                    </div>

                    {symptomsImage && (
                      <button
                        type="button"
                        onClick={() => setShowSymptomMask(!showSymptomMask)}
                        className={`px-2.5 py-1 rounded-lg text-3xs font-mono font-bold uppercase tracking-wider border transition-all flex items-center gap-1.5 ${
                          showSymptomMask
                            ? 'bg-rose-500/15 border-rose-500/40 text-rose-300'
                            : 'bg-surface-container border-outline-variant/30 text-outline'
                        }`}
                      >
                        <span className="material-symbols-outlined text-xs">
                          {showSymptomMask ? 'layers' : 'layers_clear'}
                        </span>
                        <span>{showSymptomMask ? 'Symptom Mask ON' : 'Symptom Mask OFF'}</span>
                      </button>
                    )}
                  </div>

                  {/* Visual Image Viewport */}
                  <div className="relative rounded-xl overflow-hidden bg-black/60 aspect-[4/3] flex items-center justify-center border border-outline-variant/10 shadow-inner group">
                    {activeView === 'lesion' && croppedImage ? (
                      <img
                        src={showSymptomMask && symptomsImage ? symptomsImage : croppedImage}
                        alt="Lesion Region of Interest"
                        className="w-full h-full object-contain"
                      />
                    ) : (
                      <img
                        src={showSymptomMask && symptomsImage ? symptomsImage : (imagePreview || croppedImage)}
                        alt="Clinical Cattle Scan"
                        className="w-full h-full object-cover"
                      />
                    )}

                    {/* Bounding Box overlay for full view */}
                    {activeView === 'full' && bestBbox && !symptomsImage && (
                      <div
                        className="absolute border-2 border-primary/80 bg-primary/10 rounded pointer-events-none transition-all duration-300"
                        style={{
                          top: `${bestBbox.y1 * 100}%`,
                          left: `${bestBbox.x1 * 100}%`,
                          width: `${(bestBbox.x2 - bestBbox.x1) * 100}%`,
                          height: `${(bestBbox.y2 - bestBbox.y1) * 100}%`,
                        }}
                      >
                        <span className="absolute -top-5 left-0 px-1.5 py-0.5 bg-primary text-on-primary text-3xs font-mono font-bold rounded">
                          BOVINE_SUBJECT ({((result?.best_detection?.confidence || 0.9) * 100).toFixed(0)}%)
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Visual Telemetry Footnote */}
                  <div className="mt-3 flex items-center justify-between text-3xs text-outline font-mono">
                    <span>ANATOMICAL_SEGMENTATION: ACTIVE</span>
                    <span>RESOLUTION: {result?.image_size?.width || 640}x{result?.image_size?.height || 480}</span>
                  </div>
                </div>
              </div>

              {/* Column 2: AI Logic Trace & Disease Reporting (5/12) */}
              <div className="lg:col-span-5">
                <div className="bg-surface-container-low rounded-2xl p-4 md:p-6 border border-outline-variant/15 shadow-card-subtle h-full flex flex-col justify-between">
                  <div className="space-y-4">
                    {/* Section Header */}
                    <div className="flex items-center justify-between pb-3 border-b border-outline-variant/10">
                      <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-primary/10 rounded-lg border border-primary/20">
                          <span className="material-symbols-outlined text-primary text-base">account_tree</span>
                        </div>
                        <span className="text-xs font-bold text-primary tracking-widest uppercase font-mono">
                          03 Logic Trace &amp; Classification
                        </span>
                      </div>
                      <span className="text-3xs font-mono text-outline">TRIAGE_V3</span>
                    </div>

                    {/* Logic Steps */}
                    <div className="space-y-2 text-xs font-mono">
                      {/* Step 1: Bovine Localization */}
                      <div className={`p-2.5 rounded-xl border transition-all duration-300 ${visibleSteps >= 1 ? 'bg-surface-container border-primary/30 opacity-100' : 'bg-surface-container/30 border-transparent opacity-30'}`}>
                        <div className="flex items-center justify-between text-2xs mb-0.5">
                          <span className="text-outline uppercase font-bold">Step 1 • Detection</span>
                          <span className="text-primary font-bold">PASS</span>
                        </div>
                        <p className="text-on-surface font-semibold text-2xs">Bovine Localization Confirmed</p>
                      </div>

                      {/* Step 2: ViT Classification */}
                      <div className={`p-2.5 rounded-xl border transition-all duration-300 ${visibleSteps >= 2 ? 'bg-surface-container border-primary/30 opacity-100' : 'bg-surface-container/30 border-transparent opacity-30'}`}>
                        <div className="flex items-center justify-between text-2xs mb-0.5">
                          <span className="text-outline uppercase font-bold">Step 2 • Classification</span>
                          <span className="text-primary font-bold">{confidence}%</span>
                        </div>
                        <p className="text-on-surface font-extrabold text-xs text-primary">{disease?.name || 'Undetermined'}</p>
                      </div>

                      {/* Step 3: Clinical Metrics */}
                      <div className={`p-2.5 rounded-xl border transition-all duration-300 ${visibleSteps >= 3 ? 'bg-surface-container border-primary/30 opacity-100' : 'bg-surface-container/30 border-transparent opacity-30'}`}>
                        <div className="flex items-center justify-between text-2xs mb-0.5">
                          <span className="text-outline uppercase font-bold">Step 3 • Severity Assessment</span>
                          <span className={`font-bold ${severityColor}`}>{severityGrade}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 mt-1 text-3xs text-on-surface-variant">
                          <div>Stage: <strong className="text-white">{stage}</strong></div>
                          <div>Prognosis: <strong className={prognosisColor}>{prognosis}</strong></div>
                        </div>
                      </div>
                    </div>

                    {/* Pathological Narrative */}
                    {severityDescription && (
                      <div className="p-3 rounded-xl bg-surface-container border border-outline-variant/15 text-2xs text-on-surface-variant leading-relaxed">
                        <span className="text-outline uppercase font-bold tracking-wider block mb-1 text-3xs">
                          Clinical Telemetry Summary
                        </span>
                        <p>{severityDescription}</p>
                      </div>
                    )}
                  </div>

                  {/* Report Action Area for Farmer */}
                  <div className="mt-5 pt-4 border-t border-outline-variant/15">
                    {caseReport ? (
                      <div className="p-4 rounded-xl bg-emerald-500/15 border border-emerald-500/30 space-y-3 animate-fadeIn" data-testid="farmer-reported-case-banner">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs">
                            <span className="material-symbols-outlined text-base">forward_to_inbox</span>
                            <span>Report Submitted to Veterinarian</span>
                          </div>
                          <span className="text-[10px] font-mono text-emerald-300 font-bold px-2 py-0.5 rounded bg-emerald-500/20">
                            {caseReport.case_number}
                          </span>
                        </div>
                        <p className="text-2xs text-slate-300 leading-relaxed">
                          Your report for <strong>{caseReport.animal_identifier || cattleInfo?.identifier || 'this cattle'}</strong> has been sent to your assigned veterinarian. It is currently <strong>Pending Verification</strong>.
                        </p>
                        <div className="flex items-center gap-2 pt-1">
                          <button
                            onClick={() => navigate('/health/case-history')}
                            className="flex-1 py-2 px-3 rounded-lg bg-emerald-500 text-black font-bold text-xs uppercase tracking-wider hover:brightness-110 transition-all text-center flex items-center justify-center gap-1"
                          >
                            <span className="material-symbols-outlined text-xs">folder_open</span>
                            <span>View Case History</span>
                          </button>
                          <button
                            onClick={handleResetAnalysis}
                            className="py-2 px-3 rounded-lg bg-white/5 hover:bg-white/10 text-white text-xs font-bold transition-all border border-white/10"
                          >
                            New Scan
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2.5">
                        {reportError && (
                          <div className="p-2.5 rounded-lg bg-error/15 border border-error/30 text-error text-2xs flex items-center gap-2">
                            <span className="material-symbols-outlined text-sm">error</span>
                            <span>{reportError}</span>
                          </div>
                        )}
                        <button
                          onClick={handleReportCase}
                          disabled={isReporting}
                          className="w-full primary-gradient text-on-primary py-3 rounded-xl font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2.5 shadow-lg shadow-primary/15 hover:shadow-primary/30 hover:brightness-105 active:scale-[0.98] transition-all disabled:opacity-50"
                          id="farmer-report-btn"
                          data-testid="farmer-report-btn"
                        >
                          {isReporting ? (
                            <>
                              <span className="material-symbols-outlined text-base animate-spin">progress_activity</span>
                              <span>Submitting Disease Report...</span>
                            </>
                          ) : (
                            <>
                              <span className="material-symbols-outlined text-base">send</span>
                              <span>Report Disease Case to Veterinarian</span>
                            </>
                          )}
                        </button>
                        <p className="text-center text-3xs text-outline mt-2 font-medium flex items-center justify-center gap-1">
                          <span className="material-symbols-outlined text-xs">verified_user</span>
                          Case will be reviewed and verified by your assigned clinical veterinarian.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Model Reasoning & Evidence Section */}
            <div className={`bg-surface-container-low rounded-2xl p-5 md:p-8 border border-outline-variant/15 shadow-card-subtle transition-all duration-700 delay-300 ${visibleSteps >= 5 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
              <div className="flex items-center gap-3 mb-6 pb-4 border-b border-outline-variant/10">
                <div className="p-2.5 bg-primary/10 rounded-xl border border-primary/20">
                  <span className="material-symbols-outlined text-primary text-xl md:text-2xl">clinical_notes</span>
                </div>
                <div>
                  <h3 className="text-base md:text-lg font-bold text-on-surface tracking-tight">
                    Model Reasoning &amp; Evidence
                  </h3>
                  <span className="text-2xs font-mono text-outline">
                    MULTI-MODAL FEATURE CORRELATION
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
                {/* Left: Rationale cards */}
                <div className="space-y-4">
                  <div className="p-4 bg-surface-container/60 rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-colors">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-primary shadow-glow-sm" />
                        <h4 className="text-2xs font-bold text-primary uppercase tracking-widest font-mono">
                          Diagnostic Rationale
                        </h4>
                      </div>
                      <span className="text-[9px] font-mono font-bold text-primary px-1.5 py-0.5 rounded bg-primary/10">
                        {severityAssessment?.diagnostic_rationale ? 'LLM REASONED' : 'VISION INFERENCE'}
                      </span>
                    </div>
                    <p className="text-xs md:text-sm text-on-surface-variant leading-relaxed">
                      {rationale}
                    </p>
                  </div>
                  <div className="p-4 bg-surface-container/60 rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-colors">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-primary shadow-glow-sm" />
                        <h4 className="text-2xs font-bold text-primary uppercase tracking-widest font-mono">
                          Spatial Correlation
                        </h4>
                      </div>
                      <span className="text-[9px] font-mono font-bold text-primary px-1.5 py-0.5 rounded bg-primary/10">
                        {severityAssessment?.spatial_correlation ? 'ANATOMICAL TELEMETRY' : 'MASK R-CNN ROI'}
                      </span>
                    </div>
                    <p className="text-xs md:text-sm text-on-surface-variant leading-relaxed">
                      {spatialCorrelation}
                    </p>
                  </div>
                </div>

                {/* Right: Confidence score + evidence list */}
                <div className="bg-surface-container-highest/40 backdrop-blur-sm rounded-xl p-5 md:p-6 flex flex-col justify-center border border-primary/15">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-bold text-on-surface-variant">Evidence Confidence Score</span>
                    <span className="text-xl md:text-2xl font-black text-primary font-mono tracking-tight">
                      {confidence}%
                    </span>
                  </div>
                  <div className="w-full bg-surface-container rounded-full h-2.5 mb-5 p-0.5 border border-outline-variant/20">
                    <div
                      className="primary-gradient h-full rounded-full transition-all duration-1000 shadow-glow-sm"
                      style={{ width: `${confidence}%` }}
                    />
                  </div>
                  <ul className="space-y-2.5">
                    {(evidenceItems || []).map((item, idx) => (
                      <li key={idx} className="flex items-start gap-2.5 text-xs text-on-surface-variant leading-relaxed">
                        <span className="material-symbols-outlined text-primary text-sm shrink-0 mt-0.5" style={{ fontVariationSettings: "'FILL' 1" }}>
                          check_circle
                        </span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* Tier 3 — AI Clinical Briefing (LLM Reasoning) */}
            <ReasoningBriefing
              reasoning={reasoning}
              reasoningStatus={reasoningStatus}
              reasoningError={reasoningError}
              severityAssessment={severityAssessment}
            />
          </div>
        )}

        {/* ========= FAILURE VIEW ========= */}
        {isFailure && (
          <div
            className="w-full bg-surface-container-low rounded-2xl p-8 md:p-14 border border-error/25 shadow-card-subtle flex flex-col items-center justify-center relative overflow-hidden"
            data-testid="failure-view"
          >
            <div className="w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-error/10 border border-error/20 flex items-center justify-center mb-6 shadow-sm">
              <span className="material-symbols-outlined text-3xl md:text-4xl text-error">
                sentiment_very_dissatisfied
              </span>
            </div>
            <h3 className="text-lg md:text-xl font-bold text-on-surface mb-2 text-center tracking-tight">Diagnosis Inconclusive</h3>
            <p className="text-on-surface-variant text-center max-w-md mb-8 text-xs md:text-sm leading-relaxed">
              {error || 'Our AI engine could not reliably identify bovine features or clinical lesions in the provided asset. Please ensure the lighting is adequate and the cattle subject is clearly visible.'}
            </p>
            <button
              onClick={reset}
              className="px-6 md:px-8 py-3 bg-surface-container-highest border border-outline-variant/30 rounded-xl font-bold text-xs uppercase tracking-wider hover:bg-surface-bright hover:border-primary/40 transition-all text-on-surface shadow-sm active:scale-95 flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-base">arrow_back</span>
              Try Another Image
            </button>
          </div>
        )}
      </div>

      {/* Mortality Confirmation Modal */}
      {showMortalityModal && cattleInfo && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-[#0f172a] border border-red-500/30 max-w-md w-full rounded-2xl p-6 shadow-2xl space-y-4 text-white">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-500/20 text-red-400 flex items-center justify-center">
                <span className="material-symbols-outlined text-2xl">skull</span>
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Declare Cattle Deceased</h3>
                <p className="text-xs text-slate-400">Animal Tag: <strong className="text-white font-mono">{cattleInfo.identifier}</strong></p>
              </div>
            </div>

            <form onSubmit={handleDeclareDeceasedSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="block text-xs font-mono font-bold uppercase text-slate-400">Date of Death</label>
                <input
                  type="date"
                  required
                  value={deathDate}
                  onChange={(e) => setDeathDate(e.target.value)}
                  className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-red-500"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-mono font-bold uppercase text-slate-400">Cause of Death</label>
                <select
                  value={deathCause}
                  onChange={(e) => setDeathCause(e.target.value)}
                  className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-red-500"
                >
                  <option value="FMD">Foot-and-Mouth Disease (FMD)</option>
                  <option value="LSD">Lumpy Skin Disease (LSD)</option>
                  <option value="Other">Other / Natural Mortality</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="block text-xs font-mono font-bold uppercase text-slate-400">Remarks / Observation</label>
                <textarea
                  value={deathNotes}
                  onChange={(e) => setDeathNotes(e.target.value)}
                  placeholder="Provide context or symptoms observed prior to mortality..."
                  rows="3"
                  className="w-full bg-slate-900 border border-white/10 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-red-500 placeholder-slate-600"
                />
              </div>

              {deathError && (
                <div className="p-2.5 rounded-lg bg-red-500/15 border border-red-500/30 text-red-400 text-xs flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">error</span>
                  <span>{deathError}</span>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowMortalityModal(false)}
                  disabled={submittingDeath}
                  className="flex-1 py-2 px-4 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white text-xs font-bold transition-all"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingDeath}
                  className="flex-1 py-2 px-4 rounded-lg bg-red-600 hover:bg-red-700 text-white text-xs font-bold transition-all flex items-center justify-center gap-1"
                >
                  {submittingDeath ? (
                    <>
                      <span className="material-symbols-outlined text-xs animate-spin">progress_activity</span>
                      <span>Recording...</span>
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined text-xs">check</span>
                      <span>Confirm Deceased</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default FarmerSmartDiagnostics;
