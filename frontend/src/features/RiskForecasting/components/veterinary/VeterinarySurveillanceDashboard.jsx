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

const BLOCKED_CARDS = [
  {
    id: 'assigned-farms-heading',
    title: 'Assigned Farms',
    icon: 'other_houses',
    description:
      'Assigned farm records and spatial management tools require integration with the future assigned-farms service.',
  },
  {
    id: 'surveillance-records-heading',
    title: 'Surveillance Records',
    icon: 'clinical_notes',
    description:
      'Verified field observation logs, disease reports, and laboratory diagnostic records are not connected.',
  },
  {
    id: 'active-alerts-heading',
    title: 'Active Alerts',
    icon: 'notifications_paused',
    description:
      'Authorized veterinary outbreak notification channels and district alert escalation services are unavailable.',
  },
  {
    id: 'response-activities-heading',
    title: 'Response Activities',
    icon: 'assignment_turned_in',
    description:
      'Outbreak-response task assignments, field investigation logs, and quarantine record services are not connected.',
  },
];

const SURVEILLANCE_RESPONSIBILITIES = [
  {
    title: 'Symptom Review',
    description: 'Review reports of unusual animal symptoms submitted through authorized surveillance channels.',
  },
  {
    title: 'Field Documentation',
    description: 'Maintain accurate field observation notes, diagnostic samples, and livestock movement records.',
  },
  {
    title: 'Outbreak Escalation',
    description: 'Escalate suspected infectious disease outbreaks through approved departmental procedures.',
  },
  {
    title: 'Field Biosecurity',
    description: 'Apply strict departmental biosecurity practices during farm visits and epidemiological sampling.',
  },
  {
    title: 'Diagnostic Validation',
    description: 'Do not treat statistical forecasting results or risk indicators as laboratory confirmation of infection.',
  },
];

/**
 * Veterinary Officer Surveillance Dashboard Component
 *
 * @param {object} props
 * @param {object} props.viewerContext
 * @param {object} [props.operationalData]
 */
