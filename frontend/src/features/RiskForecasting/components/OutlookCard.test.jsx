import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OutlookCard, describeOutlookEvidence } from './OutlookCard';

const outlook = {
  disease: 'FMD', district: 'Colombo', probability: 0.0326, probability_low: 0.0, probability_high: 0.0967,
  interval_level: 0.8, years_observed: 7, positive_years: 0, issue_date: '2026-10-15', lead_days: 17,
};

describe('OutlookCard', () => {
  it('shows the outlook with its evidence and disclaimers, and never a risk tier', () => {
    render(<OutlookCard outlook={outlook} />);
    expect(screen.getByText('SEASONAL OUTLOOK')).toBeInTheDocument();
    expect(screen.getByText('3.3%')).toBeInTheDocument();
    expect(screen.getByText('80% range 0–10%')).toBeInTheDocument();
    expect(screen.getByText('Historical evidence: 7 years, 0 with an outbreak in this month.')).toBeInTheDocument();
    expect(screen.getByText(/does not include current surveillance/i)).toBeInTheDocument();
    expect(screen.getByText(/වත්මන් රෝග වාර්තා/)).toBeInTheDocument();
    expect(screen.getByText('Issued 2026-10-15 · 17 days before the month')).toBeInTheDocument();
    expect(screen.queryByText(/LOW|MEDIUM|HIGH/)).not.toBeInTheDocument();
  });

  it('labels a preview as not yet issued', () => {
    render(<OutlookCard outlook={outlook} preview />);
    expect(screen.getByText('PREVIEW · not yet issued')).toBeInTheDocument();
    expect(screen.queryByText(/^Issued /)).not.toBeInTheDocument();
  });

  it('has a one-line compact form and renders nothing without an outlook', () => {
    const { container, rerender } = render(<OutlookCard outlook={outlook} compact />);
    expect(screen.getByTestId('outlook-compact')).toHaveTextContent('Outlook issued earlier: 3.3% (80% range 0–10%)');
    rerender(<OutlookCard outlook={null} />);
    expect(container).toBeEmptyDOMElement();
    expect(describeOutlookEvidence({})).toBeNull();
  });
});
