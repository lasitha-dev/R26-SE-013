import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeverityEstimate } from './SeverityEstimate';
import { describeSeverityEstimate } from './forecastPresentation';

const entry = {
  outbreak_years: 6, counts: { LOW: 4, MEDIUM: 2, HIGH: 0 }, years: [2017, 2024],
  probabilities: { LOW: 0.6, MEDIUM: 0.33, HIGH: 0.07 }, typical: 'LOW',
};

describe('SeverityEstimate', () => {
  it('shows the usual level, the three shares and where it comes from', () => {
    render(<SeverityEstimate entry={entry} />);
    expect(screen.getByText('Severity if an outbreak occurs')).toBeInTheDocument();
    expect(screen.getByText('LOW')).toBeInTheDocument();
    expect(screen.getByText('Low 60% · Medium 33% · High 7%')).toBeInTheDocument();
    expect(screen.getByText('Based on 6 past outbreak years (2017–2024).')).toBeInTheDocument();
  });

  it('shows nothing (not LOW) for a district with no recorded outbreak year', () => {
    const { container } = render(<SeverityEstimate entry={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('compact form is one word with the shares in its tooltip, and a dash when unknown', () => {
    const { rerender } = render(<SeverityEstimate entry={entry} compact />);
    const badge = screen.getByTestId('severity-estimate-compact');
    expect(badge).toHaveTextContent('LOW');
    expect(badge.getAttribute('title')).toContain('MEDIUM 33%');
    rerender(<SeverityEstimate entry={null} compact />);
    expect(screen.queryByTestId('severity-estimate-compact')).not.toBeInTheDocument();
  });

  it('uses the singular for one outbreak year and rejects an unknown class', () => {
    expect(describeSeverityEstimate({ ...entry, outbreak_years: 1 }).evidence).toContain('1 past outbreak year (');
    expect(describeSeverityEstimate({ ...entry, typical: 'NONE' })).toBeNull();
  });
});
