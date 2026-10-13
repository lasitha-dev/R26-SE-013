import { describe, it, expect } from 'vitest';
import {
  BASELINE_BADGE,
  describeForecastSource,
  describeProvenance,
  isBaselineRecord,
} from './forecastPresentation';

const v2 = (overrides) => ({ model_version: 'fmd_v2.0', forecaster: 'A', deployment_status: 'back_tested', ...overrides });

describe('forecast source wording', () => {
  it('never calls a back-tested model "validated"', () => {
    const source = describeForecastSource(v2());
    expect(source.label).toBe('Back-tested candidate');
    expect(source.title).toMatch(/not yet been confirmed on future data/);
  });

  it('keeps exploratory and baseline distinct', () => {
    expect(describeForecastSource(v2({ forecaster: 'S', deployment_status: 'exploratory' })).label).toBe('Exploratory model');
    expect(describeForecastSource(v2({ forecaster: 'climatology', deployment_status: 'baseline' })).label).toBe('Historical baseline');
  });
});

describe('baseline records', () => {
  it('are recognised only for v2 climatology records', () => {
    expect(isBaselineRecord(v2({ forecaster: 'climatology' }))).toBe(true);
    expect(isBaselineRecord(v2())).toBe(false);
    expect(isBaselineRecord({ forecaster: 'climatology' })).toBe(false); // v1 has no model_version
    expect(isBaselineRecord(null)).toBe(false);
  });

  it('are not presented as an assessed LOW RISK tier', () => {
    expect(BASELINE_BADGE.label).toBe('BASELINE');
    expect(BASELINE_BADGE.label).not.toMatch(/LOW/);
    expect(BASELINE_BADGE.title).toMatch(/not a model forecast/);
  });
});

describe('describeProvenance', () => {
  it('does not call a v2 baseline a fallback proxy', () => {
    const record = v2({ forecaster: 'climatology', fallback_applied: true });
    expect(describeProvenance(record)).toBe('Historical baseline');
  });

  it('keeps the v1 wording', () => {
    expect(describeProvenance({ fallback_applied: true })).toBe('Fallback Proxy Applied');
    expect(describeProvenance({ fallback_applied: false })).toBe('Exact Period');
  });
});
