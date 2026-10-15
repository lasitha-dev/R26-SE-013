import React from 'react';
import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ForecastDetails } from './ForecastDetails';

const high = {
  forecast_id: 'f1', disease: 'FMD', district: 'Colombo', target_year: 2026, target_month: 10, risk_level: 'HIGH',
  probability: 0.295, baseline_probability: 0.031, relative_risk: 9.6, model_version: 'fmd_v2.0', forecaster: 'O',
  deployment_status: 'back_tested', model_variant: 'fmd_v2.0:O', data_quality: 'V2_MODEL', status: 'GENERATED',
  probability_low: 0.24, probability_high: 0.36, interval_level: 0.8,
};

describe('ForecastDetails risk explanation', () => {
  it('says in plain words why the risk is HIGH', () => {
    render(<ForecastDetails record={high} district="Colombo" chance="29.5%" />);
    const box = screen.getByTestId('risk-reason');
    expect(box).toHaveTextContent('Why the risk is HIGH');
    expect(box).toHaveTextContent('The chance of an outbreak in October (29.5%) is 9.6 times higher than usual for Colombo in October (3.1%).');
    expect(box).toHaveTextContent('Based on past records only. It has not been confirmed on future cases yet.');
  });

  it('shows how it was worked out when the light bulb is hovered', () => {
    render(<ForecastDetails record={high} district="Colombo" chance="29.5%" />);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    fireEvent.mouseEnter(screen.getByLabelText('How this risk was worked out'));
    const card = screen.getByRole('tooltip');
    expect(card).toHaveTextContent('How this risk was worked out');
    expect(card).toHaveTextContent('In past years, the chance of an outbreak in Colombo in October was 3.1%.');
    expect(card).toHaveTextContent('29.5% ÷ 3.1% = 9.6 times the usual chance.');
    expect(card).toHaveTextContent('4× or more');
    expect(card).toHaveTextContent('This forecast is HIGH.');
  });

  it('shows no empty box for a usual-level (baseline) record', () => {
    const baseline = { ...high, risk_level: 'LOW', forecaster: 'climatology', deployment_status: 'baseline', relative_risk: 1.0, probability: 0.033 };
    render(<ForecastDetails record={baseline} district="Colombo" chance="3.3%" />);
    expect(screen.queryByTestId('risk-reason')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('How this risk was worked out')).not.toBeInTheDocument();
  });

  it('explains a HIGH that comes from a 50% chance, not from the multiple', () => {
    const byChance = { ...high, probability: 0.55, relative_risk: 2.1 };
    render(<ForecastDetails record={byChance} district="Colombo" chance="55.0%" />);
    expect(screen.getByTestId('risk-reason')).toHaveTextContent('which is a 1 in 2 chance or more');
  });
});
