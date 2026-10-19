import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ImageEvidenceStatus from './ImageEvidenceStatus';

const assessment = {
  grade: 'Moderate', coverage_pct: 20, policy_version: 'crop_visual_burden_v1',
  thresholds_pct: { moderate_min_pct: 10, severe_min_pct: 30 },
  evidence: { yolo_confidence: .9, vit_confidence_pct: 85, top2_margin_pct: 60 },
  rationale: 'Demonstration cutoffs requiring veterinary validation.',
  review_reasons: ['visual_thresholds_unvalidated'],
};

describe('Visual severity evidence', () => {
  it('displays the returned grade, thresholds, measurement and validation status', () => {
    render(<ImageEvidenceStatus result={{ severity: { visual_assessment: assessment } }} />);
    expect(screen.getByTestId('visual-severity-grade')).toHaveTextContent('Moderate visual burden');
    expect(screen.getByText(/20% predicted lesion coverage/)).toBeInTheDocument();
    expect(screen.getByText(/Moderate: 10% to below 30%/)).toBeInTheDocument();
    expect(screen.getByText(/Detector confidence: 90.0%/)).toBeInTheDocument();
    expect(screen.getByText(/Unvalidated thresholds/)).toBeInTheDocument();
    expect(screen.queryByText(/Veterinary review required/)).not.toBeInTheDocument();
  });

  it('keeps an unassessable result when measurements are unavailable', () => {
    render(<ImageEvidenceStatus result={{ severity: { visual_assessment: { ...assessment,
      grade: 'Unassessable', coverage_pct: null } } }} />);
    expect(screen.getByTestId('visual-severity-grade')).toHaveTextContent('Unassessable');
    expect(screen.getByText('Coverage unavailable')).toBeInTheDocument();
  });

  it('shows visual burden independently of an unassessable clinical checklist', () => {
    render(<ImageEvidenceStatus result={{ disease: { name: 'Mastitis' },
      severity: { source: 'clinical_rules', grade: 'Unassessable', visual_assessment: assessment } }} />);
    expect(screen.getByTestId('visual-severity-grade')).toHaveTextContent('Moderate visual burden');
  });
});
