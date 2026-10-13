import React from 'react';
import { DemoForecastingAuthProvider } from './context/DemoForecastingAuthContext.jsx';
import { DemoForecastingGateway } from './components/demo/DemoForecastingGateway.jsx';

/**
 * RiskForecastingDemoEntry Component
 * Unwired standalone entrypoint for the Disease Forecasting Demonstration Experience.
 * Wraps the Isolated Gateway with DemoForecastingAuthProvider and theme container.
 *
 * Rules:
 * - Accepts NO caller-supplied role, permissions, districts, farm IDs, token, or ViewerContext.
 * - Obtains all authorization state exclusively through trusted backend /me token validation.
 * - Enforces full-height dark surface theme wrapper.
 */
export function RiskForecastingDemoEntry() {
  return (
    <div className="min-h-screen bg-surface font-body text-on-surface selection:bg-primary selection:text-on-primary p-4 sm:p-6 lg:p-8">
      <DemoForecastingAuthProvider>
        <DemoForecastingGateway />
      </DemoForecastingAuthProvider>
    </div>
  );
}
