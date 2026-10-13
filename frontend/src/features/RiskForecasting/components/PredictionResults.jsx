import React, { useState } from 'react';
import PropTypes from 'prop-types';

/**
 * PredictionResults — Displays 2-stage risk inference results, calibration details, UQ, and raw JSON.
 */
const PredictionResults = ({ result, onBack }) => {
  const [showRawJson, setShowRawJson] = useState(false);
  const [showCalibrationDetails, setShowCalibrationDetails] = useState(false);

  if (!result) return null;

  const {
    disease,
    district,
    year,
    month_name,
    stage1 = {},
    stage2 = {},
    calibration_info = {},
    uncertainty = {},
    recommendations = [],
    provenance = {},
  } = result;

  const probPct = stage1.probability_pct ?? (stage1.probability ? (stage1.probability * 100).toFixed(1) : 0);
  const riskLevel = stage1.risk_level || 'UNKNOWN';

  // Risk level color mapping
  const riskColorMap = {
    HIGH: { text: 'text-error', bg: 'bg-error/10', border: 'border-error/30' },
    MEDIUM: { text: 'text-[#f59e0b]', bg: 'bg-[#f59e0b]/10', border: 'border-[#f59e0b]/30' },
    LOW: { text: 'text-primary', bg: 'bg-primary/10', border: 'border-primary/30' },
  };
  const currentRiskTheme = riskColorMap[riskLevel] || riskColorMap.LOW;

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6" data-testid="prediction-results-container">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-xl">
        <div className="flex items-center gap-3">
          <div className={`p-3 rounded-xl ${currentRiskTheme.bg} ${currentRiskTheme.text} border ${currentRiskTheme.border}`}>
            <span className="material-symbols-outlined text-2xl">
              {riskLevel === 'HIGH' ? 'warning' : riskLevel === 'MEDIUM' ? 'error_outline' : 'verified_user'}
            </span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl md:text-2xl font-bold text-on-surface">
                {district} — {month_name} {year}
              </h2>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-primary/10 text-primary border border-primary/20">
                {disease}
              </span>
            </div>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Target Epizootic Risk &amp; Severity Assessment Result
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onBack}
          className="px-4 py-2.5 bg-surface-container-highest border border-outline-variant/30 rounded-lg text-xs md:text-sm font-semibold text-on-surface hover:bg-surface-bright transition-colors flex items-center justify-center gap-2 shrink-0"
          id="new-prediction-btn"
          data-testid="back-to-input-btn"
        >
          <span className="material-symbols-outlined text-sm">arrow_back</span>
          New Prediction
        </button>
      </div>

      {/* Two-Column Stage 1 vs Stage 2 Core Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Stage 1: Outbreak Occurrence Risk */}
        <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-xl flex flex-col justify-between space-y-6">
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-bold text-primary uppercase tracking-widest flex items-center gap-1.5">
                <span className="material-symbols-outlined text-base">radar</span>
                Stage 1: Occurrence Likelihood
              </span>
              <span className="text-[10px] text-on-surface-variant uppercase font-semibold">
                Threshold: t = {stage1.decision_threshold ?? 0.40}
              </span>
            </div>

            {/* Circular Gauge / Probability */}
            <div className="flex flex-col items-center justify-center py-4 text-center">
              <div className={`text-4xl md:text-5xl font-black ${currentRiskTheme.text} tracking-tight`}>
                {probPct}%
              </div>
              <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider mt-1">
                Predicted Outbreak Probability
              </p>

              {/* Risk Level Badge */}
              <div className={`mt-4 px-4 py-1.5 rounded-full font-extrabold text-xs md:text-sm tracking-wide ${currentRiskTheme.bg} ${currentRiskTheme.text} border ${currentRiskTheme.border}`} data-testid="risk-level-badge">
                RISK LEVEL: {riskLevel}
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-outline-variant/10 text-xs text-on-surface-variant space-y-1">
            <div className="flex justify-between">
              <span>Model Architecture:</span>
              <span className="font-semibold text-on-surface">{stage1.model_variant || 'LogisticRegression'}</span>
            </div>
            <div className="flex justify-between">
              <span>Raw Probability:</span>
              <span className="font-mono text-on-surface">{stage1.probability ? stage1.probability.toFixed(4) : 'N/A'}</span>
            </div>
          </div>
        </div>

        {/* Stage 2: Outbreak Severity & Honesty Gating */}
        <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-xl flex flex-col justify-between space-y-6">
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-bold text-primary uppercase tracking-widest flex items-center gap-1.5">
                <span className="material-symbols-outlined text-base">medical_services</span>
                Stage 2: Severity Assessment
              </span>
              {/* Evaluated Status Badge */}
              {stage2.evaluated ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-primary/10 text-primary border border-primary/20" data-testid="stage2-evaluated-badge">
                  MODEL EVALUATED
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#f59e0b]/10 text-[#f59e0b] border border-[#f59e0b]/20" data-testid="stage2-bypassed-badge">
                  THRESHOLD BYPASS
                </span>
              )}
            </div>

            {/* Severity Result Box */}
            <div className="space-y-4">
              <div className="p-4 bg-surface-container-lowest/60 rounded-lg border border-outline-variant/10">
                <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-wider mb-1">
                  Predicted Outbreak Severity
                </p>
                <div className="flex items-center justify-between">
                  <span className="text-xl font-extrabold text-on-surface" data-testid="severity-predicted-value">
                    {stage2.severity_predicted || 'LOW'}
                  </span>
                  <span className="text-xs font-mono text-on-surface-variant">
                    Code: {stage2.severity_code ?? 0}
                  </span>
                </div>
              </div>

              {/* Status Flags Grid */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-surface-container-lowest/40 rounded-lg border border-outline-variant/10">
                  <span className="text-[10px] text-on-surface-variant uppercase font-bold block mb-1">
                    Action Required
                  </span>
                  <span className={`font-extrabold ${stage2.action_required ? 'text-error' : 'text-primary'}`}>
                    {stage2.action_required ? 'YES (EMERGENCY)' : 'NO (MILD/LOW)'}
                  </span>
                </div>
                <div className="p-3 bg-surface-container-lowest/40 rounded-lg border border-outline-variant/10">
                  <span className="text-[10px] text-on-surface-variant uppercase font-bold block mb-1">
                    Discriminator Validated
                  </span>
                  <span className={`font-extrabold ${stage2.discriminator_validated ? 'text-primary' : 'text-[#f59e0b]'}`}>
                    {stage2.discriminator_validated ? 'VALIDATED' : 'LIMITATION (UNVALIDATED)'}
                  </span>
                </div>
              </div>

              {/* Explanatory Notes */}
              {stage2.notes && (
                <p className="text-xs text-on-surface-variant italic bg-surface-container-lowest/30 p-3 rounded border border-outline-variant/5">
                  &ldquo;{stage2.notes}&rdquo;
                </p>
              )}
            </div>
          </div>

          <div className="pt-4 border-t border-outline-variant/10 text-xs text-on-surface-variant flex justify-between">
            <span>Stage 2 Model:</span>
            <span className="font-semibold text-on-surface">{stage2.model_name || 'Classifier'}</span>
          </div>
        </div>
      </div>

      {/* Calibration & Uncertainty Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Calibration Info Panel */}
        <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-primary uppercase tracking-widest flex items-center gap-1.5">
              <span className="material-symbols-outlined text-base">tune</span>
              Probability Calibration
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${calibration_info.is_calibrated ? 'bg-primary/10 text-primary border border-primary/20' : 'bg-surface-container-highest text-tertiary'}`}>
              {calibration_info.is_calibrated ? 'CALIBRATED' : 'RAW / UNCALIBRATED'}
            </span>
          </div>

          <div className="text-xs text-on-surface-variant space-y-2">
            <div>
              <span className="font-bold text-on-surface block">{calibration_info.calibration_method}</span>
              {calibration_info.ece_score !== null && calibration_info.ece_score !== undefined && (
                <span className="text-xs font-mono text-primary mt-1 block">
                  Expected Calibration Error (ECE): {calibration_info.ece_score}
                </span>
              )}
            </div>
            <p className="text-xs bg-surface-container-lowest/40 p-3 rounded border border-outline-variant/5">
              {calibration_info.notes}
            </p>
          </div>
        </div>

        {/* Uncertainty Quantification (Conformal Prediction) */}
        <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-primary uppercase tracking-widest flex items-center gap-1.5">
              <span className="material-symbols-outlined text-base">verified</span>
              Uncertainty Quantification (UQ)
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${uncertainty.status === 'VALIDATED' ? 'bg-primary/10 text-primary border border-primary/20' : 'bg-[#f59e0b]/10 text-[#f59e0b] border border-[#f59e0b]/20'}`}>
              {uncertainty.status || 'UNRELIABLE'}
            </span>
          </div>

          <div className="text-xs text-on-surface-variant space-y-2">
            <div className="flex items-center justify-between">
              <span>Prediction Set:</span>
              <span className="font-mono font-bold text-primary">
                {uncertainty.prediction_set ? JSON.stringify(uncertainty.prediction_set) : 'null'}
              </span>
            </div>
            {uncertainty.empirical_coverage_pct && (
              <div className="flex items-center justify-between">
                <span>Empirical Coverage:</span>
                <span className="font-semibold text-on-surface">{uncertainty.empirical_coverage_pct}%</span>
              </div>
            )}
            <p className="text-xs bg-surface-container-lowest/40 p-3 rounded border border-outline-variant/5">
              {uncertainty.notes}
            </p>
          </div>
        </div>
      </div>

      {/* Field Recommendations */}
      {recommendations.length > 0 && (
        <div className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 shadow-xl space-y-4">
          <h3 className="text-xs font-bold text-primary uppercase tracking-widest flex items-center gap-2">
            <span className="material-symbols-outlined text-base">list_alt</span>
            Field Veterinary Action Protocol
          </h3>
          <ul className="space-y-2">
            {recommendations.map((rec, idx) => (
              <li key={idx} className="flex items-start gap-2.5 text-xs md:text-sm text-on-surface">
                <span className="material-symbols-outlined text-primary text-base shrink-0 mt-0.5">
                  check_circle
                </span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Provenance & Fallback Notice */}
      {provenance.fallback_applied && (
        <div className="p-4 bg-[#f59e0b]/10 border border-[#f59e0b]/30 rounded-xl text-xs text-[#f59e0b] flex items-center gap-3">
          <span className="material-symbols-outlined text-lg shrink-0">info</span>
          <span>{provenance.fallback_message || 'Historical baseline fallback applied.'}</span>
        </div>
      )}

      {/* Raw API Response Accordion (User-Requested Feature) */}
      <div className="bg-surface-container-low rounded-xl border border-outline-variant/10 shadow-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setShowRawJson((prev) => !prev)}
          className="w-full p-4 text-xs font-bold text-on-surface-variant hover:text-primary uppercase tracking-wider flex items-center justify-between transition-colors bg-surface-container-lowest/30"
          data-testid="toggle-raw-json-btn"
        >
          <span className="flex items-center gap-2">
            <span className="material-symbols-outlined text-base">code</span>
            View Raw API Response JSON (Auditing &amp; Verification)
          </span>
          <span className="material-symbols-outlined text-base">
            {showRawJson ? 'expand_less' : 'expand_more'}
          </span>
        </button>

        {showRawJson && (
          <div className="p-4 bg-surface-container-lowest border-t border-outline-variant/10">
            <pre
              className="text-[11px] font-mono text-on-surface-variant overflow-x-auto p-4 rounded-lg bg-surface-container-lowest/80 border border-outline-variant/10 leading-relaxed"
              data-testid="raw-json-output"
            >
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

PredictionResults.propTypes = {
  result: PropTypes.object,
  onBack: PropTypes.func.isRequired,
};

export default PredictionResults;
