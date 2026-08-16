import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ForecastDashboard from './ForecastDashboard';

describe('ForecastDashboard Component', () => {
  const mockForecast = {
    disease: 'FMD',
    month: 1,
    year: 2024,
    forecasts: [
      { district: 'Anuradhapura', probability_pct: 79.5, risk_level: 'HIGH', severity_predicted: 'MOD_HIGH' },
      { district: 'Jaffna', probability_pct: 12.3, risk_level: 'LOW', severity_predicted: 'LOW' },
      { district: 'Batticaloa', probability_pct: 45.0, risk_level: 'MEDIUM', severity_predicted: 'MOD_HIGH' },
    ],
  };

  it('renders forecast table, stat cards, and district rows', () => {
    render(<ForecastDashboard forecastData={mockForecast} onRunForecast={vi.fn()} onBackToForm={vi.fn()} />);

    expect(screen.getByTestId('forecast-dashboard-container')).toBeInTheDocument();
    expect(screen.getByTestId('forecast-table')).toBeInTheDocument();
    expect(screen.getByText('Anuradhapura')).toBeInTheDocument();
    expect(screen.getByText('Jaffna')).toBeInTheDocument();
    expect(screen.getByText('Batticaloa')).toBeInTheDocument();
  });
});
