import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AccessContextUnavailable } from './AccessContextUnavailable';

describe('AccessContextUnavailable Component', () => {
  it('renders default title and message in accessible alert region', () => {
    render(<AccessContextUnavailable />);
    const alertBox = screen.getByRole('alert');
    expect(alertBox).toBeInTheDocument();

    expect(screen.getByText('Access context unavailable')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Your forecasting access scope could not be verified. Please sign in again or contact the system administrator.'
      )
    ).toBeInTheDocument();
  });

  it('renders custom safe reason string when supplied', () => {
    render(<AccessContextUnavailable reason="Incompatible scopeLevel 'DISTRICT' for role 'FARMER'" />);
    expect(
      screen.getByText("Reason: Incompatible scopeLevel 'DISTRICT' for role 'FARMER'")
    ).toBeInTheDocument();
  });

  it('does not render district selectors, role selectors, or fallback action triggers', () => {
    render(<AccessContextUnavailable />);
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.queryByRole('select')).not.toBeInTheDocument();
  });

  it('does not render AI Diagnosis CTAs', () => {
    render(<AccessContextUnavailable />);
    expect(screen.queryByText(/AI Diagnosis/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Report Symptoms/i)).not.toBeInTheDocument();
  });

  it('renders as a visible card container and is not hidden with sr-only', () => {
    const { container } = render(<AccessContextUnavailable />);
    const alertElement = screen.getByRole('alert');
    expect(alertElement.className).not.toContain('sr-only');
    expect(container.querySelector('.max-w-2xl')).not.toBeNull();
  });

  it('renders default title as a level 1 heading (h1) by default', () => {
    render(<AccessContextUnavailable />);
    const heading = screen.getByRole('heading', { level: 1, name: 'Access context unavailable' });
    expect(heading).toBeInTheDocument();
  });

  it('renders custom title as a level 1 heading (h1) by default', () => {
    render(<AccessContextUnavailable title="Custom Access Error" />);
    const heading = screen.getByRole('heading', { level: 1, name: 'Custom Access Error' });
    expect(heading).toBeInTheDocument();
  });

  it('renders explicit supported h2 or h3 heading level when passed', () => {
    const { rerender } = render(<AccessContextUnavailable headingLevel="h2" title="Section Error" />);
    expect(screen.getByRole('heading', { level: 2, name: 'Section Error' })).toBeInTheDocument();

    rerender(<AccessContextUnavailable headingLevel="h3" title="Sub-section Error" />);
    expect(screen.getByRole('heading', { level: 3, name: 'Sub-section Error' })).toBeInTheDocument();
  });

  it('safely falls back to h1 when an invalid headingLevel is supplied', () => {
    render(<AccessContextUnavailable headingLevel="script" title="Fallback Test" />);
    const heading = screen.getByRole('heading', { level: 1, name: 'Fallback Test' });
    expect(heading).toBeInTheDocument();
  });

  it('preserves role="alert" and aria-live="polite" semantics', () => {
    render(<AccessContextUnavailable />);
    const alertBox = screen.getByRole('alert');
    expect(alertBox).toHaveAttribute('aria-live', 'polite');
  });

  it('applies mobile margin mx-4 and desktop centering sm:mx-auto for responsive layout', () => {
    render(<AccessContextUnavailable />);
    const alertElement = screen.getByRole('alert');
    expect(alertElement.className).toContain('mx-4');
    expect(alertElement.className).toContain('sm:mx-auto');
    expect(alertElement.className).toContain('max-w-2xl');
  });

  it('does not expose fake retry, support phone numbers, or role switching controls', () => {
    render(<AccessContextUnavailable />);
    expect(screen.queryByText(/retry/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/change role/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/call support/i)).not.toBeInTheDocument();
  });
});
