import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeverityBadge, SeverityPanel } from './SeverityPanel';
import { describeSeverityPanel } from './forecastPresentation';

const history = {
  district: 'Colombo', outbreak_years: 3, counts: { LOW: 1, MEDIUM: 0, HIGH: 2 }, years: [2017, 2024],
  probabilities: { LOW: 0.45, MEDIUM: 0.11, HIGH: 0.44 }, typical: 'HIGH',
};
const september = { label: 'September 2026', observation: { verified_cases: 1, deaths: 2 } };
const october = { label: 'October 2026 so far', observation: { cases: 0, deaths: 0 } };

describe('describeSeverityPanel', () => {
  it('follows the recorded cases and deaths when there are any', () => {
    const panel = describeSeverityPanel({ recent: [october, september], entry: history });
    expect(panel.level).toBe('MEDIUM');           // 1 case + 10 x 2 deaths = 21
    expect(panel.basis).toBe('recorded');
    expect(panel.historyLine).toBe('Past outbreaks in Colombo: usually HIGH');
    expect(panel.items).toHaveLength(2);
  });

  it('falls back to the district\'s past outbreaks when nothing is recorded, and shows nothing when there is neither', () => {
    const fallback = describeSeverityPanel({ recent: [], entry: history });
    expect(fallback.level).toBe('HIGH');
    expect(fallback.basisText).toBe('Based on past outbreaks in Colombo, 2017–2024.');
    expect(fallback.historyCounts).toBe('1 low · 0 medium · 2 high (2017–2024)');
    expect(describeSeverityPanel({ recent: [], entry: null })).toBeNull();
  });

  it('uses the past outbreaks when the recorded months are all empty, and never turns "unknown" into zero', () => {
    expect(describeSeverityPanel({ recent: [october], entry: history }).level).toBe('HIGH');
    const uncovered = describeSeverityPanel({ recent: [{ label: 'October 2026 so far', observation: { cases: null, deaths: null } }], entry: history });
    expect(uncovered.items).toHaveLength(0);
    expect(uncovered.noReports).toBe('No app reports for this district yet.');
  });

  it('moves up with the recorded counts: 3 cases is LOW, 12 cases and 2 deaths is HIGH', () => {
    const level = (cases, deaths) => describeSeverityPanel({ recent: [{ label: 'x', observation: { cases, deaths } }], entry: null }).level;
    expect(level(3, 0)).toBe('LOW');
    expect(level(12, 0)).toBe('MEDIUM');
    expect(level(12, 2)).toBe('HIGH');
  });
});

describe('SeverityPanel', () => {
  it('shows one level, a meter, the recorded months and the past-outbreak line', () => {
    render(<SeverityPanel recent={[october, september]} entry={history} />);
    expect(screen.getByTestId('severity-level')).toHaveTextContent('MEDIUM');
    expect(screen.getByRole('img', { name: 'Severity MEDIUM' })).toBeInTheDocument();
    const chips = screen.getAllByTestId('severity-recorded').map((c) => c.textContent);
    expect(chips.some((t) => /September 2026/.test(t) && /1 case/.test(t) && /2 deaths/.test(t))).toBe(true);
    expect(chips.some((t) => /October 2026 so far/.test(t) && /No cases or deaths/.test(t))).toBe(true);
    expect(screen.getByTestId('severity-history')).toHaveTextContent('Past outbreaks in Colombo: usually HIGH');
  });

  it('explains how the level is decided in a tooltip and keeps the percentages out of the main view', () => {
    render(<SeverityPanel recent={[september]} entry={history} />);
    expect(screen.getByRole('button', { name: 'How is severity decided?' })).toBeInTheDocument();
    const tip = screen.getByRole('tooltip');
    expect(tip).toHaveTextContent('one death counts as much as ten cases');
    expect(tip).toHaveTextContent('not a prediction of future severity');
    expect(tip).toHaveTextContent('1 low · 0 medium · 2 high');
    expect(screen.queryByText(/45%|44%/)).not.toBeInTheDocument();
  });

  it('renders nothing without any information, and the compact badge shows a dash', () => {
    const { container } = render(<SeverityPanel recent={[]} entry={null} />);
    expect(container).toBeEmptyDOMElement();
    render(<SeverityBadge recent={[]} entry={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('the compact badge carries the same level and the basis in its tooltip', () => {
    render(<SeverityBadge recent={[september]} entry={history} />);
    const badge = screen.getByTestId('severity-badge');
    expect(badge).toHaveTextContent('MEDIUM');
    expect(badge.getAttribute('title')).toContain('September 2026');
  });
});
