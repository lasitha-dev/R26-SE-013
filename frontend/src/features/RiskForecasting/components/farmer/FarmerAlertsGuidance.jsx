import React from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  SCOPE_LEVELS,
  validateViewerContext,
  getRegisteredFarmDistrict,
} from '../../contracts/viewerContext.js';
import { AccessContextUnavailable } from '../AccessContextUnavailable.jsx';
import { OPERATIONAL_STATUS } from '../../hooks/useDemoOperationalData.js';

const GENERAL_GUIDANCE_ITEMS = [
  {
    title: 'Animal Isolation',
    description: 'Isolate newly introduced or visibly unwell animals from the rest of the herd.',
  },
  {
    title: 'Equipment Sanitation',
    description: 'Avoid sharing equipment between farms without appropriate cleaning and disinfection.',
  },
  {
    title: 'Movement Control',
    description: 'Limit unnecessary animal and visitor movement during periods of increased concern.',
  },
  {
    title: 'Hygiene & Housing',
    description: 'Maintain clean feeding, watering, and housing areas for all livestock.',
  },
  {
    title: 'Record Keeping',
    description: 'Keep farm records and animal movement logs current and accessible.',
  },
  {
    title: 'Surveillance Reporting',
    description: 'Contact an authorized veterinary officer when animals show unusual health symptoms.',
  },
];

/**
 * Farmer Alerts & Guidance Component
 *
 * @param {object} props
 * @param {object} props.viewerContext
 * @param {object} [props.operationalData]
 */
