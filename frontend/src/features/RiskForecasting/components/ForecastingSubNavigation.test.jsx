import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ForecastingSubNavigation } from './ForecastingSubNavigation';

describe('ForecastingSubNavigation Component', () => {
  const mockItems = [
    { id: 'disease-risk', label: 'Disease Risk', icon: 'health_and_safety' },
    { id: 'alerts-guidance', label: 'Alerts & Guidance', icon: 'notifications_active' },
  ];

  it('renders nothing when items array is empty or undefined', () => {
    const { container } = render(<ForecastingSubNavigation items={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders semantic nav with custom or default aria-label', () => {
    render(<ForecastingSubNavigation items={mockItems} activeItem="disease-risk" />);
    const nav = screen.getByRole('navigation', { name: 'Risk Forecasting sub-navigation' });
    expect(nav).toBeInTheDocument();
  });

  it('renders all supplied items as buttons with type="button"', () => {
    render(<ForecastingSubNavigation items={mockItems} activeItem="disease-risk" />);
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(2);
    buttons.forEach((btn) => {
      expect(btn).toHaveAttribute('type', 'button');
    });
  });

  it('marks active item with aria-current="page"', () => {
    render(<ForecastingSubNavigation items={mockItems} activeItem="disease-risk" />);
    const activeBtn = screen.getByRole('button', { name: /disease risk/i });
    const inactiveBtn = screen.getByRole('button', { name: /alerts & guidance/i });

    expect(activeBtn).toHaveAttribute('aria-current', 'page');
    expect(inactiveBtn).not.toHaveAttribute('aria-current');
  });

  it('triggers onSelect callback with item ID on click', () => {
    const onSelect = vi.fn();
    render(<ForecastingSubNavigation items={mockItems} activeItem="disease-risk" onSelect={onSelect} />);

    const inactiveBtn = screen.getByRole('button', { name: /alerts & guidance/i });
    fireEvent.click(inactiveBtn);

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith('alerts-guidance');
  });

  it('hides Material Symbols icons from screen readers using aria-hidden="true"', () => {
    render(<ForecastingSubNavigation items={mockItems} activeItem="disease-risk" />);
    const icon = screen.getByText('health_and_safety');
    expect(icon).toHaveAttribute('aria-hidden', 'true');
  });

  it('provides a min-h-[44px] touch target on all navigation buttons', () => {
    render(<ForecastingSubNavigation items={mockItems} activeItem="disease-risk" />);
    const buttons = screen.getAllByRole('button');
    buttons.forEach((btn) => {
      expect(btn.className).toContain('min-h-[44px]');
    });
  });

  it('includes focus ring styling contract on all navigation buttons', () => {
    render(<ForecastingSubNavigation items={mockItems} activeItem="disease-risk" />);
    const buttons = screen.getAllByRole('button');
    buttons.forEach((btn) => {
      expect(btn.className).toMatch(/focus:ring-2|focus-visible:ring-2/);
    });
  });

  it('retains mobile horizontal scroll overflow container with reduced-motion fallback class', () => {
    const { container } = render(<ForecastingSubNavigation items={mockItems} activeItem="disease-risk" />);
    const scrollContainer = container.querySelector('.overflow-x-auto');
    expect(scrollContainer).not.toBeNull();
    expect(scrollContainer.className).toContain('scroll-smooth');
    expect(scrollContainer.className).toContain('motion-reduce:scroll-auto');
  });
});
