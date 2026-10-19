import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ReasoningBriefing from './ReasoningBriefing';

const explanation = {
  origin: 'llm_selected', summary: 'Moderate visual burden; clinical severity is not established.',
  supporting_evidence: [{ id: 'coverage', text: 'Predicted coverage: 20% of crop pixels.', evidence_ids: ['segmentation'], reference_ids: [] }],
  reference_context: [{ id: 'fmd_confirmation', text: 'General context: suspected FMD needs laboratory confirmation.', reference_ids: ['woah_fmd'] }],
  limitations: [{ id: 'review', text: 'Missing measurements do not establish health.', reference_ids: [] }],
  next_checks: [{ id: 'fmd_exam', text: 'Discuss examination and confirmatory testing.', reference_ids: ['woah_fmd'] }],
  references: [{ id: 'woah_fmd', title: 'WOAH: Foot and mouth disease', url: 'https://www.woah.org/en/disease/foot-and-mouth-disease/' }],
  reference_pack_version: 'veterinary_explanations_v1', prompt_version: 'evidence_selection_v1',
  evidence_sha256: 'synthetic-evidence-fingerprint', reference_review_status: 'Veterinary review pending.',
};
const assessment = { source: 'visual_thresholds', grade: 'Moderate', formatted: 'Moderate visual burden (provisional)' };

describe('Grounded explanations', () => {
  it('renders the explanation alongside a visual-threshold result instead of hiding it', () => {
    render(<ReasoningBriefing reasoningStatus="done" severityAssessment={assessment} explanation={explanation} />);
    expect(screen.getByText('Evidence-based explanation')).toBeInTheDocument();
    expect(screen.getByText('Predicted coverage: 20% of crop pixels.')).toBeInTheDocument();
    expect(screen.getByText('General reference context')).toBeInTheDocument();
    expect(screen.getByTestId('briefing-severity-grade')).toHaveTextContent(assessment.formatted);
    expect(screen.getAllByRole('link', { name: 'WOAH: Foot and mouth disease' })[0]).toHaveAttribute('href', explanation.references[0].url);
  });

  it('shows the reference summary and evidence when the LLM is unavailable', () => {
    render(<ReasoningBriefing reasoningStatus="fallback" severityAssessment={assessment}
      explanation={{ ...explanation, origin: 'template' }} reasoningError="Service unavailable" />);
    expect(screen.getByRole('status')).toHaveTextContent('Reference summary');
    expect(screen.getByText('Predicted coverage: 20% of crop pixels.')).toBeInTheDocument();
    expect(screen.getByText('Veterinary review pending.')).toBeInTheDocument();
  });

  it('renders reported text as text, including markup-like user input', () => {
    const text = 'User-reported symptoms (unverified): "<img src=x onerror=alert(1)>"';
    const { container } = render(<ReasoningBriefing reasoningStatus="done" severityAssessment={assessment}
      explanation={{ ...explanation, supporting_evidence: [{ id: 'reported', text, reference_ids: [] }] }} />);
    expect(screen.getByText(text)).toBeInTheDocument();
    expect(container.querySelector('img')).toBeNull();
  });
});
