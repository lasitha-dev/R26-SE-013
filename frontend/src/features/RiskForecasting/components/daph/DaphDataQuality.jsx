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

const BLOCKED_METRIC_CARDS = [
  {
    id: 'input-availability-heading',
    title: 'Current-Period Input Availability',
    icon: 'rule',
    status: 'Live metric unavailable',
    description:
      'Evaluates whether feature inputs match requested target period observations (EXACT_REQUESTED_PERIOD) or rely on historical proxies.',
  },
  {
    id: 'fallback-usage-heading',
    title: 'Historical Fallback Usage',
    icon: 'history_toggle_off',
    status: 'Live metric unavailable',
    description:
      'Tracks feature fallback usage (fallback_applied) and input proxy age in months (data_age_months) when current observations are delayed.',
  },
  {
    id: 'provenance-coverage-heading',
    title: 'District Provenance Coverage',
    icon: 'policy',
    status: 'Live metric unavailable',
    description:
      'Classifies district feature sourcing into exact period, historical same-month proxy, or district/national historical median imputation.',
  },
  {
    id: 'quality-review-heading',
    title: 'Data-Quality Review Status',
    icon: 'verified_user',
    status: 'Live metric unavailable',
    description:
      'Audits disease-specific input status, including live model fallback metadata and LSD lag-1 observation availability status.',
  },
];

const PROVENANCE_CONCEPTS = [
  {
    title: 'Input Sourcing Provenance (data_quality)',
    description:
      'Backend models classify feature input quality into four explicit levels: EXACT_REQUESTED_PERIOD (exact target match), HISTORICAL_SAME_MONTH_PROXY (same-month historical observations), DISTRICT_HISTORICAL_MEDIAN (district median imputation), and NATIONAL_HISTORICAL_MEDIAN (national median imputation).',
  },
  {
    title: 'Historical Fallback Applied (fallback_applied & data_age_months)',
    description:
      'When current surveillance or environmental data is delayed, historical fallback is applied (fallback_applied = true) and proxy age is recorded (data_age_months). Fallback is an input sourcing mechanism for missing data and does not automatically represent model failure.',
  },
  {
    title: 'FMD Provenance Architecture (FMDDataProvenance)',
    description:
      'FMD responses track model fallback status (model_fallback_applied) and log specific fallback rationale (model_fallback_reason). Model fallback metadata records whether the backend used its compatible fallback prediction path when the preferred input configuration was unavailable.',
  },
  {
    title: 'LSD Target Autocorrelation & Provenance (LSDDataProvenance)',
    description:
      'LSD responses evaluate target autocorrelation lag-1 observation status (lag1_status: VERIFIED_OBSERVATION or UNAVAILABLE), model fallback status (model_fallback_applied), and model fallback rationale (model_fallback_reason).',
  },
  {
    title: 'Missing Provenance Handling',
    description:
      'Absence of provenance metadata prevents a reliable current data-quality conclusion. Unconnected or missing metrics must not be interpreted as complete or zero-fallback data.',
  },
];

/**
 * DAPH Official Data Quality Component
 * UI_READY_API_BLOCKED: Capability-gated screen for DAPH officials with viewDataQuality permission.
 * Explains backend data provenance schema concepts while keeping live district metrics blocked
 * until backend scope authorization is integrated.
 *
 * @param {object} props
 * @param {object} props.viewerContext
 */
