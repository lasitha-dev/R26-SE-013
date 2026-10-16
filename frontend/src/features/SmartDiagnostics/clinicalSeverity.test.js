import { describe, it, expect } from 'vitest';
import { resolveSeverity } from './clinicalSeverity';

describe('Clinical severity display', () => {
  it.each(['Mastitis', 'Foot and Mouth Disease', 'Lumpy Skin Disease'])('displays the combined model and reasoning grade for %s', (name) => {
    const result = { disease: { name }, severity: { grade: 'Mild', source: 'visual_thresholds' } };
    const combined = { grade: 'Moderate', source: 'model_llm_reasoning', reasoning_assessment: { llm_grade: 'Severe' } };
    expect(resolveSeverity(result, combined)).toBe(combined);
    expect(resolveSeverity(result, null)).toBe(result.severity);
  });
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
  it.each(['Mastitis', 'Foot and Mouth Disease'])('uses automatic visual estimates for %s and keeps clinical grading optional', (name) => {
    const automatic = { grade: 'Moderate', source: 'visual_thresholds' };
    const result = { disease: { name }, severity: automatic };
    expect(resolveSeverity(result, null)).toBe(automatic);
    expect(resolveSeverity(result, { grade: 'Severe', source: 'llm_reasoning' })).toBe(automatic);
    const clinical = { grade: 'Mild', source: 'clinical_rules' };
    expect(resolveSeverity(result, clinical)).toBe(clinical);
  });
});
