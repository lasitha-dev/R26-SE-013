import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RiskForecastingDemoEntry } from './RiskForecastingDemoEntry.jsx';

describe('RiskForecastingDemoEntry Component Unit Tests', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('renders disabled state when demo mode is disabled in environment', () => {
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'false');

    render(<RiskForecastingDemoEntry />);

    expect(screen.getByText('Disease Forecasting Demo Disabled')).toBeInTheDocument();
  });

  it('renders unauthenticated login view when demo mode is enabled and no token exists', async () => {
    vi.stubEnv('VITE_FORECASTING_DEMO_ENABLED', 'true');

    render(<RiskForecastingDemoEntry />);

    const heading = await screen.findByRole('heading', { level: 1 });
    expect(heading).toHaveTextContent('Disease Forecasting Demonstration');
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });
});