export function DaphDataQuality({ viewerContext }) {
  // 1. Access & Strict Capability Validation
  const validation = validateViewerContext(viewerContext);
  const isDaphRole =
    validation.valid && validation.normalizedContext.role === ROLES.DAPH_OFFICIAL;

  const scopeLevel = isDaphRole ? validation.normalizedContext.authorization.scopeLevel : null;
  const isAllowedScope =
    scopeLevel === SCOPE_LEVELS.DISTRICT ||
    scopeLevel === SCOPE_LEVELS.PROVINCE ||
    scopeLevel === SCOPE_LEVELS.NATIONAL;

  const authorizedDistricts = isDaphRole ? getAuthorizedDistricts(viewerContext) : [];
  const hasAuthorizedDistricts = authorizedDistricts.length > 0;

  // Strict boolean check for viewDataQuality permission (must not infer from role alone)
  const hasDataQualityPermission = hasForecastingPermission(
    viewerContext,
    PERMISSIONS.viewDataQuality
  );

  const isAccessAllowed = Boolean(
    isDaphRole && isAllowedScope && hasAuthorizedDistricts && hasDataQualityPermission
  );

  if (!isAccessAllowed) {
    return (
      <AccessContextUnavailable
        reason={
          validation.reason ||
          'DAPH_OFFICIAL role with valid scopeLevel, explicit authorized districts, and viewDataQuality permission required.'
        }
      />
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-on-surface">
      {/* Header */}
      <header className="bg-surface-container p-6 rounded-2xl border border-outline-variant/30 shadow-xl space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-primary tracking-tight">
              Data Quality &amp; Input Provenance
            </h1>
            <p className="text-sm text-on-surface-variant">
              Department of Animal Production &amp; Health (DAPH) — Epidemiological Data Quality
            </p>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-container-high rounded-full border border-outline-variant/40 text-xs text-on-surface-variant w-fit">
            <span className="material-symbols-outlined text-primary text-sm" aria-hidden="true">
              high_quality
            </span>
            <span>
              Scope:{' '}
              <span className="font-semibold text-primary uppercase tracking-wide">
                {scopeLevel}
              </span>
            </span>
          </div>
        </div>

        <p className="text-xs text-on-surface-variant leading-relaxed max-w-4xl">
          Capability-gated oversight of feature sourcing, historical fallback usage, and input provenance standards.
        </p>
      </header>

      {/* Authorized Data Quality Scope */}
      <section aria-labelledby="dq-scope-heading" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-3">
        <div className="flex items-center justify-between">
          <h2 id="dq-scope-heading" className="text-base font-semibold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-lg" aria-hidden="true">
              fact_check
            </span>
            <span>Authorized data-quality scope</span>
          </h2>
          <span className="text-xs text-on-surface-variant">
            {authorizedDistricts.length} {authorizedDistricts.length === 1 ? 'district' : 'districts'} assigned
          </span>
        </div>

        <div className="flex flex-wrap gap-2 pt-1">
          {authorizedDistricts.map((dst) => (
            <span
              key={dst}
              className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface border border-outline-variant/40 text-xs font-medium tracking-wide flex items-center gap-1.5"
            >
              <span className="material-symbols-outlined text-xs text-primary" aria-hidden="true">
                location_on
              </span>
              <span>{dst} District</span>
            </span>
          ))}
        </div>

        <p className="text-xs text-on-surface-variant pt-2 border-t border-outline-variant/20">
          Frontend capability and scope checks control presentation only. Backend authorization remains required for operational data access.
        </p>
      </section>

      {/* Integration Status Notice (Accessible Status Region) */}
      <section
        role="status"
        aria-live="polite"
        aria-labelledby="daph-dq-integration-heading"
        className="p-6 rounded-2xl bg-surface-container border border-amber-500/30 shadow-xl space-y-2"
      >
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
            <span className="material-symbols-outlined text-2xl" aria-hidden="true">
              sync_problem
            </span>
          </div>
          <div className="space-y-1.5">
            <h2 id="daph-dq-integration-heading" className="text-lg font-semibold text-amber-300 tracking-wide">
              Live data-quality metrics are awaiting secure integration
            </h2>
            <p className="text-sm text-on-surface-variant leading-relaxed">
              Backend forecasting responses contain provenance and fallback information, but secure scoped retrieval is not connected. Current district quality and fallback status cannot be displayed safely.
            </p>
            <p className="text-xs text-amber-400/90 font-medium">
              Missing metrics must not be interpreted as complete, current or high-quality data.
            </p>
          </div>
        </div>
      </section>

      {/* Blocked Metric Cards Grid */}
      <section aria-labelledby="dq-blocked-cards-heading" className="space-y-4">
        <h2 id="dq-blocked-cards-heading" className="text-xl font-bold text-on-surface tracking-tight">
          District Data-Quality Metrics
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {BLOCKED_METRIC_CARDS.map((card) => (
            <article
              key={card.id}
              className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg flex flex-col justify-between space-y-4"
              aria-labelledby={card.id}
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-lg bg-surface-container-high text-on-surface-variant border border-outline-variant/40">
                      <span className="material-symbols-outlined text-xl" aria-hidden="true">
                        {card.icon}
                      </span>
                    </div>
                    <h3 id={card.id} className="text-base font-semibold text-on-surface">
                      {card.title}
                    </h3>
                  </div>

                  <span className="px-2.5 py-1 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/30 text-xs font-semibold">
                    {card.status}
                  </span>
                </div>

                <p className="text-xs text-on-surface-variant leading-relaxed">
                  {card.description}
                </p>
              </div>

              <div className="pt-3 border-t border-outline-variant/20 text-xs text-on-surface-variant flex items-center gap-1.5">
                <span className="material-symbols-outlined text-sm" aria-hidden="true">
                  lock
                </span>
                <span>Awaiting backend scoped data integration</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Verified Backend Provenance Reference Concepts */}
      <section aria-labelledby="provenance-concepts-heading" className="space-y-4">
        <div className="space-y-1">
          <h2 id="provenance-concepts-heading" className="text-xl font-bold text-on-surface tracking-tight">
            Backend Data Provenance &amp; Quality Architecture
          </h2>
          <p className="text-xs text-on-surface-variant">
            Technical reference documentation for DAPH data provenance parameters implemented in backend risk forecasting endpoints.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {PROVENANCE_CONCEPTS.map((item, idx) => (
            <article
              key={idx}
              className="p-5 rounded-xl bg-surface-container border border-outline-variant/30 shadow space-y-2"
            >
              <h3 className="text-sm font-semibold text-primary font-mono text-xs sm:text-sm break-words">{item.title}</h3>
              <p className="text-xs text-on-surface-variant leading-relaxed break-words">{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      {/* Scientific & Diagnostic Interpretation Boundaries */}
      <section
        aria-labelledby="dq-scientific-boundaries-heading"
        className="p-6 rounded-2xl bg-surface-container-low border border-outline-variant/30 text-on-surface space-y-3"
      >
        <div className="flex items-center gap-2 text-on-surface font-semibold text-sm">
          <span className="material-symbols-outlined text-amber-400 text-lg" aria-hidden="true">
            biomedical
          </span>
          <h2 id="dq-scientific-boundaries-heading">Scientific Interpretation Boundaries</h2>
        </div>
        <p className="text-xs text-on-surface-variant leading-relaxed">
          Data provenance describes input sourcing and feature availability, not prediction certainty or outbreak probability. Historical fallback usage does not provide a probability of model correctness. Data quality metrics must not be interpreted as risk levels, nor can any farm-level conclusions be derived.
        </p>
      </section>

      {/* Footer */}
      <footer className="p-4 bg-surface-container-low/60 rounded-xl border border-outline-variant/30 text-center text-xs text-on-surface-variant">
        <p>
          Departmental Decision Support — Department of Animal Production &amp; Health (DAPH), Sri Lanka.
        </p>
      </footer>
    </div>
  );
}
