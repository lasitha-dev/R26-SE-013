import { describe, it, expect } from 'vitest';
import {
  BASELINE_BADGE,
  describeForecastSource,
  describeProvenance,
  describeTierBasis,
  formatProbabilityInterval,
  pickOfficialRecord,
  selectOfficialRecords,
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

describe('formatProbabilityInterval', () => {
  it('formats the interval as a rounded percentage range', () => {
    expect(formatProbabilityInterval({ probability_low: 0.1234, probability_high: 0.4766, interval_level: 0.8 }))
      .toBe('80% range 12–48%');
  });

  it('is absent for records without an interval', () => {
    expect(formatProbabilityInterval({})).toBeNull();
    expect(formatProbabilityInterval(null)).toBeNull();
    expect(formatProbabilityInterval({ probability_low: 0.1, probability_high: null, interval_level: 0.8 })).toBeNull();
  });
});

describe('official record selection', () => {
  const rec = (id, extra = {}) => ({
    forecast_id: id, disease: 'FMD', district: 'Colombo', target_year: 2026, target_month: 10,
    status: 'GENERATED', generated_at: '2026-10-01T00:00:00Z', ...extra,
  });

  it('prefers a v2 record over a newer v1 record and remembers the other record id', () => {
    const picked = pickOfficialRecord([rec('v1', { generated_at: '2026-10-20T00:00:00Z' }), rec('v2', { model_version: 'x_v2.0' })]);
    expect(picked.forecast_id).toBe('v2');
    expect(picked.related_forecast_ids).toEqual(['v1']);
  });

  it('ignores superseded records and falls back to the newest', () => {
    const picked = pickOfficialRecord([rec('old', { status: 'SUPERSEDED', model_version: 'x' }), rec('a'), rec('b', { generated_at: '2026-10-05T00:00:00Z' })]);
    expect(picked.forecast_id).toBe('b');
    expect(pickOfficialRecord([rec('s', { status: 'SUPERSEDED' })])).toBeNull();
    expect(pickOfficialRecord([])).toBeNull();
  });

  it('keeps one record per disease, district and month', () => {
    const all = [
      rec('c1'), rec('c2', { model_version: 'v' }), rec('l1', { disease: 'LSD' }),
      rec('k1', { district: 'KANDY' }), rec('k2', { district: 'Kandy', model_version: 'v' }),
      rec('n1', { target_month: 11 }),
    ];
    const ids = selectOfficialRecords(all).map((r) => r.forecast_id).sort();
    expect(ids).toEqual(['c2', 'k2', 'l1', 'n1']);
  });
});

describe('describeTierBasis', () => {
  const base = { model_version: 'fmd_v2.1', forecaster: 'O', deployment_status: 'back_tested' };

  it('explains a relative HIGH and states the evidence level, without changing the tier', () => {
    const basis = describeTierBasis({ ...base, risk_level: 'HIGH', relative_risk: 9.553, baseline_probability: 0.030886, probability: 0.295 });
    expect(basis.text).toBe('HIGH because 9.6× the usual rate of 3.1% for this district and month (HIGH starts at 4×).');
    expect(basis.evidence).toMatch(/back-tested only/);
  });

  it('explains a HIGH that comes from the absolute probability', () => {
    const basis = describeTierBasis({ ...base, risk_level: 'HIGH', relative_risk: 1.5, probability: 0.6, baseline_probability: 0.4 });
    expect(basis.text).toBe('HIGH because the probability is 50% or more.');
  });

  it('explains MEDIUM and returns nothing for baseline, LOW and v1 records', () => {
    expect(describeTierBasis({ ...base, risk_level: 'MEDIUM', relative_risk: 2.4, baseline_probability: 0.1 }).text).toMatch(/MEDIUM because 2\.4×/);
    expect(describeTierBasis({ ...base, forecaster: 'climatology', deployment_status: 'baseline', risk_level: 'LOW', relative_risk: 1 })).toBeNull();
    expect(describeTierBasis({ ...base, risk_level: 'LOW', relative_risk: 1.2 })).toBeNull();
    expect(describeTierBasis({ risk_level: 'HIGH', relative_risk: 9 })).toBeNull(); // v1: no model_version
  });
});
