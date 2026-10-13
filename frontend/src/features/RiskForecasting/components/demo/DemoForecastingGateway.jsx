import React from 'react';
import { useDemoForecastingAuth } from '../../hooks/useDemoForecastingAuth.js';
import { AUTH_STATUS } from '../../context/DemoForecastingAuthContext.jsx';
import { DemoForecastingLogin } from './DemoForecastingLogin.jsx';
import { RiskForecastingFeature } from '../../RiskForecastingFeature.jsx';
import { DemoForecastingOperationalBridge } from './DemoForecastingOperationalBridge.jsx';
import { validateViewerContext, ROLES } from '../../contracts/viewerContext.js';

/**
 * Maps canonical backend system role to human-readable demo display label.
 * @param {string} role
 * @param {Object} authorization
 * @returns {string}
 */
export function getHumanReadableRoleLabel(role, authorization = {}) {
  switch (role) {
    case ROLES.FARMER:
      return `Farmer Demonstration (${authorization?.registeredFarmDistrict || 'Jaffna'})`;
    case ROLES.VETERINARY_OFFICER:
      return `Veterinary Officer Demonstration (${authorization?.scopeLevel || 'PROVINCE'} Scope)`;
    case ROLES.DAPH_OFFICIAL:
      return `DAPH Official Demonstration (${authorization?.scopeLevel || 'NATIONAL'} Scope)`;
    default:
      return 'Authenticated Demo User';
  }
}

/**
 * DemoForecastingGateway Component
 * Isolated entry gateway that gates access to RiskForecastingFeature based on trusted ViewerContext.
 */
export function DemoForecastingGateway() {
  const { demoEnabled, status, viewerContext, error, logout } = useDemoForecastingAuth();

  // 1. Status: Disabled
  if (!demoEnabled || status === AUTH_STATUS.DISABLED) {
    return (
      <div className="max-w-2xl mx-4 sm:mx-auto my-12 p-8 rounded-2xl bg-surface-container border border-outline-variant/40 shadow-xl text-on-surface text-center space-y-4">
        <div className="inline-flex p-3 rounded-2xl bg-surface-container-high text-on-surface-variant">
          <span className="material-symbols-outlined text-3xl" aria-hidden="true">
            block
          </span>
        </div>
        <h1 className="text-xl font-bold text-on-surface">Disease Forecasting Demo Disabled</h1>
        <p className="text-sm text-on-surface-variant leading-relaxed">
          The disease forecasting demonstration mode is currently disabled in this environment. To enable demo mode, configure <code className="px-1.5 py-0.5 rounded bg-surface-container-lowest font-mono text-xs text-primary">VITE_FORECASTING_DEMO_ENABLED=true</code> in your frontend environment settings.
        </p>
      </div>
    );
  }

  // 2. Status: Checking
  if (status === AUTH_STATUS.CHECKING) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="min-h-[50vh] flex flex-col items-center justify-center p-6 space-y-4 text-center"
      >
        <div className="p-3 rounded-2xl bg-primary/10 text-primary border border-primary/20">
          <span className="material-symbols-outlined text-3xl animate-spin" aria-hidden="true">
            progress_activity
          </span>
        </div>
        <div className="space-y-1">
          <span className="text-sm font-semibold text-on-surface block">Verifying demo authentication session...</span>
          <span className="text-xs text-on-surface-variant block">Connecting to trusted authentication context</span>
        </div>
      </div>
    );
  }

  // 3. Status: Unauthenticated
  if (status === AUTH_STATUS.UNAUTHENTICATED) {
    return <DemoForecastingLogin />;
  }

  // 4. Status: Error
  if (status === AUTH_STATUS.ERROR) {
    return (
      <div
        role="alert"
        aria-live="polite"
        className="max-w-xl mx-4 sm:mx-auto my-12 p-6 rounded-2xl bg-surface-container border border-error/30 shadow-xl text-on-surface space-y-4"
      >
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-error-container/20 text-error border border-error/30 shrink-0">
            <span className="material-symbols-outlined text-2xl" aria-hidden="true">
              gpp_maybe
            </span>
          </div>
          <div className="space-y-1.5 flex-1">
            <h2 className="text-base font-semibold text-error">Authentication Service Unavailable</h2>
            <p className="text-xs text-on-surface-variant leading-relaxed">
              {error || 'Demo authentication is currently unavailable.'}
            </p>
          </div>
        </div>
        <div className="pt-2 flex justify-end">
          <button
            type="button"
            onClick={logout}
            className="min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant text-xs font-semibold text-on-surface focus:outline-none focus:ring-2 focus:ring-primary transition-colors"
          >
            Return to login
          </button>
        </div>
      </div>
    );
  }

  // 5. Status: Authenticated
  if (status === AUTH_STATUS.AUTHENTICATED) {
    const validation = validateViewerContext(viewerContext);

    // Fail-closed guard against invalid/null ViewerContext in authenticated state
    if (!validation.valid || !validation.normalizedContext) {
      return (
        <div
          role="alert"
          aria-live="polite"
          className="max-w-xl mx-4 sm:mx-auto my-12 p-6 rounded-2xl bg-surface-container border border-error/30 shadow-xl text-on-surface space-y-4"
        >
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-2xl text-error" aria-hidden="true">
              gpp_bad
            </span>
            <div>
              <h2 className="text-base font-semibold text-error">Session Validation Failure</h2>
              <p className="text-xs text-on-surface-variant">
                The authenticated session context could not be verified. Returning to unauthenticated state.
              </p>
            </div>
          </div>
          <div className="pt-2 flex justify-end">
            <button
              type="button"
              onClick={logout}
              className="min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high border border-outline-variant text-xs font-semibold text-on-surface"
            >
              Clear Session
            </button>
          </div>
        </div>
      );
    }

    const validContext = validation.normalizedContext;
    const humanRole = getHumanReadableRoleLabel(validContext.role, validContext.authorization);

    return (
      <div className="w-full min-w-0 space-y-6">
        {/* Compact Demo Session Header */}
        <header className="w-full p-4 rounded-2xl bg-surface-container border border-outline-variant/40 shadow-lg space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-primary/10 border border-primary/20 text-primary shrink-0">
                <span className="material-symbols-outlined text-2xl" aria-hidden="true">
                  analytics
                </span>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-on-surface tracking-tight">Disease Forecasting Demo</h2>
                  <span className="px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[10px] font-semibold">
                    Synthetic demonstration data
                  </span>
                </div>
                <div className="text-xs text-on-surface-variant font-medium mt-0.5">
                  {humanRole}
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={logout}
              className="min-h-[44px] px-4 py-2 rounded-xl bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant/50 text-xs font-semibold text-on-surface flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-primary transition-colors"
            >
              <span className="material-symbols-outlined text-base" aria-hidden="true">
                logout
              </span>
              <span>Log Out</span>
            </button>
          </div>

          {/* Scientific Use Notice */}
          <div className="p-2.5 rounded-xl bg-amber-500/5 border border-amber-500/20 text-[11px] text-amber-300/90 flex items-center gap-2">
            <span className="material-symbols-outlined text-sm text-amber-400 shrink-0" aria-hidden="true">
              info
            </span>
            <span>
              This standalone demo uses synthetic operational records. Synthetic records are not permitted for model training or scientific analysis.
            </span>
          </div>
        </header>

        {/* Protected Feature Content */}
        <main className="w-full min-w-0">
          <DemoForecastingOperationalBridge viewerContext={validContext} />
        </main>
      </div>
    );
  }

  return null;
}
