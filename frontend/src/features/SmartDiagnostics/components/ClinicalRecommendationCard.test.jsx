import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ClinicalRecommendationCard from './ClinicalRecommendationCard';

describe('ClinicalRecommendationCard', () => {
  it('returns null when recommendation is null or undefined and not loading', () => {
    const { container } = render(<ClinicalRecommendationCard recommendation={null} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders loading skeleton when loading is true', () => {
    render(<ClinicalRecommendationCard recommendation={null} loading={true} />);
    expect(screen.getByTestId('clinical-recommendation-skeleton')).toBeInTheDocument();
  });

  it('renders recommendation with triage level, biosecurity protocols, and clinical monitoring', () => {
    const mockRec = {
      triage_level: 'Urgent',
      biosecurity_protocol: [
        'Enforce immediate physical isolation in a vector-screened pen.',
        'Sanitize animal handling equipment and footwear.'
      ],
      clinical_monitoring: [
        'Record core rectal temperature every 12 hours.',
        'Monitor daily dry-matter intake and hydration.'
      ],
      treatment_considerations: 'Administer NSAIDs under veterinary supervision for antipyresis.',
    };

    render(<ClinicalRecommendationCard recommendation={mockRec} />);

    expect(screen.getByTestId('clinical-recommendation-card')).toBeInTheDocument();
    expect(screen.getByTestId('recommendation-triage-level')).toHaveTextContent('Triage: Urgent');
    expect(screen.getByText('Biosecurity & Quarantine Protocol')).toBeInTheDocument();
    expect(screen.getByText('Enforce immediate physical isolation in a vector-screened pen.')).toBeInTheDocument();
    expect(screen.getByText('Clinical Monitoring & Surveillance')).toBeInTheDocument();
    expect(screen.getByText('Record core rectal temperature every 12 hours.')).toBeInTheDocument();
    expect(screen.getByText('Therapeutic & Supportive Considerations')).toBeInTheDocument();
    expect(screen.getByText('Administer NSAIDs under veterinary supervision for antipyresis.')).toBeInTheDocument();
  });

  it('renders Emergency triage level with emergency styling', () => {
    const mockRec = {
      triage_level: 'Emergency',
      biosecurity_protocol: ['Immediate quarantine'],
      clinical_monitoring: ['Emergency veterinary consultation'],
    };

    render(<ClinicalRecommendationCard recommendation={mockRec} />);
    const badge = screen.getByTestId('recommendation-triage-level');
    expect(badge).toHaveTextContent('Triage: Emergency');
    expect(badge.className).toContain('text-rose-300');
  });

  it('renders Routine triage level with emerald styling', () => {
    const mockRec = {
      triage_level: 'Routine',
      biosecurity_protocol: ['Maintain standard sanitary housing'],
      clinical_monitoring: ['Routine herd health observation'],
    };

    render(<ClinicalRecommendationCard recommendation={mockRec} />);
    const badge = screen.getByTestId('recommendation-triage-level');
    expect(badge).toHaveTextContent('Triage: Routine');
    expect(badge.className).toContain('text-emerald-300');
  });
});