export function FarmerAlertsGuidance({ viewerContext, operationalData = null }) {
  // 1. Access & Fail-Closed Validation
  const validation = validateViewerContext(viewerContext);
  const isValidFarmer =
    validation.valid &&
    validation.normalizedContext.role === ROLES.FARMER &&
    validation.normalizedContext.authorization.scopeLevel === SCOPE_LEVELS.FARM;

  const district = isValidFarmer ? getRegisteredFarmDistrict(viewerContext) : null;
  const isAccessAllowed = Boolean(isValidFarmer && district && district.trim() !== '');

  if (!isAccessAllowed) {
    return (
      <AccessContextUnavailable
        reason={
          validation.reason ||
          'FARMER role with valid FARM scopeLevel and registered district required.'
        }
      />
    );
  }

  const { farms, alerts } = operationalData || {};

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-on-surface">
      {/* Synthetic Data & Non-Training Caution Notice */}
      {operationalData && (
        <div
          role="note"
          className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-start gap-3 shadow-md"
        >
          <span className="material-symbols-outlined text-amber-400 text-lg shrink-0 mt-0.5" aria-hidden="true">
            warning
          </span>
          <p className="leading-relaxed">
            This screen uses synthetic operational records for demonstration and software testing only. These records must not be used for model training or scientific conclusions.
          </p>
        </div>
      )}

      {/* Header */}
      <header className="bg-surface-container p-6 rounded-2xl border border-outline-variant/30 shadow-xl space-y-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <h1 className="text-2xl font-bold text-primary tracking-tight">
            Alerts &amp; Guidance
          </h1>
          <span className="text-xs font-medium px-3 py-1 bg-surface-container-high text-on-surface-variant rounded-full border border-outline-variant/40 w-fit">
            Registered area: <span className="font-semibold text-primary">{district} District</span>
          </span>
        </div>
        <p className="text-sm text-on-surface-variant max-w-3xl">
          {operationalData
            ? 'Authorized farm operational details and active synthetic outbreak alerts for your registered district.'
            : 'Personalized surveillance alerts are not yet connected to the verified alert and farm-registration services.'}
        </p>
      </header>

      {/* Authorized Farm Details Section (when connected) */}
      {farms && (
        <section aria-labelledby="authorized-farm-info-heading" className="space-y-4">
          <h2 id="authorized-farm-info-heading" className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">
              home_work
            </span>
            <span>Registered Farm Operational Info</span>
          </h2>

          {farms.status === OPERATIONAL_STATUS.LOADING && (
            <div role="status" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-center space-y-2">
              <span className="material-symbols-outlined text-2xl text-primary animate-spin" aria-hidden="true">
                progress_activity
              </span>
              <p className="text-xs text-on-surface-variant">Loading registered farm operational data...</p>
            </div>
          )}

          {farms.status === OPERATIONAL_STATUS.ERROR && (
            <div role="alert" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-error/30 text-on-surface space-y-3">
              <p className="text-xs text-error font-medium">{farms.error || 'Operational data service is currently unavailable.'}</p>
              <button
                type="button"
                onClick={() => farms.reload()}
                className="min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant text-xs font-semibold text-on-surface"
              >
                Try again
              </button>
            </div>
          )}

          {farms.status === OPERATIONAL_STATUS.FORBIDDEN && (
            <div className="p-6 rounded-2xl bg-surface-container border border-amber-500/30 text-xs text-amber-300">
              Operational farm data access is not permitted for your assigned role or scope.
            </div>
          )}

          {(farms.status === OPERATIONAL_STATUS.SUCCESS || farms.status === OPERATIONAL_STATUS.EMPTY) && (
            <div className="space-y-3">
              {farms.items.length === 0 ? (
                <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-xs text-on-surface-variant">
                  No registered synthetic farm records found for your user account.
                </div>
              ) : (
                farms.items.map((farm) => (
                  <article key={farm.farmId} className="p-5 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-md space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="text-base font-bold text-on-surface">{farm.displayName}</h3>
                      <span className="px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 text-[11px] font-semibold">
                        ACTIVE DEMO FARM
                      </span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-on-surface-variant">
                      <div><span className="font-semibold text-on-surface">District:</span> {farm.district}</div>
                      <div>
                        <span className="font-semibold text-on-surface">Livestock Types:</span>{' '}
                        {farm.livestockTypes?.join(', ') || 'N/A'}
                      </div>
                    </div>
                  </article>
                ))
              )}
            </div>
          )}
        </section>
      )}

      {/* Live Alerts Section */}
      {!operationalData ? (
        /* Legacy Blocked UI when operationalData is absent */
        <section
          role="status"
          aria-live="polite"
          aria-labelledby="alerts-integration-heading"
          className="p-6 rounded-2xl bg-surface-container border border-amber-500/30 shadow-xl space-y-4"
        >
          <div className="flex items-start gap-4">
            <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
              <span className="material-symbols-outlined text-2xl" aria-hidden="true">
                notifications_paused
              </span>
            </div>
            <div className="space-y-2">
              <h2 id="alerts-integration-heading" className="text-lg font-semibold text-amber-300 tracking-wide">
                Personalized alerts are not connected yet
              </h2>
              <p className="text-sm text-on-surface-variant leading-relaxed">
                Verified outbreak alerts are currently unavailable in this component. This screen cannot confirm whether active alerts exist for your farm. Do not interpret this status as "no alerts" or "no risk."
              </p>
              <p className="text-xs text-on-surface-variant/70 leading-relaxed">
                Connecting personalized notifications will require verified farm registration, surveillance records, and authorized veterinary alert channels.
              </p>
            </div>
          </div>
        </section>
      ) : (
        /* Connected Operational Alerts Section */
        <section aria-labelledby="live-alerts-heading" className="space-y-4">
          <h2 id="live-alerts-heading" className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
            <span className="material-symbols-outlined text-amber-400 text-xl" aria-hidden="true">
              notifications_active
            </span>
            <span>Authorized Synthetic Outbreak Alerts</span>
          </h2>

          {alerts?.status === OPERATIONAL_STATUS.LOADING && (
            <div role="status" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-center space-y-2">
              <span className="material-symbols-outlined text-2xl text-primary animate-spin" aria-hidden="true">
                progress_activity
              </span>
              <p className="text-xs text-on-surface-variant">Loading authorized synthetic outbreak alerts...</p>
            </div>
          )}

          {alerts?.status === OPERATIONAL_STATUS.EMPTY && (
            <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-sm text-on-surface-variant leading-relaxed">
              No synthetic alerts were returned for your authorized demo farm.
            </div>
          )}

          {alerts?.status === OPERATIONAL_STATUS.ERROR && (
            <div role="alert" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-error/30 text-on-surface space-y-3">
              <p className="text-xs text-error font-medium">{alerts.error || 'Operational alert service is currently unavailable.'}</p>
              <button
                type="button"
                onClick={() => alerts.reload()}
                className="min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant text-xs font-semibold text-on-surface"
              >
                Try again
              </button>
            </div>
          )}

          {alerts?.status === OPERATIONAL_STATUS.FORBIDDEN && (
            <div className="p-6 rounded-2xl bg-surface-container border border-amber-500/30 text-xs text-amber-300">
              Operational alert access is not permitted for your assigned role or scope.
            </div>
          )}

          {alerts?.status === OPERATIONAL_STATUS.SUCCESS && (
            <div className="space-y-4">
              {alerts.items.map((alert) => (
                <article
                  key={alert.alertId}
                  className="p-6 rounded-2xl bg-surface-container border border-amber-500/40 shadow-lg space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-outline-variant/20 pb-3">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-1 rounded-md bg-amber-500/20 text-amber-300 text-xs font-bold tracking-wider">
                        {alert.diseaseCode}
                      </span>
                      <span className="px-2 py-0.5 rounded-md bg-surface-container-high text-on-surface-variant text-[11px] font-semibold">
                        Priority: {alert.priority}
                      </span>
                      <span className="px-2 py-0.5 rounded-md bg-surface-container-high text-on-surface-variant text-[11px] font-semibold uppercase">
                        {alert.status}
                      </span>
                    </div>

                    <span className="text-[11px] text-amber-300/80 font-medium px-2.5 py-0.5 bg-amber-500/10 rounded-full border border-amber-500/20">
                      Synthetic Demonstration Alert
                    </span>
                  </div>

                  <div className="space-y-1">
                    <h3 className="text-base font-bold text-on-surface">{alert.title}</h3>
                    <p className="text-xs text-on-surface-variant leading-relaxed">{alert.message}</p>
                  </div>

                  <div className="flex flex-wrap justify-between items-center text-[11px] text-on-surface-variant/70 pt-2 border-t border-outline-variant/15">
                    <span>District: {alert.district}</span>
                    <span>Issued: {new Date(alert.issuedAt).toLocaleString()}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {/* General Preventive Guidance Section */}
      <section aria-labelledby="general-guidance-heading" className="space-y-4">
        <div className="space-y-1">
          <h2 id="general-guidance-heading" className="text-xl font-bold text-on-surface tracking-tight">
            General preventive guidance
          </h2>
          <p className="text-xs text-on-surface-variant">
            Standard biosecurity best practices for livestock management. These general educational guidelines are not personalized or generated from forecast outputs or farm records.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {GENERAL_GUIDANCE_ITEMS.map((item, idx) => (
            <article
              key={idx}
              className="p-5 rounded-xl bg-surface-container border border-outline-variant/30 shadow-md flex items-start gap-3.5"
            >
              <span className="text-primary text-lg font-bold shrink-0 mt-0.5">•</span>
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-on-surface">{item.title}</h3>
                <p className="text-xs text-on-surface-variant leading-relaxed">{item.description}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Symptom & Reporting Notice */}
      <section
        aria-labelledby="reporting-notice-heading"
        className="p-6 rounded-2xl bg-surface-container-low border border-outline-variant/30 text-on-surface space-y-3"
      >
        <div className="flex items-center gap-2 text-on-surface font-semibold text-sm">
          <span className="material-symbols-outlined text-amber-400 text-lg" aria-hidden="true">
            health_and_safety
          </span>
          <h2 id="reporting-notice-heading">Official Veterinary Reporting Notice</h2>
        </div>
        <p className="text-xs text-on-surface-variant leading-relaxed">
          Disease forecasting cannot confirm infection in an individual animal. If animals show unusual symptoms, isolate them where practical and contact the authorized local veterinary service.
        </p>
      </section>

      {/* Footer Disclaimer */}
      <footer className="p-4 bg-surface-container-low/60 rounded-xl border border-outline-variant/30 text-center text-xs text-on-surface-variant">
        <p>
          District educational decision support — non-diagnostic biosecurity guidance for Sri Lankan livestock farmers.
        </p>
      </footer>
    </div>
  );
}

FarmerAlertsGuidance.propTypes = {
  viewerContext: PropTypes.object,
  operationalData: PropTypes.object,
};
