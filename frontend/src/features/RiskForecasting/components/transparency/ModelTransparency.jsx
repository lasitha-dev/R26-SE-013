import React from 'react';
import {
  ROLES,
  SCOPE_LEVELS,
  PERMISSIONS,
  validateViewerContext,
  hasForecastingPermission,
  getAuthorizedDistricts,
} from '../../contracts/viewerContext';
import { AccessContextUnavailable } from '../AccessContextUnavailable';

/**
 * Model Transparency Component
 * UI_READY_API_BLOCKED: Capability-gated screen with role-sensitive presentation.
 * Explains verified backend model transparency concepts without displaying live values
 * until secure backend authorization is integrated.
 *
 * @param {object} props
 * @param {object} props.viewerContext
 */
export function ModelTransparency({ viewerContext }) {
  // 1. Access & Strict Capability Validation
  const validation = validateViewerContext(viewerContext);
  if (!validation.valid) {
    return <AccessContextUnavailable reason={validation.reason} />;
  }

  const normalized = validation.normalizedContext;
  const role = normalized.role;

  // Strict boolean check for viewModelTransparency permission (must not infer from role alone)
  const hasTransparencyPermission = hasForecastingPermission(
    viewerContext,
    PERMISSIONS.viewModelTransparency
  );

  if (!hasTransparencyPermission) {
    return (
      <AccessContextUnavailable reason="Strict viewModelTransparency permission (boolean true) is required to view Model Transparency." />
    );
  }

  // Role & Scope Validation
  let isScopeValid = false;
  let farmerDistrict = null;
  let authorizedDistricts = [];

  if (role === ROLES.FARMER) {
    farmerDistrict = normalized.authorization.registeredFarmDistrict;
    isScopeValid =
      normalized.authorization.scopeLevel === SCOPE_LEVELS.FARM &&
      Boolean(farmerDistrict && farmerDistrict.trim() !== '');
  } else if (role === ROLES.VETERINARY_OFFICER || role === ROLES.DAPH_OFFICIAL) {
    const isAllowedLevel =
      normalized.authorization.scopeLevel === SCOPE_LEVELS.DISTRICT ||
      normalized.authorization.scopeLevel === SCOPE_LEVELS.PROVINCE ||
      normalized.authorization.scopeLevel === SCOPE_LEVELS.NATIONAL;

    authorizedDistricts = getAuthorizedDistricts(viewerContext);
    isScopeValid = isAllowedLevel && authorizedDistricts.length > 0;
  }

  if (!isScopeValid) {
    return (
      <AccessContextUnavailable reason="Role and authorized scope criteria failed for Model Transparency screen access." />
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-on-surface">
      {/* Header */}
      <header className="bg-surface-container p-6 rounded-2xl border border-outline-variant/30 shadow-xl space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-primary tracking-tight">
              Model Transparency &amp; Explainability
            </h1>
            <p className="text-sm text-on-surface-variant">
              Risk Forecasting Module — Model Architecture &amp; Output Interpretation
            </p>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-container-high rounded-full border border-outline-variant/40 text-xs text-on-surface-variant w-fit">
            <span className="material-symbols-outlined text-primary text-sm" aria-hidden="true">
              visibility
            </span>
            <span>
              Role:{' '}
              <span className="font-semibold text-primary uppercase tracking-wide">
                {role}
              </span>
            </span>
          </div>
        </div>

        <p className="text-xs text-on-surface-variant leading-relaxed max-w-4xl">
          Role-appropriate transparency documentation for epidemic decision support models and scientific boundaries.
        </p>
      </header>

      {/* Authorized Transparency Scope Section */}
      <section aria-labelledby="transparency-scope-heading" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-3">
        <div className="flex items-center justify-between">
          <h2 id="transparency-scope-heading" className="text-base font-semibold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-lg" aria-hidden="true">
              fact_check
            </span>
            <span>Authorized transparency scope</span>
          </h2>
          <span className="text-xs text-on-surface-variant">
            {role === ROLES.FARMER ? 'Registered farm district' : `${authorizedDistricts.length} districts authorized`}
          </span>
        </div>

        <div className="flex flex-wrap gap-2 pt-1">
          {role === ROLES.FARMER ? (
            <span className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface border border-outline-variant/40 text-xs font-medium tracking-wide flex items-center gap-1.5">
              <span className="material-symbols-outlined text-xs text-primary" aria-hidden="true">
                home_pin
              </span>
              <span>{farmerDistrict} District</span>
            </span>
          ) : (
            authorizedDistricts.map((dst) => (
              <span
                key={dst}
                className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface border border-outline-variant/40 text-xs font-medium tracking-wide flex items-center gap-1.5"
              >
                <span className="material-symbols-outlined text-xs text-primary" aria-hidden="true">
                  location_on
                </span>
                <span>{dst} District</span>
              </span>
            ))
          )}
        </div>

        <p className="text-xs text-on-surface-variant pt-2 border-t border-outline-variant/20">
          Frontend capability checks control presentation only. Backend authorization remains required before live model output can be retrieved.
        </p>
      </section>

      {/* Integration Status Notice (Accessible Status Region) */}
      <section
        role="status"
        aria-live="polite"
        aria-labelledby="model-transparency-integration-heading"
        className="p-6 rounded-2xl bg-surface-container border border-amber-500/30 shadow-xl space-y-2"
      >
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
            <span className="material-symbols-outlined text-2xl" aria-hidden="true">
              analytics
            </span>
          </div>
          <div className="space-y-1.5">
            <h2 id="model-transparency-integration-heading" className="text-lg font-semibold text-amber-300 tracking-wide">
              Live model outputs are awaiting secure integration
            </h2>
            <p className="text-sm text-on-surface-variant leading-relaxed">
              Backend responses define transparency and uncertainty fields, but live model output has not been requested for this session. This screen currently provides reference documentation only.
            </p>
            <p className="text-xs text-amber-400/90 font-medium">
              Missing values must not be interpreted as zero uncertainty or perfect reliability.
            </p>
          </div>
        </div>
      </section>

      {/* ROLE PRESENTATION: FARMER */}
      {role === ROLES.FARMER && (
        <section aria-labelledby="farmer-transparency-heading" className="space-y-6">
          <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-4">
            <h2 id="farmer-transparency-heading" className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
              <span className="material-symbols-outlined text-primary" aria-hidden="true">
                help_center
              </span>
              <span>How to understand your forecast</span>
            </h2>

            <ul className="space-y-3 text-sm text-on-surface-variant leading-relaxed list-disc list-inside">
              <li>
                Forecasts estimate district-level disease outbreak likelihood for administrative areas in Sri Lanka.
              </li>
              <li>
                Forecasts provide early warning guidance for regional risk awareness and do not diagnose individual animals or farms.
              </li>
              <li>
                Forecast results can be affected by surveillance input availability across the district.
              </li>
              <li>
                Historical reference inputs may be used when current-period surveillance inputs are unavailable or delayed.
              </li>
              <li>
                Clinical diagnosis always requires authorized veterinary field investigation or laboratory confirmation.
              </li>
            </ul>
          </div>
        </section>
      )}

      {/* ROLE PRESENTATION: VETERINARY OFFICER */}
      {role === ROLES.VETERINARY_OFFICER && (
        <section aria-labelledby="vet-transparency-heading" className="space-y-6">
          <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-4">
            <h2 id="vet-transparency-heading" className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
              <span className="material-symbols-outlined text-primary" aria-hidden="true">
                medical_services
              </span>
              <span>Operational model interpretation</span>
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <article aria-labelledby="vet-stage1-ref" className="p-4 rounded-xl bg-surface-container-high/60 border border-outline-variant/40 space-y-2">
                <div className="flex items-center justify-between">
                  <h3 id="vet-stage1-ref" className="text-sm font-semibold text-on-surface">Stage 1 Likelihood</h3>
                  <span className="text-xs text-amber-400 font-medium">Reference only — no live model output loaded</span>
                </div>
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  Stage 1 outputs represent district-level outbreak occurrence likelihood. Forecast probabilities reflect regional risk trends and are not farm-level outbreak predictions.
                </p>
              </article>

              <article aria-labelledby="vet-uq-ref" className="p-4 rounded-xl bg-surface-container-high/60 border border-outline-variant/40 space-y-2">
                <div className="flex items-center justify-between">
                  <h3 id="vet-uq-ref" className="text-sm font-semibold text-on-surface">Uncertainty Disclosure</h3>
                  <span className="text-xs text-amber-400 font-medium">Reference only — no live model output loaded</span>
                </div>
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  Uncertainty evaluation output may be graded as HEURISTIC, VALIDATED, or UNRELIABLE_INSUFFICIENT_DATA. Unavailable or unreliable uncertainty must be explicitly disclosed during surveillance planning.
                </p>
              </article>

              <article aria-labelledby="vet-stage2-ref" className="p-4 rounded-xl bg-surface-container-high/60 border border-outline-variant/40 space-y-2">
                <div className="flex items-center justify-between">
                  <h3 id="vet-stage2-ref" className="text-sm font-semibold text-on-surface">Stage 2 Disease-Specific Output</h3>
                  <span className="text-xs text-amber-400 font-medium">Reference only — no live model output loaded</span>
                </div>
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  Stage 2 is evaluated under disease-specific backend conditions when Stage 1 probability reaches decision thresholds. Operational interpretation differs by disease: FMD Stage 2 evaluates active outbreak severity, whereas LSD Stage 2 serves strictly as a quiet-period false-alarm suppressor and is not a validated active-wave severity prediction.
                </p>
              </article>

              <article aria-labelledby="vet-provenance-ref" className="p-4 rounded-xl bg-surface-container-high/60 border border-outline-variant/40 space-y-2">
                <div className="flex items-center justify-between">
                  <h3 id="vet-provenance-ref" className="text-sm font-semibold text-on-surface">Surveillance Sourcing</h3>
                  <span className="text-xs text-amber-400 font-medium">Reference only — no live model output loaded</span>
                </div>
                <p className="text-xs text-on-surface-variant leading-relaxed">
                  Input fallback and data provenance affect forecast interpretation. Forecasts support surveillance prioritization but do not replace field investigations or confirmed diagnostic alerts.
                </p>
              </article>
            </div>
          </div>
        </section>
      )}

      {/* ROLE PRESENTATION: DAPH OFFICIAL */}
      {role === ROLES.DAPH_OFFICIAL && (
        <section aria-labelledby="daph-technical-heading" className="space-y-6">
          <div className="space-y-1">
            <h2 id="daph-technical-heading" className="text-xl font-bold text-on-surface tracking-tight">
              Technical model transparency reference
            </h2>
            <p className="text-xs text-on-surface-variant">
              Verified backend prediction and evaluation schemas for DAPH departmental oversight.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 1. Stage 1 Prediction */}
            <article aria-labelledby="daph-tech-stage1" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-3">
              <div className="flex items-center justify-between">
                <h3 id="daph-tech-stage1" className="text-base font-semibold text-primary font-mono text-xs sm:text-sm break-words">
                  1. Stage 1 Binary Outbreak Likelihood (Stage1Prediction)
                </h3>
                <span className="text-xs text-amber-400 font-medium">Reference only — no live model output loaded</span>
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed break-words">
                Represents outbreak occurrence likelihood (probability, probability_pct) evaluated against decision_threshold (t=0.40) to assign risk_level (LOW, MEDIUM, HIGH) and record model_variant. Meaning remains strictly district-level.
              </p>
            </article>

            {/* 2. Stage 2 Disease-Specific Output */}
            <article aria-labelledby="daph-tech-stage2" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-3">
              <div className="flex items-center justify-between">
                <h3 id="daph-tech-stage2" className="text-base font-semibold text-primary font-mono text-xs sm:text-sm break-words">
                  2. Stage 2 Disease-Specific Output (Stage2Prediction)
                </h3>
                <span className="text-xs text-amber-400 font-medium">Reference only — no live model output loaded</span>
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed break-words">
                Respects stage2.evaluated status (True when Stage 1 probability &gt;= 0.40) and tracks severity_predicted, model_name, notes, and action_required. FMD Stage 2 provides backend-returned severity output when evaluated. LSD Stage 2 serves strictly as a quiet-period false-alarm suppressor and is not statistically validated to discriminate severity during active outbreak waves.
              </p>
            </article>


            {/* 3. Probability Calibration */}
            <article aria-labelledby="daph-tech-calib" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-3">
              <div className="flex items-center justify-between">
                <h3 id="daph-tech-calib" className="text-base font-semibold text-primary font-mono text-xs sm:text-sm break-words">
                  3. Probability Calibration (CalibrationInfo)
                </h3>
                <span className="text-xs text-amber-400 font-medium">Reference only — no live model output loaded</span>
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed break-words">
                Records calibration_info (is_calibrated, calibration_method, ece_score, notes). Expected Calibration Error (ECE) is a statistical calibration metric measuring probability reliability, not outbreak probability itself.
              </p>
            </article>

            {/* 4. Uncertainty Quantification */}
            <article aria-labelledby="daph-tech-uq" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-3">
              <div className="flex items-center justify-between">
                <h3 id="daph-tech-uq" className="text-base font-semibold text-primary font-mono text-xs sm:text-sm break-words">
                  4. Uncertainty Quantification (UncertaintyInfo)
                </h3>
                <span className="text-xs text-amber-400 font-medium">Reference only — no live model output loaded</span>
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed break-words">
                Evaluates uncertainty method, status (HEURISTIC, VALIDATED, UNRELIABLE_INSUFFICIENT_DATA), reliability grade, prediction_set, empirical_coverage_pct, and notes. UQ metrics remain separate fields and must not be collapsed into an invented confidence score.
              </p>
            </article>

            {/* 5. Feature Explanation */}
            <article aria-labelledby="daph-tech-exp" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-3">
              <div className="flex items-center justify-between">
                <h3 id="daph-tech-exp" className="text-base font-semibold text-primary font-mono text-xs sm:text-sm break-words">
                  5. Local Feature Explanation (ExplanationInfo)
                </h3>
                <span className="text-xs text-amber-400 font-medium">Reference only — no live model output loaded</span>
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed break-words">
                Linear Log-Odds Decomposition returns additive feature contributions (LOG_ODDS) to decision_score. Log-odds contributions are additive mathematical decision factors, NOT percentage feature importance, and positive or negative directions must not be reinterpreted as causal field effects.
              </p>
            </article>

            {/* 6. Provenance & LSD Disclaimer Handling */}
            <article aria-labelledby="daph-tech-disclaimer" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-3">
              <div className="flex items-center justify-between">
                <h3 id="daph-tech-disclaimer" className="text-base font-semibold text-primary font-mono text-xs sm:text-sm break-words">
                  6. Provenance &amp; LSD Response Disclaimer Protocol
                </h3>
                <span className="text-xs text-amber-400 font-medium">Reference only — no live model output loaded</span>
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed break-words">
                Data provenance affects output interpretation but is distinct from uncertainty probability. When live LSD Stage 2 output is retrieved, authorized technical views must display response.disclaimer verbatim.
              </p>
            </article>
          </div>
        </section>
      )}

      {/* Scientific Boundaries */}
      <section
        aria-labelledby="model-transparency-boundaries-heading"
        className="p-6 rounded-2xl bg-surface-container-low border border-outline-variant/30 text-on-surface space-y-3"
      >
        <div className="flex items-center gap-2 text-on-surface font-semibold text-sm">
          <span className="material-symbols-outlined text-amber-400 text-lg" aria-hidden="true">
            health_and_safety
          </span>
          <h2 id="model-transparency-boundaries-heading">Scientific Interpretation Boundaries</h2>
        </div>
        <p className="text-xs text-on-surface-variant leading-relaxed">
          Predictive risk models evaluate district-level epidemiological outbreak likelihoods using audited statistical methods. Predictive outputs do not confirm active disease on individual farms, nor do they replace authorized veterinary clinical diagnosis or laboratory confirmation.
        </p>
      </section>

      {/* Footer */}
      <footer className="p-4 bg-surface-container-low/60 rounded-xl border border-outline-variant/30 text-center text-xs text-on-surface-variant">
        <p>
          Risk Forecasting Module — Department of Animal Production &amp; Health (DAPH), Sri Lanka.
        </p>
      </footer>
    </div>
  );
}
