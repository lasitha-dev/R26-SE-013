import React, { useEffect, useState } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import UploadDropzone from './components/UploadDropzone';
import ReasoningBriefing from './components/ReasoningBriefing';
import useDetection from './hooks/useDetection';
import { getDiseaseProfile } from './diseaseProfiles';
import { reportDiagnosticCase, verifyDiagnosticCase } from './services/api';

/**
 * SmartDiagnostics — main feature page for AI-Powered Smart Diagnosis.
 *
 * Implements the full Stitch "AI Smart Diagnosis - Prototype with Reasoning" layout:
 * - 01 Image Intake (upload dropzone)
 * - 02 Symptom Analysis (annotated image with scan-line & spotlight)
 * - 03 AI Logic Trace (animated step reveal + inference results)
 * - Model Reasoning & Evidence (rationale + confidence score)
 */
const SmartDiagnostics = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const cattleId = searchParams.get('cattle_id');
  const farmId = searchParams.get('farm_id');

  const [cattleInfo, setCattleInfo] = useState(null);
  const [farmInfo, setFarmInfo] = useState(null);
  const [existingCase, setExistingCase] = useState(null);
  const [loadingContext, setLoadingContext] = useState(false);

  // Case reporting and verification states
  const [caseReport, setCaseReport] = useState(null);
  const [isReporting, setIsReporting] = useState(false);
  const [reportError, setReportError] = useState(null);

  const {
    status, result, error, imagePreview, detect, reset,
    reasoning, reasoningStatus, reasoningError, severityAssessment,
  } = useDetection();
  const [visibleSteps, setVisibleSteps] = useState(0);
  const [showSymptomMask, setShowSymptomMask] = useState(true);
  const [activeView, setActiveView] = useState('full'); // 'full' | 'lesion'

  // Fetch cattle metadata and existing cases if cattleId is passed in URL
  useEffect(() => {
    const fetchCattleContext = async () => {
      if (!cattleId) {
        setCattleInfo(null);
        setFarmInfo(null);
        setExistingCase(null);
        return;
      }
      setLoadingContext(true);
      try {
        const token = localStorage.getItem('token');
        const res = await fetch(`http://127.0.0.1:8000/api/cattle/${cattleId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
        if (res.ok) {
          const data = await res.json();
          setCattleInfo(data);
        }

        if (farmId) {
          const farmRes = await fetch(`http://127.0.0.1:8000/api/vet/farms/${farmId}/cattle`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {}
          });
          if (farmRes.ok) {
            const fData = await farmRes.json();
            setFarmInfo(fData.farm || null);
          }
        }

        // Fetch existing diagnostic case for this cattle
        const casesRes = await fetch(`http://127.0.0.1:8000/api/vet/cases`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
        if (casesRes.ok) {
          const casesList = await casesRes.json();
          if (Array.isArray(casesList)) {
            const matched = casesList.find((c) => c.cattle_id === cattleId);
            if (matched) {
              setExistingCase(matched);
            }
          }
        }
      } catch (err) {
        console.error('Error fetching cattle context:', err);
      } finally {
        setLoadingContext(false);
      }
    };
    fetchCattleContext();
  }, [cattleId, farmId]);

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

  // Prioritize LLM-synthesized severity assessment over initial vision telemetry
  const effectiveSeverity = severityAssessment || result?.severity;
  const dynamicSeverity = effectiveSeverity;
  const dynamicStage = severityAssessment?.stage || result?.stage;
  const dynamicSpatialCorrelation = severityAssessment?.spatial_correlation || result?.spatial_correlation;

  const severityGrade = effectiveSeverity?.grade || (staticProfile.severity.split('/')[1] || '').trim() || 'Moderate';
  const severityDescription = effectiveSeverity?.description || staticProfile.rationale;
  const severityFormatted = effectiveSeverity?.formatted || (effectiveSeverity?.grade ? `${effectiveSeverity.grade} (${dynamicStage || 'Active'})` : staticProfile.severity);

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

  // Get best detection bounding box and Mask R-CNN segmentation image
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

  const handleVerifyAndReport = async () => {
    if (!result) return;
    setIsReporting(true);
    setReportError(null);
    try {
      const payload = {
        cattle_id: cattleId || null,
        farm_id: farmId || null,
        farm_name: farmInfo?.owner_name ? `${farmInfo.owner_name}'s Farm` : null,
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
        clinical_notes: `Clinical verification completed by authorized veterinary practitioner. Pathology: ${disease?.name || 'Healthy'}. Severity: ${severityGrade} (${stage}). Pathological assessment: ${severityDescription}`,
        llm_reasoning: reasoning,
        verified: true,
      };

      const resData = await reportDiagnosticCase(payload);
      setCaseReport(resData);
    } catch (err) {
      console.error('Case verification error:', err);
      setReportError(err.message || 'Failed to submit verified case report.');
    } finally {
      setIsReporting(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Page Title + Header Actions */}
      <div className="mb-6 md:mb-8 flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4 pb-4 border-b border-outline-variant/10">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="px-2.5 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-3xs font-mono font-bold uppercase tracking-wider">
              Diagnostic Intake &amp; Visual Triage
            </span>
            <span className="text-outline text-3xs">•</span>
            <span className="text-tertiary text-3xs font-mono">CV Pipeline v3.2</span>
          </div>
          <h2 className="text-2xl md:text-3xl lg:text-4xl font-extrabold text-on-surface tracking-tight">
            AI-Powered Smart Diagnosis System
          </h2>
          <p className="text-on-surface-variant text-xs md:text-sm max-w-2xl mt-1.5 leading-relaxed">
            Upload clinical imagery for automated feature extraction, visual highlighting, and logic tracing.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 shrink-0">
          <Link
            to="/vet/clinical-records"
            className="text-slate-200 hover:text-white hover:bg-surface-container-highest font-bold text-xs flex items-center gap-2 border border-white/10 px-4 py-2.5 rounded-xl bg-surface-container-high transition-all shadow-sm shrink-0 active:scale-95"
            id="view-clinical-records-btn"
          >
            <span className="material-symbols-outlined text-base text-emerald-400">folder_open</span>
            Clinical Case Records
          </Link>
          {!isIdle && !isLoading && (
            <button
              onClick={handleResetAnalysis}
              className="text-primary hover:text-on-primary hover:bg-primary font-bold text-xs flex items-center gap-2 border border-primary/30 px-4 py-2.5 rounded-xl bg-primary/10 transition-all shadow-sm hover:shadow-glow-sm shrink-0 active:scale-95"
              id="new-analysis-btn"
            >
              <span className="material-symbols-outlined text-base">refresh</span>
              New Analysis
            </button>
          )}
        </div>
      </div>

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
                  Target Livestock Record
                </span>
                <span className="text-slate-500">•</span>
                <span className="text-slate-400 text-3xs font-mono">{farmInfo?.location_district || 'Regional Node'}</span>
                {existingCase && (
                  <span className="px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-300 text-3xs font-mono font-bold uppercase border border-amber-500/30">
                    Existing Case: {existingCase.case_number}
                  </span>
                )}
              </div>
              <h3 className="text-lg font-bold text-white font-mono flex items-center gap-2">
                {cattleInfo.identifier}
                <span className="text-xs font-normal text-slate-300">({cattleInfo.breed})</span>
              </h3>
              <p className="text-2xs text-slate-400 mt-0.5">
                Estate: <strong className="text-slate-200">{farmInfo?.owner_name ? `${farmInfo.owner_name}'s Farm` : 'Assigned Farm'}</strong> • Current Status:{' '}
                <span className={`font-bold ${cattleInfo.health_status === 'Alert' ? 'text-red-400' : 'text-emerald-400'}`}>
                  {cattleInfo.health_status || 'Healthy'}
                </span>
                {cattleInfo.bcs_score !== null && cattleInfo.bcs_score !== undefined && (
                  <span> • BCS: <strong className="text-emerald-400 font-mono">{Number(cattleInfo.bcs_score).toFixed(1)}</strong></span>
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end md:self-auto">
            {farmId && (
              <Link
                to={`/vet/farm/${farmId}`}
                className="px-3.5 py-2 rounded-lg bg-surface-container-highest/60 hover:bg-surface-container-highest border border-white/10 text-slate-300 hover:text-white text-xs font-mono flex items-center gap-1.5 transition-all"
              >
                <span className="material-symbols-outlined text-sm">arrow_back</span>
                <span>Change Cattle</span>
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Unassigned Animal Protocol Warning Banner */}
      {!cattleInfo && !loadingContext && (
        <div className="p-4 rounded-xl bg-surface-container-low border border-outline-variant/15 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-card-subtle">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 text-primary flex items-center justify-center flex-shrink-0">
              <span className="material-symbols-outlined text-lg">info</span>
            </div>
            <div>
              <p className="text-xs font-bold text-on-surface">Unassigned Diagnostic Session</p>
              <p className="text-2xs text-on-surface-variant">
                To link this clinical diagnosis directly to an animal ear tag and sync herd telemetry, select a cattle from your assigned estates.
              </p>
            </div>
          </div>
          <Link
            to="/vet/assigned-farms"
            className="px-3.5 py-1.5 rounded-lg bg-primary/15 hover:bg-primary/25 border border-primary/30 text-primary text-xs font-bold font-mono uppercase tracking-wider flex items-center gap-1.5 shrink-0 transition-all"
          >
            <span className="material-symbols-outlined text-sm">agriculture</span>
            <span>Select Animal from Herd</span>
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
              <p className="text-xs md:text-sm font-bold text-on-surface">Analysis Failed</p>
              <p className="text-2xs md:text-xs text-on-surface-variant mt-0.5">
                {error || 'Cattle not identified or low quality image. Please retry with a clearer asset.'}
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
            <p className="text-sm">Diagnostics locked for deceased cattle. Disease reporting is locked for deceased subjects.</p>
            {farmId && (
              <Link
                to={`/components/health_anomaly`}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(`/vet/farm/${farmId}`);
                }}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-error text-on-error hover:brightness-110 rounded-xl text-xs font-bold uppercase tracking-wider transition-all select-none cursor-pointer"
              >
                <span className="material-symbols-outlined text-sm">arrow_back</span>
                <span>Return to Herd View</span>
              </Link>
            )}
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

              {/* Column 1: Symptom Analysis (7/12 on desktop) */}
              <div className="lg:col-span-7">
                <div className="bg-surface-container-low rounded-2xl p-4 md:p-6 h-full flex flex-col overflow-hidden relative border border-outline-variant/15 shadow-card-subtle">
                  {/* Section header */}
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

                  {/* Diagnostic Layer & View Controls Toolbar */}
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                    {/* View Switcher: Full Scan vs Lesion Focus */}
                    <div className="flex items-center p-0.5 bg-surface-container rounded-lg border border-outline-variant/20">
                      <button
                        type="button"
                        onClick={() => setActiveView('full')}
                        className={`px-2.5 py-1 rounded-md text-3xs font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all ${
                          activeView === 'full'
                            ? 'bg-primary text-on-primary shadow-sm'
                            : 'text-on-surface-variant hover:text-on-surface'
                        }`}
                        id="view-mode-full-btn"
                        data-testid="view-mode-full-btn"
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
                        id="view-mode-lesion-btn"
                        data-testid="view-mode-lesion-btn"
                      >
                        <span className="material-symbols-outlined text-xs">zoom_in</span>
                        Lesion Focus
                      </button>
                    </div>

                    {/* Mask R-CNN Symptom Overlay Toggle */}
                    {symptomsImage && (
                      <button
                        type="button"
                        onClick={() => setShowSymptomMask((prev) => !prev)}
                        className={`px-2.5 py-1 rounded-lg text-3xs font-mono font-bold uppercase tracking-wider border flex items-center gap-1.5 transition-all cursor-pointer ${
                          showSymptomMask
                            ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-glow-sm'
                            : 'bg-surface-container text-on-surface-variant border-outline-variant/20 hover:text-on-surface'
                        }`}
                        id="toggle-symptom-mask-btn"
                        data-testid="toggle-symptom-mask-btn"
                      >
                        <span className="material-symbols-outlined text-xs">
                          {showSymptomMask ? 'layers' : 'layers_clear'}
                        </span>
                        Symptom Mask: <span className="font-bold">{showSymptomMask ? 'VISIBLE' : 'HIDDEN'}</span>
                      </button>
                    )}
                  </div>

                  {/* Image Viewer Container */}
                  <div
                    className="relative flex-1 min-h-[280px] md:min-h-[420px] rounded-xl overflow-hidden group scanning bg-surface-container-lowest/90 border border-outline-variant/20 select-none flex items-center justify-center"
                    id="image-container"
                  >
                    {/* Clinical Framing Corner Brackets */}
                    <div className="absolute top-2 left-2 w-3.5 h-3.5 border-t-2 border-l-2 border-primary z-20 pointer-events-none" />
                    <div className="absolute top-2 right-2 w-3.5 h-3.5 border-t-2 border-r-2 border-primary z-20 pointer-events-none" />
                    <div className="absolute bottom-2 left-2 w-3.5 h-3.5 border-b-2 border-l-2 border-primary z-20 pointer-events-none" />
                    <div className="absolute bottom-2 right-2 w-3.5 h-3.5 border-b-2 border-r-2 border-primary z-20 pointer-events-none" />

                    {/* Scan Line */}
                    <div className="scan-line" />

                    {/* ===== FULL SCAN VIEW ===== */}
                    {activeView === 'full' && (
                      <>
                        {/* Cattle Image (darkened to draw contrast to detected region) */}
                        <img
                          className="w-full h-full object-cover transition-all duration-700 image-dimmed"
                          src={imagePreview}
                          alt="Uploaded clinical image"
                        />

                        {/* Bounding box / lesion spotlight overlay */}
                        {bestBbox && (
                          <div className="absolute inset-0 opacity-100 transition-opacity duration-500 pointer-events-none">
                            {/* High-illumination spotlight area & Mask R-CNN overlay */}
                            <div
                              className={`absolute rounded-xl border-2 transition-all duration-300 overflow-hidden ${
                                symptomsImage && showSymptomMask
                                  ? 'border-rose-400 symptom-mask-container'
                                  : 'border-primary animate-pulse lesion-spotlight lesion-focused'
                              }`}
                              style={{
                                left: `${bestBbox.x1 * 100}%`,
                                top: `${bestBbox.y1 * 100}%`,
                                width: `${(bestBbox.x2 - bestBbox.x1) * 100}%`,
                                height: `${(bestBbox.y2 - bestBbox.y1) * 100}%`,
                              }}
                            >
                              {/* Mask R-CNN pixel segmentation overlay (red symptom heatmap) */}
                              {symptomsImage && showSymptomMask ? (
                                <img
                                  src={symptomsImage}
                                  alt="Mask R-CNN Symptom Segmentation Overlay"
                                  className="w-full h-full object-cover pointer-events-none opacity-95 transition-opacity duration-300"
                                  data-testid="mask-rcnn-overlay"
                                />
                              ) : croppedImage ? (
                                <img
                                  src={croppedImage}
                                  alt="Cropped lesion region"
                                  className="w-full h-full object-cover pointer-events-none opacity-90 transition-opacity duration-300"
                                  data-testid="raw-crop-overlay"
                                />
                              ) : null}

                              {/* Inner corner reticle accents */}
                              <div className={`absolute top-1.5 left-1.5 w-2.5 h-2.5 border-t-2 border-l-2 ${symptomsImage && showSymptomMask ? 'border-rose-400 shadow-glow-sm' : 'border-primary shadow-glow-sm'}`} />
                              <div className={`absolute top-1.5 right-1.5 w-2.5 h-2.5 border-t-2 border-r-2 ${symptomsImage && showSymptomMask ? 'border-rose-400 shadow-glow-sm' : 'border-primary shadow-glow-sm'}`} />
                              <div className={`absolute bottom-1.5 left-1.5 w-2.5 h-2.5 border-b-2 border-l-2 ${symptomsImage && showSymptomMask ? 'border-rose-400 shadow-glow-sm' : 'border-primary shadow-glow-sm'}`} />
                              <div className={`absolute bottom-1.5 right-1.5 w-2.5 h-2.5 border-b-2 border-r-2 ${symptomsImage && showSymptomMask ? 'border-rose-400 shadow-glow-sm' : 'border-primary shadow-glow-sm'}`} />
                            </div>

                            {/* Label Badge */}
                            <div
                              className="absolute pointer-events-auto z-30"
                              style={{
                                left: `${Math.min(bestBbox.x2 * 100, 68)}%`,
                                top: `${Math.max(bestBbox.y1 * 100 - 5, 2)}%`,
                              }}
                            >
                              <div className="bg-surface-container-highest/95 backdrop-blur-md px-2.5 py-1 rounded-lg text-3xs md:text-2xs border border-primary/60 shadow-xl whitespace-nowrap flex items-center gap-1.5">
                                <span className={`w-1.5 h-1.5 rounded-full ${symptomsImage && showSymptomMask ? 'bg-rose-400 animate-ping' : 'bg-primary animate-pulse'}`} />
                                <span className="text-primary font-mono font-bold">
                                  {symptomsImage && showSymptomMask ? 'MASK_RCNN_LESION' : 'LESION_01'}
                                </span>
                                <span className="hidden sm:inline text-on-surface-variant font-medium">
                                  {symptomsImage && showSymptomMask ? ': Symptom segmented' : ': Detected region'}
                                </span>
                              </div>
                            </div>
                          </div>
                        )}
                      </>
                    )}

                    {/* ===== LESION FOCUS (ZOOMED CROP INSPECTION) ===== */}
                    {activeView === 'lesion' && (
                      <div className="relative w-full h-full flex flex-col items-center justify-center p-4 lesion-crop-container">
                        <div className="relative max-w-md max-h-[340px] rounded-xl overflow-hidden border-2 border-rose-500/50 shadow-2xl symptom-mask-glow">
                          <img
                            src={showSymptomMask && symptomsImage ? symptomsImage : (croppedImage || imagePreview)}
                            alt="Lesion High-Resolution Focus"
                            className="w-full h-full object-contain"
                            data-testid="lesion-focus-image"
                          />
                          <div className="absolute top-2 left-2 bg-surface-container-highest/90 px-2 py-0.5 rounded text-3xs font-mono text-primary border border-primary/30">
                            MAGNIFIED LESION ROI (224×224)
                          </div>
                        </div>

                        {/* Pathology Legend */}
                        <div className="mt-3 flex flex-wrap items-center justify-center gap-4 bg-surface-container-highest/80 backdrop-blur-md px-3.5 py-1.5 rounded-xl border border-outline-variant/20 text-3xs font-mono">
                          <div className="flex items-center gap-1.5 text-rose-300">
                            <span className="w-2.5 h-2.5 rounded bg-rose-500 inline-block" />
                            <span>Mask R-CNN Pathological Area</span>
                          </div>
                          <div className="flex items-center gap-1.5 text-primary">
                            <span className="w-2.5 h-2.5 rounded border border-primary inline-block" />
                            <span>YOLO Bounding Margin</span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Confidence footer badge */}
                    <div className="absolute bottom-3 left-3 right-3 flex justify-between items-center glass-panel px-3.5 py-2.5 rounded-xl border border-white/10 shadow-lg z-20">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
                        <span className="text-3xs md:text-2xs font-mono font-bold tracking-tight text-on-surface uppercase">
                          AI DIAGNOSTIC CONFIDENCE: {confidence}%
                        </span>
                        {symptomsImage && (
                          <span className="hidden md:inline text-rose-400 text-3xs font-mono font-bold">
                            • MASK R-CNN SEGMENTATION VERIFIED
                          </span>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => setActiveView((prev) => (prev === 'full' ? 'lesion' : 'full'))}
                        className="text-tertiary hover:text-on-surface flex items-center gap-1 text-3xs font-mono"
                        title="Toggle View Mode"
                      >
                        <span className="material-symbols-outlined text-sm">
                          {activeView === 'full' ? 'zoom_in' : 'aspect_ratio'}
                        </span>
                        <span className="hidden sm:inline">{activeView === 'full' ? 'Focus Lesion' : 'Full Scan'}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Column 2: AI Logic Trace (5/12 on desktop) */}
              <div className="lg:col-span-5">
                <div className="bg-surface-container-low rounded-2xl p-4 md:p-6 flex flex-col border border-outline-variant/15 shadow-card-subtle h-full">
                  {/* Section header */}
                  <div className="flex items-center justify-between mb-4 md:mb-5 pb-3 border-b border-outline-variant/10">
                    <div className="flex items-center gap-2.5">
                      <div className="p-1.5 bg-primary/10 rounded-lg border border-primary/20">
                        <span className="material-symbols-outlined text-primary text-base">account_tree</span>
                      </div>
                      <span className="text-xs font-bold text-primary tracking-widest uppercase font-mono">
                        03 AI Logic Trace
                      </span>
                    </div>
                    <span className="text-3xs font-mono text-outline">AUTO-VERIFIED</span>
                  </div>

                  {/* Step-by-step trace */}
                  <div className="space-y-3 mb-5 md:mb-6 flex-1">
                    {/* Step 1 */}
                    <div className={`p-2.5 rounded-xl bg-surface-container/60 border border-outline-variant/10 transition-all duration-500 flex items-center gap-3 ${visibleSteps >= 1 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                      <div className="w-6 h-6 rounded-lg bg-primary/15 border border-primary/30 flex items-center justify-center shrink-0">
                        <span className="material-symbols-outlined text-sm text-primary" style={{ fontVariationSettings: "'wght' 700" }}>check</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-on-surface">
                          Pre-Validation: <span className="text-primary font-mono">Passed</span>
                        </p>
                      </div>
                      <span className="text-3xs font-mono text-outline">0.12s</span>
                    </div>

                    {/* Step 2 */}
                    <div className={`p-2.5 rounded-xl bg-surface-container/60 border border-outline-variant/10 transition-all duration-500 flex items-center gap-3 ${visibleSteps >= 2 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                      <div className="w-6 h-6 rounded-lg bg-primary/15 border border-primary/30 flex items-center justify-center shrink-0">
                        <span className="material-symbols-outlined text-sm text-primary" style={{ fontVariationSettings: "'wght' 700" }}>check</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-on-surface">
                          Preprocessing: <span className="text-on-surface-variant font-mono">Filters Applied</span>
                        </p>
                      </div>
                      <span className="text-3xs font-mono text-outline">0.24s</span>
                    </div>

                    {/* Step 3 */}
                    <div className={`p-2.5 rounded-xl bg-surface-container/60 border border-outline-variant/10 transition-all duration-500 flex items-center gap-3 ${visibleSteps >= 3 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                      <div className="w-6 h-6 rounded-lg bg-primary/15 border border-primary/30 flex items-center justify-center shrink-0">
                        <span className="material-symbols-outlined text-sm text-primary" style={{ fontVariationSettings: "'wght' 700" }}>check</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-on-surface">
                          Feature Extraction: <span className="text-primary font-mono">Complete</span>
                        </p>
                      </div>
                      <span className="text-3xs font-mono text-outline">0.38s</span>
                    </div>
                  </div>

                  {/* Inference Results Card */}
                  <div className={`bg-surface-container-highest/80 backdrop-blur-sm rounded-xl p-4 md:p-5 border-l-4 border-primary border border-outline-variant/15 shadow-lg transition-all duration-500 ${visibleSteps >= 4 ? 'opacity-100 scale-100' : 'opacity-0 scale-95'}`}>
                    <div className="flex items-center justify-between mb-3 pb-2 border-b border-outline-variant/15">
                      <h3 className="text-2xs font-bold text-primary uppercase tracking-widest font-mono">
                        Inference Results
                      </h3>
                      <span className="px-2 py-0.5 rounded bg-primary/10 text-primary text-3xs font-mono font-semibold">
                        CLASSIFIED
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-y-3.5 gap-x-3">
                      <div>
                        <p className="text-3xs text-outline uppercase font-bold tracking-wider mb-0.5">
                          Predicted Condition
                        </p>
                        <p className="text-xs md:text-sm font-extrabold text-on-surface truncate" data-testid="predicted-condition">
                          {disease?.name || 'Unknown'}
                        </p>
                      </div>
                      <div>
                        <p className="text-3xs text-outline uppercase font-bold tracking-wider mb-0.5 flex items-center gap-1">
                          <span className="material-symbols-outlined text-xs text-primary">psychology</span>
                          Clinical Severity
                        </p>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {reasoningStatus === 'loading' ? (
                            <div className="flex items-center gap-1.5 text-primary text-xs font-mono font-bold animate-pulse">
                              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-ping" />
                              <span>Synthesizing...</span>
                            </div>
                          ) : (
                            <>
                              <p className={`text-xs md:text-sm font-extrabold ${severityColor}`} data-testid="severity-grade">
                                {severityGrade}
                              </p>
                              {dynamicSeverity && dynamicSeverity.lesion_coverage_pct > 0 && (
                                <span className="inline-block px-1.5 py-0.2 rounded bg-rose-500/10 text-rose-300 text-[10px] font-mono border border-rose-500/20">
                                  {dynamicSeverity.lesion_coverage_pct}% area
                                </span>
                              )}
                              {dynamicSeverity && dynamicSeverity.cluster_count > 0 && (
                                <span className="hidden sm:inline-block px-1.5 py-0.2 rounded bg-primary/10 text-primary text-[10px] font-mono border border-primary/20">
                                  {dynamicSeverity.cluster_count} clusters
                                </span>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                      <div>
                        <p className="text-3xs text-outline uppercase font-bold tracking-wider mb-0.5">
                          Disease Stage
                        </p>
                        <p className="text-xs font-semibold text-on-surface truncate">{stage}</p>
                      </div>
                      <div>
                        <p className="text-3xs text-outline uppercase font-bold tracking-wider mb-0.5">
                          Prognosis
                        </p>
                        <p className={`text-xs font-semibold ${prognosisColor} truncate`}>
                          {prognosis}
                        </p>
                      </div>

                      {/* Dynamic Pathological Severity Narrative from LLM */}
                      {severityDescription && (
                        <div className="col-span-2 pt-2.5 mt-0.5 border-t border-outline-variant/15">
                          <p className="text-[10px] text-outline uppercase font-bold tracking-wider mb-1 flex items-center justify-between">
                            <span className="flex items-center gap-1">
                              <span className="material-symbols-outlined text-xs text-primary">clinical_notes</span>
                              Pathological Severity Assessment
                            </span>
                            <span className="text-[9px] font-mono text-primary font-bold px-1.5 py-0.5 rounded bg-primary/10">
                              {severityAssessment ? 'LLM REASONED' : 'VISION TELEMETRY'}
                            </span>
                          </p>
                          <p className="text-2xs text-on-surface-variant leading-relaxed" data-testid="severity-narrative">
                            {severityDescription}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Vet Action & Verification Area */}
                  <div className={`mt-5 md:mt-6 transition-all duration-500 ${visibleSteps >= 5 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                    {caseReport && caseReport.verified ? (
                      <div className="p-4 rounded-xl bg-emerald-500/15 border border-emerald-500/30 space-y-3 animate-fadeIn" data-testid="verified-case-banner">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs">
                            <span className="material-symbols-outlined text-base">verified</span>
                            <span>{existingCase ? 'Case Updated & Verified' : 'Case Verified & Archived'}</span>
                          </div>
                          <span className="text-[10px] font-mono text-emerald-300 font-bold px-2 py-0.5 rounded bg-emerald-500/20">
                            {caseReport.case_number}
                          </span>
                        </div>
                        <p className="text-2xs text-slate-300 leading-relaxed">
                          Clinical case report officially {existingCase ? 'updated' : 'recorded'} under <strong>{caseReport.vet_license || 'Verified Vet'}</strong>. Herd status synchronized.
                        </p>
                        <div className="flex items-center gap-2 pt-1">
                          <button
                            onClick={() => navigate('/vet/clinical-records')}
                            className="flex-1 py-2 px-3 rounded-lg bg-emerald-500 text-black font-bold text-xs uppercase tracking-wider hover:brightness-110 transition-all text-center flex items-center justify-center gap-1"
                          >
                            <span className="material-symbols-outlined text-xs">folder_open</span>
                            <span>View Case Records</span>
                          </button>
                          <button
                            onClick={handleResetAnalysis}
                            className="py-2 px-3 rounded-lg bg-white/5 hover:bg-white/10 text-white text-xs font-bold transition-all border border-white/10"
                          >
                            New
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
                          onClick={handleVerifyAndReport}
                          disabled={isReporting}
                          className="w-full primary-gradient text-on-primary py-3 rounded-xl font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2.5 shadow-lg shadow-primary/15 hover:shadow-primary/30 hover:brightness-105 active:scale-[0.98] transition-all disabled:opacity-50"
                          id="vet-verify-btn"
                          data-testid="vet-verify-btn"
                        >
                          {isReporting ? (
                            <>
                              <span className="material-symbols-outlined text-base animate-spin">progress_activity</span>
                              <span>{existingCase ? 'Updating & Verifying...' : 'Recording & Verifying...'}</span>
                            </>
                          ) : (
                            <>
                              <span className="material-symbols-outlined text-base">{existingCase ? 'published_with_changes' : 'fact_check'}</span>
                              <span>{existingCase ? 'Vet: Update & Verify Case' : 'Vet: Verify & Report'}</span>
                            </>
                          )}
                        </button>
                        <p className="text-center text-3xs text-outline mt-2.5 font-medium flex items-center justify-center gap-1">
                          <span className="material-symbols-outlined text-xs">sync</span>
                          {existingCase ? 'Updates active case record and synchronizes surveillance telemetry.' : 'Verified reports sync with regional surveillance feeds.'}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Model Reasoning & Evidence Section */}
            <div className={`bg-surface-container-low rounded-2xl p-5 md:p-8 border border-outline-variant/15 shadow-card-subtle transition-all duration-700 delay-300 ${visibleSteps >= 6 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
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
                    <p className="text-xs md:text-sm text-on-surface-variant leading-relaxed" data-testid="diagnostic-rationale">
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
                    <p className="text-xs md:text-sm text-on-surface-variant leading-relaxed" data-testid="spatial-correlation">
                      {spatialCorrelation}
                    </p>
                  </div>
                </div>

                {/* Right: Confidence score + evidence list */}
                <div className="bg-surface-container-highest/40 backdrop-blur-sm rounded-xl p-5 md:p-6 flex flex-col justify-center border border-primary/15">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-bold text-on-surface-variant">Evidence Confidence Score</span>
                    <span className="text-xl md:text-2xl font-black text-primary font-mono tracking-tight" data-testid="confidence-score">
                      {confidence}%
                    </span>
                  </div>
                  <div className="w-full bg-surface-container rounded-full h-2.5 mb-5 p-0.5 border border-outline-variant/20">
                    <div
                      className="primary-gradient h-full rounded-full transition-all duration-1000 shadow-glow-sm"
                      style={{ width: `${confidence}%` }}
                      role="progressbar"
                      aria-valuenow={parseFloat(confidence)}
                      aria-valuemin={0}
                      aria-valuemax={100}
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
            <h3 className="text-lg md:text-xl font-bold text-on-surface mb-2 text-center tracking-tight">Diagnosis Aborted</h3>
            <p className="text-on-surface-variant text-center max-w-md mb-8 text-xs md:text-sm leading-relaxed">
              {error || 'Our AI engine could not reliably identify bovine features or clinical lesions in the provided asset. Please ensure the lighting is adequate and the subject is clearly framed.'}
            </p>
            <button
              onClick={reset}
              className="px-6 md:px-8 py-3 bg-surface-container-highest border border-outline-variant/30 rounded-xl font-bold text-xs uppercase tracking-wider hover:bg-surface-bright hover:border-primary/40 transition-all text-on-surface shadow-sm active:scale-95 flex items-center gap-2"
              id="return-to-intake-btn"
            >
              <span className="material-symbols-outlined text-base">arrow_back</span>
              Return to Intake
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SmartDiagnostics;
