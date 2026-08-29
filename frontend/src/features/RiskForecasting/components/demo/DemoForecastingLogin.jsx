import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useDemoForecastingAuth } from '../../hooks/useDemoForecastingAuth.js';
import { AUTH_STATUS } from '../../context/DemoForecastingAuthContext.jsx';

export const APPROVED_DEMO_ACCOUNTS = Object.freeze([
  { loginName: 'demo_farmer_jaffna', label: 'demo_farmer_jaffna — Farmer demonstration' },
  { loginName: 'demo_vet_north', label: 'demo_vet_north — Veterinary Officer demonstration' },
  { loginName: 'demo_daph_official', label: 'demo_daph_official — DAPH Official demonstration' },
]);

/**
 * DemoForecastingLogin Component
 * Responsive login form card for Disease Forecasting Demo Mode.
 * Enforces strict credential entry without password prefilling or role/district tampering.
 */
export function DemoForecastingLogin() {
  const { login, status, error } = useDemoForecastingAuth();
  const [loginName, setLoginName] = useState('demo_farmer_jaffna');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isPending = status === AUTH_STATUS.CHECKING || isSubmitting;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isPending) return;

    setIsSubmitting(true);
    try {
      await login(loginName.trim(), password);
    } catch (_) {
      // Clear password on failed login
      setPassword('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAccountSelect = (e) => {
    setLoginName(e.target.value);
    setPassword('');
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center p-4 sm:p-6 lg:p-8">
      <div className="w-full max-w-md rounded-2xl bg-surface-container border border-outline-variant/40 shadow-2xl p-6 sm:p-8 space-y-6 text-on-surface">

        {/* Header */}
        <div className="space-y-2 text-center">
          <div className="inline-flex p-3 rounded-2xl bg-primary/10 border border-primary/20 text-primary mb-2">
            <span className="material-symbols-outlined text-3xl" aria-hidden="true">
              lock
            </span>
          </div>
          <h1 className="text-2xl font-bold text-on-surface tracking-tight">
            Disease Forecasting Demonstration
          </h1>
          <p className="text-xs text-on-surface-variant leading-relaxed">
            Isolated synthetic demonstration environment for risk prediction, surveillance alerts, and decision support.
          </p>
        </div>

        {/* Synthetic Data Caution Banner */}
        <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs space-y-1">
          <div className="flex items-center gap-2 font-semibold text-amber-200">
            <span className="material-symbols-outlined text-base" aria-hidden="true">
              warning
            </span>
            <span>Synthetic Demonstration Data</span>
          </div>
          <p className="text-[11px] text-amber-300/90 leading-tight">
            Notice: All data in this environment is synthetic. Synthetic records must not be used for ML model training, calibration, or scientific research conclusions.
          </p>
        </div>

        {/* Auth Error Alert */}
        {error && (
          <div
            role="alert"
            aria-live="polite"
            className="p-3.5 rounded-xl bg-error/10 border border-error/30 text-error text-xs flex items-start gap-2.5"
          >
            <span className="material-symbols-outlined text-base shrink-0 mt-0.5" aria-hidden="true">
              error
            </span>
            <div className="space-y-0.5">
              <span className="font-semibold block">Authentication Failure</span>
              <span className="text-error/90">{error}</span>
            </div>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">

          {/* Approved Demo Account Dropdown */}
          <div className="space-y-1.5">
            <label htmlFor="demo-account-select" className="block text-xs font-medium text-on-surface-variant">
              Select Demo Account
            </label>
            <select
              id="demo-account-select"
              value={loginName}
              onChange={handleAccountSelect}
              disabled={isPending}
              className="w-full min-h-[44px] px-3.5 py-2 rounded-xl bg-surface-container-high border border-outline-variant/50 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 transition-colors"
            >
              {APPROVED_DEMO_ACCOUNTS.map((acc) => (
                <option key={acc.loginName} value={acc.loginName}>
                  {acc.label}
                </option>
              ))}
            </select>
          </div>

          {/* Login Name Control */}
          <div className="space-y-1.5">
            <label htmlFor="demo-login-name" className="block text-xs font-medium text-on-surface-variant">
              Login Name
            </label>
            <input
              id="demo-login-name"
              type="text"
              name="username"
              value={loginName}
              onChange={(e) => setLoginName(e.target.value)}
              autoComplete="username"
              required
              disabled={isPending}
              placeholder="e.g. demo_farmer_jaffna"
              className="w-full min-h-[44px] px-3.5 py-2 rounded-xl bg-surface-container-high border border-outline-variant/50 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 transition-colors"
            />
          </div>

          {/* Password Control */}
          <div className="space-y-1.5">
            <label htmlFor="demo-password" className="block text-xs font-medium text-on-surface-variant">
              Password
            </label>
            <input
              id="demo-password"
              type="password"
              name="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              disabled={isPending}
              placeholder="Enter configured demo password"
              className="w-full min-h-[44px] px-3.5 py-2 rounded-xl bg-surface-container-high border border-outline-variant/50 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 transition-colors"
            />
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isPending || password.trim() === ''}
            className="w-full min-h-[44px] mt-2 px-4 py-2.5 rounded-xl bg-primary text-on-primary font-semibold text-sm shadow-md hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-surface disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center gap-2"
          >
            {isPending ? (
              <>
                <span className="material-symbols-outlined text-lg animate-spin" aria-hidden="true">
                  progress_activity
                </span>
                <span>Signing in...</span>
              </>
            ) : (
              <>
                <span>Sign in to demo</span>
                <span className="material-symbols-outlined text-lg" aria-hidden="true">
                  arrow_forward
                </span>
              </>
            )}
          </button>

        </form>

        <div className="pt-2 text-center text-[11px] text-on-surface-variant/80 border-t border-outline-variant/30">
          Roles, scope levels, and districts are securely assigned by backend token context.
        </div>

      </div>
    </div>
  );
}

DemoForecastingLogin.propTypes = {};
