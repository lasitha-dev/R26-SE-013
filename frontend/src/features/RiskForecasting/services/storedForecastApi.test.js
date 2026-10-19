import { describe, it, expect, vi, afterEach } from 'vitest';
import * as workflow from './riskForecastingWorkflowApi';
import { fetchStoredDistrictRisks, STORED_FORECAST_NO_RECORD } from './storedForecastApi';

const record = (overrides) => ({
  forecast_id: 'f', district: 'Jaffna', target_year: 2026, target_month: 10, probability_pct: 20, risk_level: 'LOW',
  status: 'GENERATED', generated_at: '2026-10-13T00:00:00Z', ...overrides,
});

describe('fetchStoredDistrictRisks', () => {
  afterEach(() => vi.restoreAllMocks());

  it('prefers a v2 record, ignores superseded ones and never calls a prediction endpoint', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const list = vi.spyOn(workflow, 'listForecastRecords').mockImplementation(async ({ disease }) => ({
      records: [
        record({ forecast_id: 'v1', disease, generated_at: '2026-10-20T00:00:00Z' }),
        record({ forecast_id: 'v2', disease, model_version: 'x_v2.0', generated_at: '2026-10-01T00:00:00Z' }),
        record({ forecast_id: 'old', disease, model_version: 'x_v2.0', status: 'SUPERSEDED' }),
      ],
    }));

    const result = await fetchStoredDistrictRisks({ district: ' Jaffna ', year: 2026, month: 10 });

    expect(result.overallStatus).toBe('success');
    expect(result.fmd.data.record.forecast_id).toBe('v2');
    expect(list).toHaveBeenCalledWith(expect.objectContaining({ district: 'Jaffna', target_year: 2026, target_month: 10 }), {});
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('reports NO_RECORD, partial and error states without inventing values', async () => {
    vi.spyOn(workflow, 'listForecastRecords').mockImplementation(async ({ disease }) => (
      disease === 'FMD' ? { records: [record({ disease })] } : { records: [] }
    ));
    const partial = await fetchStoredDistrictRisks({ district: 'Jaffna', year: 2026, month: 10 });
    expect(partial.overallStatus).toBe('partial');
    expect(partial.lsd).toEqual({ status: 'error', data: null, error: { category: STORED_FORECAST_NO_RECORD } });

    vi.spyOn(workflow, 'listForecastRecords').mockRejectedValue(new Error('down'));
    const failed = await fetchStoredDistrictRisks({ district: 'Jaffna', year: 2026, month: 10 });
    expect(failed.overallStatus).toBe('error');
    expect(failed.fmd.error.message).toBe('down');
  });

  it('rejects a missing district', async () => {
    await expect(fetchStoredDistrictRisks({ district: '', year: 2026, month: 10 })).rejects.toThrow(TypeError);
  });
});
