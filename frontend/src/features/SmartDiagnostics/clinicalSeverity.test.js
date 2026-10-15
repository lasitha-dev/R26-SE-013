import { describe, it, expect } from 'vitest';
import { resolveSeverity } from './clinicalSeverity';

describe('Clinical severity display', () => {
  it.each(['Mastitis', 'Foot and Mouth Disease'])('does not display image-only or LLM severity for %s', (name) => {
    const result = { disease: { name }, severity: { grade: 'Severe', source: 'composite_scoring' } };
    expect(resolveSeverity(result, { grade: 'Mild', source: 'llm_reasoning' }).grade).toBe('Unassessable');
  });
  it('preserves the existing LSD result and LLM selection', () => {
    const result = { disease: { name: 'Lumpy Skin Disease' }, severity: { grade: 'Severe' } };
    expect(resolveSeverity(result, null)).toBe(result.severity);
    const assessment = { grade: 'Moderate' };
    expect(resolveSeverity(result, assessment)).toBe(assessment);
  });
});
