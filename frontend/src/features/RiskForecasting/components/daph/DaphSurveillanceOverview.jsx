import React from 'react';
import PropTypes from 'prop-types';
import {
  ROLES,
  SCOPE_LEVELS,
  validateViewerContext,
  getAuthorizedDistricts,
} from '../../contracts/viewerContext.js';
import { AccessContextUnavailable } from '../AccessContextUnavailable.jsx';
import { OPERATIONAL_STATUS } from '../../hooks/useDemoOperationalData.js';

const BLOCKED_MODULES = [
  {
    id: 'verified-records-heading',
    title: 'Verified Surveillance Records',
    icon: 'folder_managed',
    description:
      'National case registry, field disease observations, and laboratory diagnostic records are not connected.',
  },
  {
    id: 'authorized-alerts-heading',
    title: 'Authorized Alerts',
    icon: 'notifications_paused',
    description:
      'Official departmental outbreak notification channels, warning alerts, and escalation services are unavailable.',
  },
  {
    id: 'regional-summaries-heading',
    title: 'Regional Situation Summaries',
    icon: 'grid_view',
    description:
      'Verified provincial and district epidemiological aggregation tools are not connected to operational databases.',
  },
  {
    id: 'response-coordination-heading',
    title: 'Response Coordination',
    icon: 'hub',
    description:
      'National outbreak investigation tracking, quarantine management, and field response task services are not connected.',
  },
];

const COORDINATION_PRINCIPLES = [
  {
    title: 'Laboratory Validation',
    description: 'Validate suspected disease outbreaks through authorized veterinary field investigations and laboratory procedures.',
  },
  {
    title: 'Traceable Audit Logs',
    description: 'Maintain complete, traceable surveillance observation logs and outbreak response activity records.',
  },
  {
    title: 'Departmental Escalation',
    description: 'Coordinate epidemic escalation and official biosecurity directives through approved DAPH channels.',
  },
  {
    title: 'Evidence Separation',
    description: 'Keep statistical predictive risk modeling separate from verified field clinical diagnostic evidence.',
  },
  {
    title: 'Authorized Scope Control',
    description: 'Apply explicit regional authorization controls prior to requesting or distributing operational surveillance data.',
  },
];

/**
 * DAPH Official Surveillance Overview Component
 *
 * @param {object} props
 * @param {object} props.viewerContext
 * @param {object} [props.operationalData]
 */
