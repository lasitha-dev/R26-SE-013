import React from 'react';
import RiskForecasting from './features/RiskForecasting/index';
import { RiskForecastingDemoEntry } from './features/RiskForecasting/RiskForecastingDemoEntry';

export function isDemoPath(pathname) {
  const currentPath = pathname || (typeof window !== 'undefined' ? window.location.pathname : '/');
  return currentPath === '/risk-forecasting-demo' || currentPath.startsWith('/risk-forecasting-demo');
}

export function isDemoEnabled(envVal) {
  const flag = envVal !== undefined ? envVal : import.meta.env?.VITE_FORECASTING_DEMO_ENABLED;
  return flag === 'true';
}

export default function App() {
  const currentPath = typeof window !== 'undefined' ? window.location.pathname : '/';

  if (isDemoPath(currentPath)) {
    if (isDemoEnabled()) {
      return <RiskForecastingDemoEntry />;
    }
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

  return <RiskForecasting />;
}
