import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OutlookCard, describeOutlookEvidence, OUTLOOK_NOTE, OUTLOOK_NOTE_SI } from './OutlookCard';

const outlook = {
  disease: 'FMD', district: 'Colombo', target_month: 11, probability: 0.0326, probability_low: 0.0, probability_high: 0.0967,
  interval_level: 0.8, years_observed: 7, positive_years: 0, issue_date: '2026-10-15', lead_days: 17,
};

describe('OutlookCard', () => {
  it('says the chance, the likely range and how often it happened, in ordinary words and never a risk tier', () => {
    render(<OutlookCard outlook={outlook} title="Foot-and-Mouth Disease (FMD)" />);
    expect(screen.getByText('Foot-and-Mouth Disease (FMD)')).toBeInTheDocument();
    expect(screen.getByText('about 3%')).toBeInTheDocument();
    expect(screen.getByText('likely between 0% and 10%')).toBeInTheDocument();
    expect(screen.getByText('An outbreak was recorded in this month in 0 of the last 7 years.')).toBeInTheDocument();
    expect(screen.queryByText(/LOW|MEDIUM|HIGH|RISK|%\s*range/)).not.toBeInTheDocument();
    expect(screen.queryByText('Preview')).not.toBeInTheDocument();
  });

  it('labels a computed (not yet issued) outlook as a preview', () => {
    render(<OutlookCard outlook={outlook} preview />);
    expect(screen.getByText('Preview')).toBeInTheDocument();
  });

  it('has a one-line compact form and renders nothing without an outlook', () => {
    const { container, rerender } = render(<OutlookCard outlook={outlook} compact />);
    expect(screen.getByTestId('outlook-compact')).toHaveTextContent('Outlook given earlier: about 3% (likely between 0% and 10%)');
    rerender(<OutlookCard outlook={null} />);
    expect(container).toBeEmptyDOMElement();
    expect(describeOutlookEvidence({})).toBeNull();
  });

  it('keeps the short explanatory notes in English and Sinhala', () => {
    expect(OUTLOOK_NOTE).toMatch(/Based on past years only/);
    expect(OUTLOOK_NOTE_SI).toMatch(/අතීත/);
  });

  it('shows the usual severity of the district under the outlook when history exists, and nothing otherwise', () => {
    const entry = { outbreak_years: 4, years: [2017, 2024], typical: 'MEDIUM', probabilities: { LOW: 0.3, MEDIUM: 0.45, HIGH: 0.25 } };
    const { rerender } = render(<OutlookCard outlook={outlook} severityEntry={entry} />);
    expect(screen.getByText('Severity if an outbreak occurs')).toBeInTheDocument();
    expect(screen.getByText('MEDIUM')).toBeInTheDocument();
    rerender(<OutlookCard outlook={outlook} />);
    expect(screen.queryByText('Severity if an outbreak occurs')).not.toBeInTheDocument();
  });
});
