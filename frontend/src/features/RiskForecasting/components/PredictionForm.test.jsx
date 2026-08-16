import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PredictionForm from './PredictionForm';

describe('PredictionForm Component', () => {
  const defaultProps = {
    districts: ['Anuradhapura', 'Jaffna', 'Batticaloa'],
    selectedDisease: 'FMD',
    onSelectDisease: vi.fn(),
    selectedDistrict: 'Anuradhapura',
    onSelectDistrict: vi.fn(),
    selectedYear: 2024,
    onSelectYear: vi.fn(),
    selectedMonth: 1,
    onSelectMonth: vi.fn(),
    use31Features: false,
    onToggle31Features: vi.fn(),
    onSubmit: vi.fn(),
    onOpenDashboard: vi.fn(),
    isLoading: false,
  };

  it('renders form container, disease toggles, inputs, and submit button', () => {
    render(<PredictionForm {...defaultProps} />);

    expect(screen.getByTestId('prediction-form-container')).toBeInTheDocument();
    expect(screen.getByTestId('disease-toggle-fmd')).toBeInTheDocument();
    expect(screen.getByTestId('disease-toggle-lsd')).toBeInTheDocument();
    expect(screen.getByTestId('district-select')).toBeInTheDocument();
    expect(screen.getByTestId('year-input')).toBeInTheDocument();
    expect(screen.getByTestId('month-select')).toBeInTheDocument();
    expect(screen.getByTestId('submit-forecast-btn')).toBeInTheDocument();
  });

  it('calls onSelectDisease when LSD toggle is clicked', () => {
    render(<PredictionForm {...defaultProps} />);
    fireEvent.click(screen.getByTestId('disease-toggle-lsd'));
    expect(defaultProps.onSelectDisease).toHaveBeenCalledWith('LSD');
  });

  it('calls onSubmit when form submit button is clicked', () => {
    render(<PredictionForm {...defaultProps} />);
    fireEvent.click(screen.getByTestId('submit-forecast-btn'));
    expect(defaultProps.onSubmit).toHaveBeenCalled();
  });

  it('renders FMD variant toggle when FMD is selected', () => {
    render(<PredictionForm {...defaultProps} selectedDisease="FMD" />);
    expect(screen.getByTestId('fmd-variant-toggle')).toBeInTheDocument();
  });
});
