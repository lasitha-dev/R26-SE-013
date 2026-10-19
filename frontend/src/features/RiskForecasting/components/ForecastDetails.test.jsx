import React from 'react';
import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { ForecastDetails } from './ForecastDetails';
import { RiskReasonBulb } from './GuideCards';

const high = {
  forecast_id: 'f1', disease: 'FMD', district: 'Colombo', target_year: 2026, target_month: 10, risk_level: 'HIGH',
  probability: 0.295, baseline_probability: 0.031, relative_risk: 9.6, model_version: 'fmd_v2.0', forecaster: 'O',
  deployment_status: 'back_tested', model_variant: 'fmd_v2.0:O', data_quality: 'V2_MODEL', status: 'GENERATED',
  probability_low: 0.24, probability_high: 0.36, interval_level: 0.8,
};

describe('Risk reason bulb', () => {
  it('opens one card with the plain reason first and the working out after it', () => {
    render(<RiskReasonBulb record={high} district="Colombo" />);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    fireEvent.mouseEnter(screen.getByLabelText('Why is the risk this level?'));
    const card = screen.getByRole('tooltip');
    expect(card).toHaveTextContent('Why the risk is HIGH');
    expect(card).toHaveTextContent('The chance of an outbreak in October (29.5%) is 9.6 times higher than usual for Colombo in October (3.1%).');
    expect(card).toHaveTextContent('Based on past records only. It has not been confirmed on future cases yet.');
    expect(card).toHaveTextContent('How it was worked out');
    expect(card).toHaveTextContent('In past years, the chance of an outbreak in Colombo in October was 3.1%.');
    expect(card).toHaveTextContent('29.5% \u00f7 3.1% = 9.6 times the usual chance.');
    expect(card).toHaveTextContent('This forecast is HIGH.');
    const rule = within(card).getByText('The rule').closest('li');
    const points = within(rule).getAllByRole('listitem');
    expect(points.map((li) => li.textContent)).toEqual([
      'USUAL LEVEL \u2014 under 2\u00d7 the usual chance',
      'MEDIUM \u2014 2\u00d7 to 4\u00d7 the usual chance',
      'HIGH \u2014 4\u00d7 or more, or a 50% chance or more',
    ]);
  });

  it('shows no bulb for a usual-level (baseline) record', () => {
    const baseline = { ...high, risk_level: 'LOW', forecaster: 'climatology', deployment_status: 'baseline', relative_risk: 1.0, probability: 0.033 };
    const { container } = render(<RiskReasonBulb record={baseline} district="Colombo" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('explains a HIGH that comes from a 50% chance, not from the multiple', () => {
    render(<RiskReasonBulb record={{ ...high, probability: 0.55, relative_risk: 2.1 }} district="Colombo" />);
    fireEvent.mouseEnter(screen.getByLabelText('Why is the risk this level?'));
    expect(screen.getByRole('tooltip')).toHaveTextContent('which is a 1 in 2 chance or more');
  });
});

describe('More details', () => {
  it('no longer carries a "why the risk" box, and shows no empty box for any record', () => {
    render(<ForecastDetails record={high} district="Colombo" chance="29.5%" />);
    expect(screen.queryByTestId('risk-reason')).not.toBeInTheDocument();
    expect(screen.queryByText('Why the risk is HIGH')).not.toBeInTheDocument();
    expect(screen.getByText('Chance this month')).toBeInTheDocument();
  });
});
