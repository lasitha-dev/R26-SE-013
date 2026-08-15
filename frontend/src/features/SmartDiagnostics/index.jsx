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
 * - 02 Symptom Analysis (annotated image with scan-line)
 * - 03 AI Logic Trace (animated step reveal + inference results)
 * - Model Reasoning & Evidence (rationale + confidence score)
 */
const SmartDiagnostics = () => {
  const {
    status, result, error, imagePreview, detect, reset,
    reasoning, reasoningStatus, reasoningError,
  } = useDetection();
  const [visibleSteps, setVisibleSteps] = useState(0);

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
      const timer = setTimeout(() => setVisibleSteps(i), i * 600);
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

  // Get best detection bounding box for lesion overlay
  const bestBbox = result?.best_detection?.bbox_normalized;

  const handleFile = (file) => {
    detect(file);
  };

  return (
    <AppShell activeNavItem="smart-diagnosis" headerTitle="AI Diagnostics Panel">
      {/* Page Title + New Analysis button */}
      <div className="mb-6 md:mb-10 flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
        <div>
          <h2 className="text-2xl md:text-4xl font-extrabold text-on-surface tracking-tight mb-2">
            AI-Powered Smart Diagnosis System
          </h2>
          <p className="text-on-surface-variant text-base md:text-lg max-w-2xl">
            Upload clinical imagery for automated feature extraction, visual highlighting, and logic tracing.
          </p>
        </div>
        {!isIdle && !isLoading && (
          <button
            onClick={reset}
            className="text-primary hover:text-primary-fixed-dim font-bold text-sm flex items-center gap-2 border border-primary/20 px-4 py-2 rounded-lg bg-primary/5 transition-all shrink-0"
            id="new-analysis-btn"
          >
            <span className="material-symbols-outlined text-sm">refresh</span>
            New Analysis
          </button>
        )}
      </div>

      {/* Failure Alert Banner */}
      {isFailure && (
        <div className="mb-8" id="alert-container">
          <div className="flex-1 p-4 rounded-lg bg-surface-container border-l-4 border-error flex items-center gap-4">
            <span className="material-symbols-outlined text-error">error</span>
            <div className="flex-1">
              <p className="text-sm font-bold text-on-surface">Analysis Failed</p>
              <p className="text-xs text-on-surface-variant">
                {error || 'Cattle not identified or low quality image. Please retry with a clearer asset.'}
              </p>
            </div>
            <button
              onClick={reset}
              className="ml-auto text-on-surface-variant hover:text-on-surface shrink-0"
              aria-label="Dismiss alert"
            >
              <span className="material-symbols-outlined text-sm">close</span>
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
                <div className="bg-surface-container rounded-lg p-4 md:p-6 h-full flex flex-col overflow-hidden relative border border-outline-variant/10">
                  {/* Section header */}
                  <div className="flex items-center justify-between mb-4 md:mb-6">
                    <div className="flex items-center gap-2">
                      <span className="text-[0.6875rem] font-bold text-primary tracking-widest uppercase">
                        02 Symptom Analysis
                      </span>
                      <span className="px-2 py-1 bg-primary/10 text-primary text-[10px] rounded font-bold uppercase tracking-widest">
                        Live Scan
                      </span>
                    </div>
                    <span className="material-symbols-outlined text-primary">visibility</span>
                  </div>

                  {/* Image with scan overlay */}
                  <div
                    className="relative flex-1 min-h-[250px] md:min-h-[400px] rounded-xl overflow-hidden group scanning"
                    id="image-container"
                  >
                    <div className="scan-line" />
                    <img
                      className="w-full h-full object-cover transition-all duration-700 image-dimmed"
                      src={imagePreview}
                      alt="Uploaded clinical image"
                    />

                    {/* Bounding box / lesion overlay */}
                    {bestBbox && (
                      <div className="absolute inset-0 opacity-100 transition-opacity duration-500">
                        <div
                          className="absolute rounded-lg bg-primary/30 border-2 border-primary animate-pulse lesion-focused shadow-[0_0_20px_#4edea3]"
                          style={{
                            left: `${bestBbox.x1 * 100}%`,
                            top: `${bestBbox.y1 * 100}%`,
                            width: `${(bestBbox.x2 - bestBbox.x1) * 100}%`,
                            height: `${(bestBbox.y2 - bestBbox.y1) * 100}%`,
                          }}
                        />
                        {/* Label */}
                        <div
                          className="absolute"
                          style={{
                            left: `${bestBbox.x2 * 100}%`,
                            top: `${bestBbox.y1 * 100}%`,
                          }}
                        >
                          <div className="h-px w-8 md:w-12 bg-primary" />
                          <div className="bg-surface-container-highest/90 backdrop-blur p-1.5 md:p-2 rounded text-[10px] border border-primary/40 mt-[-1px] whitespace-nowrap">
                            <span className="text-primary font-bold">LESION_01</span>
                            <span className="hidden sm:inline">: Detected region</span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Confidence footer */}
                    <div className="absolute bottom-2 md:bottom-4 left-2 md:left-4 right-2 md:right-4 flex justify-between items-center glass-panel p-2 md:p-3 rounded-lg border border-white/5">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
                        <span className="text-[9px] md:text-[10px] font-bold tracking-tight text-on-surface">
                          AI SEGMENTATION CONFIDENCE: {confidence}%
                        </span>
                      </div>
                      <span className="material-symbols-outlined text-sm text-on-surface">fullscreen</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Column 2: AI Logic Trace (5/12 on desktop) */}
              <div className="lg:col-span-5">
                <div className="bg-surface-container-low rounded-lg p-4 md:p-6 flex flex-col border border-outline-variant/10 h-full">
                  {/* Section header */}
                  <div className="flex items-center justify-between mb-4 md:mb-6">
                    <span className="text-[0.6875rem] font-bold text-primary tracking-widest uppercase">
                      03 AI Logic Trace
                    </span>
                    <span className="material-symbols-outlined text-primary">account_tree</span>
                  </div>

                  {/* Step-by-step trace */}
                  <div className="space-y-4 mb-6 md:mb-8 flex-1">
                    {/* Step 1 */}
                    <div className={`transition-all duration-500 flex items-center gap-3 ${visibleSteps >= 1 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                      <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                        <span className="material-symbols-outlined text-sm text-primary" style={{ fontVariationSettings: "'wght' 700" }}>check</span>
                      </div>
                      <p className="text-xs font-medium text-on-surface">
                        Pre-Validation: <span className="text-primary">Passed</span>
                      </p>
                    </div>

                    {/* Step 2 */}
                    <div className={`transition-all duration-500 flex items-center gap-3 ${visibleSteps >= 2 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                      <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                        <span className="material-symbols-outlined text-sm text-primary" style={{ fontVariationSettings: "'wght' 700" }}>check</span>
                      </div>
                      <p className="text-xs font-medium text-on-surface">
                        Preprocessing: <span className="text-on-surface-variant">Filters Applied</span>
                      </p>
                    </div>

                    {/* Step 3 */}
                    <div className={`transition-all duration-500 flex items-center gap-3 ${visibleSteps >= 3 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                      <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                        <span className="material-symbols-outlined text-sm text-primary" style={{ fontVariationSettings: "'wght' 700" }}>check</span>
                      </div>
                      <p className="text-xs font-medium text-on-surface">
                        Feature Extraction: <span className="text-primary">Complete</span>
                      </p>
                    </div>
                  </div>

                  {/* Inference Results Card */}
                  <div className={`bg-surface-container-highest rounded-xl p-4 md:p-6 border-l-4 border-primary shadow-2xl transition-all duration-500 ${visibleSteps >= 4 ? 'opacity-100 scale-100' : 'opacity-0 scale-95'}`}>
                    <h3 className="text-xs font-bold text-primary mb-4 uppercase tracking-widest">
                      Inference Results
                    </h3>
                    <div className="grid grid-cols-2 gap-y-4 md:gap-y-6 gap-x-4">
                      <div>
                        <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-tighter mb-1">
                          Predicted Condition
                        </p>
                        <p className="text-sm md:text-base font-extrabold text-on-surface" data-testid="predicted-condition">
                          {disease?.name || 'Unknown'}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-tighter mb-1">
                          Severity Score
                        </p>
                        <p className={`text-sm md:text-base font-extrabold ${profile.severityColor}`}>
                          {profile.severity}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-tighter mb-1">
                          Disease Stage
                        </p>
                        <p className="text-sm font-semibold text-on-surface">{profile.stage}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-tighter mb-1">
                          Prognosis
                        </p>
                        <p className={`text-sm font-semibold ${profile.prognosisColor}`}>
                          {profile.prognosis}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Vet Action Button */}
                  <div className={`mt-6 md:mt-8 transition-all duration-500 ${visibleSteps >= 5 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}`}>
                    <button
                      className="w-full primary-gradient text-on-primary py-3 md:py-4 rounded-lg font-bold text-sm flex items-center justify-center gap-3 shadow-xl hover:scale-[1.02] transition-transform"
                      id="vet-verify-btn"
                    >
                      <span className="material-symbols-outlined">fact_check</span>
                      Vet: Verify &amp; Report
                    </button>
                    <p className="text-center text-[10px] text-on-surface-variant mt-3 md:mt-4 font-medium italic">
                      Verified reports sync with regional feeds.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Model Reasoning & Evidence Section */}
            <div className={`bg-surface-container-low rounded-xl p-4 md:p-8 border border-outline-variant/10 transition-all duration-700 delay-300 ${visibleSteps >= 6 ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <span className="material-symbols-outlined text-primary">clinical_notes</span>
                </div>
                <h3 className="text-lg md:text-xl font-bold text-on-surface tracking-tight">
                  Model Reasoning &amp; Evidence
                </h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
                {/* Left: Rationale cards */}
                <div className="space-y-4">
                  <div className="p-4 bg-surface-container-lowest/50 rounded-lg border border-outline-variant/5">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                      <h4 className="text-xs font-bold text-primary uppercase tracking-widest">
                        Diagnostic Rationale
                      </h4>
                    </div>
                    <p className="text-sm text-on-surface-variant leading-relaxed">
                      {profile.rationale}
                    </p>
                  </div>
                  <div className="p-4 bg-surface-container-lowest/50 rounded-lg border border-outline-variant/5">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                      <h4 className="text-xs font-bold text-primary uppercase tracking-widest">
                        Spatial Correlation
                      </h4>
                    </div>
                    <p className="text-sm text-on-surface-variant leading-relaxed">
                      {profile.spatialCorrelation}
                    </p>
                  </div>
                </div>

                {/* Right: Confidence score + evidence list */}
                <div className="bg-surface-container-highest/30 rounded-lg p-4 md:p-6 flex flex-col justify-center border border-primary/5">
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-xs font-bold text-on-surface-variant">Evidence Confidence Score</span>
                    <span className="text-xl md:text-2xl font-black text-primary" data-testid="confidence-score">
                      {confidence}%
                    </span>
                  </div>
                  <div className="w-full bg-surface-container rounded-full h-2 mb-6">
                    <div
                      className="bg-primary h-2 rounded-full transition-all duration-1000"
                      style={{ width: `${confidence}%` }}
                      role="progressbar"
                      aria-valuenow={parseFloat(confidence)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    />
                  </div>
                  <ul className="space-y-2">
                    {profile.evidenceItems.map((item, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-[11px] text-on-surface-variant">
                        <span className="material-symbols-outlined text-primary text-[14px] shrink-0 mt-0.5">
                          check_circle
                        </span>
                        {item}
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
            className="w-full bg-surface-container-low rounded-xl p-8 md:p-16 border border-error/20 flex flex-col items-center justify-center"
            data-testid="failure-view"
          >
            <div className="w-16 h-16 md:w-20 md:h-20 rounded-full bg-error/10 flex items-center justify-center mb-6">
              <span className="material-symbols-outlined text-3xl md:text-4xl text-error">
                sentiment_very_dissatisfied
              </span>
            </div>
            <h3 className="text-xl md:text-2xl font-bold text-on-surface mb-2 text-center">Diagnosis Aborted</h3>
            <p className="text-on-surface-variant text-center max-w-md mb-8 text-sm md:text-base">
              {error || 'Our AI engine could not reliably identify bovine features or clinical lesions in the provided asset. Please ensure the lighting is adequate and the subject is clearly framed.'}
            </p>
            <button
              onClick={reset}
              className="px-8 md:px-10 py-3 md:py-4 bg-surface-container-highest border border-outline-variant/30 rounded-xl font-bold hover:bg-surface-bright transition-colors text-on-surface"
              id="return-to-intake-btn"
            >
              Return to Intake
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
};

export default SmartDiagnostics;
