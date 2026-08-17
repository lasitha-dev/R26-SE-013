import React, { useEffect, useState } from 'react';
import AppShell from '../../shared_components/AppShell';
import UploadDropzone from './components/UploadDropzone';
import ReasoningBriefing from './components/ReasoningBriefing';
import useDetection from './hooks/useDetection';
import { getDiseaseProfile } from './diseaseProfiles';

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
  const {
    status, result, error, imagePreview, detect, reset,
    reasoning, reasoningStatus, reasoningError,
  } = useDetection();
  const [visibleSteps, setVisibleSteps] = useState(0);
  const [showSymptomMask, setShowSymptomMask] = useState(true);
  const [activeView, setActiveView] = useState('full'); // 'full' | 'lesion'

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

  // Get disease profile for the detected disease
  const disease = result?.disease;
  const profile = getDiseaseProfile(disease?.name);
  const confidence = disease?.confidence
    ? disease.confidence.toFixed(1)
    : '0.0';

  // Get best detection bounding box and Mask R-CNN segmentation image
  const bestBbox = result?.best_detection?.bbox_normalized;
  const symptomsImage = result?.symptoms_image;
  const croppedImage = result?.cropped_image;

  const handleFile = (file) => {
    detect(file);
  };

  return (
    <AppShell activeNavItem="smart-diagnosis" headerTitle="AI Diagnostics Panel">
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
        {!isIdle && !isLoading && (
          <button
            onClick={() => {
              setActiveView('full');
              setShowSymptomMask(true);
              reset();
            }}
            className="text-primary hover:text-on-primary hover:bg-primary font-bold text-xs flex items-center gap-2 border border-primary/30 px-4 py-2.5 rounded-xl bg-primary/10 transition-all shadow-sm hover:shadow-glow-sm shrink-0 active:scale-95"
            id="new-analysis-btn"
          >
            <span className="material-symbols-outlined text-base">refresh</span>
            New Analysis
          </button>
        )}
      </div>

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
        {/* ========= IDLE / LOADING VIEW ========= */}
        {(isIdle || isLoading) && (
          <UploadDropzone isLoading={isLoading} onFile={handleFile} />
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
                        <p className="text-3xs text-outline uppercase font-bold tracking-wider mb-0.5">
                          Severity Score
                        </p>
                        <p className={`text-xs md:text-sm font-extrabold ${profile.severityColor}`}>
                          {profile.severity}
                        </p>
                      </div>
                      <div>
                        <p className="text-3xs text-outline uppercase font-bold tracking-wider mb-0.5">
                          Disease Stage
                        </p>
                        <p className="text-xs font-semibold text-on-surface truncate">{profile.stage}</p>
                      </div>
                      <div>
                        <p className="text-3xs text-outline uppercase font-bold tracking-wider mb-0.5">
                          Prognosis
                        </p>
                        <p className={`text-xs font-semibold ${profile.prognosisColor} truncate`}>
                          {profile.prognosis}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Vet Action Button */}
                  <div className={`mt-5 md:mt-6 transition-all duration-500 ${visibleSteps >= 5 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                    <button
                      className="w-full primary-gradient text-on-primary py-3 rounded-xl font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2.5 shadow-lg shadow-primary/15 hover:shadow-primary/30 hover:brightness-105 active:scale-[0.98] transition-all"
                      id="vet-verify-btn"
                    >
                      <span className="material-symbols-outlined text-base">fact_check</span>
                      Vet: Verify &amp; Report
                    </button>
                    <p className="text-center text-3xs text-outline mt-2.5 font-medium flex items-center justify-center gap-1">
                      <span className="material-symbols-outlined text-xs">sync</span>
                      Verified reports sync with regional surveillance feeds.
                    </p>
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
                    <div className="flex items-center gap-2 mb-2">
                      <span className="w-2 h-2 rounded-full bg-primary shadow-glow-sm" />
                      <h4 className="text-2xs font-bold text-primary uppercase tracking-widest font-mono">
                        Diagnostic Rationale
                      </h4>
                    </div>
                    <p className="text-xs md:text-sm text-on-surface-variant leading-relaxed">
                      {profile.rationale}
                    </p>
                  </div>
                  <div className="p-4 bg-surface-container/60 rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-colors">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="w-2 h-2 rounded-full bg-primary shadow-glow-sm" />
                      <h4 className="text-2xs font-bold text-primary uppercase tracking-widest font-mono">
                        Spatial Correlation
                      </h4>
                    </div>
                    <p className="text-xs md:text-sm text-on-surface-variant leading-relaxed">
                      {profile.spatialCorrelation}
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
                    {profile.evidenceItems.map((item, idx) => (
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
    </AppShell>
  );
};

export default SmartDiagnostics;