export function VeterinarySurveillanceDashboard({ viewerContext, operationalData = null }) {
  // 1. Access & Fail-Closed Validation
  const validation = validateViewerContext(viewerContext);
  const isVetRole =
    validation.valid && validation.normalizedContext.role === ROLES.VETERINARY_OFFICER;

  const scopeLevel = isVetRole ? validation.normalizedContext.authorization.scopeLevel : null;
  const isAllowedScope =
    scopeLevel === SCOPE_LEVELS.DISTRICT || scopeLevel === SCOPE_LEVELS.PROVINCE;

  const authorizedDistricts = isVetRole ? getAuthorizedDistricts(viewerContext) : [];
  const hasAuthorizedDistricts = authorizedDistricts.length > 0;

  const isAccessAllowed = Boolean(isVetRole && isAllowedScope && hasAuthorizedDistricts);

  if (!isAccessAllowed) {
    return (
      <AccessContextUnavailable
        reason={
          validation.reason ||
          'VETERINARY_OFFICER role with valid DISTRICT or PROVINCE scopeLevel and authorized districts required.'
        }
      />
    );
  }

  const { farms, surveillanceRecords, alerts, responseTasks } = operationalData || {};

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
              My Surveillance Dashboard
            </h1>
            <p className="text-sm text-on-surface-variant">
              District Veterinary Surveillance Operations &amp; Field Coordination
            </p>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-container-high rounded-full border border-outline-variant/40 text-xs text-on-surface-variant w-fit">
            <span className="material-symbols-outlined text-primary text-sm" aria-hidden="true">
              shield_person
            </span>
            <span>
              Role Scope:{' '}
              <span className="font-semibold text-primary uppercase tracking-wide">
                {scopeLevel}
              </span>
            </span>
          </div>
        </div>

        <p className="text-xs text-on-surface-variant leading-relaxed max-w-4xl">
          {operationalData
            ? 'Authenticated synthetic operational records for assigned farms, field surveillance observations, outbreak alerts, and response tasks.'
            : 'This dashboard is prepared for future integration with verified farm assignments, surveillance records, authorized alerts, and response activities.'}
        </p>
      </header>

      {/* Authorized Surveillance Scope Section */}
      <section aria-labelledby="authorized-scope-heading" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-lg space-y-3">
        <div className="flex items-center justify-between">
          <h2 id="authorized-scope-heading" className="text-base font-semibold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-lg" aria-hidden="true">
              map
            </span>
            <span>Authorized surveillance area</span>
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
          Access shown here is based on the current frontend integration contract. Server-side authorization must be enforced before operational use.
        </p>
      </section>

      {/* Connected vs Blocked Operational Modules */}
      {!operationalData ? (
        /* Unconnected / Legacy Blocked View */
        <>
          <section
            role="status"
            aria-live="polite"
            aria-labelledby="vet-dashboard-integration-heading"
            className="p-6 rounded-2xl bg-surface-container border border-amber-500/30 shadow-xl space-y-2"
          >
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
                <span className="material-symbols-outlined text-2xl" aria-hidden="true">
                  sync_problem
                </span>
              </div>
              <div className="space-y-1.5">
                <h2 id="vet-dashboard-integration-heading" className="text-lg font-semibold text-amber-300 tracking-wide">
                  Surveillance data services unavailable
                </h2>
                <p className="text-sm text-on-surface-variant leading-relaxed">
                  Operational surveillance databases, active alert systems, and farm records are not connected to this frontend component.
                </p>
                <p className="text-xs text-amber-400/90 font-medium">
                  Unavailable data must not be interpreted as zero cases, zero alerts, or no disease risk.
                </p>
              </div>
            </div>
          </section>

          <section aria-labelledby="surveillance-modules-heading" className="space-y-4">
            <h2 id="surveillance-modules-heading" className="text-xl font-bold text-on-surface tracking-tight">
              Surveillance Operational Modules
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {BLOCKED_CARDS.map((card) => (
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
                    <span>Requires backend service integration</span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </>
      ) : (
        /* Connected Live Operational Sections */
        <div className="space-y-8">
          {/* Module 1: Assigned Farms */}
          <section aria-labelledby="assigned-farms-live-heading" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 id="assigned-farms-live-heading" className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">
                  other_houses
                </span>
                <span>Assigned Farms</span>
              </h2>
              {farms?.count !== undefined && (
                <span className="text-xs text-on-surface-variant font-medium px-2.5 py-1 bg-surface-container-high rounded-full border border-outline-variant/30">
                  Total Count: {farms.count}
                </span>
              )}
            </div>

            {farms?.status === OPERATIONAL_STATUS.LOADING && (
              <div role="status" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-center space-y-2">
                <span className="material-symbols-outlined text-2xl text-primary animate-spin" aria-hidden="true">progress_activity</span>
                <p className="text-xs text-on-surface-variant">Loading assigned synthetic farms...</p>
              </div>
            )}

            {farms?.status === OPERATIONAL_STATUS.EMPTY && (
              <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-xs text-on-surface-variant">
                No assigned synthetic farm records found.
              </div>
            )}

            {farms?.status === OPERATIONAL_STATUS.ERROR && (
              <div role="alert" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-error/30 space-y-3">
                <p className="text-xs text-error font-medium">{farms.error || 'Failed to load assigned farms.'}</p>
                <button type="button" onClick={() => farms.reload()} className="min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high border border-outline-variant text-xs font-semibold text-on-surface">Try again</button>
              </div>
            )}

            {farms?.status === OPERATIONAL_STATUS.SUCCESS && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {farms.items.map((farm) => (
                  <article key={farm.farmId} className="p-5 rounded-2xl bg-surface-container border border-outline-variant/30 shadow-md space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-bold text-on-surface">{farm.displayName}</h3>
                      <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 text-[10px] font-semibold">
                        ACTIVE DEMO FARM
                      </span>
                    </div>
                    <div className="space-y-1 text-xs text-on-surface-variant">
                      <div><span className="font-semibold text-on-surface">District:</span> {farm.district}</div>
                      <div><span className="font-semibold text-on-surface">Livestock:</span> {farm.livestockTypes?.join(', ') || 'N/A'}</div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          {/* Module 2: Surveillance Records */}
          <section aria-labelledby="surveillance-records-live-heading" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 id="surveillance-records-live-heading" className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">
                  clinical_notes
                </span>
                <span>Surveillance Records</span>
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
                <p className="text-xs text-on-surface-variant">Loading synthetic surveillance records...</p>
              </div>
            )}

            {surveillanceRecords?.status === OPERATIONAL_STATUS.EMPTY && (
              <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-xs text-on-surface-variant">
                No synthetic surveillance records found.
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
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-outline-variant/20 pb-2">
                      <span className="px-2.5 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-bold">
                        {rec.diseaseCode}
                      </span>
                      <span className={`px-2.5 py-0.5 rounded-md text-xs font-semibold border ${
                        rec.verificationStatus === 'LAB_CONFIRMED'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                          : rec.verificationStatus === 'AI_SCREENED'
                          ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                          : 'bg-surface-container-high text-on-surface-variant border-outline-variant/40'
                      }`}>
                        {rec.verificationStatus === 'AI_SCREENED' ? 'AI SCREENED (UNCONFIRMED)' : rec.verificationStatus}
                      </span>
                    </div>

                    <div className="space-y-1 text-xs text-on-surface-variant">
                      <p className="text-on-surface font-medium">{rec.summary}</p>
                      <div><span className="font-semibold text-on-surface">Evidence:</span> {rec.evidenceType}</div>
                      <div><span className="font-semibold text-on-surface">Source Module:</span> {rec.sourceModule}</div>
                      <div><span className="font-semibold text-on-surface">Observed At:</span> {new Date(rec.observedAt).toLocaleString()}</div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          {/* Module 3: Active Alerts */}
          <section aria-labelledby="active-alerts-live-heading" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 id="active-alerts-live-heading" className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
                <span className="material-symbols-outlined text-amber-400 text-xl" aria-hidden="true">
                  notifications_active
                </span>
                <span>Authorized Alerts</span>
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
                <p className="text-xs text-on-surface-variant">Loading authorized alerts...</p>
              </div>
            )}

            {alerts?.status === OPERATIONAL_STATUS.EMPTY && (
              <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-xs text-on-surface-variant">
                No synthetic alerts found.
              </div>
            )}

            {alerts?.status === OPERATIONAL_STATUS.ERROR && (
              <div role="alert" aria-live="polite" className="p-6 rounded-2xl bg-surface-container border border-error/30 space-y-3">
                <p className="text-xs text-error font-medium">{alerts.error || 'Failed to load alerts.'}</p>
                <button type="button" onClick={() => alerts.reload()} className="min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high border border-outline-variant text-xs font-semibold text-on-surface">Try again</button>
              </div>
            )}

            {alerts?.status === OPERATIONAL_STATUS.SUCCESS && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {alerts.items.map((alert) => (
                  <article key={alert.alertId} className={`p-5 rounded-2xl bg-surface-container border shadow-md space-y-3 ${alert.status === 'CLOSED' ? 'border-outline-variant/30 opacity-75' : 'border-amber-500/40'}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-outline-variant/20 pb-2">
                      <span className="px-2.5 py-0.5 rounded-md bg-amber-500/20 text-amber-300 text-xs font-bold">
                        {alert.diseaseCode}
                      </span>
                      <span className={`px-2.5 py-0.5 rounded-md text-xs font-bold border ${
                        alert.status === 'OPEN'
                          ? 'bg-error-container/20 text-error border-error/30'
                          : alert.status === 'ACKNOWLEDGED'
                          ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                          : 'bg-surface-container-high text-on-surface-variant border-outline-variant/40'
                      }`}>
                        STATUS: {alert.status}
                      </span>
                    </div>

                    <div className="space-y-1 text-xs text-on-surface-variant">
                      <h3 className="text-sm font-bold text-on-surface">{alert.title}</h3>
                      <p>{alert.message}</p>
                      <div><span className="font-semibold text-on-surface">District:</span> {alert.district}</div>
                      <div><span className="font-semibold text-on-surface">Priority:</span> {alert.priority}</div>
                      <div><span className="font-semibold text-on-surface">Issued:</span> {new Date(alert.issuedAt).toLocaleString()}</div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          {/* Module 4: Response Tasks (Read-Only) */}
          <section aria-labelledby="response-tasks-live-heading" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 id="response-tasks-live-heading" className="text-xl font-bold text-on-surface tracking-tight flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">
                  assignment_turned_in
                </span>
                <span>Response Tasks (Read-Only Demonstration)</span>
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
                <p className="text-xs text-on-surface-variant">Loading synthetic response tasks...</p>
              </div>
            )}

            {responseTasks?.status === OPERATIONAL_STATUS.EMPTY && (
              <div className="p-6 rounded-2xl bg-surface-container border border-outline-variant/30 text-xs text-on-surface-variant">
                No synthetic response tasks assigned.
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
                      <h3 className="text-sm font-bold text-on-surface">{task.taskType}</h3>
                      <span className="px-2 py-0.5 rounded-md bg-surface-container-high text-on-surface-variant text-[11px] font-semibold uppercase">
                        {task.status}
                      </span>
                    </div>

                    <div className="space-y-1 text-xs text-on-surface-variant">
                      <p>{task.notes}</p>
                      <div><span className="font-semibold text-on-surface">District:</span> {task.district}</div>
                      <div><span className="font-semibold text-on-surface">Due Date:</span> {new Date(task.dueAt).toLocaleString()}</div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {/* General Surveillance Responsibilities */}
      <section aria-labelledby="general-responsibilities-heading" className="space-y-4">
        <div className="space-y-1">
          <h2 id="general-responsibilities-heading" className="text-xl font-bold text-on-surface tracking-tight">
            General surveillance responsibilities
          </h2>
          <p className="text-xs text-on-surface-variant">
            Standard operating guidelines for district veterinary surveillance officers. These static reference procedures are not active tasks assigned to the viewer.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {SURVEILLANCE_RESPONSIBILITIES.map((item, idx) => (
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
          District Veterinary Decision Support — Department of Animal Production &amp; Health (DAPH), Sri Lanka.
        </p>
      </footer>
    </div>
  );
}

VeterinarySurveillanceDashboard.propTypes = {
  viewerContext: PropTypes.object,
  operationalData: PropTypes.object,
};