export function DaphSurveillanceOverview({ viewerContext, operationalData = null }) {
  // 1. Access & Fail-Closed Validation
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

  const isAccessAllowed = Boolean(isDaphRole && isAllowedScope && hasAuthorizedDistricts);

  if (!isAccessAllowed) {
    return (
      <AccessContextUnavailable
        reason={
          validation.reason ||
          'DAPH_OFFICIAL role with valid scopeLevel and explicit authorized districts required.'
        }
      />
    );
  }

  const { surveillanceRecords, alerts, responseTasks } = operationalData || {};

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8 text-on-surface">
      {/* Synthetic Data & Non-Training Notice */}
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
      <header className="bg-surface-container p-6 rounded-2xl border border-outline-variant/30 shadow-xl space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-primary tracking-tight">
              Departmental Surveillance Overview
            </h1>
            <p className="text-sm text-on-surface-variant">
              Department of Animal Production &amp; Health (DAPH) — National &amp; Regional Surveillance
            </p>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-container-high rounded-full border border-outline-variant/40 text-xs text-on-surface-variant w-fit">
            <span className="material-symbols-outlined text-primary text-sm" aria-hidden="true">
              account_balance
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
          {operationalData
            ? 'District-scoped synthetic operational records for authorized surveillance observations, departmental alert notifications, and regional response task tracking.'
            : 'National and regional epidemiological surveillance oversight for authorized DAPH officials.'}
        </p>
      </header>

      {/* Authorized Surveillance Scope Section */}
      <section aria-labelledby="daph-authorized-scope-heading" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-3">
        <div className="flex items-center justify-between">
          <h2 id="daph-authorized-scope-heading" className="text-base font-semibold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-lg" aria-hidden="true">
              domain
            </span>
            <span>Authorized surveillance scope</span>
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
          Scope shown here comes from the current frontend integration contract. Operational authorization must be enforced by the backend.
        </p>
      </section>

      {/* Connected vs Blocked Operational Modules */}
      {!operationalData ? (
        /* Unconnected / Legacy Blocked View */
        <>
          <section
            role="status"
            aria-live="polite"
            aria-labelledby="daph-overview-integration-heading"
            className="p-6 rounded-2xl bg-surface-container border border-amber-500/30 shadow-xl space-y-2"
          >
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
                <span className="material-symbols-outlined text-2xl" aria-hidden="true">
                  dvr
                </span>
              </div>
              <div className="space-y-1.5">
                <h2 id="daph-overview-integration-heading" className="text-lg font-semibold text-amber-300 tracking-wide">
                  Surveillance overview is awaiting verified data integration
                </h2>
                <p className="text-sm text-on-surface-variant leading-relaxed">
                  This interface cannot determine current case, alert or response status until verified surveillance services and backend authorization are connected.
                </p>
                <p className="text-xs text-amber-400/90 font-medium">
                  Unavailable records must not be interpreted as zero cases, zero alerts or no disease risk.
                </p>
              </div>
            </div>
          </section>

          <section aria-labelledby="daph-overview-modules-heading" className="space-y-4">
            <h2 id="daph-overview-modules-heading" className="text-xl font-bold text-on-surface tracking-tight">
              Departmental Overview Modules
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {BLOCKED_MODULES.map((card) => (
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
                        Integration unavailable
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
                    <span>Requires DAPH backend integration</span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </>
      ) : (
        /* Connected Live DAPH Sections */
        <div className="space-y-8">
          {/* Module 1: District Surveillance Records */}
          <section aria-labelledby="daph-surv-records-heading" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 id="daph-surv-records-heading" className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">
                  folder_managed
                </span>
                <span>District Surveillance Records</span>
              </h2>
              {surveillanceRecords?.count !== undefined && (
                <span className="text-xs text-on-surface-variant font-medium px-2.5 py-1 bg-surface-container-high rounded-full border border-outline-variant/30">
                  Total Count: {surveillanceRecords.count}
                </span>
              )}
            </div>

            {surveillanceRecords?.status === OPERATIONAL_STATUS.LOADING && (
              <div role="status" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-center space-y-2">
                <span className="material-symbols-outlined text-2xl text-primary animate-spin" aria-hidden="true">progress_activity</span>
                <p className="text-xs text-on-surface-variant">Loading district synthetic surveillance records...</p>
              </div>
            )}

            {surveillanceRecords?.status === OPERATIONAL_STATUS.EMPTY && (
              <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-xs text-on-surface-variant">
                No synthetic surveillance records found for authorized districts.
              </div>
            )}

            {surveillanceRecords?.status === OPERATIONAL_STATUS.ERROR && (
              <div role="alert" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-error/30 space-y-3">
                <p className="text-xs text-error font-medium">{surveillanceRecords.error || 'Failed to load surveillance records.'}</p>
                <button type="button" onClick={() => surveillanceRecords.reload()} className="min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high border border-outline-variant text-xs font-semibold text-on-surface">Try again</button>
              </div>
            )}

            {surveillanceRecords?.status === OPERATIONAL_STATUS.SUCCESS && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {surveillanceRecords.items.map((rec) => (
                  <article key={rec.surveillanceRecordId} className="p-5 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-md space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="px-2.5 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-bold">
                        {rec.diseaseCode} ({rec.district} District)
                      </span>
                      <span className="px-2.5 py-0.5 rounded-md bg-surface-container-high text-on-surface-variant text-xs font-semibold">
                        {rec.verificationStatus}
                      </span>
                    </div>

                    <div className="space-y-1 text-xs text-on-surface-variant">
                      <p className="text-on-surface font-medium">{rec.summary}</p>
                      <div><span className="font-semibold text-on-surface">Evidence Type:</span> {rec.evidenceType}</div>
                      <div><span className="font-semibold text-on-surface">Observed At:</span> {new Date(rec.observedAt).toLocaleString()}</div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          {/* Module 2: Departmental Alerts */}
          <section aria-labelledby="daph-alerts-heading" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 id="daph-alerts-heading" className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
                <span className="material-symbols-outlined text-amber-400 text-xl" aria-hidden="true">
                  notifications_active
                </span>
                <span>Departmental Outbreak Alerts</span>
              </h2>
              {alerts?.count !== undefined && (
                <span className="text-xs text-on-surface-variant font-medium px-2.5 py-1 bg-surface-container-high rounded-full border border-outline-variant/30">
                  Total Count: {alerts.count}
                </span>
              )}
            </div>

            {alerts?.status === OPERATIONAL_STATUS.LOADING && (
              <div role="status" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-center space-y-2">
                <span className="material-symbols-outlined text-2xl text-primary animate-spin" aria-hidden="true">progress_activity</span>
                <p className="text-xs text-on-surface-variant">Loading departmental synthetic alerts...</p>
              </div>
            )}

            {alerts?.status === OPERATIONAL_STATUS.EMPTY && (
              <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-xs text-on-surface-variant">
                No synthetic alerts found for authorized districts.
              </div>
            )}

            {alerts?.status === OPERATIONAL_STATUS.ERROR && (
              <div role="alert" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-error/30 space-y-3">
                <p className="text-xs text-error font-medium">{alerts.error || 'Failed to load departmental alerts.'}</p>
                <button type="button" onClick={() => alerts.reload()} className="min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high border border-outline-variant text-xs font-semibold text-on-surface">Try again</button>
              </div>
            )}

            {alerts?.status === OPERATIONAL_STATUS.SUCCESS && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {alerts.items.map((alert) => (
                  <article key={alert.alertId} className="p-5 rounded-2xl bg-surface-container border border-amber-500/40 shadow-md space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="px-2.5 py-0.5 rounded-md bg-amber-500/20 text-amber-300 text-xs font-bold">
                        {alert.diseaseCode} — {alert.district}
                      </span>
                      <span className="px-2 py-0.5 rounded-md bg-surface-container-high text-on-surface-variant text-[11px] font-semibold uppercase">
                        {alert.status}
                      </span>
                    </div>

                    <div className="space-y-1 text-xs text-on-surface-variant">
                      <h3 className="text-sm font-bold text-on-surface">{alert.title}</h3>
                      <p>{alert.message}</p>
                      <div><span className="font-semibold text-on-surface">Priority:</span> {alert.priority}</div>
                      <div><span className="font-semibold text-on-surface">Issued:</span> {new Date(alert.issuedAt).toLocaleString()}</div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          {/* Module 3: Response Coordination */}
          <section aria-labelledby="daph-response-tasks-heading" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 id="daph-response-tasks-heading" className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">
                  hub
                </span>
                <span>Regional Response Coordination Tasks</span>
              </h2>
              {responseTasks?.count !== undefined && (
                <span className="text-xs text-on-surface-variant font-medium px-2.5 py-1 bg-surface-container-high rounded-full border border-outline-variant/30">
                  Total Count: {responseTasks.count}
                </span>
              )}
            </div>

            {responseTasks?.status === OPERATIONAL_STATUS.LOADING && (
              <div role="status" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-center space-y-2">
                <span className="material-symbols-outlined text-2xl text-primary animate-spin" aria-hidden="true">progress_activity</span>
                <p className="text-xs text-on-surface-variant">Loading response tasks...</p>
              </div>
            )}

            {responseTasks?.status === OPERATIONAL_STATUS.EMPTY && (
              <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-xs text-on-surface-variant">
                No synthetic response tasks found for authorized districts.
              </div>
            )}

            {responseTasks?.status === OPERATIONAL_STATUS.ERROR && (
              <div role="alert" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-error/30 space-y-3">
                <p className="text-xs text-error font-medium">{responseTasks.error || 'Failed to load response tasks.'}</p>
                <button type="button" onClick={() => responseTasks.reload()} className="min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high border border-outline-variant text-xs font-semibold text-on-surface">Try again</button>
              </div>
            )}

            {responseTasks?.status === OPERATIONAL_STATUS.SUCCESS && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {responseTasks.items.map((task) => (
                  <article key={task.responseTaskId} className="p-5 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-md space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-on-surface">{task.taskType} ({task.district})</h3>
                      <span className="px-2 py-0.5 rounded-md bg-surface-container-high text-on-surface-variant text-[11px] font-semibold uppercase">
                        {task.status}
                      </span>
                    </div>

                    <div className="space-y-1 text-xs text-on-surface-variant">
                      <p>{task.notes}</p>
                      <div><span className="font-semibold text-on-surface">Due Date:</span> {new Date(task.dueAt).toLocaleString()}</div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {/* General Surveillance Coordination Principles */}
      <section aria-labelledby="coordination-principles-heading" className="space-y-4">
        <div className="space-y-1">
          <h2 id="coordination-principles-heading" className="text-xl font-bold text-on-surface tracking-tight">
            General surveillance coordination principles
          </h2>
          <p className="text-xs text-on-surface-variant">
            Standard departmental operating guidelines for DAPH officials. These static reference principles are not active tasks assigned to the viewer.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {COORDINATION_PRINCIPLES.map((item, idx) => (
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

      {/* Footer */}
      <footer className="p-4 bg-surface-container-low/60 rounded-xl border border-outline-variant/30 text-center text-xs text-on-surface-variant">
        <p>
          Departmental Decision Support — Department of Animal Production &amp; Health (DAPH), Sri Lanka.
        </p>
      </footer>
    </div>
  );
}

DaphSurveillanceOverview.propTypes = {
  viewerContext: PropTypes.object,
  operationalData: PropTypes.object,
};
