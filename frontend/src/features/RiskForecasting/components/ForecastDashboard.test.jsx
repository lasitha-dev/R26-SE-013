import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ForecastDashboard from './ForecastDashboard';

describe('ForecastDashboard Component', () => {
  const mockForecast = {
    disease: 'FMD',
    target_month: 1,
    target_month_name: 'January',
    model_variant: '30_feature_baseline',
    districts: [
      { district: 'Anuradhapura', probability_pct: 79.5, risk_level: 'HIGH', severity_predicted: 'MOD_HIGH' },
      { district: 'Jaffna', probability_pct: 12.3, risk_level: 'LOW', severity_predicted: 'LOW' },
      { district: 'Batticaloa', probability_pct: 45.0, risk_level: 'MEDIUM', severity_predicted: 'MOD_HIGH' },
    ],
  };

  it('renders forecast table, stat cards, district rows, and model variant badge', () => {
    render(<ForecastDashboard forecastData={mockForecast} onRunForecast={vi.fn()} onBackToForm={vi.fn()} />);

    expect(screen.getByTestId('forecast-dashboard-container')).toBeInTheDocument();
    expect(screen.getByTestId('forecast-table')).toBeInTheDocument();
    expect(screen.getByText('Anuradhapura')).toBeInTheDocument();
    expect(screen.getByText('Jaffna')).toBeInTheDocument();
    expect(screen.getByText('Batticaloa')).toBeInTheDocument();
    expect(screen.getByTestId('forecast-model-variant-badge')).toHaveTextContent('FMD — 30_feature_baseline');
  });

  it('initializes month dropdown value from target_month 9 (September)', () => {
    const septemberForecast = {
      ...mockForecast,
      target_month: 9,
      target_month_name: 'September',
    };

    render(<ForecastDashboard forecastData={septemberForecast} onRunForecast={vi.fn()} onBackToForm={vi.fn()} />);

    const select = screen.getByRole('combobox');
    expect(select.value).toBe('9');
  });

  it('synchronizes month dropdown when target_month prop updates and invokes onRunForecast with synchronized month', () => {
    const onRunForecast = vi.fn();
    const { rerender } = render(
      <ForecastDashboard forecastData={mockForecast} onRunForecast={onRunForecast} onBackToForm={vi.fn()} />
    );

    const select = screen.getByRole('combobox');
    expect(select.value).toBe('1');

    const updatedForecast = {
      ...mockForecast,
      target_month: 9,
      target_month_name: 'September',
    };

    rerender(
      <ForecastDashboard forecastData={updatedForecast} onRunForecast={onRunForecast} onBackToForm={vi.fn()} />
    );

    expect(select.value).toBe('9');

    const runBtn = screen.getByTestId('run-all-forecast-btn');
    fireEvent.click(runBtn);

    expect(onRunForecast).toHaveBeenCalledTimes(1);
    expect(onRunForecast).toHaveBeenCalledWith('FMD', 9);
  });

  it('preserves local user month selection without immediate API calls until Run Forecast is clicked', () => {
    const onRunForecast = vi.fn();
    const septemberForecast = {
      ...mockForecast,
      target_month: 9,
      target_month_name: 'September',
    };

    render(
      <ForecastDashboard forecastData={septemberForecast} onRunForecast={onRunForecast} onBackToForm={vi.fn()} />
    );

    const select = screen.getByRole('combobox');
    expect(select.value).toBe('9');

    // Manually change month selection 9 -> 11 (November)
    fireEvent.change(select, { target: { value: '11' } });

    // Selector remains at 11
    expect(select.value).toBe('11');
    // Changing dropdown alone causes no API / callback invocation
    expect(onRunForecast).not.toHaveBeenCalled();

    // Click Run Forecast
    const runBtn = screen.getByTestId('run-all-forecast-btn');
    fireEvent.click(runBtn);

    expect(onRunForecast).toHaveBeenCalledTimes(1);
    expect(onRunForecast).toHaveBeenCalledWith('FMD', 11);
  });
});
