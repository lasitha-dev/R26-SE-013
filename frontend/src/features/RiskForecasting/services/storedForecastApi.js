/**
 * Stored-forecast reader for end users (for example farmers).
 *
 * The official forecast for a district and month is the stored forecast decision record. This reads that
 * record instead of running a model on demand, so every screen shows the same number. When no record has
 * been issued for the period it reports NO_RECORD; it never computes or invents a forecast.
 *
 * Result shape matches the combined district prediction contract used by the Farmer screen:
 *   { district, year, month, fmd|lsd: { status, data, error }, overallStatus }
 */

import { listForecastRecords } from './riskForecastingWorkflowApi';
import { isActiveRecord } from '../components/forecastPresentation';

export const STORED_FORECAST_NO_RECORD = 'NO_RECORD';

export function newestPreferringV2(records) {
  return [...records].sort((a, b) => {
    const v2 = Number(Boolean(b.model_version)) - Number(Boolean(a.model_version));
    if (v2 !== 0) return v2;
    return String(b.generated_at || '').localeCompare(String(a.generated_at || ''));
  })[0];
}

function toDiseaseResult(record) {
  return {
    status: 'success',
    data: {
      stage1: {
        probability_pct: record.probability_pct,
        risk_level: record.risk_level,
        predicted_severity: record.predicted_severity ?? null,
      },
      provenance: {
        data_quality_status: record.input_quality === 'DEGRADED' ? 'DEGRADED' : 'OK',
        fallback_applied: Boolean(record.fallback_applied),
      },
      record,
    },
    error: null,
  };
}

async function loadDisease(disease, { district, year, month }, options) {
  try {
    const response = await listForecastRecords(
      { disease, district, target_year: year, target_month: month, limit: 50 },
      options,
    );
    const active = (response?.records || []).filter(isActiveRecord);
    if (active.length === 0) {
      return { status: 'error', data: null, error: { category: STORED_FORECAST_NO_RECORD } };
    }
    return toDiseaseResult(newestPreferringV2(active));
  } catch (error) {
    return { status: 'error', data: null, error };
  }
}

export async function fetchStoredDistrictRisks({ district, year, month } = {}, options = {}) {
  if (typeof district !== 'string' || district.trim() === '') {
    throw new TypeError('Invalid district: district must be a non-empty string');
  }
  const request = { district: district.trim(), year: Number(year), month: Number(month) };
  const [fmd, lsd] = await Promise.all([
    loadDisease('FMD', request, options),
    loadDisease('LSD', request, options),
  ]);
  const successes = [fmd, lsd].filter((r) => r.status === 'success').length;
  return {
    ...request,
    fmd,
    lsd,
    overallStatus: successes === 2 ? 'success' : successes === 1 ? 'partial' : 'error',
  };
}
