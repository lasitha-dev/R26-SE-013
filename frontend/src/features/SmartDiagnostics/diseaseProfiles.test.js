import { describe, it, expect } from 'vitest';
import DISEASE_PROFILES, { getDiseaseProfile } from './diseaseProfiles';

const REQUIRED_DISEASES = [
  'Lumpy Skin Disease',
  'Foot and Mouth Disease',
  'Healthy',
  'Mastitis',
  'Dermatophilosis',
  'Pediculosis',
  'Ringworm',
];

const REQUIRED_FIELDS = [
  'severity',
  'severityColor',
  'prognosis',
  'prognosisColor',
  'rationale',
  'spatialCorrelation',
  'evidenceItems',
];

describe('diseaseProfiles', () => {
  it('contains all 7 backend disease classes', () => {
    REQUIRED_DISEASES.forEach((disease) => {
      expect(DISEASE_PROFILES).toHaveProperty(disease);
    });
  });

  it.each(REQUIRED_DISEASES)('has all required fields for "%s"', (disease) => {
    const profile = DISEASE_PROFILES[disease];
    REQUIRED_FIELDS.forEach((field) => {
      expect(profile).toHaveProperty(field);
      expect(profile[field]).toBeTruthy();
    });
  });

  it.each(REQUIRED_DISEASES)('has 3 evidence items for "%s"', (disease) => {
    const profile = DISEASE_PROFILES[disease];
    expect(Array.isArray(profile.evidenceItems)).toBe(true);
    expect(profile.evidenceItems.length).toBeGreaterThanOrEqual(3);
  });

  it('getDiseaseProfile returns correct profile for exact match', () => {
    const profile = getDiseaseProfile('Lumpy Skin Disease');
    expect(profile.severity).toBe('8.2 / High');
    expect(profile.prognosis).toBe('Recoverable');
  });

  it('getDiseaseProfile returns correct profile for case-insensitive match', () => {
    const profile = getDiseaseProfile('lumpy skin disease');
    expect(profile.severity).toBe('8.2 / High');
  });

  it('getDiseaseProfile returns Healthy for null/undefined input', () => {
    const profile = getDiseaseProfile(null);
    expect(profile.severity).toBe('0.0 / None');
    expect(profile.prognosis).toBe('Excellent');
  });

  it('getDiseaseProfile returns fallback for unknown disease', () => {
    const profile = getDiseaseProfile('Unknown Disease XYZ');
    expect(profile.prognosis).toBe('Requires Manual Assessment');
    expect(profile.evidenceItems.length).toBe(3);
    expect(profile.rationale).toContain('Unknown Disease XYZ');
  });
});
