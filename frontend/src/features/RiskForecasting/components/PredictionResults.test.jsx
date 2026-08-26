import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PredictionResults from './PredictionResults';

describe('PredictionResults Component', () => {
  const mockResult = {
    disease: 'FMD',
    district: 'Anuradhapura',
    year: 2024,
    month: 1,
    month_name: 'January',
    stage1: {
      probability: 0.636,
      probability_pct: 63.6,
      risk_level: 'HIGH',
      decision_threshold: 0.40,
      model_variant: '30_feature_baseline',
    },
    stage2: {
      severity_predicted: 'LOW',
      severity_code: 0,
      model_name: 'RandomForestClassifier',
      evaluated: true,
      discriminator_validated: true,
      action_required: false,
      notes: 'Stage 2 Random Forest severity model explicitly evaluated (predicted LOW).',
    },
    calibration_info: {
      is_calibrated: false,
      calibration_method: 'Uncalibrated Raw Logistic Regression',
      ece_score: null,
      notes: 'FMD uses raw walk-forward probabilities.',
    },
    uncertainty: {
      method: 'Mondrian Conformal Prediction',
      status: 'VALIDATED',
      reliability: 'HIGH',
      prediction_set: ['HIGH'],
      empirical_coverage_pct: 94.9,
      notes: 'Validated coverage exceeding 90%.',
    },
    recommendations: ['TARGETED VACCINATION RESPONSE REQUIRED'],
    provenance: { fallback_applied: false, fallback_message: 'Exact match found.' },
  };

  it('renders risk level, stage 1 prob, stage 2 status, and recommendations', () => {
    render(<PredictionResults result={mockResult} onBack={vi.fn()} />);

    expect(screen.getByTestId('prediction-results-container')).toBeInTheDocument();
    expect(screen.getByTestId('risk-level-badge')).toHaveTextContent('RISK LEVEL: HIGH');
    expect(screen.getByTestId('stage2-evaluated-badge')).toBeInTheDocument();
    expect(screen.getByTestId('severity-predicted-value')).toHaveTextContent('LOW');
  });

  it('toggles raw JSON response visibility when accordion button is clicked', () => {
    render(<PredictionResults result={mockResult} onBack={vi.fn()} />);

    const toggleBtn = screen.getByTestId('toggle-raw-json-btn');
    expect(screen.queryByTestId('raw-json-output')).not.toBeInTheDocument();

    fireEvent.click(toggleBtn);
    expect(screen.getByTestId('raw-json-output')).toBeInTheDocument();
    expect(screen.getByTestId('raw-json-output')).toHaveTextContent('Anuradhapura');
  });
});
